' vlc-amp-url.vbs - the vlc-amp: link handler (Setup registers it under HKCU\Software\Classes\vlc-amp).
'
'   wscript.exe vlc-amp-url.vbs "vlc-amp:play?mode=video&url=..."
'
' Runs vlc-amp-url.ps1 without a console window. The link goes in an environment variable, never on a
' command line, so a crafted link cannot add arguments.
Option Explicit
Dim sh, fso, link, i, ps1
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
If WScript.Arguments.Count = 0 Then WScript.Quit 1
link = WScript.Arguments(0)
For i = 1 To WScript.Arguments.Count - 1
    link = link & " " & WScript.Arguments(i)
Next
sh.Environment("Process")("VLCAMP_URI") = link
ps1 = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "vlc-amp-url.ps1")
sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """", 0, False
