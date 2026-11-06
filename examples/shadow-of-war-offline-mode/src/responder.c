/* Local stand-in for WB's Hydra server. Only what the single-player game needs to treat itself as signed in
 * offline: no account data leaves the PC, nothing here is sent anywhere, and no purchasable items are created.
 *
 * Known from the client (build 3095001):
 *   POST /auth    body {fail_on_missing, steam: <ticket>}  -> {token, type}       (handler 0x14095FF30)
 *   POST /access  body {auth_token, options, metadata}     -> {token, <key>: ...} (handler 0x14095FC20; any extra
 *                 top-level key is passed to a handler registered under that name, unknown keys are skipped)
 * Every other request currently gets 200 + an empty map and is logged, so the next run shows what to add.
 */
#include "responder.h"
#include "agb.h"
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* one fixed local identity (Hydra ids are 24 hex chars); never sent anywhere */
#define OFFLINE_ID "0ff11e000000000000000001"

static wchar_t dataPath[MAX_PATH];
static char sessionToken[64];
static int garrisonSize = 50;
int storePlaceholders = 1; /* ini StorePlaceholders; needed for the store (and the Garrison) to open */
static CRITICAL_SECTION notifLock; /* guards the pending Garrison notifications (see notif_add) */

void responder_init(const wchar_t *dataFile, int garrison)
{
    wcsncpy(dataPath, dataFile, MAX_PATH - 1);
    if (garrison > 0) garrisonSize = garrison;
    InitializeCriticalSection(&notifLock);
    /* a fresh local token per launch; it only has to be a non-empty string the client sends back to us */
    snprintf(sessionToken, sizeof sessionToken, "offline-%08lx%08lx", GetTickCount(), GetCurrentProcessId());
}

void resp_free(Response *r) { free(r->body); r->body = NULL; r->len = 0; }

/* ---------- local wallet: profiles/<id>/inventory ----------
 * After the 2018 Market shutdown the game moves the save's Mirian into the online wallet as "vc-earned"
 * (PUT {modifications:[{command:"set_count", slug:"vc-earned", count:N}]}) and zeroes PC_Mirian locally, then
 * reads the wallet back. A server that drops this loses the player's Mirian, so it's kept in OfflineWallet.txt
 * (one "slug=count" per line, next to the DLL). Only the game's own commands change it. */
typedef struct { char slug[64]; long long count; } WalletItem;
static WalletItem wallet[64];
static int walletN = -1;

static void wallet_path(wchar_t *out)
{
    wcsncpy(out, dataPath, MAX_PATH - 1); out[MAX_PATH - 1] = 0;
    wchar_t *s = wcsrchr(out, L'\\'); if (s) s[1] = 0;
    wcsncat(out, L"OfflineWallet.txt", MAX_PATH - wcslen(out) - 1);
}

static FILETIME walletStamp;
static void wallet_load(void)
{
    wchar_t path[MAX_PATH]; wallet_path(path);
    WIN32_FILE_ATTRIBUTE_DATA fa; FILETIME stamp = {0, 0};
    if (GetFileAttributesExW(path, GetFileExInfoStandard, &fa)) stamp = fa.ftLastWriteTime;
    if (walletN >= 0 && !CompareFileTime(&stamp, &walletStamp)) return; /* unchanged since last read */
    walletStamp = stamp;
    walletN = 0;
    FILE *f = _wfopen(path, L"r"); if (!f) return;
    char line[128];
    while (walletN < 64 && fgets(line, sizeof line, f)) {
        char *eq = strchr(line, '='); if (!eq || line[0] == '#') continue;
        *eq = 0; strncpy(wallet[walletN].slug, line, 63); wallet[walletN].count = _atoi64(eq + 1); walletN++;
    }
    fclose(f);
}

static void wallet_save(void)
{
    wchar_t path[MAX_PATH], tmp[MAX_PATH]; wallet_path(path);
    _snwprintf(tmp, MAX_PATH, L"%ls.tmp", path); tmp[MAX_PATH - 1] = 0;
    FILE *f = _wfopen(tmp, L"w"); if (!f) return;
    fprintf(f, "# Shadow of War Offline Mode: the online wallet, kept on this PC (vc-earned = Mirian moved online)\n");
    for (int i = 0; i < walletN; i++) fprintf(f, "%s=%lld\n", wallet[i].slug, wallet[i].count);
    fclose(f);
    MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING);
    WIN32_FILE_ATTRIBUTE_DATA fa; if (GetFileAttributesExW(path, GetFileExInfoStandard, &fa)) walletStamp = fa.ftLastWriteTime;
}

