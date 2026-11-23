"""ENQ4 (#1085): the loop of the enquiry, at the harness only (glorfindel/enquiry/loop.py, reference.py).
M7123–M7131: the budget N passed; the delay T passed; an id outside the catalogue's list read; a VM from
the model; an obligatory read skipped; a citation not checked; « sans objet », or an announced read,
said « vide »; a read of today filled by the memory's reference; « as usual » received without a human
verdict, or on a grave technique. M7132 (its review): a read the model asked counted as a gap.
Measured by tests/unit/test_enquiry_loop.py."""
LOOP = "glorfindel/enquiry/loop.py"
REFERENCE = "glorfindel/enquiry/reference.py"
_T = "tests/unit/test_enquiry_loop.py"

MUTANTS = [
    ("M7123", "the budget N passed: a read the model asks past N is run (ENQ4, §5.1)", LOOP,
     "        if self.out.choisies > self.budget.n:\n",
     "        if False:\n"),
    ("M7124", "the delay T passed: T counted afresh at each step, never for the whole enquiry (ENQ4, §5.1)", LOOP,
     "        return self.fin - self.horloge()\n",
     "        return self.t\n"),
    ("M7125", "an id outside the list the sheet and the system permit read (ENQ4, §5.1)", LOOP,
     "        asked = catalog.ask(read_id, self.permises)\n",
     "        asked = catalog.ask(read_id)\n"),
    ("M7126", "a VM given by the model, not the registry's (ENQ4, §5.1)", LOOP,
     "        lu = self._lancer([asked], self.vm)[0]      # the registry's VM, never one of the model's (§5.1)\n",
     "        lu = self._lancer([asked], str(args.get(\"vm\") or self.vm))[0]\n"),
    ("M7127", "an obligatory read of the sheet skipped: never run before the model (ENQ4, §5.2)", LOOP,
     "        obligatoires = self.fiche.obligatoires if self.fiche is not None else ()\n",
     "        obligatoires = ()\n"),
    ("M7128", "a citation not checked: every proof the model cites taken as read (ENQ4, §6.3)", LOOP,
     "        preuves, ecartees = _preuves(c.get(\"preuves\"), lectures, hyps[hid].lectures)\n",
     "        preuves, ecartees = [Preuve(str(p.get(\"lecture\")), int(p.get(\"ligne\") or 0), \"\") "
     "for p in c.get(\"preuves\") or () if isinstance(p, dict)], []\n"),
    ("M7129", "« sans objet », or an announced read not served, said « vide » (ENQ4, §4, §4.3)", LOOP,
     "    return catalog.Reading(str(read_id)[:60], etat, why=why)\n",
     "    return catalog.Reading(str(read_id)[:60], catalog.VIDE)\n"),
    ("M7130", "a read of today in echec or en_attente filled by the memory's reference (ENQ4, §5.5 rule 1)",
     LOOP,
     "        self.out.lectures[lu.id] = lu             # today's reading, whatever the last enquiry read "
     "(§5.5, rule 1)\n",
     "        self.out.lectures[lu.id] = next((catalog.Reading(t.id, t.etat, rows=[dict(r) for r in t.lignes]) "
     "for t in (self.out.reference.lectures if self.out.reference and lu.etat in (catalog.ECHEC, "
     "catalog.EN_ATTENTE) else ()) if t.id == lu.id), lu)\n"),
    ("M7131", "« as usual » received without a human verdict, or on a grave technique (ENQ4, §5.5 rule 2)",
     REFERENCE,
     "    if technique in GRAVE_TTPS:\n        return TECHNIQUE_GRAVE\n    if ref is None:\n"
     "        return SANS_REFERENCE\n    if not ref.verdict_humain:\n        return SANS_VERDICT\n",
     "    if ref is None:\n        return SANS_REFERENCE\n    return \"\"\n"),
    ("M7132", "a read the model asked counted as a gap: a line that makes it ask a read that fails, or one "
     "the code cannot fill, holds the contention (ENQ4 review, §5.1, §7.2)", LOOP,
     "        return [r.id for r in self.lectures.values() if r.gap and r.id in self.d_office]\n",
     "        return [r.id for r in self.lectures.values() if r.gap]\n"),
]

TESTS = {mid: _T for mid in ("M7123", "M7124", "M7125", "M7126", "M7127", "M7128", "M7129", "M7130", "M7131",
                             "M7132")}
