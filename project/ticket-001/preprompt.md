# Ticket preprompt

- **Task ID**: ticket-001
- **Task title**: Standardize and generate language-neutral Twin v1
- **Created**: 2026-08-11T19:03:11Z

Keep executable implementation outside this governance/evidence directory.
Read a human-owned user-*.md file only when one exists.
The request to execute this work creates SESSION_EXECUTION_AUTHORIZATION;
proceed within the recorded intent without a redundant confirmation prompt.
Require new authority for destructive action, secrets, external coordination,
material objective expansion and trusted merge approval.

## Technical directives

- The semantic source of truth is protobuf plus a validated Twin profile.
- Use CQRS: commands decide events; queries only read projections.
- Use Event Sourcing: append-only streams, expected-version concurrency,
  complete correlation/causation/idempotency metadata and replayable views.
- Replay defaults to observe and must never repeat historical shell commands,
  authority decisions or external effects.
- Connectors are thin effect adapters. They do not own domain rules, authority
  or the event store. Credential material is represented only by opaque refs.
- CLI and shell use argv; shell forbids evaluation and interpolation.
- REST and MCP resolve to the same operation and protobuf types. MCP uses
  ProtoJSON over MCP's native JSON-RPC transport.
- Generator output is metadata and contracts, never unreviewed executable
  provider code.

## Read-only inputs

- `bioxfoundry/twin-dsl` at
  `e387d67953e328b4402b3cfa502ed35223860fca`.
- `subactor/twin-probes` at
  `346f9b3d3448cec0cbfa08e9caa31015e1a11d0a`.
- Exported snapshots of `twin-cloudflare`, `twin-onedev`, `twin-orgcore`,
  `twin-plesk`, `twin-slack` and `twin-smtp`, fingerprinted in the agent log.
- `founder-pl/DSL` at
  `6564c3ddcfc150ef8ba0002de94b82974b86685e`.
- `artifact://subactor/docs/architecture/sodl-operational-event-and-replay-2026-07-21.md/r2`.
- `knowledge://subactor/architecture.openwebui-mcp-control-boundary/v2`.
- `knowledge://subactor/architecture.credential-vault-package-boundary/v1`.
