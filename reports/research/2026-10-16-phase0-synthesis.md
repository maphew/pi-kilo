# Phase 0 synthesis — Kilo External Runtime Integration

- **Bead:** `pi-kilo-hyj.8` (P0) — Phase 0 synthesis: evidence ledger, ADR, go/no-go.
- **Date:** 2026-10-17 (UTC).
- **Status:** complete — decision document. Phase 0 only; no implementation, no
  upstream PR, no branch publish, no git push, no production writes.
- **Verdict:** **CONDITIONAL NO-GO** on "small adapter, no Kilo changes"; **GO**
  for a bounded, explicitly labelled local Phase-1 harness gated on an
  execution-owner lease with a runtime-kind guard and on message-id dedupe
  engaged at the send path.

### Inputs and revisions read

Working tree HEAD `af95b738d63591b08800b6f87a7d716202251c34`; last commit that
touched each path (the revision the content was read at):

| Path | Revision |
|---|---|
| `Plan.md` | `86f07bfdc336cec2b1fa0ad3bf00ddabf9bffed5` |
| `reports/research/Readme.md` | `1c4a4491704708f8dd07a45d6a5c8d325238327c` |
| `reports/research/evidence-ledger.md` | `bb5754e8a56fadd4df7edd6316943f114cf7e365` |
| `2026-10-16-workstream-a-kilo-local.md` | `b31f9a157fa219071f3242e513fafac713df5ff5` |
| `2026-10-16-workstream-b-kilo-cloud.md` | `b31f9a157fa219071f3242e513fafac713df5ff5` |
| `2026-10-16-workstream-c-pi-runtime.md` | `bb5754e8a56fadd4df7edd6316943f114cf7e365` |
| `2026-10-16-workstream-d-prior-art.md` | `b31f9a157fa219071f3242e513fafac713df5ff5` |
| `2026-10-16-workstream-e-architecture.md` | `b31f9a157fa219071f3242e513fafac713df5ff5` |
| `2026-10-16-workstream-f-falsification.md` | `b31f9a157fa219071f3242e513fafac713df5ff5` |
| `2026-10-17-review-a-kilo-local.md` | `af95b738d63591b08800b6f87a7d716202251c34` |
| `2026-10-17-review-b-kilo-cloud.md` | `af95b738d63591b08800b6f87a7d716202251c34` |
| `2026-10-17-review-c-pi-runtime.md` | `af95b738d63591b08800b6f87a7d716202251c34` |
| `2026-10-17-review-d-prior-art.md` | `af95b738d63591b08800b6f87a7d716202251c34` |
| `2026-10-17-review-e-architecture.md` | `af95b738d63591b08800b6f87a7d716202251c34` |
| `2026-10-17-review-f-falsification.md` | `af95b738d63591b08800b6f87a7d716202251c34` |

External pins (unchanged across artifacts and reviews; **zero drift**):
`Kilo-Org/kilocode` `1552877e82ceaecc79a9fd4be7859518745e6f56` (v7.8.14, MIT);
`Kilo-Org/cloud` `d38649d7e3ac06c45d76c61baa334be5df0fbc02` (OCVSAL v1.0
source-available); `earendil-works/pi` (ex `badlogic/pi-mono`)
`8efd314fa3d3232ce197d8d7a6a5660530b9d83e`, installed
`@earendil-works/pi-coding-agent` 1.3.0, MIT; `kilo-pi-provider`
`4c361a604349ebbaf29576ada481df27e853b2b4` (**BSL-1.0 = Boost Software License
1.0, not "Business Source"** — review D/correction); ACP `e7dac67a`, ASP
`b6cdb662`, USL `d9b8680c`, `pi-acp` `04d0a15d`, OpenHands `d6415636`.

### Method note

This document consolidates six workstream artifacts and six independent
reviews; it adds no new research and edits no input. Each material claim is
labelled (**Verified fact** / **Observed behavior** / **Source claim** /
**Inference** / **Recommendation** / **Open question**) and pointed at its
source artifact section. Where a review corrected the source, the corrected
version is used and the correction is stated. The Plan.md five-way distinction
— **history access / bidirectional messaging / continuation / turn-boundary
handoff / active-turn migration** — is preserved throughout. No secrets were
present; anything sensitive would be shown as `<redacted>`.

---

## 1. Answer to the seven first-assignment questions

