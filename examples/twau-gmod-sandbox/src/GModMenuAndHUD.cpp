// GModMenuAndHUD: everything drawn on top of The Wolf Among Us' Direct3D 9 frame.
//   - IDirect3DDevice9::Present / Reset hooks (ImGui DX9 + Win32 backends)
//   - the HL2/GMod HUD (health, suit, ammo, crosshair) in HALFLIFE2.ttf read from the user's GMod install
//   - weapon selector (slots 1-6, HL2 bucket layout and weapon glyphs), tool info, notifications
//   - spawn menu (hold Q): NPCs / ragdolls / playermodels filtered by biped, quadruped, bird
//   - context menu (hold C): Face Poser presets and per-channel sliders, tool modes
//   - map menu (M): every location of the five episodes
//   - console (Insert), physgun beam, tracers, explosions, the flashlight overlay, first-person viewmodels
//     built from the GMod/HL2 .mdl files, and Camera screenshots (WIC JPEG)
//   - input isolation: while the sandbox runs, the game's window procedure and DirectInput see nothing
#include <d3d9.h>
#define DIRECTINPUT_VERSION 0x0800
#include <dinput.h>
#include <imgui.h>
#include <imgui_impl_dx9.h>
#include <imgui_impl_win32.h>
#include <MinHook.h>
#include <wincodec.h>

#include <algorithm>
#include <atomic>
#include <ctime>
#include <map>

#include "Sandbox.h"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND, UINT, WPARAM, LPARAM);

