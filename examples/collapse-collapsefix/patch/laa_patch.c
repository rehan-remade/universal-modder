/* laa_patch: set the Large Address Aware flag on the user's own collapse.exe (Collapse, 2008, Steam 289620).
 * The same patcher as laa_patch.py, for players without Python.
 *
 * Why: the engine's init_heap reserves all free address space below 0x70000000 before WinMain, leaving little
 * for the D3D driver, file mappings and DLLs. LAA gives the process 2 GB more above 0x80000000.
 *
 * Changes exactly one bit (IMAGE_FILE_LARGE_ADDRESS_AWARE, 0x20 in the COFF Characteristics) and nothing else.
 * Only a known build is patched (SHA-256), the original is kept as collapse.exe.bak, and --restore puts it back.
 *
 *     laa_patch.exe                      collapse.exe next to laa_patch.exe (double-click it in the game folder)
 *     laa_patch.exe <path\collapse.exe>  or drop collapse.exe onto laa_patch.exe
 *     laa_patch.exe [path] --dry-run     only report
 *     laa_patch.exe [path] --restore     put the backup back
 *
 * Build: build.ps1 (zig cc, x86-windows-gnu, Unicode paths, bcrypt for SHA-256).
 */
#include <windows.h>
#include <bcrypt.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#define LAA 0x20
static const struct { const char *sha256, *build; } KNOWN[] = {
    {"3003600f506e4c1e9388716cc395fb958ef2d729ec8d291138b3f57f3bded283", "Steam 289620 (PE 2008-10-13)"},
};

static int g_pause; /* started from Explorer: keep the window open at the end */

/* A double-click or a drop starts us from explorer.exe. Asking the console how many processes share it does not
   work under Windows Terminal, the Windows 11 default, so look at the parent process instead. */
static int started_from_explorer(void) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32W e;
    DWORD me = GetCurrentProcessId(), parent = 0;
    int found = 0;
    if (snap == INVALID_HANDLE_VALUE) return 0;
    e.dwSize = sizeof e;
    for (BOOL ok = Process32FirstW(snap, &e); ok; ok = Process32NextW(snap, &e))
        if (e.th32ProcessID == me) parent = e.th32ParentProcessID;
    e.dwSize = sizeof e;
    for (BOOL ok = Process32FirstW(snap, &e); ok && parent; ok = Process32NextW(snap, &e))
        if (e.th32ProcessID == parent) found = !_wcsicmp(e.szExeFile, L"explorer.exe");
    CloseHandle(snap);
    return found;
}

static int finish(int code) {
    if (g_pause) {
        printf("\nPress Enter to close.");
        getchar();
    }
    return code;
}
static int fail(const char *msg) {
    printf("ERROR: %s\n", msg);
    return finish(1);
}

static unsigned char *read_all(const wchar_t *path, DWORD *size) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    unsigned char *buf;
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) return NULL;
    *size = GetFileSize(h, NULL);
    buf = *size != INVALID_FILE_SIZE ? malloc(*size ? *size : 1) : NULL;
    if (buf && (!ReadFile(h, buf, *size, &got, NULL) || got != *size)) free(buf), buf = NULL;
    CloseHandle(h);
    return buf;
}

static void sha256_hex(const unsigned char *data, DWORD size, char out[65]) {
    BCRYPT_ALG_HANDLE alg;
    unsigned char hash[32];
    int i;
    out[0] = 0;
    if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, NULL, 0) != 0) return;
    if (BCryptHash(alg, NULL, 0, (PUCHAR)data, size, hash, sizeof hash) == 0)
        for (i = 0; i < 32; i++) sprintf(out + 2 * i, "%02x", hash[i]);
    BCryptCloseAlgorithmProvider(alg, 0);
}

static const char *known_build(const char *hex) {
    unsigned i;
    for (i = 0; i < sizeof KNOWN / sizeof KNOWN[0]; i++)
        if (!strcmp(hex, KNOWN[i].sha256)) return KNOWN[i].build;
    return NULL;
}

/* printf's %ls stops at the first character outside the C locale (a Cyrillic folder name), so paths go out as UTF-8 */
static void print_path(const char *label, const wchar_t *path) {
    char utf8[4 * MAX_PATH];
    if (!WideCharToMultiByte(CP_UTF8, 0, path, -1, utf8, sizeof utf8, NULL, NULL)) strcpy(utf8, "?");
    printf("%s%s\n", label, utf8);
}

/* offset of the COFF Characteristics field, or 0 with a message */
static DWORD char_offset(const unsigned char *d, DWORD size) {
    DWORD pe;
    if (size < 0x40 || d[0] != 'M' || d[1] != 'Z') return printf("ERROR: not an MZ executable\n"), 0;
    pe = *(const DWORD *)(d + 0x3C);
    if (pe > size - 24 || memcmp(d + pe, "PE\0\0", 4)) return printf("ERROR: no PE signature\n"), 0;
    if (*(const WORD *)(d + pe + 4) != 0x14C) return printf("ERROR: not an x86 (i386) image\n"), 0;
    return pe + 4 + 18; /* COFF header: Machine, NumberOfSections, TimeDateStamp, PtrSym, NumSym, SizeOptHdr */
}

