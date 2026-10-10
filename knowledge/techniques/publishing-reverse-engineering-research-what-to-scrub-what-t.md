---
kind: technique
title: 'Publishing reverse-engineering research: what to scrub, what to keep, and how to know you are clean'
status: working
agents:
- OpenCode (DeepSeek V4.1 Flash)
humans:
- '@Selene0623'
date: '2026-10-06'
links:
- https://github.com/rehan-remade/universal-modder/pull/65
tags: [publishing, sanitization, secrets, license-keys, local-paths, documentation, attribution, docusaurus, grep]
---
# Publishing reverse-engineering research: what to scrub, what to keep, and how to know you are clean

> Research notes taken from retail builds, leaks and engine internals can be published safely, as long as the
> write-up carries the knowledge and the repository carries none of the material: no pasted code, no licence
> keys, no download links, no home directories. This is the pass that takes a docs repo from "we wrote it all
> down" to "clean enough to publish", and the residue that survives a careless scrub. The point is not only to
> satisfy your own rules but to match what the community the notes are published into expects: attributed
> findings in the author's own words, and none of the material itself. Worked out on a Docusaurus RE reference
> site (~175 pages); nothing here is specific to that stack beyond the build step.

## When to use it

Before any research note leaves the private workspace: pushing a docs repo public, moving notes into a shared
knowledge base, or handing a draft to another agent. It also applies when the target is someone else's
publication: a site, wiki or knowledge base that a community reads and contributes to, where the standard is
whatever that community expects rather than whatever your workspace tolerated. Run it again whenever a file is
swept into a commit by accident — a repo-wide commit is where unrelated drafts, private paths and stray keys
travel.

## How

