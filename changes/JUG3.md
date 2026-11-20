### Added
- **Several cards judged at once, in TO JUDGE or in a tile's group** (JUG3, #980; `docs/design/console.md`, « Juger plusieurs cartes »). Jonathan's choices on a mockup (20/11), after judging 35 cards one by one, 11 of them from one `terraform apply`.
  - A box on each line of TO JUDGE (« select all » on top); a tile that folds two cards to judge or more shows « to judge ×N ▸ », whose window ranges them by rule, with « select this rule » and « select all ». The box keeps its click: the line still opens its card (JUG1).
  - One verdict and one note for all. Each card gets exactly what its own button gives it, its verdict and the note, then its acknowledgement, one card after the other, each answer read. Never an action, never a verdict proposed (VP1) confirmed in the operator's place.
  - A summary before anything is written: the count by rule, the note. A selection of several rules is warned of in the bar.
  - The outcome card by card: judged and acknowledged; judged, not acknowledged, and why; not judged, and why, left checked to try again. The others go on. The note goes with its batch only.
  - A card judged elsewhere since the summary (the bot, another tab) is left as it was: the list is read again at the confirmation, since the server takes a second verdict. A list that cannot be read again writes nothing: each card is said and left checked.
  - One batch at a time for the page: the list and a group's window may hold the same cards.
  - On a phone: a 20 px box in a 44 × 44 px hit area, all of it reachable, the bar's note in 16 px, its verdicts 44 px high; a tile's « to judge ▸ » 44 px high.
  - Tests: `tests/unit/test_console_judge_batch.py`; mutants M6734–M6748, M6765–M6767 and M6780–M6787 (`scripts/mutants/JUG3.py`).

### Fixed
- **The list TO JUDGE no longer drops what is being typed when it redraws, every 30 s** (JUG3, #980). A card's note was wiped, and the field lost its focus: on a phone, the keyboard closed mid-word. The notes, the field and its caret now stay.
