### Added
- **The dossier of an isolation reads Azure, after the action, for the human** (DOS4, #1138;
  `docs/design/dossier-isolation.md` §3, §4.5, §7, §11, §12; `docs/glorfindel.md`, « Le dossier d'une
  isolation »). A thread of the watch, `dossier`, reads each dossier's VM, read only, under the Reader
  Imladris already holds: the activity log around the signal (the VM and its children, bounded in pages),
  the vault's jobs, the VM's model and instance view, the host's disk-write metrics per minute, and
  Resource Health. Each window is anchored on the signal's hour, never on the read's; a read that fails,
  is refused, is cut past its bound or answers in an undocumented shape is unreadable, never empty. The
  facts: the backup job near the signal, the extensions (the platform's log and the guest's own state),
  a reboot, the health events and the planned maintenance, the host's series, and Glorfindel's own
  gestures with their duration by operation, every call counted. Read again at T + 5 and 15 min for what
  was not yet delivered, and once the session drain settles; settled once its last read is complete
  (T + 35 min), when a log with no event is said empty and what still waits is said unreadable, with why.
  Never for a detection attributed to no VM: its dossier says no Azure read was made. Nothing reaches
  the model, the signal, the memory or a gate: the message is frozen to the byte.
  - Tests: `tests/unit/test_dossier_reads.py`, `tests/unit/test_read_budget.py`; mutants M7290–M7309,
    M7338–M7343.

### Changed
- **One reads' budget per service replaces the dossier's hourly ceiling** (DOS4, #1138; the maintainer's
  decisions of 24/11; `docs/operations.md`). Step 0 of a dossier reads nothing and has no ceiling any more
  (`GLORFINDEL_DOSSIER_MAX_PER_H` is gone). Each budget counts its own real calls, a minute at a time,
  and neither takes from the other: Log Analytics for the detection's KQL queries, only counted, never
  refused nor delayed (`GLORFINDEL_LA_BUDGET_PER_MIN`, 120 by default, a threshold); ARM for the
  dossier's reads, taken before they are made (`GLORFINDEL_ARM_BUDGET_PER_MIN`, 60 by default; a value
  under one pass of a dossier is raised to it, and said at the start). A real isolation reads before an
  exercise, a critical object first, and a dossier refused lets none behind it read; one left without
  room by its settling says « not composed » on its card with what held the budget, a critical object
  never: it waits. A budget held is said in the watch's log once an episode. Both values come from the
  documented limits, to be measured on the bench; the watch's other ARM readers are not counted yet.
- **The enquiry and the dossier speak one vocabulary of states** (DOS4, #1138). Each fact drawn from a
  read keeps the read's state among the catalogue's seven and shows its word among the card's five; a
  read on an unknown system is « without object » for both, and the dossier reads the system in the VM's
  model. A parameter with no object is a sentinel, never `None`: a raw `None` goes through its check.
- **A proposal of a block, approved since, keeps its dossier until 30 days after the unblock** (DOS4,
  #1138), as an isolation's is kept 30 days after the lift. The signal's hour is taken from the row only
  near the signal: a forged row time never moves the windows read.
