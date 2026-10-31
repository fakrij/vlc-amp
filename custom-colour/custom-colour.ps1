# custom-colour.ps1 - pick the accent colour of the Titlebar skin's Custom theme (Windows).
#
#   Custom colour.cmd      double-click: colour dialog, then recolours every Titlebar-*.vlt in the folder above
#
# Switches (optional, when run by hand):
#   -Colour "#33ff99"      do not ask, use this colour
#   -Reset                 back to the default accent (CUSTOM_DEFAULT in source\build_skin.py)
#   -Files a.vlt b.vlt     change these files instead of the Titlebar-*.vlt next to this folder
#
# How it works: every .vlt keeps the Custom theme's images in a red reference colour in custom-ref\
# (pixel = grey + t * red). This script unpacks the .vlt with tar.exe (Windows 10 1803 and later),
# turns the red images into grey + t * accent, writes them to img\ together with the recoloured
# theme.xml, and packs the same files again. Needs Windows PowerShell 5.1; no admin rights.
param([string]$Colour = "", [switch]$Reset,
      [Parameter(ValueFromRemainingArguments = $true)][string[]]$Files)

$ErrorActionPreference = "Stop"
$Default = "#b48cff"        # same as CUSTOM_DEFAULT in source\build_skin.py
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Show-Msg($text, $icon = "Information") {
    [void][System.Windows.Forms.MessageBox]::Show($text, "Titlebar VLC skin - custom colour", "OK", $icon)
}

# The pixel loop, as C# 5 (Windows PowerShell 5.1 compiles it with Add-Type).
if (-not ("CustomColour" -as [type])) {
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

public static class CustomColour
{
    // round(t * c / 255) for t = 0..255 (never a tie, so integer arithmetic is exact)
    static int[] Table(int c)
    {
        int[] tab = new int[256];
        for (int v = 0; v < 256; v++) tab[v] = (v * c * 2 + 255) / 510;
        return tab;
    }

    // A pixel grey n + t * red becomes n + t * (ar, ag, ab); alpha stays. Format32bppArgb is
    // straight (not premultiplied) alpha, which is what the skin's PNGs use.
    public static void RecolourPng(string src, string dst, int ar, int ag, int ab)
    {
        int[] tr = Table(ar), tg = Table(ag), tb = Table(ab);
        using (Bitmap bmp = new Bitmap(src))
        {
            int w = bmp.Width, h = bmp.Height;
            BitmapData bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
            try
            {
                byte[] buf = new byte[w * 4];
                for (int y = 0; y < h; y++)
                {
                    IntPtr row = new IntPtr(bd.Scan0.ToInt64() + (long)y * bd.Stride);
                    Marshal.Copy(row, buf, 0, buf.Length);
                    for (int i = 0; i < buf.Length; i += 4)      // memory order: B G R A
                    {
                        int g = buf[i + 1];
                        int t = buf[i + 2] - g;
                        if (t < 0) t = 0;
                        int r2 = g + tr[t], g2 = g + tg[t], b2 = g + tb[t];
                        buf[i + 2] = (byte)(r2 > 255 ? 255 : r2);
                        buf[i + 1] = (byte)(g2 > 255 ? 255 : g2);
                        buf[i] = (byte)(b2 > 255 ? 255 : b2);
                    }
                    Marshal.Copy(buf, 0, row, buf.Length);
                }
            }
            finally
            {
                bmp.UnlockBits(bd);
            }
            bmp.Save(dst, ImageFormat.Png);
        }
    }

    // The same for the #RRGGBB colours of the lines that belong to the Custom theme.
    public static string RecolourXml(string xml, int slot, int ar, int ag, int ab)
    {
        int[] tr = Table(ar), tg = Table(ag), tb = Table(ab);
        string mark = "visible=\"th" + slot + ".isVisible";
        Regex rx = new Regex("#[0-9A-Fa-f]{6}");
        MatchEvaluator ev = delegate(Match m)
        {
            int r = Convert.ToInt32(m.Value.Substring(1, 2), 16);
            int g = Convert.ToInt32(m.Value.Substring(3, 2), 16);
            int t = r - g;
            if (t < 0) t = 0;
            return String.Format("#{0:X2}{1:X2}{2:X2}", Math.Min(255, g + tr[t]), Math.Min(255, g + tg[t]), Math.Min(255, g + tb[t]));
        };
        string[] lines = xml.Split('\n');
        for (int i = 0; i < lines.Length; i++)
            if (lines[i].IndexOf(mark, StringComparison.Ordinal) >= 0) lines[i] = rx.Replace(lines[i], ev);
        return String.Join("\n", lines);
    }
}
'@
}

