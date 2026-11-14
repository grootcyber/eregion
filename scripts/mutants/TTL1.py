"""TTL1 (#812): the isolation's TTL read in one place (`config.isolation_ttl_h`) for the watch and for
`check-ttl`; `--ttl` wins when given, 0 included, and 0 escalates every isolation at once; a negative or
unreadable TTL is refused — by `check-ttl` (its reason, code 1, nothing escalated, `--dry-run` included),
said by the watch, which keeps 4 h and never stops for it. M5295–M5304, measured by
tests/unit/test_isolation_ttl.py."""
CONFIG = "glorfindel/config.py"
CLI = "glorfindel/cli.py"
_T = "tests/unit/test_isolation_ttl.py"

MUTANTS = [
    ("M5295", "`check-ttl --ttl 0` silently the variable or 4 h again (`ttl or …`), as before TTL1", CLI,
     "        ttl_h = _cfg.isolation_ttl_h(ttl)        # the watch's own reading (TTL1)\n",
     "        ttl_h = _cfg.isolation_ttl_h(ttl or None)        # the watch's own reading (TTL1)\n"),
    ("M5296", "the option wins only when it is not 0: `--ttl 0` falls through to the variable (TTL1)", CONFIG,
     "    if option is not None:\n        value, said = option, f\"--ttl {option:g}\"\n",
     "    if option:\n        value, said = option, f\"--ttl {option:g}\"\n"),
    ("M5297", "a negative TTL accepted: it escalates every isolation at once, as 0 does (TTL1)", CONFIG,
     "    if value < 0:\n        raise TTLRefused(",
     "    if False:\n        raise TTLRefused("),
    ("M5298", "`nan` accepted as a TTL: `age_h < nan` is never true, every isolation escalated (TTL1)", CONFIG,
     "    if math.isnan(value):\n",
     "    if False:\n"),
    ("M5299", "an unreadable variable raises its bare ValueError again: the watch stops at its start, "
     "`check-ttl` gives no reason (TTL1)", CONFIG,
     "            raise TTLRefused(f\"{said} : illisible, pas un nombre d'heures\") from None\n",
     "            raise\n"),
    ("M5300", "the watch keeps 0 h on a refused TTL, not 4 h: every isolation escalated at once (TTL1)", CLI,
     "        ttl_h = _cfg.ISOLATION_TTL_H\n        said = ",
     "        ttl_h = 0.0\n        said = "),
    ("M5301", "the watch's refused TTL said on the console only, never in the log (TTL1)", CLI,
     "        logging.getLogger(\"glorfindel.ttl\").warning(\"TTL refusé — %s\", said)\n",
     ""),
    ("M5302", "the watch reads its TTL by its own `float(...)` again: an unreadable variable stops it, a "
     "negative one passes unsaid (TTL1)", CLI,
     "    ttl_h = _watch_ttl_h()             # never stops the watch (TTL1)\n",
     "    ttl_h = float(os.environ.get(\"GLORFINDEL_ISOLATION_TTL_H\") or \"4\")\n"),
    ("M5303", "`check-ttl` falls back to 4 h on a refused TTL instead of refusing it: escalates, code 0 "
     "(TTL1)", CLI,
     "        console.print(f\"[bold red]TTL refusé[/bold red] — {_esc_markup(str(exc))} ; rien n'est escaladé.\")\n"
     "        raise SystemExit(1)\n",
     "        console.print(f\"[bold red]TTL refusé[/bold red] — {_esc_markup(str(exc))} ; rien n'est escaladé.\")\n"
     "        ttl_h = _cfg.ISOLATION_TTL_H\n"),
    ("M5304", "`check-ttl --dry-run` returns before reading the TTL: a negative one passes, code 0 (TTL1)", CLI,
     "    from glorfindel import config as _cfg\n    try:\n        ttl_h = _cfg.isolation_ttl_h(ttl)",
     "    from glorfindel import config as _cfg\n    if dry_run:\n        return\n    try:\n"
     "        ttl_h = _cfg.isolation_ttl_h(ttl)"),
]
TESTS = {mid: _T for mid, *_ in MUTANTS}