namespace gm {
namespace hud {
void SubclassWindow();
namespace {

typedef HRESULT(__stdcall* PresentFn)(IDirect3DDevice9*, const RECT*, const RECT*, HWND, const RGNDATA*);
typedef HRESULT(__stdcall* ResetFn)(IDirect3DDevice9*, D3DPRESENT_PARAMETERS*);
PresentFn g_origPresent = nullptr;
ResetFn g_origReset = nullptr;
WNDPROC g_origWndProc = nullptr;
HWND g_hwnd = nullptr;
bool g_imgui = false;
std::atomic<float> g_wheel{0};

ImFont* g_fontNumbers = nullptr;  // HalfLife2, HUD digits
ImFont* g_fontIcons = nullptr;    // HalfLife2, weapon glyphs (big)
ImFont* g_fontLabel = nullptr;    // Verdana bold, HUD labels
ImFont* g_fontUi = nullptr;       // Roboto / coolvetica for menus
Bytes g_hl2Font, g_uiFont, g_labelFont;

struct Note { std::string text; float t; };
std::vector<Note> g_notes;
std::mutex g_noteMu;
float g_weaponSwitchTime = -10;
Weapon g_lastWeapon = Weapon::PhysGun;

// console
std::vector<std::string> g_consoleOut;
char g_consoleInput[512] = {};
// spawn menu
char g_search[64] = {};
int g_planFilter = 0;  // 0 all, 1 biped, 2 quadruped, 3 bird
int g_spawnTab = 0;    // 0 NPCs, 1 ragdolls, 2 playermodels, 3 tools
int g_mapEpisode = 0;

// HL2 HUD colours (ClientScheme.res: FgColor 255 220 0 100, BgColor 0 0 0 76, BrightFg 255 220 0 255)
const ImU32 kFg = IM_COL32(255, 220, 0, 230), kBg = IM_COL32(0, 0, 0, 76), kBright = IM_COL32(255, 220, 0, 255);
const ImU32 kDamaged = IM_COL32(180, 0, 0, 230);
const ImU32 kBeam = IM_COL32(77, 190, 255, 230);

// ====================================================================== viewmodels
struct VmVertex { float x, y, z, nx, ny, nz, u, v; };
constexpr DWORD kVmFvf = D3DFVF_XYZ | D3DFVF_NORMAL | D3DFVF_TEX1;
struct GpuModel {
    bool tried = false, ok = false;
    struct Part { IDirect3DVertexBuffer9* vb; IDirect3DIndexBuffer9* ib; UINT nv, ntri; IDirect3DTexture9* tex; };
    std::vector<Part> parts;
};
std::map<std::string, GpuModel> g_models;
std::map<std::string, IDirect3DTexture9*> g_textures;
IDirect3DTexture9* g_flashTex = nullptr;

// The game's device is D3D9Ex, which has no managed pool (run 7: every viewmodel buffer failed). Static
// buffers go in the default pool there; textures are filled in system memory and copied over.
bool g_deviceIsEx = false;
D3DPOOL StaticPool() { return g_deviceIsEx ? D3DPOOL_DEFAULT : D3DPOOL_MANAGED; }

IDirect3DTexture9* MakeTexture(IDirect3DDevice9* dev, UINT w, UINT h, D3DFORMAT fmt,
                               const std::function<void(D3DLOCKED_RECT&)>& fill) {
    IDirect3DTexture9* tex = nullptr;
    D3DLOCKED_RECT lr;
    if (!g_deviceIsEx) {
        if (FAILED(dev->CreateTexture(w, h, 1, 0, fmt, D3DPOOL_MANAGED, &tex, nullptr))) return nullptr;
        if (SUCCEEDED(tex->LockRect(0, &lr, nullptr, 0))) {
            fill(lr);
            tex->UnlockRect(0);
        }
        return tex;
    }
    IDirect3DTexture9* sys = nullptr;
    if (FAILED(dev->CreateTexture(w, h, 1, 0, fmt, D3DPOOL_SYSTEMMEM, &sys, nullptr))) return nullptr;
    if (SUCCEEDED(sys->LockRect(0, &lr, nullptr, 0))) {
        fill(lr);
        sys->UnlockRect(0);
    }
    if (SUCCEEDED(dev->CreateTexture(w, h, 1, 0, fmt, D3DPOOL_DEFAULT, &tex, nullptr)) &&
        FAILED(dev->UpdateTexture(sys, tex))) {
        tex->Release();
        tex = nullptr;
    }
    sys->Release();
    return tex;
}

IDirect3DTexture9* LoadVtfTexture(IDirect3DDevice9* dev, const std::string& vmtPath) {
    auto it = g_textures.find(vmtPath);
    if (it != g_textures.end()) return it->second;
    IDirect3DTexture9* tex = nullptr;
    Bytes vmt, vtf;
    VtfImage img;
    auto& src = AssetBridge::Get().Source();
    if (!vmtPath.empty() && src.Read(vmtPath, vmt)) {
        std::string base = VmtBaseTexture(std::string(vmt.begin(), vmt.end()));
        if (!base.empty() && src.Read("materials/" + base + ".vtf", vtf) && ParseVtf(vtf, img)) {
            D3DFORMAT fmt = img.format == VtfImage::DXT1 ? D3DFMT_DXT1 : img.format == VtfImage::DXT3 ? D3DFMT_DXT3
                          : img.format == VtfImage::DXT5 ? D3DFMT_DXT5 : D3DFMT_A8R8G8B8;
            tex = MakeTexture(dev, img.width, img.height, fmt, [&](D3DLOCKED_RECT& lr) {
                bool dxt = img.format != VtfImage::BGRA8;
                UINT rows = dxt ? (img.height + 3) / 4 : img.height;
                UINT rowBytes = (UINT)(img.pixels.size() / rows);
                for (UINT r = 0; r < rows; ++r)
                    memcpy((uint8_t*)lr.pBits + r * lr.Pitch, img.pixels.data() + r * rowBytes, rowBytes);
            });
        }
    }
    g_textures[vmtPath] = tex;
    return tex;
}

GpuModel& GetModel(IDirect3DDevice9* dev, const std::string& path) {
    GpuModel& gm = g_models[path];
    if (gm.tried) return gm;
    gm.tried = true;
    SourceModel sm;
    std::string err;
    if (!LoadSourceModel(AssetBridge::Get().Source(), path, "idle01", sm, &err)) {
        Log("[hud] viewmodel %s: %s", path.c_str(), err.c_str());
        return gm;
    }
    for (auto& mesh : sm.meshes) {
        GpuModel::Part part{};
        part.nv = (UINT)mesh.vertices.size();
        part.ntri = (UINT)mesh.indices.size() / 3;
        if (FAILED(dev->CreateVertexBuffer(part.nv * sizeof(VmVertex), D3DUSAGE_WRITEONLY, kVmFvf, StaticPool(), &part.vb, nullptr)) ||
            FAILED(dev->CreateIndexBuffer((UINT)mesh.indices.size() * 2, D3DUSAGE_WRITEONLY, D3DFMT_INDEX16, StaticPool(), &part.ib, nullptr)))
            continue;
        VmVertex* v;
        part.vb->Lock(0, 0, (void**)&v, 0);
        for (auto& mv : mesh.vertices)  // Source viewmodel space (x fwd, y left, z up) -> D3D view (x right, y up, z fwd)
            *v++ = {-mv.pos.y, mv.pos.z, mv.pos.x, -mv.normal.y, mv.normal.z, mv.normal.x, mv.u, mv.v};
        part.vb->Unlock();
        void* ip;
        part.ib->Lock(0, 0, &ip, 0);
        memcpy(ip, mesh.indices.data(), mesh.indices.size() * 2);
        part.ib->Unlock();
        part.tex = mesh.material < (int)sm.materials.size() ? LoadVtfTexture(dev, sm.materials[mesh.material]) : nullptr;
        gm.parts.push_back(part);
    }
    gm.ok = !gm.parts.empty();
    Log("[hud] viewmodel %s: %zu parts, pose from %s", path.c_str(), gm.parts.size(), sm.poseSource.c_str());
    return gm;
}

const char* ViewmodelPath(Weapon w) {
    switch (w) {
        case Weapon::PhysGun: return "models/weapons/v_physcannon.mdl";
        case Weapon::ToolGun: return "models/weapons/v_toolgun.mdl";
        case Weapon::Crowbar: return "models/weapons/v_crowbar.mdl";
        case Weapon::Pistol: return "models/weapons/v_pistol.mdl";
        case Weapon::Smg: return "models/weapons/v_smg1.mdl";
        case Weapon::Shotgun: return "models/weapons/v_shotgun.mdl";
        case Weapon::Rpg: return "models/weapons/v_rpg.mdl";
        default: return nullptr;  // the camera has no viewmodel, like GMod's
    }
}

void SetMatrix(IDirect3DDevice9* dev, D3DTRANSFORMSTATETYPE t, const Mat4& m) { dev->SetTransform(t, (const D3DMATRIX*)&m); }

void DrawViewmodel(IDirect3DDevice9* dev, const World& w, float W, float H) {
    const char* path = ViewmodelPath(w.player.weapon);
    if (!path || w.player.thirdPerson) return;
    GpuModel& m = GetModel(dev, path);
    if (!m.ok) return;
    const Player& p = w.player;
    dev->Clear(0, nullptr, D3DCLEAR_ZBUFFER, 0, 1.0f, 0);
    dev->SetVertexShader(nullptr);
    dev->SetPixelShader(nullptr);
    dev->SetFVF(kVmFvf);
    dev->SetRenderState(D3DRS_ZENABLE, TRUE);
    dev->SetRenderState(D3DRS_ZWRITEENABLE, TRUE);
    dev->SetRenderState(D3DRS_ZFUNC, D3DCMP_LESSEQUAL);
    dev->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
    dev->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
    dev->SetRenderState(D3DRS_ALPHATESTENABLE, FALSE);
    dev->SetRenderState(D3DRS_FOGENABLE, FALSE);
    dev->SetRenderState(D3DRS_STENCILENABLE, FALSE);
    dev->SetRenderState(D3DRS_SCISSORTESTENABLE, FALSE);
    dev->SetRenderState(D3DRS_COLORWRITEENABLE, 0xF);
    dev->SetRenderState(D3DRS_SRGBWRITEENABLE, FALSE);
    dev->SetRenderState(D3DRS_LIGHTING, TRUE);
    dev->SetRenderState(D3DRS_NORMALIZENORMALS, TRUE);
    dev->SetRenderState(D3DRS_AMBIENT, D3DCOLOR_XRGB(95, 92, 88));
    D3DLIGHT9 light{};
    light.Type = D3DLIGHT_DIRECTIONAL;
    light.Diffuse = {0.85f, 0.82f, 0.78f, 1};
    light.Direction = {0.35f, -0.6f, 0.7f};
    dev->SetLight(0, &light);
    dev->LightEnable(0, TRUE);
    D3DMATERIAL9 mat{};
    mat.Diffuse = mat.Ambient = {1, 1, 1, 1};
    dev->SetMaterial(&mat);
    dev->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_MODULATE);
    dev->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
    dev->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
    dev->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_DISABLE);
    dev->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_DISABLE);
    dev->SetSamplerState(0, D3DSAMP_MINFILTER, D3DTEXF_LINEAR);
    dev->SetSamplerState(0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
    dev->SetSamplerState(0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
    dev->SetSamplerState(0, D3DSAMP_ADDRESSU, D3DTADDRESS_WRAP);
    dev->SetSamplerState(0, D3DSAMP_ADDRESSV, D3DTADDRESS_WRAP);
    // Source's viewmodel_fov 54 is horizontal at 4:3 -> 41.6 degrees vertical.
    Mat4 proj = Mat4::PerspectiveFovLH(Deg2Rad(41.6f), W / H, 1.0f, 512.0f);
    // Bob as HL2 does it (CalcViewmodelBob / AddViewmodelBob): speed in Source units (320 = running) drives
    // a vertical cycle every 0.45 s and a lateral one every 0.9 s; the gun moves and also pitches, rolls
    // and yaws with them. Then mouse sway and the recoil kick. View space: x right, y up, z forward.
    static float bobTime = 0, lastTime = 0;
    float speed = Length(Vec3(p.vel.x, 0, p.vel.z)) / std::max(0.01f, w.axes.unitsPerMeter);
    // GMod's speeds, not metres: our walk (3 m/s) is its 200 units/s and our run (6 m/s) its 400 (capped at 320)
    float su = p.onGround && !p.noclip ? Clamp(speed * (400.0f / 6.0f), 0, 320) : 0;
    if (w.time > lastTime) bobTime += (w.time - lastTime) * (su / 320);
    lastTime = w.time;
    auto cycle = [](float t, float period) { return 2 * kPi * (std::fmod(t, period) / period); };
    float vb = Clamp(su * 0.005f * (0.3f + 0.7f * std::sin(cycle(bobTime, 0.45f))), -7, 4);
    float lb = Clamp(su * 0.005f * (0.3f + 0.7f * std::sin(cycle(bobTime, 0.9f))), -7, 4);
    float pitch = Deg2Rad(-vb * 0.4f - p.punchPitch * 0.5f), yaw = Deg2Rad(lb * 0.3f), roll = Deg2Rad(-vb * 0.5f);
    Mat4 rx = Mat4::Identity(), ry = Mat4::Identity(), rz = Mat4::Identity();
    rx.m[1][1] = std::cos(pitch); rx.m[1][2] = std::sin(pitch); rx.m[2][1] = -std::sin(pitch); rx.m[2][2] = std::cos(pitch);
    ry.m[0][0] = std::cos(yaw); ry.m[0][2] = -std::sin(yaw); ry.m[2][0] = std::sin(yaw); ry.m[2][2] = std::cos(yaw);
    rz.m[0][0] = std::cos(roll); rz.m[0][1] = std::sin(roll); rz.m[1][0] = -std::sin(roll); rz.m[1][1] = std::cos(roll);
    Mat4 world = rz * rx * ry;
    world.m[3][0] = lb * 0.8f - p.swayX;
    world.m[3][1] = vb * 0.1f - p.swayY - p.punchPitch * 0.15f;
    world.m[3][2] = vb * 0.1f - p.punchPitch * 0.25f;
    SetMatrix(dev, D3DTS_WORLD, world);
    SetMatrix(dev, D3DTS_VIEW, Mat4::Identity());
    SetMatrix(dev, D3DTS_PROJECTION, proj);
    for (auto& part : m.parts) {
        dev->SetTexture(0, part.tex);
        dev->SetStreamSource(0, part.vb, 0, sizeof(VmVertex));
        dev->SetIndices(part.ib);
        dev->DrawIndexedPrimitive(D3DPT_TRIANGLELIST, 0, 0, part.nv, 0, part.ntri);
    }
}

// Screen-space flashlight when the engine light agent didn't work: multiply the frame by (1 + cone).
void DrawFlashlightOverlay(IDirect3DDevice9* dev, float W, float H) {
    if (!g_flashTex) {
        g_flashTex = MakeTexture(dev, 128, 128, D3DFMT_A8R8G8B8, [](D3DLOCKED_RECT& lr) {
            for (int y = 0; y < 128; ++y)
                for (int x = 0; x < 128; ++x) {
                    float dx = (x - 63.5f) / 64.f, dy = (y - 63.5f) / 64.f, r = std::sqrt(dx * dx + dy * dy);
                    float v = Clamp(1.0f - (r - 0.25f) / 0.75f, 0, 1);
                    v = v * v * 0.9f;
                    uint8_t c = (uint8_t)(v * 255);
                    ((uint32_t*)((uint8_t*)lr.pBits + y * lr.Pitch))[x] = D3DCOLOR_ARGB(255, c, c, (uint8_t)(c * 0.92f));
                }
        });
        if (!g_flashTex) return;
    }
    struct V { float x, y, z, rhw, u, v; };
    float s = H * 1.1f, cx = W * 0.5f, cy = H * 0.5f;
    V q[4] = {{cx - s, cy - s, 0, 1, 0, 0}, {cx + s, cy - s, 0, 1, 1, 0}, {cx - s, cy + s, 0, 1, 0, 1}, {cx + s, cy + s, 0, 1, 1, 1}};
    dev->SetFVF(D3DFVF_XYZRHW | D3DFVF_TEX1);
    dev->SetRenderState(D3DRS_ZENABLE, FALSE);
    dev->SetRenderState(D3DRS_LIGHTING, FALSE);
    dev->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
    dev->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_DESTCOLOR);
    dev->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_ONE);
    dev->SetTexture(0, g_flashTex);
    dev->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
    dev->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
    dev->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, q, sizeof(V));
}

