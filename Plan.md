# Project Brief: Kilo External Runtime Integration — Pi Prototype

## Mission

Investigate, design, and prototype integration of the Pi coding agent with Kilo’s shared project/session experience, so a user can move between Pi, Kilo CLI, and Kilo Cloud without losing the continuity of their work.

The desired experience is that `app.kilo.ai` does not fundamentally care which compatible runtime is executing a session. The interface should show the shared conversation, and messages should reach whichever runtime currently owns execution.

This must be real runtime interoperability, not merely exporting a transcript or displaying a read-only copy of another agent’s session.

**Primary question:** Can Pi become an external runtime for Kilo’s existing session infrastructure through a relatively small adapter, or does Kilo need changes to its session, persistence, or ownership model?

## Repositories and prior art

Start with these repositories and projects. Verify their current state, implementation details, and license before proposing dependencies or copying code.

### Kilo

- Kilo Code: https://github.com/Kilo-Org/kilocode
- Kilo Cloud: https://github.com/Kilo-Org/cloud
- Kilo Pi provider: https://github.com/Kilo-Org/kilo-pi-provider

Investigate Kilo’s existing Remote Connections implementation, session lifecycle, persistence model, event transport, cloud session architecture, and agent/runtime boundaries.

Kilo documents session import from other coding agents and remote interaction with local CLI sessions. Determine exactly what these capabilities support today, and whether they offer reusable interfaces for an external runtime.

Do not assume that a session-import implementation can also support live, bidirectional runtime integration.

### Pi

- Pi monorepo: https://github.com/badlogic/pi-mono
- Pi CLI integration documentation: https://pi.dev/docs/latest/cli-integration

Investigate Pi’s RPC interface, SDK, extension API, session storage, event model, tool execution, permission handling, and resume behavior.

Prefer structured APIs over terminal scraping or fragile parsing of human-oriented output.

### Agent Client Protocol (ACP)

- Website: https://agentclientprotocol.com/
- Specification and implementation: https://github.com/agentclientprotocol/agent-client-protocol

ACP is a potential standard interface between a coding agent and its client, including session operations, prompts, streaming updates, and permission requests.

Determine whether ACP can serve as the Pi adapter boundary, whether Pi has a suitable implementation or would require an adapter, and whether Kilo can consume ACP-compatible agents without substantial changes.

ACP is not automatically a solution for shared Kilo session identity, persistence, or cross-runtime continuation. Verify those separately.

### Agent Session Protocol / Universal Session Log (ASP/USL)

- Documentation: https://agent-session-protocol.github.io/docs
- Project organization: https://github.com/agent-session-protocol

Investigate the project’s goals, implementation maturity, data model, event semantics, conversion support, licensing, and adoption.

Its focus on portable agent-session history may overlap with the session/event model this project would otherwise invent. Determine whether it is mature and suitable enough to reuse, or whether it is only a useful conceptual reference.

Verify the current project names, repositories, and status before relying on them.

### OpenHands

- Repository: https://github.com/All-Hands-AI/OpenHands

Investigate its integration of external agents, including ACP, as an example of separating the host application from the agent runtime. Focus on concrete implementation lessons rather than adopting OpenHands wholesale.

### OpenTelemetry

- Project: https://opentelemetry.io/
- Semantic conventions: https://opentelemetry.io/docs/specs/semconv/

Consider its structured event and tracing practices where useful. Do not confuse observability with durable session history, session identity, or runtime control. OpenTelemetry is not a substitute for the session protocol.

## Product invariants

Any proposed architecture must preserve the following.

1. **Shared logical identity.** Pi and Kilo should be able to refer to the same logical project and conversation, rather than maintaining unrelated sessions that happen to display similar text.
2. **Shared history.** User messages, assistant responses, tool activity, errors, and relevant metadata should remain available across interfaces.
3. **Real continuation.** A message sent from Kilo to a Pi-owned session must reach Pi and be executed by Pi. It must not silently create a separate Kilo conversation.
4. **Explicit execution ownership.** At any moment, it must be clear which runtime is authorized to execute a turn.
5. **No duplicate side effects.** Reconnects, retries, replay, or handoff must not accidentally repeat tool calls or other consequential actions.
6. **Native runtime preservation.** Pi should continue to behave like Pi, with its existing tools, extensions, permissions, configuration, and model/provider support. Kilo should retain its own native behavior.
7. **Local-first operation.** Pi must continue to work locally when the Kilo connection is unavailable. Integration must not require routing all local execution through an external service.
8. **Honest capability boundaries.** Do not claim that transcript synchronization provides runtime-state migration or that a runtime can resume another runtime’s private state.
9. **Security.** No unauthenticated control endpoint, exposed credentials, unintended command execution, or permission bypass.
10. **Upstream viability.** Prefer a small, well-separated adapter and a narrowly scoped Kilo extension over a large fork or permanent synchronization sidecar.

