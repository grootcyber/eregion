"""CON-D (#735): the console's live feed says the day of a line that is not today's, in UTC
(« yesterday », or its date), and orders its lines by their full moment, the latest on top —
never by the time of day alone. M4820–M4823, measured by tests/unit/test_console_feed_day.py
(the page read in its text: no browser in the suite)."""
API = "eregion_console/api.py"
JS = "eregion_console/static/glorfindel.js"
_TESTS = "tests/unit/test_console_feed_day.py"

MUTANTS = [
    ("M4820", "the feed's history ordered by the time of day alone: today's 00:00 before yesterday's 23:59 (CON-D)",
     API,
     "    entries.sort(key=_feed_order)\n    return entries[-n:]\n",
     '    entries.sort(key=lambda e: e.get("time", ""))\n    return entries[-n:]\n'),
    ("M4821", "a turn of the live feed in the order of its files, not of its lines' moments (CON-D)", API,
     "    out.sort(key=_feed_order)\n    return out\n",
     "    return out\n"),
    ("M4822", "a line of the feed says its time alone, whatever its day: yesterday's snapshot read as today's (CON-D)",
     JS,
     "  const ts = _feedWhen(entry, Date.now());\n",
     "  const ts = fmtTime(entry.timestamp);\n"),
    ("M4823", "a line of the feed put on top by its arrival, not by its moment: a late line above newer ones (CON-D)",
     JS,
     "    if (row._at <= el._at) { list.insertBefore(el, row); return; }\n",
     "    list.insertBefore(el, row); return;\n"),
]
TESTS = {f"M{n}": _TESTS for n in range(4820, 4824)}
