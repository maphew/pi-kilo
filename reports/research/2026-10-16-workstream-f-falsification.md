# Workstream F — Independent falsification and test design

- Bead: `pi-kilo-hyj.6`
- Date of investigation: 2026-10-16 (UTC)
- Owner: ws-f
- Status: complete (Phase 0 research + test design only — no implementation)
- Independence: threat scenarios F1–F8 were derived **only** from `Plan.md`
  ("Product invariants", "Essential conceptual distinction", "Security and
  reliability requirements", Workstream F question list) and read-only source
  inspection. Workstreams A–E artifacts were **not** read until after F1–F8 and
  the falsification experiment were drafted; see "Cross-check vs A–E" at the end.

## Sources examined (retrieval date 2026-10-16)

| Repo / artifact | Revision | Notes |
|---|---|---|
| `/home/mhw/dev/kilocode` (Kilo Code, maphew fork of Kilo-Org/kilocode) | `11c1899e09cc58d57e96950ab60a531b6c3793d9` | opencode-derived core, `packages/opencode/src/kilo-sessions/*` |
| `/home/mhw/dev/kilo-cloud` (Kilo Cloud) | `40b2a4dc5b23a40dd805d97d0f469550359075cc` | `services/session-ingest`, `packages/cloud-agent-sdk`, `packages/session-ingest-contracts` |
| Pi CLI docs, installed `@earendil-works/pi-coding-agent@1.3.0` | package `1.3.0` | docs `rpc.md`, `rpc-commands.md`, `rpc-extension-ui.md`, `json.md`, `session-format.md`, `sdk.md`, `cli-integration.md` |
| `/home/mhw/dev/pi-kilo` | `1c4a4491704708f8dd07a45d6a5c8d325238327c` | `Plan.md` invariants only |

Local clones were used; commit SHAs above are the local HEADs at retrieval time.
"Verified fact" below cites a file/symbol in those revisions.

> Scope note: this is a **private/internal wire protocol**. `services/session-ingest/src/types/user-connection-protocol.ts` and
> `packages/opencode/src/kilo-sessions/remote-protocol.ts` are two hand-mirrored
> copies of the same contract. Neither is documented as a public/stable API.

---

## Architecture under test (reconstructed, to be falsified)

The Plan's preferred shape is a small Pi adapter plus a narrow Kilo
extension. The most attractive concrete form — and the one F1–F8 attacks — is:

> **Preferred architecture (PA):** a Pi process runs a thin adapter that speaks
> Kilo's existing remote-connection wire protocol to the existing cloud relay
> (`/api/user/cli` → `UserConnectionDO`), advertises a session id that Kilo
> knows, forwards Pi's RPC/JSONL events into Kilo's event shapes, and
> receives web `command` frames (`send_message`, `permission_respond`, …).
> The existing Kilo web/mobile UI renders that session. No (or minimal) Kilo
> changes; shared logical identity is achieved by both runtimes using the same
> Kilo session id.

PA is what the falsification experiment tries to break. If PA's own wire
contract cannot satisfy ownership + identity + dedupe, then Kilo changes are
required and the "relatively small adapter" answer is wrong.

Key verified structure of PA's contract:

- CLI→relay frames: `heartbeat` (session list + instance + capabilities),
  `event`, `response`
  (`kilo-cloud/.../types/user-connection-protocol.ts`, `CLIOutboundMessageSchema`).
- Relay→CLI frames: `subscribe`, `unsubscribe`, `command`, `system`,
  `heartbeat_ack` (`CLIInboundMessageSchema`).
- Relay→web frames carry the same `event`/`response` envelopes
  (`WebInboundMessageSchema`); the SDK normalizes them in
  `kilo-cloud/packages/cloud-agent-sdk/src/normalizer.ts`.
- Live CLI session consumption is `cli-live-transport.ts`; history is
  `SessionIngestDO` + `session-ingest-contracts`; the relay is
  `UserConnectionDO`.

---

## F1 — The existing Kilo UI cannot represent an externally-owned runtime

**Failure mechanism.** Kilo's identity for a connection only knows two
producer kinds: `instance.kind: z.enum(["cli", "remote"])` and a free-form
`platform` (OS) field
(`kilo-cloud/.../user-connection-protocol.ts`; mirrored in
`kilocode/.../remote-protocol.ts`). There is no "runtime provider" or
"external agent" field on a session or connection, and
`SessionIngestDO`'s ingest item set (`session-sync.ts`) has no runtime-kind
item. `normalizer.ts` maps a fixed set of Kilo/opencode event names
(`message.updated`, `message.part.delta`, `permission.asked`, …). A Pi
session can therefore only appear by **impersonating a Kilo CLI** and emitting
Kilo event shapes.

**Invariants broken.** #8 honest capability boundaries (UI would present Pi as
"a connected Kilo CLI/remote instance"); #4 explicit execution ownership
(nothing distinguishes "Pi owns this" from "Kilo CLI owns this"); #1 shared
logical identity is claimed but not visible as such.

