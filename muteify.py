import psutil
import time
import requests

def is_spotify_running() -> bool:
    """
    Check if Spotify.exe is running.
    Returns True if found, otherwise False.
    """
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == "spotify.exe":
            return True
    return False

def get_spotify_metadata():
    return

def get_current_volume():
    return 

def set_spotify_volume():
    return

if __name__ == "__main__":
    print("Test is_spotify_running()...")
    print("Is Spotify running: ", is_spotify_running())