// ====================================================================== screenshots (Camera weapon)
void SaveScreenshot(IDirect3DDevice9* dev) {
    IDirect3DSurface9 *bb = nullptr, *rt = nullptr, *sys = nullptr;
    if (FAILED(dev->GetBackBuffer(0, 0, D3DBACKBUFFER_TYPE_MONO, &bb))) return;
    D3DSURFACE_DESC d;
    bb->GetDesc(&d);
    IDirect3DSurface9* src = bb;
    if (d.MultiSampleType != D3DMULTISAMPLE_NONE &&
        SUCCEEDED(dev->CreateRenderTarget(d.Width, d.Height, d.Format, D3DMULTISAMPLE_NONE, 0, FALSE, &rt, nullptr))) {
        dev->StretchRect(bb, nullptr, rt, nullptr, D3DTEXF_NONE);
        src = rt;
    }
    if (SUCCEEDED(dev->CreateOffscreenPlainSurface(d.Width, d.Height, d.Format, D3DPOOL_SYSTEMMEM, &sys, nullptr)) &&
        SUCCEEDED(dev->GetRenderTargetData(src, sys))) {
        D3DLOCKED_RECT lr;
        if (SUCCEEDED(sys->LockRect(&lr, nullptr, D3DLOCK_READONLY))) {
            CreateDirectoryA((GetPaths().modDir + "\\screenshots").c_str(), nullptr);
            char name[MAX_PATH];
            time_t t = time(nullptr);
            tm lt;
            localtime_s(&lt, &t);
            snprintf(name, sizeof name, "%s\\screenshots\\twau_%04d%02d%02d_%02d%02d%02d.jpg", GetPaths().modDir.c_str(),
                     lt.tm_year + 1900, lt.tm_mon + 1, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec);
            IWICImagingFactory* f = nullptr;
            IWICStream* stream = nullptr;
            IWICBitmapEncoder* enc = nullptr;
            IWICBitmapFrameEncode* frame = nullptr;
            wchar_t wname[MAX_PATH];
            MultiByteToWideChar(CP_ACP, 0, name, -1, wname, MAX_PATH);
            if (SUCCEEDED(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&f))) &&
                SUCCEEDED(f->CreateStream(&stream)) && SUCCEEDED(stream->InitializeFromFilename(wname, GENERIC_WRITE)) &&
                SUCCEEDED(f->CreateEncoder(GUID_ContainerFormatJpeg, nullptr, &enc)) &&
                SUCCEEDED(enc->Initialize(stream, WICBitmapEncoderNoCache)) &&
                SUCCEEDED(enc->CreateNewFrame(&frame, nullptr)) && SUCCEEDED(frame->Initialize(nullptr))) {
                WICPixelFormatGUID pf = GUID_WICPixelFormat32bppBGR;
                frame->SetSize(d.Width, d.Height);
                frame->SetPixelFormat(&pf);
                frame->WritePixels(d.Height, lr.Pitch, lr.Pitch * d.Height, (BYTE*)lr.pBits);
                frame->Commit();
                enc->Commit();
                Notify(std::string("Saved ") + (strrchr(name, '\\') + 1));
            }
            if (frame) frame->Release();
            if (enc) enc->Release();
            if (stream) stream->Release();
            if (f) f->Release();
            sys->UnlockRect();
        }
    }
    if (sys) sys->Release();
    if (rt) rt->Release();
    bb->Release();
}

