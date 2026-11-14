"""IR1f (#828): the plan of an identity card never proposes to cut the defense off, says who is
protected, and checks the revocation of sessions against the hour of the event. Measured on the bench
of 14/11 on four real consent cards (the operator giving the watch its reads of Graph): E-1, the plan
proposed first to disable the watch, the card not marked Glorfindel's (its client is in `ClientId`);
E-2, the operator, its author, not said protected, a step on its sessions; E-3, `TimeGenerated` a
datetime, its `str()` with a space, the plan's hour empty, the check of a revocation never run.
M5341: the client of a consent no longer compared with Glorfindel's identities; M5342: a hour with a
space unread again; M5343: an offset kept, not written in UTC; M5344: an unreadable never_target list
taken for a list that names every id (its steps dropped, its reason unsaid); M5345: a listed author's
steps kept; M5346: a sign-in's subject taken for an author; M5347: a step on an identity of the
defense left a default one; M5348: never_target applied to the executor's items only again; M5349: an
hour not read unsaid; M5350: Discord silent of who is protected.
The review (r1): « no step aims at the author » dropped every step whose target was the author, not only
what cuts it off — a listed service principal adding itself a secret lost its removal, Verify
« unreadable » for « not held ». M5351: that defect back; M5352: the removal taken for a cut; M5353: a
predicate without `listed` taken for the list; M5354, M5355: `defense` said wrong for a listed identity;
M5356, M5357: the example of the watch's reads of Graph given to all, or to none; M5358–M5360: Discord
and the console titling any protected identity the defense's, or a protected author « À savoir »."""
_ENTRA = "glorfindel/providers/azure/entra.py"
_ITEMS = "glorfindel/providers/azure/entra_items.py"
_PLAN = "glorfindel/providers/azure/entra_plan.py"
_BOT = "glorfindel/bot.py"
_T = "tests/unit/test_identity_plan.py::"
_C = "tests/unit/test_identity_cards.py::"
_D = "tests/unit/test_entra_detection.py::"
_MARKED = f"{_T}test_e1_a_consent_whose_client_is_the_watch_is_marked_glorfindels_and_said"
_WATCH = f"{_T}test_e1_the_watchs_consent_plan_never_disables_it_it_says_what_to_check"
_LISTED = f"{_T}test_e1_a_client_never_target_lists_is_never_cut_by_default"
_UNREADABLE = f"{_T}test_e1_never_target_unreadable_the_step_stays_its_reason_said"
_AUTHOR = f"{_T}test_e2_an_author_never_target_lists_is_said_protected_and_no_step_aims_at_it"
_ROLE_AUTHOR = f"{_T}test_e2_a_roles_author_listed_its_sessions_dropped_the_members_kept"
_HUMANS = f"{_T}test_e2_a_humans_step_on_a_protected_identity_says_never_targets_reason"
_SIGNIN = f"{_T}test_e2_a_signins_principal_is_its_subject_not_an_author"
_HOUR = f"{_T}test_e3_time_generated_as_azure_monitor_query_gives_it_reaches_the_plan"
_SESSIONS = f"{_T}test_e3_the_sessions_check_runs_on_a_real_cards_hour"
_NO_HOUR = f"{_T}test_e3_an_hour_absent_or_illegible_is_said_never_taken_for_checked"
_ALONE = f"{_T}test_ir1f_nothing_glorfindel_does_alone_changes"
_POLLED = f"{_D}test_a_consent_whose_client_is_its_own_identity_is_kept_critical_and_marked"
_DISCORD = f"{_C}test_discord_says_the_card_is_the_defenses_and_never_proposes_to_disable_it"
_DISCORD_HOUR = f"{_C}test_discord_says_an_hour_not_read"

