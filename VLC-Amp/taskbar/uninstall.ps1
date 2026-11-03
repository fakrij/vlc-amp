# uninstall.ps1 - remove the VLC Amp (run by Uninstall.cmd). VLC itself stays installed.
#
#   restores VLC's settings from vlcrc.before-vlc-amp (the current file is kept as vlcrc.vlc-amp-removed),
#   stops the helper, removes its Startup shortcut, the Lua extras, the Start menu entries,
#   the vlc-amp: link handler and the relay secret (links from the browser),
#   the per-user file association overrides listed in file-associations.txt (only keys that still have
#   --no-media-library),
#   optionally the media controls plugin, and the installed folder %LOCALAPPDATA%\VLC-Amp.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:LOCALAPPDATA "VLC-Amp"
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK", $icon = "Information") {
    return [System.Windows.Forms.MessageBox]::Show($text, "VLC Amp", $buttons, $icon)
}
function Step($text) { Write-Host "-> $text" -ForegroundColor Cyan }

if ((Show-Msg "Remove the VLC Amp skin and restore VLC's previous settings?" "YesNo" "Question") -ne "Yes") { exit 0 }

Step "Checking that VLC is closed"
while (Get-Process vlc -ErrorAction SilentlyContinue) {
    if ((Show-Msg "Please close VLC, then click Retry." "RetryCancel" "Warning") -ne "Retry") { exit 1 }
}

Step "Stopping the helper"
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like "*vlc-taskbar.ps1*" -or $_.CommandLine -like "*vlc-amp-url.ps1*") } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }

Step "Restoring VLC's settings"
$rc = Join-Path $env:APPDATA "vlc\vlcrc"
$backup = "$rc.before-vlc-amp"
if (Test-Path $rc) { Copy-Item $rc "$rc.vlc-amp-removed" -Force }
if (Test-Path $backup) {
    Move-Item $backup $rc -Force
    Write-Host "   vlcrc restored from vlcrc.before-vlc-amp"
} elseif (Test-Path $rc) {
    Remove-Item $rc      # there was no vlcrc before the setup: VLC starts with its defaults
    Write-Host "   vlcrc removed (there was none before the setup); VLC starts with its defaults"
}
if (Test-Path "$rc.vlc-amp-created") { Remove-Item "$rc.vlc-amp-created" }

Step "Removing the file association overrides (--no-media-library)"
# Setup wrote HKCU\Software\Classes\<ProgID>\shell\<verb>\command for the VLC ProgIDs and listed them, one
# path under HKCU per line, in file-associations.txt. Remove exactly those keys, and only when the command
# still has our flag (otherwise the user or another program changed it). Then the verb, shell and ProgID keys
# if they are empty now. HKLM (VLC's own entries) is never touched.
function Remove-EmptyKey($hive, $path) {
    $k = $hive.OpenSubKey($path)
    if (-not $k) { return $false }
    $empty = ($k.SubKeyCount -eq 0 -and $k.ValueCount -eq 0)
    $k.Close()
    if ($empty) { $hive.DeleteSubKey($path, $false) }
    return $empty
}
$assocFile = Join-Path $dest "file-associations.txt"
if (Test-Path -LiteralPath $assocFile) {
    $hkcu = [Microsoft.Win32.RegistryKey]::OpenBaseKey('CurrentUser', 'Registry64')
    $removed = 0
    foreach ($line in [IO.File]::ReadAllLines($assocFile)) {
        $rel = $line.Trim()
        if (-not $rel -or $rel.StartsWith('#')) { continue }
        if ($rel -notmatch '^Software\\Classes\\.+\\shell\\[^\\]+\\command$') { continue }   # only keys of this kind
        try {
            $k = $hkcu.OpenSubKey($rel)
            if (-not $k) { continue }
            $cmd = [string]$k.GetValue('')
            $k.Close()
            if ($cmd -notmatch '(^|\s)--no-media-library(\s|$)') { continue }
            $hkcu.DeleteSubKeyTree($rel, $false)
            $removed++
            $verbKey  = $rel.Substring(0, $rel.LastIndexOf('\'))
            $shellKey = $verbKey.Substring(0, $verbKey.LastIndexOf('\'))
            $progKey  = $shellKey.Substring(0, $shellKey.LastIndexOf('\'))
            foreach ($up in $verbKey, $shellKey, $progKey) { if (-not (Remove-EmptyKey $hkcu $up)) { break } }
        } catch { }
    }
    Write-Host "   $removed registry key(s) removed"
}

Step "Removing the Startup shortcut, Lua extras and Start menu entries"
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "VLC Amp helper.lnk"
if (Test-Path $lnk) { Remove-Item $lnk }
$lua = Join-Path $env:APPDATA "vlc\lua\intf\vlcamp.lua"
if (Test-Path $lua) { Remove-Item $lua }
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "VLC Amp"
if (Test-Path $menu) { Remove-Item -Recurse -Force $menu }

Step "Removing the vlc-amp: link handler (links from the browser)"
$linkKey = "HKCU:\Software\Classes\vlc-amp"
$cmd = Get-Item -Path "$linkKey\shell\open\command" -ErrorAction SilentlyContinue
if ($cmd -and $cmd.GetValue("") -like "*vlc-amp-url.vbs*") { Remove-Item -Path $linkKey -Recurse -Force }
$state = Join-Path $env:LOCALAPPDATA "VLC-Amp-state"   # the relay's secret
if (Test-Path $state) { Remove-Item -Recurse -Force $state }
Write-Host "   (the browser extension and yt-dlp stay; remove them in the browser and with winget uninstall yt-dlp.yt-dlp)"

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

Show-Msg ("The VLC Amp skin is removed. VLC starts with its previous settings.`n`n" +
    "Your last settings file is kept as $rc.vlc-amp-removed.") | Out-Null
exit 0
