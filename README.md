# Muteify

Muteify is a Windows-only Python utility that lowers Spotify's volume while a
local Spotify window title appears to indicate an advertisement, then restores
the previous volume when normal playback resumes.

It uses the desktop Spotify window title and Windows audio sessions through
PyCaw. It does not use the Spotify Web API, OAuth, network requests, tokens, or
a Spotify Developer application.

## Requirements

- Windows 10 or Windows 11
- Python 3.8 or newer
- The Spotify desktop application (browser playback is not supported)
- A free Spotify account if you want to handle advertisements

## Installation

From the project directory, create the virtual environment and install the two
runtime dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run manually

```powershell
.venv\Scripts\python.exe muteify.py
```

Muteify checks Spotify's process and visible window title periodically. When
an ad is inferred, Spotify volume is reduced to 5%; when a track is detected,
the saved volume is restored. Press `Ctrl+C` to stop a manual run.

## Start automatically

The recommended setup uses a per-user Windows Scheduled Task:

```powershell
.\install_autostart.ps1
```

The task starts Muteify once at logon with `pythonw.exe`, so it does not open a
console window. Muteify waits efficiently while Spotify is closed and begins
handling it as soon as it starts. A named Windows mutex prevents duplicate
instances if Muteify is also started manually.

Remove the task with:

```powershell
.\uninstall_autostart.ps1
```

If PowerShell blocks local scripts, run the installer explicitly with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

## Project files

- `muteify.py` — main ad-detection and volume-control program.
- `install_autostart.ps1` — registers the background Scheduled Task.
- `uninstall_autostart.ps1` — removes that task.
- `requirements.txt` — runtime Python dependencies.

The old Spotify Web API authorization flow was removed because the current
implementation is entirely local. Existing `.env` and `tokens.txt` files are
ignored local files and are not needed by Muteify; they were left untouched so
any personal credentials or tokens are not accidentally deleted.

## Limitations

- Spotify can change its window-title format, which may affect detection.
- Only visible desktop window metadata is used; some Spotify states may not
  expose useful title information.
- This project changes local playback volume only and does not block ads.
- Use it in accordance with Spotify's terms and applicable laws.

## License / attribution

Muteify relies on [PyCaw](https://github.com/AndreMiras/pycaw) for Windows audio
session control and [psutil](https://github.com/giampaolo/psutil) for process
detection.
