"""CFG3 (#1139): the view « Relaxed », read-only (glorfindel/relaxed.py, eregion_console/api.py,
eregion_console/static/glorfindel.js). M7310–M7319: a latent relaxation left out of the view; the view written
by the console; a pattern without what it designates today; a file refused read as « nothing relaxed »; a
discovery unreadable read as « no VM »; a twin entry hidden; the reason not carried; an old view not said; an
entry's object written raw on the page (#254); a removal that empties a list classed on a refused file. Measured
by tests/unit/test_relaxed_view.py (and tests/unit/test_console_escaping.py for M7318). M7330–M7334: below."""
REL = "glorfindel/relaxed.py"
_T = "tests/unit/test_relaxed_view.py"

MUTANTS = [
    ("M7310", "a latent relaxation left out of the view: an exact bold entry that changes nothing today (CFG3)", REL,
     "            if said[\"class\"] != \"relax\":\n                continue\n",
     "            if said[\"class\"] != \"relax\" or said.get(\"latent\"):\n                continue\n"),
    ("M7311", "the view written by the console: its route computes and writes it instead of reading it (CFG3)",
     "eregion_console/api.py", "    return await asyncio.to_thread(relaxed.load)\n",
     "    return await asyncio.to_thread(relaxed.publish)\n"),
    ("M7312", "a pattern without what it designates today: only the VM of its exact name counted (CFG3)", REL,
     "    hit = [n for n in names if vm_name_matches(n, pattern)]\n",
     "    hit = [n for n in names if n.lower() == pattern.lower()]\n"),
    ("M7313", "a file the strict reading refuses read as « nothing relaxed » (CFG3)", REL,
     "                              \"error\": f\"{type(exc).__name__}: {str(exc)[:400]}\"}\n            return view\n",
     "                              \"error\": f\"{type(exc).__name__}: {str(exc)[:400]}\"}\n"
     "            return {**view, \"entries\": [], \"count\": 0}\n"),
    ("M7314", "a discovery registry that can't be read read as « no VM »: a pattern says 0 VMs (CFG3)", REL,
     "        return None, f\"registry unreadable ({type(exc).__name__}: {str(exc)[:120]})\"\n",
     "        return [], \"\"\n"),
    ("M7315", "a twin entry hidden: taken out alone it changes nothing, and is never classed alone (CFG3)", REL,
     "        if said[\"class\"] == \"neutral\" and isinstance(path[-1], int):\n", "        if False:\n"),
    ("M7316", "the reason of an entry not carried to the view (CFG3)", REL,
     "\"what\": what, \"reason\": reason,", "\"what\": what, \"reason\": \"\","),
    ("M7317", "a view the watch no longer refreshes read as fresh (CFG3)", REL,
     " else \"stale\" if age > STALE_S else \"fresh\"\n", " else \"fresh\"\n"),
    ("M7318", "an entry's object written raw on the config page (CFG3, #254)", "eregion_console/static/glorfindel.js",
     "<span class=\"cfg-key\">${_attr(e.object)}</span>", "<span class=\"cfg-key\">${e.object}</span>"),
    ("M7319", "a removal that empties a list leaves it empty: the entry classed on a file the strict reading "
     "refuses (CFG3)", REL, "        if holder[key] not in ([], {}, None):\n", "        if True:\n"),
]

# The review of CFG3: M7330–M7334 — the cost of the view, and what a mode pattern designates.
MUTANTS += [
    ("M7330", "the view never computed again: a file, a discovery or a --mode changed, the old view written "
     "(CFG3 review)", REL, "    if (last is not None and _LAST.get(\"inputs\") == key\n",
     "    if (last is not None\n"),
    ("M7331", "the view computed again every minute, nothing changed: quadratic, each minute (CFG3 review)", REL,
     "    if (last is not None and _LAST.get(\"inputs\") == key\n", "    if (False and _LAST.get(\"inputs\") == key\n"),
    ("M7332", "a bold mode pattern said to hold a VM a pattern as long and more prudent holds (CFG3 review)", REL,
     "    return mine and cfg.autonomy.resolve(name) == mode\n", "    return mine\n"),
    ("M7333", "every line of the view said at the start: a long file floods the watch's log (CFG3 review)", REL,
     "    for e in view[\"entries\"][:most]:\n", "    for e in view[\"entries\"]:\n"),
    ("M7334", "the view computed in the watch's loop, not in a thread of its own: « Verify » waits (CFG3 review)",
     "glorfindel/watch/local_reads.py", "        self._relaxed_thread.start(self._relaxed_run)\n",  # WCH2
     "        self._relaxed_run()\n"),
]

TESTS = {**{f"M{n}": _T for n in (*range(7310, 7320), *range(7330, 7335))},
         "M7318": f"{_T} tests/unit/test_console_escaping.py"}
