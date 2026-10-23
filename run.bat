@echo off
REM DiskDoctor launcher. Uses py launcher (Python 3.10+).
cd /d "%~dp0"
py main.py
if errorlevel 1 (
  echo.
  echo DiskDoctor exited with an error. Press any key to close.
  pause >nul
)