**Q1 — What exact Kilo code path creates and maintains a session visible to
`app.kilo.ai`?**
A session is created by `Session.create` → `createNext`
(`packages/opencode/src/session/session.ts` ~602–660), which mints
`SessionID.descending`, binds a `projectID`/`directory`, and publishes
`Session.Event.Created`; it persists in a per-host SQLite store at
`<Global.Path.data>/storage` (`storage/storage.ts`) (**Verified fact**, A Q1).
To become cloud-visible the CLI dials an **outbound** WSS to
`ingest.kilosessions.ai` (`/api/user/cli?token=…&connectionId=…`) via
`KiloSessions.enableRemote()`, bootstraps the session with
`POST {ingest}/api/session`, and advertises it in a ~10 s heartbeat
`sessions: SessionInfo[]` (**Verified fact**, A Q2). The web/UI then reaches it
as a Remote Connections session over `/api/user/web`; the shared logical
identity is the `ses_…` row in Postgres `cli_sessions_v2` and the transcript is
the per-session `SessionIngestDO` Durable Object (**Verified fact**, B Q1–Q2).
Cloud Agent is a *separate* hosted product with its own DO-held fenced wrapper
lease, not the path that carries a local session (**Verified fact**, B Q3–Q4).

**Q2 — What existing Remote Connections or session interfaces can an external
runtime reuse?**
Three surfaces exist and only one is a genuine reuse candidate. (a) The relay
WebSocket protocol (`remote-protocol.ts`: `Heartbeat|Event|Response` /
`Subscribe|Unsubscribe|Command|System|HeartbeatAck`) is machine-readable but is
a private product convention; the CLI dials Kilo's relay with the *user's*
account token, there is no third-party registration or runtime identity, and
`send_message` feeds `SessionPrompt.prompt()` directly with no execute-elsewhere
mode — reusing it as-is means **impersonating a Kilo CLI** (**Verified fact**,
A Q2/Q4/Q6; review A). Correction to A: A's open question "does the relay
allowlist commands?" is already answered by B — the relay has
`ALLOWED_VIEWER_COMMANDS` (`UserConnectionDO.ts:133`), so a new
`forward_message` needs a **backend** allowlist change, not CLI-only (review A,
B Q4). (b) The local authenticated HTTP API + SSE (`POST
/session/:id/prompt_async`, `GET /event`, Basic auth) is the best same-host
sidecar candidate but is **Inference/partial**, not observed — it can drive a
Kilo-owned session, not register an external owner (A Q4; review A
label-hygiene). (c) Import (`/resume-claude`, `/resume-codex`, cloud-clone) is
one-way transcript copy with an `IMPORT_NOTICE` (`session-resume/index.ts:849`;
correction to A, which cited `import.ts:849`) — history access only, no live
link. A missed the local `SessionDrain` primitive that E anchors on:
`kilocode/session/drain.ts`, `session.drained`/`session.drain.interrupted`,
`session.active` (review A gap 3; E §1).

**Q3 — What Pi interface provides reliable event observation and message
control?**
Pi's **RPC mode** (`pi --mode rpc`), a long-lived JSONL stdin/stdout process,
is the boundary: it is both long-lived and bidirectional and needs no core
modification (**Verified fact**, C Q1/Q6). Observation uses the event stream
(`agent_*`, `turn_*`, `message_*` with delta-only `message_update` and
authoritative `message_end`, `tool_execution_*`, `queue_update`,
`compaction_*`, `auto_retry_*`) plus `get_messages` and `get_entries(since=…)`;
control uses `prompt`/`steer`/`follow_up`/`abort`; turn completion is
`agent_settled`, **not** `agent_end` (**Verified fact**, C Q2/Q3, C1–C3).
Permissions ride an extension `tool_call` handler + `ctx.ui.confirm()`, which
crosses RPC as `extension_ui_request`/`extension_ui_response` and is enforced
**by Pi** (deny + allow reproduced, C3). Correction to C: the claim that Pi
preserves an "`Other` content-block variant" is **wrong** and is not cited
here; the real mechanism is `CustomMessage` role tolerance and unknown-`kind`
tolerance (review C). The SDK half of the recommendation is docs-only and is a
Recommendation, not fact (review C).

**Q4 — Can ACP or another existing protocol reduce the amount of custom work?**
ACP (v1 stable, v2 Draft) is a genuine live-control protocol — `session/prompt`,
`session/cancel`, `session/update`, `session/request_permission`, tool
streaming, diffs — and an MIT Pi↔ACP adapter (`pi-acp` 0.0.34) already exists
and is consumed by OpenHands (**Verified fact**, D 1.1/1.3/1.5). But ACP session
IDs are agent-owned (`NewSessionRequest` carries no client session id) and
`session/load`/`resume` only reach the *same* agent, so ACP provides no shared
logical identity, no durable store, no ownership lease and no idempotent prompt
(**Verified fact**, D 1.1/3). Kilo today is an ACP **agent**, not a host; there
is **no ACP client** anywhere in kilocode/cloud/kilo-pi-provider, so "Kilo
consumes Pi-over-ACP" means building a new ACP host plus an ACP-id→Kilo-session
mapping (**Verified fact**, D 1.6). Correction to D: the ACP "`Other` block /
passthrough" claim is **v2-forward**, not v1 — v1's `ContentBlock` has no
`Other` variant (review D). ACP can reduce *Pi-facing control* work at the edge,
but not the shared-session work this project actually needs.

