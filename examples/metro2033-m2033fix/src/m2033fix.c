/* m2033fix: dinput8.dll proxy for the original Metro 2033 (2010, Steam 43110, metro2033.exe 1.0.0.1).
 *
 * The exe on disk is never touched. On the game's first DirectInput8Create call (after SteamStub has
 * decrypted .text) the proxy checks the exe identity and the exact bytes at each site, applies the enabled
 * in-memory patches, then forwards to the system dinput8.dll. Any mismatch skips that patch (vanilla).
 * One patch (P12) must beat the first user.cfg read (~1.95 s), so a watcher thread started in DllMain applies it as
 * soon as SteamStub has decrypted its bytes.
 * Mechanism, patch list, verification and rollback: README.md.
 * Groups (ini sections): [core] P1 P11 P12, [compat] P4 P5 P10 P13 P14, [perf] P8 (+P9), [research] P17.
 * A key is looked up in its section, then in the old [fix] section, so 0.2/0.3 ini files keep working; keys that
 * are new in 0.4 default to off when an old ini does not have them.
 * Build: build.ps1 (zig cc, x86-windows-gnu, kernel32 only, no CRT; user32 is resolved at run time).
 */
#include <windows.h>

typedef HRESULT(WINAPI *DI8Create)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);

#define GAME_BASE 0x00400000u
#define GAME_SIZE 0x00B64000u
#define GAME_STAMP 0x4C7775B7u
#define MISSING 0x7FFF0123u /* GetPrivateProfileIntW default that means "key not there" */

static HMODULE g_self;
static DI8Create g_real;
static volatile LONG g_once;
static WCHAR g_dir[MAX_PATH]; /* folder of this DLL (the game folder), with trailing backslash */
static WCHAR g_ini[MAX_PATH], g_log_path[MAX_PATH];
static HANDLE g_log = INVALID_HANDLE_VALUE;
static int g_log_on;
static volatile LONG g_log_lock;

/* user32, resolved in init_once (the game has a window by then) */
static HWND(WINAPI *pGetForegroundWindow)(void);
static BOOL(WINAPI *pIsIconic)(HWND);
static int(WINAPI *pGetSystemMetrics)(int);

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
unsigned strlen(const char *s) {
    unsigned n = 0;
    while (s[n]) n++;
    return n;
}
static int same(const unsigned char *a, const unsigned char *b, unsigned n) {
    while (n--)
        if (*a++ != *b++) return 0;
    return 1;
}

