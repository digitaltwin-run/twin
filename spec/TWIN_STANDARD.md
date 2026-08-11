# Twin Standard v1

## 1. Status and conformance language

This document defines the normative, language-neutral Twin Standard v1.
`MUST`, `MUST NOT`, `SHOULD` and `MAY` are interpreted as RFC 2119 terms. A
Twin implementation conforms only when its profile passes the reference
validator and its language adapter passes the generated conformance cases.

The standard has three sources of truth:

1. `proto/twin/v1/twin.proto` defines wire-neutral semantic types;
2. a `twin.profile/v1` document selects traits and binds operations;
3. this document defines invariants that cannot be expressed by protobuf.

Generated output is contract metadata. It MUST NOT contain provider-specific
application code, credentials, authority grants or executable shell text.

## 2. Semantic model

### 2.1 Aggregate and CQRS

A Twin aggregate owns domain decisions for one `aggregate_id` and
`aggregate_type`. A command is change intent evaluated against an
`expected_version`. A conforming command:

- MUST be marked mutating;
- MUST declare one or more possible events;
- MUST require an authority reference and idempotency key;
- MUST NOT write a projection or call a connector directly.

A query is non-mutating, declares no events and reads one named projection.
Queries MUST NOT decide new domain facts. Command and query message types are
protobuf messages in the profile's declared package.

### 2.2 Event Sourcing

Events are immutable facts appended to a stream with optimistic concurrency.
The canonical `EventEnvelope` metadata is:

`event_id`, `aggregate_id`, `aggregate_type`, `aggregate_version`, `sequence`,
`event_type`, `schema_version`, `actor_ref`, `authority_ref`, `correlation_id`,
`causation_id`, `idempotency_key`, `occurred_at`, `evidence` and `payload`.

An event store MUST reject a conflicting expected version and MUST treat an
already accepted idempotency key as the same command, not a second mutation.
Snapshots are caches and MUST NOT become the source of truth. Projections MUST
be rebuildable from the ordered event stream.

Replay defaults to `observe`. Replay MUST NOT execute historical connectors,
shell commands, authority decisions, notifications or outbox effects. A new
effect may happen only after a new authorized command creates a new event.

### 2.3 Observations, evidence and health

An observation identifies its aggregate and target URI, carries an observed
time and may expire. Evidence MUST contain join keys sufficient to associate it
with both. Missing or unavailable measurement is `UNEVALUABLE`; it MUST NOT be
reported as healthy. Reporting evidence and enforcing a decision are separate
responsibilities.

### 2.4 Receipts, authority and secrets

Every accepted mutation produces a receipt bound to command, aggregate,
authority, event IDs and resulting aggregate version. A receipt reports a
decision; it does not manufacture authority.

Profiles and protobuf messages MAY contain opaque `credential_ref` or
`authority_ref` handles. Secret, password, token and credential values MUST NOT
appear in profiles, commands, events, observations, receipts, logs or generated
bundles.

### 2.5 Outbox and connectors

External effects are represented by `OutboxMessage` records written in the
same consistency boundary as domain events. A connector consumes an outbox
record and reports a new outcome through an authorized command. Connectors are
thin adapters: they MUST NOT own domain rules, authority decisions or the
event store.

## 3. Standard traits

An all-traits reference profile contains these independently composable traits:

| Trait | Required semantic responsibility |
| --- | --- |
| `reconciliation` | Compare desired and observed state and request convergence. |
| `mirror` | Refresh an externally sourced, read-oriented mirror. |
| `invariant` | Evaluate constitutional or domain invariants as facts. |
| `simulation` | Record a non-authoritative predicted outcome. |
| `preflight-verification` | Record checks before an effect is eligible. |
| `notification` | Enqueue notification intent without delivering inline. |
| `outbox` | Record and acknowledge external-effect delivery. |
| `probe` | Publish diagnostic observations and explicit unevaluable state. |

A trait references declared operation IDs. Traits do not create an alternative
transport or bypass CQRS.

## 4. Transport bindings

Every declared operation MUST have exactly one binding in each enabled
surface. All four v1 surfaces are required.

### 4.1 CLI

