@echo off
rem VLC Amp - remove it again (VLC itself stays installed).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0taskbar\uninstall.ps1"
if errorlevel 1 pause
