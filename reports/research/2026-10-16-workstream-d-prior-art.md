# Workstream D — Prior art and protocol reuse

- Bead: `pi-kilo-hyj.4`
- Date of investigation: 2026-10-16 (UTC)
- Status: complete (Phase 0, read-only)
- Owner: ws-d (`pi-kilo-hyj.4`)
- Scope: evaluate existing protocols/implementations against the actual
  requirements in `Plan.md`; recommend an integration boundary. No new
  protocol designed. No external changes, no upstream PRs, no pushes.

### Evidence label legend (per `reports/research/Readme.md`)

**Verified fact** = confirmed in current source/docs at the cited commit/URL.
**Source claim** = a repo/vendor asserts it; not independently reproduced.
**Inference** = plausible, with what would verify/falsify it.
**Recommendation** = proposed decision. **Open question** = unresolved.

### Sources examined (retrieval date 2026-10-16 UTC unless noted)

| Source | Commit / release | Notes |
|---|---|---|
| `agentclientprotocol/agent-client-protocol` | `e7dac67ac64ec7cf69079b3bb6eff46a21e026b3`; CHANGELOG `1.12.0` 2026-10-16 | Apache-2.0, 4458★, active |
| ACP docs `agentclientprotocol.com` / repo `docs/` | same commit | stable protocol **v1**; **v2 Draft** 2026-07-20 |
| `agent-session-protocol/asp` | `b6cdb66215367ecefe87408c99a22e95b0c8db34` (2026-08-30) | MIT, 3★, draft schema v1.0 |
| `agent-session-protocol/universal-session-log` | `d9b8680c9ea8ad7965422bf120b86a730f02bb17` (2026-10-12) | MIT, 55★, validation stage |
| ASP docs site `agent-session-protocol.github.io/docs` | live HTTP 200 | coordinator pre-check |
| `All-Hands-AI/OpenHands` | `d641563687d6342743d243a69d1fa3e92b3f1a31` (2026-10-16) | MIT, 91079★, active |
| `svkozak/pi-acp` (discovered; not in original brief) | `04d0a15d6bb42bb65cce5c9caedcdcb2cdcb6905` (2026-10-05); npm `0.0.34` | MIT, 734★, MVP |
| `Kilo-Org/kilocode` | `1552877e82ceaecc79a9fd4be7859518745e6f56` (2026-10-16) | MIT, 27629★ |
| `Kilo-Org/cloud` | `d38649d7e3ac06c45d76c61baa334be5df0fbc02` (2026-10-16) | inspected only for ACP-client absence |
| `Kilo-Org/kilo-pi-provider` | `4c361a604349ebbaf29576ada481df27e853b2b4` (2026-10-01) | **BSL-1.0**, Pi package |
| `badlogic/pi-mono` → **`earendil-works/pi`** | `8efd314fa3d3232ce197d8d7a6a5660530b9d83e` (2026-10-16) | MIT, 115734★; **repo renamed** |
| OpenTelemetry semantic conventions | site 1.44.0; GenAI moved to `open-telemetry/semantic-conventions-genai` (Apache-2.0, created 2026-05-05, pushed 2026-10-14) | observability only |

Pre-clone SHAs verified with `git rev-parse HEAD`; **no drift** from the
coordinator's addendum. Workstreams A/B/C files were still unstarted stubs at
this commit (`1c4a449`), so all Kilo/Cloud/Pi observations below are my own
independent findings, not citations of their claims.

---

## 1. Candidate findings

### 1.1 ACP — Agent Client Protocol (spec + working implementation + ecosystem)

**What it is.** **Verified fact:** A JSON-RPC 2.0 protocol for editor↔agent
interaction, schema crate `agent-client-protocol-schema`, stable wire protocol
version `1`, with a `v2` **Draft** published 2026-07-20 (`docs/announcements/acp-v2-draft.mdx`;
README "current stable ACP protocol version is `1`"). Transports: stdio
(current, normative) and Streamable HTTP (draft). Apache-2.0. Official SDKs
(Rust/Kotlin/Java/Python/TS); npm `@agentclientprotocol/sdk` latest `1.9.0`
(as of 2026-10-16). A stabilized **ACP Registry** exists for agent discovery.
**Verified fact:** `CHANGELOG.md` shows active development through 2026-10-16.

