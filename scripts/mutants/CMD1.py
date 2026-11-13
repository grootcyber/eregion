"""CMD1 (#797): `glorfindel isolate` and `glorfindel block` exist — a containment by a human's hand, the
console's approval of a held card without the card, the same calls and the same guards
(glorfindel/gestures.py) — and no command Glorfindel proposes is invented. M5205–M5219, measured by
tests/unit/test_cli_contain.py (the gestures, on the in-memory Azure) and tests/unit/test_proposed_commands.py
(every command to copy of the code, held against Click's own tree). M5275–M5284 after the first review
(#808): a session cut no watch here rereads, a prefix two cards share, a write that lands in part, the
dry run's read-only guard, the way into the watch's container."""
GESTURES = "glorfindel/gestures.py"
CLI = "glorfindel/cli.py"
POLICY = "glorfindel/response/policy.py"
ESC = "glorfindel/escalations.py"
REASSERT = "glorfindel/reassert.py"
API = "eregion_console/api.py"
CONSOLE_JS = "eregion_console/static/glorfindel.js"
_C = "tests/unit/test_cli_contain.py"
_P = "tests/unit/test_proposed_commands.py"

MUTANTS = [
    ("M5205", "the CLI isolates a VM the watch does not know: any id pasted, a VM of another perimeter cut off "
     "(CMD1)", GESTURES,
     "    if not approval.in_perimeter(resource_id):\n",
     "    if False:\n"),
    ("M5206", "the CLI isolates the VM a card is only anchored on: the detection does not name it (AL1, CMD1)",
     GESTURES,
     "    if anchored:\n        ids = ",
     "    if False:\n        ids = "),
    ("M5207", "the console's message for a card without its address names the VM by its full id again: the "
     "subscription on the page, a homonym of another group taken (MSK3b, CMD1)", API,
     'f"or run: glorfindel block <ip> {group_and_name(resource_id)} --yes")}',
     'f"or run: glorfindel block <ip> {resource_id} --yes")}'),
    ("M5208", "the CLI's block takes an address of the never-block list up to the connector: refused only at "
     "the write, its connector made, said as an Azure error (SEC2, CMD1)", GESTURES,
     "    return approval.address_refusal(ip)\n",
     '    return ip, ""\n'),
    ("M5209", "the CLI's gesture runs without the VM's lock: the watch or the console releases the VM between "
     "its isolation and its check (CMD1)", GESTURES,
     '    with _vm_lock(resource_id.rstrip("/").rsplit("/", 1)[-1]):\n',
     '    with __import__("contextlib").nullcontext():\n'),
    ("M5210", "the CLI's gesture is never checked after: a NIC still open said contained, no card (Q11, CMD1)",
     GESTURES,
     '        verification = approval.verify_approved(connector, {"id": ""}, action, resource_id, result, ip,\n'
     '                                                record=record, signal_id=f"cli-{action}",\n'
     '                                                drain_followed=drain_followed)\n',
     '        verification = {"verified": True}\n'),
    ("M5211", "the CLI's gesture is not noted in runs/console: the feed never shows the hand that isolated "
     "(CMD1)", GESTURES,
     '                                                record=record, signal_id=f"cli-{action}",\n',
     '                                                record=None, signal_id=f"cli-{action}",\n'),
    ("M5212", "read-only credentials are found only at the write: the boundary says « a state file owned by "
     "root » (CMD1)", CLI,
     '    if getattr(connector, "read_only", False):\n        raise click.ClickException("credentials en lecture',
     '    if False:\n        raise click.ClickException("credentials en lecture'),
    ("M5213", "the CLI resolves the held card of its gesture in silence: the human never reads it, nor checks "
     "before acknowledging (CMD1)", CLI,
     "        console.print(f\"  [cyan]Carte {e['id'][:8]} en attente pour ce geste",
     "        __import__(\"glorfindel.escalations\").escalations.resolve(e[\"id\"]) or "
     "console.print(f\"  [cyan]Carte {e['id'][:8]} en attente pour ce geste"),
    ("M5214", "`block --scope subnet` blocks the VM alone: the human's reach dropped (CMD1)", GESTURES,
     "        return connector.block_suspicious_ip(ip, resource_id, scope, False, port)\n",
     '        return connector.block_suspicious_ip(ip, resource_id, "vm", False, port)\n'),
    ("M5215", "the reassertion's card proposes `block <ip>` with the VM's full id again: the subscription on the "
     "card, no command once masked (MSK3b, CMD1)", REASSERT,
     "`glorfindel block {ip} {group_and_name(rid)} --scope vm --yes`.",
     "`glorfindel block {ip} {rid} --scope vm --yes`."),
    ("M5216", "the console's 📋 Command proposes a command the CLI does not have (CMD1)", CONSOLE_JS,
     "      isolate_vm:          `glorfindel isolate ${vm} --yes`,\n",
     "      isolate_vm:          `glorfindel contain ${vm} --yes`,\n"),
    ("M5217", "an action the console does not run sends the operator to `respond <id>`, which takes a file of "
     "signals (CMD1)", API,
     'f"la faire à la main, puis glorfindel ack {str(esc.get(\'id\', \'\'))[:8]}")',
     'f"CLI : glorfindel respond {esc.get(\'resource_id\', \'\')}")'),
    ("M5218", "`glorfindel ack <8 characters>` — what the console and the TUI give — matches no card again "
     "(CMD1)", ESC,
     '    hits = exact or [e for e in cards if str(e.get("id", "")).lower().startswith(ref)]\n',
     "    hits = exact\n"),
    ("M5219", "the CLI writes its state on a workstation while the watch runs on Imladris, unsaid: no "
     "reassertion, no release by its console (CMD1)", CLI,
     "    if watch_gate.fresh(watch_gate.local_beat(), datetime.now(timezone.utc)):\n",
     "    if True:\n"),
    # Review 1 (#808).
    ("M5275", "a session cut still running is said reread by the reassertion where no watch lives: « ✓ », "
     "code 0, no card — an attacker's session open (CMD1, review)", POLICY,
     "        if followed is False:\n",
     "        if False:\n"),
    ("M5276", "the CLI's isolate never says whether a watch lives here: the cut it leaves running is "
     "followed by nobody, said held (CMD1, review)", CLI,
     '                           drain_followed=None if watched else False)\n    _contained_said(out, "VM isolée"',
     '                           drain_followed=None)\n    _contained_said(out, "VM isolée"'),
    ("M5277", "the gesture drops what the CLI knows of the watch here: the check reads the reassertion's "
     "setting only (CMD1, review)", GESTURES,
     "                                                drain_followed=drain_followed)\n",
     "                                                drain_followed=None)\n"),
    ("M5278", "`ack <8 characters>` two cards share acknowledges the first of them in silence (CMD1, review)",
     ESC,
     '    if len(hits) > 1:\n        raise ValueError(f"{escalation_id} matches {len(hits)} cards — give more '
     'characters")\n    return hits[0]\n',
     "    return hits[0]\n"),
    ("M5279", "an isolation landed on some NICs only escapes the gesture: said once as an Azure error, code 1, "
     "neither noted nor carded (CMD1, review)", GESTURES,
     "        except PartialActionError as exc:\n",
     "        except ZeroDivisionError as exc:\n"),
    ("M5280", "an isolation landed in part leaves no card: nobody is asked to finish it (CMD1, review)",
     GESTURES,
     '    escalations.record(signal_id=f"cli-{action}", resource_id=resource_id, action=action,\n',
     '    (lambda **k: None)(signal_id=f"cli-{action}", resource_id=resource_id, action=action,\n'),
    ("M5281", "an isolation landed in part is not noted in runs/console: the feed never shows it (CMD1, "
     "review)", GESTURES,
     '            record(action, resource_id, {**result, **verification, "approved_escalation": ""})\n',
     "            pass\n"),
    ("M5282", "a dry run passes read-only credentials: « the guards only » checks one guard less (CMD1, "
     "review)", CLI,
     '    if getattr(connector, "read_only", False):\n',
     '    if not dry_run and getattr(connector, "read_only", False):\n'),
    ("M5283", "the line to the watch's container gives `docker exec` without `-it`: the prompt reads an end "
     "of file, the gesture aborted (CMD1, review)", CLI,
     '"conteneur (docker exec -it eregion-watch …).[/yellow]")',
     '"conteneur (docker exec eregion-watch …).[/yellow]")'),
    ("M5284", "a session cut no watch here rereads is said « the reassertion is off »: the wrong cause, the "
     "wrong remedy (CMD1, review)", POLICY,
     '                    "drain_followed": False, "error": DRAIN_UNWATCHED}\n',
     '                    "drain_followed": False, "error": DRAIN_UNFOLLOWED}\n'),
]
TESTS = {
    "M5205": f"{_C}::test_a_vm_outside_the_watch_s_perimeter_is_refused_before_any_call",
    "M5206": f"{_C}::test_a_vm_a_card_is_only_anchored_on_is_refused",
    "M5207": f"{_P}::test_every_proposed_command_exists_with_its_arguments",
    "M5208": f"{_C}::test_only_one_blockable_host_address_is_blocked",
    "M5209": f"{_C}::test_the_whole_gesture_holds_the_vm_s_lock",
    "M5210": f"{_C}::test_a_check_that_fails_is_said_left_on_a_card_and_exits_2",
    "M5211": f"{_C}::test_isolate_by_group_and_name_cuts_the_vm_off_verified_noted_and_held",
    "M5212": f"{_C}::test_read_only_credentials_refuse_before_any_write",
    "M5213": f"{_C}::test_a_held_card_of_the_same_gesture_is_said_never_resolved",
    "M5214": f"{_C}::test_block_on_the_subnet_is_the_human_s_choice",
    "M5215": f"{_P}::test_every_proposed_command_exists_with_its_arguments",
    "M5216": f"{_P}::test_every_proposed_command_exists_with_its_arguments",
    "M5217": f"{_P}::test_an_action_the_console_does_not_run_is_sent_to_commands_that_exist",
    "M5218": f"{_C}::test_ack_takes_the_eight_characters_the_console_and_the_tui_give",
    "M5219": f"{_C}::test_no_live_watch_here_is_said",
    "M5275": f"{_C}::test_a_session_cut_no_watch_here_rereads_is_not_verified",
    "M5276": f"{_C}::test_a_session_cut_no_watch_here_rereads_is_not_verified",
    "M5277": f"{_C}::test_a_session_cut_no_watch_here_rereads_is_not_verified",
    "M5278": f"{_C}::test_ack_of_a_prefix_two_cards_share_acknowledges_neither",
    "M5279": f"{_C}::test_an_isolation_that_lands_on_some_nics_only_is_noted_and_left_on_a_card",
    "M5280": f"{_C}::test_an_isolation_that_lands_on_some_nics_only_is_noted_and_left_on_a_card",
    "M5281": f"{_C}::test_an_isolation_that_lands_on_some_nics_only_is_noted_and_left_on_a_card",
    "M5282": f"{_C}::test_a_dry_run_holds_the_read_only_guard_too",
    "M5283": f"{_C}::test_the_way_to_the_watch_s_container_is_one_a_prompt_answers_in",
    "M5284": f"{_C}::test_a_session_cut_no_watch_here_rereads_is_not_verified",
}
