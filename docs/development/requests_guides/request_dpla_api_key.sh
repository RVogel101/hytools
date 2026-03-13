#!/usr/bin/env bash
# Request a DPLA API key. The key is sent to the email address you provide.
#
# Usage (from repo root):
#   ./docs/development/requests_guides/request_dpla_api_key.sh YOUR_EMAIL@example.com
#
# Or with curl directly (replace YOUR_EMAIL@example.com):
#   curl -v -X POST "https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com"
#
# On success you get: HTTP/1.1 201 Created and {"message":"API key created and sent via email"}
# Then use the 32-character key in config["ingestion"]["dpla"]["api_key"] or config["scraping"]["dpla"]["api_key"] or DPLA_API_KEY env.

set -e
EMAIL="${1:-}"
if [[ -z "$EMAIL" ]]; then
  echo "Usage: $0 YOUR_EMAIL@example.com"
  echo "Example: curl -v -X POST https://api.dp.la/v2/api_key/you@example.com"
  exit 1
fi
URL="https://api.dp.la/v2/api_key/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$EMAIL'))")"
echo "Requesting DPLA API key for: $EMAIL"
curl -v -X POST "$URL"
