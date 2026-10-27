// TWAU_GMod.asi entry: log, paths, and the init sequence (on a worker thread, never under the loader lock).
#include <MinHook.h>

#include <deque>
#include <mutex>

#include "Sandbox.h"

namespace gm {

static Paths g_paths;
Paths& GetPaths() { return g_paths; }

static std::mutex g_logMu;
static std::deque<std::string> g_logLines;
static FILE* g_logFile = nullptr;

static LONG CALLBACK CrashNote(EXCEPTION_POINTERS* x);

void Log(const char* fmt, ...) {
    char buf[2048];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    std::lock_guard<std::mutex> lk(g_logMu);
    if (g_logFile) {
        SYSTEMTIME t;
        GetLocalTime(&t);
        fprintf(g_logFile, "%02d:%02d:%02d.%03d %s\n", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds, buf);
        fflush(g_logFile);
    }
    g_logLines.push_back(buf);
    if (g_logLines.size() > 400) g_logLines.pop_front();
}

std::vector<std::string> RecentLog(size_t maxLines) {
    std::lock_guard<std::mutex> lk(g_logMu);
    size_t n = std::min(maxLines, g_logLines.size());
    return std::vector<std::string>(g_logLines.end() - n, g_logLines.end());
}

static void ReadIniPaths() {
    FILE* f = fopen((g_paths.modDir + "\\gmod_sandbox.ini").c_str(), "r");
    if (!f) return;
    char line[1024];
    while (fgets(line, sizeof line, f)) {
        std::string s(line);
        while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
        if (s.rfind("gmodRoot=", 0) == 0) g_paths.gmodRoot = s.substr(9);
    }
    fclose(f);
}

// Runs inside DllMain, before the game's entry point: paths, log and MinHook only.
static bool EarlySetup() {
    char exe[MAX_PATH];
    GetModuleFileNameA(nullptr, exe, MAX_PATH);
    std::string dir(exe);
    dir.resize(dir.find_last_of('\\'));
    g_paths.twauRoot = dir;
    g_paths.modDir = dir + "\\gmod";
    CreateDirectoryA(g_paths.modDir.c_str(), nullptr);
    g_logFile = fopen((g_paths.modDir + "\\gmod_sandbox.log").c_str(), "w");
    ReadIniPaths();
    Log("TWAU GMod Sandbox 0.1.0 (built " __DATE__ ") in %s", exe);
    AddVectoredExceptionHandler(0, CrashNote);
    if (MH_Initialize() != MH_OK) {
        Log("MinHook init failed");
        return false;
    }

    return true;
}

// Crash notes: the first access violations inside the exe go to the log with the registers, the call chain
// and every string the stack points at (resource names being loaded), before the game dies.
static LONG CALLBACK CrashNote(EXCEPTION_POINTERS* x) {
    static volatile LONG notes = 0;
    if (x->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION) return EXCEPTION_CONTINUE_SEARCH;
    uintptr_t exe = (uintptr_t)GetModuleHandleA(nullptr);
    CONTEXT* c = x->ContextRecord;
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery((void*)exe, &mbi, sizeof mbi) || c->Eip < exe || c->Eip > exe + 0x1000000) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedIncrement(&notes) > 3) return EXCEPTION_CONTINUE_SEARCH;
    Log("[crash] access violation at exe+%06x (%s %08x) eax %08x ebx %08x ecx %08x edx %08x esi %08x edi %08x",
        (unsigned)(c->Eip - exe), x->ExceptionRecord->ExceptionInformation[0] ? "writing" : "reading",
        (unsigned)x->ExceptionRecord->ExceptionInformation[1], c->Eax, c->Ebx, c->Ecx, c->Edx, c->Esi, c->Edi);
    std::string chain;
    uint32_t fp = c->Ebp;
    for (int i = 0; i < 12; ++i) {
        uint32_t ret = 0, next = 0;
        if (IsBadReadPtr((void*)fp, 8)) break;
        memcpy(&next, (void*)fp, 4);
        memcpy(&ret, (void*)(fp + 4), 4);
        char b[16];
        snprintf(b, sizeof b, " %06x", (unsigned)(ret - exe));
        chain += b;
        if (next <= fp) break;
        fp = next;
    }
    Log("[crash] callers%s", chain.c_str());
    // strings the stack points at, directly or through one pointer (std::string / Symbol holders)
    const uint32_t* sp = (const uint32_t*)c->Esp;
    int found = 0;
    for (int i = 0; i < 1024 && found < 24; ++i) {
        if (IsBadReadPtr(sp + i, 4)) break;
        for (int hop = 0; hop < 2; ++hop) {
            uint32_t v = sp[i];
            if (hop) { if (IsBadReadPtr((void*)v, 4)) break; v = *(const uint32_t*)v; }
            if (v < 0x10000 || IsBadReadPtr((void*)v, 6)) continue;
            const char* t = (const char*)v;
            int n = 0;
            while (n < 120 && t[n] >= 0x20 && t[n] < 0x7f) ++n;
            if (n >= 5 && t[n] == 0 && strchr(t, '.')) {
                Log("[crash]   stack+%03x%s: %s", i * 4, hop ? " ->" : "", t);
                ++found;
                break;
            }
        }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI InitThread(LPVOID) {
    hud::Init();
    // Lua first: the hook only needs the exe's code, which is plain on disk (see MODLOG.md).
    if (!lua::Init()) return 0;
    state::Init();
    combat::Init();
    // Assets: VPK trees + every .ttarch2 name table (about half a second).
    AssetBridge::Get().Init(g_paths);
    audio::Init();
    // No D3D9 work here: a device made on this thread raced the game's own and corrupted the heap (run 3).
    // The frame hooks are placed from the game thread (hud::LateHook, called by state::Tick).
    return 0;
}

}  // namespace gm

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        if (!gm::EarlySetup()) return TRUE;
        HANDLE t = CreateThread(nullptr, 0, gm::InitThread, nullptr, 0, nullptr);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
