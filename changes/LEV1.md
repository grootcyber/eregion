### Added
- **Design: the lift after a restore, alone and on probation, unless the door is proven open** (LEV1, #690;
  `docs/design/levee-probation.md`, linked from `docs/glorfindel.md` and the threat model). A design only,
  nothing coded. One rule for every lift after a restore (the watch, `glorfindel release`, the console, the
  bot), with three verdicts: an exercise proven by the control plane (Orodruin's identity acting on the VM
  within the run's published window, no third party) lifts without probation; a real incident lifts into
  probation; a third party that acted on the VM, as the activity log says, and keeps its rights (or whose
  rights cannot be read in full) keeps the quarantine, with a card that carries the revocation plan in
  IR1a's form and a Verify button. The mode still decides who executes. Probation: 24 h by default, the
  administration ports closed from the Internet by a named, reversible Glorfindel rule that the
  reassertion and the orphan sweep recognize, probation-only rules and thresholds in the rules file, and a
  re-isolation on any signal decided by code, without the model (a card in `human_only`). The original
  disks are named on every card as evidence, never touched. The model's input stays byte-identical. The
  vocabulary (quarantine, probation), six invariant properties, the bench exercise (T1486 "as a real
  incident", then T1136.001 during probation), the lots LEV2 to LEV8, and ten questions.