// ====================================================================== fonts and ImGui
bool ReadFile(const std::string& p, Bytes& out) {
    FILE* f = fopen(p.c_str(), "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    out.resize(ftell(f));
    fseek(f, 0, SEEK_SET);
    fread(out.data(), 1, out.size(), f);
    fclose(f);
    return true;
}

void SetupImGui(IDirect3DDevice9* dev, float H) {
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    ImGui_ImplWin32_Init(g_hwnd);
    ImGui_ImplDX9_Init(dev);
    float s = H / 480.0f;
    ImFontConfig cfg;
    cfg.FontDataOwnedByAtlas = false;
    std::string gmod = GetPaths().gmodRoot;
    if (ReadFile(gmod + "\\garrysmod\\resource\\fonts\\Roboto-Regular.ttf", g_uiFont))
        g_fontUi = io.Fonts->AddFontFromMemoryTTF(g_uiFont.data(), (int)g_uiFont.size(), 9.0f * s, &cfg);
    else
        g_fontUi = io.Fonts->AddFontDefault();
    if (AssetBridge::Get().Source().Read("resource/HALFLIFE2.ttf", g_hl2Font)) {
        g_fontNumbers = io.Fonts->AddFontFromMemoryTTF(g_hl2Font.data(), (int)g_hl2Font.size(), 32.0f * s, &cfg);
        g_fontIcons = io.Fonts->AddFontFromMemoryTTF(g_hl2Font.data(), (int)g_hl2Font.size(), 48.0f * s, &cfg);
    }
    if (ReadFile("C:\\Windows\\Fonts\\verdanab.ttf", g_labelFont))
        g_fontLabel = io.Fonts->AddFontFromMemoryTTF(g_labelFont.data(), (int)g_labelFont.size(), 8.0f * s, &cfg);
    if (!g_fontNumbers) g_fontNumbers = g_fontIcons = g_fontUi;
    if (!g_fontLabel) g_fontLabel = g_fontUi;
    io.FontDefault = g_fontUi;
    ImGuiStyle& st = ImGui::GetStyle();
    st.WindowRounding = 4;
    st.FrameRounding = 3;
    st.Colors[ImGuiCol_WindowBg] = ImVec4(0.12f, 0.12f, 0.13f, 0.94f);
    st.Colors[ImGuiCol_TitleBgActive] = ImVec4(0.20f, 0.42f, 0.70f, 1);
    st.Colors[ImGuiCol_Button] = ImVec4(0.25f, 0.27f, 0.30f, 1);
    st.Colors[ImGuiCol_ButtonHovered] = ImVec4(0.27f, 0.52f, 0.82f, 1);
    st.ScaleAllSizes(std::max(1.0f, s * 0.6f));
    g_imgui = true;
}

// ====================================================================== HUD pieces
void Box(ImDrawList* dl, float x, float y, float w, float h, float s) {
    dl->AddRectFilled(ImVec2(x, y), ImVec2(x + w, y + h), kBg, 8 * s);
}

void DrawHud(ImDrawList* dl, World& w, float W, float H) {
    float s = H / 480.0f;
    Player& p = w.player;
    // health / suit, bottom-left (HudLayout.res: xpos 16, ypos 432, wide 102, tall 36)
    float y = 432 * s;
    auto stat = [&](float x, float wide, const char* label, float value) {
        Box(dl, x, y, wide * s, 36 * s, s);
        ImU32 c = value < 20 ? kDamaged : kFg;
        dl->AddText(g_fontLabel, g_fontLabel->FontSize, ImVec2(x + 8 * s, y + 20 * s), c, label);
        char b[16];
        snprintf(b, sizeof b, "%d", (int)std::max(0.0f, value));
        dl->AddText(g_fontNumbers, g_fontNumbers->FontSize, ImVec2(x + 50 * s, y + 2 * s), c, b);
    };
    stat(16 * s, 102, "HEALTH", p.health);
    if (p.armor > 0) stat(140 * s, 108, "SUIT", p.armor);
    // ammo, bottom-right (xpos r150, wide 136)
    WeaponState& a = p.ammo[(int)p.weapon];
    if (a.clipMax > 0) {
        float x = W - 150 * s;
        Box(dl, x, y, 136 * s, 36 * s, s);
        dl->AddText(g_fontLabel, g_fontLabel->FontSize, ImVec2(x + 8 * s, y + 20 * s), kFg, "AMMO");
        char b[16];
        snprintf(b, sizeof b, "%d", a.clip);
        dl->AddText(g_fontNumbers, g_fontNumbers->FontSize, ImVec2(x + 44 * s, y + 2 * s), a.clip == 0 ? kDamaged : kFg, b);
        snprintf(b, sizeof b, "%d", a.reserve);
        dl->AddText(g_fontLabel, g_fontLabel->FontSize * 1.6f, ImVec2(x + 98 * s, y + 16 * s), kFg, b);
    }
    // crosshair + hit marker
    float cx = W * 0.5f, cy = H * 0.5f, g = 4 * s, l = 7 * s;
    ImU32 ch = IM_COL32(255, 220, 0, 200);
    dl->AddLine(ImVec2(cx - g - l, cy), ImVec2(cx - g, cy), ch, 1.5f);
    dl->AddLine(ImVec2(cx + g, cy), ImVec2(cx + g + l, cy), ch, 1.5f);
    dl->AddLine(ImVec2(cx, cy - g - l), ImVec2(cx, cy - g), ch, 1.5f);
    dl->AddLine(ImVec2(cx, cy + g), ImVec2(cx, cy + g + l), ch, 1.5f);
    if (w.time - w.lastHitTime < 0.15f) {
        ImU32 hc = IM_COL32(255, 255, 255, 220);
        for (int sx : {-1, 1})
            for (int sy : {-1, 1})
                dl->AddLine(ImVec2(cx + sx * 6 * s, cy + sy * 6 * s), ImVec2(cx + sx * 11 * s, cy + sy * 11 * s), hc, 2);
    }
}

// HL2 weapon glyphs in HALFLIFE2.ttf (the "character" key of each weapon script).
const char* WeaponGlyph(Weapon wpn) {
    switch (wpn) {
        case Weapon::PhysGun: return "m";
        case Weapon::Crowbar: return "c";
        case Weapon::Pistol: return "d";
        case Weapon::Smg: return "a";
        case Weapon::Shotgun: return "b";
        case Weapon::Rpg: return "i";
        default: return nullptr;
    }
}

void DrawWeaponSelector(ImDrawList* dl, World& w, float W, float H) {
    if (w.player.weapon != g_lastWeapon) {
        g_lastWeapon = w.player.weapon;
        g_weaponSwitchTime = w.time;
    }
    float age = w.time - g_weaponSwitchTime;
    if (age > 2.0f) return;
    float s = H / 480.0f, alpha = age > 1.5f ? (2.0f - age) / 0.5f : 1.0f;
    int slotOf[(int)Weapon::Count] = {1, 2, 3, 4, 4, 5, 5, 6};
    int active = slotOf[(int)w.player.weapon];
    float slotW = 20 * s, activeW = 112 * s, gap = 4 * s;
    float total = 5 * (slotW + gap) + activeW;
    float x = W * 0.5f - total * 0.5f, y = 16 * s;
    for (int slot = 1; slot <= 6; ++slot) {
        float bw = slot == active ? activeW : slotW;
        float yy = y;
        for (int i = 0; i < (int)Weapon::Count; ++i) {
            if (slotOf[i] != slot) continue;
            bool sel = (Weapon)i == w.player.weapon;
            float bh = slot == active ? (sel ? 64 * s : 20 * s) : 20 * s;
            dl->AddRectFilled(ImVec2(x, yy), ImVec2(x + bw, yy + bh), IM_COL32(0, 0, 0, (int)(110 * alpha)), 6 * s);
            ImU32 c = IM_COL32(255, 220, 0, (int)((sel ? 255 : 120) * alpha));
            if (slot == active) {
                const char* gly = WeaponGlyph((Weapon)i);
                if (sel && gly && g_fontIcons != g_fontUi)
                    dl->AddText(g_fontIcons, g_fontIcons->FontSize, ImVec2(x + 10 * s, yy + 2 * s), c, gly);
                dl->AddText(g_fontLabel, g_fontLabel->FontSize, ImVec2(x + 6 * s, yy + bh - 12 * s), c,
                            combat::WeaponName((Weapon)i));
            }
            yy += bh + gap;
            if (slot != active) break;
        }
        char n[4];
        snprintf(n, sizeof n, "%d", slot);
        dl->AddText(g_fontLabel, g_fontLabel->FontSize, ImVec2(x + 3 * s, y + 1 * s), IM_COL32(255, 220, 0, (int)(255 * alpha)), n);
        x += bw + gap;
    }
}

void DrawEffects(ImDrawList* dl, World& w, float W, float H) {
    float sx, sy, ex, ey;
    for (auto& t : w.tracers)
        if (state::ProjectToScreen(t.from, sx, sy) && state::ProjectToScreen(t.to, ex, ey))
            dl->AddLine(ImVec2(sx, sy), ImVec2(ex, ey), w.player.weapon == Weapon::ToolGun ? IM_COL32(255, 255, 255, 220)
                                                                                           : IM_COL32(255, 230, 150, 200), 2);
    for (auto& b : w.blasts)
        if (state::ProjectToScreen(b.at, sx, sy)) {
            float k = (w.time - b.t) / 0.6f, r = (40 + 260 * k) * H / 1080.0f;
            dl->AddCircleFilled(ImVec2(sx, sy), r, IM_COL32(255, 160, 40, (int)(200 * (1 - k))), 32);
            dl->AddCircleFilled(ImVec2(sx, sy), r * 0.5f, IM_COL32(255, 240, 180, (int)(230 * (1 - k))), 24);
        }
    for (auto& r : combat::RocketPositions())
        if (state::ProjectToScreen(r, sx, sy)) dl->AddCircleFilled(ImVec2(sx, sy), 4, IM_COL32(255, 200, 80, 255));
    // physgun beam: from the muzzle to the held object, slightly curved like GMod's
    Entity* held = combat::HeldEntity();
    if (w.player.weapon == Weapon::PhysGun && (held || w.input.down[VK_LBUTTON])) {
        ImVec2 a(W * 0.63f, H * 0.80f), b(W * 0.5f, H * 0.5f);
        if (held && state::ProjectToScreen(held->pos + w.axes.up * ((held->character ? held->height * 0.5f : 0.3f) * w.axes.unitsPerMeter), ex, ey))
            b = ImVec2(ex, ey);
        ImVec2 c1(a.x + (b.x - a.x) * 0.3f, a.y - H * 0.12f), c2(b.x, b.y + (a.y - b.y) * 0.2f);
        dl->AddBezierCubic(a, c1, c2, b, IM_COL32(77, 190, 255, 90), 9);
        dl->AddBezierCubic(a, c1, c2, b, kBeam, 3);
        dl->AddCircleFilled(b, 6, kBeam);
    }
}

void DrawToolInfo(ImDrawList* dl, World& w, float H) {
    if (w.player.weapon != Weapon::ToolGun) return;
    float s = H / 480.0f;
    ImVec2 o(16 * s, 16 * s);
    dl->AddRectFilled(o, ImVec2(o.x + 170 * s, o.y + 38 * s), IM_COL32(0, 0, 0, 120), 4 * s);
    dl->AddText(g_fontUi, g_fontUi->FontSize * 1.4f, ImVec2(o.x + 6 * s, o.y + 3 * s), IM_COL32(255, 255, 255, 255),
                combat::ToolName(w.player.tool));
    const char* desc[] = {"Left: remove object", "Left: pick a face, then hold C", "Left/Right: next/previous animation",
                          "Left: toggle gravity, Right: launch", "Left: first object, Left: weld to"};
    dl->AddText(g_fontUi, g_fontUi->FontSize, ImVec2(o.x + 6 * s, o.y + 22 * s), IM_COL32(220, 220, 220, 255),
                desc[(int)w.player.tool]);
    if (w.player.tool == ToolMode::Animator && !combat::ToolInfo().empty())
        dl->AddText(g_fontUi, g_fontUi->FontSize, ImVec2(o.x + 6 * s, o.y + 42 * s), IM_COL32(255, 220, 0, 255),
                    combat::ToolInfo().c_str());
}

void DrawNotes(ImDrawList* dl, World& w, float W, float H) {
    std::lock_guard<std::mutex> lk(g_noteMu);
    float s = H / 480.0f, y = H - 80 * s;
    g_notes.erase(std::remove_if(g_notes.begin(), g_notes.end(), [&](const Note& n) { return w.time - n.t > 5; }), g_notes.end());
    for (auto it = g_notes.rbegin(); it != g_notes.rend(); ++it) {
        ImVec2 ts = g_fontUi->CalcTextSizeA(g_fontUi->FontSize, 1e9f, 0, it->text.c_str());
        float x = W - ts.x - 24 * s;
        dl->AddRectFilled(ImVec2(x - 6 * s, y - 2 * s), ImVec2(W - 16 * s, y + ts.y + 2 * s), IM_COL32(0, 0, 0, 160), 3 * s);
        dl->AddRectFilled(ImVec2(x - 6 * s, y - 2 * s), ImVec2(x - 3 * s, y + ts.y + 2 * s), IM_COL32(60, 160, 255, 255));
        dl->AddText(g_fontUi, g_fontUi->FontSize, ImVec2(x, y), IM_COL32(255, 255, 255, 255), it->text.c_str());
        y -= ts.y + 8 * s;
    }
}

// ====================================================================== menus
bool PlanMatches(BodyPlan p) {
    return g_planFilter == 0 || (g_planFilter == 1 && p == BodyPlan::Biped) || (g_planFilter == 2 && p == BodyPlan::Quadruped) ||
           (g_planFilter == 3 && p == BodyPlan::Bird);
}

void SpawnMenu(World& w, float W, float H) {
    ImGui::SetNextWindowPos(ImVec2(W * 0.06f, H * 0.08f));
    ImGui::SetNextWindowSize(ImVec2(W * 0.62f, H * 0.84f));
    ImGui::Begin("Spawn Menu", nullptr, ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse);
    const char* tabs[] = {"NPCs", "Ragdolls", "Playermodels", "Tools"};
    for (int i = 0; i < 4; ++i) {
        if (i) ImGui::SameLine();
        if (ImGui::Selectable(tabs[i], g_spawnTab == i, 0, ImVec2(W * 0.08f, 0))) g_spawnTab = i;
    }
    ImGui::Separator();
    if (g_spawnTab == 3) {
        for (int t = 0; t < (int)ToolMode::Count; ++t)
            if (ImGui::Selectable(combat::ToolName((ToolMode)t), w.player.tool == (ToolMode)t)) {
                w.player.tool = (ToolMode)t;
                combat::SelectWeapon(Weapon::ToolGun);
            }
        ImGui::End();
        return;
    }
    ImGui::SetNextItemWidth(W * 0.18f);
    ImGui::InputTextWithHint("##search", "Search...", g_search, sizeof g_search);
    ImGui::SameLine();
    ImGui::RadioButton("All", &g_planFilter, 0); ImGui::SameLine();
    ImGui::RadioButton("Bipeds", &g_planFilter, 1); ImGui::SameLine();
    ImGui::RadioButton("Quadrupeds", &g_planFilter, 2); ImGui::SameLine();
    ImGui::RadioButton("Birds", &g_planFilter, 3);
    ImGui::BeginChild("grid");
    std::string q = ToLower(g_search);
    float cell = W * 0.095f;
    int cols = std::max(1, (int)(ImGui::GetContentRegionAvail().x / (cell + 6)));
    int n = 0;
    for (auto& c : AssetBridge::Get().Telltale().Characters()) {
        if (!PlanMatches(c.plan)) continue;
        if (!q.empty() && ToLower(c.display + " " + c.skeleton).find(q) == std::string::npos) continue;
        if (n++ % cols) ImGui::SameLine();
        ImGui::PushID(c.prop.c_str());
        std::string label = c.display + "\n" + (c.plan == BodyPlan::Quadruped ? "[4 legs]" : c.plan == BodyPlan::Bird ? "[bird]" : "") +
                            (c.walkClip.empty() ? " no walk" : "");
        bool selected = g_spawnTab == 2 && w.player.playerModel == c.prop;
        if (selected) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.27f, 0.52f, 0.82f, 1));
        if (ImGui::Button(label.c_str(), ImVec2(cell, cell * 0.55f))) {
            const CharacterInfo* ci = &c;
            int tab = g_spawnTab;
            if (tab == 2) {
                w.player.playerModel = c.prop;
                w.player.playerModelAgent.clear();
                Notify("Playermodel: " + c.display + " (thirdperson in the console to see it)");
            } else {
                PostCommand([ci, tab](lua::State* L) {
                    std::lock_guard<std::recursive_mutex> lk(WorldLock());
                    Entity* e = combat::Spawn(L, *ci, tab == 0);
                    if (e && tab == 1) combat::Kill(L, e, Vec3());
                });
            }
        }
        if (selected) ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) ImGui::SetTooltip("%s\nwalk: %s\nrun: %s\nface: %s", c.prop.c_str(), c.walkClip.c_str(),
                                                      c.runClip.c_str(), c.facePrefix.c_str());
        ImGui::PopID();
    }
    ImGui::EndChild();
    ImGui::End();
}

