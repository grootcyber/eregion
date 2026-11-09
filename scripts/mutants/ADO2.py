"""ADO2 (#671): Eregion by role — every figure of the site dated and sourced in docs/proofs.json, and shown
on the page as its source says (scripts/adoption.py). M4624–M4627; after the review, M4633–M4635 (a card
that says more than its fields, a figure in a title or a label, a figure in a meta's content)."""
ADOPTION = "scripts/adoption.py"
_TEST = "tests/unit/test_adoption.py"

MUTANTS = [
    ("M4624", "a figure without its date accepted on the site (ADO2)", ADOPTION,
     "        if day is None:\n",
     "        if False:\n"),
    ("M4625", "a digit of the page outside docs/proofs.json accepted: a figure without a source (ADO2)", ADOPTION,
     '        if re.search(r"\\d", bare):\n',
     "        if False:\n"),
    ("M4626", "a quote its source no longer says accepted: the figure moved, the page did not (ADO2)", ADOPTION,
     "        if norm(quote) not in norm(where):\n",
     "        if False:\n"),
    ("M4627", "a figure shown on the page otherwise than its source says accepted (ADO2)", ADOPTION,
     '        if f.get("value") != norm(str(p.get("value"))):\n',
     "        if False:\n"),
]
MUTANTS += [
    ("M4633", "a card's text outside its fields read by nobody: « 99% of attacks stopped. » passes (ADO2 review)",
     ADOPTION,
     '        if s["loose"].replace("·", "").strip():\n',
     "        if False:\n"),
    ("M4634", "a figure in a title, a label or an image's text unchecked (ADO2 review)", ADOPTION,
     '        self.outside += [a[k] for k in ("alt", "title", "aria-label") if a.get(k)]\n',
     ""),
    ("M4635", "a figure in a meta's content, the description included, unchecked (ADO2 review)", ADOPTION,
     '        if tag == "meta" and a.get("name", "").lower() != "viewport":\n',
     "        if False:\n"),
]
TESTS = {
    "M4624": _TEST,
    "M4625": _TEST,
    "M4626": _TEST,
    "M4627": _TEST,
    "M4633": _TEST,
    "M4634": _TEST,
    "M4635": _TEST,
}
