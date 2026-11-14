### Added
- **A pinned public library's control-plane identity technique is now a playable scenario**
  (`annatar/scenarios/`), the scenario behind the identity card of the 0.6.0: Annatar runs it from
  the injector host against an enrolled bench group, through the existing injector cycle, with a
  read-only directory probe of the initial state. Its control-plane detection will be measured at
  the bench with the 0.6.0 (#819 open). (RID1, #822)

### Changed
- **A control-plane injector-library scenario that targets a VM is refused at authoring**
  (`annatar/runner/parser.py`): it acts on the control plane, not a virtual machine, so a VM
  target type or a VM name is a misauthoring, refused before anything runs. (RID1, #822)
