/* collapsefix: dinput8.dll proxy for Collapse (2008, Creoteam; Steam 289620, collapse.exe PE 2008-10-13).
 *
 * The exe on disk is never touched (LAA is a separate one-bit patcher, laa_patch.exe / .py). The proxy is delay-loaded by
 * the game in WinMain right after Direct3DCreate9 and before the device is created, so on the first
 * DirectInput8Create it hooks:
 *   - IDirect3D9::CreateDevice through the vtable found by creating our own IDirect3D9, and the TestCooperativeLevel /
 *     Present of every device it creates (each device has its own vtable copy, C-57);
 *   - IDirectInput8::CreateDevice (mouse_keeper) and the device's GetProperty (english_keys) and Acquire /
 *     GetDeviceState / GetDeviceData / SetCooperativeLevel (log only), through dinput8's vtables;
 *   - GetTickCount and CreateFileA, through the game's own import table (looked up by name);
 *   - call instructions and branches in memory (fov, ui_scale, nav_guard, release_batches) and the entry of the
 *     allocator's unmap (heap_guard), each found by a byte pattern that must match exactly once.
 * Fixes (ini keys in [fix], 1 = on):
 *   borderless    C-05  fullscreen becomes a windowed device in a popup window over the monitor. In exclusive mode
 *                       every Alt+Tab makes the engine rebuild the device without releasing the old one, which
 *                       other engine resources keep alive (~80-90 MB per Alt+Tab, then "Cannot initialize video");
 *                       a windowed device is never lost, so the rebuild never happens (memory stayed flat). The
 *                       resources were the leaked batch buffers: with release_batches the old device dies.
 *   dpi_aware     C-25  SetProcessDpiAwarenessContext before the game creates its window (the exe has no manifest).
 *   alt_tab       C-05  exclusive mode only: no device is created while the game is in the background (stops the
 *                       re-init loop), a live device is Reset and reused when possible, DEVICELOST is "OK, wait".
 *                       With release_batches the old device is released on each Alt+Tab (84 tested).
 *   display_mode  C-11  a fullscreen Resolution the adapter does not list (CreateDevice 8876086c, endless retry)
 *                       is replaced by the desktop mode.
 *   refresh       C-12  0 = desktop refresh rate (default), -1 = keep the game's choice, N = N Hz if listed.
 *   vsync         C-21  present interval ONE instead of IMMEDIATE (off by default).
 *   timer         C-20  GetTickCount from QueryPerformanceCounter (1 ms steps instead of 15.6 ms).
 *   save_log      C-04  log saves the game failed to create (the engine skips them silently).
 *   fov           C-40/41  0 = the game's FOV, auto = Hor+ for the screen's aspect ratio, N = N degrees horizontal.
 *                       Cutscene cameras are widened by the same factor.
 *   ui_scale      C-42  100 = the game's, auto = fit the resolution, N = N percent: the whole interface grows together.
 *   english_keys  C-53  key names in hints stay English whatever the keyboard layout at launch.
 *   input         C-14  log what DirectInput reports for the mouse and keyboard (changes nothing).
 *   pad_camera_deadzone  C-44  0 = the game's 13.3 %, N = N percent for the right stick (camera).
 *   nav_guard     C-54  a step limit on the navmesh walk (an endless loop in mark_castle).
 *   release_batches  C-55  release the level geometry buffers the renderer drops without releasing on each load.
 *   mouse_keeper  C-56  one extra system mouse device, never released, so dinput8's shared mouse state is never freed.
 *   heap_guard    C-58  the game's allocator gives free memory back to Windows only when all of it can go, and never
 *                       past the segment (a crash on a save load after a partly freed segment).
 * Build: build.ps1 (zig cc, x86-windows-gnu, kernel32 only, no CRT).
 */
#include <windows.h>
#include <d3d9.h>

#define FIX_VERSION "1.0.1"
#define GAME_STAMP 0x48F36777u /* PE TimeDateStamp of the Steam exe (same in the ru and en depots) */
#define MISSING 0x7FFF0123u

typedef HRESULT(WINAPI *DI8Create)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);
typedef IDirect3D9 *(WINAPI *D3DCreate9)(UINT);
typedef HRESULT(WINAPI *CreateDeviceFn)(IDirect3D9 *, UINT, D3DDEVTYPE, HWND, DWORD, D3DPRESENT_PARAMETERS *,
                                        IDirect3DDevice9 **);
typedef HRESULT(WINAPI *TclFn)(IDirect3DDevice9 *);
typedef HRESULT(WINAPI *PresentFn)(IDirect3DDevice9 *, const RECT *, const RECT *, HWND, const RGNDATA *);
typedef DWORD(WINAPI *TickFn)(void);
typedef HANDLE(WINAPI *CreateFileAFn)(LPCSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);

static DI8Create g_real;
static volatile LONG g_once;
static WCHAR g_dir[MAX_PATH], g_ini[MAX_PATH], g_log_path[MAX_PATH];
static HANDLE g_log = INVALID_HANDLE_VALUE;
static int g_log_on;
static volatile LONG g_log_lock;
static int g_alt_tab, g_display_mode, g_refresh, g_vsync, g_save_log;

static CreateDeviceFn o_create_device;
static TclFn o_tcl;
static PresentFn o_present;
static TickFn o_tick;
static CreateFileAFn o_create_file;

/* -nostdlib: the compiler may still emit calls to these */
void *memcpy(void *d, const void *s, unsigned n) {
    unsigned char *a = d;
    const unsigned char *b = s;
    while (n--) *a++ = *b++;
    return d;
}
void *memset(void *d, int c, unsigned n) {
    unsigned char *a = d;
    while (n--) *a++ = (unsigned char)c;
    return d;
}
unsigned wcslen(const unsigned short *s) {
    unsigned n = 0;
    while (s[n]) n++;
    return n;
}
unsigned strlen(const char *s) {
    unsigned n = 0;
    while (s[n]) n++;
    return n;
}
static int streq(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return *a == *b;
}
static int contains_ci(const char *s, const char *sub) { /* ASCII case-insensitive */
    for (; *s; s++) {
        const char *a = s, *b = sub;
        while (*a && *b && ((*a | 32) == (*b | 32))) a++, b++;
        if (!*b) return 1;
    }
    return 0;
}

/* ---- tiny logger (from m2033fix): init block written once, later events appended one line each ---- */
static void put(const char *s) {
    DWORD n = 0, w;
    if (g_log == INVALID_HANDLE_VALUE) return;
    while (s[n]) n++;
    WriteFile(g_log, s, n, &w, NULL);
}
static void put_hex(unsigned v, int digits) {
    char b[11];
    int i;
    b[0] = '0';
    b[1] = 'x';
    for (i = 0; i < digits; i++) b[2 + i] = "0123456789ABCDEF"[(v >> ((digits - 1 - i) * 4)) & 15];
    b[2 + digits] = 0;
    put(b);
}
static void put_dec(unsigned v) {
    char b[12];
    int i = 11;
    b[i] = 0;
    do b[--i] = (char)('0' + v % 10); while (v /= 10);
    put(b + i);
}
static void put_mode(unsigned w, unsigned h, unsigned hz) {
    put_dec(w), put("x"), put_dec(h), put("@"), put_dec(hz);
}
static void path_in_dir(WCHAR *out, const WCHAR *name) {
    int i = 0, j = 0;
    while (g_dir[i] && i < MAX_PATH - 1) out[i] = g_dir[i], i++;
    while (name[j] && i < MAX_PATH - 1) out[i++] = name[j++];
    out[i] = 0;
}
static int ev_begin(void) {
    if (!g_log_on) return 0;
    while (InterlockedCompareExchange(&g_log_lock, 1, 0)) Sleep(0);
    g_log = CreateFileW(g_log_path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    put("[");
    put_dec(GetTickCount());
    put("] ");
    return 1;
}
static void ev_end(void) {
    put("\r\n");
    if (g_log != INVALID_HANDLE_VALUE) {
        CloseHandle(g_log);
        g_log = INVALID_HANDLE_VALUE;
    }
    g_log_lock = 0;
}
static int key_int(const WCHAR *sec, const WCHAR *key, int def) {
    unsigned v = GetPrivateProfileIntW(sec, key, MISSING, g_ini);
    return v == MISSING ? def : (int)v;
}

/* ---- write one pointer (vtable or IAT slot) ---- */
static int put_ptr(void **slot, void *to, void **old) {
    DWORD prot;
    if (!VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &prot)) return 0;
    if (old) *old = *slot;
    *slot = to;
    VirtualProtect(slot, sizeof(void *), prot, &prot);
    return 1;
}
/* C-57: every D3D9 device gets its own copy of the vtable, so a slot is hooked again on each new object. The copies point
   to the same functions; a slot that points elsewhere is left alone, since the hook could not forward it. */
static int vt_hook(void **vt, int i, void *to, void **orig) {
    void *old = vt[i];
    if (old == to) return 1;
    if (*orig && old != *orig) return 0;
    *orig = old; /* before the slot changes: another thread may call through it at once */
    return put_ptr(&vt[i], to, 0);
}

/* ---- C-20: GetTickCount from QPC, continuous with the real value at hook time ---- */
static LARGE_INTEGER g_qf, g_q0;
static DWORD g_t0;
static DWORD WINAPI h_tick(void) {
    LARGE_INTEGER n;
    double ms;
    QueryPerformanceCounter(&n);
    ms = (double)(n.QuadPart - g_q0.QuadPart) * 1000.0 / (double)g_qf.QuadPart;
    return g_t0 + (DWORD)(int)ms; /* int: stays below 2^31 ms (24.8 days); DWORD wrap like the original */
}

/* ---- C-04: with Windows Controlled Folder Access on, the game can't write to Documents at all: no profile, no saves,
   no log, no message. Probe once at start and tell the player how to allow the game. ---- */
