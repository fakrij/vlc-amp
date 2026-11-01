# find-vlc.ps1 - Find-Vlc, shared by install.ps1 and vlc-taskbar.ps1 (dot-sourced).

# Path of vlc.exe from VLC's installer registry key, else the usual install folders; $null when not found.
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
