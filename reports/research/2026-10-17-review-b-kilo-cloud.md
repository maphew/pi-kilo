# Review B — Kilo Cloud and hosted sessions
- Review bead: `pi-kilo-hyj.10`; reviewer date (UTC): 2026-10-17
- Artifact reviewed: `reports/research/2026-10-16-workstream-b-kilo-cloud.md` @ `b31f9a157fa219071f3242e513fafac713df5ff5` (`git log -1` on the path; working tree clean except this new review file)
- Repos checked (pre-clones, no drift — both match artifact's pinned SHAs exactly):
  - `/tmp/pi-kilo-workers/src/cloud` HEAD `d38649d7e3ac06c45d76c61baa334be5df0fbc02` — OK
  - `/tmp/pi-kilo-workers/src/kilocode` HEAD `1552877e82ceaecc79a9fd4be7859518745e6f56` — OK (kilocode side only cross-read for A-consistency)

## Verdict: PASS WITH MINORS
Justification: every load-bearing claim spot-checked confirms in substance at the pinned SHAs — schema tables, wire protocol, allowlist, Cloud fenced lease, closed enums, both licenses. Synthesis may rely on the feasibility verdict (Cloud Agent no-go; Remote Connections only) and the hard-coupling list. It must not copy the artifact's line numbers or the `session-ingest-contracts/` path prefix verbatim — several have drifted (all minor, enumerated below).

## Citation spot-checks
| Claim | Artifact section | Status | Evidence (2026-10-17) |
|---|---|---|---|
| `cloud_agent_workspace_folders` :6272, `cloud_agent_worktrees` :6305, `cli_sessions_v2` :6346 + columns | Q1 | confirmed | `packages/db/src/schema.ts` — all three tables + listed columns present |
| `live_summary` comment "only this summary is stored, never the raw text" | Q2 | drifted-line-numbers | text confirmed at `schema.ts:6392`, not :6366 |
| `sessionIdSchema` ses_+26, worktree provider enum `cloudflare\|vercel\|cloudflare-containers` | Q1 | confirmed (path drift) | file is `packages/session-ingest-contracts/src/rpc-contract.ts:4-15`, not `session-ingest-contracts/src/…` as cited (root prefix missing; file otherwise exact) |
| `SessionItemSchema` item types; `z.looseObject` tolerance | Q1/Q6 | confirmed | `session-sync.ts:12-87` — all 11 literals present |
| `SessionIngestDO` ingest/export/messages/clone-batch lines | Q1 | confirmed | `SessionIngestDO.ts:482,:1072,:1059,:1556` — all exact |
| `SessionEventPayload` 4 event types | Q1 | confirmed | `user-connection-protocol.ts:247-251` |
| `instanceSchema` kind; 16-cmd allowlist; `sessionOwners`, `handleHeartbeat` | Q1/Q4 | confirmed | protocol :13-19; `UserConnectionDO.ts:133` (verbatim), :335, :660 |
| Owner-change fail-pending; `getConnectedInstances`; `findCliForSession` | Q4/Q1 | confirmed | `UserConnectionDO.ts:711-730,:2186,:2431` — all exact |
| `aggregateSessions:3106` owner-unique dedupe | Q4/Q6 | drifted-line-numbers | def at :3063; dedupe comment ~:3100-3110; file is 3126 lines — cite :3063 |
| WS + ingest/export/messages routes; JWT on `/api/*` | Q5 | confirmed | `routes/api.ts` + `app.ts:64`; DO-local `/cli`+`/web` at `UserConnectionDO.fetch:448` |
| Heartbeat-timeout 4408; connected/disconnected events; attention reset | Q5/Q7 | confirmed, one drift | all exact; but `closeStaleSocket` **def** is :2386, not :466 (:456 is its call site) |
| `mutationId` ≤128 durable id; `COMMAND_EXPIRED` | Q5 | confirmed | protocol :137,:168-172; `UserConnectionDO.ts:203-205,:373-374` |
| Cloud Agent: Dockerfile installs `@kilocode/cli`; `KILO_PLATFORM`/`KILO_DISABLE_AUTOUPDATE`; control-plane "Agent behavior belongs to Kilo" §1; HS256 launch envelope, "no unsigned-wrapper bypass" §2 | Q3 | confirmed | `services/cloud-agent-next/Dockerfile:65`; `wrapper-launch-env.ts:62-63`; `docs/control-plane.md:12,:47` |
| Wrapper lease/generation (`wrapper_runtime_state`, `wrapper_lease`, `startup_verified/delivery_accepted/retain_warm`, `wrapperGeneration/ConnectionId/RunId`) | Q1 | confirmed | `session/wrapper-runtime-state.ts:12-14,:181-183,:517-519` |
| `/stream` ticket+Origin gate; `/ingest` internal-only | Q4/Q5 | confirmed | `persistence/CloudAgentSession.ts:1234-1290`; "internal-only" header at `websocket/ingest.ts:12` |
| Three-way transport switch; `ResolvedSession`; read-only spec; `StreamEventType` | Q4 | confirmed | `CloudAgentProvider.tsx:147-160`; `cloud-agent-sdk/types.ts:284-299`; `.specs:39`; `websocket/types.ts:23-43` |
| Sentinel connection id; status resolvers; `connectedInstanceSchema`; `KNOWN_PLATFORMS`; admission fn | Q7/Q6 | confirmed, micro-drift | resolvers at :214/:234 (artifact says :215/:238, off-by-one); router :36; `platforms.ts:2`; `user-session-admission.ts:11` |
| `cloud_agent_sessions` :6628, `cloud_agent_session_runs` :6780, run status enum | Q1 | confirmed | schema defs + enum check at :6827 |
| Licenses: cloud OCVSAL, kilocode MIT | header | confirmed | see License section below |

## Label-hygiene findings
Essentially clean — load-bearing uncertainties are labelled Inference with explicit falsifiers (Q4a, Q4b, Q2). Two nits: (1) blended "Source claim / Verified fact" license label — harmless, both texts check out; (2) "documented-for-third-parties" (Q5) cites no third-party docs — treat as Source claim. Neither affects synthesis.

## Distinction violations
None. The five-capability table is enforced throughout: Strategy 1 is scoped to history+bidi+continuation **for Pi-owned sessions only**; Cloud-Agent-owned continuation and active-turn migration are explicitly excluded with schema-level reasons (no shared tool/approval/provider state).

## Cross-consistency notes
- **Agrees with A** (`2026-10-16-workstream-a-kilo-local.md` Q2/Q-conclusion): same closed `kind: cli|remote` enum, same JWT-authenticated outbound CLI socket, same allowlist shape. Framing differs complementarily — A calls reuse "impersonation, not registration" (normative), B calls the wire shape "generic enough" but flags the `kind` mislabeling + admission unknown (technical). No contradiction.
- **Agrees with F** (`2026-10-16-workstream-f-falsification.md` §F4/D8): same `/api/user/cli → UserConnectionDO` relay model, same `sessionOwners` plain-Map + `mutationId` durable-dedupe mechanics. F deepens the failure analysis (double-dispatch on resend) and thereby supports B's open question on whether last-writer-wins ownership can guarantee invariant 5.
- B's "ownership transfer exists between two Kilo CLIs" cell is directly evidenced (`UserConnectionDO.ts:711-730`), consistent with A's `attached-state.ts` fencing account.

## Recommendation assessment
Entailed. The Cloud Agent no-go follows from a verified conjunction: baked-in `@kilocode/cli` image + internal-only `/ingest` + HS256 admission with no bypass + DO-held fenced lease + "Agent behavior belongs to Kilo" principle. The Remote-Connections-only half follows from JWT+Zod generic shape with no CLI-proof — correctly labelled Inference with a concrete verifier (minimal WS client on a local stack). Falsifier: a route rebinding `wrapper_runtime_state` to a non-sandbox process, or server-side rejection of non-Kilo clients on `/api/user/cli` — B names both searches.

## License/status corrections
None — both confirmed verbatim at the pinned SHAs. Operative terms for prototype purposes: **cloud `LICENSE.md` (OCVSAL v1.0):** "Using software … in production requires a valid commercial agreement"; free to "modify…, test…, and publish modifications", but "the copyright holder retains all right, title and interest in and to all modifications" — so local reading/testing is fine, but copying Cloud code into the prototype or running Cloud pieces in production needs commercial review. **kilocode `LICENSE`:** standard MIT (2026 Kilo Code / 2025 opencode) — reusable under MIT terms.

## Gaps for synthesis
1. **Live-stack admission check** (Phase-1-gating) — does `/api/user/cli` accept a non-Kilo client beyond the user JWT? Closes with: minimal WS client on a local dev stack, no prod creds.
2. **`SessionItemSchema` expressiveness** — can Pi's native tool/permission/error events map without loss? Closes with: C's Pi event inventory mapped field-by-field against `session-sync.ts`.
3. **Handoff race-safety** — can last-writer-wins `sessionOwners` guarantee invariant 5 for Pi↔Kilo transfer? Closes with: F's falsification experiment on a local stack.
4. **UI label acceptance** — which `kind`/`created_on_platform` values render unchanged? Closes with: local web run (code paths already located).
5. **Cloud read-only sufficiency** — is the Cloud Agent event log reconcilable with `SessionIngestDO` history for Pi continuation? Closes with: schema comparison + local read test.
6. **Prod-side risks (do not poke prod):** relay behavior, prod JWT/ticket flows, private Cloud APIs — risks for Kilo-side confirmation, not Phase-1 experiments.
