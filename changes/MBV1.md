### Fixed
- **The model breaker's cards are seen in the console again** (MBV1, #1175; `docs/design/console.md`, « Les cartes de la watch »). A card `model_budget_tripped` (PRT2) says that until 00:00 UTC a detection may not be seen by the model. It is written without a resource, and it was nowhere in the console: not a decision, so out of TO JUDGE, and given a tile without a name that was never drawn. Jonathan's choices on a mockup (25/11):
  - On the GLORFINDEL node, a red band, « ⚡ MODEL BREAKER ×N », opens the watch's cards: each reason whole, its steps, its Ack (each answer read, a refusal said), « Ack all ».
  - In the header of every page, a pill « ⚡ model breaker ×N » beside the watch while one is open; from another page it leads to `/glorfindel?watch`, which opens them. `/api/watch/status` carries their count (`model_breaker`).
  - An Ack closes the card, not the breaker: the model comes back at 00:00 UTC, after a provider's limit once a call is served. The pill's tooltip and the window's foot say so.
  - A card the page cannot place is never lost: any card without a resource is the watch's, on its node.
  - On a phone, the band in the Infra tab and the Acks 44 px high.
  - Nothing changes in Glorfindel: the card keeps its type and its empty resource.
  - Tests: `tests/unit/test_console_watch_cards.py`; mutants M7556–M7565 (`scripts/mutants/MBV1.py`).
