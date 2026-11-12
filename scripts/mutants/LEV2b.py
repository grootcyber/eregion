"""LEV2b (#763): the tool of the measure of the lift, corrected on what the bench of 12/11 read — a
failure said as Azure wrote it, and why a `Conflict` under another code counts; each event judged once;
the name of an operation is no identifier; another resource named by its type and its place, never its
name. M4960–M4969, measured by tests/unit/test_bench_lev2.py."""
LEV2 = "scripts/bench_lev2.py"
SHARED = "scripts/bench_shared.py"
_T = "tests/unit/test_bench_lev2.py"

MUTANTS = [
    ("M4960", "the operation of gesture 6 masked as an id: `microsoft.resources<ressource>` back in the "
     "report (LEV2b, the defect back)", SHARED,
     '    if namespace == RESOURCES_NS and path and not re.search(r"[\\w/-]", after):\n',
     "    if False:\n"),
    ("M4961", "whatever follows a Microsoft.Resources path kept: a subscription id that starts with letters "
     "lets its group's name through (LEV2b)", SHARED,
     '    if namespace == RESOURCES_NS and path and not re.search(r"[\\w/-]", after):\n',
     "    if namespace == RESOURCES_NS and path:\n"),
    ("M4962", "the code of a failure folded: « Conflict conflict », read as a comparison by case (LEV2b, the "
     "defect back)", LEV2,
     '    return str(err.get("code") or "").strip() if isinstance(err, dict) else ""\n',
     '    return str(err.get("code") or "").strip().lower() if isinstance(err, dict) else ""\n'),
    ("M4963", "a `Conflict` under another code said a failure without why: the guide reads it as REC1b's "
     "refusal, the report as a failure (LEV2b, the defect back)", LEV2,
     '        elif _fold(status) == "conflict":\n',
     "        elif False:\n"),
    ("M4964", "each copy of an event judged: a `Started` read one round before its refusal left over, a "
     "refusal of the platform said a failure (LEV2b)", LEV2,
     "    events = list(unique(events).values())\n",
     "    events = list(events)\n"),
    ("M4965", "a refusal said « écarté » by its own event while Glorfindel keeps its operation: a second "
     "`Started` under its id, a command cut, hidden (LEV2b)", LEV2,
     '        if _fold(e.get("operationId")) in refused:\n',
     '        if _refused(e) or _fold(e.get("operationId")) in refused:\n'),
    ("M4966", "another resource said « une autre ressource », unnamed: the disk of gesture 15 under "
     "`disk-tag` unread (LEV2b, the defect back)", LEV2,
     "        return elsewhere(rid, t)\n",
     '        return "une autre ressource"\n'),
    ("M4967", "a word of an id out of shape said where a type is read: a name in the report (LEV2b)", LEV2,
     '    what = "/".join(w if _TYPE_WORD.fullmatch(w) else "?" for w in words) or "?"\n',
     '    what = "/".join(words) or "?"\n'),
    ("M4968", "a resource of another group said of the VM's group (LEV2b)", LEV2,
     '             "du groupe de la VM, hors de la VM" if parts[:5] == mine[:5] else "d\'un autre groupe")\n',
     '             "du groupe de la VM, hors de la VM")\n'),
    ("M4969", "a resource of another subscription said of the VM's (LEV2b)", LEV2,
     "    other_sub = parts[2] != mine[2]\n",
     "    other_sub = False\n"),
]
TESTS = {
    "M4960": f"{_T}::test_the_name_of_an_operation_is_no_identifier",
    "M4961": f"{_T}::test_the_name_of_an_operation_is_no_identifier",
    "M4962": f"{_T}::test_a_conflict_under_its_own_code_is_said_as_azure_wrote_it_and_why_it_counts "
             f"{_T}::test_a_failure_says_its_status_its_code_and_whether_it_counts",
    "M4963": f"{_T}::test_a_conflict_under_its_own_code_is_said_as_azure_wrote_it_and_why_it_counts",
    "M4964": f"{_T}::test_an_event_read_in_several_rounds_is_judged_once",
    "M4965": f"{_T}::test_a_refusal_whose_operation_still_counts_is_never_said_left_out",
    "M4966": f"{_T}::test_another_resource_is_named_by_its_type_and_its_place_never_its_name",
    "M4967": f"{_T}::test_another_resource_is_named_by_its_type_and_its_place_never_its_name",
    "M4968": f"{_T}::test_another_resource_is_named_by_its_type_and_its_place_never_its_name",
    "M4969": f"{_T}::test_another_resource_is_named_by_its_type_and_its_place_never_its_name",
}