**Method surface (Verified fact, `schema/v1/meta.json`).** Agent methods:
`initialize`, `authenticate`, `session/new`, `session/load`, `session/set_mode`,
`session/set_config_option`, `session/prompt`, `session/cancel`,
`session/list`, `session/delete`, `session/resume`, `session/close`, `logout`.
Client methods: `session/request_permission`, `session/update`,
`fs/read_text_file`, `fs/write_text_file`, `terminal/*`, `elicitation/*`.

**Does it provide shared session identity? No.**
- **Verified fact:** `NewSessionRequest` contains only `cwd`, `mcpServers`,
  `additionalDirectories` — **the client cannot supply a session ID**. The
  Agent "MUST respond with a unique Session ID" (`docs/protocol/v1/session-setup.mdx`).
  `SessionId` is documented as "opaque" and agent-owned.
- **Verified fact:** `session/load` and `session/resume` take an existing
  `sessionId` (schema `LoadSessionRequest` / `ResumeSessionRequest`) and only
  work against the **same agent** that owns the session and still retains it.
  `session/resume` deliberately does **not** replay history; `session/load`
  replays via `session/update`.
- **Inference:** ACP gives a client reconnection to an agent's own session, and
  replay to a *new client instance of the same agent*. It does **not** give two
  different runtimes a shared logical conversation, nor cross-runtime
  continuation. This matches Plan.md's warning and the ASP maintainers'
  analysis (§1.4). Verify by attempting `session/resume` on a second, different
  agent with the first agent's ID — expected to fail.

**Live control / streaming / tools / permissions.** **Verified fact:**
`session/prompt` is live bidirectional (accept/cancel); `session/prompt` in v2
returns after *acceptance*, not turn end; `session/update` carries
`agent_message_chunk`, `tool_call`, `tool_call_update`, usage; tool calls have
stable `toolCallId`, `kind`, `status`, `rawInput`/`rawOutput`, structured
diffs; `session/request_permission` is an agent→client request; unknown enum
values are preserved with `_` prefix and `Other` content blocks **must** be
preserved by receivers. This is richer than what a transcript-only import
provides and is a genuine live-control protocol.

**Ownership / reconnect.** **Verified fact:** ownership is per-connection and
per-session; ACP has no cross-process lease, no execution-owner token, and no
idempotency guarantee for retried prompts. Reconnect = `session/load`/`resume`
against the same agent. **Inference:** the host application (client) must add
ownership and dedup semantics; ACP does not provide product invariants 4–5.

**Incremental adoption / native behavior.** **Verified fact:** ACP is
sidecar-shaped (stdio subprocess); an adapter can wrap a native runtime without
changing its core. `pi-acp` (§1.5) demonstrates exactly this for Pi.

**Verdict:** strong **live-control** standard with a real ecosystem, but **not**
a session-history, session-identity, or cross-runtime-continuation solution.
Do not force it into the durable/shared-session role.

### 1.2 ASP / USL — session persistence + cross-runtime migration

