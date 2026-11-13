"""MSK2 (#762): IML1c's follow-up (decision of Jonathan, 12/11) — no output of the CLI meant for a human
shows a subscription's id (Azure's error text at the boundary and every refusal, the ambiguous short
name, the decision rendered, `list` and the commands it suggests), and no webhook nor bot of the
developer's shell in the test suite. M4950–M4959, then M4980–M4989 after the first review (pending,
activate, three forms of an id, the guard of the imports) and M4990–M4994 after the second (a short name
that takes another VM, the rules pending proposes), M5000–M5003 after the third (jobs's second step,
list's activate hint), measured by tests/unit/test_cli_masking.py and
tests/unit/test_entries_calls.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
CLI = "glorfindel/cli.py"
MASK = "glorfindel/masking.py"
CONFTEST = "tests/unit/conftest.py"
_M = "tests/unit/test_cli_masking.py"
_CALLS = "tests/unit/test_entries_calls.py"

MUTANTS = [
    ("M4950", "Azure's error rendered as it is at the CLI's boundary: a 403's « over scope "
     "'/subscriptions/…' » pasted with the output (MSK2)", CLI,
     '            console.print(f"[red]✗ {type(e).__name__}: {_esc_markup(_ids_masked(e))}[/red]")\n',
     '            console.print(f"[red]✗ {type(e).__name__}: {e}[/red]")\n'),
    ("M4951", "a refusal said as raised: the id its text carries reaches the terminal (MSK2)", CLI,
     "            e.message = _ids_masked(e.message)\n",
     "            e.message = e.message\n"),
    ("M4952", "the refusal of an ambiguous short name lists the full ids, the subscription's with them "
     "(MSK2)", CLI,
     '            + "\\n  ".join(_vms_said(found.values()))\n',
     '            + "\\n  ".join(sorted(found.values()))\n'),
    ("M4953", "the model's explanation rendered as it is: the signal's id it copied, on the terminal "
     "(MSK2)", CLI,
     '    table.add_row("Explanation", _esc_markup(_ids_masked(state.get("explanation", ""))))\n',
     '    table.add_row("Explanation", state.get("explanation", ""))\n'),
    ("M4954", "the model's reasoning rendered as it is: the id and the subscription it names, on the "
     "terminal (MSK2)", CLI,
     '        _esc_markup(_ids_masked(state.get("reasoning", ""))),\n',
     '        state.get("reasoning", ""),\n'),
    ("M4955", "a subscription's id a sentence names (« The subscription '…' could not be found ») left "
     "bare (MSK2)", MASK,
     '    out = _SUB_NAMED.sub(lambda m: f"{m.group(1)}{m.group(2)}{SUBSCRIPTION}", out)\n',
     "    out = out\n"),
    ("M4956", "only AZURE_SUBSCRIPTION_ID read as the environment's subscription: another one's id, bare "
     "in a text, stays (MSK2)", MASK,
     '        if name.upper().endswith("SUBSCRIPTION_ID") and re.fullmatch(_GUID, str(value or "").strip()):\n',
     '        if name.upper() == "AZURE_SUBSCRIPTION_ID" and re.fullmatch(_GUID, str(value or "").strip()):\n'),
    ("M4957", "glorfindel list suggests its commands with the full id: the subscription's id in every "
     "hint (MSK2)", CLI,
     "        target = resource_id if show_ids else _name_for_a_command(resource_id)\n",
     "        target = resource_id\n"),
    ("M4958", "glorfindel list --ids shows no id: a name two VMs hold, the hint asks for an id nothing "
     "shows (MSK2)", CLI,
     "        target = resource_id if show_ids else _name_for_a_command(resource_id)\n",
     "        target = _name_for_a_command(resource_id)\n"),
    ("M4959", "the suite keeps the developer's webhook and bot: a test without a fake posts for real "
     "(MSK2)", CONFTEST,
     "    for name in ALERTING_ENV:\n        monkeypatch.delenv(name, raising=False)\n",
     "    for name in ALERTING_ENV[:0]:\n        monkeypatch.delenv(name, raising=False)\n"),
    # The review of MSK2 (r1): pending, activate, three forms of an id, the guard of the imports.
    ("M4980", "glorfindel pending says the card's reason as the model wrote it: the id it copied, pasted "
     "(MSK2)", CLI,
     '    reason = _ids_masked(e["reason"])                   # the model\'s words: masked, then cut (MSK2)\n',
     '    reason = e["reason"]\n'),
    ("M4981", "glorfindel pending says the model's suggested steps as written: « glorfindel restore "
     "/subscriptions/… » on the card (MSK2)", CLI,
     '            console.print(f"  [cyan]{i}.[/cyan] {_esc_markup(_ids_masked(step))}")\n',
     '            console.print(f"  [cyan]{i}.[/cyan] {step}")\n'),
    ("M4982", "glorfindel pending's own steps give the full id: the subscription's id in every command "
     "it suggests (MSK2)", CLI,
     '    rid = _name_for_a_command(e["resource_id"])      # never the full id on the card (MSK2)\n',
     '    rid = e["resource_id"]\n'),
    ("M4983", "glorfindel pending suggests a name two VMs hold: the command it gives is refused (MSK2)", CLI,
     '    except click.ClickException:\n        return UNNAMED\n',
     "    except click.ClickException:\n        return named\n"),
    ("M4984", "glorfindel activate says its reasons raw: other_subscription's two subscriptions on the "
     "terminal (MSK2)", CLI,
     "        console.print(f\"  • [{r['level']}] {_esc_markup(_ids_masked(r['message'], subscriptions=subs))}\",\n",
     "        console.print(f\"  • [{r['level']}] {r['message']}\",\n"),
    ("M4985", "glorfindel activate forgets the connector's subscription: « Glorfindel agit dans <guid> » "
     "stays when the environment names none (MSK2)", CLI,
     '    subs = [s for s in (getattr(connector, "_subscription_id", None), _subscription_of(rid))\n',
     "    subs = [s for s in (_subscription_of(rid),)\n"),
    ("M4986", "an id encoded whole (« %2Fsubscriptions%2F<guid> ») read as no id: its subscription stays "
     "(MSK2)", MASK,
     '_SUB_IN_ID = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=%2F))subscriptions(?:/|%2F)(" + _GUID + ")", '
     're.IGNORECASE)\n',
     '_SUB_IN_ID = re.compile(r"\\bsubscriptions(?:/|%2F)(" + _GUID + ")", re.IGNORECASE)\n'),
    ("M4987", "the JSON of an error body (« 'subscriptionId': '<guid>' ») read as no subscription named "
     "(MSK2)", MASK,
     r'''                        r"([\s\"'=:(«»/]{1,4})(" + _GUID + r")(?![0-9A-Za-z])", re.IGNORECASE)''' + "\n",
     r'''                        r"(\W{1,3})(" + _GUID + r")(?![0-9A-Za-z])", re.IGNORECASE)''' + "\n"),
    ("M4988", "« subscription identifier '<guid>' » read as no subscription named (MSK2)", MASK,
     "(?:[ _-]?(?:identifier|id))?)",
     "(?:[ _-]?(?:id))?)"),
    ("M4989", "the guard of the imports blind to « from glorfindel import masking »: another module could "
     "mask what the model sees, unseen (MSK2)", _M,
     '        yield from (a.name == "masking" for a in node.names)\n',
     "        yield from ()\n"),
    # The review of MSK2 (r2): a short name that takes another VM, the rules pending proposes.
    ("M4990", "glorfindel pending gives a short name that resolves to another VM: « restore vm-a --yes » "
     "copied restores the homonym of another group, asking nothing (MSK2)", CLI,
     '    if resolved.rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():\n',
     "    if False:\n"),
    ("M4991", "glorfindel pending compares the resolved id by its case: the card's own VM asked by its id "
     "(MSK2)", CLI,
     '    if resolved.rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():\n',
     '    if resolved.rstrip("/") != str(resource_id or "").rstrip("/"):\n'),
    ("M4992", "a proposed rule's query shown as the model wrote it: its _ResourceId, the subscription's id "
     "with it (MSK2)", CLI,
     '    console.print(Syntax(_ids_masked(p["query"]).strip(), "sql", theme="monokai", line_numbers=False))\n',
     '    console.print(Syntax(p["query"].strip(), "sql", theme="monokai", line_numbers=False))\n'),
    ("M4993", "a proposed rule's analysis shown raw (MSK2)", CLI,
     "    console.print(f\"  Analysis  : [dim]{_esc_markup(_ids_masked(p['analysis'])[:100])}…[/dim]\")\n",
     "    console.print(f\"  Analysis  : [dim]{p['analysis'][:100]}…[/dim]\")\n"),
    ("M4994", "a proposed rule's explanation shown raw (MSK2)", CLI,
     "    console.print(f\"  Why better: {_esc_markup(_ids_masked(p['explanation'])[:100])}\")\n",
     "    console.print(f\"  Why better: {p['explanation'][:100]}\")\n"),
    # The review of MSK2 (r3): every command to copy goes through _name_for_a_command.
    ("M5000", "glorfindel jobs's second step names the VM by hand: « release vm --yes » lifts a homonym's "
     "quarantine, asking nothing (MSK2)", CLI,
     "_esc_markup(_name_for_a_command(job.get('resource_id') or resource_id))",
     "_esc_markup(vm_name)"),
    ("M5001", "glorfindel jobs's second step reads the argument, not the job: a short argument, the id "
     "asked for a VM that is known (MSK2)", CLI,
     "_name_for_a_command(job.get('resource_id') or resource_id)",
     "_name_for_a_command(resource_id)"),
    ("M5002", "glorfindel list's activate hint names the VM by hand: a name two VMs hold, refused (MSK2)", CLI,
     '                     f" → glorfindel activate {_esc_markup(target)})[/dim]") if _hold else ""\n',
     '                     f" → glorfindel activate {vm_short})[/dim]") if _hold else ""\n'),
    ("M5003", "glorfindel list says a mode's hold raw: the id its message names (MSK2)", CLI,
     "held: {_esc_markup(_ids_masked(_hold['message']))}",
     "held: {_hold['message']}"),
]
TESTS = {
    "M4950": f"{_M}::test_azure_s_error_at_the_boundary_is_said_without_the_subscription",
    "M4951": f"{_M}::test_a_refusal_is_said_without_the_subscription",
    "M4952": f"{_CALLS}::test_two_vms_of_one_name_are_refused_wherever_they_are_known",
    "M4953": f"{_M}::test_the_decision_is_rendered_without_the_subscription_and_kept_whole",
    "M4954": f"{_M}::test_the_decision_is_rendered_without_the_subscription_and_kept_whole",
    "M4955": f"{_M}::test_no_subscription_id_is_left_in_a_text",
    "M4956": f"{_M}::test_the_environment_s_subscription_is_masked_even_bare",
    "M4957": f"{_M}::test_list_says_each_vm_by_its_name_and_group_and_the_ids_when_asked",
    "M4958": f"{_M}::test_list_says_each_vm_by_its_name_and_group_and_the_ids_when_asked",
    "M4959": f"{_M}::test_no_webhook_nor_bot_comes_from_the_developer_s_shell",
    "M4980": f"{_M}::test_pending_says_the_card_without_the_subscription",
    "M4981": f"{_M}::test_pending_says_the_card_without_the_subscription",
    "M4982": f"{_M}::test_pending_s_own_steps_name_the_vm_by_its_group_and_name",
    "M4983": f"{_M}::test_pending_never_suggests_a_name_two_vms_hold",
    "M4984": f"{_M}::test_activate_says_its_reasons_without_the_subscriptions",
    "M4985": f"{_M}::test_activate_says_its_reasons_without_the_subscriptions",
    "M4986": f"{_M}::test_no_subscription_id_is_left_in_a_text",
    "M4987": f"{_M}::test_no_subscription_id_is_left_in_a_text",
    "M4988": f"{_M}::test_no_subscription_id_is_left_in_a_text",
    "M4989": f"{_M}::test_the_guard_sees_every_form_of_import",
    "M4990": f"{_M}::test_pending_never_gives_a_name_that_takes_another_vm",
    "M4991": f"{_M}::test_pending_takes_the_vm_back_whatever_its_case",
    "M4992": f"{_M}::test_pending_says_a_proposed_rule_without_the_subscription",
    "M4993": f"{_M}::test_pending_says_a_proposed_rule_without_the_subscription",
    "M4994": f"{_M}::test_pending_says_a_proposed_rule_without_the_subscription",
    "M5000": f"{_M}::test_jobs_never_gives_a_name_that_lifts_another_vm",
    "M5001": f"{_M}::test_jobs_says_its_next_step_by_the_vm_s_name",
    "M5002": f"{_M}::test_list_s_held_mode_names_activate_s_vm_without_its_id",
    "M5003": f"{_M}::test_list_s_held_mode_names_activate_s_vm_without_its_id",
}
