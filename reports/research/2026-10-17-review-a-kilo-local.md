# Review A — Kilo local runtime and Remote Connections
- Review bead: `pi-kilo-hyj.9`; reviewer date (UTC): 2026-10-17
- Artifact reviewed: `reports/research/2026-10-16-workstream-a-kilo-local.md` @ `b31f9a157fa219071f3242e513fafac713df5ff5` (`git log -1` on path; working-tree blob `ab64925f…`; tree clean except this new review file)
- Repos checked (pre-clones, **no drift** — both match the artifact's pinned SHAs exactly):
  - `/tmp/pi-kilo-workers/src/kilocode` HEAD `1552877e82ceaecc79a9fd4be7859518745e6f56` — OK (`release: v7.8.14`, package.json `7.8.14`)
  - `/tmp/pi-kilo-workers/src/kilo-pi-provider` HEAD `4c361a604349ebbaf29576ada481df27e853b2b4` — OK (`refactor: extract ambient Kilo UI controller (#37)`, 2026-10-01)

## Verdict: PASS WITH MINORS
Substance holds at the pinned SHAs: outbound-relay + in-process execution, `send_message`→local prompt loop with no external-executor mode, import = transcript copy, and the local HTTP+SSE surface are all confirmed in source. Synthesis may rely on those findings and on the Q7 shape (executor advertisement + forward branch beside `send_message`), but must not treat A's own open questions as still-open — Workstream B already answers the relay-allowlist one — and must fold in F's dedupe/ownership failures and the missed `SessionDrain` primitive before costing Phase 1.

## Citation spot-checks
| Claim | Artifact section | Status | Evidence (2026-10-17, kilocode@`1552877e`) |
|---|---|---|---|
| kilocode MIT; kilo-pi-provider Boost 1.0 (not MIT) | header | confirmed | `LICENSE` verbatim both repos |
| `remote-protocol.ts` 146 lines; `Outbound=Heartbeat\|Event\|Response`, `Inbound=Subscribe\|Unsubscribe\|Command\|System\|HeartbeatAck`; `SessionInfo` fields; `InstanceAdvertisement.kind: cli\|remote` | Q2/Q3 | confirmed | `remote-protocol.ts:6-56,81,120-141` |
| outbound wss relay `/api/user/cli?token&connectionId`; no inbound socket; `enableRemote()` URL + scheme swap | Q2 | confirmed | `kilo-sessions.ts:1001,979`; `remote-ws.ts:437` |
| `send_message` validates `SessionPrompt.PromptInput` then runs `prompt()`; no external-executor branch | Q3/Q4 | confirmed | `remote-sender.ts:1280-1319`; `session/prompt.ts:1444` |
| exactly 16 commands incl. `permission_respond`→`permission.reply`, `send_command` allowlist | Q3 | confirmed | 16 distinct literals; `remote-sender.ts:1362-1437,:848`; `remote-command.ts:122` |
| `exit_cli` owns-check → "session not owned by this CLI" | Q2 | confirmed | `remote-sender.ts:955-956` |
| IMPORT_NOTICE line 849 in `session-resume/import.ts` | Q1 | **wrong (file)** | `import.ts` is 632 lines; notice is `session-resume/index.ts:849`. Substance confirmed via `import.ts:254-300` + docs |
| cloud-clone decode→insert, `Schema.decodeUnknownSync(Session.Info)`, non-conforming→`BadRequest` | Q5 | confirmed | `import-cloud-session-in-process.ts:105-106,175,212` |
| local HTTP API `prompt`/`prompt_async`, `GET /event` `text/event-stream`, Basic auth | Q4 | confirmed | `groups/session.ts:126-127,348-370`; `groups/event.ts:16`; `server/auth.ts:18-41` |
| `kilo remote` (60 lines) advertisement→`enableRemote()`→signal park; `remote_control`/`KILO_REMOTE=1` auto-enable | Q2/Q-map | confirmed | `cli/cmd/remote.ts:1-60`; `kilo-sessions.ts:320,905` |
| no `registerRuntime`/`externalRuntime`; `UserConnectionDO` not in repo | Q6 | confirmed* | only OpenAPI strings + a `send-file.ts` comment (*artifact omits that second hit) |
| kilo-pi-provider = 338-line model provider, no session sync/relay | Q4 | confirmed | `src/index.ts` (338); `registerProvider:240`, `session_start:253`; no WS/relay |
| bus watchers 675-863 lists **PR-link watchers** | Q3 | drifted | 14 `watch()` calls there; PR-link sync is poller-based (`pr-link-poller.ts`), no watcher in range |
| ingest item types at `ingest-queue.ts ~28-64` | Q3 | drifted-line | `kilo_meta` is :15; union spans :15-64 |
| docs: `/resume-claude` empty-session rule; gateway requirement; account-trust warning | Q1/Q5 | confirmed | `cli.md:162-170,665`; `cloud-agent.md:191,214` |

## Label-hygiene findings
- Q4(a)/Q4(b) are headed **"Observed behavior"** but nothing was run (A states "I did not execute anything"). Per `Readme.md`, *Observed behavior* = demonstrated experimentally; these are code-sourced assessments / Inference. Harmless to the conclusion but inconsistent with A's own standard.
- Otherwise clean: material uncertainties are labelled Inference with explicit falsifiers (Q4a, Q4b, Q6), and Q7 is correctly Recommendation.

## Distinction violations
None material. A repeatedly separates history access / bidirectional messaging / continuation / turn-boundary handoff / active-turn migration, and explicitly marks import as one-way and active-turn migration out of scope. Q6 correctly notes import fails invariant 3.

## Cross-consistency notes
- **Agrees with F** (`2026-10-16-workstream-f-falsification.md` §F1-F4/F8): same relay shape, same closed `kind` enum, same in-process execution. F's cross-check calls A a "stub ... no findings" because it read blob `47676d2f` (the pre-`b31f9a1` stub). **That cross-check is stale** — synthesis must not use it to characterize the landed A.
- **Divergence with F (gap, not contradiction):** A's Q7 claims invariant 5 via "forward-or-execute, never both", but never mentions `mutationId`, while F3 and B/Q5 show chat `send_message` is **not** relay-deduped (dedupe is gated on an optional `mutationId`). A's ownership claim is therefore under-specified for retries.
- **A's open Q1 is already answered by B** (`2026-10-16-workstream-b-kilo-cloud.md` Q4): the relay has `ALLOWED_VIEWER_COMMANDS` (`UserConnectionDO.ts:133`). So a new `forward_message` command is **not** CLI-only — it needs a backend allowlist change. A's "smallest change" is understated vs B's Strategy 1.
- **Divergence with B:** B finds Pi can speak the existing CLI protocol with "likely no Kilo changes" (impersonating `kind: cli`); A rejects that as impersonation and proposes a contract extension. Both are documented; synthesis must pick and weigh honesty vs. size.
- **Agrees with E's convergence** on an "external owner kind"; A locates the seam in the relay protocol, E in the local `session.prompt` routing. A missed E's anchor `kilocode/session/drain.ts` + `session.drained{token}` (below).

## Recommendation assessment
Entailed **as a direction, not as a cost estimate**. Reusing heartbeat presence + command dispatch + ingest fan-out follows from the verified wire/protocol facts, and the needed new concepts (`executor`, `forward` branch) are concrete file/symbol-level extension points, not hand-waving. But it leaps over three verified blockers synthesis must add: (1) relay command allowlist (B) ⇒ backend change; (2) no durable dedupe for chat sends (F3/B) ⇒ `forward_message` can double-execute; (3) no relay-side runtime authorization (F4) ⇒ `executor` alone does not stop a second Kilo CLI from owning the id. Falsifier: a `forward_message` retried with a fixed `messageID` executing twice, or a second CLI claiming the same id and receiving the forwarded command.

## License/status corrections
None. Both licenses and the version/commit facts are exact. A's explicit warning that **kilo-pi-provider is Boost 1.0, not MIT** is correct and important (assignment's "BSL-1.0" shorthand = Boost Software License, not Business Source).

