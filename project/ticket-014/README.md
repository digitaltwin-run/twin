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

SESSION_EXECUTION_AUTHORIZATION: trusted runner PLF-13384 binds this preallocated ticket to PR #20 at frozen head `a96b9cffb5f363ac318917150145ec7b69722cd4`; `delivery.acceptedBaseSha` is the fetched main merge-base `8182bfb3bf809c013ca312e3302cc8420e53c24e`.

AC-04: Restore the exact published 0.20.14 managed workflow and Windows entrypoint through Goal adoption; preserve target-owned CI behavior and the Windows requirement. The earlier direct workflow/hash edits fail independent protected-byte verification.

SESSION_EXECUTION_AUTHORIZATION: continue, test and push the bounded repair. Reobserved remote head f6317e40cc3c91c3521550ed44bbb4e9a1690a5d; the clean registered ticket worktree was fast-forwarded without rewriting history. Goal check reports only the managed workflow, managed Windows entrypoint and adoption lock as drift. Raw evidence: receipt:worktrees-platform-verification-20260908.