static void check_documents_writable(void) {
    typedef HRESULT(WINAPI * GetFolderW)(HWND, int, HANDLE, DWORD, LPWSTR);
    HMODULE sh = LoadLibraryW(L"shell32.dll"), u32 = GetModuleHandleW(L"user32.dll");
    GetFolderW get = sh ? (GetFolderW)GetProcAddress(sh, "SHGetFolderPathW") : 0;
    int(WINAPI * box)(HWND, LPCWSTR, LPCWSTR, UINT) = u32 ? (int(WINAPI *)(HWND, LPCWSTR, LPCWSTR, UINT))GetProcAddress(u32, "MessageBoxW") : 0;
    static const WCHAR tail[] = L"\\Creoteam Collapse\\collapsefix_write_test.tmp";
    WCHAR p[MAX_PATH + 64];
    HANDLE h;
    DWORD err;
    int i, n;
    HRESULT hr;
    if (!get) return;
    hr = get(NULL, 0x8005 /* CSIDL_PERSONAL | CSIDL_FLAG_CREATE, as the game asks */, NULL, 0, p);
    if (hr != S_OK) {
        /* With CFA on the game's own SHGetFolderPathA fails too and it falls back to "<exe path>\Creoteam Collapse",
           a path that can't exist, so every profile, save and log write fails */
        put("C-04 Documents folder not available, SHGetFolderPathW ");
        put_hex((unsigned)hr, 8);
        put(" (Controlled Folder Access?)\r\n");
        err = ERROR_ACCESS_DENIED;
    } else {
        for (n = 0; p[n]; n++) {}
        for (i = 0; tail[i]; i++) p[n + i] = tail[i];
        p[n + i] = 0;
        h = CreateFileW(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, NULL);
        err = GetLastError();
        if (h != INVALID_HANDLE_VALUE) {
            CloseHandle(h);
            put("C-04 Documents\\Creoteam Collapse writable: OK\r\n");
            return;
        }
        put("C-04 Documents\\Creoteam Collapse NOT writable, error ");
        put_dec(err);
        put(err == 5 ? " (access denied: Controlled Folder Access?)\r\n" : "\r\n");
    }
    if (err == ERROR_ACCESS_DENIED && box)
        box(NULL,
            L"Collapse cannot write to your Documents folder, so your profile, saves and settings will not work.\n\n"
            L"This is usually Windows Controlled Folder Access (ransomware protection). To allow the game:\n"
            L"Windows Security > Virus & threat protection > Ransomware protection > Manage ransomware protection >\n"
            L"Allow an app through Controlled folder access > Add an allowed app > collapse.exe\n\n"
            L"(collapsefix; turn this check off with save_log=0 in collapsefix.ini)",
            L"Collapse: saves are blocked", MB_OK | MB_ICONWARNING | MB_SETFOREGROUND);
}

/* ---- C-04: saves the engine fails to create are skipped without a word; say it in our log ---- */
static HANDLE WINAPI h_create_file(LPCSTR name, DWORD acc, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disp,
                                   DWORD flags, HANDLE tmpl) {
    HANDLE h = o_create_file(name, acc, share, sa, disp, flags, tmpl);
    if (h == INVALID_HANDLE_VALUE && (acc & GENERIC_WRITE) && name && contains_ci(name, "creoteam collapse")) {
        DWORD err = GetLastError();
        if (ev_begin()) {
            put(contains_ci(name, "savegame") ? "C-04 save NOT written" : "C-04 game file NOT written");
            put(", CreateFileA error ");
            put_dec(err);
            put(err == 5 ? " (access denied: Controlled Folder Access, antivirus or folder rights?)" : "");
            put(": ");
            put(name);
            ev_end();
        }
        SetLastError(err);
    }
    return h;
}

/* ---- C-05: device loss ---- */
static volatile LONG g_lost;   /* 1 while the real device reports DEVICELOST */
static unsigned g_lost_events;
/* diag (0.1.1): who releases which device, and what is left */
typedef ULONG(WINAPI *ReleaseFn)(IDirect3DDevice9 *);
static ReleaseFn o_release;
static IDirect3DDevice9 *g_dev_prev, *g_dev_cur;
static unsigned g_tcl_calls;
static IDirect3DDevice9 *g_alive[64]; /* devices created and not yet released to 0 */
static void track_add(IDirect3DDevice9 *d) {
    int i;
    for (i = 0; i < 64; i++)
        if (!g_alive[i]) { g_alive[i] = d; return; }
}
static int track_del(IDirect3DDevice9 *d) {
    int i;
    for (i = 0; i < 64; i++)
        if (g_alive[i] == d) { g_alive[i] = 0; return 1; }
    return 0;
}
static unsigned alive_count(void) {
    unsigned i, n = 0;
    for (i = 0; i < 64; i++) n += g_alive[i] != 0;
    return n;
}
static ULONG WINAPI h_release(IDirect3DDevice9 *dev) {
    int cur = dev == g_dev_cur;
    ULONG r = o_release(dev);
    if (r == 0 && track_del(dev) && ev_begin())
        put("diag device "), put_hex((unsigned)(UINT_PTR)dev, 8), put(" destroyed; alive now "), put_dec(alive_count()), ev_end();
    if (!cur && dev != g_dev_prev) return r;
    if (r == 0) { /* destroyed: never touch it again */
        if (cur) g_dev_cur = 0;
        else g_dev_prev = 0;
    }
    return r;
}
static HRESULT WINAPI h_tcl(IDirect3DDevice9 *dev) {
    HRESULT hr = o_tcl(dev);
    g_tcl_calls++;
    if (hr != D3D_OK && hr != D3DERR_DEVICELOST && ev_begin())
        put("TestCooperativeLevel "), put_hex((unsigned)hr, 8), put(" after "), put_dec(g_tcl_calls), put(" calls"), ev_end();
    if (hr == D3DERR_DEVICELOST) {
        if (!g_lost) {
            g_lost = 1;
            g_lost_events++;
            if (ev_begin()) put("C-05 device lost #"), put_dec(g_lost_events), put(": engine told to wait"), ev_end();
        }
        Sleep(15); /* the game keeps spinning its loop while alt-tabbed; give the CPU back */
        return D3D_OK;
    }
    if (g_lost) {
        g_lost = 0;
        if (ev_begin()) {
            put("C-05 device back, TestCooperativeLevel ");
            put_hex((unsigned)hr, 8);
            put(hr == D3DERR_DEVICENOTRESET ? " -> engine resets (releases the old device first)" : "");
            ev_end();
        }
    }
    return hr;
}
static void res_tick(void);
static HRESULT WINAPI h_present(IDirect3DDevice9 *dev, const RECT *a, const RECT *b, HWND w, const RGNDATA *r) {
    HRESULT hr = o_present(dev, a, b, w, r);
    res_tick();
    return (hr == D3DERR_DEVICELOST && g_alt_tab) ? D3D_OK : hr; /* the next TestCooperativeLevel handles it */
}

/* ---- C-40 / C-41: FOV. The projection takes its angle from one engine function that blends the setup FOV (radians,
   the argument) with the cutscene camera's own. Stock is a fixed horizontal angle: Vert- on wide screens, and setup.ini
   loses a hand-written FOV line on the next save. We replace the one call to it: the function runs with the stock angle
   and the tangent of the result is scaled, so gameplay gets exactly the wanted angle and cutscenes widen with it. ---- */
#define FOV_STOCK 1.2870022f /* radians: 73.74 degrees, tan(half) = 0.75, the engine's default */
typedef double(__fastcall *FovFn)(void *, void *, float); /* thiscall: ecx, the float on the stack, st0 back */
static FovFn o_fov;
static int g_fov; /* 0 off, -1 auto, otherwise degrees */
static double g_fov_k = 1.0, g_fov_logged;
static double x87_tan(double a) {
    __asm__("fptan\n\tfstp %%st(0)" : "=t"(a) : "0"(a));
    return a;
}
static double x87_atan(double a) {
    __asm__("fld1\n\tfpatan" : "=t"(a) : "0"(a));
    return a;
}
static double __fastcall h_fov(void *self, void *unused, float setup_fov) {
    double r = o_fov(self, unused, FOV_STOCK);
    (void)setup_fov;
    return 2.0 * x87_atan(x87_tan(r * 0.5) * g_fov_k);
}
static void fov_set_aspect(unsigned w, unsigned h) {
    double k;
    if (g_fov >= 0 || !o_fov || !w || !h) return;
    k = ((double)w / (double)h) * 0.75; /* 4:3 is what the stock angle is right for */
    if (k < 1.0) k = 1.0;
    g_fov_k = k;
    if (k != g_fov_logged && ev_begin()) {
        put("C-41 fov auto: "), put_dec(w), put("x"), put_dec(h), put(" -> ");
        put_dec((unsigned)(int)(x87_atan(0.75 * k) * 360.0 / 3.14159265358979 + 0.5)), put(" degrees horizontal");
        ev_end();
    }
    g_fov_logged = k;
}
/* The one place in .text that fits, or 0 after logging why not. -1 in the pattern is any byte. */
static unsigned char *find_once(const short *pat, unsigned n) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL), *hit = 0;
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_SECTION_HEADER *sec = IMAGE_FIRST_SECTION(nt);
    unsigned char *p = base + sec->VirtualAddress, *end = p + sec->Misc.VirtualSize - n;
    unsigned i, hits = 0;
    for (; p < end; p++) {
        for (i = 0; i < n; i++)
            if (pat[i] >= 0 && p[i] != pat[i]) break;
        if (i == n) hit = p, hits++;
    }
    if (hits == 1) return hit;
    put("SKIP, pattern matched "), put_dec(hits), put(" times\r\n");
    return 0;
}
static void hook_fov(void) {
    /* mov ecx,eax; add ecx,2Ch; call blend; fmul [0.5]; mov eax,10000.0f; mov ecx,esi; fptan */
    static const short pat[] = {0x8B, 0xC8, 0x83, 0xC1, 0x2C, 0xE8, -1, -1, -1, -1, 0xDC, 0x0D, -1, -1, -1, -1,
                                0xB8, 0x00, 0x40, 0x1C, 0x46, 0x8B, 0xCE, 0xD9, 0xF2};
    unsigned char *hit;
    DWORD prot;
    put("C-40 fov (projection call): ");
    hit = find_once(pat, sizeof pat / sizeof pat[0]);
    if (!hit) return;
    if (!VirtualProtect(hit + 6, 4, PAGE_EXECUTE_READWRITE, &prot)) {
        put("SKIP, VirtualProtect failed\r\n");
        return;
    }
    o_fov = (FovFn)(hit + 10 + *(int *)(hit + 6));
    *(int *)(hit + 6) = (int)((unsigned char *)h_fov - (hit + 10));
    VirtualProtect(hit + 6, 4, prot, &prot);
    FlushInstructionCache(GetCurrentProcess(), hit + 6, 4);
    put("OK\r\n");
}

static void patch_rel32(unsigned char *rel, void *to) {
    DWORD prot;
    if (!VirtualProtect(rel, 4, PAGE_EXECUTE_READWRITE, &prot)) return;
    *(int *)rel = (int)((unsigned char *)to - (rel + 4));
    VirtualProtect(rel, 4, prot, &prot);
    FlushInstructionCache(GetCurrentProcess(), rel, 4);
}

