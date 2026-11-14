"""CMD1b (#811): `glorfindel isolate` and `glorfindel block` say the VM's enrollment zone on one line before
the prompt — read as the console reads it (TagEnrollment's tags, judged by ``enrollment``) — and never refuse
for it (Jonathan's decision of 14/11). M5285–M5294, measured by tests/unit/test_cli_contain.py (§4, a fake
reader of tags: no Azure call)."""
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
     'f"  [bold red]Zone     : production — une charge réelle : ce geste la touche pour de vrai "',
     'f"  [bold red]Zone     : production — ce geste la touche "'),
    ("M5289", "the zone refuses: a gesture on a VM of production is refused, against Jonathan's decision "
     "(CMD1b)", CLI,
     '        lift = "glorfindel release" if action == "isolate_vm" else "glorfindel unblock"\n',
     '        raise click.ClickException("zone production : rien n\'est fait")\n'),
    ("M5290", "a read of the tags that fails escapes: the gesture aborted on an Azure error, exit 1 (CMD1b)",
     GESTURES,
     '    except Exception as exc:\n        return "unreadable"',
     '    except ValueError as exc:\n        return "unreadable"'),
    ("M5291", "a dry run reads the tags through Azure: « nothing asked of Azure » broken (CMD1b)", CLI,
     '    if dry_run:\n        console.print("  [yellow]Zone     : non lue',
     '    if False:\n        console.print("  [yellow]Zone     : non lue'),
    ("M5292", "a dry run says no zone at all: the line missing where the fiche wants it (CMD1b)", CLI,
     "    _zone_said(resource_id, action, dry_run)\n",
     "    if not dry_run:\n        _zone_said(resource_id, action, dry_run)\n"),
    ("M5293", "what Azure says of a failed read is shown unmasked: the subscription's id on the terminal "
     "(MSK2, CMD1b)", CLI,
     '"".join(c if c.isprintable() else " " for c in _ids_masked(why))',
     '"".join(c if c.isprintable() else " " for c in why)'),
    ("M5294", "a tag's value is printed as rich markup: what the tag says is not what the line says (CMD1b)",
     CLI,
     "    why = _esc_markup(why[:200])\n",
     "    why = why[:200]\n"),
]
TESTS = {
    "M5285": f"{_C}::test_a_vm_not_enrolled_is_said_so_never_taken_for_the_bench",
    "M5286": f"{_C}::test_tags_unread_are_said_unreadable_and_the_gesture_is_made",
    "M5287": f"{_C}::test_a_zone_none_of_the_three_is_said_unknown_never_the_bench",
    "M5288": f"{_C}::test_production_is_said_a_real_load_and_never_refused",
    "M5289": f"{_C}::test_production_is_said_a_real_load_and_never_refused",
    "M5290": f"{_C}::test_tags_unread_are_said_unreadable_and_the_gesture_is_made",
    "M5291": f"{_C}::test_a_dry_run_says_the_zone_unread_and_reads_nothing",
    "M5292": f"{_C}::test_a_dry_run_says_the_zone_unread_and_reads_nothing",
    "M5293": f"{_C}::test_what_the_reader_says_is_masked_printable_and_never_markup",
    "M5294": f"{_C}::test_what_the_reader_says_is_masked_printable_and_never_markup",
}
