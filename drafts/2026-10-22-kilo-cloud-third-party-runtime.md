# Draft issue — Kilo-Org/cloud

Target repo: `Kilo-Org/cloud` (the session list and relay live there; if you'd
rather this sat in `kilocode`, say so and I'll move it).

---

**Title:** Third-party runtime in the cloud session list: Pi proof-of-concept + one design question

**Body:**

I've been building a Pi adapter for Kilo Cloud sessions — Pi
(`earendil-works/pi`, MIT) as a second runtime that can pick up the same
sessions the Kilo CLI produces. It works well enough to show, so here's the
state of it and one question about the session list.

**What works today, with no Kilo changes**

- `pi-kilo ses_...` fetches the cloud export from `ingest.kilosessions.ai`
  using the user's own Kilo OAuth token — the same endpoint
  `kilo --session ... --cloud-fork` uses — converts the transcript to Pi's
  session format, and continues it locally. Verified on real sessions,
  including compaction summaries and forked/branched exports.
- The result is an ordinary Pi session: shows up in `/resume`, Pi's tools,
  permissions and extensions behave as Pi. It's history import plus local
  continuation, not live sharing.
- Separate local harness: a Kilo-routed message executed by Pi over Pi RPC,
  with a single-owner guard and message-id dedupe.

Reading side (Pi consumes Kilo sessions) works with no backend change.

**The gap**

The session list can't represent a runtime that isn't `cli` or `remote`. From
reading the code:

1. `instance.kind` is a closed `cli|remote` set — nowhere to say "this session
   is owned by a third-party runtime", and no field the list can render.
2. "No live heartbeat" means "not in the list", so an offline external owner's
   row disappears.
3. `sessionOwners` / `handleHeartbeat` is last-heartbeat-wins: two connections
   can claim one session id and both think they own it. Kilo CLI rarely
   collides by luck; Pi collides by construction, because the adapter supplies
   the session id.
4. `ALLOWED_VIEWER_COMMANDS` has no way to forward a viewer message to a
   non-Kilo runtime.

**Questions**

- Is a third-party runtime kind in the session list something you want, or is
  Remote Connections meant to stay Kilo-CLI-only?
- If yes, is the minimal shape right: runtime kind on the instance/heartbeat,
  keep offline rows, single-owner lease with fencing token, `forward_message`
  beside `send_message`?
- Where should it land? I've read `cloud` (OCVSAL) and `kilocode`, but I don't
  know which side you'd want a change like this on, or whether it should be a
  PR from outside at all.

I'm not asking you to adopt or endorse Pi — it's a client, and the point is
just that the session layer turns out to be runtime-agnostic in practice.
Adapter outside your codebase is a fine answer too.

Code and notes: https://github.com/maphew/pi-kilo (`prototype/`,
`reports/research/`).
