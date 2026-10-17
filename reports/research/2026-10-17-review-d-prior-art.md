# Review D — Prior art and protocol reuse

- Review bead: `pi-kilo-hyj.12`; reviewer date (UTC): 2026-10-17
- Artifact reviewed: `reports/research/2026-10-16-workstream-d-prior-art.md` @ `b31f9a1` (file commit; worktree clean at review time)
- D's investigation date: 2026-10-16; D states A/B/C were unstarted stubs at its commit — its Kilo/Cloud/Pi findings are independent, predating siblings

Repos checked (all `git rev-parse HEAD`, zero drift vs D's pins):

| Repo | HEAD | vs D pin |
|---|---|---|
| `/tmp/pi-kilo-workers/src/acp` | `e7dac67a…` | OK |
| `/tmp/pi-kilo-workers/src/asp` | `b6cdb662…` | OK |
| `/tmp/pi-kilo-workers/src/universal-session-log` | `d9b8680c…` | OK |
| `/tmp/pi-kilo-workers/src/kilocode` | `1552877e…` | OK |
| `/tmp/pi-kilo-workers/src/pi-mono` | `8efd314f…` | OK |
| `/tmp/pi-kilo-workers/src/pi-acp` | `04d0a15d…` | OK |
| `/tmp/pi-kilo-workers/src/OpenHands` | `d6415636…` | OK (coordinator HEAD) |
| `/tmp/pi-kilo-workers/src/cloud` | `d38649d7…` | OK |
| `/tmp/pi-kilo-workers/src/kilo-pi-provider` | `4c361a60…` | OK |

## Verdict: PASS WITH MINORS

D's matrix is genuinely evidence-backed: every load-bearing protocol claim I sampled traces to real schema/docs/code at the pinned SHAs, and D hedges exactly where it should (open questions #1, #5, #6). Synthesis may rely on the ACP/USL/pi-acp/Remote-Connections findings, but must not treat Approach-1 "reuse" as proven (A's impersonation finding postdates D) nor cite v1-ACP `Other`/passthrough semantics (a v2-forward claim).

## Citation spot-checks

| Claim | Artifact § | Status | Evidence (2026-10-17) |
|---|---|---|---|
| `NewSessionRequest` has no client session id; agent MUST return unique id | 1.1 | confirmed | `acp/schema/v1/schema.json` `$defs.NewSessionRequest` (cwd/additionalDirectories/mcpServers only); `docs/protocol/v1/session-setup.mdx:71` |
| `session/load`+`resume` are same-agent (new client instance OK, other runtime not) | 1.1 | confirmed | same doc: load "sharing sessions between different Client instances"; schema `Load/ResumeSessionRequest.sessionId` |
| ACP method surface (agent + client incl. `fs/*`, `terminal/*`, elicitation) | 1.1 | confirmed | `schema/v1/meta.json` agent/clientMethods match D's list verbatim |
| Unknown enums `_`-preserved; `Other` blocks must be preserved (v1) | 1.1 | wrong (version) | v1 stable `ContentBlock` has NO `Other` variant (text/image/audio/resource_link/resource only); `_` reservation covers custom *method names* (`v1/extensibility.mdx:47`); `Other`/`_meta`-patch is v2/unstable |
| Stable v1 vs v2 Draft 2026-07-20; CHANGELOG 1.12.0 2026-10-16 | 1.1/srcs | confirmed | README "current stable … is `1`"; `docs/announcements/acp-v2-draft.mdx` "Published: July 20, 2026" |
| SDK `1.9.0` latest | 1.1 | confirmed | `npm view @agentclientprotocol/sdk` → 1.9.0, modified 2026-10-16 (unchanged today) |
| ASP draft schema v1.0, TS-only, JSON-Schema-on-roadmap; ACP/MCP/ASP split | 1.2 | confirmed | `asp/README.md:39` verbatim; `asp/spec/acp-mcp.md:13`; lineage/handoff/stableId/thinking/unknown verified in `spec/overview.md`, `content-blocks.md`, `spec/fidelity.md:38` |
| USL validation stage; pi importer/exporter; declared fidelity | 1.2 | confirmed w/ minor | `usl/README.md:74`; `packages/usl-convert/src/pi.ts` (JSONL path, id/header); `test/pi.test.ts` (deterministic/idempotent/thinking-signature). Minor: "54 Rust" vs README 32+21=53 |
| OpenHands lists Pi via `pi-acp`; typed tool-call event | 1.3 | confirmed | `OpenHands/docs/ACP_AGENTS.md:4,46`; `src/types/agent-server/core/events/acp-tool-call-event.ts` exists |
| `pi-acp@0.0.34`, caps + limits (session-map, no `fs/*`/`terminal/*`, MCP unwired, MVP) | 1.5 | confirmed | `npm view pi-acp` → 0.0.34 (2026-09-24); README:23,199–205; `src/pi-rpc/process.ts:162` (`--mode rpc`); 39 test files; MIT |
| Kilo Remote Connections protocol + attach fences + reconnect | 1.6 | confirmed w/ minor | `kilocode/packages/opencode/src/kilo-sessions/{remote-protocol,remote-ws,attached-state,remote-session-log}.ts` all match; minor: D's HTTP path omits `kilocode/` segment (real: `…/src/kilocode/server/httpapi/groups/remote.ts`, root `/remote`) |
| Kilo is ACP agent (`loadSession:true`, sdk 0.21.0); NO ACP client anywhere | 1.6 | confirmed | `packages/opencode/src/acp/service.ts:117`; `packages/opencode/package.json:72`; `ClientSideConnection` absent in kilocode, cloud, kilo-pi-provider |
| Pi RPC/JSONL tree sessions (`id`/`parentId`+header); `kilo-pi-provider` BSL-1.0, not a bridge | 1.6 | confirmed | `pi-mono/packages/coding-agent/docs/session-format.md:3,27`; provider `package.json: "BSL-1.0"` |
| v2 prompt-acceptance vs turn-end; thinking-fidelity loss over ACP tap | 3/§6 | confirmed w/ caveat | v2-draft announcement (prompt returns user-message id + idle); v2 keeps `agent_thought` upserts (`migration.mdx:66,461`), so loss is content-block-scoped; D correctly labels the USL part Source claim |