**Evidence.**
- Verified fact: `InstanceAdvertisement.kind` = `["cli","remote"]` only;
  no provider/runtime field (`kilo-cloud/.../user-connection-protocol.ts`;
  `kilocode/.../remote-protocol.ts`).
- Verified fact: session rows carry `platform` / `createdOnPlatform` but no
  runtime owner (`kilo-cloud/.../user-connection-protocol.ts` `SessionEventV2RowSchema`).
- Inference: adding a truthful "runtime: pi" surface requires a Kilo schema/UI
  change, i.e. is not achievable by a pure adapter.

**Severity: High** (but correctness-only if the UI change is accepted upstream).
**Falsify if:** a runtime/provider identity field already exists somewhere the
UI reads and is rendered. I did not find one in the schemas I read.

---

## F2 — Session identity cannot be shared without violating one runtime's assumptions

**Failure mechanism.** Session IDs are not just opaque labels:
- Kilo session IDs are `ses_…`; `SessionIngestDO`'s per-session path validates
  the strict `ses_` format (comment in
  `kilo-cloud/.../user-connection-protocol.ts` contrasting the permissive
  `UserConnectionDO` path with "the strict ses_ format ... enforced by the
  per-session SessionIngestDO path").
- Pi's session id is a UUID in the session-file header
  (`json.md` / `session-format.md`: `{"type":"session","version":3,"id":"uuid",...}`),
  and Pi continuation means loading **Pi's JSONL session file** via
  `switch_session` (`rpc-commands.md`).

If the Pi adapter advertises a Kilo `ses_` id, it collides with the
Kilo-runtime session of the same id on the relay (`sessionOwners`, F4).
If it advertises Pi's UUID, Kilo sees a different logical session and the
"shared logical identity" claim is false. Either way, there is **no
runtime-agnostic logical-session ↔ runtime-session mapping** in the protocol:
`create_session.cloneFromKiloSessionId` is a one-time copy into a new
Kilo-managed session, not a shared identity (`cli-live-transport.ts`
`buildCreateSessionWireData`).

**Invariants broken.** #1 shared logical identity; #6 native runtime
preservation (Pi's own session file must remain authoritative for Pi);
#8 (continuation would be a transcript import, not Pi state).

**Evidence.**
- Verified fact: Pi session id is a UUID header; continuation =
  `switch_session` on a Pi JSONL file (`json.md`, `rpc-commands.md`).
- Verified fact: Kilo `ses_` format enforcement note
  (`kilo-cloud/.../user-connection-protocol.ts`).
- Verified fact: `sessionOwners` is a plain `Map<string,string>` keyed by
  session id with no runtime dimension (`UserConnectionDO.ts:329`).
- Inference: a correct design needs a stable logical-session record plus a
  mapping to per-runtime session files, or an explicit owner runtime field.

**Severity: Critical** (this is the primary research question).

---

## F3 — Message sync can create duplicate turns

**Failure mechanism.** Relay-level idempotency requires the web client to send
a `mutationId`; the relay's durable dedupe (D8) is keyed on it
(`UserConnectionDO.handleWebCommand`, `inflightMutations` /
`getDurablePendingCommand`). But the live chat path does **not** send
`mutationId`:
- `cli-live-transport.ts` `send:` calls `sendCommand('send_message', {...})`
  with **two** arguments (no mutationId); same for `send_command`.
- The only `mutationId` call sites are `create_session` (line ~992) and mobile
  remote-instance spawn. `grep mutationId apps packages` shows no chat-send use.
- The CLI `send_message` handler does not dedupe either: it parses, then
  unconditionally calls `prompt(promptInput)`; `messageID` is optional and
  simply forwarded into `SessionPrompt` (comment: old clients omit it; the CLI
  then assigns `MessageID.ascending()`)
  (`kilocode/.../remote-sender.ts` ~lines 177–190, 1215–1268).

Therefore a command that is dispatched twice (web reconnect + resend, relay
retry, double-click) is executed twice; if `messageID` is omitted the runtime
cannot even recognize it as the same turn.

**Invariants broken.** #5 no duplicate side effects; #3 real continuation
(a duplicated user turn is not the same logical turn).

**Evidence.**
- Verified fact: `send_message`/`send_command` call sites pass no third
  `mutationId` argument (`cli-live-transport.ts` ~1039–1095).
- Verified fact: relay dedupe branch is guarded by `if (msg.mutationId)`
  (`UserConnectionDO.ts` ~1627).
- Verified fact: `send_message` handler has no messageID dedupe and calls
  `prompt()` (`remote-sender.ts` ~1215).
- Verified fact: `mutationId` is documented ("Stable client-side intent id …
  retry with the same mutationId runs the command once for the full TTL
  window", `user-connection-protocol.ts`).

**Severity: Critical.**
**Falsify if:** every shipped chat client already sends a stable `messageID`
*and* `SessionPrompt` is idempotent on it, or the relay treats `messageID` as
a dedupe key. I found no such relay branch.

---

## F4 — Kilo (or another runtime) can execute work for a Pi-owned session

**Failure mechanism.** Ownership is **last-heartbeat-wins**, with no explicit
lease and no runtime-type authorization:
- `sessionOwners.set(session.id, connectionId)` on every heartbeat; if a
  different connection reports the same id, the previous owner's pending
  commands are failed and ownership moves (`UserConnectionDO.ts` ~688–724).
- Command routing uses `findCliForSession(sessionId)` = whoever owns it
  (`UserConnectionDO.ts` ~2425).
- The relay only rejects a stale web-supplied `connectionId`
  (`SESSION_OWNER_CHANGED_ERROR`); it does **not** reject a second CLI that
  claims a session already owned by a Pi adapter, nor check runtime identity.

So if both Pi and a Kilo CLI heartbeat the same session id (F2), either runtime
can end up receiving a web command and executing it. There is no
"execution owner" abstraction beyond "which socket heartbeated last".

**Invariants broken.** #3 real continuation reaches the wrong runtime;
#4 explicit execution ownership; #5 duplicate/conflicting side effects;
#9 security (no authorization that a given runtime may claim a session).

**Evidence.**
- Verified fact: ownership map and overwrite-on-heartbeat
  (`UserConnectionDO.ts` ~329, ~688–724).
- Verified fact: `findCliForSession` routing (`~2425`).
- Verified fact: only stale-connection rejection (`~1568`,
  `SESSION_OWNER_CHANGED_ERROR`).
- Inference: two runtimes with the same id produce ownership flapping whose
  outcome depends on heartbeat timing — nondeterministic execution ownership.

**Severity: Critical.**
**Falsify if:** the producer contract forbids two connections advertising one
session id *and* the relay enforces it. The per-DO owner move is a failover
mechanism, not a guard.

---

## F5 — Tool events can be lost or reordered

**Failure mechanism.** The live `event` envelope has **no sequence number and
no relay-level event id** (`CLIOutboundMessageSchema` `event` variant:
`{sessionId, parentSessionId?, event, data}`; `forwarder` in
`remote-sender.ts` sends the raw event payload). Pi's side is also
cursor-less: RPC session events have no global id and no resume/catch-up;
streaming updates are delta-only (`json.md` "Reconstruct streaming messages":
`message_update` records are delta-only). `catch_up` exists only as a schema
in `ws-protocol.ts`; I found **no producer** in `services/session-ingest/src`
(grep for `catch_up` returns only the schema). History is persisted
idempotently by item identity (`message`/`part` ids), which can rebuild
*finalized* state, but an adapter/websocket drop mid-turn can lose in-flight
deltas and tool-progress events.

**Invariants broken.** #2 shared history; #5 (a lost `tool_execution_end` or
duplicated `message.part.updated` corrupts the transcript); #8 (partial
streams are not durable history).

**Evidence.**
- Verified fact: no sequence field in the relay `event` envelope
  (`user-connection-protocol.ts`).
- Verified fact: Pi `message_update` is delta-only with no global event id
  (`json.md`).
- Verified fact: `catch_up` is schema-only in the service
  (`types/ws-protocol.ts`; no producer found).
- Observed behavior (literature-level, not run): WebSocket ordering is
  preserved per connection, so *transport* reordering is unlikely; *loss*
  across reconnect is the concrete risk.
- Inference: session-file replay (Pi) + item-id ingest (Kilo) can reconcile
  finalized history; transient deltas cannot be recovered from Pi RPC alone.

**Severity: High.**
**Falsify if:** reconnect triggers a `catch_up` (or Pi can resume its event
stream from a cursor), or the UI treats live deltas as disposable and always
re-renders from persisted items.

---

## F6 — Reconnect can replay side effects

**Failure mechanism.** Two independent replay paths:
1. **Pending-state replay (Kilo → web).** On (re)subscribe the CLI re-sends
   pending `suggestion.shown`, `question.asked`, `permission.asked`, and a
   `session.queue.changed` snapshot (`remote-sender.ts` `replay()` ~554–609).
   If a permission was answered but not yet removed from `permission.list()`,
   a re-subscribing client can be shown it again; a second
   `permission_respond` for an already-resolved `requestID` is then a
   semantic replay of a decision.
2. **Command replay (web → CLI).** See F3: without `mutationId`, a reconnect
   resend is a new dispatch. `sessionOwners` failure handling also fails
   pending commands on owner change, which can prompt clients to retry.

Kilo's **history** replay is comparatively safe: ingest is keyed on
`itemId`/`message.id`/`part.id` and the clone digest uses
`itemId:itemType:itemData` identity (`SessionIngestDO.ts` ~363, ~516), so
finalized history is idempotent.

**Invariants broken.** #5 no duplicate side effects; #9 (a replayed/duplicated
permission decision is an authorization side effect).

