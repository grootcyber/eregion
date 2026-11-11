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
  in each CI run. `CLAUDE_INFRA.md` and `ROADMAP.md` said O0's enrollment tags « not applied yet »: they were read on
  Azure on 11/11, on gondolin and on its resource group (`eregion-target` the bench's id on both,
  `eregion-zone` `bench`); the reading says nothing of the legacy `annatar-test` tag, which still
  enrolls, nor of a role assignment set by hand, which Orodruin's contract does not tell apart.
  `docs/design/orodruin-contract.md` said SEC5's Terraform « not applied yet »: Orodruin's `armed`
  contract of 05/11 implies it (deduced from it, not yet read on Azure), the contract refusing a write
  on the whole bench group; SEC5's other resources, by a full apply.
- **The azurerm canary's real hour and the measured form of its OIDC sign-ins** (MEN2, #722, #673;
  `infra/glorfindel-host/README.md`, « Les connexions OIDC du canari (CAN3) » ; `docs/glorfindel.md`).
  The canary is scheduled at 06:00 UTC, and GitHub delays it by hours: on 11/11 its last six scheduled
  runs started between 11:57 and 14:27 UTC (`gh run list --workflow canary-azurerm.yml` gives the real
  hour). Measured on the bench on 11/11: `ClientCredentialType` is `federatedIdentityCredential` and
  `FederatedCredentialId` is present; `ServicePrincipalCredentialKeyId` and `…Thumbprint` are filled
  too, constant, and are not the federated credential's id, so they never said a secret or a
  certificate was used — `ClientCredentialType` says it, and whether the canary still has none is
  read on its application and service principal, as counts (`az ad app show`, `az ad sp show`). The
  bench copy of the rule reads neither field.