int wmain(int argc, wchar_t **argv) {
    wchar_t exe[MAX_PATH + 16] = {0}, bak[MAX_PATH + 16], tmp[MAX_PATH + 16];
    int dry = 0, restore = 0, i;
    DWORD size, list[2], off;
    unsigned char *data;
    char hex[65];
    const char *build;
    WORD ch;

    g_pause = GetConsoleProcessList(list, 2) == 1 || started_from_explorer();
    SetConsoleOutputCP(CP_UTF8);
    for (i = 1; i < argc; i++) {
        if (!wcscmp(argv[i], L"--dry-run")) dry = 1;
        else if (!wcscmp(argv[i], L"--restore")) restore = 1;
        else if (!wcscmp(argv[i], L"--help") || !wcscmp(argv[i], L"-h") || !wcscmp(argv[i], L"/?")) {
            printf("laa_patch [path\\collapse.exe] [--dry-run] [--restore]\n"
                   "Sets the Large Address Aware bit on Collapse (2008, Steam) and keeps collapse.exe.bak.\n"
                   "Without a path it uses collapse.exe next to laa_patch.exe.\n");
            return finish(0);
        } else if (wcslen(argv[i]) < MAX_PATH) wcscpy(exe, argv[i]);
        else return fail("path too long");
    }
    if (!exe[0]) { /* collapse.exe next to this patcher */
        DWORD n = GetModuleFileNameW(NULL, exe, MAX_PATH);
        wchar_t *slash;
        if (!n || n >= MAX_PATH) return fail("cannot find my own folder");
        slash = wcsrchr(exe, L'\\');
        wcscpy(slash ? slash + 1 : exe, L"collapse.exe");
    }
    swprintf(bak, MAX_PATH + 16, L"%ls.bak", exe);
    swprintf(tmp, MAX_PATH + 16, L"%ls.laa_tmp", exe);
    print_path("collapse.exe: ", exe);

    if (restore) {
        if (!(data = read_all(bak, &size))) return fail("no backup (collapse.exe.bak) next to the exe");
        sha256_hex(data, size, hex);
        free(data);
        if (!(build = known_build(hex))) {
            printf("backup sha256 %s\n", hex);
            return fail("the backup is not a known original, refusing");
        }
        if (!dry && !CopyFileW(bak, exe, FALSE)) return fail("could not copy the backup over collapse.exe (is the game running?)");
        printf("%srestored from collapse.exe.bak (%s)\n", dry ? "would be " : "", build);
        return finish(0);
    }

    if (!(data = read_all(exe, &size))) return fail("cannot read collapse.exe (wrong folder?)");
    if (!(off = char_offset(data, size))) return free(data), finish(1);
    ch = *(WORD *)(data + off);
    if (ch & LAA) {
        printf("already Large Address Aware (Characteristics=0x%04x), nothing to do\n", ch);
        return free(data), finish(0);
    }
    sha256_hex(data, size, hex);
    if (!(build = known_build(hex))) {
        printf("sha256 %s\n", hex);
        return free(data), fail("unknown collapse.exe; only known builds are patched");
    }
    printf("%s, Characteristics 0x%04x -> 0x%04x\n", build, ch, ch | LAA);
    if (dry) return free(data), finish(0);

    if (GetFileAttributesW(bak) != INVALID_FILE_ATTRIBUTES) {
        DWORD bsize;
        unsigned char *b = read_all(bak, &bsize);
        char bhex[65] = "";
        if (b) sha256_hex(b, bsize, bhex), free(b);
        if (strcmp(bhex, hex)) return free(data), fail("collapse.exe.bak exists and differs from this exe; not overwriting it");
    } else if (!CopyFileW(exe, bak, TRUE)) {
        return free(data), fail("could not write collapse.exe.bak (folder read-only? game running?)");
    }

    *(WORD *)(data + off) = ch | LAA;
    {
        HANDLE src = CreateFileW(exe, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        HANDLE dst = CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        FILETIME c, a, w;
        DWORD put = 0;
        int ok = dst != INVALID_HANDLE_VALUE && WriteFile(dst, data, size, &put, NULL) && put == size;
        if (ok && src != INVALID_HANDLE_VALUE && GetFileTime(src, &c, &a, &w)) SetFileTime(dst, &c, &a, &w);
        if (src != INVALID_HANDLE_VALUE) CloseHandle(src);
        if (dst != INVALID_HANDLE_VALUE) CloseHandle(dst);
        if (!ok || !MoveFileExW(tmp, exe, MOVEFILE_REPLACE_EXISTING)) {
            DeleteFileW(tmp);
            return free(data), fail("could not replace collapse.exe (is the game running?)");
        }
    }
    sha256_hex(data, size, hex);
    free(data);
    printf("patched; backup at collapse.exe.bak; new sha256 %s\n", hex);
    return finish(0);
}
