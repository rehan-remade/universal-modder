// CombatAndRagdollPhysics: the GMod arsenal (physgun, toolgun, crowbar, pistol, SMG, shotgun, RPG, camera),
// hit points for every character in the scene, our own physics (Telltale Tool has no rigid-body engine),
// verlet ragdolls for the dead, and NPC locomotion that picks biped or quadruped clips from the catalog.
#include <algorithm>
#include <atomic>
#include <map>
#include <mutex>
#include <random>
#include <thread>
#include <unordered_map>

#include <MinHook.h>

#include "Sandbox.h"

namespace gm {

// ===================================================================== ragdoll
// Verlet particles + distance constraints. With the corpse's SkeletonInstance found in memory (FindSkeleton)
// there is one particle per bone and the result goes back into the bones: every frame each bone's local
// rotation (and the root's position) is recomputed from the particles and written into Telltale's Node
// (stride 0xd8: +0x1c local quat, +0x2c local pos, +0x3c/+0x4c global, +0x64 parent), both directly and from
// a hook on the engine's per-bone "apply animation" call so the mixer can't put the idle pose back. Without
// a skeleton (vtables moved in another build) it falls back to the old 7 particles that tilt the root.
namespace {
constexpr uint32_t kSkelInstVtable = 0x5f95a4;  // .?AVSkeletonInstance@@
constexpr uint32_t kNodeVtable = 0x5fb3e8;      // the bone nodes in SkeletonInstance+0x24
constexpr uint32_t kNodeSetLocal = 0x1e9520;    // Node::<apply animated local transform>(xf, w, w2, bool), thiscall
constexpr uint32_t kNodeInvalidate = 0x5d050;   // Node::<invalidate global>(), thiscall
constexpr uintptr_t kNodeSize = 0xd8;

Quat Conj(const Quat& q) { return {-q.x, -q.y, -q.z, q.w}; }

// Rotation taking the frame (u1, u2) onto (v1, v2): first vectors aligned exactly, second in the same plane.
Quat FrameRotation(const Vec3& u1, const Vec3& u2, const Vec3& v1, const Vec3& v2) {
    Vec3 a1 = Normalize(u1), a3 = Normalize(Cross(u1, u2)), a2 = Cross(a3, a1);
    Vec3 b1 = Normalize(v1), b3 = Normalize(Cross(v1, v2)), b2 = Cross(b3, b1);
    // M = sum b_k a_k^T, then matrix -> quaternion
    const Vec3* A[3] = {&a1, &a2, &a3};
    const Vec3* B[3] = {&b1, &b2, &b3};
    float m[3][3];
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j) {
            float s = 0;
            for (int k = 0; k < 3; ++k) s += (&B[k]->x)[i] * (&A[k]->x)[j];
            m[i][j] = s;
        }
    float tr = m[0][0] + m[1][1] + m[2][2];
    Quat q;
    if (tr > 0) {
        float s = std::sqrt(tr + 1.0f) * 2;
        q = {(m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, 0.25f * s};
    } else if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) {
        float s = std::sqrt(1.0f + m[0][0] - m[1][1] - m[2][2]) * 2;
        q = {0.25f * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s};
    } else if (m[1][1] > m[2][2]) {
        float s = std::sqrt(1.0f + m[1][1] - m[0][0] - m[2][2]) * 2;
        q = {(m[0][1] + m[1][0]) / s, 0.25f * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s};
    } else {
        float s = std::sqrt(1.0f + m[2][2] - m[0][0] - m[1][1]) * 2;
        q = {(m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25f * s, (m[1][0] - m[0][1]) / s};
    }
    return Normalize(q);
}

// Closest points between segments p1-q1 and p2-q2 (parameters s, t); returns the vector from the second
// to the first.
Vec3 SegmentGap(const Vec3& p1, const Vec3& q1, const Vec3& p2, const Vec3& q2, float& s, float& t) {
    Vec3 d1 = q1 - p1, d2 = q2 - p2, r = p1 - p2;
    float a = Dot(d1, d1), e = Dot(d2, d2), f = Dot(d2, r);
    if (a < 1e-9f && e < 1e-9f) { s = t = 0; return r; }
    if (a < 1e-9f) { s = 0; t = Clamp(f / e, 0, 1); }
    else {
        float c = Dot(d1, r);
        if (e < 1e-9f) { t = 0; s = Clamp(-c / a, 0, 1); }
        else {
            float b = Dot(d1, d2), den = a * e - b * b;
            s = den > 1e-9f ? Clamp((b * f - c * e) / den, 0, 1) : 0;
            t = (b * s + f) / e;
            if (t < 0) { t = 0; s = Clamp(-c / a, 0, 1); }
            else if (t > 1) { t = 1; s = Clamp((b - c) / a, 0, 1); }
        }
    }
    return (p1 + d1 * s) - (p2 + d2 * t);
}

// SkeletonInstances, from a heap scan that takes about a second: it runs on a thread when the sandbox opens
// and after each spawn, so a kill normally just picks from the list.
std::mutex g_skelMutex;
std::vector<uintptr_t> g_skelCache;
std::atomic<int> g_scanRequests{0};
std::atomic<bool> g_scanning{false};

void ScanSkeletonsAsync(DWORD delayMs) {
    ++g_scanRequests;
    if (g_scanning.exchange(true)) return;  // the running scan goes round again
    std::thread([delayMs] {
        int seen;
        do {
            seen = g_scanRequests;
            Sleep(delayMs);
            auto found = FindObjects(kSkelInstVtable, 512);
            std::lock_guard<std::mutex> lock(g_skelMutex);
            g_skelCache.swap(found);
        } while (seen != g_scanRequests);
        g_scanning = false;
    }).detach();
}

// The skeleton of the agent standing at pos: its root bones hang off the agent's own node, whose world
// position is the agent's. Several skeletons can share an agent (props); the biggest one is the body.
uintptr_t MatchSkeleton(const std::vector<uintptr_t>& objs, const Vec3& pos, const Axes& ax, int* outCount,
                        uintptr_t* outNodes) {
    uint32_t nodeVt = (uint32_t)(ExeBase() + kNodeVtable);
    uintptr_t best = 0;
    int bestCount = 0;
    for (uintptr_t o : objs) {
        uint32_t vt = 0, f[3];  // +0x1c count, +0x20 capacity, +0x24 nodes
        if (!SafeRead(o, &vt, 4) || vt != (uint32_t)(ExeBase() + kSkelInstVtable)) continue;
        if (!SafeRead(o + 0x1c, f, 12) || f[0] < 2 || f[0] > 512 || f[0] > f[1] || (int)f[0] <= bestCount) continue;
        uint32_t par = 0;
        float p[3];
        if (!SafeRead(f[2], &vt, 4) || vt != nodeVt || !SafeRead(f[2] + 0x64, &par, 4) || !par ||
            !SafeRead(par + 0x4c, p, 12))
            continue;
        if (Length(Vec3(p[0], p[1], p[2]) - pos) > 0.05f * ax.unitsPerMeter) continue;
        best = o;
        bestCount = (int)f[0];
        *outNodes = f[2];
    }
    *outCount = bestCount;
    return best;
}

uintptr_t FindSkeleton(const Vec3& pos, const Axes& ax, int* outCount, uintptr_t* outNodes) {
    std::vector<uintptr_t> cached;
    {
        std::lock_guard<std::mutex> lock(g_skelMutex);
        cached = g_skelCache;
    }
    uintptr_t r = MatchSkeleton(cached, pos, ax, outCount, outNodes);
    if (r) return r;
    auto found = FindObjects(kSkelInstVtable, 512);  // not in the list yet: scan now (a hitch)
    r = MatchSkeleton(found, pos, ax, outCount, outNodes);
    std::lock_guard<std::mutex> lock(g_skelMutex);
    g_skelCache.swap(found);
    return r;
}
}  // namespace

struct Ragdoll {
    struct P { Vec3 x, old; float invMass; };
    struct C { int a, b; float lo, hi; };  // keep |a-b| in [lo, hi]
    std::vector<P> p;
    std::vector<C> c;
    int head = 0, pelvis = 0;
    float pelvisHeight = 0;  // pelvis above the feet when standing
    Vec3 standAxis;          // the up axis when the body was standing
    Quat standRot;           // the agent's rotation when it died
    float restTimer = 0;
    float radius = 0;        // particles stay this far above the floor
    float stepClock = 0;     // fixed 120 Hz steps: verlet and the solver want a steady dt
    // The physgun's grip: particle `grab` is pulled to grabTarget every step and constraints don't move it.
    // As in GMod the gripped piece keeps its orientation (turning with the player's yaw): the bone and the two
    // that orient it are held, at grabOff from the grip; the rest of the body hangs off that piece.
    int grab = -1;
    Vec3 grabTarget;
    std::vector<int> grabSet;      // grab, frameA[grab], frameB[grab]
    std::vector<Vec3> grabOff;     // world offsets from the grip at the time of the grab (E turns them)
    std::vector<Vec3> grabTargets; // where each one goes this frame
    void Grip(int i) {
        grab = i;
        grabSet.clear();
        grabOff.clear();
        for (int k : {i, frameA[i], frameB[i]})
            if (k >= 0) { grabSet.push_back(k); grabOff.push_back(p[k].x - p[i].x); }
        grabTargets.assign(grabSet.size(), p[i].x);
    }
    void Release() { grab = -1; grabSet.clear(); }
    bool restorePose = false;  // a story character's: put its bones back when the ragdoll goes
    std::vector<float> mass;   // kg per particle (skeletal)
    std::vector<float> floorPush;  // scratch: how far the floor pushed each particle this step

    // per-bone mode
    bool skeletal = false;
    uintptr_t nodes = 0;
    int count = 0;
    Vec3 deathPos;  // the agent stays where it died; the bones move
    Quat deathRot;
    std::vector<int> parent, frameA, frameB;  // frameA/B: the children that orient a bone (-1: none)
    // Roots (parent outside the skeleton: the agent's node) also get their position written.
    bool Free(int i) const { return parent[i] < 0; }
    // Cones: bone b's direction to child a stays within acos(cosMax) of dir0 (its death direction), in the
    // frame of b's parent g. Hinges: joint p (between g and child i) bends towards bend0 (g's frame) only.
    struct Cone { int g, b, a; Vec3 dir0; float cosMax; };
    std::vector<Cone> cones;
    struct Hinge { int g, p, i; Vec3 bend0; };
    // Self-collision: capsules along the long bones (bone -> frameA) push apart, except pairs that already
    // touched at death (neighbours: thigh and pelvis, upper arm and chest).
    struct Seg { int a, b; float r; };
    std::vector<Seg> segs;
    std::vector<std::pair<int, int>> segPairs;
    std::vector<Hinge> hinges;
    std::vector<Quat> lastWorld;  // bone rotations from the last ApplyToEntity
    std::vector<Quat> deathQ, deathLocalQ, rootParentQ;
    std::vector<Vec3> deathP, rootParentP;
    std::vector<Quat> outQ;    // published local rotations (read by the hook)
    std::vector<Vec3> outPos;  // published local positions (roots only)

    ~Ragdoll();
    void Constrain(int a, int b) { float l = Length(p[a].x - p[b].x); c.push_back({a, b, l, l}); }

