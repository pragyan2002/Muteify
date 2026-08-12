$ErrorActionPreference = "Stop"
$taskName = "Muteify - Spotify ad muter"

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed '$taskName'."
