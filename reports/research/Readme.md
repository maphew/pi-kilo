# Research artifacts — Phase 0

Scope: `pi-kilo-hyj` epic, Phase 0 read-only research. No full connector
implementation. No external publish, upstream PR, merge, or production
writes without explicit user approval (Plan.md).

## Where to write

All Phase 0 artifacts live under `reports/research/`. Convention:

```
reports/research/YYYY-MM-DD-<topic>.md
```

Use lowercase-hyphenated topics. Top-level `Readme.md` (this file) and
`evidence-ledger.md` are shared. Everything else is single-owner.

## File ownership (one implementation owner per file)

| Workstream | Bead | Owner file |
|---|---|---|
| A — Kilo local + Remote Connections | `pi-kilo-hyj.1` | `2026-10-16-workstream-a-kilo-local.md` |
| B — Kilo Cloud + hosted sessions | `pi-kilo-hyj.2` | `2026-10-16-workstream-b-kilo-cloud.md` |
| C — Pi runtime integration | `pi-kilo-hyj.3` | `2026-10-16-workstream-c-pi-runtime.md` |
| D — Prior art + protocol reuse | `pi-kilo-hyj.4` | `2026-10-16-workstream-d-prior-art.md` |
| E — Architecture + session semantics | `pi-kilo-hyj.5` | `2026-10-16-workstream-e-architecture.md` |
| F — Falsification + test design | `pi-kilo-hyj.6` | `2026-10-16-workstream-f-falsification.md` |
| Synthesis — ADR + go/no-go | `pi-kilo-hyj.8` | `2026-10-16-phase0-synthesis.md` |
| Shared ledger | — | `evidence-ledger.md` (append-only entries, link from bead) |

Do not edit another workstream's file. If you need its claims, cite the
file + commit SHA. Cross-cutting corrections go in the synthesis bead,
not by editing in place.

## Evidence labels (required on every material claim)

- **Verified fact:** confirmed in current source code, official docs, or a
  reproducible test. Cite exact repo path + symbol + commit/line, or doc URL
  + retrieval date.
- **Observed behavior:** demonstrated experimentally. Give exact steps,
  commands, and results.
- **Source claim:** a repo/README/vendor asserts it; you have not
  independently verified it. Name the source and date.
- **Inference:** plausible interpretation, not yet verified. Say what would
  verify or falsify it.
- **Recommendation:** proposed decision from available evidence.
- **Open question:** blocker or uncertainty needing investigation.

Prefer source code and tests over README descriptions. For code/API/
protocol questions use source, official docs, specs, versioned tests.
Record retrieval date + version/commit for every external repo examined.

## Freshness

External repos move fast. Every artifact header must state:

- Date of investigation (UTC)
- Commit SHA or release examined for each repo
- Retrieval date for each doc URL

Recheck time-sensitive claims at handoff.

## Required distinctions (Plan.md)

Keep these separate in every document:

- History access vs bidirectional messaging vs continuation vs
  turn-boundary handoff vs active-turn migration (out of scope unless an
  existing reliable mechanism is found).

A shared transcript is not proof of runtime-state migration. Tool state,
hidden reasoning, provider metadata, pending approvals, filesystem changes,
and runtime config may not be portable.

## Product invariants (must hold in any recommendation)

1. Shared logical identity 2. Shared history 3. Real continuation
4. Explicit execution ownership 5. No duplicate side effects
6. Native runtime preservation 7. Local-first operation
8. Honest capability boundaries 9. Security 10. Upstream viability
(see Plan.md for full text).

## Security notes for researchers

- Never expose an unauthenticated local control server to the network.
- Do not log API keys, credentials, private prompts, sensitive tool output.
- Keep tool authorization in the executing runtime.
- Note any step that would bypass permission checks — fail visibly.

## Branch / worktree policy

- Read-only research: work in place on `main`, one file per owner.
  No branches needed unless two writers must touch the same file.
- Prototype phases (gated, not started): use a branch or worktree per
  implementation owner. Never publish branches or open upstream PRs
  without explicit user approval.
