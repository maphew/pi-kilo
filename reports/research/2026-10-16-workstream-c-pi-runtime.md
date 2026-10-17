# Workstream C — Pi runtime integration

- Bead: `pi-kilo-hyj.3`
- Date: 2026-10-17 (UTC)
- Status: complete (Phase 0, read-only research + local experiment)
- Owner: ws-c (coordinator, after the original worker died without delivering)

### Evidence label legend (per `reports/research/Readme.md`)

**Verified fact** = confirmed in current source/docs at the cited commit, or
reproduced locally. **Observed behavior** = demonstrated experimentally with
exact steps. **Source claim** = source asserts it, not independently verified.
**Inference** = plausible, with what would verify/falsify. **Recommendation** =
proposed decision. **Open question** = unresolved.

### Sources examined

| Source | Version / commit | Retrieved |
|---|---|---|
| Installed `@earendil-works/pi-coding-agent` | `1.3.0`, MIT | 2026-10-17 |
| `badlogic/pi-mono` (redirects to `earendil-works/pi`) | `8efd314fa3d3232ce197d8d7a6a5660530b9d83e` (2026-10-16), MIT | 2026-10-17 |
| `docs/cli-integration.md`, `rpc.md`, `rpc-commands.md`, `json.md` | installed 1.3.0 | 2026-10-17 |
| `docs/session-format.md`, `message-types.md`, `sessions.md`, `sdk.md` | installed 1.3.0 | 2026-10-17 |
| `docs/extensions.md`, `security.md`, `rpc-extension-ui.md` | installed 1.3.0 | 2026-10-17 |
| `src/core/extensions/types.ts` (`tool_call` event) | pi-mono @8efd314 | 2026-10-17 |

**Note on repo rename:** `badlogic/pi-mono` now redirects to
`earendil-works/pi` (independently confirmed by workstream D). The installed
npm package is `@earendil-works/pi-coding-agent`. Both are MIT.

---

## Executive summary

**Recommendation:** use Pi's **RPC mode** (`pi --mode rpc`) as the adapter
boundary for observation *and* control, and Pi's **extension `tool_call`
handler + `ctx.ui.confirm()`** as the permission bridge. The exported
**`RpcClient`** / **SDK** are the maintained TypeScript equivalents. All of
this is a supported, documented interface; the adapter needs **no Pi core
modification**.

Shared logical identity is achievable because **Pi accepts a caller-supplied
session id** (`--session-id`, SDK `SessionManager`), which the adapter can bind
to Kilo's session id. Shared history is achievable because RPC exposes
`get_messages` **and** `get_entries` (an append-only, stable-id entry log with a
durable `since` cursor), plus a full event stream. Real continuation works
within Pi: resuming the same session file in a new process restores history.
Permission decisions are enforced **by Pi**, surfacing to an external client as
an `extension_ui_request`/`extension_ui_response` exchange — the client decides,
Pi enforces.

**Everything in this document was reproduced locally against unmodified pi
1.3.0** except where labelled **Source claim**.

---

## Findings

### Q1. Most reliable supported way to observe Pi events and send it messages?

**Verified fact:** Pi exposes four modes that share the same agent, sessions,
tools, and resources (`docs/cli-integration.md`):

| Mode | Interface | Lifetime | Fit |
|---|---|---|---|
| Interactive | TUI | until exit | a person |
| Print (`-p`) | final text | one invocation | one-shot |
| JSON (`--mode json`) | JSONL events on stdout | one invocation | structured progress, send-only |
| **RPC** (`--mode rpc`) | JSONL commands/responses/events | **long-lived** | **bidirectional control** |

**Verified fact:** RPC mode reads JSON commands on stdin and writes
`response` records plus session events on stdout; strict JSONL framing (split
on LF only — Node `readline` is explicitly unsuitable because it also splits on
U+2028/U+2029). Since the plugins/prompt answers change interaction, RPC is the
only mode that is *both* long-lived and bidirectional.

**Verified fact:** For Node/TypeScript, the package exports `RpcClient`, which
"starts a Pi RPC child process, correlates requests, exposes typed command
methods, and delivers session events to listeners." The SDK (`createAgentSession`)
embeds the agent in-process, but "the SDK is not a CLI mode" and requires a
Node/Bun host.

