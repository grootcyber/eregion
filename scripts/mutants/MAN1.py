"""MAN1 (#664): the public manual — the public rule held in docs/manuel/modules.yaml, a lot's pull
request that moves its brick, a release that delivers the bricks on main. M4607–M4611."""
MANUEL = "scripts/manuel.py"
RELEASE = "scripts/release.py"
_TEST = "tests/unit/test_manuel.py"

MUTANTS = [
    ("M4607", "a finding of an audit (V-<n>) no longer a security lot: its brick may carry a constat (MAN1)",
     MANUEL,
     'SENSIBLE = re.compile(r"(^|[^\\w])(SEC-|V-\\d|P-0)")',
     'SENSIBLE = re.compile(r"(^|[^\\w])(SEC-|P-0)")'),
    ("M4608", "a note allowed on a brick not delivered (MAN1)", MANUEL,
     '        if b.get("note") is not None and b.get("etat") != "livree":\n',
     "        if False:\n"),
    ("M4609", "a fragment counted as named by a brick that is not on main: the lot's PR never moves it (MAN1)",
     MANUEL,
     'on_main = {lot for b in data.get("briques") or [] if b.get("etat") == "main" for lot in b.get("lots") or []}',
     'on_main = {lot for b in data.get("briques") or [] for lot in b.get("lots") or []}'),
    ("M4610", "the release leaves the manual's bricks on main: never delivered (MAN1)", RELEASE,
     "        edits.update(manual_edits)\n",
     ""),
    ("M4611", "a field for what a brick waits on (an operator's gesture) accepted on the public manual (MAN1)",
     MANUEL,
     '"doc": False, "note": False}',
     '"doc": False, "note": False, "attend": False}'),
]
TESTS = {
    "M4607": _TEST,
    "M4608": _TEST,
    "M4609": _TEST,
    "M4610": "tests/unit/test_release.py::test_a_release_delivers_the_manual_s_bricks_on_main_in_the_same_commit",
    "M4611": _TEST,
}
