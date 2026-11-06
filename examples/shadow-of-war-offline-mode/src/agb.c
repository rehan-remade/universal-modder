#include "agb.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

static void put(Agb *b, const void *d, size_t n)
{
    if (b->n + n > b->cap) {
        size_t c = b->cap ? b->cap * 2 : 256;
        while (c < b->n + n) c *= 2;
        b->p = realloc(b->p, c); b->cap = c;
    }
    memcpy(b->p + b->n, d, n); b->n += n;
}
static void put1(Agb *b, unsigned v) { unsigned char c = (unsigned char)v; put(b, &c, 1); }
static void putbe(Agb *b, uint64_t v, int bytes) { for (int i = bytes - 1; i >= 0; i--) put1(b, (unsigned)(v >> (8 * i)) & 0xFF); }

/* containers and strings pick the smallest length form */
static void sized(Agb *b, unsigned base, uint32_t n)
{
    if (n <= 0xFF) { put1(b, base); putbe(b, n, 1); }
    else if (n <= 0xFFFF) { put1(b, base + 1); putbe(b, n, 2); }
    else { put1(b, base + 2); putbe(b, n, 4); }
}

void agb_free(Agb *b) { free(b->p); b->p = NULL; b->n = b->cap = 0; }
void agb_map(Agb *b, unsigned count) { sized(b, 0x60, count); }
void agb_array(Agb *b, unsigned count) { sized(b, 0x50, count); }
void agb_str(Agb *b, const char *s) { size_t n = strlen(s); sized(b, 0x30, (uint32_t)n); put(b, s, n); }
void agb_bool(Agb *b, int v) { put1(b, v ? 0x02 : 0x03); }
void agb_i32(Agb *b, int32_t v) { put1(b, 0x14); putbe(b, (uint32_t)v, 4); }
void agb_u32(Agb *b, uint32_t v) { put1(b, 0x15); putbe(b, v, 4); }
void agb_i64(Agb *b, int64_t v) { put1(b, 0x16); putbe(b, (uint64_t)v, 8); }
void agb_f64(Agb *b, double v) { uint64_t u; memcpy(&u, &v, 8); put1(b, 0x21); putbe(b, u, 8); }
void agb_date(Agb *b, uint32_t s) { put1(b, 0x40); putbe(b, s, 4); }
void agb_raw(Agb *b, const unsigned char *p, size_t n) { put(b, p, n); }

/* ---------- reading ---------- */
typedef struct { const unsigned char *p; size_t n, i; char *o; size_t oc, oi; int err; } Rd;

static uint64_t rbe(Rd *r, int bytes)
{
    uint64_t v = 0;
    if (r->i + bytes > r->n) { r->err = 1; return 0; }
    for (int k = 0; k < bytes; k++) v = (v << 8) | r->p[r->i++];
    return v;
}
static void emit(Rd *r, const char *s, size_t n)
{
    if (!r->o) return;
    for (size_t k = 0; k < n && r->oi + 1 < r->oc; k++) r->o[r->oi++] = s[k];
    r->o[r->oi] = 0;
}
static void emits(Rd *r, const char *s) { emit(r, s, strlen(s)); }
static int lenbytes(unsigned t, unsigned base) { return (t - base == 0) ? 1 : (t - base == 1) ? 2 : 4; }

