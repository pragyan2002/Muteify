"""
auth_flow.py

A minimal Flask application that implements the Spotify Authorization Code Flow.
- Redirects user to Spotify to grant permissions.
- Receives the authorization code in /callback.
- Exchanges code for access_token & refresh_token.
- Saves tokens to tokens.txt.

Usage:
1) Set your environment variables in a .env or system env:
   SPOTIFY_CLIENT_ID=<your-client-id>
   SPOTIFY_CLIENT_SECRET=<your-client-secret>
   SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

2) Run: python auth_flow.py
3) In your browser, go to http://localhost:8888/callback
4) Log in to Spotify and authorize the app.
5) On success, tokens are written to tokens.txt
"""

import os
import requests
from flask import Flask, request, redirect
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env if present

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

app = Flask(__name__)

# The scopes your app needs. Adjust as required, for example:
#  - user-read-currently-playing
#  - user-read-playback-state
# If you want to detect ads, you likely need user-read-playback-state (which includes
# info about what's currently playing).
SPOTIFY_SCOPES = [
    "user-read-currently-playing",
    "user-read-playback-state",
]

@app.route("/")
def homepage():
    """
    Step 1: Redirect user to Spotify's /authorize endpoint with your Client ID,
    redirect_uri, and desired scopes.
    """
    scope_str = "%20".join(SPOTIFY_SCOPES)
    authorize_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={SPOTIFY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={scope_str}"
    )
    return redirect(authorize_url)


@app.route("/callback")
def callback():
    """
    Step 2: Spotify redirects here with `code` and possibly `state` (if used).
    We exchange `code` for an access_token + refresh_token.
    """
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return f"Error: {error}", 400
    if not code:
        return "Missing authorization code.", 400

    # Step 3: Exchange authorization code for tokens at /api/token
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    r = requests.post(token_url, data=data)
    if r.status_code != 200:
        return f"Failed to get token: {r.text}", r.status_code

    tokens = r.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # Step 4: Save tokens to a file (for your main script to use).
    # In production, you'd typically store these more securely (e.g., DB).
    with open("tokens.txt", "w") as f:
        f.write(f"ACCESS_TOKEN={access_token}\n")
        if refresh_token:
            f.write(f"REFRESH_TOKEN={refresh_token}\n")

    return (
        "Authorization successful! Tokens saved to tokens.txt. "
        "You can close this window now."
    )


if __name__ == "__main__":
    # Run the Flask dev server. 
    # Default port is 8888, so our redirect URI is http://127.0.0.1:8888/callback
    print("Starting auth server on http://127.0.0.1:8888 ...")
    app.run(debug=True, host="127.0.0.1", port=8888)