static WalletItem *wallet_get(const char *slug, int create)
{
    for (int i = 0; i < walletN; i++) if (!strcmp(wallet[i].slug, slug)) return &wallet[i];
    if (!create || walletN >= 64) return NULL;
    strncpy(wallet[walletN].slug, slug, 63); wallet[walletN].count = 0;
    return &wallet[walletN++];
}

static void wallet_apply(const unsigned char *req, size_t n)
{
    const unsigned char *mods; size_t mn;
    if (!req || !agb_map_find(req, n, "modifications", &mods, &mn)) { logw(L"    wallet: no modifications"); return; }
    int cnt = agb_array_len(mods, mn);
    for (int i = 0; i < cnt; i++) {
        const unsigned char *m, *v; size_t ml, vl; char cmd[32] = "", slug[64] = ""; long long c = 0;
        if (!agb_array_at(mods, mn, i, &m, &ml)) continue;
        if (agb_map_find(m, ml, "command", &v, &vl)) agb_as_str(v, vl, cmd, sizeof cmd);
        if (agb_map_find(m, ml, "slug", &v, &vl)) agb_as_str(v, vl, slug, sizeof slug);
        if (agb_map_find(m, ml, "count", &v, &vl)) agb_as_int(v, vl, &c);
        WalletItem *w = slug[0] ? wallet_get(slug, 1) : NULL;
        if (!w) { logw(L"    wallet: skipped %hs (no slug or full)", cmd); continue; }
        long long before = w->count;
        if (!strcmp(cmd, "set_count")) w->count = c;
        else if (strstr(cmd, "add") || strstr(cmd, "grant") || strstr(cmd, "incr")) w->count += c;
        else if (strstr(cmd, "remove") || strstr(cmd, "consume") || strstr(cmd, "decr") || strstr(cmd, "sub")) w->count -= c;
        else { logw(L"    wallet: UNKNOWN command '%hs' for %hs (count %lld) - not applied", cmd, slug, c); continue; }
        if (w->count < 0) w->count = 0;
        logw(L"    wallet: %hs %hs %lld -> %lld", cmd, slug, before, w->count);
    }
    wallet_save();
}

/* ---------- local object store: the Garrison ----------
 * Sending an orc to the Garrison is POST objects/user-garrison {data:{FactionMember:{...}, ...}} (~5 KB: gear,
 * appearance, traits). Each object is kept as one file OfflineGarrison\<id>.agb holding the encoded
 * {id, type, owner_id, created_at, updated_at, data} map, so the Garrison survives restarts and can be backed up. */
static void store_dir(wchar_t *out)
{
    wcsncpy(out, dataPath, MAX_PATH - 1); out[MAX_PATH - 1] = 0;
    wchar_t *s = wcsrchr(out, L'\\'); if (s) s[1] = 0;
    wcsncat(out, L"OfflineGarrison", MAX_PATH - wcslen(out) - 1);
}

