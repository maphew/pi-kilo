# Review F — falsification and test design

- Review bead: `pi-kilo-hyj.14`; reviewer date: 2026-10-17 (UTC).
- Artifact reviewed: `reports/research/2026-10-16-workstream-f-falsification.md` @ `b31f9a157fa219071f3242e513fafac713df5ff5` (committed; no working-tree drift — `git status --short reports/research/` clean).
- Repos checked (zero drift vs artifact pins):
  - `/tmp/pi-kilo-workers/src/cloud` @ `d38649d7e3ac06c45d76c61baa334be5df0fbc02` — OK (exact match).
  - `/tmp/pi-kilo-workers/src/kilocode` @ `1552877e82ceaecc79a9fd4be7859518745e6f56` — OK (exact match).
  - `/tmp/pi-kilo-workers/src/pi-mono` (Pi docs, package `1.3.0`) — checked for F2/F5/F7 Pi-side claims.
- Note: the pinned cloud/kilocode SHAs in the F artifact's header (`11c1899…`, `40b2a4d…`, pi-kilo `1c4a449…`) are the author's *local-clone* SHAs from 2026-10-16, not the `/tmp/pi-kilo-workers/src` pins. The actual code findings reproduce exactly at the pinned SHAs, so this is a provenance wrinkle, not a correctness problem.

## Verdict: PASS

F's two load-bearing claims — last-heartbeat-wins ownership with no runtime-kind guard, and chat sends without `mutationId` so relay durable dedupe never engages — both verify exactly at the pinned SHAs with file+symbol+line evidence. The conditional NO-GO is entailed by that evidence. Synthesis may rely on F's F3/F4 findings and experiment design; it must not treat the local-HEAD SHAs in F's header as the verification revisions (use the pinned SHAs cited here).

## Citation spot-checks

| # | Claim (artifact §) | Status | Evidence |
|---|---|---|---|
| 1 | F4: ownership is `sessionOwners.set` on every heartbeat; second claimant silently takes over; pending commands of old owner failed (`UserConnectionDO.ts` ~329, ~688–724) | **confirmed** | `UserConnectionDO.ts:335` (`private sessionOwners = new Map<string,string>()`); `:711–732` (previousOwner check → `failPendingCommandsForOwnerChange`, then unconditional `set` at `:730`); no kind/lease check on that path |
| 2 | F4: routing = `findCliForSession` = whoever owns it (~2425) | **confirmed** | `UserConnectionDO.ts:2431–2432` (`findCliForSession` reads `sessionOwners.get(sessionId)`); call sites `:1464`, `:1485`, `:1585`, `:2137` |
| 3 | F4: only stale-connection rejection exists, no second-claimant guard (~1568) | **confirmed** | `UserConnectionDO.ts:1574–1582` (`SESSION_OWNER_CHANGED_ERROR` only when `msg.connectionId` mismatches); heartbeat claim path has no equivalent rejection |
| 4 | F4: no runtime-kind guard anywhere in ownership/heartbeat | **confirmed** | `instanceSchema.kind = z.enum(['cli','remote']).optional()` (`user-connection-protocol.ts:19`); no `provider`/`runtime` field; `UserConnectionDO.ts` heartbeat handler never reads `instance.kind` (only `:775–786` legacy-strip + `:2202` passthrough to `getConnectedInstances`) |
| 5 | F3: `send_message`/`send_command` dispatched without `mutationId` (~1039–1095) | **confirmed** | `cli-live-transport.ts:1041` (`send_command`, 2 args), `:1087` (`send_message`, 2 args); inner `sendCommand(cmd,data,mutationId?)` (`:699–719`) supports a third arg but the chat paths omit it; only `create_session` (`:982–992`) passes one |
| 6 | F3: relay dedupe gated on `if (msg.mutationId)` (~1627) | **confirmed** | `UserConnectionDO.ts:1633` (`if (msg.mutationId)`); without it only the narrow `CATALOG_DEDUPE_COMMANDS` (`list_models`/`list_commands`, `:156`) in-flight check (`:1611–1626`) applies — chat sends get neither durable nor in-flight dedupe |
| 7 | F3: CLI `send_message` handler calls `prompt()` unconditionally, no `messageID` dedupe (~1215) | **confirmed** | `remote-sender.ts:1280–1324` (validate → normalize → `dispatchLongRunning(... prompt(promptInput))`); `messageID` optional passthrough (`:61`, `:184–187` with explicit "remove this fallback" comment) |
| 8 | F1: `kind` is `["cli","remote"]` only, no provider field | **confirmed** | cloud `user-connection-protocol.ts:19`; kilocode `remote-protocol.ts:52`; `SessionEventV2RowSchema` carries only `platform`/`createdOnPlatform`, no owner (`:65–73`, `:194`) |
| 9 | F2: `ses_` strictness is per-session-path, UserConnectionDO path permissive | **confirmed** | `user-connection-protocol.ts:3–5` (explicit comment: `z.string()` here, strict `ses_` enforced by SessionIngestDO path); `buildCreateSessionWireData` `cloneFromKiloSessionId` is one-time copy (`cli-live-transport.ts:45–60`) |
| 10 | F5: event envelope has no sequence; `catch_up` schema-only | **confirmed** | `CLIOutboundMessageSchema` event = `{sessionId, parentSessionId?, event, data}` (`user-connection-protocol.ts:101–107`); `catch_up` only in `types/ws-protocol.ts:13`, no producer in `services/session-ingest/src` |
| 11 | F6: `replay()` re-emits pending permission/question/suggestion on subscribe (~554–609) | **confirmed** | `remote-sender.ts:581–609` (`replay()` lists `Suggestion`/`question`/`permission` and re-sends); always sends queue snapshot |
| 12 | F7: permission answers route to executing CLI; relay has allowlist but no permission policy (~129–146, ~1360) | **confirmed** | `remote-sender.ts:1425–1439` (`permission_respond` → `permission.reply`); `UserConnectionDO.ts:133–153` (`ALLOWED_VIEWER_COMMANDS` incl. `send_message`, `permission_respond`) — routing control, not authorization policy |
| 13 | F8: authenticated WS endpoint with token (~437) | **confirmed** | `remote-ws.ts:437` (`/api/user/cli?token=…&connectionId=`); hand-mirrored schemas confirmed (cloud `user-connection-protocol.ts` vs kilocode `remote-protocol.ts`) |
| 14 | F2/F5/F7 Pi-side: UUID session header, `switch_session` continuation, delta-only `message_update` | **confirmed** | pi-mono@1.3.0 `docs/session-format.md:69`, `docs/rpc-commands.md:592–607`, `docs/json.md:41,67–93` |
| 15 | F3: "`grep mutationId apps packages` shows no chat-send use" | **drifted-line-numbers (substantive point confirmed)** | `mutationId` *is* passed on `create_session` (`cli-live-transport.ts:992`, via `create-session.ts:105–131`) and catalog paths; zero chat-send (`send_message`/`send_command`/`interrupt`/replies) call sites pass it — verified by reading all `sendCommand(` sites (`:992,1005,1033,1041,1087,1103,1108–1135`) |

