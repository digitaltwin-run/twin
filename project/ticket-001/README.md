# Ticket 001: Standardize and generate language-neutral Twin v1

- **ID**: ticket-001
- **Owner**: unresolved:human
- **Status**: PLAN
- **Workflow state**: WAIT_FOR_APPROVAL
- **Created**: 2026-08-11

## Goal and scope

Define Twin Standard v1 as a language-neutral, protobuf-first contract and
generate a portable reference bundle from one validated profile. The standard
unifies CQRS/Event Sourcing, observations, provenance, evidence, receipts,
outbox effects and thin connectors behind CLI, safe-shell, REST and MCP
adapters.

## Acceptance criteria

- [ ] AC-01: The normative contract covers aggregates, commands, immutable
  events, queries, rebuildable projections, observations, evidence, receipts,
  an outbox, connector boundaries, authority and replay safety.
- [ ] AC-02: A stable proto3 contract declares the canonical envelopes and
  services shared by every transport.
- [ ] AC-03: An all-traits profile covers reconciliation, mirror, invariant,
  simulation, preflight verification, notification, outbox and probe behavior;
  every CLI, shell, REST and MCP binding resolves to a declared operation.
- [ ] AC-04: Validation rejects incomplete transports, mixed CQRS duties,
  connector-owned domain mutation, unsafe shell bindings, incomplete event
  metadata, replay-unsafe projections and invalid trait declarations with
  stable `TWIN-*` diagnostics.
- [ ] AC-05: Generation is deterministic and atomic for an arbitrary language
  identifier, producing only a manifest, protobuf contract, transport map and
  conformance cases in a new destination.
- [ ] AC-06: Host tests, networkless container tests and local governance pass
  with 0 runtime dependencies and exactly 5 implementation files.

## Risks and boundaries

- MCP is native JSON-RPC; messages use ProtoJSON at the adapter boundary and
  are not described as protobuf binary transport.
- Shell support is argv-only and cannot evaluate or interpolate command text.
- “All traits” describes composable capabilities, not a forced monolith.
- Exported provider snapshots are provenance inputs, not authoritative git
  histories.

## Participants

- Human participant: the requesting user, represented by the conversation;
  no synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md)
