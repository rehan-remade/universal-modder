// GMod sounds straight out of the user's VPKs, played with XAudio2 (PCM and MS-ADPCM .wav).
#include <xaudio2.h>

#include <map>
#include <mutex>

#include "Sandbox.h"

namespace gm {
namespace audio {

namespace {
IXAudio2* g_xa = nullptr;
IXAudio2MasteringVoice* g_master = nullptr;
std::mutex g_mu;
struct Clip {
    Bytes file;
    WavInfo wav;
};
std::map<std::string, std::unique_ptr<Clip>> g_clips;
struct Voice {
    IXAudio2SourceVoice* v;
    int id;
    bool loop;
};
std::vector<Voice> g_voices;
int g_nextId = 1;

Clip* Load(const std::string& path) {
    auto it = g_clips.find(path);
    if (it != g_clips.end()) return it->second.get();
    auto c = std::make_unique<Clip>();
    if (!AssetBridge::Get().Source().Read(path, c->file) || !ParseWav(c->file, c->wav) ||
        (c->wav.format != 1 && c->wav.format != 2)) {
        Log("[audio] cannot play %s (missing, or not PCM/ADPCM)", path.c_str());
        g_clips[path] = nullptr;
        return nullptr;
    }
    return (g_clips[path] = std::move(c)).get();
}

void Reap() {
    for (size_t i = 0; i < g_voices.size();) {
        XAUDIO2_VOICE_STATE st;
        g_voices[i].v->GetState(&st, XAUDIO2_VOICE_NOSAMPLESPLAYED);
        if (!g_voices[i].loop && st.BuffersQueued == 0) {
            g_voices[i].v->DestroyVoice();
            g_voices.erase(g_voices.begin() + i);
        } else {
            ++i;
        }
    }
}

int Start(const std::string& path, float volume, bool loop) {
    std::lock_guard<std::mutex> lk(g_mu);
    if (!g_xa) return 0;
    Reap();
    Clip* c = Load(path);
    if (!c) return 0;
    IXAudio2SourceVoice* v = nullptr;
    if (FAILED(g_xa->CreateSourceVoice(&v, (const WAVEFORMATEX*)c->wav.fmtChunk.data()))) return 0;
    XAUDIO2_BUFFER b{};
    b.AudioBytes = c->wav.dataSize;
    b.pAudioData = c->wav.data;
    b.Flags = XAUDIO2_END_OF_STREAM;
    if (loop) b.LoopCount = XAUDIO2_LOOP_INFINITE;
    v->SubmitSourceBuffer(&b);
    v->SetVolume(volume);
    v->Start();
    g_voices.push_back({v, g_nextId, loop});
    return g_nextId++;
}
}  // namespace

bool Init() {
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(XAudio2Create(&g_xa, 0, XAUDIO2_DEFAULT_PROCESSOR)) ||
        FAILED(g_xa->CreateMasteringVoice(&g_master))) {
        Log("[audio] XAudio2 unavailable; GMod sounds are off");
        g_xa = nullptr;
        return false;
    }
    return true;
}

void Play(const std::string& path, float volume) { Start(path, volume, false); }
int PlayLoop(const std::string& path, float volume) { return Start(path, volume, true); }

void Stop(int id) {
    std::lock_guard<std::mutex> lk(g_mu);
    for (size_t i = 0; i < g_voices.size(); ++i)
        if (g_voices[i].id == id) {
            g_voices[i].v->Stop();
            g_voices[i].v->DestroyVoice();
            g_voices.erase(g_voices.begin() + i);
            return;
        }
}

}  // namespace audio
}  // namespace gm
