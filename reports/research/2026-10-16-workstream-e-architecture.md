# Workstream E — Architecture and session semantics

- Bead: `pi-kilo-hyj.5`
- Date: 2026-10-16 (UTC)
- Status: complete (Phase 0 design input; no implementation)
- Owner: `ws-e`
- Scope: smallest architecture satisfying the 10 product invariants. Design
  doc only. No code, no external publish.

> **Grounding note.** Workstreams A–D were still stubs when this was written
> (all `2026-10-16-workstream-*.md` files read as "research not started" at
> repo HEAD `1c4a4491704708f8dd07a45d6a5c8d325238327c`). To avoid inventing
> abstractions, E inspected source directly for the parts it can ground:
>
> - **Pi 1.3.0** installed package docs at
>   `/home/linuxbrew/.linuxbrew/lib/node_modules/@earendil-works/pi-coding-agent/docs/`
>   (`rpc.md`, `rpc-commands.md`, `json.md`, `message-types.md`,
>   `session-format.md`, `sdk.md`, `security.md`, `cli-integration.md`),
>   retrieved 2026-10-16.
> - **Kilo** working clone at `/tmp/pi-kilo-workers/src/kilocode`
>   (commit `1552877e82ceaecc79a9fd4be7859518745e6f56`), files under
>   `packages/schema/src/` and `packages/protocol/src/groups/session.ts`,
>   `packages/server/src/handlers/session.ts`,
>   `packages/opencode/src/kilocode/session/drain.ts`, retrieved 2026-10-16.
> - **Pi Kilo provider** clone at `/tmp/pi-kilo-workers/src/kilo-pi-provider`
>   (commit `4c361a604349ebbaf29576ada481df27e853b2b4`), retrieved 2026-10-16.
>
> Where a claim rests on the clone rather than on an A/B artifact, it is
> labelled and timestamped here. A's and B's code-path maps remain the
> authority for the Kilo side; E's mapping should be reconciled against
> them in synthesis. Anything not grounded is marked
> **Inference**/**Recommendation**/**Open question**.

## 0. Executive summary (one paragraph)

**Recommendation:** do **not** define a new session protocol. Kilo already
has the entities this project needs — a project identity, a durable
per-session event log with stable event IDs and per-aggregate sequence
numbers, a prompt-admission record with client-supplied message IDs, a
permission request/reply event pair, a session status model, and a
process-local execution-ownership ("drain") mechanism. The smallest
architecture is therefore a **thin Pi adapter that projects Pi's native
session events into Kilo's existing durable session-event model and drives
Pi over its native RPC/SDK control plane**, plus **one genuinely new
capability on the Kilo side: representing that a session's execution owner
is an external runtime and routing prompts there**. Shared logical identity
is the Kilo `Session.ID`; Pi keeps its own native session (its files, tools,
permissions, extensions) and is launched bound to that identity. History
access and bidirectional messaging are achievable with the projection
adapter alone. Continuation stays per-runtime; turn-boundary handoff is a
history rebuild, not state migration; active-turn migration is out of scope
for want of a reliable mechanism. The biggest risk is **ownership
routing** — whether Kilo can hold a session whose agent loop is executed by
Pi without Kilo also trying to execute it. If it cannot, Phase 1 is limited
to a local harness and read-only history access.

## 1. Conceptual entities — mapping to existing representations

The Plan.md entity list maps almost 1:1 onto representations that already
exist. Only two things are genuinely new: the **runtime binding** (which
runtime instance owns a logical session) and **external-runtime ownership
routing**.

