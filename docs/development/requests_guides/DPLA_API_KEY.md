# DPLA API key

DPLA requires an API key for requests. Request one with a **POST** to their endpoint; the key is then emailed to you.

## Request a key (any OS)

**Replace `YOUR_EMAIL@example.com` with your real email.**

### Windows (PowerShell / cmd)

Use `curl.exe` (not the PowerShell alias):

```powershell
curl.exe -v -X POST "https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com"
```

If your email contains `@`, you can URL-encode it as `%40`:

```powershell
curl.exe -v -X POST "https://api.dp.la/v2/api_key/myname%40gmail.com"
```

### Linux / macOS / Git Bash

```bash
curl -v -X POST "https://api.dp.la/v2/api_key/YOUR_EMAIL@example.com"
```

### Scripts in this repo

- **Bash:** `./docs/development/requests_guides/request_dpla_api_key.sh YOUR_EMAIL@example.com`
- **PowerShell:** `.\scripts\request_dpla_api_key.ps1 -Email "YOUR_EMAIL@example.com"`

## Expected response

- **Success:** `HTTP/1.1 200 OK` (or `201 Created`) and body like:  
  `API key created and sent to YOUR_EMAIL@example.com.`
- The **32-character API key** will arrive at that email. Use it in:
  - **Config:** `config["scraping"]["dpla"]["api_key"]` in `config/settings.yaml`
  - **Environment:** `DPLA_API_KEY`

## If the email link failed

Request the key using the **curl** commands above instead of the link in the email. The key is sent to your address; you do not need to click a link to generate it. If the key never arrives, check spam and try again with the same curl command (they may send a new key).

## Reference

- [DPLA API policies (get a key)](https://pro.dp.la/developers/policies)