/* ---- C-42: small interface. Art and layout are 1:1 in pixels, so it shrinks as screens grow. The interface is told the
   screen is smaller and its projection stretches that back over the real one, so frames, icons, text and their spacing
   grow together. Three things see the size: the scripts (two bindings read it), the projection, and the mouse, which
   comes from window messages in real pixels. 3D rendering keeps the real size. ---- */
#define UI_BASE_W 1152.0f /* chosen in play: 125 percent at 1080p. Stock art is 1:1, no base in the code */
#define UI_BASE_H 864.0f
#define R_RECT 0x1F8 /* renderer: screen rectangle, 4 floats */
typedef void(__fastcall *UiOrthoFn)(void *, void *, void *); /* thiscall: renderer */
typedef void(__cdecl *UiMsgFn)(unsigned, unsigned, unsigned);
static UiOrthoFn o_ui_ortho;
static UiMsgFn o_ui_msg;
static int g_ui_pct; /* 100 off, 0 auto, otherwise percent */
static float *g_ui_rc;
float g_ui_k = 1.0f;
__asm__(".text\n.globl _ui_screen_w\n_ui_screen_w:\n\tflds 0x200(%eax)\n\tfsubs 0x1F8(%eax)\n\tfdivs _g_ui_k\n\tret\n"
        ".globl _ui_screen_h\n_ui_screen_h:\n\tflds 0x204(%eax)\n\tfsubs 0x1FC(%eax)\n\tfdivs _g_ui_k\n\tret\n");
extern void ui_screen_w(void), ui_screen_h(void);
static void __fastcall h_ui_ortho(void *self, void *unused, void *r) {
    float *rc = (float *)((char *)self + R_RECT), right = rc[2], bottom = rc[3];
    g_ui_rc = rc;
    rc[2] = rc[0] + (right - rc[0]) / g_ui_k;
    rc[3] = rc[1] + (bottom - rc[1]) / g_ui_k;
    o_ui_ortho(self, unused, r);
    rc[2] = right;
    rc[3] = bottom;
}
/* The blood overlay and the crosshair group are drawn from inside the interface step and read the rectangle directly. */
static UiOrthoFn o_ui_overlay, o_ui_cursors;
static void ui_call_small(UiOrthoFn fn, void *self, void *unused, void *r) {
    float *rc = g_ui_rc, right, bottom;
    if (!rc) {
        fn(self, unused, r);
        return;
    }
    right = rc[2], bottom = rc[3];
    rc[2] = rc[0] + (right - rc[0]) / g_ui_k;
    rc[3] = rc[1] + (bottom - rc[1]) / g_ui_k;
    fn(self, unused, r);
    rc[2] = right;
    rc[3] = bottom;
}
static void __fastcall h_ui_overlay(void *self, void *unused, void *r) { ui_call_small(o_ui_overlay, self, unused, r); }
static void __fastcall h_ui_cursors(void *self, void *unused, void *r) { ui_call_small(o_ui_cursors, self, unused, r); }
static void __cdecl h_ui_msg(unsigned msg, unsigned wp, unsigned lp) {
    if (msg >= 0x200 && msg <= 0x209) /* WM_MOUSEMOVE .. WM_MBUTTONDBLCLK: lParam is x, y */
        lp = (unsigned)((float)(lp & 0xFFFF) / g_ui_k) | (unsigned)((float)(lp >> 16) / g_ui_k) << 16;
    o_ui_msg(msg, wp, lp);
}
static void ui_set_size(unsigned w, unsigned h) {
    float k, ky;
    if (g_ui_pct == 100 || !o_ui_ortho || !w || !h) return;
    if (g_ui_pct) k = (float)g_ui_pct / 100.0f;
    else {
        k = (float)w / UI_BASE_W;
        ky = (float)h / UI_BASE_H;
        if (ky < k) k = ky;
        if (k < 1.0f) k = 1.0f;
    }
    if (k != g_ui_k && ev_begin()) {
        put("C-42 ui_scale: "), put_dec(w), put("x"), put_dec(h), put(" -> ");
        put_dec((unsigned)(k * 100.0f + 0.5f)), put(" percent, interface sees ");
        put_dec((unsigned)((float)w / k)), put("x"), put_dec((unsigned)((float)h / k));
        ev_end();
    }
    g_ui_k = k;
}
static int patch_screen_binding(const short *pat, unsigned n, void (*to)(void)) {
    unsigned char *hit = find_once(pat, n);
    DWORD prot;
    if (!hit || !VirtualProtect(hit, 12, PAGE_EXECUTE_READWRITE, &prot)) return 0;
    hit[0] = 0xE8;
    *(int *)(hit + 1) = (int)((unsigned char *)to - (hit + 5));
    for (n = 5; n < 12; n++) hit[n] = 0x90;
    VirtualProtect(hit, 12, prot, &prot);
    FlushInstructionCache(GetCurrentProcess(), hit, 12);
    return 1;
}
static void hook_ui_scale(void) {
    /* push esi; mov ecx,app; call rect; mov ecx,eax; call ortho; mov ecx,app; call; mov al,[esp+0Ch]; test al,al */
    static const short ortho_pat[] = {0x56, 0xB9, -1, -1, -1, -1, 0xE8, -1, -1, -1, -1, 0x8B, 0xC8, 0xE8, -1, -1, -1, -1,
                                      0xB9, -1, -1, -1, -1, 0xE8, -1, -1, -1, -1, 0x8A, 0x44, 0x24, 0x0C, 0x84, 0xC0};
    /* push ecx; push edx; push eax; call input; add esp,0Ch; ret 0Ch */
    static const short msg_pat[] = {0x51, 0x52, 0x50, 0xE8, -1, -1, -1, -1, 0x83, 0xC4, 0x0C, 0xC2, 0x0C, 0x00};
    /* fld [eax+200h]; fsub [eax+1F8h]; add eax,1F8h; xor ebx,ebx: the ScreenWidth binding, then ScreenHeight */
    static const short w_pat[] = {0xD9, 0x80, 0x00, 0x02, 0x00, 0x00, 0xD8, 0xA0, 0xF8, 0x01, 0x00, 0x00,
                                  0x05, 0xF8, 0x01, 0x00, 0x00, 0x33, 0xDB};
    static const short h_pat[] = {0xD9, 0x80, 0x04, 0x02, 0x00, 0x00, 0xD8, 0xA0, 0xFC, 0x01, 0x00, 0x00,
                                  0x05, 0xF8, 0x01, 0x00, 0x00, 0x33, 0xDB};
    static const short text_filter[] = {0x6A, 0x01, 0x6A, 0x05, 0x6A, 0x00, 0x8B, 0x08, 0x50, 0xFF, 0x91, 0x14, 0x01, 0x00,
                                        0x00, 0x8B, 0x86, 0x84, 0x04, 0x00, 0x00, 0x6A, 0x01, 0x6A, 0x06, 0x6A, 0x00};
    static const short label_filter[] = {0x6A, 0x01, 0x6A, 0x05, 0x6A, 0x00, 0x8B, 0x10, 0x50, 0xFF, 0x92, 0x14, 0x01, 0x00,
                                         0x00, 0x8B, 0x86, 0x84, 0x04, 0x00, 0x00, 0x6A, 0x01, 0x6A, 0x06, 0x6A, 0x00};
    /* mov eax,[edi+38h]; push ebx; push esi; mov ecx,[eax]; call overlay; push esi; call */
    static const short overlay_pat[] = {0x8B, 0x47, 0x38, 0x53, 0x56, 0x8B, 0x08, 0xE8, -1, -1, -1, -1, 0x56, 0xE8};
    /* mov eax,[edi+38h]; push esi; mov ecx,[eax]; call cursors; pop edi; pop esi; ret */
    static const short cursors_pat[] = {0x8B, 0x47, 0x38, 0x56, 0x8B, 0x08, 0xE8, -1, -1, -1, -1, 0x5F, 0x5E, 0xC3};
    const short *filters[2];
    unsigned char *ortho, *msg, *overlay, *cursors;
    DWORD prot;
    int i;
    put("C-42 ui_scale (projection, mouse, screen size, overlays, filter): ");
    ortho = find_once(ortho_pat, sizeof ortho_pat / sizeof ortho_pat[0]);
    if (!ortho) return;
    msg = find_once(msg_pat, sizeof msg_pat / sizeof msg_pat[0]);
    if (!msg) return;
    overlay = find_once(overlay_pat, sizeof overlay_pat / sizeof overlay_pat[0]);
    if (!overlay) return;
    cursors = find_once(cursors_pat, sizeof cursors_pat / sizeof cursors_pat[0]);
    if (!cursors) return;
    if (!patch_screen_binding(w_pat, sizeof w_pat / sizeof w_pat[0], ui_screen_w)) return;
    if (!patch_screen_binding(h_pat, sizeof h_pat / sizeof h_pat[0], ui_screen_h)) return;
    o_ui_ortho = (UiOrthoFn)(ortho + 18 + *(int *)(ortho + 14));
    patch_rel32(ortho + 14, (void *)h_ui_ortho);
    o_ui_msg = (UiMsgFn)(msg + 8 + *(int *)(msg + 4));
    patch_rel32(msg + 4, (void *)h_ui_msg);
    o_ui_overlay = (UiOrthoFn)(overlay + 12 + *(int *)(overlay + 8));
    patch_rel32(overlay + 8, (void *)h_ui_overlay);
    o_ui_cursors = (UiOrthoFn)(cursors + 11 + *(int *)(cursors + 7));
    patch_rel32(cursors + 7, (void *)h_ui_cursors);
    filters[0] = text_filter, filters[1] = label_filter;
    for (i = 0; i < 2; i++) {
        unsigned char *f = find_once(filters[i], sizeof text_filter / sizeof text_filter[0]);
        if (f && VirtualProtect(f, 23, PAGE_EXECUTE_READWRITE, &prot)) {
            f[1] = 2;
            f[22] = 2;
            VirtualProtect(f, 23, prot, &prot);
            FlushInstructionCache(GetCurrentProcess(), f, 23);
        }
    }
    put("OK\r\n");
}

/* ---- C-14: mouse dead, cursor still on screen, no fix known. The engine re-acquires by itself after a failed read, but
   ignores the result of CreateDevice, SetCooperativeLevel (mouse: exclusive + foreground) and that Acquire. Nothing is
   changed here: the log tells which call fails on a player's machine. One line per change, not per frame. ---- */
