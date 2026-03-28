# PowerShell script to run pytest with a temporary MongoDB container
param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]
    $pytestArgs
)

$containerName = "hytools-test-$PID"
$mongoImage = "mongo:6.0"
$mongoPort = 27017

Write-Host "Checking Docker availability..."
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found in PATH. Install Docker or run tests against an existing MongoDB instance." -ForegroundColor Red
    exit 2
}

Write-Host "Pulling MongoDB image $mongoImage..."
docker pull $mongoImage | Out-Null

Write-Host "Starting MongoDB container ($containerName)..."
docker run -d --name $containerName -p $mongoPort:27017 $mongoImage | Out-Null

Write-Host "Waiting for MongoDB to accept connections (up to 30s)..."
$ready = $false
for ($i=0; $i -lt 30; $i++) {
    $logs = docker logs $containerName 2>&1
    if ($logs -match "Waiting for connections") {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Write-Host "Warning: MongoDB did not report readiness; continuing anyway (may still work)." -ForegroundColor Yellow
}

# Set env vars for the test run
$env:HYTOOLS_MONGODB_URI = "mongodb://localhost:$mongoPort/"
$env:HYTOOLS_MONGODB_DATABASE = "hytools_test_$PID"

# Run pytest
$pytestCmd = "pytest -q " + ($pytestArgs -join ' ')
Write-Host "Running: $pytestCmd"
$process = Start-Process -FilePath pytest -ArgumentList $pytestArgs -NoNewWindow -Wait -PassThru
$exitCode = $process.ExitCode

Write-Host "Stopping and removing MongoDB container $containerName..."
docker rm -f $containerName | Out-Null

exit $exitCode