function Parse-Colour($s) {
    if ($s -match '^\s*#?([0-9a-fA-F]{6})\s*$') {
        $h = $Matches[1]
        return @([Convert]::ToInt32($h.Substring(0, 2), 16), [Convert]::ToInt32($h.Substring(2, 2), 16), [Convert]::ToInt32($h.Substring(4, 2), 16))
    }
    throw "Not a colour like #b48cff: $s"
}

function Get-TarExe {
    $p = Join-Path $env:SystemRoot "System32\tar.exe"
    if (Test-Path -LiteralPath $p) { return $p }
    $c = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    throw "tar.exe not found. It is part of Windows 10 (version 1803) and later."
}

# Accent stored in a .vlt (custom-ref\slot.txt), or $null
function Get-CurrentAccent($vlt, $tar) {
    $tmp = Join-Path $env:TEMP ("titlebar-colour-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        & $tar -xzf $vlt -C $tmp "custom-ref/slot.txt" 2>$null
        $f = Join-Path $tmp "custom-ref\slot.txt"
        if (Test-Path -LiteralPath $f) {
            $m = [regex]::Match([IO.File]::ReadAllText($f), '(?m)^accent=(#[0-9a-fA-F]{6})')
            if ($m.Success) { return $m.Groups[1].Value }
        }
    } catch { } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
    return $null
}

