@echo off
setlocal enabledelayedexpansion

REM ── HookView — Webhook Sender (Batch) ──────────────────────────────────
REM
REM  HookView accepts ANY JSON payload — no required fields.
REM  Send whatever shape of data you want.
REM
REM  Usage:
REM    call scripts\send-webhook.bat send-json "string or {...}"  [server] [key]
REM    call scripts\send-webhook.bat send-file "field=val" "C:\file.zip"  [server] [key]
REM    call scripts\send-webhook.bat get-logs [limit]  [server] [key]
REM
REM  Examples:
REM    call scripts\send-webhook.bat send-json "{"event":"deploy","status":"ok"}"
REM    call scripts\send-webhook.bat send-file "event=deploy" "C:\build.zip"
REM    call scripts\send-webhook.bat get-logs 10
REM
REM  To import in another script:
REM    set HOOKVIEW_SERVER=http://localhost:8000
REM    set HOOKVIEW_API_KEY=your-secret-key
REM    call scripts\send-webhook.bat send-json "your payload"
REM
REM ── Configuration ──────────────────────────────────────────────────────

if "%HOOKVIEW_SERVER%"=="" set HOOKVIEW_SERVER=http://localhost:8000
if "%HOOKVIEW_API_KEY%"=="" (
    echo [!] HOOKVIEW_API_KEY is not set. Set the env var or pass API key as argument.
    exit /b 1
)

REM ── Entry point ─────────────────────────────────────────────────────────

if "%~1"=="" goto :help
goto :%~1 2>nul || goto :unknown

REM ═══════════════════════════════════════════════════════════════════════════
REM  Functions (callable from other scripts)
REM ═══════════════════════════════════════════════════════════════════════════

:send-json
REM  Usage: call :send-json "payload" [server] [api-key]
REM    Sends the argument as the raw JSON body (string, object, array, number, etc.)
REM    For objects: call :send-json "{""event"":""deploy"",""status"":""ok""}"
set "_payload=%~1"
set "_srv=%~2"
set "_key=%~3"
if "!_srv!"=="" set "_srv=%HOOKVIEW_SERVER%"
if "!_key!"=="" set "_key=%HOOKVIEW_API_KEY%"

if "!_key!"==""    echo [X] API key required & exit /b 1
if "!_payload!"=="" echo [X] Payload is required & exit /b 1

curl -s -X POST "!_srv!/webhook" ^
  -H "Authorization: Bearer !_key!" ^
  -H "Content-Type: application/json" ^
  -d "!_payload!" > %TEMP%\hookview_response.json

if %errorlevel% neq 0 (
    echo [X] Failed to send webhook
    exit /b 1
)

echo [✓] Response:
type %TEMP%\hookview_response.json
echo.
exit /b 0


:send-file
REM  Usage: call :send-file "field1=val1&field2=val2" "filepath" [server] [api-key]
REM    Sends form fields as a multipart request with optional file attachment.
REM    Example: call :send-file "event=deploy&version=1.0" "C:\build.zip"
set "_fields=%~1"
set "_file=%~2"
set "_srv=%~3"
set "_key=%~4"
if "!_srv!"=="" set "_srv=%HOOKVIEW_SERVER%"
if "!_key!"=="" set "_key=%HOOKVIEW_API_KEY%"

if "!_key!"==""   echo [X] API key required & exit /b 1
if "!_fields!"=="" echo [X] Form fields are required & exit /b 1

REM Build curl command with form fields and optional file
set "_curl_cmd=curl -s -X POST \"!_srv!/webhook\" -H \"Authorization: Bearer !_key!\""

REM Parse field=value pairs separated by &
set "_remaining=!_fields!"
:parse_fields
if "!_remaining!"=="" goto :end_fields
for /f "tokens=1* delims=&" %%a in ("!_remaining!") do (
    set "_pair=%%a"
    set "_remaining=%%b"
    for /f "tokens=1* delims==" %%x in ("!_pair!") do (
        set "_curl_cmd=!_curl_cmd! -F "%%x=%%y""
    )
)
goto :parse_fields
:end_fields

REM Add file if provided
if not "!_file!"=="" (
    if exist "!_file!" (
        echo [i] Uploading file: !_file!
        set "_curl_cmd=!_curl_cmd! -F "file=@!_file!""
    ) else (
        echo [X] File not found: !_file!
        exit /b 1
    )
)

set "_curl_cmd=!_curl_cmd! > %TEMP%\hookview_response.json"

REM Execute the built command
call !_curl_cmd!

if %errorlevel% neq 0 (
    echo [X] Failed to send multipart webhook
    exit /b 1
)

echo [✓] Response:
type %TEMP%\hookview_response.json
echo.
exit /b 0


:get-logs
REM  Usage: call :get-logs [limit] [server] [api-key]
set "_limit=%~1"
set "_srv=%~2"
set "_key=%~3"
if "!_limit!"=="" set "_limit=10"
if "!_srv!"==""   set "_srv=%HOOKVIEW_SERVER%"
if "!_key!"==""   set "_key=%HOOKVIEW_API_KEY%"

if "!_key!"=="" echo [X] API key required & exit /b 1

echo [i] Fetching last !_limit! logs from !_srv!...
curl -s "!_srv!/logs?limit=!_limit!" -H "Authorization: Bearer !_key!"
echo.
exit /b 0


REM ═══════════════════════════════════════════════════════════════════════════
REM  Interactive examples (when run directly)
REM ═══════════════════════════════════════════════════════════════════════════

:help
echo ═══════════════════════════════════════════
echo   HookView - Webhook Sender
echo   Send any JSON payload — no required fields
echo ═══════════════════════════════════════════
echo.
echo Usage:
echo   call scripts\send-webhook.bat ^<command^> [args...]
echo.
echo Commands:
echo   send-json "payload"         Send raw JSON (string, object, array, etc.)
echo   send-file "k=v&k2=v2" file  Send multipart form with optional file
echo   get-logs [limit]            Fetch recent log entries
echo.
echo Examples:
echo   call scripts\send-webhook.bat send-json "{""event"":""deploy"",""status"":""ok""}"
echo   call scripts\send-webhook.bat send-json "42"
echo   call scripts\send-webhook.bat send-json """just a string"""
echo   call scripts\send-webhook.bat send-file "event=deploy&version=1.0" "C:\build.zip"
echo   call scripts\send-webhook.bat get-logs 10
echo.
exit /b 0


:unknown
echo [X] Unknown command: %~1
echo     Available: send-json, send-file, get-logs, help
exit /b 1
