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
using System.IO;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Automation;
using System.Windows.Forms;

public static class VlcDock
{
    // ---- settings (set from PowerShell before Run)
    public static double Scale = 1.0;      // skin build scale: 1.0 = Titlebar-100.vlt
    public static string DockTo = "start"; // "start" | "left" | "right"
    public static int Gap = 8;             // px between strip and Start button / taskbar edge
    public static int OffsetY = 0;         // fine-tune vertical position of the strip
    public static bool ExitWithVlc = true; // false = keep waiting for the next VLC (started with Windows)
    public static bool Dock = true;        // false = only StartPinned, no taskbar docking
    public static bool StartPinned = false;// click VLC's pin button once after each VLC start
    public static string LogPath = null;   // debug log file (null = no log)
    public static bool TrayIcon = true;    // notification-area icon with a menu (dock, pin now, quit)
    public static int RemotePort = 0;      // VLC web interface port (from vlcrc); 0 = no control channel
    public static string RemotePassword = null;   // its http-password (from vlcrc)

    // ---- control channel to VLC (see VlcRemote at the end of this file); created in Run().
    // Remote.Status is refreshed twice a second while VLC runs; Remote.Send(...) sends commands.
    public static VlcRemote Remote = new VlcRemote("127.0.0.1", 0, null);

