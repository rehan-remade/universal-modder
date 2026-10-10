<#
  WinDrive: drive ONE game window with a line-per-command stdin protocol (one reply line each).
  No build step: Windows PowerShell 5.1 compiles the embedded C# on start (~1-2 s).

    powershell -NoProfile -ExecutionPolicy Bypass -File WinDrive.ps1 -Proc AoE2DE_s

  Commands (coordinates are CLIENT coordinates of the game window):
    focus                      bring the window to the foreground            -> ok | fail
    rect                       client area in screen coords                   -> x y w h | none
    title                      window title
    fg                         name of the foreground process
    move <x> <y>               cursor to client coords
    click <x> <y> [right]      click (left by default)
    mdown <x> <y> [right] / mup [right]    press / release a mouse button
    drag <x0> <y0> <x1> <y1>   left-drag (box select)
    rel <dx> <dy>              relative mouse move (FPS cameras / raw input)
    key <vk> [tap|down|up]     virtual-key (hex like 0x1B or decimal)
    hold <vk> <ms>             hold a key for ms (movement)
    type <text>                unicode text
    wheel <delta>              mouse wheel (120 = one notch up)
    scanmode on|off            send hardware scan codes (DirectInput / raw-input games ignore VK-only events)
    size <w> <h>               resize the window so its CLIENT area is w x h (windowed mode)
    untop                      undo the topmost flag focus may set
    idle                       seconds since the last real user input on this machine
  Safety: input is only sent while the target window is the foreground window (or nothing is, and the
  cursor is over the game), so keys never leak into other apps. Close stdin to quit.
#>
param([Parameter(Mandatory = $true)][string]$Proc)

$src = @"
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