## Essential conceptual distinction

Keep these capabilities separate in all research and design documents.

- **History access:** A UI can display events produced by another runtime.
- **Bidirectional messaging:** The UI can send messages to that runtime, and observe the results.
- **Continuation:** A runtime can resume its own session with its existing context and behavior.
- **Turn-boundary handoff:** One runtime finishes a turn; another takes ownership and continues from a shared, sufficiently complete history.
- **Active-turn migration:** Another runtime takes over an in-progress turn, including tool execution, permissions, and any necessary internal state.

The prototype should target history access and bidirectional messaging first, then continuation and safe turn-boundary handoff. Active-turn migration is explicitly out of scope unless research reveals an existing, reliable mechanism that makes it inexpensive.

A shared transcript is not necessarily a sufficient context for another runtime. Tool state, hidden reasoning, provider-specific metadata, pending approvals, filesystem changes, and runtime configuration may not be portable.

## Swarm structure

Assign independent agents to the following workstreams. Each should produce evidence and a recommendation, not just a list of possibilities.

### Workstream A — Kilo local runtime and Remote Connections

**Questions**

- How does Kilo CLI create, identify, persist, and resume a session?
- How does Remote Connections attach a web interface to a running local session?
- What messages, events, permissions, and tool activity can cross that boundary?
- Is the transport or session API reusable by an external runtime?
- What assumptions couple the interface to Kilo’s own runtime?
- Can an external runtime be registered without impersonating a Kilo agent?
- What is the smallest Kilo-side change that would enable a genuine external session?

**Deliverable:** A code-path map with concrete file/function references, the existing integration contract, and a recommendation for the smallest extension point.

### Workstream B — Kilo Cloud and hosted sessions

**Questions**

- How are projects, conversations, messages, events, and runtime instances represented?
- What is the source of truth for session history?
- Does a cloud session require a Kilo-managed execution environment?
- Can an external local runtime attach to an existing cloud-visible session?
- Which transport, authentication, and reconnect mechanisms are already available?
- What would need to change to represent execution owned by Pi?
- Can the web interface distinguish an offline, disconnected, busy, or locally owned runtime?

**Deliverable:** A cloud architecture map, identification of hard coupling, and a feasibility assessment for supporting external runtimes.

Do not assume that the presence of a session-oriented API or event log means third-party runtime integration is supported.

### Workstream C — Pi runtime integration

**Questions**

- What is the most reliable supported way to observe Pi events and send it messages?
- Can RPC or the SDK expose all information needed for a faithful shared history?
- How are tool calls, tool results, errors, approvals, and session resumes represented?
- How are session IDs and session files managed?
- What happens when the Kilo connection disappears during a turn?
- Can the adapter operate without modifying Pi core?
- What runtime capabilities can be reported accurately to Kilo?

**Deliverable:** A minimal Pi adapter design and a working local experiment that observes a Pi session and sends it a message programmatically.

### Workstream D — Prior art and protocol reuse

This is a required research track, not optional background reading.

Evaluate the projects listed above against the actual requirements. Add other relevant implementations if discovered.

For each candidate, assess:

- Is it a specification, a working implementation, or a product-specific convention?
- Does it support live bidirectional control, or only history import/export?
- Does it model session identity, event ordering, replay, and continuation?
- Does it handle permissions, tool calls, errors, and partial/streaming events?
- Does it address runtime ownership and reconnects?
- Can it be adopted incrementally without forcing Pi or Kilo to abandon native behavior?
- What is its license, maintenance status, maturity, and compatibility with the target codebases?

Explicitly compare three approaches:

1. Reuse Kilo’s existing internal interfaces directly.
2. Use an existing cross-agent protocol such as ACP, with a Kilo adapter if needed.
3. Define a minimal project-specific event/transport contract.

