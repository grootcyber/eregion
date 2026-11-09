### Fixed
- **The invariant machine sees again, on its own, three network-response mutants the 0.5.8 release gate
  found only by their frozen sequences** (MUT4, #647; `docs/design/preuves.md`). M19 (a block verified
  against the addresses recorded when it was written), M31 (one deny's priority used for both directions)
  and M38 (a block gone behind the quarantine, unsaid) were `FIXED-ONLY` at the gate (500 sequences, two
  rounds). Nothing they measure had changed since the 0.5.7: each needs three or four precise steps,
  which the machine drew together in a few sequences in a thousand. In CI, Hypothesis loads its `ci`
  profile on its own (`derandomize=True`): the machine's sequences come from a seed computed on the
  `IsolationMachine` source, so the gate's two rounds replay the same 500 sequences, and any edit of the
  class (I3K's) draws another set — the 0.5.8's held none of the three. A composite rule,
  `a_hold_moved_under_it`, makes the three states common: a VM blocked, then an address of its NIC
  changed; a VM isolated by rules, then one of our outbound denies moved behind a customer's outbound
  allow; a VM blocked then isolated by quarantine, then the block's rules taken off by a
  `terraform apply`, and the reassertion. Each is now caught by about one sequence in thirty to fifty.
  No oracle changed, none added; the CI derandomization itself is left as it is (a decision for the gate).
  - Tests: `tests/unit/test_invariants.py` (`a_hold_moved_under_it`).
