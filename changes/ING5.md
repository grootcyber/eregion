### Added
- **The bench protocol that measures how late each source arrives** (ING5, #758; `docs/banc-retard.md`).
  The design of ING1 rests on twelve hypotheses, RH1 to RH12, that nobody has measured: whether the
  quarantine holds the guest's telemetry back, what the agent delivers of a 37-hour quarantine, how
  long the catch-up after a lift lasts, the normal lateness of `Perf`, `Syslog`, the Activity log,
  Entra and `StorageBlobLogs`, the silence of `Syslog` and the period of `Heartbeat`, whether the
  agent dates a line on its arrival, and whether the platform fills the arrival time. The page gives
  each its exact Log Analytics query, read-only, on the data the bench workspace keeps for 30 days,
  each with its window in absolute dates and its deadline, in the order the data leaves: the anchors
  of every isolation and lift since 2 November first (an unknown one is excluded from the normal week), then RH5, RH3, RH4 and RH6, the first deadline on 8 December.
  The isolation record's DH2 and DH11 join the same sitting, DH11 read from the backup job's own tasks. Each hypothesis says what confirms it,
  what refutes it, what changes if it falls, and where its result is reported, in figures only: no
  query returns an identifier. RH9 is a non-destructive gesture (three log lines dated by hand on
  gondolin); RH10 waits for ING3. Nothing has been run yet. Linked from the design (§10, §11), the
  isolation record (§9.1), `docs/glorfindel.md` and the bench guide.
  - Tests: `tests/unit/test_banc_retard.py`.
