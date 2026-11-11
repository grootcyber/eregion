### Fixed
- **Five documents no longer contradict what the bench measured** (MEN2, #722). `docs/banc-t1486.md`
  said nothing of it had been played on the bench: it now says what the 09/11 run showed (the
  detection at 70.3 s, the autonomous isolation, the 302 s session cut, the console's restore refused
  at its trigger, the lift held by REC1's watch), what fixed each since (DRN1, RST1, REC1b, BNC1,
  MOB1), and what has not been replayed yet. `docs/operations.md` said the Activity Log and Entra ID
  settings were neither planned nor applied: both run on the bench since 05/11 (AL2, AL1c, C2b), the
  full measure of ID1 still ahead. `docs/design/preuves.md` counted about 870 unit tests: more than
  10,000, the exact count in each CI run. `CLAUDE_INFRA.md` (O0's enrollment tags) and
  `docs/design/orodruin-contract.md` (SEC5's Terraform) said « not applied yet »: Orodruin's
  `armed` contract of 05/11 proves both, its Run Command being granted only on VMs that carry
  `eregion-target`, and refused while a write holds on the whole bench group.
