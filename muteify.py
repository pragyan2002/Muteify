"""
Muteify - Windows-only local ad muter for Spotify.

This implementation does NOT call the Spotify Web API.
It infers ad playback from local Spotify window metadata and
controls Spotify session volume through PyCaw.
"""

import ctypes
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


def is_spotify_running() -> bool:
    """Return True if Spotify.exe is running."""
    for proc in psutil.process_iter(["name"]):
        name = proc.info.get("name")
        if name and name.lower() == "spotify.exe":
            return True
    return False


def _spotify_pids() -> Set[int]:
    pids: Set[int] = set()
    for proc in psutil.process_iter(["pid", "name"]):
        name = proc.info.get("name")
        if name and name.lower() == "spotify.exe":
            pid = proc.info.get("pid")
            if pid:
                pids.add(int(pid))
    return pids


def _window_title_for_pid(target_pids: Set[int]) -> Optional[str]:
    """
    Return the first visible top-level window title owned by a Spotify PID.
    """
    if not _is_windows or not target_pids:
        return None

    titles: List[str] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True

        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in target_pids:
            return True

        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title:
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
    if lowered in {"spotify", "spotify premium", "spotify free"}:
        return {
            "is_ad": False,
            "title": None,
            "artists": [],
        }

    # Single-piece title fallback.
    return {
        "is_ad": False,
        "title": title,
        "artists": [],
    }


def get_spotify_metadata_local() -> Optional[dict]:
    """
    Obtain best-effort now-playing metadata from local window title.
    Returns None when Spotify isn't running or no useful title exists yet.
    """
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
    proc = session.Process
    if proc and proc.name() and proc.name().lower().startswith("spotify"):
        return True

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

def monitor_spotify() -> None:
    """
    Poll local Spotify metadata and mute ads.
    """
    print("Muteify (no Spotify API) is running... Press Ctrl+C to stop.")

    is_lowered = False
    original_volume = None
    last_seen_title = None

    while True:
        try:
            if not is_spotify_running():
                if is_lowered and original_volume is not None:
                    set_spotify_volume_all(original_volume * 100)
                    is_lowered = False
                    original_volume = None
                time.sleep(2)
                continue

            meta = get_spotify_metadata_local()
            if meta is None:
                print("No local track info yet. Retrying soon...")
                time.sleep(2)
                continue

            current_window_title = meta.get("window_title")
            if current_window_title != last_seen_title:
                print(f"Window title: {current_window_title}")
                last_seen_title = current_window_title

            if meta["is_ad"]:
                if not is_lowered:
                    current_vol = get_current_spotify_volume()
                    if current_vol >= 0.0:
                        original_volume = current_vol
                    set_spotify_volume_all(5)
                    is_lowered = True
                print("Ad inferred from local metadata. Volume lowered.")
            else:
                track_name = meta["title"]
                artists = meta["artists"]
                if track_name:
                    if artists:
                        print(f"Currently playing: {track_name} by {', '.join(artists)}")
                    else:
                        print(f"Currently playing: {track_name}")

                if is_lowered:
                    if original_volume is not None:
                        set_spotify_volume_all(original_volume * 100)
                    is_lowered = False
                    original_volume = None
                    print("Ad ended (inferred). Volume restored.")

        except KeyboardInterrupt:
            print("\nStopping Muteify...")
            break
        except Exception as exc:
            print("Error in main loop:", exc)

        time.sleep(1)


if __name__ == "__main__":
    monitor_spotify()
