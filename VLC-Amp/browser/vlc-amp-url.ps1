# vlc-amp-url.ps1 - play a web page's video or audio in VLC (Windows side of "open links from the browser").
#
#   vlc-amp-url.vbs "vlc-amp:play?mode=video&url=..."   the vlc-amp: handler (Setup registers it): runs this script
#                                                       hidden, with the link in $env:VLCAMP_URI
#   vlc-amp-url.ps1 -Resolve <url> [-Audio]              print what would be sent to VLC (no VLC)
#   vlc-amp-url.ps1 -Relay                               the local relay (started on demand)
#
# Same flow as vlc-amp-url.py (Linux): yt-dlp resolves the page (up to 1080p H.264 + m4a audio, or audio only);
# chunk-only streams (YouTube) go through the relay on 127.0.0.1:48081 (VlcAmpRelay.cs); the item goes to a
# running VLC through its web interface (Setup: 127.0.0.1:48080, password in vlcrc), else VLC is started with
# the item options on its command line (through taskbar\launch.vbs, which also starts the helper).
# Log: %TEMP%\vlc-amp-url.log. Written for Windows PowerShell 5.1.
param([switch]$Relay, [string]$Resolve, [switch]$Audio)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$RelayPort = 48081
$Log = Join-Path $env:TEMP "vlc-amp-url.log"
$StateDir = Join-Path $env:LOCALAPPDATA "VLC-Amp-state"   # outside %LOCALAPPDATA%\VLC-Amp: Install mirrors that folder
$Formats = @{
    video  = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b"
    audio  = "ba[ext=m4a]/ba/b"
}
$Fields = "%(.{title,format_id,url,protocol,http_headers,downloader_options,requested_formats})j"

function Write-Log($text) {
    try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $text) -Encoding UTF8 } catch { }
}

function Fail($text) {
    Write-Log ("error: " + $text)
    if ($Resolve) { Write-Error $text; exit 1 }
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show($text, "VLC Amp", "OK", "Warning")
    exit 1
}

# ---- the link ----
function Read-Link($link) {
    $mode = "video"
    $url = $link
    if ($link -like "vlc-amp:*") {
        $rest = $link.Substring(8)
        if ($rest.StartsWith("//") -and -not $rest.StartsWith("//play")) {
            $url = [Uri]::UnescapeDataString($rest.Substring(2))            # vlc-amp://https://... (typed by hand)
        } else {
            $url = ""
            foreach ($part in ($rest -replace '^[^?]*\?', '') -split '&') {
                $kv = $part -split '=', 2
                if ($kv.Count -ne 2) { continue }
                $v = [Uri]::UnescapeDataString($kv[1].Replace('+', ' '))
                if ($kv[0] -eq "url") { $url = $v } elseif ($kv[0] -eq "mode") { $mode = $v }
            }
        }
    }
    if ($mode -ne "audio") { $mode = "video" }
    # no spaces or quotes: the URL is passed to yt-dlp on its command line
    if ($url -notmatch '^(?i)https?://[^\s/"]+[^\s"]*$') { Fail ("Not a web link: " + $url) }
    return @{ Url = $url; Mode = $mode }
}

# ---- yt-dlp ----
. (Join-Path $here 'find-ytdlp.ps1')   # Find-YtDlp (shared with taskbar\vlc-taskbar.ps1)

# Runs a console program without a window; returns @{ Code; Out; Err }.
function Invoke-Hidden($exe, $arguments, $timeoutSec) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.Arguments = $arguments
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $p = [Diagnostics.Process]::Start($psi)
    $out = $p.StandardOutput.ReadToEndAsync()
    $err = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($timeoutSec * 1000)) { try { $p.Kill() } catch { }; return $null }
    return @{ Code = $p.ExitCode; Out = $out.Result; Err = $err.Result }
}

