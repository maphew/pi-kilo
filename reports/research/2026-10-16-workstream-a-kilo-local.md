# Workstream A — Kilo local runtime and Remote Connections

- Bead: `pi-kilo-hyj.1`
- Date: 2026-10-16 (UTC)
- Status: complete — research done, read-only, no implementation
- Owner: ws-a

## Repos examined

| Repo | Commit / release | Retrieved (UTC) | License |
|---|---|---|---|
| https://github.com/Kilo-Org/kilocode | `1552877e82ceaecc79a9fd4be7859518745e6f56` (release v7.8.14, 2026-10-16) | 2026-10-16 (shallow clone, `--depth 1`) | MIT (`LICENSE`: "MIT License", © 2026 Kilo Code, © 2025 opencode) |
| https://github.com/Kilo-Org/kilo-pi-provider | `4c361a604349ebbaf29576ada481df27e853b2b4` (2026-10-01, "refactor: extract ambient Kilo UI controller (#37)") | 2026-10-16 (shallow clone, `--depth 1`) | Boost Software License 1.0 (`LICENSE`: "Boost Software License - Version 1.0 - August 17th, 2003") |

**Dependency warning (required before proposing any dependency):** neither repo's license blocks read-only research, but any vendored/copied code must carry its license. `kilo-pi-provider` is BSL-1.0 (not MIT) — check compatibility before reusing code from it. `kilocode` is MIT (with opencode lineage). No code copied in this phase.

Docs consulted (retrieved 2026-10-16, kilocode@`1552877e`, `packages/kilo-docs/pages/code-with-ai/platforms/cli.md` lines ~95–170 and ~626–699; `cloud-agent.md` lines 8, 186–228): cited inline as **Source claim** where not verified in source.

All file/line references below are against kilocode@`1552877e` unless stated otherwise. Line numbers verified for: `remote-protocol.ts` (146 lines), `remote-sender.ts` (1592), `kilo-sessions.ts` (1917), `attached-state.ts` (380), `remote-ws.ts` (570), `session/session.ts` (1251), `session/prompt.ts` (2679), `kilocode/session-resume/import.ts` (632), `kilocode/server/import-cloud-session-in-process.ts` (217), `cli/cmd/remote.ts` (60), `cli/cmd/attach.ts` (187). Other cited files were located and spot-read (grep + context), not line-verified end to end.

## Questions (from Plan.md)

- [x] How does Kilo CLI create, identify, persist, and resume a session?
- [x] How does Remote Connections attach a web interface to a running local session?
- [x] What messages, events, permissions, and tool activity can cross that boundary?
- [x] Is the transport or session API reusable by an external runtime?
- [x] What assumptions couple the interface to Kilo's own runtime?
- [x] Can an external runtime be registered without impersonating a Kilo agent?
- [x] What is the smallest Kilo-side change enabling a genuine external session?

## Findings

### Q1. How does Kilo CLI create, identify, persist, and resume a session?

**Verified fact (kilocode@`1552877e`, `packages/opencode/src/session/session.ts`):**
Session service interface (`Interface`, ~lines 514–569) defines `create` (optional `parentID`, `title`, `agent`, `model`, `metadata`, `permission`, `platform`, `workspaceID`, `sandboxInheritanceToken`), `fork({sessionID, messageID?})`, `touch`, `get(id)`, `setTitle`, `setArchived`, `setMetadata`, `setAgentModel`, `setPermission`, `setRevert`/`clearRevert`, `setSummary`, `setShare`, `setWorkspace`, `diff`, `messages`, `children`, `remove`, plus message/part CRUD. Implementation is an Effect service backed by SQLite via `Database.Service` (`session.ts` ~lines 580–600).

**Verified fact (same file, `createNext` ~lines 602–660):** create generates `id: SessionID.descending(input.id)`, a slug, `version: InstallationVersion`, `projectID` from instance context, `directory`, timestamps; calls `KiloSession.register({id, parentID, platform})`; publishes `Session.Event.Created`. The `SessionID` brand is `SessionV2.ID` (`session/schema.ts` line 7). Exact `ses_`-prefix format not verified in-source (identifier helper lives in `@opencode-ai/core`, not read) — treat prefix shape as **Open question** if an adapter must mint IDs.

