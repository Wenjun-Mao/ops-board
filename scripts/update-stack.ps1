param(
    [string]$Stack = "signoz"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

docker compose -p $Stack -f $composeFile pull
docker compose -p $Stack -f $composeFile up -d --remove-orphans
docker compose -p $Stack -f $composeFile ps
