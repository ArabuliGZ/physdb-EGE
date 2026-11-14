@echo off
cd /d "%~dp0"
set "PHYSEGE_EDITING=1"
set "PHYSEGE_EDIT_LOG=%~dp0tools\site_edits\problem_text_edits.json"
if defined PHYSEGE_PYTHON (
    "%PHYSEGE_PYTHON%" web\server.py
) else if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
    "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" web\server.py
) else (
    python web\server.py
)
pause