void ContextMenu(World& w, float W, float H) {
    ImGui::SetNextWindowPos(ImVec2(W * 0.70f, H * 0.08f));
    ImGui::SetNextWindowSize(ImVec2(W * 0.27f, H * 0.84f));
    ImGui::Begin("Face & Finger Poser", nullptr, ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse);
    Entity* e = w.facePoserTarget;
    if (!e || !e->info) {
        ImGui::TextWrapped("Pick a character with the Tool Gun in Face Poser mode (R cycles tool modes), then hold C.");
        ImGui::End();
        return;
    }
    ImGui::Text("%s  (%s)", e->name.c_str(), e->info->facePrefix.c_str());
    Entity* target = e;
    auto post = [](std::function<void(lua::State*)> f) {
        PostCommand([f](lua::State* L) { std::lock_guard<std::recursive_mutex> lk(WorldLock()); f(L); });
    };
    float bw = W * 0.083f;
    // Emotions: every rest face the character ships (Bigby has 27, Faith 12)
    if (ImGui::CollapsingHeader("Emotion", ImGuiTreeNodeFlags_DefaultOpen)) {
        int col = 0;
        for (auto& em : e->info->emotions) {
            if (col++ % 3) ImGui::SameLine();
            bool on = ToLower(em) == ToLower(e->emotion);
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.45f, 0.8f, 1));
            if (ImGui::Button(em.c_str(), ImVec2(bw, 0))) {
                std::string pick = em;
                post([target, pick](lua::State* L) { combat::SetEmotion(L, target, pick); });
            }
            if (on) ImGui::PopStyleColor();
        }
        if (ImGui::Button("Neutral", ImVec2(bw, 0))) post([target](lua::State* L) { combat::SetEmotion(L, target, ""); });
        ImGui::SameLine();
        if (ImGui::Button("Eyes shut", ImVec2(bw, 0))) post([target](lua::State* L) { combat::SetEmotion(L, target, "dead"); });
    }
    // Mouth: a lip-sync shape over the emotion, as far as the slider says
    auto shapes = combat::MouthShapes(e->info->facePrefix);
    if (!shapes.empty() && ImGui::CollapsingHeader("Mouth", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (size_t i = 0; i <= shapes.size(); ++i) {
            if (i % 6) ImGui::SameLine();
            std::string sh = i < shapes.size() ? shapes[i] : "";
            bool on = sh == e->mouthShape;
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.45f, 0.8f, 1));
            if (ImGui::Button(sh.empty() ? "none" : sh.c_str(), ImVec2(W * 0.038f, 0))) {
                float wgt = e->mouthWeight > 0 ? e->mouthWeight : 1.0f;
                post([target, sh, wgt](lua::State* L) { combat::SetMouth(L, target, sh, wgt); });
            }
            if (on) ImGui::PopStyleColor();
        }
        float mw = e->mouthWeight;
        if (ImGui::SliderFloat("amount", &mw, 0.0f, 1.0f) && !e->mouthShape.empty()) {
            e->mouthWeight = mw;
            std::string sh = e->mouthShape;
            post([target, sh, mw](lua::State* L) { combat::SetMouth(L, target, sh, mw); });
        }
    }
    // Channels: the additive face clips (brows, eyes, blinks), each parked at its peak
    if (ImGui::CollapsingHeader("Face channels")) {
        auto chans = AssetBridge::Get().Telltale().FaceChannels(e->info->facePrefix);
        if (e->faceWeights.size() < chans.size()) e->faceWeights.resize(chans.size(), 0);
        std::string pre = e->info->facePrefix + "_face_";
        for (size_t i = 0; i < chans.size(); ++i) {
            std::string label = chans[i].substr(pre.size(), chans[i].size() - pre.size() - 8);  // strip "_add.anm"
            float v = e->faceWeights[i];
            if (ImGui::SliderFloat(label.c_str(), &v, 0.0f, 1.0f)) {
                e->faceWeights[i] = v;
                post([target, i, v](lua::State* L) { combat::SetFaceChannel(L, target, i, v); });
            }
        }
    }
    // Fingers: curl per finger, as GMod's Finger Poser
    if (ImGui::CollapsingHeader("Fingers", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (e->fingerHands == -1) {
            e->fingerHands = -2;
            post([target](lua::State*) { combat::BuildFingers(target); });
        }
        if (e->fingerHands == -2) {
            ImGui::TextDisabled("Looking for the hands...");
        } else if (e->fingerHands == 0) {
            ImGui::TextWrapped("No hands found on this skeleton.");
            if (ImGui::Button("Look again")) e->fingerHands = -1;
        } else {
            // presets for every hand: thumb, index, middle, ring, pinky
            struct Preset { const char* name; float c[5]; };
            const Preset presets[] = {{"Relaxed", {0, 0, 0, 0, 0}},       {"Fist", {0.8f, 1, 1, 1, 1}},
                                      {"Point", {0.8f, 0, 1, 1, 1}},       {"Thumbs up", {-0.3f, 1, 1, 1, 1}},
                                      {"Peace", {0.8f, 0, 0, 1, 1}},       {"Rock", {0.8f, 0, 1, 1, 0}},
                                      {"Flat", {-0.2f, -0.2f, -0.2f, -0.2f, -0.2f}}, {"Claw", {0.5f, 0.55f, 0.55f, 0.55f, 0.55f}}};
            int col = 0;
            for (auto& pr : presets) {
                if (col++ % 4) ImGui::SameLine();
                if (ImGui::Button(pr.name, ImVec2(W * 0.062f, 0))) {
                    for (size_t f = 0; f < e->fingerCurl.size(); ++f) e->fingerCurl[f] = pr.c[f % 5];
                    std::vector<float> curls = e->fingerCurl;
                    post([target, curls](lua::State*) { target->fingerCurl = curls; combat::ApplyFingers(target); });
                }
            }
            for (size_t f = 0; f < e->fingerCurl.size() && f < e->fingerNames.size(); ++f) {
                float v = e->fingerCurl[f];
                if (ImGui::SliderFloat(e->fingerNames[f].c_str(), &v, -0.3f, 1.0f)) {
                    e->fingerCurl[f] = v;
                    std::vector<float> curls = e->fingerCurl;
                    post([target, curls](lua::State*) { target->fingerCurl = curls; combat::ApplyFingers(target); });
                }
            }
        }
    }
    ImGui::End();
}

