# Review E — Architecture and session semantics

- Review bead: `pi-kilo-hyj.13`; reviewer date: 2026-10-17 (UTC)
- Artifact reviewed: `reports/research/2026-10-16-workstream-e-architecture.md` @ `b31f9a157fa219071f3242e513fafac713df5ff5` (committed; working tree clean except unrelated untracked Review-B file)
- Repos checked:
  - `/tmp/pi-kilo-workers/src/kilocode` HEAD `1552877e82ceaecc79a9fd4be7859518745e6f56` — **matches E's pinned SHA, zero drift**
  - `/tmp/pi-kilo-workers/src/kilo-pi-provider` HEAD `4c361a604349ebbaf29576ada481df27e853b2b4` — **matches E's pinned SHA**
  - Pi docs, installed `@earendil-works/pi-coding-agent@1.3.0` — **matches E's cited version**

## Verdict: PASS WITH MINORS

E's core deliverable — reuse Kilo's durable session-event log, project Pi events into it, name exactly one new Kilo capability — is well-grounded: I confirmed every load-bearing Kilo symbol and nearly every Pi claim below. Synthesis may rely on the entity/event mapping and the capability ladder. It must **not** treat ownership or idempotency as solved: E's ownership rules lack a fencing mechanism and do not survive F's last-heartbeat-wins finding, and `msg_` idempotency is a labeled Recommendation, not verified behavior.

## Citation spot-checks

| Claim (E section) | Artifact section | Status | Evidence |
|---|---|---|---|
| Event envelope `evt_` + `durable:{aggregateID,seq,version}` + `metadata` | §1 Event, §3.3 | confirmed | `packages/schema/src/event.ts:9,34-36,39,56` @1552877e |
| `session.next.step.started/ended/failed`, `text.delta/ended`, `reasoning.*`, `tool.input.*`, `tool.called/success/failed/progress`, `retried`, `compaction.*` | §1 Turn/Event, §3.2 | confirmed | `packages/schema/src/session-event.ts:95,150,163,186,211,222,236-265,282-360,388,400-421` |
| "Stream fragments are live-only; …Ended is the replayable full-value boundary" | §3.1 | confirmed (near-verbatim) | `session-event.ts:209,247,291` |
| `session.create` accepts optional client `id` | §2 Pi-first | confirmed | `packages/protocol/src/groups/session.ts:138-141` |
| `session.prompt` accepts optional `id`; `SessionInput.Admitted{admittedSeq,id,…delivery}` | §3.2, §5 | confirmed | `protocol/groups/session.ts:219-224`; `schema/src/session-input.ts:15-21` |
| `history` "after an exclusive aggregate sequence"; SSE "replay after seq, then live" | §3.1, §4.3(6) | confirmed | `protocol/groups/session.ts:333,351` |
| `session.active` = "foreground Session drains currently owned by this Kilo process" | §1 Runtime/Owner | confirmed (verbatim) | `protocol/groups/session.ts:157-163`; handler `server/src/handlers/session.ts:86-90` |
| Drain is in-memory per directory, not a distributed lease | §1, §8 Q2 | confirmed | `opencode/src/kilocode/session/drain.ts:31,43-45,64-65`; `schema/src/kilocode/session-drain.ts:8-13` |
| `permission.v2.asked` (tool source) / `replied` (once/always/reject) | §3.2, §5 | confirmed | `packages/schema/src/permission.ts:25-50` |
| `session.status` idle/retry/busy/offline | §3.2, §4.3(5) | confirmed | `packages/schema/src/session-status-event.ts:13,16,32,36` |
| `SessionMessage.ID` = `msg_…`; `msg_` as idempotency key | §3, §5 | confirmed (field exists; idempotent *behavior* unverified — see Label-hygiene) | `packages/schema/src/session-message.ts:12` |
| Pi `--session-id`, custom IDs; turn_start/end; `message_end` authoritative; `agent_settled` vs `agent_end`; steer/followUp reject-without-choice | §1, §2, §3.1 | confirmed | `docs/cli.md:92,107`; `session-format.md:14`; `docs/json.md:44-68`; `docs/sdk.md:66-68`; `docs/rpc.md:69` |
| Pi `toolCallId` lifecycle; `auto_retry_*`; `queue_update`; `session_info_changed`; opaque thinking/text signatures; `extension_ui_request confirm` | §3.2, §3.3, §5 | confirmed | `docs/json.md:85-123,166-170`; `message-types.md:21-65`; `rpc-extension-ui.md:7-63` |
| `importFromJsonl` / `SessionManager` restore for handoff-as-rebuild | §4.1 | confirmed, and E correctly labels it **Source claim** | `docs/sdk.md:58` |
| kilo-pi-provider is provider + ambient UI, not session sharing | §2 | confirmed | `src/index.ts:240` (`registerProvider`), `:246` (`registerCommand`), `ambient-ui.ts` |

## Label-hygiene findings