typedef HRESULT(WINAPI *DiCreateFn)(void *, REFGUID, void **, void *);
typedef HRESULT(WINAPI *DevFn)(void *);
typedef HRESULT(WINAPI *DevStateFn)(void *, DWORD, void *);
typedef HRESULT(WINAPI *DevDataFn)(void *, DWORD, void *, DWORD *, DWORD);
typedef HRESULT(WINAPI *DevCoopFn)(void *, HWND, DWORD);
static DiCreateFn o_di_create;
static int g_input;
static struct { void **vt; DevFn acquire; DevStateFn state; DevDataFn data; DevCoopFn coop; } g_divt[4];
static struct { void *dev; HRESULT acquire, read; } g_didev[8];
static int di_vt(void *dev) { /* dinput8 shares one vtable today; a table keeps this right if it does not */
    void **vt = *(void ***)dev;
    int i;
    for (i = 0; i < 4; i++)
        if (g_divt[i].vt == vt) return i;
    return -1;
}
static int di_dev(void *dev) {
    int i;
    for (i = 0; i < 8; i++)
        if (g_didev[i].dev == dev) return i;
    for (i = 0; i < 8; i++)
        if (!g_didev[i].dev) {
            g_didev[i].dev = dev;
            return i;
        }
    return 0;
}
static void di_report(void *dev, HRESULT *last, const char *what, HRESULT hr) {
    if (*last == hr) return;
    *last = hr;
    if (ev_begin()) {
        put("C-14 device "), put_hex((unsigned)(UINT_PTR)dev, 8), put(" "), put(what), put(" ");
        put_hex((unsigned)hr, 8);
        ev_end();
    }
}
static HRESULT WINAPI h_di_acquire(void *dev) {
    HRESULT hr = g_divt[di_vt(dev)].acquire(dev);
    di_report(dev, &g_didev[di_dev(dev)].acquire, "Acquire", hr < 0 ? hr : 0);
    return hr;
}
static HRESULT WINAPI h_di_state(void *dev, DWORD cb, void *out) {
    HRESULT hr = g_divt[di_vt(dev)].state(dev, cb, out);
    di_report(dev, &g_didev[di_dev(dev)].read, "GetDeviceState", hr < 0 ? hr : 0);
    return hr;
}
static HRESULT WINAPI h_di_data(void *dev, DWORD cb, void *out, DWORD *n, DWORD flags) {
    HRESULT hr = g_divt[di_vt(dev)].data(dev, cb, out, n, flags);
    di_report(dev, &g_didev[di_dev(dev)].read, "GetDeviceData", hr < 0 ? hr : 0);
    return hr;
}
static HRESULT WINAPI h_di_coop(void *dev, HWND w, DWORD flags) {
    HRESULT hr = g_divt[di_vt(dev)].coop(dev, w, flags);
    if (ev_begin()) {
        put("C-14 device "), put_hex((unsigned)(UINT_PTR)dev, 8), put(" SetCooperativeLevel flags "), put_hex(flags, 2);
        put(" -> "), put_hex((unsigned)hr, 8);
        ev_end();
    }
    return hr;
}
/* C-53: the game builds its key name table once at startup from DirectInput, which names keys by the keyboard layout of
   that moment: "Press у" for E on a Cyrillic layout. Bindings are stored as scan codes, so the names are only shown.
   We answer the name request with the US name for the character keys. */
typedef HRESULT(WINAPI *DevPropFn)(void *, REFGUID, void *);
static DevPropFn o_di_prop;
static int g_english_keys;
static HRESULT WINAPI h_di_prop(void *dev, REFGUID prop, void *hdr) {
    static const char row1[] = "1234567890-=", row2[] = "QWERTYUIOP[]", row3[] = "ASDFGHJKL;'`", row4[] = "\\ZXCVBNM,./";
    HRESULT hr = o_di_prop(dev, prop, hdr);
    if (hr >= 0 && (UINT_PTR)prop == 20 && hdr) { /* DIPROP_KEYNAME: DIPROPHEADER (size, header, offset, how), then the name */
        DWORD *d = (DWORD *)hdr;
        WCHAR *name = (WCHAR *)(d + 4);
        unsigned k = d[2];
        char c = 0;
        if (d[3] == 1) { /* DIPH_BYOFFSET: the offset is the scan code */
            if (k >= 0x02 && k <= 0x0D) c = row1[k - 0x02];
            else if (k >= 0x10 && k <= 0x1B) c = row2[k - 0x10];
            else if (k >= 0x1E && k <= 0x29) c = row3[k - 0x1E];
            else if (k >= 0x2B && k <= 0x35) c = row4[k - 0x2B];
        }
        if (c) {
            name[0] = (WCHAR)(unsigned char)c;
            name[1] = 0;
        }
    }
    return hr;
}
/* C-56: the game releases its mouse device and makes a new one on every scene load. All system mouse devices share one
   state in dinput8 whose table of fields is freed when the last of them is released, while dinput8's own mouse thread
   may be reading that table for a mouse move: a crash inside dinput8 (seen once). One more mouse device, created
   with the game's first and never released, keeps that count above zero. It is never acquired and reads nothing. */
static int g_mouse_keeper;
static void *g_mouse_kept;
static int is_sys_mouse(REFGUID g) {
    static const unsigned char sys_mouse[16] = {0x60, 0x2B, 0x1D, 0x6F, 0xA0, 0xD5, 0xCF, 0x11,
                                                0xBF, 0xC7, 0x44, 0x45, 0x53, 0x54, 0x00, 0x00};
    const unsigned char *p = (const unsigned char *)g;
    int i;
    if (!p) return 0;
    for (i = 0; i < 16; i++)
        if (p[i] != sys_mouse[i]) return 0;
    return 1;
}
static HRESULT WINAPI h_di_create(void *di, REFGUID guid, void **out, void *outer) {
    HRESULT hr = o_di_create(di, guid, out, outer);
    if (hr < 0 && ev_begin()) put("C-14 IDirectInput8::CreateDevice "), put_hex((unsigned)hr, 8), ev_end();
    if (hr >= 0 && g_mouse_keeper && is_sys_mouse(guid)) {
        HRESULT k = o_di_create(di, guid, &g_mouse_kept, 0);
        g_mouse_keeper = 0; /* one try */
        if (ev_begin()) {
            put(k >= 0 ? "C-56 mouse_keeper: OK" : "C-56 mouse_keeper: FAILED ");
            if (k < 0) put_hex((unsigned)k, 8);
            ev_end();
        }
    }
    if (hr >= 0 && out && *out && g_english_keys && !o_di_prop)
        put_ptr(&(*(void ***)*out)[5], (void *)h_di_prop, (void **)&o_di_prop); /* one vtable today: see di_vt */
    if (hr >= 0 && out && *out && g_input && di_vt(*out) < 0) {
        void **vt = *(void ***)*out;
        int i;
        for (i = 0; i < 4 && g_divt[i].vt; i++) {}
        if (i < 4) {
            int ok;
            g_divt[i].vt = vt;
            ok = put_ptr(&vt[7], (void *)h_di_acquire, (void **)&g_divt[i].acquire) &&
                 put_ptr(&vt[9], (void *)h_di_state, (void **)&g_divt[i].state) &&
                 put_ptr(&vt[10], (void *)h_di_data, (void **)&g_divt[i].data) &&
                 put_ptr(&vt[13], (void *)h_di_coop, (void **)&g_divt[i].coop);
            if (ev_begin()) put(ok ? "C-14 input: OK (device vtable)" : "C-14 input: FAILED to hook"), ev_end();
        }
    }
    return hr;
}

