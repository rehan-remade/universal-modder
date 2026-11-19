// StateAndCameraManager: the sandbox frame, F1/F3 mode switches with a full snapshot/restore of the scene,
// the first-person controller (WASD, Space, Shift, Ctrl, mouse), noclip (V), flashlight (F), camera-axis
// calibration and the developer console. Engine work goes through lua/gmod_sandbox.lua (GM.*).
#include <algorithm>
#include <fstream>
#include <sstream>

#include "Sandbox.h"
#include <tlhelp32.h>

namespace gm {

// ===================================================================== world plumbing
World& GetWorld() {
    static World w;
    return w;
}
std::recursive_mutex& WorldLock() {
    static std::recursive_mutex m;
    return m;
}
Entity* World::Find(const std::string& name) {
    for (auto& e : ents)
        if (e->name == name) return e.get();
    return nullptr;
}
Entity* World::Add(const std::string& name) {
    ents.push_back(std::make_unique<Entity>());
    ents.back()->name = name;
    return ents.back().get();
}
void World::Remove(Entity* e) {
    if (facePoserTarget == e) facePoserTarget = nullptr;
    ents.erase(std::remove_if(ents.begin(), ents.end(), [e](const std::unique_ptr<Entity>& p) { return p.get() == e; }),
               ents.end());
}

static std::mutex g_cmdMu;
static std::deque<std::function<void(lua::State*)>> g_cmds;
void PostCommand(std::function<void(lua::State*)> fn) {
    std::lock_guard<std::mutex> lk(g_cmdMu);
    g_cmds.push_back(std::move(fn));
}
void RunCommands(lua::State* L) {
    std::deque<std::function<void(lua::State*)>> q;
    {
        std::lock_guard<std::mutex> lk(g_cmdMu);
        q.swap(g_cmds);
    }
    for (auto& f : q) f(L);
}

namespace state {
namespace {

// ===================================================================== config (gmod\gmod_sandbox.ini)
struct Config {
    float walkSpeed = 3.0f, runSpeed = 6.0f, noclipSpeed = 6.0f;  // m/s
    float jumpSpeed = 4.2f, gravity = 15.0f;                         // GMod-ish, snappier than real
    float eyeHeight = 1.62f, crouchEye = 0.95f;
    float mouseSens = 0.12f;  // degrees per mickey
    float fov = 70.0f;
    std::string playerAgent = "Bigby";
} g_cfg;

void LoadIni(World& w) {
    std::ifstream f(GetPaths().modDir + "\\gmod_sandbox.ini");
    std::string line;
    while (std::getline(f, line)) {
        auto eq = line.find('=');
        if (eq == std::string::npos || line[0] == ';' || line[0] == '#') continue;
        std::string k = line.substr(0, eq), v = line.substr(eq + 1);
        while (!k.empty() && k.back() == ' ') k.pop_back();
        while (!v.empty() && v[0] == ' ') v.erase(0, 1);
        float n = (float)atof(v.c_str());
        if (k == "unitsPerMeter") w.axes.unitsPerMeter = n;
        else if (k == "walkSpeed") g_cfg.walkSpeed = n;
        else if (k == "runSpeed") g_cfg.runSpeed = n;
        else if (k == "noclipSpeed") g_cfg.noclipSpeed = n;
        else if (k == "jumpSpeed") g_cfg.jumpSpeed = n;
        else if (k == "gravity") g_cfg.gravity = n;
        else if (k == "eyeHeight") g_cfg.eyeHeight = n;
        else if (k == "mouseSensitivity") g_cfg.mouseSens = n;
        else if (k == "fov") g_cfg.fov = n;
        else if (k == "playerAgent") g_cfg.playerAgent = v;
    }
}

}  // namespace
}  // namespace state

// ===================================================================== memory probes (reverse engineering)
// For mapping engine objects from the console (skel / peek / poke): SEH-guarded reads and writes, and a scan
// of private read-write memory for objects by their vtable.
bool SafeRead(uintptr_t a, void* out, size_t n) {
    __try { memcpy(out, (const void*)a, n); return true; } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
bool SafeWrite(uintptr_t a, const void* in, size_t n) {
    __try { memcpy((void*)a, in, n); return true; } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
size_t ScanRegion(const uint32_t* p, size_t n, uint32_t v, uintptr_t* hits, size_t maxHits) {
    size_t k = 0;
    __try {
        for (size_t i = 0; i < n && k < maxHits; ++i)
            if (p[i] == v) hits[k++] = (uintptr_t)(p + i);
    } __except (EXCEPTION_EXECUTE_HANDLER) {}
    return k;
}
uintptr_t ExeBase() { return (uintptr_t)GetModuleHandleA(nullptr); }
std::vector<uintptr_t> FindObjects(uint32_t vtableRva, size_t max) {
    std::vector<uintptr_t> out;
    uint32_t vt = (uint32_t)(ExeBase() + vtableRva);
    MEMORY_BASIC_INFORMATION mbi;
    uintptr_t hits[256];
    for (uintptr_t a = 0x10000; a < 0x7FFF0000 && out.size() < max; a += mbi.RegionSize) {
        if (!VirtualQuery((void*)a, &mbi, sizeof mbi)) break;
        if (mbi.State != MEM_COMMIT || mbi.Type != MEM_PRIVATE || !(mbi.Protect & PAGE_READWRITE) ||
            (mbi.Protect & PAGE_GUARD))
            continue;
        size_t k = ScanRegion((const uint32_t*)mbi.BaseAddress, mbi.RegionSize / 4, vt, hits,
                              std::min<size_t>(256, max - out.size()));
        out.insert(out.end(), hits, hits + k);
    }
    return out;
}
std::string HexDwords(uintptr_t a, int n, bool floats) {
    std::string s;
    char b[48];
    for (int i = 0; i < n; ++i) {
        uint32_t v = 0;
        if (!SafeRead(a + 4 * i, &v, 4)) { s += " ??"; continue; }
        if (floats) { float f; memcpy(&f, &v, 4); snprintf(b, sizeof b, " %08x(%.3g)", v, f); }
        else snprintf(b, sizeof b, " %08x", v);
        s += b;
    }
    return s;
}

// Hardware write watch (hwbp): debug register 0 on every thread, and a vectored handler that tallies the
// instruction addresses that wrote there. Answers "which engine function writes this field?".
struct HwHit { uint32_t eip; uint32_t n; uint32_t ecx, esi, edi; uint32_t ret[3]; };
HwHit g_hwHits[16];
volatile LONG g_hwCount = 0;
PVOID g_hwVeh = nullptr;
LONG CALLBACK HwVeh(EXCEPTION_POINTERS* x) {
    if (x->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP || !(x->ContextRecord->Dr6 & 1))
        return EXCEPTION_CONTINUE_SEARCH;
    uint32_t eip = x->ContextRecord->Eip;
    for (auto& h : g_hwHits) {
        if (h.eip == eip) { ++h.n; break; }
        if (!h.eip) {
            h = {eip, 1, x->ContextRecord->Ecx, x->ContextRecord->Esi, x->ContextRecord->Edi, {0, 0, 0}};
            uint32_t fp = x->ContextRecord->Ebp;  // callers, by the frame-pointer chain
            for (int i = 0; i < 3 && SafeRead(fp + 4, &h.ret[i], 4) && SafeRead(fp, &fp, 4); ++i) {}
            break;
        }
    }
    InterlockedIncrement(&g_hwCount);
    x->ContextRecord->Dr6 = 0;
    return EXCEPTION_CONTINUE_EXECUTION;
}
// addr 0 clears. rw: 1 = write, 3 = read/write. Returns the number of threads armed.
struct HwArgs { uintptr_t addr; int rw; DWORD skip; int armed; };
DWORD WINAPI ArmThreads(LPVOID p);
int SetHwWatch(uintptr_t addr, int rw) {
    if (!g_hwVeh) g_hwVeh = AddVectoredExceptionHandler(1, HwVeh);
    if (addr) { memset(g_hwHits, 0, sizeof g_hwHits); g_hwCount = 0; }
    // A thread can't set its own debug registers, so a helper arms every thread (this one included) while
    // this one waits.
    HwArgs a = {addr, rw, 0, 0};
    HANDLE h = CreateThread(nullptr, 0, ArmThreads, &a, 0, &a.skip);
    WaitForSingleObject(h, INFINITE);
    CloseHandle(h);
    return a.armed;
}
DWORD WINAPI ArmThreads(LPVOID p) {
    HwArgs& a = *(HwArgs*)p;
    uintptr_t addr = a.addr;
    int rw = a.rw;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 te = {sizeof te};
    for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
        if (te.th32OwnerProcessID != GetCurrentProcessId() || te.th32ThreadID == GetCurrentThreadId()) continue;
        HANDLE t = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT | THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
        if (!t) continue;
        SuspendThread(t);
        CONTEXT c = {};
        c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        if (GetThreadContext(t, &c)) {
            c.Dr0 = addr;
            c.Dr7 = addr ? (1u | ((DWORD)rw << 16) | (3u << 18)) : 0;  // L0, RW0, LEN0 = 4 bytes
            c.Dr6 = 0;
            if (SetThreadContext(t, &c)) ++a.armed;
        }
        ResumeThread(t);
        CloseHandle(t);
    }
    CloseHandle(snap);
    return 0;
}

namespace state {
namespace {

// ===================================================================== natives for the Lua side
int __cdecl N_Log(lua::State* L) {
    Log("%s", lua::ArgStr(L, 1).c_str());
    return 0;
}
int __cdecl N_ReportScene(lua::State* L) {
    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    GetWorld().activeScenes.push_back(lua::ArgStr(L, 1));
    return 0;
}
// GMN_ReportAgent(name, x,y,z, qx,qy,qz,qw, visible, scene, hasMesh)
int __cdecl N_ReportAgent(lua::State* L) {
    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    World& w = GetWorld();
    std::string name = lua::ArgStr(L, 1);
    Entity* e = w.Find(name);
    if (!e) e = w.Add(name);
    e->pos = {lua::ArgNum(L, 2), lua::ArgNum(L, 3), lua::ArgNum(L, 4)};
    e->rot = {lua::ArgNum(L, 5), lua::ArgNum(L, 6), lua::ArgNum(L, 7), lua::ArgNum(L, 8, 1)};
    e->visible = lua::ArgBool(L, 9);
    e->hasMesh = lua::ArgBool(L, 11);
    e->origPos = e->pos;
    e->origRot = e->rot;
    e->origVisible = e->visible;
    e->groundY = e->pos.y;
    // Story characters: match the agent name to a catalog skeleton ("Snow" -> sk55_snow).
    std::string ln = ToLower(name);
    for (auto& c : AssetBridge::Get().Telltale().Characters()) {
        std::string who = ToLower(c.skeleton.substr(c.skeleton.find('_') + 1));
        if (who == ln) {
            e->info = &c;
            e->skeleton = c.skeleton;
            e->prop = c.prop;
            e->character = true;
            break;
        }
    }
    e->isPlayerBody = ln == ToLower(g_cfg.playerAgent);
    return 0;
}

// ===================================================================== input
POINT g_center{};
bool g_mouseCaptured = false;
LARGE_INTEGER g_qpf{}, g_last{};

void PollInput(World& w) {
    InputFrame& in = w.input;
    bool focus = GameWindowFocused();
    for (int k = 1; k < 256; ++k) {
        bool d = focus && (GetAsyncKeyState(k) & 0x8000) != 0;
        in.pressed[k] = d && !in.down[k];
        in.released[k] = !d && in.down[k];
        in.down[k] = d;
    }
    in.wheel = hud::ConsumeWheel();
    in.mouseDx = in.mouseDy = 0;
    bool want = w.mode == Mode::Sandbox && focus && !hud::AnyMenuOpen();
    if (want) {
        RECT rc;
        GetClientRect(GameWindow(), &rc);
        POINT c{(rc.right - rc.left) / 2, (rc.bottom - rc.top) / 2};
        ClientToScreen(GameWindow(), &c);
        POINT p;
        GetCursorPos(&p);
        if (g_mouseCaptured) {
            in.mouseDx = (float)(p.x - c.x);
            in.mouseDy = (float)(p.y - c.y);
        }
        SetCursorPos(c.x, c.y);
        g_center = c;
        if (!g_mouseCaptured) while (ShowCursor(FALSE) >= 0) {}
        g_mouseCaptured = true;
    } else if (g_mouseCaptured) {
        while (ShowCursor(TRUE) < 0) {}
        g_mouseCaptured = false;
    }
}

// ===================================================================== camera basis
// Orientation from yaw/pitch/roll around the calibrated up axis, starting from a reference horizontal
// direction (the story camera's forward at F1).
Vec3 g_refForward{0, 0, 1};

void Basis(const World& w, Vec3& f, Vec3& r, Vec3& u) {
    const Player& p = w.player;
    Vec3 U = w.axes.up;
    // Positive yaw turns toward screen-right and positive pitch looks up, whatever the engine's handedness.
    Vec3 h0 = g_refForward, r0 = Normalize(Cross(U, h0)) * w.axes.rightSign;
    float y = Deg2Rad(p.yaw), pt = Deg2Rad(p.pitch);
    Vec3 h = h0 * std::cos(y) + r0 * std::sin(y);
    f = Normalize(h * std::cos(pt) + U * std::sin(pt));
    Vec3 up = Normalize(U - f * Dot(U, f));
    Vec3 rn = Normalize(Cross(up, f)) * w.axes.rightSign;
    Quat roll = Quat::AxisAngle(f, Deg2Rad(p.roll));
    r = roll.Rotate(rn);
    u = roll.Rotate(up);
}

// Rotation that takes the camera's local forward/up onto f/u.
Quat LookRotation(const Vec3& localF, const Vec3& localU, const Vec3& f, const Vec3& u) {
    Quat q1 = FromTo(Normalize(localF), f);
    Vec3 u1 = q1.Rotate(localU);
    Vec3 a = Normalize(u1 - f * Dot(u1, f)), b = Normalize(u - f * Dot(u, f));
    float ang = std::atan2(Dot(Cross(a, b), f), Dot(a, b));
    return Normalize(Quat::AxisAngle(f, ang) * q1);
}

// Calibration: after CameraBegin we set an orientation and read back AgentGetForwardVec; try the six
// local axes until the engine agrees, then compare screen positions to settle handedness.
int g_calibStep = -1;
const Vec3 kAxisCandidates[] = {{0, 0, 1}, {0, 0, -1}, {1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}};

void ApplyCamera(lua::State* L, World& w) {
    Player& p = w.player;
    Vec3 f, r, u;
    Basis(w, f, r, u);
    float upm = w.axes.unitsPerMeter;
    float eye = (p.crouch ? g_cfg.crouchEye : g_cfg.eyeHeight) * upm;
    p.forward = f;
    p.right = r;
    p.up = u;
    p.eye = p.pos + w.axes.up * eye;
    // view bob, a little like HL2
    float speed = Length(Vec3(p.vel.x, 0, p.vel.z));
    if (p.onGround && !p.noclip && speed > 0.5f * upm) p.bob += w.dt * speed / upm * 2.2f;
    p.eye += w.axes.up * (std::sin(p.bob * 2) * 0.012f * upm);
    Vec3 camPos = p.eye;
    if (p.thirdPerson) camPos = p.eye - f * (2.2f * upm) + r * (0.4f * upm);
    Vec3 localUp = std::fabs(w.axes.camLocalForward.y) > 0.5f ? Vec3(0, 0, 1) : Vec3(0, 1, 0);
    Vec3 fPunched = Normalize(f + u * Deg2Rad(-p.punchPitch));
    Quat q = LookRotation(w.axes.camLocalForward, localUp, fPunched, u);
    lua::Call(L, "GM.CameraSet", {camPos.x, camPos.y, camPos.z, q.x, q.y, q.z, q.w, p.fov});

    if (g_calibStep >= 0 && g_calibStep < 6) {
        auto r2 = lua::Call(L, "GM.CameraForward", {}, 3);
        if (r2.ok && r2.type[0] == lua::TNUMBER) {
            Vec3 got = Normalize(Vec3(r2.N(0), r2.N(1), r2.N(2)));
            float d = Dot(got, fPunched);
            if (d > 0.9f) {
                // Forward agrees. Handedness: a point to our right must project right of the centre.
                auto c = lua::Call(L, "GM.ScreenPos", {camPos.x + f.x * 5, camPos.y + f.y * 5, camPos.z + f.z * 5}, 2);
                Vec3 rp = camPos + f * 5 + r * 1;
                auto s = lua::Call(L, "GM.ScreenPos", {rp.x, rp.y, rp.z}, 2);
                // The projection uses the engine's camera of the previous frame, so it can't settle handedness
                // (run 16 flipped it the wrong way); kept as a readout only.
                if (c.ok && s.ok && c.type[0] == lua::TNUMBER)
                    Log("[camera] screen x: centre %.3f, 1 m to our right %.3f", c.N(0), s.N(0));
                w.axes.calibrated = true;
                Log("[camera] calibrated: local forward (%g %g %g), rightSign %g (dot %.3f)", w.axes.camLocalForward.x,
                    w.axes.camLocalForward.y, w.axes.camLocalForward.z, w.axes.rightSign, d);
                g_calibStep = -1;
            } else {
                Log("[camera] local forward (%g %g %g) gives dot %.3f; trying the next axis", w.axes.camLocalForward.x,
                    w.axes.camLocalForward.y, w.axes.camLocalForward.z, d);
                if (++g_calibStep < 6) w.axes.camLocalForward = kAxisCandidates[g_calibStep];
                else Log("[camera] no local axis matched; set it by hand (MODLOG open item 3)");
            }
        } else {
            Log("[camera] AgentGetForwardVec gave nothing; calibration skipped");
            g_calibStep = -1;
        }
    }
}

// ===================================================================== player movement
void MovePlayer(lua::State* L, World& w) {
    Player& p = w.player;
    InputFrame& in = w.input;
    float dt = w.dt, upm = w.axes.unitsPerMeter;
    if (!combat::CapturesMouse()) {
        p.yaw += in.mouseDx * g_cfg.mouseSens;
        p.pitch = Clamp(p.pitch - in.mouseDy * g_cfg.mouseSens, -89.0f, 89.0f);
    }
    p.punchPitch *= std::exp(-dt * 10.0f);
    p.crouch = in.down[VK_CONTROL] && !p.noclip;
    Vec3 f, r, u;
    Basis(w, f, r, u);
    Vec3 U = w.axes.up;
    Vec3 wish;
    float fw = (in.down['W'] ? 1.f : 0.f) - (in.down['S'] ? 1.f : 0.f);
    float sd = (in.down['D'] ? 1.f : 0.f) - (in.down['A'] ? 1.f : 0.f);
    if (p.noclip) {
        wish = f * fw + r * sd + U * ((in.down[VK_SPACE] ? 1.f : 0.f) - (in.down[VK_CONTROL] ? 1.f : 0.f));
        float sp = g_cfg.noclipSpeed * (in.down[VK_SHIFT] ? 3.f : 1.f) * upm;
        p.vel = Normalize(wish) * sp;
        p.pos += p.vel * dt;
        return;
    }
    Vec3 fh = Normalize(f - U * Dot(f, U)), rh = Normalize(r - U * Dot(r, U));
    wish = Normalize(fh * fw + rh * sd);
    float sp = (in.down[VK_SHIFT] ? g_cfg.runSpeed : g_cfg.walkSpeed) * (p.crouch ? 0.4f : 1.f) * upm;
    Vec3 target = wish * sp;
    float accel = p.onGround ? 12.f : 2.f;
    float vy = Dot(p.vel, U);
    Vec3 hv = p.vel - U * vy;
    hv += (target - hv) * std::min(1.f, accel * dt);
    if (p.onGround && in.pressed[VK_SPACE]) { vy = g_cfg.jumpSpeed * upm; p.onGround = false; }
    vy -= g_cfg.gravity * upm * dt;
    // Horizontal move per axis so walls (off the walk boxes) slide instead of stopping dead.
    float groundY = p.floorY;
    Vec3 step = hv * dt;
    for (int axis = 0; axis < 2; ++axis) {
        Vec3 part = axis == 0 ? fh * Dot(step, fh) : rh * Dot(step, rh);
        Vec3 cand = p.pos + part;
        auto ok = lua::Call(L, "GM.OnWalkBoxes", {cand.x, cand.y, cand.z}, 1);
        if (!ok.ok || ok.B(0)) p.pos = cand;
        else hv -= axis == 0 ? fh * Dot(hv, fh) : rh * Dot(hv, rh);
    }
    p.pos += U * (vy * dt);
    float h = Dot(p.pos, U);
    if (h <= groundY) {
        p.pos += U * (groundY - h);
        vy = 0;
        p.onGround = true;
    }
    p.vel = hv + U * vy;
}

void UpdateFlashlight(lua::State* L, World& w) {
    static bool wasOn = false;
    Player& p = w.player;
    if (p.flashlight) {
        Vec3 localUp = std::fabs(w.axes.camLocalForward.y) > 0.5f ? Vec3(0, 0, 1) : Vec3(0, 1, 0);
        Quat q = LookRotation(w.axes.camLocalForward, localUp, p.forward, p.up);
        Vec3 at = p.eye + p.right * (0.15f * w.axes.unitsPerMeter);
        auto r = lua::Call(L, "GM.Light", {true, w.sceneForSpawns, at.x, at.y, at.z, q.x, q.y, q.z, q.w}, 1);
        w.engineLightOk = r.ok && r.B(0);
    } else if (wasOn) {
        lua::Call(L, "GM.Light", {false});
    }
    wasOn = p.flashlight;
}

bool g_scriptLoaded = false;

void LoadScript(lua::State* L) {
    lua::Register(L, "GMN_Log", N_Log);
    lua::Register(L, "GMN_ReportScene", N_ReportScene);
    lua::Register(L, "GMN_ReportAgent", N_ReportAgent);
    std::string err;
    g_scriptLoaded = lua::RunFile(L, GetPaths().modDir + "\\lua\\gmod_sandbox.lua", &err);
    GetWorld().luaReady = g_scriptLoaded;
    hud::Notify(g_scriptLoaded ? "Garry's Mod sandbox ready: F1" : "gmod_sandbox.lua failed: " + err);
}

}  // namespace

// ===================================================================== mode switches
void EnterSandbox(lua::State* L) {
    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    World& w = GetWorld();
    if (w.mode == Mode::Sandbox || !w.luaReady) return;
    w.ents.clear();
    w.activeScenes.clear();
    // 1) Remember every agent of the current scene exactly as it is.
    auto snap = lua::Call(L, "GM.Snapshot", {}, 1);
    w.sceneForSpawns = w.activeScenes.empty() ? "" : w.activeScenes.back();
    Log("[state] F1: %d agents in %zu scenes (spawns go to %s)", (int)snap.N(0), w.activeScenes.size(),
        w.sceneForSpawns.c_str());
    // 2) Freeze the story: chores, animations and the dialog line keep their time.
    lua::Call(L, "GM.Freeze", {}, 1);
    // 3) The player stands where Bigby stands; Bigby's model goes away.
    Player& p = w.player;
    p = Player{};
    p.fov = g_cfg.fov;
    for (int i = 0; i < (int)Weapon::Count; ++i) p.ammo[i] = WeaponState{};
    //    Without Bigby (a scene from the map menu), under the story camera; either way on the walk boxes.
    Entity* body = w.Find(g_cfg.playerAgent);
    if (body) {
        lua::Call(L, "GM.Show", {body->name, false});
        body->visible = false;
    }
    std::vector<lua::Arg> where{w.sceneForSpawns};
    if (body) where.insert(where.end(), {body->pos.x, body->pos.y, body->pos.z});
    auto at = lua::Call(L, "GM.StartPoint", where, 4);
    if (at.ok && !at.type.empty() && at.type[0] == lua::TNUMBER) {
        p.pos = Vec3(at.N(0), at.N(1), at.N(2));
        Log("[state] start (%s): %.2f %.2f %.2f", at.S(3).c_str(), p.pos.x, p.pos.y, p.pos.z);
        if (at.S(3) == "camera") {
            // No walk boxes: a staged shot (adv_barTripTrapExterior104, adv_centralParkBridge104). Look
            // through the story camera and fly, since there is no floor to stand on.
            p.pos -= w.axes.up * (g_cfg.eyeHeight * w.axes.unitsPerMeter);
            p.noclip = true;
            hud::Notify("No walk boxes in this scene: flying from the story camera (noclip)");
        }
    } else {
        Log("[state] no agent named %s, no camera and no walk boxes; starting at the scene origin",
            g_cfg.playerAgent.c_str());
        hud::Notify("This scene has no level to walk on (a cut-scene or a stub)");
    }
    p.floorY = Dot(p.pos, w.axes.up);
    // The interaction markers (ui_obj_<prop>_dot_point/_pulse circles) are agents in the story scene, not in
    // the ui_* scenes GM.Freeze hides; F3 shows them again with every other changed visibility.
    int markers = 0;
    for (auto& e : w.ents) {
        if (e->visible && e->name.rfind("ui_", 0) == 0) {
            lua::Call(L, "GM.Show", {e->name, false});
            e->visible = false;
            ++markers;
        }
    }
    Log("[state] hid %d interaction markers", markers);
    // The level itself is <scene>_meshesA/B/... agents. A chase scene opened from the map menu has them all
    // hidden until its script lays the street out (adv_fabletownStreetTile105), so show them when none is.
    bool levelShown = false;
    for (auto& e : w.ents)
        if (e->visible && e->name.find("_meshes") != std::string::npos) levelShown = true;
    if (!levelShown) {
        int shown = 0;
        for (auto& e : w.ents) {
            if (e->name.find("_meshes") == std::string::npos) continue;
            lua::Call(L, "GM.Show", {e->name, true});
            e->visible = true;
            ++shown;
        }
        if (shown) Log("[state] no level meshes were visible; showed %d", shown);
    }
    // 4) Our camera replaces Telltale's, looking where the story camera looked.
    auto cam = lua::Call(L, "GM.CameraBegin", {w.sceneForSpawns}, 1);
    auto fwd = lua::Call(L, "GM.PrevCameraForward", {}, 3);
    if (fwd.ok && fwd.type[0] == lua::TNUMBER) {
        Vec3 f(fwd.N(0), fwd.N(1), fwd.N(2));
        Vec3 h = f - w.axes.up * Dot(f, w.axes.up);
        if (Length(h) > 0.1f) g_refForward = Normalize(h);
        p.pitch = std::asin(Clamp(Dot(Normalize(f), w.axes.up), -1, 1)) * 180.f / kPi;
    }
    if (!w.axes.calibrated) {
        g_calibStep = 0;
        w.axes.camLocalForward = kAxisCandidates[0];
    }
    w.mode = Mode::Sandbox;
    combat::OnEnterSandbox(L);
    audio::Play("sound/common/wpn_hudoff.wav", 0.6f);
    hud::Notify(cam.B(0) ? "Sandbox: F3 returns to the story" : "Sandbox (camera agent failed, see log)");
}

void ExitSandbox(lua::State* L) {
    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    World& w = GetWorld();
    if (w.mode != Mode::Sandbox) return;
    combat::OnExitSandbox(L);  // removes spawns, ragdolls, clips, the physgun loop
    if (w.player.flashlight) {
        w.player.flashlight = false;
        lua::Call(L, "GM.Light", {false});
    }
    // Story agents back to where F1 found them, visible as they were.
    for (auto& e : w.ents) {
        if (e->spawned) continue;
        e->pos = e->origPos;
        e->rot = e->origRot;
        lua::Call(L, "GM.Set", {e->name, e->pos.x, e->pos.y, e->pos.z, e->rot.x, e->rot.y, e->rot.z, e->rot.w});
        if (e->visible != e->origVisible || e->isPlayerBody) lua::Call(L, "GM.Show", {e->name, e->origVisible});
    }
    lua::Call(L, "GM.CameraEnd");
    lua::Call(L, "GM.Unfreeze");
    w.ents.clear();
    w.mode = Mode::Story;
    w.spawnMenuOpen = w.contextMenuOpen = w.mapMenuOpen = false;
    hud::Notify("Back to the story");
    Log("[state] F3: story resumed");
}

// Pushes every dirty entity transform to the engine.
void SyncTransforms(lua::State* L) {
    World& w = GetWorld();
    for (auto& e : w.ents) {
        if (!e->dirty) continue;
        e->dirty = false;
        lua::Call(L, "GM.Set", {e->name, e->pos.x, e->pos.y, e->pos.z, e->rot.x, e->rot.y, e->rot.z, e->rot.w});
    }
}

bool ProjectToScreen(const Vec3& world, float& sx, float& sy) {
    World& w = GetWorld();
    const Player& p = w.player;
    Vec3 d = world - p.eye;
    float z = Dot(d, p.forward);
    if (z < 0.01f) return false;
    float x = Dot(d, p.right), y = Dot(d, p.up);
    RECT rc;
    GetClientRect(GameWindow(), &rc);
    float W = (float)(rc.right - rc.left), H = (float)(rc.bottom - rc.top);
    float ys = 1.0f / std::tan(Deg2Rad(p.fov) * 0.5f);
    sx = W * 0.5f + (x / z) * ys * (H * 0.5f);
    sy = H * 0.5f - (y / z) * ys * (H * 0.5f);
    return true;
}

// ===================================================================== the frame
void Tick(lua::State* L) {
    static bool first = true;
    if (first) {
        first = false;
        QueryPerformanceFrequency(&g_qpf);
        QueryPerformanceCounter(&g_last);
    }
    static int warmup = 0;
    if (++warmup == 40) hud::LateHook();  // ~2 s in: the game and the Steam overlay have their device
    if (g_scriptLoaded) {
        // Chapter loads tick us from coroutines whose globals table lacks GM (run 7): put it back, and
        // reload the script if this VM never saw it.
        int a = lua::AnchorGM(L);
        static bool restoredOnce = false;
        if (a == 1 && !restoredOnce) Log("[state] GM restored into another globals table (logged once)");
        if (a == 1) restoredOnce = true;
        if (a == 2) Log("[state] new Lua VM: reloading gmod_sandbox.lua");
        if (a == 2) g_scriptLoaded = false;
    }
    if (!g_scriptLoaded && AssetBridge::Get().Ready()) LoadScript(L);
    if (!g_scriptLoaded) return;

    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    World& w = GetWorld();
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);
    w.dt = std::min(0.1f, (float)(now.QuadPart - g_last.QuadPart) / (float)g_qpf.QuadPart);
    g_last = now;
    w.time += w.dt;

    PollInput(w);
    InputFrame& in = w.input;
    bool keys = !hud::WantsKeyboard();
    RunCommands(L);

    // <game>\gmod\cmd.txt: console commands from outside the game (one per line; output goes to the log).
    // Lets a test script drive the console without focusing the window.
    static float lastCmdCheck = 0;
    if (w.time - lastCmdCheck > 0.5f) {
        lastCmdCheck = w.time;
        std::string path = GetPaths().modDir + "\\cmd.txt";
        if (FILE* f = fopen(path.c_str(), "r")) {
            std::vector<std::string> lines;
            char buf[4096];
            while (fgets(buf, sizeof buf, f)) {
                std::string s(buf);
                while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
                if (!s.empty()) lines.push_back(s);
            }
            fclose(f);
            DeleteFileA(path.c_str());
            for (auto& line : lines) {
                Log("[cmd] > %s", line.c_str());
                for (auto& o : ConsoleCommand(L, line)) Log("[cmd] %s", o.c_str());
            }
        }
    }

    if (keys && in.pressed[VK_F1] && w.mode == Mode::Story) EnterSandbox(L);
    else if (keys && in.pressed[VK_F3] && w.mode == Mode::Sandbox) ExitSandbox(L);
    if (in.pressed[VK_INSERT]) {
        w.consoleOpen = !w.consoleOpen;
        Log("[state] console %s", w.consoleOpen ? "open" : "closed");
    }
    static int ticks = 0;
    static float lastReport = -100;
    ++ticks;
    if (w.time - lastReport > 10) {
        lastReport = w.time;
        Log("[state] heartbeat: %d ticks, focused %d; %s", ticks, (int)GameWindowFocused(), hud::FrameStats().c_str());
    }
    if (w.mode != Mode::Sandbox) return;

    // Menus: hold Q (spawn) / hold C (context, Face Poser) like GMod; M toggles the map list.
    if (keys) {
        w.spawnMenuOpen = in.down['Q'];
        w.contextMenuOpen = in.down['C'];
        if (in.pressed['M']) w.mapMenuOpen = !w.mapMenuOpen;
    }
    Player& p = w.player;
    if (keys && in.pressed['V']) {
        p.noclip = !p.noclip;
        hud::Notify(p.noclip ? "noclip ON" : "noclip OFF");
    }
    if (keys && in.pressed['F']) {
        p.flashlight = !p.flashlight;
        audio::Play("sound/items/flashlight1.wav");
    }
    if (!hud::AnyMenuOpen()) MovePlayer(L, w);
    combat::Tick(L, w.dt);
    ApplyCamera(L, w);
    UpdateFlashlight(L, w);
    SyncTransforms(L);
}

void Init() {
    World& w = GetWorld();
    LoadIni(w);
    lua::SetTickCallback([](lua::State* L) { Tick(L); });
}

// ===================================================================== console
std::vector<std::string> ConsoleCommand(lua::State* L, const std::string& line) {
    std::vector<std::string> out;
    std::istringstream is(line);
    std::string cmd;
    is >> cmd;
    std::string rest;
    std::getline(is, rest);
    if (!rest.empty() && rest[0] == ' ') rest.erase(0, 1);
    World& w = GetWorld();
    if (cmd == "help") {
        out = {"lua <code>        run Lua in the game (GM.*, engine functions)",
               "reload            reload gmod_sandbox.lua",
               "probe [agent]     dump an agent's transform, controllers and property keys",
               "agents            list tracked agents",
               "map <scene>       open a scene (as the M menu does)",
               "spawn <name>      spawn a character as an NPC (part of its name or prop)",
               "lookat [agent]    aim at an agent (default: the last spawn)",
               "ai [agent] stay|wander|follow   what a spawned NPC does (default: the last spawn)",
               "pose emotion <name> | mouth <shape> [w] | fingers <curl...>   face and finger poser (the last spawn)",
               "noclip | god | thirdperson | giveammo",
               "gm_measure        distance between the first two characters (units check)",
               "gm_calibrate      redo the camera axis calibration"};
    } else if (cmd == "lua") {
        std::string err;
        out.push_back(lua::RunString(L, rest, "=console", &err) ? "ok" : err);
    } else if (cmd == "reload") {
        LoadScript(L);
        out.push_back(g_scriptLoaded ? "reloaded" : "failed (see log)");
    } else if (cmd == "probe") {
        lua::Call(L, "GM.Probe", {rest.empty() ? g_cfg.playerAgent : rest});
        out.push_back("see the log below");
    } else if (cmd == "agents") {
        for (auto& e : w.ents) {
            char b[256];
            snprintf(b, sizeof b, "%-28s %s pos (%.2f %.2f %.2f) hp %.0f %s", e->name.c_str(),
                     e->character ? e->skeleton.c_str() : "-", e->pos.x, e->pos.y, e->pos.z, e->hp,
                     e->spawned ? "[spawned]" : "");
            out.push_back(b);
        }
    } else if (cmd == "map") {
        // map <scene> [Fables10N]: open a scene, switching the resources to its episode; map alone lists them
        std::istringstream ms(rest);
        std::string scene, episode;
        ms >> scene >> episode;
        if (scene.empty()) {
            for (auto& sc : AssetBridge::Get().Telltale().Scenes()) out.push_back(sc.episode + " " + sc.scene);
        } else {
            if (w.mode == Mode::Sandbox) ExitSandbox(L);  // as the map menu does
            if (episode.empty())  // the first episode that has it
                for (auto& sc : AssetBridge::Get().Telltale().Scenes())
                    if (episode.empty() && ToLower(sc.scene) == ToLower(scene)) episode = sc.episode;
            out.push_back(lua::Call(L, "GM.OpenScene", {scene, episode}, 1).B(0) ? "opening " + scene + " " + episode
                                                                                 : "SceneOpen failed");
        }
    } else if (cmd == "spawn") {
        // spawn <part of a name or prop>: the first matching character, as an NPC (for tests and binds)
        std::string q = ToLower(rest);
        const CharacterInfo* found = nullptr;
        for (auto& c : AssetBridge::Get().Telltale().Characters())
            if (!q.empty() && !found && (ToLower(c.display).find(q) != std::string::npos || ToLower(c.prop).find(q) != std::string::npos))
                found = &c;
        if (w.mode != Mode::Sandbox) out.push_back("press F1 first");
        else if (!found) out.push_back("no character matches '" + rest + "'");
        else {
            Entity* e = combat::Spawn(L, *found, true);
            out.push_back(e ? "spawned " + e->name + " (" + found->prop + ")" : "spawn failed (see log)");
        }
    } else if (cmd == "lookat") {
        // Aim at an agent's chest (default: the last thing spawned). For tests: mouse input is too coarse.
        Entity* e = nullptr;
        for (auto& x : w.ents)
            if (rest.empty() ? x->spawned : x->name == rest) e = x.get();
        if (!e) {
            out.push_back("no such agent");
        } else {
            Vec3 U = w.axes.up;
            Vec3 at = combat::AimPoint(*e);
            Vec3 d = Normalize(at - w.player.eye);
            Vec3 h0 = g_refForward, r0 = Normalize(Cross(U, h0)) * w.axes.rightSign;
            Vec3 hd = Normalize(d - U * Dot(d, U));
            w.player.pitch = std::asin(Clamp(Dot(d, U), -1, 1)) * 180.f / kPi;
            w.player.yaw = std::atan2(Dot(hd, r0), Dot(hd, h0)) * 180.f / kPi;
            char b[96];
            snprintf(b, sizeof b, " (%.2f %.2f %.2f from %.2f %.2f %.2f)", at.x, at.y, at.z, w.player.eye.x,
                     w.player.eye.y, w.player.eye.z);
            out.push_back("looking at " + e->name + b);
        }
    } else if (cmd == "ai") {
        // ai [agent] stay|wander|follow: what a spawned NPC does (default: the last spawn). For tests and binds.
        std::istringstream as(rest);
        std::string a, b;
        as >> a >> b;
        if (b.empty()) std::swap(a, b);
        Entity* e = nullptr;
        for (auto& x : w.ents)
            if (a.empty() ? x->spawned : x->name == a) e = x.get();
        Entity::Ai mode = b == "stay" ? Entity::Ai::Idle : b == "wander" ? Entity::Ai::Wander : Entity::Ai::Follow;
        if (!e || !e->spawned) out.push_back("no such spawned agent");
        else if (b != "stay" && b != "wander" && b != "follow") out.push_back("ai [agent] stay|wander|follow");
        else {
            e->ai = mode;
            e->aiTimer = 0;
            out.push_back(e->name + ": " + b);
        }
    } else if (cmd == "pose") {
        // pose emotion <name> | mouth <shape> [weight] | fingers <curl...>: the Face & Finger Poser on the last
        // spawn, from the console (tests and binds). Curls repeat per hand: thumb, index, middle, ring, pinky.
        std::istringstream ps(rest);
        std::string what, arg;
        ps >> what >> arg;
        Entity* e = nullptr;
        for (auto& x : w.ents)
            if (x->spawned) e = x.get();
        if (!e || !e->info) {
            out.push_back("no spawned character");
        } else if (what == "emotion") {
            combat::SetEmotion(L, e, arg);
            out.push_back(e->name + " emotion: " + (e->emotion.empty() ? "none" : e->emotion));
        } else if (what == "mouth") {
            float wgt = 1.0f;
            ps >> wgt;
            combat::SetMouth(L, e, arg, wgt);
            out.push_back(e->name + " mouth: " + (e->mouthHandle >= 0 ? e->mouthShape : "none"));
        } else if (what == "fingers") {
            if (e->fingerHands < 0) combat::BuildFingers(e);
            std::vector<float> curl;
            if (!arg.empty()) curl.push_back((float)atof(arg.c_str()));
            for (float v; ps >> v;) curl.push_back(v);
            for (size_t f = 0; !curl.empty() && f < e->fingerCurl.size(); ++f) e->fingerCurl[f] = curl[f % curl.size()];
            combat::ApplyFingers(e);
            out.push_back(e->name + ": " + std::to_string(e->fingerCurl.size()) + " fingers");
        } else {
            std::string em, sh;
            for (auto& x : e->info->emotions) em += x + " ";
            for (auto& x : combat::MouthShapes(e->info->facePrefix)) sh += x + " ";
            out.push_back("emotions: " + em);
            out.push_back("mouths: " + sh);
            out.push_back("pose emotion <name> | mouth <shape> [weight] | fingers <curl...>");
        }
    } else if (cmd == "skel") {
        // skel [vtable rva]: live objects with that vtable (default SkeletonInstance, RTTI .?AVSkeletonInstance@@)
        uint32_t rva = rest.empty() ? 0x5f95a4 : (uint32_t)strtoul(rest.c_str(), nullptr, 16);
        auto objs = FindObjects(rva, 64);
        char b[64];
        snprintf(b, sizeof b, "%zu objects (exe base %08x)", objs.size(), (unsigned)ExeBase());
        out.push_back(b);
        for (auto o : objs) {
            snprintf(b, sizeof b, "%08x:", (unsigned)o);
            out.push_back(b + HexDwords(o, 20, false));
        }
    } else if (cmd == "hwbp") {
        // hwbp <hex addr> [rw]: watch writes (or reads too) there; hwbp alone lists the writers and disarms
        std::istringstream ps(rest);
        std::string as, mode;
        ps >> as >> mode;
        char b[160];
        if (!as.empty()) {
            int n = SetHwWatch((uintptr_t)strtoul(as.c_str(), nullptr, 16), mode == "rw" ? 3 : 1);
            snprintf(b, sizeof b, "watching %s on %d threads", as.c_str(), n);
            out.push_back(b);
        } else {
            SetHwWatch(0, 0);
            snprintf(b, sizeof b, "%ld hits (exe base %08x)", g_hwCount, (unsigned)ExeBase());
            out.push_back(b);
            for (auto& h : g_hwHits) {
                if (!h.eip) break;
                uint32_t eb = (uint32_t)ExeBase();
                snprintf(b, sizeof b, "  rva %06x x%u  ecx %08x esi %08x edi %08x  callers %06x %06x %06x",
                         h.eip - eb, h.n, h.ecx, h.esi, h.edi, h.ret[0] - eb, h.ret[1] - eb, h.ret[2] - eb);
                out.push_back(b);
            }
        }
    } else if (cmd == "peek") {
        // peek <hex address> [dwords]: hex and float view
        std::istringstream ps(rest);
        std::string as;
        int n = 16;
        ps >> as >> n;
        uintptr_t a = (uintptr_t)strtoul(as.c_str(), nullptr, 16);
        for (int i = 0; i < n; i += 8) {
            char b[32];
            snprintf(b, sizeof b, "%08x:", (unsigned)(a + 4 * i));
            out.push_back(b + HexDwords(a + 4 * i, std::min(8, n - i), true));
        }
    } else if (cmd == "poke") {
        // poke <hex address> <float>
        std::istringstream ps(rest);
        std::string as;
        float v = 0;
        ps >> as >> v;
        uintptr_t a = (uintptr_t)strtoul(as.c_str(), nullptr, 16);
        out.push_back(SafeWrite(a, &v, 4) ? "ok" : "write failed");
    } else if (cmd == "noclip") {
        w.player.noclip = !w.player.noclip;
    } else if (cmd == "god") {
        w.player.health = 999;
    } else if (cmd == "thirdperson") {
        w.player.thirdPerson = !w.player.thirdPerson;
    } else if (cmd == "giveammo") {
        for (auto& a : w.player.ammo) a.reserve = 999;
    } else if (cmd == "gm_measure") {
        Entity* a = nullptr;
        Entity* b = nullptr;
        for (auto& e : w.ents) {
            if (!e->character) continue;
            if (!a) a = e.get();
            else if (!b) b = e.get();
        }
        if (a && b) {
            char s[200];
            snprintf(s, sizeof s, "%s -> %s: %.3f units (ini unitsPerMeter=%g)", a->name.c_str(), b->name.c_str(),
                     Length(a->pos - b->pos), w.axes.unitsPerMeter);
            out.push_back(s);
        } else {
            out.push_back("need two characters in the scene");
        }
    } else if (cmd == "gm_calibrate") {
        w.axes.calibrated = false;
        g_calibStep = 0;
        w.axes.camLocalForward = kAxisCandidates[0];
        w.axes.rightSign = -1;
    } else if (!cmd.empty()) {
        out.push_back("unknown command; try help");
    }
    return out;
}

}  // namespace state
}  // namespace gm
