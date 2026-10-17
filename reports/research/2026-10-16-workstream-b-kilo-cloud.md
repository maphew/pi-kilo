# Workstream B — Kilo Cloud and hosted sessions

- Bead: `pi-kilo-hyj.2`
- Date: 2026-10-16 (UTC)
- Status: complete (Phase 0 read-only research)
- Owner: `ws-b` (claim `pi-kilo-hyj.2` before editing)
- Scope: read-only. No connector implementation, no upstream PR, no branch
  publish, no production writes.

## Repos examined

| Repo | Commit | Retrieved (UTC) | License |
|---|---|---|---|
| https://github.com/Kilo-Org/cloud | `d38649d7e3ac06c45d76c61baa334be5df0fbc02` | 2026-10-16T23:02Z | **OCVSAL v1.0 (source-available, not OSI)** — `LICENSE.md`: "Using software … in production requires a valid commercial agreement from the copyright holder." |
| https://github.com/Kilo-Org/kilocode | `1552877e82ceaecc79a9fd4be7859518745e6f56` | 2026-10-16T23:02Z | **MIT** — `LICENSE` |

### License warning before proposing dependencies

**Source claim / Verified fact:** `Kilo-Org/cloud` is licensed under the Open
Core Ventures Source Available License, not an open-source license. Reading and
testing are permitted; `LICENSE.md` states production use requires a commercial
agreement and that the copyright holder retains title to modifications. Any
architecture that adds a runtime to Cloud, or copies Cloud code, must be
reviewed by whoever owns that commercial relationship. `Kilo-Org/kilocode`
(the CLI/SDK side) is MIT and can be reused under MIT terms. This report does
not propose a dependency; it maps interfaces.

All line/symbol citations below are against the two SHAs above.

## Questions (from Plan.md)

- [x] How are projects, conversations, messages, events, runtime instances represented?
- [x] What is the source of truth for session history?
- [x] Does a cloud session require a Kilo-managed execution environment?
- [x] Can an external local runtime attach to an existing cloud-visible session?
- [x] Which transport, authentication, and reconnect mechanisms already exist?
- [x] What would need to change to represent execution owned by Pi?
- [x] Can the web interface distinguish offline / disconnected / busy / locally owned runtimes?

## Required distinction: "session is visible" ≠ "runtime integration"

Keep these five capabilities separate (Plan.md). This report uses them
consistently:

| Capability | Definition | Status for external runtime on Cloud (today) |
|---|---|---|
| History access | A UI can display events produced elsewhere | Read-only sessions exist (`ResolvedSession` type `read-only`, `CloudAgentProvider.tsx:147`) |
| Bidirectional messaging | UI sends messages to the owning runtime and observes results | Exists only for Kilo CLI transports (remote / cloud-agent); no third-party runtime transport |
| Continuation | A runtime resumes its own session with its own context | Works for Kilo CLI (session import / snapshot restore); not for Pi |
| Turn-boundary handoff | Another runtime takes ownership between turns | Remote Connections ownership transfer exists between two Kilo CLIs; not exposed to non-Kilo runtimes |
| Active-turn migration | Take over an in-progress turn incl. tool state | **Out of scope**; no mechanism found |

**Verified fact (explicitly separate concerns):** Cloud's own session spec
defines a **Read-only session** as "a session this viewer cannot drive"
(`.specs/cloud-agent-session.md`, Definitions). Driving a session and reading
it are distinct, first-class states in the product, not the same capability.

## Findings

### Q1. How are projects, conversations, messages, events, runtime instances represented?

**Projects / workspaces.**

- **Verified fact:** Cloud "projects" are generated from repository + worktree
  grouping, not a first-class `project` table. Tables:
  - `cloud_agent_workspace_folders` — `packages/db/src/schema.ts:6272`.
  - `cloud_agent_worktrees` — `packages/db/src/schema.ts:6305` (has
    `runtime_locations` JSONB: array of `{ sandboxId, provider }`,
    `session-ingest-contracts/src/rpc-contract.ts`
    `cloudAgentWorktreeLocationSchema`, provider enum
    `cloudflare | vercel | cloudflare-containers`).