1. **Fix the policy line first, in writing.** Knowledge in your own words (formats, layouts, symbol names,
   behaviour, gotchas) is publishable with attribution. The material is not: decompiled or leaked source,
   SDK/firmware files, extracted game data, licence keys, download links, or instructions to go fetch a leak.
   A project that already publishes under a contribution policy is the cheapest source of that line — see the
   universal-modder PR above for a policy written exactly this way (closes the "is my leak-derived note
   allowed?" question without a per-note debate). When the destination is an existing community publication,
   its own standard wins: attributed, own-words findings are welcome; the material is not. Do not import the
   tolerance of a private workspace into someone else's public wiki.
2. **Sweep with literal strings, not regex heuristics.** A drive-letter pattern like `[A-Za-z]:\\` misses
   lowercase drives and everything outside Windows. Grep for the literal fragments instead: `~/`, `/home/`,
   `C:\Users\`, `Documents/`, `/tmp/`, plus the site's own internal repo names and any agent-only file names.
   Sweep the whole docs tree, including drafts and directories you think are out of scope.
3. **Triage every hit into drop, genericise, or keep.** The keep list matters as much as the drop list: a
   scrub that strips documentation-target paths or a quoted tutorial's wording damages the note.
4. **Delete secrets; do not relocate them.** Third-party licence keys, tokens, activation data and serials
   are deleted outright: keep none in the repo, none in a private file, and publish no extraction method.
   A method for recovering someone else's keys is not publishable knowledge, however interesting the format
   is.
5. **Hunt the residue a scrub leaves behind.** Removing a link or a sentence leaves dangling prose: "samples
   available in ." where the path used to be, "cross-game work lives in" followed by an empty line, a table
   row whose only column is `AGENTS.md`, a sentence citing an internal file the reader cannot open. After the
   main pass, grep for the leftovers (lines ending in "in .", empty table cells, `AGENTS.md`) and repair them
   into plain sentences — the fact belongs in the doc, the reference to a private process file does not.
6. **Verify by building, then re-sweep before publishing.** A static-site build with strict link
   checking (`onBrokenLinks: 'throw'` on Docusaurus, plus a pre-build link script) catches the damage from
   step 5. Record what the build still warns about, so the next agent does not treat an old warning as new
   breakage.
7. **Re-sweep the second checkout.** A scrub is per-tree, not per-repo. If a migration worktree, a branch or a
   stale clone exists, the pre-scrub text is still there — and it will be published the moment that branch
   merges.
8. **Treat history and deploys as already published.** The working tree is not the boundary. A scrub changes
   what the next commit contains, while the old blob stays reachable in git history and any built output
   branch (`gh-pages`, a build artifact, a mirrored site) stays online on its own. Either rewrite history and
   force-push, then confirm the deploy branch was replaced, or accept that everything ever committed to those
   branches is public and act accordingly. The second option is what happens by default.

What to drop, genericise and keep:

| Hit | Verdict |
|---|---|
| Home directories, usernames, `~/Tools/...`, personal project paths, `/tmp` clone paths, internal research-repo paths | Drop, or genericise to the tool or repo name alone |
| Licence keys, tokens, activation data, serials | Drop entirely — delete the values, keep none privately, publish no extraction method |
| Agent-only instruction files (`AGENTS.md`, internal notes) cited in public prose | Drop the reference, keep the fact |
| Extracted game data paths under a personal workspace | Genericise to the unpack directory name, or drop |
| Personal machine details: hostname, CPU/GPU model, distro tuning knobs, `~/.config` snippet, a Wine/Proton prefix path | Drop — the finding is the method, not the box it ran on |
| Private conversation content: DMs, screenshots of someone's messages, a handle attached to a claim they did not make publicly | Drop the content; publish the finding only if it is independently verifiable, and credit by handle only with permission |
| Generic example paths (`C:\Modding\...`, `<Steam library>/...`, `C:\DEV\<tool>\`, a game's own documented settings search order such as the `Public\Documents\<publisher>\...` subtree) | Keep |
| Placeholders already in the text (`C:\Users\<USERNAME>`) | Keep — do not re-substitute a real name |
| Verbatim third-party content: a quoted gist's paths, a scraped tutorial's drive letters, a contributor's handle | Keep the quote intact, attribute it; only strip a *personal* username if it is clearly not part of the quote's meaning |

## Gotchas

1. **Symptom:** the local link checker is green but the published site throws on a broken link. **Cause:** the
   checker validates that file paths exist in the repo, not that the site's routes resolve — a deleted hub page
   still passes every file-path test while every page linking to `/docs/` breaks. **Fix:** after deleting or
   renaming a page, run the real build, and check the route (`/docs/...`), not just the file.
2. **Symptom:** a "docs-only" commit touches a hundred unrelated files. **Cause:** commit helpers that stage
   everything (`git add -A` wrappers, "smart commit" scripts) sweep whatever happens to be dirty, including
   private drafts. **Fix:** stage explicitly by path; before committing, `git status` and check whether the
   file list matches the intended change; prefer separate commits once unrelated work is in the tree.
3. **Symptom:** the keys are gone from the main checkout but still published. **Cause:** a second worktree or
   branch carries the pre-scrub copy, and its build is what deploys if it merges. **Fix:** sweep every
   checkout (`git worktree list`, then grep each tree), and re-check branches that could publish.
4. **Symptom:** a literal path search reports "nothing left" while paths are still there. **Cause:** regex
   narrowing or a search that excluded the very directory holding the hits (a too-clever pattern will miss
   lowercase drives, alternate separators, and the excluded workspace). **Fix:** sweep by literal fragment over
   the whole tree, and when a result contradicts what you saw in a file, re-read the file instead of trusting
   the search.
5. **Symptom:** a scrub silently loses information. **Cause:** deleting a whole paragraph because it contained
   one private path. **Fix:** edit to the smallest span that removes the private part; re-read the section after
   editing, and keep the surrounding facts.
6. **Symptom:** published notes cite things readers cannot open — internal worktree names, agent-only files,
   paths from someone's private repo. **Cause:** a citation was written for a teammate instead of a reader, so
   the standards the note documents end up outside the community's reach. **Fix:** cite public sources (docs
   sites, upstream repos, forum threads, PRs) or state the fact outright.
7. **Symptom:** prose renders mangled after a placeholder substitution. **Cause:** markdown swallows
   angle-bracketed text (`<YourName>` in a paragraph becomes an HTML tag). **Fix:** in prose use
   `%USERPROFILE%` or `~`; keep angle-bracket placeholders for fenced code blocks and tables.

8. **Symptom:** a note reads as unsourced or over-claimed after publishing. **Cause:** the finding came from a
   conversation, a screenshot or a DM, and the evidence itself cannot be published (nor can the person be cited
   as agreeing with a rephrasing). **Fix:** publish the finding, mark it community-reported with the reporter's
   handle and date *if* they are fine with it, otherwise attribute it to the community thread generically;
   keep "unverified" explicit rather than upgrading it to fact. A person declining to collaborate does not make
   their statements unquotable, but it does mean their files and private messages stay out, and their work is
   not the source you built on.
9. **Symptom:** a reader follows your note and reproduces a bug you already fixed. **Cause:** the note links the
   upstream project, but the fix lives on a fork or branch (the packer change, the format fix, the CI repair).
   **Fix:** say what the fix does, and name the branch and the commits that carry it; link the fork only if the
   account behind it is one you would point a stranger at — if it also hosts leaked material or keys, name
   the branch and hashes and link the upstream project instead,
   so the note stays honest about lineage without sending readers through the rest of the account.
10. **Symptom:** the keys are gone from every file, yet someone finds one. **Cause:** the scrub only touched the
    working tree — the blob is still reachable in history (`git log -S<literal> --all`, `git log --all -- <path>`)
    and in whatever a deploy branch already shipped. **Fix:** check history and the output branch before
    claiming clean; either purge (`git filter-repo` or BFG, force-push, then redeploy so the branch is
    replaced) or say plainly that everything ever committed there stays published.
11. **Symptom:** the branches are clean and the key is still fetchable. **Cause:** a rewrite and force-push cover
    the branch refs only. Two copies survive on the host: pull-request refs (`refs/pull/N/head`, which nobody can
    force-push) and any other branch you did not rewrite. **Fix:** enumerate every ref before calling it done
    (`git ls-remote origin`, then scan each one), rewrite the ones you own, and for pull-request refs file a host
    support request to purge the objects (GitHub Support can purge pull-request refs and cached views), since the
    ref itself cannot be corrected. Expired keys are still keys: an expiry date lowers the stakes, it does not make
    the literal safe to leave addressable.

## Seen in

No game note uses this yet; the audit was run on a community reference site for Disrupt, Dunia and Havok
formats after an upstream project declined to link to it for publishing licence keys extracted from a retail
build. Related: the Disrupt cross-game toolchain technique note in this folder.
Re-swept in 2026-10-06: the Watch Dogs 1 shader-pack game note in `games/watch-dogs/` cites upstream
`gibbed/Gibbed.Disrupt` and describes the packer fix it needs (gotcha 9) instead of pointing at a fork, and a
hardware-specific line was removed from the RTX-on-WD1 reference page. The hardware/prefix row and the conversation-content row were added after both
kinds of hit showed up in drafts written from Discord-sourced findings. Step 4 and the licence-key row were
tightened after review to delete keys outright rather than relocate them, and step 8 plus gotcha 10 were added
for the history and deploy-branch boundary.
