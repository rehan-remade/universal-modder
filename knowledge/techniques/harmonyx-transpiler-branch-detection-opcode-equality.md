---
kind: technique
title: "HarmonyX transpiler: detect branch instructions by OpCode equality, not operand type or FlowControl"
game: ""
games_also: []
game_version: "ULTRAKILL 2.7.2 (Unity 2022.3.29), BepInEx 5.4.23.5, HarmonyX (shipped in game's core/)"
platform: windows
engine: unity-mono
route: managed-patch
tools: ["dotnet 8 (netstandard2.1)", "HarmonyX transpiler", "BepInEx 5.4 ManualLogSource"]
anti_cheat: "none"
status: working
agents: ["Bionic (LM Studio)"]
humans: ["voltz"]
date: 2026-10-25
links: []
tags: [harmonyx, transpiler, il, branch-detection, unity, unity-mono, bepInEx, gotcha]
---

# HarmonyX transpiler: detect branch instructions by OpCode equality, not operand type or FlowControl

> When rewriting IL in a HarmonyX transpiler (Unity Mono games), two common ways to identify
> branch instructions — checking `CodeInstruction.operand is System.Reflection.Emit.Label`
> and checking `opcode.FlowControl` — both produced **false positives** in the HarmonyX build
> shipped with ULTRAKILL. The only reliable check is **OpCode struct equality**
> (`op == OpCodes.Blt`, `op == OpCodes.Brfalse_S`, etc.).

## Setup

- **Game:** ULTRAKILL 2.7.2 (Steam), Unity 2022.3.29.9261324, .NET 4.x Mono runtime
- **Loader:** BepInEx 5.4.23.5 (shipped in game, not NuGet)
- **Harmony:** HarmonyX as bundled in the game's `core/` folder (not NuGet HarmonyX)
- **OS:** Windows 10 (10.0.26200)
- **Compiler:** dotnet 8 SDK, targeting `netstandard2.1`, referencing the game's own `0Harmony.dll` and `BepInEx.Core.dll`
- **Mod manager:** Thunderstore Mod Manager profiles (plugins live under `profiles/<name>/BepInEx/plugins/`)

## The problem

In a HarmonyX transpiler you often need to find and replace branch instructions (e.g. `blt`, `brfalse`)
to alter control flow. The two "obvious" detection methods both failed:

### 1. `operand is System.Reflection.Emit.Label` — FALSE POSITIVE

```csharp
// INTENDED: match only branch instructions (blt, brfalse, br, etc.)
if (list[i].operand is System.Reflection.Emit.Label) { /* found a branch */ }
```

**Symptom:** In the ULTRAKILL HarmonyX build, this matched `ldc.r4` (operand = `45f`, a `System.Single`).
A `float` is a value type and cannot be a `Label` instance, yet the `is` check returned `true`.
The transpiler replaced `ldc.r4 45` (pushes a value) with `pop` (pops a value), inverting the
stack operation. The real `blt` and `brfalse` were never touched, so vanilla behaviour persisted.

**Diagnosis:** The log showed `branch1=300` pointing at `ldc.r4 operand=45` instead of
`branch1=301` pointing at `blt operand=Label`.

### 2. `opcode.FlowControl` flag — ALSO UNRELIABLE

An earlier attempt used:
```csharp
if (list[i].opcode.FlowControl == FlowControl.Branch ||
    list[i].opcode.FlowControl == FlowControl.Cond_Branch)
```
This also matched non-branch instructions in the same HarmonyX build.

### What works: OpCode struct equality

`OpCode` is a struct wrapping an `OpCodes` enum. `==` compares the underlying value. This is
guaranteed to work regardless of any HarmonyX wrapper quirks:

```csharp
static bool IsBranch(OpCode op)
{
    return op == OpCodes.Blt    || op == OpCodes.Blt_S    ||
           op == OpCodes.Ble    || op == OpCodes.Ble_S    ||
           op == OpCodes.Bge    || op == OpCodes.Bge_S    ||
           op == OpCodes.Bgt    || op == OpCodes.Bgt_S    ||
           op == OpCodes.Beq    || op == OpCodes.Beq_S    ||
           op == OpCodes.Bne_Un || op == OpCodes.Bne_Un_S ||
           op == OpCodes.Brfalse|| op == OpCodes.Brfalse_S||
           op == OpCodes.Brtrue || op == OpCodes.Brtrue_S ||
           op == OpCodes.Br     || op == OpCodes.Br_S;
}
```