1. **Exec summary presents "per-session seq + `msg_` idempotency" as the invariant-5 mechanism; the artifact body correctly labels the idempotent-admission half Recommendation** (§3: "Recommendation building on Verified fact of the id field"). Synthesis must carry the body label, not the summary confidence — F3 shows the chat path does not dedupe today.
2. **§4.3(4) "durable events … are written once, keyed by `callID`" reads as guarantee; it is adapter-side dedupe logic that is not yet designed.** Treat as requirement, not fact.
3. **Minor technical slip: `admittedSeq` is server-assigned (Admitted struct), not a client idempotency key** — only `id` (`msg_`) is client-supplied. E's "session.prompt id + admittedSeq support this" conflates cursor with key. Harmless if synthesis uses `id` as the key.
4. **Positive:** grounding note (A–D were stubs), Inference/Recomm­endation/Open-question labels, and the "not durable distributed lease" admission are exemplary.

## Distinction violations

**None material.** §4.1's capability ladder and "continuation stays per-runtime; handoff is history rebuild" (summary, §4.1, §6.3, ADR) hold throughout; active-turn migration is excluded with "no mechanism found" on both sides. One ambiguity to clarify in synthesis, not a slide: **both `turn_end` and `message_end` map to `step.ended`** (§3.2) — the single-writer/dedupe rule between them (presumably keyed by `assistantMessageID`) is unstated.

## Cross-consistency notes

- **E vs C (C post-dates E — deltas that strengthen E):** C *confirms* E's RPC boundary, delta-vs-authoritative discipline, `agent_settled`-as-completion, custom `--session-id` pinning (C2 `expc2`), and the Pi-enforced permission bridge (C3 deny/allow). C *adds* two primitives E lacks: `get_entries(since)` durable cursor (E's "adapter buffers, reconciles by seq" should be re-based on it) and the `disposition` branch (`handled` needs no settlement wait). C *contradicts* E's §4.3(6) completeness: adapter death kills the Pi child (stdin-close shutdown) — E covers Kilo-loss but not adapter-loss.
- **E vs F (the dissent):** E's "biggest risk is ownership routing" framing **survives** — F4 confirms it is the crux — but E **under-scopes** it: E scoped the risk to the CLI drain layer and never examined the relay's owner map, so its turn-boundary rules have no mechanism that survives F4. On F3, `msg_` is necessary but insufficient (relay dedupe is `mutationId`-gated; chat sends omit it). On F2, E's binding record *is* essentially F's demanded fix — but the Kilo-first `ses_`-verbatim option collides with F2's owner-collision problem; the mapping fallback is the safe path. E does not address F6 permission-reply replay or C's dialog-timeout auto-resolve.
- **E vs A:** aligned — A's recommended "externally owned session + forward seam" is the same one capability E names; A's localhost+token listener matches E §5.
- **E vs B:** E correctly punts cloud (open Q3/Q6); B's OCVSAL license warning and out-of-scope-for-execution verdict are compatible constraints synthesis must carry.
- **E vs D:** aligned — E's rejected-alternatives (no new protocol; ACP not the session layer) match D's Approach 1+3; E's "ACP may still be Pi-side control" open question matches D's edge-only ACP role.

## Recommendation assessment

"Thin adapter + one new Kilo capability; no new protocol" is **entailed for history-access scope** (both sides' durable/partial-complete models verified) and **explicitly conditional for bidi/continuation** — E states the falsifier itself (if prompts can't route without Kilo executing, Phase 1 = labelled harness). The single falsifying observation: F-experiment step 3 shows a second heartbeat steals the session, or `session.prompt` is proven to always schedule Kilo's own engine with no routing seam. E's risk framing stays right after C and F, but must be widened from "prompt routing" to "leased, fenced, runtime-typed ownership."

## License/status corrections

None required. E's SHAs/versions all check out. One note for synthesis (from A, not an E error): `kilo-pi-provider` is **BSL-1.0, not MIT** — E's "separate adapter package" recommendation sidesteps copying, but the ADR should state the constraint explicitly.

## Gaps for synthesis

1. **Ownership lease spec** (TTL, conflict-reject, fencing token, runtime-kind, UI surfacing) incl. the relay layer E never read — via F-experiment step 3 + A/B relay paths, before any Phase 1 routing bet.
2. **Admission idempotency proof** (same `msg_` → one turn) — via F-experiment step 2; until then invariant 5 is partial.
3. **Binding record home** (where stored, who reads `runtimeKind:"pi"`) — ADR decision with B.
4. **`ses_` verbatim acceptance by Pi** — one-line experiment in C's C2 pattern; use mapping fallback until proven.
5. **Abort encoding** (`step.failed` vs open step) and **title/rename + `queue_update`** mapping — ADR decisions; minor.
6. **Permission-reply replay suppression + timeout policy** (F6/F7, C's auto-resolve note) — adapter spec requirement.
7. **Adapter-death vs Kilo-loss matrix + `get_entries` reconcile** — Phase 1 exit criteria; re-base E's buffer story on C's cursor.
8. **Cloud execution scope** stays per B's verdict; E's design must not be read as covering Phase 3.
