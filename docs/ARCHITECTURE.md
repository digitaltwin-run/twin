# Architecture

Twin Standard v1 uses one semantic core with four transport adapters:

```text
CLI argv ─┐
shell ────┤
REST ─────┼→ protobuf command/query boundary → aggregate decision
MCP ──────┘                                  → append-only events
                                                    │
                         event store → projections ─┼→ query/read model
                                      → outbox ─────┘→ external connector
```

Commands are intent to change an aggregate. They never return an invented new
state; the aggregate decides events against an expected stream version. Events
are immutable facts. Projections can be rebuilt from the event stream. Queries
read projections only. External effects are requested through an outbox after
the event append succeeds.

CLI, shell, REST and MCP bind to the same protobuf message and operation IDs.
MCP uses its native JSON-RPC transport with protobuf JSON mapping at the typed
adapter boundary. A shell binding passes an argv vector and must not use
`eval`, interpolation or an implicit login shell.

## Source decisions

- `twin-dsl` supplies protobuf-first resources, observations, provenance,
  evidence, hard authority gates, receipts and the existing generic wizard.
- Provider twins supply reusable traits: reconciliation, read-only mirrors,
  invariants, simulation, preflight verification, notification, outbox and
  diagnostic probes.
- `twin-probes` establishes that an unavailable measurement is unevaluable,
  never healthy, and that evidence needs target join keys.
- SODL supplies correlation, causation, idempotency, append-only replay and the
  rule that replay defaults to observation rather than historical execution.
- Founder DSL supplies the command → event → store → projection decomposition.
- Subactor connector guidance keeps domain rules and the event store out of
  effect adapters; secrets remain references and never enter events or
  protobuf payloads.
