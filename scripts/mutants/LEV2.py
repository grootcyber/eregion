"""LEV2 (#690): the door's facts — who acted on a VM by the control plane, and whether they keep their
rights —, read only, for information; the disks noted at the isolation. A read cut or failed is
unreadable, never empty; whatever its status a gesture counts, a refusal of the platform aside; the
children of the VM are read through its group; on a shared NSG only a rule that covers the VM counts;
a group, an eligibility, a deleted principal are unreadable; a VM isolated again keeps the disks of its
first isolation. M4720–M4729, measured by tests/unit/test_door_facts.py."""
DOOR = "glorfindel/providers/azure/door.py"
RIGHTS = "glorfindel/providers/azure/door_rights.py"
ISOLATION = "glorfindel/providers/azure/isolation.py"
_T = "tests/unit/test_door_facts.py"

MUTANTS = [
    ("M4720", "a read past its bound taken as all read: a busy group's 21st page, a third party's gesture "
     "in it, never seen — the actors « none » (LEV2)", DOOR,
     '        raise CutRead(f"plus de {bound} pages, la suite n\'est pas lue")\n',
     "        return items, bound\n"),
    ("M4721", "a read that failed leaves the verdict to what was read: a log refused (403) reads « nobody "
     "acted on the VM » (LEV2)", DOOR,
     '        out["verdict"] = "unreadable" if out["unreadable"] else "seen" if out["actors"] else "none"\n',
     '        out["verdict"] = "seen" if out["actors"] else "none"\n'),
    ("M4722", "the group never read: an extension, a managed Run Command, a rule of the NSG — children under "
     "their own id — never seen (LEV2, H9)", DOOR,
     '        reads = [("uri", what, rid) for what, rid in exact] + [("group", "group", g) for g in groups]\n',
     '        reads = [("uri", what, rid) for what, rid in exact]\n'),
    ("M4723", "a refusal of the platform counted as a gesture: a Run Command on a deallocated VM, which "
     "reached nothing, names an actor (LEV2)", DOOR,
     '        kept = [(e, g) for e, g in gestures if not (_refused(e) or _fold(e.get("operationId")) in refused)]\n',
     "        kept = gestures\n"),
    ("M4724", "only a succeeded gesture counted: a third party's Run Command that failed in the guest, its "
     "settings left in the VM model, never says who tried (LEV2)", DOOR,
     "        if kind is None or kind not in DOOR_OPERATIONS[op][0]:\n            return None\n",
     "        if kind is None or kind not in DOOR_OPERATIONS[op][0]:\n            return None\n"
     '        if _fold((e.get("status") or {}).get("value")) != "succeeded":\n            return None\n'),
    ("M4725", "every rule of a shared NSG counted: a rule aimed at another VM of the subnet read as a "
     "gesture on this one (LEV2)", DOOR,
     "                if not g[\"covers\"]:\n                    return None               # a rule aimed at another VM of a shared NSG\n",
     "                if False:\n                    return None\n"),
    ("M4726", "a right through a group read as absent: members H0 never reads, the door left open behind "
     "« absent » (LEV2, Q11)", RIGHTS,
     '            out["unreadable"].append(f"« {role[\'name\']} » sur {where} à un groupe : H0 n\'en lit pas les membres")\n',
     "            pass\n"),
    ("M4727", "the PIM eligibilities never judged: a third party eligible to Owner read as absent (LEV2, "
     "H2)", RIGHTS,
     "    every = list(reading.assignments.values()) + list(reading.eligibilities.values())\n",
     "    every = list(reading.assignments.values())\n"),
    ("M4728", "a deleted principal read as any other: its orphan assignment held, or « absent » while it is "
     "restorable from the recycle bin with its rights (LEV2, H11)", RIGHTS,
     '        if mine and gone and a["kind"] == "assignments":\n',
     "        if False:\n"),
    ("M4729", "a VM isolated again notes its disks anew: after a restore in place, the original disks — the "
     "evidence — replaced by the restored ones (LEV2, §8)", ISOLATION,
     '    if isinstance(kept, dict) and kept.get("ids"):\n        return kept\n',
     '    if False:\n        return kept\n'),
]
TESTS = {
    "M4720": f"{_T}::test_a_busy_group_past_twenty_pages_is_unreadable_and_twenty_pages_are_read "
             f"{_T}::test_every_scope_read_refused_or_cut_makes_the_rights_unreadable",
    "M4721": f"{_T}::test_every_read_cut_or_failed_makes_the_actors_unreadable_never_none",
    "M4722": f"{_T}::test_a_third_partys_extension_is_a_gesture_whatever_its_type_and_read_from_the_group",
    "M4723": f"{_T}::test_a_failed_gesture_counts_a_refusal_of_the_platform_does_not",
    "M4724": f"{_T}::test_a_failed_gesture_counts_a_refusal_of_the_platform_does_not",
    "M4725": f"{_T}::test_a_rule_of_a_shared_nsg_counts_only_when_it_covers_the_vm",
    "M4726": f"{_T}::test_what_h0_cant_read_whole_is_unreadable_never_absent",
    "M4727": f"{_T}::test_what_h0_cant_read_whole_is_unreadable_never_absent",
    "M4728": f"{_T}::test_what_h0_cant_read_whole_is_unreadable_never_absent "
             f"{_T}::test_a_deleted_principal_with_nothing_left_is_absent",
    "M4729": f"{_T}::test_the_disks_are_noted_at_the_isolation_and_kept_by_an_isolation_again",
}
