"""SEC-Fc (#907): the rest of SEC-F's review — text from outside never markup, to the end. Azure's
poll error said as it is, the search going on; a decision taken whose display fails said as such,
never « Error processing »; the error that keeps the campaign reports off said as it is; the name
in `pending`'s `az vm show` quoted; the TUI's panels never handing a control character to the
terminal (`literal`); and a mutant each for three quotes SEC-F left without one (the TUI's
commands, the bot's first detection, the ack of `_render_next_steps`). M6271–M6290, measured by
tests/unit/test_outside_markup.py and tests/unit/test_hosted_report.py."""
TERM = "glorfindel/terminal.py"
MON = "glorfindel/providers/azure/monitor.py"
CLI = "glorfindel/cli.py"
DISPATCH = "glorfindel/watch/dispatch.py"   # WCH1: the watch moved to glorfindel/watch/
STARTUP = "glorfindel/watch/startup.py"
BOT = "glorfindel/bot.py"
TUI = "glorfindel/tui.py"
_T = "tests/unit/test_outside_markup.py"
_H = "tests/unit/test_hosted_report.py"

MUTANTS = [
    ("M6271", "Azure's poll error printed raw: a `[/…]` in it raises out of the poll, the search ends "
     "as a cycle_failed card (SEC-Fc, the defect back)", MON,
     '                    _console.print(f"  [dim]Poll error: {outside(e)}[/dim]")\n',
     '                    _console.print(f"  [dim]Poll error: {e}[/dim]")\n'),
    ("M6272", "the display of a decision no longer guarded on its own: its failure said « Error "
     "processing », a decision taken said unprocessed (SEC-Fc, the defect back)", DISPATCH,
     "                self._render_decision(state, self.dry_run)\n"
     "            except Exception as e:\n",
     "                self._render_decision(state, self.dry_run)\n"
     "            except ZeroDivisionError as e:\n"),
    ("M6273", "a decision's display that fails swallowed in silence (SEC-Fc)", DISPATCH,
     '                _say_failure(self.console, f"Décision prise pour {_sig.signal_id}, "\n'
     '                             "son affichage a échoué", e)   # the lock held already\n',
     "                pass\n"),
    ("M6274", "pending's fallback names the VM unquoted in its `az vm show` (SEC-Fc)", CLI,
     "-n {shlex.quote(_short_name(e['resource_id']))} ",
     "-n {_short_name(e['resource_id'])} "),
    ("M6275", "the error that keeps the campaign reports off printed raw (SEC-Fc, the defect back)", STARTUP,
     '        console.print(f"[yellow]Rapports de campagne désactivés — {type(exc).__name__}: "\n'
     '                      f"{_outside(exc)}[/yellow]")\n',
     '        console.print(f"[yellow]Rapports de campagne désactivés — {type(exc).__name__}: "\n'
     '                      f"{exc}[/yellow]")\n'),
    ("M6276", "literal() shows no control character: every `Text` of the TUI hands an escape sequence "
     "to the terminal (SEC-Fc)", TERM,
     "    return _controls_shown(value)\n",
     '    return "" if value is None else str(value)\n'),
    ("M6277", "the TUI's card says its id raw (SEC-Fc)", TUI,
     'lines.append(f"  [{_literal(esc_id)}]  ", style="dim")',
     'lines.append(f"  [{esc_id}]  ", style="dim")'),
    ("M6278", "the TUI's card says the model's action raw (SEC-Fc, the defect back)", TUI,
     "lines.append(_literal(_shown(action, e['resource_id'])), style=\"bold yellow\")",
     "lines.append(f\"{_shown(action, e['resource_id'])}\", style=\"bold yellow\")"),
    ("M6279", "the TUI's card says its VM's name raw (SEC-Fc)", TUI,
     'lines.append(f"  {_literal(vm_short)}  {age} ago\\n", style="dim")',
     'lines.append(f"  {vm_short}  {age} ago\\n", style="dim")'),
    ("M6280", "the TUI's card says the model's steps raw (SEC-Fc, the defect back)", TUI,
     'lines.append(f"    • {_literal(step[:72])}\\n", style="dim")',
     'lines.append(f"    • {step[:72]}\\n", style="dim")'),
    ("M6281", "the TUI's restore command says the card's first detection raw (SEC-Fc)", TUI,
     "            lines.append(_literal(\n"
     '                f"    → glorfindel restore {vm_arg} --yes --before "\n'
     '                f"{before}  # before the attack began\\n"),\n',
     "            lines.append((\n"
     '                f"    → glorfindel restore {vm_arg} --yes --before "\n'
     '                f"{before}  # before the attack began\\n"),\n'),
    ("M6282", "the TUI says what the restore said raw (SEC-Fc)", TUI,
     '    return _literal(_shown(_last_restore.get("text", ""), _last_restore.get("rid", "")))\n',
     '    return _shown(_last_restore.get("text", ""), _last_restore.get("rid", ""))\n'),
    ("M6283", "the TUI's restore panel says its label raw (SEC-Fc)", TUI,
     "    lines.append(f\"\\n  ⚡ {_literal(pending['label'])}\\n\\n\", style=\"bold yellow\")\n"
     '    if pending["stage"] == "moment":\n',
     "    lines.append(f\"\\n  ⚡ {pending['label']}\\n\\n\", style=\"bold yellow\")\n"
     '    if pending["stage"] == "moment":\n'),
    ("M6284", "the TUI's restore panel says why its moment raw (SEC-Fc)", TUI,
     "lines.append(f\"  {_literal(_shown(pending['why'], rid))}\\n\", style=\"dim\")",
     "lines.append(f\"  {_shown(pending['why'], rid)}\\n\", style=\"dim\")"),
    ("M6285", "the TUI's restore panel says its error raw (SEC-Fc)", TUI,
     "lines.append(f\"  ✗ {_literal(_shown(pending['error'], rid))}\\n\", style=\"red\")",
     "lines.append(f\"  ✗ {_shown(pending['error'], rid)}\\n\", style=\"red\")"),
    ("M6286", "the TUI's confirmation says its label raw (SEC-Fc)", TUI,
     "    if pending:\n        lines.append(f\"\\n  ⚡ {_literal(pending['label'])}\\n\\n\", style=\"bold yellow\")\n",
     "    if pending:\n        lines.append(f\"\\n  ⚡ {pending['label']}\\n\\n\", style=\"bold yellow\")\n"),
    ("M6287", "the TUI's ack names the card unquoted (SEC-F, V-22; its own mutant, SEC-Fc)", TUI,
     "        ack_id = shlex.quote(str(esc_id))\n",
     "        ack_id = str(esc_id)\n"),
    ("M6288", "the TUI's restore command names the first detection unquoted (SEC-F, V-22; its own "
     "mutant, SEC-Fc)", TUI,
     '        before = shlex.quote(str(before)) if before else "<ISO8601>"\n',
     '        before = str(before) if before else "<ISO8601>"\n'),
    ("M6289", "the bot's restore command names the first detection unquoted (SEC-F, V-22; its own "
     "mutant, SEC-Fc)", BOT,
     '        before = _arg(before) if before else "<ISO8601>"\n',
     '        before = str(before) if before else "<ISO8601>"\n'),
    ("M6290", "pending's fallback acks the card unquoted (SEC-F; its own mutant, SEC-Fc)", CLI,
     "            f\"If false positive: glorfindel ack {shlex.quote(str(e['id']))}\",\n",
     "            f\"If false positive: glorfindel ack {e['id']}\",\n"),
]
_TUI_ESC = f"{_T}::test_the_tui_s_panels_never_hand_a_control_character_to_the_terminal"
TESTS = {
    "M6271": f"{_T}::test_a_poll_error_from_azure_is_said_as_it_is_and_the_search_goes_on",
    "M6272": f"{_T}::test_a_decision_whose_display_fails_is_said_taken_never_error_processing "
             f"{_T}::test_whatever_one_detection_raised_the_thread_takes_the_next",
    "M6273": f"{_T}::test_a_decision_whose_display_fails_is_said_taken_never_error_processing",
    "M6274": f"{_T}::test_pending_s_fallback_steps_quote_the_card_s_name_and_id",
    "M6275": f"{_H}::test_the_reports_off_say_their_error_as_it_is",
    "M6276": _TUI_ESC,
    "M6277": _TUI_ESC,
    "M6278": _TUI_ESC,
    "M6279": _TUI_ESC,
    "M6280": _TUI_ESC,
    "M6281": _TUI_ESC,
    "M6282": _TUI_ESC,
    "M6283": _TUI_ESC,
    "M6284": _TUI_ESC,
    "M6285": _TUI_ESC,
    "M6286": _TUI_ESC,
    "M6287": f"{_T}::test_the_tui_quotes_each_argument_of_a_command",
    "M6288": f"{_T}::test_the_tui_quotes_each_argument_of_a_command",
    "M6289": f"{_T}::test_each_argument_of_the_bot_s_command_is_quoted_for_the_shell",
    "M6290": f"{_T}::test_pending_s_fallback_steps_quote_the_card_s_name_and_id",
}
