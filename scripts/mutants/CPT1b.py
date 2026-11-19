"""CPT1b (#940): the summary card of the control plane (past 5 operations in one poll) names the
caller and the resource of each operation as its own card does — `Caller`, else the name, the
object id or the application id from `Claims`; `_ResourceId`, else `ResourceId` —, a true void said
« appelant inconnu »; « Sévérité moindre » only on a card really lowered; the long URIs of `upn` and
`name` read, and the short `name`; a client's `CallerName` names the caller; a name, then the
object id, then the application; the console's feed names a card of incomplete telemetry.
M6466–M6480, M6447 and M6448 (ceded from MUT14's range), measured by
tests/unit/test_control_plane_incomplete.py."""
RULES = "glorfindel/detection_rules.py"
AGENT = "glorfindel/agent.py"
JS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_control_plane_incomplete.py"

MUTANTS = [
    ("M6466", "the summary keeps each operation's Caller alone again (CPT1b)", RULES,
     "             **caller_columns(r),\n", '             "Caller": r.get("Caller") or "",\n'),
    ("M6467", "the summary card reads each operation's Caller alone, « ? » else (CPT1b)", AGENT,
     "par {_caller_said({}, o)} sur ", "par {o.get('Caller') or '?'} sur "),
    ("M6468", "the summary loses each operation's resource (CPT1b)", RULES,
     '             "_ResourceId": operation_resource(r),\n', '             "_ResourceId": "",\n'),
    ("M6469", "the summary card reads each operation's resource in ResourceId alone (CPT1b)", AGENT,
     "{operation_resource(o) or '?'} (", "{o.get('ResourceId') or '?'} ("),
    ("M6470", "« Sévérité moindre » written on a card that stays critical (CPT1b)", AGENT,
     '    return signal.get("severity") != "critical" and names_no_one(_control_plane_row(signal))\n',
     "    return names_no_one(_control_plane_row(signal))\n"),
    ("M6471", "the console's feed no longer names a card of incomplete telemetry (CPT1b)", JS,
     "\n  control_plane_incomplete: 'control plane, incomplete telemetry (detection only)' };", " };"),
    ("M6472", "the long URI of upn unread in Claims (CPT1b)", RULES,
     '_CLAIM_NAME = ("upn", "unique_name", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",\n',
     '_CLAIM_NAME = ("upn", "unique_name",\n'),
    ("M6473", "the long URI of name unread in Claims (CPT1b)", RULES,
     '               "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",\n', ""),
    ("M6474", "a true void of a summary said « ? », not « appelant inconnu » (CPT1b)", AGENT,
     '    return "appelant inconnu"\n', '    return "?"\n'),
    ("M6475", "the card no longer reads the caller in a projected Claims (CPT1b)", AGENT,
     "    claimed = claimed_caller(row)\n", '    claimed = {"name": "", "oid": "", "app": ""}\n'),
    ("M6476", "the summary drops the object id drawn from Claims (CPT1b)", RULES,
     '            "CallerObjectId": _text(row.get("CallerObjectId")) or claimed["oid"],\n',
     '            "CallerObjectId": _text(row.get("CallerObjectId")),\n'),
    ("M6477", "the summary drops the caller's name drawn from Claims (CPT1b)", RULES,
     '            "CallerName": _text(row.get("CallerName")) or claimed["name"],\n',
     '            "CallerName": _text(row.get("CallerName")),\n'),
    ("M6478", "an operation's resource read in _ResourceId alone (CPT1b)", RULES,
     '    return next((_text(row.get(c)) for c in RESOURCE_COLUMNS if _said(row.get(c))), "")\n',
     '    return _text(row.get("_ResourceId"))\n'),
    ("M6479", "a client's CallerName alone lowered to incomplete telemetry (CPT1b)", RULES,
     '                  "CallerName")\n', "                  )\n"),
    ("M6480", "the object id named before the caller's name (CPT1b)", AGENT,
     '''    name = str(row.get("CallerName") or "").strip() or claimed["name"]
    if name:
        return f"{name} (lu dans Claims, Caller vide)"
    oid = str(row.get("CallerObjectId") or "").strip()
    oid = oid or claimed["oid"]
    if oid:
        return f"l'identité d'objet {oid} (lue dans Claims, Caller vide)"
''', '''    oid = str(row.get("CallerObjectId") or "").strip()
    oid = oid or claimed["oid"]
    if oid:
        return f"l'identité d'objet {oid} (lue dans Claims, Caller vide)"
    name = str(row.get("CallerName") or "").strip() or claimed["name"]
    if name:
        return f"{name} (lu dans Claims, Caller vide)"
'''),
    ("M6447", "the summary drops the CallerName a client's rule projects (CPT1b)", RULES,
     '            "CallerName": _text(row.get("CallerName")) or claimed["name"],\n',
     '            "CallerName": claimed["name"],\n'),
    ("M6448", "the short name claim unread in Claims (CPT1b)", RULES,
     '               "name")\n', "               )\n"),
]
TESTS = {
    "M6466": f"{_T}::test_a_summary_operation_whose_caller_is_in_claims_alone_is_named",
    "M6467": f"{_T}::test_a_summary_operation_whose_caller_is_in_claims_alone_is_named",
    "M6468": f"{_T}::test_a_summary_card_names_the_caller_and_the_resource_of_each_operation",
    "M6469": f"{_T}::test_a_summary_card_names_the_caller_and_the_resource_of_each_operation",
    "M6470": f"{_T}::test_a_critical_signal_on_a_bare_row_never_says_lower_severity",
    "M6471": f"{_T}::test_the_console_feed_names_a_card_of_incomplete_telemetry",
    "M6472": f"{_T}::test_the_long_uris_of_upn_and_name_name_the_caller",
    "M6473": f"{_T}::test_the_long_uris_of_upn_and_name_name_the_caller",
    "M6474": f"{_T}::test_a_true_void_in_a_summary_stays_unknown",
    "M6475": f"{_T}::test_the_long_uris_of_upn_and_name_name_the_caller",
    "M6476": f"{_T}::test_a_summary_reads_what_a_clients_rule_projects",
    "M6477": f"{_T}::test_a_summary_reads_what_a_clients_rule_projects",
    "M6478": f"{_T}::test_a_summary_reads_what_a_clients_rule_projects",
    "M6479": f"{_T}::test_a_clients_rule_that_projects_the_callers_name_alone_is_not_lowered",
    "M6480": f"{_T}::test_the_caller_is_named_by_its_name_then_its_object_id_then_its_application",
    "M6447": f"{_T}::test_a_summary_reads_what_a_clients_rule_projects",
    "M6448": f"{_T}::test_the_short_name_claim_names_the_caller",
}
