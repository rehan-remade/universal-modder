---
kind: technique
title: "HarmonyX transpiler: find branches by opcode, and pop their operands when you remove one"
game: ""
games_also: []
game_version: "ULTRAKILL 2.7.2 (Unity 2022.3.29), BepInEx 5.4.23.5 with its HarmonyX 2.9.0 (BepInEx/core/0Harmony.dll)"
platform: windows
engine: unity-mono
route: managed-patch
tools: ["dotnet 8 (netstandard2.1)", "HarmonyX 2.9.0 transpiler", "BepInEx 5.4 ManualLogSource"]
anti_cheat: "none (single-player; keep modded runs off the Steam leaderboards)"
status: working
agents: ["Bionic (LM Studio, model not recorded)"]
humans: ["voltz"]
date: 2026-10-25
links:
  - "https://github.com/BepInEx/HarmonyX"
  - "https://github.com/BepInEx/BepInEx"
  - "https://harmony.pardeike.net/articles/patching-transpiler.html"
tags: [harmonyx, transpiler, il, branch-detection, unity, unity-mono, bepinex, gotcha]
---

# HarmonyX transpiler: find branches by opcode, and pop their operands when you remove one

> When rewriting IL in a HarmonyX transpiler (Unity Mono games), match branch instructions by **OpCode
> struct equality** (`op == OpCodes.Blt`, `op == OpCodes.Brfalse`, etc.), and when you remove a conditional
> branch, `pop` the values it would have consumed. In this session two other checks (`operand is Label` and
> `opcode.FlowControl`) seemed to match non-branch instructions such as an `ldc.r4`; neither check can do
> that, so the wrong index came from somewhere else in the transpiler (Gotcha 1). Used for an ULTRAKILL mod
> that lets you ride a rocket from the ground, confirmed in game.

## Setup

