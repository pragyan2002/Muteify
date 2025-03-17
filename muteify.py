"""
Muteify - A Windows-based script to detect if Spotify is playing advertisements
and automatically lower the volume. Uses the Spotify Web API + OAuth tokens for ad detection.
"""

import os
import time
import psutil
import requests

# PyCaw imports
from ctypes import POINTER, cast
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

from dotenv import load_dotenv
load_dotenv()

###############################################################################
# 1) TOKEN MANAGEMENT HELPERS
###############################################################################

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "YOUR_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

TOKEN_FILE = "tokens.txt"

def load_tokens_from_file():
    """
    Reads ACCESS_TOKEN and REFRESH_TOKEN from a local 'tokens.txt' file.
    Returns (access_token, refresh_token).
    """
    access_token = None
    refresh_token = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            for line in f:
                if line.startswith("ACCESS_TOKEN"):
                    access_token = line.split("=")[1].strip()
                elif line.startswith("REFRESH_TOKEN"):
                    refresh_token = line.split("=")[1].strip()
    return access_token, refresh_token


def save_tokens_to_file(access_token, refresh_token):
    """
    Saves ACCESS_TOKEN and REFRESH_TOKEN to 'tokens.txt'.
    Overwrites any existing tokens.
    """
    with open(TOKEN_FILE, "w") as f:
        f.write(f"ACCESS_TOKEN={access_token}\n")
        f.write(f"REFRESH_TOKEN={refresh_token}\n")


def refresh_access_token(refresh_token):
    """
    Uses the Spotify API to exchange a refresh_token for a new access_token.
    Returns (new_access_token, new_refresh_token) or (None, None) on failure.
    """
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    response = requests.post(url, data=data)

    if response.status_code == 200:
        json_data = response.json()
        new_access_token = json_data.get("access_token")
        # Spotify might or might not return a new refresh token
        new_refresh_token = json_data.get("refresh_token", refresh_token)
        return new_access_token, new_refresh_token
    else:
        print("Error refreshing token:", response.text)
        return None, None


###############################################################################
# 2) CORE FUNCTIONS
###############################################################################

def is_spotify_running() -> bool:
    """
    Check if 'Spotify.exe' is running on Windows.
    Returns True if found, otherwise False.
    """
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == 'spotify.exe':
            #print("Spotify session found!")
            return True
    return False


def get_spotify_metadata() -> dict:
    """
    Returns a dict that might look like:
    {
      "is_ad": bool,
      "title": str or None,
      "artists": [str],
      "duration_ms": int or 0,
      "progress_ms": int or 0,
      "track_id": str or None
    }
    or None if we truly cannot get any info at all (e.g., error, offline).
    """
    access_token, refresh_token = load_tokens_from_file()
    if not access_token:
        print("No access token found. Please run auth flow.")
        return None

    url = "https://api.spotify.com/v1/me/player/currently-playing"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 204:
            # 204 means no content — maybe user is paused or no track info
            return None
        if resp.status_code == 401:
            new_access_token, new_refresh_token = refresh_access_token(refresh_token)
            if not new_access_token:
                print("Token refresh failed.")
                return None
            # Save new tokens
            save_tokens_to_file(new_access_token, new_refresh_token)
            
            # Attempt the request again with the new token
            headers = {"Authorization": f"Bearer {new_access_token}"}
            resp = requests.get(url, headers=headers, timeout=5)

        if resp.status_code != 200:
            print("Error status:", resp.status_code)
            return None

        data = resp.json()
        if not data:
            return None

        # Extract the basic fields
        currently_playing_type = data.get("currently_playing_type")
        is_ad = (currently_playing_type == "ad")

        # "item" may be None if it's an ad
        item = data.get("item")
        track_name = item.get("name") if item else None
        track_id = item.get("id") if item else None
        duration_ms = item.get("duration_ms") if item else 0

        progress_ms = data.get("progress_ms", 0)

        return {
            "is_ad": is_ad,
            "title": track_name,
            "artists": [artist["name"] for artist in item["artists"]] if item and "artists" in item else [],
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "track_id": track_id
        }

    except requests.exceptions.RequestException as e:
        print("Request error:", e)
        return None



def get_current_volume() -> float:
    """
    Returns Spotify's current volume (0.0 - 1.0).
    If Spotify is not found, returns -1.0.
    """
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        proc = session.Process
        if proc and proc.name() and proc.name().lower() == 'spotify.exe':
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            return volume.GetMasterVolume()
    return -1.0


