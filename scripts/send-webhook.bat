@echo off
setlocal enabledelayedexpansion

REM ── HookView — Webhook Sender (Batch) ──────────────────────────────────
REM
REM  Usage:
REM    call scripts\send-webhook.bat send-json "your message"
REM    call scripts\send-webhook.bat send-json "{""event"":""deploy""}" "http://..." "key"
REM    call scripts\send-webhook.bat send-file "message" "C:\path\to\file.zip"
REM    call scripts\send-webhook.bat get-logs [limit]
REM
REM  To import in another script:
REM    set HOOKVIEW_SERVER=http://localhost:8000
REM    set HOOKVIEW_API_KEY=your-secret-key
REM    call scripts\send-webhook.bat send-json "Deploy completed!"
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
REM  Usage: call :send-json "message" [server] [api-key]
set "_msg=%~1"
set "_srv=%~2"
set "_key=%~3"
if "!_srv!"=="" set "_srv=%HOOKVIEW_SERVER%"
if "!_key!"=="" set "_key=%HOOKVIEW_API_KEY%"

if "!_key!"=="" echo [X] API key required & exit /b 1
if "!_msg!"==""  echo [X] Message is required & exit /b 1

REM Build JSON payload and send
set "_payload={\"message\":!_msg!}"
curl -s -X POST "!_srv!/webhook" ^
  -H "Authorization: Bearer !_key!" ^
  -H "Content-Type: application/json" ^
  -d "!_payload!" > %TEMP%\hookview_response.json

if %errorlevel% neq 0 (
    echo [X] Failed to send webhook
    exit /b 1
)

REM Parse and display response
echo [✓] Response:
type %TEMP%\hookview_response.json
echo.
exit /b 0


:send-file
REM  Usage: call :send-file "message" "filepath" [server] [api-key]
set "_msg=%~1"
set "_file=%~2"
set "_srv=%~3"
set "_key=%~4"
if "!_srv!"=="" set "_srv=%HOOKVIEW_SERVER%"
if "!_key!"=="" set "_key=%HOOKVIEW_API_KEY%"

if "!_key!"==""  echo [X] API key required & exit /b 1
if "!_msg!"==""   echo [X] Message is required & exit /b 1
if "!_file!"==""  echo [X] File path is required & exit /b 1
if not exist "!_file!" echo [X] File not found: !_file! & exit /b 1

curl -s -X POST "!_srv!/webhook" ^
  -H "Authorization: Bearer !_key!" ^
  -F "message=!_msg!" ^
  -F "file=@!_file!" > %TEMP%\hookview_response.json

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
echo ═══════════════════════════════════════════
echo.
echo Usage:
echo   %% HookView ^> call scripts\send-webhook.bat ^<command^> [args...]
echo.
echo Commands:
echo   send-json "message"     Send a string or JSON message
echo   send-file "msg" "file"  Send message with file upload
echo   get-logs [limit]        Fetch recent log entries
echo.
echo Examples:
echo   call scripts\send-webhook.bat send-json "Hello World"
echo   call scripts\send-webhook.bat send-json "{""event"":""deploy""}"
echo   call scripts\send-webhook.bat send-file "Report" "C:\log.zip"
echo   call scripts\send-webhook.bat get-logs 5
echo.
exit /b 0


:unknown
echo [X] Unknown command: %~1
echo     Available: send-json, send-file, get-logs, help
exit /b 1
