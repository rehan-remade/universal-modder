// dinput8.dll proxy for TheWolfAmongUs.exe (which imports DINPUT8.dll). Forwards every export to the system
// dinput8.dll and loads *.asi from the game folder right away, before the game's entry point runs, so a
// plugin can hook d3d9 exports before the game creates its device. Plugins must keep their DllMain light.
#include <windows.h>
#include <unknwn.h>

#include <string>

static HMODULE g_real = nullptr;

static FARPROC Real(const char* name) {
    if (!g_real) {
        char sys[MAX_PATH];
        GetSystemDirectoryA(sys, MAX_PATH);
        g_real = LoadLibraryA((std::string(sys) + "\\dinput8.dll").c_str());
    }
    return g_real ? GetProcAddress(g_real, name) : nullptr;
}

extern "C" {
HRESULT WINAPI Proxy_DirectInput8Create(HINSTANCE h, DWORD v, REFIID r, LPVOID* o, LPUNKNOWN u) {
    typedef HRESULT(WINAPI * Fn)(HINSTANCE, DWORD, REFIID, LPVOID*, LPUNKNOWN);
    Fn f = (Fn)Real("DirectInput8Create");
    return f ? f(h, v, r, o, u) : E_FAIL;
}
HRESULT WINAPI Proxy_DllCanUnloadNow() {
    typedef HRESULT(WINAPI * Fn)();
    Fn f = (Fn)Real("DllCanUnloadNow");
    return f ? f() : S_FALSE;
}
HRESULT WINAPI Proxy_DllGetClassObject(REFCLSID c, REFIID r, LPVOID* o) {
    typedef HRESULT(WINAPI * Fn)(REFCLSID, REFIID, LPVOID*);
    Fn f = (Fn)Real("DllGetClassObject");
    return f ? f(c, r, o) : E_FAIL;
}
HRESULT WINAPI Proxy_DllRegisterServer() {
    typedef HRESULT(WINAPI * Fn)();
    Fn f = (Fn)Real("DllRegisterServer");
    return f ? f() : E_FAIL;
}
HRESULT WINAPI Proxy_DllUnregisterServer() {
    typedef HRESULT(WINAPI * Fn)();
    Fn f = (Fn)Real("DllUnregisterServer");
    return f ? f() : E_FAIL;
}
LPCVOID WINAPI Proxy_GetdfDIJoystick() {
    typedef LPCVOID(WINAPI * Fn)();
    Fn f = (Fn)Real("GetdfDIJoystick");
    return f ? f() : nullptr;
}
}

static DWORD WINAPI LoadAsis(LPVOID) {
    char exe[MAX_PATH];
    GetModuleFileNameA(nullptr, exe, MAX_PATH);
    std::string dir(exe);
    dir.resize(dir.find_last_of('\\') + 1);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA((dir + "*.asi").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    do {
        LoadLibraryA((dir + fd.cFileName).c_str());
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        LoadAsis(nullptr);
    }
    return TRUE;
}
