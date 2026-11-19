// Shared world model for the three gameplay modules:
//   StateAndCameraManager  - modes (F1/F3), snapshot/restore, player controller, camera, noclip, flashlight
//   GModMenuAndHUD         - D3D9/ImGui: HUD, weapon selector, spawn menu (Q), face poser (C), maps (M)
//   CombatAndRagdollPhysics- weapons, physgun, toolgun, physics bodies, ragdolls, NPC locomotion
// Everything here is touched on the game thread (inside the lua_pcall hook) and read by the renderer
// under WorldLock().
#pragma once
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "AssetBridge.h"
#include "Common.h"
#include "LuaBridge.h"

namespace gm {

enum class Mode { Story, Sandbox };

// ------------------------------------------------------------------ engine axis calibration
// Telltale's camera forward axis and handedness are checked at runtime (StateAndCameraManager) by reading
// AgentGetForwardVec back from the camera we created; defaults are the first guess (Y up, camera looks +Z).
struct Axes {
    Vec3 up{0, 1, 0};
    Vec3 camLocalForward{0, 0, 1};
    // screen-right = rightSign * cross(up, forward). Telltale's is -1 (run 16: with +1 the mouse turned and A/D
    // strafed the wrong way); the screen-projection check reads a stale camera, so it only logs.
    float rightSign = -1.0f;
    float unitsPerMeter = 1.0f; // from gmod_sandbox.ini (measure with the console: gm_measure)
    bool calibrated = false;
};

// ------------------------------------------------------------------ entities
struct Ragdoll;    // CombatAndRagdollPhysics.cpp
struct FingerRig;  // CombatAndRagdollPhysics.cpp
struct RagdollDeleter {
    void operator()(Ragdoll* r) const;
};

enum class Phys {
    Animated,  // the engine animates it (story pose, or our locomotion clip)
    Frozen,    // physgun right-click: stays in the air
    Held,      // in the physgun beam
    Rigid,     // falling/sliding body we integrate
    Ragdoll    // dead: verlet ragdoll drives the root transform
};

struct Entity {
    std::string name;      // engine agent name
    std::string prop;      // e.g. sk54_bigby.prop (spawns) or guessed from the name
    std::string skeleton;  // sk54_bigby, empty for non-characters
    const CharacterInfo* info = nullptr;
    bool spawned = false;  // ours: destroyed on F3
    bool character = false;
    bool isPlayerBody = false;  // the story Bigby (hidden in first person)

    // engine transform as last read/written
    Vec3 pos;
    Quat rot;
    bool visible = true;
    bool hasMesh = true;  // false for logical helpers (look-at targets, stations): not hittable
    // snapshot at F1 (story agents only)
    Vec3 origPos;
    Quat origRot;
    bool origVisible = true;

    // gameplay
    float hp = 100, maxHp = 100;
    bool dead = false;
    Phys phys = Phys::Animated;
    Vec3 vel, angVel;
    float radius = 0.3f, height = 1.8f;  // metres before unitsPerMeter
    float groundY = 0;
    bool gravity = true;
    float mass = 80;
    std::unique_ptr<Ragdoll, RagdollDeleter> ragdoll;
    bool dirty = false;  // push pos/rot to the engine this tick

    // NPC locomotion
    enum class Ai { None, Idle, Wander, Follow } ai = Ai::Idle;
    Vec3 goal;
    float aiTimer = 0;
    int clipHandle = -1;  // GM.PlayClip handle of the current body loop
    std::string clipName;
    // face poser
    int emotionHandle = -1;
    std::string emotion;  // the rest face playing: phoneme_default_<emotion> ("angryB"), "" for none
    int mouthHandle = -1;
    std::string mouthShape;  // phoneme mouth over the emotion: "AA", "O", "MM"... ("" for none)
    float mouthWeight = 1.0f;
    std::vector<std::pair<std::string, int>> faceHandles;  // channel clip -> handle
    std::vector<float> faceWeights;
    // finger poser: curl per finger (hand * 5 + finger, thumb first), -0.3 bent back .. 1 a fist
    int fingerHands = -1;  // hands found; -1 not looked yet, -2 looking
    std::vector<std::string> fingerNames;
    std::vector<float> fingerCurl;
    std::shared_ptr<FingerRig> fingerRig;
};

// ------------------------------------------------------------------ player
enum class Weapon { PhysGun = 0, ToolGun, Crowbar, Pistol, Smg, Shotgun, Rpg, Camera, Count };
struct WeaponState {
    int clip = 0, reserve = 0, clipMax = 0;
    float nextFire = 0;
};

enum class ToolMode { Remover = 0, FacePoser, Animator, Physics, Weld, Count };

struct Player {
    Vec3 pos;        // feet, engine units
    float yaw = 0, pitch = 0, roll = 0;
    float fov = 75;  // degrees, vertical
    Vec3 vel;
    bool onGround = true, noclip = false, crouch = false;
    bool flashlight = false;
    float health = 100, armor = 0;
    float floorY = 0;  // ground height (along up) where the sandbox started
    Weapon weapon = Weapon::PhysGun;
    WeaponState ammo[(int)Weapon::Count];
    ToolMode tool = ToolMode::Remover;
    std::string playerModel = "sk54_bigby.prop";
    std::string playerModelAgent;  // spawned body for third person
    bool thirdPerson = false;
    // view effects
    float punchPitch = 0, bob = 0, swayX = 0, swayY = 0;
    // derived each tick
    Vec3 eye, forward, right, up;
};

// ------------------------------------------------------------------ input (polled on the game thread)
struct InputFrame {
    float mouseDx = 0, mouseDy = 0, wheel = 0;
    bool down[256] = {};
    bool pressed[256] = {};   // went down this tick
    bool released[256] = {};
};

// ------------------------------------------------------------------ the world
struct World {
    Mode mode = Mode::Story;
    Axes axes;
    Player player;
    std::vector<std::unique_ptr<Entity>> ents;
    std::vector<std::string> activeScenes;
    std::string sceneForSpawns;
    std::string storyCamera;  // camera that was active at F1 (restored at F3)
    InputFrame input;
    float time = 0, dt = 0;
    int spawnCounter = 0;
    bool luaReady = false;
    bool engineLightOk = false;  // flashlight agent works; otherwise the screen-space fallback is drawn
    std::string status;          // one-line status for the HUD/console

