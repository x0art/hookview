<#
.SYNOPSIS
    Send webhooks to HookView — a real-time webhook log receiver.
.DESCRIPTION
    Contains reusable functions for sending webhooks to a HookView server.
    HookView accepts ANY JSON payload — no required fields.
    Supports objects, strings, arrays, numbers, booleans, null, and file uploads.
.EXAMPLE
    .\scripts\send-webhook.ps1
    . .\scripts\send-webhook.ps1; Send-HookJson -Payload @{ event = "deploy" }
#>

# ── Configuration ──────────────────────────────────────────────────────────
# Set these before calling the functions, or pass as parameters

$script:HookView_Server  = if ($env:HOOKVIEW_SERVER)  { $env:HOOKVIEW_SERVER }  else { "http://localhost:8000" }
$script:HookView_ApiKey  = if ($env:HOOKVIEW_API_KEY) { $env:HOOKVIEW_API_KEY } else { "" }

# ── Functions ──────────────────────────────────────────────────────────────

<#
.SYNOPSIS
    Send any JSON value as a webhook payload to HookView.
.PARAMETER Payload
    Any value to send as the webhook body. Can be a hashtable, string, array, number, etc.
.PARAMETER Server
    HookView server URL. Defaults to $env:HOOKVIEW_SERVER or http://localhost:8000.
.PARAMETER ApiKey
    Bearer API key. Defaults to $env:HOOKVIEW_API_KEY.
.EXAMPLE
    Send-HookJson -Payload @{ event = "deploy"; status = "success" }
    Send-HookJson -Payload "A plain string message"
    Send-HookJson -Payload @(1, 2, 3)
    Send-HookJson -Payload $null