**Q5 — Does ASP/USL offer a sufficiently mature session/event model worth
adopting?**
ASP/USL is the right *conceptual* model and the wrong *dependency*. ASP (draft
schema v1.0, TypeScript-only, 3★) explicitly owns the "durable past" while ACP
owns the "live present"; USL (Rust append-only log, 55★, "validation stage") has
a lineage DAG (`fork/resume/handoff/subagent/compact`), content-addressed
`stableId` for idempotent re-import, declared per-axis fidelity, opaque `unknown`
passthrough, and a working Pi session importer/exporter
(`usl-convert/src/pi.ts`) (**Verified fact**, D 1.2). But it is draft,
single-implementation, no ecosystem, and the "zero-loss" Pi round-trip is a
**Source claim** (D 1.2/6). Recommendation: borrow the vocabulary and the Pi
mappings, do **not** take a hard Phase-1 dependency (D 4; E rejected
alternatives).

**Q6 — What is the smallest experiment that proves or falsifies the idea?**
F's "one shared id, two owners, one retry" local harness (**Recommendation**,
F experiment; review F PASS): start one real `pi --mode rpc`, a thin adapter
speaking the Remote Connections protocol for a fabricated `ses_…` id, and a
second claimant process for the same id; then (2) send one `send_message` with
a fixed `messageID`, drop and resend it; (3) send the next message while the
second claimant heartbeats; (4) kill the adapter mid-`tool_execution` and
reconnect; (5) install a Pi permission extension that **denies** `bash` and
drive it through the web path, including (6) across a reconnect after the
prompt appears. Any falsifying outcome disproves "no Kilo changes"; step 1/3/5
failing disproves the labelled-harness path too.

**Q7 — What can be demonstrated locally without production credentials?**
Everything on the Pi side, and nothing on the real relay side. C reproduced
Pi RPC observe/control (C1), caller-supplied `--session-id` with cross-process
resume and a durable `get_entries(since)` cursor (C2), and Pi-enforced
permission deny/allow (C3), all against unmodified `pi` 1.3.0 with no production
credentials (**Observed behavior**, C local experiment). The Kilo relay is an
authenticated, private, hand-mirrored wire contract (token on
`/api/user/cli`; `remote-protocol.ts` vs cloud `user-connection-protocol.ts`)
with no published third-party contract, so real `app.kilo.ai` rendering cannot
be shown locally (**Verified fact**, F8; B Q5). What is demonstrable locally is
a **clearly labelled harness** — either the repo's own vitest/Durable-Object
integration environment or a ~200-line WS stub — which Plan.md explicitly
allows (**Recommendation**, F F8/test plan; Plan.md Phase 1).

---

## 2. Research report (condensed)

**Kilo local (kilocode@`1552877e`, MIT).** Session create/persist/resume:
`session/session.ts` `createNext` + SQLite storage; resume is same-process
re-prompt (`SessionPrompt.prompt`, `session/prompt.ts:1444`) — there is no
portable session handle detached from the runtime (**Verified fact**, A Q1).
Remote Connections is outbound-only (`enableRemote` ~979–1010; `remote-ws.ts:437`)
with a two-set presence/ownership state machine (`attached-state.ts`) and 16
inbound commands, the salient one being `send_message` → `prompt()`
(`remote-sender.ts:1280–1319`) (**Verified fact**, A Q2/Q3; review A). The
execution-ownership primitive A missed is `SessionDrain` (`session/drain.ts`;
`session.drained`/`session.drain.interrupted`; `session.active`) — **in-memory,
per-directory, not a distributed lease** (**Verified fact**, E §1; review E).

**Kilo Cloud (cloud@`d38649d7`, OCVSAL source-available — production requires a
commercial agreement; kilocode MIT)** (**Verified fact**, B header; review B).
Shared logical identity = `cli_sessions_v2` (`ses_` + 26 chars); shared
transcript = `SessionIngestDO` fed by `POST /api/session/:id/ingest` and idempotent
on item id; Cloud Agent is hosted-only (baked-in `@kilocode/cli`, internal-only
`/ingest`, HS256 launch envelope, DO-held `wrapperGeneration`/`wrapperConnectionId`
lease) with no external attach path (**Verified fact**, B Q1–Q4). Runtime
instance = heartbeat `instance{name,projectName,kind:'cli'|'remote'}`; there is
**no external/third-party kind** (**Verified fact**, B Q1/Q6). Ownership =
`sessionOwners` `Map<string,string>` (B Q4 → F4). Viewer commands are gated by
`ALLOWED_VIEWER_COMMANDS` (`UserConnectionDO.ts:133`); retries are deduped only
when a client supplies `mutationId` (**Verified fact**, B Q4/Q5). UI routing is
a closed three-way `remote | cloud-agent | read-only` enum; a disconnected CLI's
sessions **drop out of the list** rather than showing offline (**Verified fact**,
B Q7).