- **Verified fact:** There is also a *logical* session table `cli_sessions_v2`
  (`packages/db/src/schema.ts:6346`) with `git_url`, `git_branch`,
  `organization_id`, `parent_session_id`, `public_id`,
  `cloud_agent_session_id`, `cloud_agent_session_scope_id`,
  `cloud_agent_worktree_id`, `profile_id`, `status`, `last_activity_at`,
  `total_cost_microdollars`, `live_summary`. This is the shared, cross-interface
  session identity that both local CLI and Cloud write.

**Conversations / logical sessions.**

- **Verified fact:** A logical conversation is a row in `cli_sessions_v2`,
  keyed by `(session_id, kilo_user_id)` where `session_id` matches
  `ses_` + 26 chars (`session-ingest-contracts/src/rpc-contract.ts`
  `sessionIdSchema`). The same row is what a local CLI session, a Cloud Agent
  session, and the web UI all reference.
- **Verified fact:** Cloud Agent conversations additionally have
  `cloud_agent_sessions` (`packages/db/src/schema.ts:6628`), keyed by
  `cloud_agent_session_id` (`agent_<uuid>` legacy, `workspace_<uuid>` control
  plane), unique-linked to one `kilo_session_id`. Per-turn execution rows live
  in `cloud_agent_session_runs` (`packages/db/src/schema.ts:6780`, status enum
  `queued|accepted|completed|failed|interrupted`).

**Messages / events.**

- **Verified fact:** Message/part history is *not* in Postgres. It is ingested
  as a stream of typed items to a per-`(user, session)` Durable Object, defined
  by `SessionItemSchema` in
  `services/session-ingest/src/types/session-sync.ts`: `kilo_meta`, `session`,
  `message`, `part`, `session_diff`, `model`, `session_open`, `session_close`,
  `session_status`, `agent_notification`, `session_pr_link`. `message`/`part`
  carry client-supplied `id`/`messageID` storage-key segments.
- **Verified fact:** `SessionIngestDO` (`services/session-ingest/src/dos/SessionIngestDO.ts`)
  ingests (`ingest()` line 482), exports the full stream (`getAllStream()`
  line 1072), reads paginated SDK messages (`readKiloSdkMessages()` line 1059),
  and supports clone export (`exportCloneBatch()` line 1556).
- **Verified fact:** Session lifecycle/metadata *events* (not transcript) are
  broadcast as `SessionEventPayload` — `session.created`, `session.updated`,
  `session.status.updated`, `session.deleted` — in
  `services/session-ingest/src/types/user-connection-protocol.ts`.
- **Verified fact (cloud-only):** Cloud Agent has its *own* append-only event
  log in the `CloudAgentSession` Durable Object SQLite `events` table
  (`services/cloud-agent-next/src/session/queries/events.ts`; types in
  `services/cloud-agent-next/src/websocket/types.ts` `StreamEvent`).
  `StreamEventType` includes `kilocode`, `output`, `status`, `error`,
  `complete`, `preparing`, `cloud.status`, `cloud.message.*`,
  `commands.available`, `heartbeat`, `interrupted`.

**Runtime instances.**

- **Verified fact:** For Remote Connections, a runtime instance is the
  optional `instance` object on the CLI heartbeat:
  `{ name, projectName, version?, kind: 'cli'|'remote', startedAt?, gitBranch? }`
  (`services/session-ingest/src/types/user-connection-protocol.ts`,
  `instanceSchema`). It is stored in the WebSocket attachment and surfaced by
  `UserConnectionDO.getConnectedInstances()` (`UserConnectionDO.ts:2186`) and
  `/api/instances/active` (`routes/api.ts:946`). The only kinds are `cli` and
  `remote` — there is no third-party/external kind.
