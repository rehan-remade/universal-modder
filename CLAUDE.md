@AGENTS.md

## Claude Code specifics
- Installed as a plugin, the skills are namespaced (`/universal-modder:mod-any-game`), the fal MCP server comes
  from `.mcp.json` (needs `FAL_KEY` in the environment), and a SessionStart hook puts `um` on PATH.
- Without `FAL_KEY`, `.mcp.json` sends the literal `${FAL_KEY}`, fal answers 401, and Claude Code doesn't fall
  back to OAuth while a header is set. Start Claude Code with the key set, or add fal's OAuth endpoint as a
  second server (`claude mcp add --transport http fal-oauth https://mcp.fal.ai/mcp-relay`) and authenticate
  it in `/mcp`.
- In a clone, `.claude/settings.json` adds the same PATH hook, and `.claude/skills` is a copy of `skills/`.
- `agents/` holds a three-agent team for long mods: `mod-orchestrator`, run as the main session, spawns
  `mod-game-worker` and `mod-offline-worker`. Claude Code loads `agents/` only from a plugin, so in a clone
  start it with `claude --plugin-dir . --agent mod-orchestrator` (installed: `claude --agent mod-orchestrator`).
