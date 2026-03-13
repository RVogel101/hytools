# Request a DPLA API key. The key is sent to the email address you provide.
#
# Usage (from repo root):
#   .\docs\development\requests_guides\request_dpla_api_key.ps1 -Email "YOUR_EMAIL@example.com"
#
# Or with curl (if available) directly:
#   curl -v -X POST "https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com"
#
# On success you get: HTTP/1.1 201 Created and {"message":"API key created and sent via email"}
# Then use the 32-character key in config["ingestion"]["dpla"]["api_key"] or config["scraping"]["dpla"]["api_key"] or DPLA_API_KEY env.

param(
    [Parameter(Mandatory = $true)]
    [string]$Email
)

$Encoded = [System.Web.HttpUtility]::UrlEncode($Email)
$Url = "https://api.dp.la/v2/api_key/$Encoded"
Write-Host "Requesting DPLA API key for: $Email"
Invoke-RestMethod -Uri $Url -Method Post -UseBasicParsing | ConvertTo-Json
