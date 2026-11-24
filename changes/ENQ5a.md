### Added
- **The enquiry's loop reads, at the harness, the three readings that judge a ransomware** (ENQ5a, #1162;
  `docs/design/enquete-raisonnee.md` §9.6, `docs/raisonnement.md` §10.3). `perf_minute_series` (the
  guest's disk writes in one-minute bins, by volume, with when each minute was ingested and how far the
  workspace has ingested the VM), `vault_jobs` and `vault_activity` (the backup vault's jobs and its
  activity log, read by ARM with the dossier's code, under the same Reader) enter the catalogue. Each
  window is anchored on the signal's hour by the code, through the loop's reader; the model gives an
  id, never a query, a VM, a vault nor a window. A reading not served carries a marker of its own, never
  taken for one without object; an obligatory reading still waiting is a gap; « waiting » is computed on
  what the source has ingested, not on the declared latency alone. The predicates of the ransomware
  sheet's two discriminating hypotheses (the minute's mean, the backup's job) are computed by the code
  and win over the model's verdict. Wired to nothing in production: neither the watch nor the graph
  imports the loop, its reader nor its predicates, and nothing the model sees in production changes.
  - Tests: `tests/unit/test_enquiry_reads.py`, `tests/unit/test_enquiry_loop.py`,
    `tests/unit/test_enquiry_catalog.py`, `tests/unit/test_harness_enquete.py`.
- **A read-only capture of an episode's readings at the bench, and the harness that replays it** (ENQ5a,
  #1162; `docs/operations.md`, « La capture d'un épisode au banc »). `make enquete-capture` reads, for one
  VM and the hour of its signal, each reading of the catalogue, under the operator's rights, and writes
  it out of the repository (a path inside it is refused), its names, GUIDs and e-mail addresses
  pseudonymised by default. `make llm-compare … ENQUETE=1 CAPTURES=<folder>` plays a folder of captures,
  each replayed at the moment of its decision: only the rows ingested by then. No call to Azure nor to
  the model in the tests.
  - Tests: `tests/unit/test_capture_enquete.py`.