void MapMenu(World& w, float W, float H) {
    ImGui::SetNextWindowPos(ImVec2(W * 0.25f, H * 0.1f), ImGuiCond_Appearing);
    ImGui::SetNextWindowSize(ImVec2(W * 0.5f, H * 0.8f), ImGuiCond_Appearing);
    bool open = true;
    ImGui::Begin("Maps - The Wolf Among Us", &open, ImGuiWindowFlags_NoCollapse);
    const char* eps[] = {"Faith", "Smoke & Mirrors", "A Crooked Mile", "In Sheep's Clothing", "Cry Wolf"};
    for (int i = 0; i < 5; ++i) {
        if (i) ImGui::SameLine();
        char b[48];
        snprintf(b, sizeof b, "%d. %s", i + 1, eps[i]);
        if (ImGui::Selectable(b, g_mapEpisode == i, 0, ImVec2(W * 0.085f, 0))) g_mapEpisode = i;
    }
    ImGui::Separator();
    char ep[16];
    snprintf(ep, sizeof ep, "Fables10%d", g_mapEpisode + 1);
    ImGui::TextDisabled("Switches the game's resources to that episode and opens the scene (no story logic).");
    for (auto& sc : AssetBridge::Get().Telltale().Scenes()) {
        if (sc.episode != ep) continue;
        if (ImGui::Button((sc.display + "##" + sc.scene).c_str(), ImVec2(-1, 0))) {
            std::string scene = sc.scene, episode = sc.episode;
            PostCommand([scene, episode](lua::State* L) {
                state::ExitSandbox(L);
                bool ok = lua::Call(L, "GM.OpenScene", {scene, episode}, 1).B(0);
                Notify(ok ? "Loading " + scene : "SceneOpen failed for " + scene);
            });
            w.mapMenuOpen = false;
        }
    }
    ImGui::End();
    if (!open) w.mapMenuOpen = false;
}

void Console(World& w, float W, float H) {
    ImGui::SetNextWindowPos(ImVec2(W * 0.05f, H * 0.05f), ImGuiCond_Appearing);
    ImGui::SetNextWindowSize(ImVec2(W * 0.6f, H * 0.5f), ImGuiCond_Appearing);
    bool open = true;
    ImGui::Begin("Console (Insert)", &open);
    ImGui::BeginChild("log", ImVec2(0, -ImGui::GetFrameHeightWithSpacing()));
    for (auto& l : RecentLog(200)) ImGui::TextUnformatted(l.c_str());
    for (auto& l : g_consoleOut) ImGui::TextColored(ImVec4(0.6f, 0.85f, 1, 1), "%s", l.c_str());
    if (ImGui::GetScrollY() >= ImGui::GetScrollMaxY() - 20) ImGui::SetScrollHereY(1.0f);
    ImGui::EndChild();
    ImGui::SetNextItemWidth(-1);
    if (ImGui::InputText("##cmd", g_consoleInput, sizeof g_consoleInput, ImGuiInputTextFlags_EnterReturnsTrue)) {
        std::string line = g_consoleInput;
        g_consoleInput[0] = 0;
        g_consoleOut.push_back("] " + line);
        PostCommand([line](lua::State* L) {
            auto out = state::ConsoleCommand(L, line);
            g_consoleOut.insert(g_consoleOut.end(), out.begin(), out.end());
        });
        ImGui::SetKeyboardFocusHere(-1);
    }
    ImGui::End();
    if (!open) w.consoleOpen = false;
}