**Pi (earendil-works/pi@`8efd314f`, 1.3.0, MIT).** RPC JSONL control/observe;
caller-supplied `--session-id` normalizes to a session file
`..._<id>.jsonl`; `get_entries(since=<leafId>)` is a durable catch-up cursor even
across process restarts; `message_update` deltas are transient, `message_end`
authoritative; `agent_settled` = no further automatic work; permissions are an
extension concern enforced inside Pi; closing RPC stdin requests orderly
shutdown (**Verified fact / Observed behavior**, C Q1–Q5, C1–C3).

**Concrete verified relay facts (line-exact at the pinned SHAs; review F PASS).**
(1) Ownership is last-heartbeat-wins with no runtime-kind guard:
`sessionOwners = new Map<string,string>()` (`UserConnectionDO.ts:335`);
`handleHeartbeat` moves ownership when `previousOwner !== connectionId`, failing
the old owner's pending commands and then unconditionally setting the new owner
(`:711–732`); routing is `findCliForSession` = `sessionOwners.get(sessionId)`
(`:2431–2432`); the only rejection is a stale web-supplied `connectionId`
(`SESSION_OWNER_CHANGED_ERROR`), never a second claimant. (2) Relay durable
dedupe is gated on `if (msg.mutationId)` (`:1633`), but the chat send path omits
it: `cli-live-transport.ts:1041` (`send_command`) and `:1087` (`send_message`)
pass two args, and only `create_session` passes a `mutationId` (`:982–992`).
The CLI `send_message` handler calls `prompt()` unconditionally with optional
`messageID` (`remote-sender.ts:1280–1324`). Therefore a re-dispatched chat
command can execute twice. These two facts, plus F2 (no runtime-agnostic
logical↔runtime session mapping), entail the conditional NO-GO.

**Zero-drift status.** All six reviews re-ran `git rev-parse HEAD` on the
pre-clone checkouts and confirmed **exact** matches to the artifact pins (A/B/C/
D/E/F source tables; reviews A–F). Minor line-number drifts were found in A and
B prose but no load-bearing claim failed; F's *header* SHAs are local-clone
revisions and must **not** be cited as verification revisions (review F gap 1).

---

## 3. Prior-art matrix

Legend: ✅ supported; ◐ partial / host work required; ❌ absent.

| Candidate | What it is | Live bidi vs history | Identity / order / replay / continuation | Perms / tools / errors / streaming | Ownership / reconnect | Incremental | License / maturity |
|---|---|---|---|---|---|---|---|
| **Kilo Remote Connections** | Product convention (WS + Zod; `remote-protocol.ts`) | ✅ live (`command`→runtime, `event`←runtime) | ◐ `ses_` ids, subscribe, heartbeat; replay/dedup partial; cross-runtime continuation unproven | ◐ opaque `data`; tool/perm encoding is Kilo's own | ◐ CLI `attached-state.ts` fences real; **relay `sessionOwners` last-heartbeat-wins, no kind guard** | ◐ (correction to D: ◐, not ✅, until A's seam resolves) | MIT; shipping |
| **ACP** | Spec + many impls + registry | ✅ (`session/prompt`,`cancel`,`request_permission`) | ◐ agent-owned `SessionId`; `load`/`resume` same-agent only; ❌ shared identity, ❌ cross-runtime continuation | ✅ tools/diffs/usage/streaming; `Other`/`_meta` passthrough is **v2** (v1 has none) | ❌ no owner lease/dedup | ✅ sidecar | Apache-2.0; v1 stable, v2 Draft, active |
| **Pi RPC / SDK** | Working impl (JSONL stdio / in-process) | ✅ prompt/steer/follow_up/abort + events | ◐ native session tree; `get_entries(since)` durable cursor; continuation within Pi only | ✅ `tool_execution_*` partials/errors; permission bridge | ❌ no owner lease; process-scoped | ✅ read-only; no core change | MIT; active |
| **ASP / USL** | Draft spec (TS) + reference impl (Rust) | ❌ explicitly not live control | ✅ content-addressed ids, append log, lineage `handoff`, idempotent replay; cross-harness Pi converter | ◐ models tool/thinking/approval/unknown; no live perms | ◐ single-writer; no live owner | ◐ import/export library | MIT; draft 3★ / "validation" 55★ |
| **`pi-acp`** (discovered) | Working community impl | ✅ ACP agent over Pi RPC | ◐ ACP id → Pi session file map; `session/load` | ◐ text/tool/diff/usage; **no `fs/*`/`terminal/*`**, MCP unwired | ◐ inherits ACP weakness | ✅ pure sidecar | MIT; 0.0.x MVP, 734★, 39 tests |
| **OpenHands** | Product + host/runtime pattern | ✅ as ACP host | ◐ UI-side persisted events | ✅ typed `ACPToolCallEvent` (started+terminal) | ◐ host owns subprocess/creds | ❌ different product; lessons only | MIT; very active |
| **OpenTelemetry** | Spec (semconv) | ❌ not control | ❌ not history/identity/replay | ◐ GenAI spans/events (Development) | ❌ | ✅ additive | Apache-2.0; active |
| **Kilo ACP agent** | Working impl (Kilo as agent) | ✅ agent side | ◐ Kilo's own sessions | ✅ ACP tool/permission mapping | ◐ per-connection | ✅ shipped | MIT |
| **`kilo-pi-provider`** | Pi package (model provider + UI) | ❌ session transport | ❌ | ❌ | ❌ | ✅ | **BSL-1.0 = Boost**, not a bridge |

