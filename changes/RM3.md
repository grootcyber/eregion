### Changed
- **The roadmap catches up with the decisions of 12 Nov** (RM3, #777; `ROADMAP.md`, `README.md`,
  `docs/operations.md`, `docs/manuel/modules.yaml`). 0.6.0 « identity defended » is recentred on ID1 lit and
  measured, IDI1 applied (done), IR1a seen on a real identity card provoked by a public technique on the test
  identity (C2, #199; the technique and its library are still to be chosen), and NT1 (the `never_target`
  gesture on protected identities). R2 (a Stratus control-plane technique in R2b's dedicated subscription,
  with the 06/11 audit SEC-A1 to SEC-D and the weekly bench drill) moves from 0.6.0 to 0.6.1; the README, the
  operations guide and the public manual no longer give R2 the attack on the identity. Stratus's Entra
  techniques, the FIC among them, stay `planned`, out of R2b (`docs/design/stratus-cible.md`). The releases
  table marks 0.5.11 « named and mapped » published (12 Nov) and adds 0.5.12 « always heard » in preparation
  with the lots merged on `main` since `v0.5.11`.
  - Tests: `tests/unit/test_manuel.py`, `test_docs_budget.py`, `test_host_name.py`.