15 citations sampled; 14 confirmed verbatim, 1 confirmed in substance (F's "~1039–1095" line range is ~50 lines stale vs the pinned cloud SHA but names the exact functions). No `wrong` or `unverifiable` findings on load-bearing claims.

## Label-hygiene findings

- Minor: F3's "`grep mutationId apps packages` shows no chat-send use" is phrased as a Verified fact but is really a negative grep result (a Source-claim-grade observation). Harmless — I re-ran the equivalent check and it holds — but synthesis should cite the positive evidence (call sites listed above), not the grep.
- Minor: F5's "Observed behavior (literature-level, not run)" for WS ordering is honest but the label stretches "Observed behavior" (nothing was observed). It is correctly scoped to transport-ordering-unlikely / loss-across-reconnect-is-the-risk, so no conclusion depends on it.
- Otherwise exemplary: every threat carries an explicit **Falsify if** clause, and Inferences (F1 runtime-field change, F2 mapping need, F4 flapping, F7 adapter fidelity) are marked as such.

## Distinction violations

None. F consistently frames the experiment as testing history-display + message-delivery + ownership (bidirectional messaging), never claims transcript import equals continuation, and its "What this experiment does NOT prove" paragraph explicitly excludes runtime-state migration and active-turn migration.

## Cross-consistency notes

- **Agrees with A** (wire contract): A verifies the same 16-command dispatch, `kind: cli|remote`, `send_message → prompt()` full execution (`a…,162-line` artifact, Q3), and independently concludes the relay path requires CLI impersonation. F's relay-side findings (last-heartbeat-wins, no kind guard) are the cloud-half complement A could not see (A notes the relay is closed-source from kilocode's side).
- **Agrees with B** (cloud/ownership): B verifies `sessionOwners` (`UserConnectionDO.ts:335`), owner-move semantics (`:711`), and `mutationId`-optional dedupe from the same file. B also flags the impersonation-shaped onboarding (heartbeat a `ses_` row with a user JWT). No contradictions found.
- **Engages E but with a real tension synthesis must resolve**: E proposes an adapter-side design around a *different* Kilo surface (canonical identity + durable `seq`/`evt_` events, `session.prompt` idempotency keys, SSE `after=seq` resume — E §3–4) with an explicit `owner`/`runtimeBinding` routing rule. **E's seq+idempotency mechanism does NOT answer F's risk 2 as scoped**: F attacks the *Remote Connections* path (relay `UserConnectionDO` + `cli-live-transport`), where I verified there is no `seq` on the live event envelope and no `messageID`-keyed relay dedupe. E's mechanism lives on a different surface (durable/SSE/prompt endpoint) than the PA-under-test F falsifies. Compatible *if* synthesis scopes E's design to the durable-event surface and F's NO-GO to the remote-connection PA — contradictory if E is read as "the relay path already dedupes."
- **Agrees with C** (permissions): C's verified deny/allow matrix (C §C3, deny/allow observed via `tool_call` + `ctx.ui.confirm`, enforcement stays in Pi) is exactly the enforcement point F7's step 5 depends on. F adds the adversarial paths C does not stress (reconnect/timeout auto-approve, lossy dialog mapping). Agreement on mechanism, F extends the threat surface.
- **Converges with D independently**: D's gap list (external-runtime registration, owner grant/revoke + fencing, session identity, replay dedup) matches F1–F4. F's relay-side evidence sharpens D's optimism where D credits CLI-side `attached-state.ts` machinery — the CLI fence is real (verified: `attached-state.ts` containment fences) but relay-side `sessionOwners` bypasses it for foreign claimants.

