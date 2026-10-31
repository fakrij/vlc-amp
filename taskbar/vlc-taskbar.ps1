# vlc-taskbar.ps1 - start VLC with the Titlebar skin docked in the Windows taskbar.
# Run via "VLC in taskbar.cmd" (double-click), or:
#   powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File vlc-taskbar.ps1

# ---------------- settings ----------------
$Skin              = "Titlebar-100.vlt" # skin file in the folder above; the number (100/125/150/200) is read as the scale
$DockTo            = "start"            # start = left of the Start button | left = left end of taskbar | right = next to the tray icons
$Gap               = 8                  # pixels between the strip and the Start button / edge
$OffsetY           = 0                  # nudge the strip up (-) or down (+) inside the taskbar
$HideVlcTaskbarButton = $true           # the player is in the taskbar already, so hide VLC's own taskbar button
$StartVlc          = $true              # start VLC if it is not running
# -----------------------------------------

$ErrorActionPreference = "Stop"
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$skinPath = Join-Path (Split-Path -Parent $here) $Skin
if (-not (Test-Path $skinPath)) { $skinPath = Join-Path $here $Skin }

$scale = 1.0
if ($Skin -match '-(\d+)\.vlt$') { $scale = [int]$Matches[1] / 100.0 }

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

# Only one helper at a time
$mutex = New-Object System.Threading.Mutex($false, "Local\VlcTaskbarDock")
if (-not $mutex.WaitOne(0)) { exit }

if ($StartVlc -and -not (Get-Process vlc -ErrorAction SilentlyContinue)) {
    $exe = Find-Vlc
    if (-not $exe) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show("VLC was not found. Install VLC or set its path in vlc-taskbar.ps1.", "VLC in taskbar") | Out-Null
        exit 1
    }
    $vlcArgs = @('--intf', 'skins2', "--skins2-last=`"$skinPath`"")
    if ($HideVlcTaskbarButton) { $vlcArgs += '--no-skins2-taskbar' }
    Start-Process -FilePath $exe -ArgumentList $vlcArgs
}

# UI Automation is used to find the Start button
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase
$refs = [AppDomain]::CurrentDomain.GetAssemblies() |
    Where-Object { $_.GetName().Name -in 'UIAutomationClient', 'UIAutomationTypes', 'WindowsBase' } |
    ForEach-Object { $_.Location }

if (-not ('VlcDock' -as [type])) {
    Add-Type -TypeDefinition (Get-Content -Raw (Join-Path $here 'VlcDock.cs')) -ReferencedAssemblies $refs
}

[VlcDock]::Scale   = $scale
[VlcDock]::DockTo  = $DockTo
[VlcDock]::Gap     = $Gap
[VlcDock]::OffsetY = $OffsetY
[VlcDock]::Run()   # returns when VLC exits