### Three-way comparison and recommendation

**Approach 1 — reuse Kilo internals.** Buys the only existing implementations of
invariants 1–5/7 (session ids, durable transcript, relay, attach fences).
Costs: private convention; a **backend** allowlist change; and A's finding that
a foreign runtime can only join as-is by impersonating a CLI.
**Approach 2 — ACP with a Kilo adapter.** Buys a standard live-control edge and
a ready Pi adapter; costs a new ACP host in Kilo plus an id mapping, and ACP
supplies none of identity/persistence/ownership; inherits the v2 thinking-
fidelity caveat. **Approach 3 — project-specific contract.** Only for the
semantics neither provides (registration, owner lease, handoff); must be a thin
layer over 1/2, not a new transport.

**Recommendation (entailed, with qualifications — review D):** **Approach 1 +
a minimal semantics layer (Approach 3)**, with ACP considered only at the
Pi-facing edge if `pi-acp` earns its keep. Rejected: (a) **ACP as the
shared-session layer** — agent-owned ids, same-agent resume, no store/lease;
(b) a **new general protocol** — duplicates Kilo's relay/fences; (c) **ASP/USL
as a hard Phase-1 dependency** — draft/single-impl (borrow vocabulary instead);
(d) **vendoring OpenHands / kilo-pi-provider**; (e) **OTel as the session
protocol** (observability ≠ durable history). One falsifier can invert the
ranking: if A's seam work shows a foreign runtime can only join by impersonating
a CLI, "reuse" collapses into rebuild (review D).

---

## 4. ADR

**Title:** Reuse Kilo's `ses_` session + durable transcript as the shared truth;
Pi is an external execution owner reached over Pi RPC, joined through a
runtime-kind-aware relay ownership seam.

**Status:** Accepted for Phase 0 direction; gated on Phase-1 conditions in §7.

**Decision.** The integration boundary is **(i) Kilo's Remote Connections
session identity and transcript** (`cli_sessions_v2` + `SessionIngestDO`) plus
**(ii) a Pi-side process adapter that speaks Pi RPC** (`pi --mode rpc`). Shared
history is produced by projecting Pi native events into Kilo's existing durable
session-event / ingest shapes, preserving unknown payloads in `metadata`.
Continuation stays per-runtime; **turn-boundary handoff is a history rebuild,
not state migration**; **active-turn migration is out of scope**.

*Minimum Kilo change (Recommendation; not yet proven upstreamable):*
(1) widen the runtime label — `instance.kind` (closed `cli|remote`) or an
equivalent **runtime-kind/owner field** so Pi is representable honestly, and
render it; (2) stop equating "not live in heartbeat" with "not in the list" so
an offline external owner keeps its session row; (3) add a **runtime-kind guard
plus an owner lease/fencing token** on the relay ownership path
(`sessionOwners`/`handleHeartbeat`) so a second claimant for one logical session
is **rejected**, not silently installed; (4) add a `forward_message` command (or
an `external:true` branch) to the **relay allowlist**
(`ALLOWED_VIEWER_COMMANDS`, `UserConnectionDO.ts:133`) and a forward-or-execute
branch beside `send_message` in `remote-sender.ts`; and engage a **mandatory
idempotency key** on the chat send path.

*Minimum Pi adapter:* spawn `pi --mode rpc --session-dir <managed> --session-id
<kilo-session-id>`, strict LF-only JSONL; project RPC events into Kilo's ingest
shapes (delta-only for live, authoritative boundaries only for durable,
`agent_settled` for completion); catch up with `get_entries(since=<last id>)`;
control with `prompt`/`steer`/`follow_up`/`abort`, branching on `disposition`;
load an adapter extension whose `tool_call` handler bridges
`extension_ui_request`/`extension_ui_response` (enforcement stays in Pi); report
capabilities from `get_state`/`get_available_models`/`get_commands` with tools
via the extension. No Pi core edits.

**Context.** The ten invariants require a shared logical session, shared
history, real continuation, explicit ownership, no duplicate side effects, and
native, local-first runtimes, with a small adapter and a narrowly scoped Kilo
extension. Both runtimes already have mature session/event models and the same
partial-vs-complete discipline. Two blockers are **verified**: ownership without
a runtime-kind guard (`UserConnectionDO.ts:335, 711–732, 2431–2432`) and missing
`mutationId`/message-id dedupe on the send paths (`cli-live-transport.ts:1041,
1087`; `UserConnectionDO.ts:1633`; `remote-sender.ts:1280–1324`). Correction to
E: E's ownership rules and `msg_` idempotency are **specified, not proven**, and
E's design does not by itself answer F's relay-path attack; the two are
compatible only when E's `seq`/idempotency is scoped to the durable/SSE surface
and F's NO-GO to the Relay Connections path (review E).

