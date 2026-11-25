### Fixed
- **Dagorlad's Plan tab by the finger, on a phone** (DGB1, #1199; `docs/design/console.md`, « Overview et Dagorlad sur un téléphone »). The follow of MOB5. Measured at 390 × 844 on main: every button of the Plan tab 17 px high (Stop all among them), the drill's fields in 11 px (Safari on iOS zooms on them), the plan's table wider than the screen, a wire's ✕ beyond its edge.
  - Under 760 px: the buttons of the plan, the drills and the weekly drill 44 px high, a table's ✕ 44 × 44 px, the fields in 16 px; a wire, and a wire to place, on its own lines, its ✕ at the end of the second, on the screen. Above 760 px nothing changes.
  - Tests: `tests/unit/test_console_phone_plan.py`; mutants M7706–M7710 (`scripts/mutants/DGB1.py`).