/* ---- C-11 / C-12 / C-21: fullscreen mode, refresh rate and present interval ---- */
static int mode_listed(IDirect3D9 *d3d, UINT ad, D3DFORMAT fmt, UINT w, UINT h, UINT hz) {
    UINT i, n = d3d->lpVtbl->GetAdapterModeCount(d3d, ad, fmt);
    D3DDISPLAYMODE m;
    for (i = 0; i < n; i++)
        if (d3d->lpVtbl->EnumAdapterModes(d3d, ad, fmt, i, &m) == D3D_OK && m.Width == w && m.Height == h &&
            (!hz || m.RefreshRate == hz))
            return 1;
    return 0;
}
static int g_borderless, g_borderless_pending;
/* user32, resolved at init (the exe imports it, so it is loaded) */
static LONG(WINAPI *pSetWindowLongW)(HWND, int, LONG);
static BOOL(WINAPI *pSetWindowPos)(HWND, HWND, int, int, int, int, UINT);
static HMONITOR(WINAPI *pMonitorFromWindow)(HWND, DWORD);
static BOOL(WINAPI *pGetMonitorInfoW)(HMONITOR, LPMONITORINFO);
static void make_borderless(HWND w) {
    MONITORINFO mi;
    RECT *r = &mi.rcMonitor;
    if (!w || !pSetWindowLongW || !pSetWindowPos || !pMonitorFromWindow || !pGetMonitorInfoW) return;
    mi.cbSize = sizeof mi;
    if (!pGetMonitorInfoW(pMonitorFromWindow(w, MONITOR_DEFAULTTONEAREST), &mi)) return;
    pSetWindowLongW(w, GWL_EXSTYLE, 0);
    pSetWindowLongW(w, GWL_STYLE, WS_POPUP | WS_VISIBLE);
    pSetWindowPos(w, HWND_TOP, r->left, r->top, r->right - r->left, r->bottom - r->top, SWP_FRAMECHANGED | SWP_SHOWWINDOW);
    if (ev_begin()) {
        put("C-05 borderless window ");
        put_dec((unsigned)(r->right - r->left)), put("x"), put_dec((unsigned)(r->bottom - r->top));
        put(" at "), put_dec((unsigned)r->left), put(","), put_dec((unsigned)r->top);
        ev_end();
    }
}
static void fix_present_params(IDirect3D9 *d3d, UINT ad, D3DPRESENT_PARAMETERS *pp) {
    D3DDISPLAYMODE desk;
    UINT w = pp->BackBufferWidth, h = pp->BackBufferHeight, hz = pp->FullScreen_RefreshRateInHz;
    if (pp->Windowed || d3d->lpVtbl->GetAdapterDisplayMode(d3d, ad, &desk) != D3D_OK) return;
    if (!ev_begin()) g_log = INVALID_HANDLE_VALUE;
    put("CreateDevice fullscreen ");
    put_mode(w, h, hz);
    put(" fmt ");
    put_dec(pp->BackBufferFormat);
    put(", desktop ");
    put_mode(desk.Width, desk.Height, desk.RefreshRate);
    if (g_borderless) { /* C-05 (0.2): no exclusive mode, so Alt+Tab never loses the device and the engine never rebuilds it */
        put("; C-05 borderless: windowed device, popup window over the monitor");
        pp->Windowed = TRUE;
        pp->FullScreen_RefreshRateInHz = 0;
        pp->PresentationInterval = g_vsync ? D3DPRESENT_INTERVAL_ONE : D3DPRESENT_INTERVAL_IMMEDIATE;
        g_borderless_pending = 1;
        if (g_log != INVALID_HANDLE_VALUE) ev_end(); else g_log_lock = 0;
        return;
    }
    if (g_display_mode) {
        if (!d3d->lpVtbl->GetAdapterModeCount(d3d, ad, pp->BackBufferFormat)) {
            put("; C-11 no modes in this format -> X8R8G8B8");
            pp->BackBufferFormat = D3DFMT_X8R8G8B8;
        }
        if (!mode_listed(d3d, ad, pp->BackBufferFormat, w, h, 0)) {
            put("; C-11 mode not listed by the adapter -> desktop mode");
            pp->BackBufferWidth = w = desk.Width;
            pp->BackBufferHeight = h = desk.Height;
            pp->FullScreen_RefreshRateInHz = hz = desk.RefreshRate;
        }
    }
    if (g_refresh >= 0) {
        UINT want = g_refresh ? (UINT)g_refresh : desk.RefreshRate;
        if (want != hz && mode_listed(d3d, ad, pp->BackBufferFormat, w, h, want)) {
            put("; C-12 refresh ");
            put_dec(hz);
            put(" -> ");
            put_dec(want);
            pp->FullScreen_RefreshRateInHz = want;
        }
    }
    if (g_vsync && pp->PresentationInterval != D3DPRESENT_INTERVAL_ONE) {
        put("; C-21 present interval -> ONE (V-Sync)");
        pp->PresentationInterval = D3DPRESENT_INTERVAL_ONE;
    }
    if (g_log != INVALID_HANDLE_VALUE) ev_end(); else g_log_lock = 0;
}
/* ---- C-55 diag: resources alive per kind, to tell a game leak from a driver pool. Sizes are estimates. ---- */
enum { RES_TEX, RES_VOL, RES_CUBE, RES_VB, RES_IB, RES_SURF, RES_KINDS };
#define RES_SLOTS 65536
typedef ULONG(WINAPI *ResRelFn)(void *);
static struct { void *obj; unsigned size; int kind, def; } g_res[RES_SLOTS];
static volatile LONG g_res_lock;
static ResRelFn o_res_rel[RES_KINDS];
static unsigned g_res_live[RES_KINDS], g_res_made[RES_KINDS], g_res_def, g_res_lost;
static unsigned long long g_res_bytes[RES_KINDS];
static int g_d3d_counts;
static DWORD g_res_next;
static void res_lock(void) { while (InterlockedExchange(&g_res_lock, 1)) Sleep(0); }
static unsigned res_hash(void *p) { return ((unsigned)(UINT_PTR)p >> 4) * 2654435761u >> 16; }
static void res_add(void *obj, int kind, int pool, unsigned size) {
    unsigned i = res_hash(obj), n;
    res_lock();
    for (n = 0; n < RES_SLOTS; n++, i = (i + 1) & (RES_SLOTS - 1))
        if (!g_res[i].obj || g_res[i].obj == (void *)1) break;
    if (n == RES_SLOTS) {
        g_res_lost++;
    } else {
        g_res[i].obj = obj, g_res[i].size = size, g_res[i].kind = kind, g_res[i].def = pool == D3DPOOL_DEFAULT;
        g_res_live[kind]++, g_res_made[kind]++, g_res_bytes[kind] += size, g_res_def += pool == D3DPOOL_DEFAULT;
    }
    g_res_lock = 0;
}
static void res_del(void *obj) {
    unsigned i = res_hash(obj), n;
    res_lock();
    for (n = 0; n < RES_SLOTS && g_res[i].obj; n++, i = (i + 1) & (RES_SLOTS - 1))
        if (g_res[i].obj == obj) {
            int k = g_res[i].kind;
            g_res_live[k]--, g_res_bytes[k] -= g_res[i].size, g_res_def -= g_res[i].def;
            g_res[i].obj = (void *)1; /* tombstone */
            break;
        }
    g_res_lock = 0;
}
#define RES_REL(k) static ULONG WINAPI h_res_rel##k(void *o) { ULONG r = o_res_rel[k](o); if (!r) res_del(o); return r; }
RES_REL(0) RES_REL(1) RES_REL(2) RES_REL(3) RES_REL(4) RES_REL(5)
static void *const h_res_rel[RES_KINDS] = {(void *)h_res_rel0, (void *)h_res_rel1, (void *)h_res_rel2,
                                           (void *)h_res_rel3, (void *)h_res_rel4, (void *)h_res_rel5};
static void res_new(HRESULT hr, void **out, int kind, int pool, unsigned size) {
    if (hr != D3D_OK || !out || !*out) return;
    if ((*(void ***)*out)[2] != h_res_rel[kind]) { /* vtables may be per object too, as for devices (C-57) */
        int ok;
        res_lock();
        ok = vt_hook(*(void ***)*out, 2, h_res_rel[kind], (void **)&o_res_rel[kind]);
        g_res_lock = 0;
        if (!ok) { /* its Release is not seen, so it is not counted */
            g_res_lost++;
            return;
        }
    }
    res_add(*out, kind, pool, size);
}
static unsigned res_size(unsigned w, unsigned h, unsigned d, unsigned levels, D3DFORMAT f) {
    unsigned bits = f == D3DFMT_DXT1 ? 4 : (f == D3DFMT_DXT3 || f == D3DFMT_DXT5) ? 8 : 32;
    unsigned s = w * h / 8 * d * bits;
    return levels == 1 ? s : s / 3 * 4;
}
static void res_report(const char *why) {
    static const char *const names[RES_KINDS] = {"tex", "vol", "cube", "vb", "ib", "surf"};
    int k;
    if (!g_d3d_counts || !ev_begin()) return;
    put("C-55 live ("), put(why), put("):");
    for (k = 0; k < RES_KINDS; k++) {
        put(" "), put(names[k]), put(" "), put_dec(g_res_live[k]), put("/"), put_dec(g_res_made[k]);
        put(" "), put_dec((unsigned)(g_res_bytes[k] >> 20)), put("MB");
    }
    put("; default pool "), put_dec(g_res_def), put("; devices "), put_dec(alive_count());
    if (g_res_lost) put("; untracked "), put_dec(g_res_lost);
    ev_end();
}
typedef HRESULT(WINAPI *CTexFn)(void *, UINT, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *CVolFn)(void *, UINT, UINT, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *CCubeFn)(void *, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *CVbFn)(void *, UINT, DWORD, DWORD, D3DPOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *CIbFn)(void *, UINT, DWORD, D3DFORMAT, D3DPOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *CRtFn)(void *, UINT, UINT, D3DFORMAT, D3DMULTISAMPLE_TYPE, DWORD, BOOL, void **, HANDLE *);
typedef HRESULT(WINAPI *COffFn)(void *, UINT, UINT, D3DFORMAT, D3DPOOL, void **, HANDLE *);
static CTexFn o_c_tex;
static CVolFn o_c_vol;
static CCubeFn o_c_cube;
static CVbFn o_c_vb;
static CIbFn o_c_ib;
static CRtFn o_c_rt, o_c_ds;
static COffFn o_c_off;
static HRESULT WINAPI h_c_tex(void *dv, UINT w, UINT h, UINT l, DWORD u, D3DFORMAT f, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_tex(dv, w, h, l, u, f, p, o, s);
    res_new(hr, o, RES_TEX, p, res_size(w, h, 1, l, f));
    return hr;
}
static HRESULT WINAPI h_c_vol(void *dv, UINT w, UINT h, UINT d, UINT l, DWORD u, D3DFORMAT f, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_vol(dv, w, h, d, l, u, f, p, o, s);
    res_new(hr, o, RES_VOL, p, res_size(w, h, d, l, f));
    return hr;
}
static HRESULT WINAPI h_c_cube(void *dv, UINT e, UINT l, DWORD u, D3DFORMAT f, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_cube(dv, e, l, u, f, p, o, s);
    res_new(hr, o, RES_CUBE, p, res_size(e, e, 6, l, f));
    return hr;
}
static HRESULT WINAPI h_c_vb(void *dv, UINT n, DWORD u, DWORD fvf, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_vb(dv, n, u, fvf, p, o, s);
    res_new(hr, o, RES_VB, p, n);
    return hr;
}
static HRESULT WINAPI h_c_ib(void *dv, UINT n, DWORD u, D3DFORMAT f, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_ib(dv, n, u, f, p, o, s);
    res_new(hr, o, RES_IB, p, n);
    return hr;
}
static HRESULT WINAPI h_c_rt(void *dv, UINT w, UINT h, D3DFORMAT f, D3DMULTISAMPLE_TYPE m, DWORD q, BOOL b, void **o, HANDLE *s) {
    HRESULT hr = o_c_rt(dv, w, h, f, m, q, b, o, s);
    res_new(hr, o, RES_SURF, D3DPOOL_DEFAULT, res_size(w, h, 1, 1, f));
    return hr;
}
static HRESULT WINAPI h_c_ds(void *dv, UINT w, UINT h, D3DFORMAT f, D3DMULTISAMPLE_TYPE m, DWORD q, BOOL b, void **o, HANDLE *s) {
    HRESULT hr = o_c_ds(dv, w, h, f, m, q, b, o, s);
    res_new(hr, o, RES_SURF, D3DPOOL_DEFAULT, res_size(w, h, 1, 1, f));
    return hr;
}
static HRESULT WINAPI h_c_off(void *dv, UINT w, UINT h, D3DFORMAT f, D3DPOOL p, void **o, HANDLE *s) {
    HRESULT hr = o_c_off(dv, w, h, f, p, o, s);
    res_new(hr, o, RES_SURF, p, res_size(w, h, 1, 1, f));
    return hr;
}
static void res_tick(void) {
    if (!g_d3d_counts || (int)(GetTickCount() - g_res_next) < 0) return;
    g_res_next = GetTickCount() + 30000;
    res_report("30 s");
}
static int hook_res_counts(void **vt) {
    int ok = vt_hook(vt, 23, (void *)h_c_tex, (void **)&o_c_tex) && vt_hook(vt, 24, (void *)h_c_vol, (void **)&o_c_vol) &&
             vt_hook(vt, 25, (void *)h_c_cube, (void **)&o_c_cube) && vt_hook(vt, 26, (void *)h_c_vb, (void **)&o_c_vb) &&
             vt_hook(vt, 27, (void *)h_c_ib, (void **)&o_c_ib) && vt_hook(vt, 28, (void *)h_c_rt, (void **)&o_c_rt) &&
             vt_hook(vt, 29, (void *)h_c_ds, (void **)&o_c_ds) && vt_hook(vt, 36, (void *)h_c_off, (void **)&o_c_off);
    if (!g_res_next) g_res_next = GetTickCount() + 30000;
    return ok;
}
static void hook_device_vtable(IDirect3DDevice9 *dev) {
    void **vt = *(void ***)dev;
    static unsigned devices;
    devices++;
    if (g_d3d_counts) {
        int ok = hook_res_counts(vt);
        if ((devices == 1 || !ok) && ev_begin()) {
            put(ok ? "C-55 d3d_counts: OK" : "C-55 d3d_counts: FAILED to hook, device #");
            if (!ok) put_dec(devices);
            ev_end();
        }
    }
    if (g_alt_tab) {
        int ok = vt_hook(vt, 3, (void *)h_tcl, (void **)&o_tcl) && vt_hook(vt, 17, (void *)h_present, (void **)&o_present) &&
                 vt_hook(vt, 2, (void *)h_release, (void **)&o_release);
        if ((devices == 1 || !ok) && ev_begin()) {
            put(ok ? "C-05 alt_tab: OK (device TestCooperativeLevel, Present)" : "C-05 alt_tab: FAILED to hook, device #");
            if (!ok) put_dec(devices);
            ev_end();
        }
    }
}
/* C-05 (0.2): logs showed the engine re-running its display init every 1-4 s while the game is in the background;
   each run ends in a successful CreateDevice that replaces the previous device without releasing it (30 devices
   alive after three Alt+Tabs). Two guards: no device is created while the game window is not in front (the engine
   gets DEVICELOST and retries later), and when the previous device is still alive it is Reset and handed back
   instead of creating another one. */
