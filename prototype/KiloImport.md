# Continue a Kilo session in Pi

`prototype/pi-kilo` fetches a Kilo Cloud session, converts its history to Pi's
session JSONL format, and continues it locally with Pi — the Pi-side equivalent
of `kilo --session <ses_id> --cloud-fork`.

This is **history import + local continuation**, not live integration. The Pi
session is a new, independent session that carries the Kilo conversation so far.
Kilo does not see Pi's new turns, and Pi cannot resume Kilo's private runtime
state. See [Honest boundaries](#honest-boundaries).

## Requirements

- `pi` on `PATH` (or `PI_BIN` pointing at it) and `node` available to it.
- `python3` (standard library only; no third-party packages).
- Kilo credentials: run `kilo auth login` once so
  `~/.local/share/kilo/auth.json` holds a Kilo OAuth access token.
- Network access to `https://ingest.kilosessions.ai` (override with
  `KILO_SESSION_INGEST_URL` / `--ingest`).

## Usage

```bash
# Import and immediately continue in Pi (Kilo-style flags)
prototype/pi-kilo --session ses_eb5d6080cffeyzVSJWq1dCcInP --cloud-fork

# Same thing, positional
prototype/pi-kilo ses_eb5d6080cffeyzVSJWq1dCcInP

# Import into a specific project directory and pass flags through to pi
prototype/pi-kilo ses_eb5d6080cffeyzVSJWq1dCcInP --cwd ~/dev/project -- --model kilo/x

# Write the Pi session without launching the TUI
prototype/pi-kilo ses_eb5d6080cffeyzVSJWq1dCcInP --import-only --out /tmp/session.jsonl

# Convert a previously saved cloud export (offline, no credentials)
prototype/pi-kilo --export-json export.json --cwd ~/dev/project --import-only
```

By default the Pi session is written to Pi's normal session directory for
`--cwd`:

```
~/.pi/agent/sessions/--<cwd-slug>--/<timestamp>_<uuid>.jsonl
```

so it also appears in `/resume`. Each import creates a new Pi session; running
the import twice does not overwrite the earlier one.

## What gets converted

| Kilo (cloud export) | Pi session JSONL |
| --- | --- |
| `info` + `title` | session header, `session_info` name, `kilo_import` custom entry (source session id) |
| user `text` parts | user message (`content` string, or text/image blocks when there are several) |
| assistant `text` parts | assistant `text` content blocks |
| assistant `reasoning` parts | assistant `thinking` content blocks |
| assistant `tool` parts (`state.input`) | assistant `toolCall` blocks (Kilo `callID` preserved) |
| completed/errored tool state | one Pi `toolResult` message per call (`isError` on failure) |
| `step-finish` tokens/cost | assistant `usage` (input/output/cache/reasoning totals) |
| `info.finish` | `stopReason` (`tool-calls` → `toolUse`) |

Message and part order follows Kilo's own importer: ascending message/part id,
which is transcript order for cloud exports (they are listed in ingest order).

Skipped and reported in the summary: `step-start`, `step-finish`, `patch`, and
unknown future part types. `patch`/`step-finish` are runtime metadata with no
Pi equivalent; file state is **not** restored from the cloud `sessionDiff`.

## Verification

```bash
# Pi can parse the imported session without calling a model
printf '{"id":"r1","type":"get_state"}\n' \
  | pi --mode rpc --session /tmp/session.jsonl
# -> messageCount equals imported messages; sessionName shows the Kilo id

# Render the conversation as HTML
pi --export /tmp/session.jsonl /tmp/session.html
```

The converter's mapping is covered by unit tests that need no network:

```bash
python3 -m unittest prototype/test_kilo_import.py
```

## Honest boundaries

- **History, not runtime state.** Tool outputs and reasoning text are preserved;
  pending permissions, provider-private reasoning signatures, snapshots, and
  Kilo's workspace diffs are not. The target directory's files are used as-is.
- **One-way, point-in-time.** New Pi turns stay in Pi. Live bidirectional
  messaging and turn-boundary handoff remain the Phase 1/2 goals in `Plan.md`.
- **Different cwd.** Cloud sessions record the machine directory they ran in.
  When it differs from `--cwd`, the importer warns and continues in `--cwd`.
- **Branches/compaction.** The importer takes the linear transcript. Kilo
  branch structure and compaction summaries are not reconstructed.
- **Auth.** The Kilo access token is read from disk and sent only to the Kilo
  ingest endpoint; it is never printed or written into the Pi session. If the
  token has expired, run `kilo auth login`.

## Evidence

Observed against Kilo `ses_eb5d6080cffeyzVSJWq1dCcInP` (324 messages:
3 user, 321 assistant, 349 tool calls) on 2026-10-21:

- import reported `3 user, 321 assistant, 349 tool, 349 toolResult`;
- Pi RPC `get_state` loaded the file with `messageCount: 673`;
- `pi --export` rendered the full conversation to HTML.
