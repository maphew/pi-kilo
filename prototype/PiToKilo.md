# Make Pi sessions available in Kilo

`pi-kilo import` converts Pi session JSONL into Kilo's export shape and imports
it into Kilo's **local** session store. Nothing is sent to Kilo Cloud unless you
explicitly run `pi-kilo publish --post`.

This mirrors Kilo's own behavior: a CLI session stays local until you connect it
with `/remote` or share it with `/share`. Pi sessions get the same deal.

Two steps, on purpose:

| Step | What it does | Talks to Cloud? |
| --- | --- | --- |
| `pi-kilo import` | Pi JSONL → Kilo export JSON → `kilo import` with `KILO_DISABLE_SESSION_INGEST=1` | No |
| `pi-kilo publish --post` | Reads the local Kilo session back out and POSTs history to the ingest API | Yes, opt-in |

Publishing uploads **history**, not ownership. Messages sent from Kilo still
execute in Kilo (or nowhere if no Kilo runtime owns the session); Pi is not
attached. See [Honest boundaries](#honest-boundaries).

## Requirements

- Pi sessions under `~/.pi/agent/sessions/--<cwd-slug>--/*.jsonl`
  (override with `PI_SESSIONS_DIR` or `PI_CODING_AGENT_DIR`).
- Kilo CLI 7.x on `PATH`, or set `KILO_BIN`. The import runs
  `kilo import <export.json>`.
- Python 3.10+ (standard library only).
- For `publish --post`: Kilo credentials from `kilo auth login`, or
  `--auth-file` / `KILO_AUTH_FILE`.

## Import

```bash
# Convert and import every Pi session into Kilo (local only)
pi-kilo import --all

# The 10 most recently modified sessions only
pi-kilo import --limit 10

# One session, by id, id prefix, or file path
pi-kilo import --session 164b1be580000tubDUz9Q2l9sX
pi-kilo import --session ~/.pi/agent/sessions/--home-mhw-dev--/2026-10-22T15-00-00_abc.jsonl

# Only sessions recorded for one project directory
pi-kilo import --cwd ~/dev/project

# Convert without touching Kilo's DB
pi-kilo import --all --dry-run --out /tmp/kilo-exports
```

Sessions are ordered newest-first by file mtime, so `--limit N` means the last N
sessions you worked on. Export JSON is written to a temporary directory and
deleted when the run finishes unless `--out` names a directory to keep.

Each converted session gets a deterministic `ses_...` id derived from the Pi
session UUID, so a second run skips what is already imported. `--replace`
deletes the local Kilo session first and re-imports it (refused if the session
has a `share_url` or a `session_share` storage entry, i.e. was published).

Imports run with `KILO_DISABLE_SESSION_INGEST=1` and `KILO_DISABLE_SHARE=1`, so
the `kilo` process cannot bootstrap a Cloud session or register a share. The
result is an ordinary local Kilo session: it appears in `/resume` for that
project, uses Kilo's tools and models, and can be continued in Kilo.

## Publish (opt-in)

```bash
# What was imported locally?
pi-kilo publish --list

# Show what would be uploaded, without uploading
pi-kilo publish ses_14a29f7f3000vf2KajB32cs6Za

# Upload history to the Kilo ingest API
pi-kilo publish ses_14a29f7f3000vf2KajB32cs6Za --post
```

`publish` reads `session`, `message`, and `part` rows from Kilo's SQLite store
(`~/.local/share/kilo/kilo.db`, override with `--db`), builds the same
`kilo_meta`/`session`/`message`/`part` items the Kilo CLI sends in `fullSync`,
and posts them in chunks of at most 128 items / 4 MiB. It first calls
`POST /api/session` to create the cloud row, then
`POST /api/session/<id>/ingest?v=2`. Re-running a publish is safe: ingest keys
messages and parts by id, so a retry overwrites rather than duplicates.

The result is visible in Kilo Cloud's session history. It is **not** in the live
session list, because that list is driven by relay heartbeats (the `/remote`
path), not by ingest. To make it live and controllable from Cloud, open it in
Kilo and use `/remote`; Kilo then owns execution.

## What gets converted

| Pi | Kilo export |
| --- | --- |
| session header `id`/`timestamp`/`cwd` | session `info` (`id`, `time`, `directory`) |
| `session_info.name` or first user text | session title |
| user text | user message + `text` part |
| user image block | `file` part with a `data:` URL |
| assistant text | `text` part |
| assistant `thinking` | `reasoning` part (text only) |
| assistant `toolCall` + separate `toolResult` message | one `tool` part with `state.input/output/title/time` |
| assistant `usage` | message `tokens` + `cost` |
| `stopReason` | `finish` (`toolUse` → `tool-calls`) |
| all active-branch messages | `{info, messages:[{info, parts}]}` via `kilo import` |

Skipped and reported in the run summary: `system` messages (Pi prompt/tool
declarations), `compaction`, `branch_summary`, `context_edit`, `custom`,
`custom_message`, `label`, `model_change`, `thinking_level_change`, `usage`, and
abandoned `/tree` branches.

Compaction is skipped because Pi keeps the full pre-compaction messages; the
imported Kilo session therefore has the complete history, including text that
Pi's compacted context no longer sends to the model. Reasoning signatures,
patches/snapshots, pending permissions, and workspace file state do not exist in
the Kilo export shape and are not migrated.

## Honest boundaries

- **Local by default.** `import` makes no network calls and creates no share.
  If the Kilo session has no `share_url` and no `session_share` entry, nothing
  about it is in Cloud.
- **History, not a live bridge.** `publish` is one-way upload. It does not make
  Pi the executor of a Kilo-visible session, and it does not let a Kilo message
  reach Pi. That is the Phase 2 runtime-registration work in `Plan.md`.
- **Active branch only.** Pi can hold multiple roots and abandoned branches.
  The import follows the file's final leaf back to its root and drops the rest.
- **Local identity.** The Cloud session id is deterministic from the Pi session
  UUID, but it is a new Kilo identity. Re-importing the same Pi session after it
  was published is refused by `--replace`.
- **Existing sessions are skipped.** `--replace` re-imports; it does not
  incrementally append turns. Delete the local Kilo session first if you need a
  clean rebuild.
- **Model names are copied as-is.** A Pi provider/model that Kilo does not know
  still imports as history; continuing the session in Kilo uses Kilo's own model
  selection.
- **Large tool output is preserved.** Items are chunked to the ingest limits
  (128 items / 4 MiB per request, 2 MiB per stored item). A single tool result
  above the per-item limit will be rejected by ingest; the local import still
  succeeds. Images inside tool results are not carried into Kilo's text output.

## Verification

Offline tests cover conversion, active-branch selection, tool pairing, ids
(including clones that reuse Pi entry ids), discovery, and publish chunking:

```bash
python3 -m unittest prototype/test_pi_to_kilo.py
```

Observed on this workstation (2026-10-22):

- `pi-kilo import --limit 10` imported the 10 most recent Pi sessions, all with
  `share_url` NULL and no `session_share` entry; scratch exports were removed.
- `pi-kilo import --all --dry-run` converted 39 Pi sessions in 4 project
  directories with 0 failures.
- A 324-message session (321 assistant, 349 tool calls) imported as 324 Kilo
  messages and 621 parts, `share_url` NULL, and `publish` planned 948 items in
  8 chunks (1.2 MB) without posting.
- Two cloned Pi sessions that reuse entry ids import with disjoint Kilo part ids
  (regression test: Kilo's `part.id` is a global primary key).
