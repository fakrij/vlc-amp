// VlcDock - keeps the "Titlebar" VLC skin docked in the Windows taskbar.
// Loaded by vlc-taskbar.ps1 (Windows PowerShell 5.1, C# 5 syntax).
//
// The helper re-places VLC's main window whenever it moves (WinEvent hook) and on
// a 250 ms timer. The skin has one main window (class "SkinWindowClass", owned by
// vlc.exe). All its layouts have the same size; the parts without pixels are cut
// out with a window region, so the helper reads that region to see what is showing
// (DockShape.Classify, from the height of the visible part):
//   bar at the bottom of the window = panels open above it ("up" layouts), else below
//   strip  -> the strip sits inside the taskbar, left of Start (panels stick out)
//   full   -> the visible part just above the taskbar
// VLC's skin engine keeps its own copy of the window position and does not notice
// moves from outside, so the helper moves the window by letting VLC move itself (a
// posted drag on the skin's grip, see MoveTo). The skin also has 1x1 "flag" windows
// (no pixels); the helper never touches them, so their WS_EX_TOPMOST is VLC's own
// "always on top" state (VlcPinState). The video window (WS_EX_APPWINDOW) is never touched.

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

public static partial class VlcDock   // partial: the taskbar button is at the end of this file
{
    // ---- settings (set from PowerShell before Run)
    public static double Scale = 1.0;      // skin build scale: 1.0 = Titlebar-100.vlt
    public static double BarHeight = 24;   // strip height in logical px: 24, or 36 for Titlebar-taskbar-NNN.vlt (generator --bar-height)
    public static string DockTo = "start"; // "start" | "left" | "right"
    public static int Gap = 8;             // px between strip and Start button / taskbar edge
    public static int OffsetY = 0;         // fine-tune vertical position of the strip
    public static bool ExitWithVlc = true; // false = keep waiting for the next VLC (started with Windows)
    public static bool Dock = true;        // false = only StartPinned, no taskbar docking
    public static bool StartPinned = false;// click VLC's pin button once after each VLC start
    public static bool FlipPanels = true;  // docked strip with PL / EQ open off the screen (below a bottom taskbar): click the flip arrow
    public static string LogPath = null;   // debug log file (null = no log)
    public static bool TrayIcon = true;    // notification-area icon with a menu (dock, pin now, quit)
    public static int RemotePort = 0;      // VLC web interface port (from vlcrc); 0 = no control channel
    public static string SkinFile = null;  // the skin file Scale / BarHeight come from, and where it was found (log only)
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
    static bool lastBarAtBottom = true;    // direction of the last shape that showed it (see DockShape.Classify)
    static Dictionary<string, string> logged = new Dictionary<string, string>();   // LogChange: last text per topic
    static int startMisses;                // Start button lookups failed in a row (the last position is kept)
    // moving: see MoveTo
    static bool dragPending;               // a drag was posted to VLC and has not shown its effect yet
    static DateTime dragAt;
    static int dragFromX, dragFromY, dragToX, dragToY;
    static int dragFails, dragMisses;      // in a row: VLC did not move / moved somewhere else
    static bool dragOff;                   // drags do not work with this VLC: SetWindowPos from now on
    static int lastTargetX = int.MinValue, lastTargetY = int.MinValue;
    // z-order: see FixZOrder
    static bool helperTop;                 // the main window is topmost because the helper made it so
    static int lastMainTop = -1;           // main window's WS_EX_TOPMOST at the last tick (-1 unknown)
    static int pinOddTicks;                // ticks in a row where VLC's own flag contradicts the flag windows
    static bool pinFromMain;               // flag windows proved useless: VLC's pin = the main window's flag
    static List<DateTime> raises = new List<DateTime>();   // re-raises above the taskbar in the last 10 s
    static DateTime raiseWarnAt = DateTime.MinValue;
    // panels flip: see FlipIfOffScreen
    static DateTime lastFlipAt = DateTime.MinValue;
    static int flipTries;
    // panels flip keeps the bar in place (item 32): see KeepBarOnFlip
    static bool flipRef;                   // the fields below describe the last shape with a known direction
    static IntPtr flipRefMain;
    static bool flipRefFull, flipRefUp;
    static int flipRefBarTop;
    static RECT flipRefRect;
    static bool flipMoving;                // moving the window after a flip until it gets there
    static bool flipMoveFull;
    static int flipToX, flipToY;
    static DateTime flipMoveUntil;
    // VLC hidden / minimized (item 33): see KeepVisible
    static IntPtr lastMain = IntPtr.Zero;  // the main skin window last seen visible ...
    static RECT lastMainRect;              // ... where it was ...
    static ShapeInfo lastMainShape;        // ... and what it showed
    static bool hidden;                    // the main window is not visible right now
    static DateTime hiddenAt;
    static bool hiddenByUser;              // minimized with the full player's own button: left alone
    static DateTime lastRestoreAt = DateTime.MinValue;
    static List<DateTime> restores = new List<DateTime>();
    static DateTime lastFullTick = DateTime.MinValue;
    static IntPtr locHook = IntPtr.Zero, fgHook = IntPtr.Zero;
    static IntPtr minHook = IntPtr.Zero, showHook = IntPtr.Zero, cloakHook = IntPtr.Zero;   // VLC's windows: logged (item 33)
    static WinEventProc winEventDelegate = OnWinEvent; // keep alive (GC)
    static WinEventProc vlcEventDelegate = OnVlcWindowEvent;
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
    struct POINT { public int X, Y; }

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
    [DllImport("gdi32.dll")] static extern uint GetRegionData(IntPtr rgn, uint count, byte[] data);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int vk);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] static extern bool ShowWindowAsync(IntPtr h, int cmd);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attr, out int value, int size);
    // DPI (see DpiEnter); the first three need Windows 10 1607, the next two 8.1 / Vista
    [DllImport("user32.dll")] static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] static extern IntPtr GetThreadDpiAwarenessContext();
    [DllImport("user32.dll")] static extern int GetAwarenessFromDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] static extern uint GetDpiForWindow(IntPtr h);
    [DllImport("shcore.dll")] static extern int SetProcessDpiAwareness(int value);
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();

    const int GWL_EXSTYLE = -20;
    const int WS_EX_TOOLWINDOW = 0x80, WS_EX_APPWINDOW = 0x40000, WS_EX_TOPMOST = 0x8;
    const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOZORDER = 0x4, SWP_NOACTIVATE = 0x10, SWP_NOOWNERZORDER = 0x200;
    static readonly IntPtr HWND_TOPMOST = new IntPtr(-1), HWND_NOTOPMOST = new IntPtr(-2);
    const uint GW_OWNER = 4, GW_HWNDPREV = 3;
    const int VK_LBUTTON = 1, VK_RBUTTON = 2;
    const uint EVENT_SYSTEM_FOREGROUND = 0x3, EVENT_OBJECT_LOCATIONCHANGE = 0x800B;
    const uint EVENT_SYSTEM_MINIMIZESTART = 0x16, EVENT_SYSTEM_MINIMIZEEND = 0x17;
    const uint EVENT_OBJECT_SHOW = 0x8002, EVENT_OBJECT_HIDE = 0x8003, EVENT_OBJECT_CLOAKED = 0x8017, EVENT_OBJECT_UNCLOAKED = 0x8018;
    const int DWMWA_CLOAKED = 14, SW_SHOWNOACTIVATE = 4;
    static readonly IntPtr DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = new IntPtr(-4), DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = new IntPtr(-3);
    const uint WINEVENT_OUTOFCONTEXT = 0, WM_HOTKEY = 0x312;
    const uint MOD_ALT = 1, MOD_CONTROL = 2, MOD_SHIFT = 4, MOD_NOREPEAT = 0x4000;
    const int NULLREGION = 1;
    const uint WM_MOUSEMOVE = 0x200, WM_LBUTTONDOWN = 0x201, WM_LBUTTONUP = 0x202;
    const int MK_LBUTTON = 1;

    const long LogMaxBytes = 1000000;

    static int W(RECT r) { return r.Right - r.Left; }
    static int H(RECT r) { return r.Bottom - r.Top; }

    // ---------------------------------------------------------------- entry
    public static void Run()
    {
        // A hidden helper that dies leaves nothing behind: log what killed it.
        AppDomain.CurrentDomain.UnhandledException += delegate(object o, UnhandledExceptionEventArgs e)
        {
            Log("CRASH (unhandled, terminating=" + e.IsTerminating + "): " + e.ExceptionObject);
        };
        DpiInit();   // first: every coordinate the helper reads or posts is in physical pixels from here on
        fgHook = SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, IntPtr.Zero,
                                 winEventDelegate, 0, 0, WINEVENT_OUTOFCONTEXT);
        SetTimer(IntPtr.Zero, UIntPtr.Zero, 50, timerDelegate);   // work every 250 ms, every 50 ms while the mouse is over VLC (OnTimer)
        // Ctrl+Alt+Shift+V: dock / undock
        RegisterHotKey(IntPtr.Zero, 1, MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, 0x56);
        lastVlcSeen = DateTime.Now;
        Remote = new VlcRemote("127.0.0.1", RemotePort, RemotePassword);
        Remote.Logger = Log;
        Log("helper started: scale=" + Scale + " barHeight=" + BarHeight + " dockTo=" + DockTo + " gap=" + Gap + " offsetY=" + OffsetY +
            " dock=" + Dock + " startPinned=" + StartPinned + " exitWithVlc=" + ExitWithVlc +
            " remote=" + (Remote.Configured ? "port " + RemotePort : "off") +
            " skinFile=" + (SkinFile ?? "?") + " dpi: " + dpiSetup);
        StartRemote();
        if (TrayIcon) CreateTray();
        TaskbarStart();  // own taskbar button (end of this file)

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
            Log("helper exiting (message loop ended)");
            remoteStop = true;
            TaskbarStop();
            DisposeTray();   // also when VLC quit (not -Watch): no ghost icon left behind
            UnregisterHotKey(IntPtr.Zero, 1);
            UnhookVlc();
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
        IntPtr dpi = DpiEnter();
        try { ToggleDocking(); }
        finally { DpiLeave(dpi); }
    }

    static void ToggleDocking()
    {
        enabled = !enabled;
        Log("hotkey: docking " + (enabled ? "on" : "off"));
        if (!enabled)
        {
            // release the window: freely movable again, and "on top" exactly as VLC's pin says
            IntPtr main;
            RECT r;
            if (FindMain(FindSkinWindows(), out main, out r))
            {
                string detail;
                int pin = VlcPinState(main, out detail);
                bool mainTop = IsTopmost(main);
                if (pin == 0 && mainTop) SetPos(main, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                if (pin == 1 && !mainTop) SetPos(main, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                helperTop = false;
            }
        }
        flipRef = false; flipMoving = false; dragPending = false;
        Tick();
    }

    // ---------------------------------------------------------------- DPI
    // Second Windows test (125 %): powershell.exe is DPI-unaware and VLC is DPI-aware, so Windows
    // scaled the helper's view of VLC's window (587x436 instead of 734x545, positions / 1.25, the
    // Start button too). While a thread handles a message for a window it takes that window's DPI
    // awareness, so the helper got one or the other depending on the path that called Place
    // (WinEvent / timer vs. a message to a WinForms window), and moved VLC back and forth between
    // them (the flashing), with drags that missed by the ratio. Now the helper's thread is per-
    // monitor aware (V2, else V1) from the start, so windows it creates are too, and every entry
    // point that touches windows sets it again (DpiEnter / DpiLeave): all coordinates are physical,
    // as GetWindowRgn, VLC's own client coordinates (posted drags and clicks) and UI Automation's
    // BoundingRectangle for a per-monitor-aware caller are. Before Windows 10 1607 (no thread
    // contexts): the process is made per-monitor aware (8.1) or system aware (Vista) instead.
    static int dpiApi;                     // 1 = thread DPI contexts work, -1 = not available
    static string dpiSetup = "not set";

    static void DpiInit()
    {
        DpiEnter();   // no DpiLeave: the thread stays per-monitor aware
        if (dpiApi > 0) { dpiSetup = "thread " + DpiAwareness(); return; }
        try
        {
            int hr = SetProcessDpiAwareness(2);   // PROCESS_PER_MONITOR_DPI_AWARE
            dpiSetup = "process per-monitor aware (SetProcessDpiAwareness hr=0x" + hr.ToString("X8") + ")";
            return;
        }
        catch (Exception) { }
        try { dpiSetup = "process system aware (SetProcessDPIAware " + (SetProcessDPIAware() ? "ok" : "failed") + ")"; }
        catch (Exception) { dpiSetup = "no DPI API: coordinates may be scaled"; }
    }

    // Makes this thread per-monitor DPI aware; returns the context to give back to DpiLeave.
    static IntPtr DpiEnter()
    {
        if (dpiApi < 0) return IntPtr.Zero;
        try
        {
            IntPtr old = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
            if (old == IntPtr.Zero) old = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE);   // before 1703
            if (old == IntPtr.Zero) { dpiApi = -1; return IntPtr.Zero; }
            dpiApi = 1;
            return old;
        }
        catch (Exception) { dpiApi = -1; return IntPtr.Zero; }   // EntryPointNotFoundException: older Windows
    }

    static void DpiLeave(IntPtr old)
    {
        if (old == IntPtr.Zero || dpiApi <= 0) return;
        try { SetThreadDpiAwarenessContext(old); }
        catch (Exception) { }
    }

    static string DpiAwareness()
    {
        try
        {
            int a = GetAwarenessFromDpiAwarenessContext(GetThreadDpiAwarenessContext());
            return a == 0 ? "DPI-unaware" : a == 1 ? "system DPI aware" : a == 2 ? "per-monitor DPI aware" : "awareness " + a;
        }
        catch (Exception) { return "awareness unknown"; }
    }

    static string DpiOf(IntPtr h)
    {
        try { return GetDpiForWindow(h).ToString(); }
        catch (Exception) { return "?"; }
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
        IntPtr dpi = DpiEnter();   // a menu click comes through the tray icon's window
        try
        {
            IntPtr main;
            RECT r;
            if (FindMain(FindSkinWindows(), out main, out r)) ClickPin(main, r);
        }
        finally { DpiLeave(dpi); }
    }

    static void OnMenuPlay(object sender, EventArgs e) { Remote.SendAsync("pl_pause"); }

    static void OnMenuQuit(object sender, EventArgs e) { PostQuitMessage(0); }

    // Every 250 ms; every 50 ms while the mouse is over VLC's window or a move is on its way, so
    // a layout change from a click (flip, expand) is followed at once instead of a quarter
    // second later (item 32: a short jump instead of a visible one).
    static void OnTimer(IntPtr hwnd, uint msg, UIntPtr id, uint time)
    {
        if ((DateTime.Now - lastFullTick).TotalMilliseconds >= 240 || Hot()) Tick();
    }

    static bool Hot()
    {
        if (flipMoving || dragPending) return true;
        if (lastMain == IntPtr.Zero || hidden) return false;
        POINT p;
        IntPtr dpi = DpiEnter();   // lastMainRect is in physical pixels
        try { if (!GetCursorPos(out p)) return false; }
        finally { DpiLeave(dpi); }
        RECT r = lastMainRect;
        return p.X >= r.Left && p.X < r.Right && p.Y >= r.Top && p.Y < r.Bottom;
    }

    static void OnWinEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (ev == EVENT_OBJECT_LOCATIONCHANGE && idObject != 0) return; // only whole windows
        if (ev == EVENT_SYSTEM_FOREGROUND && LogPath != null)
            Log("foreground: " + DescribeOwner(hwnd) + "; " + VlcStateText());
        Tick();
    }

    // Minimize / restore, show / hide and cloak / uncloak of VLC's root and main skin windows: only
    // logged (item 33: which window, when, where the mouse was, who had the foreground), then a
    // tick so a minimize is seen at once.
    static void OnVlcWindowEvent(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        if (idObject != 0 || hwnd == IntPtr.Zero) return;
        bool isMain = hwnd == lastMain;
        bool isRoot = !isMain && (hwnd == tbRoot || IsSkinRoot(hwnd, vlcPid));
        if (!isMain && !isRoot) return;   // flag windows, tooltips, video, menus
        if (LogPath != null)
        {
            IntPtr dpi = DpiEnter();
            string name = ev == EVENT_SYSTEM_MINIMIZESTART ? "minimized" : ev == EVENT_SYSTEM_MINIMIZEEND ? "restored" :
                          ev == EVENT_OBJECT_SHOW ? "shown" : ev == EVENT_OBJECT_HIDE ? "hidden" :
                          ev == EVENT_OBJECT_CLOAKED ? "cloaked" : ev == EVENT_OBJECT_UNCLOAKED ? "uncloaked" : "event 0x" + ev.ToString("X");
            POINT p;
            GetCursorPos(out p);
            DpiLeave(dpi);
            Log("VLC window event: " + (isRoot ? "root" : "main") + " window " + Describe(hwnd) + " " + name +
                "; mouse at " + Pt(p.X, p.Y) + (MouseButtonDown() ? " (button down)" : "") +
                ", foreground " + DescribeOwner(GetForegroundWindow()));
        }
        Tick();
    }

    // ---------------------------------------------------------------- window region
    // What is visible in VLC's main window, from the region skins2 sets on it (SetWindowRgn
    // with every pixel whose alpha is > 0, win32_graphics.cpp). The region's rectangles go
    // to DockShape.Classify, which the tests also feed with the X11 shape of the same skin.
    static ShapeInfo ReadShape(IntPtr h, int ww, int hh)
    {
        List<RECT> rects = new List<RECT>();
        IntPtr rgn = CreateRectRgn(0, 0, 0, 0);
        try
        {
            if (GetWindowRgn(h, rgn) > NULLREGION)
            {
                uint size = GetRegionData(rgn, 0, null);
                if (size >= 32)
                {
                    byte[] data = new byte[size];
                    if (GetRegionData(rgn, size, data) != 0)
                    {
                        // RGNDATAHEADER: dwSize, iType, nCount, nRgnSize, rcBound (32 bytes), then nCount RECTs
                        int n = BitConverter.ToInt32(data, 8);
                        for (int i = 0; i < n && 32 + 16 * i + 16 <= data.Length; i++)
                        {
                            RECT r;
                            r.Left = BitConverter.ToInt32(data, 32 + 16 * i);
                            r.Top = BitConverter.ToInt32(data, 32 + 16 * i + 4);
                            r.Right = BitConverter.ToInt32(data, 32 + 16 * i + 8);
                            r.Bottom = BitConverter.ToInt32(data, 32 + 16 * i + 12);
                            rects.Add(r);
                        }
                    }
                }
            }
        }
        finally { DeleteObject(rgn); }
        ShapeInfo s = DockShape.Classify(rects, ww, hh, Scale, BarHeight, lastBarAtBottom);
        if (s.DirectionKnown) lastBarAtBottom = s.BarAtBottom;
        LogShape(s, ww, hh);
        return s;
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

    // Describe plus the window's process (foreground changes in the log)
    static string DescribeOwner(IntPtr h)
    {
        if (h == IntPtr.Zero) return "none";
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        string who = "";
        if (pid == vlcPid && pid != 0) who = " (VLC)";
        else if (tbWindow != null && h == tbWindow.Handle) who = " (the helper's taskbar button)";
        else
        {
            try { using (Process p = Process.GetProcessById((int)pid)) who = " (" + p.ProcessName + ")"; }
            catch (Exception) { }
        }
        return Describe(h) + " pid " + pid + who;
    }

    // DWM cloaking (another virtual desktop, an app hidden by the shell): visible for Win32, not on screen
    static int Cloaked(IntPtr h)
    {
        int v = 0;
        try { if (DwmGetWindowAttribute(h, DWMWA_CLOAKED, out v, 4) != 0) v = 0; }
        catch (Exception) { v = 0; }
        return v;
    }

    static string WinState(IntPtr h)
    {
        if (h == IntPtr.Zero) return "unknown";
        if (!TbNative.IsWindow(h)) return Describe(h) + " gone";
        int cl = Cloaked(h);
        return "0x" + h.ToInt64().ToString("X") + " visible=" + (IsWindowVisible(h) ? 1 : 0) + " minimized=" + (TbNative.IsIconic(h) ? 1 : 0) +
               " topmost=" + (IsTopmost(h) ? 1 : 0) + (cl != 0 ? " cloaked=" + cl : "");
    }

    // VLC's root window (skins2's hidden owner of all skin windows) and main skin window (item 33)
    static string VlcStateText()
    {
        if (vlcPid == 0) return "VLC not running";
        return "VLC root " + WinState(tbRoot != IntPtr.Zero && tbRootPid == vlcPid ? tbRoot : IntPtr.Zero) + ", main " + WinState(lastMain);
    }

    static void LogShape(ShapeInfo s, int ww, int hh)
    {
        if (LogPath == null) return;
        string t = "shape: " + s.Describe() + " (window " + ww + "x" + hh + ", visible rows " + s.Top + ".." + s.Bottom +
                   ", " + s.Rects.Count + " rects)";
        if (t == lastShape) return;
        lastShape = t;
        Log(t);
    }

    // Logs text when it differs from the last text logged for this topic (state changes only).
    static void LogChange(string topic, string text)
    {
        if (LogPath == null) return;
        string old;
        if (logged.TryGetValue(topic, out old) && old == text) return;
        logged[topic] = text;
        Log(text);
    }

    static string Pt(int x, int y) { return x + "," + y; }

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
            UnhookVlc();
            vlcPid = pid;
            mainSeenAt = DateTime.MinValue;
            // per-VLC state of moving, z-order and flipping
            dragPending = false; dragFails = 0; dragMisses = 0; dragOff = false;
            lastTargetX = int.MinValue; lastTargetY = int.MinValue;
            helperTop = false; lastMainTop = -1; pinOddTicks = 0; pinFromMain = false;
            flipTries = 0;
            flipRef = false; flipMoving = false;
            lastMain = IntPtr.Zero; lastMainShape = null; hidden = false; hiddenByUser = false;
            restores.Clear(); lastRestoreAt = DateTime.MinValue;
            logged.Clear();
            if (pid != 0)
            {
                locHook = SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE, IntPtr.Zero,
                                          winEventDelegate, pid, 0, WINEVENT_OUTOFCONTEXT);
                minHook = SetWinEventHook(EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND, IntPtr.Zero,
                                          vlcEventDelegate, pid, 0, WINEVENT_OUTOFCONTEXT);
                showHook = SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_HIDE, IntPtr.Zero,
                                           vlcEventDelegate, pid, 0, WINEVENT_OUTOFCONTEXT);
                cloakHook = SetWinEventHook(EVENT_OBJECT_CLOAKED, EVENT_OBJECT_UNCLOAKED, IntPtr.Zero,
                                            vlcEventDelegate, pid, 0, WINEVENT_OUTOFCONTEXT);
            }
        }
        if (ExitWithVlc && pid == 0 && (DateTime.Now - lastVlcSeen).TotalSeconds > 5)
            PostQuitMessage(0);
    }

    static void UnhookVlc()
    {
        if (locHook != IntPtr.Zero) { UnhookWinEvent(locHook); locHook = IntPtr.Zero; }
        if (minHook != IntPtr.Zero) { UnhookWinEvent(minHook); minHook = IntPtr.Zero; }
        if (showHook != IntPtr.Zero) { UnhookWinEvent(showHook); showHook = IntPtr.Zero; }
        if (cloakHook != IntPtr.Zero) { UnhookWinEvent(cloakHook); cloakHook = IntPtr.Zero; }
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
    // A failed lookup keeps the last position (up to 30 tries, about a minute): falling back to
    // the taskbar's left end for one lookup would make the strip jump there and back.
    static void UpdateStartButton(IntPtr tray)
    {
        if ((DateTime.Now - lastStartLookup).TotalSeconds < 2) return;
        lastStartLookup = DateTime.Now;
        string why = "not found";
        try
        {
            AutomationElement root = AutomationElement.FromHandle(tray);
            AutomationElement start = root.FindFirst(TreeScope.Descendants,
                new PropertyCondition(AutomationElement.AutomationIdProperty, "StartButton"));
            if (start != null)
            {
                System.Windows.Rect r = start.Current.BoundingRectangle;
                if (!r.IsEmpty && r.Width > 0)
                {
                    if (startMisses > 0) Log("Start button: found again after " + startMisses + " failed lookups");
                    startMisses = 0;
                    if ((int)r.Left != startLeft)
                    {
                        RECT tb;
                        GetWindowRect(tray, out tb);
                        Log("Start button: left edge at x=" + (int)r.Left + (startLeft == int.MinValue ? "" : " (was " + startLeft + ")") +
                            (r.Left < tb.Left || r.Left + r.Width > tb.Right + 1 ? " WARNING: outside the taskbar " + Pt(tb.Left, tb.Top) + ".." +
                             Pt(tb.Right, tb.Bottom) + " (scaled coordinates?)" : ""));
                    }
                    startLeft = (int)r.Left;
                    return;
                }
                why = "empty rectangle";
            }
        }
        catch (Exception ex) { why = ex.GetType().Name + ": " + ex.Message; }
        startMisses++;
        if (startMisses == 1) Log("Start button: lookup failed (" + why + ")" + (startLeft != int.MinValue ? ", keeping x=" + startLeft : ""));
        if (startLeft != int.MinValue && startMisses <= 30) return;
        if (startLeft != int.MinValue) Log("Start button: lost, docking at the taskbar's left end");
        startLeft = int.MinValue;
    }

    // ---------------------------------------------------------------- the work
    static void Tick()
    {
        if (busy) return;
        busy = true;
        lastFullTick = DateTime.Now;
        IntPtr dpi = DpiEnter();   // whatever window's message brought us here: physical pixels
        try { Place(); }
        catch (Exception) { }
        finally { DpiLeave(dpi); busy = false; }
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

    static bool IsTopmost(IntPtr h) { return (GetWindowLong(h, GWL_EXSTYLE) & WS_EX_TOPMOST) != 0; }

    // A mouse button is held (physical buttons, so both: left-handed mice swap them). The user
    // may be dragging or resizing VLC: moving the window now would fight the drag.
    static bool MouseButtonDown()
    {
        return (GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0 || (GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0;
    }

    static IntPtr LParam(int x, int y) { return new IntPtr((y << 16) | (x & 0xFFFF)); }

    // A click at client point x,y, as posted mouse messages (skins2 handles them like real ones;
    // the move first, so the control under the point sees the mouse enter).
    static void PostClick(IntPtr h, int x, int y)
    {
        IntPtr pos = LParam(x, y);
        PostMessage(h, WM_MOUSEMOVE, IntPtr.Zero, pos);
        PostMessage(h, WM_LBUTTONDOWN, new IntPtr(MK_LBUTTON), pos);
        PostMessage(h, WM_LBUTTONUP, IntPtr.Zero, pos);
    }

    // ---------------------------------------------------------------- VLC's pin ("always on top")
    // skins2 pins with SetWindowPos(HWND_TOPMOST / HWND_NOTOPMOST) on every one of its top-level
    // windows (WindowManager::setOnTop -> Win32Window::toggleOnTop), the hidden 1x1 flag windows
    // (eqflag, plflag, tflag, th0, ...) as well. The helper never touches those, so their
    // WS_EX_TOPMOST is VLC's own pin state even while the helper keeps the main window topmost.
    //   1 = pinned, 0 = not pinned, -1 = no flag window found (another skin), -2 = mixed (VLC is
    //   switching right now). pinFromMain: the flag windows turned out not to follow the pin.
    static int VlcPinState(IntPtr main, out string detail)
    {
        if (pinFromMain)
        {
            detail = "from the main window's own flag";
            return IsTopmost(main) ? 1 : 0;
        }
        int total = 0, top = 0;
        uint pid = vlcPid;
        EnumWindows(delegate (IntPtr h, IntPtr l)
        {
            uint p;
            GetWindowThreadProcessId(h, out p);
            if (p != pid || h == main || ClassOf(h) != "SkinWindowClass") return true;
            if (GetWindow(h, GW_OWNER) == IntPtr.Zero) return true;   // skins2's root window
            int ex = GetWindowLong(h, GWL_EXSTYLE);
            if ((ex & (WS_EX_APPWINDOW | WS_EX_TOOLWINDOW)) != 0) return true;   // video, tooltip
            RECT r;
            if (!GetWindowRect(h, out r) || W(r) >= 8 || H(r) >= 8) return true;   // flag windows: 1x1 (0x0 until first shown)
            total++;
            if ((ex & WS_EX_TOPMOST) != 0) top++;
            return true;
        }, IntPtr.Zero);
        detail = top + " of " + total + " flag windows topmost";
        if (total == 0) return -1;
        if (top == 0) return 0;
        if (top == total) return 1;
        return -2;
    }

    // ---------------------------------------------------------------- z-order
    // The main window is topmost when VLC is pinned, and also while the strip sits in the
    // taskbar: the taskbar is topmost itself, so a strip that is not would always be behind it,
    // i.e. invisible. Unpinned and showing the full player, the helper takes back what it added,
    // so "unpin" works as in VLC. While it should be on top, the helper raises it again when the
    // taskbar came above it (a click on the taskbar raises the taskbar; item 15).
    static void FixZOrder(IntPtr main, IntPtr tray, ShapeInfo s)
    {
        string detail;
        int pin = VlcPinState(main, out detail);
        bool mainTop = IsTopmost(main);
        bool below = IsBelow(main, tray);
        if (!mainTop) helperTop = false;

        // the flag windows must change whenever VLC itself changes the main window's flag; if the
        // main window turned topmost on its own (not the helper) and the flags still say "not
        // pinned" a quarter second later, they do not show the pin: use the main window's flag
        if (pin == 0 && mainTop && lastMainTop == 0 && !helperTop) pinOddTicks = 1;
        else if (pin == 0 && mainTop && pinOddTicks > 0 && !helperTop) pinOddTicks++;
        else pinOddTicks = 0;
        if (pinOddTicks >= 2)
        {
            pinFromMain = true;
            Log("z-order: VLC made its window topmost but its flag windows do not show it; reading the pin from the main window from now on");
            pin = 1;
        }
        lastMainTop = mainTop ? 1 : 0;

        LogChange("z", "z-order: VLC pin " + (pin == 1 ? "ON" : pin == 0 ? "off" : pin == -1 ? "unknown" : "changing") +
                  " (" + detail + "), main window topmost=" + mainTop + (helperTop ? " (set by the helper)" : "") +
                  ", taskbar above VLC=" + below + ", showing " + (s.Full ? "full player" : "strip"));
        if (pin == -2) return;   // VLC is switching: look again next tick

        bool pinned = pin == 1 || (pin == -1 && mainTop);
        // without flag windows the helper cannot tell its own topmost from VLC's, so then it
        // only keeps up what VLC set (never adds)
        bool want = pinned || (!s.Full && pin != -1);
        if (want && (!mainTop || below))
        {
            string why = !mainTop ? (pinned ? "VLC is pinned but its window is not topmost" :
                                              "strip in the taskbar must be above it (VLC unpinned)") :
                                    "the taskbar came above VLC";
            Log("z-order: raise VLC to topmost: " + why);
            SetPos(main, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
            if (!pinned) helperTop = true;
            CountRaise();
            if (IsBelow(main, tray))
            {
                // item 33: the raise did not take; say what is above VLC, and insert it again
                Log("z-order: the taskbar is still above VLC after the raise; above VLC: " + WindowsAbove(main, tray) +
                    "; inserting it again (NOTOPMOST, then TOPMOST)");
                SetPos(main, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                SetPos(main, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                if (IsBelow(main, tray)) Log("z-order: WARNING: VLC stays below the taskbar; " + VlcStateText());
            }
        }
        else if (!want && mainTop && pin == 0)
        {
            Log("z-order: VLC is not pinned and shows the full player: topmost removed");
            SetPos(main, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
            helperTop = false;
        }
    }

    // The visible windows between VLC's main window and the taskbar in the z-order (nearest to VLC first, at most 6)
    static string WindowsAbove(IntPtr h, IntPtr tray)
    {
        StringBuilder sb = new StringBuilder();
        int n = 0;
        for (IntPtr p = GetWindow(h, GW_HWNDPREV); p != IntPtr.Zero && p != tray; p = GetWindow(p, GW_HWNDPREV))
        {
            if (!IsWindowVisible(p)) continue;
            if (n++ >= 6) { sb.Append(", ..."); break; }
            if (sb.Length > 0) sb.Append(", ");
            sb.Append(DescribeOwner(p));
        }
        return (sb.Length > 0 ? sb.ToString() + ", then " : "") + "the taskbar " + Describe(tray);
    }

    // More than 8 re-raises in 10 s: something keeps putting the taskbar back on top (a loop
    // that would make the strip flicker). Logged, at most every 30 s.
    static void CountRaise()
    {
        DateTime now = DateTime.Now;
        raises.Add(now);
        raises.RemoveAll(delegate (DateTime t) { return (now - t).TotalSeconds > 10; });
        if (raises.Count > 8 && (now - raiseWarnAt).TotalSeconds > 30)
        {
            raiseWarnAt = now;
            Log("z-order: WARNING: raised VLC above the taskbar " + raises.Count + " times in 10 s; the taskbar keeps coming back on top");
        }
    }

    // ---------------------------------------------------------------- moving
    // skins2 keeps its own copy of the window position (GenericWindow m_left / m_top) and never
    // learns about moves from outside (win32_loop.cpp has no WM_MOVE / WM_WINDOWPOSCHANGED).
    // Every move or resize it makes later starts from that stale copy (a layout switch or the
    // resize grip: GenericWindow::resize -> MoveWindow(m_left, m_top, ...)), so a window moved
    // with SetWindowPos jumps back to where VLC last put it, and the helper pulls it back:
    // that flashes, and a resize drag computes the width from a window that keeps jumping.
    // So the helper lets VLC move itself: a posted drag on the skin's grip (button down, mouse
    // move by the offset, button up). skins2's CtrlMove moves the window by the mouse offset in
    // client coordinates, from its own copy of the position, which it then updates. If that copy
    // was off (the window was moved from outside before), the drag lands off by as much and the
    // next one corrects it. SetWindowPos only when drags do not work (2 without effect, 4 misses).
    static void MoveTo(IntPtr main, RECT r, ShapeInfo s, int x, int y, string why)
    {
        if (dragPending)
        {
            if (r.Left == dragFromX && r.Top == dragFromY)
            {
                if ((DateTime.Now - dragAt).TotalMilliseconds < 700) return;   // VLC has not handled it yet
                dragPending = false;
                dragFails++;
                Log("move: VLC did not react to the drag (" + dragFails + " in a row)");
                if (dragFails >= 2) DragOff("VLC does not move on posted drags");
            }
            else
            {
                dragPending = false;
                if (r.Left == dragToX && r.Top == dragToY)
                {
                    dragFails = 0;
                    dragMisses = 0;
                    LogChange("drag", "move: done, VLC moved itself to " + Pt(r.Left, r.Top));
                }
                else
                {
                    dragMisses++;
                    Log("move: the drag ended at " + Pt(r.Left, r.Top) + ", not " + Pt(dragToX, dragToY) +
                        " (VLC's own idea of its position was off by " + Pt(r.Left - dragToX, r.Top - dragToY) +
                        "; " + dragMisses + " in a row)");
                    if (dragMisses >= 4) DragOff("drags keep missing (screen scaling?)");
                }
            }
        }
        if (r.Left == x && r.Top == y) return;

        int dx = x - r.Left, dy = y - r.Top;
        int gx = 0, gy = 0;
        bool canDrag = !dragOff && DockShape.GripPoint(s, W(r), H(r), out gx, out gy) &&
                       Math.Abs(gx + dx) < 30000 && Math.Abs(gy + dy) < 30000;
        if (canDrag && !DockShape.Inside(s.Rects, gx, gy))
        {
            LogChange("grip", "move: the grip point " + Pt(gx, gy) + " is not visible in this layout, moving from outside");
            canDrag = false;
        }
        Log("move (" + why + "): " + Pt(r.Left, r.Top) + " -> " + Pt(x, y) +
            (canDrag ? ", by a drag on VLC's grip at " + Pt(gx, gy) : ", SetWindowPos" + (dragOff ? " (drags off)" : "")));
        if (canDrag)
        {
            PostMessage(main, WM_MOUSEMOVE, IntPtr.Zero, LParam(gx, gy));
            PostMessage(main, WM_LBUTTONDOWN, new IntPtr(MK_LBUTTON), LParam(gx, gy));
            PostMessage(main, WM_MOUSEMOVE, new IntPtr(MK_LBUTTON), LParam(gx + dx, gy + dy));
            PostMessage(main, WM_LBUTTONUP, IntPtr.Zero, LParam(gx + dx, gy + dy));
            dragPending = true;
            dragAt = DateTime.Now;
            dragFromX = r.Left; dragFromY = r.Top;
            dragToX = x; dragToY = y;
        }
        else
            SetPos(main, IntPtr.Zero, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
    }

    static void DragOff(string why)
    {
        dragOff = true;
        Log("move: " + why + ": moving the window from outside from now on (VLC's own moves and resizes will jump back first)");
    }

    // ---------------------------------------------------------------- panels off the screen
    // The docked strip with PL / EQ open on the side away from the screen (below a bottom
    // taskbar: the "dn" layouts) would have them under the screen edge. Click the flip arrow
    // on the panel next to the strip (at most 3 tries in a row, 1.5 s apart).
    static bool FlipIfOffScreen(IntPtr main, ShapeInfo s, int ww, int hh, bool atBottom)
    {
        if (!FlipPanels || !DockShape.PanelsOffScreen(s, atBottom)) { flipTries = 0; return false; }
        if (flipTries >= 3)
        {
            LogChange("flip", "flip: the panels stay off the screen after 3 clicks on the flip arrow; flip them by hand");
            return false;
        }
        if ((DateTime.Now - lastFlipAt).TotalMilliseconds < 1500) return true;   // the last click may still be on its way
        int fx, fy;
        if (!DockShape.FlipPoint(s, ww, hh, out fx, out fy) || !DockShape.Inside(s.Rects, fx, fy)) return false;
        flipTries++;
        lastFlipAt = DateTime.Now;
        Log("flip: " + (s.Eq ? "EQ" : "playlist") + " open " + (s.BarAtBottom ? "above" : "below") + " the docked strip, off the screen;" +
            " clicking its flip arrow at " + Pt(fx, fy) + " (try " + flipTries + ")");
        PostClick(main, fx, fy);
        return true;
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
        string detail;
        if (VlcPinState(main, out detail) == 1)
        {
            pinnedPid = vlcPid;
            Log("PinOnce: VLC is pinned already (" + detail + "), no click");
            return;
        }
        ClickPin(main, r);
    }

    // The click itself, also used by the tray menu. It toggles the skin's pin button.
    static void ClickPin(IntPtr main, RECT r)
    {
        pinnedPid = vlcPid;   // StartPinned must not click again for this VLC
        ShapeInfo s = ReadShape(main, W(r), H(r));
        int x, y;
        DockShape.PinPoint(s, W(r), H(r), out x, out y);
        Log("PinOnce: click at " + Pt(x, y) + " in " + Describe(main) + " (" + s.Describe() + ", window " + W(r) + "x" + H(r) + ")");
        PostClick(main, x, y);
    }

    // ---------------------------------------------------------------- VLC hidden (item 33)
    // A click on the taskbar (an empty spot, another app's icon) left the player hidden until
    // VLC's own tray icon brought it back (second Windows test). skins2 hides its windows only by
    // minimizing its root window (or on a skin change / window.hide()); see HidePolicy. While
    // docked the strip is always visible, so a minimize that did not come from the full player's
    // minimize button is undone the way skins2 itself restores: WM_SYSCOMMAND SC_RESTORE to the
    // root window (Win32Factory::Win32Proc -> restore() -> ShowWindow(root, SW_RESTORE), the same
    // as a double-click on VLC's tray icon). Not docked: only logged.
    static void SeenVisible(IntPtr main, RECT r)
    {
        if (hidden)
        {
            Log("VLC visible again after " + (int)(DateTime.Now - hiddenAt).TotalSeconds + " s: " + VlcStateText());
            hidden = false;
            hiddenByUser = false;
            logged.Remove("hide");
        }
        if (main != lastMain) flipRef = false;
        lastMain = main;
        lastMainRect = r;
        LogChange("vlcstate", "VLC windows: " + VlcStateText());
    }

    static void KeepVisible(bool docked)
    {
        IntPtr main = lastMain;
        if (main == IntPtr.Zero) return;   // not shown yet (VLC starting)
        if (!TbNative.IsWindow(main))
        {
            // skin changed, or VLC is quitting
            Log("VLC's main window " + Describe(main) + " is gone");
            lastMain = IntPtr.Zero; lastMainShape = null; hidden = false;
            return;
        }
        IntPtr root = tbRoot != IntPtr.Zero && tbRootPid == vlcPid ? tbRoot : IntPtr.Zero;
        bool rootIconic = root != IntPtr.Zero && TbNative.IsIconic(root);
        bool mainVisible = IsWindowVisible(main);
        DateTime now = DateTime.Now;
        if (!hidden)
        {
            hidden = true;
            hiddenAt = now;
            flipMoving = false;
            POINT p;
            GetCursorPos(out p);
            hiddenByUser = rootIconic && HidePolicy.ByUser(lastMainShape, lastMainRect, p.X, p.Y);
            Log("VLC hidden: " + VlcStateText() + "; mouse at " + Pt(p.X, p.Y) + (MouseButtonDown() ? " (button down)" : "") +
                ", foreground " + DescribeOwner(GetForegroundWindow()) + "; it showed " +
                (lastMainShape != null ? lastMainShape.Describe() : "?") + " at " + Pt(lastMainRect.Left, lastMainRect.Top) +
                (hiddenByUser ? "; the mouse is on the full player, so its minimize button: left minimized" : ""));
        }
        restores.RemoveAll(delegate (DateTime t) { return (now - t).TotalSeconds > 60; });
        int act = HidePolicy.Decide(docked, mainVisible, rootIconic, hiddenByUser, MouseButtonDown(),
                                    (now - lastRestoreAt).TotalMilliseconds, restores.Count);
        switch (act)
        {
            case HidePolicy.Restore:
                RestoreVlc(root);
                break;
            case HidePolicy.KeepMinimized:
                LogChange("hide", "VLC hidden: minimized by its own button, left so (the helper's taskbar button or VLC's tray icon bring it back)");
                break;
            case HidePolicy.GiveUp:
                LogChange("hide", "VLC hidden: WARNING: restored " + restores.Count + " times in a minute and minimized again each time; not restoring any more for now");
                break;
            case HidePolicy.NotMinimized:
                LogChange("hide", "VLC hidden although its root window is not minimized (" + VlcStateText() + "); nothing in skins2 does that except a skin change: not restoring");
                break;
            case HidePolicy.Nothing:
                if (!docked) LogChange("hide", "VLC hidden while not docked: left so");
                break;
        }
    }

    static void RestoreVlc(IntPtr root)
    {
        lastRestoreAt = DateTime.Now;
        restores.Add(lastRestoreAt);
        UIntPtr res;
        IntPtr ok = TbNative.SendMessageTimeout(root, TB_WM_SYSCOMMAND, new IntPtr(TB_SC_RESTORE), IntPtr.Zero,
                                                TbNative.SMTO_ABORTIFHUNG, 500, out res);
        bool still = TbNative.IsIconic(root);
        if (still) ShowWindowAsync(root, SW_SHOWNOACTIVATE);   // VLC did not do it: restore from outside, without focus
        Log("restore: VLC was minimized while docked, not by its own button: SC_RESTORE to its root window " + Describe(root) +
            (ok == IntPtr.Zero ? " (no answer in 0.5 s)" : "") +
            (still ? "; still minimized, ShowWindow(SW_SHOWNOACTIVATE) as well" : "") +
            "; now " + VlcStateText() + ", foreground " + DescribeOwner(GetForegroundWindow()) +
            " (" + restores.Count + " in the last minute)");
    }

    // ---------------------------------------------------------------- panels flip (item 32)
    // The PL / EQ header arrow switches strip-dn <-> strip-up (full-dn <-> full-up). The layouts
    // have one size and the bar is at the top in "dn" and at the bottom in "up", so the bar
    // jumps by about the window height. Not docked (act), the helper moves the window back by
    // that much with the same posted drag as MoveTo, so the bar stays where it was; clamped so the
    // visible part stays on the work area. Docked, Place does it (the strip stays in the taskbar).
    // Never while a mouse button is down (the user drags), never on strip <-> full, never when the
    // window was moved as well, and only for 2 s after the flip.
    static void KeepBarOnFlip(IntPtr main, RECT r, ShapeInfo s, bool act)
    {
        if (MouseButtonDown())
        {
            if (flipMoving)
            {
                flipMoving = false;
                if (act) dragPending = false;   // not docked, nothing else finishes its bookkeeping
                Log("flip: a mouse button is down (the user moves VLC): no more moving after the flip");
            }
            return;   // the reference stays: the shape after a click is compared once the button is up
        }
        if (flipMoving)
        {
            string stop = !act ? "docking now" : main != flipRefMain ? "another window" :
                          s.Full != flipMoveFull ? "the layout changed" : DateTime.Now > flipMoveUntil ? "not there after 2 s" : null;
            if (stop != null)
            {
                flipMoving = false;
                if (act) dragPending = false;
                Log("flip: stopped moving VLC to " + Pt(flipToX, flipToY) + " (" + stop + "); it is at " + Pt(r.Left, r.Top));
            }
            else
            {
                MoveTo(main, r, s, flipToX, flipToY, "keep the bar in place after the panels flipped");
                if (r.Left == flipToX && r.Top == flipToY)
                {
                    flipMoving = false;
                    Log("flip: done, the bar is back where it was");
                }
                RememberShape(main, r, s);
                return;
            }
        }
        int dy;
        if (act && flipRef && main == flipRefMain && W(flipRefRect) == W(r) && H(flipRefRect) == H(r) &&
            DockShape.FlipOffset(flipRefFull, flipRefUp, flipRefBarTop, s, out dy) && dy != 0)
        {
            string what = (s.Full ? "full-" : "strip-") + (flipRefUp ? "up" : "dn") + " -> " + (s.BarAtBottom ? "up" : "dn");
            if (r.Left != flipRefRect.Left || r.Top != flipRefRect.Top)
                Log("flip: " + what + ", but the window moved as well (" + Pt(flipRefRect.Left, flipRefRect.Top) + " -> " +
                    Pt(r.Left, r.Top) + "): left where it is");
            else
            {
                MONITORINFO mi = new MONITORINFO();
                mi.cbSize = Marshal.SizeOf(typeof(MONITORINFO));
                int y = r.Top + dy, yc = y;
                if (GetMonitorInfo(MonitorFromWindow(main, 2), ref mi)) yc = DockShape.ClampVisible(y, s, mi.rcWork.Top, mi.rcWork.Bottom);
                Log("flip: " + what + ": the bar moved " + (-dy) + " px inside the window; moving VLC by " + (yc - r.Top) +
                    " px so it stays in place" + (yc != y ? " (clamped: the visible part stays on the work area, y " +
                    mi.rcWork.Top + ".." + mi.rcWork.Bottom + ")" : ""));
                if (yc != r.Top)
                {
                    flipMoving = true;
                    flipMoveFull = s.Full;
                    flipToX = r.Left; flipToY = yc;
                    flipMoveUntil = DateTime.Now.AddSeconds(2);
                    MoveTo(main, r, s, flipToX, flipToY, "keep the bar in place after the panels flipped");
                }
            }
        }
        RememberShape(main, r, s);
    }

    // the last shape with a known direction, and where the window was then
    static void RememberShape(IntPtr main, RECT r, ShapeInfo s)
    {
        if (!s.DirectionKnown || s.Rects.Count == 0) return;
        flipRef = true;
        flipRefMain = main;
        flipRefFull = s.Full;
        flipRefUp = s.BarAtBottom;
        flipRefBarTop = DockShape.BarTop(s);
        flipRefRect = r;
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
        FindVlcRoot(vlcPid);   // cached: skins2's root window, for the state log and KeepVisible

        List<IntPtr> wins = FindSkinWindows();
        IntPtr main;
        RECT rMain;
        bool docked = Dock && enabled;
        if (!FindMain(wins, out main, out rMain))
        {
            KeepVisible(docked);   // item 33: hidden or minimized?
            return;
        }
        SeenVisible(main, rMain);
        LogChange("dpi", "DPI: VLC's window " + DpiOf(main) + " dpi, " + W(rMain) + "x" + H(rMain) + " px; helper thread " + DpiAwareness());
        if (StartPinned) PinOnce(main, rMain);
        if (!docked)
        {
            // not docked (-NoDock, or Ctrl+Alt+Shift+V): only keep the bar in place when the panels flip
            ShapeInfo su = ReadShape(main, W(rMain), H(rMain));
            lastMainShape = su;
            KeepBarOnFlip(main, rMain, su, true);
            return;
        }

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
                Log("fullscreen mode: enter, foreground " + Describe(fg) + " (VLC topmost=" + IsTopmost(main) + ")");
                foreach (IntPtr h in wins)
                {
                    SetPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                    SetPos(h, fg, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER);
                }
                fullscreenMode = true;
            }
            return;
        }
        if (fullscreenMode)
        {
            fullscreenMode = false;
            Log("fullscreen mode: leave (z-order is set again from VLC's pin)");
        }

        // horizontal anchor: right-aligned to the left of Start (or of the tray),
        // or left-aligned at the left end of the taskbar
        bool alignRight = false;
        int anchor = tb.Left + Gap;
        string anchorWhy = "taskbar left end";
        if (DockTo == "right")
        {
            IntPtr notify = FindWindowEx(tray, IntPtr.Zero, "TrayNotifyWnd", null);
            RECT rn;
            anchor = ((notify != IntPtr.Zero && GetWindowRect(notify, out rn)) ? rn.Left : tb.Right) - Gap;
            alignRight = true;
            anchorWhy = "right edge at the tray";
        }
        else if (DockTo == "start")
        {
            UpdateStartButton(tray);
            if (startLeft != int.MinValue) { anchor = startLeft - Gap; alignRight = true; anchorWhy = "right edge at Start"; }
        }

        // vertical placement: the strip inside the taskbar (panels stick out above or
        // below it); the full player's visible part right next to the taskbar
        int ww = W(rMain), hh = H(rMain);
        ShapeInfo s = ReadShape(main, ww, hh);
        lastMainShape = s;
        // docked, the placement below keeps the strip in the taskbar after a flip (and the full
        // player's visible part above it); this only keeps the flip reference up to date
        KeepBarOnFlip(main, rMain, s, false);
        int mainY = DockShape.TargetY(s, hh, tb.Top, tb.Bottom, atBottom, OffsetY);
        int mainX = XFor(alignRight, anchor, ww, tb.Left + 2, mon.Right);

        // z-order also while a button is held: a click on the taskbar raises it at once
        FixZOrder(main, tray, s);

        // the user may be dragging or resizing VLC: wait until the button is released. With
        // DockTo=start the right edge then goes back to Start, so a wider strip grows to the left.
        bool off = rMain.Left != mainX || rMain.Top != mainY;
        if (MouseButtonDown())
        {
            if (off) LogChange("mouse", "mouse button down: VLC stays at " + Pt(rMain.Left, rMain.Top) + " " + ww + "x" + hh +
                               " until it is released (dock position " + Pt(mainX, mainY) + ")");
            return;
        }
        string held;
        if (logged.TryGetValue("mouse", out held))
        {
            logged.Remove("mouse");
            Log("mouse button released: docking again");
        }

        if (FlipIfOffScreen(main, s, ww, hh, atBottom)) return;   // the layout changes: place it next tick

        if (off)
        {
            string why = (s.Full ? "full player " + (atBottom ? "above" : "below") + " the taskbar" :
                                   "strip in the taskbar, bar at the " + (s.BarAtBottom ? "bottom" : "top")) + ", " + anchorWhy;
            why += (mainX != lastTargetX || mainY != lastTargetY) ? "; dock position changed" : "; window was moved away from it";
            MoveTo(main, rMain, s, mainX, mainY, why);
        }
        else if (dragPending) MoveTo(main, rMain, s, mainX, mainY, "");   // only finishes the drag's bookkeeping
        lastTargetX = mainX; lastTargetY = mainY;
    }
}

// ---------------------------------------------------------------------------------------
// What VLC's main window shows, read from its window region (VlcDock.ReadShape). Pure code,
// no Win32: the tests feed it the X11 shapes of the real skin under Xvfb.
//
// The window is 436 logical px tall in every layout (full player 122 + EQ 116 + playlist 198),
// the strip is BarHeight tall (24, 36 for the taskbar build). The visible height alone tells
// strip from full player and which panels are open:
//   strip  bar, bar + EQ, bar + PL, bar + EQ + PL
//   full   122, 122 + EQ, 122 + PL, 122 + EQ + PL
// and the visible part touches the window's top ("dn" layouts, bar at the top) or bottom
// ("up", bar at the bottom); only the full player with both panels fills it all.
// This does not depend on how the corners are drawn. It is ambiguous only for a strip height
// that makes two sums equal (40: strip + PL = full + EQ); then, and for heights that fit
// nothing, the old test decides: a pixel one bar height from the bar's outer edge is visible
// in the full player and transparent at the rounded corner of a panel next to the strip.
// A height that fits no strip of the configured height but a strip of 12 to 80 px is taken
// as such a strip (wrong skin file in the settings; logged). The scale comes from the window
// height when it does not match the configured one.
// ---------------------------------------------------------------------------------------
public sealed class ShapeInfo
{
    public List<VlcDock.RECT> Rects = new List<VlcDock.RECT>();   // visible rectangles, window coordinates
    public int Top, Bottom;          // visible rows
    public bool Full;                // full player (else the strip)
    public bool BarAtBottom;         // "up" layouts: the panels open above the bar
    public bool DirectionKnown = true;   // false: the full player with both panels (fills the window)
    public bool Eq, Pl;              // panels open (as far as the height tells)
    public int Bar;                  // strip height in px (configured, or read from the shape)
    public double Scale;             // skin scale used
    public string How = "";          // how it was decided (log)

    public string Describe()
    {
        return (Full ? "full" : "strip") + "-" + (BarAtBottom ? "up" : "dn") + (DirectionKnown ? "" : "?") +
               (Eq ? " +EQ" : "") + (Pl ? " +PL" : "") + " bar=" + Bar + "px scale=" + Scale + " [" + How + "]";
    }
}

public static class DockShape
{
    public const int FullH = 122, EqH = 116, PlH = 198, WinH = 436;
    const int Tol = 2;   // px: every part is rounded on its own at 125 % / 150 %

    static int Px(double v, double scale) { return (int)Math.Round(v * scale); }

    public static bool Inside(List<VlcDock.RECT> rects, int x, int y)
    {
        foreach (VlcDock.RECT r in rects)
            if (x >= r.Left && x < r.Right && y >= r.Top && y < r.Bottom) return true;
        return false;
    }

    // which of base, base+EQ, base+PL, base+EQ+PL the height h is; false if none
    static bool Match(int h, int b, int e, int l, out bool eq, out bool pl)
    {
        eq = false; pl = false;
        if (Math.Abs(h - b) <= Tol) return true;
        if (Math.Abs(h - b - e) <= Tol) { eq = true; return true; }
        if (Math.Abs(h - b - l) <= Tol) { pl = true; return true; }
        if (Math.Abs(h - b - e - l) <= Tol) { eq = true; pl = true; return true; }
        return false;
    }

    public static ShapeInfo Classify(List<VlcDock.RECT> rects, int ww, int hh, double scale, double barHeight, bool lastBarAtBottom)
    {
        ShapeInfo s = new ShapeInfo();
        s.Scale = scale;
        if (Math.Abs(hh - Px(WinH, scale)) > Tol && hh > 100)
        {
            s.Scale = Math.Round(hh * 100.0 / WinH) / 100;   // window height says another scale than the settings
            s.How = "scale from window height; ";
        }
        double sc = s.Scale;
        s.Bar = Px(barHeight, sc);
        if (rects == null || rects.Count == 0)
        {
            // no region: the whole window shows (not this skin, or not drawn yet); as before
            s.Top = 0; s.Bottom = hh; s.BarAtBottom = true; s.Full = false;
            s.How += "no region";
            return s;
        }
        s.Rects = rects;
        int top = int.MaxValue, bottom = int.MinValue;
        foreach (VlcDock.RECT r in rects) { top = Math.Min(top, r.Top); bottom = Math.Max(bottom, r.Bottom); }
        s.Top = top; s.Bottom = bottom;
        int h = bottom - top;

        // direction: the visible part touches one end of the window
        bool atTop = top <= Tol - 1, atEnd = bottom >= hh - Tol + 1;
        if (atTop && !atEnd) s.BarAtBottom = false;
        else if (atEnd && !atTop) s.BarAtBottom = true;
        else { s.BarAtBottom = lastBarAtBottom; s.DirectionKnown = false; }

        int f = Px(FullH, sc), e = Px(EqH, sc), l = Px(PlH, sc);
        bool feq, fpl, seq, spl;
        bool full = Match(h, f, e, l, out feq, out fpl);
        bool strip = Match(h, s.Bar, e, l, out seq, out spl);
        if (full && !strip) { s.Full = true; s.Eq = feq; s.Pl = fpl; s.How += "height fits the full player"; }
        else if (strip && !full) { s.Eq = seq; s.Pl = spl; s.How += "height fits the strip"; }
        else if (!full && !strip && InferBar(h, sc, e, l, s)) s.Full = false;
        else
        {
            // ambiguous (or nothing fits): the pixel test at the bar's corner
            int y = s.BarAtBottom ? hh - s.Bar : s.Bar;
            s.Full = Inside(rects, 0, y);
            if (s.Full) { s.Eq = feq; s.Pl = fpl; } else { s.Eq = seq; s.Pl = spl; }
            s.How += (full ? "height fits both, " : "height fits nothing, ") + "corner pixel " + 0 + "," + y + (s.Full ? " visible" : " transparent");
        }

        // the full player with both panels fills the window, so the ends do not tell the
        // direction; the seam between the full player and the panel next to it does: its rounded
        // corners make the left edge transparent there (rows f-1 / f in "dn", hh-f-1 / hh-f in "up")
        if (!s.DirectionKnown && s.Full)
        {
            bool seamTop = Seam(rects, f), seamBottom = Seam(rects, hh - f);
            if (seamTop != seamBottom)
            {
                s.BarAtBottom = seamBottom;
                s.DirectionKnown = true;
                s.How += "; direction from the seam at row " + (seamBottom ? hh - f : f);
            }
        }
        return s;
    }

    // the left edge is transparent in one of the rows y-2 .. y+1 (rounded corners of two parts meet)
    static bool Seam(List<VlcDock.RECT> rects, int y)
    {
        for (int i = y - 2; i <= y + 1; i++)
            if (!Inside(rects, 0, i)) return true;
        return false;
    }

    // ---- item 32: the panels flip (strip-dn <-> strip-up, full-dn <-> full-up)
    // All four layouts have one size; the bar is at the top of the window in "dn" and at the
    // bottom in "up", so a flip moves the bar by about (window height - bar height). True when
    // cur is a flip of the shape seen before (prevFull, prevBarAtBottom, prevBarTop = its BarTop):
    // same kind, other side. dy is how far the window must move so the bar stays where it was.
    public static bool FlipOffset(bool prevFull, bool prevBarAtBottom, int prevBarTop, ShapeInfo cur, out int dy)
    {
        dy = 0;
        if (cur == null || !cur.DirectionKnown || cur.Full != prevFull || cur.BarAtBottom == prevBarAtBottom) return false;
        dy = prevBarTop - BarTop(cur);
        return true;
    }

    // Window row of the bar's top edge (strip or full player), from the visible rows: the
    // visible part starts with the bar in "dn" and ends with it in "up" (at 125 % the full
    // player ends a row above the window's bottom, so not hh - bar).
    public static int BarTop(ShapeInfo s)
    {
        int bar = s.Full ? Px(FullH, s.Scale) : s.Bar;
        return s.BarAtBottom ? s.Bottom - bar : s.Top;
    }

    // Window y nearest to y that keeps the visible part (rows s.Top .. s.Bottom) inside the work
    // area workTop .. workBottom; if it is taller than the work area, its top wins.
    public static int ClampVisible(int y, ShapeInfo s, int workTop, int workBottom)
    {
        if (y + s.Bottom > workBottom) y = workBottom - s.Bottom;
        if (y + s.Top < workTop) y = workTop - s.Top;
        return y;
    }

    // a strip of another height (the settings name another skin file than VLC uses)
    static bool InferBar(int h, double sc, int e, int l, ShapeInfo s)
    {
        int[] add = { 0, e, l, e + l };
        for (int i = 0; i < add.Length; i++)
        {
            int b = h - add[i];
            if (b >= Px(12, sc) && b <= Px(80, sc))
            {
                s.Bar = b;
                s.Eq = i == 1 || i == 3;
                s.Pl = i == 2 || i == 3;
                s.How += "height fits a strip of " + b + " px, not the configured height";
                return true;
            }
        }
        return false;
    }

    // Window y that docks it: the strip centred in the taskbar, or the visible part of the full
    // player just above (bottom taskbar) or below (top taskbar) the taskbar.
    public static int TargetY(ShapeInfo s, int hh, int tbTop, int tbBottom, bool atBottom, int offsetY)
    {
        if (!s.Full)
        {
            int barTop = tbTop + (tbBottom - tbTop - s.Bar) / 2 + offsetY;
            return s.BarAtBottom ? barTop - (hh - s.Bar) : barTop;
        }
        return atBottom ? tbTop - s.Bottom : tbBottom - s.Top;
    }

    // Strip with panels open on the side away from the screen: below a bottom taskbar
    // ("dn"), above a top one ("up").
    public static bool PanelsOffScreen(ShapeInfo s, bool atBottom)
    {
        return !s.Full && (s.Eq || s.Pl) && s.DirectionKnown && (atBottom ? !s.BarAtBottom : s.BarAtBottom);
    }

    // Client point on the skin's move grip (the dots at the left end; build_skin.py: the
    // strip's and the full player's background, action "move", 14 px left cap, the first
    // control starts at x 16).
    public static bool GripPoint(ShapeInfo s, int ww, int hh, out int x, out int y)
    {
        double sc = s.Scale;
        x = Px(6, sc);
        if (s.Full) y = (s.BarAtBottom ? hh - Px(FullH, sc) : 0) + Px(10, sc);
        else y = (s.BarAtBottom ? hh - s.Bar : 0) + s.Bar / 2;
        return ww > Px(16, sc);
    }

    // Client point of the flip arrow on the panel next to the strip: EQ (68 px from the right
    // edge) when it is open, else the playlist (26 px); 18 x 12 buttons 4 px below the panel top.
    public static bool FlipPoint(ShapeInfo s, int ww, int hh, out int x, out int y)
    {
        double sc = s.Scale;
        x = y = 0;
        if (s.Full || !(s.Eq || s.Pl)) return false;
        x = ww - Px(s.Eq ? 68 : 26, sc) + Px(9, sc);
        int panelTop = s.BarAtBottom ? hh - s.Bar - Px(s.Eq ? EqH : PlH, sc) : s.Bar;
        y = panelTop + Px(10, sc);
        return true;
    }

    // Client point of the pin button: full player 82 px from the right edge, 5 px from its top;
    // strip 34 px from the right edge, centred in the bar.
    public static void PinPoint(ShapeInfo s, int ww, int hh, out int x, out int y)
    {
        double sc = s.Scale;
        if (s.Full)
        {
            x = ww - Px(82, sc) + Px(9, sc);
            y = (s.BarAtBottom ? hh - Px(FullH, sc) : 0) + Px(11, sc);
        }
        else
        {
            x = ww - Px(34, sc) + Px(11, sc);
            y = (s.BarAtBottom ? hh - s.Bar : 0) + s.Bar / 2;
        }
    }
}

// ---------------------------------------------------------------------------------------
// Item 33: what to do when VLC's main skin window is not visible (pure code, tested with Mono).
// skins2 hides its windows only by minimizing its hidden root window (vlc.minimize(), or
// WM_SYSCOMMAND SC_MINIMIZE to the root; Windows then hides every window the root owns), by a
// skin change, or by a skin's window.hide(). The tray icon brings them back with SW_RESTORE on
// the root (double-click; a single click only calls SetForegroundWindow on each window).
// While docked, the strip is always visible (agreed with the user), so a minimize the user did
// not make with the full player's own minimize button is undone; undocked, never.
// ---------------------------------------------------------------------------------------
public static class HidePolicy
{
    public const int Nothing = 0;        // visible, or not docked: not the helper's business
    public const int Restore = 1;        // SC_RESTORE to skins2's root window
    public const int KeepMinimized = 2;  // the user minimized it with the full player's button
    public const int Wait = 3;           // a mouse button is held, or a restore was just sent
    public const int GiveUp = 4;         // restored too often in the last minute: something keeps minimizing it
    public const int NotMinimized = 5;   // hidden although the root is not minimized: only logged

    public const int MaxRestoresPerMinute = 6;

    public static int Decide(bool docked, bool mainVisible, bool rootIconic, bool byUser, bool mouseDown,
                             double msSinceRestore, int restoresLastMinute)
    {
        if (mainVisible || !docked) return Nothing;
        if (!rootIconic) return NotMinimized;
        if (byUser) return KeepMinimized;
        if (mouseDown || msSinceRestore < 1000) return Wait;
        if (restoresLastMinute >= MaxRestoresPerMinute) return GiveUp;
        return Restore;
    }

    // The minimize came from the full player's minimize button: it showed the full player and
    // the mouse is over its visible part (the button acts on release). A click on the taskbar,
    // another app or the desktop has the mouse elsewhere; the strip has no minimize button.
    public static bool ByUser(ShapeInfo lastShape, VlcDock.RECT lastRect, int cursorX, int cursorY)
    {
        if (lastShape == null || !lastShape.Full) return false;
        return DockShape.Inside(lastShape.Rects, cursorX - lastRect.Left, cursorY - lastRect.Top);
    }

    public static string Name(int action)
    {
        switch (action)
        {
            case Nothing: return "nothing";
            case Restore: return "restore";
            case KeepMinimized: return "keep minimized";
            case Wait: return "wait";
            case GiveUp: return "give up";
            case NotMinimized: return "hidden, not minimized";
        }
        return "?";
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

// =======================================================================================
// Own taskbar button (BACKLOG item 19): prev / play-pause / next when hovering it, the track
// progress in the button, a hover preview with title / artist / time, VLC's icon.
//
// Why a button of our own: skins2's taskbar button belongs to its hidden 0 x 0 root window
// inside vlc.exe, and Windows sends thumbnail-button clicks only to the window that owns the
// button. So the helper shows a button for an invisible window of its own (and VLC's is
// hidden with skins2-taskbar=0, which Setup / the launcher set when this is on).
//
//   the window   WS_POPUP + WS_EX_APPWINDOW, 192 x 108 at -32000,-32000, layered with alpha 0
//                and click-through: it has a taskbar button but is never seen. DWM is told to
//                use our bitmap for its thumbnail (DWMWA_FORCE_ICONIC_REPRESENTATION) and not
//                to peek at it (DWMWA_DISALLOW_PEEK: there is nothing to peek at).
//   app id       PKEY_AppUserModel_ID = the id Windows derives for vlc.exe itself (VLC 3 sets
//                none, nor does its installer on the shortcuts), so the button groups with a
//                pinned VLC; plus RelaunchCommand / DisplayName / Icon = vlc.exe, so pinning
//                this button pins VLC and not PowerShell. See TaskbarAppIdFor.
//   click        the shell activates our window; we hand the activation to VLC's main skin
//                window (restoring VLC first if it was minimized) and drop to the bottom.
//   close        "Close window" (taskbar menu, thumbnail X) = quit VLC: WM_SYSCOMMAND SC_CLOSE
//                to skins2's root window, which calls libvlc_Quit (win32_factory.cpp), the same
//                as VLC's own taskbar button. WM_CLOSE would not do: skins2 does not handle it
//                and DefWindowProc would destroy the window under VLC's feet.
//
// Lifecycle: TaskbarStart() / TaskbarStop() from Run(); a 250 ms timer creates the window
// while VLC runs with the skin (its root window exists) and the web interface is configured,
// and destroys it when VLC is gone. Everything runs on the helper's UI thread.
// =======================================================================================
public static partial class VlcDock
{
    // ---- settings (set from PowerShell before Run)
    public static bool TaskbarButton = false;    // own taskbar button with hover controls (needs RemotePort)
    public static string TaskbarAppId = "auto";  // "auto" = the id Windows derives from vlc.exe's path; "" = none; else this id

    // ---- state (UI thread only)
    static TimerProc tbTimerDelegate = OnTaskbarTimer;   // keep alive (GC)
    static UIntPtr tbTimer = UIntPtr.Zero;
    static TaskbarWindow tbWindow;
    static uint tbPid;                          // VLC process tbWindow belongs to
    static IntPtr tbRoot = IntPtr.Zero;         // skins2's hidden root window ...
    static uint tbRootPid;                      // ... of this process
    static IntPtr tbRootTabRemoved = IntPtr.Zero;   // root window whose own taskbar button we removed
    static DateTime tbRetryAt = DateTime.MinValue;
    static ITaskbarList3 tbList;

    const uint TB_WM_SYSCOMMAND = 0x112;
    const int TB_SC_CLOSE = 0xF060, TB_SC_RESTORE = 0xF120;

    static void TaskbarStart()
    {
        if (!TaskbarButton) return;
        if (!Remote.Configured)
        {
            Log("taskbar button: off (VLC's web interface is not set up; run Setup)");
            return;
        }
        tbTimer = SetTimer(IntPtr.Zero, UIntPtr.Zero, 250, tbTimerDelegate);
        Log("taskbar button: on (app id setting \"" + TaskbarAppId + "\")");
    }

    static void TaskbarStop()
    {
        if (tbTimer != UIntPtr.Zero) { TbNative.KillTimer(IntPtr.Zero, tbTimer); tbTimer = UIntPtr.Zero; }
        TaskbarDestroy();
        if (tbList != null)
        {
            try { Marshal.ReleaseComObject(tbList); }
            catch (Exception) { }
            tbList = null;
        }
    }

    static void OnTaskbarTimer(IntPtr hwnd, uint msg, UIntPtr id, uint time)
    {
        IntPtr dpi = DpiEnter();
        try { TaskbarUpdate(); }
        catch (Exception ex) { Log("taskbar button: " + ex.GetType().Name + ": " + ex.Message); }
        finally { DpiLeave(dpi); }
    }

    static void TaskbarUpdate()
    {
        uint pid = vlcPid;
        IntPtr root = pid != 0 ? FindVlcRoot(pid) : IntPtr.Zero;
        if (tbWindow != null && (root == IntPtr.Zero || pid != tbPid)) TaskbarDestroy();
        if (root == IntPtr.Zero) return;
        if (tbWindow == null)
        {
            if (DateTime.Now < tbRetryAt) return;
            if (!TaskbarCreate(pid)) { tbRetryAt = DateTime.Now.AddSeconds(10); return; }
        }
        HideVlcOwnButton(root);
        tbWindow.Refresh(Remote.Status, DateTime.Now);
    }

    static bool TaskbarCreate(uint pid)
    {
        string exe = TbNative.ProcessPath(pid);
        string appId = TaskbarAppIdFor(exe);
        TaskbarWindow w = new TaskbarWindow();
        try
        {
            w.Create(exe, appId);
        }
        catch (Exception ex)
        {
            Log("taskbar button: could not create the window: " + ex.GetType().Name + ": " + ex.Message);
            w.Destroy();
            return false;
        }
        tbWindow = w;
        tbPid = pid;
        Log("taskbar button: created " + Describe(w.Handle) + " for VLC pid " + pid + ", exe \"" + (exe ?? "?") +
            "\", app id \"" + (appId ?? "(none)") + "\"");
        return true;
    }

    static void TaskbarDestroy()
    {
        if (tbWindow == null) return;
        try { tbWindow.Destroy(); }
        catch (Exception) { }
        tbWindow = null;
        tbPid = 0;
        tbRootTabRemoved = IntPtr.Zero;
        Log("taskbar button: removed");
    }

    // skins2's root window: class SkinWindowClass, no owner, title "VLC Media Player" (its other
    // windows are titled "VlC Media Player"; win32_factory.cpp / win32_window.cpp). Normally the
    // owner of the main skin window; while VLC is minimized its windows are hidden, so then by title.
    static IntPtr FindVlcRoot(uint pid)
    {
        if (tbRoot != IntPtr.Zero && tbRootPid == pid && TbNative.IsWindow(tbRoot)) return tbRoot;
        IntPtr found = IntPtr.Zero;
        IntPtr main;
        RECT r;
        if (FindMain(FindSkinWindows(), out main, out r))
        {
            IntPtr owner = TbNative.GetWindow(main, TbNative.GW_OWNER);
            if (IsSkinRoot(owner, pid)) found = owner;
        }
        if (found == IntPtr.Zero)
        {
            TbNative.EnumWindows(delegate (IntPtr h, IntPtr l)
            {
                if (!IsSkinRoot(h, pid)) return true;
                found = h;
                return false;
            }, IntPtr.Zero);
        }
        if (found != tbRoot && found != IntPtr.Zero) Log("VLC's root window (skins2): " + Describe(found));
        tbRoot = found;
        tbRootPid = pid;
        return found;
    }

    static bool IsSkinRoot(IntPtr h, uint pid)
    {
        if (h == IntPtr.Zero) return false;
        uint p;
        TbNative.GetWindowThreadProcessId(h, out p);
        if (p != pid || ClassOf(h) != "SkinWindowClass") return false;
        if (TbNative.GetWindow(h, TbNative.GW_OWNER) != IntPtr.Zero) return false;
        StringBuilder sb = new StringBuilder(32);
        TbNative.GetWindowText(h, sb, 32);
        return sb.ToString() == "VLC Media Player";
    }

    // skins2-taskbar=1 (Setup not run again): VLC's own button would sit next to ours, in the
    // same group. Take it off the taskbar (once per root window).
    static void HideVlcOwnButton(IntPtr root)
    {
        if (root == tbRootTabRemoved || tbList == null || tbWindow == null || !tbWindow.Ready) return;
        tbRootTabRemoved = root;
        if ((TbNative.GetWindowLong(root, TbNative.GWL_EXSTYLE) & TbNative.WS_EX_APPWINDOW) == 0) return;
        int hr = tbList.DeleteTab(root);
        Log("taskbar button: VLC shows its own taskbar button (skins2-taskbar=1; run Setup), removed it: hr=0x" +
            hr.ToString("X8"));
    }

    // ---- what the button does
    static void TaskbarClicked(int id)
    {
        string cmd = id == 1 ? "pl_previous" : id == 2 ? "pl_pause" : id == 3 ? "pl_next" : null;
        if (cmd == null) return;
        Log("taskbar button: " + cmd);
        Remote.SendAsync(cmd);
    }

    // Our window was activated (taskbar click, its thumbnail, Alt+Tab): we are the foreground
    // process now, so we may hand the foreground to VLC.
    static void TaskbarActivated()
    {
        IntPtr root = tbRoot;
        uint pid = vlcPid;
        if (root == IntPtr.Zero || pid == 0) return;
        TbNative.AllowSetForegroundWindow(pid);
        if (TbNative.IsIconic(root))
        {
            // VLC minimized (skin's minimize button = ShowWindow(root, SW_MINIMIZE)): restore it
            // through skins2 itself (its root window handles SC_RESTORE), and wait for it.
            UIntPtr res;
            TbNative.SendMessageTimeout(root, TB_WM_SYSCOMMAND, new IntPtr(TB_SC_RESTORE), IntPtr.Zero,
                                        TbNative.SMTO_ABORTIFHUNG, 1000, out res);
            Log("taskbar button: VLC was minimized, restored");
        }
        IntPtr main;
        RECT r;
        if (FindMain(FindSkinWindows(), out main, out r))
        {
            bool ok = TbNative.SetForegroundWindow(main);
            Log("taskbar button: activated, VLC to the front " + Describe(main) + (ok ? "" : " FAILED"));
        }
        else Log("taskbar button: activated, but VLC's main window is not visible");
        if (tbWindow != null)
            TbNative.SetWindowPos(tbWindow.Handle, TbNative.HWND_BOTTOM, 0, 0, 0, 0,
                                  TbNative.SWP_NOMOVE | TbNative.SWP_NOSIZE | TbNative.SWP_NOACTIVATE);
    }

    static void TaskbarClose()
    {
        IntPtr root = tbRoot;
        if (root == IntPtr.Zero) return;
        Log("taskbar button: close, VLC quits (SC_CLOSE to " + Describe(root) + ")");
        TbNative.PostMessage(root, TB_WM_SYSCOMMAND, new IntPtr(TB_SC_CLOSE), IntPtr.Zero);
    }

    // ---- app id
    // Windows groups taskbar buttons by AppUserModelID. VLC 3 never sets one (nothing in
    // bin/winvlc.c or modules/gui; the installer's shortcuts have none), so Windows derives
    // it from the exe path, for the running vlc.exe and for a pinned VLC shortcut alike: the
    // path with a known folder replaced by its GUID, e.g.
    //   {6D809377-6AF0-444B-8957-A3773F02200E}\VideoLAN\VLC\vlc.exe   (C:\Program Files)
    // which is also the AppID that Get-StartApps lists for VLC. Using that id puts our button
    // into VLC's group (pinned icon, jump list). If it is not the right one, the button simply
    // stands on its own; $TaskbarAppId in the ps1 can then set the right id by hand.
    static string TaskbarAppIdFor(string exe)
    {
        string id = TaskbarAppId ?? "auto";
        if (id != "auto") return id.Length > 0 ? id : null;
        if (exe == null) return null;
        string derived = VlcTaskbarView.ImplicitAppId(exe, KnownFolderRoots());
        return derived.Length <= 128 ? derived : "VideoLAN.VLC.TitlebarHelper";   // AUMIDs are at most 128 characters
    }

    static List<KeyValuePair<string, string>> KnownFolderRoots()
    {
        List<KeyValuePair<string, string>> l = new List<KeyValuePair<string, string>>();
        string pf64 = Environment.GetEnvironmentVariable("ProgramW6432");   // also set in 32-bit processes on 64-bit Windows
        string pf86 = Environment.GetEnvironmentVariable("ProgramFiles(x86)");
        if (string.IsNullOrEmpty(pf64)) pf86 = Environment.GetEnvironmentVariable("ProgramFiles");   // 32-bit Windows (unverified)
        AddRoot(l, pf64, "{6D809377-6AF0-444B-8957-A3773F02200E}");                    // FOLDERID_ProgramFilesX64
        AddRoot(l, pf86, "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}");                    // FOLDERID_ProgramFilesX86
        AddRoot(l, Environment.SystemDirectory, "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}"); // FOLDERID_System
        AddRoot(l, Environment.GetEnvironmentVariable("windir"), "{F38BF404-1D43-42F2-9305-67DE0B28FC23}"); // FOLDERID_Windows
        AddRoot(l, Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}");                              // FOLDERID_LocalAppData
        AddRoot(l, Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}");                              // FOLDERID_RoamingAppData
        AddRoot(l, Environment.GetEnvironmentVariable("USERPROFILE"), "{5E6C858F-0E22-4760-9AFE-EA3317B67173}"); // FOLDERID_Profile
        return l;
    }

    static void AddRoot(List<KeyValuePair<string, string>> l, string path, string guid)
    {
        if (!string.IsNullOrEmpty(path)) l.Add(new KeyValuePair<string, string>(path, guid));
    }

    // ---------------------------------------------------------------------------------------
    // The invisible window that owns the button. A NativeWindow: its messages arrive through
    // the helper's own GetMessage loop (no Application.Run).
    sealed class TaskbarWindow : NativeWindow
    {
        static readonly uint WM_TASKBARBUTTONCREATED = TbNative.RegisterWindowMessage("TaskbarButtonCreated");
        const int WM_ACTIVATE = 0x0006, WM_CLOSE = 0x0010, WM_SETTINGCHANGE = 0x001A, WM_COMMAND = 0x0111,
                  WM_SYSCOMMAND = 0x0112, WM_DWMSENDICONICTHUMBNAIL = 0x0323, WM_FORWARD = 0x8000 + 19;   // WM_APP + 19
        const int SC_SIZE = 0xF000, SC_MOVE = 0xF010, SC_MINIMIZE = 0xF020, SC_MAXIMIZE = 0xF030, SC_CLOSE = 0xF060;
        const int THBN_CLICKED = 0x1800;

        IntPtr bigIcon = IntPtr.Zero, smallIcon = IntPtr.Zero;
        IntPtr[] glyphs;                // prev, play, pause, next (VlcTaskbarView.Glyph*)
        bool lightTheme;
        bool ready;                     // TaskbarButtonCreated seen, buttons added
        VlcStatus shown = VlcStatus.Offline;
        string title;
        int buttonState = -1;           // what the thumbnail buttons show (enabled / playing / theme bits)
        int progressFlag = -1;
        long progressPermille = -1;
        string thumbKey;

        public bool Ready { get { return ready; } }

        public void Create(string exe, string appId)
        {
            CreateParams cp = new CreateParams();
            cp.Caption = VlcTaskbarView.DefaultTitle;
            cp.Style = unchecked((int)(TbNative.WS_POPUP | TbNative.WS_SYSMENU | TbNative.WS_MINIMIZEBOX));
            cp.ExStyle = TbNative.WS_EX_APPWINDOW | TbNative.WS_EX_LAYERED | TbNative.WS_EX_TRANSPARENT;
            cp.X = -32000; cp.Y = -32000;
            cp.Width = 192; cp.Height = 108;   // 16:9, so DWM offers a card-shaped thumbnail
            CreateHandle(cp);                  // throws Win32Exception on failure
            IntPtr h = Handle;
            TbNative.SetLayeredWindowAttributes(h, 0, 0, TbNative.LWA_ALPHA);   // fully transparent

            if (exe != null && TbNative.ExtractIconEx(exe, 0, out bigIcon, out smallIcon, 1) > 0)
            {
                if (bigIcon != IntPtr.Zero) TbNative.SendMessage(h, TbNative.WM_SETICON, new IntPtr(1), bigIcon);     // ICON_BIG
                if (smallIcon != IntPtr.Zero) TbNative.SendMessage(h, TbNative.WM_SETICON, IntPtr.Zero, smallIcon); // ICON_SMALL
            }
            SetAppProperties(h, exe, appId);

            int on = 1;
            TbNative.DwmSetWindowAttribute(h, TbNative.DWMWA_FORCE_ICONIC_REPRESENTATION, ref on, 4);
            TbNative.DwmSetWindowAttribute(h, TbNative.DWMWA_HAS_ICONIC_BITMAP, ref on, 4);
            TbNative.DwmSetWindowAttribute(h, TbNative.DWMWA_DISALLOW_PEEK, ref on, 4);
            // only matters if the helper runs elevated: let Explorer's messages through
            TbNative.ChangeWindowMessageFilterEx(h, WM_TASKBARBUTTONCREATED, TbNative.MSGFLT_ALLOW, IntPtr.Zero);
            TbNative.ChangeWindowMessageFilterEx(h, (uint)WM_COMMAND, TbNative.MSGFLT_ALLOW, IntPtr.Zero);

            lightTheme = VlcTaskbarView.SystemUsesLightTheme();
            glyphs = MakeGlyphs(lightTheme);
            TbNative.ShowWindow(h, TbNative.SW_SHOWNOACTIVATE);   // now the taskbar button appears
            // bottom of the z-order: when another window closes, Windows activates the next
            // one in z-order, and that should not be ours (it would pull VLC forward)
            TbNative.SetWindowPos(h, TbNative.HWND_BOTTOM, 0, 0, 0, 0,
                                  TbNative.SWP_NOMOVE | TbNative.SWP_NOSIZE | TbNative.SWP_NOACTIVATE);
        }

        public void Destroy()
        {
            IntPtr h = Handle;
            if (h != IntPtr.Zero)
            {
                ClearAppProperties(h);   // the docs ask for this before the window goes
                DestroyHandle();
            }
            if (bigIcon != IntPtr.Zero) TbNative.DestroyIcon(bigIcon);
            if (smallIcon != IntPtr.Zero) TbNative.DestroyIcon(smallIcon);
            bigIcon = smallIcon = IntPtr.Zero;
            FreeGlyphs(glyphs);
            glyphs = null;
            ready = false;
        }

        // Called every 250 ms with the newest status.
        public void Refresh(VlcStatus s, DateTime now)
        {
            IntPtr h = Handle;
            if (h == IntPtr.Zero) return;
            shown = s ?? VlcStatus.Offline;
            string t = VlcTaskbarView.ButtonTitle(shown);
            if (t != title) { TbNative.SetWindowText(h, t); title = t; }
            if (!ready) return;
            UpdateButtons(false);
            UpdateProgress(now);
            string key = VlcTaskbarView.ThumbnailKey(shown, now);
            if (key != thumbKey)
            {
                thumbKey = key;
                TbNative.DwmInvalidateIconicBitmaps(h);   // DWM asks again when it shows the preview
            }
        }

        void OnButtonCreated()
        {
            if (tbList == null)
            {
                tbList = (ITaskbarList3)new CTaskbarList();
                int hr0 = tbList.HrInit();
                if (hr0 < 0) Log("taskbar button: ITaskbarList3.HrInit hr=0x" + hr0.ToString("X8"));
            }
            buttonState = -1; progressFlag = -1; progressPermille = -1;
            tbRootTabRemoved = IntPtr.Zero;   // after an Explorer restart VLC's own button may be back
            int hr = tbList.ThumbBarAddButtons(Handle, 3, Buttons(shown));
            Log("taskbar button: button created, ThumbBarAddButtons hr=0x" + hr.ToString("X8"));
            if (hr >= 0) buttonState = ButtonState(shown);
            ready = true;
            UpdateProgress(DateTime.Now);
        }

        int ButtonState(VlcStatus s)
        {
            return (s.Ok ? 1 : 0) | (s.State == VlcState.Playing ? 2 : 0) | (lightTheme ? 4 : 0);
        }

        THUMBBUTTON[] Buttons(VlcStatus s)
        {
            bool playing = s.State == VlcState.Playing;
            uint flags = s.Ok ? TbNative.THBF_ENABLED : TbNative.THBF_DISABLED;
            THUMBBUTTON[] b = new THUMBBUTTON[3];
            b[0] = Button(1, glyphs[VlcTaskbarView.GlyphPrev], "Previous", flags);
            b[1] = Button(2, glyphs[playing ? VlcTaskbarView.GlyphPause : VlcTaskbarView.GlyphPlay], playing ? "Pause" : "Play", flags);
            b[2] = Button(3, glyphs[VlcTaskbarView.GlyphNext], "Next", flags);
            return b;
        }

        static THUMBBUTTON Button(uint id, IntPtr icon, string tip, uint flags)
        {
            THUMBBUTTON b = new THUMBBUTTON();
            b.dwMask = TbNative.THB_ICON | TbNative.THB_TOOLTIP | TbNative.THB_FLAGS;
            b.iId = id;
            b.hIcon = icon;
            b.szTip = tip;
            b.dwFlags = flags;
            return b;
        }

        void UpdateButtons(bool force)
        {
            int state = ButtonState(shown);
            if (!force && state == buttonState) return;
            int hr = tbList.ThumbBarUpdateButtons(Handle, 3, Buttons(shown));
            if (hr >= 0) buttonState = state;
            else Log("taskbar button: ThumbBarUpdateButtons hr=0x" + hr.ToString("X8"));
        }

        // Green while playing, yellow while paused, none when stopped / no length (streams).
        void UpdateProgress(DateTime now)
        {
            VlcStatus s = shown;
            int flag = VlcTaskbarView.ProgressFlag(s);
            long total = (long)s.Length * 1000;
            long done = VlcTaskbarView.ElapsedMs(s, now);
            long permille = flag == TbNative.TBPF_NOPROGRESS || total <= 0 ? -1 : done * 1000 / total;
            if (flag == progressFlag && permille == progressPermille) return;
            IntPtr h = Handle;
            // a value switches the state to NORMAL only from NOPROGRESS, so value first, then state
            if (flag != TbNative.TBPF_NOPROGRESS) tbList.SetProgressValue(h, (ulong)done, (ulong)total);
            if (flag != progressFlag) tbList.SetProgressState(h, flag);
            progressFlag = flag;
            progressPermille = permille;
        }

        // DWM wants a thumbnail no larger than maxW x maxH: a 32-bit top-down DIB section with
        // premultiplied alpha. GDI+ draws straight into the DIB's memory as Format32bppPArgb.
        void SendThumbnail(int maxW, int maxH)
        {
            if (maxW <= 0 || maxH <= 0) return;
            int w = maxW, h = maxH;
            VlcTaskbarView.FitCard(ref w, ref h);
            TbNative.BITMAPINFOHEADER bi = new TbNative.BITMAPINFOHEADER();
            bi.biSize = (uint)Marshal.SizeOf(typeof(TbNative.BITMAPINFOHEADER));
            bi.biWidth = w;
            bi.biHeight = -h;          // top-down, like GDI+'s rows
            bi.biPlanes = 1;
            bi.biBitCount = 32;
            bi.biCompression = 0;      // BI_RGB
            IntPtr bits;
            IntPtr hbmp = TbNative.CreateDIBSection(IntPtr.Zero, ref bi, 0, out bits, IntPtr.Zero, 0);
            if (hbmp == IntPtr.Zero || bits == IntPtr.Zero) { Log("taskbar button: CreateDIBSection failed"); return; }
            try
            {
                using (Bitmap bmp = new Bitmap(w, h, w * 4, System.Drawing.Imaging.PixelFormat.Format32bppPArgb, bits))
                using (Graphics g = Graphics.FromImage(bmp))
                    VlcTaskbarView.DrawThumbnail(g, w, h, Remote.Status, DateTime.Now);
                int hr = TbNative.DwmSetIconicThumbnail(Handle, hbmp, 0);
                if (hr < 0) Log("taskbar button: DwmSetIconicThumbnail " + w + "x" + h + " hr=0x" + hr.ToString("X8"));
            }
            finally { TbNative.DeleteObject(hbmp); }   // DWM keeps its own copy
        }

        void OnThemeChanged()
        {
            bool light = VlcTaskbarView.SystemUsesLightTheme();
            if (light == lightTheme) return;
            IntPtr[] old = glyphs;
            lightTheme = light;
            glyphs = MakeGlyphs(light);
            if (ready) UpdateButtons(true);
            FreeGlyphs(old);   // only after the taskbar has the new ones
        }

        static IntPtr[] MakeGlyphs(bool light)
        {
            int n = TbNative.GetSystemMetrics(TbNative.SM_CXSMICON);
            if (n < 16) n = 16;
            Color c = light ? Color.FromArgb(32, 33, 36) : Color.White;
            IntPtr[] icons = new IntPtr[4];
            for (int k = 0; k < 4; k++)
            {
                using (Bitmap bmp = VlcTaskbarView.GlyphBitmap(k, n, c))
                    icons[k] = bmp.GetHicon();
            }
            return icons;
        }

        static void FreeGlyphs(IntPtr[] icons)
        {
            if (icons == null) return;
            foreach (IntPtr i in icons) if (i != IntPtr.Zero) TbNative.DestroyIcon(i);
        }

        void SetAppProperties(IntPtr h, string exe, string appId)
        {
            TbNative.IPropertyStore ps = OpenProps(h);
            if (ps == null) return;
            try
            {
                // relaunch first, the id last (setting the id makes the taskbar read the others)
                if (exe != null)
                {
                    SetProp(ps, TbNative.PID_RelaunchCommand, "\"" + exe + "\"");
                    SetProp(ps, TbNative.PID_RelaunchDisplayNameResource, VlcTaskbarView.DefaultTitle);
                    SetProp(ps, TbNative.PID_RelaunchIconResource, exe + ",0");
                }
                if (appId != null) SetProp(ps, TbNative.PID_ID, appId);
                ps.Commit();
            }
            finally { Marshal.ReleaseComObject(ps); }
        }

        void ClearAppProperties(IntPtr h)
        {
            TbNative.IPropertyStore ps = OpenProps(h);
            if (ps == null) return;
            try
            {
                SetProp(ps, TbNative.PID_ID, null);
                SetProp(ps, TbNative.PID_RelaunchCommand, null);
                SetProp(ps, TbNative.PID_RelaunchDisplayNameResource, null);
                SetProp(ps, TbNative.PID_RelaunchIconResource, null);
                ps.Commit();
            }
            catch (Exception) { }
            finally { Marshal.ReleaseComObject(ps); }
        }

        static TbNative.IPropertyStore OpenProps(IntPtr h)
        {
            Guid iid = TbNative.IID_IPropertyStore;
            TbNative.IPropertyStore ps;
            int hr = TbNative.SHGetPropertyStoreForWindow(h, ref iid, out ps);
            if (hr < 0 || ps == null) { Log("taskbar button: SHGetPropertyStoreForWindow hr=0x" + hr.ToString("X8")); return null; }
            return ps;
        }

        // value null = VT_EMPTY (removes the property)
        static void SetProp(TbNative.IPropertyStore ps, uint pid, string value)
        {
            TbNative.PROPERTYKEY key = new TbNative.PROPERTYKEY();
            key.fmtid = TbNative.FMTID_AppUserModel;
            key.pid = pid;
            TbNative.PROPVARIANT pv = new TbNative.PROPVARIANT();
            if (value != null) { pv.vt = TbNative.VT_LPWSTR; pv.p = Marshal.StringToCoTaskMemUni(value); }
            try
            {
                int hr = ps.SetValue(ref key, ref pv);
                if (hr < 0) Log("taskbar button: property " + pid + " hr=0x" + hr.ToString("X8"));
            }
            finally { if (pv.p != IntPtr.Zero) Marshal.FreeCoTaskMem(pv.p); }   // the store keeps its own copy
        }

        protected override void WndProc(ref Message m)
        {
            try
            {
                if (OnMessage(ref m)) return;
            }
            catch (Exception ex) { Log("taskbar button: message 0x" + m.Msg.ToString("X") + ": " + ex.GetType().Name + ": " + ex.Message); }
            base.WndProc(ref m);
        }

        bool OnMessage(ref Message m)
        {
            int msg = m.Msg;
            long wp = m.WParam.ToInt64();
            if ((uint)msg == WM_TASKBARBUTTONCREATED) { OnButtonCreated(); return true; }   // also after Explorer restarts
            switch (msg)
            {
                case WM_COMMAND:
                    if (((wp >> 16) & 0xFFFF) != THBN_CLICKED) return false;
                    TaskbarClicked((int)(wp & 0xFFFF));
                    return true;
                case WM_DWMSENDICONICTHUMBNAIL:
                    long lp = m.LParam.ToInt64();
                    SendThumbnail((int)((lp >> 16) & 0xFFFF), (int)(lp & 0xFFFF));   // HIWORD = width, LOWORD = height
                    return true;
                case WM_ACTIVATE:
                    if ((wp & 0xFFFF) != 0)
                    {
                        // item 33 log: when and from where our invisible window gets activated
                        Log("taskbar button: our window activated (WA " + (wp & 0xFFFF) + ", from " + DescribeOwner(m.LParam) + "); " + VlcStateText());
                        TbNative.PostMessage(Handle, (uint)WM_FORWARD, IntPtr.Zero, IntPtr.Zero);   // after activation completes
                    }
                    return false;
                case WM_FORWARD:
                    IntPtr dpi = DpiEnter();
                    try { TaskbarActivated(); }
                    finally { DpiLeave(dpi); }
                    return true;
                case WM_SYSCOMMAND:
                    int sc = (int)(wp & 0xFFF0);
                    Log("taskbar button: WM_SYSCOMMAND 0x" + sc.ToString("X") + " to our window" +
                        (sc == SC_MINIMIZE ? " (minimize: ignored, VLC is not touched)" : ""));
                    if (sc == SC_CLOSE) { TaskbarClose(); return true; }
                    // the window must stay as it is: no minimize (a click on the active button), maximize, move, size
                    return sc == SC_MINIMIZE || sc == SC_MAXIMIZE || sc == SC_MOVE || sc == SC_SIZE;
                case WM_CLOSE:
                    TaskbarClose();   // never DestroyWindow from outside: TaskbarDestroy does that
                    return true;
                case WM_SETTINGCHANGE:
                    if (m.LParam != IntPtr.Zero && Marshal.PtrToStringUni(m.LParam) == "ImmersiveColorSet") OnThemeChanged();
                    return false;
            }
            return false;
        }

    }
}

// What the taskbar button shows: pure functions (no Win32), so they can be tested anywhere.
public static class VlcTaskbarView
{
    public const string DefaultTitle = "VLC media player";
    public const int GlyphPrev = 0, GlyphPlay = 1, GlyphPause = 2, GlyphNext = 3;

    // Midnight
    static readonly Color Back = Color.FromArgb(0x1b, 0x1c, 0x1e);
    static readonly Color Track = Color.FromArgb(0x2e, 0x31, 0x35);
    static readonly Color Accent = Color.FromArgb(0x5f, 0xd3, 0xe8);
    static readonly Color Text = Color.FromArgb(0xe8, 0xea, 0xed);
    static readonly Color Dim = Color.FromArgb(0x9a, 0xa0, 0xa6);

    // "Artist - Title", "Title", or "VLC media player" when nothing is loaded / VLC does not answer
    public static string ButtonTitle(VlcStatus s)
    {
        if (s == null || !s.Ok || s.State == VlcState.Offline) return DefaultTitle;
        string t = (s.Title ?? "").Trim(), a = (s.Artist ?? "").Trim();
        if (t.Length == 0) return DefaultTitle;
        return a.Length > 0 ? a + " - " + t : t;
    }

    // Milliseconds into the track now: VLC reports whole seconds every 500 ms, so count on
    // from the last report while playing (at most 5 s, in case the reports stop).
    public static long ElapsedMs(VlcStatus s, DateTime now)
    {
        if (s == null || !s.Ok) return 0;
        long ms = (long)s.Time * 1000;
        if (s.State == VlcState.Playing && s.At != DateTime.MinValue)
        {
            double d = (now - s.At).TotalMilliseconds;
            if (d > 0) ms += (long)Math.Min(d, 5000);
        }
        if (s.Length > 0 && ms > (long)s.Length * 1000) ms = (long)s.Length * 1000;
        return ms < 0 ? 0 : ms;
    }

    // ITaskbarList3 progress state: TBPF_NORMAL (2) playing, TBPF_PAUSED (8) paused, else TBPF_NOPROGRESS (0)
    public static int ProgressFlag(VlcStatus s)
    {
        if (s == null || !s.Ok || s.Length <= 0) return 0;
        if (s.State == VlcState.Playing) return 2;
        if (s.State == VlcState.Paused) return 8;
        return 0;
    }

    public static string FormatTime(long seconds)
    {
        if (seconds < 0) seconds = 0;
        long h = seconds / 3600, m = seconds / 60 % 60, sec = seconds % 60;
        return h > 0 ? h + ":" + m.ToString("00") + ":" + sec.ToString("00") : m + ":" + sec.ToString("00");
    }

    // "1:23 / 4:56", or "1:23" without a length (streams)
    public static string TimeText(VlcStatus s, DateTime now)
    {
        long el = ElapsedMs(s, now) / 1000;
        return s != null && s.Length > 0 ? FormatTime(el) + " / " + FormatTime(s.Length) : FormatTime(el);
    }

    // Changes whenever the preview would look different (the time once a second).
    public static string ThumbnailKey(VlcStatus s, DateTime now)
    {
        if (s == null || !s.Ok) return "offline";
        return s.State + "|" + s.Title + "|" + s.Artist + "|" + TimeText(s, now) + "|" + s.PlaylistId;
    }

    // Our own window's taskbar group: Windows' id for an exe without an explicit one is its
    // path with the known folder it is in replaced by that folder's GUID (longest match), else
    // the full path. roots: (folder path, "{GUID}").
    public static string ImplicitAppId(string exe, IList<KeyValuePair<string, string>> roots)
    {
        string best = null, guid = null;
        foreach (KeyValuePair<string, string> r in roots)
        {
            string dir = (r.Key ?? "").TrimEnd('\\');
            if (dir.Length == 0 || exe.Length <= dir.Length + 1 || exe[dir.Length] != '\\') continue;
            if (!exe.StartsWith(dir, StringComparison.OrdinalIgnoreCase)) continue;
            if (best == null || dir.Length > best.Length) { best = dir; guid = r.Value; }
        }
        return best == null ? exe : guid + exe.Substring(best.Length);
    }

    public static bool SystemUsesLightTheme()
    {
        try
        {
            using (Microsoft.Win32.RegistryKey k = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(
                       @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"))
            {
                object v = k != null ? k.GetValue("SystemUsesLightTheme") : null;
                return v is int && (int)v == 1;
            }
        }
        catch (Exception) { return false; }
    }

    // Keep the preview card-shaped (about 16:9) inside what DWM allows.
    public static void FitCard(ref int w, ref int h)
    {
        int ch = (int)Math.Round(w * 0.5625);
        if (ch <= h) { h = Math.Max(1, ch); return; }
        w = Math.Max(1, Math.Min(w, (int)Math.Round(h / 0.5625)));
    }

    // Thumbnail-button image: n x n, transparent, glyph in colour c.
    public static Bitmap GlyphBitmap(int kind, int n, Color c)
    {
        Bitmap bmp = new Bitmap(n, n, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.Clear(Color.Transparent);
            DrawGlyph(g, kind, 0, 0, n, c);
        }
        return bmp;
    }

    public static void DrawGlyph(Graphics g, int kind, float x, float y, float n, Color c)
    {
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        using (SolidBrush b = new SolidBrush(c))
        {
            float t = y + n * 0.22f, bo = y + n * 0.78f, mid = y + n * 0.5f;
            switch (kind)
            {
                case GlyphPlay:
                    g.FillPolygon(b, new PointF[] { new PointF(x + n * 0.28f, y + n * 0.18f), new PointF(x + n * 0.28f, y + n * 0.82f),
                                                    new PointF(x + n * 0.82f, mid) });
                    break;
                case GlyphPause:
                    g.FillRectangle(b, x + n * 0.24f, t, n * 0.18f, bo - t);
                    g.FillRectangle(b, x + n * 0.58f, t, n * 0.18f, bo - t);
                    break;
                case GlyphPrev:
                    g.FillRectangle(b, x + n * 0.18f, t, n * 0.13f, bo - t);
                    g.FillPolygon(b, new PointF[] { new PointF(x + n * 0.82f, t), new PointF(x + n * 0.82f, bo),
                                                    new PointF(x + n * 0.33f, mid) });
                    break;
                default:   // next
                    g.FillRectangle(b, x + n * 0.69f, t, n * 0.13f, bo - t);
                    g.FillPolygon(b, new PointF[] { new PointF(x + n * 0.18f, t), new PointF(x + n * 0.18f, bo),
                                                    new PointF(x + n * 0.67f, mid) });
                    break;
            }
        }
    }

    // The hover preview: title (up to 2 lines), artist, state + time, progress bar.
    public static void DrawThumbnail(Graphics g, int w, int h, VlcStatus s, DateTime now)
    {
        if (s == null) s = VlcStatus.Offline;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;   // opaque background: no ClearType needed
        g.Clear(Back);

        float pad = Math.Max(5f, h * 0.08f);
        float barH = Math.Max(3f, (float)Math.Round(h * 0.04f));
        float inner = w - 2 * pad;
        RectangleF bar = new RectangleF(pad, h - pad - barH, inner, barH);

        bool item = s.Ok && s.State != VlcState.Offline && (s.Title ?? "").Trim().Length > 0;
        string title = item ? s.Title.Trim() : DefaultTitle;
        string artist = item ? (s.Artist ?? "").Trim() : (s.Ok ? "Nothing playing" : "Not connected");
        string state = !s.Ok ? "" : s.State == VlcState.Paused ? "Paused" : s.State == VlcState.Stopped ? "Stopped" : "";

        using (Font titleFont = new Font("Segoe UI", Math.Max(9f, h * 0.15f), FontStyle.Bold, GraphicsUnit.Pixel))
        using (Font smallFont = new Font("Segoe UI", Math.Max(8f, h * 0.115f), FontStyle.Regular, GraphicsUnit.Pixel))
        using (SolidBrush text = new SolidBrush(Text))
        using (SolidBrush dim = new SolidBrush(Dim))
        using (SolidBrush accent = new SolidBrush(Accent))
        using (SolidBrush track = new SolidBrush(Track))
        using (StringFormat wrap = new StringFormat(StringFormatFlags.LineLimit))
        using (StringFormat one = new StringFormat(StringFormatFlags.NoWrap))
        {
            wrap.Trimming = StringTrimming.EllipsisWord;
            one.Trimming = StringTrimming.EllipsisCharacter;
            float smallH = smallFont.GetHeight(g), titleH = titleFont.GetHeight(g);

            // bottom up: progress bar, time line
            float timeY = bar.Top - pad * 0.5f - smallH;
            if (item && s.Length > 0)
            {
                g.FillRectangle(track, bar);
                float f = (float)Math.Min(1.0, ElapsedMs(s, now) / (s.Length * 1000.0));
                if (f > 0) g.FillRectangle(accent, bar.Left, bar.Top, Math.Max(1f, bar.Width * f), bar.Height);
            }
            if (item)
            {
                float gs = smallH * 0.8f;
                int kind = s.State == VlcState.Playing ? GlyphPlay : GlyphPause;
                if (s.State != VlcState.Stopped) DrawGlyph(g, kind, pad - gs * 0.2f, timeY + (smallH - gs) / 2, gs, Accent);
                float tx = pad + gs * 0.9f;
                g.DrawString(TimeText(s, now), smallFont, accent, new RectangleF(tx, timeY, inner - (tx - pad), smallH + 2), one);
            }
            if (state.Length > 0)
            {
                using (StringFormat right = new StringFormat(StringFormatFlags.NoWrap))
                {
                    right.Alignment = StringAlignment.Far;
                    g.DrawString(state, smallFont, dim, new RectangleF(pad, timeY, inner, smallH + 2), right);
                }
            }

            // top down: title (2 lines when there is room), artist
            float room = timeY - pad * 0.5f - pad - (artist.Length > 0 ? smallH : 0);
            bool oneLine = g.MeasureString(title, titleFont, new PointF(0, 0), one).Width <= inner;
            int lines = !oneLine && room >= titleH * 2 ? 2 : 1;
            float titleBox = titleH * lines;
            g.DrawString(title, titleFont, text, new RectangleF(pad, pad, inner, titleBox + 1), lines == 2 ? wrap : one);
            if (artist.Length > 0)
                g.DrawString(artist, smallFont, dim, new RectangleF(pad, pad + titleBox + 1, inner, smallH + 2), one);
        }
    }
}

// ---- Win32 / COM for the taskbar button (kept apart from VlcDock's own declarations)
static class TbNative
{
    public const uint WS_POPUP = 0x80000000, WS_SYSMENU = 0x80000, WS_MINIMIZEBOX = 0x20000;
    public const int WS_EX_APPWINDOW = 0x40000, WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20;
    public const int GWL_EXSTYLE = -20;
    public const uint GW_OWNER = 4;
    public const uint LWA_ALPHA = 2;
    public const int SW_SHOWNOACTIVATE = 4;
    public const uint WM_SETICON = 0x80;
    public const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOACTIVATE = 0x10;
    public static readonly IntPtr HWND_BOTTOM = new IntPtr(1);
    public const uint SMTO_ABORTIFHUNG = 2;
    public const uint MSGFLT_ALLOW = 1;
    public const int SM_CXSMICON = 49;
    public const int DWMWA_FORCE_ICONIC_REPRESENTATION = 7, DWMWA_HAS_ICONIC_BITMAP = 10, DWMWA_DISALLOW_PEEK = 11;
    public const uint THB_ICON = 0x2, THB_TOOLTIP = 0x4, THB_FLAGS = 0x8;
    public const uint THBF_ENABLED = 0x0, THBF_DISABLED = 0x1;
    public const int TBPF_NOPROGRESS = 0, TBPF_NORMAL = 2, TBPF_PAUSED = 8;
    const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;

    // PKEY_AppUserModel_* = {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, pid (propkey.h)
    public static readonly Guid FMTID_AppUserModel = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
    public const uint PID_RelaunchCommand = 2, PID_RelaunchIconResource = 3, PID_RelaunchDisplayNameResource = 4, PID_ID = 5;
    public static readonly Guid IID_IPropertyStore = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");
    public const ushort VT_LPWSTR = 31;

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct PROPERTYKEY { public Guid fmtid; public uint pid; }

    // PROPVARIANT: vt + 3 reserved WORDs, then a union of up to 2 pointers (16 bytes on x86, 24 on x64)
    [StructLayout(LayoutKind.Sequential)]
    public struct PROPVARIANT { public ushort vt, r1, r2, r3; public IntPtr p; public IntPtr p2; }

    [StructLayout(LayoutKind.Sequential)]
    public struct BITMAPINFOHEADER
    {
        public uint biSize; public int biWidth; public int biHeight; public ushort biPlanes; public ushort biBitCount;
        public uint biCompression; public uint biSizeImage; public int biXPelsPerMeter; public int biYPelsPerMeter;
        public uint biClrUsed; public uint biClrImportant;
    }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore
    {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int GetAt(uint index, out PROPERTYKEY key);
        [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
        [PreserveSig] int Commit();
    }

    [DllImport("user32.dll")] public static extern bool KillTimer(IntPtr h, UIntPtr id);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int index);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int max);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern bool SetWindowText(IntPtr h, string text);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern uint RegisterWindowMessage(string name);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool AllowSetForegroundWindow(uint pid);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr wParam, IntPtr lParam,
                                                                             uint flags, uint timeout, out UIntPtr result);
    [DllImport("user32.dll")] public static extern bool SetLayeredWindowAttributes(IntPtr h, uint key, byte alpha, uint flags);
    [DllImport("user32.dll")] public static extern bool ChangeWindowMessageFilterEx(IntPtr h, uint msg, uint action, IntPtr info);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr icon);
    [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);
    [DllImport("gdi32.dll")] public static extern IntPtr CreateDIBSection(IntPtr hdc, ref BITMAPINFOHEADER bmi, uint usage,
                                                                          out IntPtr bits, IntPtr section, uint offset);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)] public static extern uint ExtractIconEx(string file, int index,
                                                                                                  out IntPtr large, out IntPtr small, uint count);
    [DllImport("shell32.dll")] public static extern int SHGetPropertyStoreForWindow(IntPtr h, ref Guid iid,
                                                                                    [MarshalAs(UnmanagedType.Interface)] out IPropertyStore store);
    [DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr h, int attr, ref int value, int size);
    [DllImport("dwmapi.dll")] public static extern int DwmSetIconicThumbnail(IntPtr h, IntPtr hbmp, uint flags);
    [DllImport("dwmapi.dll")] public static extern int DwmInvalidateIconicBitmaps(IntPtr h);
    [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool QueryFullProcessImageName(IntPtr h, uint flags,
                                                                                                        StringBuilder sb, ref uint size);

    // Full path of a process's exe; works across 32 / 64 bit (Process.MainModule does not). null on failure.
    public static string ProcessPath(uint pid)
    {
        IntPtr h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
        if (h == IntPtr.Zero) return null;
        try
        {
            StringBuilder sb = new StringBuilder(1024);
            uint size = (uint)sb.Capacity;
            return QueryFullProcessImageName(h, 0, sb, ref size) ? sb.ToString() : null;
        }
        finally { CloseHandle(h); }
    }
}

// ITaskbarList3 (shobjidl_core.h): ITaskbarList, ITaskbarList2 and ITaskbarList3 methods in
// vtable order. HWNDs and handles as IntPtr, so it works in 32- and 64-bit PowerShell.
[ComImport, Guid("ea1afb91-9e28-4b86-90e9-9e9f8a5eefaf"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface ITaskbarList3
{
    // ITaskbarList
    [PreserveSig] int HrInit();
    [PreserveSig] int AddTab(IntPtr hwnd);
    [PreserveSig] int DeleteTab(IntPtr hwnd);
    [PreserveSig] int ActivateTab(IntPtr hwnd);
    [PreserveSig] int SetActiveAlt(IntPtr hwnd);
    // ITaskbarList2
    [PreserveSig] int MarkFullscreenWindow(IntPtr hwnd, int fullscreen);
    // ITaskbarList3
    [PreserveSig] int SetProgressValue(IntPtr hwnd, ulong completed, ulong total);
    [PreserveSig] int SetProgressState(IntPtr hwnd, int flags);
    [PreserveSig] int RegisterTab(IntPtr hwndTab, IntPtr hwndMdi);
    [PreserveSig] int UnregisterTab(IntPtr hwndTab);
    [PreserveSig] int SetTabOrder(IntPtr hwndTab, IntPtr hwndInsertBefore);
    [PreserveSig] int SetTabActive(IntPtr hwndTab, IntPtr hwndMdi, uint reserved);
    [PreserveSig] int ThumbBarAddButtons(IntPtr hwnd, uint count, [MarshalAs(UnmanagedType.LPArray)] THUMBBUTTON[] buttons);
    [PreserveSig] int ThumbBarUpdateButtons(IntPtr hwnd, uint count, [MarshalAs(UnmanagedType.LPArray)] THUMBBUTTON[] buttons);
    [PreserveSig] int ThumbBarSetImageList(IntPtr hwnd, IntPtr himl);
    [PreserveSig] int SetOverlayIcon(IntPtr hwnd, IntPtr icon, [MarshalAs(UnmanagedType.LPWStr)] string description);
    [PreserveSig] int SetThumbnailTooltip(IntPtr hwnd, [MarshalAs(UnmanagedType.LPWStr)] string tip);
    [PreserveSig] int SetThumbnailClip(IntPtr hwnd, IntPtr clip);
}

// CLSID_TaskbarList
[ComImport, Guid("56FDF344-FD6D-11d0-958A-006097C9A090"), ClassInterface(ClassInterfaceType.None)]
class CTaskbarList { }

// THUMBBUTTON (shobjidl_core.h, pshpack8 = natural alignment): 540 bytes on x86, 552 on x64
[StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
struct THUMBBUTTON
{
    public uint dwMask;
    public uint iId;
    public uint iBitmap;
    public IntPtr hIcon;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szTip;
    public uint dwFlags;
}