Do not build a new protocol merely because it seems cleaner. Equally, do not force a general-purpose standard into a role it does not support.

**Deliverable:** A comparison matrix, evidence-backed recommendation, and a list of protocol concepts that genuinely need to be defined by this project.

### Workstream E — Architecture and session semantics

Independently design the smallest architecture satisfying the invariants.

Use these conceptual entities, adjusting them to match existing implementations:

- **Project:** The shared working context, including its repository/workspace identity.
- **Logical session:** The conversation identity visible to the user across interfaces.
- **Runtime instance:** A particular running Pi or Kilo process.
- **Turn:** A unit of work initiated by a user or other authorized actor.
- **Event:** A durable or transient observation associated with a session.
- **Execution owner:** The runtime authorized to execute the current turn.

Investigate whether the existing system already represents these concepts and can be extended. Do not create duplicate abstractions unnecessarily.

The event model may need to represent:

- User messages
- Assistant output and streaming updates
- Tool calls, results, and errors
- Turn start, completion, interruption, and failure
- Permission requests and decisions
- Runtime status and capabilities
- Session metadata and rename operations
- Connection loss and reconnection
- Execution ownership and handoff
- Unsupported or runtime-specific event payloads

Requirements include stable event identity, deterministic ordering where needed, idempotent processing, and explicit treatment of partial versus completed events.

Preserve native or unknown event payloads when practical instead of silently discarding them.

**Deliverable:** An architecture decision record (ADR), session lifecycle diagram, event mapping, and explicit list of unsupported cases.

### Workstream F — Independent falsification and test design

This agent must challenge the proposed design rather than simply validate it.

Investigate:

- Whether the existing Kilo UI can represent an external session at all
- Whether session identity can be shared without violating assumptions in either runtime
- Whether message synchronization can create duplicate turns
- Whether Kilo can accidentally execute work for a Pi-owned session
- Whether tool events can be lost or reordered
- Whether reconnecting can replay side effects
- Whether permissions remain enforced by the runtime that actually executes the tool
- Whether cloud support depends on private APIs or inaccessible production infrastructure

Design a small falsification experiment that can disprove the preferred architecture before significant implementation work.

**Deliverable:** A test plan, failure scenarios, and a go/no-go recommendation.

## Implementation plan

Implementation is gated on the research findings. Do not commit to a large rewrite before the first architecture review.

### Phase 0 — Research and architecture decision

Complete the workstreams above. The swarm lead consolidates findings and recommends:

- The smallest viable integration boundary
- The prior art to reuse
- The minimum Kilo changes required
- The minimum Pi adapter required
- Which parts can be tested locally without production credentials
- What remains unproven

Present the recommendation before starting broad implementation.

### Phase 1 — Minimal vertical slice

Prove that an actual Pi session can appear in the actual Kilo session/project experience.

Minimum requirements:

1. Start Pi locally in a project.
2. Register or associate its logical session with Kilo through a legitimate integration path.
3. Display its conversation in Kilo’s interface.
4. Send a message from Kilo to the Pi-owned session.
5. Verify that Pi, not a parallel Kilo runtime, receives and executes the message.
6. Display the response and relevant activity.
7. Reconnect without duplicating events or turns.
8. Disconnect Kilo and verify that Pi continues working locally.

Use test fixtures and local infrastructure wherever possible. Do not require production credentials merely to demonstrate the basic architecture.

If the real Kilo interface cannot be extended without substantial changes, build a minimal local harness for the Pi adapter while clearly labelling it as a harness—not proof of Kilo integration.

### Phase 2 — Continuation and safe handoff

Demonstrate:

1. Start a conversation in Kilo CLI.
2. Continue it using Pi, preserving the logical session identity and a usable history.
3. Continue again using Kilo CLI.
4. Verify that the next runtime has sufficient context to behave coherently.
5. Confirm that only the authorized runtime executes each turn.

Be explicit about which data is preserved and which runtime-specific state cannot migrate.

### Phase 3 — Cloud feasibility and integration

Test whether the same logical session can be represented and continued through `app.kilo.ai` and Kilo Cloud.

Do not fake cloud integration by copying transcript text into an unrelated session. If the existing architecture cannot support the desired semantics without meaningful changes, document the required upstream changes and provide a working local proof of concept separately.