def is_spotify_running() -> bool:
    """
    Check if 'Spotify.exe' is running on Windows.
    Returns True if found, otherwise False.
    """
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] and proc.info['name'].lower() == 'spotify.exe':
            #print("Spotify session found!")
            return True
    return False


def get_spotify_metadata() -> dict:
    """
    Returns a dict that might look like:
    {
      "is_ad": bool,
      "title": str or None,
      "artists": [str],
      "duration_ms": int or 0,
      "progress_ms": int or 0,
      "track_id": str or None
    }
    or None if we truly cannot get any info at all (e.g., error, offline).
    """
    access_token, refresh_token = load_tokens_from_file()
    if not access_token:
        print("No access token found. Please run auth flow.")
        return None

    url = "https://api.spotify.com/v1/me/player/currently-playing"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 204:
            # 204 means no content — maybe user is paused or no track info
            return None
        if resp.status_code == 401:
            new_access_token, new_refresh_token = refresh_access_token(refresh_token)
            if not new_access_token:
                print("Token refresh failed.")
                return None
            # Save new tokens
            save_tokens_to_file(new_access_token, new_refresh_token)
            
            # Attempt the request again with the new token
            headers = {"Authorization": f"Bearer {new_access_token}"}
            resp = requests.get(url, headers=headers, timeout=5)

        if resp.status_code != 200:
            print("Error status:", resp.status_code)
            return None

        data = resp.json()
        if not data:
            return None

        # Extract the basic fields
        currently_playing_type = data.get("currently_playing_type")
        is_ad = (currently_playing_type == "ad")

        # "item" may be None if it's an ad
        item = data.get("item")
        track_name = item.get("name") if item else None
        track_id = item.get("id") if item else None
        duration_ms = item.get("duration_ms") if item else 0

        progress_ms = data.get("progress_ms", 0)

        return {
            "is_ad": is_ad,
            "title": track_name,
            "artists": [artist["name"] for artist in item["artists"]] if item and "artists" in item else [],
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "track_id": track_id
        }

    except requests.exceptions.RequestException as e:
        print("Request error:", e)
        return None



def get_current_volume() -> float:
    """
    Returns Spotify's current volume (0.0 - 1.0).
    If Spotify is not found, returns -1.0.
    """
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        proc = session.Process
        if proc and proc.name() and proc.name().lower() == 'spotify.exe':
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            return volume.GetMasterVolume()
    return -1.0


def set_spotify_volume(volume_percent: float) -> bool:
    """
    Sets Spotify's volume to volume_percent (0.0 - 100.0).
    Returns True if successful, False otherwise.
    """
    volume_percent = max(0.0, min(100.0, volume_percent))
    desired_volume = volume_percent / 100.0

    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        proc = session.Process
        if proc and proc.name() and proc.name().lower() == 'spotify.exe':
            volume = session._ctl.QueryInterface(ISimpleAudioVolume)
            volume.SetMasterVolume(desired_volume, None)
            return True
    return False


###############################################################################
# 3) MAIN MONITORING LOGIC
###############################################################################

def monitor_spotify():
    """
    Monitor Spotify for ads via the Web API metadata. If an ad is detected,
    lower volume to 5%. When normal track resumes, restore previous volume.
    """
    print("Muteify is running... Press Ctrl+C to stop.")
    is_lowered = False
    original_volume = None

    while True:
        try:
            meta = get_spotify_metadata()
            if meta is None:
                # Maybe user paused or there's an error
                print("No track info. Retrying soon...")
                time.sleep(2)
                continue

            if meta["is_ad"]:
                print("Ad is playing!")
                if not is_lowered:
                    current_vol = get_current_volume()
                    if current_vol >= 0.0:
                        original_volume = current_vol
                    set_spotify_volume(5)  # 5% volume
                    is_lowered = True
            else:
                track_name = meta["title"]
                artists = meta["artists"]
                print(f"Currently playing: {track_name} by {', '.join(artists)}")
                if is_lowered:
                    if original_volume is not None:
                        set_spotify_volume(original_volume * 100)
                    is_lowered = False
                    original_volume = None

        except KeyboardInterrupt:
            print("\nStopping Muteify...")
            break
        except Exception as e:
            # Catch unforeseen errors to keep script running
            print("Error in main loop:", e)

        time.sleep(1)


###############################################################################
# 4) ENTRY POINT
###############################################################################

if __name__ == "__main__":
    monitor_spotify()