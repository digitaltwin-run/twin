# twin

`twin` standardizes a language-neutral contract for generating Digital Twin
implementations. One protobuf model defines commands, events, queries,
projections, observations, evidence, receipts and transport bindings. CLI,
safe shell wrappers, REST and MCP are adapters over that model, never separate
business runtimes.

The first reference profile consolidates traits observed in:

- `bioxfoundry/twin-dsl`;
- exported provider snapshots retained under the local `digitaltwin-run`
  workspace names `plesk-service-twin`, `twin-plesk`, `twin-cloudflare`,
  `twin-onedev`, `twin-orgcore`, `twin-slack` and `twin-smtp`;
- the live `subactor/twin-probes` governance and diagnostic-probe source;
- Subactor SODL replay and connector boundaries;
- the Founder DSL CQRS/Event Sourcing implementation.

The exported provider snapshots are fingerprinted provenance inputs, not
public GitHub repositories or runtime dependencies.

## Planned command contract

```text
python -m twin_standard validate profiles/generic-twin.json
python -m twin_standard generate profiles/generic-twin.json --out generated/example --language rust
```

The generated bundle is implementation-language metadata and contracts, not
executable application code. A language adapter conforms by compiling the
protobuf and passing the emitted conformance cases.

This repository is private while its initial contract is under review.
