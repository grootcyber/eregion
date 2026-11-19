### Security
- **What the outside sends is said as it is, to the end** (SEC-Fc, #907; `docs/glorfindel.md`, « Le texte du dehors n'est jamais du balisage »). The rest of SEC-F's review, closed.
  - A detection query's error from Azure is printed escaped, and the search goes on: a closing tag in its text raised out of the poll, and the search ended as a `cycle_failed` card on a transient error.
  - A decision taken whose display fails is said as such — taken, its display failed — never « Error processing »: its action and its cycle are already there.
  - The error that keeps the campaign reports off is printed escaped.
  - `glorfindel pending`'s fallback steps quote the VM's name in their `az vm show`.
  - The TUI's panels (cards, commands to copy, restore, confirmation) never hand a control character to the terminal: each field goes through `literal()` (`glorfindel/terminal.py`), its control characters shown, never obeyed.
  - Three quotes for the shell that had no mutant of their own now have one (the TUI's commands, the bot's first detection, the ack of `pending`'s fallback); the TUI's ack test now holds an id that splits when unquoted.
  - Tests: `tests/unit/test_outside_markup.py`, `tests/unit/test_hosted_report.py`; mutants M6271–M6290 (`scripts/mutants/SEC-Fc.py`).