## Label-hygiene findings

1. Highest impact: matrix `Incremental? ✅` for Remote Connections ("it is Kilo's own code") carries the Approach-1 recommendation while external registration is admitted open (§6-Q1). Until A resolves, this cell should be ◐. Downgrade, don't drop.
2. v1-`Other`/enum-preservation presented as Verified fact — actually v2/unstable (see table). Relabel v2-forward.
3. "SessionId documented as opaque" — doc says "unique identifier" (§Session ID); "opaque" is used for replay messageIds. Wording drift, substance intact.
4. Star counts/SDK/npm dates are Source claims (GH/npm APIs) — correctly date-stamped; ACP 4458→4459 today, others unchanged. Fine as-is.
5. D's key inferences carry falsifiers (e.g. cross-agent `session/resume` attempt). Good practice, no flag.

## Distinction violations

None. D separates history-access / bidirectional-messaging / continuation / turn-boundary handoff throughout (§1.1 vs §1.2, §5-item-3 explicitly scopes out active-turn migration) and correctly tags `cloneFromKiloSessionId`-style import as non-delegation logic.

## Cross-consistency notes

- **Remote Connections: D is the optimist; A/B/F are harder.** D: "strongest existing substrate… maps almost one-to-one onto invariants 1–5 and 7" but flags registration as open. A (Q2/Q6): relay path as-is = impersonation (user-token dial to closed Kilo relay, `send_message`→`SessionPrompt` direct, no execute-elsewhere mode). B: ownership transfer exists only between two Kilo CLIs; no third-party transport. F: `InstanceAdvertisement.kind ∈ {cli,remote}`, no external-runtime field. Agreement on machinery, disagreement on readiness — synthesis must weight A/B/F.
- **C vs D on Pi/ACP: compatible layering, no tension.** C recommends native RPC and never mentions ACP/pi-acp; D's concrete step 2 is *also* native RPC/SDK bridging, with ACP only "at the Pi-facing edge if it earns its keep." Both land on RPC as the Pi boundary. E (§401–407) aligns: ACP rejected as complete solution, viable as Pi-side control.
- **ASP/USL "draft/reference-only": holds.** E explicitly defers to D ("Not adopted pending D"); D's verdict (borrow vocabulary + `pi.ts` mappings, no Phase-1 hard dependency) is consistent with E's open question.

## Recommendation assessment

Approach 1 + minimal semantics layer (3), ACP-at-edge is **entailed with qualifications, not a leap**: the matrix honestly marks every cross-runtime cell ◐/❌, and §§5–6 scope the new work to 7 items. But the ranking leans on the ◐→✅ readability of Kilo's fences. **Single falsifier:** if A's seam work shows the relay/attach path requires the CLI's in-process session store (i.e. a foreign runtime can only join by impersonating a CLI), Approach-1 "reuse" collapses into rebuild and the cost ranking inverts toward a thicker adapter. On §5's list: items 1 (registration), 4 (fidelity mapping), 5 (Pi↔logical identity) are irreducibly new; 2/3/7 are thin deltas over existing fences — fine; **item 6 (capability advertisement) is weakest** and could merge into Kilo's existing `Capabilities`/`InstanceAdvertisement` rather than stand as a new concept.

## License/status corrections

- `kilo-pi-provider` "BSL-1.0" = **Boost** Software License 1.0 (LICENSE text; no change-date/additional-use terms found) — permissive-style, nonstandard, but NOT the Business Source License. Synthesis must not misread the acronym.
- Otherwise none: Apache-2.0 (ACP), MIT (ASP/USL/pi-acp/OpenHands/Pi/Kilo), versions and activity claims re-verified above.

## Gaps for synthesis

1. **External-registration seam** (D-Q1, now A's Q6/Q7 answer): can a foreign runtime join without impersonation, and what is the smallest Kilo change? Closes with A's recommended seam + B's relay/auth confirmation.
2. **Cloud attach path** (D-Q2): third-party runtime transport/auth on Cloud. Closes with B's feasibility verdict.
3. **`pi-acp` depend-vs-fork decision** (D-Q3): 0.0.x, single maintainer, no `fs/*`/`terminal/*`, MCP unwired. Closes with a review of its 39 tests + C's RPC experiment.
4. **Thinking-signature survival** on any ACP path (D-Q4): reproduce Pi thinking round-trip through `pi-acp` vs native RPC; the `Other`-block premise is v2-only.
5. **Owner-lease reuse** (D-Q5): confirm Kilo's attach fence covers a foreign runtime before designing a new lease (F's test plan territory).
6. **USL "zero-loss" reproduction** (D-Q6): rerun `usl-convert` pi import/export on fixtures; until then the fidelity vocabulary is borrowed, not normative.
