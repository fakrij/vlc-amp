# install.ps1 - one-step install of the Titlebar VLC skin (run by Install.cmd).
#
#   1. unblocks the files (Windows marks files copied from another computer)
#   2. installs VLC 3 with winget if it is missing
#   3. waits until VLC is closed
#   4. copies this folder to %LOCALAPPDATA%\Titlebar-VLC-skin (the skin must stay somewhere permanent)
#   5. runs the setup from there (vlc-taskbar.ps1 -Setup: VLC settings, helper, media controls, Lua extras)
#   6. adds Start menu entries: setup again, VLC in taskbar, uninstall, skin folder
$ErrorActionPreference = "Stop"
$src  = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path   # the folder Install.cmd is in
$dest = Join-Path $env:LOCALAPPDATA "Titlebar-VLC-skin"
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK", $icon = "Information") {
    return [System.Windows.Forms.MessageBox]::Show($text, "Titlebar VLC skin", $buttons, $icon)
}
function Step($text) { Write-Host "-> $text" -ForegroundColor Cyan }

function Find-Vlc {
    foreach ($key in 'HKLM:\SOFTWARE\VideoLAN\VLC', 'HKLM:\SOFTWARE\WOW6432Node\VideoLAN\VLC') {
        try {
            $k = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($k.InstallDir -and (Test-Path (Join-Path $k.InstallDir 'vlc.exe'))) { return (Join-Path $k.InstallDir 'vlc.exe') }
        } catch { }
    }
    foreach ($p in "$env:ProgramFiles\VideoLAN\VLC\vlc.exe", "${env:ProgramFiles(x86)}\VideoLAN\VLC\vlc.exe") {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

Write-Host "Titlebar VLC skin - install`n"
if (-not (Test-Path (Join-Path $src "taskbar\vlc-taskbar.ps1")) -or -not (Get-ChildItem $src -Filter "Titlebar-*.vlt")) {
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
        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*vlc-taskbar.ps1*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    # mirror: the folder holds only this package (your own edits of vlc-taskbar.ps1 there are replaced)
    & robocopy.exe $src $dest /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Show-Msg "Copying to $dest failed (robocopy code $LASTEXITCODE)." "OK" "Error" | Out-Null; exit 1 }
}

Step "Setting up VLC (answer the questions in the windows that open)"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dest "taskbar\vlc-taskbar.ps1") -Setup
if ($LASTEXITCODE -ne 0) { Write-Host "   Setup stopped (code $LASTEXITCODE)."; exit 1 }

Step "Adding Start menu entries"
$menu = Join-Path ([Environment]::GetFolderPath("Programs")) "Titlebar VLC skin"
New-Item -ItemType Directory -Force -Path $menu | Out-Null
$sh = New-Object -ComObject WScript.Shell
foreach ($e in @(
        @{ Name = "Titlebar skin setup";     Target = "$dest\taskbar\Setup.cmd" },
        @{ Name = "VLC in taskbar";          Target = "$dest\taskbar\VLC in taskbar.cmd" },
        @{ Name = "Uninstall Titlebar skin"; Target = "$dest\Uninstall.cmd" },
        @{ Name = "Titlebar skin folder";    Target = $dest })) {
    $s = $sh.CreateShortcut((Join-Path $menu ($e.Name + ".lnk")))
    $s.TargetPath = $e.Target
    $s.WorkingDirectory = $dest
    if ($e.Target -like "*.cmd") { $s.WindowStyle = 7; $s.IconLocation = "$vlc,0" }
    $s.Save()
}

Write-Host "`nDone. Open a music file or folder to start VLC with the skin." -ForegroundColor Green
Write-Host "Start menu > Titlebar VLC skin: setup again, VLC in taskbar, uninstall."
Write-Host "You can delete the folder you ran Install.cmd from."
Start-Sleep -Seconds 4
exit 0
