# Logic flow

```text
profile input
  → structural validation
  → operation/transport/CQRS/ES invariant validation
  → canonical profile hash
  → atomic generation in a new empty directory
  → manifest + protobuf + transport map + conformance cases
```

Runtime flow required from every conforming implementation:

```text
request envelope
  → authenticate actor and authority reference
  → validate protobuf message
  → command: load stream at expected version
  → decide zero or more events
  → append events and outbox records atomically
  → project events idempotently
  → emit receipt with evidence references

query envelope
  → authenticate read scope
  → read projection only
  → return freshness and source sequence
```

Validation is deterministic. LLMs may help author a profile, but cannot make a
profile valid, grant authority or produce trusted execution evidence.