**What it is.** **Verified fact:** ASP (`asp`, MIT) is a **draft schema v1.0**
(TypeScript reference only; "a JSON Schema artifact and SDK generation are on
the roadmap"). USL (`universal-session-log`, MIT) is the "storage-first
reference implementation" — Rust `usl-core` append-only log with length-prefix +
CRC recovery, plus `usl-convert`. **Source claim:** README reports 54 Rust +
25 TS tests green and a Codex session round-trip with "zero loss".

**Explicit positioning (Verified fact, `spec/acp-mcp.md`):** ASP owns the
"durable past" (persistence, replay, migration); ACP owns the "live present";
MCP owns tools. ASP's own words: it is "**not** a live control protocol".
This is the correct role split and it directly answers the Plan.md question.

**Data model (Verified fact, `spec/overview.md`):** `Session → Run → Turn →
Message → ContentBlocks`, plus `ToolCall`/`ToolResult` and a session **lineage
DAG** with relations `{fork, resume, handoff, subagent, compact}`. A `handoff`
"creates a **new session + handoff relation**, never masquerades as the same
session." Event envelope carries `eventId`, `sessionId`, `timestamp`,
`entityRevision`, `source{layer,adapter,nativeEventId,authenticated}`,
`authority`, `confidence`, `correlation`. 27 event types incl.
`message.*`, `tool.*`, `approval.*`, `capabilities.changed`, `status.changed`,
`unknown.observed`. Content blocks include first-class `thinking{text,signature}`
and typed `unknown{nativeType,value}` for opaque passthrough.
Identity is content-addressed: `stableId(sessionId, nativeEventId, type)` and a
canonical session id hashed from `harness ‖ native_session_id ‖ source_sha256`
→ **idempotent re-import** and replay-dedup.

**Fidelity (Verified fact, `spec/fidelity.md`):** declared, per-axis
fidelity (`preserved`/`partial`/`evidence-only`/`dropped`/`not-in-source`) with a
measured 4-harness matrix, plus **resume-target profiles** that refuse to export
when required fields are missing. For **pi**, the resume requirement is
documented as "entry tree (id/parentId) + session header"; pi records
`run/turn boundaries partial`, `model/usage evidence-only`, `approvals
not-in-source`.

**Pi already supported.** **Verified fact:** `packages/usl-convert/src/pi.ts`
imports Pi's native JSONL sessions (`~/.pi/agent/sessions/<cwd>/<ts>_<uuid>.jsonl`,
entry types `session`/`model_change`/`message`/…, roles user/assistant/toolResult),
with `test/pi.test.ts` asserting deterministic, idempotent import and
thinking-signature preservation. Importer/exporter exist both directions.
This targets the same Pi as `earendil-works/pi` (session-path and content-block
shapes match `pi-mono/packages/coding-agent/docs/session-format.md`).

**Maturity.** **Verified fact:** ASP 3★/draft/TS-only; USL 55★/"validation
stage"; single-implementation governance; no ecosystem. **Inference:** mature
enough to reuse as a **conceptual model and mapping vocabulary**, risky as a
hard runtime dependency in Phase 1. The `usl-convert/pi.ts` code is a
high-value reference for history import/export and round-trip fidelity.

### 1.3 OpenHands — host/runtime separation lesson (and a Pi datapoint)

**What it is.** **Verified fact:** MIT, 91079★, very active; Agent Canvas + a
separate Python **Agent Server** (`OpenHands/software-agent-sdk`, MIT, 1266★).
`docs/ACP_AGENTS.md`: "The Agent Server owns the subprocess and the credentials;
Agent Canvas only records *which* agent to run." ACP agents are spawned as
subprocesses over stdio; the UI renders returned events. **Verified fact:** the
UI has a typed `ACPToolCallEvent` (`src/types/agent-server/core/events/acp-tool-call-event.ts`)
that persists two events per `tool_call_id` (started + terminal) and tolerates
`null` for forward-compat — a concrete host-side mapping of ACP tool streaming
into a durable conversation event model.

**Critical Pi relevance (Verified fact, `docs/ACP_AGENTS.md`):** OpenHands
already lists **Pi** as a supported ACP provider and launches it as
`npx -y --package=pi-acp --package=@earendil-works/pi-coding-agent pi-acp`.
Pi and OpenCode are offered on local/self-hosted backends only. This is
**evidence that an ACP Pi adapter is a shipping, consumed integration**, and
it validates the "host app separate from agent runtime" pattern.

**Lesson, not adoption:** OpenHands is a different product; do not adopt it
wholesale. Its concrete lessons: (a) keep credentials + process ownership in
the host/server, not the adapter; (b) persist an explicit tool-call
started/terminal pair; (c) spawn ACP agents as isolated subprocesses.

### 1.4 USL's own ACP-vs-USL analysis — strong corroboration

**Source claim** (USL repo `docs/research/2026-08-acp-vs-usl.md`, 2026-08-29,
Chinese): ACP is a live control wire protocol with no persistence, no
cross-runtime resume, and no provenance/fidelity; USL is the durable store +
cross-runtime converter; the two are "complementary, not competing"; ACP's
`Other` block and patch semantics are isomorphic to USL's `unknown` block and
`entityRevision` deltas. It also flags the **thinking divergence**: ACP v2
demoted thinking out of content blocks, so over an ACP tap Pi/Claude thinking
signatures can only be passively preserved in `Other` — a declared fidelity
loss. **My independent ACP doc reading (§1.1) corroborates the positioning;
the Chinese doc is labeled a Source claim for its USL-specific assertions.**