    // UI state shared with GModMenuAndHUD
    bool spawnMenuOpen = false, contextMenuOpen = false, mapMenuOpen = false, consoleOpen = false;
    bool hideHud = false;  // camera weapon
    Entity* facePoserTarget = nullptr;
    float lastHitTime = -10;  // hit marker
    struct Shot { Vec3 from, to; float t; };
    std::vector<Shot> tracers;
    struct Blast { Vec3 at; float t; };
    std::vector<Blast> blasts;

    Entity* Find(const std::string& name);
    Entity* Add(const std::string& name);
    void Remove(Entity* e);
};

World& GetWorld();
std::recursive_mutex& WorldLock();

// Work for the game thread (UI -> engine). Runs at the start of the next tick with the Lua state.
void PostCommand(std::function<void(lua::State*)> fn);
void RunCommands(lua::State* L);

// Memory probes (StateAndCameraManager.cpp): SEH-guarded access and a vtable scan of the heap.
bool SafeRead(uintptr_t a, void* out, size_t n);
bool SafeWrite(uintptr_t a, const void* in, size_t n);
uintptr_t ExeBase();
std::vector<uintptr_t> FindObjects(uint32_t vtableRva, size_t max);

// Called by the modules
namespace state {
void Init();                       // loads ini, registers the tick
void Tick(lua::State* L);          // the whole sandbox frame
void EnterSandbox(lua::State* L);  // F1
void ExitSandbox(lua::State* L);   // F3
void SyncTransforms(lua::State* L);
bool ProjectToScreen(const Vec3& world, float& sx, float& sy);  // using the calibrated camera
std::vector<std::string> ConsoleCommand(lua::State* L, const std::string& line);
}  // namespace state

namespace combat {
void Init();
void Tick(lua::State* L, float dt);    // weapons, physics, AI
void OnEnterSandbox(lua::State* L);
void OnExitSandbox(lua::State* L);
void SelectWeapon(Weapon w);
Vec3 AimPoint(const Entity& e);  // chest, or a corpse's pelvis
bool CapturesMouse();  // physgun rotate (E) or camera zoom (RMB) uses the mouse instead of the view
const char* WeaponName(Weapon w);
const char* ToolName(ToolMode t);
Entity* Spawn(lua::State* L, const CharacterInfo& c, bool asNpc);
void SetEmotion(lua::State* L, Entity* e, const std::string& emotion);  // "" clears
void SetFaceChannel(lua::State* L, Entity* e, size_t channel, float weight);
void SetMouth(lua::State* L, Entity* e, const std::string& shape, float weight);  // "" clears
std::vector<std::string> MouthShapes(const std::string& facePrefix);  // "AA", "EE", ... the face has
void BuildFingers(Entity* e);   // finds the hands: sets fingerHands, fingerNames, fingerCurl
void ApplyFingers(Entity* e);   // pushes fingerCurl to the bones
void Kill(lua::State* L, Entity* e, const Vec3& impulse);
// Ray vs entities: returns the closest hit (or nullptr) and the distance along the ray.
Entity* Trace(const Vec3& from, const Vec3& dir, float maxDist, float* outDist, const Entity* ignore = nullptr);
// For the HUD (read under WorldLock)
Entity* HeldEntity();
bool TakeScreenshotRequest();
std::vector<Vec3> RocketPositions();
const std::string& ToolInfo();
}  // namespace combat

namespace hud {

bool Init();       // from the init thread: DirectInput isolation
std::string FrameStats();  // hook call counters for the heartbeat log
void LateHook();   // from the game thread, if the early route missed the device (Steam overlay)
void Notify(const std::string& msg);
float ConsumeWheel();   // mouse wheel notches since the last call (from the window procedure)
bool WantsKeyboard();   // a text field (console, search) has focus: no hotkeys
bool AnyMenuOpen();     // spawn menu, context menu, map menu or console: free cursor, no mouse look
}  // namespace hud

namespace audio {
bool Init();
void Play(const std::string& sourceSoundPath, float volume = 1.0f);  // e.g. "sound/items/flashlight1.wav"
int PlayLoop(const std::string& sourceSoundPath, float volume = 1.0f);
void Stop(int loopId);
}  // namespace audio

}  // namespace gm