/* ---- tiny logger: the init log is written once; later events (P10, P11, P14, P17) append one line each ---- */
static void put(const char *s) {
    DWORD n = 0, w;
    if (g_log == INVALID_HANDLE_VALUE) return;
    while (s[n]) n++;
    WriteFile(g_log, s, n, &w, NULL);
}
static void put_n(const char *s, unsigned max) { /* game strings: stop at max chars */
    char b[2] = {0, 0};
    while (s && *s && max--) b[0] = *s++, put(b);
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
static void put_bytes(const unsigned char *p, unsigned n) {
    unsigned i;
    char b[4];
    for (i = 0; i < n; i++) {
        b[0] = "0123456789ABCDEF"[p[i] >> 4];
        b[1] = "0123456789ABCDEF"[p[i] & 15];
        b[2] = i + 1 < n ? ' ' : 0;
        b[3] = 0;
        put(b);
    }
}
static void path_in_dir(WCHAR *out, const WCHAR *name) {
    int i = 0, j = 0;
    while (g_dir[i] && i < MAX_PATH - 1) out[i] = g_dir[i], i++;
    while (name[j] && i < MAX_PATH - 1) out[i++] = name[j++];
    out[i] = 0;
}
static unsigned ms_since_start(void) {
    FILETIME c, e, k, u, now;
    ULARGE_INTEGER a, b;
    if (!GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &u)) return 0;
    GetSystemTimeAsFileTime(&now);
    a.LowPart = c.dwLowDateTime, a.HighPart = c.dwHighDateTime;
    b.LowPart = now.dwLowDateTime, b.HighPart = now.dwHighDateTime;
    b.QuadPart -= a.QuadPart; /* 100 ns units; below 429 s 32 bits are enough */
    return b.HighPart ? 0xFFFFFFFFu : b.LowPart / 10000; /* 32-bit division: no CRT helper */
}
/* run-time event line: "[12345 ms] text..." appended to m2033fix.log; any thread */
static int ev_begin(void) {
    if (!g_log_on) return 0;
    while (InterlockedCompareExchange(&g_log_lock, 1, 0)) Sleep(0);
    g_log = CreateFileW(g_log_path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    put("[");
    put_dec(ms_since_start());
    put(" ms] ");
    return 1;
}
static void ev_end(void) {
    put("\r\n");
    if (g_log != INVALID_HANDLE_VALUE) {
        FlushFileBuffers(g_log);
        CloseHandle(g_log);
        g_log = INVALID_HANDLE_VALUE;
    }
    g_log_lock = 0;
}

/* ---- ini: section first, then the 0.2/0.3 [fix] section, then the default ---- */
static int key_int(const WCHAR *sec, const WCHAR *key, int def) {
    unsigned v = GetPrivateProfileIntW(sec, key, MISSING, g_ini);
    if (v == MISSING) v = GetPrivateProfileIntW(L"fix", key, MISSING, g_ini);
    return v == MISSING ? def : (int)v;
}

/* ---- patches ---- */
typedef struct {
    const char *id;
    const WCHAR *sec; /* m2033fix.ini section (0.4); [fix] is the fallback */
    const WCHAR *key;
    int def;          /* default when the ini has no value */
    unsigned addr;
    unsigned len;
    unsigned char expect[16];
    unsigned char repl[16];
    int group; /* nonzero: every part with this group is applied, or none of them is */
} Patch;

static const Patch g_patches[] = {
    /* P1: text-language switch at 0x85B090: drop "mov [0xA14F88],0 ; call 0x40C060" so the charmap global is
       replaced in one store at 0x85B0C2 and the old table stays valid for concurrent readers (leaks once). */
    {"P1 lang_switch_race", L"core", L"lang_switch_race", 1, 0x0085B0A8, 15,
     {0xC7, 0x05, 0x88, 0x4F, 0xA1, 0x00, 0x00, 0x00, 0x00, 0x00, 0xE8, 0xA9, 0x0F, 0xBB, 0xFF},
     {0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90}, 0},
    /* P2 (exit-time charmap free, never proven) and P3 (save mouse_inertion, convenience) were dropped in 0.2;
       README.md says what they did and why they went. */
    /* P4: 0x7A1F17 lists display modes with IDXGIOutput::GetDisplayModeList(fmt, DXGI_ENUM_MODES_SCALING)
       into a stack buffer of 512 DXGI_MODE_DESC (28 B). Raise it to 1024, byte for byte as the GOG build does:
       frame size for _alloca_probe, the buffer for the call, the capacity, the buffer for the copy loop.
       Nothing else in the function touches the buffer. All four parts or none. */
    {"P4 display_modes_1024 frame", L"compat", L"display_modes_1024", 1, 0x007A1F1A, 5,
     {0xB8, 0x40, 0x38, 0x00, 0x00}, {0xB8, 0x80, 0x70, 0x00, 0x00}, 4},
    {"P4 display_modes_1024 buf", L"compat", L"display_modes_1024", 1, 0x007A1F3F, 6,
     {0x8D, 0x95, 0xC0, 0xC7, 0xFF, 0xFF}, {0x8D, 0x95, 0x80, 0x8F, 0xFF, 0xFF}, 4},
    {"P4 display_modes_1024 count", L"compat", L"display_modes_1024", 1, 0x007A1F4F, 7,
     {0xC7, 0x45, 0xFC, 0x00, 0x02, 0x00, 0x00}, {0xC7, 0x45, 0xFC, 0x00, 0x04, 0x00, 0x00}, 4},
    {"P4 display_modes_1024 copy", L"compat", L"display_modes_1024", 1, 0x007A1F77, 6,
     {0x8D, 0x8D, 0xC0, 0xC7, 0xFF, 0xFF}, {0x8D, 0x8D, 0x80, 0x8F, 0xFF, 0xFF}, 4},
    /* P13 (GOG E): the "press any key" screen after a level load (0x8543CA) takes only gamepad codes 0x105/0x10B when
       the input system reports a gamepad (Steam Input counts), so mouse and keyboard cannot leave it.
       je -> jmp at 0x8543E2 accepts any press; byte for byte as GOG 1.01 v5, which also drops the ~1 s guard at
       0x8543D7 (kept here). Movement does not reach this handler. Not verified in game (no gamepad here). */
    {"P13 press_key_any_input", L"compat", L"press_key_any_input", 0, 0x008543DD, 7,
     {0x3D, 0x05, 0x01, 0x00, 0x00, 0x74, 0x0B}, {0x3D, 0x05, 0x01, 0x00, 0x00, 0xEB, 0x0B}, 0},
};

/* every part of the group still holds either its original or its patched bytes */
static int group_ok(int group) {
    unsigned i;
    for (i = 0; i < sizeof g_patches / sizeof g_patches[0]; i++) {
        const Patch *p = &g_patches[i];
        const unsigned char *at = (const unsigned char *)p->addr;
        if (p->group == group && !same(at, p->expect, p->len) && !same(at, p->repl, p->len)) return 0;
    }
    return 1;
}

static int game_header_ok(void) {
    const unsigned char *base = (const unsigned char *)GetModuleHandleW(NULL);
    const IMAGE_DOS_HEADER *dos = (const IMAGE_DOS_HEADER *)base;
    const IMAGE_NT_HEADERS32 *nt;
    if ((unsigned)base != GAME_BASE || dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (const IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    return nt->Signature == IMAGE_NT_SIGNATURE && nt->OptionalHeader.SizeOfImage == GAME_SIZE &&
           nt->FileHeader.TimeDateStamp == GAME_STAMP;
}
static int game_is_expected(void) {
    const unsigned char *base = (const unsigned char *)GetModuleHandleW(NULL);
    const IMAGE_NT_HEADERS32 *nt = (const IMAGE_NT_HEADERS32 *)(base + ((const IMAGE_DOS_HEADER *)base)->e_lfanew);
    put("exe base ");
    put_hex((unsigned)base, 8);
    if ((unsigned)base == GAME_BASE) {
        put(" size ");
        put_hex(nt->OptionalHeader.SizeOfImage, 8);
        put(" stamp ");
        put_hex(nt->FileHeader.TimeDateStamp, 8);
    }
    if (!game_header_ok()) {
        put(" -> not metro2033.exe 1.0.0.1 (Steam), no patches\r\n");
        return 0;
    }
    put(" -> ok\r\n");
    return 1;
}

static int unprotect(unsigned addr, unsigned len, DWORD *old) {
    return VirtualProtect((void *)addr, len, PAGE_EXECUTE_READWRITE, old);
}
static void reprotect(unsigned addr, unsigned len, DWORD old) {
    VirtualProtect((void *)addr, len, old, &old);
    FlushInstructionCache(GetCurrentProcess(), (void *)addr, len);
}

/* 5-byte site -> "jmp to" (op 0xE9) or "call to" (0xE8): the site sits inside one aligned qword, which is swapped
   with one cmpxchg8b, so a thread can never see half an instruction. */
static int put_rel(unsigned site, unsigned char op, unsigned to) {
    unsigned q = site & ~7u, k = site - q, rel = to - (site + 5), i;
    union { LONGLONG v; unsigned char b[8]; } was, now;
    DWORD old;
    if (k > 3) return 0;
    was.v = *(volatile LONGLONG *)q;
    now = was;
    now.b[k] = op;
    for (i = 0; i < 4; i++) now.b[k + 1 + i] = (unsigned char)(rel >> (8 * i));
    if (!unprotect(q, 8, &old)) return 0;
    i = InterlockedCompareExchange64((volatile LONGLONG *)q, now.v, was.v) == was.v;
    reprotect(q, 8, old);
    return (int)i;
}
static int put_jmp(unsigned site, unsigned to) { return put_rel(site, 0xE9, to); }
/* "call rel32" that need not be qword-aligned: only for code that runs on the main thread, which is inside
   DirectInput8Create while we patch */
static int put_call_main(unsigned site, unsigned to) {
    unsigned rel = to - (site + 5);
    DWORD old;
    if (!unprotect(site, 5, &old)) return 0;
    *(unsigned char *)site = 0xE8;
    memcpy((void *)(site + 1), &rel, 4);
    reprotect(site, 5, old);
    return 1;
}
static void log_site(const char *id, unsigned site, unsigned to, int ok, unsigned shown) {
    put(id);
    put(" @");
    put_hex(site, 8);
    put(" -> ");
    put_hex(to, 8);
    put(ok ? ": OK " : ": FAILED ");
    put_bytes((const unsigned char *)site, shown);
    put("\r\n");
}
static int skip_bytes(const char *id, unsigned site, unsigned shown) {
    put(id);
    put(": SKIP, bytes differ: ");
    put_bytes((const unsigned char *)site, shown);
    put("\r\n");
    return 0;
}

/* ---- P5: Present's SyncInterval from r_vsync (README.md). The two per-frame call sites jump to stubs in this
   DLL that push r_vsync ? 1 : 0 instead of the constant 0. (A stub in the exe's .text padding, as in the GOG build,
   also passed the tests; it is not used.) ---- */
#define SITE_A 0x007A1733u /* push ebx; push ebx; push edi; call ecx  (back at 0x7A1738) */
#define SITE_B 0x007A1D71u /* push ebx; push ebp; call [eax+0x20]     (back at 0x7A1D76; Flags pushed at 0x7A1D70) */

/* the stubs return through these, so they stay right if this DLL is rebased */
__attribute__((used)) unsigned g_p5_back_a = SITE_A + 5;
__attribute__((used)) unsigned g_p5_back_b = SITE_B + 5;
void p5_stub_a(void);
void p5_stub_b(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p5_stub_a\n"
        "_p5_stub_a:\n"
        "    pushl %ebx\n"          /* Flags, as before (0) */
        "    movl 0x9F2820, %eax\n" /* eax is dead here: it held the vtable ecx came from */
        "    shrl $4, %eax\n"
        "    andl $1, %eax\n"
        "    pushl %eax\n" /* SyncInterval = r_vsync ? 1 : 0 */
        "    pushl %edi\n" /* the swap chain */
        "    call *%ecx\n" /* IDXGISwapChain::Present, stdcall: pops 12 bytes, HRESULT in eax */
        "    jmp *_g_p5_back_a\n"
        ".p2align 4\n"
        ".globl _p5_stub_b\n"
        "_p5_stub_b:\n"
        "    movl 0x9F2820, %ecx\n" /* ecx is dead here: eax holds the vtable for the call */
        "    shrl $4, %ecx\n"
        "    andl $1, %ecx\n"
        "    pushl %ecx\n"
        "    pushl %ebp\n"
        "    call *0x20(%eax)\n"
        "    jmp *_g_p5_back_b\n");

/* the code that registers r_vsync must say: name "r_vsync", value word 0x9F2820, mask 0x10. It is plain .text,
   so this holds before the game builds the cvar object (lazily, later than our first call). */
static int p5_cvar_ok(void) {
    static const unsigned char name_reg[] = {0xC7, 0x05, 0xC4, 0x86, 0xA4, 0x00, 0x48, 0x67, 0x97, 0x00};
    static const unsigned char word_reg[] = {0xC7, 0x05, 0xD0, 0x86, 0xA4, 0x00, 0x20, 0x28, 0x9F, 0x00};
    static const unsigned char mask_reg[] = {0xC7, 0x05, 0xD4, 0x86, 0xA4, 0x00, 0x10, 0x00, 0x00, 0x00};
    static const char name[] = "r_vsync";
    return same((const unsigned char *)0x0093A778, name_reg, sizeof name_reg) &&
           same((const unsigned char *)0x0093A7A9, word_reg, sizeof word_reg) &&
           same((const unsigned char *)0x0093A7B3, mask_reg, sizeof mask_reg) &&
           same((const unsigned char *)0x00976748, (const unsigned char *)name, sizeof name);
}

static void apply_p5(void) {
    static const unsigned char site_a[] = {0x8B, 0x48, 0x20, 0x53, 0x53, 0x57, 0xFF, 0xD1}; /* qword 0x7A1730 */
    static const unsigned char site_b[] = {0x53, 0x53, 0x55, 0xFF, 0x50, 0x20, 0x5F, 0x5E}; /* qword 0x7A1D70 */
    unsigned to_a = (unsigned)&p5_stub_a, to_b = (unsigned)&p5_stub_b;
    put("P5 vsync_follow_cvar");
    if (!key_int(L"compat", L"vsync_follow_cvar", 1)) {
        put(": disabled in ini\r\n");
        return;
    }
    if (!p5_cvar_ok()) {
        put(": SKIP, r_vsync registration differs\r\n");
        return;
    }
    if (!same((const unsigned char *)(SITE_A - 3), site_a, 8) || !same((const unsigned char *)(SITE_B - 1), site_b, 8)) {
        put(": SKIP, bytes differ: A ");
        put_bytes((const unsigned char *)(SITE_A - 3), 8);
        put(" B ");
        put_bytes((const unsigned char *)(SITE_B - 1), 8);
        put("\r\n");
        return;
    }
    put("\r\n    A @");
    put_hex(SITE_A, 8);
    put(" -> ");
    put_hex(to_a, 8);
    put(put_jmp(SITE_A, to_a) ? ": OK " : ": FAILED ");
    put_bytes((const unsigned char *)(SITE_A - 3), 8);
    put("\r\n    B @");
    put_hex(SITE_B, 8);
    put(" -> ");
    put_hex(to_b, 8);
    put(put_jmp(SITE_B, to_b) ? ": OK " : ": FAILED ");
    put_bytes((const unsigned char *)(SITE_B - 1), 8);
    put("\r\n");
}

/* ---- P8: frame limiter that waits until a deadline (field note, Gotcha 23). The engine's limiter at
   0x8536FB..0x8537E9 sleeps int(1000/target_fps) - int(1000/fps) whole ms, which hides inside the Present wait when
   the GPU is the bottleneck. The block is skipped and replaced by p8_wait: wait until the previous tick's QPC
   ([timer+0x70], u64) plus 1/target_fps, sleeping on a high-resolution waitable timer and spinning the last
   fps_limiter_spin_us (600 us by default). ---- */
#define P8_SITE 0x008536FBu      /* mov eax,[0xA1BE08]: start of the Sleep block */
#define P8_BACK 0x008537EAu      /* mov cl,[edi+0x2c]: first instruction after the Sleep call */
#define TARGET_FPS_PTR 0x00A1BE08u /* the cvar's value pointer; the limiter reads target_fps through it */
#define QPC_PER_MS 0x00A13BD8u   /* u64: QueryPerformanceFrequency / 1000, set by the engine timer */

__attribute__((used)) unsigned g_p8_back = P8_BACK;
static unsigned g_p8_spin_us = 600; /* spin the last part before the deadline (ini fps_limiter_spin_us, 100..3000) */
static HANDLE g_p8_timer;
static int g_p8_timer_tried;

__attribute__((used)) void __cdecl p8_wait(const unsigned char *timer) {
    const int *target_p = *(int *const *)TARGET_FPS_PTR;
    unsigned tpm, period, rem, spin;
    int target;
    unsigned long long prev, deadline;
    LARGE_INTEGER now;
    if (!target_p) return;
    target = *target_p;
    if (target <= 0 || target > 1000) return; /* target_fps 0: no cap */
    if (*(const unsigned *)(QPC_PER_MS + 4) || !(tpm = *(const unsigned *)QPC_PER_MS) || tpm > 400000) return;
    period = tpm * 1000u / (unsigned)target; /* ticks; at most 4e8, 32-bit math (no CRT 64-bit division) */
    prev = *(const volatile unsigned long long *)(timer + 0x70);
    deadline = prev + period;
    if (!g_p8_timer_tried) {
        g_p8_timer_tried = 1;
        /* manual reset + bounded waits: the function is also reached from render code, so two threads may wait
           at once; an auto-reset timer would release only one of them */
        g_p8_timer = CreateWaitableTimerExW(NULL, NULL, 0x1 | 0x2 /* MANUAL_RESET | HIGH_RESOLUTION */, TIMER_ALL_ACCESS);
    }
    for (;;) {
        QueryPerformanceCounter(&now);
        if ((unsigned long long)now.QuadPart >= deadline) return;
        if (deadline - (unsigned long long)now.QuadPart > period) return; /* stale timestamp: never wait longer than one period */
        rem = (unsigned)(deadline - (unsigned long long)now.QuadPart);
        spin = tpm * g_p8_spin_us / 1000u;
        if (rem > spin + tpm / 2) {
            /* sleep until spin_us before the deadline; due time in 100 ns units, negative = relative */
            unsigned sleep_ticks = rem - spin;
            LARGE_INTEGER due;
            due.QuadPart = -(LONGLONG)((sleep_ticks / tpm) * 10000u + (sleep_ticks % tpm) * 10000u / tpm);
            if (g_p8_timer && SetWaitableTimer(g_p8_timer, &due, 0, NULL, NULL, FALSE))
                WaitForSingleObject(g_p8_timer, rem / tpm + 2);
            else
                Sleep(1);
        } else {
            YieldProcessor();
        }
    }
}

void p8_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p8_stub\n"
        "_p8_stub:\n"
        "    pushfl\n"
        "    pushal\n"
        "    pushl %edi\n" /* the engine timer object */
        "    call _p8_wait\n"
        "    addl $4, %esp\n"
        "    popal\n"
        "    popfl\n"
        "    jmp *_g_p8_back\n"); /* skip the old Sleep block */

static int apply_p8(void) {
    static const unsigned char site[] = {0x47, 0x2E, 0x00, 0xA1, 0x08, 0xBE, 0xA1, 0x00}; /* qword 0x8536F8 */
    static const unsigned char head[] = {0xF3, 0x0F, 0x10, 0x4F, 0x6C, 0xF3, 0x0F, 0x2A, 0x10, 0x0F, 0x2F, 0xCA};
    static const unsigned char tail[] = {0x56, 0xFF, 0x15, 0x50, 0xF0, 0x94, 0x00, 0x8A, 0x4F, 0x2C}; /* 0x8537E3 */
    unsigned to = (unsigned)&p8_stub;
    put("P8 fps_limiter_deadline @");
    put_hex(P8_SITE, 8);
    if (!key_int(L"perf", L"fps_limiter_deadline", 1)) {
        put(": disabled in ini\r\n");
        return 0;
    }
    if (!same((const unsigned char *)(P8_SITE - 3), site, 8) || !same((const unsigned char *)(P8_SITE + 5), head, 12) ||
        !same((const unsigned char *)0x008537E3u, tail, 10)) {
        put(": SKIP, bytes differ: ");
        put_bytes((const unsigned char *)(P8_SITE - 3), 8);
        put("\r\n");
        return 0;
    }
    g_p8_spin_us = (unsigned)key_int(L"perf", L"fps_limiter_spin_us", 600);
    if (g_p8_spin_us < 100) g_p8_spin_us = 100;
    if (g_p8_spin_us > 3000) g_p8_spin_us = 3000;
    put(" -> ");
    put_hex(to, 8);
    put(put_jmp(P8_SITE, to) ? ": OK " : ": FAILED ");
    put_bytes((const unsigned char *)(P8_SITE - 3), 8);
    put(" (QPC/ms now ");
    put_dec(*(const unsigned *)QPC_PER_MS);
    put(", spin ");
    put_dec(g_p8_spin_us);
    put(" us)\r\n");
    return 1;
}

/* ---- P9 (part of P8 since 0.4): let the game save target_fps in user.cfg: OR 0x01000000 into the cvar's flags
   (byte 0xA1BE03 00 -> 01), as mouse_sens/r_gamma have. On with P8 unless target_fps_save = 0 (old key).
   The object must already say int vtable, name "target_fps", flags 0x101. ---- */
static void apply_p9(int p8_on) {
    static const char name[] = "target_fps";
    const unsigned *obj = (const unsigned *)0x00A1BDF8u;
    DWORD old;
    put("P9 target_fps_save (with P8) @00A1BE03");
    if (!p8_on || !key_int(L"perf", L"target_fps_save", 1)) {
        put(p8_on ? ": disabled in ini (target_fps_save = 0)\r\n" : ": off (P8 off)\r\n");
        return;
    }
    if (obj[2] == 0x01000101u) {
        put(": already applied\r\n");
        return;
    }
    if (obj[0] != 0x00963788u || obj[1] != 0x00964078u || obj[2] != 0x00000101u ||
        !same((const unsigned char *)0x00964078u, (const unsigned char *)name, sizeof name)) {
        put(": SKIP, cvar object not as expected: ");
        put_bytes((const unsigned char *)obj, 12);
        put("\r\n");
        return;
    }
    if (!unprotect(0x00A1BE03u, 1, &old)) {
        put(": SKIP, VirtualProtect failed\r\n");
        return;
    }
    *(unsigned char *)0x00A1BE03u = 0x01;
    reprotect(0x00A1BE03u, 1, old);
    put(": OK flags 00000101 -> ");
    put_hex(obj[2], 8);
    put("\r\n");
}

/* ---- P10 (field note, Gotcha 20): fullscreen entry when the game had no focus at start. 0x7A1E4B creates the
   swap chain with Windowed = [0xA16915]; without focus DXGI answers DXGI_STATUS_OCCLUDED and leaves a window, the
   game ignores the HRESULT and never retries (it also gets no focus event after a click). After CreateSwapChain
   (0x7A1EE1) we note the result; once per frame on the main thread (the call at 0x85B523 to 0x85B090) we retry
   SetFullscreenState(TRUE) when the game window is in front, under the renderer lock 0xA2E5B0 that 0x7A2913 takes
   for the same call. ---- */
#define P10_SITE1 0x007A1EE1u /* mov eax,[edi]; lea ecx,[ebp-0xC]: right after CreateSwapChain */
#define P10_SITE2 0x0085B523u /* call 0x85B090 in the main-loop tick */
#define WINDOWED_FLAG 0x00A16915u
#define GAME_HWND 0x00A16940u
#define RENDER_LOCK 0x00A2E5B0u
__attribute__((used)) unsigned g_p10_back1 = P10_SITE1 + 5;
__attribute__((used)) unsigned g_p10_tick_target = 0x0085B090u;
static unsigned char *volatile g_p10_renderer;
static volatile int g_p10_pending, g_p10_tries;
static unsigned g_p10_last;

__attribute__((used)) void __cdecl p10_created(HRESULT hr, unsigned char *renderer) {
    g_p10_renderer = renderer;
    g_p10_tries = 0;
    g_p10_pending = hr == (HRESULT)0x087A0001 && *(volatile unsigned char *)WINDOWED_FLAG == 0;
    if (g_p10_pending && ev_begin()) {
        put("P10: CreateSwapChain asked for fullscreen, got DXGI_STATUS_OCCLUDED; retry when the window is in front");
        ev_end();
    }
}
typedef HRESULT(WINAPI *SetFs)(void *, BOOL, void *);
typedef HRESULT(WINAPI *GetFs)(void *, BOOL *, void **);
__attribute__((used)) void __cdecl p10_tick(void) {
    HWND w;
    void *sc, **vt;
    BOOL fs = FALSE;
    HRESULT hr;
    unsigned now;
    if (!g_p10_pending) return;
    now = GetTickCount();
    if (now - g_p10_last < 500) return;
    w = *(volatile HWND *)GAME_HWND;
    if (!w || !g_p10_renderer || pGetForegroundWindow() != w || pIsIconic(w)) return;
    if (*(volatile unsigned char *)WINDOWED_FLAG) { /* the player switched to windowed meanwhile */
        g_p10_pending = 0;
        return;
    }
    g_p10_last = now;
    sc = *(void *volatile *)(g_p10_renderer + 0x2D0); /* after a mode change the game makes a new swap chain */
    if (!sc) return;
    vt = *(void ***)sc;
    EnterCriticalSection((LPCRITICAL_SECTION)RENDER_LOCK);
    hr = ((SetFs)vt[10])(sc, TRUE, NULL); /* IDXGISwapChain::SetFullscreenState */
    LeaveCriticalSection((LPCRITICAL_SECTION)RENDER_LOCK);
    ((GetFs)vt[11])(sc, &fs, NULL); /* GetFullscreenState */
    g_p10_tries++;
    if (fs || g_p10_tries >= 5) g_p10_pending = 0;
    if (ev_begin()) {
        put("P10: try ");
        put_dec((unsigned)g_p10_tries);
        put(" SetFullscreenState(TRUE) hr ");
        put_hex((unsigned)hr, 8);
        put(fs ? ", now fullscreen" : g_p10_pending ? ", still windowed" : ", still windowed, giving up");
        ev_end();
    }
}
void p10_after_create(void);
void p10_tick_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p10_after_create\n"
        "_p10_after_create:\n"
        "    pushfl\n"
        "    pushal\n"
        "    pushl %edi\n" /* the renderer (swap chain at +0x2D0) */
        "    pushl %eax\n" /* CreateSwapChain's HRESULT */
        "    call _p10_created\n"
        "    addl $8, %esp\n"
        "    popal\n"
        "    popfl\n"
        "    movl (%edi), %eax\n" /* the two instructions the jmp replaced */
        "    leal -0xC(%ebp), %ecx\n"
        "    jmp *_g_p10_back1\n"
        ".p2align 4\n"
        ".globl _p10_tick_stub\n"
        "_p10_tick_stub:\n" /* reached by the game's call, so its return address is on the stack */
        "    pushfl\n"
        "    pushal\n"
        "    call _p10_tick\n"
        "    popal\n"
        "    popfl\n"
        "    jmp *_g_p10_tick_target\n");

static void apply_p10(void) {
    static const unsigned char s1[] = {0xFF, 0x52, 0x28, 0x8B, 0x07, 0x8D, 0x4D, 0xF4}; /* 0x7A1EDE: call [edx+0x28]; site */
    static const unsigned char s2[] = {0xE8, 0x68, 0xFB, 0xFF, 0xFF};                   /* 0x85B523: call 0x85B090 */
    static const unsigned char lock[] = {0x68, 0xB0, 0xE5, 0xA2, 0x00};                 /* 0x7A291F: push 0xA2E5B0 */
    static const unsigned char wflag[] = {0x0F, 0xB6, 0x05, 0x15, 0x69, 0xA1, 0x00};   /* 0x7A1E95: movzx eax,[0xA16915] */
    if (!key_int(L"compat", L"fullscreen_retry", 0)) {
        put("P10 fullscreen_retry: disabled in ini\r\n");
        return;
    }
    if (!pGetForegroundWindow || !pIsIconic) {
        put("P10 fullscreen_retry: SKIP, user32 functions not found\r\n");
        return;
    }
    if (!same((const unsigned char *)0x007A1EDEu, s1, 8)) return (void)skip_bytes("P10 fullscreen_retry create", 0x007A1EDEu, 8);
    if (!same((const unsigned char *)P10_SITE2, s2, 5)) return (void)skip_bytes("P10 fullscreen_retry tick", P10_SITE2, 5);
    if (!same((const unsigned char *)0x007A291Fu, lock, 5) || !same((const unsigned char *)0x007A1E95u, wflag, 7))
        return (void)skip_bytes("P10 fullscreen_retry lock/flag", 0x007A291Fu, 5);
    log_site("P10 fullscreen_retry create", P10_SITE1, (unsigned)&p10_after_create,
             put_jmp(P10_SITE1, (unsigned)&p10_after_create), 5);
    log_site("P10 fullscreen_retry tick", P10_SITE2, (unsigned)&p10_tick_stub,
             put_rel(P10_SITE2, 0xE8, (unsigned)&p10_tick_stub), 5);
}

/* ---- P11 (field note, Gotcha 21): 0x7B3740 sorts the display-mode list and reads its last entry to pick the
   aspect ratio ([0xA16908]) without checking that the list has one; an empty list (GetDisplayModeList gave 0,
   HRESULT ignored) reads 0xFFFFFFF8. The function's entry jumps to p11_stub: an empty list sets the desktop aspect
   and returns (stdcall, 1 argument); otherwise the moved prologue runs and the function goes on. Both callers
   (0x7A1F9D DX11, 0x7ACA25) are covered. ---- */
#define P11_SITE 0x007B3740u
__attribute__((used)) unsigned g_p11_back = P11_SITE + 6;
__attribute__((used)) void __cdecl p11_empty(void) {
    int cx = pGetSystemMetrics ? pGetSystemMetrics(SM_CXSCREEN) : 0, cy = pGetSystemMetrics ? pGetSystemMetrics(SM_CYSCREEN) : 0;
    *(volatile float *)0x00A16908u = cx > 0 && cy > 0 ? (float)cx / (float)cy : 16.0f / 9.0f;
    if (ev_begin()) {
        put("P11: empty display mode list, aspect from desktop ");
        put_dec((unsigned)cx);
        put("x");
        put_dec((unsigned)cy);
        ev_end();
    }
}
void p11_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p11_stub\n"
        "_p11_stub:\n"
        "    pushl %eax\n"
        "    movl 8(%esp), %eax\n" /* the list: {ptr, ?, count} */
        "    testl %eax, %eax\n"
        "    jz 1f\n"
        "    cmpl $0, (%eax)\n"
        "    je 1f\n"
        "    cmpl $0, 8(%eax)\n"
        "    je 1f\n"
        "    popl %eax\n"
        "    pushl %ebp\n" /* the moved prologue: push ebp; mov ebp,esp; and esp,-64 */
        "    movl %esp, %ebp\n"
        "    andl $-64, %esp\n"
        "    jmp *_g_p11_back\n"
        "1:  popl %eax\n"
        "    pushfl\n"
        "    pushal\n"
        "    call _p11_empty\n"
        "    popal\n"
        "    popfl\n"
        "    ret $4\n");