### 1.5 `pi-acp` — an existing Pi↔ACP adapter (major finding)

**What it is.** **Verified fact:** npm `pi-acp@0.0.34` and
`github.com/svkozak/pi-acp` (`04d0a15d…`, 2026-10-05), **MIT**, 734★, 97
commits since 2026-02-20, **39 test files**. It "communicates ACP JSON-RPC 2.0
over stdio to an ACP client and spawns `pi --mode rpc`, bridging
requests/events." Not affiliated with the Pi vendor.

**Capabilities (Verified fact, README):** streams assistant output as
`agent_message_chunk`; maps Pi tool execution to ACP `tool_call`/
`tool_call_update` with locations and structured edit diffs; **session
persistence** via a `~/.pi/pi-acp/session-map.json` mapping ACP `sessionId`
→ Pi session file, enabling `session/load`; slash commands/skills; context
usage; model/thinking-level switching; steering/follow-up modes; queue.

**Limitations (Verified fact, README "Limitations"):** no ACP `fs/*` or
`terminal/*` delegation (Pi does I/O locally — consistent with native
preservation); MCP params stored but not wired to Pi; no separate thought
stream; client-side queue; "MVP-style", "minor breaking changes" expected.

**Why it matters:** the Plan.md premise that "Pi would require an ACP adapter"
is **already satisfied by an existing MIT adapter**. Choosing Approach 2 does
not require writing a Pi agent interface from scratch; it requires deciding
whether to depend on a third-party 0.0.x package.

### 1.6 Kilo Remote Connections + Kilo ACP agent + Pi RPC/SDK (own findings)

**Kilo Remote Connections (Verified fact, `kilocode` @ `1552877e`).**
`packages/opencode/src/kilo-sessions/remote-protocol.ts` defines a
product-specific WebSocket protocol (Zod schemas): outbound `heartbeat` (with
`SessionInfo[]`, `instance`, `capabilities`), `event` (`sessionId`, `event`,
`data`), `response`; inbound `subscribe`/`unsubscribe`/`command`
(`id`, `command`, `sessionId`, `data`)/`system`/`heartbeat_ack`. `remote-ws.ts`
adds connect/timeout/backoff and an id-containment fence for attach/detach;
`attached-state.ts` is an explicit ownership state machine (presence-owned vs
pending, duplicate-safe announce, rollback); `remote-session-log.ts` logs
start/end/duration. The HTTP surface is `/remote/{enable,disable,status}`
(`kilocode/server/httpapi/groups/remote.ts`), and the CLI entry is
`kilo remote` (`cli/cmd/remote.ts`). **Inference:** this is the strongest
existing substrate for plan invariants 1–5 and 7 — session identity, event
relay, subscribe, command routing, ownership/attach fences, and reconnect are
already modeled. It is a **product convention**, not a public spec, and its
cloud relay is a Cloudflare Durable Object (Workstream B territory). Whether an
*external* runtime can register without impersonating a Kilo agent is the
Workstream A question and remains open here (§6).

**Kilo ACP agent (Verified fact).** Kilo already implements an ACP **agent
server**: `packages/opencode/src/acp/` + `cli/cmd/acp.ts` (`kilo … acp`), using
`@agentclientprotocol/sdk@0.21.0`, an `AgentSideConnection`. `acp/service.ts`
advertises `loadSession: true` and `sessionCapabilities.resume`, and implements
`newSession/loadSession/listSessions/resumeSession`. So Kilo can be **driven
by** ACP clients (OpenHands lists `opencode-ai acp`). **Verified fact:** a
repo-wide search found **no ACP client** (`ClientSideConnection`) anywhere in
`kilocode`, `cloud`, or `kilo-pi-provider`. **Inference:** "Kilo consumes a Pi
ACP agent" requires building a new ACP host/client in Kilo; it is not available
today.

