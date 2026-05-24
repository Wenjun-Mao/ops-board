param(
    [string]$Stack = "signoz",
    [switch]$RemoveOrphans
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
$composeArgs += @("-p", $Stack, "-f", $composeFile)

docker @composeArgs pull
$upArgs = $composeArgs + @("up", "-d")
if ($RemoveOrphans) {
    $upArgs += "--remove-orphans"
}

docker @upArgs
docker @composeArgs ps
