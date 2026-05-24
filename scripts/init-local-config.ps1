param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envExample = Join-Path $repoRoot ".env.example"
$envFile = Join-Path $repoRoot ".env"
$secretsDir = Join-Path $repoRoot "secrets"
$signozJwtSecretFile = Join-Path $secretsDir "signoz_jwt_secret"

function New-SecretValue {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes)
    }
    finally {
        $rng.Dispose()
    }
}

if (-not (Test-Path -LiteralPath $envExample)) {
    throw "Missing .env.example at $envExample"
}

if ((-not (Test-Path -LiteralPath $envFile)) -or $Force) {
    Copy-Item -LiteralPath $envExample -Destination $envFile -Force
    Write-Host "Wrote local .env from .env.example"
}
else {
    Write-Host "Keeping existing .env. Use -Force to recreate it from .env.example."
}

New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

if ((-not (Test-Path -LiteralPath $signozJwtSecretFile)) -or $Force) {
    New-SecretValue | Set-Content -LiteralPath $signozJwtSecretFile -NoNewline -Encoding ascii
    Write-Host "Wrote Docker secret: secrets/signoz_jwt_secret"
}
else {
    Write-Host "Keeping existing Docker secret: secrets/signoz_jwt_secret. Use -Force to rotate it."
}

Write-Host "Local config is ready."
Write-Host "Start SigNoz with:"
Write-Host "docker compose --env-file .env -f stacks/signoz/compose.yaml up -d"
