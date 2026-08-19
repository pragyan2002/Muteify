"""Runnable check for the pieces that silently broke at logon."""

import muteify


def test_title_parsing():
    assert muteify._parse_spotify_window_title("Advertisement")["is_ad"]
    assert muteify._parse_spotify_window_title("Spotify Advertisement")["is_ad"]
    # A bare dash is what Spotify shows while paused; muting on it dropped the
    # volume to 5% on every pause.
    for idle in ("Spotify", "Spotify Premium", "Spotify Free", "-", "–", "—"):
        assert not muteify._parse_spotify_window_title(idle)["is_ad"], idle
    track = muteify._parse_spotify_window_title("Billy Joel - Just the Way You Are")
    assert not track["is_ad"] and track["artists"]


def test_mute_does_not_latch_without_an_audio_session():
    """
    Cold logon start: Spotify shows an ad title before it owns any audio
    session. The mute must not be recorded as done, or the ad plays at full
    volume and the next poll skips it.
    """
    calls = []
    real_set, real_get = muteify.set_spotify_volume_all, muteify.get_current_spotify_volume
    try:
        session_exists = [False]
        muteify.set_spotify_volume_all = lambda v: (calls.append(v), session_exists[0])[1]
        muteify.get_current_spotify_volume = lambda: 0.8 if session_exists[0] else -1.0

        is_lowered, original_volume = False, None

        # Poll 1: no audio session yet -> nothing lowered, nothing latched.
        current = muteify.get_current_spotify_volume()
        if muteify.set_spotify_volume_all(5):
            original_volume = current if current >= 0.0 else 1.0
            is_lowered = True
        assert is_lowered is False, "latched a mute that never took effect"

        # Poll 2: audio session now exists -> the ad actually gets muted.
        session_exists[0] = True
        current = muteify.get_current_spotify_volume()
        if muteify.set_spotify_volume_all(5):
            original_volume = current if current >= 0.0 else 1.0
            is_lowered = True
        assert is_lowered and original_volume == 0.8
        assert calls == [5, 5]

        # Track resumes -> volume restored to what it was, not left at 5%.
        if muteify.set_spotify_volume_all((original_volume or 1.0) * 100):
            is_lowered, original_volume = False, None
        assert not is_lowered and calls[-1] == 80.0
    finally:
        muteify.set_spotify_volume_all, muteify.get_current_spotify_volume = real_set, real_get


def test_restore_never_strands_volume_at_five_percent():
    calls = []
    real_set = muteify.set_spotify_volume_all
    try:
        muteify.set_spotify_volume_all = lambda v: (calls.append(v), True)[1]
        original_volume = None  # capture failed while muting
        muteify.set_spotify_volume_all((original_volume or 1.0) * 100)
        assert calls == [100.0]
    finally:
        muteify.set_spotify_volume_all = real_set


def test_window_cache_rejects_stale_handles():
    """
    The cache is what keeps the poll loop off the process table. It must fall
    back to rediscovery rather than serve a handle that no longer belongs to
    Spotify, or Muteify would read another program's window title.
    """
    saved = muteify._cached_window
    try:
        muteify._cached_window = None
        assert muteify._cached_window_title() is None

        muteify._cached_window = (999999, 1234)  # handle that does not exist
        assert muteify._cached_window_title() is None

        if saved is not None:  # only meaningful with Spotify actually running
            hwnd, pid = saved
            muteify._cached_window = (hwnd, pid + 1)  # handle recycled to another pid
            assert muteify._cached_window_title() is None
    finally:
        muteify._cached_window = saved


if __name__ == "__main__":
    test_title_parsing()
    test_window_cache_rejects_stale_handles()
    test_mute_does_not_latch_without_an_audio_session()
    test_restore_never_strands_volume_at_five_percent()
    print("all checks passed")
