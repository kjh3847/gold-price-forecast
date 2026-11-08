param(
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')][string]$ForecastDate = '2026-09-24',
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$')][string]$Release = ('run-' + (Get-Date -Format 'yyyyMMddHHmmss')),
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed (exit $LASTEXITCODE). Deployment stopped." }
}
$oldRelease = $env:RELEASE
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $env:RELEASE = $Release
    Invoke-Docker info --format '{{.OSType}}'
    Invoke-Docker compose version
    Invoke-Docker compose config --quiet
    if ($CheckOnly) { Write-Host 'Prerequisites and Compose configuration OK. No build or deployment performed.'; return }
    Invoke-Docker build --target test -f deploy/Dockerfile.api -t "gold-forecast-test:$Release" .
    Invoke-Docker run --rm "gold-forecast-test:$Release"
    Invoke-Docker compose build
    # Uses the same persistent volume as the API. Batch errors stop deployment.
    Invoke-Docker compose run --rm --no-deps api python -m gold_service.run_daily --date $ForecastDate
    Invoke-Docker compose up -d --no-build --wait --wait-timeout 180
    # Verify a real forecast through the web proxy, not just a running process.
    Invoke-Docker compose exec -T web wget -qO- http://127.0.0.1:8080/api/forecast/latest
    Write-Host "`nDeployment OK: release=$Release forecast-request=$ForecastDate"
    Write-Host 'Open http://localhost:8080 (unless WEB_PORT was overridden). AWS delivery requires separate configuration.'
} finally {
    Pop-Location
    $env:RELEASE = $oldRelease
}
