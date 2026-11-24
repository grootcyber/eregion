"""CFG3c (#1154): the view « Relaxed » shows the expected origins, in force only by the switch the watch reads
(glorfindel/relaxed.py, eregion_console/static/glorfindel.js). M7400–M7407: the expected origins left out of the
view; the switch inverted; an origin said in force, or its effect said, whatever the switch; the switch out of
the cache's key; a named network cited by an origin without effect said in force; the console showing in force
what the watch did not write in force; the watch's start lines no longer saying « sans effet ». Measured by
tests/unit/test_relaxed_view.py."""
REL = "glorfindel/relaxed.py"
JS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_relaxed_view.py"

MUTANTS = [
    ("M7400", "the expected origins left out of the view: `network_zones.expected_origins` no longer walked (CFG3c)", REL,
     ", ((\"network_zones\", \"expected_origins\"), \"expected_origin\"))\n",
     ")\n"),
    ("M7401", "the switch inverted: an origin shown in force while GLORFINDEL_LATERAL is off, and the reverse (CFG3c)",
     REL,
     "    return {\"name\": lateral.SWITCH, \"on\": bool(on), \"said\": said}\n",
     "    return {\"name\": lateral.SWITCH, \"on\": not bool(on), \"said\": said}\n"),
    ("M7402", "an expected origin always said in force, the switch off too (CFG3c)", REL,
     "in_force=switch[\"on\"] if kind == \"expected_origin\" else True))\n",
     "in_force=True))\n"),
    ("M7403", "an expected origin's effect said in force whatever the switch: the sentence of the switch on (CFG3c)",
     REL,
     "        return str(item), EXPECTED_ON if switch[\"on\"] else EXPECTED_OFF\n",
     "        return str(item), EXPECTED_ON\n"),
    ("M7404", "the switch out of the cache's key: a switch changed at the restart leaves the last view (CFG3c)", REL,
     "mode_override or \"\",\n            switch[\"on\"], switch[\"said\"])\n",
     "mode_override or \"\")\n"),
    ("M7405", "a named network cited only by an origin without effect said in force (CFG3c)", REL,
     "in_force=any(ln[\"in_force\"] for ln in citing)))\n",
     "in_force=True))\n"),
    ("M7406", "the console shows an expected origin in force unless the watch wrote `false` (CFG3c)", JS,
     "  return e.in_force === true\n",
     "  return e.in_force !== false\n"),
    ("M7407", "the watch's start lines no longer say an origin without effect (CFG3c)", REL,
     "                    + (\"\" if e.get(\"in_force\", True) else \" (sans effet)\")\n",
     ""),
]

TESTS = {f"M{n}": _T for n in range(7400, 7408)}
