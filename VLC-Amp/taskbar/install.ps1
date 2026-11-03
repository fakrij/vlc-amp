# install.ps1 - one-step install of the VLC Amp (run by Install.cmd).
#
#   1. unblocks the files (Windows marks files copied from another computer)
#   2. installs VLC 3 with winget if it is missing
#   3. waits until VLC is closed
#   4. copies this folder to %LOCALAPPDATA%\VLC-Amp (the skin must stay somewhere permanent)
#   5. runs the setup from there (vlc-taskbar.ps1 -Setup: VLC settings, helper, media controls, Lua extras)
#   6. adds Start menu entries: setup again, VLC in taskbar, uninstall, skin folder, and "VLC Amp"
#      (vlc.exe with --no-media-library: VLC's own launcher forces the Media Library on)
$ErrorActionPreference = "Stop"
$src  = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path   # the folder Install.cmd is in
$dest = Join-Path $env:LOCALAPPDATA "VLC-Amp"
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK", $icon = "Information") {
    return [System.Windows.Forms.MessageBox]::Show($text, "VLC Amp", $buttons, $icon)
}
function Step($text) { Write-Host "-> $text" -ForegroundColor Cyan }

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'find-vlc.ps1')   # Find-Vlc (shared with vlc-taskbar.ps1)

Write-Host "VLC Amp - install`n"
if (-not (Test-Path (Join-Path $src "taskbar\vlc-taskbar.ps1")) -or -not (Get-ChildItem $src -Filter "VLC-Amp-*.vlt")) {
    Show-Msg "Files are missing next to Install.cmd. Copy the whole folder and run Install.cmd again." "OK" "Error" | Out-Null
    exit 1
}

Step "Unblocking the files"
Get-ChildItem -Path $src -Recurse -File | ForEach-Object { try { Unblock-File -LiteralPath $_.FullName } catch { } }

Step "Looking for VLC"
$vlc = Find-Vlc
if (-not $vlc) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget -and (Show-Msg "VLC is not installed. Install it now (winget, VideoLAN.VLC)?" "YesNo" "Question") -eq "Yes") {
        Step "Installing VLC with winget (this can take a minute)"
        & $winget.Source install --id VideoLAN.VLC --exact --silent --accept-package-agreements --accept-source-agreements
        $vlc = Find-Vlc
    }
    if (-not $vlc) {
        Show-Msg "Please install VLC 3 from https://www.videolan.org/vlc/ and run Install.cmd again." "OK" "Warning" | Out-Null
        Start-Process "https://www.videolan.org/vlc/"
        exit 1
    }
}
$ver = (Get-Item $vlc).VersionInfo.FileVersion
Write-Host "   VLC $ver at $vlc"
if ($ver -and -not $ver.StartsWith("3.")) {
    if ((Show-Msg "This skin is made for VLC 3; you have VLC $ver. Continue anyway?" "YesNo" "Warning") -ne "Yes") { exit 1 }
}

Step "Checking that VLC is closed"
while (Get-Process vlc -ErrorAction SilentlyContinue) {
    if ((Show-Msg "Please close VLC (it rewrites its settings when it exits), then click Retry." "RetryCancel" "Warning") -ne "Retry") { exit 1 }
}

if ($src.TrimEnd('\') -ne $dest.TrimEnd('\')) {
    Step "Copying the skin to $dest"
    # a running helper uses the old copy: stop it (the setup starts it again)
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like "*vlc-taskbar.ps1*" -or $_.CommandLine -like "*vlc-amp-url.ps1*") } |
        ForEach-Object {
            try { Add-Content -LiteralPath (Join-Path $env:TEMP "vlc-amp-helper.log") -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff") + "  helper (pid " + $_.ProcessId + ") stopped by Install (new copy)") } catch { }
            Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    # mirror: the folder holds only this package (your own edits of vlc-taskbar.ps1 there are replaced)
    # (file-associations.txt is written by the setup, it is not in the package: /XF keeps /MIR from deleting it)
    & robocopy.exe $src $dest /MIR /XF file-associations.txt /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Show-Msg "Copying to $dest failed (robocopy code $LASTEXITCODE)." "OK" "Error" | Out-Null; exit 1 }
}

Step "Setting up VLC (answer the questions in the windows that open)"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dest "taskbar\vlc-taskbar.ps1") -Setup
if ($LASTEXITCODE -ne 0) { Write-Host "   Setup stopped (code $LASTEXITCODE)."; exit 1 }

Step "Adding Start menu entries"
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "VLC Amp"
New-Item -ItemType Directory -Force -Path $menu | Out-Null
$sh = New-Object -ComObject WScript.Shell
foreach ($e in @(
        @{ Name = "VLC Amp setup";     Target = "$dest\taskbar\Setup.cmd" },
        @{ Name = "VLC in taskbar";          Target = "$dest\taskbar\VLC in taskbar.cmd" },
        @{ Name = "Uninstall VLC Amp"; Target = "$dest\Uninstall.cmd" },
        @{ Name = "VLC Amp folder";    Target = $dest })) {
    $s = $sh.CreateShortcut((Join-Path $menu ($e.Name + ".lnk")))
    $s.TargetPath = $e.Target
    $s.WorkingDirectory = $dest
    if ($e.Target -like "*.cmd") { $s.WindowStyle = 7; $s.IconLocation = "$vlc,0" }
    $s.Save()
}

# VLC's own Start menu entry, desktop icon and a pinned taskbar icon start vlc.exe without the flag, so the
# Media Library entry shows there. Those shortcuts are in the all-users Start menu or pinned (changing them needs
# admin, or is not allowed for pins), so this extra per-user one is the way to start VLC without it. It starts
# vlc.exe through taskbar\launch.vbs, which also starts the helper if it should run and does not.
$s = $sh.CreateShortcut((Join-Path $menu "VLC Amp.lnk"))
$s.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
$s.Arguments = "`"$dest\taskbar\launch.vbs`" `"$vlc`" --no-media-library"
$s.WorkingDirectory = Split-Path -Parent $vlc
$s.IconLocation = "$vlc,0"
$s.Description = "VLC with the VLC Amp skin, without the Media Library entry in the playlist"
$s.Save()

Write-Host "`nDone. Open a music file or folder to start VLC with the skin." -ForegroundColor Green
Write-Host "Start menu > VLC Amp: VLC Amp, setup again, VLC in taskbar, uninstall."
Write-Host "Files opened from Explorer start without the Media Library entry. VLC's own Start menu entry and a pinned VLC icon still show it: use VLC Amp."
Write-Host "You can delete the folder you ran Install.cmd from."
Start-Sleep -Seconds 4
exit 0
