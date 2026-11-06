/* Shadow of War Offline Mode: winhttp.dll proxy.
 *
 * The game's online layer (WB/Agora "Hydra" SDK) talks to WB's servers through WinHTTP in async mode.
 * This DLL sits next to ShadowOfWar.exe and forwards every WinHTTP call to the real System32 winhttp.dll,
 * except for WB/Agora hosts. Those never reach the network:
 *   Mode=block    each request fails like an unreachable server (REQUEST_ERROR / ERROR_WINHTTP_CANNOT_CONNECT).
 *   Mode=emulate  each request is answered locally by responder.c (a minimal stand-in for WB's server, so
 *                 offline-capable features such as the Garrison can work from a local file).
 * Requests are logged to OfflineMode.log (sign-in bodies and auth headers are redacted). The exe is never modified.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <time.h>
#include "names.h"
#include "agb.h"
#include "responder.h"

typedef void *HINTERNET;
typedef void (CALLBACK *STATUS_CB)(HINTERNET, DWORD_PTR, DWORD, LPVOID, DWORD);
typedef struct { DWORD_PTR dwResult; DWORD dwError; } ASYNC_RESULT;

#define FLAG_ASYNC                 0x10000000
#define CB_HANDLE_CLOSING          0x00000800
#define CB_HEADERS_AVAILABLE       0x00020000
#define CB_DATA_AVAILABLE          0x00040000
#define CB_READ_COMPLETE           0x00080000
#define CB_REQUEST_ERROR           0x00200000
#define CB_SENDREQUEST_COMPLETE    0x00400000
#define API_SEND_REQUEST           5
#define ERR_CANNOT_CONNECT         12029
#define ERR_INCORRECT_HANDLE_STATE 12019
#define ERR_HEADER_NOT_FOUND       12150
#define QUERY_FLAG_NUMBER          0x20000000
#define QUERY_CONTENT_TYPE         1
#define QUERY_CONTENT_LENGTH       5
#define QUERY_STATUS_CODE          19
#define QUERY_STATUS_TEXT          20
#define QUERY_RAW_HEADERS          21
#define QUERY_RAW_HEADERS_CRLF     22
#define QUERY_CUSTOM               65535
#define INVALID_CB                 ((STATUS_CB)(LONG_PTR)-1)

extern void *real_ptrs[REAL_COUNT];

HINTERNET WINAPI Real_WinHttpOpen(LPCWSTR, DWORD, LPCWSTR, LPCWSTR, DWORD);
HINTERNET WINAPI Real_WinHttpConnect(HINTERNET, LPCWSTR, WORD, DWORD);
HINTERNET WINAPI Real_WinHttpOpenRequest(HINTERNET, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR *, DWORD);
BOOL WINAPI Real_WinHttpAddRequestHeaders(HINTERNET, LPCWSTR, DWORD, DWORD);
BOOL WINAPI Real_WinHttpSendRequest(HINTERNET, LPCWSTR, DWORD, LPVOID, DWORD, DWORD, DWORD_PTR);
BOOL WINAPI Real_WinHttpReceiveResponse(HINTERNET, LPVOID);
BOOL WINAPI Real_WinHttpQueryHeaders(HINTERNET, DWORD, LPCWSTR, LPVOID, LPDWORD, LPDWORD);
BOOL WINAPI Real_WinHttpReadData(HINTERNET, LPVOID, DWORD, LPDWORD);
BOOL WINAPI Real_WinHttpQueryDataAvailable(HINTERNET, LPDWORD);
BOOL WINAPI Real_WinHttpWriteData(HINTERNET, LPCVOID, DWORD, LPDWORD);
BOOL WINAPI Real_WinHttpSetTimeouts(HINTERNET, int, int, int, int);
STATUS_CB WINAPI Real_WinHttpSetStatusCallback(HINTERNET, STATUS_CB, DWORD, DWORD_PTR);
BOOL WINAPI Real_WinHttpCloseHandle(HINTERNET);
BOOL WINAPI Real_WinHttpSetOption(HINTERNET, DWORD, LPVOID, DWORD);
BOOL WINAPI Real_WinHttpQueryOption(HINTERNET, DWORD, LPVOID, LPDWORD);

/* ---------- state ---------- */
typedef struct Sess { HINTERNET h; BOOL async; STATUS_CB cb; DWORD flags; struct Sess *next; } Sess;
typedef struct Fake {
    DWORD magic; int kind; /* 1 = connect, 2 = request */
    HINTERNET session;
    STATUS_CB cb; DWORD flags; BOOL async; DWORD_PTR ctx;
    volatile LONG inflight; DWORD cbThread; volatile LONG dead;  /* callbacks running / closed inside one */
    WCHAR host[256]; WCHAR verb[16]; WCHAR path[1024];
    unsigned char *req; size_t reqLen;                            /* request body */
    Response resp; size_t readPos; BOOL haveResp;                  /* emulated response */
    DWORD readLeft;                                               /* bytes of the current async read */
    struct Fake *next;
} Fake;