static void val(Rd *r, int depth)
{
    char tmp[64];
    if (depth > 32 || r->err) { r->err = 1; return; }
    unsigned t = (unsigned)rbe(r, 1);
    if (r->err) return;
    switch (t) {
    case 0x02: emits(r, "true"); break;
    case 0x03: emits(r, "false"); break;
    case 0x10: snprintf(tmp, sizeof tmp, "%d", (int8_t)rbe(r, 1)); emits(r, tmp); break;
    case 0x11: snprintf(tmp, sizeof tmp, "%u", (unsigned)rbe(r, 1)); emits(r, tmp); break;
    case 0x12: snprintf(tmp, sizeof tmp, "%d", (int16_t)rbe(r, 2)); emits(r, tmp); break;
    case 0x13: snprintf(tmp, sizeof tmp, "%u", (unsigned)rbe(r, 2)); emits(r, tmp); break;
    case 0x14: snprintf(tmp, sizeof tmp, "%d", (int32_t)rbe(r, 4)); emits(r, tmp); break;
    case 0x15: snprintf(tmp, sizeof tmp, "%u", (uint32_t)rbe(r, 4)); emits(r, tmp); break;
    case 0x16: snprintf(tmp, sizeof tmp, "%lld", (long long)(int64_t)rbe(r, 8)); emits(r, tmp); break;
    case 0x17: snprintf(tmp, sizeof tmp, "%llu", (unsigned long long)rbe(r, 8)); emits(r, tmp); break;
    case 0x20: { uint32_t u = (uint32_t)rbe(r, 4); float f; memcpy(&f, &u, 4); snprintf(tmp, sizeof tmp, "%g", f); emits(r, tmp); break; }
    case 0x40: snprintf(tmp, sizeof tmp, "@%u", (unsigned)rbe(r, 4)); emits(r, tmp); break;
    case 0x21: { uint64_t u = rbe(r, 8); double d; memcpy(&d, &u, 8); snprintf(tmp, sizeof tmp, "%g", d); emits(r, tmp); break; }
    case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: case 0x35: {
        int bin = t >= 0x33;
        size_t n = (size_t)rbe(r, lenbytes(t, bin ? 0x33 : 0x30));
        if (r->err || r->i + n > r->n) { r->err = 1; return; }
        if (bin) { snprintf(tmp, sizeof tmp, "<%zu bytes>", n); emits(r, tmp); }
        else { emits(r, "\""); emit(r, (const char *)r->p + r->i, n); emits(r, "\""); }
        r->i += n; break;
    }
    case 0x50: case 0x51: case 0x52: {
        size_t n = (size_t)rbe(r, lenbytes(t, 0x50));
        emits(r, "[");
        for (size_t k = 0; k < n && !r->err; k++) { if (k) emits(r, ","); val(r, depth + 1); }
        emits(r, "]"); break;
    }
    case 0x60: case 0x61: case 0x62: {
        size_t n = (size_t)rbe(r, lenbytes(t, 0x60));
        emits(r, "{");
        for (size_t k = 0; k < n && !r->err; k++) { if (k) emits(r, ","); val(r, depth + 1); emits(r, ":"); val(r, depth + 1); }
        emits(r, "}"); break;
    }
    default: snprintf(tmp, sizeof tmp, "<type 0x%02X?>", t); emits(r, tmp); r->err = 1;
    }
}

size_t agb_to_text(const unsigned char *p, size_t n, char *out, size_t outcap)
{
    Rd r = { p, n, 0, out, outcap, 0, 0 };
    if (outcap) out[0] = 0;
    val(&r, 0);
    return r.err ? 0 : r.i;
}

int agb_get_str(const unsigned char *p, size_t n, const char *key, char *out, size_t outcap)
{
    Rd r = { p, n, 0, NULL, 0, 0, 0 };
    unsigned t = (unsigned)rbe(&r, 1);
    if (r.err || t < 0x60 || t > 0x62) return 0;
    size_t cnt = (size_t)rbe(&r, lenbytes(t, 0x60));
    size_t kl = strlen(key);
    for (size_t k = 0; k < cnt && !r.err; k++) {
        unsigned kt = r.i < n ? p[r.i] : 0;
        if (kt >= 0x30 && kt <= 0x32) {
            r.i++;
            size_t ln = (size_t)rbe(&r, lenbytes(kt, 0x30));
            int match = !r.err && ln == kl && r.i + ln <= n && !memcmp(p + r.i, key, kl);
            r.i += ln;
            if (match && r.i < n && p[r.i] >= 0x30 && p[r.i] <= 0x32) {
                unsigned vt = p[r.i++];
                size_t vl = (size_t)rbe(&r, lenbytes(vt, 0x30));
                if (r.err || r.i + vl > n || !outcap) return 0;
                size_t c = vl < outcap - 1 ? vl : outcap - 1;
                memcpy(out, p + r.i, c); out[c] = 0;
                return 1;
            }
        } else val(&r, 1);
        val(&r, 1); /* skip value */
    }
    return 0;
}

/* ---------- navigation ---------- */
static uint64_t be(const unsigned char *p, int k) { uint64_t v = 0; for (int i = 0; i < k; i++) v = (v << 8) | p[i]; return v; }

size_t agb_skip(const unsigned char *p, size_t n)
{
    Rd r = { p, n, 0, NULL, 0, 0, 0 };
    val(&r, 0);
    return r.err ? 0 : r.i;
}

/* header of a sized type: returns header length, sets count/length */
static size_t sized_hdr(const unsigned char *p, size_t n, unsigned base, size_t *cnt)
{
    if (n < 1 || p[0] < base || p[0] > base + 2) return 0;
    int k = (p[0] - base == 0) ? 1 : (p[0] - base == 1) ? 2 : 4;
    if (n < (size_t)(1 + k)) return 0;
    *cnt = (size_t)be(p + 1, k);
    return 1 + k;
}

