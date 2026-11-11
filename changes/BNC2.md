### Added
- **Design: the bench that measures itself** (BNC2, #684; `docs/design/banc-autonome.md`). The
  destructive T1486 run stays launched by the operator (`make bench-run`, from the workstation or the
  phone through it), and its restore stays a second human gesture, from the isolation card once FS1g
  and TOT1 exist, from `make bench-restore` until then. What surrounds them is automated: the
  preflight; a calm check that refuses rather than waits; a refusal ("restore first") on a VM that
  carries a destructive run without a restore since, the runs listed from Azure's activity log of
  the VM (every Run Command since its last restore, whatever its caller; only the host's own
  session drain left out), the technique of the current Orodruin's runs from its journal (an
  unreadable one counting as destructive), and the restores from the vault's jobs; after the typed name, the newest recovery
  point checked clean (taken after the VM's last restore and outside any quarantine) and, when it
  is not, a new one asked through the snapshot button's own route of the host's console (a signed
  request the watch executes under the action queue), followed to its end, then the preflight played again before the attack; the lift by the host;
  and a masked report composed alone on the workstation and then on the host at the end of the
  run, with the rights already there. A dated slot plays a non-destructive drill of DRL1 once, at an
  armed hour, one slot at a time; the weekly drill's Logic App wakes Orodruin for it by reading the
  slot's permit in the exercise channel, its read bounded to that one blob, and let through the
  channel's firewall by a resource instance rule for that Logic App alone, the bypass kept at None. The design questions are
  settled by the operator's decisions of 11/11. Linked from the weekly drill design and the T1486
  bench guide. No code yet.
