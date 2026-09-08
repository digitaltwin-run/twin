# Ticket 010: Recover and clarify reference DigitalTwin source snapshots

- **ID**: ticket-010
- **Owner**: unresolved:human
- **Status**: BLOCKED
- **Workflow state**: PUBLICATION
- **Created**: 2026-09-01

## Goal and scope

Recover the still-relevant documentation intent from dangling commit
`20a612a32ada929f8de186f42cd00a8d96188ee7` without reviving its stale source
assumptions. Clarify that the provider-twin inputs are fingerprinted exported
snapshots retained under local `digitaltwin-run` workspace names, not live
GitHub repositories or runtime dependencies, and distinguish the live
`subactor/twin-probes` governance/probe source from service-twin snapshots.

The implementation is limited to the provenance paragraph in `README.md` and
this ticket's governance evidence. It does not add a contract source, change a
profile, republish any snapshot, or modify runtime behavior.

## Acceptance criteria

- [x] AC-01: Bind the recovery evidence to commit `20a612a32ada929f8de186f42cd00a8d96188ee7`, patch SHA-256 `3b5692c0a3388b421e908e347f5e24b38343951a56b55f6a7d379903322b311f`, and issue #14.
- [x] AC-02: Verify against current GitHub state that the legacy `subactor/twin-{cloudflare,onedev,orgcore,plesk,slack,smtp}` names do not resolve, while `subactor/twin-probes` remains a live repository.
- [x] AC-03: Describe the corresponding provider-twin inputs as exported snapshots retained under local `digitaltwin-run` workspace names and state explicitly that they are provenance rather than GitHub or runtime dependencies.
- [x] AC-04: Pass the host test suite, networkless Docker suite and deterministic governance check for the exact ticket diff.
- [ ] AC-05: Publish one bounded pull request with `Closes #14`; do not merge it or delete the recovery ref.

## Risks and rollback

- A namespace-looking code span can be mistaken for a public GitHub owner. The
  wording therefore labels these inputs as local exported snapshots and avoids
  hyperlinks.
- The historical recovery commit remains protected by
  `refs/recovery/2026-09-01/twin-reference-digitaltwin-run`; rollback is the
  single README change and does not discard that evidence.

## Participants

- Human participant: the requesting user, represented by the conversation;
  no synthetic `user-*` artifact was created.
- Agent participant: [ai-codex.md](ai-codex.md)