    // ---- state
    static bool enabled = true;
    static bool busy;
    static bool fullscreenMode;
    static volatile uint vlcPid;           // also read by the remote polling thread
    static DateTime lastVlcSeen = DateTime.MinValue;
    static DateTime lastPidCheck = DateTime.MinValue;
    static DateTime lastStartLookup = DateTime.MinValue;
    static int startLeft = int.MinValue;   // screen x of the Start button, if found
    static uint pinnedPid;                 // VLC process already pinned by StartPinned
    static DateTime mainSeenAt = DateTime.MinValue;
    static readonly object logLock = new object();   // Log is also called from the remote polling thread
    static string lastLogText;             // last line written (without time stamp)
    static int logRepeats;                 // how many identical lines came after it
    static string lastShape;               // last ReadShape result logged
    static int lastBelow = -1;             // last IsBelow(main, tray) logged: -1 unknown, 0 no, 1 yes
    static IntPtr locHook = IntPtr.Zero, fgHook = IntPtr.Zero;
    static WinEventProc winEventDelegate = OnWinEvent; // keep alive (GC)
    static TimerProc timerDelegate = OnTimer;
    static NotifyIcon tray;
    static ContextMenu trayMenu;
    static MenuItem dockItem, pinItem, playItem, logItem;
    static MenuItem playbackItem;          // submenu "Playback": A-B loop, folder jump, EQ preset (Lua interface)
    static Icon trayIcon;
    static IntPtr trayIconHandle = IntPtr.Zero;
    static Thread remoteThread;
    static volatile bool remoteStop;

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
    [DllImport("user32.dll", SetLastError = true)] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
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
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] static extern int GetWindowRgn(IntPtr h, IntPtr rgn);
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr icon);
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
    const uint WM_MOUSEMOVE = 0x200, WM_LBUTTONDOWN = 0x201, WM_LBUTTONUP = 0x202;
    const int MK_LBUTTON = 1;

    const long LogMaxBytes = 1000000;

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
        Remote = new VlcRemote("127.0.0.1", RemotePort, RemotePassword);
        Remote.Logger = Log;
        Log("helper started: scale=" + Scale + " dockTo=" + DockTo + " gap=" + Gap + " offsetY=" + OffsetY +
            " dock=" + Dock + " startPinned=" + StartPinned + " exitWithVlc=" + ExitWithVlc +
            " remote=" + (Remote.Configured ? "port " + RemotePort : "off"));
        StartRemote();
        if (TrayIcon) CreateTray();

        try
        {
            // The tray icon's hidden window lives on this thread, so this loop also
            // delivers its messages (no Application.Run needed).
            MSG msg;
            while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0)
            {
                if (msg.message == WM_HOTKEY) { Toggle(); continue; }
                TranslateMessage(ref msg);
                DispatchMessage(ref msg);
            }
        }
        finally
        {
            remoteStop = true;
            DisposeTray();   // also when VLC quit (not -Watch): no ghost icon left behind
            UnregisterHotKey(IntPtr.Zero, 1);
            if (locHook != IntPtr.Zero) UnhookWinEvent(locHook);
            if (fgHook != IntPtr.Zero) UnhookWinEvent(fgHook);
        }
    }

    // ---------------------------------------------------------------- control channel
    // Background thread: polls VLC's web interface while VLC runs, so the message loop never
    // waits for the network. Off (no thread) when Setup has not enabled the web interface.
    static void StartRemote()
    {
        if (!Remote.Configured) return;
        remoteThread = new Thread(RemoteLoop);
        remoteThread.IsBackground = true;   // never keeps the process alive
        remoteThread.Name = "VlcRemote poll";
        remoteThread.Start();
    }

    static void RemoteLoop()
    {
        while (!remoteStop)
        {
            int wait = 500;
            try
            {
                if (vlcPid == 0) Remote.Reset();
                else if (!Remote.Poll()) wait = 2000;   // VLC still starting, or no web interface: ask less often
            }
            catch (Exception) { wait = 2000; }
            for (int i = 0; i < wait && !remoteStop; i += 50) Thread.Sleep(50);
        }
    }

    static void Toggle()
    {
        enabled = !enabled;
        Log("hotkey: docking " + (enabled ? "on" : "off"));
        if (!enabled)
        {
            // release the windows: normal z-order, freely movable again
            foreach (IntPtr h in FindSkinWindows())
                SetPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        }
        Tick();
    }

    // ---------------------------------------------------------------- tray icon
    // Uses the classic ContextMenu (a native popup menu): it needs no message filter, which
    // a ContextMenuStrip would only get from Application.Run.
    static void CreateTray()
    {
        try
        {
            dockItem = new MenuItem("Dock in taskbar", OnMenuDock);
            pinItem = new MenuItem("Pin VLC on top now", OnMenuPin);
            playItem = new MenuItem("Play / pause", OnMenuPlay);   // smoke test of the control channel
            // These send VLC hotkey actions through the web interface; lua/intf/titlebar.lua (Setup installs it) does the work.
            playbackItem = new MenuItem("Playback", new MenuItem[] {
                new MenuItem("A-B loop (set A / set B / clear)", delegate { Remote.SendAsync("key", "subsync-markaudio"); }),
                new MenuItem("Next folder", delegate { Remote.SendAsync("key", "viewpoint-roll-clock"); }),
                new MenuItem("Previous folder", delegate { Remote.SendAsync("key", "viewpoint-roll-anticlock"); }),
                new MenuItem("Next EQ preset", delegate { Remote.SendAsync("key", "viewpoint-fov-in"); })
            });
            logItem = new MenuItem("Open debug log", OnMenuLog);
            MenuItem quitItem = new MenuItem("Quit helper", OnMenuQuit);
            trayMenu = new ContextMenu(new MenuItem[] { dockItem, pinItem, playItem, playbackItem, logItem, new MenuItem("-"), quitItem });
            trayMenu.Popup += OnMenuPopup;

            tray = new NotifyIcon();
            tray.Icon = MakeTrayIcon();
            tray.Text = "Titlebar VLC helper";
            tray.ContextMenu = trayMenu;
            tray.Visible = true;
        }
        catch (Exception)
        {
            DisposeTray();   // no icon is not fatal, the helper works without it
        }
    }

    static void DisposeTray()
    {
        try
        {
            if (tray != null) { tray.Visible = false; tray.Dispose(); }
            if (trayMenu != null) trayMenu.Dispose();
            if (trayIcon != null) trayIcon.Dispose();
            if (trayIconHandle != IntPtr.Zero) DestroyIcon(trayIconHandle);
        }
        catch (Exception) { }
        tray = null; trayMenu = null; trayIcon = null; trayIconHandle = IntPtr.Zero;
    }

    // Small dark rounded square with a cyan bar (the strip), drawn at the system's small-icon size.
    static Icon MakeTrayIcon()
    {
        int n = SystemInformation.SmallIconSize.Width;
        if (n < 16) n = 16;
        float r = n * 0.22f, d = r * 2, e = n - 1;
        using (Bitmap bmp = new Bitmap(n, n))
        using (Graphics g = Graphics.FromImage(bmp))
        using (GraphicsPath path = new GraphicsPath())
        using (SolidBrush back = new SolidBrush(Color.FromArgb(34, 38, 44)))
        using (SolidBrush bar = new SolidBrush(Color.FromArgb(0, 200, 230)))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            path.AddArc(0, 0, d, d, 180, 90);
            path.AddArc(e - d, 0, d, d, 270, 90);
            path.AddArc(e - d, e - d, d, d, 0, 90);
            path.AddArc(0, e - d, d, d, 90, 90);
            path.CloseFigure();
            g.FillPath(back, path);
            g.FillRectangle(bar, n * 0.2f, n * 0.42f, n * 0.6f, n * 0.16f);
            trayIconHandle = bmp.GetHicon();
        }
        trayIcon = Icon.FromHandle(trayIconHandle);   // does not own the handle: DestroyIcon in DisposeTray
        return trayIcon;
    }

    static void OnMenuPopup(object sender, EventArgs e)
    {
        dockItem.Enabled = Dock;
        dockItem.Checked = Dock && enabled;
        pinItem.Enabled = vlcPid != 0;
        playItem.Visible = Remote.Configured;
        playItem.Enabled = vlcPid != 0 && Remote.Status.Ok;
        playbackItem.Visible = Remote.Configured;
        playbackItem.Enabled = vlcPid != 0 && Remote.Status.Ok;
        logItem.Visible = LogPath != null;
        logItem.Enabled = LogPath != null && File.Exists(LogPath);
    }

    static void OnMenuLog(object sender, EventArgs e)
    {
        try { Process.Start(LogPath); }   // opens in the default text editor
        catch (Exception) { }
    }

    static void OnMenuDock(object sender, EventArgs e) { if (Dock) Toggle(); }

    static void OnMenuPin(object sender, EventArgs e)
    {
        IntPtr main;
        RECT r;
        if (!FindMain(FindSkinWindows(), out main, out r)) return;
        ClickPin(main, r);
    }

    static void OnMenuPlay(object sender, EventArgs e) { Remote.SendAsync("pl_pause"); }

    static void OnMenuQuit(object sender, EventArgs e) { PostQuitMessage(0); }

    static void OnTimer(IntPtr hwnd, uint msg, UIntPtr id, uint time) { Tick(); }

    static void OnWinEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (ev == EVENT_OBJECT_LOCATIONCHANGE && idObject != 0) return; // only whole windows
        if (ev == EVENT_SYSTEM_FOREGROUND && LogPath != null)
            Log("foreground: " + Describe(hwnd));
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
        finally
        {
            DeleteObject(rgn);
            LogShape(box, hh, barAtBottom, full);
        }
    }

    // ---------------------------------------------------------------- debug log
    // Only active when LogPath is set. Never throws: a log problem must not stop the helper.
    // Identical consecutive lines are counted instead of repeated; at about 1 MB the file
    // is moved to <log>.old (replacing the previous one) and a new file is started.
    static void Log(string text)
    {
        string path = LogPath;
        if (path == null) return;
        lock (logLock) LogLocked(path, text);
    }

    static void LogLocked(string path, string text)
    {
        try
        {
            if (text == lastLogText) { logRepeats++; return; }
            string head = "";
            if (logRepeats > 0) head = Stamp() + "  (previous line repeated " + logRepeats + " more times)\r\n";
            lastLogText = text;
            logRepeats = 0;
            FileInfo fi = new FileInfo(path);
            if (fi.Exists && fi.Length > LogMaxBytes)
            {
                if (File.Exists(path + ".old")) File.Delete(path + ".old");
                File.Move(path, path + ".old");
            }
            File.AppendAllText(path, head + Stamp() + "  " + text + "\r\n");
        }
        catch (Exception) { }
    }

    static string Stamp() { return DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff"); }

    static string ClassOf(IntPtr h)
    {
        StringBuilder sb = new StringBuilder(64);
        if (h != IntPtr.Zero) GetClassName(h, sb, 64);
        return sb.ToString();
    }

    static string Describe(IntPtr h)
    {
        if (h == IntPtr.Zero) return "none";
        return "0x" + h.ToInt64().ToString("X") + " class=\"" + ClassOf(h) + "\"";
    }

    static void LogShape(RECT box, int hh, bool barAtBottom, bool full)
    {
        if (LogPath == null) return;
        string s = "shape: box=" + box.Left + "," + box.Top + "," + box.Right + "," + box.Bottom +
                   " windowH=" + hh + " barAtBottom=" + barAtBottom + " full=" + full;
        if (s == lastShape) return;
        lastShape = s;
        Log(s);
    }

    // ---------------------------------------------------------------- VLC process
    static void CheckVlc()
    {
        // look for VLC every second while it runs, every 2 s while waiting for it (-Watch)
        if ((DateTime.Now - lastPidCheck).TotalMilliseconds < (vlcPid != 0 ? 1000 : 2000)) return;
        lastPidCheck = DateTime.Now;
        uint pid = 0;
        Process[] ps = Process.GetProcessesByName("vlc");
        if (ps.Length > 0) pid = (uint)ps[0].Id;
        foreach (Process p in ps) p.Dispose();

        if (pid != 0) lastVlcSeen = DateTime.Now;
        if (pid != vlcPid)
        {
            if (vlcPid != 0) Log("VLC lost: pid " + vlcPid);
            if (pid != 0) Log("VLC found: pid " + pid);
            if (locHook != IntPtr.Zero) { UnhookWinEvent(locHook); locHook = IntPtr.Zero; }
            vlcPid = pid;
            mainSeenAt = DateTime.MinValue;
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

    // SetWindowPos with a log line (target, insert-after, position, flags, result)
    static void SetPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags)
    {
        bool ok = SetWindowPos(h, after, x, y, cx, cy, flags);
        if (LogPath == null) return;
        int err = ok ? 0 : Marshal.GetLastWin32Error();
        string a = after == HWND_TOPMOST ? "TOPMOST" : after == HWND_NOTOPMOST ? "NOTOPMOST" : Describe(after);
        Log("SetWindowPos " + Describe(h) + " after=" + a + " x=" + x + " y=" + y + " cx=" + cx + " cy=" + cy +
            " flags=0x" + flags.ToString("X") + (ok ? " ok" : " FAILED err=" + err));
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
        SetPos(h, after, x, y, 0, 0, flags);
    }

    // ---------------------------------------------------------------- start pinned
    // VLC never saves "always on top", so it starts unpinned. Clicking the skin's own pin
    // button (posted mouse messages, which skins2 handles like real clicks) keeps VLC's
    // state and the lit pin icon in sync, unlike setting HWND_TOPMOST from outside.
    static void PinOnce(IntPtr main, RECT r)
    {
        if (pinnedPid == vlcPid) return;
        if (mainSeenAt == DateTime.MinValue) { mainSeenAt = DateTime.Now; return; }
        if ((DateTime.Now - mainSeenAt).TotalMilliseconds < 1500) return;  // let the skin settle
        ClickPin(main, r);
    }

    // The click itself, also used by the tray menu. It toggles the skin's pin button.
    static void ClickPin(IntPtr main, RECT r)
    {
        pinnedPid = vlcPid;   // StartPinned must not click again for this VLC

        int hh = H(r);
        RECT box;
        bool barAtBottom, full;
        ReadShape(main, hh, out box, out barAtBottom, out full);
        int x, y;
        if (full)   // full player: small pin, 82 px from the right edge, 5 px from its top
        {
            x = W(r) - P(82) + P(9);
            y = (barAtBottom ? hh - P(122) : 0) + P(11);
        }
        else        // strip: pin 34 px from the right edge
        {
            x = W(r) - P(34) + P(11);
            y = (barAtBottom ? hh - P(24) : 0) + P(12);
        }
        Log("PinOnce: click at " + x + "," + y + " in " + Describe(main) + " (full=" + full + " barAtBottom=" + barAtBottom +
            " windowW=" + W(r) + " windowH=" + hh + ")");
        IntPtr pos = new IntPtr((y << 16) | (x & 0xFFFF));
        PostMessage(main, WM_MOUSEMOVE, IntPtr.Zero, pos);
        PostMessage(main, WM_LBUTTONDOWN, new IntPtr(MK_LBUTTON), pos);
        PostMessage(main, WM_LBUTTONUP, IntPtr.Zero, pos);
    }

    static bool FindMain(List<IntPtr> wins, out IntPtr main, out RECT rMain)
    {
        main = IntPtr.Zero;
        rMain = new RECT();
        foreach (IntPtr h in wins)
        {
            main = h;
            GetWindowRect(h, out rMain);
        }
        return main != IntPtr.Zero;
    }

    static void Place()
    {
        CheckVlc();
        if (vlcPid == 0) return;

        List<IntPtr> wins = FindSkinWindows();
        IntPtr main;
        RECT rMain;
        if (!FindMain(wins, out main, out rMain)) return;
        if (StartPinned) PinOnce(main, rMain);
        if (!Dock || !enabled) return;

        IntPtr tray = FindWindow("Shell_TrayWnd", null);
        if (tray == IntPtr.Zero) return;
        RECT tb;
        GetWindowRect(tray, out tb);
        MONITORINFO mi = new MONITORINFO();
        mi.cbSize = Marshal.SizeOf(typeof(MONITORINFO));
        GetMonitorInfo(MonitorFromWindow(tray, 2), ref mi);
        RECT mon = mi.rcMonitor;
        bool atBottom = (tb.Top + tb.Bottom) / 2 > (mon.Top + mon.Bottom) / 2;

        // fullscreen app in front: get out of the way
        bool fs = ForegroundIsFullscreen(tray, wins);
        if (fs)
        {
            if (!fullscreenMode)
            {
                IntPtr fg = GetForegroundWindow();
                Log("fullscreen mode: enter, foreground " + Describe(fg));
                foreach (IntPtr h in wins)
                {
                    SetPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
                    SetPos(h, fg, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
                }
                fullscreenMode = true;
            }
            return;
        }
        bool leavingFullscreen = fullscreenMode;
        fullscreenMode = false;
        if (leavingFullscreen) Log("fullscreen mode: leave");

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

        bool below = IsBelow(main, tray);
        if (LogPath != null && lastBelow != (below ? 1 : 0))
        {
            lastBelow = below ? 1 : 0;
            Log("IsBelow(main, tray) = " + below + (below ? " (taskbar is above VLC)" : " (VLC is above the taskbar)"));
        }
        bool fixMain = leavingFullscreen || below;
        Move(main, rMain, mainX, mainY, fixMain);
    }
}

// ---------------------------------------------------------------------------------------
// VlcRemote - reads VLC's playback state and sends it commands through VLC's built-in web
// interface (extraintf=http, bound to 127.0.0.1; vlc-taskbar.ps1 -Setup writes the settings).
//
//   VlcRemote r = new VlcRemote("127.0.0.1", 48080, password);
//   if (r.Configured && r.Poll()) { VlcStatus s = r.Status; ... s.State, s.Time, s.Length ... }
//   r.Send("pl_pause");            // blocks up to 1 s: use SendAsync from the UI thread
//   r.Send("seek", "90");          // seconds; also "+10", "-10", "50%", "1m30s" (VLC's own syntax)
//
// Commands that work: pl_pause (toggle; plays when stopped), pl_forcepause, pl_forceresume,
// pl_stop, pl_next, pl_previous, seek (val = target), volume (val = 0..512, 256 = 100 %).
// Each request is requests/status.json?command=..., and VLC answers with the new status, so
// Send updates Status as well. Requests are serialized; every call has a 1 s timeout.
// Basic auth with an empty user name. Poll / Send never throw: they return false and set
// Status to VlcStatus.Offline. Status can be read from any thread.
// ---------------------------------------------------------------------------------------
public enum VlcState { Offline, Stopped, Playing, Paused }

public sealed class VlcStatus
{
    public bool Ok;                    // false = VLC / its web interface did not answer
    public VlcState State = VlcState.Offline;
    public int Time;                   // seconds into the current item (VLC reports whole seconds)
    public int Length;                 // seconds, 0 = unknown (streams)
    public double Position;            // 0.0 - 1.0
    public string Title = "";          // title tag, else the file name, else ""
    public string Artist = "";
    public string Album = "";
    public int PlaylistId = -1;        // id of the current playlist item, -1 = none
    public DateTime At = DateTime.MinValue;   // when it was read

    public static readonly VlcStatus Offline = new VlcStatus();
}

public sealed class VlcRemote
{
    const int TimeoutMs = 1000;

    readonly string host;
    readonly int port;
    readonly string auth;
    readonly object requestLock = new object();
    volatile VlcStatus status = VlcStatus.Offline;
    string lastError;                  // last problem logged, so a lasting problem is logged once
    bool wasConnected;

    public Action<string> Logger;      // optional; called from the polling thread, so it must be thread-safe

    public VlcRemote(string host, int port, string password)
    {
        this.host = string.IsNullOrEmpty(host) ? "127.0.0.1" : host;
        this.port = port;
        this.auth = string.IsNullOrEmpty(password) ? null :
            "Basic " + Convert.ToBase64String(Encoding.UTF8.GetBytes(":" + password));
    }

    // True when a port and a password are known. If not, every call returns false without
    // touching the network.
    public bool Configured { get { return port > 0 && port < 65536 && auth != null; } }

    // The newest status; VlcStatus.Offline until a request succeeded.
    public VlcStatus Status { get { return status; } }

    // Reads requests/status.json and updates Status.
    public bool Poll() { return Request(null, null); }

    // Sends a command and updates Status from the answer. val is optional (for seek, volume).
    public bool Send(string command, string val = null)
    {
        if (string.IsNullOrEmpty(command)) return false;
        return Request(command, val);
    }

    // Send on a thread-pool thread (the result is dropped): for menu and button handlers.
    public void SendAsync(string command, string val = null)
    {
        System.Threading.ThreadPool.QueueUserWorkItem(delegate (object o) { Send(command, val); });
    }

    // Forget the old status (VLC is gone).
    public void Reset() { status = VlcStatus.Offline; }

    bool Request(string command, string val)
    {
        if (!Configured) return false;
        lock (requestLock)
        {
            string url = "http://" + host + ":" + port + "/requests/status.json";
            if (command != null)
            {
                url += "?command=" + Uri.EscapeDataString(command);
                if (val != null) url += "&val=" + Uri.EscapeDataString(val);
            }
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
                req.Method = "GET";
                req.Timeout = TimeoutMs;
                req.ReadWriteTimeout = TimeoutMs;
                req.Proxy = null;                  // never through a system proxy / WPAD lookup
                req.KeepAlive = false;
                req.AllowAutoRedirect = false;
                req.Headers["Authorization"] = auth;   // sent at once: no 401 round trip
                string text;
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                using (Stream s = resp.GetResponseStream())
                using (StreamReader sr = new StreamReader(s, Encoding.UTF8))
                    text = sr.ReadToEnd();
                VlcStatus st = Parse(text);
                status = st;
                if (!wasConnected || lastError != null) Say("web interface connected");
                wasConnected = true;
                lastError = null;
                return true;
            }
            catch (WebException ex)
            {
                HttpWebResponse r = ex.Response as HttpWebResponse;
                if (r != null)
                {
                    string why = "HTTP " + (int)r.StatusCode;
                    if (r.StatusCode == HttpStatusCode.Unauthorized || r.StatusCode == HttpStatusCode.Forbidden)
                        why += " (wrong or missing http-password)";
                    r.Close();
                    return Fail(why);
                }
                return Fail(ex.Status.ToString());     // ConnectFailure while VLC starts, Timeout, ...
            }
            catch (Exception ex)
            {
                return Fail(ex.GetType().Name + ": " + ex.Message);
            }
        }
    }

    bool Fail(string why)
    {
        status = VlcStatus.Offline;
        if (why != lastError)
        {
            lastError = why;
            Say("web interface not available: " + why);
        }
        wasConnected = false;
        return false;
    }

    void Say(string text)
    {
        Action<string> log = Logger;
        if (log == null) return;
        try { log("remote: " + text); }
        catch (Exception) { }
    }

    // ---- status.json -> VlcStatus
    static VlcStatus Parse(string text)
    {
        Dictionary<string, object> root = MiniJson.Parse(text) as Dictionary<string, object>;
        if (root == null) throw new FormatException("status.json is not an object");
        VlcStatus st = new VlcStatus();
        st.Ok = true;
        st.At = DateTime.Now;
        string state = Str(root, "state");
        st.State = state == "playing" ? VlcState.Playing :
                   state == "paused" ? VlcState.Paused : VlcState.Stopped;
        st.Time = (int)Num(root, "time", 0);
        st.Length = (int)Num(root, "length", 0);
        st.Position = Num(root, "position", 0);
        st.PlaylistId = (int)Num(root, "currentplid", -1);

        // information.category.meta: title, artist, album, filename, ... (only when an item is loaded)
        Dictionary<string, object> info = Sub(root, "information");
        Dictionary<string, object> cat = info != null ? Sub(info, "category") : null;
        Dictionary<string, object> meta = cat != null ? Sub(cat, "meta") : null;
        if (meta != null)
        {
            st.Title = Str(meta, "title");
            if (st.Title.Length == 0) st.Title = Str(meta, "filename");
            st.Artist = Str(meta, "artist");
            st.Album = Str(meta, "album");
        }
        return st;
    }

    static Dictionary<string, object> Sub(Dictionary<string, object> d, string key)
    {
        object o;
        return d.TryGetValue(key, out o) ? o as Dictionary<string, object> : null;
    }

    static string Str(Dictionary<string, object> d, string key)
    {
        object o;
        if (!d.TryGetValue(key, out o) || o == null) return "";
        string s = o as string;
        return s != null ? s : Convert.ToString(o, System.Globalization.CultureInfo.InvariantCulture);
    }

    static double Num(Dictionary<string, object> d, string key, double fallback)
    {
        object o;
        if (!d.TryGetValue(key, out o) || !(o is double)) return fallback;
        double v = (double)o;
        return double.IsNaN(v) || double.IsInfinity(v) ? fallback : v;
    }
}

// Minimal JSON reader (C# 5 Add-Type has no JSON library without System.Web.Extensions).
// Objects -> Dictionary<string, object>, arrays -> List<object>, numbers -> double, strings,
// bool, null. Tolerant: raw control characters inside strings are accepted. Throws
// FormatException on anything else it does not understand.
static class MiniJson
{
    public static object Parse(string text)
    {
        int i = 0;
        object v = Value(text, ref i, 0);
        Skip(text, ref i);
        if (i != text.Length) throw new FormatException("trailing text in JSON");
        return v;
    }

    static void Skip(string t, ref int i)
    {
        while (i < t.Length && (t[i] == ' ' || t[i] == '\t' || t[i] == '\r' || t[i] == '\n' || t[i] == '\uFEFF')) i++;
    }

    static object Value(string t, ref int i, int depth)
    {
        if (depth > 32) throw new FormatException("JSON nested too deep");
        Skip(t, ref i);
        if (i >= t.Length) throw new FormatException("unexpected end of JSON");
        char c = t[i];
        if (c == '{')
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            i++;
            Skip(t, ref i);
            if (i < t.Length && t[i] == '}') { i++; return d; }
            while (true)
            {
                Skip(t, ref i);
                if (i >= t.Length || t[i] != '"') throw new FormatException("JSON object key expected");
                string key = ReadString(t, ref i);
                Skip(t, ref i);
                if (i >= t.Length || t[i] != ':') throw new FormatException("':' expected");
                i++;
                d[key] = Value(t, ref i, depth + 1);
                Skip(t, ref i);
                if (i < t.Length && t[i] == ',') { i++; continue; }
                if (i < t.Length && t[i] == '}') { i++; return d; }
                throw new FormatException("',' or '}' expected");
            }
        }
        if (c == '[')
        {
            List<object> a = new List<object>();
            i++;
            Skip(t, ref i);
            if (i < t.Length && t[i] == ']') { i++; return a; }
            while (true)
            {
                a.Add(Value(t, ref i, depth + 1));
                Skip(t, ref i);
                if (i < t.Length && t[i] == ',') { i++; continue; }
                if (i < t.Length && t[i] == ']') { i++; return a; }
                throw new FormatException("',' or ']' expected");
            }
        }
        if (c == '"') return ReadString(t, ref i);
        if (string.CompareOrdinal(t, i, "true", 0, 4) == 0) { i += 4; return true; }
        if (string.CompareOrdinal(t, i, "false", 0, 5) == 0) { i += 5; return false; }
        if (string.CompareOrdinal(t, i, "null", 0, 4) == 0) { i += 4; return null; }
        int start = i;
        while (i < t.Length && "+-0123456789.eE".IndexOf(t[i]) >= 0) i++;
        double n;
        if (i == start || !double.TryParse(t.Substring(start, i - start), System.Globalization.NumberStyles.Float,
                                          System.Globalization.CultureInfo.InvariantCulture, out n))
            throw new FormatException("bad JSON value at " + start);
        return n;
    }

    static string ReadString(string t, ref int i)
    {
        StringBuilder sb = new StringBuilder();
        i++;   // opening quote
        while (i < t.Length)
        {
            char c = t[i++];
            if (c == '"') return sb.ToString();
            if (c != '\\') { sb.Append(c); continue; }
            if (i >= t.Length) break;
            c = t[i++];
            switch (c)
            {
                case 'b': sb.Append('\b'); break;
                case 'f': sb.Append('\f'); break;
                case 'n': sb.Append('\n'); break;
                case 'r': sb.Append('\r'); break;
                case 't': sb.Append('\t'); break;
                case 'u':
                    int code;
                    if (i + 4 > t.Length || !int.TryParse(t.Substring(i, 4), System.Globalization.NumberStyles.HexNumber,
                                                          System.Globalization.CultureInfo.InvariantCulture, out code))
                        throw new FormatException("bad \\u escape");
                    sb.Append((char)code);
                    i += 4;
                    break;
                default: sb.Append(c); break;   // \" \\ \/
            }
        }
        throw new FormatException("unterminated JSON string");
    }
}
