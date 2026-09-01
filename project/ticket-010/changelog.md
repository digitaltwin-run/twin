# Ticket Changelog (ticket-010)

## [0.1.0] - 2026-09-01

- Allocated the bounded recovery ticket through the managed allocator.
- Bound the work to recovery commit `20a612a` and issue #14.
- Distinguished live repository provenance from local exported snapshots.
- Passed 74 host tests, 74 networkless-container tests and deterministic
  governance with one material documentation file and no runtime dependency.
