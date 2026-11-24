### Security
- **The restore executor apart: a fourth service, the only one meant to restore from a button; the
  watch never restores** (FS1g, #1127; `docs/design/file-actions-signee.md` §11). Behind
  `EREGION_ACTION_QUEUE=1` (off by default) and the compose profile `restore`
  (`make restore-executor-start`), the console's and the bot's Restore deposit a request signed by
  their key under a domain of its own (`eregion.restore-request/1`: never read as a request of the
  watch's queue), in `runs/console/restore/` or `runs/bot/restore/`. The executor
  (`glorfindel/restore_executor.py`) verifies it (the key pinned for its directory, freshness, its own
  register of nonces, rate, ASCII), replays the console's guard (the restore card of this VM, at the
  byte, never an anchored one), the moment with its time zone, one restore at a time (the CLI's own
  claim), the bot's human against its own copy of the allowed users, then starts the restore with the
  CLI's own code under its own pair (`EREGION_RESTORE_AZURE_CLIENT_*`). A request whose life ended is
  never restored late; one cut by a stop is said failed, never run again. Its receipts and status
  (`runs/restore/`, a writer of its own) are signed by its key; the console's card and the bot's
  thread say each one. **Until TOT1 (#685) brings the operator's one-time code, it refuses every
  request**, and says why. It refuses to start without the queue's flag, without a whole pair of its
  own, or when the VM's token point (IMDS) answers its container — on Imladris until FS1d cuts it, so
  Imladris does not run it. Its principal and its roles are not declared by the repository yet.
  - Tests: `tests/unit/test_restore_executor.py`; mutants M7226–M7245 (`scripts/mutants/FS1g.py`).
