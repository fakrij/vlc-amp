# uninstall.ps1 - remove the Titlebar VLC skin (run by Uninstall.cmd). VLC itself stays installed.
#
#   restores VLC's settings from vlcrc.before-titlebar (the current file is kept as vlcrc.titlebar-removed),
#   stops the helper, removes its Startup shortcut, the Lua extras, the Start menu entries,
#   optionally the media controls plugin, and the installed folder %LOCALAPPDATA%\Titlebar-VLC-skin.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:LOCALAPPDATA "Titlebar-VLC-skin"
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK", $icon = "Information") {
    return [System.Windows.Forms.MessageBox]::Show($text, "Titlebar VLC skin", $buttons, $icon)
}
function Step($text) { Write-Host "-> $text" -ForegroundColor Cyan }

if ((Show-Msg "Remove the Titlebar skin and restore VLC's previous settings?" "YesNo" "Question") -ne "Yes") { exit 0 }

Step "Checking that VLC is closed"
while (Get-Process vlc -ErrorAction SilentlyContinue) {
    if ((Show-Msg "Please close VLC, then click Retry." "RetryCancel" "Warning") -ne "Retry") { exit 1 }
}

Step "Stopping the helper"
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*vlc-taskbar.ps1*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }

Step "Restoring VLC's settings"
$rc = Join-Path $env:APPDATA "vlc\vlcrc"
$backup = "$rc.before-titlebar"
if (Test-Path $rc) { Copy-Item $rc "$rc.titlebar-removed" -Force }
if (Test-Path $backup) {
    Move-Item $backup $rc -Force
    Write-Host "   vlcrc restored from vlcrc.before-titlebar"
} elseif (Test-Path $rc) {
    Remove-Item $rc      # there was no vlcrc before the setup: VLC starts with its defaults
    Write-Host "   vlcrc removed (there was none before the setup); VLC starts with its defaults"
}

Step "Removing the Startup shortcut, Lua extras and Start menu entries"
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Titlebar VLC helper.lnk"
if (Test-Path $lnk) { Remove-Item $lnk }
$lua = Join-Path $env:APPDATA "vlc\lua\intf\titlebar.lua"
if (Test-Path $lua) { Remove-Item $lua }
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Titlebar VLC skin"
if (Test-Path $menu) { Remove-Item -Recurse -Force $menu }

# the media controls plugin is harmless once switched off (restored vlcrc), so only on request
foreach ($key in 'HKLM:\SOFTWARE\VideoLAN\VLC', 'HKLM:\SOFTWARE\WOW6432Node\VideoLAN\VLC') {
    try { $dir = (Get-ItemProperty -Path $key -ErrorAction Stop).InstallDir } catch { continue }
    if (-not $dir) { continue }
    $dll = Join-Path $dir "plugins\misc\libwin10smtc_plugin.dll"
    if (Test-Path $dll) {
        if ((Show-Msg ("Also remove the Windows media controls plugin from VLC's folder?`n`n$dll`n`n" +
                "(Needs admin rights once. Keeping it does no harm: VLC only uses it when switched on.)") "YesNo" "Question") -eq "Yes") {
            $q = "'" + ($dll -replace "'", "''") + "'"
            $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("Remove-Item -LiteralPath $q -Force"))
            try { Start-Process powershell.exe -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "-NoProfile -EncodedCommand $enc" } catch { }
        }
        break
    }
}

if (Test-Path $dest) {
    Step "Removing $dest"
    if ($here -like "$dest\*") {
        # this script runs from that folder: delete it from a separate process after this one has exited
        Set-Location $env:TEMP
        Start-Process cmd.exe -WindowStyle Hidden -ArgumentList "/c timeout /t 3 /nobreak >nul & rmdir /s /q `"$dest`""
    } else {
        Remove-Item -Recurse -Force $dest
    }
}

Show-Msg ("The Titlebar skin is removed. VLC starts with its previous settings.`n`n" +
    "Your last settings file is kept as $rc.titlebar-removed.") | Out-Null
exit 0