| Plan.md entity | Existing Kilo representation | Existing Pi representation | Status |
|---|---|---|---|
| **Project** | `Project.Info` — `id`, `worktree`, `vcs`, `name`, `time`; `Location.Ref` — `directory`, `workspaceID` (`packages/schema/src/project.ts`, `location.ts`). `Session.Info.location` + `subpath`. **Verified fact.** | Working directory `cwd`; sessions grouped by directory under `~/.pi/agent/sessions/--<path>--/` (`session-format.md`, `sessions.md`). **Verified fact.** | Reuse Kilo Project; bind via `Location.Ref.directory` = Pi `cwd`. |
| **Logical session** | `Session.ID` = `ses_…`; `Session.Info` with `projectID`, `agent`, `model`, `location`, `subpath`, `parentID`, `title`, `time`, `cost`, `tokens`, `revert` (`packages/schema/src/session.ts`). **Verified fact.** | Session header `{type:"session", version, id, cwd}`; id is a UUID by default, settable via `--session-id` / SDK (`session-format.md`, `cli.md`). **Verified fact.** | Kilo `ses_…` is canonical; store Pi session id/file as the runtime binding (new, §2). |
| **Runtime instance** | Partially implied: `session.active` returns "foreground Session drains currently owned by this Kilo process"; `session.drained {token}` / `session.drain.interrupted` events (`protocol/groups/session.ts`, `schema/src/kilocode/session-drain.ts`). No durable runtime-instance record. **Verified fact** for the endpoints/events; **Inference** that this is the intended ownership primitive. | A Pi process / `AgentSession`; RPC child process; `AgentSessionRuntime` (`sdk.md`). **Verified fact.** | New: a Runtime binding record (§2). |
| **Turn** | No first-class `Turn`. The closest durable unit is a **Step** (`session.next.step.started` / `step.ended` / `step.failed`, `session-event.ts`) plus `SessionInput.Admitted` (prompt admission). **Verified fact.** | First-class `turn_start` / `turn_end` = "one assistant response plus its tool calls and tool results" (`json.md`). **Verified fact.** | Map Pi turn → Kilo Step; Pi prompt → Kilo SessionInput/Prompted. No new Kilo turn type. |
| **Event** | Durable event envelope `{id: evt_…, type, data, durable:{aggregateID, seq, version}, location?, metadata?}` (`schema/src/event.ts`). Durable vs live-only events distinguished in `session-event.ts`. **Verified fact.** | `AgentSessionEvent` stream (SDK in-process `session.subscribe`; JSON/RPC JSONL on stdout) — `agent_*`, `turn_*`, `message_*`, `tool_execution_*`, `queue_update`, `session_info_changed`, compaction, retry (`json.md`). **Verified fact.** | Map Pi events → Kilo durable events; unknown payloads preserved in `metadata` (§3). |
| **Execution owner** | Process-local `SessionDrain` service (`opencode/src/kilocode/session/drain.ts`) + durable `session.drained`/`session.drain.interrupted` + `session.active`. **Verified fact** (in-memory per directory; not a durable distributed lease). | Pi is inherently single-writer: one `AgentSession` owns the conversation; `prompt()` while streaming must choose steer/follow-up or it rejects (`sdk.md`). **Verified fact.** | Reuse drain as the ownership claim; add an **external owner kind** (§2, §5). |

**Design consequence:** do not create a parallel Project/Session/Event model.
Extend Kilo's `Session.Info`/event envelope with the two missing concepts
(runtime binding; external owner) rather than introducing a sidecar model.

## 2. Identity binding and shared logical identity

**Recommendation — binding record.** For a Pi-owned logical session:

- Kilo owns the canonical `Session.ID` (`ses_…`) and the durable event log.
- Pi keeps its native session (its own JSONL, tools, permissions,
  extensions, model/provider config) — invariant 6 and 7.
- A **runtime binding** records: `sessionID`, `runtimeKind:"pi"`,
  `runtimeInstanceID`, `piSessionID`, `piSessionFile`, `cwd`,
  `capabilities`, `ownerToken`, `updatedAt`. This is genuinely new.
