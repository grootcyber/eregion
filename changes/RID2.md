### Added
- **A pinned public library's directory identity technique is now a playable scenario**
  (`annatar/scenarios/`), the directory side of the 0.6.0 identity card: the injector adapter now
  also runs the library's directory techniques (not only control-plane ones), each held to the
  same closed allow-list the catalogue vouches for, run from the injector host through the existing
  cycle, with a read-only directory probe of the initial state. Its directory-log detection will be
  measured at the bench with the 0.6.0 (#844 open). (RID2, #844)

### Changed
- **A directory injector-library scenario needs no resource group** (`annatar/runner/parser.py`,
  `schemas/`): a directory technique acts in the tenant directory, under no resource group, so the
  scenario and catalogue schemas require none for such a target; every other target still names its
  group. (RID2, #844)