static void apply_p11(void) {
    static const unsigned char s[] = {0x55, 0x8B, 0xEC, 0x83, 0xE4, 0xC0, 0x83, 0xEC, 0x3C, 0x56, 0x8B, 0x75, 0x08};
    if (!key_int(L"core", L"empty_mode_list_guard", 0)) {
        put("P11 empty_mode_list_guard: disabled in ini\r\n");
        return;
    }
    if (!same((const unsigned char *)P11_SITE, s, sizeof s)) return (void)skip_bytes("P11 empty_mode_list_guard", P11_SITE, 13);
    log_site("P11 empty_mode_list_guard", P11_SITE, (unsigned)&p11_stub, put_jmp(P11_SITE, (unsigned)&p11_stub), 6);
}

/* ---- P12 (field note, Gotcha 22): config_load copies each user.cfg line with
   strncpy_s(buf[0x400], 0x400, line, len) and then writes buf[len] = 0; a line of 1024+ characters ends the process
   (MSVCR80 invalid parameter). Clamp len to 1023 at 0x422702. (The unchecked buf[len] = 0 for a file without line
   breaks is not covered; see the note.) The first config_load runs at ~1.95 s, before DirectInput8Create (~2.2 s),
   so a thread started in DllMain applies this one as soon as SteamStub has decrypted the bytes (~0.25 s). ---- */
