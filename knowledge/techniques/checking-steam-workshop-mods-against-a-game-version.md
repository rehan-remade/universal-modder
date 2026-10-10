---
kind: technique
title: 'Checking Steam Workshop mods against a game version: the public API, page scraping limits, and what evidence to trust'
tags: [steam-workshop, modlist, compatibility, steam-web-api, scraping, rate-limits, triage]
agents:
- Claude Code (Opus 5)
- Claude Code (Opus 5.5)
- OpenCode (DeepSeek V4.1 Flash)
humans: [RedSuper, Selene0623]
date: '2026-10-05'
links: ['https://partner.steamgames.com/doc/webapi/ISteamRemoteStorage', 'https://partner.steamgames.com/doc/webapi/ISteamNews']
---
# Checking Steam Workshop mods against a game version: the public API, page scraping limits, and what evidence to trust

> How an agent can check a big Workshop modlist (130+ items) against the game build the player runs, without a
> Steam login: what the public Web API gives, where scraping the community pages stops working, and which kinds
> of evidence held up when the game itself was the judge. Worked out on Project Zomboid Build 42.20.3 (see
> `games/project-zomboid/b42-20-modlist-preset-and-world-load-errors.md`); nothing here is specific to that game
> except the tag names.
>
> **Age warning:** observed in August 2026 by an older model (Claude Opus 5); Steam's endpoints, page markup and
> rate limits can change. Re-test the limits before relying on the numbers.

## What the API gives you (no key, no login)
- **Item metadata in bulk:** `POST https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/`
  with form fields `itemcount=N` and `publishedfileids[0..N-1]`. 50 ids per call worked every time and was never
  rate-limited. Per item: `title`, `description` (BBCode), `tags` (Project Zomboid uses `Build 41` / `Build 42`),
  `time_created`, `time_updated`, `subscriptions`, `creator` (SteamID64), `visibility`, `banned`, and `result`
  (1 = found).
- **Release dates for the cut-off:** `GET https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=<app>&count=60`
  lists patch notes with dates, so "updated after the build shipped" can be a date comparison.
- **Search:** the HTML browse page `https://steamcommunity.com/workshop/browse/?appid=<app>&searchtext=<q>&browsesort=textsearch`
  (optionally `&requiredtags[]=Build 42`) returns item links as `filedetails/?id=<n>`; take the ids and feed them
  to the API above for clean data. Searching "<mod name> <build>" finds forks and fix uploads.
- **Local truth:** `steamapps/workshop/appworkshop_<app>.acf` lists the account's subscriptions;
  `steamapps/workshop/downloads/<app>/<id>/` holds items still downloading; `content/<app>/<id>/` is what the game
  sees.

```python
import json, urllib.parse, urllib.request
def details(ids):  # ids: list of workshop id strings, up to 50
    form = {"itemcount": len(ids), **{f"publishedfileids[{i}]": w for i, w in enumerate(ids)}}
    req = urllib.request.Request(
        "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
        data=urllib.parse.urlencode(form).encode())
    return json.load(urllib.request.urlopen(req, timeout=45))["response"]["publishedfiledetails"]
```

## What only the item page gives you, and its limits
The item page (`https://steamcommunity.com/sharedfiles/filedetails/?id=<n>`) carries the newest ~10 comments with
`data-timestamp` attributes, and the "Required items" block (`requiredItemsContainer`).
- **Rate limit:** after roughly 20–60 quick requests Steam started answering every page with the same ~327 KB
  error page ("an error was encountered while processing your request"). One request every ~25 s, with retries
  and a longer pause after an all-failed round, got 124 of 126 pages over about an hour. Cache good pages
  (check for `workshopItemTitle`) and never cache the error page.
- **Adult-rated items** return a ~27 KB age gate to logged-out requests. Don't try to get past it (no age
  cookies, no login); treat them as "no comment evidence".
- **Comments can be disabled.** Such a page has no comment thread markup at all (no
  `commentthread_comment_text`, no comment counter). 11 of 126 items in our list were like this, including
  several of the most popular. Detect it and record "no evidence", never "no complaints".
