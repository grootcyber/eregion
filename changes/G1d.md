### Added
- **A fault waits for the previous exercise window on its target, and says until when** (G1d, part of #76; `gothmog/README.md`, « Une panne attend la fenêtre de la précédente »). On 20/11, three faults on gondolin ran 5 to 13 min apart. A card of the first fell inside its window (its end plus 15 min of grace) after the next fault had started. Two faults were left unmeasured, and a third was taken for an attack it was not.
  - `gothmog run` and `gothmog preflight` now first read this host's Gothmog windows, before the watch (V1), the contract and anything that reaches the cloud. A window on one of the fault's targets that still runs, grace included, refuses the fault and says until when, in UTC.
  - The target is compared without its case, by its full id. Without a subscription, it is compared by the VM's name, which refuses more, never less.
  - No window ever written lets the fault go. A directory that cannot be read, a file that cannot be read or holds no window: refused. What cannot be read is never « no window ».
  - The run's window is now opened and closed on the engine's clock.
  - Only a fault's window counts: a fault waits for the previous fault, never for a technique, which a Dagorlad request chains with a fault on purpose (DG-b).
  - Tests: `tests/unit/test_gothmog.py` (mutants M6865–M6874, `scripts/mutants/G1d.py`).
