param(
    [string]$BackupRoot = "$env:USERPROFILE\ops-board-backups"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force $BackupRoot | Out-Null

Write-Host "Backup root: $BackupRoot"
Write-Host "No backup jobs are defined yet. Add stack-specific backup tasks before storing production data."
