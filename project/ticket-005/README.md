# Ticket 005: Add lifecycle and modular evolutionary Twin contracts

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-12

## Goal and scope

Extend Twin Standard with a language-neutral lifecycle and modular evolution
contract. Require lifecycle transition records to be immutable and
evidence-gated. Forbid lifecycle transitions from granting execution
authority. Require evolution to start from a pinned base revision, preserve
candidate lineage and use typed module-aware plans. Apply or revert changes
only through commands/events, then regenerate and read back derived artifacts.

The normative inputs are pinned to `subactor/lifecycle@f3b8e13`,
`subactor/modularity@1c8c94e` and `digitaltwin-run/twinstudio@4183807`.
Twinstudio supplies proven patterns for lifecycle blueprints, candidate
lineage, event-backed change queues, undo and artifact regeneration; it is
informative implementation evidence rather than a runtime dependency.

## Acceptance criteria

- [x] AC-01: Record the user's request as bounded
  `SESSION_EXECUTION_AUTHORIZATION` and keep all edits within the five declared
  implementation files plus ticket governance.
- [x] AC-02: Pin immutable Lifecycle, Modularity and Twinstudio artifacts by
  repository, full revision, path and SHA-256 digest in the reference profile.
- [x] AC-03: Enforce lifecycle evidence, replay and authority separation plus
  evolution base revision, candidate lineage, typed module impact, event-backed
  apply/revert and regeneration/readback invariants with stable diagnostics.
- [x] AC-04: Expose lifecycle transition and evolution plan/apply/revert/query
  semantics through protobuf-backed CLI, safe shell, REST and MCP bindings.
- [x] AC-05: Run reference validation, unit tests, deterministic generation,
  networkless Docker and governance; verify that the runtime dependency set
  remains unchanged.
- [x] AC-06: Run current todo2code LLM-first through SubLLM and obtain an
  independent exact-head Validator Agent review before merge.

## Risks and constraints

- Reject a proposal, predicted score, simulation or generated artifact as gate
  proof unless recorded observations/evidence authenticate it.
- Keep lifecycle approval separate from authority; require external
  authorization and receipts for effectful apply and revert commands.
- Require module changes to reference the immutable Modularity graph and
  contract digests, respect ownership/layers/DAG rules and create a new
  revision.
- Rebuild state without effects during replay. Model undo as a compensating
  command/event and forbid rewriting or deleting history.
- Limit `auto-apply-safe` to explicitly allow-listed, reversible plans. Keep
  analysis and change-plan modes free of external effects.

## Validation evidence

- Exact source revisions and SHA-256 digests are asserted by the reference
  validator and negative mutation tests. The profile validates with zero
  diagnostics.
- Host and networkless Docker each pass all 73 tests. Ruff, Python compilation,
  deterministic generation and governance also pass; governance reports
  `GOV-PASS` with 0 errors and 0 warnings.
- todo2code runs `20260812T160032Z-2dbd0a88` and
  `20260812T160520Z-62a8cf1f` sent every requested semantic stage through
  SubLLM to GLM-5.2 without fallback or degradation. The combined cost was
  `$0.65304052`; useful ambiguity findings were repaired and ungrounded plans
  were not applied.
- Validator run `31616518821` approved exact PR head `bde2ea3` with trusted
  deterministic authority and advisory GLM-5.2 `APPROVE`, with no findings.
  Linux, Windows and review-governance checks passed before merge.
- PR #9 merged as `a841321`; its implementation branch was deleted. An exact
  `main@a841321` post-merge workflow was explicitly dispatched as run
  `31616943617` because GitHub did not create the expected automatic push run;
  Linux, Windows, networkless Docker and reusable governance all passed.

## Participants

- Human participant: the requesting user, represented by the conversation; no
  synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md)

## Directory boundary

This directory contains governance, decisions, logs and evidence only.
Executable Twin contracts and validation remain in their declared product
paths.
