### Added
- **Eregion by role: a sheet per reader, on the project's site, every figure dated and sourced** (ADO2,
  #671 ; `docs/adoption/`, served at `https://grootcyber.github.io/eregion/adoption/`, linked from the README
  and the home page ; `docs/sessions.md`, « Les fiches d'adoption »). Nine sheets, in English: a CISO, a
  CDIO, a CTO, a security engineer, an SRE or platform team, a DPO, an MSSP or MSP, an auditor or an
  insurer, an executive or a CFO. Each says the reader's fear, what changes for them, three proofs, what to
  show them in five minutes, their objection and its answer, and the next step with its document. A section
  says what the project does not promise: Azure VMs today; identities and the control plane in detection
  only; not a SOC; `full_auto` planned, not available; autonomy on a real fleet not recommended yet; the
  ransomware times from a June run, to be replayed, and a second human step after a restore with the hosted
  watch; bench measures on small samples; no hosted offer, no price. The page runs no script, under a content
  policy that allows only itself; its fonts are the replay's; it prints one sheet per page and reads on a
  phone.
  - **One source for the site's figures, `docs/proofs.json`**: each figure has its value, what it says, its
    date (a day or a month), its kind (measured, an estimate, a setting, or a measure to take again, which
    the page says) and its source in the repository — a file, the sentence of it that gives the figure, and
    the heading it sits under or the run it comes from. `python3 scripts/adoption.py check` refuses a figure
    without its date or its source, a source the repository does not hold, a quote its file no longer says or
    that does not give the figure's numbers, a figure on the page shown otherwise than its source says, a
    digit on the page outside a figure of the source (a technique's id and the license aside), and a figure
    no page shows. The figures of the private preview the repository does not hold (vendors' prices, a test
    count, a catalogue size, a proof a month) are not on the page.
  - Tests: `tests/unit/test_adoption.py` (the rule, the real source and page, the page's policy and links,
    what it does not promise).
