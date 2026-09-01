# Ticket 012: Use exact ranges in legacy Twin CI

- **ID**: ticket-012
- **Owner**: requesting user, represented by the conversation
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-01

## Goal and scope

Repair the repository-specific `twin-ci` workflow after the new-project 0.19.22
adoption exposed its legacy default-branch shortcut. A push to `main` currently
asks governance to inspect only `project/TICKETS.md`, which is neither the real
event range nor a material delivery and causes the post-merge workflow to fail
after all product tests pass.

For default-branch pushes, both Linux and Windows jobs must validate the exact
GitHub event range `github.event.before..github.sha` and fail closed when the
event does not supply a non-zero full base SHA. Pull-request, review and manual
dispatch behavior remains unchanged. Twin runtime, tests, reusable governance,
action revisions and repository rules are outside scope.

## Acceptance criteria

- [ ] AC-01: Linux default-branch pushes validate the exact event base and head
  instead of a synthetic ticket-only changed path.
- [ ] AC-02: Windows default-branch pushes validate the same exact event range.
- [ ] AC-03: Pull-request, review and manual-dispatch range resolution remains
  intact, and immutable action revisions are unchanged.
- [ ] AC-04: All host and networkless-container tests pass and exact-range
  governance accepts the material workflow change.

## Risks and constraints

- Reject missing, malformed or all-zero event base SHAs instead of silently
  weakening governance.
- Keep the Linux and PowerShell branches behaviorally equivalent.
- Do not modify Twin runtime, tests, reusable governance or rulesets.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
