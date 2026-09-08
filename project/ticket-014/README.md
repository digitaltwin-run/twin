# ticket-014: Local CI publication policy and PR #20 repair

- **Status**: IN_PROGRESS
- **Workflow state**: EDIT

SESSION_EXECUTION_AUTHORIZATION: user requests implementation and publication of Wellmanifest standards across Semcod and Subactor.

## Acceptance criteria

- [x] AC-01: Adopt published immutable new-project 0.20.14 through the managed updater.
- [ ] AC-02: Preserve required checks, validate scope and use independent protected publication for the complete frozen PR diff.
- [ ] AC-03: Repair PR #20 required `test` and `windows-governance` checks without changing merge metadata or unrelated content.

Canonical fleet evidence: `subactor/docs/architecture/analysis/local-ci-adoption.md`. Full runtime CI coverage is assessed separately.

SESSION_EXECUTION_AUTHORIZATION: continue the preserved adoption, test and publish Worktrees v5; exact target-owned adoption paths are assigned before the updater runs.

SESSION_EXECUTION_AUTHORIZATION: trusted runner PLF-13393 binds this preallocated ticket to PR #20 at frozen head `25006f110c2b941afd86ab19fe3e1e875fb14d78`; `delivery.acceptedBaseSha` is the fetched main merge-base `8182bfb3bf809c013ca312e3302cc8420e53c24e`.

AC-04: Repair reusable PR governance range selection and the Windows entrypoint while preserving target-owned CI behavior, the Windows requirement and managed adoption integrity through exact lock digests.

SESSION_EXECUTION_AUTHORIZATION: continue, test and push the bounded PLF-13393 repair from frozen head `25006f110c2b941afd86ab19fe3e1e875fb14d78`. The repair keeps `ticket-014` as the single integration ticket for the complete frozen PR diff plus the required-check delta and validates PR governance from the fetched base-branch merge-base.

AC-05: Harden the target-owned Linux and Windows CI governance fetch path so
remote-tracking refs are refreshed with an explicit forced refspec and resolved
head/base revisions fail closed unless they are exact non-zero commit SHAs.

AC-06: Restore the immutable published managed files after independently approved Autonom #148 stopped interpreting trusted GitHub billing failures as source repair requests. Preserve PLF-13393 target-owned CI changes. Runtime canary at b8e36abd60dd870d8f84929cb4fec36ff204b9f7 classified Twin and Subauth as infrastructure waits without mutations; native Windows verification remains required. Evidence: receipt:ci-infrastructure-repair-20260908.