**Verified fact (persist location):** sessions persist in a per-host store rooted at `Global.Path.data + "/storage"` (`storage/storage.ts` ~lines 234–243, `make()` layer boot with migrations) — i.e. a local SQLite-backed store on the CLI host, not per-project files. `Session.Info` schema (`session.ts` ~lines 236–271) carries `id, slug, projectID, workspaceID?, directory, path?, parentID?, summary?, cost?, tokens?, share?, title, agent?, model?, version, metadata?, time, permission?, revert?`.

**Verified fact (resume = continuation within the same runtime):** resuming is loading the persisted row and prompting again. `kilo attach <url>` (`cli/cmd/attach.ts`) supports `--continue/-c` (continue last session), `--session/-s <id>`, `--fork`, `--cloud-fork` (fetch from cloud then continue locally), `--dir`. Execution entry is `SessionPrompt.prompt(input)` (`session/prompt.ts` line 1444, `Effect.fn("SessionPrompt.prompt")`), which `get`s the session, recovers dangling/failed assistant turns (`recoverDanglingAssistant`, `recoverProviderFinishError`, `recoverFailedAssistant`), creates the user message, and runs the agent loop. Resume is therefore cheap *because the same process owns the DB, the prompt loop, permissions, and provider auth* — there is no portable "session handle" detached from the runtime.

**Source claim (docs, `cli.md` ~lines 162–170, retrieved 2026-10-16):** `/resume-claude [uuid]` / `/resume-codex [uuid]` import Claude Code / Codex transcripts, must run in an empty session, keep original order, end with an import notice, skip unrepresentable content. **Verified fact (corroborating, `kilocode/session-resume/import.ts` lines 255–330, 849):** the importer discovers external transcripts, tracks already-migrated sources by `format:id` marker in session metadata, and stamps `IMPORT_NOTICE` ("This conversation was imported from an external session. Some tool outputs and context may not be fully represented."). This is the **IMPORT (transcript copy)** pattern — one-way, lossy by design, no live link. Never conflate with LIVE integration.

Distinction ledger for Q1: history access (read rows via `messages`/`get`) ✔ exists; continuation (same runtime re-prompts) ✔ exists; turn-boundary handoff to another runtime ✘ no mechanism; active-turn migration ✘ out of scope, no mechanism found.

### Q2. How does Remote Connections attach a web interface to a running local session?

**Verified fact (transport shape):** the CLI opens an **outbound** WebSocket to the ingest relay: `KILO_SESSION_INGEST_URL` (default `https://ingest.kilosessions.ai`, scheme-swapped to `wss://`) at path `/api/user/cli?token=…&connectionId=…` (`kilo-sessions.ts` `enableRemote()`, ~lines 979–1010; `remote-ws.ts` ~lines 422–441, token redacted in logs as `token=***`). Auth is the user's Kilo credential (`kilocodeToken()`, ~lines 201–215: stored `kilo` auth of type api/oauth/wellknown, else `KILO_API_KEY` env), pre-validated via `GET <KILO_API_BASE>/api/user` with `Authorization: Bearer` (`authValid`, ~lines 177–199, 15-min cache). **There is no inbound listening socket on the CLI** — the web UI never connects directly to the local machine; both sides connect to Kilo-operated cloud infrastructure (relay + ingest service). Docs corroborate: "Requires Kilo Gateway connection", "Your computer handles the compute; the cloud gives you a window" (`cli.md` ~line 664; `cloud-agent.md` ~lines 188–205).

**Verified fact (wire protocol, `kilo-sessions/remote-protocol.ts`, full file 146 lines):** zod schemas define CLI→relay `Outbound = Heartbeat | Event | Response` and relay→CLI `Inbound = Subscribe | Unsubscribe | Command | System | HeartbeatAck`. Heartbeat carries `sessions: SessionInfo[]` (`id, status, scheduledAt?, title, parentSessionId?, gitUrl?, gitBranch?, platform?, prLink?`), optional `instance: InstanceAdvertisement` (spawn-capable host row: `name, projectName, version?, kind: cli|remote, startedAt?, gitBranch?`), and `capabilities` (`attachments?, sessionClone?, sessionCloneAtMessage?`).

