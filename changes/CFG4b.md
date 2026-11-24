### Changed
- **A change to `human_only` is said loud by the VMs it really touches, no longer by its entries** (CFG4b, #1136 ;
  `docs/design/configuration-console.md`, §5.4, Q11). `glorfindel/config_class.py`: `loud(before, after, vms)`,
  apart from the class, which stays a function of the two texts — loud when the default turns to `human_only`,
  or when five or more of the VMs the discovery knows go from a bolder mode to `human_only` at once; a pattern
  counts the VMs it designates, a name no discovery knows counts for nothing, a VM already `human_only` is not
  touched. `edit_config` calls it with the discovery's registry and returns `loud` and `loud_said`
  (« response disarmed on N VMs »). The time window (five VMs in ten minutes) comes with CFG5.
  - Tests : `tests/unit/test_config_edit.py`.
