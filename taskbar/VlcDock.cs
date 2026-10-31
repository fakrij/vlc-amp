// VlcDock - keeps the "Titlebar" VLC skin docked in the Windows taskbar.
// Loaded by vlc-taskbar.ps1 (Windows PowerShell 5.1, C# 5 syntax).
//
// VLC's skin engine does not notice when another program moves its windows,
// so this helper re-places them whenever they move (WinEvent hook) and on a
// 250 ms timer. The skin has one main window (class "SkinWindowClass", owned by
// vlc.exe). All its layouts have the same size; the parts without pixels are cut
// out with a window region, so the helper reads that region to see what is showing:
//   bar at the bottom of the window = panels open above it ("up" layouts), else below
//   strip  -> the strip sits inside the taskbar, left of Start (panels stick out)
//   full   -> the visible part just above the taskbar
// The skin also has 1x1 "flag" windows (no pixels); they and the video window
// (WS_EX_APPWINDOW) are never touched.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Automation;

public static class VlcDock
{
    // ---- settings (set from PowerShell before Run)
    public static double Scale = 1.0;      // skin build scale: 1.0 = Titlebar-100.vlt
    public static string DockTo = "start"; // "start" | "left" | "right"
    public static int Gap = 8;             // px between strip and Start button / taskbar edge
    public static int OffsetY = 0;         // fine-tune vertical position of the strip
    public static bool ExitWithVlc = true;

    // ---- state
    static bool enabled = true;
    static bool busy;
    static bool fullscreenMode;
    static uint vlcPid;
    static DateTime lastVlcSeen = DateTime.MinValue;
    static DateTime lastPidCheck = DateTime.MinValue;
    static DateTime lastStartLookup = DateTime.MinValue;
    static int startLeft = int.MinValue;   // screen x of the Start button, if found
    static IntPtr locHook = IntPtr.Zero, fgHook = IntPtr.Zero;
    static WinEventProc winEventDelegate = OnWinEvent; // keep alive (GC)
    static TimerProc timerDelegate = OnTimer;

