/* "application/x-ag-binary": the Hydra SDK's wire format (decoder switch at 0x1409F6940 in build 3095001).
 * Every value is a type byte followed by its payload; all multi-byte numbers are big-endian.
 *   02 true, 03 false
 *   10 i8, 11 u8, 12 i16, 13 u16, 14 i32, 15 u32, 16 i64, 17 u64, 20 f32, 21 f64
 *   30/31/32 string, length u8/u16/u32 then bytes; 33/34/35 binary, same length forms
 *   40 date-time: u32 epoch seconds; 67 ? (not used here)
 *   50/51/52 array, count u8/u16/u32 then values
 *   60/61/62 map, count u8/u16/u32 then (key value) pairs; keys are strings
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

typedef struct { unsigned char *p; size_t n, cap; } Agb;

void agb_free(Agb *b);
void agb_map(Agb *b, unsigned count);
void agb_array(Agb *b, unsigned count);
void agb_str(Agb *b, const char *s);
void agb_bool(Agb *b, int v);
void agb_i32(Agb *b, int32_t v);
void agb_u32(Agb *b, uint32_t v);
void agb_i64(Agb *b, int64_t v);
void agb_f64(Agb *b, double v);
void agb_date(Agb *b, uint32_t epochSeconds); /* type 0x40 */
void agb_raw(Agb *b, const unsigned char *encoded, size_t n); /* append an already-encoded value */
/* convenience: key + value in one call */
#define agb_kstr(b, k, v)  (agb_str(b, k), agb_str(b, v))
#define agb_ki32(b, k, v)  (agb_str(b, k), agb_i32(b, v))
#define agb_kbool(b, k, v) (agb_str(b, k), agb_bool(b, v))

/* Renders a buffer as JSON-like text into out (always NUL-terminated). Returns bytes consumed or 0 on error. */
size_t agb_to_text(const unsigned char *p, size_t n, char *out, size_t outcap);
/* Finds the string value of top-level map key `key`; copies it to out. Returns 1 if found. */
int agb_get_str(const unsigned char *p, size_t n, const char *key, char *out, size_t outcap);

/* ---- navigation over an encoded value (p, n = one complete value) ---- */
size_t agb_skip(const unsigned char *p, size_t n);                       /* encoded size of the value at p, 0 on error */
int agb_map_find(const unsigned char *p, size_t n, const char *key, const unsigned char **vp, size_t *vn);
int agb_array_len(const unsigned char *p, size_t n);                     /* -1 if not an array */
int agb_array_at(const unsigned char *p, size_t n, int idx, const unsigned char **vp, size_t *vn);
int agb_as_int(const unsigned char *p, size_t n, long long *out);       /* any integer type */
int agb_as_str(const unsigned char *p, size_t n, char *out, size_t cap); /* string types */
/* Re-encodes a value the way Hydra's server returns it: every integer as int64 (0x16), f32 as f64.
 * Hydra's readers only accept int64 Values (0x140A01460), so stored data must come back normalised. */
int agb_normalize(const unsigned char *p, size_t n, Agb *out);