**Verified fact (enable path):** `kilo remote` (`cli/cmd/remote.ts`, full file 60 lines) bootstraps the instance, sets the instance advertisement, calls `KiloSessions.enableRemote()`, and parks until SIGTERM/SIGINT/SIGHUP. Auto-enable also occurs when config `remote_control` is set (`kilo-sessions.ts` ~lines 904–910). Heartbeats go out on a ~10s timer plus out-of-band on advertisement/reconnect (`conn.heartbeat()`). Relay→CLI commands dispatch in `RemoteSender` (`remote-sender.ts`, 1592 lines; 16 distinct `msg.command` values — see Q3).

**Verified fact (attach semantics — presence + ownership, `attached-state.ts` 380 lines):** attachment is a two-set state machine: `setPresence` (presence-service snapshot, authoritative) and `announce` (per-`create_session` awaitable). Heartbeat "fences" prove the relay observed the union (attach) or its removal (detach, "negative-containment fence"). `exit_cli` verifies `AttachedState.has(id)` ownership before cancel+detach, else responds `"session not owned by this CLI"` (`remote-sender.ts` ~lines 909–1000). Sessions are executed **in-process** (no spawned child per session; per-directory `InstanceRef` isolation) — `attachSession/detachSession/hasSession/ownedCount/cancelPrompt/importFromCloud` seams wired from `KiloSessions` into `RemoteSender.create` (`kilo-sessions.ts` ~lines 1185–1235).

**Verified fact (session bootstrap gate):** each hosted session is `POST`ed to `<ingest>/api/session` (`bootstrap()`, ~lines 1447–1480); only an explicit relay refusal (4xx → `RelayRefusal`, ~lines 124–162) blocks hosting — skipped/transient bootstrap resolves as success and the session stays local-only. `ensureSharedSession` + `attachedState.announce({requireShare})` sequence this for `create_session` (~lines 1302–1360).

Net: "attach" = (1) CLI dials out with user credentials, (2) advertises session presence via heartbeat, (3) relay routes web-UI commands down the same socket, (4) CLI executes everything locally in-process and streams events back up. No peer-to-peer or local-server attach exists in this path.

### Q3. What messages, events, permissions, and tool activity can cross that boundary?

**Verified fact (inbound commands, `remote-sender.ts`):** exactly 16 commands: `create_session`, `drop_queued_message`, `exit_cli`, `interrupt`, `list_agents`, `list_commands`, `list_directories`, `list_models`, `permission_respond`, `question_reject`, `question_reply`, `send_command`, `send_message`, `set_pr_link`, `suggestion_accept`, `suggestion_dismiss` (grep-verified, lines 750–1446+). Salient behaviors:
- `send_message` validates against `SessionPrompt.PromptInput` and runs the **real local prompt loop** (`prompt(input)`, ~lines 1280–1324) — full execution, not a preview.
- `create_session` creates (optionally cloning a cloud session **in-process** via `importFromCloud`, ~lines 1000–1198; clone failures never fall back to fresh-create) and attaches with the share-gate.
- `send_command` allowlists executables (`RemoteCommand.executable`, ~lines 848–908); `interrupt` cancels the active prompt; `exit_cli` = detach-this-session (+ maybe close CLI).
- `permission_respond` → `permission.reply({requestID…})` (~lines 1425–1445); `question_reply/reject`, `suggestion_accept/dismiss` similarly route to the live local services. `set_pr_link` pins a PR link to the owning session only (fail-closed without a session id).

**Verified fact (outbound events):** (a) ingest queue item types (`ingest-queue.ts` ~lines 28–64): `message, part, session_diff, model, session_status (idle|busy|question|permission|retry|scheduled), kilo_meta, session, session_open, session_close, session_pr_link`; (b) Bus watchers synced per session (`kilo-sessions.ts` ~lines 675–863): `Session.Created/Updated/Deleted/Diff/TurnOpen/TurnClose`, `MessageV2.Updated`, `PartUpdated`, `SessionStatus.Status`, `Question.Asked/Replied/Rejected`, `Permission.Asked/Replied`, PR-link watchers; (c) live relay events forwarded only to subscribed sessions (`remote-sender.ts forwarder`, ~lines 660–690, with `extractSessionId` handling per-event id locations) plus `replay()` of pending suggestions/questions/permissions and queue snapshot on subscribe (~lines 578–656).

