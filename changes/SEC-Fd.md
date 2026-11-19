### Security
- **The whole TUI says what the outside sends as it is** (SEC-Fd, #908; `docs/glorfindel.md`, « Le texte du dehors n'est jamais du balisage »). No panel of `glorfindel tui` hands a control character to the terminal any more; a value at normal values renders as before.
  - The RESOURCES panel: a resource's name and a block's IP, read from the state files, go through `literal()` (`glorfindel/terminal.py`), their control characters shown.
  - The FEED: its title (the run's name) and the line of a file of `runs/` refused (its name), written by another container, go through `outside()`: their markup escaped, as before, and now their control characters shown too — the markup escape alone let an escape sequence through.
  - The restore's confirmation (its moment, its warning, an unreadable vault's error, a recovery point's time), the moment's field and the `revert` command to copy already went through `literal()`; each now has its test and its mutant.
  - Tests: `tests/unit/test_outside_markup.py`; mutants M6321–M6330 (`scripts/mutants/SEC-Fd.py`); M3143 follows the code.
