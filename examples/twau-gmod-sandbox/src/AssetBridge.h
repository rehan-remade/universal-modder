// AssetBridge: reads Garry's Mod / Source VPKs and The Wolf Among Us .ttarch2 archives straight from the
// user's installs, and builds the catalogs the sandbox needs (characters, skeleton families, locomotion
// clips, face clips, scenes). Nothing is copied out of the games.
#pragma once
#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "Common.h"

namespace gm {

using Bytes = std::vector<uint8_t>;
std::string ToLower(std::string s);

// ======================================================================= Source VPK (v1 and v2)
class VpkArchive {
public:
    bool Open(const std::string& dirVpkPath);
    bool Contains(const std::string& path) const;
    bool Read(const std::string& path, Bytes& out) const;
    void List(std::vector<std::string>& out) const;
    const std::string& DirPath() const { return dirPath_; }

private:
    struct Entry {
        uint32_t crc;
        uint16_t archive;  // 0x7fff: data follows the tree inside the _dir file
        uint32_t offset, length;
        Bytes preload;
    };
    std::string dirPath_, stem_;  // stem_ = path without "_dir.vpk"
    uint32_t treeEnd_ = 0;        // absolute offset of the embedded data block
    std::unordered_map<std::string, Entry> entries_;  // key: lower-case path with '/'
};

// All Source content a GMod install exposes: loose files first (garrysmod\, sourceengine\), then VPKs.
class SourceFileSystem {
public:
    bool Mount(const std::string& gmodRoot);
    bool Read(const std::string& path, Bytes& out) const;
    bool Exists(const std::string& path) const;
    size_t ArchiveCount() const { return vpks_.size(); }

private:
    std::vector<std::string> looseRoots_;
    std::vector<std::unique_ptr<VpkArchive>> vpks_;
};

// ======================================================================= Telltale .ttarch2 (NCTT / ZCTT + 3ATT)
class TTArchive {
public:
    struct Entry {
        std::string name;
        uint64_t crc = 0, offset = 0;
        uint32_t size = 0;
    };
    bool Open(const std::string& path);
    const std::vector<Entry>& Entries() const { return entries_; }
    const std::string& Path() const { return path_; }
    bool Read(const std::string& name, Bytes& out);

private:
    bool ReadStream(uint64_t pos, uint64_t len, uint8_t* dst);  // over the (decompressed) inner stream
    bool LoadChunk(uint32_t index);
    std::string path_;
    FILE* file_ = nullptr;
    bool compressed_ = false;
    uint32_t chunkSize_ = 0x10000;
    std::vector<uint64_t> chunkOffsets_;  // ZCTT
    uint64_t rawBase_ = 0;                // NCTT: file offset of the inner stream
    uint64_t dataBase_ = 0;               // inner offset where file data begins
    std::vector<Entry> entries_;
    std::unordered_map<std::string, size_t> byName_;
    int cachedChunk_ = -1;
    Bytes chunkCache_;
    std::mutex mu_;
};

// ======================================================================= TWAU catalog
enum class BodyPlan { Biped, Quadruped, Bird, Prop };

struct CharacterInfo {
    std::string prop;        // "sk54_bigby.prop": what AgentCreate takes
    std::string skeleton;    // "sk54_bigby"
    std::string display;     // "Bigby"
    int family = 0;          // 54
    BodyPlan plan = BodyPlan::Biped;
    std::string episode;     // archive the prop came from, e.g. "Fables101"
    std::string walkClip, runClip, idleClip;  // best locomotion clips (.anm), may be empty
    std::string facePrefix;  // "bigby" if <face>_face_*.anm exist
    std::vector<std::string> emotions;        // "angryA", "happyA", ... (phoneme_default_<emotion>)
};

struct SceneInfo {
    std::string scene;    // "adv_barTripTrap.scene"
    std::string display;  // "Bar Trip Trap"
    std::string episode;  // "Fables101" .. "Fables105"
};

class TTCatalog {
public:
    bool Build(const std::string& packDir);  // lists every .ttarch2; reads only the name tables
    const std::vector<CharacterInfo>& Characters() const { return characters_; }
    const std::vector<SceneInfo>& Scenes() const { return scenes_; }
    const CharacterInfo* FindBySkeleton(const std::string& skeleton) const;
    bool HasFile(const std::string& name) const { return files_.count(ToLower(name)) != 0; }
    std::vector<std::string> ClipsFor(const std::string& skeleton, size_t max = 400) const;
    std::vector<std::string> FaceChannels(const std::string& facePrefix) const;
    size_t FileCount() const { return files_.size(); }
    size_t ArchiveCount() const { return archives_.size(); }
    bool Read(const std::string& name, Bytes& out);  // pulls one file out of whichever archive has it
    std::vector<std::string> Find(const std::string& substring) const;  // names containing it (any case)

private:
    void Classify();
    std::vector<std::unique_ptr<TTArchive>> archives_;
    std::unordered_map<std::string, std::pair<size_t, size_t>> files_;  // lower name -> (archive, entry)
    std::vector<std::string> anmNames_;  // every .anm, original case, sorted
    std::vector<CharacterInfo> characters_;
    std::vector<SceneInfo> scenes_;
};

// ======================================================================= Source assets
struct WavInfo {
    uint16_t format = 0, channels = 0, bitsPerSample = 0, blockAlign = 0;
    uint32_t sampleRate = 0;
    Bytes fmtChunk;  // raw WAVEFORMATEX(+extra) for XAudio2 (PCM and MS-ADPCM)
    const uint8_t* data = nullptr;
    uint32_t dataSize = 0;
};
bool ParseWav(const Bytes& file, WavInfo& out);

struct VtfImage {
    uint32_t width = 0, height = 0;
    enum Format { BGRA8, DXT1, DXT3, DXT5 } format = BGRA8;
    Bytes pixels;  // largest mip, frame 0, face 0; BGRA8 is converted from the other raw formats
};
bool ParseVtf(const Bytes& file, VtfImage& out);
std::string VmtBaseTexture(const std::string& vmtText);  // "$basetexture" value, or ""

struct ModelVertex {
    Vec3 pos, normal;
    float u = 0, v = 0;
};
struct ModelMesh {
    int material = 0;  // index into SourceModel::materials (already through the skin table, family 0)
    std::vector<ModelVertex> vertices;
    std::vector<uint16_t> indices;  // triangle list
};
struct SourceModel {
    std::string name;
    std::vector<std::string> materials;  // full "materials/....vmt" paths that exist
    std::vector<ModelMesh> meshes;       // posed with frame 0 of the requested sequence
    std::vector<std::string> sequences;
    Vec3 boundsMin, boundsMax;
    std::string poseSource;              // "sequence idle01 frame 0" or "reference pose"
    float worstBindError = 0;            // self-check: |boneWorld * poseToBone - I|
};
// Loads models/x.mdl + .vvd + .dx90.vtx, body part 0 / model 0 of each part, LOD 0.
bool LoadSourceModel(const SourceFileSystem& fs, const std::string& mdlPath, const std::string& sequence,
                     SourceModel& out, std::string* error = nullptr);

// ======================================================================= the process-wide bridge
class AssetBridge {
public:
    static AssetBridge& Get();
    bool Init(const Paths& paths);  // mounts VPKs, builds the TWAU catalog (a second or two)
    SourceFileSystem& Source() { return source_; }
    TTCatalog& Telltale() { return catalog_; }
    bool Ready() const { return ready_; }

private:
    SourceFileSystem source_;
    TTCatalog catalog_;
    bool ready_ = false;
};

}  // namespace gm