**Pi RPC / SDK (Verified fact, `pi-mono` @ `8efd314f`, Pi renamed to
`earendil-works/pi`, MIT).** RPC mode runs Pi as a long-lived JSONL subprocess
(`pi --mode rpc`): stdin commands (`prompt`, `steer`, `follow_up`, `abort`,
`new_session`, `switch_session`, `fork`, `clone`, `get_entries`, `get_tree`,
`get_messages`, `set_model`, `compact`, `bash`, session stats, etc.); stdout
`response`/events; correlation by `id`; session events (`agent_start/end/settled`,
`turn_start/end`, `message_start/update/end` with deltas, `tool_execution_*`
with `partialResult`, compaction/retry/queue events). **Verified fact:** Pi's
native sessions are JSONL trees at `~/.pi/agent/sessions/…` with
`id`/`parentId` and a header (`session-format.md`). RPC is exactly the
"structured API over terminal scraping" Plan.md asks for, and is what `pi-acp`
already bridges. The SDK (`SessionManager`, in-process TypeScript) also exists.

**`kilo-pi-provider` (Verified fact, BSL-1.0).** A **Pi package** that provides
Kilo model access/usage/UI *inside Pi* (`pi.extensions`). It is not a session
bridge. **Inference:** reusable only as evidence of the Kilo↔Pi provider
relationship and as a candidate for capability/credential reporting — not as a
session transport. Note the BSL-1.0 license differs from Kilo's MIT.

### 1.7 OpenTelemetry — observability only

**Verified fact:** OTel semantic conventions site version 1.44.0; the GenAI
conventions have **moved** to `open-telemetry/semantic-conventions-genai`
(Apache-2.0, created 2026-05-05, pushed 2026-10-14), where GenAI events are
marked **Development**. It has agent spans, model spans, client-inference
events, and an MCP convention. **Verified fact / explicit scope:** OTel models
traces, metrics, logs, and events for observability; it does not define
conversation content as a durable resume artifact, does not own session
identity or ordering, and provides no runtime control. **Inference:** OTel is
useful *around* the adapter (spans for lifecycle/turn/tool latency, error
metrics, optional `gen_ai.*` convention alignment) and must **not** be used as
the session-history/identity/control layer. Plan.md already says this; my
reading confirms it.

---

## 2. Comparison matrix

Legend: ✅ supported; ◐ partial/only via host work; ❌ absent.