**Alternatives rejected.** (a) **Transcript import as the integration** — gives
history access only, fails invariants 3–4 (A Q6). (b) **Hosted Cloud Agent
ownership** — DK-held fenced wrapper lease, internal-only ingest, `@kilocode/cli`
baked into the image, OCVSAL production terms; contradicts "Agent behavior
belongs to Kilo" and is a large change (B Q3/Q6). (c) **ACP as the shared-session
layer** — agent-owned ids, no store/lease (D 1.1/4). (d) **A new general
protocol** — duplicates the relay/fences and violates invariant 10 (D 3, E ADR).
(e) **Forking Kilo or a permanent transcript-sync sidecar** — invariant 10.

**Consequences.** Honest capability boundary: **history access and
bidirectional messaging are achievable**; **continuation stays per-runtime**;
**turn-boundary handoff is a history rebuild on the target runtime, not state
migration**; **active-turn migration is out of scope**. Positive: smallest
delta, reuses `seq`/idempotency/permission primitives, keeps Pi native and
local-first. Negative: the one genuinely new Kilo capability (external owner +
routing) is the critical path, and if the relay cannot be extended, Phase 1
degrades to a labelled harness. The `kilo-pi-provider` **Boost** license and the
Cloud **OCVSAL** terms constrain what may be copied or run in production
(reviews A/B/D).

---

## 5. Protocol/event mapping

Per Plan.md, only concepts existing interfaces do **not** provide. All
ownership/idempotency items below are **designed-but-unproven** (review E
caveat) — the mechanisms are named, not demonstrated.

| # | New concept | Why genuinely needed | Minimal shape | Idempotency / ordering rule | Owner |
|---|---|---|---|---|---|
| 1 | External-runtime registration / runtime kind | `instance.kind` is `cli|remote`; no third-party kind exists (F1, B Q1) | Optional `runtime: {kind:"pi", instanceId}` on the heartbeat/instance and a `runtimeKind` the UI reads | N/A (advertisement) | Kilo relay schema + adapter |
| 2 | Execution-owner lease + fencing token (runtime-kind aware) | Relay ownership is last-heartbeat-wins with no kind guard (F4) | `{sessionId, ownerRuntimeKind, ownerToken, leaseExpiry}`; second claimant for a live lease → reject | Reject on conflict; owner changes only at turn boundaries | Kilo relay (`UserConnectionDO`) |
| 3 | Turn-boundary handoff semantics | No wire concept of a transferable owner beyond presence, and no accepted-vs-complete distinction at transfer (A Q3/Q7, D §5.3) | `ownerToken` grant/revoke + handoff record; `accepted` (Pi `disposition`/relay ack) vs `turn-complete` (`agent_settled`) | Transfer only when idle; never mid-turn | Adapter + Kilo |
| 4 | Pi-event fidelity / unknown-payload convention | Kilo's durable event union is closed; Pi emits provider-specific blobs (E §3.3) | Namespaced `metadata["pi.payload"]` on the nearest durable event, verbatim | Carry verbatim; never re-interpret | Adapter |
| 5 | Pi-native ↔ logical session binding record | No runtime-agnostic logical↔runtime mapping exists (F2) | `{sessionID, runtimeKind, piSessionID, piSessionFile, cwd, capabilities, updatedAt}` | Keyed by `sessionID` + `piSessionID` | Adapter (storage home TBD, review E gap 3) |
| 6 | Pi capability advertisement | UI cannot distinguish external-runtime capabilities (B Q7) — **weakest item; may merge into existing `InstanceAdvertisement.capabilities`** (review D) | Capability flags from `get_state`/`get_available_models`/`get_commands` | N/A | Adapter → Kilo |
| 7 | Reconnect/replay dedupe policy | Chat sends omit `mutationId`; relay dedupe never engages (F3/F6) | Mandatory stable idempotency key (`mutationId`/`messageID`) on every send and replay; completed tool calls keyed by `callID` | Once per key over the dedupe window | Adapter + Kilo client |

**Already covered natively — no new definition needed.** Kilo models and Pi
emits both sides of: user messages (`SessionInput.Admitted`/`SessionMessage.User`
↔ `prompt`); assistant streaming (`session.next.text/reasoning/tool.input`
delta/live-only vs `*.ended` durable ↔ `message_update` deltas vs `message_end`);
tool calls/results/errors (`session.next.tool.called/success/failed/progress` ↔
`tool_execution_start/update/end`); turn start/completion/interruption/failure
(`step.started/ended/failed` + status ↔ `turn_start/end`, `agent_settled`,
aborted); permission asks/decisions (`permission.v2.asked/replied` ↔
`extension_ui_request/response`); runtime status (`session.status` ↔ `get_state`);
session rename (`Session.Info.title` ↔ `session_info_changed`); connection
loss/reconnect (transport + `session.drain.interrupted`); partial-vs-complete
discipline (live-only vs durable). These require **mapping only**, not new
protocol. Minor open mappings: abort encoding (`step.failed` vs leaving the step
open), title/rename durable event, `queue_update`, and the `turn_end`-vs-
`message_end`→`step.ended` dedupe key (review E gap 5).

