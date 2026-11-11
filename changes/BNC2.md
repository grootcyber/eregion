### Added
- **Design: the bench that measures itself** (BNC2, #684; `docs/design/banc-autonome.md`). The
  destructive T1486 run stays launched by the operator (`make bench-run`, from the workstation or the
  phone through it), and its restore stays a second human gesture, from the isolation card once FS1g
  and TOT1 exist, from `make bench-restore` until then. What surrounds them is automated: the
  preflight, a calm check, the lift by the host, and a masked report composed alone on the
  workstation and then on the host at the end of the run, with the rights already there. A dated
  slot plays a non-destructive drill of DRL1 once, at an hour armed by the operator. Linked from the
  weekly drill design and the T1486 bench guide. No code yet.
