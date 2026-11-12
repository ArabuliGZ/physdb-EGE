@echo off
cd /d "%~dp0"
docker compose up --build -d
if errorlevel 1 pause