    void Build(const Entity& e, const Axes& ax, BodyPlan plan) {
        float upm = ax.unitsPerMeter, h = e.height * upm;
        Vec3 U = ax.up;
        Vec3 side = Normalize(Cross(U, std::fabs(U.x) < 0.9f ? Vec3(1, 0, 0) : Vec3(0, 0, 1)));
        side = e.rot.Rotate(side);
        Vec3 fwd = Normalize(Cross(side, U));
        auto add = [&](Vec3 at, float m) { p.push_back({at, at, 1.0f / m}); return (int)p.size() - 1; };
        Vec3 o = e.pos;
        standAxis = U;
        standRot = e.rot;
        if (plan == BodyPlan::Quadruped) {
            float len = h * 0.9f, hh = h * 0.45f;
            int hd = add(o + fwd * (len * 0.6f) + U * (hh * 1.1f), 4);
            int sh = add(o + fwd * (len * 0.35f) + U * hh, 10);
            int hp = add(o - fwd * (len * 0.35f) + U * hh, 10);
            int f1 = add(o + fwd * (len * 0.35f) + side * (hh * 0.3f), 3), f2 = add(o + fwd * (len * 0.35f) - side * (hh * 0.3f), 3);
            int b1 = add(o - fwd * (len * 0.35f) + side * (hh * 0.3f), 3), b2 = add(o - fwd * (len * 0.35f) - side * (hh * 0.3f), 3);
            for (int a : {sh, hp}) for (int b : {f1, f2, b1, b2}) Constrain(a, b);
            Constrain(hd, sh); Constrain(sh, hp); Constrain(hd, hp); Constrain(f1, f2); Constrain(b1, b2);
            head = hd; pelvis = hp;
            pelvisHeight = hh;
        } else {
            int hd = add(o + U * (h * 0.93f), 5);
            int ch = add(o + U * (h * 0.72f), 15);
            int pv = add(o + U * (h * 0.52f), 15);
            int lh = add(o + U * (h * 0.45f) + side * (h * 0.22f), 3), rh = add(o + U * (h * 0.45f) - side * (h * 0.22f), 3);
            int lf = add(o + side * (h * 0.08f), 5), rf = add(o - side * (h * 0.08f), 5);
            Constrain(hd, ch); Constrain(ch, pv); Constrain(hd, pv);
            Constrain(ch, lh); Constrain(ch, rh); Constrain(pv, lh); Constrain(pv, rh);
            Constrain(pv, lf); Constrain(pv, rf); Constrain(ch, lf); Constrain(ch, rf); Constrain(lf, rf);
            head = hd; pelvis = pv;
            pelvisHeight = h * 0.52f;
        }
    }

    // One particle per bone, starting from the pose the character is in right now.
    bool BuildSkeletal(const Entity& e, const Axes& ax, const Vec3& forward) {
        uintptr_t inst = FindSkeleton(e.pos, ax, &count, &nodes);
        if (!inst) return false;
        float upm = ax.unitsPerMeter;
        Vec3 U = ax.up;
        parent.assign(count, -1);
        deathQ.resize(count); deathLocalQ.resize(count); deathP.resize(count);
        rootParentQ.resize(count); rootParentP.resize(count);
        for (int i = 0; i < count; ++i) {
            uintptr_t n = nodes + i * kNodeSize;
            float lq[4], lp[3], gq[4], gp[3];
            uint32_t par = 0;
            if (!SafeRead(n + 0x1c, lq, 16) || !SafeRead(n + 0x2c, lp, 12) || !SafeRead(n + 0x3c, gq, 16) ||
                !SafeRead(n + 0x4c, gp, 12) || !SafeRead(n + 0x64, &par, 4))
                return false;
            deathLocalQ[i] = Normalize(Quat(lq[0], lq[1], lq[2], lq[3]));
            deathQ[i] = Normalize(Quat(gq[0], gq[1], gq[2], gq[3]));
            deathP[i] = Vec3(gp[0], gp[1], gp[2]);
            if (par >= nodes && par < nodes + count * kNodeSize && (par - nodes) % kNodeSize == 0)
                parent[i] = (int)((par - nodes) / kNodeSize);
            if (parent[i] >= i) return false;  // the order below relies on parents first
            if (parent[i] < 0) {  // the agent's own node, as it was at death
                rootParentQ[i] = Normalize(deathQ[i] * Conj(deathLocalQ[i]));
                rootParentP[i] = deathP[i] - rootParentQ[i].Rotate(Vec3(lp[0], lp[1], lp[2]));
            }
        }
        skeletal = true;
        deathPos = e.pos;
        deathRot = e.rot;
        standAxis = U;
        standRot = e.rot;
        radius = 0.045f * upm;
        p.clear();
        c.clear();
        for (int i = 0; i < count; ++i) p.push_back({deathP[i], deathP[i], 1.0f});
        std::vector<std::vector<int>> kids(count);
        for (int i = 0; i < count; ++i)
            if (parent[i] >= 0) kids[parent[i]].push_back(i);
        // Pieces: a bone with its children, plus the children of its short ones (the pelvis takes the hips
        // and the base of the spine, the chest the collarbones, the head the face). A piece is rigid; the
        // joints between pieces bend.
        const float shortLink = 0.1f * upm;
        std::vector<std::vector<int>> piece(count);
        for (int i = 0; i < count; ++i)
            for (int k : kids[i]) {
                piece[i].push_back(k);
                if (Length(deathP[k] - deathP[i]) < shortLink)
                    for (int kk : kids[k]) piece[i].push_back(kk);
            }
        // the members that orient each bone: the farthest one, and the one most off its line
        frameA.assign(count, -1);
        frameB.assign(count, -1);
        for (int i = 0; i < count; ++i) {
            float longest = 0.01f * upm;
            for (int k : piece[i]) {
                float l = Length(deathP[k] - deathP[i]);
                if (l > longest) { longest = l; frameA[i] = k; }
            }
            if (frameA[i] < 0) continue;
            Vec3 da = Normalize(deathP[frameA[i]] - deathP[i]);
            float off = 0.015f * upm;
            for (int k : piece[i]) {
                float s = Length(Cross(da, deathP[k] - deathP[i]));
                if (k != frameA[i] && s > off) { off = s; frameB[i] = k; }
            }
        }
        auto rigid = [&](int a, int b) { if (a >= 0 && b >= 0 && a != b) Constrain(a, b); };
        for (int i = 0; i < count; ++i) {
            if (parent[i] >= 0) rigid(parent[i], i);
            if (frameB[i] < 0) continue;
            rigid(frameA[i], frameB[i]);
            for (int k : piece[i]) { rigid(k, i); rigid(k, frameA[i]); rigid(k, frameB[i]); }
        }
        // pelvis: the root with the most children; head: the highest bone
        pelvis = 0;
        for (int i = 0; i < count; ++i)
            if (parent[i] < 0 && kids[i].size() > kids[pelvis].size()) pelvis = i;
        head = 0;
        for (int i = 0; i < count; ++i)
            if (Dot(deathP[i], U) > Dot(deathP[head], U)) head = i;
        pelvisHeight = Dot(deathP[pelvis], U) - e.groundY;
        // Joint limits for every bone but the root: its direction to frameA may swing this far from where it
        // pointed at death, measured in its parent's frame. Spine and neck (above the pelvis, close to its
        // vertical) bend a little at each joint, everything else a lot. Knees and elbows (two long bones)
        // also bend one way only: the way they were bent, else knees back and elbows forward.
        Vec3 pel = deathP[pelvis];
        for (int i = 0; i < count; ++i) {
            int a = frameA[i], pa = parent[i];
            if (a < 0 || pa < 0) continue;
            Vec3 off = deathP[i] - pel;
            float up = Dot(off, U);
            bool axial = up > 0 && Length(off - U * up) < 0.12f * upm;
            float deg = axial ? 30.0f : 100.0f;
            cones.push_back({pa, i, a, Normalize(deathP[a] - deathP[i]), std::cos(Deg2Rad(deg))});
            float l1 = Length(deathP[i] - deathP[pa]), l2 = Length(deathP[a] - deathP[i]);
            if (axial || l1 < 0.2f * upm || l2 < 0.2f * upm) continue;  // (frameA skips twist helpers)
            Vec3 axis = Normalize(deathP[i] - deathP[pa]), v = deathP[a] - deathP[i];
            Vec3 bend = v - axis * Dot(v, axis);
            if (Length(bend) < 0.05f * Length(v)) {  // straight at death
                bool knee = Dot(deathP[i], U) < Dot(pel, U);
                bend = forward * (knee ? -1.0f : 1.0f);
                bend = bend - axis * Dot(bend, axis);
            }
            if (Length(bend) > 1e-4f) hinges.push_back({pa, i, a, Conj(deathQ[pa]).Rotate(Normalize(bend))});
        }
        for (int i = 0; i < count; ++i) {
            int a = frameA[i];
            if (a < 0) continue;
            float len = Length(deathP[a] - deathP[i]);
            if (len < 0.08f * upm) continue;
            Vec3 off = deathP[i] - pel;
            float up = Dot(off, U);
            bool axial = up > -0.05f * upm && Length(off - U * up) < 0.12f * upm;
            segs.push_back({i, a, (axial ? 0.11f : len > 0.3f * upm ? 0.06f : 0.05f) * upm});
        }
        // Mass per bone, roughly a 75 kg body: the trunk is heavy, limb bones weigh by their length, and the
        // short ones (fingers, face, twist helpers) almost nothing. With equal masses the 15 finger bones made
        // a hand outweigh the chest and the face bones made the head a lead ball.
        mass.assign(count, 0.05f);
        for (int i = 0; i < count; ++i) {
            int a = frameA[i];
            float len = a < 0 ? 0 : Length(deathP[a] - deathP[i]) / upm;
            Vec3 off = deathP[i] - pel;
            float up = Dot(off, U);
            bool axial = up > -0.05f * upm && Length(off - U * up) < 0.12f * upm;
            if (len >= 0.06f) mass[i] = axial ? 5 + 20 * len : 12 * len;
        }
        mass[pelvis] = std::max(mass[pelvis], 10.0f);
        // A light bone between heavy ones (a twist helper in the arm) would let the limb stretch: at least 1 kg
        // for every bone with a heavy bone below it.
        for (int pass = 0; pass < 8; ++pass)
            for (int i = 0; i < count; ++i)
                if (parent[i] >= 0 && mass[i] >= 1.0f) mass[parent[i]] = std::max(mass[parent[i]], 1.0f);
        for (int i = 0; i < count; ++i) p[i].invMass = 1.0f / mass[i];
        for (size_t x = 0; x < segs.size(); ++x)
            for (size_t y = x + 1; y < segs.size(); ++y) {
                const Seg &s1 = segs[x], &s2 = segs[y];
                if (s1.a == s2.a || s1.a == s2.b || s1.b == s2.a || s1.b == s2.b) continue;
                float sa, sb;
                Vec3 d = SegmentGap(deathP[s1.a], deathP[s1.b], deathP[s2.a], deathP[s2.b], sa, sb);
                if (Length(d) > s1.r + s2.r) segPairs.push_back({(int)x, (int)y});
            }
        lastWorld = deathQ;
        outQ = deathLocalQ;
        outPos.assign(count, Vec3());
        for (int i = 0; i < count; ++i)
            if (Free(i)) outPos[i] = Conj(rootParentQ[i]).Rotate(deathP[i] - rootParentP[i]);
        return true;
    }

    static constexpr float kStep = 1.0f / 120.0f;  // Step() runs at a fixed 120 Hz

    void Impulse(const Vec3& at, const Vec3& dv, float /*dt*/) {
        int best = 0;
        float bd = 1e30f;
        for (size_t i = 0; i < p.size(); ++i) {
            float d = Length(p[i].x - at);
            if (d < bd) { bd = d; best = (int)i; }
        }
        float reach = 0.35f * GetWorld().axes.unitsPerMeter;
        if (skeletal && !mass.empty()) {
            // A hit is momentum (dv as if it hit 40 kg) given to the bones within reach, weighted by mass: a
            // shot to the chest knocks the trunk back and the arms lag and fly up, as in Source.
            std::vector<float> k(p.size(), 0.0f);
            float m = 0;
            for (size_t i = 0; i < p.size(); ++i) {
                k[i] = std::max(0.0f, 1.0f - Length(p[i].x - p[best].x) / reach);
                m += k[i] * mass[i];
            }
            if (m <= 0) return;
            Vec3 dvLocal = dv * (40.0f / m);
            for (size_t i = 0; i < p.size(); ++i)
                if (k[i] > 0) p[i].old -= dvLocal * (k[i] * kStep);  // verlet: velocity is (x - old) / step
        } else {
            for (size_t i = 0; i < p.size(); ++i) p[i].old -= dv * (((int)i == best ? 1.0f : 0.35f) * kStep);
        }
        restTimer = 0;
    }