    // ---- Win32
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public int ptX; public int ptY; }

    [StructLayout(LayoutKind.Sequential)]
    struct MONITORINFO { public int cbSize; public RECT rcMonitor; public RECT rcWork; public uint dwFlags; }

    delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    delegate void WinEventProc(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time);
    delegate void TimerProc(IntPtr hwnd, uint msg, UIntPtr id, uint time);

    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int max);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int index);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr FindWindow(string cls, string name);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr FindWindowEx(IntPtr parent, IntPtr after, string cls, string name);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
    [DllImport("user32.dll")] static extern bool GetMonitorInfo(IntPtr mon, ref MONITORINFO mi);
    [DllImport("user32.dll")] static extern IntPtr SetWinEventHook(uint evMin, uint evMax, IntPtr hmod, WinEventProc cb, uint pid, uint tid, uint flags);
    [DllImport("user32.dll")] static extern bool UnhookWinEvent(IntPtr hook);
    [DllImport("user32.dll")] static extern int GetMessage(out MSG msg, IntPtr h, uint min, uint max);
    [DllImport("user32.dll")] static extern bool TranslateMessage(ref MSG msg);
    [DllImport("user32.dll")] static extern IntPtr DispatchMessage(ref MSG msg);
    [DllImport("user32.dll")] static extern UIntPtr SetTimer(IntPtr h, UIntPtr id, uint ms, TimerProc cb);
    [DllImport("user32.dll")] static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
    [DllImport("user32.dll")] static extern void PostQuitMessage(int code);
    [DllImport("user32.dll")] static extern int GetWindowRgn(IntPtr h, IntPtr rgn);
    [DllImport("gdi32.dll")] static extern IntPtr CreateRectRgn(int l, int t, int r, int b);
    [DllImport("gdi32.dll")] static extern int GetRgnBox(IntPtr rgn, out RECT r);
    [DllImport("gdi32.dll")] static extern bool PtInRegion(IntPtr rgn, int x, int y);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);

    const int GWL_EXSTYLE = -20;
    const int WS_EX_TOOLWINDOW = 0x80, WS_EX_APPWINDOW = 0x40000, WS_EX_TOPMOST = 0x8;
    const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOACTIVATE = 0x10, SWP_NOOWNERZORDER = 0x200;
    static readonly IntPtr HWND_TOPMOST = new IntPtr(-1), HWND_NOTOPMOST = new IntPtr(-2);
    const uint GW_HWNDPREV = 3;
    const uint EVENT_SYSTEM_FOREGROUND = 0x3, EVENT_OBJECT_LOCATIONCHANGE = 0x800B;
    const uint WINEVENT_OUTOFCONTEXT = 0, WM_HOTKEY = 0x312;
    const uint MOD_ALT = 1, MOD_CONTROL = 2, MOD_SHIFT = 4, MOD_NOREPEAT = 0x4000;
    const int NULLREGION = 1;

    static int P(double v) { return (int)Math.Round(v * Scale); }
    static int W(RECT r) { return r.Right - r.Left; }
    static int H(RECT r) { return r.Bottom - r.Top; }

    // ---------------------------------------------------------------- entry
    public static void Run()
    {
        fgHook = SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, IntPtr.Zero,
                                 winEventDelegate, 0, 0, WINEVENT_OUTOFCONTEXT);
        SetTimer(IntPtr.Zero, UIntPtr.Zero, 250, timerDelegate);
        // Ctrl+Alt+Shift+V: dock / undock
        RegisterHotKey(IntPtr.Zero, 1, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, 0x56);
        lastVlcSeen = DateTime.Now;

        MSG msg;
        while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0)
        {
            if (msg.message == WM_HOTKEY) { Toggle(); continue; }
            TranslateMessage(ref msg);
            DispatchMessage(ref msg);
        }
        UnregisterHotKey(IntPtr.Zero, 1);
        if (locHook != IntPtr.Zero) UnhookWinEvent(locHook);
        if (fgHook != IntPtr.Zero) UnhookWinEvent(fgHook);
    }

    static void Toggle()
    {
        enabled = !enabled;
        if (!enabled)
        {
            // release the windows: normal z-order, freely movable again
            foreach (IntPtr h in FindSkinWindows())
                SetWindowPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        }
        Tick();
    }

    static void OnTimer(IntPtr hwnd, uint msg, UIntPtr id, uint time) { Tick(); }

    static void OnWinEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (ev == EVENT_OBJECT_LOCATIONCHANGE && idObject != 0) return; // only whole windows
        Tick();
    }

    // ---------------------------------------------------------------- window region
    // What is visible in VLC's main window, from the region skins2 sets on it.
    static void ReadShape(IntPtr h, int hh, out RECT box, out bool barAtBottom, out bool full)
    {
        box = new RECT(); box.Bottom = hh;
        barAtBottom = true;
        full = false;
        IntPtr rgn = CreateRectRgn(0, 0, 0, 0);
        try
        {
            if (GetWindowRgn(h, rgn) <= NULLREGION || GetRgnBox(rgn, out box) <= NULLREGION)
            {
                box = new RECT(); box.Bottom = hh;
                return;
            }
            // "dn" layouts have the bar at the top; only full player + EQ + playlist reach the bottom
            barAtBottom = box.Bottom >= hh - 1;
            // the strip's corner is rounded (transparent); the full player's edge there is not
            full = PtInRegion(rgn, 0, barAtBottom ? hh - P(24) : P(24));
        }
        finally { DeleteObject(rgn); }
    }

    // ---------------------------------------------------------------- VLC process
    static void CheckVlc()
    {
        if ((DateTime.Now - lastPidCheck).TotalMilliseconds < 1000 && vlcPid != 0) return;
        lastPidCheck = DateTime.Now;
        uint pid = 0;
        Process[] ps = Process.GetProcessesByName("vlc");
        if (ps.Length > 0) pid = (uint)ps[0].Id;
        foreach (Process p in ps) p.Dispose();

        if (pid != 0) lastVlcSeen = DateTime.Now;
        if (pid != vlcPid)
        {
            if (locHook != IntPtr.Zero) { UnhookWinEvent(locHook); locHook = IntPtr.Zero; }
            vlcPid = pid;
            if (pid != 0)
                locHook = SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE, IntPtr.Zero,
                                          winEventDelegate, pid, 0, WINEVENT_OUTOFCONTEXT);
        }
        if (ExitWithVlc && pid == 0 && (DateTime.Now - lastVlcSeen).TotalSeconds > 5)
            PostQuitMessage(0);
    }

    static List<IntPtr> FindSkinWindows()
    {
        List<IntPtr> found = new List<IntPtr>();
        if (vlcPid == 0) return found;
        EnumWindows(delegate (IntPtr h, IntPtr l)
        {
            uint pid;
            GetWindowThreadProcessId(h, out pid);
            if (pid != vlcPid || !IsWindowVisible(h)) return true;
            StringBuilder sb = new StringBuilder(64);
            GetClassName(h, sb, 64);
            if (sb.ToString() != "SkinWindowClass") return true;
            int ex = GetWindowLong(h, GWL_EXSTYLE);
            if ((ex & (WS_EX_APPWINDOW | WS_EX_TOOLWINDOW)) != 0) return true; // video / tooltip / hidden parent
            RECT r;
            if (!GetWindowRect(h, out r) || W(r) < 8 || H(r) < 8) return true;  // the skin's 1x1 flag windows
            found.Add(h);
            return true;
        }, IntPtr.Zero);
        return found;
    }

    // ---------------------------------------------------------------- Start button (UI Automation)
    static void UpdateStartButton(IntPtr tray)
    {
        if ((DateTime.Now - lastStartLookup).TotalSeconds < 2) return;
        lastStartLookup = DateTime.Now;
        try
        {
            AutomationElement root = AutomationElement.FromHandle(tray);
            AutomationElement start = root.FindFirst(TreeScope.Descendants,
                new PropertyCondition(AutomationElement.AutomationIdProperty, "StartButton"));
            if (start != null)
            {
                System.Windows.Rect r = start.Current.BoundingRectangle;
                if (!r.IsEmpty && r.Width > 0) { startLeft = (int)r.Left; return; }
            }
        }
        catch (Exception) { }
        startLeft = int.MinValue;
    }

    // ---------------------------------------------------------------- the work
    static void Tick()
    {
        if (busy) return;
        busy = true;
        try { Place(); }
        catch (Exception) { }
        finally { busy = false; }
    }

    static bool IsBelow(IntPtr h, IntPtr other)
    {
        for (IntPtr p = GetWindow(h, GW_HWNDPREV); p != IntPtr.Zero; p = GetWindow(p, GW_HWNDPREV))
            if (p == other) return true;
        return false;
    }

    static bool ForegroundIsFullscreen(IntPtr tray, List<IntPtr> ours)
    {
        IntPtr fg = GetForegroundWindow();
        if (fg == IntPtr.Zero || fg == tray || ours.Contains(fg)) return false;
        StringBuilder sb = new StringBuilder(64);
        GetClassName(fg, sb, 64);
        string cls = sb.ToString();
        if (cls == "Progman" || cls == "WorkerW" || cls == "Shell_TrayWnd") return false;
        RECT r;
        if (!GetWindowRect(fg, out r)) return false;
        MONITORINFO mi = new MONITORINFO();
        mi.cbSize = Marshal.SizeOf(typeof(MONITORINFO));
        if (!GetMonitorInfo(MonitorFromWindow(fg, 2), ref mi)) return false;
        return r.Left <= mi.rcMonitor.Left && r.Top <= mi.rcMonitor.Top &&
               r.Right >= mi.rcMonitor.Right && r.Bottom >= mi.rcMonitor.Bottom;
    }

    static int XFor(bool alignRight, int anchor, int w, int minX, int maxRight)
    {
        int x = alignRight ? anchor - w : anchor;
        if (x + w > maxRight) x = maxRight - w;
        if (x < minX) x = minX;
        return x;
    }

    static void Move(IntPtr h, RECT cur, int x, int y, bool fixZ)
    {
        if (cur.Left == x && cur.Top == y && !fixZ) return;
        uint flags = SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER;
        IntPtr after = HWND_TOPMOST;
        if (!fixZ) flags |= 0x4; // SWP_NOZORDER
        SetWindowPos(h, after, x, y, 0, 0, flags);
    }

    static void Place()
    {
        CheckVlc();
        if (!enabled || vlcPid == 0) return;

        IntPtr tray = FindWindow("Shell_TrayWnd", null);
        if (tray == IntPtr.Zero) return;
        RECT tb;
        GetWindowRect(tray, out tb);
        MONITORINFO mi = new MONITORINFO();
        mi.cbSize = Marshal.SizeOf(typeof(MONITORINFO));
        GetMonitorInfo(MonitorFromWindow(tray, 2), ref mi);
        RECT mon = mi.rcMonitor;
        bool atBottom = (tb.Top + tb.Bottom) / 2 > (mon.Top + mon.Bottom) / 2;

        List<IntPtr> wins = FindSkinWindows();
        IntPtr main = IntPtr.Zero;
        RECT rMain = new RECT();
        foreach (IntPtr h in wins)
        {
            main = h;
            GetWindowRect(h, out rMain);
        }
        if (main == IntPtr.Zero) return;

        // fullscreen app in front: get out of the way
        bool fs = ForegroundIsFullscreen(tray, wins);
        if (fs)
        {
            if (!fullscreenMode)
            {
                IntPtr fg = GetForegroundWindow();
                foreach (IntPtr h in wins)
                {
                    SetWindowPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
                    SetWindowPos(h, fg, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
                }
                fullscreenMode = true;
            }
            return;
        }
        bool leavingFullscreen = fullscreenMode;
        fullscreenMode = false;

        // horizontal anchor: right-aligned to the left of Start (or of the tray),
        // or left-aligned at the left end of the taskbar
        bool alignRight = false;
        int anchor = tb.Left + Gap;
        if (DockTo == "right")
        {
            IntPtr notify = FindWindowEx(tray, IntPtr.Zero, "TrayNotifyWnd", null);
            RECT rn;
            anchor = ((notify != IntPtr.Zero && GetWindowRect(notify, out rn)) ? rn.Left : tb.Right) - Gap;
            alignRight = true;
        }
        else if (DockTo == "start")
        {
            UpdateStartButton(tray);
            if (startLeft != int.MinValue) { anchor = startLeft - Gap; alignRight = true; }
        }

        // vertical placement: the strip inside the taskbar (panels stick out above or
        // below it); the full player's visible part right next to the taskbar
        int hh = H(rMain);
        RECT box;
        bool barAtBottom, full;
        ReadShape(main, hh, out box, out barAtBottom, out full);
        int mainY;
        if (!full)
        {
            int barTop = tb.Top + (H(tb) - P(24)) / 2 + OffsetY;
            mainY = barAtBottom ? barTop - (hh - P(24)) : barTop;
        }
        else
            mainY = atBottom ? tb.Top - box.Bottom : tb.Bottom - box.Top;
        int mainX = XFor(alignRight, anchor, W(rMain), tb.Left + 2, mon.Right);

        bool fixMain = leavingFullscreen || IsBelow(main, tray);
        Move(main, rMain, mainX, mainY, fixMain);
    }
}