#>
function Send-HookJson {
    param(
        [Parameter(Mandatory = $true)] $Payload,
        [string] $Server = $script:HookView_Server,
        [string] $ApiKey = $script:HookView_ApiKey
    )

    if (-not $ApiKey) {
        Write-Error "API key is required. Set `$env:HOOKVIEW_API_KEY or pass -ApiKey."
        return $null
    }

    # Convert payload to JSON string.
    if ($null -eq $Payload) {
        $body = "null"
    } else {
        $body = $Payload | ConvertTo-Json -Depth 20 -Compress
    }

    try {
        $response = Invoke-RestMethod -Uri "$Server/webhook" `
            -Method Post `
            -Headers @{
                "Authorization" = "Bearer $ApiKey"
                "Content-Type"  = "application/json"
            } `
            -Body $body `
            -ErrorAction Stop

        $display = if ($response.payload -is [string]) { $response.payload } else { $response.payload | ConvertTo-Json -Compress }
        Write-Host "[✓] Log #$($response.id) created" -ForegroundColor Green
        Write-Host "    payload: $display" -ForegroundColor Cyan
        if ($response.filename) {
            Write-Host "    file:    $($response.filename)" -ForegroundColor Yellow
        }
        return $response
    }
    catch {
        Write-Error "Failed to send webhook: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Send a multipart webhook with custom form fields and optional file upload.
.PARAMETER Fields
    Hashtable of form fields to send. All fields become the JSON payload object.
.PARAMETER FilePath
    Path to an optional file to upload (sent as the 'file' field).
.PARAMETER Server
    HookView server URL.
.PARAMETER ApiKey
    Bearer API key.
.EXAMPLE
    Send-HookMultipart -Fields @{ event = "deploy"; service = "api" }
    Send-HookMultipart -Fields @{ note = "Report" } -FilePath ./report.pdf
#>
function Send-HookMultipart {
    param(
        [Parameter(Mandatory = $true)] [hashtable] $Fields,
        [string] $FilePath = "",
        [string] $Server = $script:HookView_Server,
        [string] $ApiKey = $script:HookView_ApiKey
    )

    if (-not $ApiKey) {
        Write-Error "API key is required. Set `$env:HOOKVIEW_API_KEY or pass -ApiKey."
        return $null
    }

    $uri = "$Server/webhook"
    $headers = @{ "Authorization" = "Bearer $ApiKey" }

    # Build form data: simple values as strings, files via Get-Item
    $form = @{ }
    foreach ($key in $Fields.Keys) {
        $val = $Fields[$key]
        if ($val -is [string] -or $val -is [int] -or $val -is [double] -or $val -is [bool]) {
            $form[$key] = "$val"
        } elseif ($val -is [hashtable] -or $val -is [array] -or $val -is [pscustomobject]) {
            $form[$key] = ($val | ConvertTo-Json -Compress)
        } else {
            $form[$key] = "$val"
        }
    }

    if ($FilePath -and (Test-Path $FilePath)) {
        Write-Host "[i] Uploading file: $FilePath" -ForegroundColor Yellow
        $form["file"] = Get-Item -Path $FilePath
    }

    try {
        $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Form $form -ErrorAction Stop

        $display = if ($response.payload -is [string]) { $response.payload } else { $response.payload | ConvertTo-Json -Compress }
        Write-Host "[✓] Log #$($response.id) created" -ForegroundColor Green
        Write-Host "    payload: $display" -ForegroundColor Cyan
        if ($response.filename) {
            Write-Host "    file:    $($response.filename)" -ForegroundColor Yellow
        }
        return $response
    }
    catch {
        Write-Error "Failed to send multipart webhook: $_"
        return $null
    }
}

<#
.SYNOPSIS
    Fetch the latest N log entries from HookView.
.PARAMETER Limit
    Number of entries to fetch (default 10).
.PARAMETER Server
    HookView server URL.
.PARAMETER ApiKey
    Bearer API key.
#>
function Get-HookLogs {
    param(
        [int] $Limit = 10,
        [string] $Server = $script:HookView_Server,
        [string] $ApiKey = $script:HookView_ApiKey
    )

    if (-not $ApiKey) {
        Write-Error "API key is required. Set `$env:HOOKVIEW_API_KEY or pass -ApiKey."
        return $null
    }

    try {
        $response = Invoke-RestMethod -Uri "$Server/logs?limit=$Limit" `
            -Method Get `
            -Headers @{ "Authorization" = "Bearer $ApiKey" } `
            -ErrorAction Stop

        Write-Host "[i] $($response.total) total logs, showing $($response.items.Count)" -ForegroundColor Cyan
        foreach ($log in $response.items) {
            $payload = if ($log.payload -is [string]) { $log.payload } else { $log.payload | ConvertTo-Json -Compress }
            Write-Host "  #$($log.id) [$($log.timestamp)] $($log.ip_address) → $payload" -ForegroundColor Gray
            if ($log.filename) { Write-Host "         file: $($log.filename)" -ForegroundColor DarkYellow }
        }
        return $response
    }
    catch {
        Write-Error "Failed to fetch logs: $_"
        return $null
    }
}

# ── Examples (run when script is executed directly) ────────────────────────

if ($MyInvocation.InvocationName -ne '.') {
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Magenta
    Write-Host "  HookView - Webhook Sender Examples"          -ForegroundColor Magenta
    Write-Host "  (send any JSON payload — no required fields)" -ForegroundColor Gray
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Magenta

    # ── Example 1: Full JSON object payload ──
    Write-Host "`n[1/4] Sending structured JSON object... (recommended)" -ForegroundColor Cyan
    $payload = @{
        event    = "deploy"
        service  = "api-gateway"
        version  = "v2.1.0"
        duration = 3421
        status   = "success"
    }
    Send-HookJson -Payload $payload

    # ── Example 2: String payload (not wrapped in object) ──
    Write-Host "`n[2/4] Sending a plain string (no object wrapper)..." -ForegroundColor Cyan
    Send-HookJson -Payload "Hello from PowerShell! 🚀"

    # ── Example 3: Array as payload ──
    Write-Host "`n[3/4] Sending an array as the payload..." -ForegroundColor Cyan
    Send-HookJson -Payload @(1, 2, 3, "complete")

    # ── Example 4: Fetch recent logs ──
    Write-Host "`n[4/4] Fetching recent logs..." -ForegroundColor Cyan
    Get-HookLogs -Limit 5

    Write-Host "`n══════════════════════════════════════════════" -ForegroundColor Magenta
    Write-Host "  Done! Import functions with:"                  -ForegroundColor Gray
    Write-Host "  . .\scripts\send-webhook.ps1"                  -ForegroundColor Yellow
    Write-Host "  Send-HookJson -Payload @{ event = 'deploy'; status = 'ok' }" -ForegroundColor Yellow
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Magenta
}