**Evidence.**
- Verified fact: `replay()` re-emits pending permission/question/suggestion
  events on subscribe (`remote-sender.ts` ~554–609).
- Verified fact: relay dedupe gated on optional `mutationId`
  (`UserConnectionDO.ts` ~1627).
- Verified fact: ingest identity keyed on item id (`SessionIngestDO.ts` ~363).

**Severity: High.**
**Falsify if:** `permission.reply`/`question.reply` are idempotent on their
request id and the UI suppresses replays it has already answered.

---

## F7 — Permissions may not remain enforced by the executing runtime

**Failure mechanism.** The contract *intends* enforcement in the executing
runtime: the web sends `permission_respond`; the CLI handles it via
`permission.reply({...})` (`remote-sender.ts` ~1360–1372), and `permission.asked`
is a runtime-emitted event. On the Pi side, permissions are **extension/UI
driven**: `extension_ui_request` (`confirm`/`select`) is answered by
`extension_ui_response`, and RPC can only forward *supported* dialogs, not
custom terminal components (`rpc-extension-ui.md`; `extensions.md`).

Risk: the adapter maps Pi permission asks onto Kilo's `permission.asked`, but
if the mapping is lossy or the adapter auto-approves on reconnect/timeout
(F6), the Kilo web could cause Pi to run a tool that Pi's own permission
extension would have denied. The relay also has no allow/deny policy of its
own beyond the viewer command allowlist (`UserConnectionDO.ts`
`Viewer command allowlist`, ~129–146), so enforcement leans entirely on the
adapter's fidelity.