## Gaps for synthesis
1. **Relay dedupe for the forward path** — `mutationId` is optional and chat doesn't send it (B/Q5, F3). Close with: F's retry experiment against a local stack; design a mandatory idempotency key for `forward_message`.
2. **Relay-side ownership fencing** — `sessionOwners` is last-heartbeat-wins with no runtime check (F4, B/Q4). Close with: B's admission check + a rejected second-owner test.
3. **Missed existing ownership primitive** — A never cites `kilocode/session/drain.ts`, `packages/schema/.../session-drain.ts` (`session.drained`/`session.drain.interrupted`), or `cli/run-drain.ts` (E's anchor). Close with: reconcile A's `AttachedState` third-marker proposal against `SessionDrain`.
4. **ID-format compatibility** — A leaves `SessionID`/`ses_` minting open (Q4); F2 notes Pi's id is a UUID while Cloud enforces strict `ses_`, and C/Q4 shows Pi accepts a caller-supplied `--session-id`. Close with: a one-line proof that Pi accepts and persists a `ses_…` id.
5. **Sidecar fidelity** — A's local HTTP+SSE reuse is labelled Inference and unrun (Q4b, open Q3). Close with: C/F harness exercising `prompt_async` + `GET /event` with `KILO_SERVER_PASSWORD`.
6. **Two-track seam choice** — A recommends relay `forward_message` *and* local HTTP sidecar; synthesis must decide which is the Phase-1 boundary (E chose local prompt routing).