#define P12_SITE 0x00422702u /* mov edi,eax; push edi; push esi; lea ecx,[esp+0x28] */
__attribute__((used)) unsigned g_p12_back = P12_SITE + 8;
static volatile LONG g_p12_state; /* 0 waiting, 1 applied, 2 disabled, 3 not this exe, 4 bytes never matched, 5 write failed */
static unsigned g_p12_ms;
void p12_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p12_stub\n"
        "_p12_stub:\n"
        "    movl %eax, %edi\n" /* the line length */
        "    cmpl $0x3FF, %edi\n"
        "    jbe 1f\n"
        "    movl $0x3FF, %edi\n"
        "1:  pushl %edi\n"
        "    pushl %esi\n"
        "    leal 0x28(%esp), %ecx\n"
        "    jmp *_g_p12_back\n");
static const unsigned char g_p12_expect[] = {0x8B, 0xF8, 0x57, 0x56, 0x8D, 0x4C, 0x24, 0x28};

static DWORD WINAPI p12_watcher(LPVOID unused) {
    int i;
    (void)unused;
    if (!key_int(L"core", L"config_line_clamp", 0)) {
        g_p12_state = 2;
        return 0;
    }
    if (!game_header_ok()) {
        g_p12_state = 3;
        return 0;
    }
    for (i = 0; i < 1000 && g_p12_state == 0; i++) { /* 10 s */
        if (same((const unsigned char *)P12_SITE, g_p12_expect, 8)) {
            Sleep(300); /* let SteamStub finish with .text; the first config_load is ~1.6 s later */
            if (!same((const unsigned char *)P12_SITE, g_p12_expect, 8)) continue;
            g_p12_ms = ms_since_start();
            InterlockedCompareExchange(&g_p12_state, put_jmp(P12_SITE, (unsigned)&p12_stub) ? 1 : 5, 0);
            return 0;
        }
        Sleep(10);
    }
    InterlockedCompareExchange(&g_p12_state, 4, 0);
    return 0;
}
static void report_p12(void) {
    put("P12 config_line_clamp @");
    put_hex(P12_SITE, 8);
    if (g_p12_state == 0) { /* the watcher has not seen the bytes yet: try here, once */
        int ok = same((const unsigned char *)P12_SITE, g_p12_expect, 8);
        if (InterlockedCompareExchange(&g_p12_state, ok ? 6 : 4, 0) == 0 && ok) {
            g_p12_ms = ms_since_start();
            g_p12_state = put_jmp(P12_SITE, (unsigned)&p12_stub) ? 1 : 5;
        }
    }
    switch (g_p12_state) {
    case 1: put(": OK at "); put_dec(g_p12_ms); put(" ms (before the first user.cfg read if < ~1900) "); put_bytes((const unsigned char *)P12_SITE, 5); break;
    case 2: put(": disabled in ini"); break;
    case 3: put(": SKIP, not this exe"); break;
    case 4: put(": SKIP, bytes differ: "); put_bytes((const unsigned char *)P12_SITE, 8); break;
    default: put(": FAILED to write"); break;
    }
    put("\r\n");
}

