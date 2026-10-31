@echo off
rem Pick the accent colour of the Custom theme in the Titlebar-*.vlt files next to this folder.
rem A colour dialog opens; VLC must be closed, restart it afterwards. Details: custom-colour.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0custom-colour.ps1" %*
if errorlevel 1 pause