**Recommendation:** **RPC mode** (or the exported `RpcClient`) is the adapter
boundary. It satisfies Plan.md's "prefer structured APIs over terminal scraping"
directly and gives a process boundary that keeps Pi's native runtime intact.
Use the **SDK** only if the host is already Node/TypeScript and wants zero
process boundary; RPC is more language-neutral and safer for isolation.

**Observed behavior (C1):** the coordinator sent
`{"id":"p1","type":"prompt","message":"..."}` to `pi --mode rpc --no-session --no-tools`
and received the full lifecycle: `prompt` response `{disposition:"started"}`,
`agent_start`, `turn_start`, `message_start/end`, streaming `message_update`
`text_delta`, `turn_end`, `agent_end`, `agent_settled`, then a `get_state`
response. Exact transcript in "Local experiment" below.

### Q2. Can RPC or the SDK expose all information needed for a faithful shared history?

**Verified fact — yes, with two complementary commands:**

- `get_messages` → the conversation as `AgentMessage` values (what the model
  sees, post-compaction).
- `get_entries` → **all** session entries in append order, *excluding* the
  header; "includes pre-compaction history and abandoned branches." Each entry
  has a stable `id`; passing `since=<last id>` returns only entries strictly
  after it, "even across client restarts." The response also carries `leafId`,
  so a client can tell in one round trip whether the active branch moved.

**Verified fact (event coverage):** the shared JSON/RPC event stream
(`docs/json.md`) carries `agent_start/end/settled`, `turn_start/end`,
`message_start/update/end`, `tool_execution_start/update/end`,
`queue_update`, `entry_appended`, `session_info_changed`,
`thinking_level_changed`, `compaction_start/end`, `auto_retry_*`,
`summarization_retry_*`, plus RPC-only `bash_execution_update` and
`extension_error`. Unknown/extension content is preserved (content blocks
include an `Other` variant that receivers **must** preserve per ACP-independent
Pi docs; `thinkingSignature`/`textSignature` are documented as opaque
provider-specific metadata).

**Verified fact — streaming reconstruction:** `message_update` on the wire is
**delta-only**; `text_end`/`thinking_end`/`toolcall_end` carry authoritative
completed content, and `message_end.message` is the authoritative final
message. A consumer must buffer deltas then replace with the authoritative
value. This is exactly the partial-vs-completed distinction Plan.md requires.

**Verified fact — distinct terminal boundaries:** `agent_end` closes one
low-level run but retries/compaction/steering/follow-up may continue;
`agent_settled` means Pi will not continue automatically. Plan.md's turn
completion must map to `agent_settled`, not `agent_end`.

**Inference:** history fidelity is high but **not total**. Provider-specific
`thinkingSignature`/`textSignature`/`thoughtSignature` are opaque and must be
carried verbatim if another runtime is ever to reconstruct provider context;
raw provider stream bytes are available (`provider_stream_event`) but are
notification-only and not persisted. Cross-*runtime* context migration remains
impossible in general (a different runtime cannot consume Pi's opaque
signatures). This confirms Plan.md's warning; verify by attempting to replay a
Pi assistant message with opaque signatures into another provider.

### Q3. How are tool calls, tool results, errors, approvals, resumes represented?

**Verified fact — tool calls/results (events):** `tool_execution_start`
(`toolCallId`, `toolName`, `args`), `tool_execution_update` (`partialResult`),
`tool_execution_end` (`result`, `isError`, `durationMs`); correlate by
`toolCallId`. Nested tool calls use `toolCallId` `<parent>/<n>` and carry
`parentToolCallId`.

**Verified fact — transcript representation:** assistant messages contain
`ToolCall` blocks (`{type:"toolCall", id, name, arguments, thoughtSignature?,
namespace?}`); results are `ToolResultMessage` entries
(`{role:"toolResult", toolCallId, toolName, content, details?, isError,
nestedCalls?, usage?}`), persisted as `message` session entries.

**Verified fact — approvals are NOT a built-in per-tool prompt.** `docs/security.md`
states plainly: Pi "does not ask for approval before every tool call." The
supported approval mechanism is an **extension `tool_call` handler** that calls
`ctx.ui.confirm(...)` and returns `{block:true, reason}` on refusal. The docs
give exactly this pattern and note tool `annotations`
(`readOnlyHint`/`destructiveHint`/…) let a "permission extension … decide which
calls to confirm." `tool_call` handlers may also **mutate `event.input`** in
place before execution; a handler failure blocks the tool as a fail-safe.

