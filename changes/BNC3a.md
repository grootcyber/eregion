### Changed
- **The bench's report composes itself after the run's cycle and after the lift** (BNC3a, #753 ;
  `docs/banc-t1486.md`, steps 6 and 8 ; `docs/demarrer/mobile.md` ; `docs/operations.md`, « Le banc
  lisible »). On 12 Nov `make bench-run` composed its report 7 s after the detection: the isolation and its
  cycle were not there yet, and the report said « an action held back, or a recommendation », which was
  false. The watch wrote the cycle 5 min 22 s after the detection, the session cut included. Now
  `make bench-run` reads Imladris again every 30 s until the run's cycle is written, 10 min at most, then
  reads Azure. `make bench-restore`, once the restore is done, follows the lift by Imladris the same way,
  30 min at most, then composes the run's report alone: the run of `RUN=`, or the one the moment came
  from. A lift held by the watch's recovery also ends the wait: its `release_hold` card, except `stopped`,
  which the watch reads again. The report gives that card's kind and time, never its reason. Past the
  bound, or on Ctrl-C, the report is composed anyway and says what is not yet written. A report composed
  before the cycle says « not yet written », never an action held back. Everything is read-only, under
  the operator's environment (never the console's pair). `bench-restore-go` now gets Imladris's ssh
  command too.
  - Tests: `tests/unit/test_bench_report.py`, `tests/unit/test_bench_run.py`,
    `tests/unit/test_bench_restore.py`; mutants M4880–M4889 (`scripts/mutants/BNC3a.py`).

### Fixed
- **The vault's jobs of the day are read** (BNC3a, #753). `az backup job list --end-date` with today's
  date leaves today's jobs out (measured on 12 Nov). The report then showed the previous night's backup
  as the restore point, and missed the morning's clean point and the restore job. The bound is now the
  next day.
