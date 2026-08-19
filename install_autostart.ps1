$ErrorActionPreference = "Stop"

# Run this once from the project directory. It drops a shortcut in the per-user
# Startup folder, so no administrator rights are needed and Muteify starts after
# the user logs in.
#
# This replaced a Scheduled Task. Task Scheduler defaults every task to
# DisallowStartIfOnBatteries and StopIfGoingOnBatteries, so on a laptop the task
# silently never started at logon while on battery -- and fixing those settings
# afterwards needs an elevated shell, because tasks live in System32\Tasks.
# A Startup shortcut has none of those conditions.
$projectPath = (Resolve-Path $PSScriptRoot).Path
$pythonwPath = Join-Path $projectPath ".venv\Scripts\pythonw.exe"
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
$scriptPath = Join-Path $projectPath "muteify.py"

if (Test-Path $pythonwPath) {
    # pythonw.exe keeps the console window from appearing.
    $executable = $pythonwPath
} elseif (Test-Path $pythonPath) {
    $executable = $pythonPath
} else {
    throw "Python was not found in $projectPath\.venv\Scripts. Create the virtual environment and install requirements first."
}

$startupDir = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupDir "Muteify.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $executable
$shortcut.Arguments = '"{0}"' -f $scriptPath
$shortcut.WorkingDirectory = $projectPath
$shortcut.WindowStyle = 7          # minimized, in case python.exe is the fallback
$shortcut.Description = "Starts Muteify in the background at logon; it waits for Spotify."
$shortcut.Save()

# Remove the old Scheduled Task if a previous version of this installer made
# one, so the two do not both try to start Muteify.
$legacyTask = Get-ScheduledTask -TaskName "Muteify - Spotify ad muter" -ErrorAction SilentlyContinue
if ($legacyTask) {
    try {
        Unregister-ScheduledTask -TaskName "Muteify - Spotify ad muter" -Confirm:$false -ErrorAction Stop
        Write-Host "Removed the old 'Muteify - Spotify ad muter' Scheduled Task."
    } catch {
        Write-Warning "Could not remove the old Scheduled Task (needs an elevated PowerShell). The startup shortcut still works; Muteify's mutex stops a second copy from running."
    }
}

Write-Host "Installed $shortcutPath"
Write-Host "It will start automatically at your next logon."
Write-Host "To start it now: Start-Process '$executable' -ArgumentList '\"$scriptPath\"' -WorkingDirectory '$projectPath'"
