# Roadmap

## Active

- [ ] [`ticket-006`](project/ticket-006/README.md): bind the lifecycle trait to
  an immutable blueprint revision from the separately versioned
  `wellmanifest/twin-lifecycle` standard, so the stage graph behind
  `LifecycleBlueprintRef` is a reviewed contract instead of an unmodelled
  assertion, and correct the transferred `lifecycle`/`modularity` provenance
  URLs. Status: `IN_PROGRESS / PUBLICATION`; PR #11 open with required checks passing; classification:
  `FEATURE / P1 / requested`.

- [x] [`ticket-005`](project/ticket-005/README.md): add evidence-gated
  lifecycle and modular, revision-pinned evolution contracts grounded in
  immutable Lifecycle, Modularity and Twinstudio sources. Status:
  `DONE / DONE`; classification: `FEATURE / P1 / requested`; PR #9 merged after
  73 tests, LLM-backed todo2code and exact-head Validator Agent approval.

- [x] [`ticket-004`](project/ticket-004/README.md): adopt the approved
  Node.js 24 reusable governance workflow at one immutable standard SHA without
  changing the separately pinned local governance package. Status:
  `DONE / DONE`; classification: `SERVICE / P1 / health`; PR #7 and post-merge
  Linux/Windows/reusable governance passed with zero remaining Node.js 20
  warning in the owned execution path.

- [x] Define Twin Standard v1 and generate a portable all-traits reference
  bundle with protobuf-backed CLI, shell, REST and MCP mappings over CQRS,
  Event Sourcing, canonical URI capabilities and replay-safe URI Processes.
- [x] [`ticket-002`](project/ticket-002/README.md): resolve ticket-branch push
  governance against the accepted `main` merge base so incremental pushes do
  not report false stale-base failures beside authoritative PR checks.
- [x] [`ticket-003`](project/ticket-003/README.md): move the twin-owned CI
  checkout and Python setup steps from deprecated Node 20 action releases to
  exact published Node 24 pins without changing event or governance behavior.

## Later

- [ ] Add independently governed language adapters and generated SDK fixtures.
- [ ] Add persistent event-store conformance suites for PostgreSQL and SQLite.
- [ ] Add deployment-specific profiles only after the core replay contract is
  stable.
