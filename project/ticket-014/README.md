# ticket-014: Local CI publication policy and PR #20 repair

- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

SESSION_EXECUTION_AUTHORIZATION: user requests implementation and publication of Wellmanifest standards across Semcod and Subactor.

## Acceptance criteria

- [x] AC-01: Adopt published immutable new-project 0.20.14 through the managed updater.
- [ ] AC-02: Preserve required checks, validate scope and use independent protected publication for the complete frozen PR diff.
- [ ] AC-03: Repair PR #20 required `test` and `windows-governance` checks without changing merge metadata or unrelated content.

Canonical fleet evidence: `subactor/docs/architecture/analysis/local-ci-adoption.md`. Full runtime CI coverage is assessed separately.

SESSION_EXECUTION_AUTHORIZATION: continue the preserved adoption, test and publish Worktrees v5; exact target-owned adoption paths are assigned before the updater runs.

SESSION_EXECUTION_AUTHORIZATION: trusted runner PLF-13385 binds this preallocated ticket to PR #20 at frozen head `ee97263e13c2ae83b7865cbda98fddfd3f895bf7`; `delivery.acceptedBaseSha` is the fetched main merge-base `8182bfb3bf809c013ca312e3302cc8420e53c24e`.

AC-04: Repair reusable PR governance range selection and the Windows entrypoint while preserving target-owned CI behavior, the Windows requirement and managed adoption integrity through exact lock digests.

SESSION_EXECUTION_AUTHORIZATION: continue, test and push the bounded PLF-13385 repair from frozen head `ee97263e13c2ae83b7865cbda98fddfd3f895bf7`. The repair keeps `ticket-014` as the single integration ticket for the complete frozen PR diff plus the required-check delta and validates PR governance from the fetched base-branch merge-base.
