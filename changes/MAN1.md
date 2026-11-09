### Added
- **The public manual: where each part of Eregion stands, on the project's site** (MAN1, #664 ;
  `docs/manuel/`, served at `https://grootcyber.github.io/eregion/manuel/`, linked from the README and the
  home page ; `docs/sessions.md`, « Le manuel public »). Each component is shown as bricks laid on its
  chain (detect, investigate, decide, guard, act, verify…), each brick at its state: planned, in development,
  in review, on `main`, released with its version; the road from 0.2 to 1.0, release by release, and what
  each one lays. Its source is `docs/manuel/modules.yaml`, which a lot's pull request updates;
  `make manuel` writes the `modules.json` the page reads. On load, the page reads GitHub's public API
  without a token (open pull requests, open issues, the last release; kept ten minutes): an open pull
  request on a brick shows it in review. Without the API, it shows what the repository says, and says so.
  The page runs only its own script, under a content policy that allows GitHub's API alone; nothing it
  reads is written as HTML; its fonts are the replay's.
  - The public rule, held in the YAML itself: a security brick (its lots, in any case, a flag of its own, or
    its issue or pull request in the list of the audit's issues) has a neutral title only, no note, and,
    until released, a neutral place; the page shows neither its issue nor its pull request; no text of the
    manual names a finding; there is no field for an operator's gesture or a review; a note only on a
    brick released. A version cut but not yet published on GitHub reads « to be published ».
  - Tests: `tests/unit/test_manuel.py` (the schema, the rule, the page, and a fragment `changes/<LOT>.md`
    that no brick on `main` names fails).

### Changed
- **`make release` releases the manual's bricks on `main`** (MAN1, #664 ; `scripts/release.py`,
  `scripts/manuel.py`). In the version's commit, each brick on `main` becomes released with the version,
  its release step is published with its last version and its date, and `modules.json` follows; a manual
  it cannot read is refused before anything is written. Tests: `tests/unit/test_release.py`.