public static class WinDrive
{
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint data, flags, time; public IntPtr extra; }
    [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public IntPtr extra; }
    [StructLayout(LayoutKind.Explicit)] struct U { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public U u; }
    [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint size, time; }

    [DllImport("user32.dll")] static extern uint SendInput(uint n, INPUT[] i, int size);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
    [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO i);
    [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);

    static string proc;
    static bool scanMode = false;

    static IntPtr Window()
    {
        foreach (var p in Process.GetProcessesByName(proc))
            if (p.MainWindowHandle != IntPtr.Zero) return p.MainWindowHandle;
        return IntPtr.Zero;
    }

    static string ProcName(IntPtr h)
    {
        uint pid;
        GetWindowThreadProcessId(h, out pid);
        try { return Process.GetProcessById((int)pid).ProcessName; } catch { return "?"; }
    }

    static bool IsForeground()
    {
        var fg = GetForegroundWindow();
        return fg != IntPtr.Zero && ProcName(fg).Equals(proc, StringComparison.OrdinalIgnoreCase);
    }

    static INPUT Mouse(uint flags, uint data, int dx, int dy)
    {
        var i = new INPUT(); i.type = 0; i.u.mi.flags = flags; i.u.mi.data = data; i.u.mi.dx = dx; i.u.mi.dy = dy; return i;
    }

    static INPUT Key(ushort vk, bool up)
    {
        var i = new INPUT(); i.type = 1;
        ushort sc = (ushort)MapVirtualKey(vk, 0);
        bool ext = vk == 0x25 || vk == 0x26 || vk == 0x27 || vk == 0x28 || vk == 0x2D || vk == 0x2E || vk == 0x24 || vk == 0x23 || vk == 0x21 || vk == 0x22 || vk == 0xA3 || vk == 0xA5;
        if (scanMode) { i.u.ki.vk = 0; i.u.ki.scan = sc; i.u.ki.flags = 0x0008u | (up ? 2u : 0u) | (ext ? 1u : 0u); }
        else { i.u.ki.vk = vk; i.u.ki.scan = sc; i.u.ki.flags = (up ? 2u : 0u) | (ext ? 1u : 0u); }
        return i;
    }

    static bool Focus()
    {
        var h = Window();
        if (h == IntPtr.Zero) return false;
        if (IsForeground()) return true;
        keybd_event(0x12, 0, 0, IntPtr.Zero); keybd_event(0x12, 0, 2, IntPtr.Zero); // alt tap: allowed to take the foreground
        uint dummy;
        uint target = GetWindowThreadProcessId(h, out dummy), me = GetCurrentThreadId();
        AttachThreadInput(me, target, true);
        ShowWindow(h, 9);
        SetForegroundWindow(h);
        AttachThreadInput(me, target, false);
        Thread.Sleep(300);
        if (IsForeground()) return true;
        // Foreground lock: a real click activates the window - only if the point really is on our window.
        SetWindowPos(h, new IntPtr(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040);
        RECT r; GetClientRect(h, out r);
        var p = new POINT(); p.X = (r.R - r.L) / 2; p.Y = 4;
        ClientToScreen(h, ref p);
        var under = WindowFromPoint(p);
        if (GetAncestor(under, 2) != GetAncestor(h, 2) && under != h) return false;
        SetCursorPos(p.X, p.Y);
        SendInput(1, new INPUT[] { Mouse(2u, 0, 0, 0) }, Marshal.SizeOf(typeof(INPUT)));
        SendInput(1, new INPUT[] { Mouse(4u, 0, 0, 0) }, Marshal.SizeOf(typeof(INPUT)));
        Thread.Sleep(300);
        return IsForeground();
    }

    // Safe if the game is the foreground window, or if nothing is (windowed games can drop the
    // foreground on clicks) and the cursor is over the game - then input can only reach the game.
    static bool Safe()
    {
        if (IsForeground()) return true;
        if (GetForegroundWindow() != IntPtr.Zero) return false;
        POINT p; GetCursorPos(out p);
        var under = WindowFromPoint(p);
        var h = Window();
        return under == h || GetAncestor(under, 2) == GetAncestor(h, 2);
    }

    static void Send(params INPUT[] i)
    {
        if (!Safe()) throw new InvalidOperationException("target window is not in the foreground (foreground: " + ProcName(GetForegroundWindow()) + ")");
        SendInput((uint)i.Length, i, Marshal.SizeOf(typeof(INPUT)));
    }

    static void MoveTo(int x, int y)
    {
        var p = new POINT(); p.X = x; p.Y = y;
        ClientToScreen(Window(), ref p);
        SetCursorPos(p.X, p.Y);
    }

    static ushort Vk(string s) { return s.StartsWith("0x") ? Convert.ToUInt16(s, 16) : ushort.Parse(s); }

    static string Do(string line)
    {
        var a = line.Trim().Split(new char[] { ' ' }, 2);
        var rest = a.Length > 1 ? a[1] : "";
        var n = rest.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        switch (a[0])
        {
            case "focus": return Focus() ? "ok" : "fail";
            case "fg": return ProcName(GetForegroundWindow());
            case "title": { var h = Window(); if (h == IntPtr.Zero) return "none"; foreach (var p in Process.GetProcessesByName(proc)) if (p.MainWindowHandle == h) return p.MainWindowTitle; return ""; }
            case "untop": SetWindowPos(Window(), new IntPtr(-2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040); return "ok";
            case "rect":
            {
                var h = Window();
                if (h == IntPtr.Zero) return "none";
                RECT r; GetClientRect(h, out r);
                var p = new POINT(); ClientToScreen(h, ref p);
                return p.X + " " + p.Y + " " + (r.R - r.L) + " " + (r.B - r.T);
            }
            case "size":
            {
                var h = Window();
                RECT wr, cr; GetWindowRect(h, out wr); GetClientRect(h, out cr);
                int bw = (wr.R - wr.L) - (cr.R - cr.L), bh = (wr.B - wr.T) - (cr.B - cr.T);
                SetWindowPos(h, IntPtr.Zero, 0, 0, int.Parse(n[0]) + bw, int.Parse(n[1]) + bh, 0x0002 | 0x0004);
                return "ok";
            }
            case "move": MoveTo(int.Parse(n[0]), int.Parse(n[1])); return "ok";
            case "click":
            {
                MoveTo(int.Parse(n[0]), int.Parse(n[1]));
                Thread.Sleep(40);
                bool right = n.Length > 2 && n[2] == "right";
                Send(Mouse(right ? 8u : 2u, 0, 0, 0)); Thread.Sleep(60); Send(Mouse(right ? 16u : 4u, 0, 0, 0));
                return "ok";
            }
            case "mdown": { MoveTo(int.Parse(n[0]), int.Parse(n[1])); Thread.Sleep(30); Send(Mouse(n.Length > 2 && n[2] == "right" ? 8u : 2u, 0, 0, 0)); return "ok"; }
            case "mup": { Send(Mouse(n.Length > 0 && n[0] == "right" ? 16u : 4u, 0, 0, 0)); return "ok"; }
            case "rel": { Send(Mouse(0x0001, 0, int.Parse(n[0]), int.Parse(n[1]))); return "ok"; }
            case "drag":
            {
                int x0 = int.Parse(n[0]), y0 = int.Parse(n[1]), x1 = int.Parse(n[2]), y1 = int.Parse(n[3]);
                MoveTo(x0, y0); Thread.Sleep(40);
                Send(Mouse(2u, 0, 0, 0)); Thread.Sleep(80);
                for (int k = 1; k <= 10; k++) { MoveTo(x0 + (x1 - x0) * k / 10, y0 + (y1 - y0) * k / 10); Thread.Sleep(20); }
                Send(Mouse(4u, 0, 0, 0));
                return "ok";
            }
            case "key":
            {
                var vk = Vk(n[0]);
                string mode = n.Length > 1 ? n[1] : "tap";
                if (mode != "up") Send(Key(vk, false));
                if (mode == "tap") Thread.Sleep(50);
                if (mode != "down") Send(Key(vk, true));
                return "ok";
            }
            case "hold": { var vk = Vk(n[0]); Send(Key(vk, false)); Thread.Sleep(int.Parse(n[1])); Send(Key(vk, true)); return "ok"; }
            case "scanmode": scanMode = n.Length > 0 && n[0] == "on"; return "ok";
            case "type":
                foreach (char c in rest)
                {
                    var d = new INPUT(); d.type = 1; d.u.ki.scan = c; d.u.ki.flags = 4;
                    var u = new INPUT(); u.type = 1; u.u.ki.scan = c; u.u.ki.flags = 4 | 2;
                    Send(d, u);
                    Thread.Sleep(10);
                }
                return "ok";
            case "wheel": Send(Mouse(0x0800, unchecked((uint)int.Parse(n[0])), 0, 0)); return "ok";
            case "sleep": Thread.Sleep(int.Parse(n[0])); return "ok";   // a pause inside one drive call (ms); "idle" only reports
            case "idle":
            {
                var li = new LASTINPUTINFO(); li.size = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO));
                GetLastInputInfo(ref li);
                return (unchecked((uint)Environment.TickCount - li.time) / 1000.0).ToString("F1", System.Globalization.CultureInfo.InvariantCulture);
            }
            default: return "error unknown " + a[0];
        }
    }

    public static void Run(string p)
    {
        proc = p.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) ? p.Substring(0, p.Length - 4) : p;
        Console.Out.WriteLine("ready " + (Window() != IntPtr.Zero ? "window" : "no-window"));
        Console.Out.Flush();
        string line;
        while ((line = Console.In.ReadLine()) != null)
        {
            if (line.Trim().Length == 0) continue;
            string reply;
            try { reply = Do(line); } catch (Exception e) { reply = "error " + e.Message; }
            Console.Out.WriteLine(reply);
            Console.Out.Flush();
        }
    }
}
"@

Add-Type -TypeDefinition $src -Language CSharp
[WinDrive]::Run($Proc)
