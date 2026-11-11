### Fixed
- **Seven documents no longer contradict what the bench measured** (MEN2, #722). `docs/banc-t1486.md`
  said nothing of it had been played on the bench: it now says what the 09/11 run showed (the
  detection at 70.3 s, the autonomous isolation, the 302 s session cut, the restore from the
  workstation under the console's principal refused at its trigger, the lift held by REC1's watch),
  what fixed each since (DRN1, RST1, REC1b; BNC1 and MOB1 for the gestures typed by hand), and what
  has not been replayed yet; the version it runs is the published release, no longer « 0.5.8, in
  service ». `docs/operations.md` said the Activity Log and Entra ID settings were neither planned nor
  applied: the Activity Log runs on the bench since 05/11, Entra ID since 06/11 at the latest (AL2,
  AL1c, C2b), the full measure of ID1 still ahead; `docs/azure.md` no longer calls AL1 and C2
  unmeasured. `docs/design/preuves.md` counted about 870 unit tests: more than 10,000, the exact count
  in each CI run. `CLAUDE_INFRA.md` and `ROADMAP.md` (O0's enrollment tags) and
  `docs/design/orodruin-contract.md` (SEC5's Terraform) said « not applied yet »: Orodruin's `armed`
  contract of 05/11 implies both (deduced from it, not yet read on Azure), its Run Command being
  granted by Terraform only on VMs that carry `eregion-target`, and refused while a write holds on
  the whole bench group. `eregion-zone` and the resource group's tag are only deduced with
  `eregion-target`, set by the same table; SEC5's other resources, by a full apply. The tags still to
  read on Azure are named.