int agb_map_find(const unsigned char *p, size_t n, const char *key, const unsigned char **vp, size_t *vn)
{
    size_t cnt, off = sized_hdr(p, n, 0x60, &cnt), kl = strlen(key);
    if (!off) return 0;
    for (size_t k = 0; k < cnt; k++) {
        size_t ks = agb_skip(p + off, n - off); if (!ks) return 0;
        size_t sl, sh = sized_hdr(p + off, n - off, 0x30, &sl);
        int match = sh && sl == kl && !memcmp(p + off + sh, key, kl);
        off += ks;
        size_t vs = agb_skip(p + off, n - off); if (!vs) return 0;
        if (match) { *vp = p + off; *vn = vs; return 1; }
        off += vs;
    }
    return 0;
}

int agb_array_len(const unsigned char *p, size_t n) { size_t c; return sized_hdr(p, n, 0x50, &c) ? (int)c : -1; }

int agb_array_at(const unsigned char *p, size_t n, int idx, const unsigned char **vp, size_t *vn)
{
    size_t cnt, off = sized_hdr(p, n, 0x50, &cnt);
    if (!off || idx < 0 || (size_t)idx >= cnt) return 0;
    for (int k = 0; ; k++) {
        size_t vs = agb_skip(p + off, n - off); if (!vs) return 0;
        if (k == idx) { *vp = p + off; *vn = vs; return 1; }
        off += vs;
    }
}

int agb_as_int(const unsigned char *p, size_t n, long long *out)
{
    if (n < 1) return 0;
    switch (p[0]) {
    case 0x10: if (n < 2) return 0; *out = (int8_t)p[1]; return 1;
    case 0x11: if (n < 2) return 0; *out = p[1]; return 1;
    case 0x12: if (n < 3) return 0; *out = (int16_t)be(p + 1, 2); return 1;
    case 0x13: if (n < 3) return 0; *out = (long long)be(p + 1, 2); return 1;
    case 0x14: if (n < 5) return 0; *out = (int32_t)be(p + 1, 4); return 1;
    case 0x15: if (n < 5) return 0; *out = (long long)be(p + 1, 4); return 1;
    case 0x16: case 0x17: if (n < 9) return 0; *out = (long long)be(p + 1, 8); return 1;
    }
    return 0;
}

int agb_as_str(const unsigned char *p, size_t n, char *out, size_t cap)
{
    size_t len, h = sized_hdr(p, n, 0x30, &len);
    if (!h || h + len > n || !cap) return 0;
    size_t c = len < cap - 1 ? len : cap - 1;
    memcpy(out, p + h, c); out[c] = 0;
    return 1;
}

/* ---------- normalisation ---------- */
static size_t norm(const unsigned char *p, size_t n, Agb *o, int depth)
{
    if (!n || depth > 64) return 0;
    unsigned t = p[0];
    long long iv;
    if (t >= 0x10 && t <= 0x17) { if (!agb_as_int(p, n, &iv)) return 0; agb_i64(o, iv); return agb_skip(p, n); }
    if (t == 0x20) { if (n < 5) return 0; uint32_t u = (uint32_t)be(p + 1, 4); float f; memcpy(&f, &u, 4); agb_f64(o, f); return 5; }
    if (t >= 0x50 && t <= 0x52) {
        size_t cnt, off = sized_hdr(p, n, 0x50, &cnt); if (!off) return 0;
        agb_array(o, (unsigned)cnt);
        for (size_t k = 0; k < cnt; k++) { size_t s = norm(p + off, n - off, o, depth + 1); if (!s) return 0; off += s; }
        return off;
    }
    if (t >= 0x60 && t <= 0x62) {
        size_t cnt, off = sized_hdr(p, n, 0x60, &cnt); if (!off) return 0;
        agb_map(o, (unsigned)cnt);
        for (size_t k = 0; k < 2 * cnt; k++) { size_t s = norm(p + off, n - off, o, depth + 1); if (!s) return 0; off += s; }
        return off;
    }
    size_t s = agb_skip(p, n); if (!s) return 0;   /* strings, binary, bools, dates, ... verbatim */
    put(o, p, s);
    return s;
}

int agb_normalize(const unsigned char *p, size_t n, Agb *out) { return norm(p, n, out, 0) != 0; }
