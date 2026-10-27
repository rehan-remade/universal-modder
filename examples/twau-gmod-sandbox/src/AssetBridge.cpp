// AssetBridge: VPK + ttarch2 readers, TWAU catalogs, Source MDL/VVD/VTX/VTF/WAV decoding.
// Formats as verified on the target PC on 2026-10-18 (see MODLOG.md).
#include "AssetBridge.h"

#include <zlib.h>

#include <algorithm>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <set>

namespace fs = std::filesystem;

namespace gm {

std::string ToLower(std::string s) {
    for (auto& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}
static std::string NormPath(std::string s) {
    for (auto& c : s) c = c == '\\' ? '/' : (char)std::tolower((unsigned char)c);
    while (!s.empty() && s[0] == '/') s.erase(0, 1);
    return s;
}
static bool StartsWith(const std::string& s, const std::string& p) {
    return s.size() >= p.size() && std::equal(p.begin(), p.end(), s.begin());
}
static bool EndsWith(const std::string& s, const std::string& p) {
    return s.size() >= p.size() && std::equal(p.rbegin(), p.rend(), s.rbegin());
}
static bool ReadWholeFile(const std::string& path, Bytes& out) {
    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return false;
    _fseeki64(f, 0, SEEK_END);
    long long n = _ftelli64(f);
    _fseeki64(f, 0, SEEK_SET);
    out.resize((size_t)n);
    bool ok = n == 0 || fread(out.data(), 1, (size_t)n, f) == (size_t)n;
    fclose(f);
    return ok;
}
template <class T>
static T Rd(const uint8_t* p) {
    T v;
    memcpy(&v, p, sizeof(T));
    return v;
}

// ===================================================================================== VPK
bool VpkArchive::Open(const std::string& dirVpkPath) {
    dirPath_ = dirVpkPath;
    if (!EndsWith(ToLower(dirVpkPath), "_dir.vpk")) return false;
    stem_ = dirVpkPath.substr(0, dirVpkPath.size() - 8);
    Bytes d;
    if (!ReadWholeFile(dirVpkPath, d) || d.size() < 12) return false;
    if (Rd<uint32_t>(&d[0]) != 0x55AA1234) return false;
    uint32_t version = Rd<uint32_t>(&d[4]), treeSize = Rd<uint32_t>(&d[8]);
    size_t header = version == 2 ? 28 : 12;
    treeEnd_ = (uint32_t)(header + treeSize);
    size_t p = header;
    auto readz = [&](std::string& s) {
        size_t st = p;
        while (p < d.size() && d[p]) ++p;
        s.assign((const char*)&d[st], p - st);
        ++p;
        return !s.empty();
    };
    std::string ext, dir, name;
    while (p < d.size() && readz(ext)) {
        while (readz(dir)) {
            while (readz(name)) {
                if (p + 18 > d.size()) return false;
                Entry e;
                e.crc = Rd<uint32_t>(&d[p]);
                uint16_t pre = Rd<uint16_t>(&d[p + 4]);
                e.archive = Rd<uint16_t>(&d[p + 6]);
                e.offset = Rd<uint32_t>(&d[p + 8]);
                e.length = Rd<uint32_t>(&d[p + 12]);
                p += 18;
                e.preload.assign(d.begin() + p, d.begin() + p + pre);
                p += pre;
                std::string full = (dir == " " ? "" : dir + "/") + name + "." + ext;
                entries_[NormPath(full)] = std::move(e);
            }
        }
    }
    return true;
}

bool VpkArchive::Contains(const std::string& path) const { return entries_.count(NormPath(path)) != 0; }

void VpkArchive::List(std::vector<std::string>& out) const {
    for (auto& kv : entries_) out.push_back(kv.first);
}

bool VpkArchive::Read(const std::string& path, Bytes& out) const {
    auto it = entries_.find(NormPath(path));
    if (it == entries_.end()) return false;
    const Entry& e = it->second;
    out = e.preload;
    if (e.length == 0) return true;
    std::string file;
    uint64_t off = e.offset;
    if (e.archive == 0x7fff) {
        file = dirPath_;
        off += treeEnd_;
    } else {
        char buf[16];
        snprintf(buf, sizeof buf, "_%03u.vpk", e.archive);
        file = stem_ + buf;
    }
    FILE* f = fopen(file.c_str(), "rb");
    if (!f) return false;
    size_t base = out.size();
    out.resize(base + e.length);
    _fseeki64(f, (long long)off, SEEK_SET);
    bool ok = fread(out.data() + base, 1, e.length, f) == e.length;
    fclose(f);
    return ok;
}

bool SourceFileSystem::Mount(const std::string& gmodRoot) {
    looseRoots_ = {gmodRoot + "\\garrysmod", gmodRoot + "\\sourceengine"};
    std::vector<std::string> dirs;
    std::error_code ec;
    // garrysmod_dir.vpk first: GMod's own v_physcannon etc. win over the HL2 copies.
    dirs.push_back(gmodRoot + "\\garrysmod\\garrysmod_dir.vpk");
    for (auto& de : fs::directory_iterator(gmodRoot + "\\sourceengine", ec)) {
        std::string p = de.path().string();
        if (EndsWith(ToLower(p), "_dir.vpk")) dirs.push_back(p);
    }
    std::sort(dirs.begin() + 1, dirs.end());
    for (auto& d : dirs) {
        auto v = std::make_unique<VpkArchive>();
        if (v->Open(d)) vpks_.push_back(std::move(v));
        else Log("[assets] could not open %s", d.c_str());
    }
    return !vpks_.empty();
}

bool SourceFileSystem::Read(const std::string& path, Bytes& out) const {
    std::string n = NormPath(path);
    for (auto& r : looseRoots_) {
        std::string p = r + "\\" + n;
        for (auto& c : p) if (c == '/') c = '\\';
        if (ReadWholeFile(p, out)) return true;
    }
    for (auto& v : vpks_)
        if (v->Read(n, out)) return true;
    return false;
}

bool SourceFileSystem::Exists(const std::string& path) const {
    std::string n = NormPath(path);
    for (auto& v : vpks_)
        if (v->Contains(n)) return true;
    std::error_code ec;
    for (auto& r : looseRoots_)
        if (fs::exists(r + "\\" + n, ec)) return true;
    return false;
}

// ===================================================================================== TTArchive
static bool InflateRaw(const uint8_t* src, size_t n, uint8_t* dst, size_t cap, size_t& outLen) {
    z_stream zs{};
    if (inflateInit2(&zs, -15) != Z_OK) return false;
    zs.next_in = const_cast<Bytef*>(src);
    zs.avail_in = (uInt)n;
    zs.next_out = dst;
    zs.avail_out = (uInt)cap;
    int r = inflate(&zs, Z_FINISH);
    outLen = cap - zs.avail_out;
    inflateEnd(&zs);
    return r == Z_STREAM_END || (r == Z_BUF_ERROR && zs.avail_out == 0);
}

bool TTArchive::LoadChunk(uint32_t index) {
    if ((int)index == cachedChunk_) return true;
    if (index + 1 >= chunkOffsets_.size()) return false;
    uint64_t a = chunkOffsets_[index], b = chunkOffsets_[index + 1];
    Bytes raw((size_t)(b - a));
    _fseeki64(file_, (long long)a, SEEK_SET);
    if (fread(raw.data(), 1, raw.size(), file_) != raw.size()) return false;
    chunkCache_.resize(chunkSize_);
    size_t got = 0;
    if (!InflateRaw(raw.data(), raw.size(), chunkCache_.data(), chunkSize_, got)) return false;
    chunkCache_.resize(got);
    cachedChunk_ = (int)index;
    return true;
}

bool TTArchive::ReadStream(uint64_t pos, uint64_t len, uint8_t* dst) {
    if (!compressed_) {
        _fseeki64(file_, (long long)(rawBase_ + pos), SEEK_SET);
        return fread(dst, 1, (size_t)len, file_) == len;
    }
    while (len) {
        uint32_t ci = (uint32_t)(pos / chunkSize_), co = (uint32_t)(pos % chunkSize_);
        if (!LoadChunk(ci) || co >= chunkCache_.size()) return false;
        size_t take = (size_t)std::min<uint64_t>(len, chunkCache_.size() - co);
        memcpy(dst, chunkCache_.data() + co, take);
        dst += take;
        pos += take;
        len -= take;
    }
    return true;
}

bool TTArchive::Open(const std::string& path) {
    path_ = path;
    file_ = fopen(path.c_str(), "rb");
    if (!file_) return false;
    uint8_t h[12];
    if (fread(h, 1, 12, file_) != 12) return false;
    if (!memcmp(h, "NCTT", 4)) {
        compressed_ = false;
        rawBase_ = 12;
    } else if (!memcmp(h, "ZCTT", 4)) {
        compressed_ = true;
        chunkSize_ = Rd<uint32_t>(h + 4);
        uint32_t n = Rd<uint32_t>(h + 8);
        chunkOffsets_.resize(n + 1);
        if (fread(chunkOffsets_.data(), 8, n + 1, file_) != n + 1) return false;
    } else {
        Log("[assets] %s: unknown archive magic %.4s (encrypted ECTT is not handled)", path.c_str(), h);
        return false;
    }
    uint8_t ih[16];
    if (!ReadStream(0, 16, ih)) return false;
    uint32_t nameSize, count, hdr;
    if (!memcmp(ih, "3ATT", 4)) {
        nameSize = Rd<uint32_t>(ih + 8);
        count = Rd<uint32_t>(ih + 12);
        hdr = 16;
    } else if (!memcmp(ih, "4ATT", 4)) {
        nameSize = Rd<uint32_t>(ih + 4);
        count = Rd<uint32_t>(ih + 8);
        hdr = 12;
    } else {
        Log("[assets] %s: unknown inner magic %.4s", path.c_str(), ih);
        return false;
    }
    Bytes tab((size_t)count * 28 + nameSize);
    if (!ReadStream(hdr, tab.size(), tab.data())) return false;
    const uint8_t* names = tab.data() + (size_t)count * 28;
    dataBase_ = hdr + tab.size();
    entries_.resize(count);
    for (uint32_t i = 0; i < count; ++i) {
        const uint8_t* e = tab.data() + (size_t)i * 28;
        Entry& en = entries_[i];
        en.crc = Rd<uint64_t>(e);
        en.offset = Rd<uint64_t>(e + 8);
        en.size = Rd<uint32_t>(e + 16);
        uint32_t at = Rd<uint16_t>(e + 24) * 0x10000u + Rd<uint16_t>(e + 26);
        if (at < nameSize) en.name = (const char*)names + at;  // zero-terminated in the table
        byName_[ToLower(en.name)] = i;
    }
    return true;
}

bool TTArchive::Read(const std::string& name, Bytes& out) {
    std::lock_guard<std::mutex> lk(mu_);
    auto it = byName_.find(ToLower(name));
    if (it == byName_.end()) return false;
    const Entry& e = entries_[it->second];
    out.resize(e.size);
    return ReadStream(dataBase_ + e.offset, e.size, out.data());
}

// ===================================================================================== TWAU catalog
static std::string EpisodeOf(const std::string& archiveFile) {
    std::string f = fs::path(archiveFile).filename().string();
    for (int ep = 1; ep <= 5; ++ep) {
        char a[16], b[16];
        snprintf(a, sizeof a, "Fables10%d", ep);
        snprintf(b, sizeof b, "Episode_0%d", ep);
        if (f.find(a) != std::string::npos || f.find(b) != std::string::npos) return a;
    }
    if (f.find("105") != std::string::npos) return "Fables105";
    if (f.find("Menu") != std::string::npos) return "Menu";
    if (f.find("Boot") != std::string::npos) return "Boot";
    return "Project";
}

// "barTripTrapExterior104" -> "Bar Trip Trap Exterior 104"
static std::string Humanize(const std::string& s) {
    std::string out;
    for (size_t i = 0; i < s.size(); ++i) {
        char c = s[i];
        bool split = i > 0 && ((std::isupper((unsigned char)c) && !std::isupper((unsigned char)s[i - 1])) ||
                               (std::isdigit((unsigned char)c) && !std::isdigit((unsigned char)s[i - 1])));
        if (c == '_') { out += ' '; continue; }
        if (split) out += ' ';
        out += (out.empty() || out.back() == ' ') ? (char)std::toupper((unsigned char)c) : c;
    }
    return out;
}

// "bigbyShirtlessBrokenArm" -> {"bigbyShirtlessBrokenArm","bigbyShirtlessBroken","bigbyShirtless","bigby"}
static std::vector<std::string> CamelPrefixes(std::string s) {
    std::vector<std::string> r;
    while (!s.empty() && std::isdigit((unsigned char)s.back())) s.pop_back();
    while (!s.empty()) {
        r.push_back(s);
        size_t cut = std::string::npos;
        for (size_t i = s.size() - 1; i > 0; --i)
            if (std::isupper((unsigned char)s[i])) { cut = i; break; }
        if (cut == std::string::npos) break;
        s.resize(cut);
    }
    return r;
}

bool TTCatalog::Build(const std::string& packDir) {
    std::vector<std::string> paths;
    std::error_code ec;
    for (auto& de : fs::directory_iterator(packDir, ec))
        if (EndsWith(ToLower(de.path().string()), ".ttarch2")) paths.push_back(de.path().string());
    std::sort(paths.begin(), paths.end());  // update archives sort after the base ones and win
    for (auto& p : paths) {
        auto a = std::make_unique<TTArchive>();
        if (!a->Open(p)) continue;
        size_t ai = archives_.size();
        for (size_t i = 0; i < a->Entries().size(); ++i) files_[ToLower(a->Entries()[i].name)] = {ai, i};
        archives_.push_back(std::move(a));
    }
    if (archives_.empty()) return false;
    Classify();
    return true;
}

bool TTCatalog::Read(const std::string& name, Bytes& out) {
    auto it = files_.find(ToLower(name));
    if (it == files_.end()) return false;
    TTArchive& a = *archives_[it->second.first];
    return a.Read(a.Entries()[it->second.second].name, out);
}

std::vector<std::string> TTCatalog::Find(const std::string& substring) const {
    std::vector<std::string> out;
    std::string l = ToLower(substring);
    for (auto& kv : files_)
        if (kv.first.find(l) != std::string::npos)
            out.push_back(archives_[kv.second.first]->Entries()[kv.second.second].name);
    std::sort(out.begin(), out.end());
    return out;
}

const CharacterInfo* TTCatalog::FindBySkeleton(const std::string& skeleton) const {
    std::string l = ToLower(skeleton);
    for (auto& c : characters_)
        if (ToLower(c.skeleton) == l) return &c;
    return nullptr;
}

std::vector<std::string> TTCatalog::ClipsFor(const std::string& skeleton, size_t max) const {
    std::vector<std::string> r;
    std::string l = ToLower(skeleton);
    std::string fam = l.substr(0, l.find('_') + 1);  // "sk54_"
    std::string base = l.substr(fam.size());
    for (auto& pre : CamelPrefixes(skeleton.substr(fam.size()))) {
        std::string p = fam + ToLower(pre);
        auto it = std::lower_bound(anmNames_.begin(), anmNames_.end(), p,
                                   [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
        for (; it != anmNames_.end() && StartsWith(ToLower(*it), p) && r.size() < max; ++it)
            if (std::find(r.begin(), r.end(), *it) == r.end()) r.push_back(*it);
        if (!r.empty()) break;
    }
    (void)base;
    return r;
}

std::vector<std::string> TTCatalog::FaceChannels(const std::string& facePrefix) const {
    std::vector<std::string> r;
    std::string p = ToLower(facePrefix) + "_face_";
    for (auto& n : anmNames_) {
        std::string l = ToLower(n);
        if (StartsWith(l, p) && EndsWith(l, "_add.anm")) r.push_back(n);
    }
    return r;
}

void TTCatalog::Classify() {
    std::set<std::string> anm;  // lower-case
    for (auto& kv : files_) {
        if (EndsWith(kv.first, ".anm")) {
            auto& e = archives_[kv.second.first]->Entries()[kv.second.second];
            anmNames_.push_back(e.name);
            anm.insert(kv.first);
        }
    }
    std::sort(anmNames_.begin(), anmNames_.end(),
              [](const std::string& a, const std::string& b) { return ToLower(a) < ToLower(b); });

    auto has = [&](const std::string& n) { return anm.count(ToLower(n)) != 0; };
    // First "<fam><who>_<kind>*.anm" match, e.g. sk54_bigby_walk.anm, sk54_bigbyWere_runQuadruped.anm.
    auto findClip = [&](const std::string& fam, const std::vector<std::string>& who,
                        const std::vector<std::string>& kinds) -> std::string {
        for (auto& w : who)
            for (auto& k : kinds) {
                std::string n = fam + w + "_" + k + ".anm";
                if (has(n)) {
                    auto it = std::lower_bound(anmNames_.begin(), anmNames_.end(), ToLower(n),
                                               [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
                    if (it != anmNames_.end()) return *it;
                }
            }
        return "";
    };

    std::map<int, CharacterInfo> familyDefault;  // a family's first character with a walk clip
    for (auto& kv : files_) {
        const std::string& l = kv.first;
        if (!(StartsWith(l, "sk") && EndsWith(l, ".prop"))) continue;
        size_t us = l.find('_');
        if (us == std::string::npos || us < 3 || !std::all_of(l.begin() + 2, l.begin() + us, ::isdigit)) continue;
        auto& e = archives_[kv.second.first]->Entries()[kv.second.second];
        CharacterInfo c;
        c.prop = e.name;
        c.skeleton = e.name.substr(0, e.name.size() - 5);
        c.family = std::atoi(l.substr(2, us - 2).c_str());
        c.episode = EpisodeOf(archives_[kv.second.first]->Path());
        std::string who = c.skeleton.substr(us + 1);
        c.display = Humanize(who);
        switch (c.family) {
            case 18: case 35: c.plan = BodyPlan::Quadruped; break;  // Colin, the Big Bad Wolf
            case 37: c.plan = BodyPlan::Bird; break;                // crows
            default: c.plan = BodyPlan::Biped;
        }
        std::string fam = l.substr(0, us + 1);
        auto prefixes = CamelPrefixes(who);
        c.walkClip = findClip(fam, prefixes, {"walk", "walkA"});
        c.runClip = findClip(fam, prefixes, {"runQuadruped", "run", "runALT", "walkFast"});
        // Idle: sk54_idle_bigbyStandA.anm, else sk54_bigbyStandA_weightShiftA.anm (not the _add layers),
        // else any StandA clip that isn't a transition, turn or additive layer.
        for (auto& w : prefixes) {
            for (const std::string& n : {fam + "idle_" + w + "StandA.anm", fam + w + "StandA_weightShiftA.anm",
                                         fam + w + "StandA_weightShift.anm"})
                if (c.idleClip.empty() && has(n)) c.idleClip = *std::lower_bound(
                    anmNames_.begin(), anmNames_.end(), ToLower(n),
                    [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
            std::string p = ToLower(fam + w + "standa");
            auto it = std::lower_bound(anmNames_.begin(), anmNames_.end(), p,
                                       [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
            for (; c.idleClip.empty() && it != anmNames_.end() && StartsWith(ToLower(*it), p); ++it) {
                std::string li = ToLower(*it);
                if (li.find("_add") == std::string::npos && li.find("_to") == std::string::npos &&
                    li.find("turn") == std::string::npos)
                    c.idleClip = *it;
            }
            if (!c.idleClip.empty()) break;
        }
        // Else a weight shift of another stand (Faith only has sk55_faithStandSmoke_weightShiftA.anm).
        for (auto& w : prefixes) {
            std::string p = ToLower(fam + w + "stand");
            auto it = std::lower_bound(anmNames_.begin(), anmNames_.end(), p,
                                       [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
            for (; c.idleClip.empty() && it != anmNames_.end() && StartsWith(ToLower(*it), p); ++it) {
                std::string li = ToLower(*it);
                if (li.find("_weightshift") != std::string::npos && li.find("_add") == std::string::npos)
                    c.idleClip = *it;
            }
            if (!c.idleClip.empty()) break;
        }
        // Face: "<face>_face_blink.anm" / "<face>_phoneme_default.anm", or for faces that only ship emotion
        // variants (Faith: faith_phoneme_default_angryA.anm, faith_face_blinkHappyB.anm) any clip of that kind.
        auto hasPrefix = [&](const std::string& prefix) {
            std::string lp = ToLower(prefix);
            auto it = std::lower_bound(anmNames_.begin(), anmNames_.end(), lp,
                                       [](const std::string& a, const std::string& b) { return ToLower(a) < b; });
            return it != anmNames_.end() && StartsWith(ToLower(*it), lp);
        };
        for (auto& w : prefixes) {
            std::string f = w;
            f[0] = (char)std::tolower((unsigned char)f[0]);
            if (has(f + "_face_blink.anm") || has(f + "_face_default.anm") || has(f + "_phoneme_default.anm") ||
                hasPrefix(f + "_phoneme_default_") || hasPrefix(f + "_face_")) {
                c.facePrefix = f;
                break;
            }
        }
        if (!c.facePrefix.empty()) {
            std::string p = ToLower(c.facePrefix + "_phoneme_default_");
            for (auto& n : anmNames_) {
                std::string ln = ToLower(n);
                if (StartsWith(ln, p) && ln.find("smoking") == std::string::npos)
                    c.emotions.push_back(n.substr(p.size(), n.size() - p.size() - 4));
            }
        }
        if (!c.walkClip.empty() && !familyDefault.count(c.family)) familyDefault[c.family] = c;
        characters_.push_back(std::move(c));
    }
    // Same family = same skeleton: borrow a walk/run from a sibling (sk54_crane_walk drives any sk54 man).
    std::map<int, std::string> familyRun, familyIdle;
    for (auto& c : characters_) {
        if (!c.runClip.empty() && c.runClip.find("Quadruped") == std::string::npos && !familyRun.count(c.family))
            familyRun[c.family] = c.runClip;
        if (!c.idleClip.empty() && !familyIdle.count(c.family)) familyIdle[c.family] = c.idleClip;
    }
    for (auto& c : characters_) {
        auto it = familyDefault.find(c.family);
        if (it != familyDefault.end() && c.walkClip.empty()) c.walkClip = it->second.walkClip;
        auto r = familyRun.find(c.family);
        if (r != familyRun.end() && c.runClip.empty()) c.runClip = r->second;
        auto i = familyIdle.find(c.family);  // a standing pose beats a T-pose
        if (i != familyIdle.end() && c.idleClip.empty()) c.idleClip = i->second;
    }
    std::sort(characters_.begin(), characters_.end(),
              [](const CharacterInfo& a, const CharacterInfo& b) { return ToLower(a.display) < ToLower(b.display); });

    // The same scene file ships in several episodes with different contents (adv_barTripTrap.scene is in
    // Fables101, 102 and 103), so a location is (scene, episode), not just the name.
    std::set<std::string> seen;
    for (auto& arch : archives_) for (auto& e : arch->Entries()) {
        std::string ln = ToLower(e.name);
        if (!(StartsWith(ln, "adv_") && EndsWith(ln, ".scene"))) continue;
        SceneInfo s;
        s.scene = e.name;
        s.episode = EpisodeOf(arch->Path());
        if (!seen.insert(ln + "|" + s.episode).second) continue;
        std::string n = e.name.substr(4, e.name.size() - 10);
        s.display = Humanize(n);
        // Recaps, credits and "next time" teasers aren't playable locations.
        if (ln.find("previouslyon") != std::string::npos || ln.find("nexttimeon") != std::string::npos ||
            ln.find("credits") != std::string::npos)
            continue;
        scenes_.push_back(s);
    }
    std::sort(scenes_.begin(), scenes_.end(), [](const SceneInfo& a, const SceneInfo& b) {
        return a.episode != b.episode ? a.episode < b.episode : a.display < b.display;
    });
}

// ===================================================================================== WAV
bool ParseWav(const Bytes& f, WavInfo& out) {
    if (f.size() < 12 || memcmp(f.data(), "RIFF", 4) || memcmp(f.data() + 8, "WAVE", 4)) return false;
    size_t p = 12;
    bool haveFmt = false;
    while (p + 8 <= f.size()) {
        uint32_t sz = Rd<uint32_t>(&f[p + 4]);
        const uint8_t* body = &f[p + 8];
        if (!memcmp(&f[p], "fmt ", 4) && sz >= 16) {
            out.format = Rd<uint16_t>(body);
            out.channels = Rd<uint16_t>(body + 2);
            out.sampleRate = Rd<uint32_t>(body + 4);
            out.blockAlign = Rd<uint16_t>(body + 12);
            out.bitsPerSample = Rd<uint16_t>(body + 14);
            out.fmtChunk.assign(body, body + sz);
            if (out.fmtChunk.size() < 18) out.fmtChunk.resize(18, 0);  // WAVEFORMATEX.cbSize
            haveFmt = true;
        } else if (!memcmp(&f[p], "data", 4)) {
            out.data = body;
            out.dataSize = (uint32_t)std::min<size_t>(sz, f.size() - (p + 8));
        }
        p += 8 + sz + (sz & 1);
    }
    return haveFmt && out.data;
}

// ===================================================================================== VTF
static size_t VtfImageSize(int fmt, uint32_t w, uint32_t h) {
    w = std::max(1u, w);
    h = std::max(1u, h);
    switch (fmt) {
        case 13: case 20: return ((w + 3) / 4) * ((h + 3) / 4) * 8;            // DXT1
        case 14: case 15: return ((w + 3) / 4) * ((h + 3) / 4) * 16;           // DXT3/5
        case 0: case 1: case 11: case 12: case 16: case 23: return w * h * 4;
        case 2: case 3: case 9: case 10: return w * h * 3;
        case 4: case 6: case 17: case 18: case 19: case 21: case 22: return w * h * 2;
        case 5: case 7: case 8: return w * h;
        case 24: return w * h * 8;
        default: return 0;
    }
}

bool ParseVtf(const Bytes& f, VtfImage& out) {
    if (f.size() < 64 || memcmp(f.data(), "VTF\0", 4)) return false;
    uint32_t minor = Rd<uint32_t>(&f[8]), headerSize = Rd<uint32_t>(&f[12]);
    uint32_t w = Rd<uint16_t>(&f[16]), h = Rd<uint16_t>(&f[18]), flags = Rd<uint32_t>(&f[20]);
    uint32_t frames = std::max<uint32_t>(1, Rd<uint16_t>(&f[24]));
    int fmt = Rd<int32_t>(&f[52]);
    uint32_t mips = f[56];
    int lowFmt = Rd<int32_t>(&f[57]);
    uint32_t lowW = f[61], lowH = f[62];
    uint32_t depth = minor >= 2 ? std::max<uint32_t>(1, Rd<uint16_t>(&f[63])) : 1;
    uint32_t faces = (flags & 0x4000) ? 6 : 1;
    size_t start = 0;
    if (minor >= 3) {
        uint32_t nres = Rd<uint32_t>(&f[68]);
        for (uint32_t i = 0; i < nres && 80 + i * 8 + 8 <= f.size(); ++i) {
            const uint8_t* r = &f[80 + i * 8];
            if (r[0] == 0x30 && r[1] == 0 && r[2] == 0) start = Rd<uint32_t>(r + 4);
        }
        if (!start) return false;
    } else {
        start = headerSize + (lowFmt >= 0 ? VtfImageSize(lowFmt, lowW, lowH) : 0);
    }
    size_t off = start;
    for (int m = (int)mips - 1; m >= 1; --m) off += VtfImageSize(fmt, w >> m, h >> m) * frames * faces * depth;
    size_t sz = VtfImageSize(fmt, w, h);
    if (!sz || off + sz > f.size()) return false;
    const uint8_t* src = &f[off];
    out.width = w;
    out.height = h;
    switch (fmt) {
        case 13: case 20: out.format = VtfImage::DXT1; out.pixels.assign(src, src + sz); return true;
        case 14: out.format = VtfImage::DXT3; out.pixels.assign(src, src + sz); return true;
        case 15: out.format = VtfImage::DXT5; out.pixels.assign(src, src + sz); return true;
        default: break;
    }
    out.format = VtfImage::BGRA8;
    out.pixels.resize((size_t)w * h * 4);
    uint8_t* d = out.pixels.data();
    for (size_t i = 0; i < (size_t)w * h; ++i, d += 4) {
        const uint8_t* s;
        switch (fmt) {
            case 12: s = src + i * 4; d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = s[3]; break;   // BGRA8888
            case 16: s = src + i * 4; d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = 255; break;    // BGRX8888
            case 0: s = src + i * 4; d[0] = s[2]; d[1] = s[1]; d[2] = s[0]; d[3] = s[3]; break;    // RGBA8888
            case 1: s = src + i * 4; d[0] = s[1]; d[1] = s[2]; d[2] = s[3]; d[3] = s[0]; break;    // ABGR8888
            case 11: s = src + i * 4; d[0] = s[3]; d[1] = s[2]; d[2] = s[1]; d[3] = s[0]; break;   // ARGB8888
            case 2: case 9: s = src + i * 3; d[0] = s[2]; d[1] = s[1]; d[2] = s[0]; d[3] = 255; break;
            case 3: case 10: s = src + i * 3; d[0] = s[0]; d[1] = s[1]; d[2] = s[2]; d[3] = 255; break;
            case 5: s = src + i; d[0] = d[1] = d[2] = s[0]; d[3] = 255; break;                    // I8
            case 6: s = src + i * 2; d[0] = d[1] = d[2] = s[0]; d[3] = s[1]; break;               // IA88
            case 8: s = src + i; d[0] = d[1] = d[2] = 255; d[3] = s[0]; break;                    // A8
            default: return false;
        }
    }
    return true;
}

std::string VmtBaseTexture(const std::string& vmt) {
    std::string l = ToLower(vmt);
    size_t k = l.find("$basetexture");
    while (k != std::string::npos && k + 12 < l.size() && (std::isalnum((unsigned char)l[k + 12]) || l[k + 12] == '_'))
        k = l.find("$basetexture", k + 1);  // skip $basetexture2, $basetexturetransform
    if (k == std::string::npos) return "";
    size_t p = k + 12;
    if (p < l.size() && l[p] == '"') ++p;
    while (p < l.size() && (l[p] == ' ' || l[p] == '\t')) ++p;
    bool quoted = p < l.size() && l[p] == '"';
    if (quoted) ++p;
    size_t e = p;
    while (e < l.size() && (quoted ? l[e] != '"' : !std::isspace((unsigned char)l[e]))) ++e;
    return NormPath(vmt.substr(p, e - p));
}

// ===================================================================================== Source MDL
namespace {
struct M34 {
    float m[3][4];
};
M34 QuatMatrix(const Quat& q, const Vec3& p) {
    M34 r;
    r.m[0][0] = 1 - 2 * q.y * q.y - 2 * q.z * q.z; r.m[1][0] = 2 * q.x * q.y + 2 * q.w * q.z; r.m[2][0] = 2 * q.x * q.z - 2 * q.w * q.y;
    r.m[0][1] = 2 * q.x * q.y - 2 * q.w * q.z; r.m[1][1] = 1 - 2 * q.x * q.x - 2 * q.z * q.z; r.m[2][1] = 2 * q.y * q.z + 2 * q.w * q.x;
    r.m[0][2] = 2 * q.x * q.z + 2 * q.w * q.y; r.m[1][2] = 2 * q.y * q.z - 2 * q.w * q.x; r.m[2][2] = 1 - 2 * q.x * q.x - 2 * q.y * q.y;
    r.m[0][3] = p.x; r.m[1][3] = p.y; r.m[2][3] = p.z;
    return r;
}
M34 Concat(const M34& a, const M34& b) {
    M34 r;
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 4; ++j)
            r.m[i][j] = a.m[i][0] * b.m[0][j] + a.m[i][1] * b.m[1][j] + a.m[i][2] * b.m[2][j];
        r.m[i][3] += a.m[i][3];
    }
    return r;
}
Vec3 XformPoint(const M34& a, const Vec3& v) {
    return {a.m[0][0] * v.x + a.m[0][1] * v.y + a.m[0][2] * v.z + a.m[0][3],
            a.m[1][0] * v.x + a.m[1][1] * v.y + a.m[1][2] * v.z + a.m[1][3],
            a.m[2][0] * v.x + a.m[2][1] * v.y + a.m[2][2] * v.z + a.m[2][3]};
}
Vec3 XformDir(const M34& a, const Vec3& v) {
    return {a.m[0][0] * v.x + a.m[0][1] * v.y + a.m[0][2] * v.z, a.m[1][0] * v.x + a.m[1][1] * v.y + a.m[1][2] * v.z,
            a.m[2][0] * v.x + a.m[2][1] * v.y + a.m[2][2] * v.z};
}
Quat EulerQuat(float x, float y, float z) {  // Source AngleQuaternion(RadianEuler)
    float sr = std::sin(x * 0.5f), cr = std::cos(x * 0.5f), sp = std::sin(y * 0.5f), cp = std::cos(y * 0.5f);
    float sy = std::sin(z * 0.5f), cy = std::cos(z * 0.5f);
    return {sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy};
}
float Half(uint16_t h) {
    uint32_t s = (h >> 15) & 1, e = (h >> 10) & 31, m = h & 1023;
    if (e == 0) return (s ? -1.f : 1.f) * std::ldexp((float)m, -24);
    if (e == 31) return s ? -1e30f : 1e30f;
    return (s ? -1.f : 1.f) * std::ldexp((float)(m | 1024), (int)e - 25);
}
Quat Quat48(const uint8_t* p) {
    uint16_t a = Rd<uint16_t>(p), b = Rd<uint16_t>(p + 2), c = Rd<uint16_t>(p + 4);
    Quat q;
    q.x = ((int)a - 32768) * (1.0f / 32768.0f);
    q.y = ((int)b - 32768) * (1.0f / 32768.0f);
    q.z = ((int)(c & 0x7fff) - 16384) * (1.0f / 16384.0f);
    q.w = std::sqrt(std::max(0.0f, 1 - q.x * q.x - q.y * q.y - q.z * q.z));
    if (c & 0x8000) q.w = -q.w;
    return q;
}
Quat Quat64(const uint8_t* p) {
    uint64_t v = Rd<uint64_t>(p);
    Quat q;
    q.x = ((int)(v & 0x1fffff) - 1048576) * (1.0f / 1048576.5f);
    q.y = ((int)((v >> 21) & 0x1fffff) - 1048576) * (1.0f / 1048576.5f);
    q.z = ((int)((v >> 42) & 0x1fffff) - 1048576) * (1.0f / 1048576.5f);
    q.w = std::sqrt(std::max(0.0f, 1 - q.x * q.x - q.y * q.y - q.z * q.z));
    if (v >> 63) q.w = -q.w;
    return q;
}
// mstudioanimvalue_t run-length stream, frame k
float AnimValue(const uint8_t* v, int frame, float scale) {
    int k = frame;
    for (int guard = 0; guard < 10000; ++guard) {
        uint8_t valid = v[0], total = v[1];
        if (total == 0) return 0;
        if (total > k) {
            int16_t val = valid > k ? Rd<int16_t>(v + 2 * (k + 1)) : Rd<int16_t>(v + 2 * valid);
            return val * scale;
        }
        k -= total;
        v += 2 * (valid + 1);
    }
    return 0;
}
struct Bone {
    std::string name;
    int parent;
    Vec3 pos, rot, posScale, rotScale;
    Quat quat;
    M34 poseToBone;
};
}  // namespace

bool LoadSourceModel(const SourceFileSystem& sfs, const std::string& mdlPath, const std::string& sequence,
                     SourceModel& out, std::string* error) {
    auto fail = [&](const char* why) {
        if (error) *error = why;
        return false;
    };
    std::string stem = NormPath(mdlPath);
    if (EndsWith(stem, ".mdl")) stem.resize(stem.size() - 4);
    Bytes mdl, vvd, vtx;
    if (!sfs.Read(stem + ".mdl", mdl)) return fail("mdl not found");
    if (!sfs.Read(stem + ".vvd", vvd)) return fail("vvd not found");
    if (!sfs.Read(stem + ".dx90.vtx", vtx) && !sfs.Read(stem + ".dx80.vtx", vtx)) return fail("vtx not found");
    if (mdl.size() < 408 || memcmp(mdl.data(), "IDST", 4)) return fail("not an IDST mdl");
    int version = Rd<int32_t>(&mdl[4]);
    if (version < 44 || version > 49) return fail("unsupported mdl version");
    const uint8_t* H = mdl.data();
    auto I = [&](size_t o) { return Rd<int32_t>(H + o); };
    out.name = stem;

    // ---- bones (216 bytes each)
    std::vector<Bone> bones(I(156));
    for (size_t b = 0; b < bones.size(); ++b) {
        const uint8_t* p = H + I(160) + b * 216;
        Bone& B = bones[b];
        B.name = (const char*)p + Rd<int32_t>(p);
        B.parent = Rd<int32_t>(p + 4);
        B.pos = {Rd<float>(p + 32), Rd<float>(p + 36), Rd<float>(p + 40)};
        B.quat = {Rd<float>(p + 44), Rd<float>(p + 48), Rd<float>(p + 52), Rd<float>(p + 56)};
        B.rot = {Rd<float>(p + 60), Rd<float>(p + 64), Rd<float>(p + 68)};
        B.posScale = {Rd<float>(p + 72), Rd<float>(p + 76), Rd<float>(p + 80)};
        B.rotScale = {Rd<float>(p + 84), Rd<float>(p + 88), Rd<float>(p + 92)};
        memcpy(B.poseToBone.m, p + 96, 48);
    }
    auto worldFrom = [&](const std::vector<Quat>& q, const std::vector<Vec3>& pos) {
        std::vector<M34> w(bones.size());
        for (size_t b = 0; b < bones.size(); ++b) {
            M34 local = QuatMatrix(q[b], pos[b]);
            w[b] = bones[b].parent >= 0 ? Concat(w[bones[b].parent], local) : local;
        }
        return w;
    };
    std::vector<Quat> refQ(bones.size()), animQ(bones.size());
    std::vector<Vec3> refP(bones.size()), animP(bones.size());
    for (size_t b = 0; b < bones.size(); ++b) { refQ[b] = animQ[b] = bones[b].quat; refP[b] = animP[b] = bones[b].pos; }
    {   // self-check from the field note: world bind * poseToBone == identity
        auto w = worldFrom(refQ, refP);
        for (size_t b = 0; b < bones.size(); ++b) {
            M34 c = Concat(w[b], bones[b].poseToBone);
            for (int i = 0; i < 3; ++i)
                for (int j = 0; j < 4; ++j)
                    out.worstBindError = std::max(out.worstBindError, std::fabs(c.m[i][j] - (i == j ? 1.f : 0.f)));
        }
    }

    // ---- sequences (212 bytes) and frame 0 of the requested one
    int numSeq = I(188), seqIndex = I(192), animIndex = I(184);
    int pick = -1;
    for (int s = 0; s < numSeq; ++s) {
        const uint8_t* sp = H + seqIndex + s * 212;
        std::string label = (const char*)sp + Rd<int32_t>(sp + 4);
        out.sequences.push_back(label);
        if (pick < 0 && ToLower(label) == ToLower(sequence)) pick = s;
    }
    for (const char* fallback : {"idle01", "idle", "draw"})
        for (int s = 0; pick < 0 && s < numSeq; ++s)
            if (ToLower(out.sequences[s]) == fallback) pick = s;
    out.poseSource = "reference pose";
    if (pick >= 0) {
        const uint8_t* sp = H + seqIndex + pick * 212;
        int animDescIdx = Rd<int16_t>(sp + Rd<int32_t>(sp + 60));  // first blend cell
        const uint8_t* ad = H + animIndex + animDescIdx * 100;
        int flags = Rd<int32_t>(ad + 12);
        int block = Rd<int32_t>(ad + 52), aindex = Rd<int32_t>(ad + 56);
        if (Rd<int32_t>(ad + 84) != 0) {  // sectioned: section 0 holds frame 0
            const uint8_t* sec = ad + Rd<int32_t>(ad + 80);
            block = Rd<int32_t>(sec);
            aindex = Rd<int32_t>(sec + 4);
        }
        const uint8_t* data = nullptr;
        Bytes ani;
        if (block == 0) {
            data = ad + aindex;
        } else {
            std::string aniName = (const char*)H + I(348);
            const uint8_t* bt = H + I(356) + block * 8;
            if (sfs.Read(aniName, ani)) data = ani.data() + Rd<int32_t>(bt) + aindex;
        }
        if (flags & 0x40) {
            Log("[assets] %s: sequence %s is frame-by-bone (0x40); using the reference pose", stem.c_str(),
                out.sequences[pick].c_str());
        } else if (data) {
            const uint8_t* a = data;
            for (int guard = 0; guard < 512; ++guard) {
                int bone = a[0], fl = a[1];
                int16_t next = Rd<int16_t>(a + 2);
                const uint8_t* p = a + 4;
                if (bone < (int)bones.size() && !(fl & 0x10)) {  // skip delta entries
                    Bone& B = bones[bone];
                    if (fl & 0x02) { animQ[bone] = Quat48(p); p += 6; }
                    else if (fl & 0x20) { animQ[bone] = Quat64(p); p += 8; }
                    else if (fl & 0x08) {
                        float e[3];
                        for (int k = 0; k < 3; ++k) {
                            int16_t o = Rd<int16_t>(p + 2 * k);
                            e[k] = (&B.rot.x)[k] + (o ? AnimValue(p + o, 0, (&B.rotScale.x)[k]) : 0.f);
                        }
                        animQ[bone] = EulerQuat(e[0], e[1], e[2]);
                        p += 6;
                    }
                    if (fl & 0x01) { animP[bone] = {Half(Rd<uint16_t>(p)), Half(Rd<uint16_t>(p + 2)), Half(Rd<uint16_t>(p + 4))}; }
                    else if (fl & 0x04) {
                        for (int k = 0; k < 3; ++k) {
                            int16_t o = Rd<int16_t>(p + 2 * k);
                            (&animP[bone].x)[k] = (&B.pos.x)[k] + (o ? AnimValue(p + o, 0, (&B.posScale.x)[k]) : 0.f);
                        }
                    }
                }
                if (!next) break;
                a += next;
            }
            out.poseSource = "sequence " + out.sequences[pick] + " frame 0";
        }
    }
    std::vector<M34> skin(bones.size());
    {
        auto w = worldFrom(animQ, animP);
        for (size_t b = 0; b < bones.size(); ++b) skin[b] = Concat(w[b], bones[b].poseToBone);
    }

    // ---- materials through the skin table (family 0)
    int numTex = I(204), texIndex = I(208), numCd = I(212), cdIndex = I(216);
    int numSkinRef = I(220), skinIndex = I(228);
    std::vector<std::string> texPaths(numTex);
    for (int t = 0; t < numTex; ++t) {
        const uint8_t* tp = H + texIndex + t * 64;
        std::string name = (const char*)tp + Rd<int32_t>(tp);
        for (int c = 0; c < numCd && texPaths[t].empty(); ++c) {
            std::string dir = (const char*)H + Rd<int32_t>(H + cdIndex + c * 4);
            std::string p = NormPath("materials/" + dir + name + ".vmt");
            if (sfs.Exists(p)) texPaths[t] = p;
        }
    }
    out.materials = texPaths;

    // ---- vertices (VVD, 48 bytes, LOD 0 after fixups)
    if (vvd.size() < 64 || memcmp(vvd.data(), "IDSV", 4)) return fail("bad vvd");
    int numFixups = Rd<int32_t>(&vvd[48]), fixupStart = Rd<int32_t>(&vvd[52]), vertStart = Rd<int32_t>(&vvd[56]);
    int lod0Count = Rd<int32_t>(&vvd[16]);
    std::vector<const uint8_t*> verts;
    if (numFixups > 0) {
        for (int f = 0; f < numFixups; ++f) {
            const uint8_t* fx = &vvd[fixupStart + f * 12];
            if (Rd<int32_t>(fx) < 0) continue;
            int src = Rd<int32_t>(fx + 4), n = Rd<int32_t>(fx + 8);
            for (int k = 0; k < n; ++k) verts.push_back(&vvd[vertStart + (src + k) * 48]);
        }
    } else {
        for (int k = 0; k < lod0Count; ++k) verts.push_back(&vvd[vertStart + k * 48]);
    }
    auto posed = [&](int idx) {
        const uint8_t* v = verts[idx];
        ModelVertex mv;
        Vec3 p{Rd<float>(v + 16), Rd<float>(v + 20), Rd<float>(v + 24)};
        Vec3 n{Rd<float>(v + 28), Rd<float>(v + 32), Rd<float>(v + 36)};
        int nb = std::max(1, (int)v[15]);
        Vec3 sp, sn;
        for (int k = 0; k < nb && k < 3; ++k) {
            float w = Rd<float>(v + 4 * k);
            int b = (int8_t)v[12 + k];
            if (b < 0 || b >= (int)skin.size()) continue;
            sp += XformPoint(skin[b], p) * w;
            sn += XformDir(skin[b], n) * w;
        }
        mv.pos = sp;
        mv.normal = Normalize(sn);
        mv.u = Rd<float>(v + 40);
        mv.v = Rd<float>(v + 44);
        return mv;
    };

    // ---- triangles (VTX), body part 0..n, model 0, LOD 0
    if (vtx.size() < 36) return fail("bad vtx");
    const uint8_t* X = vtx.data();
    int numBodyParts = I(232), bodyPartIndex = I(236);
    int vtxBodyParts = Rd<int32_t>(X + 28), vtxBodyOff = Rd<int32_t>(X + 32);
    bool first = true;
    for (int bp = 0; bp < numBodyParts && bp < vtxBodyParts; ++bp) {
        const uint8_t* mbp = H + bodyPartIndex + bp * 16;
        if (Rd<int32_t>(mbp + 4) < 1) continue;
        const uint8_t* mm = mbp + Rd<int32_t>(mbp + 12);  // model 0 (148 bytes)
        int modelVertBase = Rd<int32_t>(mm + 84) / 48;
        const uint8_t* xbp = X + vtxBodyOff + bp * 8;
        const uint8_t* xm = xbp + Rd<int32_t>(xbp + 4);
        const uint8_t* xl = xm + Rd<int32_t>(xm + 4);  // LOD 0
        int numMeshes = Rd<int32_t>(mm + 72);
        for (int m = 0; m < numMeshes && m < Rd<int32_t>(xl); ++m) {
            const uint8_t* mesh = mm + Rd<int32_t>(mm + 76) + m * 116;
            int meshVertOff = Rd<int32_t>(mesh + 12), mat = Rd<int32_t>(mesh);
            const uint8_t* xmesh = xl + Rd<int32_t>(xl + 4) + m * 9;
            int ngroups = Rd<int32_t>(xmesh);
            // Strip groups are 25 bytes in HL2-era files, 33 in later builds; take whichever fits.
            int sgSize = 25;
            if (ngroups > 0) {
                const uint8_t* sg = xmesh + Rd<int32_t>(xmesh + 4);
                int nIdx = Rd<int32_t>(sg + 8), nStrips = Rd<int32_t>(sg + 16);
                const uint8_t* st = sg + Rd<int32_t>(sg + 20);
                if (nStrips > 0 && (Rd<int32_t>(st) > nIdx || Rd<int32_t>(st) < 0)) sgSize = 33;
            }
            ModelMesh out_mesh;
            int texIdx = mat;
            if (numSkinRef > 0 && mat < numSkinRef) texIdx = Rd<int16_t>(H + skinIndex + mat * 2);
            out_mesh.material = texIdx;
            std::unordered_map<int, uint16_t> remap;
            for (int g = 0; g < ngroups; ++g) {
                const uint8_t* sg = xmesh + Rd<int32_t>(xmesh + 4) + g * sgSize;
                int nVerts = Rd<int32_t>(sg), vertOff = Rd<int32_t>(sg + 4);
                int nIdx = Rd<int32_t>(sg + 8), idxOff = Rd<int32_t>(sg + 12);
                for (int i = 0; i + 2 < nIdx; i += 3) {
                    for (int c = 0; c < 3; ++c) {
                        int vi = Rd<uint16_t>(sg + idxOff + (i + c) * 2);
                        if (vi >= nVerts) continue;
                        int orig = Rd<uint16_t>(sg + vertOff + vi * 9 + 4);
                        int final_ = modelVertBase + meshVertOff + orig;
                        if (final_ < 0 || final_ >= (int)verts.size()) return fail("vertex index out of range");
                        auto it = remap.find(final_);
                        if (it == remap.end()) {
                            it = remap.emplace(final_, (uint16_t)out_mesh.vertices.size()).first;
                            ModelVertex mv = posed(final_);
                            out_mesh.vertices.push_back(mv);
                            if (first) { out.boundsMin = out.boundsMax = mv.pos; first = false; }
                            out.boundsMin = {std::min(out.boundsMin.x, mv.pos.x), std::min(out.boundsMin.y, mv.pos.y), std::min(out.boundsMin.z, mv.pos.z)};
                            out.boundsMax = {std::max(out.boundsMax.x, mv.pos.x), std::max(out.boundsMax.y, mv.pos.y), std::max(out.boundsMax.z, mv.pos.z)};
                        }
                        out_mesh.indices.push_back(it->second);
                    }
                }
            }
            if (!out_mesh.indices.empty()) out.meshes.push_back(std::move(out_mesh));
        }
    }
    if (out.meshes.empty()) return fail("no triangles");
    return true;
}

// ===================================================================================== bridge
AssetBridge& AssetBridge::Get() {
    static AssetBridge b;
    return b;
}

bool AssetBridge::Init(const Paths& p) {
    DWORD t0 = GetTickCount();
    bool okSrc = source_.Mount(p.gmodRoot);
    bool okTT = catalog_.Build(p.twauRoot + "\\Pack");
    Log("[assets] GMod: %s (%zu VPKs). TWAU: %s (%zu archives, %zu files, %zu characters, %zu scenes) in %lu ms",
        okSrc ? "ok" : "MISSING", source_.ArchiveCount(), okTT ? "ok" : "MISSING", catalog_.ArchiveCount(),
        catalog_.FileCount(), catalog_.Characters().size(), catalog_.Scenes().size(), GetTickCount() - t0);
    ready_ = okSrc && okTT;
    return ready_;
}

}  // namespace gm
