### Added
- **An interactive replay of the loop, on the project's site** (PRES1, #658 ; `docs/replay/`, served at
  `https://grootcyber.github.io/eregion/replay/`, linked from the README and the home page). A ransomware
  simulation on a bench VM, in ten chapters: Annatar's checks before any cloud call, the attack, the
  `ransomware-disk-write` detection, the questions Glorfindel asks before deciding, the guards on its decision,
  the quarantine NSG on every network card (your own NSG kept intact), the proof read back from Azure, the
  restore, the release and the memory. It plays in `human_only` (every step approved by you), `non_disruptive`
  (contained alone, the restore approved by you) and `full_auto`, said planned and not available today. The
  operator's screen shows what reaches you, in the formats of the bot and the console (texts of the bot
  translated from French). Times shown as measured are the README's (55–71 s, about a minute, 21 min 29 s);
  everything else is said illustrative. The page is static and loads nothing from elsewhere: its fonts are
  served with it (SIL Open Font License, `docs/replay/fonts/`), its images carry no metadata.