/* ---- P14 (GOG F): 0x938E20 warns about an unknown GPU vendor (Intel too), an old driver, or unreadable driver
   info through 0x938C00, which logs "!DX: %s" and shows a modal MessageBox that can hide behind the fullscreen
   window. The two calls at 0x938EA5 and 0x938F9E (text in edi) go to p14_stub: the same game-log line, plus a line
   in m2033fix.log, no box. The other 0x938C00 callers (real DX errors) are untouched. ---- */
__attribute__((used)) unsigned g_game_log = 0x0085E1B0u; /* cdecl (fmt, ...) */
__attribute__((used)) void __cdecl p14_note(const char *text) {
    if (ev_begin()) {
        put("P14: driver warning not shown as a window: ");
        put_n(text, 200);
        ev_end();
    }
}
void p14_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p14_stub\n"
        "_p14_stub:\n"
        "    pushfl\n"
        "    pushal\n"
        "    pushl %edi\n"
        "    pushl $0x977E90\n" /* "!DX: %s" */
        "    call *_g_game_log\n"
        "    addl $8, %esp\n"
        "    pushl %edi\n"
        "    call _p14_note\n"
        "    addl $4, %esp\n"
        "    popal\n"
        "    popfl\n"
        "    ret\n");
static void apply_p14(void) {
    static const unsigned char a[] = {0xBF, 0x48, 0x7D, 0x97, 0x00, 0xE8, 0x56, 0xFD, 0xFF, 0xFF}; /* 0x938EA0 */
    static const unsigned char b[] = {0x8D, 0x7C, 0x24, 0x30, 0xE8, 0x5D, 0xFC, 0xFF, 0xFF};       /* 0x938F9A */
    static const char fmt[] = "!DX: %s";
    if (!key_int(L"compat", L"no_driver_popup", 0)) {
        put("P14 no_driver_popup: disabled in ini\r\n");
        return;
    }
    if (!same((const unsigned char *)0x00938EA0u, a, sizeof a) || !same((const unsigned char *)0x00938F9Au, b, sizeof b) ||
        !same((const unsigned char *)0x00977E90u, (const unsigned char *)fmt, sizeof fmt))
        return (void)skip_bytes("P14 no_driver_popup", 0x00938EA0u, 10);
    /* 0x938E20 runs on the main thread, which is inside DirectInput8Create now */
    log_site("P14 no_driver_popup a", 0x00938EA5u, (unsigned)&p14_stub, put_call_main(0x00938EA5u, (unsigned)&p14_stub), 5);
    log_site("P14 no_driver_popup b", 0x00938F9Eu, (unsigned)&p14_stub, put_call_main(0x00938F9Eu, (unsigned)&p14_stub), 5);
}

