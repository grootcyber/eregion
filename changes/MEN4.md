### Changed
- **The ransomware times are those of the bench run of 12 Nov, replayed end to end on the current
  architecture** (MEN4, #748, with the documentation part of RAN1b, #665 ; `docs/banc-t1486.md`, « Les chiffres
  du 12/11 » ; `README.md`, `ROADMAP.md`, `docs/proofs.json`, `docs/adoption/index.html`,
  `docs/demarrer/a-rejouer.md`). Run `20261112T091448Z-b218`, Imladris and Orodruin on v0.5.10: detected at
  141.6 s from T0 (70.3 s on 9 Nov — the gap is said, not explained: ING5, RH1), the quarantine NSG laid at
  161.1 s, the isolation verified on Azure at 463.1 s (7 min 43 s, after the session cut, 304.2 s under the
  quarantine), a `restore_time` of 25 min 14 s, the release by Imladris alone at 3019.9 s; 27 min 55 s in the
  README's sense (detection, isolation, restore, the human's wait excluded). They replace « ~1 min to
  contain, 21m29s to restored service », a run of 9 June from before Imladris, Orodruin and Dagorlad, in the
  README, the ROADMAP's indicators (the time to contain, the part contained alone: 1 of 3 exercises, the age
  of the last proof: 12 Nov) and the site's figures (`contain_ransom`, `restore_ransom`, `last_e2e`, now
  measured).
- **« 0 / 41 » disruptive actions judged wrong is a figure to measure again** (MEN4, #748 ; `ROADMAP.md`,
  `docs/proofs.json`). Bree's isolation of 10 Nov was judged wrong on 11 Nov, and the sources do not give the
  count over 30 days since: the figure of 2 Nov stays, dated, shown as « to be re-measured » with why.
- **The coverage says both numbers** (MEN4, #748 ; `ROADMAP.md`, `docs/proofs.json`): eight techniques
  implemented in the catalog, the three of VM3 never played on the bench; the last proof on the bench, dated,
  of each one played (T1486 on 12 Nov, T1136.001 on 31 Oct).
- **The bench's documents say what was measured on 11 and 12 Nov** (MEN4, #748). `docs/banc-lev2.md`: played
  on 12 Nov, the verdict per hypothesis, a tag's value a text (`=1` is refused by az), the group's tag removed
  through the tags API (`az group update --remove` fails), the `eregion-auditd` check only where
  `auditd_enabled` sets it, the bench's public IP on gondolin's card. `docs/design/corroboration.md` and
  `docs/operations.md`, « Vérifier CR15 au banc »: INF-FL applied and measured, CR15, CF1 and CF2 hold; the
  expected assignments name the bot, the workstation's watch and Orodruin's contract reader; the SSH key to
  pass; about 46 s of flows lost once at traffic analytics' switch. `docs/observation.md`: an autonomous
  action executed and verified makes no card in TO JUDGE today (JUG1, to come). `docs/banc-bl1.md` and the
  documents that said otherwise: bree in `human_only` since 11 Nov. `docs/design/levee-probation.md`: H8
  falls (gondolin carries the bench's public IP, a real SSH brute force from the Internet was blocked there).
  `docs/azure.md`: on 12 Nov, before the restore, the guest agent was read `Ready` under the quarantine
  (a single reading, when the report was composed): a running VM's agent announces itself under the
  quarantine, after a delay not measured; after a restore, #677's hypothesis stays open. The bench guides: no full `make
  celebrimbor-up` on a running bench while its drifts hold (42 of the 44 rules of the shared NSG are
  Glorfindel's, the LUN 10 disk of gondolin is the restore's), a targeted apply only. `make bench-restore`
  prints the VM's full id, subscription included: said where it is run, not to be pasted. `ROADMAP.md`,
  0.6.0: R2 is a control-plane technique in R2b's dedicated subscription, Entra's techniques out of it.
  - Tests: `tests/unit/test_adoption.py`; mutants M4850–M4852 (`scripts/mutants/MEN4.py`).
