# Workstream B — Kilo Cloud and hosted sessions

- Bead: `pi-kilo-hyj.2`
- Date: 2026-10-16 (UTC)
- Status: open — research not started
- Owner: unassigned (claim `pi-kilo-hyj.2` before editing this file)

## Repos examined

| Repo | Commit / release | Retrieved |
|---|---|---|
| https://github.com/Kilo-Org/cloud | _tbd_ | _tbd_ |
| https://github.com/Kilo-Org/kilocode | _tbd_ | _tbd_ |

Record license for each before proposing dependencies or copying code.

## Questions (from Plan.md)

- [ ] How are projects, conversations, messages, events, runtime instances represented?
- [ ] What is the source of truth for session history?
- [ ] Does a cloud session require a Kilo-managed execution environment?
- [ ] Can an external local runtime attach to an existing cloud-visible session?
- [ ] Which transport, authentication, and reconnect mechanisms already exist?
- [ ] What would need to change to represent execution owned by Pi?
- [ ] Can the web interface distinguish offline / disconnected / busy / locally owned runtimes?

## Findings

_tbd — one section per question. Label every material claim:
**Verified fact** / **Observed behavior** / **Source claim** /
**Inference** / **Open question**._

Do not assume a session-oriented API or event log means third-party
runtime integration is supported — verify against source.

## Cloud architecture map

_tbd — projects, conversations, messages, events, runtime instances,
source of truth, transport/auth/reconnect._

## Hard coupling

_tbd — what ties cloud sessions to Kilo-managed execution._

## Feasibility assessment

_tbd — what works for external runtimes today, what needs changes,
what is unknown._
