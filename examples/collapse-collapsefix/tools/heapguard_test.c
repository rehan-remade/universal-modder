/* heapguard_test: C-58 without the game running. Maps a copy of collapse.exe as an image (no imports resolved, nothing
 * of it runs but one function), fills the two import slots that function uses, and calls the game's own allocator unmap
 * and collapsefix's replacement (game_unmap, taken from collapsefix.c) on the same made-up memory layouts.
 * Retail offsets are fine here: a local test tool, not shipped code.
 * Build: zig cc -target x86-windows-gnu -O1 -Wl,--image-base=0x20000000 -o heapguard_test.exe heapguard_test.c
 * Run:   heapguard_test.exe <copy of collapse.exe>
 */
#include "../patch/collapsefix.c"
#include <stdio.h>
#include <string.h>

#define RVA_UNMAP 0x1e5bb0
#define RVA_IAT_VQ 0x203110 /* VirtualQuery */
#define RVA_IAT_VF 0x2030e0 /* VirtualFree */
#define K64 0x10000u

typedef int(__cdecl *UnmapFn)(void **, void *, unsigned);
static int fails;

static const char *state(void *p) {
    MEMORY_BASIC_INFORMATION m;
    if (!VirtualQuery(p, &m, sizeof m)) return "?";
    return m.State == MEM_COMMIT ? "commit" : m.State == MEM_RESERVE ? "reserve" : "free";
}
/* want is what this implementation is expected to do: the game's bug, or the fix */
static void check(const char *who, const char *what, int got, int want) {
    printf("  %-6s %-47s got %-3s want %-3s %s\n", who, what, got ? "yes" : "no", want ? "yes" : "no",
           got == want ? "ok" : "MISMATCH");
    if (got != want) fails++;
}
/* A then B, adjacent: A a committed allocation of its own (n bytes), B a reserved one of 64K. B also stops the game's
   walk once its count has wrapped: without it the walk goes on into whatever the test process has mapped next. */
static unsigned char *two_adjacent(unsigned n) {
    unsigned char *x = VirtualAlloc(0, n + K64, MEM_RESERVE, PAGE_NOACCESS);
    VirtualFree(x, 0, MEM_RELEASE);
    if (VirtualAlloc(x, n, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) != x ||
        VirtualAlloc(x + n, K64, MEM_RESERVE, PAGE_NOACCESS) != x + n) {
        printf("could not place two allocations\n");
        ExitProcess(2);
    }
    x[0] = 0x5A;
    return x;
}
static void cleanup(unsigned char *a, unsigned char *b) {
    if (a) VirtualFree(a, 0, MEM_RELEASE);
    if (b) VirtualFree(b, 0, MEM_RELEASE);
}

static void run(const char *who, UnmapFn f, int fixed) {
    void *res[1];
    unsigned char *x, *r;
    int ret;
    printf("%s\n", who);

    /* P: the crash in the dump. A fails nothing, B fails the checks. */
    x = two_adjacent(K64);
    res[0] = (void *)1;
    ret = f(res, x, 2 * K64);
    printf(" P  segment over A (own allocation, committed) + B (reserved): ret %d, A %s\n", ret, state(x));
    check(who, "returns -1", ret == -1, 1);
    check(who, "A still committed (safe to put the chunk back)", strcmp(state(x), "commit") == 0, fixed);
    cleanup(strcmp(state(x), "free") ? x : 0, x + K64);

    /* O: a segment inside the reservation, with a live committed neighbour after it. */
    r = two_adjacent(3 * K64);
    r[K64] = 0x5A, r[2 * K64] = 0x5A;
    res[0] = r;
    ret = f(res, r, K64);
    printf(" O  first 64K of a reservation, neighbours committed: ret %d, %s / %s / %s\n", ret, state(r),
           state(r + K64), state(r + 2 * K64));
    check(who, "returns 0 (the game: -1 after the decommit)", ret == 0, fixed);
    check(who, "the segment is decommitted", strcmp(state(r), "reserve") == 0, 1);
    check(who, "neighbours still committed", strcmp(state(r + K64), "commit") == 0 && strcmp(state(r + 2 * K64), "commit") == 0,
          fixed);
    cleanup(r, r + 3 * K64);

    /* G: a plain allocation of its own. */
    x = VirtualAlloc(0, K64, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    res[0] = (void *)1;
    ret = f(res, x, K64);
    printf(" G  own allocation, whole: ret %d, %s\n", ret, state(x));
    check(who, "returns 0", ret == 0, 1);
    check(who, "released", strcmp(state(x), "free") == 0, 1);

    /* L: the last segment of a reservation. */
    r = VirtualAlloc(0, 3 * K64, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    res[0] = r;
    ret = f(res, r + 2 * K64, K64);
    printf(" L  last 64K of a reservation: ret %d, %s / %s\n", ret, state(r + K64), state(r + 2 * K64));
    check(who, "returns 0", ret == 0, 1);
    check(who, "only the segment decommitted", strcmp(state(r + K64), "commit") == 0 && strcmp(state(r + 2 * K64), "reserve") == 0,
          1);
    cleanup(r, 0);
}

static LONG WINAPI on_crash(EXCEPTION_POINTERS *e) {
    printf("crash %08lx at %p, address %p\n", e->ExceptionRecord->ExceptionCode, e->ExceptionRecord->ExceptionAddress,
           (void *)e->ExceptionRecord->ExceptionInformation[1]);
    ExitProcess(3);
}

int main(int argc, char **argv) {
    unsigned char *img;
    DWORD prot;
    int game_fails;
    setvbuf(stdout, 0, _IONBF, 0);
    SetUnhandledExceptionFilter(on_crash);
    if (argc < 2) return printf("usage: heapguard_test <copy of collapse.exe>\n"), 2;
    img = (unsigned char *)LoadLibraryExA(argv[1], 0, DONT_RESOLVE_DLL_REFERENCES);
    if (!img) return printf("cannot map %s: %lu\n", argv[1], GetLastError()), 2;
    if (img != (unsigned char *)0x400000) /* the exe has no relocations: its code reads absolute addresses */
        return printf("mapped at %p, not 0x400000 (the range was taken); run again\n", img), 2;
    if (memcmp(img + RVA_UNMAP, "\x83\xEC\x1C\x53\x8B\x5C\x24\x2C", 8))
        return printf("unexpected bytes at the unmap function, not the Steam exe?\n"), 2;
    VirtualProtect(img + RVA_IAT_VF, RVA_IAT_VQ - RVA_IAT_VF + 4, PAGE_READWRITE, &prot);
    *(void **)(img + RVA_IAT_VQ) = (void *)VirtualQuery;
    *(void **)(img + RVA_IAT_VF) = (void *)VirtualFree;
    printf("image at %p\n", img);

    run("game", (UnmapFn)(img + RVA_UNMAP), 0);
    game_fails = fails, fails = 0;
    run("fixed", (UnmapFn)game_unmap, 1);
    printf("\ngame: %s; fixed: %s\n", game_fails ? "did NOT behave as described in C-58" : "shows the C-58 bug",
           fails ? "FAIL" : "PASS");
    return fails || game_fails;
}
