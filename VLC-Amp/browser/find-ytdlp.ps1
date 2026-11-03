# find-ytdlp.ps1 - Find-YtDlp, shared by vlc-amp-url.ps1 and taskbar\vlc-taskbar.ps1 (dot-sourced).

# Path of yt-dlp.exe: of all the copies (PATH, and where winget puts it: the PATH of a process started by the
# browser can be older than the winget install), the one installed or updated last - an old pip copy first on
# the PATH must not hide a current winget one (YouTube cuts old versions off). $null when there is none.
function Find-YtDlp {
    $paths = @(Get-Command yt-dlp.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }) +
        @("$env:LOCALAPPDATA\Microsoft\WinGet\Links\yt-dlp.exe") +
        @(Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\yt-dlp.yt-dlp*\yt-dlp.exe" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    $found = @($paths | Where-Object { $_ -and (Test-Path $_) } | Get-Item | Sort-Object LastWriteTime -Descending)
    if ($found.Count -eq 0) { return $null }
    return $found[0].FullName
}
