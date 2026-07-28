@echo off
REM Двойной клик запускает демо Onvy с доступом со всех устройств.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1"