// ====================================================================== the frame
void Frame(IDirect3DDevice9* dev) {
    std::lock_guard<std::recursive_mutex> lk(WorldLock());
    World& w = GetWorld();
    D3DVIEWPORT9 vp;
    dev->GetViewport(&vp);
    RECT rc;
    GetClientRect(g_hwnd, &rc);
    float W = (float)(rc.right - rc.left), H = (float)(rc.bottom - rc.top);
    if (W < 1 || H < 1) return;
    if (!g_imgui) SetupImGui(dev, H);

    bool sandbox = w.mode == Mode::Sandbox;
    if (sandbox && combat::TakeScreenshotRequest()) SaveScreenshot(dev);  // the clean game frame

    IDirect3DStateBlock9* sb = nullptr;
    dev->CreateStateBlock(D3DSBT_ALL, &sb);
    dev->BeginScene();
    if (sandbox) {
        if (w.player.flashlight && !w.engineLightOk) DrawFlashlightOverlay(dev, W, H);
        if (!w.hideHud) DrawViewmodel(dev, w, W, H);
    }
    if (sb) { sb->Apply(); sb->Release(); }

    ImGui_ImplDX9_NewFrame();
    ImGui_ImplWin32_NewFrame();
    ImGui::GetIO().MouseDrawCursor = AnyMenuOpen();
    ImGui::NewFrame();
    ImDrawList* dl = ImGui::GetForegroundDrawList();
    if (sandbox) {
        DrawEffects(dl, w, W, H);
        if (!w.hideHud) {
            DrawHud(dl, w, W, H);
            DrawWeaponSelector(dl, w, W, H);
            DrawToolInfo(dl, w, H);
        }
        if (w.spawnMenuOpen) SpawnMenu(w, W, H);
        if (w.contextMenuOpen) ContextMenu(w, W, H);
        if (w.mapMenuOpen) MapMenu(w, W, H);
    }
    if (w.consoleOpen) Console(w, W, H);
    DrawNotes(dl, w, W, H);
    ImGui::EndFrame();
    ImGui::Render();
    ImGui_ImplDX9_RenderDrawData(ImGui::GetDrawData());
    dev->EndScene();
}

BOOL CALLBACK FindOwnWindow(HWND h, LPARAM out) {
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || GetWindow(h, GW_OWNER)) return TRUE;
    *(HWND*)out = h;
    return FALSE;
}

// The frame hooks. Telltale's renderer uses a D3D9Ex device and presents with PresentEx (exe+0x1952FE:
// call [vtable+0x1E4]), plain Present when a flag is off; both draw once per frame.
thread_local bool t_inPresent = false;
std::atomic<long> g_nPresent{0}, g_nPresentEx{0}, g_nEndScene{0};

void OnPresent(IDirect3DDevice9* dev, const char* via) {
    if (!g_hwnd) {
        D3DDEVICE_CREATION_PARAMETERS cp;
        dev->GetCreationParameters(&cp);
        g_hwnd = cp.hFocusWindow;
        if (!g_hwnd) EnumWindows(FindOwnWindow, (LPARAM)&g_hwnd);
        SubclassWindow();
    }
    static bool first = true;
    if (first) {
        first = false;
        Log("[hud] first frame via %s, window %p", via, (void*)g_hwnd);
    }
    lua::RequestTick();
    Frame(dev);
}

HRESULT __stdcall HookPresent(IDirect3DDevice9* dev, const RECT* a, const RECT* b, HWND c, const RGNDATA* d) {
    ++g_nPresent;
    if (t_inPresent) return g_origPresent(dev, a, b, c, d);
    t_inPresent = true;
    OnPresent(dev, "Present");
    HRESULT hr = g_origPresent(dev, a, b, c, d);
    t_inPresent = false;
    return hr;
}

typedef HRESULT(__stdcall* PresentExFn)(IDirect3DDevice9Ex*, const RECT*, const RECT*, HWND, const RGNDATA*, DWORD);
typedef HRESULT(__stdcall* ResetExFn)(IDirect3DDevice9Ex*, D3DPRESENT_PARAMETERS*, D3DDISPLAYMODEEX*);
PresentExFn g_origPresentEx = nullptr;
ResetExFn g_origResetEx = nullptr;

HRESULT __stdcall HookPresentEx(IDirect3DDevice9Ex* dev, const RECT* a, const RECT* b, HWND c, const RGNDATA* d,
                                DWORD f) {
    ++g_nPresentEx;
    if (t_inPresent) return g_origPresentEx(dev, a, b, c, d, f);
    t_inPresent = true;
    OnPresent(dev, "PresentEx");
    HRESULT hr = g_origPresentEx(dev, a, b, c, d, f);
    t_inPresent = false;
    return hr;
}

HRESULT __stdcall HookReset(IDirect3DDevice9* dev, D3DPRESENT_PARAMETERS* pp) {
    if (g_imgui) ImGui_ImplDX9_InvalidateDeviceObjects();
    HRESULT hr = g_origReset(dev, pp);
    if (g_imgui && SUCCEEDED(hr)) ImGui_ImplDX9_CreateDeviceObjects();
    return hr;
}

HRESULT __stdcall HookResetEx(IDirect3DDevice9Ex* dev, D3DPRESENT_PARAMETERS* pp, D3DDISPLAYMODEEX* mode) {
    if (g_imgui) ImGui_ImplDX9_InvalidateDeviceObjects();
    HRESULT hr = g_origResetEx(dev, pp, mode);
    if (g_imgui && SUCCEEDED(hr)) ImGui_ImplDX9_CreateDeviceObjects();
    return hr;
}

// ====================================================================== input isolation
bool IsInputMsg(UINT m) {
    return (m >= WM_KEYFIRST && m <= WM_KEYLAST) || (m >= WM_MOUSEFIRST && m <= WM_MOUSELAST) || m == WM_INPUT;
}

LRESULT CALLBACK WndProc(HWND h, UINT m, WPARAM wp, LPARAM lp) {
    if (m == WM_MOUSEWHEEL) g_wheel = g_wheel + (float)GET_WHEEL_DELTA_WPARAM(wp) / WHEEL_DELTA;
    bool sandbox = GetWorld().mode == Mode::Sandbox;
    if (g_imgui && AnyMenuOpen()) ImGui_ImplWin32_WndProcHandler(h, m, wp, lp);
    if ((sandbox || GetWorld().consoleOpen) && IsInputMsg(m)) return 0;  // the story underneath must not react to WASD, clicks, Q...
    if (sandbox && m == WM_SETCURSOR) return TRUE;
    return CallWindowProc(g_origWndProc, h, m, wp, lp);
}

// DirectInput: zero what the game reads while the sandbox runs.
typedef HRESULT(__stdcall* GetStateFn)(IDirectInputDevice8A*, DWORD, LPVOID);
typedef HRESULT(__stdcall* GetDataFn)(IDirectInputDevice8A*, DWORD, LPDIDEVICEOBJECTDATA, LPDWORD, DWORD);
GetStateFn g_origGetStateA = nullptr, g_origGetStateW = nullptr;
GetDataFn g_origGetDataA = nullptr, g_origGetDataW = nullptr;

HRESULT __stdcall HookGetStateA(IDirectInputDevice8A* d, DWORD n, LPVOID p) {
    HRESULT hr = g_origGetStateA(d, n, p);
    if (SUCCEEDED(hr) && GetWorld().mode == Mode::Sandbox) memset(p, 0, n);
    return hr;
}
HRESULT __stdcall HookGetStateW(IDirectInputDevice8A* d, DWORD n, LPVOID p) {
    HRESULT hr = g_origGetStateW(d, n, p);
    if (SUCCEEDED(hr) && GetWorld().mode == Mode::Sandbox) memset(p, 0, n);
    return hr;
}
HRESULT __stdcall HookGetDataA(IDirectInputDevice8A* d, DWORD sz, LPDIDEVICEOBJECTDATA o, LPDWORD n, DWORD f) {
    HRESULT hr = g_origGetDataA(d, sz, o, n, f);
    if (SUCCEEDED(hr) && n && GetWorld().mode == Mode::Sandbox) *n = 0;
    return hr;
}
HRESULT __stdcall HookGetDataW(IDirectInputDevice8A* d, DWORD sz, LPDIDEVICEOBJECTDATA o, LPDWORD n, DWORD f) {
    HRESULT hr = g_origGetDataW(d, sz, o, n, f);
    if (SUCCEEDED(hr) && n && GetWorld().mode == Mode::Sandbox) *n = 0;
    return hr;
}

