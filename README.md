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

The setup adds a shortcut to your per-user Startup folder:

```powershell
.\install_autostart.ps1
```

It starts Muteify at logon with `pythonw.exe`, so no console window appears.
Muteify waits while Spotify is closed and begins handling it as soon as it
starts. A named Windows mutex prevents duplicate instances if Muteify is also
started manually.

Because `pythonw.exe` has no console, Muteify writes its output to
`muteify.log` in the project directory. Check that file first when autostart
misbehaves.

Remove the shortcut with:

```powershell
.\uninstall_autostart.ps1
```

An earlier version of the installer registered a Scheduled Task instead. That
approach was dropped: Task Scheduler defaults every task to
`DisallowStartIfOnBatteries` and `StopIfGoingOnBatteries`, so on a laptop the
task silently never started at logon while on battery. Both scripts try to
remove that leftover task, but deleting it needs an **elevated** PowerShell:

```powershell
Unregister-ScheduledTask -TaskName "Muteify - Spotify ad muter" -Confirm:$false
```

Until it is gone, Muteify is worse off than with no autostart at all: the task
and the shortcut each start a copy at logon, the loser exits on the mutex, and
Task Scheduler then stops the winner on battery, so nothing is left running.
Confirm your setup with `Get-Process pythonw`. Expect one Muteify, which shows
up as two entries: this `.venv` is a redirector, so `.venv\Scripts\pythonw.exe`
launches the base interpreter as a child and both stay alive. Anything more than
that pair means a second copy is starting from somewhere.

If PowerShell blocks local scripts, run the installer explicitly with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

## Behaviour when Spotify closes

Muteify does not exit when Spotify does. It restores the volume it lowered,
logs that the window went away, and keeps waiting. This is deliberate: autostart
runs at logon only, so exiting would leave you unprotected for the rest of the
session if you reopened Spotify.

## Resource usage

Ad state is inferred from a window title, so Muteify has to poll. The cost of
polling is kept low by caching Spotify's window handle: the steady-state poll is
two syscalls against that handle rather than a walk of the process table, which
is roughly 700x cheaper per poll.

Measured on a machine running ~300 processes:

| State | Poll interval | CPU (one core) | RAM |
| --- | --- | --- | --- |
| Spotify playing | 1s | ~0.13% | ~26 MB |
| Spotify closed | 5s | ~0.05% | ~26 MB |

The handle cache is revalidated on every poll and falls back to a full scan when
Spotify starts, closes, or replaces its window. Most of the ~26 MB is the Python
interpreter plus `psutil` and `pycaw`, not Muteify itself.

## Project files

- `muteify.py` — main ad-detection and volume-control program.
- `install_autostart.ps1` — adds the Startup-folder shortcut.
- `uninstall_autostart.ps1` — removes that shortcut.
- `test_muteify.py` — self-check for ad parsing and the mute/restore logic.
- `requirements.txt` — runtime Python dependencies.

The old Spotify Web API authorization flow was removed because the current
implementation is entirely local. Existing `.env` and `tokens.txt` files are
ignored local files and are not needed by Muteify; they were left untouched so
any personal credentials or tokens are not accidentally deleted.

## Limitations

- Spotify can change its window-title format, which may affect detection.
- Desktop window metadata is used; some Spotify states may not expose useful
  title information. The window does not need to be visible, so Spotify
  minimized to the tray still works.
- This project changes local playback volume only and does not block ads.
- Use it in accordance with Spotify's terms and applicable laws.

## License / attribution

Muteify relies on [PyCaw](https://github.com/AndreMiras/pycaw) for Windows audio
session control and [psutil](https://github.com/giampaolo/psutil) for process
detection.
