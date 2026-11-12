"""MEN4 (#748, with the documentation part of RAN1b, #665): the ransomware times of the site are those of
the bench run of 12/11, measured and sourced in its page; « 0 / 41 » disruptive actions judged wrong is a
figure to measure again, after bree's isolation judged wrong on 11/11. M4850–M4852."""
PROOFS = "docs/proofs.json"
_TEST = "tests/unit/test_adoption.py"

MUTANTS = [
    ("M4850", "« 0 / 41 » shown as a measure, though bree's isolation was judged wrong since (MEN4)", PROOFS,
     '      "kind": "to-remeasure",\n      "note": "since, an isolation of a bench VM',
     '      "kind": "measured",\n      "note": "since, an isolation of a bench VM'),
    ("M4851", "the time to contain a ransomware VM sourced to the run of 09/06, from before Imladris (MEN4)",
     PROOFS,
     '        "run": "20261112T091448Z-b218",\n        "quote": "463,1 s',
     '        "run": "20260609T190824Z",\n        "quote": "463,1 s'),
    ("M4852", "the measured time to contain a ransomware VM shown as an estimate (MEN4)", PROOFS,
     '      "date": "2026-11-12",\n      "kind": "measured",\n      "source": {\n'
     '        "path": "docs/banc-t1486.md",\n        "anchor": "les-chiffres-du-1211",\n'
     '        "run": "20261112T091448Z-b218",\n        "quote": "463,1 s',
     '      "date": "2026-11-12",\n      "kind": "estimate",\n      "source": {\n'
     '        "path": "docs/banc-t1486.md",\n        "anchor": "les-chiffres-du-1211",\n'
     '        "run": "20261112T091448Z-b218",\n        "quote": "463,1 s'),
]
TESTS = {
    "M4850": _TEST,
    "M4851": _TEST,
    "M4852": _TEST,
}