static int valid_id(const char *id)
{
    size_t n = strlen(id);
    if (n < 8 || n > 40) return 0;
    for (size_t i = 0; i < n; i++) if (!((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f'))) return 0;
    return 1;
}

static int obj_read(const char *id, unsigned char **buf, size_t *len)
{
    wchar_t dir[MAX_PATH], path[MAX_PATH]; store_dir(dir);
    if (!valid_id(id)) return 0;
    _snwprintf(path, MAX_PATH, L"%ls\\%hs.agb", dir, id); path[MAX_PATH - 1] = 0;
    FILE *f = _wfopen(path, L"rb"); if (!f) return 0;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    *buf = malloc(n > 0 ? n : 1); *len = fread(*buf, 1, n, f); fclose(f);
    return *len > 0;
}

static int obj_write(const char *id, const unsigned char *buf, size_t len)
{
    wchar_t dir[MAX_PATH], path[MAX_PATH], tmp[MAX_PATH]; store_dir(dir);
    if (!valid_id(id)) return 0;
    CreateDirectoryW(dir, NULL);
    _snwprintf(path, MAX_PATH, L"%ls\\%hs.agb", dir, id); path[MAX_PATH - 1] = 0;
    _snwprintf(tmp, MAX_PATH, L"%ls.tmp", path); tmp[MAX_PATH - 1] = 0;
    FILE *f = _wfopen(tmp, L"wb"); if (!f) return 0;
    size_t w = fwrite(buf, 1, len, f); fclose(f);
    return w == len && MoveFileExW(tmp, path, MOVEFILE_REPLACE_EXISTING);
}

/* encodes {id, type, owner_id, created_at, updated_at, data} with data copied verbatim */
static void obj_encode(Agb *b, const char *id, const char *type, uint32_t created, const unsigned char *data, size_t dlen)
{
    static const unsigned char emptyMap[] = { 0x60, 0x00 };
    if (!data || !dlen) { data = emptyMap; dlen = 2; }
    agb_map(b, 6);
    agb_kstr(b, "id", id);
    agb_kstr(b, "type", type);
    agb_kstr(b, "owner_id", OFFLINE_ID);
    agb_str(b, "created_at"); agb_date(b, created);
    agb_str(b, "updated_at"); agb_date(b, (uint32_t)time(NULL));
    agb_str(b, "data");
    Agb nd = { 0 };
    if (agb_normalize(data, dlen, &nd)) { agb_raw(b, nd.p, nd.n); agb_free(&nd); }
    else { agb_free(&nd); agb_raw(b, data, dlen); }
}

static void obj_field_str(const unsigned char *o, size_t n, const char *key, char *out, size_t cap)
{
    const unsigned char *v; size_t vl; out[0] = 0;
    if (agb_map_find(o, n, key, &v, &vl)) agb_as_str(v, vl, out, cap);
}

/* all stored objects of one type, as search results [{score, result}] */
static int obj_search(Agb *b, const char *type)
{
    wchar_t dir[MAX_PATH], pat[MAX_PATH]; store_dir(dir);
    _snwprintf(pat, MAX_PATH, L"%ls\\*.agb", dir); pat[MAX_PATH - 1] = 0;
    char ids[256][41]; int n = 0;
    WIN32_FIND_DATAW fd; HANDLE h = FindFirstFileW(pat, &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            char id[64]; WideCharToMultiByte(CP_UTF8, 0, fd.cFileName, -1, id, sizeof id, NULL, NULL);
            char *dot = strrchr(id, '.'); if (dot) *dot = 0;
            unsigned char *o; size_t ol; char t[64];
            if (n < 256 && obj_read(id, &o, &ol)) {
                obj_field_str(o, ol, "type", t, sizeof t);
                if (!strcmp(t, type)) { strncpy(ids[n], id, 40); ids[n][40] = 0; n++; }
                free(o);
            }
        } while (FindNextFileW(h, &fd));
        FindClose(h);
    }
    agb_map(b, 5);
    agb_kstr(b, "cursor", "");
    agb_ki32(b, "start", 0);
    agb_ki32(b, "count", n);
    agb_ki32(b, "total", n);
    agb_str(b, "results"); agb_array(b, n);
    for (int i = 0; i < n; i++) {
        unsigned char *o; size_t ol;
        agb_map(b, 2);
        agb_str(b, "score"); agb_f64(b, 1.0);
        agb_str(b, "result");
        if (obj_read(ids[i], &o, &ol)) { agb_raw(b, o, ol); free(o); } else agb_map(b, 0);
    }
    return n;
}

/* the wallet as the game reads it: [{slug, quantity, invdata}] (0x1417F66D8) plus hydra InventoryItem fields */
static void wallet_emit(Agb *b)
{
    int n = 0;
    for (int i = 0; i < walletN; i++) if (wallet[i].count > 0) n++;
    agb_array(b, n);
    for (int i = 0; i < walletN; i++) {
        if (wallet[i].count <= 0) continue;
        long long c = wallet[i].count;
        agb_map(b, 8);
        agb_kstr(b, "id", wallet[i].slug);
        agb_kstr(b, "slug", wallet[i].slug);
        agb_kstr(b, "item_slug", wallet[i].slug);
        agb_str(b, "quantity"); agb_i64(b, c); /* Hydra reads counts only as int64 Values (0x140A01460): int32 reads as 0 */
        agb_str(b, "count"); agb_i64(b, c);
        agb_kstr(b, "account_id", OFFLINE_ID);
        agb_str(b, "invdata"); agb_map(b, 0);
        agb_str(b, "data"); agb_map(b, 0);
    }
}

/* ---------- notifications: accounts/me/notifications ----------
 * Deploying or destroying a Garrison orc runs a state machine (names at 0x141FE1DE8..0x141FE1EA8):
 * CreateGarrisonMemberRemoval (DELETE objects/user-garrison/<id>) -> WaitForGarrisonMemberRemoval ->
 * WaitForCurrent/NewNotifications -> AwardLoot (destroy, loot rolled locally from the orc) or the new captain
 * (deploy, rebuilt from the stored record) -> RemoveNotification. The server confirms the removal with a
 * notification {cmd:"garrison_removal", payload:{obj:<object id>}} (checks 0x141C508A0 / 0x141C509EC); without
 * it the flow fails and the orc is simply gone. GET .../unread must be a list (0x14098E0B0 wants Value type 5)
 * of hydra::Notification {id, cmd, header, payload, state, consumed} (fromValue 0x14529A910); a notification
 * without cmd is ignored. The game dismisses it with DELETE accounts/me/notifications/<id> (0x14098F5F0).
 * Kept in memory only: a confirmation is only useful while the game waits for it. */
static char notifObj[32][41]; /* object id per pending removal notification */
static int notifN;

static void notif_id(const char *obj, char *out) { snprintf(out, 25, "0ff11e0c%.16s", strlen(obj) > 8 ? obj + 8 : obj); }

static void notif_add(const char *obj)
{
    EnterCriticalSection(&notifLock);
    if (notifN == 32) { memmove(notifObj[0], notifObj[1], sizeof notifObj[0] * 31); notifN--; }
    strncpy(notifObj[notifN], obj, 40); notifObj[notifN][40] = 0; notifN++;
    LeaveCriticalSection(&notifLock);
}

/* drops every pending notification whose id appears in s (one id, or a bulk list in the query string) */
static int notif_remove_in(const char *s)
{
    int removed = 0;
    EnterCriticalSection(&notifLock);
    for (int i = 0; i < notifN; ) {
        char nid[25]; notif_id(notifObj[i], nid);
        if (strstr(s, nid)) { memmove(notifObj[i], notifObj[i + 1], sizeof notifObj[0] * (notifN - i - 1)); notifN--; removed++; }
        else i++;
    }
    LeaveCriticalSection(&notifLock);
    return removed;
}

static void notif_encode(Agb *b, const char *obj)
{
    char nid[25]; notif_id(obj, nid);
    /* the game's list (0x141868A74) keeps only {id, header, data} of each entry with consumed == false: the
     * removal checks compare header with "garrison_removal" and data.obj with the object id */
    agb_map(b, 9);
    agb_kstr(b, "id", nid);
    agb_kstr(b, "account_id", OFFLINE_ID);
    agb_kstr(b, "cmd", "garrison_removal");
    agb_kstr(b, "header", "garrison_removal");
    agb_kbool(b, "consumed", 0);
    agb_str(b, "payload"); agb_map(b, 1); agb_kstr(b, "obj", obj);
    agb_str(b, "created_at"); agb_date(b, (uint32_t)time(NULL));
    agb_str(b, "data"); agb_map(b, 1); agb_kstr(b, "obj", obj);
    agb_str(b, "server_data"); agb_map(b, 0);
}

static void notif_emit(Agb *b, const char *onlyId)
{
    EnterCriticalSection(&notifLock);
    int n = 0;
    for (int i = 0; i < notifN; i++) { char nid[25]; notif_id(notifObj[i], nid); if (!onlyId || !strcmp(nid, onlyId)) n++; }
    if (!onlyId) agb_array(b, n);
    for (int i = 0; i < notifN; i++) {
        char nid[25]; notif_id(notifObj[i], nid);
        if (!onlyId || !strcmp(nid, onlyId)) { notif_encode(b, notifObj[i]); if (onlyId) break; }
    }
    if (onlyId && !n) agb_map(b, 0);
    LeaveCriticalSection(&notifLock);
}

static void finish(Response *out, int status, Agb *b)
{
    out->status = status; out->body = b->p; out->len = b->n;
}

/* path without leading slashes or query string, e.g. "auth", "ssc/invoke/garrison-get-collection" */
static void norm_path(const wchar_t *path, char *out, size_t cap)
{
    while (*path == L'/') path++;
    size_t i = 0;
    for (; *path && *path != L'?' && i + 1 < cap; path++) out[i++] = (char)(*path < 128 ? *path : '?');
    out[i] = 0;
}

void respond(const wchar_t *verb, const wchar_t *path, const unsigned char *req, size_t reqLen, Response *out)
{
    char p[512];
    Agb b = { 0 };
    norm_path(path, p, sizeof p);


    if (!strcmp(p, "auth")) {
        agb_map(&b, 2);
        agb_kstr(&b, "token", sessionToken);
        agb_kstr(&b, "type", "steam");
        return finish(out, 200, &b);
    }
    if (!strcmp(p, "access")) {
        /* The game counts itself signed in only when both "account" and "profile" are maps and profile.data
         * is a map (0x141B5229C / 0x141B526AC). account.wbplay_identity.email and account.opt_ins.wbplay_optin
         * are read (0x141B52760); profile.server_data.telemetry_settings.send_sampled_events is read (0x141B526DC). */
        agb_map(&b, 3);
        agb_kstr(&b, "token", sessionToken);
        agb_str(&b, "account");
        agb_map(&b, 5);
        agb_kstr(&b, "id", OFFLINE_ID);
        agb_kstr(&b, "public_id", OFFLINE_ID);
        agb_kstr(&b, "username", "Offline");
        /* a non-empty email makes the game treat WB Play as registered (copied to +0x23EC by 0x141B52760); .invalid never resolves */
        agb_str(&b, "wbplay_identity"); agb_map(&b, 2); agb_kstr(&b, "email", "offline@offline.invalid"); agb_kstr(&b, "username", "Offline");
        agb_str(&b, "opt_ins"); agb_map(&b, 1); agb_kbool(&b, "wbplay_optin", 0);
        agb_str(&b, "profile");
        agb_map(&b, 4);
        agb_kstr(&b, "id", OFFLINE_ID);
        agb_kstr(&b, "account_id", OFFLINE_ID);
        agb_str(&b, "data"); agb_map(&b, 0);
        agb_str(&b, "server_data"); agb_map(&b, 1);
        agb_str(&b, "telemetry_settings"); agb_map(&b, 1); agb_kbool(&b, "send_sampled_events", 0);
        return finish(out, 200, &b);
    }
    if (!strcmp(p, "ssc/invoke/get_server_time")) {
        /* 0x141B5238C: clock offset = server_time + (now - query_start_MS) / 2, both read as ints */
        long long startMs = 0;
        const wchar_t *q = wcsstr(path, L"query_start_MS=");
        if (q) startMs = _wtoi64(q + 15);
        FILETIME ft; GetSystemTimeAsFileTime(&ft);
        long long nowMs = (long long)((((unsigned long long)ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 10000ULL) - 11644473600000LL;
        agb_map(&b, 2);
        agb_str(&b, "server_time"); agb_i64(&b, nowMs);
        agb_str(&b, "query_start_MS"); agb_i64(&b, startMs);
        return finish(out, 200, &b);
    }

    if (!strncmp(p, "profiles/", 9) && strlen(p) > 10 && !strcmp(p + strlen(p) - 10, "/inventory")) {
        wallet_load();
        if (!wcscmp(verb, L"PUT") || !wcscmp(verb, L"POST")) wallet_apply(req, reqLen);
        wallet_emit(&b);
        return finish(out, 200, &b);
    }

    if (!strcmp(p, "ssc/invoke/valve_userinfo")) {
        /* The Store (which hosts the Garrison screen) waits for this before loading (0x1417F7894 reads
         * status.currency and status.country). Only labels prices; the local catalog stays empty. */
        agb_map(&b, 1);
        agb_str(&b, "status");
        agb_map(&b, 2);
        agb_kstr(&b, "currency", "USD");
        agb_kstr(&b, "country", "US");
        return finish(out, 200, &b);
    }

    if (!strncmp(p, "broadcast_channels/", 19) && strstr(p, "/broadcasts/timeline")) {
        /* Same cursor container as searches (0x1409886A0); each result is a message
         * {broadcast_channel_slug, content, start_at, end_at} (0x14510D970).
         * "game-settings" is WB's remote config, read by CloudServicesGameSettingsMgr (0x1418368B0):
         * store_enabled = false is what shows "We have temporarily disabled the Garrison"
         * (UI_MenuError_Store_Closed_Body). Every other channel (MOTD, store ticker...) stays empty. */
        char slug[64] = "";
        sscanf(p + 19, "%63[^/]", slug);
        if (!strcmp(slug, "game-settings")) {
            char json[256];
            snprintf(json, sizeof json,
                "{\"store_enabled\":true,\"garrison_size\":%d,\"vendettas_enabled\":false,\"telemetry_enabled\":false}",
                garrisonSize);
            uint32_t now = (uint32_t)time(NULL);
            agb_map(&b, 5);
            agb_kstr(&b, "cursor", "");
            agb_ki32(&b, "start", 0);
            agb_ki32(&b, "count", 1);
            agb_ki32(&b, "total", 1);
            agb_str(&b, "results"); agb_array(&b, 1);
            /* the game reads message, slug, message_id, start_at, end_at and the settings MAP under "data"
             * (0x1417B5C04 -> 0x1417B548C copies data to +0x3290, parsed by 0x1418368B0) */
            agb_map(&b, 8);
            agb_kstr(&b, "broadcast_channel_slug", "game-settings");
            agb_kstr(&b, "slug", "game-settings");
            agb_kstr(&b, "message_id", "offline-game-settings");
            agb_kstr(&b, "message", "");
            agb_kstr(&b, "content", json);
            agb_str(&b, "start_at"); agb_date(&b, now - 86400);
            agb_str(&b, "end_at"); agb_date(&b, now + 3650u * 86400u);
            agb_str(&b, "data");
            agb_map(&b, 4);
            agb_kbool(&b, "store_enabled", 1);
            agb_ki32(&b, "garrison_size", garrisonSize);
            agb_kbool(&b, "vendettas_enabled", 0);
            agb_kbool(&b, "telemetry_enabled", 0);
            return finish(out, 200, &b);
        }
        if (!strcmp(slug, "store-front") || !strcmp(slug, "japan-store-front")) {
            /* The store (and the Garrison inside it) is "inaccessible" until a storefront layout exists
             * (commerce+0x268, built by 0x1418633BC from this channel's message data). Needs version 2 and
             * non-empty act_i/act_ii rack ids. racks = [] means an empty storefront: no products at all. */
            uint32_t now = (uint32_t)time(NULL);
            agb_map(&b, 5);
            agb_kstr(&b, "cursor", "");
            agb_ki32(&b, "start", 0);
            agb_ki32(&b, "count", 1);
            agb_ki32(&b, "total", 1);
            agb_str(&b, "results"); agb_array(&b, 1);
            agb_map(&b, 7);
            agb_kstr(&b, "broadcast_channel_slug", slug);
            agb_kstr(&b, "slug", slug);
            agb_kstr(&b, "message_id", "offline-store-front");
            agb_kstr(&b, "message", "");
            agb_str(&b, "start_at"); agb_date(&b, now - 86400);
            agb_str(&b, "end_at"); agb_date(&b, now + 3650u * 86400u);
            agb_str(&b, "data");
            agb_map(&b, 5);
            agb_ki32(&b, "version", 2);
            agb_str(&b, "title"); agb_map(&b, 1); agb_kstr(&b, "enUS", "Garrison");
            agb_kstr(&b, "act_i", "offline");
            agb_kstr(&b, "act_ii", "offline");
            agb_str(&b, "racks"); agb_array(&b, 0);
            return finish(out, 200, &b);
        }
        agb_map(&b, 5);
        agb_kstr(&b, "cursor", "");
        agb_ki32(&b, "start", 0);
        agb_ki32(&b, "count", 0);
        agb_ki32(&b, "total", 0);
        agb_str(&b, "results"); agb_array(&b, 0);
        return finish(out, 200, &b);
    }

    /* The store (which hosts the Garrison) only counts as accessible when the item-definition list and the
     * product catalog are both non-empty (0x14071D900 / 0x1417F5D58 test commerce+0x238 / +0x220). Both
     * endpoints must return an array (0x140992F00 / 0x140998F90). Each gets ONE inert placeholder: max_count 0,
     * no price, no grants, not on any storefront shelf. Nothing can be bought, granted or used. */
    if (storePlaceholders && !strcmp(p, "inventory/items")) {
        /* hydra::InventoryItem (fromValue 0x14512EBC0, vtable 0x141E28868): count (int), item_slug, account_id.
         * The first build sent definition-style fields without count and crashed at +0xA00360. */
        agb_array(&b, 1);
        agb_map(&b, 6);
        agb_kstr(&b, "id", "offline-placeholder");
        agb_ki32(&b, "count", 0);
        agb_kstr(&b, "item_slug", "offline-placeholder");
        agb_kstr(&b, "account_id", OFFLINE_ID);
        agb_kstr(&b, "slug", "offline-placeholder");
        agb_str(&b, "data"); agb_map(&b, 0);
        return finish(out, 200, &b);
    }
    if (storePlaceholders && !strcmp(p, "commerce/catalog/me/products")) {
        /* hydra::CatalogProduct (fromValue 0x14099EE30, vtable 0x141E2A6A8): name, description (strings),
         * tags (array), payment_options (map, parsed unchecked), items (array of {item, quantity}). */
        agb_array(&b, 1);
        agb_map(&b, 10);
        agb_kstr(&b, "id", "offline-placeholder");
        agb_kstr(&b, "slug", "offline-placeholder");
        agb_kstr(&b, "name", "Offline");
        agb_kstr(&b, "description", "");
        agb_str(&b, "tags"); agb_array(&b, 0);
        agb_str(&b, "payment_options"); agb_map(&b, 0);
        agb_str(&b, "items"); agb_array(&b, 0);
        agb_str(&b, "applied_sales"); agb_array(&b, 0);
        agb_str(&b, "data"); agb_map(&b, 0);
        agb_str(&b, "proddata");
        agb_map(&b, 10);
        agb_str(&b, "name"); agb_map(&b, 0);
        agb_str(&b, "description"); agb_map(&b, 0);
        agb_str(&b, "details"); agb_map(&b, 0);
        agb_kstr(&b, "icon_id", "");
        agb_kstr(&b, "image_id", "");
        agb_ki32(&b, "unpack_uruks", 0);
        agb_ki32(&b, "unpack_inventory", 0);
        agb_ki32(&b, "grant_total", 0);
        agb_kbool(&b, "limited_quantity", 0);
        agb_ki32(&b, "max_count", 0);
        return finish(out, 200, &b);
    }

    if (!strncmp(p, "objects/types/", 14) && strstr(p, "/search_queries/") && strstr(p, "/run")) {
        /* cursor-paged search (parser 0x14097A090): {cursor, start, count, total, results: [{score, result}]}.
         * The Garrison is "objects/types/user-garrison/search_queries/garrison-get-collection/run". */
        char type[64] = "";
        sscanf(p + 14, "%63[^/]", type);
        int n = obj_search(&b, type);
        logw(L"    garrison: %d stored %hs object(s)", n, type);
        return finish(out, 200, &b);
    }

    if (!strncmp(p, "objects/", 8)) {
        /* Hydra objects. POST objects/<type> creates; GET/PUT/DELETE objects/<id>. Replies always carry an id and
         * a data map: the object reader 0x14097D7F0 iterates data without a null check. */
        /* paths seen: POST objects/user-garrison, GET objects/user-garrison/<id>; also accept objects/<id> */
        const char *rest = p + 8;
        char seg[64] = "", seg2[64] = "";
        sscanf(rest, "%63[^/]/%63[^/?]", seg, seg2);
        if (seg2[0] && valid_id(seg2)) strcpy(seg, seg2);
        int isPost = !wcscmp(verb, L"POST"), isPut = !wcscmp(verb, L"PUT"), isDel = !wcscmp(verb, L"DELETE");
        const unsigned char *data = NULL; size_t dlen = 0;
        if (req && reqLen) agb_map_find(req, reqLen, "data", &data, &dlen);
        if (isPost && !valid_id(seg)) {
            static unsigned serial;
            char oid[32];
            snprintf(oid, sizeof oid, "0ff11e0b%08x%08x", (unsigned)time(NULL), ++serial);
            obj_encode(&b, oid, seg, (uint32_t)time(NULL), data, dlen);
            int ok = obj_write(oid, b.p, b.n);
            logw(L"    garrison: created %hs object %hs (%zu bytes of data) %ls", seg, oid, dlen, ok ? L"saved" : L"SAVE FAILED");
            return finish(out, 200, &b);
        }
        unsigned char *o = NULL; size_t ol = 0;
        int have = obj_read(seg, &o, &ol);
        if (isDel) {
            wchar_t dir[MAX_PATH], path[MAX_PATH] = L""; store_dir(dir);
            BOOL gone = FALSE; DWORD err = 0;
            if (valid_id(seg)) { _snwprintf(path, MAX_PATH, L"%ls\\%hs.agb", dir, seg); path[MAX_PATH - 1] = 0; gone = DeleteFileW(path); if (!gone) err = GetLastError(); }
            if (gone) logw(L"    garrison: deleted object %hs", seg);
            else logw(L"    garrison: delete of %hs failed (%ls, error %lu)", seg, have ? L"existed" : L"not found", err);
            /* confirm the removal so Deploy / Destroy for gear can finish (see notif_add) */
            if (have) { notif_add(seg); logw(L"    garrison: queued garrison_removal notification for %hs", seg); }
            /* reply with the removed object: an empty {} made "Destroy for gear" show a data error and grant no gear */
            if (have) { agb_raw(&b, o, ol); free(o); return finish(out, 200, &b); }
            agb_map(&b, 3);
            agb_kstr(&b, "id", seg);
            agb_kstr(&b, "owner_id", OFFLINE_ID);
            agb_str(&b, "data"); agb_map(&b, 0);
            return finish(out, 200, &b);
        }
        if (isPut && have && data) {
            char type[64]; obj_field_str(o, ol, "type", type, sizeof type);
            obj_encode(&b, seg, type, (uint32_t)time(NULL), data, dlen);
            obj_write(seg, b.p, b.n);
            logw(L"    garrison: replaced data of %hs", seg);
            free(o);
            return finish(out, 200, &b);
        }
        if (isPut) logw(L"    garrison: PUT on %hs not applied (%ls) - shape logged above", seg, have ? L"no data field" : L"unknown object");
        if (have) { agb_raw(&b, o, ol); free(o); return finish(out, 200, &b); }
        logw(L"    garrison: %ls %hs - no such object", verb, seg);
        agb_map(&b, 3);
        agb_kstr(&b, "id", valid_id(seg) ? seg : "0ff11e0b0000000000000000");
        agb_kstr(&b, "owner_id", OFFLINE_ID);
        agb_str(&b, "data"); agb_map(&b, 0);
        return finish(out, 200, &b);
    }

    if (!strncmp(p, "accounts/me/notifications", 25)) {
        const char *rest = p[25] == '/' ? p + 26 : "";
        if (!strcmp(rest, "unread") || !rest[0]) {
            notif_emit(&b, NULL);
            EnterCriticalSection(&notifLock); int n = notifN; LeaveCriticalSection(&notifLock);
            if (n) logw(L"    notifications: served %d pending", n);
            return finish(out, 200, &b);
        }
        if (!wcscmp(verb, L"DELETE") || !wcscmp(verb, L"PUT") || !wcscmp(verb, L"POST")) {
            /* dismiss one (notifications/<id>) or several (notifications/bulk/?...): match ids anywhere in the
             * full path including the query string, and in the body as text */
            char full[1024]; size_t i = 0;
            for (const wchar_t *w = path; *w && i + 1 < sizeof full; w++) full[i++] = (char)(*w < 128 ? *w : '?');
            full[i] = 0;
            int n = notif_remove_in(full);
            if (req && reqLen) {
                char *txt = malloc(reqLen * 4 + 64);
                if (txt) { agb_to_text(req, reqLen, txt, reqLen * 4 + 64); n += notif_remove_in(txt); free(txt); }
            }
            logw(L"    notifications: %ls dismissed %d", verb, n);
            agb_map(&b, 0);
            return finish(out, 200, &b);
        }
        notif_emit(&b, rest); /* GET notifications/<id> */
        return finish(out, 200, &b);
    }

    /* not modelled yet: an empty map, logged by the caller */
    agb_map(&b, 0);
    finish(out, 200, &b);
}
