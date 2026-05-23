param(
    [string]$Stack = "signoz",
    [switch]$RemoveOrphans
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

docker compose -p $Stack -f $composeFile pull
$upArgs = @("compose", "-p", $Stack, "-f", $composeFile, "up", "-d")
if ($RemoveOrphans) {
    $upArgs += "--remove-orphans"
}

docker @upArgs
docker compose -p $Stack -f $composeFile ps
