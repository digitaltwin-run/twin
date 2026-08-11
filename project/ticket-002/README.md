# Ticket 002: Use accepted main base for ticket-branch push governance

- **ID**: ticket-002
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-11

## Goal and scope

Correct the Linux and Windows CI governance base selection for pushes to
non-default branches. Pull requests must stay bound to GitHub's exact PR base
SHA, while branch pushes must fetch `main` and validate the pushed head against
its merge base with `origin/main` instead of using the previous branch head
from `github.event.before`.

This ticket changes only `.github/workflows/ci.yml` plus its own governance
evidence. It does not weaken required checks, alter the adopted governance
package, or change application contracts.

## Acceptance criteria

- [ ] AC-01: On a non-default `push`, both Linux and Windows jobs fetch
  `origin/main` and derive `base` with `git merge-base origin/main EVENT_HEAD`.
- [ ] AC-02: On `pull_request`, both jobs continue to use the exact
  `github.event.pull_request.base.sha` and head SHA supplied by GitHub.
- [ ] AC-03: Default-branch pushes keep the existing changed-file governance
  path and do not require a synthetic base/head comparison.
- [ ] AC-04: Host tests, workflow syntax checks, networkless Docker tests, and
  governance pass without adding a runtime dependency or implementation file.
- [ ] AC-05: Protected push and pull-request checks pass on the published exact
  head without a false `GOV-BASE-001` from a prior ticket-branch commit.

## Risks and rollback

- A branch push could accidentally validate against a moving remote tip.
  Fetching `main` and deriving the merge base binds validation to the common
  history available in the exact checkout; pull requests remain bound to the
  immutable event base SHA.
- Linux and Windows expressions can drift. Their event selection and Git
  operations must remain structurally equivalent.
- Rollback is the single workflow-file commit; no data or generated bundle is
  migrated.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