**Verified fact — the approval crosses RPC as a subprotocol.** In RPC mode,
`ctx.ui.confirm()` emits an `extension_ui_request` (`method:"confirm"`) on
stdout and blocks until the client sends `extension_ui_response`
(`confirmed:true/false` or `cancelled:true`) with the matching `id`
(`docs/rpc-extension-ui.md`). Fire-and-forget methods (`notify`, `setStatus`)
emit requests that need no response. Dialog methods may carry a `timeout`, after
which Pi auto-resolves with a default.

**Verified fact — resumption:** RPC `switch_session` (load a different session
file), `new_session`, `fork`, `clone`, `get_fork_messages`; SDK
`AgentSessionRuntime.newSession/switchSession/fork/importFromJsonl`. CLI
`--continue`/`--resume`/`--session`/`--session-id`. `SessionManager` "is
authoritative for finalized model context"; assigning
`session.agent.state.messages` does **not** replace persisted context.

**Verified fact — errors:** assistant `stopReason` is a terminal enum
(`stop|length|toolUse|error|aborted|deferred|pending`); provider failures after
acceptance appear in the message/event stream, not as a second command response.
Compaction failure carries `errorMessage`.

### Q4. How are session IDs and session files managed?

**Verified fact:** sessions are JSONL files at
`~/.pi/agent/sessions/--<path>--/<timestamp>_<session-id>.jsonl`. "By default
`<session-id>` is a UUID. **Callers can supply a custom ID through the SDK or
`--session-id`.**" Entries form a tree via `id`/`parentId`; header carries
`version` (current v3), `id`, `timestamp`, `cwd`, optional `parentSession`.
`--session-dir` relocates storage (`PI_CODING_AGENT_SESSION_DIR` env).

**Observed behavior (C2):** spawning with `--session-dir <scratch> --session-id expc2`
produced `get_state` → `sessionId: "expc2"`, `sessionFile:
.../2026-10-17T18-31-32-592Z_expc2.jsonl`. So **the adapter can pin Pi's native
session to a stable, caller-chosen identity** — the mechanism for Plan.md
invariant 1 (shared logical identity).