**Verified fact (what does NOT cross):** provider credentials (only a session-scoped `ingestPath` + bearer token on the wire; LLM keys stay host-side), raw tool binaries (only `send_command` through an allowlist), and host filesystem except via agent tool execution and attachment materialization (`RemoteAttachments` fetchable-URL → data-URL/scratch-path conversion before `prompt()`, ~lines 1300–1320). Tool *activity* crosses as message parts/diffs/status events; tool *authorization decisions* cross as `permission.asked` → `permission_respond`. The executing runtime keeps the permission service — consistent with invariant 9 (no permission bypass by architecture, though the account-trust warning below applies).

**Source claim (docs, `cloud-agent.md` ~lines 192–201):** "Messages and responses sync in real-time; agent questions appear in both places; permission requests route to your active connection; full editing capabilities work remotely; renames sync both directions; file attachments sync with mobile." Matches source behavior observed above; treat the "real-time" qualifier as vendor phrasing (**Source claim**), the mechanism list as corroborated.

Capability mapping: history access ✔ (subscribe + replay + ingest backlog), bidirectional messaging ✔ (`send_message` + live events), continuation ✔ (same CLI owns the loop), turn-boundary handoff to a *different* runtime ✘ (no wire concept of execution owner beyond `attachedState` presence), active-turn migration ✘ (explicitly out of scope; `interrupt`+`send_message` is stop-and-restart, not state migration).

### Q4. Is the transport or session API reusable by an external runtime?

Two transports exist; reusability differs sharply:

**(a) Relay WebSocket protocol (`RemoteProtocol` + `RemoteSender` + `RemoteWS` + ingest HTTP). Observed behavior: NO for third parties as-is.** **Verified facts:** the wire format is zod-defined and machine-readable, but (i) the CLI dials a Kilo-operated relay (`ingest.kilosessions.ai`) authenticated with the *user's Kilo account token* — there is no documented external-client registration, no per-runtime identity (only user identity + `InstanceAdvertisement`), and the relay side is closed source (not in the `kilocode` repo — no `UserConnectionDO`/ingest service implementation found; `grep` for `UserConnectionDO` hits only the OpenAPI description string in `kilocode/server/httpapi/groups/remote.ts`); (ii) `send_message` feeds `SessionPrompt.prompt()` directly — the protocol has no "execute elsewhere and report back" mode, so an external runtime cannot sit behind this socket without reimplementing the CLI's session store, prompt loop, permission/question services, and heartbeat presence; (iii) `create_session.cloneFromKiloSessionId` is IMPORT (transcript copy via `import-cloud-session-in-process.ts`), not delegation. **Inference:** the relay protocol is reusable only by a Kilo-blessed client impersonating a CLI (same token, same heartbeat contract). That is impersonation, not registration — violates the "without impersonating a Kilo agent" requirement. Falsify/verify by: asking Kilo for relay API docs or finding a published relay spec (Workstream B/D should confirm from the cloud side).

**(b) Local HTTP API + SSE event stream (`server/routes/instance/httpapi/groups/`: `session.ts`, `event.ts`, `permission.ts`, `question.ts`, …). Observed behavior: PARTIALLY — best local reuse candidate.** **Verified facts:** the running CLI serves an authenticated (Basic, `KILO_SERVER_PASSWORD`/`KILO_SERVER_USERNAME`, `server/auth.ts`) HTTP API consumed today by `kilo attach <url>` (TUI/mini) — i.e. an existing local multi-client surface. `POST /session/:sessionID/message` (`session.prompt`) and `POST …/prompt_async` run the real prompt loop; `permission.reply`, `question.reply/reject`, session create/get/list/message-history endpoints exist (`groups/session.ts` ~lines 126–127, 242, 348–420; `permission.ts`, `question.ts` identifiers); `GET /event` is SSE (`groups/event.ts`, `contentType: "text/event-stream"`). **Inference:** a same-host adapter (Pi sidecar) could plausibly observe (`GET event`, message history) and inject (`prompt_async`, `permission.reply`) over this API with only a password — no relay, no account token, works offline. What it canNOT do: register an externally-owned session (every endpoint executes in Kilo's loop; responses come from Kilo's agents/models), or receive structured tool-activity callbacks beyond the event stream. Verify by: running `kilo serve` + `attach` locally and exercising the endpoints from a script (Workstream C/F experiment; I did not execute anything — read-only phase).