---

## 6. Invariant compliance

| # | Invariant | Status | Mechanism / gap | What would prove it |
|---|---|---|---|---|
| 1 | Shared logical identity | **Partial** | Kilo `ses_` canonical; Pi accepts caller-supplied id (C2). Gap: no runtime-agnostic mapping; `ses_` collision (F2) | Pi accepts `--session-id ses_test01` verbatim **and** binding record round-trips |
| 2 | Shared history | **Partial** | `SessionIngestDO` ingest is item-id idempotent; Pi `get_entries(since)` cursor. Gap: relay event envelope has no `seq`; `catch_up` schema-only; deltas lost mid-turn (F5) | Drop socket mid-tool; reconcile from ingest item ids + Pi cursor with no lost finalized event |
| 3 | Real continuation | **Partial** | Pi executes via RPC; but Kilo must route to the owner, not its local loop (E §4.3). Gap: ownership routing unproven | Prompt to a Pi-owned session reaches Pi only, never a Kilo loop |
| 4 | Explicit execution ownership | **Not satisfied (today)** | `sessionOwners` last-heartbeat-wins; no runtime-kind guard; routing = whoever owns it (F4) | Second claimant for one live lease is **rejected**; owner stable |
| 5 | No duplicate side effects | **Not satisfied (today)** | Chat sends omit `mutationId`; relay dedupe gated on it; `send_message`→`prompt()` unconditional (F3) | Retried identical `messageID` executes once (F experiment step 2) |
| 6 | Native runtime preservation | **Satisfied** | RPC + extension, no Pi core change (C Q6); permissions enforced in Pi (C3) | — |
| 7 | Local-first operation | **Satisfied** | Pi is a separate process; Kilo loss does not stop Pi (C Q5). Caveat: adapter death closes stdin → orderly Pi shutdown, session file survives | Adapter dies mid-turn; Pi session resumable from file |
| 8 | Honest capability boundaries | **Partial** | Design states boundaries, but UI cannot represent an external runtime and would present Pi as a Kilo CLI (F1) | A truthful runtime label renders; offline owner stays visible |
| 9 | Security | **Partial** | Pi enforces permissions; control channel is stdio/localhost+token. Gap: adapter fidelity on reconnect/timeout; permission-reply replay (F6/F7) | F experiment steps 5–6: deny survives reconnect, no auto-approve |
| 10 | Upstream viability | **Partial** | Thin Pi package + narrow Kilo hook is the right shape; but the minimum Kilo change touches the **relay backend** (allowlist + owner guard) and UI, not adapter-only; Cloud is OCVSAL | A small, reviewable upstream proposal with evidence |

Bluntly: **invariant 4 and invariant 5 are not satisfied today** and are the
reason the verdict is conditional. Invariants 6 and 7 are the two already
satisfied.

---

## 7. Phase-1 go/no-go

**Verdict — reconciled with F:** **CONDITIONAL NO-GO.** The "small adapter, no
Kilo changes" claim is **rejected** (F3 + F4 + F2, all line-exact verified,
review F PASS). A **GO** is granted only for a bounded, explicitly labelled
local Phase-1 harness whose exit gate is ownership + dedupe behaviour.

**GO conditions (all must hold before Phase 1 is presented as shared identity or
cloud support):**
1. An **execution-owner lease with a runtime-kind guard** exists (or is stubbed
   in the harness) such that a second claimant for one logical session is
   **rejected** and the owner is stable.
2. **Message-id dedupe is engaged** on the send path — a mandatory stable
   `mutationId`/`messageID`, with a retried identical message executing **once**.
3. **Catch-up on reconnect** uses Pi's durable `get_entries(since=<last id>)`
   cursor plus Kilo ingest item ids, with no lost finalized event and no
   re-executed tool call.
4. The **Pi permission gate survives reconnect and timeout** (deny stays deny;
   no auto-approval), and permission replies are idempotent on their request id.
5. The Pi adapter reports capabilities and stays **unmodified-core**; Pi keeps
   working when Kilo is disconnected.

**NO-GO conditions (stop and report):**
- Two concurrent claimants for one `ses_…` id are **not** rejected (ownership
  flap) and no adapter-side fix is possible.
- A Pi permission deny can be bypassed via the web path on every representable
  mapping.
- Identity can only work by forking Kilo's session model (invariant 10) or by
  copying Cloud code contrary to OCVSAL.
- Media/UI truthfulness requires presenting Pi as a Kilo CLI with no upstream
  path to describe it honestly.