static HWND(WINAPI *pGetForegroundWindow)(void);
static HWND(WINAPI *pGetAncestor)(HWND, UINT);
static unsigned g_deferred, g_reused;
static int game_in_front(HWND wnd) {
    HWND fg;
    if (!wnd || !pGetForegroundWindow || !pGetAncestor) return 1;
    fg = pGetForegroundWindow();
    return fg && pGetAncestor(fg, GA_ROOTOWNER) == pGetAncestor(wnd, GA_ROOTOWNER);
}
static HRESULT WINAPI h_create_device(IDirect3D9 *d3d, UINT ad, D3DDEVTYPE type, HWND wnd, DWORD flags,
                                      D3DPRESENT_PARAMETERS *pp, IDirect3DDevice9 **out) {
    HRESULT hr;
    if (g_alt_tab && g_dev_cur && out && !game_in_front(pp && pp->hDeviceWindow ? pp->hDeviceWindow : wnd)) {
        if (!g_deferred++ && ev_begin()) put("C-05 game not in front: CreateDevice deferred (DEVICELOST to the engine)"), ev_end();
        *out = 0;
        Sleep(50);
        return D3DERR_DEVICELOST;
    }
    if (g_deferred) {
        if (ev_begin()) put("C-05 game back in front after "), put_dec(g_deferred), put(" deferred CreateDevice calls"), ev_end();
        g_deferred = 0;
    }
    if (pp) {
        fix_present_params(d3d, ad, pp);
        fov_set_aspect(pp->BackBufferWidth, pp->BackBufferHeight);
        ui_set_size(pp->BackBufferWidth, pp->BackBufferHeight);
    }
    if (g_alt_tab && g_dev_cur && out && pp) { /* the engine forgot a live device: reuse it */
        D3DPRESENT_PARAMETERS keep = *pp;
        hr = g_dev_cur->lpVtbl->Reset(g_dev_cur, pp);
        if (hr == D3D_OK) {
            g_dev_cur->lpVtbl->AddRef(g_dev_cur);
            *out = g_dev_cur;
            g_reused++;
            if (ev_begin()) put("C-05 live device reused via Reset (#"), put_dec(g_reused), put("), no new device"), ev_end();
            return D3D_OK;
        }
        *pp = keep;
        if (ev_begin()) put("C-05 Reset of the live device failed "), put_hex((unsigned)hr, 8), put(": creating a new one (leaks the old)"), ev_end();
        res_report("Reset failed");
    }
    if (ev_begin()) put("CreateDevice call; devices alive before it: "), put_dec(alive_count()), ev_end();
    hr = o_create_device(d3d, ad, type, wnd, flags, pp, out);
    if (hr != D3D_OK && ev_begin()) put("CreateDevice returned "), put_hex((unsigned)hr, 8), ev_end();
    if (hr == D3D_OK && out && *out) {
        if (g_borderless_pending) make_borderless(pp && pp->hDeviceWindow ? pp->hDeviceWindow : wnd);
        g_borderless_pending = 0;
        hook_device_vtable(*out);
        track_add(*out);
        g_dev_prev = g_dev_cur;
        g_dev_cur = *out;
        if (ev_begin()) put("new device "), put_hex((unsigned)(UINT_PTR)*out, 8), ev_end();
    }
    return hr;
}

/* ---- the game's import table: patch one kernel32 slot by name ---- */
static void **iat_slot(const char *dll, const char *fn) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY *dir = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *d = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir->VirtualAddress);
    if (!dir->VirtualAddress) return 0;
    for (; d->Name; d++) {
        const char *name = (const char *)(base + d->Name);
        IMAGE_THUNK_DATA32 *names, *slots;
        if (!contains_ci(name, dll) || !d->OriginalFirstThunk) continue;
        names = (IMAGE_THUNK_DATA32 *)(base + d->OriginalFirstThunk);
        slots = (IMAGE_THUNK_DATA32 *)(base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++)
            if (!(names->u1.Ordinal & IMAGE_ORDINAL_FLAG32) &&
                streq((const char *)((IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData))->Name, fn))
                return (void **)&slots->u1.Function;
    }
    return 0;
}
static void hook_iat(const char *fn, void *to, void **old, const char *label) {
    void **slot = iat_slot("kernel32", fn);
    put(label);
    if (!slot) put(": SKIP, import not found\r\n");
    else if (!put_ptr(slot, to, old)) put(": SKIP, VirtualProtect failed\r\n");
    else put(": OK\r\n");
}

/* C-44: the camera stick's dead zone is 13.3 % in the game, and worn sticks rest above that, so the camera drifts. We answer
   with a rescaled value: nothing inside the chosen zone, and the game's own curve starts at its edge and still reaches the top. */
#define PAD_STOCK_ZONE 4345 /* the first value the game acts on */
typedef DWORD(WINAPI *XGetStateFn)(DWORD, void *);
static int g_pad_zone;
static int pad_rescale(int v) {
    int a = v < 0 ? -v : v;
    if (a > 32767) a = 32767;
    if (a <= g_pad_zone) return 0;
    a = PAD_STOCK_ZONE + (a - g_pad_zone) * (32767 - PAD_STOCK_ZONE) / (32767 - g_pad_zone); /* under 2^30 */
    return v < 0 ? -a : a;
}
static DWORD WINAPI h_xinput_state(DWORD slot, void *state) {
    static XGetStateFn real;
    DWORD r;
    if (!real) {
        HMODULE m = LoadLibraryA("xinput1_3.dll");
        real = m ? (XGetStateFn)GetProcAddress(m, (LPCSTR)2) : 0;
        if (!real) return ERROR_DEVICE_NOT_CONNECTED;
    }
    r = real(slot, state);
    if (r == 0) { /* XINPUT_STATE: the right stick's X and Y are the last two shorts */
        SHORT *rs = (SHORT *)((unsigned char *)state + 12);
        rs[0] = (SHORT)pad_rescale(rs[0]);
        rs[1] = (SHORT)pad_rescale(rs[1]);
    }
    return r;
}
/* XInput is a delay-load import by ordinal (XInputGetState = 2). The game's old-format table holds addresses, newer linkers
   write offsets. Whole numbers here: adding to a null pointer lets the compiler drop the address case. */
static void hook_pad_zone(void) {
    typedef struct { DWORD attrs, name, module, iat, names, bound, unload, stamp; } Delay;
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    IMAGE_DATA_DIRECTORY *dir = &nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT];
    Delay *d = (Delay *)(base + dir->VirtualAddress);
    put("C-44 pad_camera_deadzone (XInputGetState)");
    if (dir->VirtualAddress) {
        for (; d->name; d++) {
            UINT_PTR off = (d->attrs & 1) ? (UINT_PTR)base : 0;
            DWORD *names, *slots;
            if (!contains_ci((const char *)(off + d->name), "xinput")) continue;
            names = (DWORD *)(off + d->names);
            slots = (DWORD *)(off + d->iat);
            for (; *names; names++, slots++)
                if (*names == (IMAGE_ORDINAL_FLAG32 | 2)) {
                    void *old;
                    put(put_ptr((void **)slots, (void *)h_xinput_state, &old) ? ": OK\r\n" : ": SKIP, VirtualProtect failed\r\n");
                    return;
                }
        }
    }
    put(": SKIP, import not found\r\n");
}

/* C-54: the walk over slope triangles in the navmesh collision follows neighbours with no step limit, and mark_castle's
   navmesh has a ring of seven, so a query from the wrong point spins forever. The branch back to the next triangle goes
   through here; past the limit the walk leaves by the same exit as a mesh border, and the move simply fails. */
#define NAV_STEP_CAP 100000u
#define NAV_GAP (1ull << 24) /* cycles between steps that mean a new query, some milliseconds */
__attribute__((used)) void *g_nav_next, *g_nav_exit;
static unsigned g_nav_steps, g_nav_trips;
static unsigned long long g_nav_last;
__attribute__((used)) int __cdecl nav_step(void) {
    unsigned long long now;
    __asm__ volatile("rdtsc" : "=A"(now));
    if (now - g_nav_last > NAV_GAP) g_nav_steps = 0;
    g_nav_last = now;
    if (++g_nav_steps <= NAV_STEP_CAP) return 0;
    g_nav_steps = 0;
    if (++g_nav_trips <= 20 && ev_begin()) put("C-54 navmesh walk stopped at the step limit, #"), put_dec(g_nav_trips), ev_end();
    return 1;
}
void h_nav_step(void);
__asm__(".text\n_h_nav_step:\n"
        "  pushal\n  call _nav_step\n  testl %eax, %eax\n  popal\n"
        "  jne 1f\n  jmp *_g_nav_next\n1:\n  jmp *_g_nav_exit\n");
