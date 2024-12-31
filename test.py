# test_set_volume.py
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume

def set_spotify_volume(volume_percent):
    from ctypes import POINTER, cast
    import psutil

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        proc = session.Process
        if proc and proc.name() and proc.name().lower() == 'spotify.exe':
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            volume.SetMasterVolume(volume_percent / 100.0, None)
            return True
    return False

if __name__ == "__main__":
    success = set_spotify_volume(5)  # or 0 to "mute"
    print("Set volume success:", success)
