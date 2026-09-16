# Ticket 013: Respect terminal merge receipts in legacy Twin CI

- **ID**: ticket-013
- **Owner**: requesting user, represented by the conversation
- **Status**: BLOCKED
- **Workflow state**: EDIT
- **Created**: 2026-09-01

## Goal and scope

Finish the legacy Twin CI repair after the first exact-range fix exposed two
post-merge-only failures. The protected Validator receipt for PR #18 is already
terminal lifecycle truth, but a subsequent push workflow tries to validate the
merged ticket again. The delivery gate correctly rejects that replay as an
overlap with the ticket's accepted component (`GOV-BASE-002`). The legacy
reusable governance job also remains pinned to a pre-adoption revision and
cannot validate the current manifest when invoked without a pull-request range.

Keep exact-range governance on pull requests and reviews, where it protects the
head before merge. On a push to the default branch, run the product and
networkless-container tests without replaying ticket approval. Do not invoke the
legacy reusable governance job for that terminal event. Its remaining review
and manual-dispatch paths must use the repository's adopted immutable
new-project 0.19.22 revision.

## Acceptance criteria

- [ ] AC-01: A default-branch push runs host and networkless-container tests
  without replaying governance for an already merged ticket.
- [ ] AC-02: Linux and Windows pull-request/review paths retain exact event
  base/head governance and fail closed on invalid event SHAs.
- [ ] AC-03: The legacy reusable governance job no longer runs on a protected
  merge push and its remaining paths pin the adopted 0.19.22 source revision.
- [ ] AC-04: Local tests and pre-merge exact-range governance pass; the merge
  commit receives a green `twin-ci` push run.

## Risks and constraints

- Do not weaken any pre-merge required check or exact-head approval binding.
- Keep Linux and PowerShell default-branch behavior equivalent.
- Do not change Twin runtime, product tests, repository rules or the managed
  new-project workflow.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
