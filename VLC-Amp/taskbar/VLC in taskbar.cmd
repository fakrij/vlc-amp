@echo off
rem Starts VLC with the VLC Amp skin docked in the taskbar. Settings: vlc-taskbar.ps1
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0vlc-taskbar.ps1"
