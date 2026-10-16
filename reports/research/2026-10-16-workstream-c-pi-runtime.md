# Workstream C — Pi runtime integration

- Bead: `pi-kilo-hyj.3`
- Date: 2026-10-16 (UTC)
- Status: open — research not started
- Owner: unassigned (claim `pi-kilo-hyj.3` before editing this file)

## Repos examined

| Repo | Commit / release | Retrieved |
|---|---|---|
| https://github.com/badlogic/pi-mono | _tbd_ | _tbd_ |
| https://pi.dev/docs/latest/cli-integration | _tbd_ | _tbd_ |

Record license before proposing dependencies or copying code. Prefer
structured APIs over terminal scraping or fragile parsing.

## Questions (from Plan.md)

- [ ] Most reliable supported way to observe Pi events and send messages?
- [ ] Can RPC or SDK expose all info needed for a faithful shared history?
- [ ] How are tool calls, results, errors, approvals, session resumes represented?
- [ ] How are session IDs and session files managed?
- [ ] What happens when the Kilo connection disappears mid-turn?
- [ ] Can the adapter operate without modifying Pi core?
- [ ] What runtime capabilities can be reported accurately to Kilo?

## Findings

_tbd — label every material claim._

## Minimal adapter design

_tbd — boundary, no Pi core modifications if possible, capability
reporting, disconnect behavior._

## Local experiment

_tbd — working experiment that observes a Pi session and sends it a
message programmatically. Exact commands + results (Observed behavior).
Must work without production credentials._

## Open questions

_tbd_
