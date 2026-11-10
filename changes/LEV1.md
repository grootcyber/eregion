### Added
- **Design: the lift after a restore, alone and on probation, unless the door is proven open** (LEV1, #690;
  `docs/design/levee-probation.md`, linked from `docs/glorfindel.md` and the threat model). A design only,
  nothing coded. One rule for every lift after a restore (the watch, `glorfindel release`, the console, the
  bot; a human's lift reads the restore on Azure itself), with three verdicts:
  - an exercise proven by the control plane (Orodruin's identity acting on the VM within the run's
    published window, no third party), on the bench or the twin only, never in production, lifts without
    probation;
  - a real incident lifts into probation;
  - the quarantine is kept, with a card, when a detection on the VM is dated after the restore's end, or
    when a third party that acted on the VM keeps its rights or its rights cannot be read in full. The
    activity log is read with its child resources (extensions, managed Run Commands, NSG rules). Glorfindel
    and the restoring principals are excused only for their own operations, targets and windows, and
    expected callers only per operation (never a Run Command, VMAccess or a disk export). The card carries
    the revocation plan in IR1a's form and a Verify button.

  The mode still decides who executes. Probation: 24 h by default. The administration ports are closed from
  the Internet by a named Glorfindel rule; its state is written before it, so that the control-plane
  detection, the reassertion, the orphan sweep and `reset` recognize it, and it is laid and read back before
  the quarantine is removed. Probation-only rules and thresholds live in the rules file. The re-isolation on
  any signal dated after the restore's end is decided by code at the head of `decide`, guard by guard,
  without the model (a card in `human_only`; Jonathan's decision of 10/11), and its cycles never go to the
  memory. The original disks are named on every card as evidence, never touched. The model's input stays
  byte-identical. Also: the vocabulary (quarantine, probation), eight invariant properties, the bench
  exercise (T1486 "as a real incident", then T1136.001 during probation), the lots LEV2 to LEV8, and the
  questions left for Jonathan.
