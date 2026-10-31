# vlc-taskbar.ps1 - Titlebar skin helper for Windows.
#
#   VLC in taskbar.cmd     start VLC with the skin, docked in the taskbar
#   Setup.cmd              one-time setup (VLC settings + optional start with Windows)
#
# Switches (used by the .cmd files and the startup shortcut):
#   -Setup    write VLC's settings, offer to start the helper with Windows, then exit
#   -Watch    do not start VLC; wait for it (files opened from Explorer), keep running
#   -NoDock   do not dock in the taskbar, only pin VLC on top when it starts
#   -DebugLog write a log to %TEMP%\titlebar-helper.log (or set the $DebugLog line below to $true)
param([switch]$Setup, [switch]$Watch, [switch]$NoDock, [switch]$DebugLog)

# ---------------- settings ----------------
$Skin              = "auto"             # "auto" = pick the skin file from the Windows display scale (the taller Titlebar-taskbar-NNN.vlt when docking and it exists), or a file name
$DockTo            = "start"            # start = left of the Start button | left = left end of taskbar | right = next to the tray icons
$Gap               = 8                  # pixels between the strip and the Start button / edge
$OffsetY           = 0                  # nudge the strip up (-) or down (+) inside the taskbar
$HideVlcTaskbarButton = $true           # the player is in the taskbar already, so hide VLC's own taskbar button
$StartVlc          = $true              # start VLC if it is not running (not in -Watch mode)
$StartPinned       = $true              # pin VLC "always on top" each time it starts
$DebugLog          = $DebugLog.IsPresent -or $false   # $true = log what the helper does to %TEMP%\titlebar-helper.log
$TrayIcon          = $true              # notification-area icon with a menu (dock on / off, pin now, quit)
$VlcControl        = $true              # read VLC's state and send it commands through its local web interface (Setup enables it)
# -----------------------------------------

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK") {
    return [System.Windows.Forms.MessageBox]::Show($text, "Titlebar VLC skin", $buttons)
}

# Strip height (logical px) of the taller skin build "Titlebar-taskbar-NNN.vlt" (generator --bar-height);
# "Titlebar-bar<N>-NNN.vlt" carries its own height in the name. Plain "Titlebar-NNN.vlt" is 24.
$TaskbarBarHeight = 36

# Scale (1.5) and strip height (24, 36, ...) from a skin file name, as @{ Scale = ..; BarHeight = .. }
function Get-SkinInfo($path) {
    $info = @{ Scale = 1.0; BarHeight = 24 }
    if (-not $path) { return $info }
    $leaf = Split-Path -Leaf $path
    if ($leaf -match '^Titlebar-(taskbar|bar(\d+))-(\d+)\.vlt$') {
        $info.Scale = [int]$Matches[3] / 100.0
        if ($Matches[2]) { $info.BarHeight = [int]$Matches[2] } else { $info.BarHeight = $TaskbarBarHeight }
    } elseif ($leaf -match '-(\d+)\.vlt$') {
        $info.Scale = [int]$Matches[1] / 100.0
    }
    return $info
}

