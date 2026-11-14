@echo off
cd /d "%~dp0"
docker compose -f compose.yaml -f compose.local.yaml up --build --force-recreate -d
if errorlevel 1 pause
