### Added
- **The configuration is written in round trip** (CFG4, #1129 ; `docs/design/configuration-console.md`, §3.2,
  §5). `glorfindel/config_edit.py`: `apply_change(text, op)` for a closed list of operations (`set_mode`,
  `unset_mode`, `set_default_mode`, `exclude`, `unexclude`, `never_block_add`, `never_block_remove`), their
  fields exact, and `inverse()` for each; the text spliced where PyYAML reads each node, so comments and every
  other byte stay, with no library added; an exact VM name only, never a pattern; nothing produced that the
  strict reading refuses, or that does not read back as the dictionary asked for; `digest()`, the SHA-256 of
  the bytes. `glorfindel/config_class.py`: the class of a change (relax, tighten, neutral, latent, loud) from
  the two texts alone, never the discovery nor the operation's name — an added exclusion relaxes, an exact
  bold entry relaxes even when it changes nothing today, a `never_block` entry wider than one private host
  relaxes (Q10), the default to `human_only` is loud (Q11).
  - Tests : `tests/unit/test_config_edit.py`.

### Changed
- **The console's and `glorfindel activate`'s mode writes keep the file's comments** (CFG4, #1129). They used
  to dump the file again (`yaml.safe_dump`), losing them. A file the strict reading refuses is no longer
  rewritten: the change of mode is refused until it is corrected by hand.
