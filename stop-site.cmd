@echo off
cd /d "%~dp0"
docker compose -f compose.yaml -f compose.local.yaml down
if errorlevel 1 pause
