# Ticket 011: Adopt wellmanifest/new-project 0.19.22

- **ID**: ticket-011
- **Owner**: requesting user, represented by the conversation
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-01

## Goal and scope

Upgrade the repository-owned governance package from published revision
`3549d21a5a31fea87b2dd4da37d8e8bd793f20f6` (0.14.1) to the exact published
revision `f7fe7163e886d5540cedf83d383b6dd99daafd7c` (0.19.22). The recovery work
for issue #14 landed independently in PR #16 while this adoption was under
validation; this follow-up replaces its legacy plan-only intent rule with the
current material-delivery contract without rewriting the integrated recovery.

The upgrade is one bounded, atomic standard-adoption transaction. Goal must
first produce a reviewed write-free preflight, then perform the explicit
`--upgrade`. Repository-owned runtime, profiles, specs, tests and product
documentation are outside scope and must remain byte-identical.

The inherited required-check declaration incorrectly identifies the repository
as `wellmanifest/new-project`; this target-specific extension is corrected to
`subactor/twin` before preflight so Goal preserves it instead of projecting the
hub's CI declaration through an existing reusable-workflow caller.

## Acceptance criteria

- [x] AC-01: Goal preflight is reviewed and the installed lock records
  published 0.19.22 at exact SHA `f7fe7163e886d5540cedf83d383b6dd99daafd7c`.
- [x] AC-02: All host Twin tests pass with no runtime or product-documentation
  change.
- [x] AC-03: The same suite passes in the immutable networkless Docker image.
- [x] AC-04: Exact `base..HEAD` governance accepts the atomic adoption without
  a plan-only baseline commit or bypass.
- [x] AC-05: The clone-level managed pre-commit hook is active and Python
  packaging invokes the pinned governance plugin automatically.
- [ ] AC-06: A pull request closes GitHub issue #15 but is not merged by this
  workstream.

## Risks and constraints

- Use only the published full SHA; never use a tag, branch or dirty local
  standard checkout as adoption authority.
- Preserve target extensions through the generator's three-way manifest merge.
- Do not rewrite the integrated `ticket-010` recovery, and do not remove any
  `/tmp` checkout.
- Ruleset changes, trusted approval and merge remain outside this ticket.

## Validation evidence

- Goal 2.1.300 verified the final release, reported a reviewed 73-operation
  write-free plan, installed 0.19.22 with `--upgrade`, and a second `--check`
  reports the exact SHA up to date.
- The lock pins `publicationStatus: published`, version `0.19.22` and source
  revision `f7fe7163e886d5540cedf83d383b6dd99daafd7c`.
- All 74 tests pass on the host and inside image `twin-ticket-011` with
  `--network none`; no path under `src/`, `tests/`, `profiles/`, `spec/`,
  `README.md` or `docs/` changed.
- `scripts/install-agent-hosts.sh --check` confirms clone-local
  `core.hooksPath=.githooks`; manifest and intent validate against the newly
  installed schemas.
- After rebasing onto the recovery merge `e8d15fc`, 74 host tests, 74
  networkless Docker tests, pytest lifecycle collection and exact-range
  governance all pass again; governance reports `0 errors, 0 warnings`.

## Participants

- Human participant: the requesting user, represented by the conversation; no
  synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md).

## Directory boundary

This directory stores bounded intent and evidence only. Managed executable
governance stays in the package-owned paths declared by the adoption manifest.
