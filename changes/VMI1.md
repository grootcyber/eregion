### Added
- **A VM's identity on its card: on hover of its name, and copied from its unfolded card** (VMI1, #971; `docs/design/console.md`, « L'identité d'une VM sur sa carte »). Jonathan's choice on a mockup (20/11, option A).
  - On hover of the name, the browser's tooltip: the name, its resource group, its subscription, the backend that detected it with the age of its heartbeat, and its full resource id.
  - On the unfolded card, a block with the same fields; the name, the group, the subscription and the id are each copied in one click (the value is the button, as an address is). The id takes two lines at most, whole on hover and in the copy.
  - The name still unfolds the card; the folded card is unchanged. Ids read whatever their case (Log Analytics lowercases them); a card filed under a name without its id says no id.
  - A long value is shortened in the copy's toast, never in the copy.
  - Nothing is asked of the server. Everything is escaped.
  - Tests: `tests/unit/test_console_vm_identity.py`; mutants M6673–M6682 (`scripts/mutants/VMI1.py`); M6442 of IPS1b anchored again on the toast.