    void Step(float dt, const Axes& ax, float groundY) {
        float grabMass[3] = {};
        for (size_t k = 0; k < grabSet.size(); ++k) std::swap(grabMass[k], p[grabSet[k]].invMass);
        Vec3 g = ax.up * (-9.8f * ax.unitsPerMeter * dt * dt);
        for (size_t i = 0; i < p.size(); ++i) {
            P& q = p[i];
            Vec3 v = (q.x - q.old) * (std::find(grabSet.begin(), grabSet.end(), (int)i) != grabSet.end() ? 0.5f : 0.998f);
            float vmax = 12.0f * ax.unitsPerMeter * dt, vl = Length(v);  // a hard physgun swing still lands nearby
            if (vl > vmax) v *= vmax / vl;
            q.old = q.x;
            q.x += v + g;
        }
        // The grip is a stiff spring, not a teleport: the gripped bone keeps a velocity, so the body swings.
        for (size_t k = 0; k < grabSet.size(); ++k) p[grabSet[k]].x += (grabTargets[k] - p[grabSet[k]].x) * 0.35f;
        floorPush.assign(p.size(), 0.0f);
        float floor = groundY + radius;
        for (int it = 0; it < (skeletal ? 12 : 10); ++it) {
            for (auto& k : c) {
                Vec3 d = p[k.b].x - p[k.a].x;
                float l = Length(d);
                if (l < 1e-6f) continue;
                float target = l < k.lo ? k.lo : (l > k.hi ? k.hi : l);
                if (target == l) continue;
                float w = p[k.a].invMass + p[k.b].invMass;
                if (w <= 0) continue;
                Vec3 corr = d * ((l - target) / (l * w));
                p[k.a].x += corr * p[k.a].invMass;
                p[k.b].x -= corr * p[k.b].invMass;
            }
            for (auto& k : cones) {  // joint limits
                Quat turn = lastWorld[k.g] * Conj(deathQ[k.g]);
                Vec3 ref = turn.Rotate(k.dir0), cur = p[k.a].x - p[k.b].x;
                float len = Length(cur);
                if (len < 1e-5f) continue;
                Vec3 d = cur * (1.0f / len);
                float cs = Dot(d, ref);
                if (cs >= k.cosMax) continue;
                Vec3 side = Normalize(d - ref * cs);
                if (Length(side) < 0.5f) continue;
                Vec3 lim = ref * k.cosMax + side * std::sqrt(std::max(0.0f, 1 - k.cosMax * k.cosMax));
                Vec3 delta = p[k.b].x + lim * len - p[k.a].x;
                float wa = p[k.a].invMass, wb = p[k.b].invMass;  // shared: one-sided pushes would propel the body
                if (wa + wb <= 0) continue;
                p[k.a].x += delta * (wa / (wa + wb));
                p[k.b].x -= delta * (wb / (wa + wb));
            }
            for (auto& pr : segPairs) {  // limbs don't pass through each other or the body
                const Seg &s1 = segs[pr.first], &s2 = segs[pr.second];
                float sa, sb;
                Vec3 d = SegmentGap(p[s1.a].x, p[s1.b].x, p[s2.a].x, p[s2.b].x, sa, sb);
                float l = Length(d), pen = s1.r + s2.r - l;
                if (pen <= 0 || l < 1e-6f) continue;
                Vec3 n = d * (pen * 0.5f / l);
                p[s1.a].x += n * ((1 - sa) * p[s1.a].invMass);
                p[s1.b].x += n * (sa * p[s1.b].invMass);
                p[s2.a].x -= n * ((1 - sb) * p[s2.a].invMass);
                p[s2.b].x -= n * (sb * p[s2.b].invMass);
            }
            for (auto& h : hinges) {  // no bending backwards
                Vec3 axis = Normalize(p[h.p].x - p[h.g].x);
                Vec3 bd = lastWorld[h.g].Rotate(h.bend0);
                bd = Normalize(bd - axis * Dot(bd, axis));
                float side = Dot(p[h.i].x - p[h.p].x, bd);
                float wi = p[h.i].invMass, wp = p[h.p].invMass;
                if (side < 0 && wi + wp > 0) {
                    p[h.i].x -= bd * (side * wi / (wi + wp));
                    p[h.p].x += bd * (side * wp / (wi + wp));
                }
            }
            for (size_t i = 0; i < p.size(); ++i) {  // floor
                float h = Dot(p[i].x, ax.up) - floor;
                if (h < 0) {
                    p[i].x -= ax.up * h;
                    floorPush[i] -= h;
                }
            }
        }
        // Coulomb friction, once per step: the floor takes away at most mu times how hard it pushed, so a body
        // slides and rolls instead of sticking where it touches (it was applied every iteration: glue).
        for (size_t i = 0; i < p.size(); ++i) {
            if (floorPush[i] <= 0) continue;
            Vec3 v = p[i].x - p[i].old;
            float vn = Dot(v, ax.up);
            Vec3 tang = v - ax.up * vn;
            float tl = Length(tang), cut = std::min(tl, 0.5f * floorPush[i]);
            Vec3 keep = tl > 1e-9f ? tang * (1 - cut / tl) : Vec3();
            p[i].old = p[i].x - keep - ax.up * std::max(vn, 0.0f);
        }
        for (size_t k = 0; k < grabSet.size(); ++k) p[grabSet[k]].invMass = grabMass[k];
        float motion = 0;
        for (auto& q : p) motion = std::max(motion, Length(q.x - q.old));
        restTimer = motion < 0.0005f * ax.unitsPerMeter ? restTimer + dt : 0;
    }