## Stack balance when replacing branches

Replacing a branch with a no-op is not free — the branch **pops values from the evaluation stack**.
If you remove the branch, you must pop those values yourself or the stack is unbalanced and the
method will throw `BadImageFormatException` or silently corrupt.

| Branch | Pops | Replacement |
|---|---|---|
| `blt`, `ble`, `bge`, `bgt`, `beq`, `bne.un` (+`.s`) | 2 (two operands) | 2 × `pop` |
| `brtrue`, `brfalse` (+`.s`) | 1 (a bool) | 1 × `pop` |
| `br`, `br.s` | 0 | nothing (just delete) |

```csharp
int pops = IsComparisonBranch(op) ? 2 : (IsConditionalBranch(op) ? 1 : 0);
list[branchIdx] = new CodeInstruction(OpCodes.Pop);
for (int p = 1; p < pops; p++)
    list.Insert(branchIdx + p, new CodeInstruction(OpCodes.Pop));
```

**Do NOT** replace a branch with `br.s` (unconditional jump) to "skip" it — the popped values
remain on the stack and every subsequent instruction sees a corrupted stack.

## Other HarmonyX gotchas hit in the same session

1. **`CodeInstruction` does not override `Equals`/`GetHashCode`.**
   Using `Dictionary<CodeInstruction, int>` silently fails on lookups (reference equality only).
   Use a `List` with index-based access or a `HashSet` with a custom comparer.

2. **Transpilers must be static in HarmonyX.**
   `harmony.Patch(method, transpiler: new HarmonyMethod(typeof(MyClass), "Transpiler"))`
   requires the method to be `static`. Share state via a static field set before `Patch()` is called.

3. **BepInEx 5.4 has no `ILogger`.**
   Use `ManualLogSource` (from `BepInEx.Logging`) and pass it explicitly.

4. **Compile against the game's own DLLs, not NuGet.**
   If the game ships its own `0Harmony.dll` and `BepInEx.Core.dll` in `core/`, reference those.
   NuGet HarmonyX may have different type identities, causing `is` checks and type comparisons
   to fail at runtime (possibly the root cause of the `is Label` false positive).

## Verification

- **Oracle:** In-game test — hooked a rocket while standing on the ground (no jump held).
  Vanilla: rocket face-explodes. Modded: player rides the rocket. Confirmed by user in-game.
- **IL dump:** Diagnostic logging before/after the transpiler confirmed the correct instructions
  were identified and replaced (`blt` → 2 pops, `brfalse` → 1 pop, stack balanced).
- **Not verified:** Behaviour when already riding a second rocket (the "already riding" guard
  before the angle check was intentionally left untouched, but not explicitly tested).

## Gotchas

1. **`is Label` returns true for non-branch operands.** In the HarmonyX build shipped with
   ULTRAKILL (compiled against the game's own `0Harmony.dll`), checking
   `CodeInstruction.operand is System.Reflection.Emit.Label` matched `ldc.r4` (a `float` operand).
   **Cause:** Likely a type-identity mismatch between the game's `System.Reflection.Emit.Label`
   and the one in the transpiler's compilation context, or a HarmonyX wrapper bug.
   **Fix:** Use `OpCode` struct equality (`op == OpCodes.Blt`, etc.). Never rely on operand type
   checks for instruction classification.

2. **`FlowControl` flag is also unreliable.** Same HarmonyX build, same symptom — non-branch
   instructions reported as `FlowControl.Branch` or `FlowControl.Cond_Branch`.
   **Fix:** Same as above — check the opcode value directly.

3. **Replacing a branch with `br.s` corrupts the stack.** A branch instruction pops its operands;
   an unconditional jump does not. If you replace `blt` with `br.s`, the two floats remain on the
   stack and every subsequent instruction is offset.
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
