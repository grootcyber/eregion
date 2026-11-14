"""CMD1b (#811): `glorfindel isolate` and `glorfindel block` say the VM's enrollment zone on one line before
the prompt — read as the console reads it (TagEnrollment's tags, judged by ``enrollment``) — and never refuse
for it (Jonathan's decision of 14/11). M5285–M5294, measured by tests/unit/test_cli_contain.py (§4, a fake
reader of tags: no Azure call). M5305–M5309 after the review: a block on the subnet, a read bounded in time,
the old chaos tag, no empty brackets; M5310 and M5291–M5292 recast after
Jonathan's decision of 14/11: a dry run reads the real zone, writes nothing."""
GESTURES = "glorfindel/gestures.py"
CLI = "glorfindel/cli.py"
_C = "tests/unit/test_cli_contain.py"

MUTANTS = [
    ("M5285", "a VM not enrolled is said to be the bench's: the VM with a real load, never enrolled, "
     "isolated as a bench target (CMD1b)", GESTURES,
     '        return "not_enrolled", verdict.reason\n',
     '        return "bench", ""\n'),
    ("M5286", "tags that could not be read are taken for the bench: a 403 says « bench » (CMD1b)", GESTURES,
     '        return "unreadable", str(exc) or type(exc).__name__\n',
     '        return "bench", ""\n'),
    ("M5287", "a zone none of the three (« Production ») is taken for the bench (CMD1b)", GESTURES,
     '        return "unknown", verdict.zone\n',
     '        return "bench", ""\n'),
    ("M5288", "production is said a zone like another: the line no longer says a real load (CMD1b)", CLI,
     'f"  [bold red]Zone     : production{note} — une charge réelle : ce geste la touche pour "',
     'f"  [bold red]Zone     : production{note} — ce geste la touche "'),
    ("M5289", "the zone refuses: a gesture on a VM of production is refused, against Jonathan's decision "
     "(CMD1b)", CLI,
     '        lift = "glorfindel release" if action == "isolate_vm" else "glorfindel unblock"\n',
     '        raise click.ClickException("zone production : rien n\'est fait")\n'),
    ("M5290", "a read of the tags that fails escapes: the gesture aborted on an Azure error, exit 1 (CMD1b)",
     GESTURES,
     '    except Exception as exc:\n        return "unreadable"',
     '    except ValueError as exc:\n        return "unreadable"'),
    ("M5291", "a dry run says no zone at all: the line missing where Jonathan wants the real zone (CMD1b)",
     CLI,
     "    _zone_said(resource_id, action, scope)\n",
     "    if not dry_run:\n        _zone_said(resource_id, action, scope)\n"),
    ("M5292", "a dry run says the zone unread again, the tags never read: the zone of a real load unsaid "
     "(CMD1b, Jonathan's decision of 14/11)", CLI,
     "    _zone_said(resource_id, action, scope)\n",
     "    _zone_said(resource_id, action, scope) if not dry_run else console.print(\"  Zone     : non lue\")\n"),
    ("M5293", "what Azure says of a failed read is shown unmasked: the subscription's id on the terminal "
     "(MSK2, CMD1b)", CLI,
     '"".join(c if c.isprintable() else " " for c in _ids_masked(why))',
     '"".join(c if c.isprintable() else " " for c in why)'),
    ("M5294", "a tag's value is printed as rich markup: what the tag says is not what the line says (CMD1b)",
     CLI,
     "    why = _esc_markup(why[:200])\n",
     "    why = why[:200]\n"),
    # Review of CMD1b.
    ("M5305", "`block --scope subnet` says the named VM's zone as if it were the block's: its neighbours, any "
     "of them a real load, unsaid (CMD1b, review)", CLI,
     '             "zones non lues") if scope == "subnet" else ""\n',
     '             "zones non lues") if False else ""\n'),
    ("M5306", "the read of the zone waits as long as the credential's search: tens of seconds before the "
     "prompt, unsaid (CMD1b, review)", GESTURES,
     "    reader.join(READ_TIMEOUT_S)\n",
     "    reader.join()\n"),
    ("M5307", "a read that does not answer in time is taken for the bench (CMD1b, review)", GESTURES,
     '        return "unreadable", f"pas de réponse en {READ_TIMEOUT_S:g} s"\n',
     '        return "bench", ""\n'),
    ("M5308", "a VM enrolled by the old chaos tag alone is said bench as if by eregion-target (CMD1b, review)",
     GESTURES,
     '    return verdict.zone, "ancien tag" if verdict.legacy else ""\n',
     '    return verdict.zone, ""\n'),
    ("M5309", "a reason left empty shows « () » (CMD1b, review)", CLI,
     '    note = f" ({why})" if why else ""',
     '    note = f" ({why})"'),
    ("M5310", "the zone is read before the guards: a gesture refused (read-only credentials, a dry run too) "
     "asks Azure for its tags (CMD1b)", CLI,
     "    connector = AzureConnector(dry_run=dry_run)\n    if getattr(connector, \"read_only\", False):\n",
     "    connector = AzureConnector(dry_run=dry_run)\n    _zone_said(resource_id, action, scope)\n"
     "    if getattr(connector, \"read_only\", False):\n"),
]
TESTS = {
    "M5285": f"{_C}::test_a_vm_not_enrolled_is_said_so_never_taken_for_the_bench",
    "M5286": f"{_C}::test_tags_unread_are_said_unreadable_and_the_gesture_is_made",
    "M5287": f"{_C}::test_a_zone_none_of_the_three_is_said_unknown_never_the_bench",
    "M5288": f"{_C}::test_production_is_said_a_real_load_and_never_refused",
    "M5289": f"{_C}::test_production_is_said_a_real_load_and_never_refused",
    "M5290": f"{_C}::test_tags_unread_are_said_unreadable_and_the_gesture_is_made",
    "M5291": f"{_C}::test_a_dry_run_reads_the_real_zone_and_writes_nothing",
    "M5292": f"{_C}::test_a_dry_run_reads_the_real_zone_and_writes_nothing",
    "M5293": f"{_C}::test_what_the_reader_says_is_masked_printable_and_never_markup",
    "M5294": f"{_C}::test_what_the_reader_says_is_masked_printable_and_never_markup",
    "M5305": f"{_C}::test_a_block_on_the_subnet_says_its_other_vms_zones_are_not_read",
    "M5306": f"{_C}::test_a_read_that_does_not_answer_in_time_is_said_and_the_gesture_made",
    "M5307": f"{_C}::test_a_read_that_does_not_answer_in_time_is_said_and_the_gesture_made",
    "M5308": f"{_C}::test_the_old_chaos_tag_alone_is_said_bench_by_the_old_tag",
    "M5309": f"{_C}::test_a_reason_left_empty_shows_no_empty_brackets",
    "M5310": f"{_C}::test_a_refused_gesture_reads_no_tag",
}
