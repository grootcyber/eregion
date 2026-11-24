### Added
- **The view « Relaxed » shows a backend whose discovery is cut** (CFG3b, #1148 ;
  `docs/design/configuration-console.md`, §6). `monitoring_backends[i].discovery.enabled: false` takes a line of
  the view when CFG4's `classify` says it relaxes: the backend, the key's path, and its effect as the code has
  it — a VM new to that backend is never seen, so no rule applied to all VMs watches it and the posture never
  checks it; the VMs it already knows stay as last seen, never evicted — with the VMs the registry keeps for
  it, « no reason » (a backend carries none) and the author « unknown ». The console shows it as the other
  lines, escaped. `sensitive_commands` and `origin_proof` (they tighten) and `allow_destructive` (no code reads
  it) stay out of the view, though `classify` takes their change as relaxing; the note says why, and says the
  decisions on `never_block` (the whole list with the configuration page, CFG7; a named network cited there
  always relaxes). Nothing is written to the configuration; the view's cost and cache are unchanged.
  - Tests : `tests/unit/test_relaxed_view.py`.