# @{ Title; Main; Audio }; a stream is @{ Url; UA; Referer; Chunked }
function Resolve-Page($url, $mode) {
    $exe = Find-YtDlp
    if (-not $exe) { Fail "yt-dlp is not installed (needed to play web pages).`n`nRun Start menu > VLC Amp > VLC Amp setup again and answer Yes to yt-dlp, or: winget install yt-dlp.yt-dlp" }
    $a = "--no-update --no-playlist --playlist-items 1 --no-warnings --encoding utf-8 -f `"$($Formats[$mode])`" -O `"$Fields`""
    foreach ($rt in "deno", "node") { if (Get-Command "$rt.exe" -ErrorAction SilentlyContinue) { $a += " --js-runtimes $rt" } }
    $a += " -- `"$url`""
    $t = Get-Date
    $r = Invoke-Hidden $exe $a 90
    if (-not $r) { Fail "yt-dlp took too long for $url" }
    if ($r.Code -ne 0) {
        $last = @($r.Err.Trim() -split "`r?`n")[-1]
        Fail ("yt-dlp could not read the page:`n$last`n`n(An old yt-dlp is the usual cause: winget upgrade yt-dlp.yt-dlp)")
    }
    $line = @($r.Out.Trim() -split "`r?`n")[0]
    if (-not $line) { Fail "yt-dlp found nothing to play on $url" }
    $info = $line | ConvertFrom-Json
    Write-Log ("resolved $url ($mode) in {0:N1} s: $($info.format_id)" -f ((Get-Date) - $t).TotalSeconds)
    $streams = @()
    $fmts = if ($info.requested_formats) { @($info.requested_formats) } else { @($info) }
    foreach ($f in $fmts) {
        $h = $f.http_headers
        $chunked = [bool]($f.downloader_options -and $f.downloader_options.http_chunk_size) -or
            (([Uri]$f.url).Host -like "*.googlevideo.com")
        $streams += @{ Url = $f.url; UA = $(if ($h) { $h.'User-Agent' } else { "" }); Referer = $(if ($h) { $h.Referer } else { "" }); Chunked = $chunked }
    }
    $title = if ($info.title) { $info.title } else { $url }
    return @{ Title = $title; Main = $streams[0]; Audio = $(if ($streams.Count -gt 1) { $streams[1] } else { $null }) }
}

# ---- relay ----
function Get-RelaySecret {
    $file = Join-Path $StateDir "relay-secret"
    if (Test-Path $file) {
        $s = (Get-Content -LiteralPath $file -Raw).Trim()
        if ($s -match '^[A-Za-z0-9_-]{20,}$') { return $s }
    }
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $bytes = New-Object byte[] 24
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($bytes); $rng.Dispose()
    $s = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    [IO.File]::WriteAllText($file, $s)
    return $s
}

function Test-Relay($secret) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 "http://127.0.0.1:$RelayPort/$secret/ping"
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Start-Relay($secret) {
    if (Test-Relay $secret) { return }
    $ps = (Get-Command powershell.exe).Source
    Start-Process -FilePath $ps -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", "`"$PSCommandPath`"", "-Relay") | Out-Null
    for ($i = 0; $i -lt 80; $i++) {           # Add-Type compiles the relay first (1-3 s)
        Start-Sleep -Milliseconds 100
        if (Test-Relay $secret) { return }
    }
    Fail "The local relay did not start (port $RelayPort in use?). See $Log"
}

function Get-RelayUrl($s, $secret) {
    $q = "u=" + [Uri]::EscapeDataString($s.Url)
    if ($s.UA) { $q += "&ua=" + [Uri]::EscapeDataString($s.UA) }
    if ($s.Referer) { $q += "&ref=" + [Uri]::EscapeDataString($s.Referer) }
    return "http://127.0.0.1:$RelayPort/$secret/s?$q"
}

# ---- VLC ----
function Get-VlcSetting($lines, $key) {
    $v = $null
    foreach ($l in $lines) { if ($l -match ('^' + [regex]::Escape($key) + '=(.*)$')) { $v = $Matches[1].Trim() } }
    return $v
}