**Minimum viable architecture.** Kilo `ses_` row in `cli_sessions_v2` +
`SessionIngestDO` transcript as shared truth; a Pi adapter process spawned as
`pi --mode rpc --session-id <ses_…>` projecting native events into Kilo ingest
shapes with unknown payloads in `metadata`; a runtime-kind-aware, leased owner
record so Kilo routes `send_message` to the owner (Pi) and never executes it
locally; Pi local-first with a durable `get_entries` cursor for reconnect
reconciliation. This is the smallest shape that can satisfy invariants 1–7.

**Realistic prototype boundary.** Because the relay is a private, JWT-authenticated
Durable-Object-backed wire contract and the Cloud repo is OCVSAL, **real
`app.kilo.ai` rendering cannot be shown in Phase 1 without Kilo-side changes**
(**Verified fact**, F8/B Q5/Q6). The deliverable is therefore a **labelled
local harness** — the repo's own vitest/DO integration environment if it runs
without prod bindings, otherwise a ~200-line WS stub implementing
`user-connection-protocol.ts` — plus the real Pi RPC adapter. Anything shown
through the stub must be labelled a harness, not proof of Kilo integration
(Plan.md Phase 1 allowance; F test plan).

**Testable locally without production credentials:** Pi RPC observe/control
(C1), caller-supplied identity + cross-process resume + durable cursor (C2),
permission deny/allow (C3); event-mapping golden fixtures; adapter-side
dedupe/ownership/binding unit and property tests; the two-owner/one-retry
harness (F steps 1–5 with a stub or bound local env).
**Remains unproven:** real relay admission of a non-Kilo client; whether the
relay allowlist can be extended; real UI rendering of an external runtime; real
prod ownership semantics; the entire Cloud Agent path.

**Unresolved risks (numbered; each with the experiment that retires it):**
1. **Ownership fencing** — relay last-heartbeat-wins, no runtime-kind guard.
   *Retire:* F step 3 (second claimant rejected, owner stable).
2. **Duplicate execution on retry** — chat sends omit `mutationId`.
   *Retire:* F step 2 (retried identical `messageID` executes once).
3. **Identity collision / mapping** — Pi UUID vs strict `ses_`; no
   runtime-agnostic map. *Retire:* `--session-id ses_test01` spawn + binding
   record round-trip + two-owner test.
4. **Permission bypass on reconnect/timeout** — adapter fidelity.
   *Retire:* F steps 5–6.
5. **Mid-turn adapter death / lost deltas** — closing stdin shuts Pi down.
   *Retire:* kill the adapter mid-turn, resume from the session file, count lost
   vs duplicated work.
6. **Live event loss/reorder across reconnect** — no `seq`, `catch_up` producer
   absent. *Retire:* drop the socket mid-tool; reconcile from ingest item ids +
   Pi cursor.
7. **Honest UI / offline ownership** — closed `kind`, no offline badge.
   *Retire:* local web run with a widened kind; offline row no longer disappears.
8. **Relay opacity/admission** — can the relay carry an unknown command / accept
   a non-Kilo client? *Retire:* minimal WS client against a local dev stack.
9. **Upstream cost** — the minimum Kilo change touches backend + UI.
   *Retire:* scope a one-file upstream proposal / time-boxed spike.

---

## 8. Deliverables checklist and next actions

**Plan.md deliverables produced by Phase 0:**
- [x] **Research report** — interfaces, code paths, prior art, verified limits
  (§2; A–C, F).
- [x] **Prior-art matrix** — §3 (from D, with review-D corrections).
- [x] **Architecture decision record** — §4, chosen boundary + rejected
  alternatives with reasons.
- [x] **Protocol/event mapping** — §5, only where existing interfaces fall
  short.
- [x] **Cloud feasibility (source material)** — B's architecture map + hard
  coupling + verdict; formal report remains a Phase-3 deliverable (§7).
- [ ] **Prototype** — not in Phase 0 (Phase 1).
- [ ] **Automated tests** — designed in F's test plan; not implemented.
- [ ] **Demo script** — Phase 1.
- [ ] **Upstream plan** — seam identified (§4), reviewable proposal not written.

**What Phase 1 must build:** the F harness (two owners, one retry, reconnect,
permission-deny); the Pi RPC adapter skeleton with strict LF framing and
`--session-id` binding; the Pi event → Kilo ingest mapping with golden fixtures;
the permission bridge extension; the owner-lease + runtime-kind guard (in the
harness first); and the message-id dedupe regression test **written before the
adapter** so it can fail.

**External action:** nothing has been published upstream; no branch was pushed,
no PR opened, no production write made. Any external change (upstream proposal,
relay/backend change, Cloud involvement) requires **explicit user approval**
(Plan.md; Readme.md branch/worktree policy).

---

*No secrets were accessed or recorded; any would appear as `<redacted>`.
Phase 0 read-only: no code, no git commit/push, no external publish.*
