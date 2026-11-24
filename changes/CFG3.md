### Added
- **Everything the configuration relaxes stays visible: the view « Relaxed », read-only** (CFG3, #1139 ;
  `docs/design/configuration-console.md`, §6, `docs/operations.md`). `glorfindel/relaxed.py`: each entry of
  glorfindel-config.yaml that relaxes the defence — an exclusion, the default and the bold modes (latent ones
  included: an exact entry that changes nothing today but screens its VM), the client's `never_block`, the
  expected administrators, the investigation access to an isolated VM, the exposed zones and the named
  networks they cite — classed by CFG4's pure function (the file without the entry, then with it; a twin
  classed alone, shown latent; an entry that can't be classed shown, never hidden), with its reason when it
  has one, what a pattern or a named network designates today, and the author « unknown » until the history.
  The watch writes it in its own directory, `runs/glorfindel/config/relaxed.json`, at its start and every
  minute, in a thread of its own, computed again only when the file, the discovery, the client's network or the
  session's `--mode` changed (each entry is classed on the whole file: 5.6 s for 204 entries, then 10 ms), and
  says its lines at its start, bounded; the console reads it (`/api/config/relaxed`) and shows it on `/config`, escaped — it never computes
  nor writes it. A file the strict reading refuses, a discovery that can't be read, a view absent, unreadable,
  older than 5 minutes or computed from another version of the file: said, never read as « nothing relaxed ».
  Nothing is written to the configuration, and nothing the model sees changes.
  - Tests : `tests/unit/test_relaxed_view.py`.
