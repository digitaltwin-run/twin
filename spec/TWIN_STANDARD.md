# Twin Standard v1

## 1. Status and conformance language

This document defines the normative, language-neutral Twin Standard v1.
`MUST`, `MUST NOT`, `SHOULD` and `MAY` are interpreted as RFC 2119 terms. A
Twin implementation conforms only when its profile passes the reference
validator and its language adapter passes the generated conformance cases.

The standard has three local sources of truth:

1. `proto/twin/v1/twin.proto` defines wire-neutral semantic types;
2. a `twin.profile/v1` document selects traits and binds operations;
3. this document defines invariants that cannot be expressed by protobuf.

Generated output is contract metadata. It MUST NOT contain provider-specific
application code, credentials, authority grants or executable shell text.

The lifecycle and evolution extension is based on immutable upstream
contracts, recorded in every conforming profile as repository, full revision,
artifact path and `sha256:` digest:

- Lifecycle DSL v1 is the normative finite-state, evidence and diagnostic
  contract (`subactor/lifecycle@f3b8e13eb17128fd0f3ff05ac45fc99c99c470c4`);
- Modularity Workspace v1 is the normative module graph, ownership, contract,
  layer and bounded-analysis contract
  (`subactor/modularity@1c8c94ee7e13ab95af3ab734b9548ebdfc4a7c20`);
- Twinstudio lifecycle-blueprint and evolution-run schemas are informative
  implementation evidence for lifecycle tailoring, candidate lineage,
  event-backed change queues, compensating undo and artifact regeneration
  (`digitaltwin-run/twinstudio@4183807d9be0bb2a39149ddea494a224286f5dbb`).

The upstream revisions are provenance, not runtime dependencies. Updating a
revision or digest is an explicit contract review; a moving branch name is not
an acceptable source reference.

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

### 2.6 URI capabilities and resolution

Every operation is also an addressable capability with one canonical URI:

```text
scheme://uri-authority/resource[/subresource...]/query|command/action
```

The URI scheme and authority identify a routing namespace. `uri-authority`
MUST NOT be interpreted as an authorization decision. The penultimate segment
is the CQRS effect: `query` binds only to a query operation and `command` binds
only to a command operation. User information, query strings, fragments,
relative paths and embedded credential material are forbidden.

A reviewed baseline declares capability identity, effect, risk, prerequisites,
credential handles and candidate providers. Live discovery reports concrete
connector routes and safe binding status. Their composition produces an
immutable capability map with a content hash. Resolution MUST be descriptive:
it pins the map hash and either selects an exact reviewed connector URI or
returns one typed gap:

- `connector_unavailable`;
- `provider_not_implemented`;
- `credential_missing`;
- `capability_missing`;
- `precondition_failed`;
- `authority_missing`.

A credential handle describes technical readiness but never supplies
authority. A planned route that discovery did not observe MUST fail closed.
Resolution cannot dispatch the selected URI.

### 2.7 URI Process definitions and runs

A URI Process definition is an immutable, versioned DAG of steps. Multiple
immutable revisions of one process ID MAY coexist; an ID and version pair and
its canonical definition URI MUST be unique. Each step binds a declared
operation ID to its exact canonical URI, capability and reviewed provider and
declares:

- dependencies;
- timeout and bounded retry/backoff policy;
- `stop`, `continue` or `compensate` failure behavior;
- an authority scope for commands;
- per-step idempotency and receipt requirements;
- optional explicit inverse URI when reversible.

Dependencies MUST exist, MUST NOT refer to the same step and MUST form an
acyclic graph. A process plan resolves every step against one capability-map
hash. Execution MUST reject a changed map, mismatched connector route,
unresolved gap or absent external authority decision.

A run moves through `PLANNED`, `WAITING`, `READY`, `RUNNING`, `SUCCEEDED`,
`FAILED`, `CANCELLED`, `COMPENSATING` and `COMPENSATED`. Only the last four
applicable outcomes are terminal. Every attempted step records a receipt bound
to run, step, URI, attempt, idempotency key, event IDs, evidence and output
digest. Retrying a step reuses its idempotency identity.

Human participation is represented as a task with `PENDING`, `RESOLVED`,
`DECLINED`, `CANCELLED` or `EXPIRED` state. An actor/persona twin MAY describe
identity and competencies and MAY request a human task. It MUST NOT impersonate
effective authority, accept platform terms, resolve its own approval request,
or turn an LLM verdict or declared grant into an authority decision.

Rebuilding a run projection from events is observation only. Replay MUST NOT
dispatch URI steps, repeat human decisions, decrement quotas or invoke inverse
routes.