- **Verified fact:** For Cloud Agent, the "runtime instance" is the **wrapper**
  process inside a sandbox. Its identity is a persisted lease and generation in
  `CloudAgentSession` DO storage:
  `services/cloud-agent-next/src/session/wrapper-runtime-state.ts`
  (`wrapper_runtime_state`, `wrapper_lease`, `wrapperGeneration`,
  `wrapperConnectionId`, `wrapperRunId`), with supervised
  `startup_verified`/`delivery_accepted`/`retain_warm` transitions.

### Q2. What is the source of truth for session history?

**Verified fact:** History is split:

1. **Transcript (messages, parts, diffs, tool activity)** — source of truth is
   the per-session `SessionIngestDO` SQLite state, fed by
   `POST /api/session/:sessionId/ingest`
   (`services/session-ingest/src/routes/api.ts:440`) and read back through:
   - `GET /api/session/:sessionId/export` (`api.ts:480`) → full DO stream;
   - `GET /api/session/:sessionId/messages` (`api.ts:557`) → paginated SDK
     messages;
   - internal scoped export under `/internal/cloud-agent/v1` for Cloud.
2. **Session metadata / index** — Postgres `cli_sessions_v2` (title, status,
   git refs, cost, `live_summary`). The schema comment at
   `packages/db/src/schema.ts:6366` says `live_summary` is derived by
   session-ingest from tool/todo/diff/error items and "only this summary is
   stored, never the raw text."
3. **Cloud Agent execution state** — its own DO (`CloudAgentSession`) event log
   + message queue + `cloud_agent_session_runs` in Postgres. This is the
   source of truth for a Cloud turn's lifecycle and streaming, and it
   *ingests* native Kilo history into session-ingest (see
   `services/cloud-agent-next/src/session-ingest-binding.ts`; Kilo's native
   history is published "to session-ingest" per `docs/control-plane.md`
   component table).

**Inference:** `cli_sessions_v2` is the *shared logical identity*, while
`SessionIngestDO` is the *shared transcript*, and the Cloud Agent DO is a
per-execution event/log owner that forwards to the transcript. A runtime that
wants to appear in Kilo must write items in the `SessionItemSchema` shape and
register the `ses_...` identity; that is sufficient for history to be visible.

### Q3. Does a cloud session require a Kilo-managed execution environment?

**Verified fact: yes for Cloud Agent.**
- `services/cloud-agent-next/Dockerfile:65` installs
  `@kilocode/cli@${KILOCODE_CLI_VERSION}` globally; the wrapper is
  `@kilocode/cloud-agent-wrapper` using `@kilocode/sdk` (`wrapper/package.json`).
- `services/cloud-agent-next/docs/control-plane.md` §1: "Cloud Agent is
  infrastructure around Kilo. It keeps a sandbox and Kilo running, passes
  messages from the user to Kilo, passes events and turn outcomes back, and
  stops idle sandboxes. Agent behavior belongs to Kilo."
- Wrapper launch env hardcodes `KILO_PLATFORM: 'cloud-agent'` and
  `KILO_DISABLE_AUTOUPDATE: 'true'`
  (`src/sandbox-control/wrapper-launch-env.ts`).
- The wrapper connects to the session DO over an internal `/ingest` WebSocket
  (`src/persistence/CloudAgentSession.ts:1283`); `ingest.ts` header states
  "The /ingest endpoint is internal-only - it should only be called by the
  wrapper via DO fetch, not exposed to external clients."
- Wrapper admission is authenticated: control-plane launch envelope is an HS256
  token with audience `cloud-agent-control-wrapper-launch`; "There is no
  unsigned-wrapper bypass" (`docs/control-plane.md` §2).

**Conclusion:** Cloud Agent is a hosted-execution product by construction: the
agent binary, workspace, credentials, and event transport are Kilo-managed
inside a Cloudflare sandbox (or Vercel / cloudflare-containers via the
`provider` enum). It is not a bring-your-own-runtime host.