static CRITICAL_SECTION cs;
static Sess *sessions;
static Fake *fakes;
static FILE *logf;
static volatile LONG net_started;   /* v0.12: set by the game's first WinHttpSendRequest (online layer is up) */
static WCHAR blocked[32][64];
static int nblocked;
static BOOL emulate;

void logw(const wchar_t *fmt, ...)
{
    if (!logf) return;
    SYSTEMTIME t; GetLocalTime(&t);
    EnterCriticalSection(&cs);
    fwprintf(logf, L"%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
    va_list a; va_start(a, fmt); vfwprintf(logf, fmt, a); va_end(a);
    fputwc(L'\n', logf); fflush(logf);
    LeaveCriticalSection(&cs);
}

static Sess *find_sess(HINTERNET h) { Sess *s; for (s = sessions; s; s = s->next) if (s->h == h) return s; return NULL; }
static Fake *find_fake_locked(HINTERNET h) { Fake *f; for (f = fakes; f; f = f->next) if ((HINTERNET)f == h) break; return f; }
static Fake *find_fake(HINTERNET h) { EnterCriticalSection(&cs); Fake *f = find_fake_locked(h); LeaveCriticalSection(&cs); return f; }

static BOOL is_blocked(LPCWSTR host)
{
    if (!host) return FALSE;
    size_t hl = wcslen(host);
    for (int i = 0; i < nblocked; i++) {
        size_t bl = wcslen(blocked[i]);
        if (hl < bl || _wcsicmp(host + hl - bl, blocked[i])) continue;
        if (hl == bl || host[hl - bl - 1] == L'.') return TRUE; /* exact or subdomain */
    }
    return FALSE;
}

static BOOL is_signin(const Fake *f) { return wcsstr(f->path, L"auth") || wcsstr(f->path, L"access"); }

/* log a body: decoded if it's x-ag-binary, else printable/escaped */
static void log_body(const char *label, const void *p, size_t n)
{
    if (!p || !n) return;
    size_t cap = 16384; char *txt = malloc(cap);
    if (agb_to_text(p, n, txt, cap)) { logw(L"    %hs (%zu bytes): %hs", label, n, txt); free(txt); return; }
    const unsigned char *b = p; size_t m = n > 4096 ? 4096 : n, o = 0;
    static const char hx[] = "0123456789ABCDEF";
    for (size_t i = 0; i < m && o + 5 < cap; i++) {
        if (b[i] >= 32 && b[i] < 127 && b[i] != '\\') txt[o++] = b[i];
        else { txt[o++] = '\\'; txt[o++] = 'x'; txt[o++] = hx[b[i] >> 4]; txt[o++] = hx[b[i] & 15]; }
    }
    txt[o] = 0;
    logw(L"    %hs (%zu bytes, raw%ls): %hs", label, n, n > m ? L", first 4096" : L"", txt);
    free(txt);
}

static void log_headers(LPCWSTR hdr, DWORD len)
{
    if (!hdr) return;
    size_t n = (len == (DWORD)-1) ? wcslen(hdr) : len;
    wchar_t *c = malloc((n + 1) * sizeof(wchar_t)); wcsncpy(c, hdr, n); c[n] = 0;
    for (wchar_t *line = c, *e; line && *line; line = e) {
        e = wcsstr(line, L"\r\n"); if (e) { *e = 0; e += 2; }
        if (!*line) continue;
        wchar_t *colon = wcschr(line, L':');
        if (colon && (!_wcsnicmp(line, L"Authorization", 13) || !_wcsnicmp(line, L"x-hydra-access-token", 20) || !_wcsnicmp(line, L"Cookie", 6)))
            logw(L"    header %.*ls: <redacted>", (int)(colon - line), line);
        else logw(L"    header %ls", line);
    }
    free(c);
}

/* ---------- async callbacks (always from a worker thread, like real WinHTTP) ---------- */
typedef struct { Fake *f; DWORD status; DWORD_PTR ctx; void *info; DWORD len; unsigned char inl[32]; int useInl; } Job;

static DWORD WINAPI cb_thread(LPVOID p)
{
    Job *j = p; STATUS_CB cb = NULL;
    Sleep(1);
    EnterCriticalSection(&cs);
    Fake *f = find_fake_locked((HINTERNET)j->f);
    if (f && !f->dead && f->cb && f->cb != INVALID_CB && (f->flags & j->status)) {
        cb = f->cb; f->cbThread = GetCurrentThreadId(); InterlockedIncrement(&f->inflight);
    }
    LeaveCriticalSection(&cs);
    if (cb) {
        cb((HINTERNET)f, j->ctx, j->status, j->useInl ? (void *)j->inl : j->info, j->len);
        if (InterlockedDecrement(&f->inflight) == 0 && f->dead) { free(f->req); resp_free(&f->resp); free(f); }
    }
    free(j);
    return 0;
}

static BOOL post_cb(Fake *f, DWORD status, void *info, DWORD len, BOOL copy)
{
    if (!f->cb || f->cb == INVALID_CB || !(f->flags & status)) return FALSE;
    Job *j = calloc(1, sizeof *j); j->f = f; j->status = status; j->ctx = f->ctx; j->len = len;
    if (copy && info && len <= sizeof j->inl) { memcpy(j->inl, info, len); j->useInl = 1; } else j->info = info;
    HANDLE t = CreateThread(NULL, 0, cb_thread, j, 0, NULL);
    if (!t) { free(j); return FALSE; }
    CloseHandle(t);
    return TRUE;
}

/* ---------- hooked exports ---------- */
HINTERNET WINAPI WinHttpOpen(LPCWSTR agent, DWORD access, LPCWSTR proxy, LPCWSTR bypass, DWORD flags)
{
    HINTERNET h = Real_WinHttpOpen(agent, access, proxy, bypass, flags);
    if (h) {
        Sess *s = calloc(1, sizeof *s); s->h = h; s->async = (flags & FLAG_ASYNC) != 0;
        EnterCriticalSection(&cs); s->next = sessions; sessions = s; LeaveCriticalSection(&cs);
    }
    logw(L"WinHttpOpen agent=\"%ls\" async=%d -> %p", agent ? agent : L"", (flags & FLAG_ASYNC) != 0, h);
    return h;
}

HINTERNET WINAPI WinHttpConnect(HINTERNET session, LPCWSTR host, WORD port, DWORD reserved)
{
    if (!is_blocked(host)) {
        HINTERNET h = Real_WinHttpConnect(session, host, port, reserved);
        logw(L"connect %ls:%u (allowed) -> %p", host ? host : L"?", port, h);
        return h;
    }
    Fake *f = calloc(1, sizeof *f); f->magic = 'OFFL'; f->kind = 1; f->session = session;
    EnterCriticalSection(&cs);
    Sess *s = find_sess(session);
    if (s) { f->async = s->async; f->cb = s->cb; f->flags = s->flags; }
    f->next = fakes; fakes = f;
    LeaveCriticalSection(&cs);
    wcsncpy(f->host, host, 255);
    logw(L"connect %ls:%u %ls -> local %p", host, port, emulate ? L"EMULATED" : L"BLOCKED", f);
    return (HINTERNET)f;
}

HINTERNET WINAPI WinHttpOpenRequest(HINTERNET c, LPCWSTR verb, LPCWSTR path, LPCWSTR ver, LPCWSTR ref, LPCWSTR *types, DWORD flags)
{
    Fake *p = find_fake(c);
    if (!p) return Real_WinHttpOpenRequest(c, verb, path, ver, ref, types, flags);
    Fake *f = calloc(1, sizeof *f); f->magic = 'OFFL'; f->kind = 2; f->session = p->session;
    f->async = p->async; f->cb = p->cb; f->flags = p->flags;
    wcsncpy(f->host, p->host, 255);
    wcsncpy(f->verb, verb ? verb : L"GET", 15);
    wcsncpy(f->path, path ? path : L"/", 1023);
    EnterCriticalSection(&cs); f->next = fakes; fakes = f; LeaveCriticalSection(&cs);
    return (HINTERNET)f;
}

BOOL WINAPI WinHttpAddRequestHeaders(HINTERNET r, LPCWSTR hdr, DWORD len, DWORD mod)
{
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpAddRequestHeaders(r, hdr, len, mod);
    return TRUE; /* logged with the send */
}

BOOL WINAPI WinHttpSendRequest(HINTERNET r, LPCWSTR hdr, DWORD hlen, LPVOID opt, DWORD olen, DWORD total, DWORD_PTR ctx)
{
    net_started = 1;
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpSendRequest(r, hdr, hlen, opt, olen, total, ctx);
    f->ctx = ctx;
    if (olen && opt) { f->req = malloc(olen); memcpy(f->req, opt, olen); f->reqLen = olen; }
    logw(L"%ls %ls  [%ls]", f->verb, f->path, f->host);
    log_headers(hdr, hlen);
    if (is_signin(f)) { if (olen) logw(L"    request (%lu bytes): <sign-in, redacted>", olen); }
    else log_body("request", opt, olen);

    if (emulate) {
        respond(f->verb, f->path, f->req, f->reqLen, &f->resp);
        f->haveResp = TRUE; f->readPos = 0;
        logw(L"    -> %d (%zu bytes)", f->resp.status, f->resp.len);
        if (!is_signin(f)) log_body("response", f->resp.body, f->resp.len);
        if (f->async && post_cb(f, CB_SENDREQUEST_COMPLETE, NULL, 0, FALSE)) return TRUE;
        return TRUE; /* sync, or the game didn't ask for the notification */
    }

    if (f->async) {
        ASYNC_RESULT res = { API_SEND_REQUEST, ERR_CANNOT_CONNECT };
        if (post_cb(f, CB_REQUEST_ERROR, &res, sizeof res, TRUE)) return TRUE;
    }
    SetLastError(ERR_CANNOT_CONNECT);
    return FALSE;
}

BOOL WINAPI WinHttpWriteData(HINTERNET r, LPCVOID b, DWORD n, LPDWORD w)
{
    if (!find_fake(r)) return Real_WinHttpWriteData(r, b, n, w);
    SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE;
}

BOOL WINAPI WinHttpReceiveResponse(HINTERNET r, LPVOID x)
{
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpReceiveResponse(r, x);
    if (!f->haveResp) { SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE; }
    if (f->async) post_cb(f, CB_HEADERS_AVAILABLE, NULL, 0, FALSE);
    return TRUE;
}

/* the emulated response's headers, as WinHTTP would report them */
static void header_text(Fake *f, DWORD level, LPCWSTR name, WCHAR *out, size_t cap, BOOL *found)
{
    *found = TRUE; out[0] = 0;
    switch (level) {
    case QUERY_STATUS_CODE: _snwprintf(out, cap, L"%d", f->resp.status); break;
    case QUERY_STATUS_TEXT: _snwprintf(out, cap, L"%ls", f->resp.status == 200 ? L"OK" : L"Error"); break;
    case QUERY_CONTENT_TYPE: _snwprintf(out, cap, L"application/x-ag-binary"); break;
    case QUERY_CONTENT_LENGTH: _snwprintf(out, cap, L"%zu", f->resp.len); break;
    case QUERY_RAW_HEADERS_CRLF:
        _snwprintf(out, cap, L"HTTP/1.1 %d %ls\r\nContent-Type: application/x-ag-binary\r\nContent-Length: %zu\r\n\r\n",
                   f->resp.status, f->resp.status == 200 ? L"OK" : L"Error", f->resp.len); break;
    case QUERY_CUSTOM:
        if (name && !_wcsicmp(name, L"Content-Type")) _snwprintf(out, cap, L"application/x-ag-binary");
        else *found = FALSE;
        break;
    default: *found = FALSE;
    }
    out[cap - 1] = 0;
}

BOOL WINAPI WinHttpQueryHeaders(HINTERNET r, DWORD info, LPCWSTR name, LPVOID buf, LPDWORD blen, LPDWORD idx)
{
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpQueryHeaders(r, info, name, buf, blen, idx);
    if (!f->haveResp) { SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE; }
    WCHAR txt[512]; BOOL found;
    if ((info & 0xFFFF) == QUERY_RAW_HEADERS) { /* NUL-separated lines, double-NUL terminated */
        header_text(f, QUERY_RAW_HEADERS_CRLF, NULL, txt, 512, &found);
        DWORD n = 0;
        for (WCHAR *s = txt; *s; s++) { if (s[0] == L'\r' && s[1] == L'\n') { txt[n++] = 0; s++; } else txt[n++] = *s; }
        while (n >= 2 && txt[n - 1] == 0 && txt[n - 2] == 0) n--; /* the CRLF form ends with an empty line */
        txt[n++] = 0;
        DWORD need = n * sizeof(WCHAR);
        if (!buf || !blen || *blen < need) { if (blen) *blen = need; SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE; }
        memcpy(buf, txt, need); *blen = need - sizeof(WCHAR);
        return TRUE;
    }
    header_text(f, info & 0xFFFF, name, txt, 512, &found);
    if (!found) { logw(L"    (game asked for header level %lu %ls: not present)", info & 0xFFFF, name ? name : L""); SetLastError(ERR_HEADER_NOT_FOUND); return FALSE; }
    if (info & QUERY_FLAG_NUMBER) {
        if (!buf || !blen || *blen < sizeof(DWORD)) { if (blen) *blen = sizeof(DWORD); SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE; }
        *(DWORD *)buf = wcstoul(txt, NULL, 10); *blen = sizeof(DWORD);
        return TRUE;
    }
    DWORD need = (DWORD)((wcslen(txt) + 1) * sizeof(WCHAR));
    if (!buf || !blen || *blen < need) { if (blen) *blen = need; SetLastError(ERROR_INSUFFICIENT_BUFFER); return FALSE; }
    memcpy(buf, txt, need); *blen = need - sizeof(WCHAR);
    return TRUE;
}

BOOL WINAPI WinHttpQueryDataAvailable(HINTERNET r, LPDWORD n)
{
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpQueryDataAvailable(r, n);
    if (!f->haveResp) { SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE; }
    DWORD avail = (DWORD)(f->resp.len - f->readPos);
    if (n) *n = avail;
    if (f->async) post_cb(f, CB_DATA_AVAILABLE, &avail, sizeof avail, TRUE);
    return TRUE;
}

BOOL WINAPI WinHttpReadData(HINTERNET r, LPVOID b, DWORD n, LPDWORD rd)
{
    Fake *f = find_fake(r);
    if (!f) return Real_WinHttpReadData(r, b, n, rd);
    if (!f->haveResp) { SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE; }
    size_t left = f->resp.len - f->readPos;
    DWORD c = (DWORD)(left < n ? left : n);
    if (c) memcpy(b, f->resp.body + f->readPos, c);
    f->readPos += c;
    if (rd) *rd = c;
    if (f->async) post_cb(f, CB_READ_COMPLETE, b, c, FALSE); /* info = the caller's buffer, length = bytes read */
    return TRUE;
}

BOOL WINAPI WinHttpQueryOption(HINTERNET h, DWORD o, LPVOID b, LPDWORD n)
{
    Fake *f = find_fake(h);
    if (!f) return Real_WinHttpQueryOption(h, o, b, n);
    if (o == 45 /* CONTEXT_VALUE */ && b && n && *n >= sizeof(DWORD_PTR)) { *(DWORD_PTR *)b = f->ctx; *n = sizeof(DWORD_PTR); return TRUE; }
    SetLastError(ERR_INCORRECT_HANDLE_STATE); return FALSE;
}

BOOL WINAPI WinHttpSetTimeouts(HINTERNET h, int a, int b, int c, int d)
{
    if (find_fake(h)) return TRUE;
    return Real_WinHttpSetTimeouts(h, a, b, c, d);
}

BOOL WINAPI WinHttpSetOption(HINTERNET h, DWORD o, LPVOID b, DWORD n)
{
    Fake *f = find_fake(h);
    if (f) { if (o == 45 /* CONTEXT_VALUE */ && b && n >= sizeof(DWORD_PTR)) f->ctx = *(DWORD_PTR *)b; return TRUE; }
    return Real_WinHttpSetOption(h, o, b, n);
}

STATUS_CB WINAPI WinHttpSetStatusCallback(HINTERNET h, STATUS_CB cb, DWORD flags, DWORD_PTR reserved)
{
    Fake *f = find_fake(h);
    if (f) { STATUS_CB old = f->cb; f->cb = cb; f->flags = flags; return old; }
    STATUS_CB old = Real_WinHttpSetStatusCallback(h, cb, flags, reserved);
    EnterCriticalSection(&cs);
    Sess *s = find_sess(h);
    if (s && old != INVALID_CB) { s->cb = cb; s->flags = flags; }
    LeaveCriticalSection(&cs);
    return old;
}

BOOL WINAPI WinHttpCloseHandle(HINTERNET h)
{
    Fake *f = find_fake(h);
    if (!f) {
        EnterCriticalSection(&cs);
        for (Sess **pp = &sessions; *pp; pp = &(*pp)->next) if ((*pp)->h == h) { Sess *s = *pp; *pp = s->next; free(s); break; }
        LeaveCriticalSection(&cs);
        return Real_WinHttpCloseHandle(h);
    }
    if (f->cb && f->cb != INVALID_CB && (f->flags & CB_HANDLE_CLOSING)) {
        HINTERNET hv = h;
        f->cb(h, f->ctx, CB_HANDLE_CLOSING, &hv, sizeof hv);
    }
    EnterCriticalSection(&cs);
    for (Fake **pp = &fakes; *pp; pp = &(*pp)->next) if (*pp == f) { *pp = f->next; break; }
    f->dead = 1;
    LeaveCriticalSection(&cs);
    if (f->inflight) {
        if (f->cbThread == GetCurrentThreadId()) return TRUE; /* closed inside its own callback: cb_thread frees it */
        while (f->inflight) Sleep(1);
    }
    free(f->req); resp_free(&f->resp); free(f);
    return TRUE;
}

/* ---------- crash reporter ----------
 * On an access violation in the game module, log the faulting address and the return addresses found on the
 * stack (exe-relative, so they match the Ghidra project at base 0x140000000), then let the crash proceed. */
static LONG CALLBACK crash_report(PEXCEPTION_POINTERS ep)
{
    static volatile LONG count;
    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    HMODULE exe = GetModuleHandleW(NULL);
    ULONG_PTR lo = (ULONG_PTR)exe, hi = lo + 0x8000000, rip = ep->ContextRecord->Rip;
    if (rip < lo || rip >= hi || InterlockedIncrement(&count) > 20) return EXCEPTION_CONTINUE_SEARCH; /* the last one logged is the fatal one */
    logw(L"CRASH: access violation at exe+0x%llX (0x%llX), %ls address 0x%llX; rcx=0x%llX rdx=0x%llX",
         (unsigned long long)(rip - lo), (unsigned long long)(rip - lo + 0x140000000ULL),
         ep->ExceptionRecord->ExceptionInformation[0] ? L"writing" : L"reading",
         (unsigned long long)ep->ExceptionRecord->ExceptionInformation[1],
         (unsigned long long)ep->ContextRecord->Rcx, (unsigned long long)ep->ContextRecord->Rdx);
    ULONG_PTR *sp = (ULONG_PTR *)ep->ContextRecord->Rsp;
    int found = 0;
    for (int i = 0; i < 2048 && found < 16; i++) {
        ULONG_PTR v;
        if (IsBadReadPtr(sp + i, sizeof v)) break;
        v = sp[i];
        if (v > lo + 0x1000 && v < hi) { logw(L"  stack[%d] 0x%llX", i, (unsigned long long)(v - lo + 0x140000000ULL)); found++; }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

/* ---------- unique NPC GUIDs (v0.11, 2026-10-20) ----------
 * The game names each Nemesis member "<prefix>_NPC_<n>" (id writer at exe+0x1B2F174, into member+0x3D0, only while empty), with
 * <prefix> = a 32-hex session GUID at analytics-manager+0xA81 (set by exe+0x1B2F220 only when online) and n a global
 * counter that restarts at 0 every launch. Offline the prefix stays empty, so every session hands out _NPC_0, _NPC_1...
 * again: the 2026-10-20 save held 359 bare ids, _NPC_0 alone on 36 captains. A captain whose id is already taken fails
 * the Garrison predicate HasNPCGUID ("You cannot send this Follower to the Garrison"). Fix: write a fresh random prefix
 * (like the online session GUID) once the game's first request is out and the manager is stable (v0.12, below), and
 * again whenever the game clears it.
 * Manager = *(*(exe+0x26FFAA8) + 0x6D18) (Ghidra base 0x140000000). Ini [Offline] NpcGuidPrefix=0 turns it off. */
static char npc_prefix[33];

static BOOL readable(const void *p, size_t n) { return p && !IsBadReadPtr(p, n); }


/* v0.12 (2026-10-20): v0.11 wrote as soon as the manager pointer existed (15:02:00, before any network call) and that
 * session made no online requests at all -> Garrison locked. Now: wait for the first request, then 10 s; the manager
 * pointer must be unchanged for 5 polls; the whole 64-byte prefix area must be zero; plain store (heap is writable,
 * no VirtualProtect). Writes once per manager pointer; re-checks every 2 s in case the game clears it. */
static DWORD WINAPI npc_guid_thread(LPVOID unused)
{
    ULONG_PTR exe = (ULONG_PTR)GetModuleHandleW(NULL);
    ULONG_PTR *g = (ULONG_PTR *)(exe + 0x26FFAA8);
    ULONG_PTR last = 0, done = 0; int stable = 0, writes = 0;
    while (!net_started) Sleep(250);
    Sleep(10000);
    for (;; Sleep(1000)) {
        if (!readable(g, 8) || !*g || !readable((void *)(*g + 0x6D18), 8)) { stable = 0; continue; }
        ULONG_PTR mgr = *(ULONG_PTR *)(*g + 0x6D18);
        if (!mgr || !readable((void *)(mgr + 0xA81), 64)) { stable = 0; continue; }
        if (mgr != last) { last = mgr; stable = 0; continue; }
        if (++stable < 5) continue;
        char *pre = (char *)(mgr + 0xA81);
        int empty = 1; for (int i = 0; i < 64; i++) if (pre[i]) { empty = 0; break; }
        if (!empty) {
            if (done != mgr) { logw(L"NPC GUID prefix present: %.32hs", pre); done = mgr; }
            Sleep(1000);
            continue;
        }
        memcpy(pre, npc_prefix, 33);
        done = mgr; writes++;
        logw(L"NPC GUID prefix written (%d): new captains get %hs_NPC_<n>", writes, npc_prefix);
    }
    return 0;
}

static void npc_guid_init(void)
{
    LARGE_INTEGER q; QueryPerformanceCounter(&q);
    unsigned long long s = q.QuadPart ^ ((unsigned long long)GetTickCount64() << 21) ^ ((unsigned long long)GetCurrentProcessId() << 40)
                           ^ (unsigned long long)time(NULL) * 0x9E3779B97F4A7C15ULL;
    for (int i = 0; i < 32; i++) {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17;
        npc_prefix[i] = "0123456789abcdef"[(s >> 11) & 15];
    }
    npc_prefix[32] = 0;
    CreateThread(NULL, 0, npc_guid_thread, NULL, 0, NULL);
}

/* ---------- setup ---------- */
static void load_config(HMODULE self)
{
    WCHAR dir[MAX_PATH], ini[MAX_PATH], logp[MAX_PATH], list[2048], mode[32];
    GetModuleFileNameW(self, dir, MAX_PATH);
    WCHAR *slash = wcsrchr(dir, L'\\'); if (slash) slash[1] = 0;
    _snwprintf(ini, MAX_PATH, L"%lsOfflineMode.ini", dir);
    _snwprintf(logp, MAX_PATH, L"%lsOfflineMode.log", dir);
    GetPrivateProfileStringW(L"Offline", L"BlockedDomains",
        L"wbagora.com,agoragames.com,wbgames.com,turbine.com,wbplay.com,wbidams.com", list, 2048, ini);
    for (WCHAR *ctx = NULL, *t = wcstok(list, L", ", &ctx); t && nblocked < 32; t = wcstok(NULL, L", ", &ctx))
        wcsncpy(blocked[nblocked++], t, 63);
    GetPrivateProfileStringW(L"Offline", L"Mode", L"emulate", mode, 32, ini);
    emulate = _wcsicmp(mode, L"block") != 0;
    if (GetPrivateProfileIntW(L"Offline", L"Log", 1, ini)) logf = _wfopen(logp, L"w, ccs=UTF-8");
    WCHAR data[MAX_PATH]; _snwprintf(data, MAX_PATH, L"%lsOfflineGarrison.dat", dir);
    { extern int storePlaceholders; storePlaceholders = GetPrivateProfileIntW(L"Offline", L"StorePlaceholders", 1, ini); }
    responder_init(data, GetPrivateProfileIntW(L"Offline", L"GarrisonSize", 50, ini));
    logw(L"Shadow of War Offline Mode, mode=%ls. WB/Agora hosts never reach the network:", emulate ? L"emulate" : L"block");
    for (int i = 0; i < nblocked; i++) logw(L"  *.%ls", blocked[i]);
    if (GetPrivateProfileIntW(L"Offline", L"NpcGuidPrefix", 1, ini)) npc_guid_init();
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID res)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        InitializeCriticalSection(&cs);
        WCHAR sys[MAX_PATH]; GetSystemDirectoryW(sys, MAX_PATH); wcscat(sys, L"\\winhttp.dll");
        HMODULE real = LoadLibraryW(sys);
        if (!real) return FALSE;
        for (int i = 0; i < REAL_COUNT; i++) real_ptrs[i] = (void *)GetProcAddress(real, real_names[i]);
        load_config(inst);
        AddVectoredExceptionHandler(0, crash_report); /* last in line: only reports, never handles */
    }
    return TRUE;
}