| Candidate | Spec / impl / convention | Live bidi? | Identity / order / replay / continuation | Perms / tools / errors / streaming | Ownership / reconnect | Incremental? | License / maturity |
|---|---|---|---|---|---|---|---|
| **Kilo Remote Connections** | Product convention (WS + Zod schemas, `remote-protocol.ts`) | ✅ `command`→runtime, `event`←runtime | ◐ session IDs + subscribe + heartbeats; replay/dedup partly by design, cross-runtime continuation not proven | ◐ events are opaque `data`; tool/perm encoding determined by Kilo's own session model | ✅ attach/detach ownership fences, reconnect/backoff, capability flags | ✅ (it is Kilo's own code; external registration is the open question) | MIT; shipping, active |
| **ACP** | Spec + many implementations + registry | ✅ `session/prompt`/`cancel`/`request_permission` | ◐ agent-owned `SessionId`, stable message/tool IDs, `session/load` replay + `session/resume`; ❌ no shared identity, ❌ no cross-runtime continuation | ✅ tools/status/diffs/usage/`Other` passthrough; ✅ streaming | ❌ no execution-owner lease/dedup; ◐ reconnect only to same agent | ✅ sidecar adapter; native runtime untouched | Apache-2.0; v1 stable, v2 Draft, 4458★, very active |
| **Pi RPC / SDK** | Working implementation (JSONL stdio / in-process) | ✅ prompt/steer/follow_up/abort + events | ◐ native session tree `id`/`parentId`, `switch_session`/`fork`; continuation within Pi only | ✅ tool_execution start/update/end with partials, errors, streaming deltas | ❌ no owner lease; process-scoped; reconnect = switch_session | ✅ read-only adapter; no Pi core change needed | MIT; active, 115734★ (repo renamed) |
| **ASP / USL** | Spec (draft TS) + working reference impl | ❌ (ASP explicitly not live control) | ✅ content-addressed ids, append log, lineage DAG (fork/resume/handoff), idempotent replay; ✅ **cross-harness** conversion incl. **pi** | ◐ models tool/thinking/approval/unknown events; no live permission flow | ◐ single-writer storage; no live owner | ◐ import/export library; no runtime change | MIT; ASP draft 3★, USL 55★ "validation" |
| **`pi-acp`** (discovered) | Working implementation (community) | ✅ ACP agent side over Pi RPC | ◐ ACP session id → Pi session file mapping (`session-map.json`), `session/load` | ◐ text/tool/diff/usage; **no `fs/*`/`terminal/*`**, no thought stream, MCP not wired | ◐ inherits ACP weaknesses; no owner lease | ✅ pure sidecar; Pi core untouched | MIT; 0.0.x MVP, 734★, 39 tests |
| **OpenHands** | Product + host/runtime pattern | ✅ as ACP host | ◐ UI-side persisted conversation events; ACP owns live session | ✅ typed `ACPToolCallEvent` (started+terminal) | ◐ host owns subprocess/credentials; no cross-runtime handoff | ❌ different product; lessons only | MIT; 91079★, very active |
| **OpenTelemetry** | Spec (semconv) | ❌ not control | ❌ not history/identity/replay | ◐ spans/events for GenAI (Development) | ❌ | ✅ additive | Apache-2.0; GenAI repo new/active |
| **Kilo ACP agent** | Working implementation (Kilo as agent) | ✅ agent side | ◐ `loadSession`/`resume`/`list` for Kilo's own sessions | ✅ ACP tool/permission mapping exists | ◐ per-connection | ✅ already shipped | MIT; active |
| **`kilo-pi-provider`** | Product package (Pi extension) | ❌ session transport | ❌ | ❌ | ❌ | ✅ | **BSL-1.0**; active |

---

## 3. Three-way comparison (as required by `Plan.md`)

### Approach 1 — Reuse Kilo's existing internal interfaces directly

**What reuse buys (Verified fact):** Kilo already has (a) a session model with
stable IDs and an event/command relay, (b) a WebSocket Remote Connections
protocol with `subscribe`/`command`/`event`/`heartbeat`, (c) an explicit
attach/detach ownership state machine with duplicate-safe announcement and
idempotent fences (`attached-state.ts`), and (d) reconnect/backoff/capability
negotiation. These map almost one-to-one onto product invariants 1–5 and 7.

**Costs/risks:** it is a private product convention, not a published contract;
the cloud relay is a Durable Object (Workstream B); and whether an external
runtime can register without impersonating a Kilo agent is **not yet proven**
(Workstream A). An external adapter built on it may be version-coupled to Kilo
internals unless a narrow seam is added.

**Best fit for:** shared logical identity, durable history, event relay,
ownership/reconnect — the invariants no general protocol provides.

### Approach 2 — Use ACP with a Kilo adapter if needed

**What reuse buys:** a standard, well-governed live-control boundary with
permissions, tool streaming, and an ecosystem; **and a Pi adapter already
exists** (`pi-acp`, consumed by OpenHands). Adopting ACP for the Pi-facing edge
avoids inventing an agent interface.

**Costs/risks:** ACP is **not** a shared-session or persistence layer
(agent-owned IDs; `resume` only same-agent). Kilo today is an ACP **agent**,
not a host; using ACP to bring Pi *into* Kilo means writing an ACP client in
Kilo or a bridge process, plus a separate mapping of ACP session IDs to Kilo
logical sessions. It also introduces a dependency on a third-party 0.0.x
adapter and inherits the ACP **thinking-signature fidelity loss** over an ACP
tap (Source claim USL + Verified ACP v2 content model). It does not, by itself,
satisfy invariants 1, 2, 4, or 5.

**Best fit for:** the Pi-facing adapter edge and future interoperability; **not**
the shared-session substrate.

### Approach 3 — Define a minimal project-specific event/transport contract