### Q4. Can an external local runtime attach to an existing cloud-visible session?

Split by session type.

**(a) Remote Connections sessions (local CLI visible in Kilo web) — yes, the
wire protocol is generic enough in shape, but today only Kilo CLI implements
it.**

- **Verified fact:** A CLI connects its own authenticated WebSocket to
  `GET /api/user/cli` (`routes/api.ts:954`), authenticated by a Kilo **user
  JWT** (`kiloJwtAuthMiddleware`; `services/session-ingest/src/app.ts`). It then
  heartbeats `sessions: [{id,status,title,...}]` and an optional `instance`.
  The DO tracks a single owner per session id in `sessionOwners`
  (`UserConnectionDO.ts:335`, `handleHeartbeat` line 660, `findCliForSession`
  line 2431).
- **Verified fact:** The web side can target that owner with an allowlisted
  command set (`ALLOWED_VIEWER_COMMANDS`, `UserConnectionDO.ts:133`):
  `send_message`, `interrupt`, `drop_queued_message`, `question_reply`,
  `question_reject`, `permission_respond`, `suggestion_accept`,
  `suggestion_dismiss`, `list_models`, `list_commands`, `list_directories`,
  `list_agents`, `send_command`, `create_session`, `exit_cli`.
- **Verified fact:** Ownership can move between connections: `handleHeartbeat`
  detects `previousOwner !== connectionId` and fails pending commands for the
  old owner; `aggregateSessions()` de-duplicates by "current owner"
  (`UserConnectionDO.ts:711`, `:3106`).
- **Inference (what would verify/falsify):** Because auth is a user JWT and the
  protocol is defined in a plain Zod schema, a non-Kilo process that speaks
  this protocol and claims an existing `ses_...` id could appear as its owner
  and receive commands. There is no signature/proof that the connecting client
  is Kilo CLI. *To verify:* implement a minimal WebSocket client against
  `/api/user/cli` on a local dev stack and observe `sessions.list` and command
  delivery. This is exactly the Remote Connections reuse that Workstream A
  owns; Workstream B records that the same transport is user-level, not
  cloud-level.

**(b) Cloud Agent sessions (`cloud_agent_session_id` set) — no path found.**

- **Verified fact:** Web transport selection is a three-way switch in
  `apps/web/src/components/cloud-agent-next/CloudAgentProvider.tsx:147`:
  `cloud_agent_session_id` present → `type: 'cloud-agent'`; else present in
  `activeSessions.list` (live heartbeat) → `type: 'remote'`; else
  `type: 'read-only'`. `ResolvedSession` is exactly those three
  (`packages/cloud-agent-sdk/src/types.ts`).
- **Verified fact:** The `cloud-agent` transport streams from the
  `CloudAgentSession` DO over a ticket-authenticated `/stream`
  (`packages/cloud-agent-sdk/src/cloud-agent-connection.ts`) and sends via the
  Cloud tRPC API, which dispatches to the wrapper lease held by the DO.
- **Inference:** A local process cannot become the execution owner of an
  existing `cloud-agent` session: the DO dispatches to a sandbox wrapper fenced
  by `wrapperConnectionId`/`wrapperRunId`, and `/ingest` is internal-only and
  authenticated. *To falsify:* find any route that accepts an external
  `/ingest` or rebinds `wrapper_runtime_state` for a non-sandbox process — none
  appears in `CloudAgentSession.fetch` (`:1233`) or
  `wrapper-supervisor.ts`.

**Combined answer:** An external local runtime could attach to a
**cloud-visible Remote Connections session** by implementing the CLI wire
protocol (a Workstream A surface), but there is no mechanism to attach to a
**hosted Cloud Agent session**. The two are different products sharing the
`cli_sessions_v2` identity.

### Q5. Which transport, authentication, and reconnect mechanisms already exist?

