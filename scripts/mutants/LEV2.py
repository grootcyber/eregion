"""LEV2 (#690): the door's facts — who acted on a VM by the control plane, and whether they keep their
rights —, read only, for information; the disks noted at the isolation. A read cut or failed is
unreadable, never empty; whatever its status a gesture counts, a refusal of the platform aside; the
children of the VM are read through its group; on a shared NSG only a rule that covers the VM counts;
a group, an eligibility, a deleted principal are unreadable; a VM isolated again keeps the disks of its
first isolation. Review round 1: an answer of ARM not of its documented shape is unreadable; a user is
known by its oid and UPN, never by its tool's appid; Q16 (Jonathan, 10/11): a rule deleted and the
subnet written are gestures, a deleted rule of a shared NSG judged on the rules the isolation noted; a
principal of a type absent or unknown read as a group. M4720–M4729 and M4745–M4750, measured by
tests/unit/test_door_facts.py."""
DOOR = "glorfindel/providers/azure/door.py"
RIGHTS = "glorfindel/providers/azure/door_rights.py"
NOTED = "glorfindel/providers/azure/noted.py"
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
     '            out["unreadable"].append(f"« {role[\'name\']} » sur {where} à un groupe : Imladris n\'en lit pas les membres")\n',
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
     "evidence — replaced by the restored ones (LEV2, §8)", NOTED,
     '    if isinstance(kept, dict) and kept.get("ids"):\n        return kept\n',
     '    if False:\n        return kept\n'),
    ("M4745", "a page of ARM taken whatever its shape: `200 {}` without its list read « nobody acted on the "
     "VM », a third party's extension in the log (LEV2, review round 1)", DOOR,
     "                raise RuntimeError(\"réponse d'ARM mal formée : pas la liste `value` d'une page\")\n",
     "                value = []\n"),
    ("M4746", "a role read without its permissions: a definition `{}` gives nothing, the Owner read « absent » "
     "(LEV2, review round 1)", RIGHTS,
     '                    raise RuntimeError("réponse d\'ARM mal formée : une définition sans ses permissions")\n',
     "                    perms = []\n"),
    ("M4747", "a user known by its token's appid, the client tool's: Jonathan and an attacker under `az` one "
     "actor, the role `restore` of one hiding the other (LEV2, review round 1)", DOOR,
     "    ids = token_identities(claims) if is_app_token(claims) else {\n",
     '    ids = token_identities({**claims, "upn": "", "scp": "", "idtyp": "app"}) if True else {\n'),
    ("M4748", "a rule deleted from a shared NSG without the isolation's list read as aimed elsewhere: a deny "
     "taken off in front of the VM, never seen (LEV2, Q16)", DOOR,
     '                g["covers"] = True if was is None else rule_covers(was, t["ips"], t["asgs"])\n',
     '                g["covers"] = False if was is None else rule_covers(was, t["ips"], t["asgs"])\n'),
    ("M4749", "the VM's subnet written out of the table: its NSG or its routes detached, never a gesture "
     "(LEV2, Q16)", DOOR,
     '    ("Microsoft.Network/virtualNetworks/subnets/write", ("subnet",),\n'
     '     "le sous-réseau de la VM : un NSG ou une table de routes détachés ou changés (Q16)"),\n',
     ""),
    ("M4750", "a principal of a type absent or unknown ignored: an Owner without a type read « absent » "
     "(LEV2, review round 1)", RIGHTS,
     '        mine, group = a["principal"] in ids, a["type"] not in ("user", "serviceprincipal")\n',
     '        mine, group = a["principal"] in ids, a["type"] == "group"\n'),
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
    "M4745": f"{_T}::test_a_page_of_the_log_of_a_shape_not_documented_is_unreadable_never_none",
    "M4746": f"{_T}::test_a_role_without_its_permissions_is_unreadable_never_absent",
    "M4747": f"{_T}::test_two_users_under_one_client_tool_are_two_actors",
    "M4748": f"{_T}::test_a_rule_deleted_from_a_shared_nsg_counts_unless_the_isolation_saw_it_aim_elsewhere "
             f"{_T}::test_the_quarantine_path_notes_no_rules_and_a_deleted_rule_then_counts",
    "M4749": f"{_T}::test_each_gesture_of_the_table_is_read_on_its_resource",
    "M4750": f"{_T}::test_a_principal_of_a_type_absent_or_unknown_is_read_as_a_group",
}