- Prefer storing this under Pi's native identity rather than minting a
  second conversation. Two viable encodings, both using existing surfaces:
  1. **Kilo-first (recommended):** create the Kilo session, obtain
     `Session.ID`, then start/bind Pi with `pi --session-id <id>` (Pi
     accepts a caller-supplied id, `cli.md`). If Pi's id rules allow the
     `ses_` form, identity is literally shared; otherwise derive a stable
     Pi id and store the mapping.
  2. **Pi-first:** Pi session exists; create the Kilo session with the
     optional `id` accepted by `session.create`
     (`protocol/groups/session.ts`) when compatible, else create and store
     the mapping.

**Verified fact:** `session.create` accepts an optional client `id`; Pi
accepts `--session-id`; both were read in source/docs. **Open question:**
whether Pi's session-id validation accepts the `ses_…` string verbatim
(safe because it is used in a filename; needs a one-line experiment).

### Interaction with existing Kilo Pi provider

The existing `@kilocode/kilo-pi-provider` (`/tmp/pi-kilo-workers/src/kilo-pi-provider`) is a **model/provider + ambient-UI Pi extension** (registers Kilo Gateway models, footer, usage popup). It is **not** a session-sharing adapter. **Recommendation:** keep session sharing in a separate adapter extension/Pi package so the two concerns stay independently reviewable and the provider extension is not forced to grow session semantics (invariant 10). **Verified fact** that the current extension surface is provider/UI commands (`src/index.ts`, `src/ambient-ui.ts`, `README.md`).

## 3. Event model and mapping

### 3.1 Two-level event discipline (reuse, do not reinvent)

Kilo already distinguishes:

- **Durable events** — replayable, carry `durable:{aggregateID, seq, version}`,
  are exposed by `GET /api/session/:id/history` (paged after an exclusive
  `seq`) and streamed by `GET /api/session/:id/event` (SSE: replay after
  `seq`, then live). Source: `protocol/groups/session.ts`,
  `session-event.ts`. **Verified fact.**
- **Live-only events** — stream fragments with no durable options and so no
  `seq`: `session.next.text.delta`, `reasoning.delta`, `tool.input.delta`,
  `compaction.delta`. Their `*.ended` full-value counterparts are durable.
  Source comment: "Stream fragments are live-only; …Ended is the replayable
  full-value boundary." **Verified fact.**

Pi has the same shape: `message_update` deltas are delta-only on the wire,
and `message_end` / `text_end` carry authoritative completed values;
`message_end` is "the authoritative final message" (`json.md`).
**Verified fact.**

**This is the key alignment.** The adapter should treat Pi streaming deltas
as transient UI updates and only the completed boundaries as durable facts.
That keeps deterministic ordering where it matters (durable `seq`) and
avoids replaying partial tool output.

### 3.2 Event mapping table

Legend: **D** = durable Kilo event; **L** = live-only. Mapping is E's
**Recommendation** unless marked otherwise. "Existing Kilo target" values
are **Verified fact** from `session-event.ts`/`session-message.ts`.