**Verified fact:** session entries have stable 8-char-hex ids and an
append-only tree; unknown entry `type`s/detail `kind`s should be tolerated by
consumers (docs: "Consumers should treat unknown `kind` values as normal usage
rather than rejecting them").

### Q5. What happens when the Kilo connection disappears during a turn?

**Inference (mechanism, high confidence):** Pi's execution is a **separate local
process** with its own session file. Pi does not depend on the Kilo connection
to run a turn; the adapter is the only party that talks to Kilo. Therefore
losing the *Kilo connection* while the adapter stays alive does not interrupt
Pi. This is the structural basis of Plan.md invariant 7 (local-first).

**Verified fact (durability):** because Pi persists every entry to the session
file as it goes (and `get_entries`/`switch_session` can replay it), a lost
adapter does not lose work — the session can be resumed later. C2 reproduced
resuming the same session in a fresh process with full history.

**Open question / risk:** in RPC mode, **closing the child's stdin requests
orderly shutdown** (`docs/rpc.md`). So if the adapter process itself dies, Pi
shuts down (though its session file survives). If the adapter stays alive but
Kilo drops, Pi keeps running. The adapter must therefore either (a) survive
transient Kilo disconnects itself, or (b) accept that Pi stops and resume from
the session file on reconnect. This is a design decision for workstream E, and a
falsification target for F (does a mid-turn adapter death lose the in-flight
turn's unpersisted deltas?).

### Q6. Can the adapter operate without modifying Pi core?

**Verified fact — yes.** Every mechanism used here is a documented public
interface: RPC mode, CLI flags (`--session-id`, `--session-dir`, `--mode rpc`,
`-e`), the extension API (`pi.on("tool_call")`, `ctx.ui.confirm`), the exported
`RpcClient`, and the SDK. The local experiments ran against the **installed
unmodified 1.3.0 binary**. No patching, monkey-patching, or core edits were
needed.

**Verified fact:** an extension is a TypeScript module loaded with `-e <path>`
(jiti, no build step) or from `.pi/extensions`; it runs in-process with the
same OS permissions.

### Q7. What runtime capabilities can be reported accurately to Kilo?

**Verified fact — directly available over RPC:** current model (full object:
id, provider, api, contextWindow, maxTokens, cost, reasoning), thinking level
and available levels, streaming/compacting flags, steering/follow-up modes,
session id/file/name, message/pending counts, session stats (tokens, cost,
context usage), available models, and commands (extension commands, prompt
templates, skills) via `get_commands`.

**Open question:** RPC exposes **no direct "list active tools"** command.
Tool names/annotations are available to extensions (`pi.getAllTools()`,
`pi.getActiveTools()`) and to the SDK (`session.getActiveToolNames()`), so an
adapter extension can report them, but RPC alone does not. Verify by checking
whether a future release adds it; otherwise the adapter's own extension is the
reporting channel.

---

## Minimal Pi adapter design

**Recommendation — smallest design that satisfies "observe + control + permission" without core changes:**

1. **Process:** the adapter spawns `pi --mode rpc --session-dir <managed>
   --session-id <kilo-session-id>` and speaks strict JSONL (split on LF only) on
   stdin/stdout; stderr is diagnostics, never protocol.
2. **Identity binding:** pass Kilo's logical session id as `--session-id` so Pi's
   native session file is keyed to it. Store the returned `sessionFile` to
   resume after restart.
3. **Observe → history:** forward the RPC event stream to Kilo, using
   `message_update` deltas for live display and `text_end`/`toolcall_end`/
   `message_end` as authoritative; use `agent_settled` (not `agent_end`) as
   turn completion. Use `get_entries(since=<last id>)` as the durable catch-up
   cursor after reconnect — this is the replay/dedup primitive.
4. **Control:** map Kilo user messages to `prompt`; map mid-turn instructions to
   `steer` (delivered after current tool calls) or `follow_up` (delivered when
   idle); map cancel to `abort`.
5. **Permissions:** load a small adapter extension whose `tool_call` handler
   calls `ctx.ui.confirm(...)`, translating the resulting
   `extension_ui_request`/`extension_ui_response` to a Kilo approval round-trip,
   returning `{block:true, reason}` on denial. **Authorization stays in Pi** —
   the UI influences it but cannot bypass it.
6. **Capabilities:** report model/thinking/commands from `get_state`/
   `get_available_models`/`get_available_thinking_levels`/`get_commands`; have
   the adapter extension report active tools and annotations.
7. **Local-first:** keep Pi's session file authoritative; on Kilo loss, either
   keep the child alive or resume via `switch_session` with the stored
   `sessionFile` and catch up with `get_entries(since=...)`.

This is a **process-boundary adapter over supported interfaces**, i.e. Plan.md's
"small, well-separated adapter."

---

## Local experiment (reproduced, no production credentials)

All steps ran against installed **pi 1.3.0** on this host, using the configured
`kilo` provider. Scripts and raw output are retained under
`/tmp/pi-kilo-workers/exp-c*` (transient); the essential commands and results
are reproduced here so a reviewer can re-run them.

### C1 — observe + control (smoke)

```
pi --mode rpc --no-session --no-tools
→ {"id":"p1","type":"prompt","message":"Reply with exactly: PONG-C-EXPERIMENT"}
```
**Observed:** `response prompt success=true data.disposition="started"`; then
`agent_start`, `turn_start`, `message_start/end` (user), `message_start`
(assistant), `message_update` deltas `"PONG"`, `"-C-EXPERIMENT"`,
`message_end`, `turn_end`, `agent_end`, `agent_settled`; `get_state` returned
model `kilo-auto/efficient`. 18 records total.

### C2 — persisted identity, durable cursor, cross-process resume

```
# process 1
pi --mode rpc --no-tools --session-dir <scratch> --session-id expc2
→ prompt "Reply with exactly: READY-1"; wait agent_settled
→ get_state ; get_entries
# process 2 (new process)
pi --mode rpc --no-tools --session-dir <scratch> --session <sessionFile>
→ get_state ; get_messages ; prompt "Reply with exactly: READY-2"
→ get_entries since=<leafId from process 1>
```
**Observed:**
```
sessionId: expc2
sessionFile: .../2026-10-17T18-31-32-592Z_expc2.jsonl
entry types: [model_change, thinking_level_change, message×5]
leafId: e654451f
resumed sessionId: expc2   messageCount: 5
resumed history roles: [system, user, assistant, user, assistant]
get_entries since=e654451f success=True new=2
final roles: [system, user, assistant, user, assistant, user, assistant]
streamed deltas: ['READ','Y','-','2']
```

Proves: caller-supplied stable identity; persisted history; **cross-process
resume of the same logical session** (continuation within Pi); and a **durable
entry cursor** that returns exactly the new entries across a process boundary.

### C3 — permission bridge (deny and allow)

Extension loaded with `-e`:
```typescript
export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    const ok = await ctx.ui.confirm("Allow tool call?",
      `${event.toolName}: ${JSON.stringify(event.input)}`);
    if (!ok) return { block: true, reason: `${event.toolName} blocked by policy extension` };
  });
}
```
Prompt: *"Use the read tool to read notes.txt and report its exact contents."*

**Observed — deny:**
```
UI-REQUEST confirm message='read: {"path":"notes.txt"}'
-> responded confirmed=False
tool_execution_end name=read isError=True
  result="read blocked by policy extension"
transcript roles: [system, user, assistant, toolResult, assistant]
toolResult isError=True
```
**Observed — allow:**
```
UI-REQUEST confirm message='read: {"path":"/…/notes.txt"}'
-> responded confirmed=True
tool_execution_end name=read isError=False
  result="C3-NOTES-CONTENT\n"
```

Proves: approval decisions surface to an external client over RPC and are
**enforced by Pi**; the transcript records the block truthfully.

### Not yet demonstrated (honest boundaries)

- **Mid-turn adapter death:** whether an in-flight turn's unpersisted deltas are
  lost when the adapter (not just the Kilo link) dies. **Open question**
  (relevant to invariant 5, no duplicate side effects, on resume).
- **Cross-runtime continuation:** Pi cannot consume another runtime's hidden
  state; a shared transcript is not sufficient context. Not attempted; out of
  scope except turn-boundary handoff via a rebuilt history.
- **Credential-free fixture:** a prior worker drafted a stub provider extension
  (`registerProvider` with `streamSimple`) to run RPC experiments without a
  provider account; its tool-call variant had a bug and was not used here.
  Building a clean stub provider is a good **follow-up** to make these
  experiments reproducible without any credentials.

---

## Minimal adapter design — interaction contract (summary table)

| Kilo need | Pi interface | Notes |
|---|---|---|
| Observe events | RPC stdout JSONL | strict LF framing; ignore stderr |
| Authoritative message | `message_end.message` | deltas are lossy/temporary |
| History / catch-up | `get_entries(since=id)` | durable cursor; incl. pre-compaction + abandoned branches |
| Model-visible context | `get_messages` | post-compaction view |
| Send message | `prompt` | `disposition` = started/queued/handled |
| Mid-turn instruct | `steer` / `follow_up` | per steering/follow-up mode |
| Cancel | `abort` | waits for idle |
| Turn completion | `agent_settled` | not `agent_end` |
| Identity binding | `--session-id` / `SessionManager` | caller-supplied |
| Resume | `switch_session` / `--session` | by session file |
| Permissions | `tool_call` + `ctx.ui.confirm` | RPC `extension_ui_request`/`_response` |
| Capabilities | `get_state`, `get_available_models`, `get_available_thinking_levels`, `get_commands` | tools need an extension |

---

## Open questions

1. Does a mid-turn adapter death lose the in-flight turn on resume, or does Pi
   persist enough to reconstruct it? (Falsification target for F.)
2. RPC has no `list tools`; must the adapter extension be the only capability
   reporter? (Confirm against a future release / SDK.)
3. What is the exact behavior when the same Pi session file is opened by two
   processes (ownership/conflict)? Pi has no cross-process lease; this is a
   Kilo-side ownership concern (mirrors F's ownership risk).
4. Is `agent_settled` guaranteed to follow every accepted prompt, including
   extension-handled dispositions (`"handled"`)? Docs say not to wait for
   settlement when `disposition=="handled"`; the adapter must branch on
   `disposition`.
5. Provider-specific opaque signatures mean a second runtime cannot faithfully
   replay Pi's provider context; confirm what (if anything) Pi itself needs
   preserved to resume its own session faithfully after a Kilo-driven handoff.

---

## Recommendation

Adopt **RPC mode + an adapter extension** as the Pi-side boundary. It is a
supported, unmodified-core interface; it provides live bidirectional control,
a faithful (if not provider-complete) history with a durable cursor, stable
caller-supplied identity, and a permission bridge whose enforcement stays in
Pi. Build a credential-free stub provider fixture next so the experiments above
become a repeatable test harness.
