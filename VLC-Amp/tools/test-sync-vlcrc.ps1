$dll = Join-Path $env:TEMP 'vlcdock-check.dll'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase, System.Windows.Forms, System.Drawing
$asm = [Reflection.Assembly]::LoadFrom($dll)
$t = $asm.GetType('VlcDock')
$dir = Join-Path $env:TEMP 'tb-sync-test\vlc'; New-Item -ItemType Directory -Force $dir | Out-Null
$env:APPDATA = Split-Path $dir
$rc = Join-Path $dir 'vlcrc'
function Run($name, $cfg, $follow) {
  Set-Content -Path $rc -Value @('[core]', $cfg, 'x=1') -Encoding ASCII
  $t.GetField('nextThemeSync', [Reflection.BindingFlags]'NonPublic,Static').SetValue($null, [DateTime]::MinValue)
  $t.GetField('FollowTheme').SetValue($null, $follow)
  $t.GetMethod('SyncVlcrcTheme').Invoke($null, @())
  "$name -> " + (Get-Content $rc)[1]
}
$light = $t.GetMethod('AppsUseLightTheme', [Reflection.BindingFlags]'NonPublic,Static').Invoke($null, @())
"system light = $light"
Run 'no video entry' 'skins2-config=["main" "full-up" 1 2 5 4 1]["th0" "th0-l" 1 1 1 1 1]["th1" "th1-l" 1 1 1 1 0]' $false
Run 'shrunk' 'skins2-config=["video" "video-min" 10 20 150 22 1]["th0" "th0-l" 1 1 1 1 1]["th1" "th1-l" 1 1 1 1 0]' $false
Run 'follow theme' 'skins2-config=["video" "video-l" 10 20 600 300 1]["th0" "th0-l" 1 1 1 1 1]["th1" "th1-l" 1 1 1 1 0]' $true
