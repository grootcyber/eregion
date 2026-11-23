"""ENQ3 (#1077): the knowledge base of the enquiry (glorfindel/enquiry/knowledge.py) — the seed
`fiches/T1486.yaml`, its validator, the weights and the rules of a lesson. M7108–M7113: a lesson that
relaxes applied without an accord; the model alone changing a state; a hypothesis proposed shown to the
model; `effet` learned; an unknown key accepted; an unreadable seed read empty. Measured by
tests/unit/test_enquiry_knowledge.py."""
KNOWLEDGE = "glorfindel/enquiry/knowledge.py"
_T = "tests/unit/test_enquiry_knowledge.py"

MUTANTS = [
    ("M7108", "a lesson that relaxes applied without a human's accord (ENQ3, §3.4)", KNOWLEDGE,
     "        return bool(lecon.accord)\n",
     "        return True\n"),
    ("M7109", "the model alone changes a state: its lessons reach the threshold of contestee (ENQ3, §3.3)",
     KNOWLEDGE,
     "    fortes = [le for le in faites if le.genre in SOURCES_D_ETAT]\n",
     "    fortes = faites\n"),
    ("M7110", "a hypothesis proposed shown to the model: it would learn itself (ENQ3, §3.3 rule 1)", KNOWLEDGE,
     "    return [v for v in evolutions(fiche, lecons) if v.etat not in CACHES_AU_MODELE]\n",
     "    return [v for v in evolutions(fiche, lecons) if v.etat != RETIREE]\n"),
    ("M7111", "effet learned from a lesson that asks it changed, never from the seed (ENQ3, §3.3 rule 3)",
     KNOWLEDGE,
     "    effet = hyp.effet                                        # the seed's alone: never learned (§3.3, rule 3)\n",
     "    effet = next((le.effet for le in reversed(mine) if le.verdict == REQUALIFIE), hyp.effet)\n"),
    ("M7112", "an unknown key of a sheet accepted (ENQ3, §3.2)", KNOWLEDGE,
     "        raise FicheRefusee(f\"{ou} : clé inconnue {inconnues}\")\n",
     "        pass\n"),
    ("M7113", "an unreadable seed read as an empty base (ENQ3, §3.2)", KNOWLEDGE,
     "        raise GraineIllisible(f\"{dossier} : la graine est illisible ({exc})\") from exc\n",
     "        return Base(MappingProxyType({}), MappingProxyType({}))\n"),
]

TESTS = {mid: _T for mid in ("M7108", "M7109", "M7110", "M7111", "M7112", "M7113")}