**kilo-pi-provider role (kilo-pi-provider@`4c361a6`, 338-line `src/index.ts`):** **Verified fact:** it is a Pi *model provider* extension (Kilo Gateway models inside Pi: auth, model catalog, thinking levels, footer/credits UI; session hooks used only for prefetch/refresh — `session_start`/`session_shutdown` listeners, `sessionManager.getEntries/getSessionName` for display). It contains no session-sync, relay, or runtime-registration code (only `session`-mentioning files are `index/models/footer` for UI/prefetch). It is prior art for Pi-side *model* integration, not for *session* integration. Do not cite it as a session bridge.

### Q5. What assumptions couple the interface to Kilo's own runtime?

**Verified facts (each a concrete coupling):**
1. **Execution = local prompt loop.** `send_message` → `SessionPrompt.prompt()` (`remote-sender.ts` ~line 1320; `prompt.ts` line 1444) with Kilo-specific recovery (`recoverDanglingAssistant`, plan-followup policy), tool-permission merging, subagent steering, goal loops. A foreign runtime cannot "take" this path; it can only ask Kilo to run.
2. **Identity = user account, not runtime.** Relay auth is the user's Kilo token; heartbeat advertises sessions + host, never a runtime type/owner field consumable for routing to non-Kilo executors. `platform` is client-OS telemetry, not execution ownership.
3. **Storage = Kilo's SQLite schema.** Session/message/part rows, metadata markers, `session_diff` keys, workspace refs — all Kilo-shaped (`session.ts`, `import-cloud-session-in-process.ts` ~lines 62–175 decode-then-insert with `Schema.decodeUnknownSync(Session.Info)` validation; non-conforming rows → `BadRequest`). An external session must be *converted*, losing anything Kilo cannot represent (cf. `IMPORT_NOTICE`).
4. **Permissions/questions/suggestions are Kilo services.** The wire carries replies into `permission.reply`/`question.reply`/`Suggestion.accept` — the *asking* side (tool policy, `sandboxEscalation`/`skillShell` metadata in `permission/index.ts` ~lines 148–149) is Kilo code. An external runtime's own approval model has no representation.
5. **Presence = heartbeat union + in-process attach.** `AttachedState` assumes the announcer also executes (attach ↔ willingness to run `prompt()`). There is no "present but externally executed" state.
6. **Trust = account access.** Docs warn: "Anyone with access to your Kilo account can send messages to your computer when remote mode is enabled" (`cloud-agent.md` ~line 214). Any extension point must not widen this to unauthenticated local listeners (invariant 9) — bind to localhost + auth, never 0.0.0.0 without credentials.

### Q6. Can an external runtime be registered without impersonating a Kilo agent?

**Finding: No — not today, on either transport. (Inference from verified facts above; falsifiable.)**
- Relay path: no registration endpoint, no runtime identity field, closed relay; the only way on is a valid user token + CLI-shaped heartbeat = impersonating a Kilo CLI instance.
- Local HTTP path: no registration endpoint either; `attach` clients are *view-controllers* of Kilo-owned sessions, and every prompt endpoint executes in Kilo's loop. A Pi process can drive Kilo (making Pi a remote control for a Kilo agent — wrong direction for our goal) but cannot register itself as the executor of a Kilo-visible session.
- Import paths (`/resume-claude`, `/resume-codex`, `cloneFromKiloSessionId`): IMPORT only — they mint a *new Kilo session* containing copied history, with no live link back. An "import Pi transcript into Kilo" would satisfy *history access* while failing *real continuation* (invariant 3): a message sent from Kilo would execute in Kilo, not reach Pi.
- What would falsify: discovery of a registration/claim endpoint in the relay API, a `runtime`/`executor` field in `SessionInfo`/`InstanceAdvertisement`, or plugin docs allowing executor registration (none found; `grep -ri "registerRuntime|externalRuntime|thirdParty"` over `packages/opencode/src` returned only unrelated plugin-tip and session-import hits).

### Q7. Smallest Kilo-side change enabling a genuine external session?

**Recommendation (from available evidence; needs Workstream B/E validation):**

Recommended extension point: **an "externally owned session" presence + message-forwarding seam in the relay path**, modeled exactly on the existing `AttachedState` + `send_message` machinery:

1. Add optional `executor: { runtime: string; owner: string }` (or `externalSessionId`) to `RemoteProtocol.SessionInfo` (wire-compatible: optional, cf. `platform`/`prLink` precedent) — lets a CLI heartbeat advertise a session it *hosts for presence* but does *not execute*.
2. Add one relay→CLI command, e.g. `forward_message` (or reuse `send_message` with an `external: true` flag): instead of entering `SessionPrompt.prompt()`, the CLI appends the inbound user message to local history (so Kilo-side history stays complete) and forwards it — via localhost HTTP/SSE to the registered external runtime — then streams the external runtime's events back through the existing `Event`/`message`/`part` ingest path. `interrupt`/`permission_respond`/`question_reply` already have reply-shaped handlers; they need an "owned-externally → forward, don't execute locally" branch.
3. Keep execution ownership explicit: `AttachedState` gains a third marker (presence ∪ pending ∪ external) so the heartbeat, the `exit_cli` owns-check, and status derivation (`idle|busy|question|permission…`) treat externally-owned sessions distinctly — busy-ness reported by the external runtime, never inferred from the local loop.

Why this is smallest: it reuses heartbeat presence, the 16-command dispatch, the ingest/event fan-out, and the subscribe/replay UX with zero web-UI changes (an externally-owned session looks like a session whose turns happen to arrive as events). It satisfies invariants 1–5 (shared logical id = Kilo session id; shared history = local append + event stream; real continuation = forward-to-Pi; explicit ownership = `executor` field; no duplicate side effects = forward-or-execute, never both, enforced at the `send_message` branch). Local-first (7) holds because the CLI caches history and marks the session offline/unreachable when the sidecar is absent. Security (9): the new localhost listener binds 127.0.0.1 + token (reuse `ServerAuth` scheme), and the relay-facing change adds no new trust (same user token).

Cheaper-but-insufficient alternative (do NOT mistake for the goal): transcript import (`/resume-*` pattern extended to Pi logs). It gives history access only and fails invariants 3–4. If Phase 1 needs a demo before Kilo changes land, do import *labeled as such*.

Out-of-scope guard: active-turn migration stays out — the seam above is turn-boundary handoff + bidirectional messaging, nothing more.

**Open question for B/E:** whether the relay/Cloud backend can carry the `executor` field and route `forward_message` without backend changes (if the relay passes commands opaquely by name, only the CLI changes; if it allowlists commands, the relay needs a one-line addition — Workstream B must determine this from the cloud side).

## Code-path map

Session lifecycle (kilocode@`1552877e`, `packages/opencode/src/`):

