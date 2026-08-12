$ErrorActionPreference = "Stop"

# Run this once from the project directory. The task is per-user, so no
# administrator rights are required and it starts only after the user logs in.
$projectPath = (Resolve-Path $PSScriptRoot).Path
$pythonwPath = Join-Path $projectPath ".venv\Scripts\pythonw.exe"
$pythonPath = Join-Path $projectPath ".venv\Scripts\python.exe"
$scriptPath = Join-Path $projectPath "muteify.py"
$taskName = "Muteify - Spotify ad muter"

if (Test-Path $pythonwPath) {
    $executable = $pythonwPath
} elseif (Test-Path $pythonPath) {
    $executable = $pythonPath
} else {
    throw "Python was not found in $projectPath\.venv\Scripts. Create the virtual environment and install requirements first."
}

$action = New-ScheduledTaskAction `
    -Execute $executable `
    -Argument ('"{0}"' -f $scriptPath) `
    -WorkingDirectory $projectPath
$userId = "$($env:USERDOMAIN)\$($env:USERNAME)"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Starts Muteify in the background at logon; it waits efficiently for Spotify." `
    -Force | Out-Null

Write-Host "Installed '$taskName'. It will start automatically at your next logon."
Write-Host "To start it now: Start-ScheduledTask -TaskName '$taskName'"
