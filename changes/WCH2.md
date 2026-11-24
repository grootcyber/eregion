### Changed
- **Room again in the watch's housekeeping: two concerns in modules of their own, nothing changed in what they do** (WCH2, #1150, internal ;
  `docs/fichiers-cles.md`, `docs/glorfindel.md`). `glorfindel/watch/housekeeping.py` goes from 298 lines to 202,
  under the package's ceiling of 300 with room for the next lot. The dossiers' tasks (the retention of DOS3, the
  reads of Azure and the budgets of DOS4) move to `glorfindel/watch/dossier_tasks.py`, the local reads (the
  exercise windows, the proposed verdicts, the drill of the week, the view « Relaxed » of CFG3) to
  `glorfindel/watch/local_reads.py`; both are mixed into `Housekeeping`, whose methods, threads and attributes
  stay the same: the same passes, in the same order, the same lines said, the same errors swallowed and said.
  M3226 (SEC18) and M7334 (CFG3) follow the code they mutate.
  - Tests : `tests/unit/test_watch_loop.py`, `tests/unit/test_dossier.py` (the dossier's importers, the new
    module named), `tests/unit/test_file_sizes.py`.
