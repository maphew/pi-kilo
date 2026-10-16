# pi-extensions

Pi extensions used with this project.

## beads-prime

Injects live Beads (`bd prime`) context into pi's system prompt.

pi has no bd `SessionStart` hook (unlike Claude Code, Cursor, and Codex), so
without this an agent must remember to run `bd prime` itself. The extension:

- on `session_start`, finds the nearest `.beads/` workspace and runs
  `bd prime --hook-json`, caching the returned `additionalContext`;
- on `before_agent_start`, adds that text as a `<beads>` system-prompt section,
  so the live `agent.profile` / git-authority policy and workflow rules stay
  current and survive compaction;
- otherwise no-ops (no `bd` process is spawned outside a Beads workspace).

It is generic — the same file works in every Beads repository on every machine.

### Install

Symlink or copy the file into pi's user extensions directory:

```bash
ln -sf "$(pwd)/pi-extensions/beads-prime.ts" ~/.pi/agent/extensions/beads-prime.ts
```

Or, from anywhere, load it for a single run:

```bash
pi -e /path/to/pi-extensions/beads-prime.ts
```

Use the in-session `/beads` command to report or refresh the injected context.

### Configuration

| Env var | Effect |
| --- | --- |
| `BD_BIN` | Path/name of the `bd` binary (default: `bd`) |
| `PI_BEADS_PRIME_DISABLE=1` | Disable the extension |
| `BEADS_DIR` | Honored when set to a `.beads` dir or workspace root |

### Notes

- Requires `bd` on `PATH` (or `BD_BIN`). If `bd prime` fails, the session still
  starts; the failure is reported via a notification and hidden in print/JSON modes.
- `bd prime` is invoked once per session start (and on `/beads`), not per turn.

### Making it portable across machines

The file is plain TypeScript with no dependencies, so it can be copied or
symlinked on each machine. For one-command installs, wrap it as a pi package
(`package.json` with a `pi.extensions` manifest) published to npm or a git
repository and install with `pi install <source>`.
