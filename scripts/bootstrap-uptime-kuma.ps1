$ErrorActionPreference = "Stop"

$configPath = $null
$skipOptional = $false
$showHelp = $false

for ($index = 0; $index -lt $args.Count; $index++) {
    $arg = $args[$index]

    switch ($arg.ToLowerInvariant()) {
        "--help" {
            $showHelp = $true
        }
        "-help" {
            $showHelp = $true
        }
        "-h" {
            $showHelp = $true
        }
        "--config" {
            if ($index + 1 -ge $args.Count) {
                throw "Missing value for --config."
            }
            $index++
            $configPath = $args[$index]
        }
        "-configpath" {
            if ($index + 1 -ge $args.Count) {
                throw "Missing value for -ConfigPath."
            }
            $index++
            $configPath = $args[$index]
        }
        "--skip-optional" {
            $skipOptional = $true
        }
        "-skipoptional" {
            $skipOptional = $true
        }
        default {
            throw "Unknown argument: $arg"
        }
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$bootstrapProject = Join-Path $repoRoot "stacks\uptime-kuma\bootstrap"
$bootstrapScript = Join-Path $bootstrapProject "bootstrap.py"

if (-not (Test-Path -LiteralPath $bootstrapScript)) {
    throw "Missing Uptime Kuma bootstrap helper: $bootstrapScript"
}

$uvArgs = @(
    "run",
    "--project",
    $bootstrapProject,
    "python",
    $bootstrapScript
)

if ($showHelp) {
    $uvArgs += "--help"
}
else {
    if ($configPath) {
        $uvArgs += @("--config", $configPath)
    }

    if ($skipOptional) {
        $uvArgs += "--skip-optional"
    }
}

Push-Location $repoRoot
try {
    uv @uvArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
