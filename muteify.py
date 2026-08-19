"""
Muteify - Windows-only local ad muter for Spotify.

This implementation does NOT call the Spotify Web API.
It infers ad playback from local Spotify window metadata and
controls Spotify session volume through PyCaw.
"""

import ctypes
import os
import sys
import time
from ctypes import wintypes
from typing import Iterable, List, Optional, Set

import psutil
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

# ---------------------------------------------------------------------------
# Win32 window helpers (no Spotify API required)
# ---------------------------------------------------------------------------

_is_windows = hasattr(ctypes, "windll")

if _is_windows:
    _user32 = ctypes.windll.user32
else:
    _user32 = None


_instance_mutex = None


def _acquire_single_instance() -> bool:
    """Prevent a manual launch and the scheduled task from running twice."""
    global _instance_mutex
    if not _is_windows:
        return True

    # use_last_error=True keeps the error code in a ctypes-private slot, so it
    # survives any Win32 call the interpreter makes before we read it. Reading
    # kernel32.GetLastError() separately can return a value from an unrelated
    # call and make Muteify exit at logon thinking a copy is already running.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    mutex_name = "Local\\MuteifySpotifyAdMuter"
    _instance_mutex = kernel32.CreateMutexW(None, False, mutex_name)
    if not _instance_mutex:
        return False

    # ERROR_ALREADY_EXISTS means another Muteify process owns this mutex.
    return ctypes.get_last_error() != 183


def _spotify_pids() -> Set[int]:
    pids: Set[int] = set()
    for proc in psutil.process_iter(["pid", "name"]):
        name = proc.info.get("name")
        if name and name.lower() == "spotify.exe":
            pid = proc.info.get("pid")
            if pid:
                pids.add(int(pid))
    return pids


# Spotify's now-playing title lives on its Chromium window. The same process
# also owns helper windows ("Default IME", "GDI+ Window (Spotify.exe)", ...)
# whose titles are constant noise.
_SPOTIFY_MAIN_WINDOW_CLASS = "Chrome_WidgetWin_"


# Rediscovery walks every running process, which measured at ~4 ms per call on
# a machine with ~300 processes. Doing that once per second was ~80% of
# Muteify's CPU time, so the main window handle is cached and rediscovery only
# runs when that handle goes away (Spotify started, closed, or restarted).
_cached_window = None  # (hwnd, pid) or None


def _read_window_text(hwnd: int) -> Optional[str]:
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return None
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip() or None


def _cached_window_title() -> Optional[str]:
    """Read the title straight off the cached handle, or None if it is stale."""
    if _cached_window is None:
        return None
    hwnd, pid = _cached_window
    if not _user32.IsWindow(hwnd):
        return None
    # Guard against Windows recycling the handle into another process.
    current_pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(current_pid))
    if current_pid.value != pid:
        return None
    return _read_window_text(hwnd)


def _window_title_for_pid(target_pids: Set[int]) -> Optional[str]:
    """
    Return the now-playing title from Spotify's main window.

    Deliberately does NOT require IsWindowVisible. Spotify autostarts as
    "Spotify.exe --autostart --minimized" and hides its window in the tray;
    the window is then invisible while its title still tracks playback.
    Filtering on visibility is why ad muting never engaged for a Spotify that
    was launched at logon.
    """
    if not _is_windows or not target_pids:
        return None

    titles: List[str] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in target_pids:
            return True

        class_buffer = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, class_buffer, 256)
        if not class_buffer.value.startswith(_SPOTIFY_MAIN_WINDOW_CLASS):
            return True

        title = _read_window_text(hwnd)
        if title:
            global _cached_window
            _cached_window = (hwnd, pid.value)
            titles.append(title)
            # Found a useful title, stop enumeration.
            return False

        return True

    _user32.EnumWindows(EnumWindowsProc(callback), 0)

    if not titles:
        return None
    return titles[0]


def _parse_spotify_window_title(title: str) -> dict:
    """
    Parse Spotify window title to infer track/ad state.

    Common patterns:
    - "Song Name • Artist"
    - "Song Name - Artist"
    - "Advertisement"
    - "Spotify"
    """
    lowered = title.lower().strip()

    ad_keywords = {
        "advertisement",
        "spotify advertisement",
        "spotify ad",
        "ad",
    }

    if lowered in ad_keywords or "advertisement" in lowered:
        return {
            "is_ad": True,
            "title": title,
            "artists": [],
        }

    # Best-effort title parsing for "title • artist" or "title - artist"
    for separator in (" • ", " - "):
        if separator in title:
            left, right = title.split(separator, 1)
            track = left.strip()
            artist = right.strip()
            if track and artist:
                return {
                    "is_ad": False,
                    "title": track,
                    "artists": [artist],
                }

    # Unknown/non-track states often show just "Spotify" or single labels.
    # Spotify titles its window with a bare dash while paused or stopped, which
    # the single-piece fallback below would otherwise read as an ad and drop the
    # volume to 5% every time playback is paused.
    if lowered in {"spotify", "spotify premium", "spotify free", "-", "–", "—"}:
        return {
            "is_ad": False,
            "title": None,
            "artists": [],
        }

    # Single-piece title fallback:
    # In local metadata mode, ads commonly appear as a lone phrase with no artist.
    # Treat this as ad-like by default so volume lowering still triggers.
    return {
        "is_ad": True,
        "title": title,
        "artists": [],
    }


