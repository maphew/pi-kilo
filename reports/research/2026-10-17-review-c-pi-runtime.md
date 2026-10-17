# Review C — Pi runtime integration

- Review bead: `pi-kilo-hyj.11`, reviewer date: 2026-10-17 (UTC)
- Artifact reviewed: `reports/research/2026-10-16-workstream-c-pi-runtime.md` @ `bb5754e8a56fadd4df7edd6316943f114cf7e365` (file committed at that SHA; working tree clean for `reports/research/`)
- Repos checked:
  - `/tmp/pi-kilo-workers/src/pi-mono` @ `8efd314fa3d3232ce197d8d7a6a5660530b9d83e` — **OK, zero drift** vs artifact's pinned SHA.
  - Installed `@earendil-works/pi-coding-agent` @ `1.3.0` (package.json `version` + `license: MIT` confirmed) — matches artifact header.
  - Experiment scripts `/tmp/pi-kilo-workers/exp-c2/exp_c2.py`, `/tmp/pi-kilo-workers/exp-c3/exp_c3.py` + raw `c2.out`/`c3.out` — **present**, contents match artifact's in-text evidence.

## Verdict: PASS WITH MINORS

Synthesis may rely on the load-bearing claims — RPC as adapter boundary, caller-supplied `--session-id` identity binding, `get_entries(since)` durable cursor, `agent_settled` as turn completion, and the Pi-enforced permission bridge (deny + allow paths all reproduced). It must not cite the artifact's "`Other` content-block variant" assertion, the single documentation claim that fails verification (see findings).

## Citation spot-checks

| Claim | Artifact section | Status | Evidence |
|---|---|---|---|
| RPC strict JSONL/LF framing; Node `readline` splits U+2028/U+2029 | Q1 | confirmed | `rpc.md:50-56`, near-verbatim |
| Closing child stdin = orderly shutdown | Q5 | confirmed | `rpc.md:91-95` |
| `prompt` dispositions `started/queued/handled` | Q1/C1, contract table | confirmed | `rpc-commands.md:37-42` |
| `steer` after current tool calls; `follow_up` when idle | Contract table | confirmed | `rpc-commands.md:26-27,46-48,70-72` |
| `get_entries(since)` durable cursor + `leafId` branch check | Q2/design §3 | confirmed | `rpc-commands.md:689-717` ("even across client restarts") |
| `abort` waits for idle | Contract table | confirmed | `rpc-commands.md:94-96` |
| `message_update` delta-only; `text_end`/`message_end` authoritative | Q2/design §3 | confirmed | `json.md:68,72,81-93` |
| `agent_end` vs `agent_settled`; don't wait on `handled` | Q2/design §3, OQ4 | confirmed | `json.md:44-56`; `rpc.md:67-69` |
| System-message replay yields current prompt+tools | Q2 | confirmed | `session-format.md:80` ("Replaying them in order yields…") |
| Caller-supplied ID via SDK/`--session-id`; 8-hex ids; tolerate unknown `kind` | Q4 | confirmed | `session-format.md:11-14,56,121`; `cli.md:92-107` |
| Signatures (`text/thinking/thought`) opaque + provider-specific | Q2 inference | confirmed | `message-types.md:21-25,45-50,60-65` |
| Content blocks include an "`Other` variant" receivers "must preserve" | Q2 event coverage | **wrong** | No `Other` block in `message-types.md`, `json.md`, or source (`packages/agent/src/types.ts`, `packages/ai/src/types.ts`). What exists: `CustomMessage` role + "tolerate unknown custom roles" (`message-types.md:263-276`), unknown-`kind` tolerance (`session-format.md:121`). Underlying point stands; the `Other`-variant attribution does not. |
| "No approval before every tool call" | Q3 | confirmed | `security.md:3`, verbatim quote |
| `tool_call` may mutate `event.input`; returns `{block, reason}`; handler failure fail-safe | Q3/Q6 | confirmed | `extensions.md:106,170-176,261-263`; source `types.ts:1250-1265` (`ToolCallEvent` union), `:1454-1463` (`ToolCallEventResult`) |
| `extension_ui_request/_response` confirm shapes; timeout auto-resolve | Q3/design §5 | confirmed | `rpc-extension-ui.md:7-10,48-63,174-193` |
| `SessionManager` authoritative for finalized context | Q3 | confirmed | `sdk.md:38-40`, verbatim |
| Four modes share agent/sessions; `RpcClient`; "SDK is not a CLI mode" | Q1 | confirmed | `cli-integration.md:3-16,72` |
| `stopReason` terminal enum | Q3 | confirmed | `message-types.md:134` (all 7 values match) |
| MIT license, package + repo | Sources header | confirmed | package.json `license: MIT`; `LICENSE` in pre-clone |
| C2 identity/cursor/resume evidence | C2 | confirmed | `exp_c2.py` + `c2.out`: `sessionId: expc2`, leaf `e654451f`, resume `messageCount: 5`, `since` returns exactly 2 new entries |
| C3 deny + allow evidence | C3 | confirmed | `exp_c3.py` + `c3.out` + `perm_ext.ts`: deny → `isError=True` "blocked by policy extension"; allow → file contents returned |
| C1 lifecycle | C1 | confirmed | Retained `exp-c/rpc_smoke.py` + **independent re-run 2026-10-17**: `started → agent_start → turn_start → message_start/end → deltas → turn_end → agent_end → agent_settled` reproduced with one smoke prompt (120s timeout, `--no-session --no-tools`) |

