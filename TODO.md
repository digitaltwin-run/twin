# Roadmap

## Active

- [x] Define Twin Standard v1 and generate a portable all-traits reference
  bundle with protobuf-backed CLI, shell, REST and MCP mappings over CQRS,
  Event Sourcing, canonical URI capabilities and replay-safe URI Processes.

## Later

- [ ] Align ticket-branch push governance with the accepted `main` base, or
  avoid duplicate push checks, so an implementation push cannot add a false
  stale-base failure beside the authoritative pull-request checks.
- [ ] Add independently governed language adapters and generated SDK fixtures.
- [ ] Add persistent event-store conformance suites for PostgreSQL and SQLite.
- [ ] Add deployment-specific profiles only after the core replay contract is
  stable.