- The comment render endpoint (`/comment/PublishedFile_Public/render/<creator>/<id>/`) returned
  `total_count: 0` for items that visibly had comments; we didn't get it to work.

## Evidence that held up (the game's log was the judge)
Ranked by how often it agreed with what actually crashed or ran:
1. **The game's own log** after starting a world. Everything else is a predictor.
2. **The version folders the mod actually ships**, and the `mod.info` inside the folder the game will use
   (dependencies can differ per folder).
3. **A version marker in the title or folders** (`[B42.20]`, `42.20 |`, a `42.20/` folder, `versionMin=42.20`),
   plus an update date after the build's release. Store tags lag: plenty of items tagged for both builds were
   broken, and the tags are author-set.
4. **Posted stack traces** that name the mod's file and carry a game version stamp. Good evidence even from one
   user.
5. **Plain "doesn't work" comments:** weak. Many are configuration or install mistakes, and some authors delete
   them. Read them for leads, don't act on them alone.
6. **Multiplayer-only complaints:** don't dismiss them. Read the thread; some hid single-player bugs as well.

What misled us:
- **"No complaints" on a quiet or small mod means nobody checked.** Rank uncertainty as high for low subscriber
  counts, no comments since the release, and no update since the release. A 1,000-subscriber mod untouched for
  a year with an empty comment section is the riskiest item on the list.
- **A big subscriber count proves nothing about the current build.** Four vehicle mods with 1M+ subscribers each
  referenced vehicle parts that exist nowhere; a 3.6M-subscriber mod with comments disabled had a recipe that
  stopped the world from loading.
- **"Fixed for 42.13+" isn't "works on 42.20".** Patches aimed at an older build of the same branch were often
  stale. Prefer forks whose title and folders name the build you run, updated after its release.
- **A fork may keep the original's mod id.** Then both can't be installed at once without ambiguity; unsubscribe
  the original.
- **A whole Workshop can be invalidated at once by a re-release, not by a version bump.** Saints Row IV is the
  case the community keeps repeating: creations stopped working with the Re-Elected update, and the advice given
  to anyone wanting to use Workshop content is to play the legacy (pre-Re-Elected) branch instead (Rel/NEKO,
  Watch Dogs Modding Discord, 2026-10-05). Worth checking before triaging items one by one: if the game was
  re-released under a new name or appid, an old branch can be a better target than a fix list.

## Workflow that worked
1. Read every installed `mod.info` (all version folders) and resolve ids, dependencies and duplicate ids locally.
2. One API pass for all items: tags, update dates, subscribers, titles.
3. Mark items with comments disabled, adult gates or no comments since the release as "unverified", not "fine".
4. Search for maintained forks of everything stale or unverified; keep only forks updated after the release.
5. Throttled page pass for the comments of the rest; extract stack traces and version stamps.
6. Build the list, start a world, read the log, fix, repeat. Two to four rounds are normal for 100+ mods.

## Gotchas
1. **Every page fetch returns the same big HTML file with no item title.** Cause: Steam's rate limit, served as a
   200 OK error page. Fix: throttle to ~1 request per 25 s, back off further when a whole round fails, cache only
   pages containing `workshopItemTitle`.
2. **A mod scored "safe" because nobody complained, and it crashed the game.** Cause: its comment section was
   disabled. Fix: detect disabled comments and treat them as missing evidence.
3. **Search results don't contain item ids where you expect them.** Cause: browse pages are rendered HTML; ids
   appear as `filedetails/?id=` links, not in any `sharedfile_` attribute. Fix: regex the links and dedupe.
4. **The user "installed" a mod but it isn't on disk.** Cause: still downloading behind a large item, or never
   subscribed. Fix: check `downloads/<app>/` and the `.acf` before adding it to a modlist.
5. **Every item on the list reads as broken, including ones that were fine last month.** Cause: the game was
   re-released (Saints Row IV Re-Elected) and the Workshop content was built for the legacy branch. Fix: check
   the release history and appid before triaging items; if a legacy branch exists, target it and re-check the
   items against that build instead of compiling a fix list.
