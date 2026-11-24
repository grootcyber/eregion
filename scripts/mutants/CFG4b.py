"""CFG4b (#1136): « en masse » counted in VMs really touched (Q11) — glorfindel/config_class.py, `loud()`, apart
from the class, and its call in edit_config (glorfindel/config.py). M7286–M7289: a VM no discovery knows counted
(the file's names taken for VMs); a VM already human_only counted as touched; the default to human_only not said
loud; edit_config without the registry, no VM counted. Measured by tests/unit/test_config_edit.py."""
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
    ("M7289", "edit_config without the registry: no VM counted, a mass change said quietly (CFG4b, Q11)", CFG,
     "loud(text, new, _discovered_names() if vms is None else vms)", "loud(text, new, vms or ())"),
]

TESTS = {f"M{n}": _T for n in range(7286, 7290)}