**Remote Connections (session-ingest worker).**
- **Verified fact (transport):** WebSockets. Routes:
  - CLI: `GET /api/user/cli` (`routes/api.ts:954`)
  - Web viewer: `GET /api/user/web` (`routes/api.ts:971`) after
    `POST /api/user/web-ticket` (`routes/api.ts:990`)
  - DO-local paths `/cli` and `/web` (`UserConnectionDO.fetch`, `:439`).
- **Verified fact (auth):** Every `/api/*` route requires a Kilo user JWT
  (`app.ts`: `app.use('/api/*', kiloJwtAuthMiddleware)`). The web socket is
  additionally gated by a one-use opaque ticket minted into
  `ConnectionTicketDO` (`app.ts` route `/api/user/web-ticket`;
  `dos/connection-ticket-do.ts`). CLI heartbeats carry
  `protocolVersion`/`capabilities`; legacy clients are tolerated.
- **Verified fact (reconnect / liveness):** CLI heartbeat with an alarm-based
  timeout; stale sockets closed with code `4408 'heartbeat timeout'`
  (`UserConnectionDO.ts:593`); `cli.connected` / `cli.disconnected` system
  events broadcast (`:481`, `:1997`); reconnect with the same `connectionId`
  replaces the stale socket and suppresses duplicate `cli.connected`
  (`closeStaleSocket`, `:466`). Attention status is held for an absence window
  and cleared in `alarm()` rather than on socket close
  (`deferOwnedSessionAttentionReset`, `resetAttentionStatusOnCliDisconnect`).
- **Verified fact (dedupe):** Viewer commands accept an optional `mutationId`
  (≤128 chars) used as a durable correlation id; responses carry it back
  (`user-connection-protocol.ts` `WebOutboundMessageSchema`,
  `CLIInboundMessageSchema`). Pending commands have TTL and expiration
  (`expirePendingCommands`, `COMMAND_EXPIRED`).
- **Verified fact (ingest transport):** Session history ingestion is a
  separate HTTP POST (`/api/session/:sessionId/ingest`), versioned via `?v`.
  There is no requirement that the ingesting client be the heartbeat owner.

**Cloud Agent (cloud-agent-next worker).**
- **Verified fact:** `/stream` WebSocket requires a short-lived
  `validateStreamTicket` JWT with audience `STREAM_TICKET_AUDIENCE` and
  `Origin` allowlist (`CloudAgentSession.ts:1233`); `/ingest` is the internal
  wrapper socket; all other API surfaces require a Kilo API token (README
  "Authentication"). Reconnect supports `fromId=<eventId>` replay.

**Inference:** The reusable, documented-for-third-parties transport is the
Remote Connections WebSocket + ingest HTTP API. The Cloud Agent transport is
private execution infrastructure (OCVSAL) and not an integration surface.

### Q6. What would need to change to represent execution owned by Pi?

Two distinct strategies; they are not equivalent.

**Strategy 1 — Pi as a Remote Connections "CLI" (smallest Kilo change, no
Cloud change).**
- **Required:** Pi adapter implements the CLI wire protocol:
  connect `/api/user/cli` with a user JWT; heartbeat a `sessions[]` row for the
  shared `ses_...` id; implement `send_message`, `interrupt`,
  `question_reply`/`permission_respond`, etc.; and POST items in
  `SessionItemSchema` shape to `/api/session/:id/ingest`.
- **Kilo-side changes:** likely none strictly required for appearance and
  bidirectional messaging, but capability honesty is an issue:
  - `instance.kind` is a closed enum `cli | remote` — Pi would have to
    mislabel itself as `cli` or Kilo must widen the enum
    (`user-connection-protocol.ts` `instanceSchema`).
  - `created_on_platform` is free text with a `KNOWN_PLATFORMS` allowlist
    (`packages/app-shared/src/platforms.ts`); a new `pi`/`external` value is a
    one-file change but needs UI/analytics handling.
  - `Remote Connections` command results and events are Kilo-event-shaped
    (`kilocode` JSON); Pi's native events would need mapping, and unknown
    payload preservation is already the pattern (`z.looseObject` in
    `session-sync.ts`).
