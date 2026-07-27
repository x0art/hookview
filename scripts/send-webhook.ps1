<#
.SYNOPSIS
    Send webhooks to HookView — a real-time webhook log receiver.
.DESCRIPTION
    Contains reusable functions for sending webhooks to a HookView server.
    Supports string messages, JSON objects/arrays, optional file uploads,
    and multipart form data.
.EXAMPLE
    .\scripts\send-webhook.ps1 -Message "Deploy completed"
    .\scripts\send-webhook.ps1 -Message '{"event":"deploy","status":"ok"}' -File ./build.zip
#>

# ── Configuration ──────────────────────────────────────────────────────────
# Set these before calling the functions, or pass as parameters

$script:HookView_Server  = if ($env:HOOKVIEW_SERVER)  { $env:HOOKVIEW_SERVER }  else { "http://localhost:8000" }
$script:HookView_ApiKey  = if ($env:HOOKVIEW_API_KEY) { $env:HOOKVIEW_API_KEY } else { "" }

# ── Functions ──────────────────────────────────────────────────────────────

<#
.SYNOPSIS
    Send a JSON webhook to HookView.
.PARAMETER Message
    The message value (string, or a JSON-serializable object/array).
.PARAMETER Server
    HookView server URL. Defaults to $env:HOOKVIEW_SERVER or http://localhost:8000.
.PARAMETER ApiKey
    Bearer API key. Defaults to $env:HOOKVIEW_API_KEY.
.EXAMPLE
    Send-HookJson -Message "Hello world"
    Send-HookJson -Message @{ event = "deploy"; status = "success" }
#>
function Send-HookJson {
    param(
        [Parameter(Mandatory = $true)] $Message,
        [string] $Server = $script:HookView_Server,
        [string] $ApiKey = $script:HookView_ApiKey
    )

    if (-not $ApiKey) {
        Write-Error "API key is required. Set `$env:HOOKVIEW_API_KEY or pass -ApiKey."
        return $null
    }

    $body = @{ message = $Message } | ConvertTo-Json -Depth 10 -Compress

    try {
        $response = Invoke-RestMethod -Uri "$Server/webhook" `
            -Method Post `
            -Headers @{
                "Authorization" = "Bearer $ApiKey"
                "Content-Type"  = "application/json"
            } `
            -Body $body `
            -ErrorAction Stop

        Write-Host "[✓] Log #$($response.id) created" -ForegroundColor Green
        Write-Host "    message: $($response.message)" -ForegroundColor Cyan
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
    Send a multipart webhook to HookView with optional file upload.
.PARAMETER Message
    The message string or JSON value.
.PARAMETER FilePath
    Path to an optional file to upload.
.PARAMETER Server
    HookView server URL.
.PARAMETER ApiKey
    Bearer API key.
.EXAMPLE
    Send-HookMultipart -Message "Log with file" -FilePath ./report.pdf
#>
function Send-HookMultipart {
    param(
        [Parameter(Mandatory = $true)] $Message,
        [string] $FilePath = "",
        [string] $Server = $script:HookView_Server,
        [string] $ApiKey = $script:HookView_ApiKey
    )

    if (-not $ApiKey) {
        Write-Error "API key is required. Set `$env:HOOKVIEW_API_KEY or pass -ApiKey."
        return $null
    }

    # Convert message to string for multipart (server will parse as JSON if valid)
    $messageStr = $Message
    if ($Message -is [hashtable] -or $Message -is [pscustomobject] -or $Message -is [array]) {
        $messageStr = $Message | ConvertTo-Json -Depth 10 -Compress
    }

    $uri = "$Server/webhook"
    $headers = @{ "Authorization" = "Bearer $ApiKey" }

    if ($FilePath -and (Test-Path $FilePath)) {
        Write-Host "[i] Uploading file: $FilePath" -ForegroundColor Yellow
        $form = @{
            message = $messageStr
            file    = Get-Item -Path $FilePath
        }
        try {
            $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Form $form -ErrorAction Stop
        }
        catch {
            Write-Error "Failed to send multipart webhook: $_"
            return $null
        }
    }
    else {
        $body = @{ message = $messageStr }
        try {
            $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body -ErrorAction Stop
        }
        catch {
            Write-Error "Failed to send webhook: $_"
            return $null
        }
    }

    Write-Host "[✓] Log #$($response.id) created" -ForegroundColor Green
    Write-Host "    message: $($response.message)" -ForegroundColor Cyan
    if ($response.filename) {
        Write-Host "    file:    $($response.filename)" -ForegroundColor Yellow
    }
    return $response
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
            $msg = if ($log.message -is [string]) { $log.message } else { $log.message | ConvertTo-Json -Compress }
            Write-Host "  #$($log.id) [$($log.timestamp)] $($log.ip_address) → $msg" -ForegroundColor Gray
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
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Magenta

    # ── Example 1: Simple string message ──
    Write-Host "`n[1/4] Sending simple string message..." -ForegroundColor Cyan
    Send-HookJson -Message "Hello from PowerShell! 🚀"

    # ── Example 2: JSON object message ──
    Write-Host "`n[2/4] Sending structured JSON object..." -ForegroundColor Cyan
    $payload = @{
        event    = "deploy"
        service  = "api-gateway"
        version  = "v2.1.0"
        duration = 3421
        status   = "success"
    }
    Send-HookJson -Message $payload

    # ── Example 3: Array message ──
    Write-Host "`n[3/4] Sending array message..." -ForegroundColor Cyan
    Send-HookJson -Message @(1, 2, 3, "complete")

    # ── Example 4: Fetch recent logs ──
    Write-Host "`n[4/4] Fetching recent logs..." -ForegroundColor Cyan
    Get-HookLogs -Limit 5

    Write-Host "`n══════════════════════════════════════════════" -ForegroundColor Magenta
    Write-Host "  Done! Import functions with:"                  -ForegroundColor Gray
    Write-Host "  . .\scripts\send-webhook.ps1"                  -ForegroundColor Yellow
    Write-Host "  Send-HookJson -Message 'test'"                 -ForegroundColor Yellow
    Write-Host "══════════════════════════════════════════════" -ForegroundColor Magenta
}
