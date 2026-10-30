// LuaBridge: see LuaBridge.h. RVAs come from MODLOG.md (TheWolfAmongUs.exe, Steam, PE time 1384476156).
#include "LuaBridge.h"

#include <MinHook.h>

#include <atomic>
#include <cstring>
#include <fstream>
#include <sstream>

namespace gm {
namespace lua {

Api api{};

namespace {
// VA - 0x400000. Identified from the stdlib luaL_Reg tables and luaopen_base (see MODLOG.md).
struct Rva {
    const char* name;
    uint32_t rva;
    void** slot;
};
const Rva kRvas[] = {
    {"lua_gettop", 0x4415B0, (void**)&api.gettop},       {"lua_settop", 0x4415D0, (void**)&api.settop},
    {"lua_insert", 0x441670, (void**)&api.insert},       {"lua_pushvalue", 0x441760, (void**)&api.pushvalue},
    {"lua_type", 0x441790, (void**)&api.type},           {"lua_typename", 0x4417B0, (void**)&api.typename_},
    {"lua_isnumber", 0x441800, (void**)&api.isnumber},   {"lua_tonumber", 0x441990, (void**)&api.tonumber},
    {"lua_toboolean", 0x441A10, (void**)&api.toboolean}, {"lua_tolstring", 0x441A40, (void**)&api.tolstring},
    {"lua_pushnumber", 0x441C30, (void**)&api.pushnumber}, {"lua_pushlstring", 0x441C70, (void**)&api.pushlstring},
    {"lua_pushstring", 0x441CC0, (void**)&api.pushstring}, {"lua_pushcclosure", 0x441D90, (void**)&api.pushcclosure},
    {"lua_pushboolean", 0x441E30, (void**)&api.pushboolean}, {"lua_getfield", 0x441ED0, (void**)&api.getfield},
    {"lua_createtable", 0x441FB0, (void**)&api.createtable}, {"lua_setfield", 0x4420F0, (void**)&api.setfield},
    {"lua_call", 0x442370, (void**)&api.call},           {"lua_pcall", 0x4423D0, (void**)&api.pcall},
    {"luaL_loadbuffer", 0x4430B0, (void**)&api.loadbuffer},
};
constexpr uint32_t kBaseLibTable = 0x61E4E8;  // luaL_Reg base_funcs[] in .rdata
constexpr uint8_t kPcallPrologue[] = {0x55, 0x8B, 0xEC, 0x8B, 0x4D, 0x14};

decltype(Api::pcall) g_origPcall = nullptr;
std::function<void(State*)> g_tick;
std::atomic<bool> g_tickRequested{false};
std::atomic<DWORD> g_lastTick{0};
std::atomic<bool> g_disabled{false};
DWORD g_gameThread = 0;
bool g_inTick = false;
bool g_ready = false;

void RunTick(State* L) {
    int top = api.gettop(L);
    g_tick(L);
    api.settop(L, top);
}
// No C++ objects with destructors here: SEH and unwinding don't mix.
bool SafeTick(State* L) {
    __try {
        RunTick(L);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

int __cdecl HookPcall(State* L, int nargs, int nresults, int errfunc) {
    if (!g_inTick && g_tick && !g_disabled) {
        DWORD now = GetTickCount();
        // One tick per rendered frame; time-based fallback if the D3D9 hook never requests one.
        bool due = g_tickRequested.exchange(false) || now - g_lastTick > 50;
        if (due && (g_gameThread == 0 || g_gameThread == GetCurrentThreadId())) {
            g_gameThread = GetCurrentThreadId();
            g_lastTick = now;
            g_inTick = true;
            // The engine's call already has its function and nargs on the stack: our tick restores the top.
            if (!SafeTick(L)) {
                g_disabled = true;
                Log("[lua] the mod tick raised an exception; sandbox disabled for this session");
            }
            g_inTick = false;
        }
    }
    return g_origPcall(L, nargs, nresults, errfunc);
}
// Reverse-engineering aid: if <game>\gmod\dump\ exists, every chunk the game compiles (the .lenc
// scripts, decrypted by then) is written there under its chunk name. Never ship or commit those files.
// Hooked at lua_load (RVA 0x4424F0, called by luaL_loadbuffer at 0x4430D3): script files don't go
// through luaL_loadbuffer.
typedef const char*(__cdecl* Reader)(State*, void*, size_t*);
typedef int(__cdecl* LoadFn)(State*, Reader, void*, const char*);
const uintptr_t kLuaLoadRva = 0x4424F0;
std::string g_dumpDir;
LoadFn g_origLoad = nullptr;

struct Capture {
    Reader reader;
    void* data;
    std::string bytes;
};

const char* __cdecl CaptureReader(State* L, void* ud, size_t* size) {
    Capture* c = (Capture*)ud;
    const char* p = c->reader(L, c->data, size);
    if (p && *size) c->bytes.append(p, *size);
    return p;
}

std::string DumpPath(const char* name) {
    std::string n(name ? name : "");
    if (!n.empty() && (n[0] == '@' || n[0] == '=')) n.erase(0, 1);
    if (n.empty() || n.rfind("console", 0) == 0 || n.rfind("gmod_sandbox", 0) == 0) return "";
    for (char& c : n)
        if (c == '\\' || c == '/' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' || c == '>' || c == '|')
            c = '_';
    if (n.size() > 120) n.resize(120);
    std::string path = g_dumpDir + "\\" + n;
    return GetFileAttributesA(path.c_str()) == INVALID_FILE_ATTRIBUTES ? path : "";
}

int __cdecl HookLoad(State* L, Reader reader, void* data, const char* name) {
    std::string path = DumpPath(name);
    if (path.empty()) return g_origLoad(L, reader, data, name);
    Capture c{reader, data, {}};
    int r = g_origLoad(L, &CaptureReader, &c, name);
    if (FILE* f = fopen(path.c_str(), "wb")) {
        fwrite(c.bytes.data(), 1, c.bytes.size(), f);
        fclose(f);
    }
    return r;
}

void HookScriptDump() {
    std::string dumpDir = GetPaths().modDir + "\\dump";
    DWORD attr = GetFileAttributesA(dumpDir.c_str());
    if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY)) return;
    g_dumpDir = dumpDir;
    void* load = (void*)((uintptr_t)GetModuleHandleA(nullptr) + kLuaLoadRva);
    if (MH_CreateHook(load, (void*)&HookLoad, (void**)&g_origLoad) == MH_OK && MH_EnableHook(load) == MH_OK)
        Log("[lua] dumping loaded scripts to %s", dumpDir.c_str());
}
// Natives that crash the game (a null scene handle) when a script asks about a scene that isn't loaded,
// which episode 2-5 scenes do when opened from episode 1. The guard returns nil instead and logs who asked.
struct Guarded { uint32_t rva; const char* name; CFunction orig; };
Guarded g_guarded[] = {
    {0x2cafb0, "SceneGetCamera", nullptr},  // registered at 0x5e4000
};
int CallGuarded(CFunction f, State* L, bool* faulted) {
    __try {
        return f(L);
    } __except (GetExceptionCode() == EXCEPTION_ACCESS_VIOLATION ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) {
        *faulted = true;
        return 0;
    }
}
template <int I>
int __cdecl GuardedNative(State* L) {
    int top = api.gettop(L);
    std::string arg = top >= 1 && api.type(L, 1) == TSTRING ? api.tolstring(L, 1, nullptr) : "(not a string)";
    bool faulted = false;
    int n = CallGuarded(g_guarded[I].orig, L, &faulted);
    if (!faulted) return n;
    api.settop(L, top);
    static int reports = 0;
    if (reports++ < 8) {
        std::string where;
        api.getfield(L, GLOBALSINDEX, "debug");
        if (api.type(L, -1) == TTABLE) {
            api.getfield(L, -1, "traceback");
            if (api.pcall(L, 0, 1, 0) == 0 && api.type(L, -1) == TSTRING) where = api.tolstring(L, -1, nullptr);
        }
        api.settop(L, top);
        for (auto& ch : where) if (ch == '\n' || ch == '\t') ch = ' ';
        Log("[guard] %s(%s) faulted; returning nil. %s", g_guarded[I].name, arg.c_str(), where.c_str());
    }
    api.settop(L, top + 1);  // nil
    return 1;
}
void GuardNatives(uintptr_t base) {
    CFunction hooks[] = {&GuardedNative<0>};
    for (int i = 0; i < (int)(sizeof g_guarded / sizeof g_guarded[0]); ++i) {
        void* target = (void*)(base + g_guarded[i].rva);
        unsigned char* code = (unsigned char*)target;
        bool ok = code[0] == 0x55 && code[1] == 0x8b && code[2] == 0xec &&  // push ebp; mov ebp, esp
                  MH_CreateHook(target, (void*)hooks[i], (void**)&g_guarded[i].orig) == MH_OK &&
                  MH_EnableHook(target) == MH_OK;
        Log("[lua] guard on %s: %s", g_guarded[i].name, ok ? "on" : "FAILED");
    }
}

}  // namespace

bool Init() {
    uintptr_t base = (uintptr_t)GetModuleHandleA(nullptr);
    // 1) Is this the build we reverse engineered? Compare the relocated base library table.
    struct Reg { const char* name; uintptr_t fn; };
    const Reg* t = (const Reg*)(base + kBaseLibTable);
    __try {
        if (strcmp(t[0].name, "assert") || t[0].fn != base + 0x458CA0 || strcmp(t[9].name, "loadstring") ||
            t[9].fn != base + 0x458A90 || strcmp(t[11].name, "pcall") || t[11].fn != base + 0x458E20) {
            Log("[lua] TheWolfAmongUs.exe is not the expected build (base lib table differs); Lua bridge off");
            return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log("[lua] could not read the base lib table; Lua bridge off");
        return false;
    }
    if (memcmp((void*)(base + 0x4423D0), kPcallPrologue, sizeof kPcallPrologue)) {
        Log("[lua] lua_pcall prologue differs (another hook?); Lua bridge off");
        return false;
    }
    for (auto& r : kRvas) *r.slot = (void*)(base + r.rva);
    if (MH_CreateHook((void*)api.pcall, (void*)&HookPcall, (void**)&g_origPcall) != MH_OK ||
        MH_EnableHook((void*)api.pcall) != MH_OK) {
        Log("[lua] could not hook lua_pcall");
        return false;
    }
    HookScriptDump();
    GuardNatives(base);
    g_ready = true;
    Log("[lua] Lua 5.1.4 (float) API bound at image base %p; lua_pcall hooked", (void*)base);
    return true;
}

bool Ready() { return g_ready && !g_disabled; }
void SetTickCallback(std::function<void(State*)> cb) { g_tick = std::move(cb); }
void RequestTick() { g_tickRequested = true; }

int AnchorGM(State* L) {
    int top = api.gettop(L);
    api.getfield(L, GLOBALSINDEX, "GM");
    if (api.type(L, -1) == TTABLE) {
        api.getfield(L, REGISTRYINDEX, "gm_sandbox.GM");
        bool anchored = api.type(L, -1) == TTABLE;
        api.settop(L, top + 1);
        if (!anchored) api.setfield(L, REGISTRYINDEX, "gm_sandbox.GM");  // pops GM
        api.settop(L, top);
        return 0;
    }
    api.settop(L, top);
    api.getfield(L, REGISTRYINDEX, "gm_sandbox.GM");
    if (api.type(L, -1) == TTABLE) {
        api.setfield(L, GLOBALSINDEX, "GM");
        api.settop(L, top);
        return 1;
    }
    api.settop(L, top);
    return 2;
}

// The original pcall, so our own calls don't re-enter the hook logic (they would be skipped anyway).
static int PCall(State* L, int nargs, int nres) { return g_origPcall(L, nargs, nres, 0); }

static std::string PopError(State* L) {
    size_t n = 0;
    const char* s = api.tolstring(L, -1, &n);
    std::string e = s ? std::string(s, n) : "(non-string error)";
    api.settop(L, -2);
    return e;
}

bool RunString(State* L, const std::string& code, const char* chunk, std::string* err) {
    int top = api.gettop(L);
    if (api.loadbuffer(L, code.data(), code.size(), chunk) != 0 || PCall(L, 0, 0) != 0) {
        std::string e = PopError(L);
        Log("[lua] %s: %s", chunk, e.c_str());
        if (err) *err = e;
        api.settop(L, top);
        return false;
    }
    api.settop(L, top);
    return true;
}

bool RunFile(State* L, const std::string& path, std::string* err) {
    std::ifstream f(path, std::ios::binary);
    if (!f) {
        if (err) *err = "cannot open " + path;
        Log("[lua] cannot open %s", path.c_str());
        return false;
    }
    std::stringstream ss;
    ss << f.rdbuf();
    std::string chunk = "@" + path.substr(path.find_last_of("\\/") + 1);
    return RunString(L, ss.str(), chunk.c_str(), err);
}

void Register(State* L, const char* name, CFunction fn) {
    api.pushcclosure(L, fn, 0);
    api.setfield(L, GLOBALSINDEX, name);
}

// Pushes a (possibly dotted) global; leaves exactly one value.
static void PushPath(State* L, const char* path) {
    const char* dot = strchr(path, '.');
    if (!dot) { api.getfield(L, GLOBALSINDEX, path); return; }
    std::string head(path, dot - path);
    api.getfield(L, GLOBALSINDEX, head.c_str());
    if (api.type(L, -1) != TTABLE) return;  // leaves a non-function; the call reports it
    api.getfield(L, -1, dot + 1);
    api.insert(L, -2);
    api.settop(L, -2);
}

Results Call(State* L, const char* fn, const std::vector<Arg>& args, int nresults) {
    Results r;
    int top = api.gettop(L);
    PushPath(L, fn);
    if (api.type(L, -1) != TFUNCTION) {
        api.settop(L, top);
        return r;
    }
    for (auto& a : args) {
        switch (a.k) {
            case Arg::Num: api.pushnumber(L, a.n); break;
            case Arg::Str: api.pushlstring(L, a.s.data(), a.s.size()); break;
            case Arg::Bool: api.pushboolean(L, a.b); break;
            default: api.settop(L, api.gettop(L) + 1); break;  // nil
        }
    }
    if (PCall(L, (int)args.size(), nresults) != 0) {
        Log("[lua] %s: %s", fn, PopError(L).c_str());
        api.settop(L, top);
        return r;
    }
    r.ok = true;
    for (int i = 0; i < nresults; ++i) {
        int idx = top + 1 + i;
        int t = api.type(L, idx);
        r.type.push_back(t);
        r.num.push_back(t == TNUMBER ? api.tonumber(L, idx) : t == TBOOLEAN ? (float)api.toboolean(L, idx) : 0.f);
        size_t n = 0;
        const char* s = t == TSTRING ? api.tolstring(L, idx, &n) : nullptr;
        r.str.push_back(s ? std::string(s, n) : std::string());
    }
    api.settop(L, top);
    return r;
}

float ArgNum(State* L, int i, float def) { return api.type(L, i) == TNUMBER ? api.tonumber(L, i) : def; }
std::string ArgStr(State* L, int i) {
    if (api.type(L, i) != TSTRING && api.type(L, i) != TNUMBER) return "";
    size_t n = 0;
    const char* s = api.tolstring(L, i, &n);
    return s ? std::string(s, n) : "";
}
bool ArgBool(State* L, int i) { return api.toboolean(L, i) != 0; }

}  // namespace lua
}  // namespace gm
