# Ticket Changelog (ticket-002)

## [0.1.0] - 2026-08-11

- Initial governance scaffold created.
- No human participant identity or content was generated.
- Recorded the duplicate push-check regression, exact one-file workflow scope,
  symmetric Linux/Windows acceptance criteria, and external review gate before
  implementation.
- Corrected non-default push base selection in both CI shells while preserving
  exact pull-request event SHAs and the default-branch changed-file path.
- Passed 58 host and networkless-container tests plus workflow syntax and
  structural parity checks.
- Added the required XS delivery contract after the first governance run
  failed closed on `GOV-DELIVERY-001`, then aligned its estimate with the
  policy's ten-minute XS ceiling; no publication occurred before repair.
- Verified the repaired branch-push path on exact head `4ed6e44` in hosted run
  `31546044854`: Linux and Windows required jobs both passed without a false
  `GOV-BASE-001`.
