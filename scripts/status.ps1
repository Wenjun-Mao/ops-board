param(
    [string]$Stack = "signoz"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

$composeArgs = @("compose")
if (Test-Path $envFile) {
    $composeArgs += @("--env-file", $envFile)
}
$composeArgs += @("-f", $composeFile)

docker @composeArgs ps -a