| Pi native event (source) | Kilo target | D/L | Notes |
|---|---|---|---|
| RPC `prompt` / SDK `prompt()` accepted | `SessionInput.Admitted` (via `POST …/prompt`) + `session.next.prompt.admitted`; user `SessionMessage.User` | D | Kilo prompt endpoint accepts a client `id` (`SessionMessage.ID`) → idempotency key. `delivery:"steer"\|"queue"` matches Pi `steer`/`followUp`. |
| `message_start` user | `session.next.prompted` / `prompt.admitted` | D | Do not double-write when prompt came through Kilo. |
| `message_start` assistant (`stopReason:"pending"`) | `session.next.step.started` (with `assistantMessageID`, agent, model) | D | Kilo `Step.Started` is the assistant-turn start. |
| `message_update` `text_delta`/`text_start` | `session.next.text.delta` | L | `textID` ← Pi `contentIndex` + message id. |
| `message_update` `text_end` | `session.next.text.ended` | D | Authoritative text. |
| `message_update` `thinking_*` | `session.next.reasoning.started` / `.delta` / `.ended` | D/L | Provider signatures (`thinkingSignature`) are opaque → preserve (§3.3). |
| `message_update` `toolcall_start/delta/end` | `session.next.tool.input.started` / `.delta` / `.ended` | D/L | `callID` ← Pi `ToolCall.id`. |
| `tool_execution_start` | `session.next.tool.called` | D | `provider.executed` ← whether the executing runtime actually ran it. |
| `tool_execution_update` | `session.next.tool.progress` | D | Kilo comment: bounded cadence, not every stdout chunk. |
| `tool_execution_end` (ok) | `session.next.tool.success` | D | `structured`, `content`, `outputPaths`, `result`, `provider.metadata`. |
| `tool_execution_end` (error) | `session.next.tool.failed` | D | `error` → Kilo `UnknownError {type:"unknown",message}`. |
| `turn_start` | (implicit in `step.started`) | — | No separate Kilo event needed. |
| `turn_end` | `session.next.step.ended` | D | `finish`, `cost`, `tokens`, `snapshot`, `files`. |
| `message_end` assistant | terminal assistant `SessionMessage.Assistant` projection / `step.ended` | D | Pi `message_end` is authoritative; `stopReason` maps to `finish`/`error`. |
| `agent_start` | (implicit) | — | Low-level; not independently durable. |
| `agent_end` (`willRetry`) | (implicit; do not mark turn complete) | — | Kilo `step.ended` must wait for settlement; `agent_end` can be followed by retry/compaction. |
| `agent_settled` | `session.status` → `idle` (and `step.ended` if not already) | D | Pi `agent_settled` = no more automatic work (`json.md`). |
| `auto_retry_start/end` | `session.next.retried` (`attempt`, `error`) + `session.status` `retry` | D | Distinguishes retry from new request. |
| `compaction_start` | `session.next.compaction.started` (`reason: auto\|manual\|overflow` → Kilo `auto\|manual`) | D | Overflow maps to Kilo `auto`. |
| `compaction_end` | `session.next.compaction.ended` | D | Include summary/recent. |
| `session_info_changed` (rename) | `Session.Info.title` update | D | No dedicated Kilo session event found. **Open question:** whether Kilo emits a title/rename event or only projects `Info`. |
| `queue_update` | (transient) `SessionInput` accepted; no durable queue event found | L/open | **Open question.** Pi exposes pending steering/followUp; Kilo has `delivery` + `admittedSeq`. |
| abort / `abort_bash` | `session.next.step.failed`? + `session.drain.interrupted` + `session.status idle` | D | Pi abort produces `agent_settled {aborted:true}`; Kilo `Step.Failed` expects an error. **Recommendation:** use `step.failed` with `UnknownError{message:"aborted"}` or keep step open — see Open questions. |
| permission request (Pi extension UI `confirm`/`select`) | `permission.v2.asked` (`Request` with `source:{type:"tool",messageID,callID}`) | D | Kilo permission model already exists (`schema/src/permission.ts`). |
| permission decision | `permission.v2.replied` (`once\|always\|reject`) | D | Pi dialog response → reply. Enforced by Pi, never by Kilo (§5). |
| runtime status / capabilities | `session.status` (`idle/busy/retry/offline/scheduled`) + runtime binding `capabilities` | D + binding | Status exists; **capabilities are new** (store on binding). |
| connection loss / reconnect | transport-level; not a durable event | — | Kilo SSE `after=seq` resumes; ownership drop emits `session.drain.interrupted`. |
| ownership/handoff | `session.drained {token}` / `session.drain.interrupted` | D | Reuse for ownership transitions. |
| unsupported / runtime-specific payload | `Event.metadata: Record<string, unknown>` on the nearest durable event | D | See §3.3. |

### 3.3 Preserving native/unknown payloads

