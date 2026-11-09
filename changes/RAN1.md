### Added
- **A step-by-step to replay the ransomware (T1486) on the bench and date its figures** (RAN1, #665 ;
  `docs/banc-t1486.md`, linked from `docs/demarrer/banc.md` and `docs/demarrer/a-rejouer.md`). It runs on
  gondolin: bree is not enrolled. The path is a Dagorlad request and `make orodruin-exercise`, the target's
  name typed; a declared campaign refuses T1486. The clean recovery point is taken from H0 before the attack.
  The restore runs from the operator's machine, under the console's principal, with `--before` and
  `--keep-isolated`. The release is done on H0. The page says where to read T0, the detection, the
  containment read back from Azure and the restored service, with one read-only script on H0. It also covers
  putting the bench back, the cost, and what can go wrong. Every command was checked in the code or run dry;
  nothing was played on Azure yet. The page names one gap: on the bench, the loop does not close alone. H0
  never restores, and its watch does not see a restore run elsewhere; a release made outside H0 would be put
  back by its reassertion. Two human steps remain, so the README's figures stay as they are until the run.
