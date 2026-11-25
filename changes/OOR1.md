### Fixed
- **What is out of reach, finished** (OOR1, #1202; `docs/design/console.md`, « Les finitions »): the limits the review of GRP1 left, chosen by Jonathan.
  - A held card is judged by the tile it is shown on, as its buttons are taken off: a card filed by a bare VM name no longer says « pending approval » on a tile out of reach.
  - Its Cmd window gives no command that acts — aimed by name, it would reach a homonymous VM of the watch's subscription —, its acknowledgement only.
  - The bar « the watch's subscription unknown » is said once /api/config was read without one, or could not be read (an error's answer included), never before its first answer.
  - A VM's readiness of another subscription (`/api/readiness`, `/api/activate`) is refused with a 409 « out of reach, detect only », without identifier, instead of a 500 (`eregion_console/reach.py`, its handler shared with an ambiguous VM's in `api.py`).
  - Tests: `tests/unit/test_console_oor.py`; mutants M7717–M7725 (`scripts/mutants/OOR1.py`).
