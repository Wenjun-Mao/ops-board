param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupPath)) {
    throw "Backup path does not exist: $BackupPath"
}

Write-Host "Restore source: $BackupPath"
Write-Host "No restore jobs are defined yet. Add stack-specific restore tasks before storing production data."
