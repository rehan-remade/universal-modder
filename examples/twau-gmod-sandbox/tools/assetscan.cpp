// twau_assetscan: checks AssetBridge against the real installs without launching either game.
//   twau_assetscan [--gmod <dir>] [--twau <dir>] [--chars] [--scenes] [--model <models/x.mdl>]...
// Exit code 0 only when every check passes.
#include <cstdio>
#include <cstring>

#include "AssetBridge.h"

namespace gm {
void Log(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
}
}  // namespace gm

using namespace gm;

static int g_fail = 0;
static void Check(bool ok, const char* what) {
    printf("  [%s] %s\n", ok ? " ok " : "FAIL", what);
    if (!ok) ++g_fail;
}

static const char* PlanName(BodyPlan p) {
    switch (p) {
        case BodyPlan::Quadruped: return "quadruped";
        case BodyPlan::Bird: return "bird";
        case BodyPlan::Prop: return "prop";
        default: return "biped";
    }
}

int main(int argc, char** argv) {
    Paths paths;
    bool chars = false, scenes = false;
    std::string find, dumpName, dumpDir;
    std::vector<std::string> models = {"models/weapons/v_pistol.mdl", "models/weapons/v_toolgun.mdl",
                                       "models/weapons/v_physcannon.mdl", "models/weapons/v_crowbar.mdl",
                                       "models/weapons/v_smg1.mdl", "models/weapons/v_shotgun.mdl",
                                       "models/weapons/v_rpg.mdl", "models/maxofs2d/camera.mdl"};
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--gmod") && i + 1 < argc) paths.gmodRoot = argv[++i];
        else if (!strcmp(argv[i], "--twau") && i + 1 < argc) paths.twauRoot = argv[++i];
        else if (!strcmp(argv[i], "--chars")) chars = true;
        else if (!strcmp(argv[i], "--scenes")) scenes = true;
        else if (!strcmp(argv[i], "--find") && i + 1 < argc) find = argv[++i];
        else if (!strcmp(argv[i], "--dump") && i + 2 < argc) { dumpName = argv[++i]; dumpDir = argv[++i]; }
    }
    AssetBridge& ab = AssetBridge::Get();
    printf("== mount\n");
    Check(ab.Init(paths), "both installs mounted");
    // Lookups for reverse engineering (keep dumps outside the repo: they are game files).
    if (!find.empty()) {
        for (auto& n : ab.Telltale().Find(find)) printf("%s\n", n.c_str());
        return 0;
    }
    if (!dumpName.empty()) {
        int n = 0;
        for (auto& name : ab.Telltale().Find(dumpName)) {
            Bytes b;
            if (!ab.Telltale().Read(name, b)) continue;
            FILE* f = fopen((dumpDir + "\\" + name).c_str(), "wb");
            if (f) { fwrite(b.data(), 1, b.size(), f); fclose(f); ++n; }
        }
        printf("dumped %d files to %s\n", n, dumpDir.c_str());
        return 0;
    }

    printf("== Garry's Mod sounds\n");
    for (const char* s : {"sound/items/flashlight1.wav", "sound/weapons/pistol/pistol_fire2.wav",
                          "sound/weapons/physcannon/hold_loop.wav", "sound/npc/scanner/scanner_photo1.wav",
                          "sound/common/wpn_moveselect.wav"}) {
        Bytes b;
        WavInfo w;
        bool ok = ab.Source().Read(s, b) && ParseWav(b, w);
        char line[256];
        snprintf(line, sizeof line, "%s: %zu bytes, format %u, %u ch, %u Hz, %u bytes of samples", s, b.size(),
                 w.format, w.channels, w.sampleRate, w.dataSize);
        Check(ok && (w.format == 1 || w.format == 2), line);
    }
    {
        Bytes b;
        Check(ab.Source().Read("resource/HALFLIFE2.ttf", b) && b.size() > 1000, "HUD font resource/HALFLIFE2.ttf");
    }

    printf("== Source viewmodels (MDL/VVD/VTX/VTF)\n");
    for (auto& m : models) {
        SourceModel sm;
        std::string err;
        bool ok = LoadSourceModel(ab.Source(), m, "idle01", sm, &err);
        size_t tris = 0, verts = 0;
        for (auto& mesh : sm.meshes) { tris += mesh.indices.size() / 3; verts += mesh.vertices.size(); }
        int texOk = 0;
        for (auto& mat : sm.materials) {
            Bytes vmt, vtf;
            VtfImage img;
            if (mat.empty() || !ab.Source().Read(mat, vmt)) continue;
            std::string base = VmtBaseTexture(std::string(vmt.begin(), vmt.end()));
            if (!base.empty() && ab.Source().Read("materials/" + base + ".vtf", vtf) && ParseVtf(vtf, img)) ++texOk;
        }
        char line[512];
        snprintf(line, sizeof line,
                 "%s: %s; %zu meshes, %zu verts, %zu tris, %d/%zu textures, %zu sequences, pose: %s, "
                 "bind error %.2g, bounds (%.1f %.1f %.1f)-(%.1f %.1f %.1f)",
                 m.c_str(), ok ? "ok" : err.c_str(), sm.meshes.size(), verts, tris, texOk, sm.materials.size(),
                 sm.sequences.size(), sm.poseSource.c_str(), sm.worstBindError, sm.boundsMin.x, sm.boundsMin.y,
                 sm.boundsMin.z, sm.boundsMax.x, sm.boundsMax.y, sm.boundsMax.z);
        Check(ok && tris > 50 && texOk > 0 && sm.worstBindError < 1e-3f, line);
    }

    printf("== The Wolf Among Us catalog\n");
    TTCatalog& tt = ab.Telltale();
    Check(tt.ArchiveCount() == 48, "48 .ttarch2 archives opened");
    Check(tt.FileCount() > 90000, "over 90,000 unique file names (156,789 entries with repeats)");
    int quad = 0, withWalk = 0, withFace = 0;
    for (auto& c : tt.Characters()) {
        quad += c.plan == BodyPlan::Quadruped;
        withWalk += !c.walkClip.empty();
        withFace += !c.facePrefix.empty();
    }
    printf("  %zu characters, %d quadruped, %d with a walk clip, %d with a face rig; %zu scenes\n",
           tt.Characters().size(), quad, withWalk, withFace, tt.Scenes().size());
    const CharacterInfo* bigby = tt.FindBySkeleton("sk54_bigby");
    Check(bigby && bigby->walkClip == "sk54_bigby_walk.anm", "Bigby walks with sk54_bigby_walk.anm");
    Check(bigby && bigby->facePrefix == "bigby" && bigby->emotions.size() >= 5, "Bigby has a face rig and emotions");
    const CharacterInfo* colin = tt.FindBySkeleton("sk18_colin");
    Check(colin && colin->plan == BodyPlan::Quadruped && colin->walkClip == "sk18_colin_walk.anm",
          "Colin is a quadruped with sk18_colin_walk.anm");
    const CharacterInfo* were = tt.FindBySkeleton("sk54_bigbyWere");
    Check(were && were->runClip == "sk54_bigbyWere_runQuadruped.anm", "werewolf Bigby sprints on all fours");
    {
        Bytes b;
        Check(tt.Read("sk54_bigby_walk.anm", b) && b.size() > 100, "extract sk54_bigby_walk.anm from its archive");
        Check(tt.Read("adv_barTripTrap.scene", b) && b.size() > 100, "extract adv_barTripTrap.scene (ZCTT)");
        Check(tt.Read("module_light.prop", b) && b.size() > 10, "extract module_light.prop");
    }
    bool hasTripTrap = false;
    for (auto& s : tt.Scenes()) hasTripTrap |= s.scene == "adv_barTripTrap.scene" && s.episode == "Fables101";
    Check(hasTripTrap, "Trip Trap Bar listed under episode 1");
    if (chars)
        for (auto& c : tt.Characters())
            printf("  %-32s %-10s %-10s walk=%s run=%s idle=%s face=%s emotions=%zu\n", c.prop.c_str(),
                   PlanName(c.plan), c.episode.c_str(), c.walkClip.c_str(), c.runClip.c_str(), c.idleClip.c_str(),
                   c.facePrefix.c_str(), c.emotions.size());
    if (scenes)
        for (auto& s : tt.Scenes()) printf("  %-10s %-40s %s\n", s.episode.c_str(), s.scene.c_str(), s.display.c_str());
    printf("%s (%d failed)\n", g_fail ? "FAILED" : "ALL CHECKS PASSED", g_fail);
    return g_fail ? 1 : 0;
}
