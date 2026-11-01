@echo off
rem One-time setup: VLC uses the VLC Amp skin also when you open files from Explorer.
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0vlc-taskbar.ps1" -Setup
