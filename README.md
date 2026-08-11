# twin

`twin` standardizes a language-neutral contract for generating Digital Twin
implementations. One protobuf model defines commands, events, queries,
projections, observations, evidence, receipts and transport bindings. CLI,
safe shell wrappers, REST and MCP are adapters over that model, never separate
business runtimes.

The first reference profile consolidates traits observed in:

- `bioxfoundry/twin-dsl`;
- `subactor/twin-cloudflare`, `twin-onedev`, `twin-orgcore`, `twin-plesk`,
  `twin-probes`, `twin-slack` and `twin-smtp`;
- Subactor SODL replay and connector boundaries;
- the Founder DSL CQRS/Event Sourcing implementation.

## Planned command contract

```text
python -m twin_standard validate profiles/generic-twin.json
python -m twin_standard generate profiles/generic-twin.json --out generated/example --language rust
```

The generated bundle is implementation-language metadata and contracts, not
executable application code. A language adapter conforms by compiling the
protobuf and passing the emitted conformance cases.

This repository is private while its initial contract is under review.
