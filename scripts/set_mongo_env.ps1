param(
    [string]$Uri = "mongodb://localhost:27017/",
    [string]$Database = "hytools_test_temp",
    [switch]$Persist
)

Write-Host "Setting session environment variables..."
$env:HYTOOLS_MONGODB_URI = $Uri
$env:HYTOOLS_MONGODB_DATABASE = $Database
Write-Host "HYTOOLS_MONGODB_URI = $env:HYTOOLS_MONGODB_URI"
Write-Host "HYTOOLS_MONGODB_DATABASE = $env:HYTOOLS_MONGODB_DATABASE"

if ($Persist) {
    Write-Host "Persisting to user environment variables (setx)..."
    setx HYTOOLS_MONGODB_URI "$Uri" | Out-Null
    setx HYTOOLS_MONGODB_DATABASE "$Database" | Out-Null
    Write-Host "Persisted. Note: restart any open terminals for changes to take effect." -ForegroundColor Yellow
}

Write-Host "Done."