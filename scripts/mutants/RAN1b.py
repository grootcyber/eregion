"""RAN1b (#820, after RAN1, #665): a card's target says itself in English, like the console that shows it
as it is; the replay on the site marks as measured the ransomware times of the bench run of 12/11, those
of docs/proofs.json, never those of 09/06. M5311–M5320, measured by tests/unit/test_card_target.py and
tests/unit/test_adoption.py."""
TARGET = "glorfindel/card_target.py"
POLLER = "glorfindel/detection_rules.py"
REPLAY = "docs/replay/index.html"
_CARD = "tests/unit/test_card_target.py"
_ADOPTION = "tests/unit/test_adoption.py"

MUTANTS = [
    ("M5311", "a role's scope said in French under an English card, as the bench showed on 09/11 (RAN1b)", TARGET,
     "        via = f\"role assignment, scope {_short(scope) or '/'}\"\n",
     "        via = f\"attribution de rôle, portée {_short(scope) or '/'}\"\n"),
    ("M5312", "the control plane named in French (RAN1b)", TARGET,
     '    t = {"kind": "control_plane", "id": CONTROL_PLANE_ID, "name": "control plane"}\n',
     '    t = {"kind": "control_plane", "id": CONTROL_PLANE_ID, "name": "plan de contrôle"}\n'),
    ("M5313", "a call from behind an appliance said in French (RAN1b)", TARGET,
     '              f"call from the address of {caller_appliance}, which forwards packets: the source "\n'
     '              "VM is behind it" if caller_appliance else "")\n',
     '              f"appel depuis l\'adresse de {caller_appliance}, qui fait suivre les paquets : la VM "\n'
     '              "source est derrière elle" if caller_appliance else "")\n'),
    ("M5314", "the RulePoller's limit, when the target cannot be read, said in French (RAN1b)", POLLER,
     '                    limit=f"What the row is about could not be read ({type(exc).__name__}).")\n',
     '                    limit=f"Ce que la ligne vise n\'a pas pu être lu ({type(exc).__name__}).")\n'),
    ("M5315", "a summary card of identities named in French (RAN1b)", TARGET,
     '"name": "several identities",\n',
     '"name": "plusieurs identités",\n'),
    ("M5316", "an NSG the listing does not hold said in French (RAN1b)", TARGET,
     '        t["limit"] = (f"This NSG is not in the list read on Azure ({_GONE_OR_HIDDEN}): "\n'
     '                      "the VMs it covers are not said.")\n',
     '        t["limit"] = (f"Ce NSG n\'est pas dans la liste lue sur Azure ({_GONE_OR_HIDDEN}) : "\n'
     '                      "les VM qu\'il couvre ne sont pas dites.")\n'),
    ("M5317", "the replay's time to restored service back to the run of 09/06 (RAN1b)", REPLAY,
     "['27 min 55 s to restored service, the human’s wait excluded',1];",
     "['21 min 29 s to restored service, the human’s wait excluded',1];"),
    ("M5318", "the replay's time to contain back to « about 1 min », measured before Imladris (RAN1b)", REPLAY,
     "<div class=\"stat\"><b>7 min 43 s</b><span>to contain alone, verified on Azure</span>",
     "<div class=\"stat\"><b>~1 min</b><span>to contain, alone</span>"),
    ("M5319", "the replay's detection back to the 55–71 s of June (RAN1b)", REPLAY,
     "if(t<24)return ['detected 141.6 s after T0',1];",
     "if(t<24)return ['detected 55–71 s after T0',1];"),
    ("M5320", "the replay's detection no longer marked measured, its figure right (RAN1b, review)", REPLAY,
     "if(t<24)return ['detected 141.6 s after T0',1];",
     "if(t<24)return ['detected 141.6 s after T0',0];"),
]
TESTS = {
    **{f"M{n}": _CARD for n in range(5311, 5317)},
    **{f"M{n}": _ADOPTION for n in range(5317, 5321)},
}