### Phase 4 — Hardening and upstream proposal

Add appropriate tests and address:

- Authentication and authorization
- Workspace/session isolation
- Event deduplication and ordering
- Reconnect and interruption behavior
- Execution ownership and conflict prevention
- Permission handling
- Secret redaction
- Unsupported event types
- Failure recovery and useful diagnostics

Prepare a small, reviewable upstream proposal with evidence that the design works.

## Security and reliability requirements

- Never expose an unauthenticated local control server to the network.
- Do not log API keys, credentials, private prompts, or sensitive tool output unnecessarily.
- Validate incoming messages and commands at the adapter boundary.
- Keep tool authorization in the runtime responsible for execution.
- Do not let the web UI bypass local runtime permission checks.
- Prevent two runtimes from believing they simultaneously own the same turn.
- Define what happens when ownership expires, a process crashes, or a network connection drops.
- Use stable event IDs and idempotent writes where supported.
- Make retries distinguishable from new user requests.
- Do not claim exactly-once tool execution unless it can actually be guaranteed.
- Fail visibly and safely when synchronization or ownership is uncertain.

## Swarm coordination and evidence standards

Maintain a shared evidence ledger with the following labels:

- **Verified fact:** Confirmed in current source code, official documentation, or a reproducible test.
- **Observed behavior:** Demonstrated experimentally, with steps and results.
- **Inference:** Plausible interpretation not yet verified.
- **Recommendation:** Proposed decision based on the available evidence.
- **Open question:** A blocker or uncertainty requiring further investigation.

Cite exact repository paths, symbols, relevant documentation, and reproduction steps. For architectural claims, prefer source code and tests over README descriptions alone.

Each workstream should own its research artifacts. Assign one implementation owner per file or module to minimize conflicting edits. Use separate worktrees or branches where helpful.

Do not publish branches, open upstream pull requests, merge, or otherwise make external changes without explicit user approval.

## Deliverables

1. **Research report** — existing interfaces, code paths, prior art, and verified limitations.
2. **Prior-art matrix** — Kilo Remote Connections, ACP, Pi RPC/SDK, ASP/USL, OpenHands, and other relevant candidates.
3. **Architecture decision record** — chosen integration boundary and alternatives rejected with reasons.
4. **Protocol/event mapping** — only where existing interfaces do not already provide what is needed.
5. **Prototype** — a working minimal integration with setup and teardown instructions.
6. **Automated tests** — event mapping, messaging, reconnection, deduplication, ownership, and failure handling.
7. **Demo script** — reproducible steps showing the real behavior.
8. **Cloud feasibility report** — what works, what requires changes, and what remains unsupported.
9. **Upstream plan** — smallest proposed changes, likely owners/components, and reviewable implementation sequence.

## Acceptance criteria

The prototype succeeds when a reviewer can:

- Start a Pi session in a project.
- See that logical conversation in the Kilo experience.
- Send a message through Kilo and observe Pi execute it.
- See the response and relevant tool activity.
- Reconnect without duplicating the conversation or re-executing completed work.
- Continue locally when Kilo is disconnected.
- Understand which runtime owns execution at each point.
- Demonstrate a supported turn-boundary handoff between Pi and Kilo CLI, or identify a concrete blocker with evidence.
- Inspect a clear account of which cloud behaviors are implemented versus still hypothetical.

A transcript import alone does not satisfy acceptance.

## First assignment to the swarm lead

Begin with read-only research. Do not start implementing the full connector yet.

Return concise, evidence-backed answers to these questions:

1. What exact Kilo code path creates and maintains a session visible to `app.kilo.ai`?
2. What existing Remote Connections or session interfaces can an external runtime reuse?
3. What Pi interface provides reliable event observation and message control?
4. Can ACP or another existing protocol reduce the amount of custom work?
5. Does ASP/USL offer a sufficiently mature session/event model worth adopting?
6. What is the smallest experiment that proves or falsifies the integration idea?
7. What can be demonstrated locally without production credentials or private APIs?

Conclude with a go/no-go recommendation for Phase 1, the minimum viable architecture, a realistic prototype boundary, and the unresolved risks.

**Guiding principle:** Reuse existing capabilities, preserve native runtime behavior, and prove genuine cross-runtime continuation before investing in a generalized multi-agent protocol.
