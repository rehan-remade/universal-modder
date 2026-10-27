// LuaBridge: calls The Wolf Among Us' own (statically linked, float-number) Lua 5.1.4 through the RVAs in
// MODLOG.md, hooks lua_pcall to run the mod on the game thread, and exposes GMN_* natives to the script.
#pragma once
#include <functional>
#include <string>
#include <vector>

#include "Common.h"

namespace gm {
namespace lua {

struct State;  // opaque lua_State
typedef int(__cdecl* CFunction)(State*);

constexpr int GLOBALSINDEX = -10002;
constexpr int REGISTRYINDEX = -10000;
enum Type { TNONE = -1, TNIL = 0, TBOOLEAN = 1, TLIGHTUSERDATA = 2, TNUMBER = 3, TSTRING = 4, TTABLE = 5,
            TFUNCTION = 6, TUSERDATA = 7, TTHREAD = 8 };

// The game's API (filled by Init). Signatures are Lua 5.1 with lua_Number = float.
struct Api {
    int(__cdecl* gettop)(State*);
    void(__cdecl* settop)(State*, int);
    void(__cdecl* insert)(State*, int);
    void(__cdecl* pushvalue)(State*, int);
    int(__cdecl* type)(State*, int);
    const char*(__cdecl* typename_)(State*, int);
    int(__cdecl* isnumber)(State*, int);
    float(__cdecl* tonumber)(State*, int);
    int(__cdecl* toboolean)(State*, int);
    const char*(__cdecl* tolstring)(State*, int, size_t*);
    void(__cdecl* pushnumber)(State*, float);
    void(__cdecl* pushlstring)(State*, const char*, size_t);
    void(__cdecl* pushstring)(State*, const char*);
    void(__cdecl* pushcclosure)(State*, CFunction, int);
    void(__cdecl* pushboolean)(State*, int);
    void(__cdecl* getfield)(State*, int, const char*);
    void(__cdecl* createtable)(State*, int, int);
    void(__cdecl* setfield)(State*, int, const char*);
    void(__cdecl* call)(State*, int, int);
    int(__cdecl* pcall)(State*, int, int, int);
    int(__cdecl* loadbuffer)(State*, const char*, size_t, const char*);
};
extern Api api;

// Installs the hook; returns false (and logs why) if this isn't the expected TheWolfAmongUs.exe build.
bool Init();
bool Ready();

// Called once per game frame on the game thread, from inside the lua_pcall hook.
void SetTickCallback(std::function<void(State*)> cb);
// Ask for one tick per rendered frame (EndScene calls this).
void RequestTick();
// Keeps the GM table reachable when the engine ticks us from a coroutine with other globals.
// 0: GM is in this globals table, 1: put back from the registry, 2: not in this VM (load the script).
int AnchorGM(State* L);

// ---- helpers, game thread only
bool RunString(State* L, const std::string& code, const char* chunk, std::string* err = nullptr);
bool RunFile(State* L, const std::string& path, std::string* err = nullptr);
void Register(State* L, const char* name, CFunction fn);

// Calls a global (dotted names like "GM.Spawn" allowed) with simple arguments; results stay readable via
// Results until the next Call.
struct Arg {
    enum K { Num, Str, Bool, Nil } k;
    float n = 0;
    std::string s;
    bool b = false;
    Arg(float v) : k(Num), n(v) {}
    Arg(double v) : k(Num), n((float)v) {}
    Arg(int v) : k(Num), n((float)v) {}
    Arg(bool v) : k(Bool), b(v) {}
    Arg(const char* v) : k(v ? Str : Nil), s(v ? v : "") {}
    Arg(const std::string& v) : k(Str), s(v) {}
};
struct Results {
    std::vector<float> num;
    std::vector<std::string> str;
    std::vector<int> type;
    bool ok = false;
    float N(size_t i, float def = 0) const { return i < num.size() && type[i] == TNUMBER ? num[i] : def; }
    bool B(size_t i) const { return i < num.size() && (type[i] == TBOOLEAN ? num[i] != 0 : type[i] != TNIL); }
    const std::string& S(size_t i) const { static std::string e; return i < str.size() ? str[i] : e; }
};
Results Call(State* L, const char* fn, const std::vector<Arg>& args = {}, int nresults = 0);

// Argument readers for natives.
float ArgNum(State* L, int i, float def = 0);
std::string ArgStr(State* L, int i);
bool ArgBool(State* L, int i);

}  // namespace lua
}  // namespace gm