/* ---- P17: the STOP handler 0x9316BB (cdecl: reason, file, func, line) keeps its text in the in-memory log and then
   crashes on purpose with a write to 0. Write the reason to m2033fix.log first; the game then goes on as before. ---- */
#define P17_SITE 0x009316BBu
__attribute__((used)) unsigned g_p17_back = P17_SITE + 8;
__attribute__((used)) void __cdecl p17_log(const unsigned *args) {
    if (ev_begin()) {
        put("STOP: ");
        put_n((const char *)args[0], 300);
        put(" | file ");
        put_n((const char *)args[1], 200);
        put(" | func ");
        put_n((const char *)args[2], 200);
        put(" | line ");
        put_dec(args[3]);
        put(" | tid ");
        put_dec(GetCurrentThreadId());
        ev_end();
    }
}
void p17_stub(void);
__asm__(".text\n"
        ".p2align 4\n"
        ".globl _p17_stub\n"
        "_p17_stub:\n"
        "    pushfl\n"
        "    pushal\n"
        "    leal 40(%esp), %eax\n" /* the handler's arguments: 32 (pushal) + 4 (pushfl) + 4 (return address) */
        "    pushl %eax\n"
        "    call _p17_log\n"
        "    addl $4, %esp\n"
        "    popal\n"
        "    popfl\n"
        "    pushl %ebp\n" /* the moved instructions: push ebp; mov ebp,esp; mov eax,0x1004 */
        "    movl %esp, %ebp\n"
        "    movl $0x1004, %eax\n"
        "    jmp *_g_p17_back\n");