def get_spotify_metadata_local() -> Optional[dict]:
    """
    Obtain best-effort now-playing metadata from local window title.
    Returns None when Spotify isn't running or no useful title exists yet.
    """
    window_title = _cached_window_title()
    if not window_title:
        # Cache miss: Spotify just started, closed, or replaced its window.
        pids = _spotify_pids()
        if not pids:
            return None
        window_title = _window_title_for_pid(pids)
    if not window_title:
        return None

    parsed = _parse_spotify_window_title(window_title)
    return {
        "is_ad": parsed["is_ad"],
        "title": parsed["title"],
        "artists": parsed["artists"],
        "window_title": window_title,
    }


# ---------------------------------------------------------------------------
# Volume control helpers
# ---------------------------------------------------------------------------

def _is_spotify_session(session) -> bool:
    """
    Return True for sessions that belong to Spotify,
    including some orphaned sessions with no Process object.
    """
    try:
        proc = session.Process
        if proc and (proc.name() or "").lower().startswith("spotify"):
            return True
    except Exception:
        # psutil raises NoSuchProcess for sessions whose process already exited.
        # Audio sessions churn constantly right after logon, and letting that
        # escape used to kill an entire poll cycle.
        pass

    try:
        if "spotify" in (session._ctl.GetDisplayName() or "").lower():
            return True
        if "spotify" in (session.InstanceIdentifier or "").lower():
            return True
    except Exception:
        pass

    return False


def set_spotify_volume_all(volume_percent: float) -> bool:
    """
    Set all Spotify audio sessions to volume_percent (0-100).
    Returns True if at least one session was updated.
    """
    volume_percent = max(0.0, min(100.0, volume_percent))
    desired = volume_percent / 100.0

    success = False
    for session in AudioUtilities.GetAllSessions():
        if _is_spotify_session(session):
            try:
                session._ctl.QueryInterface(ISimpleAudioVolume).SetMasterVolume(desired, None)
                success = True
            except Exception as exc:
                print(f"[Muteify] Couldn't set volume for a Spotify session: {exc}")
    return success


def get_current_spotify_volume() -> float:
    """
    Return highest volume across all Spotify sessions, or -1.0 if none.
    """
    volumes: Iterable[float] = [
        session._ctl.QueryInterface(ISimpleAudioVolume).GetMasterVolume()
        for session in AudioUtilities.GetAllSessions()
        if _is_spotify_session(session)
    ]
    return max(volumes) if volumes else -1.0


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

# Ads are inferred from a window title, so polling is the only option. These
# intervals trade detection latency against wakeups: while Spotify plays, a
# poll is two syscalls against the cached handle, so 1s is effectively free.
# While Spotify is closed every poll pays a full process scan, so back off.
POLL_SECONDS = 1.0
IDLE_POLL_SECONDS = 5.0


def monitor_spotify() -> None:
    """
    Poll local Spotify metadata and mute ads.
    """
    print("Muteify (no Spotify API) is running... Press Ctrl+C to stop.")

    is_lowered = False
    original_volume = None
    last_seen_title = None
    last_printed_track = None

    while True:
        try:
            meta = get_spotify_metadata_local()
            if meta is None:
                # Spotify is closed, or has not put up its window yet.
                if is_lowered:
                    set_spotify_volume_all((original_volume or 1.0) * 100)
                    is_lowered = False
                    original_volume = None
                if last_seen_title is not None:
                    print("Spotify window gone. Waiting for it to come back...")
                    last_seen_title = None
                    last_printed_track = None
                time.sleep(IDLE_POLL_SECONDS)
                continue

            current_window_title = meta.get("window_title")
            if current_window_title != last_seen_title:
                print(f"Window title: {current_window_title}")
                last_seen_title = current_window_title

            if meta["is_ad"]:
                last_printed_track = None
                if not is_lowered:
                    # Spotify only owns an audio session once it has played
                    # sound. At a cold logon start the ad title appears before
                    # that session exists, so latching is_lowered here used to
                    # let the whole first ad play at full volume.
                    current_vol = get_current_spotify_volume()
                    if set_spotify_volume_all(5):
                        original_volume = current_vol if current_vol >= 0.0 else 1.0
                        is_lowered = True
                        print("Ad inferred from local metadata. Volume lowered.")
            else:
                track_name = meta["title"]
                artists = meta["artists"]
                if track_name:
                    track_key = (track_name, tuple(artists))
                    if track_key == last_printed_track:
                        time.sleep(POLL_SECONDS)
                        continue
                    if artists:
                        print(f"Currently playing: {track_name} by {', '.join(artists)}")
                    else:
                        print(f"Currently playing: {track_name}")
                    last_printed_track = track_key

                if is_lowered:
                    # original_volume defaults to full rather than None so a
                    # failed capture can never strand Spotify at 5%.
                    if set_spotify_volume_all((original_volume or 1.0) * 100):
                        is_lowered = False
                        original_volume = None
                        print("Ad ended (inferred). Volume restored.")

        except KeyboardInterrupt:
            print("\nStopping Muteify...")
            break
        except Exception as exc:
            print("Error in main loop:", exc)

        time.sleep(POLL_SECONDS)


def _redirect_output_to_log() -> None:
    """
    pythonw.exe (used by the scheduled task) leaves sys.stdout as None, and
    print() silently discards everything. Without this there is no way to tell
    a logon-start failure from a detection failure.
    """
    if sys.stdout is not None:
        return
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "muteify.log")
    # ponytail: truncate per run instead of rotating; prints are already
    # deduplicated per track, so one session's log stays small. Swap in
    # logging.handlers.RotatingFileHandler if that stops being true.
    stream = open(log_path, "w", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream


if __name__ == "__main__":
    _redirect_output_to_log()
    if _acquire_single_instance():
        monitor_spotify()
    else:
        print("Another Muteify instance is already running. Exiting.")
