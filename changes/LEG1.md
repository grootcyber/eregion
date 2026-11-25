### Changed
- **The infrastructure map's lines say an action by their colour and where it stands by their stroke, and its legend says the same** (LEG1, #1181; `docs/design/console.md`, « La légende de la carte et ses fils »). Jonathan's rule, on a mockup with frame-by-frame examples (25/11). The legend had not moved since the start: a block waiting read « isolated », a rule proposed « detect ».
  - The colour says the action: red isolate (or a check failed), orange block, green restore (RECOVER's colour), blue what the detection asks (a verdict, a rule), purple any other card.
  - The stroke says where it stands: dotted and flowing from the module toward the tile while a human must act, solid once done. An action Glorfindel took alone draws no dotted line: only its verdict waits.
  - A VM isolated is red everywhere, its line too; a block done solid orange; a restore green everywhere, its tile pulsing green.
  - A card on Entra ID or the control plane draws its line from DETECT, blue, its tile blue while a verdict waits. It drew a purple line from PROTECT.
  - The legend has five lines (Modules, Waiting, Done, Dots, Tiles), read from the table the map draws from. For whoever asks for less motion, nothing flows nor pulses.
  - Tests: `tests/unit/test_console_legend.py`; mutants M7591–M7600 (`scripts/mutants/LEG1.py`).
