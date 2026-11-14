### Added
- A control-plane identity technique from a pinned public library is now a playable scenario
  (`annatar/scenarios/`): Annatar runs it from the injector host against an enrolled bench group,
  through the existing injector cycle, with a read-only directory probe of the initial state. It
  is this release's identity card; its control-plane detection is measured at the bench.

### Changed
- The scenario parser (`annatar validate` and every run) refuses a control-plane injector-library
  scenario that targets a VM: such a scenario acts on the control plane, not on a virtual machine,
  so a VM target type or a VM name is a misauthoring, refused before anything runs.
