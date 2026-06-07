param(
    [string]$BackupRoot = "$env:USERPROFILE\ops-board-backups"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupName = "ops-board-config-$timestamp"
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) $backupName
$archivePath = Join-Path $BackupRoot "$backupName.zip"

$backupItems = @(
    ".gitattributes",
    ".env.example",
    "compose.yaml",
    "README.md",
    "access/tailscale.md",
    "scripts/README.md",
    "scripts/lib/ops-board.sh",
    "scripts/init-local-config.sh",
    "scripts/bootstrap-uptime-kuma.sh",
    "scripts/status.sh",
    "scripts/update-stack.sh",
    "scripts/smoke-day1.sh",
    "scripts/tests/test-linux-operator-scripts.sh",
    "scripts/bootstrap-uptime-kuma.ps1",
    "scripts/smoke-day1.ps1",
    "scripts/init-local-config.ps1",
    "scripts/status.ps1",
    "scripts/update-stack.ps1",
    "scripts/backup.ps1",
    "scripts/restore.ps1",
    "stacks/signoz/compose.yaml",
    "stacks/signoz/otel-collector-config.yaml",
    "stacks/uptime-kuma/compose.yaml",
    "stacks/uptime-kuma/docs/monitors.md",
    "stacks/uptime-kuma/bootstrap/pyproject.toml",
    "stacks/uptime-kuma/bootstrap/bootstrap.py",
    "stacks/uptime-kuma/bootstrap/monitors.yaml",
    "stacks/homepage/compose.yaml",
    "stacks/homepage/config/services.yaml",
    "stacks/homepage/config/widgets.yaml",
    "stacks/homepage/config/settings.yaml",
    "stacks/homepage/config/bookmarks.yaml",
    "stacks/plane/compose.yaml",
    "stacks/plane/plane.env.example",
    "docs"
)

function Copy-BackupItem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    $source = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Backup item does not exist: $RelativePath"
    }

    $destination = Join-Path $stagingRoot $RelativePath
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

try {
    foreach ($item in $backupItems) {
        Copy-BackupItem -RelativePath $item
    }

    $manifestPath = Join-Path $stagingRoot "_manifest.txt"
    $backupItems | Set-Content -LiteralPath $manifestPath -Encoding ascii

    Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -Force

    Write-Host "Backup root: $BackupRoot"
    Write-Host "Created backup: $archivePath"
    Write-Host "Included non-secret config and docs only."
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