**Invariants broken.** #9 security (permission bypass via the web path);
#6 native runtime preservation (Pi's permission config).

**Evidence.**
- Verified fact: permission answers route to the executing CLI
  (`remote-sender.ts` ~1360).
- Verified fact: Pi permission/approval is extension UI in RPC mode and only
  supported dialogs forward (`rpc-extension-ui.md`).
- Verified fact: relay has a fixed command allowlist but no permission policy
  (`UserConnectionDO.ts` ~129–146).
- Inference: a faithful adapter must refuse to answer any Pi dialog it cannot
  represent, and must not auto-approve. This is a design requirement, not an
  existing guarantee.

**Severity: Critical** (security invariant).
**Falsify if:** the adapter can prove every remote tool execution still passes
through Pi's native permission gate, including reconnect and timeout paths.

---

## F8 — Cloud support depends on private APIs / inaccessible production infra

**Failure mechanism.** PA's true path is Kilo Cloud infra:
`UserConnectionDO` + `SessionIngestDO` Durable Objects, R2, queues, and an
authenticated `/api/user/cli?token=…` WebSocket
(`kilocode/.../remote-ws.ts` ~437; `kilo-cloud/services/session-ingest`).
There is no published, stable, public contract for this; the two protocol
files are hand-mirrored internal copies. Demonstrating real `app.kilo.ai`
representation therefore requires production (or a faithfully bound local
wrangler/miniflare environment with auth and DO/R2/queue bindings). The
`cloud-agent-sdk` client targets an endpoint that likewise assumes the hosted
service.