**What it buys:** only the semantics neither existing interface provides
(external-runtime registration, execution-owner grant/revoke, turn-boundary
handoff). It avoids inventing a wire protocol if it reuses Kilo's transport and
Pi's RPC.

**Costs/risks:** "minimal" can silently grow; a bespoke contract duplicates
Kilo's existing relay/ownership machinery; and a new protocol is exactly what
Plan.md warns against "merely because it seems cleaner."

**Best fit for:** a **thin mapping/semantics layer** on top of Approaches 1/2,
not a parallel transport.

---

## 4. Recommendation (evidence-backed)

**Recommendation — primary: Approach 1 + a minimal semantics layer
(Approach 3), with ACP (Approach 2) adopted only at the Pi-facing edge if it
earns its keep.**

Concretely:

1. **Reuse Kilo's existing session model and Remote Connections transport**
   (`remote-protocol.ts`, `kilo-sessions.ts`, `attached-state.ts`) for logical
   session identity, shared history, event relay, and ownership/reconnect.
   Rationale: these already implement invariants 1–5 and 7, and reusing them is
   the smallest-change path to the stated mission ("Pi as an external runtime
   for Kilo's existing session infrastructure").
2. **Bridge to Pi through Pi's native RPC/SDK, not a new agent protocol.**
   Like `pi-acp` does with ACP, a Kilo-side adapter can spawn `pi --mode rpc`
   and map commands/events. This preserves Pi's native tools/permissions/config
   (invariant 6) and local-first operation (invariant 7).
3. **Reuse `pi-acp` and the USL `pi.ts` converter as prior art, not
   necessarily as dependencies.** `pi-acp` is the proven Pi↔ACP translator
   (MIT); `usl-convert/pi.ts` is the proven Pi session import/export with
   declared fidelity and idempotent IDs. Borrow their mappings and tests.
4. **If ACP is adopted, adopt it as the Pi-facing edge only.** The cheapest
   ACP route is to reuse `pi-acp` (or a reviewed fork) rather than writing a Pi
   agent interface; this still requires a new ACP **client** in Kilo and a
   Pi-session→Kilo-logical-session mapping. Do **not** treat ACP as the
   shared-session/store layer.
5. **Borrow ASP's vocabulary for the semantics layer.** Use declared
   per-axis fidelity + loss lists, opaque `unknown` passthrough, content-
   addressed event IDs, and the explicit `handoff` lineage relation instead of
   inventing them. Treat ASP as the live **conceptual reference** (Approach 3's
   shape), not a Phase 1 runtime dependency (draft, TS-only, single impl).
6. **Use OpenTelemetry only around the adapter** (lifecycle/turn/tool spans,
   error metrics), never as session history/identity/control.
7. **Do not adopt OpenHands or `kilo-pi-provider` wholesale.** OpenHands is a
   host/runtime-separation lesson (and proof Pi-over-ACP is consumed);
   `kilo-pi-provider` is a BSL-1.0 Pi extension, not a session bridge.

### Rejected alternatives and reasons

- **ACP as the shared-session / durability layer — rejected.** ACP session IDs
  are agent-owned/opaque (`NewSessionRequest` has no client session ID);
  `load`/`resume` only reach the same agent; there is no cross-runtime
  continuation, no shared store, no ownership lease, no idempotent prompt. It
  cannot satisfy invariants 1–2 or 4–5 alone.
- **Building a brand-new general protocol — rejected.** Kilo's Remote
  Connections already covers relay/ownership/reconnect; a new wire protocol
  would duplicate it and violate the "small, well-separated adapter" goal.
- **Adopting ASP/USL as a hard Phase 1 dependency — rejected (deferred).**
  Draft TS-only schema (3★), single implementation (55★), no ecosystem; MIT and
  conceptually excellent, but too immature to depend on now. Its **Pi
  converter and fidelity model are reusable references.**
- **Vendoring OpenHands' stack — rejected.** Different product; MIT but large;
  only the host/runtime-separation pattern and tool-call event shape are
  relevant.
- **Using OTel as the session protocol — rejected.** Observability ≠ durable
  session history/identity/control (explicit in Plan.md and confirmed).

---

## 5. Protocol concepts this project genuinely needs to define

Only what the existing interfaces do **not** already provide:

1. **External-runtime registration / non-impersonation.** How Pi is advertised
   to Kilo as an *external execution owner* distinctly from a Kilo agent
   (Kilo's `InstanceAdvertisement`/`Capabilities` cover instances, not a
   third-party runtime kind). *(Workstream A's smallest seam.)*
2. **Logical-session ↔ runtime-instance binding, with an execution-owner
   grant/revoke and fencing token.** Kilo has attach/detach ownership for its
   own sessions; an explicit, transferable owner lease is still needed so two
   runtimes cannot both believe they own a turn (invariants 4–5).
3. **Turn-boundary handoff semantics.** A shared, idempotent message/turn ID,
   "accepted vs turn-complete" distinction (Pi has `disposition`/`agent_settled`;
   ACP v2 has prompt-acceptance vs idle), and a safe point at which ownership
   transfers. Explicitly declare that *active-turn migration* is out of scope.
4. **Event mapping + fidelity declaration for Pi → Kilo.** Pi-specific event
   kinds (thinking signatures, compaction, retries, queue/steering,
   `entry_appended`) must map into Kilo events with an opaque-passthrough
   container and a declared per-axis loss list (borrow ASP's model).
5. **Pi native session identity ↔ logical session identity.** Pi's tree IDs
   (`id`/`parentId`, session header, file path) must be associated with the
   shared logical session without rewriting Pi's native file (invariant 6).
6. **Runtime capability advertisement for a Pi runtime.** Accurately report
   which Pi features are exposed (model/provider set, tools, thinking,
   fork/clone) so Kilo UI can be honest (invariant 8).
7. **Reconnect/replay dedup policy at the adapter.** Reuse Kilo's attach
   fences; define idempotency keys for replayed Pi events and retried user
   messages (invariant 5).

Everything else (wire framing, heartbeats, subscribe/command/event, permission
routing, streaming chunks, unknown-payload preservation) already exists in
Kilo's transport, Pi's RPC, or ACP and should be reused rather than redefined.

---

## 6. Open questions

1. **Can an external runtime register on Kilo's Remote Connections / session
   infrastructure without impersonating a Kilo agent, and what is the smallest
   Kilo-side seam?** (Workstream A; owner file
   `2026-10-16-workstream-a-kilo-local.md`.) This determines whether Approach 1
   is truly the smallest change.
2. **Does Kilo Cloud expose a third-party-runtime attach path, and which
   transport/auth is reusable?** (Workstream B; `…-workstream-b-kilo-cloud.md`.)
3. **Is `pi-acp` stable enough to depend on or fork?** 0.0.x, single
   maintainer, 734★, self-described MVP, minor breaking changes expected; no
   `fs/*`/`terminal/*` delegation and no MCP wiring.
4. **Thinking/opaque fidelity over ACP:** ACP v2 dropped a first-class thinking
   block; confirm whether Pi thinking signatures survive any chosen ACP path
   (USL flags this as a declared-loss decision).
5. **Ownership/dedup gap:** neither ACP nor Pi RPC provides an execution-owner
   lease or exactly-once prompts; confirm the Kilo attach fence can be reused
   for a foreign runtime before designing a new lease.
6. **ASP/USL reproducibility:** the "zero-loss" Pi round-trip is a Source claim;
   reproduce `usl-convert` `pi` import/export locally (fixtures/tests) before
   borrowing the fidelity vocabulary as normative.

---

## 7. Cross-references / handoff notes

- Do **not** write to `evidence-ledger.md`; the synthesis track consolidates it.
- Cite this file + commit as: `reports/research/2026-10-16-workstream-d-prior-art.md`
  @ repo commit `1c4a449` (artifact commit TBD).
- External SHAs recorded in the sources table; ACP/ASP/USL/OpenHands/`pi-acp`
  re-verify by re-running `git rev-parse HEAD` in `/tmp/pi-kilo-workers/src/*`
  (coordinator pre-clones) or re-fetching the URLs.
- Key upstream rename to carry forward: **`badlogic/pi-mono` → `earendil-works/pi`**
  (same MIT project; `pi` package scope `@earendil-works/pi-coding-agent`).
