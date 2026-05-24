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
$planeStackDir = Join-Path $repoRoot "stacks\plane"
$planeEnvExample = Join-Path $planeStackDir "plane.env.example"
$planeEnvFile = Join-Path $planeStackDir "plane.env"

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

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$Lines,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $found = $false
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index] -match "^$([regex]::Escape($Key))=") {
            $Lines[$index] = "$Key=$Value"
            $found = $true
            break
        }
    }

    if (-not $found) {
        $Lines.Add("$Key=$Value")
    }
}

function Get-SecretText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return (Get-Content -Raw -LiteralPath $Path).Trim()
}

function Set-PlaneEnvFile {
    if (-not (Test-Path -LiteralPath $planeEnvExample)) {
        throw "Missing Plane env example at $planeEnvExample"
    }

    if ((Test-Path -LiteralPath $planeEnvFile) -and (-not $Force)) {
        Write-Host "Keeping existing Plane env: stacks/plane/plane.env. Use -Force to recreate it."
        return
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.AddRange([string[]](Get-Content -LiteralPath $planeEnvExample))

    $secretKey = Get-SecretText -Path $planeSecretKeyFile
    $postgresPassword = Get-SecretText -Path $planePostgresPasswordFile
    $rabbitmqPassword = Get-SecretText -Path $planeRabbitmqPasswordFile
    $minioPassword = Get-SecretText -Path $planeMinioPasswordFile
    $postgresPasswordEncoded = [uri]::EscapeDataString($postgresPassword)
    $rabbitmqPasswordEncoded = [uri]::EscapeDataString($rabbitmqPassword)

    Set-EnvValue -Lines $lines -Key "APP_DOMAIN" -Value "localhost"
    Set-EnvValue -Lines $lines -Key "APP_RELEASE" -Value "v1.3.1"
    Set-EnvValue -Lines $lines -Key "LISTEN_HTTP_PORT" -Value "8082"
    Set-EnvValue -Lines $lines -Key "LISTEN_HTTPS_PORT" -Value "8443"
    Set-EnvValue -Lines $lines -Key "WEB_URL" -Value "http://localhost:8082"
    Set-EnvValue -Lines $lines -Key "PLANE_DEBUG" -Value "0"
    Set-EnvValue -Lines $lines -Key "CORS_ALLOWED_ORIGINS" -Value "http://localhost:8082"
    Set-EnvValue -Lines $lines -Key "POSTGRES_PASSWORD" -Value $postgresPassword
    Set-EnvValue -Lines $lines -Key "DATABASE_URL" -Value "postgresql://plane:$postgresPasswordEncoded@plane-db/plane"
    Set-EnvValue -Lines $lines -Key "RABBITMQ_PASSWORD" -Value $rabbitmqPassword
    Set-EnvValue -Lines $lines -Key "AMQP_URL" -Value "amqp://plane:$rabbitmqPasswordEncoded@plane-mq:5672/plane"
    Set-EnvValue -Lines $lines -Key "SECRET_KEY" -Value $secretKey
    Set-EnvValue -Lines $lines -Key "LIVE_SERVER_SECRET_KEY" -Value $secretKey
    Set-EnvValue -Lines $lines -Key "AWS_SECRET_ACCESS_KEY" -Value $minioPassword

    Set-Content -LiteralPath $planeEnvFile -Value $lines -Encoding ascii
    Write-Host "Wrote local Plane env: stacks/plane/plane.env"
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
Set-PlaneEnvFile

Write-Host "Local config is ready."
Write-Host "Start Ops Board with:"
Write-Host "docker compose --env-file .env -f compose.yaml up -d"