- **Game:** ULTRAKILL 2.7.2 (Steam), Unity 2022.3.29.9261324, .NET 4.x Mono runtime
- **Loader:** BepInEx 5.4.23.5, installed into the mod manager profile (not part of the game, not NuGet)
- **Harmony:** HarmonyX 2.9.0, the `0Harmony.dll` in that BepInEx's `core/` folder (not NuGet HarmonyX)
- **OS:** Windows 11 25H2 (build 26200)
- **Compiler:** dotnet 8 SDK, targeting `netstandard2.1`, referencing BepInEx's own `0Harmony.dll` and
  `BepInEx.dll` (BepInEx 5's core assembly; `BepInEx.Core.dll` is the BepInEx 6 name)
- **Mod manager:** Thunderstore Mod Manager profiles (plugins live under `profiles/<name>/BepInEx/plugins/`)
- **Leaderboards:** ULTRAKILL is single-player, but levels and the Cyber Grind have public Steam leaderboards.
  Keep a movement change like this out of runs that submit; other ULTRAKILL mods switch submission off
  themselves (UltraPortal for levels where its guns were used, Grenade Launcher for the Cyber Grind).

## The problem

In a HarmonyX transpiler you often need to find and replace branch instructions (e.g. `blt`, `brfalse`)
to alter control flow. The two "obvious" detection methods both seemed to fail:

### 1. `operand is System.Reflection.Emit.Label`: matched the instruction next to the branch

```csharp
// INTENDED: match only branch instructions (blt, brfalse, br, etc.)
if (list[i].operand is System.Reflection.Emit.Label) { /* found a branch */ }
```

**Symptom:** The transpiler replaced `ldc.r4 45` (pushes a value) with `pop` (pops a value), inverting the
stack operation. The real `blt` and `brfalse` were never touched, so vanilla behaviour persisted.

**Diagnosis:** The log showed `branch1=300` pointing at `ldc.r4 operand=45` instead of
`branch1=301` pointing at `blt operand=Label`. That is an index one short of the branch, not a check
that matched a `float`: HarmonyX passes `ldc.r4`'s operand through as a boxed `float`, `Label` is a struct,
and a boxed `float` never passes `is Label` (Gotcha 1).

### 2. `opcode.FlowControl` flag: same symptom

An earlier attempt used:
```csharp
if (list[i].opcode.FlowControl == FlowControl.Branch ||
    list[i].opcode.FlowControl == FlowControl.Cond_Branch)
```
This also seemed to match non-branch instructions. `CodeInstruction.opcode` is the runtime's own
`System.Reflection.Emit.OpCode` (HarmonyX looks it up in `OpCodes` by value), so `FlowControl` is the
runtime's entry for that opcode (`Next` for `ldc.r4`), and HarmonyX can't change it. What the flag does
include is `leave` (`Branch`) and `switch` (`Cond_Branch`), and it doesn't tell you how many values a
branch pops.

### What works: OpCode struct equality

`OpCode` is a struct (`OpCodes` is the class with one static field per opcode), and `==` compares the opcode
value. HarmonyX's own `Branches(out Label?)` helper works the same way, with a `HashSet<OpCode>` of the 26
branch opcodes. Two things to know:

- C# compiles float comparisons to the unordered forms too: `if (x < 45f) { ... }` jumps around the block
  with `bge.un`. Include the `.un` opcodes.
- HarmonyX hands transpilers long forms only: it rewrites `blt.s` to `blt`, `brfalse.s` to `brfalse` and so
  on before each transpiler runs (`NormalizeInstructions` in `ILManipulator.cs`). The `_S` cases below are
  harmless but never match there.

```csharp
static bool IsBranch(OpCode op)
{
    return op == OpCodes.Blt    || op == OpCodes.Blt_S    ||
           op == OpCodes.Ble    || op == OpCodes.Ble_S    ||
           op == OpCodes.Bge    || op == OpCodes.Bge_S    ||
           op == OpCodes.Bgt    || op == OpCodes.Bgt_S    ||
           op == OpCodes.Beq    || op == OpCodes.Beq_S    ||
           op == OpCodes.Bne_Un || op == OpCodes.Bne_Un_S ||
           op == OpCodes.Blt_Un || op == OpCodes.Blt_Un_S ||
           op == OpCodes.Ble_Un || op == OpCodes.Ble_Un_S ||
           op == OpCodes.Bge_Un || op == OpCodes.Bge_Un_S ||
           op == OpCodes.Bgt_Un || op == OpCodes.Bgt_Un_S ||
           op == OpCodes.Brfalse|| op == OpCodes.Brfalse_S||
           op == OpCodes.Brtrue || op == OpCodes.Brtrue_S ||
           op == OpCodes.Br     || op == OpCodes.Br_S;
}
```

## Stack balance when replacing branches

Replacing a branch with a no-op is not free — the branch **pops values from the evaluation stack**.
If you remove the branch, you must pop those values yourself or the stack is unbalanced, and the patched
method fails to compile (Mono's JIT rejects it with `InvalidProgramException`, "Invalid IL code").

| Branch | Pops | Replacement |
|---|---|---|
| `blt`, `ble`, `bge`, `bgt`, `beq`, `bne.un` (+ the other `.un` forms, +`.s`) | 2 (two operands) | 2 × `pop` |
| `brtrue`, `brfalse` (+`.s`) | 1 (a bool) | 1 × `pop` |
| `br`, `br.s` | 0 | nothing (a `nop`) |

```csharp
int pops = IsComparisonBranch(op) ? 2 : (IsConditionalBranch(op) ? 1 : 0);
// Change the instruction in place, so the labels and exception blocks on it survive.
list[branchIdx].opcode = pops > 0 ? OpCodes.Pop : OpCodes.Nop;
list[branchIdx].operand = null;
for (int p = 1; p < pops; p++)
    list.Insert(branchIdx + p, new CodeInstruction(OpCodes.Pop));
// Every index after branchIdx has now moved: patch from the end of the list backwards.
```

Something else may jump to the branch itself (loop conditions often do), and that jump's label lives in the
branch's `labels` list. `list[i] = new CodeInstruction(OpCodes.Pop)` throws it away; changing the opcode in
place, or `new CodeInstruction(OpCodes.Pop).MoveLabelsFrom(list[i])`, keeps it. Harmony's transpiler docs do
the same when they replace a jump target with a `nop` instead of removing it.

**Do NOT** replace a conditional branch with `br` (unconditional jump) to "skip" it — `br` pops nothing, so
the comparison operands stay on the stack and the method fails to compile, as above.

## Other HarmonyX gotchas hit in the same session

1. **`CodeInstruction` does not override `Equals`/`GetHashCode`.**
   Using `Dictionary<CodeInstruction, int>` silently fails on lookups (reference equality only).
   Use a `List` with index-based access or a `HashSet` with a custom comparer.

2. **Transpilers must be static in HarmonyX.**
   `harmony.Patch(method, transpiler: new HarmonyMethod(typeof(MyClass), "Transpiler"))`
   requires the method to be `static`. Share state via a static field set before `Patch()` is called.

3. **BepInEx 5.4 has no `ILogger`.**
   Use `ManualLogSource` (from `BepInEx.Logging`) and pass it explicitly.

4. **Compile against the DLLs you run on, not NuGet.**
   Reference the `0Harmony.dll` and `BepInEx.dll` from the BepInEx `core/` folder the game loads (in a
   Thunderstore profile, the profile's). A newer NuGet HarmonyX lets you call APIs that HarmonyX 2.9.0
   doesn't have, which fail at run time. It doesn't explain the `is Label` match: `Label` is the runtime's
   own type whatever you compile against.

## Verification

- **Oracle:** In-game test — hooked a rocket while standing on the ground (no jump held).
  Vanilla: rocket face-explodes. Modded: player rides the rocket. Confirmed by user in-game.
- **IL dump:** Diagnostic logging before/after the transpiler confirmed the correct instructions
  were identified and replaced (`blt` → 2 pops, `brfalse` → 1 pop, stack balanced).
- **Not verified:** Behaviour when already riding a second rocket (the "already riding" guard
  before the angle check was intentionally left untouched, but not explicitly tested).
- **Not verified:** what put the index one short in the `is Label` and `FlowControl` attempts (Gotchas 1-2).

## Gotchas

1. **The branch search landed on the `ldc.r4` next to the `blt`.** In the ULTRAKILL session, checking
   `CodeInstruction.operand is System.Reflection.Emit.Label` seemed to match `ldc.r4` (a `float` operand) at
   index 300, one before the `blt` at 301.
   **Cause:** not pinned down, but it isn't the check. HarmonyX copies `ldc.r4`'s operand from Cecil as a
   boxed `float` and turns branch targets into `Label`s (`ILManipulator.cs`), and a boxed `float` never passes
   `is Label`, whatever assemblies the mod was compiled against. An index that went stale (an `Insert` or
   `RemoveAt` earlier in the list after the index was taken) is the usual way to land one instruction off.
   **Fix:** Use `OpCode` struct equality (`op == OpCodes.Blt`, etc.), which also leaves out `leave` (whose
   operand is a `Label` too). Patch from the end of the list backwards, and log `i`, `list[i].opcode` and
   `list[i].operand?.GetType()` at the moment of the match.

2. **`FlowControl` seemed to match non-branch instructions too.** Same session, same symptom.
   **Cause:** not the flag either: `FlowControl` comes from the runtime's opcode table (`ldc.r4` is `Next`).
   It does include `leave` and `switch`.
   **Fix:** Same as above — check the opcode value directly.

3. **Replacing a conditional branch with `br` corrupts the stack.** A branch instruction pops its operands;
   an unconditional jump does not. If you replace `blt` with `br`, the two floats remain on the
   stack and the method fails to compile (`InvalidProgramException` on Mono).
   **Fix:** Replace with the correct number of `pop` instructions (2 for comparison branches,
   1 for conditional branches, 0 for unconditional).

4. **`CodeInstruction` has no value equality.** `Dictionary<CodeInstruction, _>` lookups fail
   silently because `Equals`/`GetHashCode` are not overridden.
   **Fix:** Use index-based access into a `List<CodeInstruction>`, or implement a custom
   `IEqualityComparer<CodeInstruction>` that compares `opcode` + `operand`.

5. **Thunderstore Mod Manager profiles change the plugin path.** Plugins are not in
   `<Game>/BepInEx/plugins/` but in `<Thunderstore>/DataFolder/<Game>/profiles/<name>/BepInEx/plugins/`.
   Deploying to the wrong path means the mod silently doesn't load.
   **Fix:** Check the Thunderstore profile path, not the game folder.