Kilo's durable event union is a **closed tagged union**
(`schema/src/session-event.ts`), so an unknown Pi event type cannot be added
as a top-level Kilo event without a schema change. Every Kilo event payload
already carries an optional `metadata: Record<string, unknown>` envelope
field (`schema/src/event.ts`). **Recommendation:** project native Pi blobs
— `thinkingSignature`, `textSignature`, `thoughtSignature`, provider
`responseId`/`diagnostics`/`rawStopReason`, tool `details`, extension
`customType` data — into `metadata` under a namespaced key
(e.g. `pi.payload`), preserving them verbatim. Add one generic durable
passthrough event **only if** evidence (C/D) shows unknown Pi event types
must survive as first-class Kilo history; that is the sole schema addition
E currently sees as defensible.

**Requirements mapping (Plan.md §Workstream E):**

- *Stable event identity* — Kilo `evt_…` ids; tool identity is Pi
  `toolCallId`/`callID`; prompt identity is `SessionMessage.ID` `msg_…`.
  **Verified fact** (schema).
- *Deterministic ordering* — use Kilo `durable.seq` per `aggregateID`
  (session). Client-supplied `id` on prompt makes admission idempotent.
  **Verified fact** (event.ts, protocol session.ts).
- *Idempotent processing* — adapter keys writes by
  `(sessionID, source event id / message id)`; re-sending the same
  `session.prompt` id must not create a second admission. Kilo's
  `session.prompt` `id` + `admittedSeq` support this. **Recommendation**
  building on **Verified fact** of the `id` field.
- *Partial vs completed* — durable only at `*.ended` boundaries; deltas are
  live-only. **Verified fact** (session-event.ts comments).

## 4. Session lifecycle and ownership

### 4.1 Capability ladder (kept distinct, per Plan.md)

| Capability | Meaning here | Kilo support found | Pi support found | Verdict |
|---|---|---|---|---|
| **History access** | Display events produced by another runtime | Durable events + `history`/`event` endpoints. **Verified fact.** | Full native event stream. **Verified fact.** | **In scope, achievable** via projection. |
| **Bidirectional messaging** | Send a message to the owning runtime and observe results | `session.prompt` admits input. **Verified fact.** Routing to a non-Kilo owner is the open part. | `prompt`/`steer`/`follow_up` RPC. **Verified fact.** | **In scope**, gated on ownership routing. |
| **Continuation** | A runtime resumes *its own* session with native context | Kilo resumes its own session (drain/SessionV2). | Pi `--continue`/`--session-id`/SDK `SessionManager`. **Verified fact.** | **In scope, per-runtime only.** |
| **Turn-boundary handoff** | Runtime B starts the next turn from shared history | Durable history + step boundaries. | `importFromJsonl` / SDK `SessionManager` restore; context rebuild. **Source claim** (official docs). | **In scope as history rebuild**, not state transfer. |
| **Active-turn migration** | Move an in-flight turn incl. tool/permission state | No mechanism found. | No mechanism found. | **OUT OF SCOPE** — explicitly. |

**Honest boundary (invariant 8):** a shared transcript is **not** runtime
state. Kilo cannot continue a Pi turn's private state, and Pi cannot adopt
Kilo's. Pi's own docs warn that tool state, approvals, filesystem changes,
hidden reasoning (`thinkingSignature`), and provider metadata may not be
portable (`message-types.md`, `sessions.md`). State that only survives as
text/`metadata` survives; the rest does not.

### 4.2 ASCII lifecycle

```
                    Kilo (canonical identity + durable event log)
                    ─────────────────────────────────────────────
 Project(P) ── Location(directory) ── Logical Session(S = ses_…)
                                            │
             ┌──────────────────────────────┼──────────────────────────────┐
             │  durable events (seq, evt_)  │  Session.Info / status       │
             │  SessionInput.Admitted       │  ownership: session.drained  │
             └──────────────┬───────────────┴───────────────┬──────────────┘
                            │ append (projection)            │ prompt route
                            ▼                                ▼
         ┌───────────────────────────────┐     ┌───────────────────────────────┐
         │  Pi Adapter (Pi extension /    │     │  Kilo process (or cloud)      │
         │  process using Pi RPC/SDK)     │     │  sees owner=runtimeBinding    │
         │  • cursor after=seq            │     │  • owner=pi  → forward prompt │
         │  • idempotency keys            │     │  • owner=kilo → local engine  │
         └───────────────┬───────────────┘     └───────────────────────────────┘
                         │ control (Pi RPC/SDK)
                         ▼
         ┌───────────────────────────────────────────────────────────┐
         │ Runtime instance (Pi process, native session N)           │
         │  • executes turns, tools, permissions (Pi native)         │
         │  • emits AgentSessionEvent stream → adapter               │
         └───────────────────────────────────────────────────────────┘

  owner transitions (turn boundaries only):
    idle/kilo-owned ──handoff──▶ pi-owned ── Pi executes a turn ──▶ idle
         ▲                                                              │
         └──────────────── handoff back ◀──────────────────────────────┘
    (mid-turn: never migrated — active-turn migration is out of scope)
```

