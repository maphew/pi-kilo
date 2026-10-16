# Workstream F — Independent falsification and test design

- Bead: `pi-kilo-hyj.6`
- Date: 2026-10-16 (UTC)
- Status: open — research not started
- Owner: unassigned (claim `pi-kilo-hyj.6` before editing this file)

Challenge the design; do not merely validate it. Stay independent from
workstreams A–E: derive failure scenarios from the invariants and the
Plan.md threat list, not from their intermediate conclusions.

## Threats to investigate (from Plan.md)

- [ ] Can the existing Kilo UI represent an external session at all?
- [ ] Can session identity be shared without violating runtime assumptions?
- [ ] Can message sync create duplicate turns?
- [ ] Can Kilo accidentally execute work for a Pi-owned session?
- [ ] Can tool events be lost or reordered?
- [ ] Can reconnect replay side effects?
- [ ] Do permissions remain enforced by the executing runtime?
- [ ] Does cloud support depend on private APIs or inaccessible prod infra?

## Falsification experiment

_tbd — smallest experiment that can disprove the preferred
architecture before significant implementation. Exact setup, steps,
expected-vs-falsifying outcomes._

## Test plan

_tbd — event mapping, messaging, reconnection, deduplication,
ownership, failure handling. Local-only where possible; no prod
credentials required for the basic architecture proof._

## Go / no-go recommendation

_tbd — independent of A–E's optimism. State what would change the verdict._