CLI bindings are arrays of argv tokens. A language adapter parses request data
into the operation's protobuf request and serializes its protobuf response.

### 4.2 Safe shell

Shell bindings are also argv arrays. A conforming adapter MUST set
`argvOnly`, `noEval` and `noInterpolation` to true. It MUST call a process API
with an explicit argv vector and MUST NOT invoke `eval`, interpolate shell
source, or start an implicit login shell.

### 4.3 REST

REST commands use `POST`; queries use `GET`. Paths are absolute and unique by
method and path. Bodies and responses use protobuf JSON mapping unless an
adapter declares a compatible binary protobuf content type.

### 4.4 MCP

MCP uses its native JSON-RPC protocol over stdio or Streamable HTTP. It is not
a protobuf binary transport. MCP arguments and results map to the same
protobuf request and response messages using ProtoJSON. Commands are MCP tools
and MUST require authority. Queries MAY be tools or resources.

## 5. Profile contract

A `twin.profile/v1` JSON object declares:

- identity, aggregate type and canonical protobuf path/package;
- Event Sourcing, CQRS, authority, secret, connector and evidence invariants;
- the complete standard trait set;
- unique command/query operations and their protobuf types;
- complete CLI, shell, REST and MCP bindings;
- the four deterministic generator outputs.

Unknown implementation-language identifiers are allowed when they match the
safe identifier grammar `[A-Za-z][A-Za-z0-9_.+-]{0,63}`. The profile does not
enumerate supported programming languages.

## 6. Validation and diagnostics

Validation is deterministic, has no network dependency and emits diagnostics
sorted by code and JSON path. Stable diagnostic families are:

| Code | Meaning |
| --- | --- |
| `TWIN-JSON-001` | JSON cannot be parsed or contains duplicate keys. |
| `TWIN-PROFILE-001` | Required profile identity or shape is invalid. |
| `TWIN-TRAIT-001` | Required traits are missing, duplicated or unresolved. |
| `TWIN-OPERATION-001` | Operation identity, kind or protobuf type is invalid. |
| `TWIN-CQRS-001` | Command/query responsibilities are mixed. |
| `TWIN-EVENT-001` | Event-store or envelope metadata invariant is absent. |
| `TWIN-REPLAY-001` | Replay can execute effects or trusts snapshots. |
| `TWIN-AUTH-001` | Mutation authority or receipt requirements are weakened. |
| `TWIN-CONNECTOR-001` | A connector owns forbidden core responsibilities. |
| `TWIN-SECRET-001` | Secret values are permitted or modeled. |
| `TWIN-EVIDENCE-001` | Evidence, join-key or unevaluable semantics are unsafe. |
| `TWIN-TRANSPORT-001` | A surface has incomplete or unresolved bindings. |
| `TWIN-SHELL-001` | A shell binding can evaluate or interpolate text. |
| `TWIN-REST-001` | REST method/path semantics are invalid. |
| `TWIN-MCP-001` | MCP is not JSON-RPC + ProtoJSON or weakens command authority. |
| `TWIN-PROTO-001` | The protobuf file or referenced declarations are invalid. |
| `TWIN-GENERATION-001` | Language or declared generator outputs are invalid. |
| `TWIN-OUTPUT-001` | A safe atomic destination cannot be created. |

Exit status is `0` for valid/generation complete, `1` for an invalid contract,
and `2` for usage, unsafe output state or internal I/O failure.

## 7. Deterministic generation

Generation validates first, builds in a temporary sibling directory and
publishes by rename. The destination MUST NOT already exist and its parent MUST
exist. On failure, the temporary directory is removed and no partial
destination remains.

Exactly these files are emitted:

- `twin.manifest.json` — profile/protobuf hashes and language identity;
- `proto/twin/v1/twin.proto` — the canonical protobuf contract;
- `transport-map.json` — resolved operation and adapter metadata;
- `conformance.json` — deterministic operation and invariant test cases.

Canonical JSON uses UTF-8, lexicographically sorted object keys, two-space
indentation and one final LF. No clock, host path, random identifier or LLM
output enters the bundle, so equal inputs and language identifiers produce
byte-identical outputs.
