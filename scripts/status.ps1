param(
    [string]$Stack = "ops-board"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $repoRoot ".env"

if ($Stack -eq "ops-board") {
    $composeFile = Join-Path $repoRoot "compose.yaml"
    $stackEnvFiles = @()
}
else {
    $composeFile = Join-Path $repoRoot "stacks\$Stack\compose.yaml"
    $stackDir = Split-Path -Parent $composeFile
    $stackEnvFiles = @(
        (Join-Path $stackDir ".env"),
        (Join-Path $stackDir "$Stack.env")
    )
}

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

docker @composeArgs ps -a