static void apply_p17(void) {
    static const unsigned char s[] = {0x55, 0x8B, 0xEC, 0xB8, 0x04, 0x10, 0x00, 0x00, 0xE8, 0x38, 0x21, 0xCA, 0xFF};
    if (!key_int(L"research", L"log_stop", 0)) {
        put("P17 log_stop: disabled in ini\r\n");
        return;
    }
    if (!same((const unsigned char *)P17_SITE, s, sizeof s)) return (void)skip_bytes("P17 log_stop", P17_SITE, 13);
    log_site("P17 log_stop", P17_SITE, (unsigned)&p17_stub, put_jmp(P17_SITE, (unsigned)&p17_stub), 5);
}

static void apply_patch(const Patch *p) {
    unsigned char *at = (unsigned char *)p->addr;
    DWORD old;
    int on = key_int(p->sec, p->key, p->def);
    put(p->id);
    put(" @");
    put_hex(p->addr, 8);
    if (!on) {
        put(": disabled in ini\r\n");
        return;
    }
    if (same(at, p->repl, p->len)) {
        put(": already applied\r\n");
        return;
    }
    if (p->group && !group_ok(p->group)) {
        put(": SKIP, another part of this group differs\r\n");
        return;
    }
    if (!same(at, p->expect, p->len)) {
        put(": SKIP, bytes differ: found ");
        put_bytes(at, p->len);
        put("\r\n");
        return;
    }
    if (!unprotect(p->addr, p->len, &old)) {
        put(": SKIP, VirtualProtect failed ");
        put_hex(GetLastError(), 8);
        put("\r\n");
        return;
    }
    memcpy(at, p->repl, p->len);
    reprotect(p->addr, p->len, old);
    put(": OK ");
    put_bytes(p->expect, p->len);
    put(" -> ");
    put_bytes(at, p->len);
    put("\r\n");
}

