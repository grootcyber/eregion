### Fixed
- **The verdict proposed on an exercise card, to the end: the remainders of VP1's review** (VP1b, #917; `docs/design/drill-banc.md` §12, `docs/observation.md`).
  - A verdict given by hand (the console, the bot, the CLI) is the operator's own: a card confirmed from its proposal, then judged again, no longer says « proposed » (`verdict_from` removed).
  - The watch's pass is held card by card: a card it cannot assess is skipped and said once in the watch's channel (its short id and the error's kind, never its text), and the others are still proposed — one faulty card no longer stops the pass every minute. A card whose time carries no time zone is never proposed, its zone never guessed (said on the card); such a card on the expected wire and rule silences the wire, which card came first being never guessed either.
  - The bot adds the proposal's state to a message's signature only when there is one: a card without a proposal keeps its signature from before VP1, and no message of the last 14 days is edited for nothing.
  - A confirmation in Discord takes the path of any verdict given: the card acknowledged, its buttons greyed, the VM's thread archived once nothing waits in it.
  - Tests: `tests/unit/test_proposed_verdict.py`, `tests/unit/test_proposed_verdict_bot.py`; mutants M6336–M6346 (`scripts/mutants/VP1b.py`).
