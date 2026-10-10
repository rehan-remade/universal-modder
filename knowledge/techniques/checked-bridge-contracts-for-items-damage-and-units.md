---
kind: technique
title: "Checked bridge contracts for items, damage and units"
status: in-progress
tags: [mashup, bridge-contract, items, damage, health, units, axes, verification, ontology, shacl, owl, signatures]
date: 2026-10-10
agents: ["Claude Code (Opus 5.5)"]
humans: ["fabio-rovai"]
links: ["https://github.com/fabio-rovai/asset-passport/blob/main/docs/BRIDGES.md", "https://github.com/fabio-rovai/asset-passport", "https://github.com/fabio-rovai/open-ontologies"]
---

# Checked bridge contracts for items, damage and units

> The "Units and axes" and "Damage / health" parts of a `docs/CONTRACT.md` are usually prose, and prose
> drifts: the CrossOver Elden Ring and Monster Hunter: World bridges share magic and offsets, yet one sends
> Minecraft damage converted by target max HP and the other sends native HP (gotcha 1 in
> [bridge-contracts-ownership-units-and-lifecycle.md](bridge-contracts-ownership-units-and-lifecycle.md)).
> This technique writes those parts as a small data file and checks a bridge's declared axes, unit ratio and
> health multiplier against sourced facts about the two games before anything runs in game. On the nine rows
> of that note's Unit mappings table it finds three that hold and six it cannot settle, and the reasons are
> below. The same approach carries items and damage between games. Every check here has been shown to fail
> on a wrong input.

**Evidence level**, in the vocabulary of
[evidence-levels-for-mashup-claims.md](evidence-levels-for-mashup-claims.md). The bridge results are
**source inspection**: the declarations (creator reports, as the Unit mappings table restates them, and for
four projects their own code at a pinned commit) and the game facts (wiki pages and SDK source) were read,
and a synthetic run of a checker compares them. No game ran. The item crossings are a **synthetic test** on
two small browser games built for the purpose, Blockcraft (a player has 20 HP, no elemental types) and Pocket
Battlers (a creature has 100 HP, every move has a type), not on retail games. The item and bridge verdicts
are engine output, and Asset Passport's tests pin them. The gotcha measurements were taken by hand on the
engine named under Verification; the tests also pin which of gotcha 3's expressions return a value and four
of the five chains in gotcha 2.

## When to use it
- You are writing the "Units and axes" function of a bridge and want it checked against the two games'
  documented axes and unit lengths before you debug it in game.
- A damage event or a heal crosses between games that disagree on scale (20 HP against 100).
- More than one host reads the same guest messages. That is where the Elden Ring and Monster Hunter drift
  came from.
- A thing crosses from guest to host and the games disagree on vocabulary (a sword against a typed move) or
  on what exists at all (a capture device in a game where nothing can own a mob).

Not for transport, byte layout, ownership or lifecycle. The bridge-contracts note covers those.

## How

### Units, axes and health of a bridge
The bridge-contracts note asks for "Units and axes, written as a function both sides share". Asset
Passport's bridge checker (`python3 -m passport.bridge check <file>.ttl`) takes that function as a small
Turtle declaration (host, guest, each guest axis as a signed host axis, a unit ratio or a span, a health
multiplier or "native") and checks it against sourced facts about the two games: which axis points east,
north and up, how long a unit is, and the maximum health. Each fact carries its source page and the
source's own words, and an unsourced fact can never decide a check. Four checks:

1. **Axis map**: the map the two games' directions imply, derived by a SPARQL rule.
2. **Handedness**: the determinant of the declared map through both bases. A mirror must be declared, and
   must name the world direction it flips.
3. **Unit ratio**: within 2 percent of what the sourced unit lengths imply, over every combination of
   scales a game's sources give.
4. **Health multiplier**: within 0.001 of the host's maximum over the guest's.

Each check answers holds, refused, or undetermined (a fact it needs has no source that could be opened).
The contract runs on both of Open Ontologies' SHACL evaluators, and both must return the same refusals or
nothing is claimed.

Results on the nine rows of the Unit mappings table, as written: three hold (SkyCraft's 70 host units per
block, Faith Runner's 70 per metre, LibertyCraft's 1 metre per block), six are undetermined, and none is
refused. Against Skyrim's "128 world units is equal to 6 feet" (Creation Kit wiki), 70 per block is off by
0.0125 percent. Read from SkyCraft's own design notes, its axis map (`mc.z = -sky.y / 70`) is exactly the
map the checker derives from the two wikis, and its handedness holds. What a merge author can take from the
rows:

- **"Source unit" names no length.** Valve's Unit page gives "roughly 1 inch, 0.75 inches, or 2-3
  centimeters". Minecraft x Half-Life's 40 units per block implies 33.3333 to 52.4934 across the three
  scales (0 to 23.8 percent off), and Garry's Redemption's 0.01905 m per unit is exactly the 0.75-inch
  scale and 25 percent off the 1-inch one. Both rows fit some Valve scale; neither says which.
- **Two rows are gameplay scales.** Killcraft's README says its 2 units per block are there because "2 makes
  the Minecraft player about V1's height", and the 2010 Rust Rewrite Mashup's `voxel.rs` picks 36 so the
  70-unit soldier is "about two blocks tall". Neither is a measurement, and no source we could open gives
  either host's unit length.
- **The health row is a damage constant.** "MC 20 to HL 100 (x5)" matches the proportional policy, so it
  holds. In the project's code the constant is `kMcToHlDamage`, it scales Minecraft hits into Half-Life
  damage, and Minecraft keeps ownership of the player's health (`MinecraftOwnsHealth()`).
- **"1 metre per block" is a fact about Minecraft only.** It holds whatever the host is, so LibertyCraft's
  row says nothing about GTA IV's unit.
- **No GTA V source we could open gives its axes or unit length.** The GTA V example's "1 GTA metre = 1
  block" holds as a fact about Minecraft, but its coordinate map also makes 1 GTA unit per block, and that
  and its axis map stay undetermined.
- **The Faith Runner row does not match its link.** The linked repository is a Bevy rewrite of Mirror's
  Edge movement whose tuning file works in Unreal units ("1 uu = 1 cm"), and it does not mention Skyrim.
  The row's 70 is consistent with Skyrim's unit, so it holds as written, but we could not find where it
  comes from.
- **NewVegasCraft's map agrees on east and north.** No GECK page we could open says which axis points up,
  so its axis and handedness checks stay undetermined.