    void ApplyToEntity(Entity& e);
};

namespace {
// Bodies whose bones we drive; the hook reads them on whatever thread animates.
SRWLOCK g_boneLock = SRWLOCK_INIT;
std::vector<Ragdoll*> g_boneRags;
// Finger poser: a rotation added to a bone's local transform after the mixer. `base` is the mixer's own
// value: if a frame leaves the bone untouched (it still holds what we wrote), the offset goes on base again
// instead of piling up.
struct BoneOffset { Quat off, base, written; bool has = false; };
std::unordered_map<uintptr_t, BoneOffset> g_fingerOffsets;
using SetLocalFn = void(__fastcall*)(void* self, void* edx, const void* xf, float w, float w2, int flag);
SetLocalFn g_origSetLocal = nullptr;
using InvalidateFn = void(__fastcall*)(void* self, void* edx);

void WriteBone(const Ragdoll& r, uintptr_t node, int i) {
    memcpy((void*)(node + 0x1c), &r.outQ[i], 16);
    if (r.Free(i)) memcpy((void*)(node + 0x2c), &r.outPos[i], 12);
}

void __fastcall HookSetLocal(void* self, void* edx, const void* xf, float w, float w2, int flag) {
    g_origSetLocal(self, edx, xf, w, w2, flag);
    uintptr_t a = (uintptr_t)self;
    AcquireSRWLockShared(&g_boneLock);
    bool rag = false;
    for (Ragdoll* r : g_boneRags)
        if (a >= r->nodes && a < r->nodes + r->count * kNodeSize && (a - r->nodes) % kNodeSize == 0) {
            WriteBone(*r, a, (int)((a - r->nodes) / kNodeSize));
            rag = true;
            break;
        }
    ReleaseSRWLockShared(&g_boneLock);
    if (!rag && !g_fingerOffsets.empty()) {
        AcquireSRWLockExclusive(&g_boneLock);
        auto it = g_fingerOffsets.find(a);
        if (it != g_fingerOffsets.end()) {
            BoneOffset& o = it->second;
            Quat cur;
            memcpy(&cur, (void*)(a + 0x1c), 16);
            if (!o.has || memcmp(&cur, &o.written, 16) != 0) o.base = cur;
            o.has = true;
            o.written = Normalize(o.base * o.off);
            memcpy((void*)(a + 0x1c), &o.written, 16);
        }
        ReleaseSRWLockExclusive(&g_boneLock);
    }
}

bool EnsureBoneHook() {
    static int state = 0;  // 0 untried, 1 ok, -1 failed
    if (state) return state > 0;
    void* target = (void*)(ExeBase() + kNodeSetLocal);
    unsigned char head[3] = {};
    // push ebp; mov ebp, esp: the function this build was mapped from
    bool ok = SafeRead((uintptr_t)target, head, 3) && head[0] == 0x55 && head[1] == 0x8b && head[2] == 0xec &&
              MH_CreateHook(target, (void*)&HookSetLocal, (void**)&g_origSetLocal) == MH_OK &&
              MH_EnableHook(target) == MH_OK;
    state = ok ? 1 : -1;
    Log("[ragdoll] bone hook %s", ok ? "installed" : "FAILED (per-bone ragdolls off)");
    return ok;
}

void RegisterBones(Ragdoll* r) {
    AcquireSRWLockExclusive(&g_boneLock);
    g_boneRags.push_back(r);
    ReleaseSRWLockExclusive(&g_boneLock);
}
}  // namespace

// ===================================================================== finger poser
// The bone nodes carry no names we can read, so hands are found by shape: a bone with four to six children
// that each continue as a chain 2.5-20 cm long (the fingers), in a mirrored pair. The thumb is the chain
// pointing most away from the others; index to pinky follow from the thumb's side. A finger curls about the
// axis it already bends around in the current pose (towards the palm), and the hook adds that rotation to
// each joint after the animation mixer, so the pose holds while the character idles.
struct FingerRig {
    struct Finger { std::vector<uintptr_t> joints; std::vector<Vec3> axes; float maxDeg = 70; };
    std::vector<Finger> fingers;
    ~FingerRig() {
        AcquireSRWLockExclusive(&g_boneLock);
        for (auto& f : fingers)
            for (auto n : f.joints) g_fingerOffsets.erase(n);
        ReleaseSRWLockExclusive(&g_boneLock);
    }
};


Ragdoll::~Ragdoll() {
    AcquireSRWLockExclusive(&g_boneLock);
    g_boneRags.erase(std::remove(g_boneRags.begin(), g_boneRags.end(), this), g_boneRags.end());
    ReleaseSRWLockExclusive(&g_boneLock);
    // A story character revived on F3: give the bones back the pose it died in, for any the story's own
    // animation doesn't drive. (Spawned agents are gone by now, and so is their skeleton.)
    uint32_t vt = 0;
    if (!skeletal || !restorePose || !SafeRead(nodes, &vt, 4) || vt != (uint32_t)(ExeBase() + kNodeVtable)) return;
    auto invalidate = (InvalidateFn)(ExeBase() + kNodeInvalidate);
    for (int i = 0; i < count; ++i) {
        uintptr_t n = nodes + i * kNodeSize;
        SafeWrite(n + 0x1c, &deathLocalQ[i], 16);
        if (Free(i)) {
            Vec3 lp = Conj(rootParentQ[i]).Rotate(deathP[i] - rootParentP[i]);
            SafeWrite(n + 0x2c, &lp, 12);
        }
        invalidate((void*)n, nullptr);
    }
}

void Ragdoll::ApplyToEntity(Entity& e) {
    if (!skeletal) {  // root transform: keep the simulated pelvis where the model's is, tilted along pelvis->head
        Vec3 axis = Normalize(p[head].x - p[pelvis].x);
        Quat tilt = FromTo(standAxis, axis);
        e.rot = Normalize(tilt * standRot);
        e.pos = p[pelvis].x - axis * pelvisHeight;
        e.dirty = true;
        return;
    }
    // Bones, parents first: each one turned by how its children moved since death, then made local.
    std::vector<Quat> world(count), q(count);
    std::vector<Vec3> pos(count);
    for (int i = 0; i < count; ++i) {
        Quat pw = parent[i] < 0 ? rootParentQ[i] : world[parent[i]];
        int a = frameA[i], b = frameB[i];
        if (a < 0)
            world[i] = Normalize(pw * deathLocalQ[i]);
        else if (b < 0) {  // carried by the parent (so it twists with it), then swung onto its child
            Quat carry = Normalize(pw * Conj(parent[i] < 0 ? rootParentQ[i] : deathQ[parent[i]]));
            Vec3 d0 = carry.Rotate(Normalize(deathP[a] - deathP[i]));
            world[i] = Normalize(FromTo(d0, Normalize(p[a].x - p[i].x)) * carry * deathQ[i]);
        }
        else
            world[i] = Normalize(FrameRotation(deathP[a] - deathP[i], deathP[b] - deathP[i], p[a].x - p[i].x,
                                               p[b].x - p[i].x) * deathQ[i]);
        q[i] = Normalize(Conj(pw) * world[i]);
        if (Free(i)) pos[i] = Conj(rootParentQ[i]).Rotate(p[i].x - rootParentP[i]);
    }
    uint32_t nodeVt = (uint32_t)(ExeBase() + kNodeVtable), vt = 0;
    if (!SafeRead(nodes, &vt, 4) || vt != nodeVt) {  // the skeleton went away under us
        AcquireSRWLockExclusive(&g_boneLock);
        g_boneRags.erase(std::remove(g_boneRags.begin(), g_boneRags.end(), this), g_boneRags.end());
        ReleaseSRWLockExclusive(&g_boneLock);
        Log("[ragdoll] %s: skeleton gone", e.name.c_str());
        skeletal = false;
        return;
    }
    lastWorld = world;
    AcquireSRWLockExclusive(&g_boneLock);
    outQ.swap(q);
    outPos.swap(pos);
    // Directly too, for when nothing animates the body; then the engine recomputes the globals.
    for (int i = 0; i < count; ++i) WriteBone(*this, nodes + i * kNodeSize, i);
    ReleaseSRWLockExclusive(&g_boneLock);
    auto invalidate = (InvalidateFn)(ExeBase() + kNodeInvalidate);
    for (int i = 0; i < count; ++i) invalidate((void*)(nodes + i * kNodeSize), nullptr);
    // the agent itself stays put (the physgun and explosions move the particles instead)
    if (Length(e.pos - deathPos) > 0 || e.rot.x != deathRot.x || e.rot.y != deathRot.y || e.rot.w != deathRot.w) {
        e.pos = deathPos;
        e.rot = deathRot;
        e.dirty = true;
    }
}

void RagdollDeleter::operator()(Ragdoll* r) const { delete r; }

namespace combat {
namespace {

// ===================================================================== weapons
struct WeaponDef {
    const char* name;
    int slot;  // 1..6
    const char* viewmodel;
    const char* fireSound;
    int clipMax, reserve;
    float interval, damage, spread, range;
    int pellets;
    bool automatic;
};
const WeaponDef kWeapons[(int)Weapon::Count] = {
    {"Physics Gun", 1, "models/weapons/v_physcannon.mdl", nullptr, -1, -1, 0, 0, 0, 60, 0, true},
    {"Tool Gun", 2, "models/weapons/v_toolgun.mdl", "sound/weapons/airboat/airboat_gun_lastshot1.wav", -1, -1, 0.3f, 0, 0, 60, 0, false},
    {"Crowbar", 3, "models/weapons/v_crowbar.mdl", "sound/weapons/iceaxe/iceaxe_swing1.wav", -1, -1, 0.4f, 25, 0, 1.3f, 1, true},
    {"9mm Pistol", 4, "models/weapons/v_pistol.mdl", "sound/weapons/pistol/pistol_fire2.wav", 18, 150, 0.12f, 12, 0.01f, 80, 1, false},
    {"SMG", 4, "models/weapons/v_smg1.mdl", "sound/weapons/smg1/smg1_fire1.wav", 45, 225, 0.075f, 8, 0.035f, 80, 1, true},
    {"Shotgun", 5, "models/weapons/v_shotgun.mdl", "sound/weapons/shotgun/shotgun_fire6.wav", 6, 30, 0.8f, 8, 0.08f, 40, 7, false},
    {"RPG", 5, "models/weapons/v_rpg.mdl", "sound/weapons/rpg/rocketfire1.wav", 1, 3, 2.0f, 150, 0, 200, 0, false},
    {"Camera", 6, "models/maxofs2d/camera.mdl", "sound/npc/scanner/scanner_photo1.wav", -1, -1, 0.5f, 0, 0, 0, 0, false},
};
const char* kToolNames[(int)ToolMode::Count] = {"Remover", "Face Poser", "Animator", "Physics Properties", "Weld"};

std::mt19937 g_rng(1234);
float Rand(float a, float b) { return std::uniform_real_distribution<float>(a, b)(g_rng); }

// physgun
Entity* g_held = nullptr;
float g_holdDist = 0;
Vec3 g_gripForward;  // the aim when a ragdoll was gripped: its piece turns with the yaw since
int g_physLoop = 0;
Vec3 g_lastHeldPos;
// toolgun
Entity* g_weldFirst = nullptr;
struct Weld { std::string child, parent; Vec3 offset; };
std::vector<Weld> g_welds;
size_t g_animIndex = 0;
std::string g_toolInfo;
// rockets
struct Rocket { Vec3 pos, vel; float life; bool walls; };  // walls: fired from the walk boxes (not noclip)
std::vector<Rocket> g_rockets;
// camera
bool g_cameraZoom = false;
bool g_screenshotPending = false;
// local forward of character agents (read back after the first spawn)
bool g_charForwardKnown = false;
Vec3 g_charLocalForward{0, 0, 1};

float Upm() { return GetWorld().axes.unitsPerMeter; }

bool Hittable(const Entity& e) {
    if (e.isPlayerBody || !e.visible || e.name == "gm_fpcam" || e.name == "gm_flashlight" ||
        e.name == GetWorld().player.playerModelAgent)
        return false;
    if (!e.hasMesh) return false;
    if (e.character || e.spawned) return true;
    std::string l = ToLower(e.name);
    return l.rfind("obj_", 0) == 0;
}

// Ray against a vertical capsule (feet at e.pos).
bool RayCapsule(const Vec3& o, const Vec3& d, const Entity& e, float maxDist, float& tHit) {
    const Axes& ax = GetWorld().axes;
    float upm = ax.unitsPerMeter;
    float h = (e.character ? e.height : 0.6f) * upm, r = (e.character ? e.radius : 0.35f) * upm;
    Vec3 a = e.pos, b = e.pos + ax.up * h;
    if (e.phys == Phys::Ragdoll && e.ragdoll) {
        a = e.ragdoll->p[e.ragdoll->pelvis].x;
        b = e.ragdoll->p[e.ragdoll->head].x;
    }
    Vec3 s = b - a;
    float ss = Dot(s, s), sd = Dot(s, d), w0d = Dot(o - a, d), w0s = Dot(o - a, s);
    float den = ss - sd * sd;
    float t = 0, u = 0;
    if (den > 1e-8f) {
        t = (sd * w0s - ss * w0d) / den;
        u = Clamp((w0s + t * sd) / ss, 0, 1);
    }
    Vec3 q = a + s * u;
    t = Dot(q - o, d);
    if (t < 0 || t > maxDist) return false;
    if (Length(o + d * t - q) > r) return false;
    tHit = t;
    return true;
}

void Damage(lua::State* L, Entity* e, float dmg, const Vec3& dir, const Vec3& at) {
    World& w = GetWorld();
    w.lastHitTime = w.time;
    if (e->dead) {
        if (e->ragdoll) e->ragdoll->Impulse(at, dir * (dmg * 0.08f * Upm()), w.dt > 0 ? w.dt : 0.016f);
        return;
    }
    e->hp -= dmg;
    if (e->hp <= 0) Kill(L, e, dir * (dmg * 0.08f * Upm()));
}

// ===================================================================== walls
// The engine has no raycast against level geometry (AgentAtScreenPos only picks selectable agents), so the
// player's walk boxes stand in for the floor plan: off them is a wall, a counter or a car.

// Nearest point on the walk boxes at p's height; p itself when there are none.
Vec3 SnapToWalkBoxes(lua::State* L, const Vec3& p) {
    auto s = lua::Call(L, "GM.Snap", {p.x, p.y, p.z}, 3);
    if (!s.ok || s.type.empty() || s.type[0] != lua::TNUMBER) return p;
    const Vec3& U = GetWorld().axes.up;
    Vec3 q(s.N(0), s.N(1), s.N(2));
    return q - U * Dot(q, U) + U * Dot(p, U);
}

// How far p is (horizontally) outside the walk boxes; 0 on them or when there are none.
float OffWalkBoxes(lua::State* L, const Vec3& p) {
    const Vec3& U = GetWorld().axes.up;
    Vec3 off = p - SnapToWalkBoxes(L, p);
    return Length(off - U * Dot(off, U));
}

float FloorHeight() {
    World& w = GetWorld();
    for (auto& e : w.ents)
        if (e->isPlayerBody) return Dot(e->origPos, w.axes.up);
    return Dot(w.player.pos, w.axes.up);
}

// Distance along the ray to the first wall or the floor; maxDist when it stays clear (or the shot starts off
// the walk boxes, as in noclip).
float WallDistance(lua::State* L, const Vec3& o, const Vec3& d, float maxDist) {
    float upm = Upm();
    auto r = lua::Call(L, "GM.WallDistance", {o.x, o.y, o.z, d.x, d.y, d.z, maxDist, FloorHeight(), 0.2f * upm, 0.3f * upm}, 1);
    return r.ok ? std::min(maxDist, r.N(0, maxDist)) : maxDist;
}

// Trace() stopped by walls; on a miss *outDist is where the ray ends (wall, floor or maxDist).
Entity* TraceWorld(lua::State* L, const Vec3& from, const Vec3& dir, float maxDist, float* outDist) {
    float dist = 0;
    Entity* e = Trace(from, dir, maxDist, &dist);
    float wall = WallDistance(L, from, dir, e ? dist : maxDist);
    // Someone standing a little off the walk boxes (behind a counter, in a doorway) still gets hit.
    if (e && wall < dist - 0.6f * Upm()) e = nullptr;
    *outDist = e ? dist : wall;
    return e;
}

void FireBullets(lua::State* L, const WeaponDef& wd) {
    World& w = GetWorld();
    Player& p = w.player;
    for (int i = 0; i < wd.pellets; ++i) {
        Vec3 dir = Normalize(p.forward + p.right * Rand(-wd.spread, wd.spread) + p.up * Rand(-wd.spread, wd.spread));
        float dist = 0;
        Entity* e = TraceWorld(L, p.eye, dir, wd.range * Upm(), &dist);
        Vec3 end = p.eye + dir * dist;
        w.tracers.push_back({p.eye + p.right * (0.12f * Upm()) - p.up * (0.1f * Upm()), end, w.time});
        if (e) Damage(L, e, wd.damage, dir, end);
    }
}

void Explode(lua::State* L, const Vec3& at) {
    World& w = GetWorld();
    w.blasts.push_back({at, w.time});
    audio::Play("sound/weapons/explode3.wav");
    float radius = 4.0f * Upm();
    for (auto& e : w.ents) {
        if (!Hittable(*e)) continue;
        Vec3 c = e->pos + w.axes.up * (0.9f * Upm());
        float d = Length(c - at);
        if (d > radius) continue;
        float wall = WallDistance(L, at, Normalize(c - at), d);
        if (wall < d - 0.6f * Upm()) {  // behind a wall
            Log("[blast] %s at %.2f m shielded by a wall at %.2f m", e->name.c_str(), d / Upm(), wall / Upm());
            continue;
        }
        float k = 1.0f - d / radius;
        Vec3 dir = Normalize(c - at + w.axes.up * (0.5f * Upm()));
        Damage(L, e.get(), 150 * k, dir * 0.7f, c);  // up to ~9 m/s (was 36: corpses flew 40 m)
    }
}

// ===================================================================== physgun
void Physgun(lua::State* L) {
    World& w = GetWorld();
    Player& p = w.player;
    InputFrame& in = w.input;
    if (in.down[VK_LBUTTON]) {
        if (!g_held) {
            float dist = 0;
            Entity* e = TraceWorld(L, p.eye, p.forward, 60 * Upm(), &dist);
            if (e) {
                g_held = e;
                g_holdDist = dist;
                if (e->dead && e->ragdoll && e->ragdoll->skeletal) {  // grip the bone under the crosshair
                    Ragdoll& r = *e->ragdoll;
                    int best = r.pelvis;
                    float bd = 1e30f;
                    for (int i = 0; i < r.count; ++i) {
                        if (r.mass[i] < 0.5f) continue;  // not a finger or a face bone: the body would hang off it
                        Vec3 rel = r.p[i].x - p.eye;
                        float t = Dot(rel, p.forward);
                        if (t <= 0) continue;
                        float d = Length(rel - p.forward * t);
                        if (d < bd) { bd = d; best = i; }
                    }
                    r.Grip(best);
                    g_gripForward = p.forward;
                    g_holdDist = Dot(r.p[best].x - p.eye, p.forward);
                }
                Log("[physgun] holding %s%s (bone %d of piece %d, pelvis %d)", e->name.c_str(), e->dead ? " (dead)" : "",
                    e->ragdoll ? e->ragdoll->grab : -1, e->ragdoll ? (int)e->ragdoll->grabSet.size() : 0,
                    e->ragdoll ? e->ragdoll->pelvis : -1);
                e->phys = Phys::Held;
                g_lastHeldPos = e->pos;
                g_physLoop = audio::PlayLoop("sound/weapons/physcannon/hold_loop.wav", 0.5f);
            }
        }
    } else if (g_held) {  // release: throw with the beam's velocity
        if (g_held->phys == Phys::Held) {
            g_held->phys = g_held->dead ? Phys::Ragdoll : Phys::Rigid;
            g_held->vel = (g_held->pos - g_lastHeldPos) * (1.0f / std::max(w.dt, 0.001f));
        }
        if (g_held->ragdoll && g_held->ragdoll->skeletal) {  // the bones already carry the swing
            g_held->ragdoll->Release();
            g_held->vel = Vec3();
        }
        g_held = nullptr;
        audio::Stop(g_physLoop);
        audio::Play("sound/weapons/physgun_off.wav", 0.6f);
    }
    if (!g_held) return;
    Entity& e = *g_held;
    if (in.pressed[VK_RBUTTON]) {  // freeze in place, GMod style
        if (e.ragdoll) e.ragdoll->Release();
        e.phys = Phys::Frozen;
        e.vel = Vec3();
        g_held = nullptr;
        audio::Stop(g_physLoop);
        hud::Notify("Frozen");
        return;
    }
    g_holdDist = std::max(0.8f * Upm(), g_holdDist + in.wheel * 0.5f * Upm());
    if (in.down['E']) {  // rotate with the mouse instead of looking around
        Quat qy = Quat::AxisAngle(w.axes.up, Deg2Rad(in.mouseDx * 0.4f));
        Quat qx = Quat::AxisAngle(p.right, Deg2Rad(in.mouseDy * 0.4f));
        e.rot = Normalize(qx * qy * e.rot);
    }
    g_lastHeldPos = e.pos;
    if (e.dead && e.ragdoll && e.ragdoll->skeletal) {  // the gripped bone follows the beam; the rest hangs and swings
        Ragdoll& r = *e.ragdoll;
        r.grabTarget = p.eye + p.forward * g_holdDist;
        if (in.down['E'])  // E: turn the gripped piece with the mouse
            for (auto& o : r.grabOff)
                o = Quat::AxisAngle(p.right, Deg2Rad(in.mouseDy * 0.4f)).Rotate(Quat::AxisAngle(w.axes.up, Deg2Rad(in.mouseDx * 0.4f)).Rotate(o));
        // the piece turns with the player's yaw since the grab
        Vec3 U = w.axes.up, f0 = g_gripForward - U * Dot(g_gripForward, U), f1 = p.forward - U * Dot(p.forward, U);
        Quat yaw = Length(f0) > 1e-3f && Length(f1) > 1e-3f ? FromTo(Normalize(f0), Normalize(f1)) : Quat();
        for (size_t k = 0; k < r.grabSet.size(); ++k) r.grabTargets[k] = r.grabTarget + yaw.Rotate(r.grabOff[k]);
        static float logClock = 0;
        if ((logClock += w.dt) > 0.5f) {  // how it hangs, for tuning
            logClock = 0;
            float upm = w.axes.unitsPerMeter, gy = Dot(r.p[r.grab].x, U), lo = 1e30f;
            for (auto& q : r.p) lo = std::min(lo, Dot(q.x, U));
            Log("[physgun] grip %.2f m off; head %+.2f m, lowest %+.2f m from the grip",
                Length(r.p[r.grab].x - r.grabTarget) / upm, (Dot(r.p[r.head].x, U) - gy) / upm, (lo - gy) / upm);
        }
        r.restTimer = 0;
        e.dirty = true;
        return;
    }
    Vec3 target = p.eye + p.forward * g_holdDist - w.axes.up * ((e.character ? e.height * 0.5f : 0.3f) * Upm());
    e.pos += (target - e.pos) * std::min(1.0f, w.dt * 15.0f);
    if (e.dead && e.ragdoll) {  // the 7-particle body: drag it along
        Ragdoll& r = *e.ragdoll;
        Vec3 d = target + w.axes.up * (r.pelvisHeight) - r.p[r.pelvis].x;
        for (auto& q : r.p) { q.x += d * 0.5f; q.old += d * 0.5f; }
    }
    e.dirty = true;
}

// ===================================================================== toolgun
Entity* AimEntity(float range = 60) {
    World& w = GetWorld();
    float d = 0;
    return Trace(w.player.eye, w.player.forward, range * Upm(), &d);
}

void Toolgun(lua::State* L) {
    World& w = GetWorld();
    InputFrame& in = w.input;
    Player& p = w.player;
    if (in.pressed['R']) {  // R cycles the tool mode, like the GMod tool menu's quick switch
        p.tool = (ToolMode)(((int)p.tool + 1) % (int)ToolMode::Count);
        hud::Notify(std::string("Tool: ") + kToolNames[(int)p.tool]);
    }
    bool lmb = in.pressed[VK_LBUTTON], rmb = in.pressed[VK_RBUTTON];
    if (!lmb && !rmb) return;
    float d = 0;
    Entity* e = TraceWorld(L, p.eye, p.forward, 60 * Upm(), &d);  // d = wall or max range on a miss
    audio::Play(kWeapons[(int)Weapon::ToolGun].fireSound, 0.5f);
    Vec3 end = p.eye + p.forward * d;
    w.tracers.push_back({p.eye + p.right * (0.12f * Upm()) - p.up * (0.1f * Upm()), end, w.time});
    if (!e) return;
    switch (p.tool) {
        case ToolMode::Remover:
            if (e->spawned) {
                lua::Call(L, "GM.Destroy", {e->name});
                w.Remove(e);
            } else {  // story agents come back at F3
                lua::Call(L, "GM.Show", {e->name, false});
                e->visible = false;
            }
            break;
        case ToolMode::FacePoser:
            if (e->info && !e->info->facePrefix.empty()) {
                w.facePoserTarget = e;
                e->faceWeights.assign(AssetBridge::Get().Telltale().FaceChannels(e->info->facePrefix).size(), 0.0f);
                hud::Notify("Face Poser: " + e->name + " (hold C for the sliders)");
            } else {
                hud::Notify("No face rig on " + e->name);
            }
            break;
        case ToolMode::Animator: {
            if (e->skeleton.empty()) break;
            auto clips = AssetBridge::Get().Telltale().ClipsFor(e->skeleton);
            if (clips.empty()) break;
            g_animIndex = (g_animIndex + (rmb ? clips.size() - 1 : 1)) % clips.size();
            if (e->clipHandle >= 0) lua::Call(L, "GM.StopClip", {e->clipHandle});
            e->clipHandle = (int)lua::Call(L, "GM.PlayClip", {e->name, clips[g_animIndex], true, 1.0f, 50}, 1).N(0, -1);
            e->clipName = clips[g_animIndex];
            e->ai = Entity::Ai::None;
            g_toolInfo = e->clipName;
            hud::Notify(e->name + ": " + e->clipName);
            break;
        }
        case ToolMode::Physics:
            if (lmb) {
                e->gravity = !e->gravity;
                e->phys = Phys::Rigid;
                hud::Notify(e->name + (e->gravity ? ": gravity on" : ": gravity off"));
            } else {
                e->phys = e->dead ? Phys::Ragdoll : Phys::Rigid;
                e->vel += w.axes.up * (6 * Upm());
                if (e->ragdoll) e->ragdoll->Impulse(e->pos, w.axes.up * (6 * Upm()), w.dt);
            }
            break;
        case ToolMode::Weld:
            if (!g_weldFirst) {
                g_weldFirst = e;
                hud::Notify("Weld: now the second object");
            } else if (g_weldFirst != e) {
                g_welds.push_back({g_weldFirst->name, e->name, g_weldFirst->pos - e->pos});
                hud::Notify("Welded " + g_weldFirst->name + " to " + e->name);
                g_weldFirst = nullptr;
            }
            break;
        default: break;
    }
}

// ===================================================================== physics bodies
void Physics(lua::State* L) {
    World& w = GetWorld();
    float dt = w.dt, upm = Upm();
    Vec3 U = w.axes.up;
    for (auto& ep : w.ents) {
        Entity& e = *ep;
        if (e.phys == Phys::Rigid) {
            if (e.gravity) e.vel -= U * (9.8f * upm * dt);
            Vec3 prev = e.pos;
            e.pos += e.vel * dt;
            // Walls: bounce off the walk boxes' edge, but only for a body that was on them (a physgun drop
            // over a counter falls where it was let go).
            Vec3 move = e.pos - prev;
            if (Length(move - U * Dot(move, U)) > 1e-4f * upm) {
                Vec3 s = SnapToWalkBoxes(L, e.pos), off = e.pos - s;
                off -= U * Dot(off, U);
                Vec3 was = prev - SnapToWalkBoxes(L, prev);
                was -= U * Dot(was, U);
                if (Length(off) > 0.05f * upm && Length(was) < 0.05f * upm) {
                    e.pos -= off;
                    Vec3 n = Normalize(off);
                    e.vel -= n * (Dot(e.vel, n) * 1.5f);
                }
            }
            float h = Dot(e.pos, U) - e.groundY;
            if (h < 0) {
                e.pos -= U * h;
                float vn = Dot(e.vel, U);
                e.vel -= U * (vn * 1.4f);  // a little bounce
                e.vel *= 0.85f;
                if (Length(e.vel) < 0.2f * upm) {
                    e.vel = Vec3();
                    e.phys = e.dead ? Phys::Ragdoll : Phys::Animated;
                }
            }
            e.dirty = true;
        } else if (e.ragdoll && (e.phys == Phys::Ragdoll || (e.phys == Phys::Held && e.ragdoll->skeletal))) {
            if (Length(e.vel) > 0) {  // a thrown corpse: hand the velocity to the particles
                for (auto& q : e.ragdoll->p) q.old = q.x - e.vel * Ragdoll::kStep;
                e.vel = Vec3();
            }
            if (e.ragdoll->restTimer < 2.0f) {
                Ragdoll& sim = *e.ragdoll;
                const float h = Ragdoll::kStep;
                sim.stepClock = std::min(sim.stepClock + dt, 4 * h);
                for (; sim.stepClock >= h; sim.stepClock -= h) sim.Step(h, w.axes, e.groundY);
                // Walls: a body that was on the walk boxes slides along their edge (pelvis only).
                Ragdoll& rd = *e.ragdoll;
                Vec3 pel = rd.p[rd.pelvis].x, off = pel - SnapToWalkBoxes(L, pel);
                off -= U * Dot(off, U);
                if (Length(off) > 0.05f * upm) {
                    Vec3 prev = rd.p[rd.pelvis].old, was = prev - SnapToWalkBoxes(L, prev);
                    was -= U * Dot(was, U);
                    if (Length(was) < 0.3f * upm) {  // just left them; one killed behind a wall stays there
                        Vec3 n = Normalize(off);
                        for (auto& q : rd.p) {
                            q.x -= off;
                            q.old -= off;
                            float vn = Dot(q.x - q.old, n);
                            if (vn > 0) q.old += n * vn;
                        }
                    }
                }
                e.ragdoll->ApplyToEntity(e);
            }
        }
    }
    for (auto& wd : g_welds) {
        Entity* c = w.Find(wd.child);
        Entity* par = w.Find(wd.parent);
        if (!c || !par) continue;
        c->pos = par->pos + wd.offset;
        c->phys = Phys::Frozen;
        c->dirty = true;
    }
}

// ===================================================================== NPC locomotion
void FaceDirection(Entity& e, const Vec3& dir) {
    const Axes& ax = GetWorld().axes;
    Vec3 f = Normalize(dir - ax.up * Dot(dir, ax.up));
    if (Length(f) < 0.5f) return;
    Vec3 lf = Normalize(g_charLocalForward - ax.up * Dot(g_charLocalForward, ax.up));
    e.rot = FromTo(lf, f);
}

void PlayBodyClip(lua::State* L, Entity& e, const std::string& clip, float speed) {
    if (clip.empty()) return;
    // A clip started in the same tick as AgentCreate can fail (run 12: a spawn told to stay stood in its
    // T-pose for good), so a failed start is retried next tick.
    if (e.clipName != clip || e.clipHandle < 0) {
        if (e.clipHandle >= 0) lua::Call(L, "GM.StopClip", {e.clipHandle});
        e.clipHandle = (int)lua::Call(L, "GM.PlayClip", {e.name, clip, true, 1.0f, 40}, 1).N(0, -1);
        e.clipName = clip;
    }
    if (e.clipHandle >= 0) lua::Call(L, "GM.ClipSpeed", {e.clipHandle, speed});
}

void Locomotion(lua::State* L) {
    World& w = GetWorld();
    float dt = w.dt, upm = Upm();
    for (auto& ep : w.ents) {
        Entity& e = *ep;
        if (!e.spawned || e.dead || !e.info || e.phys != Phys::Animated || e.ai == Entity::Ai::None) continue;
        const CharacterInfo& c = *e.info;
        e.aiTimer -= dt;
        Vec3 goal = e.goal;
        float speed = 0;
        if (e.ai == Entity::Ai::Follow) {
            goal = SnapToWalkBoxes(L, w.player.pos);  // noclip: wait at the nearest reachable spot
            float d = Length(goal - e.pos);
            speed = d > 6 * upm ? 4.0f : d > 1.8f * upm ? 1.5f : 0;
        } else if (e.ai == Entity::Ai::Wander) {
            if (e.aiTimer <= 0) {
                float a = Rand(0, 2 * kPi), r = Rand(1, 4) * upm;
                Vec3 side = Normalize(Cross(w.axes.up, Vec3(1, 0, 0)));
                Vec3 fw = Normalize(Cross(side, w.axes.up));
                e.goal = SnapToWalkBoxes(L, e.origPos + side * (std::cos(a) * r) + fw * (std::sin(a) * r));
                e.aiTimer = Rand(4, 9);
                goal = e.goal;
            }
            speed = Length(goal - e.pos) > 0.3f * upm ? 1.2f : 0;
        }
        if (speed > 0) {
            Vec3 dir = Normalize(goal - e.pos);
            dir = Normalize(dir - w.axes.up * Dot(dir, w.axes.up));
            // Step, then put the step back on the walk boxes: along a wall that slides, into a corner it stalls.
            float want = speed * upm * dt;
            Vec3 next = SnapToWalkBoxes(L, e.pos + dir * want);
            float moved = Length(next - e.pos);
            e.pos = next;
            FaceDirection(e, dir);
            e.dirty = true;
            if (moved < 0.3f * want) {  // stuck: idle, and a wanderer picks a new goal
                if (e.ai == Entity::Ai::Wander) e.aiTimer = 0;
                PlayBodyClip(L, e, c.idleClip, 1.0f);
                continue;
            }
            bool run = speed > 2.0f && !c.runClip.empty();
            // Quadrupeds and bipeds use their own skeleton's clips (sk18_colin_walk vs sk54_bigby_walk).
            // The wolf (sk35) has no walk/run in the game data: it glides in its idle pose.
            PlayBodyClip(L, e, run ? c.runClip : c.walkClip, run ? speed / 4.0f : speed / 1.2f);
        } else {
            PlayBodyClip(L, e, c.idleClip, 1.0f);
        }
    }
}

// Third-person playermodel follows the player and walks with the right clips.
void PlayerModel(lua::State* L) {
    World& w = GetWorld();
    Player& p = w.player;
    Entity* body = p.playerModelAgent.empty() ? nullptr : w.Find(p.playerModelAgent);
    if (!p.thirdPerson) {
        if (body && body->visible) { lua::Call(L, "GM.Show", {body->name, false}); body->visible = false; }
        return;
    }
    if (!body) {
        const CharacterInfo* c = nullptr;
        for (auto& ci : AssetBridge::Get().Telltale().Characters())
            if (ci.prop == p.playerModel) c = &ci;
        if (!c) return;
        body = Spawn(L, *c, false);
        if (!body) return;
        p.playerModelAgent = body->name;
    }
    if (!body->visible) { lua::Call(L, "GM.Show", {body->name, true}); body->visible = true; }
    body->pos = p.pos;
    FaceDirection(*body, p.forward);
    body->dirty = true;
    float sp = Length(p.vel - w.axes.up * Dot(p.vel, w.axes.up)) / Upm();
    if (body->info)
        PlayBodyClip(L, *body, sp > 4 && !body->info->runClip.empty() ? body->info->runClip
                               : sp > 0.3f ? body->info->walkClip : body->info->idleClip,
                     sp > 4 ? sp / 4.0f : sp > 0.3f ? sp / 1.2f : 1.0f);
}

}  // namespace

// ===================================================================== public
const char* WeaponName(Weapon w) { return kWeapons[(int)w].name; }
const char* ToolName(ToolMode t) { return kToolNames[(int)t]; }

void SelectWeapon(Weapon wpn) {
    World& w = GetWorld();
    if (w.player.weapon == wpn) return;
    w.player.weapon = wpn;
    w.hideHud = wpn == Weapon::Camera;
    audio::Play("sound/common/wpn_moveselect.wav", 0.6f);
}

Vec3 AimPoint(const Entity& e) {
    const Axes& ax = GetWorld().axes;
    if (e.dead && e.ragdoll) return e.ragdoll->p[e.ragdoll->pelvis].x;
    return e.pos + ax.up * ((e.dead ? 0.2f : 1.3f) * ax.unitsPerMeter);
}

bool CapturesMouse() {
    World& w = GetWorld();
    return (g_held && w.input.down['E']) || (w.player.weapon == Weapon::Camera && w.input.down[VK_RBUTTON]);
}

Entity* Trace(const Vec3& from, const Vec3& dir, float maxDist, float* outDist, const Entity* ignore) {
    Entity* best = nullptr;
    float bt = maxDist;
    for (auto& e : GetWorld().ents) {
        if (e.get() == ignore || !Hittable(*e)) continue;
        float t;
        if (RayCapsule(from, dir, *e, bt, t)) { bt = t; best = e.get(); }
    }
    if (outDist) *outDist = bt;
    return best;
}

Entity* Spawn(lua::State* L, const CharacterInfo& c, bool asNpc) {
    World& w = GetWorld();
    Player& p = w.player;
    char name[64];
    snprintf(name, sizeof name, "gm_npc_%d", ++w.spawnCounter);
    Vec3 fh = Normalize(p.forward - w.axes.up * Dot(p.forward, w.axes.up));
    // 2 m ahead, on the walk boxes; facing a wall that lands in your face, so try the other three sides too
    // and keep the roomiest spot.
    Vec3 side = Cross(w.axes.up, fh), at = p.pos;
    float room = -1;
    for (Vec3 d : {fh, side, Vec3() - side, Vec3() - fh}) {
        Vec3 c = SnapToWalkBoxes(L, p.pos + d * (2.0f * Upm()));
        float r = Length(c - p.pos);
        if (r > room + 0.3f * Upm()) { room = r; at = c; }
    }
    if (!lua::Call(L, "GM.Spawn", {name, c.prop, w.sceneForSpawns, at.x, at.y, at.z, 0.f, 0.f, 0.f, 1.f}, 1).B(0)) {
        hud::Notify(std::string("Could not spawn ") + c.prop + " (see log)");
        return nullptr;
    }
    if (!g_charForwardKnown) {  // identity rotation: its forward is the character local forward axis
        auto f = lua::Call(L, "GM.Forward", {name}, 3);
        if (f.ok && f.type[0] == lua::TNUMBER) {
            g_charLocalForward = Normalize(Vec3(f.N(0), f.N(1), f.N(2)));
            g_charForwardKnown = true;
            Log("[combat] character local forward = (%.2f %.2f %.2f)", g_charLocalForward.x, g_charLocalForward.y,
                g_charLocalForward.z);
        }
    }
    Entity* e = w.Add(name);
    e->prop = c.prop;
    e->skeleton = c.skeleton;
    e->info = &c;
    e->spawned = e->character = true;
    e->pos = e->origPos = at;
    e->groundY = Dot(p.pos, w.axes.up);
    if (c.plan == BodyPlan::Quadruped) { e->height = c.family == 35 ? 1.3f : 0.7f; e->radius = 0.5f; }
    else if (c.plan == BodyPlan::Bird) { e->height = 0.4f; e->radius = 0.25f; }
    else if (c.family == 15) { e->height = 1.2f; }
    FaceDirection(*e, Vec3() - fh);  // look at the player
    e->dirty = true;
    e->ai = asNpc ? Entity::Ai::Wander : Entity::Ai::None;
    if (!c.idleClip.empty()) PlayBodyClip(L, *e, c.idleClip, 1.0f);
    ScanSkeletonsAsync(1500);  // its skeleton exists once the agent has drawn
    return e;
}

void Kill(lua::State* L, Entity* e, const Vec3& impulse) {
    if (e->dead) return;
    World& w = GetWorld();
    e->dead = true;
    e->hp = 0;
    // Story animation off: stop our loop; story controllers are already frozen by GM.Freeze.
    if (e->clipHandle >= 0) { lua::Call(L, "GM.StopClip", {e->clipHandle}); e->clipHandle = -1; e->clipName.clear(); }
    e->ai = Entity::Ai::None;
    e->ragdoll.reset(new Ragdoll());
    DWORD t0 = GetTickCount();
    if (EnsureBoneHook() && e->ragdoll->BuildSkeletal(*e, w.axes, e->rot.Rotate(g_charLocalForward))) {
        RegisterBones(e->ragdoll.get());
        e->ragdoll->restorePose = !e->spawned;
        Log("[ragdoll] %s: %d bones, %zu constraints, %zu cones, %zu hinges, %zu capsules / %zu pairs (%lu ms)",
            e->name.c_str(), e->ragdoll->count, e->ragdoll->c.size(), e->ragdoll->cones.size(),
            e->ragdoll->hinges.size(), e->ragdoll->segs.size(), e->ragdoll->segPairs.size(), GetTickCount() - t0);
    } else {
        Log("[ragdoll] %s: no skeleton found, whole-body fallback", e->name.c_str());
        e->ragdoll.reset(new Ragdoll());
        e->ragdoll->Build(*e, w.axes, e->info ? e->info->plan : BodyPlan::Biped);
    }
    e->ragdoll->Impulse(e->pos + w.axes.up * (e->height * 0.7f * Upm()), impulse, 1.0f / 60.0f);
    e->phys = Phys::Ragdoll;
    if (g_held == e) g_held = nullptr;
}

void SetEmotion(lua::State* L, Entity* e, const std::string& emotion) {
    if (!e || !e->info || e->info->facePrefix.empty()) return;
    if (e->emotionHandle >= 0) { lua::Call(L, "GM.StopClip", {e->emotionHandle}); e->emotionHandle = -1; }
    e->emotion.clear();
    if (emotion.empty()) return;
    std::string clip;
    if (emotion == "dead") {
        clip = e->info->facePrefix + "_face_blink.anm";  // eyes shut, held
        // Faces with only blink variants (faith_face_blinkHappyB.anm): the first full (non-additive) one.
        std::string want = ToLower(e->info->facePrefix + "_face_blink");
        bool exact = false;
        std::string variant;
        for (auto& n : AssetBridge::Get().Telltale().Find(want)) {
            std::string ln = ToLower(n);
            if (ln == want + ".anm") exact = true;
            else if (variant.empty() && ln.rfind(want, 0) == 0 && ln.size() > 4 && ln.compare(ln.size() - 4, 4, ".anm") == 0 &&
                     ln.find("_add") == std::string::npos)
                variant = n;
        }
        if (!exact && !variant.empty()) clip = variant;
        e->emotionHandle = (int)lua::Call(L, "GM.PlayClip", {e->name, clip, true, 1.0f, 90}, 1).N(0, -1);
        lua::Call(L, "GM.ClipPercent", {e->emotionHandle, 0.5f});
        lua::Call(L, "GM.ClipSpeed", {e->emotionHandle, 0.0f});
        return;
    }
    // "angry" -> the first of the character's phoneme_default_<emotion> rest faces starting with it.
    std::string lower = ToLower(emotion);
    for (auto& em : e->info->emotions)
        if (ToLower(em).rfind(lower, 0) == 0) {
            clip = e->info->facePrefix + "_phoneme_default_" + em + ".anm";
            e->emotion = em;
            break;
        }
    if (clip.empty()) { hud::Notify(e->name + " has no '" + emotion + "' face"); return; }
    e->emotionHandle = (int)lua::Call(L, "GM.PlayClip", {e->name, clip, true, 1.0f, 80}, 1).N(0, -1);
    if (!e->mouthShape.empty()) SetMouth(L, e, e->mouthShape, e->mouthWeight);  // that emotion's version of it
}

// Mouth shapes: the lip-sync poses <face>_phoneme_<shape>_<emotion>.anm ("AA" open, "O" round, "MM" shut,
// "EE" wide...). One is laid over the rest face with a weight: how far the mouth goes into that shape.
std::vector<std::string> MouthShapes(const std::string& facePrefix) {
    static std::map<std::string, std::vector<std::string>> cache;
    auto it = cache.find(facePrefix);
    if (it != cache.end()) return it->second;
    std::vector<std::string> out;
    std::string pre = ToLower(facePrefix + "_phoneme_");
    for (auto& n : AssetBridge::Get().Telltale().Find(pre)) {
        std::string l = ToLower(n);
        if (l.rfind(pre, 0) != 0) continue;
        size_t a = pre.size(), b = l.find('_', a);
        if (b == std::string::npos) continue;
        std::string shape = l.substr(a, b - a);
        for (auto& ch : shape) ch = (char)std::toupper((unsigned char)ch);
        if (shape != "DEFAULT" && std::find(out.begin(), out.end(), shape) == out.end()) out.push_back(shape);
    }
    std::sort(out.begin(), out.end());
    cache[facePrefix] = out;
    return out;
}

void SetMouth(lua::State* L, Entity* e, const std::string& shape, float weight) {
    if (!e || !e->info || e->info->facePrefix.empty()) return;
    if (e->mouthHandle >= 0 && shape == e->mouthShape && weight > 0) {  // just the slider
        e->mouthWeight = weight;
        lua::Call(L, "GM.ClipWeight", {e->mouthHandle, weight});
        return;
    }
    if (e->mouthHandle >= 0) { lua::Call(L, "GM.StopClip", {e->mouthHandle}); e->mouthHandle = -1; }
    e->mouthShape = shape;
    e->mouthWeight = weight;
    if (shape.empty() || weight <= 0) return;
    // this shape in the current emotion, else its first variant (angryB -> angry*), else normal, else any
    std::string pre = ToLower(e->info->facePrefix + "_phoneme_" + shape + "_");
    std::string emo = ToLower(e->emotion.empty() ? "normala" : e->emotion);
    std::string base = emo.size() > 1 ? emo.substr(0, emo.size() - 1) : emo;
    std::string exact, sameBase, normal, any;
    for (auto& n : AssetBridge::Get().Telltale().Find(pre)) {
        std::string l = ToLower(n);
        if (l.rfind(pre, 0) != 0 || l.size() < 4 || l.compare(l.size() - 4, 4, ".anm") != 0 || l.find("smoking") != std::string::npos)
            continue;
        std::string tail = l.substr(pre.size(), l.size() - pre.size() - 4);
        if (tail == emo) exact = n;
        else if (sameBase.empty() && tail.rfind(base, 0) == 0) sameBase = n;
        else if (normal.empty() && tail.rfind("normal", 0) == 0) normal = n;
        else if (any.empty()) any = n;
    }
    std::string clip = !exact.empty() ? exact : !sameBase.empty() ? sameBase : !normal.empty() ? normal : any;
    if (clip.empty()) { hud::Notify(e->name + " has no '" + shape + "' mouth"); return; }
    e->mouthHandle = (int)lua::Call(L, "GM.PlayClip", {e->name, clip, true, weight, 82}, 1).N(0, -1);
    if (e->mouthHandle < 0) return;
    lua::Call(L, "GM.ClipPercent", {e->mouthHandle, 0.5f});
    lua::Call(L, "GM.ClipSpeed", {e->mouthHandle, 0.0f});
}

void SetFaceChannel(lua::State* L, Entity* e, size_t ch, float weight) {
    if (!e || !e->info) return;
    auto chans = AssetBridge::Get().Telltale().FaceChannels(e->info->facePrefix);
    if (ch >= chans.size()) return;
    if (e->faceWeights.size() < chans.size()) e->faceWeights.resize(chans.size(), 0);
    e->faceWeights[ch] = weight;
    int h = -1;
    for (auto& fh : e->faceHandles)
        if (fh.first == chans[ch]) h = fh.second;
    if (h < 0) {
        // Additive face layer, parked at its peak (mid-clip) and weighted by the slider.
        h = (int)lua::Call(L, "GM.PlayClip", {e->name, chans[ch], true, weight, 85}, 1).N(0, -1);
        if (h < 0) return;
        lua::Call(L, "GM.ClipPercent", {h, 0.5f});
        lua::Call(L, "GM.ClipSpeed", {h, 0.0f});
        e->faceHandles.push_back({chans[ch], h});
    }
    lua::Call(L, "GM.ClipWeight", {h, weight});
}

void Init() {}

void OnEnterSandbox(lua::State* L) {
    World& w = GetWorld();
    ScanSkeletonsAsync(0);
    for (int i = 0; i < (int)Weapon::Count; ++i) {
        w.player.ammo[i].clip = kWeapons[i].clipMax;
        w.player.ammo[i].reserve = kWeapons[i].reserve;
        w.player.ammo[i].clipMax = kWeapons[i].clipMax;
    }
    w.player.weapon = Weapon::PhysGun;
    w.hideHud = false;
    g_held = nullptr;
    g_weldFirst = nullptr;
    g_welds.clear();
    g_rockets.clear();
    (void)L;
}

void OnExitSandbox(lua::State* L) {
    World& w = GetWorld();
    audio::Stop(g_physLoop);
    g_held = nullptr;
    for (auto& e : w.ents) {
        if (e->fingerRig) {  // fingers back to the animation, while the bones still exist
            std::fill(e->fingerCurl.begin(), e->fingerCurl.end(), 0.0f);
            ApplyFingers(e.get());
            e->fingerRig.reset();
        }
        if (e->clipHandle >= 0) lua::Call(L, "GM.StopClip", {e->clipHandle});
        if (e->emotionHandle >= 0) lua::Call(L, "GM.StopClip", {e->emotionHandle});
        if (e->mouthHandle >= 0) lua::Call(L, "GM.StopClip", {e->mouthHandle});
        for (auto& fh : e->faceHandles) lua::Call(L, "GM.StopClip", {fh.second});
        if (e->spawned) lua::Call(L, "GM.Destroy", {e->name});
    }
    w.ents.erase(std::remove_if(w.ents.begin(), w.ents.end(), [](const std::unique_ptr<Entity>& e) { return e->spawned; }),
                 w.ents.end());
    w.player.playerModelAgent.clear();
    w.tracers.clear();
    w.blasts.clear();
    g_welds.clear();
    g_rockets.clear();
}

void Tick(lua::State* L, float dt) {
    World& w = GetWorld();
    Player& p = w.player;
    InputFrame& in = w.input;
    bool keys = !hud::WantsKeyboard(), free = !hud::AnyMenuOpen();

    // Weapon slots 1-6 (pressing a slot again cycles inside it), wheel cycles everything.
    if (keys) {
        for (int s = 1; s <= 6; ++s) {
            if (!in.pressed['0' + s]) continue;
            int cur = (int)p.weapon, n = (int)Weapon::Count;
            for (int k = 1; k <= n; ++k) {
                int cand = (cur + k) % n;
                if (kWeapons[cand].slot == s) { SelectWeapon((Weapon)cand); break; }
            }
        }
        if (in.pressed['E'] && !g_held && p.weapon != Weapon::PhysGun) {  // use: NPC follows / stays
            if (Entity* e = AimEntity(2.5f)) {
                if (e->spawned && !e->dead) {
                    e->ai = e->ai == Entity::Ai::Follow ? Entity::Ai::Idle : Entity::Ai::Follow;
                    hud::Notify(e->name + (e->ai == Entity::Ai::Follow ? " follows you" : " stays"));
                }
            }
        }
    }
    if (free && !g_held && p.weapon != Weapon::Camera && in.wheel != 0) {
        int n = (int)Weapon::Count;
        SelectWeapon((Weapon)((((int)p.weapon - (int)in.wheel) % n + n) % n));
    }

    const WeaponDef& wd = kWeapons[(int)p.weapon];
    WeaponState& ws = p.ammo[(int)p.weapon];
    if (free) {
        switch (p.weapon) {
            case Weapon::PhysGun: Physgun(L); break;
            case Weapon::ToolGun: Toolgun(L); break;
            case Weapon::Camera:
                if (in.down[VK_RBUTTON]) {  // RMB + mouse: zoom (vertical) and tilt (horizontal)
                    p.fov = Clamp(p.fov + in.mouseDy * 0.15f, 10.0f, 100.0f);
                    p.roll = Clamp(p.roll + in.mouseDx * 0.15f, -45.0f, 45.0f);
                }
                if (in.pressed[VK_LBUTTON]) {
                    audio::Play(wd.fireSound);
                    g_screenshotPending = true;
                }
                break;
            default: {
                bool trigger = wd.automatic ? in.down[VK_LBUTTON] : in.pressed[VK_LBUTTON];
                if (in.pressed['R'] && ws.clipMax > 0 && ws.reserve > 0) {
                    int take = std::min(ws.clipMax - ws.clip, ws.reserve);
                    ws.clip += take;
                    ws.reserve -= take;
                    ws.nextFire = w.time + 1.2f;
                }
                if (trigger && w.time >= ws.nextFire) {
                    if (ws.clipMax > 0 && ws.clip <= 0) {
                        if (in.pressed[VK_LBUTTON]) audio::Play("sound/weapons/pistol/pistol_empty.wav");
                        break;
                    }
                    ws.nextFire = w.time + wd.interval;
                    if (ws.clipMax > 0) --ws.clip;
                    audio::Play(wd.fireSound, 0.8f);
                    p.punchPitch += p.weapon == Weapon::Shotgun ? 6.0f : p.weapon == Weapon::Rpg ? 4.0f : 1.5f;
                    if (p.weapon == Weapon::Rpg) {
                        Rocket r{p.eye + p.forward * (0.6f * Upm()), p.forward * (25 * Upm()), 6.0f, false};
                        r.walls = OffWalkBoxes(L, p.eye) < 0.3f * Upm();
                        if (r.walls && OffWalkBoxes(L, r.pos) > 0.3f * Upm()) r.pos = p.eye;  // muzzle in the wall
                        Log("[rpg] fired from (%.2f %.2f %.2f), %.2f m off the walk boxes: walls %s", p.eye.x, p.eye.y,
                            p.eye.z, OffWalkBoxes(L, p.eye) / Upm(), r.walls ? "on" : "off");
                        g_rockets.push_back(r);
                    } else {
                        FireBullets(L, wd);
                    }
                }
            }
        }
    }
    if (p.weapon != Weapon::Camera && (p.fov != 70.0f || p.roll != 0)) {
        p.fov += (70.0f - p.fov) * std::min(1.0f, dt * 8);
        p.roll *= std::exp(-dt * 8);
    }

    // rockets
    // Walls are tested on the rocket's next position, not from where it is: a rocket is soon off the walk
    // boxes, where WallDistance sees no walls (run 12 flew one through the wall). At a wall it blows up on
    // the near side, still on the walk boxes, so the blast's own wall test works.
    for (auto& r : g_rockets) {
        float d = 0, len = Length(r.vel * dt);
        Vec3 dir = Normalize(r.vel);
        Entity* e = Trace(r.pos, dir, len, &d);
        Vec3 next = r.pos + dir * (e ? d : len);
        bool wall = r.walls && OffWalkBoxes(L, next) > 0.3f * Upm();
        bool floor = Dot(next, w.axes.up) < FloorHeight();
        if (wall) e = nullptr;
        else r.pos = next;
        r.life -= dt;
        if (e || wall || floor || r.life <= 0) {
            Log("[rpg] explodes at (%.2f %.2f %.2f): %s", r.pos.x, r.pos.y, r.pos.z,
                e ? e->name.c_str() : wall ? "wall" : floor ? "floor" : "end of life");
            Explode(L, r.pos);
            r.life = -1;
        }
    }
    g_rockets.erase(std::remove_if(g_rockets.begin(), g_rockets.end(), [](const Rocket& r) { return r.life < 0; }),
                    g_rockets.end());
    w.tracers.erase(std::remove_if(w.tracers.begin(), w.tracers.end(), [&](const World::Shot& s) { return w.time - s.t > 0.08f; }),
                    w.tracers.end());
    w.blasts.erase(std::remove_if(w.blasts.begin(), w.blasts.end(), [&](const World::Blast& b) { return w.time - b.t > 0.6f; }),
                   w.blasts.end());

    Physics(L);
    Locomotion(L);
    PlayerModel(L);
}

// Read by the HUD (under WorldLock).
Entity* HeldEntity() { return g_held; }
bool TakeScreenshotRequest() {
    bool r = g_screenshotPending;
    g_screenshotPending = false;
    return r;
}
std::vector<Vec3> RocketPositions() {
    std::vector<Vec3> v;
    for (auto& r : g_rockets) v.push_back(r.pos);
    return v;
}
const std::string& ToolInfo() { return g_toolInfo; }

void BuildFingers(Entity* e) {
    World& w = GetWorld();
    const Axes& ax = w.axes;
    float upm = ax.unitsPerMeter;
    e->fingerHands = 0;
    int count = 0;
    uintptr_t nodes = 0;
    if (!EnsureBoneHook() || !FindSkeleton(e->pos, ax, &count, &nodes)) {
        Log("[fingers] %s: no skeleton", e->name.c_str());
        return;
    }
    std::vector<int> parent(count, -1);
    std::vector<Vec3> P(count);
    std::vector<Quat> G(count);
    for (int i = 0; i < count; ++i) {
        uintptr_t n = nodes + i * kNodeSize;
        float gq[4], gp[3];
        uint32_t par = 0;
        if (!SafeRead(n + 0x3c, gq, 16) || !SafeRead(n + 0x4c, gp, 12) || !SafeRead(n + 0x64, &par, 4)) return;
        G[i] = Normalize(Quat(gq[0], gq[1], gq[2], gq[3]));
        P[i] = Vec3(gp[0], gp[1], gp[2]);
        if (par >= nodes && par < nodes + count * kNodeSize && (par - nodes) % kNodeSize == 0)
            parent[i] = (int)((par - nodes) / kNodeSize);
        if (parent[i] >= i) return;
    }
    std::vector<std::vector<int>> kids(count);
    for (int i = 0; i < count; ++i)
        if (parent[i] >= 0) kids[parent[i]].push_back(i);
    std::vector<int> depth(count, 0);
    for (int i = count - 1; i >= 0; --i)
        for (int k : kids[i]) depth[i] = std::max(depth[i], depth[k] + 1);
    auto chainFrom = [&](int b) {
        std::vector<int> c{b};
        while (!kids[c.back()].empty()) {
            int nx = -1;
            for (int k : kids[c.back()])
                if (nx < 0 || depth[k] > depth[nx]) nx = k;
            c.push_back(nx);
        }
        return c;
    };
    struct Cand { int h; std::vector<std::vector<int>> chains; float total = 0; };
    std::vector<Cand> cands;
    for (int i = 0; i < count; ++i) {
        Cand c{i, {}, 0};
        for (int k : kids[i]) {
            if (depth[k] < 1) continue;
            auto ch = chainFrom(k);
            float len = Length(P[ch.back()] - P[ch[0]]);
            if (len > 0.025f * upm && len < 0.2f * upm && ch.size() <= 6) { c.chains.push_back(ch); c.total += len; }
        }
        if (c.chains.size() >= 4 && c.chains.size() <= 6) cands.push_back(c);
    }
    // the most alike pair (the face can look like a hand too, but it has no twin)
    int bi = -1, bj = -1;
    float best = 1e30f;
    for (size_t i = 0; i < cands.size(); ++i)
        for (size_t j = i + 1; j < cands.size(); ++j) {
            if (Length(P[cands[i].h] - P[cands[j].h]) < 0.05f * upm) continue;
            float score = std::fabs((float)cands[i].chains.size() - (float)cands[j].chains.size()) +
                          std::fabs(cands[i].total - cands[j].total) / (0.05f * upm);
            if (score < best) { best = score; bi = (int)i; bj = (int)j; }
        }
    std::vector<Cand> hands;
    if (bi >= 0) { hands.push_back(cands[bi]); hands.push_back(cands[bj]); }
    else if (cands.size() == 1) hands.push_back(cands[0]);
    Log("[fingers] %s: %zu hand-shaped bones, using %zu", e->name.c_str(), cands.size(), hands.size());
    if (hands.empty()) return;
    // Telltale's right is -cross(up, forward), for characters as for the camera
    Vec3 fwd = e->rot.Rotate(g_charLocalForward), right = Cross(ax.up, fwd) * -1.0f;
    Vec3 mid = hands.size() == 2 ? (P[hands[0].h] + P[hands[1].h]) * 0.5f : e->pos;
    auto rig = std::make_shared<FingerRig>();
    std::vector<std::string> names;
    const char* fingerNames[] = {"thumb", "index", "middle", "ring", "pinky"};
    for (auto& hc : hands) {
        std::string side = hands.size() < 2 ? "" : Dot(P[hc.h] - mid, right) > 0 ? "R " : "L ";
        Vec3 m;
        Vec3 meanBase;
        for (auto& c : hc.chains) { m += Normalize(P[c.back()] - P[c[0]]); meanBase += P[c[0]]; }
        m = Normalize(m);
        meanBase = meanBase * (1.0f / hc.chains.size());
        int thumb = 0;
        float lowest = 2;
        for (size_t c = 0; c < hc.chains.size(); ++c) {
            float d = Dot(Normalize(P[hc.chains[c].back()] - P[hc.chains[c][0]]), m);
            if (d < lowest) { lowest = d; thumb = (int)c; }
        }
        Vec3 across = P[hc.chains[thumb][0]] - meanBase;
        across = across - m * Dot(across, m);
        std::vector<int> order{thumb};
        std::vector<int> rest;
        for (size_t c = 0; c < hc.chains.size(); ++c)
            if ((int)c != thumb) rest.push_back((int)c);
        std::sort(rest.begin(), rest.end(), [&](int a, int b) {
            return Dot(P[hc.chains[a][0]] - meanBase, across) > Dot(P[hc.chains[b][0]] - meanBase, across);
        });
        for (int r : rest)
            if (order.size() < 5) order.push_back(r);
        // bend direction: how each finger already curls; straight ones borrow the hand's average
        std::vector<Vec3> bend(order.size());
        Vec3 avg;
        for (size_t f = 0; f < order.size(); ++f) {
            auto& c = hc.chains[order[f]];
            Vec3 dir = Normalize(P[c[1]] - P[c[0]]), b = P[c.back()] - P[c[0]];
            b = b - dir * Dot(b, dir);
            if (Length(b) > 0.004f * upm) { bend[f] = Normalize(b); if (f) avg += bend[f]; }
        }
        if (Length(avg) < 1e-4f) avg = Cross(m, across);
        avg = Normalize(avg);
        for (size_t f = 0; f < order.size(); ++f) {
            auto c = hc.chains[order[f]];
            if (c.size() > 1 && kids[c.back()].empty()) c.pop_back();  // the tip marker moves nothing
            if (c.size() >= 4) c.erase(c.begin());                      // a palm bone in front of the finger
            Vec3 dir = Normalize(P[c.size() > 1 ? c[1] : hc.chains[order[f]].back()] - P[c[0]]);
            Vec3 b = Length(bend[f]) > 0.5f ? bend[f] : avg;
            Vec3 axis = Normalize(Cross(dir, b));
            FingerRig::Finger fg;
            fg.maxDeg = f == 0 ? 35.0f : 70.0f;
            for (int j : c) {
                fg.joints.push_back(nodes + j * kNodeSize);
                fg.axes.push_back(Conj(G[j]).Rotate(axis));
            }
            rig->fingers.push_back(fg);
            names.push_back(side + (f < 5 ? fingerNames[f] : "finger"));
        }
    }
    e->fingerRig = rig;
    e->fingerNames = names;
    e->fingerCurl.assign(names.size(), 0.0f);
    e->fingerHands = (int)hands.size();
}

void ApplyFingers(Entity* e) {
    if (!e || !e->fingerRig) return;
    AcquireSRWLockExclusive(&g_boneLock);
    for (size_t f = 0; f < e->fingerRig->fingers.size() && f < e->fingerCurl.size(); ++f) {
        auto& fg = e->fingerRig->fingers[f];
        float v = e->fingerCurl[f];
        for (size_t j = 0; j < fg.joints.size(); ++j) {
            uintptr_t n = fg.joints[j];
            if (std::fabs(v) < 1e-3f) {  // back to the animation
                auto it = g_fingerOffsets.find(n);
                if (it != g_fingerOffsets.end()) {
                    if (it->second.has) SafeWrite(n + 0x1c, &it->second.base, 16);
                    g_fingerOffsets.erase(it);
                }
                continue;
            }
            float deg = fg.maxDeg * v * (j == 0 ? 0.8f : 1.0f);
            g_fingerOffsets[n].off = Quat::AxisAngle(fg.axes[j], Deg2Rad(deg));
        }
    }
    ReleaseSRWLockExclusive(&g_boneLock);
}

}  // namespace combat
}  // namespace gm
