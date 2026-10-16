# Workstream E — Architecture and session semantics

- Bead: `pi-kilo-hyj.5`
- Date: 2026-10-16 (UTC)
- Status: open — research not started
- Owner: unassigned (claim `pi-kilo-hyj.5` before editing this file)

Design the smallest architecture satisfying the 10 product invariants.
Check whether existing systems already represent these concepts before
creating duplicate abstractions.

## Conceptual entities

- **Project:** shared working context incl. repo/workspace identity.
- **Logical session:** conversation identity visible across interfaces.
- **Runtime instance:** a particular running Pi or Kilo process.
- **Turn:** unit of work initiated by an authorized actor.
- **Event:** durable or transient observation on a session.
- **Execution owner:** runtime authorized to execute the current turn.

_tbd — map each to existing Kilo/Pi representations or mark as new._

## Event model

Must consider: user messages; assistant output + streaming updates;
tool calls/results/errors; turn start/complete/interrupt/fail;
permission requests/decisions; runtime status/capabilities; session
metadata/rename; connection loss/reconnect; ownership/handoff;
unsupported/runtime-specific payloads.

Requirements: stable event identity, deterministic ordering where
needed, idempotent processing, explicit partial-vs-completed
treatment. Preserve native/unknown payloads where practical.

_tbd — event mapping table._

## Session lifecycle

_tbd — diagram (ASCII) + ownership/handoff rules. Keep history access
vs bidi messaging vs continuation vs turn-boundary handoff vs
active-turn migration (out of scope) distinct._

## Unsupported cases

_tbd — explicit list._

## ADR (draft)

_tbd — decision, alternatives rejected with reasons. Final ADR lives
in the synthesis artifact; this is E's input to it._
