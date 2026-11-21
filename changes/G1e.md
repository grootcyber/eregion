### Added
- **Gothmog arms on the base contract with a Stratus subscription set, held on Gothmog's side** (G1e, part of #76; `gothmog/README.md`, the bench session's step 0). On the bench on 20/11, Gothmog fell passive: `EREGION_STRATUS_SUBSCRIPTION` was set in Orodruin's `orodruin.env`, and Gothmog's container mounts neither the federated assertion nor the sandbox proof. ORG1 (#1003) scopes the two Stratus guarantees to an arming for Stratus.
  - A test now holds Gothmog's side: `gothmog preflight` and `gothmog run` arm through the real `arm()` and `check()`, with the subscription set and neither the assertion nor the proof.
  - Every reader of the contract is the real one. The cloud readers run on a faked transport, with no network, and the cap and the two Stratus guarantees run exactly as shipped.
  - Its premise is checked first: an arming for Stratus would refuse here, on those two guarantees alone.
  - Tests: `tests/unit/test_gothmog.py` (mutants M6924–M6925, `scripts/mutants/G1e.py`).
