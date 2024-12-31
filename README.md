# Mutify
Muteify is a Python-based, Windows-only script that detects advertisements on the free version of Spotify and automatically lowers (or mutes) the volume while ads play. Once the ad ends, the script restores the original volume seamlessly. It uses the Spotify Web API to detect ads and the PyCaw library to control audio sessions on Windows.
## Table of Contents

1. [Features](#features)
2. [How It Works](#how-it-works)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Authorization Code Flow](#authorization-code-flow)
7. [Troubleshooting](#troubleshooting)
8. [Limitations and Disclaimer](#limitations-and-disclaimer)
9. [Acknowledgments](#acknowledgments)

---

## Features

- **Automatic Volume Reduction**: When an ad is detected, volume is lowered to a user-defined level (e.g., 5%).
- **Auto-Restore Volume**: When the music track returns, the script restores your original volume.
- **Track Metadata Display**: (Optional) Prints the name and artist of the currently playing track in the console.
- **Smart Polling** (if implemented): Reduces the frequency of Spotify API calls by intelligently timing requests near track boundaries.

---

## How It Works

- **Lightweight Service / WMI Event**
    - Subscribes to Windows events for when `Spotify.exe` starts or stops.
    - When Spotify starts, spawn your “ad-muting” logic.
    - When Spotify stops, kill or shut down that logic.
- **Event-Driven Track Changes**
    - Within your ad-muting logic, either:
        - (A) Poll the Web API at a slower rate (e.g., every 5 seconds) until you detect a track change.
        - (B) Or if you can find a local event or semi-official approach that notifies on track changes, rely on that to trigger a single Web API call for metadata.
    - This means you’re not hammering the Web API every second. You only check metadata when the user’s track changes or at a minimal fallback interval.
- **Adjust Volume**
    - Once you know it’s an ad, set volume to 0% (or 5%) via PyCaw.
    - Once you know it’s back to a normal track, restore the volume.
    - Keep track of the volume state in memory so you don’t do repeated volume sets when nothing has changed.

---

## Requirements

- **Windows 10 or 11** (PyCaw does not support Linux/macOS).
- **Python 3.8+**
- **Spotify Desktop Client** (not web/Chrome-based playback).
- A **Spotify Developer Account** to create a client app for the Web API.
- A **free** Spotify account. (Ads only appear on free accounts.)

### Python Packages

- [**psutil**](https://pypi.org/project/psutil/)
- [**pycaw**](https://pypi.org/project/pycaw/)
- [**requests**](https://pypi.org/project/requests/)
- [**python-dotenv**](https://pypi.org/project/python-dotenv/) (optional, for environment variable loading)
- [**Flask**](https://pypi.org/project/Flask/) (optional, if you use the provided Authorization Code Flow server)

---

## Installation

1. **Clone or Download** this repository.
2. **Install Dependencies** (from a virtual environment recommended):

If you don’t have a `requirements.txt`, manually install:
    
    ```bash
    pip install -r requirements.txt
    
    ```
    
    ```bash
    pip install psutil pycaw requests python-dotenv flask
    
    ```
    
3. **Configure** your environment variables:
    - You’ll need `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REDIRECT_URI` if you haven’t already completed the OAuth setup.
    - Or supply them in a local `.env` file.

---

## Usage

1. **Obtain Tokens**
    - If you haven’t already authorized the script to access your Spotify account, run the provided `auth_flow.py` (or equivalent) to generate `tokens.txt`.
    - You’ll log in via Spotify’s authorization page, and tokens (access + refresh) are saved locally.
2. **Run Muteify**
    
    ```bash
    python muteify.py
    
    ```
    
    - You should see:
        
        ```
        Muteify is running... Press Ctrl+C to stop.
        
        ```
        
    - If you’re printing track metadata, you’ll see something like:
        
        ```
        Currently playing: Song Title by Artist
        
        ```
        
    - When an ad is detected, volume is lowered.
3. **Stop the Script**
    - Press `Ctrl+C` in your terminal to gracefully exit.

---

## Authorization Code Flow

- **Purpose**: The Spotify Web API requires OAuth tokens to access user-specific data (like “currently playing” info).
- **Workflow**:
    1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) and create an application.
    2. Retrieve **Client ID** and **Client Secret**.
    3. Set a **Redirect URI** (e.g., `http://127.0.0.1:8888/callback`) in the app settings.
    4. **Run** the local Flask server (`auth_flow.py`) included in the project. This script:
        - Launches a minimal Flask app at `http://127.0.0.1:8888/`.
        - Redirects you to Spotify’s login page for authorization.
        - Receives the authorization code in `/callback`.
        - Exchanges it for `ACCESS_TOKEN` and `REFRESH_TOKEN`.
        - Saves them into `tokens.txt`.
    5. **Muteify** loads `tokens.txt` on startup, refreshes tokens if needed, and calls the Spotify API with `Bearer <ACCESS_TOKEN>`.

---

## Troubleshooting

1. **No tokens.txt or “Failed to open page”**
    - Make sure the Flask auth server (`auth_flow.py`) actually started.
    - Confirm you’re opening the correct port in your browser (e.g., `http://127.0.0.1:8888`).
2. **No Spotify audio session**
    - Verify Spotify is actually playing a track so it appears in the Windows Volume Mixer.
    - Confirm you’re running Python on Windows (not WSL).
3. **Script Doesn’t Lower Volume**
    - Add debug prints to `set_spotify_volume()` to see if it finds `Spotify.exe`.
    - Check if your Spotify process is named differently (e.g., “SpotifyMigrated.exe”) in Task Manager.
4. **Access Token Expires**
    - Check for a `401 Unauthorized` in your logs.
    - Ensure the `refresh_access_token(...)` logic is implemented, and `save_tokens_to_file(...)` updates tokens.txt.
5. **Timeout or Network Issues**
    - Increase `timeout=5` to `timeout=10` in the `requests.get(...)` calls if you have a slow connection.
    - Wrap in `try/except requests.exceptions.Timeout` to handle gracefully.

---

## Limitations and Disclaimer

- **Educational/Personal Use**: This script is intended for **personal** ad-volume reduction.
- **No Guarantee**: There is no guarantee that this script abides by Spotify’s Terms of Service or will continue to function if Spotify changes how ads are delivered.
- **Windows-Only**: PyCaw does not work on Linux or macOS.
- **Free vs. Premium**: If you have a premium account, you won’t see ads. The script will still run but won’t need to lower volume.

---

## Acknowledgments

- [Spotify Web API](https://developer.spotify.com/documentation/web-api/) for track metadata.
- [PyCaw](https://github.com/AndreMiras/pycaw) for Windows audio session control.
- [psutil](https://github.com/giampaolo/psutil) for process checks (detecting Spotify.exe).
- [Flask](https://github.com/pallets/flask) for the local auth server.
- [python-dotenv](https://github.com/theskumar/python-dotenv) for easy `.env` variable management.

---

**Thank you for using Muteify!**

If you have any questions or run into issues, please open a GitHub issue or reach out with your feedback. Feel free to fork and modify to fit your specific needs. Enjoy ad-free (or ad-lowered) listening!
