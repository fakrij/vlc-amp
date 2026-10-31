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
$Skin              = "auto"             # "auto" = pick Titlebar-NNN.vlt from the Windows display scale, or a file name
$DockTo            = "start"            # start = left of the Start button | left = left end of taskbar | right = next to the tray icons
$Gap               = 8                  # pixels between the strip and the Start button / edge
$OffsetY           = 0                  # nudge the strip up (-) or down (+) inside the taskbar
$HideVlcTaskbarButton = $true           # the player is in the taskbar already, so hide VLC's own taskbar button
$StartVlc          = $true              # start VLC if it is not running (not in -Watch mode)
$StartPinned       = $true              # pin VLC "always on top" each time it starts
$DebugLog          = $DebugLog.IsPresent -or $false   # $true = log what the helper does to %TEMP%\titlebar-helper.log
$TrayIcon          = $true              # notification-area icon with a menu (dock on / off, pin now, quit)
# -----------------------------------------

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Add-Type -AssemblyName System.Windows.Forms

function Show-Msg($text, $buttons = "OK") {
    return [System.Windows.Forms.MessageBox]::Show($text, "Titlebar VLC skin", $buttons)
}

# Skin file for the current display scale (AppliedDPI: 96 = 100 %, 120 = 125 %, 144 = 150 %, 192 = 200 %)
function Get-SkinPath {
    $name = $Skin
    if ($name -eq "auto") {
        $dpi = 96
        try { $dpi = [int](Get-ItemProperty 'HKCU:\Control Panel\Desktop\WindowMetrics' -Name AppliedDPI).AppliedDPI } catch { }
        $pct = $dpi * 100 / 96
        $best = 100
        foreach ($s in 100, 125, 150, 200) { if ([math]::Abs($s - $pct) -lt [math]::Abs($best - $pct)) { $best = $s } }
        $name = "Titlebar-$best.vlt"
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

function Invoke-Setup {
    if (Get-Process vlc -ErrorAction SilentlyContinue) {
        Show-Msg "Please close VLC first, then run Setup again.`n(VLC rewrites its settings file when it exits.)" | Out-Null
        exit 1
    }
    $skinPath = Get-SkinPath
    if (-not $skinPath) { Show-Msg "Skin file not found next to the taskbar folder." | Out-Null; exit 1 }

    $autostart = (Show-Msg ("Start the helper with Windows? It pins VLC on top each time VLC starts " +
        "(also when you open a file from Explorer).") "YesNo") -eq "Yes"
    $dock = $false
    if ($autostart) {
        $dock = (Show-Msg ("Also dock the player in the taskbar, left of the Start button?`n`n" +
            "No = the player stays where you put it (for example in a window title bar).") "YesNo") -eq "Yes"
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
    [IO.File]::WriteAllLines($rc, $lines, (New-Object System.Text.UTF8Encoding $false))  # vlcrc: UTF-8 without BOM

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
    Show-Msg ("Done. VLC now uses $(Split-Path -Leaf $skinPath). Open a music file or folder to start it.`n`n" +
        "To undo: restore $rc.before-titlebar (VLC closed) and delete the shortcut in $startup.") | Out-Null
}

if ($Setup) { Invoke-Setup; exit 0 }

$skinPath = Get-SkinPath
$scale = 1.0
if ($skinPath -and (Split-Path -Leaf $skinPath) -match '-(\d+)\.vlt$') { $scale = [int]$Matches[1] / 100.0 }

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
[VlcDock]::DockTo      = $DockTo
[VlcDock]::Gap         = $Gap
[VlcDock]::OffsetY     = $OffsetY
[VlcDock]::Dock        = -not $NoDock
[VlcDock]::StartPinned = $StartPinned
if ($DebugLog) { [VlcDock]::LogPath = Join-Path $env:TEMP "titlebar-helper.log" }
[VlcDock]::TrayIcon    = $TrayIcon
[VlcDock]::ExitWithVlc = -not $Watch
[VlcDock]::Run()   # returns when VLC exits (not in -Watch mode)
