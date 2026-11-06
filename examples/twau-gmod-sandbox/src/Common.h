// Shared math, logging and paths for the TWAU GMod sandbox.
#pragma once
#include <windows.h>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <string>
#include <vector>

namespace gm {

// ---------------------------------------------------------------- paths
// Defaults from the target PC; overridable in gmod\gmod_sandbox.ini next to the exe.
struct Paths {
    std::string gmodRoot = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\GarrysMod";
    std::string twauRoot = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\The Wolf Among Us";
    std::string modDir;  // <twauRoot>\gmod  (lua, log, screenshots)
};
Paths& GetPaths();

// ---------------------------------------------------------------- log (gmod\gmod_sandbox.log)
void Log(const char* fmt, ...);
std::vector<std::string> RecentLog(size_t maxLines);  // for the in-game console

// ---------------------------------------------------------------- math
constexpr float kPi = 3.14159265358979f;
inline float Deg2Rad(float d) { return d * kPi / 180.0f; }
inline float Clamp(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

struct Vec3 {
    float x = 0, y = 0, z = 0;
    Vec3() = default;
    Vec3(float X, float Y, float Z) : x(X), y(Y), z(Z) {}
    Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    Vec3 operator*(float s) const { return {x * s, y * s, z * s}; }
    Vec3& operator+=(const Vec3& o) { x += o.x; y += o.y; z += o.z; return *this; }
    Vec3& operator-=(const Vec3& o) { x -= o.x; y -= o.y; z -= o.z; return *this; }
    Vec3& operator*=(float s) { x *= s; y *= s; z *= s; return *this; }
};
inline float Dot(const Vec3& a, const Vec3& b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline Vec3 Cross(const Vec3& a, const Vec3& b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}
inline float Length(const Vec3& v) { return std::sqrt(Dot(v, v)); }
inline Vec3 Normalize(const Vec3& v) { float l = Length(v); return l > 1e-6f ? v * (1.0f / l) : Vec3(0, 0, 0); }

struct Quat {
    float x = 0, y = 0, z = 0, w = 1;
    Quat() = default;
    Quat(float X, float Y, float Z, float W) : x(X), y(Y), z(Z), w(W) {}
    Quat operator*(const Quat& b) const {
        return {w * b.x + x * b.w + y * b.z - z * b.y, w * b.y - x * b.z + y * b.w + z * b.x,
                w * b.z + x * b.y - y * b.x + z * b.w, w * b.w - x * b.x - y * b.y - z * b.z};
    }
    Vec3 Rotate(const Vec3& v) const {
        Vec3 u(x, y, z);
        Vec3 t = Cross(u, v) * 2.0f;
        return v + t * w + Cross(u, t);
    }
    static Quat AxisAngle(const Vec3& axis, float rad) {
        Vec3 a = Normalize(axis);
        float s = std::sin(rad * 0.5f);
        return {a.x * s, a.y * s, a.z * s, std::cos(rad * 0.5f)};
    }
};
inline Quat Normalize(const Quat& q) {
    float l = std::sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w);
    return l > 1e-8f ? Quat(q.x / l, q.y / l, q.z / l, q.w / l) : Quat();
}
// Shortest rotation taking unit vector a onto unit vector b.
inline Quat FromTo(const Vec3& a, const Vec3& b) {
    Vec3 c = Cross(a, b);
    float d = Dot(a, b);
    if (d < -0.9999f) {
        Vec3 axis = std::fabs(a.x) < 0.9f ? Cross(a, Vec3(1, 0, 0)) : Cross(a, Vec3(0, 1, 0));
        return Quat::AxisAngle(axis, kPi);
    }
    return Normalize(Quat(c.x, c.y, c.z, 1.0f + d));
}

// Row-major 4x4 in D3D9 convention (row vectors, v * M).
struct Mat4 {
    float m[4][4];
    static Mat4 Identity() {
        Mat4 r{};
        for (int i = 0; i < 4; ++i) r.m[i][i] = 1.0f;
        return r;
    }
    Mat4 operator*(const Mat4& b) const {
        Mat4 r{};
        for (int i = 0; i < 4; ++i)
            for (int j = 0; j < 4; ++j)
                for (int k = 0; k < 4; ++k) r.m[i][j] += m[i][k] * b.m[k][j];
        return r;
    }
    static Mat4 PerspectiveFovLH(float fovY, float aspect, float zn, float zf) {
        Mat4 r{};
        float ys = 1.0f / std::tan(fovY * 0.5f);
        r.m[0][0] = ys / aspect;
        r.m[1][1] = ys;
        r.m[2][2] = zf / (zf - zn);
        r.m[2][3] = 1.0f;
        r.m[3][2] = -zn * zf / (zf - zn);
        return r;
    }
};

// ---------------------------------------------------------------- input helpers
bool GameWindowFocused();
HWND GameWindow();

}  // namespace gm
