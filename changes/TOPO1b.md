### Added
- **A readiness audit that cannot be read is said once, above the cards of the infrastructure map** (TOPO1b, #949; `docs/design/console.md`, « La bande d'un audit illisible »). Jonathan's choice on a mockup (19/11). Before, the cards lost their checks and their addresses in silence, and only the dot of the GLORFINDEL node went red.
  - Nothing read: « ⚠ Readiness audit not read: <reason> · checks and addresses unknown on every card · next try within 5 min ».
  - The last good audit kept: « … · cards show the read of HH:MM:SS UTC », and the cards keep what it said.
  - An answer that is not an audit (an HTTP error, a body without `audits`) is now a failure: an HTTP error with a JSON body (a 404 or a 422 `{detail}`, a proxy's) was read as an audit without VMs. A good audit takes the band away. The reason is escaped.

### Changed
- **The infrastructure map draws its edges once per refresh, not twice** (TOPO1b, #949, from TOPO1's review). Each render observed its new row of cards, and the observation's first notification drew the edges again; a size already seen now draws nothing (measured: 4 draws for 2 refreshes, then 2). A browser without `ResizeObserver` still draws at each render.
- **The map's shell is rebuilt when any of its three elements is missing** (`#topo-graph`, `#topo-svg`, `#topo-body`): a missing `#topo-body` threw an error. The documentation says that the content of `#topo-body` is replaced, not the element.
- Decision, no change of code: on a folded card, a click on an address still copies it (option A kept by Jonathan, 19/11, written in `docs/design/console.md`).
- Tests of TOPO1b: `tests/unit/test_console_audit_band.py`, `tests/unit/test_console_topology.py`; mutants M6501–M6510 (`scripts/mutants/TOPO1b.py`); M6387 of TOPO1 anchored again on the new shell check.
