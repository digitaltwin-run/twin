# Ticket 001: Standardize and generate language-neutral Twin v1

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-08-11

## Goal and scope

Create Twin Standard v1 as a language-neutral, protobuf-first CQRS/Event Sourcing contract that also standardizes URI-addressed capabilities and multi-step URI Processes. Generate a portable reference bundle from one validated profile; before publishing output, reject invalid operations, routes, process graphs, replay behavior, authority, evidence, connector or transport intent with stable diagnostics and leave no partial destination.

## Acceptance criteria

- [x] AC-01: Verify through the normative specification and negative unit tests that aggregates, commands, immutable events, queries, rebuildable projections, observations, evidence, receipts, outbox, connector boundaries, authority and replay safety are enforced.
- [x] AC-02: Verify with the reference validator that one stable proto3 contract declares every canonical envelope, operation message and required service used by the profile.
- [x] AC-03: Verify with coverage tests that the reference profile contains reconciliation, mirror, invariant, simulation, preflight verification, notification, outbox and probe traits and binds every operation exactly once to CLI, shell, REST and MCP.
- [x] AC-04: Verify with mutation tests that incomplete transports, mixed CQRS duties, connector-owned domain mutation, unsafe shell, incomplete event metadata, replay effects and invalid traits fail with stable `TWIN-*` diagnostics.
- [x] AC-05: Verify by generating two fresh bundles that any safe language identifier produces byte-identical manifest, protobuf, transport-map and conformance files; if the profile is invalid or destination exists, reject before publishing and preserve existing data.
- [x] AC-06: Verify by host tests, a networkless Docker run and governance base/head validation that the delivery has zero runtime dependencies and exactly five implementation files.
- [x] AC-07: Verify that every capability operation has one canonical URI whose query/command effect agrees with CQRS, and that reviewed baseline plus live discovery resolves only concrete connector routes or an explicit typed gap.
- [x] AC-08: Verify that URI Process definitions have immutable IDs, acyclic step dependencies, pinned capability-map resolution, timeouts, retries, failure policy, per-step idempotency/receipts, external authority for effects and replay-safe run states including human-task request/resolve/decline/cancel.

## Risks and boundaries

- Require MCP to remain native JSON-RPC and map messages through ProtoJSON at the adapter boundary; reject any claim that MCP itself is protobuf binary transport.
- Require shell support to use argv-only process calls and reject evaluation, interpolation and shell metacharacters.
- Treat “all traits” as independently composable capabilities, not a forced monolith.
- Treat exported provider snapshots as fingerprinted provenance inputs, not authoritative git histories.
- Treat actor/persona twins as identity and competency descriptions only; reject any model in which impersonation, an LLM verdict or a declared grant creates effective authority.

## Participants

- Human participant: the requesting user, represented by the conversation;
  no synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md)
