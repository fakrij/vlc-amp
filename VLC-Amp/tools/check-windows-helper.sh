#!/bin/bash
# check-windows-helper.sh - compile taskbar/VlcDock.cs and browser/VlcAmpRelay.cs and parse the PowerShell
# scripts (taskbar/, browser/vlc-amp-url.ps1) with the Windows tools, from WSL (no Mono needed). Same compiler family the helper uses at run time
# (.NET Framework 4, C# 5). Prints compiler errors; exit 1 on any problem.
set -uo pipefail
cd "$(dirname "$0")/../taskbar"
command -v powershell.exe >/dev/null || { echo "needs WSL with powershell.exe"; exit 2; }
rc=0
W=$(wslpath -w "$PWD/VlcDock.cs")
out=$(powershell.exe -NoProfile -Command "
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase
\$refs = foreach (\$n in 'UIAutomationClient','UIAutomationTypes','WindowsBase') { '/r:' + ([AppDomain]::CurrentDomain.GetAssemblies() | ? { \$_.GetName().Name -eq \$n } | select -First 1).Location }
\$dll = Join-Path \$env:TEMP 'vlcdock-check.dll'; Remove-Item \$dll -ErrorAction SilentlyContinue
& 'C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe' /nologo /target:library /out:\$dll @refs '$W' 2>&1
if (-not (Test-Path \$dll)) { 'COMPILE FAILED' }" | tr -d '\r')
if [ -n "$out" ]; then echo "$out"; rc=1; else echo "VlcDock.cs: compiles"; fi
W=$(wslpath -w "$PWD/../browser/VlcAmpRelay.cs")
out=$(powershell.exe -NoProfile -Command "
\$dll = Join-Path \$env:TEMP 'vlcamprelay-check.dll'; Remove-Item \$dll -ErrorAction SilentlyContinue
& 'C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe' /nologo /target:library /out:\$dll '$W' 2>&1
if (-not (Test-Path \$dll)) { 'COMPILE FAILED' }" | tr -d '\r')
if [ -n "$out" ]; then echo "$out"; rc=1; else echo "VlcAmpRelay.cs: compiles"; fi
for f in vlc-taskbar.ps1 install.ps1 uninstall.ps1 ../browser/vlc-amp-url.ps1; do
    W=$(wslpath -w "$PWD/$f")
    n=$(powershell.exe -NoProfile -Command "\$e=\$null;\$t=\$null;[void][System.Management.Automation.Language.Parser]::ParseFile('$W',[ref]\$t,[ref]\$e); \$e.Count" | tr -d '\r')
    echo "$f: $n parse errors"; [ "$n" = 0 ] || rc=1
done
exit $rc
