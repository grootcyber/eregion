### Added
- **The preflight says whether a fault can run, and be seen, before the bench session spends ten minutes of noise on it** (G1b, part of #76; `gothmog/README.md`, « Le préflight dit si la panne peut tourner, et être vue »). Past the steady state, `gothmog preflight <fault>` reads three things more, nothing written:
  - Orodruin's own rights to start and to cancel this experiment, at its scope. The contract arms on G0's experiment alone, so an experiment applied after the last `make orodruin-lock YES=1` would answer 403.
  - The Chaos agent's extension installed on each VM the experiment reaches through it.
  - Each series the fault's effect reads, collected on each target over the last 30 minutes. A counter collected under another name would run the noise unseen.

  Each read gets its line. One not held, or unreadable, refuses: « not ready ». A shutdown or a restart asks its rights only. The run does not change. The bench session (the three noise faults, then `vm-shutdown` again, its proof ageing past 30 days on 30/11) is written out step by step, with what each refusal asks.
  - Tests: `tests/unit/test_gothmog_readiness.py` (mutants M6586–M6605, `scripts/mutants/G1b.py`).