**Invariants broken / at risk.** #7 local-first (Pi must work without Kilo —
that part is fine); #10 upstream viability (adapter tracks a private wire
protocol with `protocolVersion`/`capabilities` drift); Phase 1 acceptance
("see that logical conversation in the Kilo experience") is only provable with
prod access or a harness.

**Evidence.**
- Verified fact: authenticated WS endpoint with token
  (`remote-ws.ts` ~437).
- Verified fact: DO/R2/queue architecture (`services/session-ingest`,
  `SessionIngestDO.ts`).
- Verified fact: hand-mirrored schemas (`remote-protocol.ts` vs
  `user-connection-protocol.ts`).
- Open question: how much of the path can be exercised with the repo's own
  integration test harness (`test/integration/session/*`) minus prod secrets.

**Severity: High** for cloud claims; **Medium** for Phase 1 if a clearly
labelled local harness is accepted (Plan explicitly allows a harness).

---

## Falsification experiment (smallest experiment that can disprove PA)

**Hypothesis under test (H):** *No Kilo changes are needed.* A thin Pi adapter
speaking the existing remote-connection protocol, advertising a Kilo session
id, can give (a) display of a Pi session, (b) delivery of a web message to Pi
exactly once, (c) a single explicit execution owner, (d) no side-effect replay
on reconnect, and (e) Pi-native permission enforcement.

**Design — "one shared id, two owners, one retry."** Build the smallest local
harness, no production credentials:

Setup (local only):
1. Run the relay's own integration harness in-process (the
   `services/session-ingest` vitest/DO test environment) or a ~200-line WS
   stub implementing `user-connection-protocol.ts`. Label a stub as a harness.
2. Start one real `pi --mode rpc` child; run a thin adapter that speaks the CLI
   protocol and maps a single Pi session to Kilo session id `ses_f` (fabricated
   `ses_` id).
3. Open two "web" clients: W1 (subscribe + send) and a second CLI/adaptor
   process `C2` that heartbeats the **same** `ses_f`.
4. Use a Pi tool whose side effect is easy to count (e.g. a `bash` command that
   appends a line to a local file).

Steps and outcomes:

| # | Step | Expected if H holds | FALSIFYING outcome (H false) |
|---|---|---|---|
| 1 | W1 subscribes; adapter heartbeats `ses_f` | Session appears once | UI has no way to show it as Pi-owned (F1) |
| 2 | W1 sends one `send_message` with a fixed `messageID`; drop the response and resend the identical frame | Pi executes exactly once | Pi executes twice → F3 |
| 3 | `C2` heartbeats `ses_f`; W1 sends the next message | Command reaches Pi (explicit owner) or a clear ownership error | Command reaches `C2`/is nondeterministic → F4 |
| 4 | Kill the adapter WS mid-`tool_execution`; reconnect | Reconciled transcript, no lost finalized event, no re-executed tool | Missing `tool_execution_end` or repeated side effect → F5/F6 |
| 5 | Install a Pi permission extension that **denies** `bash`; W1 sends a message that would run `bash` | Pi denies; web shows denial | Tool runs → F7 |
| 6 | Repeat 5 while reconnecting after the permission prompt appears | Denial still enforced; no auto-approve | Auto-approval → F6/F7 |

**Decision rule.** The experiment disproves PA if **any** of steps 2–6 shows a
falsifying outcome. It disproves the *no-Kilo-changes* claim if steps 1, 3, or
5 fail. Steps 1–3 can be run entirely locally against a stub/harness; step 5
needs only Pi + a permission extension; only a "real app.kilo.ai" confirmation
needs prod (and needing prod is itself F8 evidence).

