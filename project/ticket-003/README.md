# Ticket 003: Upgrade CI actions to Node 24 releases

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: DONE
- **Workflow state**: DONE
- **Created**: 2026-08-11

## Goal and scope

Replace only the twin-owned `actions/checkout` and `actions/setup-python` pins
in `.github/workflows/ci.yml` with published Node 24 releases. Preserve every
event, permission, ref binding, shell command, Linux/Windows parity and reusable
governance reference. Warnings emitted inside the separately pinned
`wellmanifest/new-project` reusable workflow are outside this ticket.

## Acceptance criteria

- [x] AC-01: Every twin-owned checkout step uses exact
  `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1,
  Node 24).
- [x] AC-02: Every twin-owned Python setup step uses exact
  `actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97` (v7.0.0,
  Node 24).
- [x] AC-03: Workflow events, permissions, exact-revision checkout inputs,
  governance base selection and Linux/Windows commands remain unchanged.
- [x] AC-04: Host tests, YAML/JSON validation, a networkless Docker run and
  governance pass with one implementation file and no dependency change.
- [x] AC-05: Published push and pull-request jobs pass on the exact head and
  no longer attach the Node 20 deprecation annotation to the twin-owned `test`
  or `windows-governance` jobs.

  Evidence: push run `31548424492` and pull-request run `31548428896` passed
  both jobs on exact head `4a6e4932210c61f73bbe92fc0a16e5ee5b37ba46`.
  The GitHub Check Runs annotations API reported zero annotations and zero
  Node 20 messages for each of the four twin-owned job executions.

## Risks and rollback

- A major action upgrade can change defaults. Existing explicit `ref`,
  `fetch-depth`, Python version and line-ending settings remain authoritative,
  and hosted Linux/Windows checks must confirm behavior.
- The action commits are immutable exact pins already exercised by the
  Validator repository. Rollback is the single workflow-file commit.

## Participants

- Human participant: unresolved; no user-* file was created by this script.
- Agent participant: [ai-codex.md](ai-codex.md)