- **Verified fact:** the protocol already tolerates unknown/extra fields
  (`SessionItemSchema` uses `z.looseObject` for `session`/`message`/`part`
  data), so Pi-specific payloads can be carried without schema breaks.
- **Open question:** whether server-side admission
  (`canCreateCliSessionForUser`, `services/session-ingest/src/services/user-session-admission.ts`)
  or `cliSessionsV2` routers reject non-Kilo platform permutations in ways not
  visible without running the stack.

**Strategy 2 — Pi as a Cloud Agent execution backend (large Kilo change).**
- **Required at minimum:** a runtime abstraction in `CloudAgentSession` to
  accept a non-wrapper owner; a way to provision Pi into the sandbox image
  (today `@kilocode/cli` is installed in the Dockerfile); a Pi/`/ingest` event
  adapter; remapping of Cloud's Kilo-specific UI concepts
  (`mode`, `model`, `commands.available`, `preparation`) and error taxonomy
  (`CloudAgentFailureReason`). This contradicts control-plane principle 1
  ("Agent behavior belongs to Kilo") and the "wrapper upgrades are
  authenticated" model.
- **Recommendation:** do not pursue Strategy 2 in Phase 1.

**Capability boundary to state honestly:** even Strategy 1 gives history
display + bidirectional messaging + continuation for sessions **Pi owns** (Pi
holds its own runtime state). It does **not** give Pi the ability to continue a
Cloud-Agent-owned session's private Kilo state, nor active-turn migration. A
shared transcript is not a portable runtime state (Plan.md invariant 8).

### Q7. Can the web interface distinguish offline / disconnected / busy / locally owned runtimes?

**Partially, and not in the vocabulary this project needs.**

- **Verified fact (cloud vs local):** The UI distinguishes a Cloud Agent
  session from a local/remote CLI session by `cloud_agent_session_id` presence
  and by a sentinel `connectionId`: `CLOUD_AGENT_CONNECTION_ID = 'cloud-agent'`
  (`apps/web/src/lib/active-sessions-list.ts:96`). Transport selection is the
  three-way `remote | cloud-agent | read-only` switch described in Q4.
- **Verified fact (busy/idle):**
  - Remote: live heartbeat `status` wins; stored `question`/`permission`
    overlay is honored via `resolveActiveSessionStatus`
    (`active-sessions-list.ts:215`).
  - Cloud: `resolveCloudCandidateStatus` (`active-sessions-list.ts:238`) uses
    `cloud_agent_session_runs.terminal_at IS NULL` ("run open") to report
    `busy` when stored status is stale; attention statuses pass through.
- **Verified fact (disconnected/offline):** There is no persisted `offline`
  badge. `handleCliDisconnect` (`UserConnectionDO.ts:1900`) broadcasts
  `cli.disconnected`, deletes `sessionOwners`, and after the absence window
  resets attention. A disconnected CLI's sessions simply drop out of
  `aggregateSessions()` (live-socket scan), so they disappear from the
  "active sessions" list rather than showing as offline.
- **Verified fact (runtime kind):** `ConnectedInstance.kind` is only
  `cli | remote` (`apps/web/src/routers/active-sessions-router.ts`
  `connectedInstanceSchema`); there is no "locally owned" /
  "Pi-owned" / "external" label.
- **Verified fact (platform labels):** `created_on_platform` distinguishes
  origin (`cloud-agent`, `cloud-agent-web`, `cli`, `vscode`, `desktop`,
  `agent-manager`, `app-builder`, …) — `packages/app-shared/src/platforms.ts`.
  It is origin metadata, not live ownership.

