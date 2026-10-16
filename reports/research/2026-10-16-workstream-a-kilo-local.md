# Workstream A — Kilo local runtime and Remote Connections

- Bead: `pi-kilo-hyj.1`
- Date: 2026-10-16 (UTC)
- Status: open — research not started
- Owner: unassigned (claim `pi-kilo-hyj.1` before editing this file)

## Repos examined

| Repo | Commit / release | Retrieved |
|---|---|---|
| https://github.com/Kilo-Org/kilocode | _tbd_ | _tbd_ |
| https://github.com/Kilo-Org/kilo-pi-provider | _tbd_ | _tbd_ |

Record license for each before proposing dependencies or copying code.

## Questions (from Plan.md)

- [ ] How does Kilo CLI create, identify, persist, and resume a session?
- [ ] How does Remote Connections attach a web interface to a running local session?
- [ ] What messages, events, permissions, and tool activity can cross that boundary?
- [ ] Is the transport or session API reusable by an external runtime?
- [ ] What assumptions couple the interface to Kilo's own runtime?
- [ ] Can an external runtime be registered without impersonating a Kilo agent?
- [ ] What is the smallest Kilo-side change enabling a genuine external session?

## Findings

_tbd — one section per question. Label every material claim:
**Verified fact** / **Observed behavior** / **Source claim** /
**Inference** / **Open question**. Cite exact file/function/symbol +
commit SHA, or doc URL + retrieval date._

## Code-path map

_tbd — concrete file/function references for: session create →
identify → persist → resume; Remote Connections attach path;
message/event/permission/tool boundary._

## Existing integration contract

_tbd — what the boundary supports today, in current source._

## Recommendation

_tbd — smallest extension point for a genuine external session._

## Open questions

_tbd_