function Update-Vlt($vlt, $rgb, $tar) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $work = Join-Path $env:TEMP ("titlebar-colour-" + [guid]::NewGuid().ToString("N"))
    $out = $vlt + ".tmp"
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        & $tar -xzf $vlt -C $work
        if ($LASTEXITCODE -ne 0) { throw "tar could not unpack $vlt" }
        $ref = Join-Path $work "custom-ref"
        $slotFile = Join-Path $ref "slot.txt"
        if (-not (Test-Path -LiteralPath $slotFile)) {
            throw "no custom-ref folder in it (built before the Custom theme existed); use a newer build"
        }
        $slotText = [IO.File]::ReadAllText($slotFile)
        $m = [regex]::Match($slotText, '(?m)^slot=(\d+)')
        if (-not $m.Success) { throw "custom-ref\slot.txt is damaged" }
        $slot = [int]$m.Groups[1].Value

        $n = 0
        foreach ($png in Get-ChildItem -LiteralPath (Join-Path $ref "img") -Filter *.png) {
            [CustomColour]::RecolourPng($png.FullName, (Join-Path $work ("img\" + $png.Name)), $rgb[0], $rgb[1], $rgb[2])
            $n++
        }
        if ($n -eq 0) { throw "custom-ref\img has no images" }
        $xml = [IO.File]::ReadAllText((Join-Path $ref "theme.xml"), $utf8)
        [IO.File]::WriteAllText((Join-Path $work "theme.xml"), [CustomColour]::RecolourXml($xml, $slot, $rgb[0], $rgb[1], $rgb[2]), $utf8)
        $hex = "#{0:x2}{1:x2}{2:x2}" -f $rgb[0], $rgb[1], $rgb[2]
        [IO.File]::WriteAllText($slotFile, ($slotText -replace '(?m)^accent=.*$', "accent=$hex"), $utf8)

        # Same members as the generator writes: theme.xml, img/, fonts/, custom-ref/ (files only, no folder entries).
        $names = New-Object System.Collections.ArrayList
        [void]$names.Add("theme.xml")
        $prefix = (Resolve-Path -LiteralPath $work).Path.TrimEnd('\') + '\'
        foreach ($f in Get-ChildItem -LiteralPath $work -Recurse -File | Sort-Object FullName) {
            $rel = $f.FullName.Substring($prefix.Length).Replace('\', '/')
            if ($rel -ne "theme.xml") { [void]$names.Add($rel) }
        }
        $list = Join-Path $env:TEMP ("titlebar-colour-" + [guid]::NewGuid().ToString("N") + ".txt")
        [IO.File]::WriteAllLines($list, [string[]]$names.ToArray())
        try {
            if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Force }
            & $tar --format ustar -czf $out -C $work -T $list
            if ($LASTEXITCODE -ne 0) { throw "tar could not pack $vlt" }
        } finally { Remove-Item -LiteralPath $list -Force -ErrorAction SilentlyContinue }
        try {
            [IO.File]::Replace($out, $vlt, $null)           # replaces the old file in one step
        } catch {
            throw "could not replace $vlt (is VLC running with this skin? close it and try again): $($_.Exception.Message)"
        }
        return $n
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue }
    }
}

try {
    $tar = Get-TarExe
    if ($Files -and $Files.Count -gt 0) {
        $vlts = @($Files | ForEach-Object { (Resolve-Path -LiteralPath $_).Path })
    } else {
        $vlts = @(Get-ChildItem -LiteralPath $root -Filter "Titlebar-*.vlt" | Sort-Object Name | ForEach-Object { $_.FullName })
    }
    if ($vlts.Count -eq 0) { throw "No Titlebar-*.vlt found in $root" }

    if ($Reset) {
        $rgb = Parse-Colour $Default
    } elseif ($Colour -ne "") {
        $rgb = Parse-Colour $Colour
    } else {
        $start = Get-CurrentAccent $vlts[0] $tar
        if (-not $start) { $start = $Default }
        $s = Parse-Colour $start
        $owner = New-Object System.Windows.Forms.Form
        $owner.TopMost = $true
        $owner.ShowInTaskbar = $false
        $owner.StartPosition = "CenterScreen"
        $dlg = New-Object System.Windows.Forms.ColorDialog
        $dlg.AnyColor = $true
        $dlg.FullOpen = $true
        $dlg.Color = [System.Drawing.Color]::FromArgb($s[0], $s[1], $s[2])
        $res = $dlg.ShowDialog($owner)
        $picked = $dlg.Color
        $owner.Dispose()
        if ($res -ne [System.Windows.Forms.DialogResult]::OK) { Write-Host "Cancelled, nothing changed."; exit 0 }
        $rgb = @([int]$picked.R, [int]$picked.G, [int]$picked.B)
    }
    Write-Host ("Accent #{0:x2}{1:x2}{2:x2}" -f $rgb[0], $rgb[1], $rgb[2])

    $errors = @()
    foreach ($v in $vlts) {
        $name = Split-Path -Leaf $v
        Write-Host -NoNewline "$name ... "
        $sw = [Diagnostics.Stopwatch]::StartNew()
        try {
            $n = Update-Vlt $v $rgb $tar
            Write-Host ("{0} images, {1:0.0} s" -f $n, $sw.Elapsed.TotalSeconds)
        } catch {
            Write-Host "failed"
            $errors += "${name}: $($_.Exception.Message)"
        }
    }
    if ($errors.Count -gt 0) {
        Show-Msg ("Some files were not changed:`r`n`r`n" + ($errors -join "`r`n")) "Warning"
        exit 1
    }
    Show-Msg "Done. Restart VLC, then choose the Custom theme with the theme button in the full player's title bar." "Information"
} catch {
    Show-Msg ("Custom colour failed:`r`n`r`n" + $_.Exception.Message) "Error"
    exit 1
}
