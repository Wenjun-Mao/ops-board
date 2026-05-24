param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envExample = Join-Path $repoRoot ".env.example"
$envFile = Join-Path $repoRoot ".env"
$secretsDir = Join-Path $repoRoot "secrets"
$signozJwtSecretFile = Join-Path $secretsDir "signoz_jwt_secret"
$planeSecretKeyFile = Join-Path $secretsDir "plane_secret_key"
$planePostgresPasswordFile = Join-Path $secretsDir "plane_postgres_password"
$planeRabbitmqPasswordFile = Join-Path $secretsDir "plane_rabbitmq_password"
$planeMinioPasswordFile = Join-Path $secretsDir "plane_minio_password"

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

function Set-SecretFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if ((-not (Test-Path -LiteralPath $Path)) -or $Force) {
        New-SecretValue | Set-Content -LiteralPath $Path -NoNewline -Encoding ascii
        Write-Host "Wrote Docker secret: $Label"
    }
    else {
        Write-Host "Keeping existing Docker secret: $Label. Use -Force to rotate it."
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

Set-SecretFile -Path $signozJwtSecretFile -Label "secrets/signoz_jwt_secret"
Set-SecretFile -Path $planeSecretKeyFile -Label "secrets/plane_secret_key"
Set-SecretFile -Path $planePostgresPasswordFile -Label "secrets/plane_postgres_password"
Set-SecretFile -Path $planeRabbitmqPasswordFile -Label "secrets/plane_rabbitmq_password"
Set-SecretFile -Path $planeMinioPasswordFile -Label "secrets/plane_minio_password"

Write-Host "Local config is ready."
Write-Host "Start SigNoz with:"
Write-Host "docker compose --env-file .env -f stacks/signoz/compose.yaml up -d"
