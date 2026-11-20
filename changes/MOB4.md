### Added
- **The Glorfindel page on a phone: one section at a time, under 760 px** (MOB4, #972; `docs/design/console.md`, « La page sur un téléphone »). Jonathan's choice on a mockup (20/11, option A). Measured at 390 px, the page had no rule for a small screen: its left column (TO JUDGE and LIVE FEED), fixed at 390 px, took the screen, the infrastructure map had 0 px, the header ran off the right edge.
  - Three tabs under the header: To judge, Infra, Feed; one section shown at a time, with its own scroll. By default To judge when cards wait, else the infra, until the operator picks a tab. A badge says how many cards wait; the configuration takes the infra's place.
  - The infra on a phone: its modules stacked, its cards one under the other across the screen, without the edges. Windows fit the screen.
  - The console's header (every page) wraps on one or two lines, without its version, separator and clock.
  - Nothing changes above 760 px: every rule sits in one media query, the stylesheet's last. Overview and Dagorlad stay for a large screen, in a lot of their own.
  - Tests: `tests/unit/test_console_phone.py`; mutants M6683–M6697 (`scripts/mutants/MOB4.py`).