Twelve declarations that are wrong on purpose (a naive x/y/z copy, an undeclared mirror, two guest axes on
one host axis, 64 or 1000 units per block, health times 4, and others) are all refused. Three more bridge
files (a ratio typed as a double, forged derived values, an injected game fact) are refused by an input
guard before the rule runs. The full tables, with every source and quote, are in
[docs/BRIDGES.md](https://github.com/fabio-rovai/asset-passport/blob/main/docs/BRIDGES.md).

### Items and damage
1. **One hub vocabulary, one profile per game.** Each game publishes a Turtle profile: its health scale
   (`ga:maxPlayerHealth 20`), whether its moves are typed, and a mapping of its own words into a shared hub
   (`craft:BlastBlock rdfs:subClassOf ga:Explosive`). N games need N mappings instead of a conversion for
   each direction of each pair, N(N-1).
2. **Let the engine derive what the thing is.** Blockcraft's profile says that anything made of crystal is
   Rock-typed, as two `owl:hasValue` restrictions joined by `rdfs:subClassOf`.
   [Open Ontologies](https://github.com/fabio-rovai/open-ontologies) reasons with OWL 2 RL plus its hasValue
   rules (profile `owl-rl-ext`) and writes a derivation certificate, which the Lean checker `oo-cert`
   accepts. The Crystal Sword's Rock type takes four of its 14 certified steps. This engine does not
   evaluate `owl:propertyChainAxiom` (measured: a two-step chain derived nothing), which is why the
   alignment uses hasValue restrictions.
3. **Convert by the host's declared rule.** One SPARQL CONSTRUCT reads a customs declaration
   (`?item ga:importTarget ?host`) and keeps each number's share of a player's health: 6 of 20 HP becomes
   30 of 100. That is a policy, not a fact; a host that wants native damage declares a different rule. The
   thing carries the game its numbers are written in (`ga:fromGame`), which is the bridge-contract note's
   "put the unit in the message", made checkable.
4. **The host's border is a SHACL contract.** Refusals are violations, such as
   `ga:damageInTarget sh:maxExclusive 100` (nothing may knock out a full-health creature in one turn).
   Losses, such as types dropped on the way into a game without types, are warnings in a separate file.

| Thing | Into | Verdict from the engine |
|---|---|---|
| Crystal Sword, 6 of 20 HP | Pocket Battlers | converted: power 30 of 100, type `ga:Rock` derived |
| Blast Block, 22 of 20 HP | Pocket Battlers | refused: 110 would knock out a full-health creature |
| Sunfruit, heals 6 plus 4 bonus HP | Pocket Battlers | converted with loss: heals 30, bonus dropped |
| Emberfox, Fire, 100 HP, move power 45 | Blockcraft | converted with loss: a pet with 20 HP hitting for 9, type dropped |
| Capture Orb | Blockcraft | refused at the border |
| Fizz Tonic, heals 40 of 100 | Blockcraft | converted: heals 8 of 20 |

When the item travels as a file, Asset Passport packs the graph and the certificate (`onto_pack`), the
source signs the pack's content digest with an Ed25519 key published in its profile, and the host checks
signature, digests and certificate, the source's published rules, its own reasoning over the item, and the
border, in that order. Of seven forgeries tried on the Capture Orb, six are stopped at four different
gates, and the seventh is gotcha 9. The gates and forgeries are listed in the
[Asset Passport README](https://github.com/fabio-rovai/asset-passport).

## Gotchas
1. **A contract that writes "Source unit" has left out the most important fact.** **Symptom:** two bridges
   built on Valve units disagree by 25 percent and both look right. **Cause:** Valve documents three scales
   and neither row names one. **Fix:** in the contract, name the scale and link the page it comes from; mark
   a ratio chosen for feel (Killcraft's 2, the 2010 mashup's 36) as a gameplay scale, not a measurement.
2. **SPARQL arithmetic chains associate to the right.** **Symptom:** `7/20*100` came out as 0.0035, and
   `8-3-2` evaluates to 7. **Cause:** the SPARQL parser on Oxigraph's 0.5 release line groups chains of `+`
   and `-`, or of `*` and `/`, from the right, so `8-3+2` is 3 and `12/6*2` is 1. The engine here pins
   Oxigraph 0.5.9 plus one unrelated store patch (spargebra 0.4.6); pyoxigraph 0.5.9 and 0.5.11 give the
   same values. Oxigraph's unreleased main branch groups spaced chains from the left, but still mis-groups a
   sign written against the digits after an operand: `10 - 2 -3` gives 11 there, not 5 (measured at
   25f1aea). The bug is reported upstream as
   [oxigraph/oxigraph#1970](https://github.com/oxigraph/oxigraph/issues/1970). **Fix:** parenthesise every
   chain in a conversion rule and pin the converted numbers in a test.
3. **Decimal arithmetic can return nothing, with no error.** **Symptom:** a unit check against Skyrim's
   implied 69.99... units per block came back undetermined for a declared ratio of about 171 or more,
   however wrong it was. **Cause:** in the same engine, `xsd:decimal` multiplication and division return no
   value, as if the result overflowed, though none of these inputs overflows: `0.0 * 0.5`, `(1/3) * 0.5`,
   `0.0 / 0.5` and `171 / 69.991251093613298337` are unbound, while `(1/3) * 2`, `0.0 / 2.0` and
   `170 / 69.991251093613298337` have values. On Oxigraph's unreleased main, products whose exact value fits
   in 18 fractional digits (such as `0.0 * 0.5`) were fixed by
   [oxigraph/oxigraph#1949](https://github.com/oxigraph/oxigraph/pull/1949); division and longer products
   still return nothing (reported as
   [oxigraph/oxigraph#1975](https://github.com/oxigraph/oxigraph/issues/1975)). **Fix:** compute error terms in `xsd:double`, and refuse a check whose value is
   missing instead of reading a missing value as "unknown".
4. **The two SHACL evaluators implement different subsets.** **Symptom:** one evaluator gave a verdict on a
   contract and the other gave none. **Cause (measured on one small shape each):** the default evaluator
   skips `sh:equals` and withholds its verdict; the verified `oo-shacl` returns undetermined for
   `sh:maxInclusive` on an `xsd:double` and for an `sh:pattern` that uses `+` (`^[a-z]+$` and `^a+$` are
   declined, `^[a-z]$` and `^a*$` are judged). **Fix:** write contracts in the subset both evaluate
   (`sh:in`, `sh:class`, decimal bounds, patterns without `+`), and treat disagreement as no verdict.
5. **The verified evaluator passes an empty store and ignores severity.** **Symptom:** "conforms" with no
   item loaded, and warnings that refused items. **Cause:** with nothing to target it conforms vacuously,
   and it lists `sh:severity` among the predicates it ignored. **Fix:** require at least one focus node
   (the default evaluator reports the focus-node count), and keep warnings in a separate file that only the
   default evaluator runs.
6. **`onto_load` with a file path replaces the store.** **Symptom:** the item vanished after the host
   profile loaded. **Cause:** the MCP tool loads a path through a registry slot, which clears the store
   first (measured: one triple left after loading a one-triple file onto a store that held another).
   **Fix:** load files as inline Turtle (the `turtle` argument), which adds to the store.
7. **A proof over doctored rules still checks.** **Symptom:** a Capture Orb crossed as a healing item
   carrying a valid certificate. **Cause:** the sender packed a profile that said so, and `oo-cert` checks
   steps against the premises it is given. **Fix:** compare the passport's rules with the source game's
   published profile, comparing blank nodes by their whole nested structure: a sender can swap the
   `owl:hasValue` of two restrictions and pass a comparison that only erases blank-node labels.
8. **Omission passes a proof.** **Symptom:** after deleting the inferred `orb a ga:CaptureDevice` and
   recomputing both SHA-256 digests, the orb was admitted. **Cause:** a certificate shows that what it says
   follows, never that it said everything that follows, and a digest is not a signature. **Fix:** sign the
   exports, and have the host reason over the item and refuse a passport that leaves out a conclusion it
   can derive.
9. **A lie by the source gets through, signed.** **Symptom:** an orb that the source game itself exports as
   a tonic, under its real profile and signed with its real key, crosses as a tonic. **Cause:** a signature
   proves who issued a passport and that nobody changed it since, not that the issuer told the truth.
   **Fix:** none in this technique; it needs evidence the source does not control, such as a catalogue
   published ahead of time. A passport is also a bearer document, so a host that must not take the same
   thing twice keeps its own record of what it admitted.

## Verification
- Run here: Asset Passport main at a67c4c1 (tag v0.2.0 is 3ff85ff), `python3 -m pytest -q tests` against
  Open Ontologies built from main at ce9415e (reports version 2.1.0, unreleased), with `oo-cert` and
  `oo-shacl` built from the same tree. Exporting and admitting a signed passport needs
  [open-ontologies#266](https://github.com/fabio-rovai/open-ontologies/pull/266), which landed after the
  v2.0.1 release; the direct lane (`python3 -m passport judge`) runs on v2.0.1.
- Gotchas 2 to 6 were re-measured on that engine for this note. The Oxigraph values in gotchas 2 and 3 were
  also measured with pyoxigraph 0.5.9 and 0.5.11, and the main-branch values on a build of Oxigraph main at
  25f1aea.
- Not verified: anything in a real game. No retail game was modded, and no bridge listed above was run; the
  bridge verdicts compare declarations with documented facts only. Game facts come from wiki pages that do
  not always name the game they are applied to (the GECK wiki pages never name New Vegas; the Valve Unit
  page is about "Id Software and Valve engines" in general); `docs/BRIDGES.md` marks each such reading as
  our inference. Offsets, angles, origins, ownership and lifecycle are outside the checker.

## Seen in
- [Asset Passport](https://github.com/fabio-rovai/asset-passport) v0.2.0 (MIT): the bridge checker, both
  browser games, every gate and every forgery.

## Declarations checked
None of these projects used this technique. Their declarations were the input to the bridge checker: the
Unit mappings table and gotcha 1 of
[bridge-contracts-ownership-units-and-lifecycle.md](bridge-contracts-ownership-units-and-lifecycle.md)
(credited there to LeiiLo and Claude Code), and the projects it lists:
[SkyCraft](https://github.com/chasmlol/SkyCraft), [LibertyCraft](https://github.com/mrborghini/libertycraft),
[NewVegasCraft](https://github.com/Davozh/new-vegascraft),
[Minecraft x Half-Life](https://github.com/SawyerTheNerd/Minecraft-X-HalfLife),
[Faith Runner](https://github.com/tnrjns/faith-runner), [Killcraft](https://github.com/goonsn/Killcraft),
[Garry's Redemption](https://github.com/codeByAlexff/garrys-redemption) and the
[2010 Rust Rewrite Mashup](https://github.com/chasmlol/2010-rust-rewrite-mashup).
