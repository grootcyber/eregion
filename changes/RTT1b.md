### Changed
- **A cloud detection's card is titled by its rule in the console** (RTT1b, #1174; RTT1a for the rules; `docs/design/console.md`, « Le titre d'une carte de détection cloud »). Jonathan's choices on a mockup (25/11).
  - « Entra ID unusual sign-in », not « Entra ID identity change » for a sign-in; « Run Command by another caller », not « Control-plane change ».
  - The line of TO JUDGE, the tile, the card of JUG1, the window « ×N » and its outcome, and an exercise's cards in Runs.
  - The title is read again as the Python reads it (`glorfindel/rule_title.py`), once for every page (`Console.ruleTitle`): unreadable or absent, the family's neutral title, « Entra ID detection » or « Control-plane detection ». The console never shows more than the Python; the title is escaped as any text.
  - A group of several rules takes the neutral title and the count of its rules, never one card's title for all.
  - The type and its guards are unchanged.
  - Tests: `tests/unit/test_console_rule_titles.py`; mutants M7546–M7555 (`scripts/mutants/RTT1b.py`).

### Fixed
- **The card of JUG1 and the window « ×N » name a tile of its own by its label** (RTT1b, #1174): « the control plane », « Entra ID — identities », never its key (`plane:control`, `entra:identities`).
