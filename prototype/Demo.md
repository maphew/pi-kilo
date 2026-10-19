# Phase 1 — Pi as external runtime: demo script

Proves a Kilo-routed message is executed BY PI, with owner guard + dedupe.
Labelled local harness (per Plan.md Phase 1 allowance): the "Kilo" side is
this script, not app.kilo.ai. No prod credentials, no relay, no Cloud.

## Prereqs

- `pi` 1.3.0+ on PATH (or at /home/linuxbrew/.linuxbrew/bin/pi)
- node on PATH (pi is a node script)
- a configured pi provider (this demo used the `kilo` provider)

## Run

```bash
# smoke: route one message to Pi, check owner guard + dedupe + cursor
python3 prototype/pi_adapter.py "Reply with exactly: PONG-HIP-01"

# full: tools executed, permission deny enforced, adapter killed + resumed
python3 prototype/pi_adapter.py --full
```

## Expected output (smoke)

```
OWNER lease held by pi:<token>; kilo claim rejected (held by pi)
PI sessionId=ses_pi_kilo_hip_01 file=/tmp/pi-kilo-hip/sessions/..._ses_pi_kilo_hip_01.jsonl
KILO -> PI [ses_pi_kilo_hip_01]: 'Reply with exactly: PONG-HIP-01'
PI executed, disposition=started
PI response text: 'PONG-HIP-01'
RETRY msg_hip_01 -> deduped, no re-execution
ENTRIES n=5 leaf=<id>
CATCH-UP since=<id> -> 0 new entries
DONE: ...
```

## Expected output (full)

```
OWNER pi holds lease; kilo second-claim rejected
PI sessionId=ses_pi_kilo_hip_tools file=...
ALLOW path: 2 tool events, text='Contents of `/etc/hostname`: ...'
DENY path: 1 tool ends, 1 errored; text='... denied by kilo-gate ...'
ADAPTER killed at leaf=<id>; resuming <session file>
RESUME ok: 0 new entries since <id>; history intact
POST-RESUME text='RESUMED-OK'
DONE-FULL: ...
```

## What this proves (vs Phase 0 invariants)

- Shared logical identity: Pi accepts caller-supplied `--session-id`
  (`ses_pi_kilo_hip_*`), binding record = session file path.
- Real continuation: the routed message is executed by Pi, not a Kilo loop.
- Explicit ownership: second claimant for a live lease is rejected.
- No duplicate side effects: retried message id executes once.
- Native runtime: unmodified pi binary; permissions enforced in Pi
  (write denied by kilo-gate extension, read allowed).
- Local-first: adapter death -> orderly Pi shutdown, session file survives,
  `switch_session` + `get_entries(since)` resumes with history intact.

## Honest boundaries (still unproven)

- Real relay admission of a non-Kilo client (needs Kilo backend change:
  allowlist + owner guard + runtime kind).
- Real UI rendering of an external runtime in app.kilo.ai.
- Cloud Agent path (hosted-only, OCVSAL).
- Turn-boundary handoff Kilo->Pi->Kilo (history rebuild, not state migration).
- Active-turn migration: out of scope.
