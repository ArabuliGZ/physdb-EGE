@echo off
cd /d "%~dp0"
if defined PHYSEGE_PYTHON (
    "%PHYSEGE_PYTHON%" web\server.py
) else if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" web\server.py
) else (
    python web\server.py
)
pause
