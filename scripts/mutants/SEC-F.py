"""SEC-F (#845): text from outside is never markup for Glorfindel's terminal, and the decision thread
of a VM never dies — `outside()`, a console that never raises on markup and `say_failure` (an error
said escaped, never raising in turn); the watch's decision thread (its display guarded, its loop
guarded); the admission of a line of runs/ (gravity, signal id, resource type of a bounded form);
the bot (its loop, its task supervised, the refusal of a click, its commands quoted, its block
never closed); `glorfindel pending` and the TUI. M5701–M5720, measured by
tests/unit/test_outside_markup.py."""
TERM = "glorfindel/terminal.py"
CLI = "glorfindel/cli.py"
ORIGIN = "glorfindel/signal_origin.py"
BOT = "glorfindel/bot.py"
TUI = "glorfindel/tui.py"
_T = "tests/unit/test_outside_markup.py"

MUTANTS = [
    ("M5701", "outside() escapes no markup: a tag from outside is read as markup again (SEC-F)", TERM,
     "    return escape(_controls_shown(value))\n",
     "    return _controls_shown(value)\n"),
    ("M5702", "Glorfindel's console raises on markup again: a closing tag left unescaped anywhere stops "
     "its thread (SEC-F)", TERM,
     '            return super().render_str(text, **{**kwargs, "markup": False})\n',
     "            raise\n"),
    ("M5703", "say_failure prints the error raw: the tag it quotes raises in the handler itself "
     "(SEC-F, the defect back)", TERM,
     '            console.print(f"[red]{outside(head)} :[/red] {outside(exc)}")\n',
     '            console.print(f"[red]{head} :[/red] {exc}")\n'),
    ("M5704", "the watch prints a signal's id raw: an injector's line breaks the head of its display "
     "(SEC-F)", CLI,
     '    console.rule(f"[bold cyan]Signal — {_outside(sig.signal_id)}[/bold cyan]")\n',
     '    console.rule(f"[bold cyan]Signal — {sig.signal_id}[/bold cyan]")\n'),
    ("M5705", "the decision thread prints a signal's resource type raw (SEC-F)", CLI,
     '                                          f"Resource: {_outside(_sig.resource_type)}\\n")\n',
     '                                          f"Resource: {_sig.resource_type}\\n")\n'),
    ("M5706", "the display of a signal no longer guarded: a display that fails leaves its detection "
     "undecided (SEC-F)", CLI,
     '                                          f"Resource: {_outside(_sig.resource_type)}\\n")\n'
     "                    except Exception as e:\n",
     '                                          f"Resource: {_outside(_sig.resource_type)}\\n")\n'
     "                    except ZeroDivisionError as e:\n"),
    ("M5707", "the decision thread's loop no longer guarded: one detection that raises kills the thread "
     "of its VM, every later detection undecided (SEC-F, the defect back)", CLI,
     "                    try:\n                        _one(item)\n                    except Exception as e:\n",
     "                    try:\n                        _one(item)\n                    except ZeroDivisionError as e:\n"),
    ("M5708", "the decision is shown with the model's action raw (SEC-F, the defect back)", CLI,
     '    action = _outside(state.get("action", "?"))\n',
     '    action = state.get("action", "?")\n'),
    ("M5709", "the admission no longer checks a line's gravity, signal id and resource type (SEC-F)",
     ORIGIN,
     "    why = form_refusal(clean)\n",
     '    why = ""\n'),
    ("M5710", "the admission takes any gravity a line gives (SEC-F)", ORIGIN,
     '    if severity not in (None, "") and severity not in SEVERITIES:\n',
     "    if False:\n"),
    ("M5711", "the bot's loop prints a card's action raw (SEC-F, the defect back)", BOT,
     "                            f\"({_outside(esc['action'])})[/green]\"\n",
     "                            f\"({esc['action']})[/green]\"\n"),
    ("M5712", "the bot's loop prints a card's error raw: the tag it quotes raises again, the turn's other "
     "cards and its notices skipped (SEC-F, the defect back)", BOT,
     '                        _say_failure(_console, "Bot post error", e)\n',
     '                        _console.print(f"[red]Bot post error: {e}[/red]")\n'),
    ("M5713", "the bot's loop started without its guard: ended by an error, it is never started again "
     "(SEC-F)", BOT,
     "            self.bg_task = self.loop.create_task(self._watch_forever())\n",
     "            self.bg_task = self.loop.create_task(self._watch_escalations())\n"),
    ("M5714", "the refusal of a click logs the member's name raw (SEC-F, the defect back)", BOT,
     "        f\"({_outside(getattr(user, 'display_name', '?'))}) on {_outside(where)} — {why}[/yellow]\"\n",
     "        f\"({getattr(user, 'display_name', '?')}) on {_outside(where)} — {why}[/yellow]\"\n"),
    ("M5715", "the refusal's log no longer guarded: a log that fails leaves the click unanswered (SEC-F)",
     BOT,
     "    except Exception as exc:\n        _say_failure(_console, f\"{what} refused (log)\", exc)\n",
     "    except ZeroDivisionError as exc:\n        _say_failure(_console, f\"{what} refused (log)\", exc)\n"),
    ("M5716", "glorfindel pending shows a card's action raw (SEC-F, the defect back)", CLI,
     "    table.add_row(\"Action\", f\"[bold yellow]{_outside(e['action'])}[/bold yellow]\")\n",
     "    table.add_row(\"Action\", f\"[bold yellow]{e['action']}[/bold yellow]\")\n"),
    ("M5717", "glorfindel pending no longer guards a card: one it cannot show stops it, the next hidden "
     "(SEC-F)", CLI,
     "        render(card)\n    except Exception as exc:\n",
     "        render(card)\n    except ZeroDivisionError as exc:\n"),
    ("M5718", "the TUI's feed writes a cycle's action raw: its screen fails on it (SEC-F)", TUI,
     "{icon} {_outside(f'{label:<28}')}[/{color}]",
     "{icon} {label:<28}[/{color}]"),
    ("M5719", "the bot's command to copy names the card's IP unquoted (SEC-F, V-22)", BOT,
     '        ip = _arg(ip) if ip else "<ip>"\n',
     '        ip = str(ip) if ip else "<ip>"\n'),
    ("M5720", "the bot's ``` block of a command closed by what it holds (SEC-F, V-22)", BOT,
     "{discord_fenced(cmds)}",
     "{cmds}"),
]
TESTS = {
    "M5701": f"{_T}::test_outside_says_markup_and_controls_as_they_are",
    "M5702": f"{_T}::test_the_console_never_raises_on_markup",
    "M5703": f"{_T}::test_an_error_is_said_escaped_and_its_saying_never_raises",
    "M5704": f"{_T}::test_a_signal_and_a_decision_from_outside_are_shown_as_they_are_and_the_next_one_decided",
    "M5705": f"{_T}::test_a_signal_and_a_decision_from_outside_are_shown_as_they_are_and_the_next_one_decided",
    "M5706": f"{_T}::test_a_display_that_fails_never_leaves_the_detection_undecided",
    "M5707": f"{_T}::test_whatever_one_detection_raised_the_thread_takes_the_next",
    "M5708": f"{_T}::test_a_signal_and_a_decision_from_outside_are_shown_as_they_are_and_the_next_one_decided",
    "M5709": f"{_T}::test_a_line_whose_gravity_id_or_type_is_out_of_form_is_refused "
             f"{_T}::test_the_watch_refuses_such_a_line_says_it_and_decides_the_next",
    "M5710": f"{_T}::test_a_line_whose_gravity_id_or_type_is_out_of_form_is_refused",
    "M5711": f"{_T}::test_a_card_from_outside_never_stops_the_bot_s_loop",
    "M5712": f"{_T}::test_a_card_from_outside_never_stops_the_bot_s_loop",
    "M5713": f"{_T}::test_the_bot_s_loop_ended_by_an_error_is_said_and_started_again",
    "M5714": f"{_T}::test_a_click_refused_is_answered_and_logged_whatever_the_name",
    "M5715": f"{_T}::test_a_click_refused_is_answered_even_when_its_log_fails",
    "M5716": f"{_T}::test_pending_shows_a_card_from_outside_as_it_is_and_the_next_one",
    "M5717": f"{_T}::test_pending_one_card_unreadable_never_hides_the_next",
    "M5718": f"{_T}::test_the_tui_feed_shows_a_line_from_outside_as_it_is",
    "M5719": f"{_T}::test_each_argument_of_the_bot_s_command_is_quoted_for_the_shell",
    "M5720": f"{_T}::test_the_command_s_block_is_never_closed_by_what_it_holds",
}
