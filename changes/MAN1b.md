### Changed
- **The public manual is in English, like the rest of the project's site** (MAN1b, #676 ; `docs/manuel/`,
  `docs/sessions.md`, « Le manuel public »). The page (its titles, states, stages, legends, the workbench,
  the road, what it says when GitHub's API answers, limits or stays silent) and every text of
  `docs/manuel/modules.yaml` (the components, their stages, the release steps and the 110 bricks, their
  names and notes) now read English; the ids, the keys and the states (`prevue`, `livree`…) stay the
  repository's words, which `make release` reads, and the page translates them (planned, in development,
  in review, on main, released). A security brick is named « Security hardening », and the page shows that
  name for any brick the public rule reads as security, whatever the YAML says. `scripts/manuel.py` refuses
  a text of the manual that reads French (an accented letter, a guillemet, a space before a colon, a common
  French word): a lot's pull request writes its brick in English. The links to the manual (README, the
  home page, Eregion by role) no longer say « French ».
  - Tests: `tests/unit/test_manuel.py`.
