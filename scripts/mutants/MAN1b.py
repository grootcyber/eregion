"""MAN1b (#676): the public manual in English — a text of the manual that reads French refused, a security
brick named « Security hardening » by the manual and by the page whatever the YAML says. M4642–M4644."""
MANUEL = "scripts/manuel.py"
PAGE = "docs/manuel/manuel.js"
_TEST = "tests/unit/test_manuel.py"

MUTANTS = [
    ("M4642", "a text of the manual in French accepted: a lot's brick written in French reaches the page (MAN1b)",
     MANUEL,
     "                if isinstance(it.get(k), str) and FRENCH.search(it[k]):\n",
     "                if False:\n"),
    ("M4643", "the page shows a security brick's name as the YAML writes it, not the neutral one (MAN1b)", PAGE,
     "  const nameOf = (b) => (sensible(b) ? NEUTRAL : b.nom);\n",
     "  const nameOf = (b) => b.nom;\n"),
    ("M4644", "the neutral title of a security brick back in French, on an English manual (MAN1b)", MANUEL,
     'NEUTRAL = "Security hardening"\n',
     'NEUTRAL = "Durcissement de sécurité"\n'),
]
TESTS = {
    "M4642": _TEST,
    "M4643": _TEST,
    "M4644": _TEST,
}
