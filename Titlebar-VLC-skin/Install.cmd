@echo off
rem Titlebar VLC skin - one-step install. Double-click this file.
rem Copies the skin to %LOCALAPPDATA%\Titlebar-VLC-skin, installs VLC if it is missing,
rem sets VLC up (taskbar\vlc-taskbar.ps1 -Setup) and adds Start menu entries.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0taskbar\install.ps1"
if errorlevel 1 pause
