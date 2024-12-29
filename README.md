# Spotify Ad-blocker
The main premise of this is for the application to be able to reduce the volume of the music playing when Spotify plays an advertisement for the user, and then restore the old volume once the ad stops playing.
## Flow
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
