### Changed
- **The night and the release gate draw a new Hypothesis seed each round, said in the report; a pull
  request and a push stay derandomized** (SEED1, #655; `docs/design/preuves.md`, `docs/operations.md`).
  In CI, Hypothesis loads its `ci` profile (`derandomize=True`): the night's 10 000 sequences were the
  same every evening, and the gate's two rounds were one — yet `mutation_check.py` said each round drew
  new seeds. Measured: under that profile `--hypothesis-seed=N` changes nothing. A test's own seed does
  come first: `tests/unit/hypothesis_seed.py`, from the conftest, sets it on every property test and on
  every invariant machine, the tests' settings untouched (the machines' database still read and written).
  `EREGION_HYPOTHESIS_SEED` asks for it: a number (a replay), `draw`, or `profile`. When nothing is
  asked, a scheduled or dispatched run on GitHub draws one; a pull request and a push keep the profile.
  xdist workers share it. It is said at the end of the run, under each failing property test and in the
  job's summary. `scripts/mutation_check.py` draws the run's seed S, or takes `--seed S`: the unmutated
  runs on S, round r on S + r − 1. The seed is said at the start and at the end, and written in each
  shard's JSON (`seed`, `round_seeds`). The total says each shard's, and the command that replays a
  mutant that survived. The mutation shards (the gate's, the Monday's) and the night need no workflow
  change; the gate's two invariant jobs, which run on the version's pull request, draw once their step
  says `EREGION_HYPOTHESIS_SEED: draw` (a workflow edit, pushed by hand, with a `seed` input to replay
  a night on GitHub). Measured at 60 sequences under `CI=true`: M38, which survives twice when
  derandomized, is caught by one round of two, and its replay by seed gives the same verdicts.
  - Tests: `tests/unit/test_hypothesis_seed.py`, `tests/unit/test_mutation_shards.py`.
