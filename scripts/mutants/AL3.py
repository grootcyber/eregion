"""AL3 (#867): two operations of the control plane detected and escalated — Run Command on a VM by
a caller other than Glorfindel, a Bastion shareable link —, every operation, refused ones too, the
card saying it failed; Glorfindel's session drain escalated by no Run Command rule, its command
outside a drain SID1's card once, another identity the external rule's; a row naming a VM the
discovery does not know a card on its group, never dropped, never acted on. M5501–M5519, measured
by tests/unit/test_run_command_callers.py."""
RULES = "glorfindel/rules/azure/detection_rules.yaml"
ORC = "glorfindel/providers/azure/own_run_command.py"
AGENT = "glorfindel/agent.py"
POLLER = "glorfindel/detection_rules.py"
TARGET = "glorfindel/card_target.py"
_TESTS = "tests/unit/test_run_command_callers.py"

_OTHERS = '      | extend WatchedCaller = "others"\n'
_BASTION_FORM = ('      // that only failed too (AL3): the card says it.\n'
                 '      | summarize arg_max(TimeGenerated, *), Succeeded = countif(')
_ROUTE = ("            if named and tgt is None and (not control or "
          "_names_known_vm(row, discovered, rule.auto_apply)):\n")
_KNOWN = ('    return not auto or _vm_id_of(str(row.get("_ResourceId") or row.get("ResourceId"))) '
          'in discovered\n')

MUTANTS = [
    # The two rules: they match, every operation, the card says it failed.
    ("M5501", "the external Run Command rule matches nothing any more (AL3)", RULES,
     _OTHERS, _OTHERS + '      | where OperationNameValue == "nothing"\n'),
    ("M5502", "the external Run Command rule watches Glorfindel only: an intruder unsaid (AL3)", RULES,
     _OTHERS, '      | extend WatchedCaller = "glorfindel"\n'),
    ("M5503", "the external Run Command rule sets refused attempts aside again (AL3)", RULES,
     _OTHERS, '      | where Succeeded > 0 or ActivityStatusValue !in~ ("Failure", "Failed")\n' + _OTHERS),
    ("M5504", "the Bastion rule reads an operation Azure does not write: it matches nothing (AL3)", RULES,
     '      | where OperationNameValue =~ "MICROSOFT.NETWORK/BASTIONHOSTS/CREATESHAREABLELINKS/ACTION"\n',
     '      | where OperationNameValue =~ "MICROSOFT.NETWORK/BASTIONHOSTS/CREATESHAREABLELINK/ACTION"\n'),
    ("M5505", "the Bastion rule drops the failure lines: a refused attempt read at its Start (AL3)", RULES,
     _BASTION_FORM,
     '      | where ActivityStatusValue !in~ ("Failure", "Failed")\n'
     '      | summarize arg_max(TimeGenerated, *), Succeeded = countif('),
    ("M5506", "the card of a refused attempt does not say it failed (AL3)", AGENT,
     '    elif status.lower() in ("failure", "failed") and _read_count(row, "Succeeded") == 0:\n',
     '    elif False:\n'),
    ("M5507", "a card says « failed » on a count it did not read (AL3)", AGENT,
     '    elif status.lower() in ("failure", "failed") and _read_count(row, "Succeeded") == 0:\n',
     '    elif status.lower() in ("failure", "failed") and _succeeded_lines(row) == 0:\n'),
    # Glorfindel's drain: its own on every Run Command rule; its command outside a drain, SID1's.
    ("M5508", "Glorfindel's command outside a drain a card of the external rule too: two cards (AL3)", ORC,
     "    if mine and watches_others_only(row):\n        return None\n",
     ""),
    ("M5509", "under the external rule, an intruder taken for Glorfindel: dropped (AL3)", ORC,
     "    if mine and watches_others_only(row):\n",
     "    if watches_others_only(row):\n"),
    ("M5510", "Glorfindel's drain escalated by a client's Run Command rule (AL3)", ORC,
     '    return attach(row, rid.rstrip("/").lower(), book() if callable(book) else book, info)\n',
     '    return attach(row, rid.rstrip("/").lower(), book() if callable(book) else book, info) '
     'or ("" if only else "outside_drain")\n'),
    ("M5511", "Glorfindel's identity unknown, every Run Command of the external rule dropped (AL3)", ORC,
     '        return "identity_unknown" if only else ""\n',
     '        return "identity_unknown" if only else None\n'),
    ("M5512", "a Run Command that names no caller dropped by the external rule (AL3)", ORC,
     '    if only and not has_caller:\n        return "caller_unreadable"\n',
     '    if only and not has_caller:\n        return "caller_unreadable"\n'
     '    if not has_caller:\n        return None\n'),
    # A VM outside the discovery: said, never dropped, never acted on.
    ("M5513", "a row on a VM the discovery does not know dropped unsaid again (AL3)", POLLER,
     _ROUTE,
     "            if named and tgt is None and (not control or _names_vm_resource(row)):\n"),
    ("M5514", "the discovery unreadable, every row on a VM dropped (AL3)", POLLER,
     _KNOWN,
     '    return not auto or not discovered or _vm_id_of(str(row.get("_ResourceId") or '
     'row.get("ResourceId"))) in discovered\n'),
    ("M5515", "a row on a VM excluded from the rule kept: the exclusion ignored (AL3)", POLLER,
     _KNOWN, "    return not auto\n"),
    ("M5516", "a rule bound to one asset keeps a row on another VM (AL3)", POLLER,
     _KNOWN, '    return _vm_id_of(str(row.get("_ResourceId") or row.get("ResourceId"))) in discovered\n'),
    ("M5517", "the discovery read on the rule's backend only: an excluded VM unknown (AL3)", POLLER,
     "            assets = self._registry.all() if self._registry is not None else []\n",
     '            assets = self._registry.for_backend("") if self._registry is not None else []\n'),
    ("M5518", "the card on a VM the discovery does not know says it may be excluded (AL3)", TARGET,
     '                             limit=f"The VM named is a VM {_UNDISCOVERED}.")\n',
     '                             limit=f"The VM named is a VM {_UNWATCHED}.")\n'),
    ("M5519", "a VM the discovery does not know filed on itself, as if it were known (AL3)", TARGET,
     '        return _group_target(rid, row, via=_short(rid),\n'
     '                             limit=f"The VM named is a VM {_UNDISCOVERED}.")\n',
     '        return vm_target(rid, limit=f"The VM named is a VM {_UNDISCOVERED}.")\n'),
]
TESTS = {f"M{n}": _TESTS for n in range(5501, 5520)}