### 4.3 Ownership rules

1. **Single owner per logical session at a time; single owner per turn
   always.** Kilo's `SessionDrain` coordinates one local active drain per
   session inside one process (`drain.ts`). **Verified fact.**
2. **Ownership is claimed, not assumed.** A runtime holds the drain/token
   for the duration of a turn. The binding records `ownerToken`.
3. **Ownership changes only at turn boundaries.** The current owner must be
   idle before `session.drained` transfers. A prompt admitted to an
   idle-but-foreign-owned session is routed to the owner, or rejected
   visibly — never silently executed locally (invariant 3, 4).
4. **No duplicate side effects (invariant 5).** Tools run in the owning
   runtime with idempotency keys where the tool supports them.
   Reconnect/replay must not re-trigger a completed tool call: durable
   events and `tool.success/failed` are written once, keyed by `callID`;
   completed work is never re-executed on replay. Exactly-once tool
   execution is **not** claimed (Kilo's model and Pi's are at-least-once at
   the boundary).
5. **Ownership expiry / crash / drop.** On adapter heartbeat loss or Pi
   process death: emit `session.drain.interrupted`, set status `offline`
   (Kilo already has an `offline` status, currently used for pending
   questions), and leave the session unowned. **Do not** silently reassign
   to Kilo. A later human/new owner may claim at the next turn boundary.
   **Recommendation** (Kilo has the events/status; the policy is new).
6. **Local-first (invariant 7).** Pi executes locally with or without Kilo.
   If Kilo is unreachable, Pi continues; the adapter buffers completed
   durable events locally and reconciles by `seq` on reconnect. Kilo must
   never be *required* for Pi execution.

## 5. Security semantics

- **Single-owner-per-turn** — enforced at the adapter boundary: only the
  runtime that admitted a prompt may execute it. Kilo's `drain` token plus
  the binding `ownerToken` gate routing. **Recommendation.**
- **Ownership expiry/crash/drop** — as §4.3(5): fail visibly, never
  silently re-home.
- **No unauthenticated control endpoints (invariant 9).** The Pi adapter's
  control channel to Pi (RPC over stdio, or SDK in-process) must not be a
  network listener. If a socket is ever used (RPC-mode Pi is normally
  stdio), bind loopback + require a per-install token; never expose to the
  network (Pi `security.md` is explicit that Pi has the OS permissions of
  its user and no built-in sandbox). Kilo's HTTP API must keep its existing
  auth/authorization for external appends; the adapter authenticates as a
  first-class client, it does not get an unauthenticated back door.
- **Permissions enforced by the executing runtime.** Pi's permission gates
  (extension `tool_call` handlers / `ctx.ui.confirm`) run **inside Pi**; the
  adapter may bridge a request to Kilo (`permission.v2.asked`) and route the
  reply back (`permission.v2.replied`), but the decision is enforced by Pi.
  **No web-UI bypass** (invariant 9; Plan.md security section). Kilo already
  has the request/reply events (`schema/src/permission.ts`). **Verified
  fact** for Kilo; **Recommendation** for the bridge.
