### Added
- **An excluded VM never vanishes from the console** (CFG2, #1128 ; `docs/design/configuration-console.md`,
  `docs/operations.md`). `exceptions[]` takes an optional `reason` (one line, at most 200 characters, read
  strictly; a version before CFG2 refuses a file that carries it). `/api/state` carries, for each VM an entry
  takes, what it is excluded from, why, by which pattern, and the rules written for it that still watch it
  (glorfindel/exclusions.py); its card stays on the map, greyed, with an `EXCLUDED` or `PARTLY EXCLUDED` chip
  and a band that says so; the Overview counts the excluded VMs, and the entries that take no VM today
  (`/api/exclusions`). Nothing is written.
  - Tests : `tests/unit/test_exclusion_visible.py`.

### Fixed
- **The audit line of an excluded VM is yellow, and right** (CFG2, #1128). It counted « exclue », in green, a
  rule written for the VM, which still watches it: an exclusion takes a VM out of the rules applied to every
  VM only. It now counts those alone, says the reason (or that none was given) and turns yellow.
