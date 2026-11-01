' launch.vbs - start VLC, then the VLC Amp helper if it is not running (Windows Script Host: no console window).
'
'   wscript.exe launch.vbs "<path>\vlc.exe" [VLC arguments...]
'
' Setup points the per-user file associations and the "VLC Amp" Start menu entry here, so the helper comes
' with VLC also after it was quit or crashed (otherwise it only starts at login). The helper is started exactly
' as the Startup shortcut "VLC Amp helper.lnk" starts it; without that shortcut (Setup: no helper) it is not.
Option Explicit
Dim sh, fso, args, i, lnkPath, lnk, procs, p, running
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 0 Then WScript.Quit 1

' 1. VLC first, so a double-click is not slowed down by the helper check
args = ""
For i = 1 To WScript.Arguments.Count - 1
    args = args & " " & Quote(WScript.Arguments(i))
Next
sh.Run Quote(WScript.Arguments(0)) & args, 1, False

' 2. the helper, if it should run and does not
lnkPath = sh.SpecialFolders("Startup") & "\VLC Amp helper.lnk"
If Not fso.FileExists(lnkPath) Then WScript.Quit 0
running = False
Set procs = GetObject("winmgmts:\\.\root\cimv2").ExecQuery( _
    "SELECT CommandLine FROM Win32_Process WHERE Name = 'powershell.exe' OR Name = 'pwsh.exe'")
For Each p In procs
    If Not IsNull(p.CommandLine) Then
        If InStr(1, p.CommandLine, "vlc-taskbar.ps1", vbTextCompare) > 0 And _
           InStr(1, p.CommandLine, "-Setup", vbTextCompare) = 0 Then running = True
    End If
Next
If running Then WScript.Quit 0
Set lnk = sh.CreateShortcut(lnkPath)
sh.Run Quote(lnk.TargetPath) & " " & lnk.Arguments, 0, False

' An argument as one command-line token (Explorer passes paths with spaces)
Function Quote(s)
    If s = "" Or InStr(s, " ") > 0 Or InStr(s, vbTab) > 0 Then
        Quote = """" & s & """"
    Else
        Quote = s
    End If
End Function
