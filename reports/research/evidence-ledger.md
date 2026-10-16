# Shared evidence ledger — Phase 0

Append-only. Each entry links to its bead and artifact. Newest entries at
the bottom. Do not rewrite history; supersede with a new entry when a
claim is falsified.

Labels: **Verified fact** · **Observed behavior** · **Source claim** ·
**Inference** · **Recommendation** · **Open question**

## Format

```
### YYYY-MM-DD — <short claim>
- Label: <one of the above>
- Bead: <id>
- Artifact: reports/research/<file>#<section> @ <commit SHA>
- Evidence: <repo path/symbol/doc URL+retrieval date/repro steps>
- Status: open | confirmed | superseded by <entry>
```

## Entries

### 2026-10-16 — Ledger and artifact convention created
- Label: Recommendation
- Bead: pi-kilo-hyj.7
- Artifact: reports/research/Readme.md
- Evidence: Plan.md swarm coordination + evidence standards section; research-to-artifact skill
- Status: open
