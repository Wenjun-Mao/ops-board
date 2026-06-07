param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,

    [string]$TargetRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")),

    [switch]$Force
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupPath)) {
    throw "Backup path does not exist: $BackupPath"
}

if ([System.IO.Path]::GetExtension($BackupPath) -ne ".zip") {
    throw "Restore only supports .zip archives created by scripts/backup.ps1"
}

$targetRootPath = if (Test-Path -LiteralPath $TargetRoot) {
    (Resolve-Path -LiteralPath $TargetRoot).Path
}
else {
    New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
    (Resolve-Path -LiteralPath $TargetRoot).Path
}

$restoreItems = @(
    ".env.example",
    "compose.yaml",
    "README.md",
    "access/tailscale.md",
    "scripts/README.md",
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

function Restore-AllowedItem {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    $source = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Backup archive is missing expected item: $RelativePath"
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    if ((Test-Path -LiteralPath $destination) -and (-not $Force)) {
        throw "Restore target already exists: $RelativePath. Re-run with -Force to overwrite allowlisted files."
    }

    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ops-board-restore-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

try {
    Expand-Archive -LiteralPath $BackupPath -DestinationPath $stagingRoot -Force

    $manifestPath = Join-Path $stagingRoot "_manifest.txt"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Backup archive is missing _manifest.txt"
    }

    foreach ($item in $restoreItems) {
        Restore-AllowedItem -RelativePath $item -SourceRoot $stagingRoot -DestinationRoot $targetRootPath
    }

    Write-Host "Restore source: $BackupPath"
    Write-Host "Restore target: $targetRootPath"
    Write-Host "Restored allowlisted non-secret config and docs only."
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