function Get-WebInterface {
    $rc = Join-Path $env:APPDATA "vlc\vlcrc"
    if (-not (Test-Path $rc)) { return $null }
    try { $lines = [IO.File]::ReadAllLines($rc) } catch { return $null }
    $mods = @((Get-VlcSetting $lines "extraintf") -split ':' | ForEach-Object { $_.Trim() })
    $password = Get-VlcSetting $lines "http-password"
    if (-not ($mods -contains 'http') -or -not $password) { return $null }
    $port = 8080
    $p = Get-VlcSetting $lines "http-port"
    if ($p -match '^\d+$') { $port = [int]$p }
    return @{ Port = $port; Password = $password }
}

function Send-ToVlc($web, $item, $opts) {
    $q = "command=in_play&input=" + [Uri]::EscapeDataString($item)
    foreach ($o in $opts) { $q += "&option=" + [Uri]::EscapeDataString($o) }
    $auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(":" + $web.Password))
    try {
        $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Headers @{ Authorization = "Basic $auth" } `
            "http://127.0.0.1:$($web.Port)/requests/status.json?$q"
        return $r.StatusCode -eq 200
    } catch { Write-Log ("web interface: " + $_.Exception.Message); return $false }
}

# One command-line token for vlc.exe (no quotes inside: titles have theirs replaced; a trailing \ would escape the closing quote).
function Quote($s) { return '"' + (($s -replace '"', "'") -replace '\\+$', '') + '"' }

function Invoke-Play($url, $mode) {
    $page = Resolve-Page $url $mode
    $secret = $null
    if ($page.Main.Chunked -or ($page.Audio -and $page.Audio.Chunked)) { $secret = Get-RelaySecret; Start-Relay $secret }
    $mrl = { param($s) if ($s.Chunked) { Get-RelayUrl $s $secret } else { $s.Url } }
    $opts = @("meta-title=" + ($page.Title -replace "[\r\n]", " "))
    if ($page.Audio) { $opts += "input-slave=" + (& $mrl $page.Audio) }
    if (-not $page.Main.Chunked) {
        if ($page.Main.UA) { $opts += "http-user-agent=" + $page.Main.UA }
        if ($page.Main.Referer) { $opts += "http-referrer=" + $page.Main.Referer }
    }
    $item = & $mrl $page.Main

    $web = Get-WebInterface
    if ($web -and (Get-Process vlc -ErrorAction SilentlyContinue)) {
        if (Send-ToVlc $web $item $opts) { Write-Log ("sent to the running VLC: " + $page.Title); return }
    }
    . (Join-Path $root "taskbar\find-vlc.ps1")
    $vlc = Find-Vlc
    if (-not $vlc) { Fail "VLC was not found." }
    # one-instance (Setup) hands the item and its options to a running VLC
    $vlcArgs = @("--no-media-library", (Quote $item)) + @($opts | ForEach-Object { Quote (":" + $_) })
    $launch = Join-Path $root "taskbar\launch.vbs"
    Write-Log ("starting VLC: " + $page.Title)
    if (Test-Path $launch) {
        Start-Process -FilePath (Join-Path $env:SystemRoot "System32\wscript.exe") -ArgumentList (@((Quote $launch), (Quote $vlc)) + $vlcArgs) | Out-Null
    } else {
        Start-Process -FilePath $vlc -ArgumentList $vlcArgs | Out-Null
    }
}

if ($Relay) {
    Add-Type -Path (Join-Path $here "VlcAmpRelay.cs")
    [void][VlcAmpRelay]::Run($RelayPort, (Get-RelaySecret), 6, $Log)
    exit 0
}
if ($Resolve) {
    Resolve-Page $Resolve $(if ($Audio) { "audio" } else { "video" }) | ConvertTo-Json -Depth 4
    exit 0
}
$link = if ($env:VLCAMP_URI) { $env:VLCAMP_URI } elseif ($args.Count -gt 0) { $args[0] } else { "" }
if (-not $link) { Fail "No link given." }
$l = Read-Link $link
Write-Log ("link: $($l.Url) ($($l.Mode))")
try { Invoke-Play $l.Url $l.Mode } catch { Fail ("Could not play the link: " + $_.Exception.Message) }
