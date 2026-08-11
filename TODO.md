# Roadmap

## Active

- [x] Define Twin Standard v1 and generate a portable all-traits reference
  bundle with protobuf-backed CLI, shell, REST and MCP mappings over CQRS,
  Event Sourcing, canonical URI capabilities and replay-safe URI Processes.
- [ ] [`ticket-002`](project/ticket-002/README.md): resolve ticket-branch push
  governance against the accepted `main` merge base so incremental pushes do
  not report false stale-base failures beside authoritative PR checks.

## Later

- [ ] Add independently governed language adapters and generated SDK fixtures.
- [ ] Add persistent event-store conformance suites for PostgreSQL and SQLite.
- [ ] Add deployment-specific profiles only after the core replay contract is
  stable.