## Recommendation assessment

Entailed. The conditional NO-GO rests on F3+F4 (both verified line-exact above) plus F2 (no logical↔runtime mapping — verified: `sessionOwners: Map<string,string>` keyed by bare id, permissive relay path vs strict ingest path). The GO-for-labelled-harness half follows from F8 (verified: token-authed private WS, hand-mirrored schemas) plus Plan Phase-1's explicit harness allowance.

- **Flip to GO (no-Kilo-changes):** a single observation — two concurrent heartbeat claimants for one `ses_` id are *rejected* (second claim gets an error, owner stable) AND a retried `send_message` with identical `messageID` executes once — observed against the real relay or its in-process DO harness. Either half alone is insufficient; ownership without dedupe (or vice versa) still breaks invariants 4/5.
- **Flip to unconditional NO-GO:** experiment step 5 fails unfixably — a Pi permission-deny is bypassed via the web path on *every* representable mapping (i.e. no faithful `permission.asked` encoding exists for Pi's dialog set), or identity can only work by forking Kilo's session model (invariant 10). A single harness run showing bypass-with-no-adapter-fix suffices.

## License/status corrections

None. F makes no license, star-count, or maintenance assertions (correctly — all targets are first-party Kilo/Pi sources, and F labels the wire protocol "private/internal," which the hand-mirrored schemas and token-authed endpoint confirm).

## Gaps for synthesis (numbered; each with closer)

1. **F's header SHAs are local-clone revisions, not the pinned `/tmp` SHAs.** Closer: cite this review's SHA table (both repos verified at exact pins, zero drift) instead of F's header table. (Provenance only; findings reproduce.)
2. **Downstream `SessionPrompt` dedupe (F open Q2) still open.** Closer: one grep-run through `session/prompt.ts` queue admission for `messageID` keying — decides whether modern full-stack clients are already safe even though the relay is not.
3. **`catch_up` producers outside `services/session-ingest/src` (F open Q1) still open.** Closer: repo-wide grep in kilo-cloud for `catch_up` producers; a found producer downgrades F5 High→Medium.
4. **Harness fidelity for steps 1–3 (F open Q3) unproven.** Closer: confirm `UserConnectionDO` runs in the repo's vitest/DO integration env without prod bindings; if not, the experiment's steps 1–3 rest on the ~200-line stub (labelled, weaker).
5. **Pi RPC resume story (F open Q5) still open.** Closer: check installed 1.3.0 source (not just docs) for any cursor/resume on the session event stream; absence confirms F5's Pi half.
6. **Experiment is FAIL-discriminating only.** A PASS in the stub harness does not transfer to `app.kilo.ai` (F admits this). Closer for ADR: require the gated Test-8 prod confirmation before any "cloud support" claim; cite F as decisive only for the *no-Kilo-changes* rejection, not for harness-GO scope.
