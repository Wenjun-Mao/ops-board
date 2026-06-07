param(
    [switch]$SkipOnboarding,
    [switch]$SkipTelemetryQuery,
    [int]$TimeoutSec = 20
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Write-Section {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    Write-Host ""
    Write-Host "== $Name =="
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $true)]
        [int[]]$AcceptedCodes
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -MaximumRedirection 0 -TimeoutSec $TimeoutSec -ErrorAction Stop
        $statusCode = [int]$response.StatusCode
    }
    catch [Microsoft.PowerShell.Commands.HttpResponseException] {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($AcceptedCodes -notcontains $statusCode) {
        throw "$Name returned HTTP $statusCode for $Uri"
    }

    Write-Host "${Name}: HTTP $statusCode"
}

function Get-RecentTelemetry {
    $query = @"
SELECT serviceName, name, count()
FROM signoz_traces.signoz_index_v3
WHERE timestamp >= now() - INTERVAL 30 MINUTE
  AND serviceName IN ('dummy-api','dummy-job')
GROUP BY serviceName, name
ORDER BY serviceName, name
"@

    docker exec signoz-clickhouse clickhouse-client --query $query
    if ($LASTEXITCODE -ne 0) {
        throw "ClickHouse telemetry query failed with exit code $LASTEXITCODE"
    }
}

function Wait-RequiredTelemetry {
    $requiredPatterns = @(
        "dummy-api\s+dummy-api\.work",
        "dummy-api\s+dummy-api\.expensive-lookup",
        "dummy-job\s+dummy-job\.run",
        "dummy-job\s+dummy-job\.process-record"
    )

    $deadline = (Get-Date).AddSeconds(90)
    $lastOutput = ""

    do {
        $lastOutput = Get-RecentTelemetry | Out-String
        $missing = @(
            foreach ($pattern in $requiredPatterns) {
                if ($lastOutput -notmatch $pattern) {
                    $pattern
                }
            }
        )

        if ($missing.Count -eq 0) {
            Write-Host "Recent SigNoz telemetry:"
            Write-Host $lastOutput.Trim()
            return
        }

        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    Write-Host "Last telemetry query output:"
    Write-Host $lastOutput.Trim()
    throw "Timed out waiting for required dummy-api and dummy-job telemetry."
}

Push-Location $repoRoot
try {
    Write-Section "Compose"
    Invoke-CheckedCommand -Label "Validating root Compose config" -Command {
        docker compose --env-file .env -f compose.yaml config --quiet
    }

    Write-Section "Uptime Kuma Bootstrap"
    Invoke-CheckedCommand -Label "Running idempotent Uptime Kuma bootstrap" -Command {
        .\scripts\bootstrap-uptime-kuma.ps1
    }

    Write-Section "Local Endpoints"
    Test-HttpEndpoint -Name "Homepage" -Uri "http://localhost:3000" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "Uptime Kuma" -Uri "http://localhost:3001" -AcceptedCodes @(200, 302)
    Test-HttpEndpoint -Name "Uptime Kuma status page" -Uri "http://localhost:3001/status/ops-board" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "SigNoz health" -Uri "http://localhost:8080/api/v1/health" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "SigNoz collector" -Uri "http://localhost:13133/" -AcceptedCodes @(200)
    Test-HttpEndpoint -Name "Plane" -Uri "http://localhost:8082" -AcceptedCodes @(200, 302, 307, 308)

    if (-not $SkipOnboarding) {
        Write-Section "Onboarding Playground"
        Invoke-CheckedCommand -Label "Starting dummy API" -Command {
            docker compose -f examples/onboarding/compose.yaml up --build -d dummy-api
        }
        Test-HttpEndpoint -Name "Dummy API health" -Uri "http://localhost:18080/health" -AcceptedCodes @(200)
        Test-HttpEndpoint -Name "Dummy API work" -Uri "http://localhost:18080/work/demo" -AcceptedCodes @(200)
        Invoke-CheckedCommand -Label "Running dummy job" -Command {
            docker compose -f examples/onboarding/compose.yaml run --rm dummy-job
        }

        if (-not $SkipTelemetryQuery) {
            Write-Section "SigNoz Telemetry"
            Wait-RequiredTelemetry
        }
    }

    Write-Host ""
    Write-Host "Day-1 smoke passed."
}
finally {
    Pop-Location
}