static void hook_nav_guard(void) {
    /* je <mesh border>; mov eax,55555556h; mov [..],ebx; imul ebx ... test byte [edx+ecx*4],1; jne <next triangle> */
    static const short pat[] = {0x0F, 0x84, -1, -1, -1, -1, 0xB8, 0x56, 0x55, 0x55, 0x55, 0x89, 0x9C, 0x24, -1, -1, -1, -1,
                                0xF7, 0xEB, 0x8B, 0xCA, 0x8B, 0x94, 0x24, -1, -1, -1, -1, 0x8B, 0xC1, 0xC1, 0xE8, 0x1F,
                                0x03, 0xC8, 0x89, 0x8C, 0x24, -1, -1, -1, -1, 0xF6, 0x04, 0x8A, 0x01, 0x0F, 0x85, -1, -1, -1, -1};
    unsigned char *hit;
    put("C-54 nav_guard (navmesh walk): ");
    hit = find_once(pat, sizeof pat / sizeof pat[0]);
    if (!hit) return;
    g_nav_exit = hit + 6 + *(int *)(hit + 2);
    g_nav_next = hit + 53 + *(int *)(hit + 49);
    patch_rel32(hit + 49, (void *)h_nav_step);
    put("OK\r\n");
}

/* C-55: the renderer packs level meshes into batches of up to 65000 vertices, each with its own vertex and index buffer
   in a record of five words. The two places that drop the batch array, the rebuild at renderer init and the teardown,
   free it without releasing those buffers, so every level load keeps the previous level's geometry in video memory and
   the address space. Both free it through one call with the renderer in esi; that call goes through here first. */
#define R_BATCH_N 0x24
#define R_BATCHES 0x28
struct batch { void *format; IUnknown *vb, *ib; int verts, indices; };
__attribute__((used)) void *g_batch_free;
static unsigned g_batch_calls;
__attribute__((used)) void __cdecl batch_release(unsigned char *r) {
    struct batch *b = *(struct batch **)(r + R_BATCHES);
    int n = *(int *)(r + R_BATCH_N), i;
    unsigned vb = 0, ib = 0;
    if (!b || n <= 0) return;
    for (i = 0; i < n; i++) {
        if (b[i].vb) b[i].vb->lpVtbl->Release(b[i].vb), b[i].vb = 0, vb++;
        if (b[i].ib) b[i].ib->lpVtbl->Release(b[i].ib), b[i].ib = 0, ib++;
    }
    if (++g_batch_calls <= 50 && ev_begin())
        put("C-55 batches dropped: released "), put_dec(vb), put(" vertex and "), put_dec(ib), put(" index buffers"), ev_end();
}
void h_batch_free(void);
__asm__(".text\n_h_batch_free:\n"
        "  pushal\n  pushl %esi\n  call _batch_release\n  addl $4, %esp\n  popal\n"
        "  jmp *_g_batch_free\n");
static void hook_batch_release(void) {
    /* mov edx,[esi+28h]; push edx; call free; add esp,4; mov [esi+28h],0; mov ecx,esi; mov [esi+24h],0; call build */
    static const short init[] = {0x8B, 0x56, 0x28, 0x52, 0xE8, -1, -1, -1, -1, 0x83, 0xC4, 0x04, 0xC7, 0x46, 0x28, 0, 0, 0, 0,
                                 0x8B, 0xCE, 0xC7, 0x46, 0x24, 0, 0, 0, 0, 0xE8};
    /* mov eax,[esi+28h]; push eax; call free; mov [esi+28h],ebp; mov [esi+24h],ebp */
    static const short down[] = {0x8B, 0x46, 0x28, 0x50, 0xE8, -1, -1, -1, -1, 0x89, 0x6E, 0x28, 0x89, 0x6E, 0x24};
    unsigned char *a, *b;
    put("C-55 release_batches (renderer init): ");
    if (!(a = find_once(init, sizeof init / sizeof init[0]))) return;
    put("found; teardown: ");
    if (!(b = find_once(down, sizeof down / sizeof down[0]))) return;
    if (a + 9 + *(int *)(a + 5) != b + 9 + *(int *)(b + 5)) {
        put("SKIP, the two calls free through different functions\r\n");
        return;
    }
    g_batch_free = a + 9 + *(int *)(a + 5);
    patch_rel32(a + 5, (void *)h_batch_free);
    patch_rel32(b + 5, (void *)h_batch_free);
    put("OK\r\n");
}

/* C-58: the game's allocator hands a fully free segment back to Windows through its own unmap(res, p, n), which walks
   the range region by region: pages inside the init_heap reservation (*res) are decommitted, other allocations must be
   committed, start at their region and fit, and are released. It acts as it goes, so a check that fails on a later
   region returns -1 with the start already gone; the allocator then puts the chunk back into its tree and writes into
   memory it no longer has. A decommit takes the whole region VirtualQuery reports, which may run past the segment into
   a neighbour's pages, and the unsigned count then wraps and the walk goes on. The replacement checks the whole range
   first, keeps every step inside it, and frees only when all of it can go; otherwise it returns -1 with nothing freed,
   which the allocator handles by keeping the segment. */
static unsigned g_unmap_calls, g_unmap_notes;
static void unmap_note(const char *what, void *p, unsigned n, MEMORY_BASIC_INFORMATION *m) {
    if (++g_unmap_notes > 50 || !ev_begin()) return;
    put("C-58 unmap "), put_hex((unsigned)p, 8), put(" size "), put_hex(n, 8), put(": "), put(what);
    if (m)
        put(", region "), put_hex((unsigned)m->BaseAddress, 8), put(" size "), put_hex(m->RegionSize, 8), put(" alloc "),
            put_hex((unsigned)m->AllocationBase, 8), put(" state "), put_hex(m->State, 5);
    ev_end();
}
/* One step of the walk from q with left bytes to go: how many bytes it covers and whether they are the reservation's
   (decommit) or a whole allocation of their own (release). 0 means the range cannot be freed. */
static unsigned unmap_step(void *res, unsigned char *q, unsigned left, int *decommit, MEMORY_BASIC_INFORMATION *m) {
    unsigned char *end;
    if (!VirtualQuery(q, m, sizeof *m) || (unsigned char *)m->BaseAddress != q) return 0;
    if (m->AllocationBase == res) {
        *decommit = 1;
        return m->RegionSize < left ? m->RegionSize : left;
    }
    *decommit = 0;
    if (m->AllocationBase != q || m->State != MEM_COMMIT) return 0;
    for (end = q + m->RegionSize;; end += m->RegionSize) { /* MEM_RELEASE frees the whole allocation */
        if ((unsigned)(end - q) > left) return 0;
        if (!VirtualQuery(end, m, sizeof *m) || m->AllocationBase != q) break;
    }
    return end - q;
}
__attribute__((used)) int __cdecl game_unmap(void **res, unsigned char *p, unsigned n) {
    MEMORY_BASIC_INFORMATION m;
    unsigned char *q;
    unsigned left, step;
    int dec;
    for (q = p, left = n; left; q += step, left -= step) {
        if (!(step = unmap_step(*res, q, left, &dec, &m))) {
            unmap_note("kept, a region cannot be freed whole", p, n, &m);
            return -1;
        }
        if (dec && m.RegionSize > left) unmap_note("decommit kept to the segment (the game's would run past it)", p, n, &m);
    }
    for (q = p, left = n; left; q += step, left -= step) {
        step = unmap_step(*res, q, left, &dec, &m);
        if (!step) break; /* cannot happen under the allocator's lock; what is left stays mapped and unused */
        if (dec ? !VirtualFree(q, step, MEM_DECOMMIT) : !VirtualFree(q, 0, MEM_RELEASE)) {
            unmap_note("VirtualFree failed, the rest stays mapped", q, left, &m);
            break;
        }
    }
    if (++g_unmap_calls <= 3) unmap_note("OK", p, n, 0);
    return 0;
}
static void hook_heap_guard(void) {
    /* sub esp,1Ch; push ebx; mov ebx,[esp+2Ch]; push ebp; push esi; mov esi,[esp+30h]; push edi; test ebx,ebx; je ..;
       mov ebp,[VirtualQuery]; mov edi,[VirtualFree]; lea eax,[esp+10h]; push 1Ch; push eax; push esi; call ebp;
       test eax,eax; je ..; mov ecx,[esp+30h]; mov eax,[esp+14h]; cmp eax,[ecx]; jne ..; ... push 4000h (MEM_DECOMMIT) */
    static const short pat[] = {0x83, 0xEC, 0x1C, 0x53, 0x8B, 0x5C, 0x24, 0x2C, 0x55, 0x56, 0x8B, 0x74, 0x24, 0x30, 0x57,
                                0x85, 0xDB, 0x74, -1, 0x8B, 0x2D, -1, -1, -1, -1, 0x8B, 0x3D, -1, -1, -1, -1, 0x8D, 0x44,
                                0x24, 0x10, 0x6A, 0x1C, 0x50, 0x56, 0xFF, 0xD5, 0x85, 0xC0, 0x74, -1, 0x8B, 0x4C, 0x24,
                                0x30, 0x8B, 0x44, 0x24, 0x14, 0x3B, 0x01, 0x75, -1, 0x8B, 0x54, 0x24, 0x1C, 0x68, 0x00,
                                0x40, 0x00, 0x00};
    unsigned char *hit;
    DWORD prot;
    put("C-58 heap_guard (allocator unmap): ");
    if (!(hit = find_once(pat, sizeof pat / sizeof pat[0]))) return;
    if (!VirtualProtect(hit, 5, PAGE_EXECUTE_READWRITE, &prot)) {
        put("SKIP, VirtualProtect failed\r\n");
        return;
    }
    *(int *)(hit + 1) = (int)((unsigned char *)game_unmap - (hit + 5)); /* jmp, written before the opcode */
    hit[0] = 0xE9;
    VirtualProtect(hit, 5, prot, &prot);
    FlushInstructionCache(GetCurrentProcess(), hit, 5);
    put("OK\r\n");
}

static int game_is_expected(void) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    put("exe: TimeDateStamp ");
    put_hex(nt->FileHeader.TimeDateStamp, 8);
    put(", Characteristics ");
    put_hex(nt->FileHeader.Characteristics, 4);
    put(nt->FileHeader.Characteristics & IMAGE_FILE_LARGE_ADDRESS_AWARE ? " (LAA)" : " (no LAA: run laa_patch.exe)");
    if (nt->FileHeader.TimeDateStamp != GAME_STAMP) {
        put("\r\nnot the expected Collapse exe: no fixes, plain dinput8 proxy\r\n");
        return 0;
    }
    put("\r\n");
    return 1;
}