### 2.8 Product lifecycle

A Twin lifecycle blueprint is immutable and versioned. It defines named stages,
entry and exit criteria, permitted transitions, required artifacts/tests,
evidence requirements, approver roles and whether a feedback stage is
repeatable. A lifecycle transition is a command evaluated against the current
stage and aggregate revision. Unmentioned transitions fail closed.

Every requested transition records its source and target stage, base revision,
status (`REQUESTED`, `APPROVED`, `BLOCKED` or `REJECTED`), evidence references,
unmet criteria and approving actor when applicable. Evidence identifiers name
proof requirements; they are not trusted booleans. A score, proposal,
simulation, generated artifact or LLM verdict MUST NOT be promoted to verified
evidence without an observation that authenticates it.

Approval and authority remain separate. An approved gate confirms that the
declared lifecycle criteria were evaluated; it MUST NOT mint authority for an
effectful command. Rebuilding lifecycle projections is observe-only and MUST
NOT approve, reject or advance a stage.

### 2.9 Evolutionary modularity

Evolution is an event-sourced refinement of a Twin, never an in-place rewrite.
An evolution run pins the aggregate `base_revision`, lifecycle stage,
deterministic seed and immutable Modularity graph digest. Each candidate has a
stable ID, zero or more parent candidate IDs, proposed module changes,
validation steps and a status that keeps `PROPOSED`, `SELECTED`, `REALIZED` and
`VERIFIED` distinct. Evaluation scores support selection but are not evidence.

Every candidate change MUST be expressed as a typed change plan against module
IDs and pinned module contract digests. The plan MUST preserve the Modularity
workspace's ownership, layer direction, acyclic dependency graph, single-writer
state and bounded analysis-scope rules. Cross-module behavior uses declared
contracts; applying a plan creates a new immutable revision and never changes a
pinned historical module revision.

Three execution modes are portable:

- `analysis-only` may produce candidates and evaluations but no change intent;
- `change-plan` may append a proposed plan but MUST NOT execute its effects;
- `auto-apply-safe` MAY apply only an explicitly allow-listed plan that is
  reversible, compatible, lifecycle-approved and externally authorized.

Apply and revert requests enter an event-backed change queue. An apply event
binds base/new revisions, selected candidates, affected modules, authority,
receipts and evidence. Revert is a new compensating command/event; it MUST NOT
delete or rewrite history. After either action, derived artifacts MUST be
regenerated and read back, and their observed digests/evidence MUST be recorded
before the new revision is reported as verified. Replay MUST NOT drain the
queue, apply, revert or regenerate artifacts.

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
| `uri-process` | Resolve reviewed URI capabilities and describe replay-safe process runs. |
| `lifecycle` | Record evidence-gated, authority-neutral lifecycle transitions. |
| `modular-evolution` | Plan, apply, compensate and verify revision-pinned module evolution. |

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
- one canonical URI, capability identity and risk class for every operation;
- URI resolution, process-runtime and human-task safety policy;
- at least one immutable process definition with an acyclic step graph;
- immutable Lifecycle, Modularity and Twinstudio source-contract provenance;
- lifecycle gate/evidence/replay policy and modular evolution policy;
- revision-pinned candidate lineage, typed module impact and apply/revert rules;
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
| `TWIN-URI-001` | A canonical URI is malformed or disagrees with its CQRS effect. |
| `TWIN-CAPABILITY-001` | Capability resolution, risk or fail-closed gap policy is incomplete. |
| `TWIN-PROCESS-001` | A process DAG, step execution policy, run state or human-task boundary is unsafe. |
| `TWIN-SOURCE-001` | An upstream contract lacks immutable revision/content provenance. |
| `TWIN-LIFECYCLE-001` | Lifecycle gates, evidence, transition states or replay semantics are unsafe. |
| `TWIN-MODULARITY-001` | Module graph, ownership, contracts, layers or analysis scope are unsafe. |
| `TWIN-EVOLUTION-001` | Candidate lineage, change modes, apply/revert or verification semantics are unsafe. |

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

The transport map also contains URI resolution/process policy and definitions,
source-contract provenance, lifecycle policy, modularity rules and evolution
policy. Conformance output adds one case per process step plus capability,
lifecycle, modularity, candidate-lineage, apply/revert, regeneration, replay
and actor/authority invariants. It never emits a URI runtime, evolution engine,
CAD generator or connector implementation.

Canonical JSON uses UTF-8, lexicographically sorted object keys, two-space
indentation and one final LF. No clock, host path, random identifier or LLM
output enters the bundle, so equal inputs and language identifiers produce
byte-identical outputs.
