# Ticket 005: Add lifecycle and modular evolutionary Twin contracts

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-12

## Goal and scope

Extend Twin Standard with a language-neutral lifecycle and modular evolution
contract. Lifecycle transitions are immutable, evidence-gated records and do
not grant execution authority. Evolution starts from a pinned base revision,
produces traceable candidates and a typed module-aware change plan, then
applies or reverts changes only through commands and events followed by
regeneration and readback verification.

The normative inputs are pinned to `subactor/lifecycle@f3b8e13`,
`subactor/modularity@1c8c94e` and `digitaltwin-run/twinstudio@4183807`.
Twinstudio supplies proven patterns for lifecycle blueprints, candidate
lineage, event-backed change queues, undo and artifact regeneration; it is
informative implementation evidence rather than a runtime dependency.

## Acceptance criteria

- [ ] AC-01: Record the user's request as bounded
  `SESSION_EXECUTION_AUTHORIZATION` and keep all edits within the five declared
  implementation files plus ticket governance.
- [ ] AC-02: Pin immutable Lifecycle, Modularity and Twinstudio artifacts by
  repository, full revision, path and SHA-256 digest in the reference profile.
- [ ] AC-03: Enforce lifecycle evidence, replay and authority separation plus
  evolution base revision, candidate lineage, typed module impact, event-backed
  apply/revert and regeneration/readback invariants with stable diagnostics.
- [ ] AC-04: Expose lifecycle transition and evolution plan/apply/revert/query
  semantics through protobuf-backed CLI, safe shell, REST and MCP bindings.
- [ ] AC-05: Pass reference validation, unit tests, deterministic generation,
  networkless Docker and governance with zero new runtime dependencies.
- [ ] AC-06: Run current todo2code LLM-first through SubLLM and obtain an
  independent exact-head Validator Agent review before merge.

## Risks and constraints

- A proposal, predicted score, simulation or generated artifact is not proof;
  only recorded observations/evidence can satisfy a lifecycle gate.
- Lifecycle approval records intent but cannot mint authority; effectful apply
  and revert commands still require external authorization and receipts.
- Module changes must reference the immutable Modularity graph and contract
  digests, respect ownership/layers/DAG rules and create a new revision.
- Replay rebuilds state only. Undo is a compensating command/event and never
  rewrites or deletes history.
- `auto-apply-safe` is limited to explicitly allow-listed, reversible plans;
  analysis and change-plan modes remain effect-free.

## Participants

- Human participant: the requesting user, represented by the conversation; no
  synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md)
