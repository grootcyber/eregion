"""CFG4b (#1136): « en masse » counted in VMs really touched (Q11) — glorfindel/config_class.py, `loud()`, apart
from the class, and its call in edit_config (glorfindel/config.py). M7286–M7289: a VM no discovery knows counted
(the file's names taken for VMs); a VM already human_only counted as touched; the default to human_only not said
loud; edit_config without the registry, no VM counted. The review (Jonathan, 24/11), M7335–M7337: a registry
empty or unreadable not falling back on the entries; loud() without a list counting nothing; edit_config's
`loud` left to the class's count of entries. Measured by tests/unit/test_config_edit.py."""
CLS = "glorfindel/config_class.py"
CFG = "glorfindel/config.py"
_T = "tests/unit/test_config_edit.py"

MUTANTS = [
    ("M7286", "a VM no discovery knows counted: the file's exact names taken for VMs (CFG4b, Q11)", CLS,
     "    names = sorted({str(v).strip().lower() for v in vms} - {\"\"})\n",
     "    names = sorted({str(v).strip().lower() for v in (*vms, *(r.match for r in a.autonomy.assets))} - {\"\"})\n"),
    ("M7287", "a VM already human_only counted as touched: loud on a change that disarms nothing (CFG4b, Q11)", CLS,
     "               if _PRUDENCE.get(b.autonomy.resolve(n), 0) > 0 and _PRUDENCE.get(a.autonomy.resolve(n), 0) == 0]\n",
     "               if _PRUDENCE.get(a.autonomy.resolve(n), 0) == 0]\n"),
    ("M7288", "the default to human_only not said loud when it touches fewer than five VMs known (CFG4b, Q11)", CLS,
     "    if default:\n", "    if False:\n"),
    ("M7289", "edit_config without the registry: no VM counted, a mass change said by entry (CFG4b, Q11)", CFG,
     "            names, unread = _discovered_names() if vms is None else",
     "            names, unread = ([], \"x\") if vms is None else"),
]

# The review of CFG4b (Jonathan, 24/11): a registry empty or unreadable falls back on the entries.
MUTANTS += [
    ("M7335", "a registry empty or unreadable not falling back on the entries: a console that empties it "
     "silences a change en masse (CFG4b review)", CFG,
     "            said[\"loud_said\"] = loud(text, new, names if names else None)\n",
     "            said[\"loud_said\"] = loud(text, new, names)\n"),
    ("M7336", "loud() without a list counts nothing instead of the entries (CFG4b review)", CLS,
     "        vms, unit = [r.match for r in (*b.autonomy.assets, *a.autonomy.assets)], \"entries\"\n",
     "        vms, unit = [], \"entries\"\n"),
    ("M7337", "edit_config's loud left to the class's count of entries, not the announcement (CFG4b review)", CFG,
     "            said[\"loud\"] = said[\"loud_said\"] is not None\n", ""),
]

TESTS = {f"M{n}": _T for n in (*range(7286, 7290), *range(7335, 7338))}
