/**
 * universal-modder: OpenCode 2 plugin.
 *
 * Exposes the `um` CLI as one passthrough tool (`um_run`, plus `um --help` behaviour) and registers
 * the fal MCP server. The CLI itself is never modified: the agent always calls the same launcher a
 * human would.
 */
import { spawn } from "node:child_process"
import { accessSync, constants } from "node:fs"
import { homedir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { Plugin } from "@opencode/plugin"

/** plugins/opencode/index.ts -> repository root */
const PLUGIN_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..")

/**
 * OpenCode substitutes `{env:VAR}` only while it reads config files, not in a config a plugin sets,
 * so the key is read from the environment here.
 */
function falMcp(key: string) {
  return {
    type: "remote" as const,
    url: "https://mcp.fal.ai/mcp",
    headers: { Authorization: `Bearer ${key}` },
    oauth: false as const,
    disabled: false,
  }
}

/** `~` and `~/...` as the user's home; relative paths against `base`. */
function expandPath(path: string, base: string): string {
  if (path === "~") return homedir()
  if (path.startsWith("~/") || path.startsWith("~\\")) return join(homedir(), path.slice(2))
  return resolve(base, path)
}

/**
 * The CLI groups (`GROUPS` in `um/cli.py`). Kept here so the tool description can name them and so a
 * typo can be answered without spawning a process. `tests/test_opencode_plugin.py` asserts this list
 * against `um/cli.py`, so a new group cannot go unnoticed.
 */
const GROUPS = [
  { name: "scan", blurb: "find installed games and report engine, anti-cheat, loaders, saves and modding routes" },
  { name: "fal", blurb: "generate art through fal: sprites, textures, PBR maps, 3D models, rigs, SFX, music, voice, video" },
  { name: "comfy", blurb: "generate images on a local ComfyUI server, no API key (status / image / run)" },
  { name: "sprixen", blurb: "2D sprites through Sprixen: one style per project, animation sheets, terrain tiles" },
  { name: "voidless", blurb: "2D sprites through Voidless: 8-way turns and animation sets that keep one size" },
  { name: "sprite", blurb: "turn generated art into engine-ready sprites: trim, pixelate, palette, sheets and strips" },
  { name: "render3d", blurb: "render a 3D model to isometric, side-view or top-down sprite frames with Blender" },
  { name: "video", blurb: "build contact sheets and EDL-driven showcase video edits with ffmpeg" },
  { name: "win", blurb: "launch, screenshot, send input to and record a game window on Windows (also from WSL)" },
  { name: "backup", blurb: "snapshot and restore a game's save files before a modded launch" },
  { name: "publish", blurb: "pre-release lint for a mod: no game files, no decompiled code, no leaked keys" },
  { name: "kb", blurb: "search, scaffold, check and index the field-note knowledge base (search / new / check / index)" },
  { name: "fastfile", blurb: "list and dump the rawfiles (GSC, CSC, menus) in Call of Duty 4 / World at War fastfiles (.ff)" },
  { name: "iwi", blurb: "convert and decode Call of Duty IWI v6 textures (png2iwi / iwi2png)" },
  { name: "weapon", blurb: "inspect, edit, clone, and diff Call of Duty weapon files" },
]

const GROUP_NAMES = new Set(GROUPS.map((group) => group.name))

function resolveUm(root: string, override?: string): string {
  if (override) return override
  // bin/um is a bash script, which Windows can't spawn directly; there, `um` must be on PATH.
  if (process.platform === "win32") return "um"
  const local = join(root, "bin", "um")
  try {
    accessSync(local, constants.X_OK)
    return local
  } catch {
    return "um" // installed with `uv tool install` and already on PATH
  }
}

function run(
  command: string,
  args: string[],
  cwd: string,
  signal: AbortSignal,
): Promise<{ code: number; out: string; err: string }> {
  return new Promise((done) => {
    const child = spawn(command, args, { cwd, signal, env: process.env })
    let out = ""
    let err = ""
    child.stdout?.setEncoding("utf8")
    child.stderr?.setEncoding("utf8")
    child.stdout?.on("data", (chunk) => (out += chunk))
    child.stderr?.on("data", (chunk) => (err += chunk))
    child.on("error", (error) => done({ code: -1, out, err: `${err}${String(error)}` }))
    child.on("close", (code) => done({ code: code ?? -1, out, err }))
  })
}

export default Plugin.define({
  id: "universal-modder",
  async setup(ctx) {
    // The project this plugin instance is loaded for; the OpenCode server's own cwd may be elsewhere.
    const project = ctx.location.directory
    const root = typeof ctx.options.root === "string" ? expandPath(ctx.options.root, project) : PLUGIN_ROOT
    const um = resolveUm(root, typeof ctx.options.command === "string" ? ctx.options.command : undefined)

    // Give the session fal's asset server, unless the user configured their own or has no FAL_KEY.
    await ctx.mcp.transform((editor) => {
      const key = process.env.FAL_KEY
      if (key && !editor.get("fal")) editor.set("fal", falMcp(key))
    })

    await ctx.tool.transform((editor) => {
      editor.namespace({
        name: "um",
        description: `universal-modder toolkit (${um}). ` +
          "Recon a game, generate assets, build sprites, verify in-game, and publish, and read the shared " +
          "knowledge base of how other games were modded before starting.",
      })

      editor.add({
        name: "run",
        description:
          "Run the universal-modder `um` CLI. `args` is the command line after `um`, so " +
          `["scan"] recon a game, ["scan", "--help"] documents the group, ` +
          `["kb", "search", "<game or engine>"] reads the shared knowledge base, ` +
          `["backup", "create"] snapshots saves before a modded launch. Groups: ` +
          GROUPS.map((group) => group.name).join(", ") +
          ".",
        input: {
          type: "object",
          properties: {
            args: {
              type: "array",
              items: { type: "string" },
              description: "Arguments for `um`, e.g. [\"kb\", \"search\", \"disrupt\"] or [\"scan\", \"--help\"].",
            },
            cwd: { type: "string", description: "Working directory. Defaults to the project directory." },
          },
          required: ["args"],
          additionalProperties: false,
        },
        options: { namespace: "um", codemode: true },
        execute: async (input, context) => {
          const parsed = (input ?? {}) as { args?: string[]; cwd?: string }
          const args = parsed.args ?? []
          const cwd = parsed.cwd ? expandPath(parsed.cwd, project) : project
          const head = args[0]

          if (head && !head.startsWith("-") && !GROUP_NAMES.has(head)) {
            return {
              content:
                `unknown group "${head}". Groups: ${GROUPS.map((group) => group.name).join(", ")}. ` +
                "Call `um --help` (or a group with `[\"<group>\", \"--help\"]`) for the full list.",
            }
          }

          const result = await run(um, args, cwd, context.signal)
          const body = [result.out.trimEnd(), result.err.trimEnd()].filter(Boolean).join("\n")
          return {
            content: `um ${args.join(" ")}` +
              `${result.code === 0 ? "" : ` (exit ${result.code})`}\n\n${body || "(no output)"}`,
          }
        },
      })
    })
  },
})