**What this experiment does NOT prove.** Even if all steps pass, it proves a
*harness* path, not that `app.kilo.ai` renders Pi-owned sessions, and it does
not create runtime-state migration (active-turn migration stays out of scope).

---

## Test plan (local-first)

Boundaries: adapter ↔ relay contract; relay ↔ web contract; adapter ↔ Pi RPC.

1. **Event mapping / contract tests.** Table-driven mapping Pi JSONL events →
   Kilo event shapes (`message_start/update/end`, `tool_execution_*`,
   `permission`, `session.idle`, queue/compaction). Assert every Kilo event in
   `normalizer.ts`'s switch has a defined Pi source or an explicit
   "unsupported, preserved as custom" outcome. Golden fixtures from a recorded
   Pi RPC stream; no network.
2. **Messaging.** `send_message` with `messageID` present/missing; duplicate
   delivery; command catalog (`list_commands`); attach/continue. Assert
   exactly-one execution per logical message id. This is the regression test
   for F3 and should be written **before** the adapter, so it can fail.
3. **Reconnection.** Fixture-driven WS harness that drops the socket at chosen
   points (mid-delta, mid-tool, after permission prompt). Assert: no lost
   finalized item, no duplicated finalized item (item-id keyed), no
   auto-answered permission, and a deterministic "unknown/uncertain" state when
   reconciliation cannot decide.
4. **Deduplication.** Property test: arbitrary duplicate/out-of-order delivery
   of the same `{messageID, mutationId}` set is idempotent. Assert the relay
   dedupe path is exercised (i.e. the client actually sends `mutationId`) or
   the design explicitly documents that it does not and why.
5. **Ownership.** Two simulated owners for one session id: assert explicit
   owner identity, ownership lease/expiry, conflict is *rejected* rather than
   silently reassigned, and commands are never delivered to a non-owner. This
   is the F4 gate.
