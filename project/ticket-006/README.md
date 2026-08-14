# Ticket 006: Bind the twin lifecycle blueprint standard

- **ID**: ticket-006
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-14

## Goal and scope

Close the gap between the lifecycle trait and the lifecycle blueprint. Since
ticket-005 the standard has asserted that a blueprint is immutable, versioned
and fail-closed, but no contract defined the document that
`LifecycleBlueprintRef.definition_uri` points at. A profile could declare the
`lifecycle` trait, validate with zero diagnostics and still name no stages, no
criteria, no permitted transitions and no approver roles.

`wellmanifest/twin-lifecycle@6ca123f` now owns that document, its graph rules
(reachability, terminal stages, repeatable feedback targets, the criteria
contract) and its `TWINLC-*` diagnostics. This ticket records it as a normative
source contract and requires every profile that declares the `lifecycle` trait
to pin exactly one immutable blueprint revision by definition URI and canonical
content digest.

The same review corrects two transferred provenance URLs: `lifecycle` and
`modularity` were moved from the `subactor` organization to `wellmanifest`, so
the recorded repositories resolved only through a GitHub redirect. Both pinned
revisions and digests were re-verified unchanged against the moved
repositories.

Out of scope: no stage-graph validator inside this repository, no protobuf
change, no new trait, operation or transport binding, and no blueprint content
inlined into a profile.

## Acceptance criteria

- [x] AC-01: The reference profile pins the `twin-lifecycle-standard` source
  contract plus one immutable blueprint revision and validates with exit status
  `0`.
- [x] AC-02: A missing, non-object, mutable, digest-unpinned, non-canonical,
  version-inconsistent or stage-inlining blueprint reference is rejected with
  `TWIN-LIFECYCLE-001`, and a missing source contract with `TWIN-SOURCE-001`.
- [x] AC-03: Generation carries the pinned blueprint reference into
  `transport-map.json` and adds the
  `invariant.lifecycle-blueprint-revision-pinned` conformance case.
- [x] AC-04: Host tests, networkless Docker and governance pass within four
  implementation files and with no runtime dependency change.

## Risks and constraints

- Keep blueprint semantics out of this repository. Stage graphs, criteria
  contracts and their diagnostics belong to the pinned external standard;
  duplicating them here would create two sources of truth for one graph.
- Keep the two digest conventions distinct. A contract source pins raw artifact
  bytes at a revision; a blueprint reference pins canonical content, so
  re-serializing a blueprint cannot silently rebind a running Twin.
- Keep approval separate from authority. Pinning a blueprint records which
  gates exist; it never grants an effectful command its authority.
- Treat a transferred repository URL as a provenance defect, not a cosmetic
  one: a redirect is resolvable today and is not immutable provenance.

## Validation evidence

- To be completed from the recorded implementation run.

## Participants

- Human participant: the requesting user, represented by the conversation; no
  synthetic `user-*` artifact was created.
- Agent participant: [ai-claude.md](ai-claude.md)

## Directory boundary

This directory contains governance, decisions, logs and evidence only.
Executable Twin contracts and validation remain in their declared product
paths.
