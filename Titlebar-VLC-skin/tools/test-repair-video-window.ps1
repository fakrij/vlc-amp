param($Src)
$t = Get-Content -Raw $Src
$m = [regex]::Match($t, '(?s)function Repair-VideoWindow.*?\r?\n}\r?\n')
Invoke-Expression $m.Value
function T($name, $line, $scale) {
  $l = New-Object 'System.Collections.Generic.List[string]'; $l.Add($line); $l.Add("other=1")
  Repair-VideoWindow $l $scale
  "$name -> " + $l[0]
}
T "none"      'skins2-config=["main" "strip-dn" 1 2 556 436 1]' 1.25
T "hidden"    'skins2-config=["main" "x" 1 2 5 4 1]["video" "video-l" 10 20 600 300 0]' 1
T "shrunk"    'skins2-config=["main" "x" 1 2 5 4 1]["video" "video-min" 10 20 150 22 0]' 1.5
T "ok"        'skins2-config=["video" "video-l" 10 20 600 300 1]' 1
T "empty"     'skins2-config=' 1