**Inference:** Representing an external runtime faithfully would require at
least: (1) a new `instance.kind` or a capability flag for external ownership;
(2) a session status/ownership projection that expresses "owned by a runtime
that is not currently connected" without deleting the row; (3) new
`created_on_platform`/`KNOWN_PLATFORMS` values. Today the model conflates
"not live" with "not present."

## Cloud architecture map

```
                          Kilo web / mobile (app.kilo.ai)
                                    |
             +----------------------+----------------------+
             |                      |                      |
   Remote Connections          Cloud Agent            Read-only
   (local/remote CLI)          (hosted)               (history)
             |                      |                      |
   /api/user/web (ticket WS)   /stream (ticket WS)    /api/session/:id/export
   /api/sessions/active        tRPC (send/interrupt)   /api/session/:id/messages
             |                      |                      |
             v                      v                      |
   UserConnectionDO (per user)   CloudAgentSession DO (per session)   SessionIngestDO
     - CLI + web sockets           - message queue / states           (per user+session)
     - sessionOwners map           - SQLite events log                 - transcript items
     - heartbeat + alarm           - wrapper lease/generation          - source of truth
     - viewer command allowlist    - cloud.status projection           - export / messages
             ^                      |                                   ^
             |                      v                                   |
   /api/user/cli (JWT WS)     Sandbox (Cloudflare/Vercel/CF-containers)  |
     heartbeat sessions[]       - @kilocode/cli + wrapper               |
     instance{kind}             - /ingest WS to DO                      |
                                - workspace clone/branch/setup         |
                                                                       |
   POST /api/session/:id/ingest (history items) -----------------------+
   cli_sessions_v2 (Postgres): shared logical identity + metadata
   cloud_agent_sessions / cloud_agent_session_runs / worktrees: Cloud execution metadata
```

**Representation summary.**

| Concept | Representation | Evidence |
|---|---|---|
| Project | repo + git branch + worktree grouping; no project table | `cloud_agent_worktrees`, `cli_sessions_v2.git_url/git_branch` |
| Logical session | `cli_sessions_v2` (`ses_...`, `(session_id,kilo_user_id)`) | `schema.ts:6346` |
| Cloud session | `cloud_agent_sessions` / `cloud_agent_session_runs` | `schema.ts:6628,6780` |
| Message/part | ingested `SessionItemSchema` items in `SessionIngestDO` | `session-sync.ts`, `SessionIngestDO.ingest:482` |
| Session lifecycle event | `SessionEventPayload` (created/updated/status/deleted) | `user-connection-protocol.ts` |
| Runtime instance (remote) | heartbeat `instance{name,projectName,kind:'cli'\|'remote'}` | `user-connection-protocol.ts`, `getConnectedInstances:2186` |
| Runtime instance (Cloud) | wrapper lease + `wrapperGeneration`/`wrapperConnectionId` | `wrapper-runtime-state.ts` |
| Execution owner (remote) | in-memory `sessionOwners` keyed by session id | `UserConnectionDO.ts:335,660` |
| Execution owner (Cloud) | DO-held wrapper lease; fenced by generation | `wrapper-runtime-state.ts` |

## Hard coupling

1. **Cloud execution is Kilo-CLI-in-a-Kilo-sandbox.** `@kilocode/cli` is baked
   into the image (`Dockerfile:65`), launched with `KILO_PLATFORM=cloud-agent`,
   and the wrapper's `/ingest` socket is explicitly internal-only. **Verified.**
2. **Cloud execution ownership is a DO-held fenced lease, not a pluggable
   runtime.** `CloudAgentSession` allocates `wrapperConnectionId`/`wrapperRunId`
   and the supervisor manages sandbox process lifecycle
   (`wrapper-runtime-state.ts`, `session/wrapper-supervisor.ts`). **Verified.**
3. **Wrapper admission is authenticated with no unsigned bypass.** Launch
   envelope HS256 + allocation binding (`docs/control-plane.md` §2). **Verified.**