static void init_once(void) {
    WCHAR sys[MAX_PATH];
    unsigned i, n;
    HMODULE u32;
    g_log_on = key_int(L"log", L"enabled", 1);
    if (g_log_on)
        g_log = CreateFileW(g_log_path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    put("m2033fix 0.4.1  first DirectInput8Create: tid ");
    put_dec(GetCurrentThreadId());
    put(", ");
    put_dec(ms_since_start());
    put(" ms after process start\r\n");

    n = GetSystemDirectoryW(sys, MAX_PATH - 16);
    if (n && n < MAX_PATH - 16) {
        static const WCHAR tail[] = L"\\dinput8.dll";
        for (i = 0; tail[i]; i++) sys[n + i] = tail[i];
        sys[n + i] = 0;
        g_real = (DI8Create)GetProcAddress(LoadLibraryW(sys), "DirectInput8Create");
    }
    put(g_real ? "system dinput8: ok\r\n" : "system dinput8: FAILED, input will not work\r\n");
    u32 = GetModuleHandleW(L"user32.dll");
    if (!u32) u32 = LoadLibraryW(L"user32.dll");
    if (u32) {
        pGetForegroundWindow = (HWND(WINAPI *)(void))GetProcAddress(u32, "GetForegroundWindow");
        pIsIconic = (BOOL(WINAPI *)(HWND))GetProcAddress(u32, "IsIconic");
        pGetSystemMetrics = (int(WINAPI *)(int))GetProcAddress(u32, "GetSystemMetrics");
    }

    if (game_is_expected()) {
        report_p12();
        for (i = 0; i < sizeof g_patches / sizeof g_patches[0]; i++) apply_patch(&g_patches[i]);
        apply_p5();
        apply_p9(apply_p8());
        apply_p10();
        apply_p11();
        apply_p14();
        apply_p17();
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
        while (g_once != 2) Sleep(0); /* another thread is initialising; wait for g_real */
    }
    if (!g_real) return E_FAIL;
    return g_real(hinst, ver, riid, out, outer);
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        /* loader lock is held and the game's .text is still encrypted: only paths here, plus the P12 watcher
           thread, which starts after DllMain returns and only reads the ini and polls 8 bytes */
        int i;
        HANDLE t;
        g_self = h;
        DisableThreadLibraryCalls(h);
        i = (int)GetModuleFileNameW(h, g_dir, MAX_PATH);
        while (i > 0 && g_dir[i - 1] != L'\\') i--;
        g_dir[i] = 0;
        path_in_dir(g_ini, L"m2033fix.ini");
        path_in_dir(g_log_path, L"m2033fix.log");
        t = CreateThread(NULL, 0, p12_watcher, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