- **Idempotent writes / retries distinguishable from new requests.** Prompt
  `id` (`msg_…`) is the idempotency key; Pi command `id` correlates
  request→response but is **not** a durable id (RPC docs). Pi retries emit
  `session.next.retried` / `auto_retry_*`; a new user message gets a fresh
  `msg_…`. Replaying history must never re-admit a prompt.
- **Fail visibly on uncertain sync/ownership.** Never write a
  completed-looking `step.ended`/`tool.success` while the transport outcome
  is unknown; surface `session.status retry/offline` and a diagnostic
  event rather than guessing.
- **Secret redaction.** Pi documents that sessions/exports can contain
  credentials and sensitive tool output (`sessions.md`, `security.md`).
  The adapter must apply redaction before projecting to shared/cloud
  history, and must never log API keys/OAuth tokens. Use `<redacted>` in
  diagnostics. (No secrets were present in this research.)
- **Input validation at the boundary.** Every message crossing
  Kilo↔Pi is parsed against the existing schemas; unknown event types are
  preserved or dropped visibly, not executed.

## 6. Unsupported cases (explicit)

1. **Active-turn migration** — moving an in-flight turn (tool execution,
   pending permission, partial model stream) between runtimes. No reliable
   mechanism found in Pi or Kilo. Out of scope.
2. **Private runtime-state migration** — Pi extension state, pending
   approvals, hidden reasoning (`thinkingSignature`), provider metadata,
   filesystem side effects, in-memory queues. Only text + `metadata` cross.
3. **Native cross-resume** — "continue a Pi session in Kilo CLI" or vice
   versa as a first-class native session. Achievable only as a history
   rebuild on the target runtime, not as the source runtime's context.
4. **Faithful tool-state portability** — a completed Kilo tool call cannot
   become a Pi tool result that Pi will treat as its own executed call;
   tool semantics are runtime-specific.
5. **Exactly-once tool execution** across reconnect/retry. Not guaranteed;
   do not claim it.
6. **Cloud execution owned by Pi** (Phase 3) — unknown until B lands.
7. **Permission decisions by a non-executing runtime** — Kilo may display
   and forward a decision, but cannot authorize execution.
8. **Unknown Kilo event types rendered richly by the Pi adapter** (and vice
   versa) — they are preserved as `metadata`, not interpreted.
9. **Rename/title propagation as a dedicated durable event** — not found on
   the Kilo side; may be metadata/`Info`-only.

## 7. ADR (draft — E's input to synthesis)

**Title:** Reuse Kilo V2 session + durable event log as the shared truth;
Pi is an external execution owner reached through a thin projection adapter.

**Status:** Proposed (input to `pi-kilo-hyj.8`; not final).

**Context:** The 10 product invariants require shared identity and history,
real continuation, explicit ownership, and local-first native runtimes,
without a new protocol or a fork. Kilo and Pi each already have a mature
session/event model with the same partial-vs-complete discipline.

**Decision (Recommendation):**

1. **Canonical identity:** Kilo `Session.ID` (`ses_…`). Pi keeps its native
   session; a runtime binding maps the two.
2. **Shared history:** project Pi native events into Kilo's existing
   durable session-event model; preserve unknown payloads in
   `Event.metadata`. Add no top-level event types unless evidence requires
   one passthrough event.
3. **Transport:** Pi native RPC/SDK for control (no terminal scraping);
   Kilo's existing `session.prompt` / `history` / `event` surfaces for
   shared history.
4. **Ownership:** reuse `session.drained` / `session.drain.interrupted` /
   `session.active`; add an **external owner kind** and prompt routing so a
   Pi-owned session is not executed by Kilo.
5. **Capability scope:** history access + bidirectional messaging (Phase 1);
   per-runtime continuation and turn-boundary handoff (Phase 2); active-turn
   migration excluded.
6. **Security:** executing runtime enforces permissions; adapter may bridge
   `permission.v2.asked/replied`; control channel never a network listener;
   idempotency via `msg_…`.

**Consequences:**