4. **Remote ownership is heartbeat/In-memory, single-owner per session, and
   last-writer-wins across connections.** `sessionOwners` is not durable DO
   storage and is rebuilt from heartbeats; `aggregateSessions` emits only the
   current owner. **Verified.** This is the mechanism that would have to be
   reused (and reasoned about for duplicate-side-effect safety) if Pi attached
   as a remote CLI.
5. **Web routing is a closed three-way enum.** `remote | cloud-agent |
   read-only`; no external/Pi branch. **Verified.**
6. **Instance kind is a closed enum `cli | remote`.** **Verified.**
7. **Transcript and session identity are shared; execution state is not.**
   `cli_sessions_v2` + `SessionIngestDO` are cross-interface, but Kilo CLI
   private runtime state (tool state, pending approvals, provider metadata) is
   not represented in the shared transcript. **Verified by schema** (no such
   fields); consistent with Plan.md invariant 8.

## Feasibility assessment

**What works for external runtimes today.**
- History access: `read-only` transport already displays any owned
  `ses_...` session from `SessionIngestDO` (`CloudAgentProvider.tsx:147`).
- Bidirectional messaging for an external runtime that implements the Remote
  Connections CLI wire protocol: the protocol, allowlist, dedupe, and reconnect
  semantics exist (`user-connection-protocol.ts`, `UserConnectionDO.ts`).
- Shared logical identity: a Pi-created `ses_...` row in `cli_sessions_v2` plus
  ingested transcript is visible across web/mobile.

**What needs changes.**
- Honest runtime labeling: widen `Instance.kind` (or add capability/ownership
  flag) and `KNOWN_PLATFORMS`.
- Offline ownership representation: stop equating "not live in heartbeat" with
  "not in the list" for sessions owned by a temporarily disconnected external
  runtime.
- (Only if Cloud-hosted Pi execution is required) a runtime abstraction in
  `CloudAgentSession` and a Pi image/adapter — large, contradicts current
  product principle; not recommended.

**What is unknown / unproven.**
- Whether server admission or tRPC routers reject a non-Kilo platform beyond
  schema checks (needs a running local stack).
- Whether Pi's native tool/permission semantics can be honestly expressed in
  `SessionItemSchema` + `ALLOWED_VIEWER_COMMANDS` without lossy mapping.
- Whether the last-writer-wins `sessionOwners` model can guarantee invariant 5
  (no duplicate side effects) during a Pi↔Kilo handoff; it currently fails
  pending commands on owner change but does not fence tool execution.

## Recommendation (Phase 0 → Phase 1 boundary)

**Recommendation:** Treat Cloud Agent as **out of scope for runtime execution
integration** and treat the **Remote Connections protocol as the single reuse
boundary** for making a Pi session visible and bidirectionally controllable in
Kilo. The smallest credible Phase 1 target is:

1. Pi publishes a `ses_...` logical session and ingests its transcript.
2. Pi attaches via `/api/user/cli` and heartbeats that session.
3. Web sends `send_message` and sees Pi execute it.
4. Reconnect without duplicate turns.
5. Disconnect Kilo; Pi keeps running locally.

Cloud-hosted execution owned by Pi is a **no-go** for Phase 1 (large change,
OCVSAL, contradicts "Agent behavior belongs to Kilo"). If the product requires
showing a Pi-owned session inside the Cloud Agent surface, that is a
**turn-boundary handoff** problem and should be scoped separately with the
ownership-fencing gaps above resolved first.

**Open questions carried forward.**
- Does `/api/user/cli` verify the client is a Kilo CLI beyond the user JWT?
  (Source suggests no; unverified without running the worker.)
- Can `sessionOwners` ownership transfer be made race-safe for Pi↔Kilo handoff
  without a durable lease (as Cloud uses)?
- Which `created_on_platform`/`kind` values would the mobile/web UI accept
  without changes?
- Does Cloud's read-only transport expose enough history for a Pi adapter to
  build coherent continuation, or is the Cloud Agent event log a separate
  history that would need reconciling?
