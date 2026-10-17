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

### 2026-10-17 — Pi RPC mode is the adapter boundary: long-lived JSONL in/out
- Label: Verified fact
- Bead: pi-kilo-hyj.3
- Artifact: reports/research/2026-10-16-workstream-c-pi-runtime.md#q1
- Evidence: docs/cli-integration.md, docs/rpc.md (pi-coding-agent 1.3.0, MIT); reproduced against installed pi 1.3.0
- Status: confirmed

### 2026-10-17 — Pi accepts a caller-supplied session id and resumes it cross-process
- Label: Observed behavior
- Bead: pi-kilo-hyj.3
- Artifact: reports/research/2026-10-16-workstream-c-pi-runtime.md#c2
- Evidence: `pi --mode rpc --session-dir <scratch> --session-id expc2` → get_state sessionId=expc2, sessionFile=..._expc2.jsonl; new process with --session <file> restored 5 messages; get_entries since=<leafId> returned exactly 2 new entries
- Status: confirmed

### 2026-10-17 — Pi tool approvals surface to an external client and are enforced by Pi
- Label: Observed behavior
- Bead: pi-kilo-hyj.3
- Artifact: reports/research/2026-10-16-workstream-c-pi-runtime.md#c3
- Evidence: extension tool_call + ctx.ui.confirm → RPC extension_ui_request(confirm); response confirmed=false → tool_execution_end isError=true "read blocked by policy extension"; confirmed=true → tool executed. docs/security.md: Pi has no built-in per-tool approval. docs/rpc-extension-ui.md defines the subprotocol.
- Status: confirmed

### 2026-10-17 — History fidelity is high but not provider-complete
- Label: Inference
- Bead: pi-kilo-hyj.3
- Artifact: reports/research/2026-10-16-workstream-c-pi-runtime.md#q2
- Evidence: docs/message-types.md — thinkingSignature/textSignature/thoughtSignature are opaque provider metadata; provider_stream_event is notification-only and not persisted. What would verify: attempt replay of a Pi assistant message with opaque signatures into another provider.
- Status: open

### 2026-10-17 — adapter must branch on prompt disposition before awaiting settle
- Label: Inference
- Bead: pi-kilo-hyj.3
- Artifact: reports/research/2026-10-16-workstream-c-pi-runtime.md#q2
- Evidence: docs/rpc.md — disposition "handled" means no run started, so do not wait for agent_settled; "agent_end" is not completion (retries/compaction may follow). What would verify: exercise an extension-command prompt and an auto-retry prompt over RPC.
- Status: open
