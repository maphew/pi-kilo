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

### 2026-10-16 — Kilo Remote Connections is outbound-relay, CLI executes in-process
- Label: Verified fact
- Bead: pi-kilo-hyj.1
- Artifact: reports/research/2026-10-16-workstream-a-kilo-local.md#q2 @ 1552877e82ceaecc79a9fd4be7859518745e6f56
- Evidence: packages/opencode/src/kilo-sessions/kilo-sessions.ts enableRemote (~L979-1010); remote-ws.ts L422-441 (wss://ingest.kilosessions.ai/api/user/cli?token); RemoteSender.create in-process seams L1185-1235
- Status: open

### 2026-10-16 — send_message executes Kilo prompt loop; no external-executor mode
- Label: Verified fact
- Bead: pi-kilo-hyj.1
- Artifact: reports/research/2026-10-16-workstream-a-kilo-local.md#q3 @ 1552877e82ceaecc79a9fd4be7859518745e6f56
- Evidence: packages/opencode/src/kilo-sessions/remote-sender.ts L1280-1324 (send_message→SessionPrompt.prompt); session/prompt.ts L1444; 16-command dispatch L750-1520
- Status: open

### 2026-10-16 — Session import (Claude/Codex/cloud-clone) is transcript copy, not live
- Label: Verified fact
- Bead: pi-kilo-hyj.1
- Artifact: reports/research/2026-10-16-workstream-a-kilo-local.md#q1 @ 1552877e82ceaecc79a9fd4be7859518745e6f56
- Evidence: packages/opencode/src/kilocode/session-resume/import.ts IMPORT_NOTICE L849; import-cloud-session-in-process.ts L62-175
- Status: open

### 2026-10-16 — Local HTTP API + SSE is best external-runtime reuse candidate
- Label: Inference
- Bead: pi-kilo-hyj.1
- Artifact: reports/research/2026-10-16-workstream-a-kilo-local.md#q4 @ 1552877e82ceaecc79a9fd4be7859518745e6f56
- Evidence: server/routes/instance/httpapi/groups/session.ts (prompt/prompt_async), event.ts (SSE), auth.ts (Basic); used by kilo attach today. Needs C/F runtime experiment to verify.
- Status: open

### 2026-10-16 — Smallest extension: executor advertisement + forward_message branch
- Label: Recommendation
- Bead: pi-kilo-hyj.1
- Artifact: reports/research/2026-10-16-workstream-a-kilo-local.md#q7 @ 1552877e82ceaecc79a9fd4be7859518745e6f56
- Evidence: RemoteProtocol.SessionInfo/InstanceAdvertisement extension precedent (optional fields); AttachedState presence model; needs Workstream B relay-opacity answer
- Status: open
