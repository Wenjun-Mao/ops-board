param(
    [string]$Stack = "signoz",
    [switch]$RemoveOrphans
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"
$envFile = Join-Path $repoRoot ".env"
$stackDir = Split-Path -Parent $composeFile
$stackEnvFiles = @(
    (Join-Path $stackDir ".env"),
    (Join-Path $stackDir "$Stack.env")
)

if (-not (Test-Path $composeFile)) {
    throw "Compose file not found for stack '$Stack': $composeFile"
}

$composeArgs = @("compose")
if (Test-Path $envFile) {
    $composeArgs += @("--env-file", $envFile)
}
foreach ($stackEnvFile in $stackEnvFiles) {
    if (Test-Path $stackEnvFile) {
        $composeArgs += @("--env-file", $stackEnvFile)
    }
}
$composeArgs += @("-f", $composeFile)

docker @composeArgs pull
$upArgs = $composeArgs + @("up", "-d")
if ($RemoveOrphans) {
    $upArgs += "--remove-orphans"
}

docker @upArgs
docker @composeArgs ps
