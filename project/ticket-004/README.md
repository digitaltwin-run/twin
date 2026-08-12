# Ticket 004: Adopt Node 24 reusable governance workflow

- **ID**: ticket-004
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-08-12

## Goal and scope

Pin the `twin-ci` reusable governance call to approved merge
`wellmanifest/new-project@268311ba502cfa5306262f709e8086011c95088a`, whose
owned JavaScript actions run on Node.js 24. The change covers only the revision
used to fetch and execute the central workflow. The separately versioned local
governance payload and its lock remain unchanged.

## Acceptance criteria

- [ ] AC-01: The user's autonomous execution request is recorded as bounded
  `SESSION_EXECUTION_AUTHORIZATION` for implementation, tests and PR delivery.
- [ ] AC-02: `uses:` and the `standard-ref` input point to the same full SHA of
  the approved `new-project` merge.
- [ ] AC-03: A hosted manual run executes reusable governance with checkout v7
  and github-script v8, passes, and emits no Node.js 20 annotation.
- [ ] AC-04: Host, networkless Docker, Linux/Windows and deterministic
  governance retain the existing baseline of 58 tests.
- [ ] AC-05: `todo2code` is invoked LLM-first and remains fail-closed when its
  provider is unavailable; independent Validator App LLM approves exact-head
  with no findings.

## Risks and constraints

- The workflow revision and local payload lock are separate contracts. This
  ticket updates executed reusable code, not the broader eight-file managed
  package upgrade.
- The central workflow uses github-script v8 and requires runner `v2.327.1`;
  hosted workflow_dispatch and review events provide the runtime proof.
- No job, permission, condition, command or Python version changes.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)

## Directory boundary

This directory contains governance, decisions, logs and evidence only.
Executable workflow implementation remains in `.github/workflows/`.
