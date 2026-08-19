$ErrorActionPreference = "Stop"

$shortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "Muteify.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Removed $shortcutPath"
} else {
    Write-Host "No startup shortcut found at $shortcutPath"
}

# Older installs registered a Scheduled Task instead.
$legacyTask = Get-ScheduledTask -TaskName "Muteify - Spotify ad muter" -ErrorAction SilentlyContinue
if ($legacyTask) {
    try {
        Unregister-ScheduledTask -TaskName "Muteify - Spotify ad muter" -Confirm:$false -ErrorAction Stop
        Write-Host "Removed the old 'Muteify - Spotify ad muter' Scheduled Task."
    } catch {
        Write-Warning "Could not remove the old Scheduled Task; run this from an elevated PowerShell to remove it."
    }
}
