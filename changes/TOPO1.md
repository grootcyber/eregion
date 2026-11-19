### Fixed
- **The infrastructure map of the Glorfindel page no longer jumps when it scrolls, however many cards it holds** (TOPO1, #927; `docs/design/console.md`, « La carte de l'infra au scroll »). Three causes, measured in a headless Chromium on the sample bench with thirty more VMs:
  - the edges were placed in the screen's coordinates while their svg scrolls with the cards: every 5-second refresh made while scrolled put each edge as far above its card as the map was scrolled (400 px measured). They are now placed in the content's coordinates;
  - the refresh replaced the scroll container itself, which cut a scroll in progress (wheel, momentum, the scrollbar held). The container and the edges' layer now outlive a refresh, and only what they hold is replaced;
  - nothing drew the edges again when the map changed size (11 edges of 34 off their card after a resize). A `ResizeObserver` now draws them again, once a frame at most.
  - The page only (`glorfindel.js`, `glorfindel.html`): no route, no data. A render of 34 cards costs 4 ms.
  - Tests: `tests/unit/test_console_topology.py`; mutants M6386–M6390 (`scripts/mutants/TOPO1.py`).