void HookDirectInput() {
    typedef HRESULT(WINAPI * CreateFn)(HINSTANCE, DWORD, REFIID, LPVOID*, LPUNKNOWN);
    HMODULE di = GetModuleHandleA("dinput8.dll");
    CreateFn create = di ? (CreateFn)GetProcAddress(di, "DirectInput8Create") : nullptr;
    if (!create) return;
    IDirectInput8A* a = nullptr;
    IDirectInput8W* wv = nullptr;
    if (SUCCEEDED(create(GetModuleHandle(nullptr), DIRECTINPUT_VERSION, IID_IDirectInput8A, (void**)&a, nullptr))) {
        IDirectInputDevice8A* dev = nullptr;
        if (SUCCEEDED(a->CreateDevice(GUID_SysKeyboard, &dev, nullptr))) {
            void** vt = *(void***)dev;
            MH_CreateHook(vt[9], (void*)&HookGetStateA, (void**)&g_origGetStateA);
            MH_CreateHook(vt[10], (void*)&HookGetDataA, (void**)&g_origGetDataA);
            MH_EnableHook(vt[9]);
            MH_EnableHook(vt[10]);
            dev->Release();
        }
        a->Release();
    }
    if (SUCCEEDED(create(GetModuleHandle(nullptr), DIRECTINPUT_VERSION, IID_IDirectInput8W, (void**)&wv, nullptr))) {
        IDirectInputDevice8W* dev = nullptr;
        if (SUCCEEDED(wv->CreateDevice(GUID_SysKeyboard, &dev, nullptr))) {
            void** vt = *(void***)dev;
            if (vt[9] != (void*)g_origGetStateA) {  // A and W may share code; MinHook refuses duplicates anyway
                MH_CreateHook(vt[9], (void*)&HookGetStateW, (void**)&g_origGetStateW);
                MH_CreateHook(vt[10], (void*)&HookGetDataW, (void**)&g_origGetDataW);
                MH_EnableHook(vt[9]);
                MH_EnableHook(vt[10]);
            }
            dev->Release();
        }
        wv->Release();
    }
}

}  // namespace

void SubclassWindow() {
    if (g_hwnd && !g_origWndProc) g_origWndProc = (WNDPROC)SetWindowLongPtrA(g_hwnd, GWLP_WNDPROC, (LONG_PTR)WndProc);
}

// ====================================================================== public
namespace {
std::atomic<bool> g_deviceHooked{false};
std::atomic<bool> g_makingProbe{false};

const char* ModuleOf(void* p, char* buf, size_t n) {
    HMODULE m = nullptr;
    buf[0] = 0;
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)p, &m))
        GetModuleFileNameA(m, buf, (DWORD)n);
    const char* s = strrchr(buf, '\\');
    return s ? s + 1 : buf;
}

// Hooks the frame functions of the game's own device (on the game thread, from a posted command).
// Hooking last puts us in front of the Steam overlay, whose Present/PresentEx patches jump back into
// d3d9.dll past the entry: a hook placed before the overlay's is never reached (runs 4-6).
void HookGameDevice(IDirect3DDevice9* dev) {
    if (g_deviceHooked) return;
    void** vt = *(void***)dev;
    char m[MAX_PATH];
    bool ok = MH_CreateHook(vt[17], (void*)&HookPresent, (void**)&g_origPresent) == MH_OK &&
              MH_CreateHook(vt[16], (void*)&HookReset, (void**)&g_origReset) == MH_OK;
    IDirect3DDevice9Ex* ex = nullptr;
    if (ok && SUCCEEDED(dev->QueryInterface(__uuidof(IDirect3DDevice9Ex), (void**)&ex)) && ex) {
        void** xv = *(void***)ex;
        Log("[hud] the game device is D3D9Ex; PresentEx at %p (%s)", xv[121], ModuleOf(xv[121], m, sizeof m));
        g_deviceIsEx = true;
        ok = MH_CreateHook(xv[121], (void*)&HookPresentEx, (void**)&g_origPresentEx) == MH_OK &&
             MH_CreateHook(xv[132], (void*)&HookResetEx, (void**)&g_origResetEx) == MH_OK;
        ex->Release();
    }
    ok = ok && MH_EnableHook(MH_ALL_HOOKS) == MH_OK;
    g_deviceHooked = ok;
    Log(ok ? "[hud] game device %p: Present/PresentEx/Reset hooked" : "[hud] game device %p: hooking failed",
        (void*)dev);
}

// EndScene finds the game's device: its first caller that isn't our probe device.
typedef HRESULT(__stdcall* EndSceneFn)(IDirect3DDevice9*);
EndSceneFn g_origEndScene = nullptr;
std::atomic<bool> g_gameDeviceSeen{false};

HRESULT __stdcall HookEndScene(IDirect3DDevice9* dev) {
    ++g_nEndScene;
    if (!g_makingProbe && !g_gameDeviceSeen.exchange(true)) {
        dev->AddRef();
        PostCommand([dev](lua::State*) {
            HookGameDevice(dev);
            dev->Release();
        });
    }
    return g_origEndScene(dev);
}
}  // namespace

// From the game thread, ~2 s after start (the game and the Steam overlay have their device by then).
// A throwaway NULLREF device gives d3d9.dll's EndScene; the game's next EndScene hands us its device.
// It's made on the game thread so no D3D call of the game's runs at the same time (a HAL device from
// the init thread corrupted the heap in run 3). Nothing is hooked at load: the game creates its device
// with Direct3DCreate9Ex, and the overlay sits in front of both exports anyway.
void LateHook() {
    static bool tried = false;
    if (tried) return;
    tried = true;
    if (!g_hwnd) EnumWindows(FindOwnWindow, (LPARAM)&g_hwnd);
    if (g_hwnd) SubclassWindow();
    WNDCLASSA wc = {};
    wc.lpfnWndProc = DefWindowProcA;
    wc.hInstance = GetModuleHandleA(nullptr);
    wc.lpszClassName = "gm_probe_d3d";
    RegisterClassA(&wc);
    HWND w = CreateWindowExA(0, wc.lpszClassName, "", WS_OVERLAPPED, 0, 0, 8, 8, nullptr, nullptr, wc.hInstance, nullptr);
    g_makingProbe = true;
    IDirect3D9* d3d = w ? Direct3DCreate9(D3D_SDK_VERSION) : nullptr;
    IDirect3DDevice9* dev = nullptr;
    if (d3d) {
        D3DPRESENT_PARAMETERS pp = {};
        pp.Windowed = TRUE;
        pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
        pp.hDeviceWindow = w;
        pp.BackBufferFormat = D3DFMT_UNKNOWN;
        HRESULT hr = d3d->CreateDevice(D3DADAPTER_DEFAULT, D3DDEVTYPE_NULLREF, w,
                                       D3DCREATE_SOFTWARE_VERTEXPROCESSING | D3DCREATE_DISABLE_DRIVER_MANAGEMENT, &pp,
                                       &dev);
        if (FAILED(hr)) Log("[hud] probe device failed (%08lx): no HUD this run", (unsigned long)hr);
    }
    if (dev) {
        void** vt = *(void***)dev;
        bool ok = MH_CreateHook(vt[42], (void*)&HookEndScene, (void**)&g_origEndScene) == MH_OK &&
                  MH_EnableHook(vt[42]) == MH_OK;
        Log(ok ? "[hud] EndScene hooked; window %p" : "[hud] could not hook EndScene; window %p", (void*)g_hwnd);
        dev->Release();
    }
    if (d3d) d3d->Release();
    g_makingProbe = false;
    if (w) DestroyWindow(w);
    UnregisterClassA(wc.lpszClassName, wc.hInstance);
}

std::string FrameStats() {
    char buf[160];
    snprintf(buf, sizeof buf, "frames: Present %ld, PresentEx %ld, EndScene %ld", g_nPresent.load(),
             g_nPresentEx.load(), g_nEndScene.load());
    return buf;
}

// From the init thread: DirectInput isolation.
bool Init() {
    HookDirectInput();
    return true;
}

void Notify(const std::string& msg) {
    std::lock_guard<std::mutex> lk(g_noteMu);
    g_notes.push_back({msg, GetWorld().time});
    Log("[note] %s", msg.c_str());
}

float ConsumeWheel() { return g_wheel.exchange(0); }
bool WantsKeyboard() { return g_imgui && ImGui::GetCurrentContext() && ImGui::GetIO().WantTextInput; }
bool AnyMenuOpen() {
    World& w = GetWorld();
    return w.spawnMenuOpen || w.contextMenuOpen || w.mapMenuOpen || w.consoleOpen;
}

}  // namespace hud

HWND GameWindow() { return hud::g_hwnd; }
bool GameWindowFocused() { return hud::g_hwnd && GetForegroundWindow() == hud::g_hwnd; }

}  // namespace gm