6. **Failure handling.** Adapter crash mid-turn, relay unavailable, Pi exits,
   token refresh, process signals. Assert Pi continues locally (invariant #7),
   adapter fails visibly and safely (invariant #9 / reliability requirements),
   and no half-applied ownership state persists.
7. **Permission enforcement.** Pi permission extension deny/allow matrix driven
   through the web path, including reconnect and concurrent requests. This is
   the F7 gate.
8. **Cloud (gated, needs prod or bound local env; label clearly).** Only after
   1–7 pass: real `app.kilo.ai` display and command delivery. Mark as
   unverifiable if prod access is denied.

No production credentials are required for tests 1–7. Test 8 requires them and
must be reported as such, not assumed.

---

## Go / no-go recommendation (independent)

**Verdict: CONDITIONAL NO-GO on "small adapter, no Kilo changes"; GO for a
bounded local Phase 1 harness that is explicitly labelled and gated on
ownership + dedupe.**

Rationale: F3 (chat sends are not relay-deduped), F4 (last-heartbeat-wins
ownership across runtimes), and F2 (no runtime-agnostic logical session ↔
runtime session mapping) attack the *core* of PA, not its edges. F1 and F8
show the honest UI/cloud story needs Kilo changes. None of these are
implementation bugs in Pi; they are consequences of reusing a protocol whose
owner model assumes exactly one Kilo CLI per session id. A Phase 1 that only
proves history display + message delivery in a local harness is still worth
doing and low-risk, but it must not be presented as shared logical identity or
as cloud support.

**What would change this verdict (upgrade to GO on no-Kilo-changes):**
1. The relay (or a documented extension point) gains an explicit execution
   owner with a lease, rejects a second owner for the same logical session, and
   carries a runtime-kind/provider field the UI renders.
2. Chat `send_message`/`send_command` are relay-deduped by a stable
   `messageID`/`mutationId` independent of client cooperation.
3. A stable logical-session record maps to per-runtime session files, so Pi and
   Kilo can each continue natively from shared *history* without claiming each
   other's private state.
4. A `catch_up`/cursor mechanism (or an equivalent) recovers missed live events
   on reconnect.

**What would downgrade to plain NO-GO:** if step 5 of the experiment (permission
bypass) fails and cannot be fixed inside the adapter, or if the only way to
make identity work is to fork Kilo's session model (violates invariant #10).

---

## Open questions

1. Does any `catch_up` producer exist outside `services/session-ingest/src`
   (e.g. a worker not in this checkout)? F5 hinges on it.
2. Does `SessionPrompt` dedupe on `messageID` anywhere downstream of
   `remote-sender.ts`? If yes, F3 severity drops for modern clients.
3. How much of `UserConnectionDO`/`SessionIngestDO` can run locally via the
   repo's own integration harness without prod secrets/bindings? F8 hinges on
   it.
4. Is advertising `kind: "remote"` with a Pi `platform` (or a new field)
   acceptable upstream, or is the UI hard-coded to CLI semantics?
5. For Pi RPC, what is the officially supported cursor/resume story (if any)
   for a client that reconnects mid-turn? Docs describe no resume; confirm
   against the installed version's source.

---

## Cross-check vs A–E

_Drafted after F1–F8 and the experiment were written; A–E were read only now.
This section notes overlap/gaps, not agreement. No A–E file was modified._

Repo commit for all files: `1c4a4491704708f8dd07a45d6a5c8d325238327c`
(`1c4a449`); working-tree blob SHAs below, since some A–E files are
uncommitted.

- **A (`2026-10-16-workstream-a-kilo-local.md`, SHA `47676d2f…`)** — stub,
  no findings. F2/F4 answer parts of A's open questions; no overlap to
  reconcile.
- **B (`2026-10-16-workstream-b-kilo-cloud.md`, SHA `86a12e3e…`)** — stub,
  no findings. F1/F8 bear directly on B's questions (does cloud distinguish
  locally owned runtimes; is there a third-party attach path).
- **C (`2026-10-16-workstream-c-pi-runtime.md`, SHA `b6abcc2a…`)** — stub,
  no findings. F5/F7 derive Pi-side failures from the installed Pi docs.
- **E (`2026-10-16-workstream-e-architecture.md`, SHA `59d48774…`)** — stub,
  no findings. F2/F4 are pre-emptive counterexamples to any E design that
  reuses Kilo session ids without a runtime-kind + owner lease.
- **D (`2026-10-16-workstream-d-prior-art.md`, SHA `525f62b5…`, 485 lines)** —
  filled. D recommends **Approach 1 + a minimal semantics layer**: reuse
  Kilo's Remote Connections transport and `attached-state.ts` for identity,
  history, relay, ownership and reconnect, then define only the missing
  semantics. D's own section 5 already lists the gaps this workstream found
  independently: (1) external-runtime registration / non-impersonation,
  (2) execution-owner grant/revoke + fencing token, (5) Pi↔logical session
  identity, (7) reconnect/replay dedup policy. D's section 6.5 open question —
  that neither ACP nor Pi RPC provides an execution-owner lease and the Kilo
  attach fence must be confirmed reusable for a foreign runtime — is exactly
  F2/F4's target.

**Where F stayed independent and where it disagrees.** F1–F8 and the
experiment were written before D was read; the overlap is convergent, not
copied. F also adds evidence D's optimism underweights:

1. D calls the Kilo ownership machinery an implementation of invariants 4–5.
   F4 shows two layers: the **CLI-side** `attached-state.ts` state machine is
   careful, but the **relay-side** `UserConnectionDO.sessionOwners` is
   last-heartbeat-wins with **no runtime-kind authorization**
   (`UserConnectionDO.ts` ~329, ~688–724). Reusing the CLI fence does not by
   itself stop a foreign runtime and a Kilo CLI from alternately claiming one
   session id.
2. D's section 5.7 asks for a reconnect/replay dedup policy. F3 shows the gap
   is live **today** for chat: `send_message`/`send_command` are dispatched
   **without** `mutationId`, and the relay's durable dedupe is gated on it, so
   retries are not once-only without adapter/client changes.
3. D treats ACP as not a shared-session layer (agree), but F7 notes the
   permission-fidelity risk applies equally to the Approach 1 bridge: the
   relay has no permission policy, so Pi's native gate must be preserved by
   the adapter on every path including timeout/reconnect.

**Net effect on the verdict.** D's recommended shape and F's conditional
no-go are compatible: D already scopes the missing semantics as work to be
*defined*, and F's experiment is the gate that decides whether that work can
stay adapter-side or must change Kilo. Where D says these invariants are
already implemented, F1–F4 say *not yet across runtimes* — that is the
measurement the Phase 0 synthesis should carry forward, and the reason F does
not recommend starting broad Phase 1 implementation before the experiment.
