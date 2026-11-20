### Added
- **Dagorlad on a phone: its board and its Runs view one column at a time, under 760 px** (MOB5, #975; `docs/design/console.md`, « Overview et Dagorlad sur un téléphone »). Jonathan's choices on a mockup (20/11), the follow of MOB4. Measured at 390 px, the board (a grid of 360 px, a flexible column and 380 px) showed its red cards only, and the Runs view its matrix only, the windows and the campaigns 1 px wide.
  - The board: three tabs, Red, Targets, Plan. The gesture is the board's own, a tap on a red card then on a target: a red card picked opens Targets under a banner that names it, a wire laid opens the plan, its badge the wires' count. The drag's handle and the wires drawn between the columns are left out; the plan lists the wires. A request is still a command run from the workstation.
  - The Runs view: three tabs, Windows, Campaigns, Coverage (a link to a campaign opens its tab), the coverage matrix's rows folded on two lines.
  - Overview needed nothing beyond MOB4's header; a test keeps its stylesheet free of fixed widths beyond a phone's.
  - Nothing changes above 760 px: one media query per page, its stylesheet's last.
  - Tests: `tests/unit/test_console_phone_dagorlad.py`; mutants M6698–M6709 (`scripts/mutants/MOB5.py`).