# Skin file for the current display scale (AppliedDPI: 96 = 100 %, 120 = 125 %, 144 = 150 %, 192 = 200 %).
# -Taskbar: the skin is docked in the taskbar, so prefer the taller Titlebar-taskbar-NNN.vlt if it exists.
function Get-SkinPath([switch]$Taskbar) {
    $name = $Skin
    if ($name -eq "auto") {
        $dpi = 96
        try { $dpi = [int](Get-ItemProperty 'HKCU:\Control Panel\Desktop\WindowMetrics' -Name AppliedDPI).AppliedDPI } catch { }
        $pct = $dpi * 100 / 96
        $best = 100
        foreach ($s in 100, 125, 150, 200) { if ([math]::Abs($s - $pct) -lt [math]::Abs($best - $pct)) { $best = $s } }
        $name = "Titlebar-$best.vlt"
        if ($Taskbar) {
            foreach ($dir in $root, $here) {
                if (Test-Path (Join-Path $dir "Titlebar-taskbar-$best.vlt")) { $name = "Titlebar-taskbar-$best.vlt"; break }
            }
        }
    }
    foreach ($dir in $root, $here) {
        $p = Join-Path $dir $name
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    return $null
}

function Find-Vlc {
    foreach ($key in 'HKLM:\SOFTWARE\VideoLAN\VLC', 'HKLM:\SOFTWARE\WOW6432Node\VideoLAN\VLC') {
        try {
            $k = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($k.InstallDir -and (Test-Path (Join-Path $k.InstallDir 'vlc.exe'))) { return (Join-Path $k.InstallDir 'vlc.exe') }
            if ($k.'(default)' -and (Test-Path $k.'(default)')) { return $k.'(default)' }
        } catch { }
    }
    foreach ($p in "$env:ProgramFiles\VideoLAN\VLC\vlc.exe", "${env:ProgramFiles(x86)}\VideoLAN\VLC\vlc.exe") {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

# Set "key=value" in VLC's vlcrc: rewrites every line for that key (the commented-out
# default "#key=..." and any active one; vlcrc can have both), or adds it to its [section].
function Set-VlcOption([System.Collections.Generic.List[string]]$lines, $section, $key, $value) {
    $pattern = '^\s*#?\s*' + [regex]::Escape($key) + '='
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) { $lines[$i] = "$key=$value"; $found = $true }
    }
    if ($found) { return }
    $head = $lines.IndexOf("[$section]")
    if ($head -lt 0) { $lines.Add(""); $lines.Add("[$section]"); $lines.Add("$key=$value"); return }
    $end = $head + 1
    while ($end -lt $lines.Count -and -not $lines[$end].StartsWith("[")) { $end++ }
    $lines.Insert($end, "$key=$value")
}

# Add (or with -Remove take out) a module in a colon-separated vlcrc list such as
# "extraintf=http:win10smtc", keeping the modules that are already there.
function Set-VlcModule([System.Collections.Generic.List[string]]$lines, $section, $key, $module, [switch]$Remove) {
    $mods = New-Object 'System.Collections.Generic.List[string]'
    foreach ($l in $lines) {
        if ($l -match ('^\s*' + [regex]::Escape($key) + '=(.*)$')) {
            foreach ($m in $Matches[1].Split(':')) { if ($m.Trim() -and -not $mods.Contains($m.Trim())) { $mods.Add($m.Trim()) } }
        }
    }
    if ($Remove) { [void]$mods.Remove($module) } elseif (-not $mods.Contains($module)) { $mods.Add($module) }
    Set-VlcOption $lines $section $key ($mods -join ':')
}

# ---- Windows media controls: the third-party plugin vlc-win10smtc (GPL-3.0) ----
# https://github.com/spmn/vlc-win10smtc - media keys, the volume / media flyout, Quick Settings, lock screen.
# Pinned release; the hashes are the zip digests published by GitHub for that release.
$SmtcVersion = "v5.0.0"
$SmtcSha256  = @{
    x64   = "2de0bc5d560635bb7be4dc7825461dcd8d1afe9fb9d865ea141ff145df163fa6"
    x86   = "bb183b2c84b90a8e1ca867c7780340562b061dd8c748493b4d9687caab5d4ab4"
    arm64 = "a2d2e6788af7b1a4914f9ce9feb7d9fa2dc1f2c8bf7e60ac88b7232a5b09753a"
}

# x64 / x86 / arm64 from the PE header of vlc.exe (the plugin must match VLC, not Windows)
function Get-ExeArch($exe) {
    $b = [IO.File]::ReadAllBytes($exe)
    $pe = [BitConverter]::ToInt32($b, 0x3C)
    switch ([BitConverter]::ToUInt16($b, $pe + 4)) {
        0x8664 { return "x64" }
        0x014C { return "x86" }
        0xAA64 { return "arm64" }
    }
    return $null
}

# Visual C++ 2015-2022 runtime (14.30+ = 2022) for one architecture, as the plugin needs it
function Test-VcRuntime($arch) {
    foreach ($key in "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\$arch",
                     "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\$arch") {
        try {
            $k = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($k.Installed -eq 1 -and ($k.Major -gt 14 -or ($k.Major -eq 14 -and $k.Minor -ge 30))) { return $true }
        } catch { }
    }
    return $false
}

# Run a script block's text as administrator (one UAC prompt) and wait for it
function Invoke-Elevated($script) {
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    $p = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -WindowStyle Hidden `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $enc"
    return $p.ExitCode
}

# Returns $true when the plugin is in VLC's plugins\misc folder afterwards
function Install-SmtcPlugin($vlcExe) {
    $ProgressPreference = "SilentlyContinue"   # PowerShell 5.1 downloads very slowly with the progress bar
    $dir = Join-Path (Split-Path $vlcExe) "plugins\misc"
    $dll = Join-Path $dir "libwin10smtc_plugin.dll"
    if (Test-Path $dll) { return $true }
    $arch = Get-ExeArch $vlcExe
    if (-not $arch) { Show-Msg "Unknown VLC architecture; media controls not installed." | Out-Null; return $false }

    if (-not (Test-VcRuntime $arch)) {
        $ok = (Show-Msg ("The media controls plugin needs the Microsoft Visual C++ runtime ($arch), which is not installed.`n`n" +
            "Download it from Microsoft and install it now?") "YesNo") -eq "Yes"
        if (-not $ok) { return $false }
        $exe = Join-Path $env:TEMP "vc_redist.$arch.exe"
        Invoke-WebRequest -UseBasicParsing "https://aka.ms/vs/17/release/vc_redist.$arch.exe" -OutFile $exe
        $sig = Get-AuthenticodeSignature $exe
        if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=Microsoft Corporation") {
            Show-Msg "The downloaded runtime is not signed by Microsoft; not installed." | Out-Null; return $false
        }
        Start-Process $exe -ArgumentList "/install /passive /norestart" -Verb RunAs -Wait
        if (-not (Test-VcRuntime $arch)) { Show-Msg "The Visual C++ runtime did not install; media controls skipped." | Out-Null; return $false }
    }

    $name = "libwin10smtc_plugin_$($SmtcVersion)_$arch.zip"
    $zip = Join-Path $env:TEMP $name
    $tmp = Join-Path $env:TEMP "titlebar-smtc"
    Invoke-WebRequest -UseBasicParsing "https://github.com/spmn/vlc-win10smtc/releases/download/$SmtcVersion/$name" -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $SmtcSha256[$arch]) {
        Remove-Item $zip
        Show-Msg "The downloaded plugin does not match the expected checksum; not installed." | Out-Null; return $false
    }
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive $zip $tmp
    $src = Get-ChildItem $tmp -Recurse -Filter "libwin10smtc_plugin.dll" | Select-Object -First 1
    if (-not $src) { Show-Msg "libwin10smtc_plugin.dll not found in the download." | Out-Null; return $false }

    try {   # portable VLC: the folder is writable, no admin needed
        Copy-Item $src.FullName $dll -ErrorAction Stop
    } catch {
        $q = { param($t) "'" + ($t -replace "'", "''") + "'" }   # quote a path for the elevated command
        Invoke-Elevated ("New-Item -ItemType Directory -Force -Path $(& $q $dir) | Out-Null; " +
            "Copy-Item -LiteralPath $(& $q $src.FullName) -Destination $(& $q $dll) -Force") | Out-Null
    }
    Remove-Item -Recurse -Force $tmp, $zip
    if (-not (Test-Path $dll)) { Show-Msg "Could not copy the plugin into $dir (admin rights refused?)." | Out-Null; return $false }
    return $true
}

# The value of the last active "key=value" line of vlcrc (commented-out defaults do not count),
# or $null when there is none.
function Get-VlcSetting($lines, $key) {
    $val = $null
    foreach ($l in $lines) {
        if ($l -match ('^\s*' + [regex]::Escape($key) + '=(.*)$')) { $val = $Matches[1].Trim() }
    }
    if ($val) { return $val }
    return $null
}

# A random password of letters and digits (only used to lock VLC's local web interface).
function New-Password($length = 24) {
    $alphabet = [char[]]'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $buf = New-Object byte[] 1
    $pw = ""
    while ($pw.Length -lt $length) {
        $rng.GetBytes($buf)
        if ($buf[0] -lt 248) { $pw += $alphabet[$buf[0] % 62] }   # 248 = 4 x 62: no modulo bias
    }
    $rng.Dispose()
    return $pw
}

# Port and password of VLC's web interface, read from vlcrc (Setup wrote them). $null when the
# web interface is not set up: the helper then leaves the control channel off.
function Get-VlcRemote {
    $rc = Join-Path $env:APPDATA "vlc\vlcrc"
    if (-not (Test-Path $rc)) { return $null }
    try { $lines = [IO.File]::ReadAllLines($rc) } catch { return $null }
    $mods = @((Get-VlcSetting $lines "extraintf") -split ':' | ForEach-Object { $_.Trim() })
    $password = Get-VlcSetting $lines "http-password"
    if (-not ($mods -contains 'http' -or $mods -contains 'luahttp') -or -not $password) { return $null }
    $port = 8080   # VLC's default
    $p = Get-VlcSetting $lines "http-port"
    if ($p -match '^\d+$') { $port = [int]$p }
    return @{ Port = $port; Password = $password }
}

# ---- Lua interface (lua\intf\titlebar.lua): A-B loop, next / previous folder, EQ presets ----
# Its triggers are VLC hotkey actions that do nothing for music (see docs/architecture.md, "Lua interface").
# Default vlcrc settings come from lua\vlcrc-keys.txt (shared with linux/setup.sh): one "<section> <key>=<value>"
# per line, "#" lines and blank lines ignored. A key is written only where vlcrc has no active, non-empty value.
function Set-VlcDefaults([System.Collections.Generic.List[string]]$lines, $file) {
    if (-not (Test-Path $file)) { return }
    foreach ($l in [IO.File]::ReadAllLines($file)) {
        $t = $l.Trim()
        if (-not $t -or $t.StartsWith("#")) { continue }
        if ($t -match '^(\S+)\s+([^=\s]+)=(.*)$') {
            $sec = $Matches[1]; $key = $Matches[2]; $val = $Matches[3].Trim()
            if ($val -and -not (Get-VlcSetting $lines $key)) { Set-VlcOption $lines $sec $key $val }
        }
    }
}

function Invoke-Setup {
    if (Get-Process vlc -ErrorAction SilentlyContinue) {
        Show-Msg "Please close VLC first, then run Setup again.`n(VLC rewrites its settings file when it exits.)" | Out-Null
        exit 1
    }
    if (-not (Get-SkinPath)) { Show-Msg "Skin file not found next to the taskbar folder." | Out-Null; exit 1 }

    $autostart = (Show-Msg ("Start the helper with Windows? It pins VLC on top each time VLC starts " +
        "(also when you open a file from Explorer).") "YesNo") -eq "Yes"
    $dock = $false
    if ($autostart) {
        $dock = (Show-Msg ("Also dock the player in the taskbar, left of the Start button?`n`n" +
            "No = the player stays where you put it (for example in a window title bar).") "YesNo") -eq "Yes"
    }

    # the strip is taller in the taskbar build (Titlebar-taskbar-NNN.vlt), used when docking if it exists
    $skinPath = Get-SkinPath -Taskbar:$dock

    # Windows media controls (optional; the plugin is downloaded from GitHub)
    $smtc = $false
    $vlcExe = Find-Vlc
    if ($vlcExe) {
        $plugged = Test-Path (Join-Path (Split-Path $vlcExe) "plugins\misc\libwin10smtc_plugin.dll")
        if ($plugged -or (Show-Msg ("Add Windows media controls to VLC? Media keys, the media panel next to the volume, " +
            "Quick Settings and the lock screen then show and control VLC.`n`n" +
            "This downloads the free plugin vlc-win10smtc $SmtcVersion from GitHub and asks for admin rights " +
            "once to copy it into VLC's folder.") "YesNo") -eq "Yes") {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            try { $smtc = Install-SmtcPlugin $vlcExe }
            catch { Show-Msg "Media controls not installed: $($_.Exception.Message)" | Out-Null }
        }
    }

    $rc = Join-Path $env:APPDATA "vlc\vlcrc"
    $lines = New-Object 'System.Collections.Generic.List[string]'
    if (Test-Path $rc) {
        $backup = "$rc.before-titlebar"
        if (-not (Test-Path $backup)) { Copy-Item $rc $backup }
        foreach ($l in [IO.File]::ReadAllLines($rc)) { $lines.Add($l) }
    } else {
        New-Item -ItemType Directory -Force -Path (Split-Path $rc) | Out-Null
    }
    Set-VlcOption $lines "core"   "intf" "skins2"                              # skin instead of the normal VLC window
    Set-VlcOption $lines "skins2" "skins2-last" $skinPath
    Set-VlcOption $lines "core"   "one-instance" "1"                           # files opened from Explorer go to the
    Set-VlcOption $lines "core"   "one-instance-when-started-from-file" "1"    # running player, no second window
    Set-VlcOption $lines "core"   "playlist-enqueue" "0"                       # ... and start playing
    Set-VlcOption $lines "core"   "media-library" "0"                          # no "Media Library" entry in the playlist
    Set-VlcOption $lines "skins2" "skins2-taskbar" $(if ($dock) { "0" } else { "1" })  # docked: no extra VLC button
    if ($smtc) { Set-VlcModule $lines "core" "extraintf" "win10smtc" }            # start the media controls plugin
    Set-VlcModule $lines "core"   "extraintf" "http"                           # VLC's web interface: the helper reads the
    Set-VlcOption $lines "core"   "http-host" "127.0.0.1"                      # playing state and sends commands through it,
    Set-VlcOption $lines "core"   "http-port" "48080"                          # on this computer only, on an unusual port
    if (-not (Get-VlcSetting $lines "http-password")) {                        # locked with a random password (kept if set)
        Set-VlcOption $lines "lua" "http-password" (New-Password 24)           # (the key lives in vlcrc's [lua] section)
    }
    # Lua interface: the script goes into VLC's user Lua folder and starts next to the skin and the web interface
    # (extraintf=http:luaintf; lua-intf only names the script that "luaintf" runs, "http" is not affected).
    $luaOn = $false
    $luaSrc = Join-Path $root "lua\intf\titlebar.lua"
    if (Test-Path $luaSrc) {
        $other = Get-VlcSetting $lines "lua-intf"
        if (-not $other -or $other -eq "dummy" -or $other -eq "titlebar") {
            $luaDir = Join-Path $env:APPDATA "vlc\lua\intf"
            New-Item -ItemType Directory -Force -Path $luaDir | Out-Null
            Copy-Item (Join-Path $root "lua\intf\*.lua") $luaDir -Force
            Set-VlcModule $lines "core" "extraintf" "luaintf"
            Set-VlcOption $lines "lua" "lua-intf" "titlebar"                       # (the key lives in vlcrc's [lua] section)
            Set-VlcDefaults $lines (Join-Path $root "lua\vlcrc-keys.txt")             # default key bindings
            $luaOn = $true
        }
    }
    [IO.File]::WriteAllLines($rc, $lines, (New-Object System.Text.UTF8Encoding $false))  # vlcrc: UTF-8 without BOM

    # a helper that is already running read the old settings: stop it (a new one starts below)
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like "*vlc-taskbar.ps1*" -and $_.CommandLine -notlike "*-Setup*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }

    $startup = [Environment]::GetFolderPath("Startup")
    $lnk = Join-Path $startup "Titlebar VLC helper.lnk"
    if ($autostart) {
        $helperArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$here\vlc-taskbar.ps1`" -Watch"
        if (-not $dock) { $helperArgs += " -NoDock" }
        $sh = New-Object -ComObject WScript.Shell
        $s = $sh.CreateShortcut($lnk)
        $s.TargetPath = (Get-Command powershell.exe).Source
        $s.Arguments = $helperArgs
        $s.WorkingDirectory = $here
        $s.WindowStyle = 7   # minimized
        $s.Save()
        Start-Process -FilePath $s.TargetPath -ArgumentList $helperArgs   # start it now as well
    } elseif (Test-Path $lnk) {
        Remove-Item $lnk
    }
    $extra = ""
    if ($smtc) { $extra = "Media controls are on (media keys, the media panel, lock screen).`n`n" }
    if ($luaOn) {
        $extra += "Extra keys (while the player has focus): Ctrl+Shift+A = A-B loop, Ctrl+Shift+Left / Right = previous / next folder, " +
            "Ctrl+Shift+Up / Down = next / previous equalizer preset. The helper's tray menu has them too.`n`n"
    }
    Show-Msg ("Done. VLC now uses $(Split-Path -Leaf $skinPath). Open a music file or folder to start it.`n`n" + $extra +
        "VLC's web interface is on for this computer only (127.0.0.1, port 48080, password in vlcrc); the helper uses it.`n`n" +
        "To undo: restore $rc.before-titlebar (VLC closed) and delete the shortcut in $startup.") | Out-Null
}

if ($Setup) { Invoke-Setup; exit 0 }

$skinPath = Get-SkinPath -Taskbar:(-not $NoDock)   # same choice as Setup made, so scale and bar height match VLC's skin
$skinInfo = Get-SkinInfo $skinPath
$scale = $skinInfo.Scale

# Only one helper at a time
$mutex = New-Object System.Threading.Mutex($false, "Local\VlcTaskbarDock")
if (-not $mutex.WaitOne(0)) { exit }

if ($StartVlc -and -not $Watch -and -not (Get-Process vlc -ErrorAction SilentlyContinue)) {
    $exe = Find-Vlc
    if (-not $exe) {
        Show-Msg "VLC was not found. Install VLC or set its path in vlc-taskbar.ps1." | Out-Null
        exit 1
    }
    $vlcArgs = @('--intf', 'skins2', "--skins2-last=`"$skinPath`"")
    if ($HideVlcTaskbarButton -and -not $NoDock) { $vlcArgs += '--no-skins2-taskbar' }
    Start-Process -FilePath $exe -ArgumentList $vlcArgs
}

# UI Automation is used to find the Start button; Forms / Drawing for the tray icon
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase, System.Windows.Forms, System.Drawing
$refs = [AppDomain]::CurrentDomain.GetAssemblies() |
    Where-Object { $_.GetName().Name -in 'UIAutomationClient', 'UIAutomationTypes', 'WindowsBase', 'System.Windows.Forms', 'System.Drawing' } |
    ForEach-Object { $_.Location }

if (-not ('VlcDock' -as [type])) {
    Add-Type -TypeDefinition (Get-Content -Raw (Join-Path $here 'VlcDock.cs')) -ReferencedAssemblies $refs
}

[VlcDock]::Scale       = $scale
[VlcDock]::BarHeight   = $skinInfo.BarHeight
[VlcDock]::DockTo      = $DockTo
[VlcDock]::Gap         = $Gap
[VlcDock]::OffsetY     = $OffsetY
[VlcDock]::Dock        = -not $NoDock
[VlcDock]::StartPinned = $StartPinned
if ($DebugLog) { [VlcDock]::LogPath = Join-Path $env:TEMP "titlebar-helper.log" }
if ($VlcControl) {
    $remote = Get-VlcRemote   # $null (control channel stays off, silently) unless Setup enabled the web interface
    if ($remote) { [VlcDock]::RemotePort = $remote.Port; [VlcDock]::RemotePassword = $remote.Password }
}
[VlcDock]::TrayIcon    = $TrayIcon
[VlcDock]::ExitWithVlc = -not $Watch
[VlcDock]::Run()   # returns when VLC exits (not in -Watch mode)