- Positive: smallest delta; leverages Kilo's `seq`, idempotency, and
  permission model; keeps Pi native (invariant 6/7); upstreamable as a Pi
  package + narrowly scoped Kilo hook (invariant 10).
- Negative/risk: the one Kilo change (external owner + prompt routing) is
  the critical path; if Kilo's prompt endpoint always schedules its own
  engine, Phase 1 cannot pass invariant 3 through the real API and must use
  a labelled local harness.
- Cost: adapter must maintain a durable cursor and dedupe; no new protocol.

**Rejected alternatives:**

1. **New project-specific session/event protocol.** Rejected: Kilo's
   `session.next.*` durable events already satisfy stable identity,
   ordering (`seq`), partial/complete separation, and permission modeling.
   A second protocol duplicates abstractions (invariant 10) and forces
   translation in both directions.
2. **ACP as the primary boundary.** Rejected *as a complete solution*:
   ACP standardizes agent↔client control but not Kilo session identity,
   persistence, or cross-runtime ownership (Plan.md caution). **Open
   question:** ACP may still be the best **Pi-side control** protocol if C/D
   show a maintained Pi/ACP implementation; that would replace the bespoke
   RPC/SDK control path, not the shared-history model.
3. **ASP/USL as the shared history model.** Not adopted pending D.
   **Open question:** if ASP/USL is mature and maps cleanly, it could be an
   interchange/export format, but adopting it as the live model would add a
   translation layer over Kilo's existing durable log.
4. **Fork Kilo / permanent transcript-sync sidecar.** Rejected: violates
   invariant 10 and creates divergence and duplicate-execution risk.
5. **Pi session file as source of truth.** Rejected: Kilo UI and cloud
   expect Kilo session identity/events; making Pi the source would invert
   the host/guest relationship and conflate history access with
   continuation (violates invariant 1 and the Plan.md distinction).
6. **Optimistic Kilo execution of Pi-owned prompts.** Rejected: causes
   duplicate side effects and fake continuation (invariants 3/5).

## 8. Open questions / ungrounded until A–D land

1. **Critical:** Can Kilo hold a session whose execution owner is an
   external runtime, and route `session.prompt` to it *without* scheduling
   Kilo's own agent loop? If not, the smallest viable Phase 1 is a
   labelled local harness + history access. (A, B)
2. Does `session.drained {token}` provide durable, cross-process ownership,
   or only a notification? `drain.ts` read here is in-memory per directory.
   (A)
3. Can the cloud session source of truth accept externally appended
   durable events, and does a cloud session require a Kilo-managed
   environment? (B)
4. Does Pi's session-id validation accept `ses_…`, enabling literal shared
   identity? (one-line experiment; C)
5. Does Pi expose all needed events over RPC/SDK including extension UI
   dialogs and permission confirmations, with stable ids across reconnects?
   (C)
6. ASP/USL maturity and mapping value; ACP as Pi control plane. (D)
7. Does Kilo emit a durable session rename/title event, or only project
   `Session.Info.title`? (A)
8. How should interruption be encoded — `step.failed` vs. leaving the step
   open (`agent_settled {aborted:true}`)? (A/F)
9. Can the Kilo UI represent an external runtime's capabilities and the
   offline/owned/busy states honestly? (A/B/F)
10. Falsification: does message projection create duplicate turns on
    reconnect, and can two runtimes ever both hold a turn? (F)

## 9. Cross-references

- Plan.md — invariants, conceptual distinction, security requirements,
  Workstream E deliverable.
- `reports/research/Readme.md` — evidence labels, ownership, freshness.
- A/B/C/D artifacts — expected to supply the Kilo code-path map, cloud
  coupling, Pi adapter experiment, and protocol comparison that this design
  assumes. **At time of writing these were stubs and E's Kilo/Pi mapping is
  E's own source reading.**
- Workstream F — should attack §4.3 and §5, especially duplicate turns,
  ownership races, and reconnect replay.

_No secrets were accessed or recorded. No git commit/push performed
(invariant: Phase 0 read-only)._