## Label-hygiene findings

- The `Other`-variant sub-claim sits inside a paragraph labelled **Verified fact (event coverage)** — a wrong claim under a Verified label. Downgrade to Inference or drop; the adjacent `thinkingSignature`/`textSignature` sentence is correctly Verified.
- Otherwise clean: Q5's Kilo-loss mechanism is honestly labelled **Inference (high confidence)**; cross-runtime impossibility is Inference with a stated falsifier; mid-turn adapter death is an **Open question**, not a pass. C1/C2/C3 observations carry exact commands and outputs.

## Distinction violations

- None. The artifact respects Plan.md's distinctions throughout: continuation is scoped to *Pi resuming its own session* (C2), cross-runtime replay is declared "impossible in general," turn-boundary handoff is future work, and active-turn migration is never claimed.

## Cross-consistency notes

- **Agreement:** E's entity map (`2026-10-16-workstream-e-architecture.md:67-70`) cites the same Pi primitives (`--session-id`, `get_entries`, `agent_settled`→idle at `:159`, `tool_call`/`confirm` inside Pi at `:302`) — no conflict with C's capability/contract tables.
- **Agreement:** E's abort mapping (`:165`, `agent_settled {aborted:true}`) is consistent with C; neither verified the `aborted:true` flag experimentally — shared gap, see below.
- **Pointer:** E's open Q4 (`:432`, does Pi accept `ses_…` verbatim?) is nearly closed by C's citations: `cli.md:92-107` allows letters/numbers/`._-` with alnum endpoints, which `ses_…` satisfies — but no experiment has actually passed a `ses_`-prefixed id. One cheap check closes it.

## Recommendation assessment

- **Entailed.** RPC-over-stdio + adapter extension follows directly from verified docs and three reproduced experiments; the "no Pi core changes" scope is bounded to the demonstrated paths and the artifact says so. Falsifier that would break it: a Kilo need (e.g. tool listing, atomic multi-command transaction) provably unservable over RPC *and* the extension bridge — the artifact's own OQ2 (`list tools`) is the nearest live candidate.
- **Caveat for synthesis:** the SDK half of the recommendation (`RpcClient`/in-process) is docs-only — never exercised. Treat "RPC preferred, SDK if Node host" as Recommendation, not fact.

## License/status corrections

- None. MIT (both), 1.3.0, SHA `8efd314`, repo-rename note — all confirmed with dated evidence above.

## Gaps for synthesis

1. **SDK path unexercised** — verify `SessionManager` binding + event parity before Phase 1 commits to it; closes by running one SDK session against the same C1/C2 script shape.
2. **`ses_…` id verbatim** — one `--session-id ses_test01` spawn closes E's OQ4 and C's binding claim for real Kilo ids.
3. **Mid-turn adapter death** — the stated falsification target (invariant 5): kill adapter mid-turn, resume from session file, check for lost deltas vs duplicated tool calls. Owned by F's test plan.
4. **Dual-open of one session file** — ownership/conflict behavior untested; Kilo-side ownership concern (C OQ3).
5. **`handled`-disposition + abort branches** — adapter must branch on `disposition` (C OQ4) and map `agent_settled {aborted:true}`; needs a test with an extension-consumed prompt and an abort.
6. **Tool reporting channel** — RPC has no `list tools` (verified absent from `rpc-commands.md` command list); the extension-as-reporter path is sketched, not built. Phase-1 design item.