_JS = "eregion_console/static/glorfindel.js"
_AUTHOR_CUT = "        items = [i for i in items if not (i[\"verb\"] in _CUTS and i[\"target\"].get(\"id\") in held)]\n"
_RETURN = "    return items, \"glorfindel\" if glorfindel else \"listed\" if cut else False\n"
_ASKED = "        items = [_ask_the_operator(who, _GLORFINDEL if glorfindel else _LISTED, glorfindel=glorfindel)] + \\\n"
# The review (r1): M5351–M5360.
_SELF = f"{_T}test_e2_r1_a_listed_principal_adding_itself_a_credential_keeps_its_removal"
_NO_LIST = f"{_T}test_e2_r1_a_predicate_without_listed_lists_no_one"
_EXAMPLE = f"{_T}test_e1_r1_the_watchs_reads_of_graph_the_example_of_glorfindels_consent_alone"
_DISCORD_TITLE = f"{_C}test_discord_r1_another_protected_identity_is_never_titled_the_defenses"
_PAGE = "tests/unit/test_console_identity_plan.py::test_the_page_says_who_is_protected_and_an_hour_not_read_escaped"

MUTANTS = [
    ("M5341", "the client of a consent no longer compared with Glorfindel's identities: the watch's own "
              "consent unmarked, high, its plan proposing to disable it (IR1f, E-1)",
     _ENTRA, "    return _ids(row, \"TargetId\", \"TargetAppId\") | ({client} - {\"\"})\n",
     "    return _ids(row, \"TargetId\", \"TargetAppId\")\n"),
    ("M5342", "an hour written with a space (`str()` of the datetime azure-monitor-query gives) unread: "
              "the plan's hour empty, the revocation of sessions never checked (IR1f, E-3)",
     _ITEMS, "    spaced = v.replace(\" \", \"T\", 1)\n", "    spaced = v\n"),
    ("M5343", "an hour with an offset written with its local time and a `Z`, never brought to UTC (IR1f, E-3)",
     _ITEMS, "    dt = (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)\n",
     "    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)\n"),
    ("M5344", "an unreadable never_target list read as naming every id: the client's disabling made "
              "conditional, every author's steps dropped — a list that names no one (IR1f)",
     _PLAN, "        return not never.refusal() and bool(guid(object_id)) and never.covers(object_id)\n",
     "        return bool(guid(object_id)) and never.covers(object_id)\n"),
    ("M5345", "an author never_target lists still aimed at: the operator's sessions a step (IR1f, E-2)",
     _PLAN, _AUTHOR_CUT, "        items = list(items)\n"),
    ("M5346", "a sign-in's principal taken for an author: its own steps dropped (IR1f, E-2)",
     _PLAN, "_AUTHORED = (\"credential\", \"consent\", \"role\")\n",
     "_AUTHORED = (\"credential\", \"consent\", \"role\", \"signin\")\n"),
    ("M5347", "a step on an identity of the defense left a default one, counted by Verify (IR1f, E-1)",
     _PLAN, "    i[\"optional\"] = True\n", "    i[\"optional\"] = i[\"optional\"]\n"),
    ("M5348", "never_target applied to the executor's items only: a human's verb on a listed identity "
              "silent of its reason (IR1f, E-2)",
     _PLAN, "        held = protected(i[\"target\"].get(\"id\", \"\")) if protected and i[\"target\"].get(\"id\") else \"\"\n"
            "        if held:  ",
     "        held = protected(i[\"target\"].get(\"id\", \"\")) if protected and i[\"target\"].get(\"id\") else \"\"\n"
     "        if held and i[\"by\"] == \"executor\":  "),
    ("M5349", "an hour of the event not read, unsaid by the plan (IR1f, E-3)",
     _PLAN, "        \"event_at_why\": \"\" if event_at or not sessions else (\n",
     "        \"event_at_why\": \"\" if True or event_at or not sessions else (\n"),
    ("M5350", "Discord silent of who is protected, and of an hour not read (IR1f)",
     _BOT, "    return head + [(names[n], \"\\n\".join(f)[:_FIELD_MAX], False) for n, f in enumerate(fields) if f]\n",
     "    return [(names[n], \"\\n\".join(f)[:_FIELD_MAX], False) for n, f in enumerate(fields) if f]\n"),
    # The review (r1).
    ("M5351", "every step aimed at a listed author dropped, not only what cuts it off: a listed principal's "
              "own credential, added to itself, never removed, Verify « unreadable » (IR1f r1)",
     _PLAN, _AUTHOR_CUT, "        items = [i for i in items if i[\"target\"].get(\"id\") not in held]\n"),
    ("M5352", "the removal of a credential taken for a cut of a listed author (IR1f r1)",
     _PLAN, _AUTHOR_CUT, _AUTHOR_CUT.replace("in _CUTS and", "in _CUTS + (\"entra_remove_credential\",) and")),
    ("M5353", "a predicate without `listed` taken for the list itself: its authors dropped, its steps "
              "conditional (IR1f r1)",
     _PLAN, "    listed = getattr(protected, \"listed\", None) or (lambda oid: False)\n",
     "    listed = getattr(protected, \"listed\", None) or (lambda oid: bool(protected(oid)))\n"),
    ("M5354", "an identity never_target lists titled the defense's, as Glorfindel's (IR1f r1)",
     _PLAN, _RETURN, "    return items, \"glorfindel\" if glorfindel or cut else False\n"),
    ("M5355", "an identity never_target lists cut off by no step, its plan not said protected (IR1f r1)",
     _PLAN, _RETURN, "    return items, \"glorfindel\" if glorfindel else False\n"),
    ("M5356", "the watch's reads of Graph given as the example of any check, a sign-in or a listed client "
              "(IR1f r1)",
     _PLAN, _ASKED, _ASKED.replace("glorfindel=glorfindel)", "glorfindel=True)")),
    ("M5357", "the watch's reads of Graph no longer the example of a consent given to Glorfindel (IR1f r1)",
     _PLAN, _ASKED, _ASKED.replace("glorfindel=glorfindel)", "glorfindel=False)")),
    ("M5358", "Discord titles any protected identity « Identité de la défense » (IR1f r1)",
     _BOT, "    if plan.get(\"defense\") == \"glorfindel\":\n", "    if plan.get(\"defense\"):\n"),
    ("M5359", "Discord titles a protected author « À savoir » (IR1f r1)",
     _BOT, "    return \"Identité protégée\" if plan.get(\"defense\") or plan.get(\"protected\") else \"À savoir\"\n",
     "    return \"Identité protégée\" if plan.get(\"defense\") else \"À savoir\"\n"),
    ("M5360", "the console titles any protected identity « An identity of the defense » (IR1f r1)",
     _JS, "  const title = plan.defense === 'glorfindel' ? 'An identity of the defense'\n",
     "  const title = plan.defense ? 'An identity of the defense'\n"),
]
TESTS = {
    "M5341": f"{_MARKED} {_WATCH} {_POLLED} {_ALONE}",
    "M5342": f"{_HOUR} {_SESSIONS} {_ALONE} {_POLLED}",
    "M5343": f"{_HOUR}",
    "M5344": f"{_UNREADABLE}",
    "M5345": f"{_AUTHOR} {_ROLE_AUTHOR}",
    "M5346": f"{_SIGNIN}",
    "M5347": f"{_WATCH} {_LISTED}",
    "M5348": f"{_HUMANS}",
    "M5349": f"{_NO_HOUR} {_DISCORD_HOUR}",
    "M5350": f"{_DISCORD} {_DISCORD_HOUR}",
    "M5351": f"{_SELF}",
    "M5352": f"{_SELF}",
    "M5353": f"{_NO_LIST}",
    "M5354": f"{_LISTED} {_DISCORD_TITLE}",
    "M5355": f"{_LISTED} {_DISCORD_TITLE}",
    "M5356": f"{_LISTED} {_EXAMPLE}",
    "M5357": f"{_EXAMPLE} {_WATCH}",
    "M5358": f"{_DISCORD_TITLE}",
    "M5359": f"{_DISCORD_TITLE}",
    "M5360": f"{_PAGE}",
}