static void hook_d3d9(void) {
    HMODULE d3d9 = GetModuleHandleW(L"d3d9.dll");
    D3DCreate9 create;
    IDirect3D9 *d3d;
    if (!d3d9) d3d9 = LoadLibraryW(L"d3d9.dll");
    create = d3d9 ? (D3DCreate9)GetProcAddress(d3d9, "Direct3DCreate9") : 0;
    d3d = create ? create(0x1F) : 0; /* the SDK version the game asks for */
    put("IDirect3D9::CreateDevice");
    if (!d3d) {
        put(": SKIP, Direct3DCreate9 failed\r\n");
        return;
    }
    put(put_ptr((void **)&d3d->lpVtbl->CreateDevice, (void *)h_create_device, (void **)&o_create_device)
            ? ": OK (vtable shared by d3d9.dll)\r\n"
            : ": SKIP, VirtualProtect failed\r\n");
    d3d->lpVtbl->Release(d3d);
}

/* C-25: the exe has no manifest, so at 125 % Windows scaling its window is bitmap-stretched (blurry, wrong size for a
   borderless window). Declare DPI awareness before the game creates windows; report windows that already exist. */
static unsigned g_own_windows;
static BOOL CALLBACK count_own(HWND w, LPARAM lp) {
    DWORD pid = 0;
    DWORD(WINAPI * gwtp)(HWND, LPDWORD) = (DWORD(WINAPI *)(HWND, LPDWORD))lp;
    gwtp(w, &pid);
    if (pid == GetCurrentProcessId()) g_own_windows++;
    return TRUE;
}
static void set_dpi_aware(HMODULE u32) {
    BOOL(WINAPI * ctx)(HANDLE) = (BOOL(WINAPI *)(HANDLE))GetProcAddress(u32, "SetProcessDpiAwarenessContext");
    BOOL(WINAPI * old)(void) = (BOOL(WINAPI *)(void))GetProcAddress(u32, "SetProcessDPIAware");
    BOOL(WINAPI * enumw)(WNDENUMPROC, LPARAM) = (BOOL(WINAPI *)(WNDENUMPROC, LPARAM))GetProcAddress(u32, "EnumWindows");
    void *gwtp = (void *)GetProcAddress(u32, "GetWindowThreadProcessId");
    BOOL ok = FALSE;
    if (enumw && gwtp) enumw(count_own, (LPARAM)gwtp);
    if (ctx) ok = ctx((HANDLE)-4); /* DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 */
    if (!ok && old) ok = old();
    put("C-25 dpi_aware: ");
    put(ok ? "OK" : "FAILED");
    put(", game windows already open: ");
    put_dec(g_own_windows);
    put(g_own_windows ? " (they stay DPI-unaware)\r\n" : "\r\n");
}

static void init_once(void) {
    WCHAR sys[MAX_PATH];
    unsigned i, n;
    g_log_on = key_int(L"log", L"enabled", 1);
    if (g_log_on)
        g_log = CreateFileW(g_log_path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    put("collapsefix " FIX_VERSION ", first DirectInput8Create, tick ");
    put_dec(GetTickCount());
    put("\r\n");

    n = GetSystemDirectoryW(sys, MAX_PATH - 16);
    if (n && n < MAX_PATH - 16) {
        static const WCHAR tail[] = L"\\dinput8.dll";
        for (i = 0; tail[i]; i++) sys[n + i] = tail[i];
        sys[n + i] = 0;
        g_real = (DI8Create)GetProcAddress(LoadLibraryW(sys), "DirectInput8Create");
    }
    put(g_real ? "system dinput8: ok\r\n" : "system dinput8: FAILED, input will not work\r\n");

    if (game_is_expected()) {
        HMODULE u32 = GetModuleHandleW(L"user32.dll");
        if (u32) {
            pGetForegroundWindow = (HWND(WINAPI *)(void))GetProcAddress(u32, "GetForegroundWindow");
            pGetAncestor = (HWND(WINAPI *)(HWND, UINT))GetProcAddress(u32, "GetAncestor");
            pSetWindowLongW = (LONG(WINAPI *)(HWND, int, LONG))GetProcAddress(u32, "SetWindowLongW");
            pSetWindowPos = (BOOL(WINAPI *)(HWND, HWND, int, int, int, int, UINT))GetProcAddress(u32, "SetWindowPos");
            pMonitorFromWindow = (HMONITOR(WINAPI *)(HWND, DWORD))GetProcAddress(u32, "MonitorFromWindow");
            pGetMonitorInfoW = (BOOL(WINAPI *)(HMONITOR, LPMONITORINFO))GetProcAddress(u32, "GetMonitorInfoW");
        }
        if (key_int(L"fix", L"dpi_aware", 1) && u32) set_dpi_aware(u32);
        g_borderless = key_int(L"fix", L"borderless", 1);
        put("ini: borderless="), put_dec(g_borderless), put("\r\n");
        if (key_int(L"fix", L"nav_guard", 1)) hook_nav_guard();
        if (key_int(L"fix", L"release_batches", 1)) hook_batch_release();
        if (key_int(L"fix", L"heap_guard", 1)) hook_heap_guard();
        g_d3d_counts = key_int(L"log", L"d3d_counts", 0);
        g_alt_tab = key_int(L"fix", L"alt_tab", 1);
        g_display_mode = key_int(L"fix", L"display_mode", 1);
        g_refresh = key_int(L"fix", L"refresh", 0);
        g_vsync = key_int(L"fix", L"vsync", 0);
        g_save_log = key_int(L"fix", L"save_log", 1);
        put("ini: alt_tab=");
        put_dec(g_alt_tab), put(" display_mode="), put_dec(g_display_mode), put(" refresh=");
        if (g_refresh < 0) put("game"); else put_dec((unsigned)g_refresh);
        put(" vsync="), put_dec(g_vsync), put(" timer="), put_dec(key_int(L"fix", L"timer", 1));
        put(" save_log="), put_dec(g_save_log), put("\r\n");
        {
            WCHAR v[16];
            int j;
            GetPrivateProfileStringW(L"fix", L"fov", L"auto", v, 16, g_ini);
            if ((v[0] | 32) == 'a') g_fov = -1;
            else for (j = 0; v[j] >= '0' && v[j] <= '9' && g_fov < 1000; j++) g_fov = g_fov * 10 + (v[j] - '0');
            if (g_fov > 0 && (g_fov < 40 || g_fov > 150)) {
                put("ini: fov out of range 40..150, ignored\r\n");
                g_fov = 0;
            }
            put("ini: fov=");
            if (g_fov < 0) put("auto"); else put_dec((unsigned)g_fov);
            g_input = key_int(L"fix", L"input", 1);
            g_english_keys = key_int(L"fix", L"english_keys", 1);
            g_mouse_keeper = key_int(L"fix", L"mouse_keeper", 1);
            put(" input="), put_dec(g_input), put(" english_keys="), put_dec(g_english_keys), put("\r\n");
            if (g_fov) {
                hook_fov();
                if (g_fov > 0) g_fov_k = x87_tan((double)g_fov * 3.14159265358979 / 360.0) / 0.75;
            }
        }
        {
            WCHAR v[16];
            int j;
            GetPrivateProfileStringW(L"fix", L"ui_scale", L"auto", v, 16, g_ini);
            for (j = 0; v[j] >= '0' && v[j] <= '9' && g_ui_pct < 1000; j++) g_ui_pct = g_ui_pct * 10 + (v[j] - '0');
            if (g_ui_pct && (g_ui_pct < 100 || g_ui_pct > 400)) {
                put("ini: ui_scale out of range 100..400, ignored\r\n");
                g_ui_pct = 100;
            }
            put("ini: ui_scale=");
            if (!g_ui_pct) put("auto"); else put_dec((unsigned)g_ui_pct);
            put("\r\n");
            if (g_ui_pct != 100) hook_ui_scale();
        }
        {
            int pct = key_int(L"fix", L"pad_camera_deadzone", 0);
            if (pct < 0 || pct > 90) {
                put("ini: pad_camera_deadzone out of range 0..90, ignored\r\n");
                pct = 0;
            }
            put("ini: pad_camera_deadzone="), put_dec((unsigned)pct), put("\r\n");
            if (pct) {
                g_pad_zone = 32767 * pct / 100;
                hook_pad_zone();
            }
        }
        if (g_borderless || g_d3d_counts || g_alt_tab || g_display_mode || g_refresh >= 0 || g_vsync || g_fov < 0 ||
            g_ui_pct != 100)
            hook_d3d9();
        if (key_int(L"fix", L"timer", 1)) {
            QueryPerformanceFrequency(&g_qf);
            g_t0 = GetTickCount();
            QueryPerformanceCounter(&g_q0);
            if (g_qf.QuadPart) hook_iat("GetTickCount", (void *)h_tick, (void **)&o_tick, "C-20 timer (GetTickCount <- QPC)");
        }
        if (g_save_log) {
            hook_iat("CreateFileA", (void *)h_create_file, (void **)&o_create_file, "C-04 save_log (CreateFileA)");
            check_documents_writable();
        }
    }
    if (g_log != INVALID_HANDLE_VALUE) {
        CloseHandle(g_log);
        g_log = INVALID_HANDLE_VALUE;
    }
}

/* exported (undecorated) through dinput8.def */
HRESULT WINAPI DirectInput8Create(HINSTANCE hinst, DWORD ver, REFIID riid, LPVOID *out, LPUNKNOWN outer) {
    if (InterlockedCompareExchange(&g_once, 1, 0) == 0) {
        init_once();
        g_once = 2;
    } else {
        while (g_once != 2) Sleep(0);
    }
    if (!g_real) return E_FAIL;
    {
        HRESULT hr = g_real(hinst, ver, riid, out, outer);
        if (hr >= 0 && (g_input || g_english_keys || g_mouse_keeper) && !o_di_create && out && *out)
            put_ptr(&(*(void ***)*out)[3], (void *)h_di_create, (void **)&o_di_create);
        return hr;
    }
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) { /* loader lock: paths only */
        int i;
        DisableThreadLibraryCalls(h);
        i = (int)GetModuleFileNameW(h, g_dir, MAX_PATH);
        while (i > 0 && g_dir[i - 1] != L'\\') i--;
        g_dir[i] = 0;
        path_in_dir(g_ini, L"collapsefix.ini");
        path_in_dir(g_log_path, L"collapsefix.log");
    }
    return TRUE;
}