| Step | File | Symbol / route | Notes |
|---|---|---|---|
| Create | `session/session.ts` ~602–660 | `createNext` (via `Session.create`) | mints `SessionID.descending`, slug, project/directory binding; publishes `Session.Event.Created` |
| Identify | `session/schema.ts:7` → `SessionV2.ID`; `session/session.ts` ~236–271 | `SessionID`, `Session.Info` | id + projectID + directory + parentID; exact `ses_` shape not verified (lives in `@opencode-ai/core`) |
| Persist | `storage/storage.ts` ~205–260; `session/session.ts` `get/list/messages/children` | `Storage.make()` → `<Global.Path.data>/storage` SQLite; `SessionTable/MessageTable/PartTable` | per-host store; `listGlobal` for cross-project (`KiloSession.listGlobal`) |
| Resume (local) | `cli/cmd/attach.ts` (`--continue/--session/--fork/--cloud-fork`); `session/prompt.ts:1444` | `SessionPrompt.prompt()` + `recoverDanglingAssistant` et al. | same-process continuation; no portable handle |
| Import (NOT live) | `kilocode/session-resume/import.ts` (632 lines); `kilocode/server/import-cloud-session-in-process.ts` (217) | `SessionResumeImport.migrated/discover`, `importSessionWithoutRestore` + `finalizeSessionImport` | transcript copy + `IMPORT_NOTICE`; clone path of `create_session` |
| Remote enable | `cli/cmd/remote.ts` (60); `kilo-sessions/kilo-sessions.ts` `enableRemote()` ~979–1235 | `setInstanceAdvertisement`, `RemoteWS.connect`, heartbeat `getSessions` | outbound WSS to `ingest.kilosessions.ai/api/user/cli?token=…`; `KILO_REMOTE=1` / `remote_control` auto-enable |
| Attach state | `kilo-sessions/attached-state.ts` (380) | `AttachedState.setPresence/announce/detach` + heartbeat fences | presence ∪ pending; owns-check in `exit_cli` |
| Command dispatch | `kilo-sessions/remote-sender.ts` (1592), 16 commands ~750–1520 | `RemoteSender.create({attachSession, detachSession, hasSession, ownedCount, cancelPrompt, importFromCloud})` | `send_message`→`prompt()`; replies→live services; all in-process, per-directory InstanceRef |
| Event fan-out | `kilo-sessions.ts` watchers ~675–863; `remote-sender.ts forwarder` ~660–690 + `replay()` ~578–656 | `ingest.sync` item types (`ingest-queue.ts` ~28–64); `Event{sessionId,event,data}` | subscribe-scoped; pending Q/P/suggestions replayed on subscribe |
| Bootstrap/share gate | `kilo-sessions.ts` `bootstrap()` ~1447–1480, `trackBootstrap`, `ensureSharedSession` ~1302–1360 | `POST {ingest}/api/session`; `RelayRefusal` (~124–162) | only explicit 4xx refusal blocks hosting |
| Local multi-client API | `server/routes/instance/httpapi/groups/{session,event,permission,question}.ts`; `server/auth.ts` | `POST /session/:id/message`, `/prompt_async`, `GET /event` (SSE), `permission.reply`, Basic auth | used by `kilo attach <url>` today; best external-runtime reuse candidate |
| Local status API | `kilocode/server/httpapi/groups/remote.ts` (76) | `POST /remote/{enable,disable}`, `GET /remote/status` → `{enabled, connected}` | control-plane only, no session payload |

## Existing integration contract

What the boundary supports today (`RemoteProtocol` + 16 commands + ingest types, all cited above):
- Presence advertisement (heartbeat with sessions + instance + capabilities), subscribe/unsubscribe, live event relay (messages, parts, diffs, statuses, Q/P/suggestions, queue), and full remote *operation of Kilo-owned sessions* (prompt, interrupt, create/fork/clone-import, approvals, PR links, model/agent listing, command execution via allowlist, detach/exit).
- Authentication = Kilo user account on both ends; transport = Kilo-operated relay; execution = always the advertising CLI process.
- Explicitly absent: runtime registration/identity, external execution ownership, opaque message forwarding, offline/localhost delegation, and any third-party relay client contract. Session import (Claude/Codex/cloud-clone) is transcript copy with a loss notice, not a live bridge.

## Recommendation

See Q7. In one line: **extend the relay contract with an optional `executor` advertisement + a `forward_message` branch beside `send_message`, backed by a localhost sidecar API on the CLI — reusing heartbeat presence, command dispatch, and event ingest — so a Kilo-visible session can be genuinely executed by Pi while Kilo keeps shared history and explicit ownership.** Validate relay opacity with Workstream B before costing; prototype the localhost sidecar against the existing `prompt_async` + SSE surface (Workstream C) without waiting for Kilo changes.

## Open questions

1. (→ B) Does the relay pass unknown command names opaquely, or allowlist them? Determines whether `forward_message` needs a backend change.
2. (→ B) Can the Cloud backend store/display an `executor` (or equivalent) session attribute without schema changes?
3. (→ C/F) Does `POST /session/:id/prompt_async` + `GET /event` suffice for a faithful Pi-side observer/injector experiment, and what auth scoping (`KILO_SERVER_PASSWORD`) is acceptable for a sidecar?
4. ID minting: exact `SessionID` (`SessionV2.ID`) format/constraints — read `@opencode-ai/core` identifier helper before any adapter mints or maps IDs.
5. `KILO_API_BASE` value and the relay/ingest OpenAPI surface (if any is published) — needed to confirm no public third-party contract already exists.
6. (→ D) ACP-fit: does ACP's session/request model cover the `AttachedState` presence + heartbeat-fence semantics, or must that stay Kilo-side? (Flagged, not investigated — D owns it.)
7. Freshness: kilocode moves fast (HEAD was a same-day release); re-verify line refs at handoff if the repo has moved.
