"""RTT1a (#1174): the title of a cloud detection's card, declared by its rule — checked at load, written on
the card from the rule alone, the neutral one in its place, shown escaped (tests/unit/test_rule_title.py).
M7536–M7545."""
TITLE = "glorfindel/rule_title.py"
RULES = "glorfindel/detection_rules.py"
ESC = "glorfindel/escalations.py"
BOT = "glorfindel/bot.py"
CLI = "glorfindel/cli.py"
_TESTS = "tests/unit/test_rule_title.py"

MUTANTS = [
    ("M7536", "a title that is no string read as one (a number, a list): the load stops on it (RTT1a)", TITLE,
     "    if not isinstance(value, str):\n        return \"`title` n'est pas une chaîne\"\n",
     "    if not isinstance(value, (str, int, float, list, dict, type(None))):\n"
     "        return \"`title` n'est pas une chaîne\"\n"),
    ("M7537", "a title of spaces read: a card titled by nothing (RTT1a)", TITLE,
     "    if not value.strip():\n",
     "    if not value:\n"),
    ("M7538", "the title's bound lifted by one: 81 characters pass (RTT1a)", TITLE,
     "    if len(value) > MAX_LEN:\n",
     "    if len(value) > MAX_LEN + 1:\n"),
    ("M7539", "only the C0/C1 controls refused: a bidi override or a zero-width space pass into the title "
     "(RTT1a)", TITLE,
     'unicodedata.category(c)[0] == "C" or',
     'unicodedata.category(c) == "Cc" or'),
    ("M7540", "the client's layer loads a rule whose title cannot be read, in the place of the shipped one "
     "(RTT1a, P1)", RULES,
     "        why = rule_title.refusal(entry[rule_title.KEY])\n",
     '        why = ""\n'),
    ("M7541", "a card of any type carries a rule_title (RTT1a)", ESC,
     "    if escalation_type in rule_title.NEUTRAL:\n",
     "    if True:\n"),
    ("M7542", "rules unreadable when a cloud card is written: the card is lost for its title (RTT1a)", TITLE,
     "    except Exception:\n        return neutral\n",
     "    except ValueError:\n        return neutral\n"),
    ("M7543", "a rule_title the store holds shown unchecked: a forged line's text, on any length, on any "
     "lines (RTT1a)", TITLE,
     "    return parse(title) if not refusal(title) else neutral\n",
     "    return str(title) if title else neutral\n"),
    ("M7544", "Discord shows the rule's title as Markdown: a masked link, a mention (RTT1a, SEC6)", BOT,
     "    type_label = discord_text(card_title(esc)) or ",
     "    type_label = card_title(esc) or "),
    ("M7545", "the CLI shows the rule's title as Rich markup (RTT1a, SEC-F)", CLI,
     'table.add_row("Title", f"[bold]{_outside(title)}[/bold]")',
     'table.add_row("Title", f"[bold]{title}[/bold]")'),
]
TESTS = {m[0]: _TESTS for m in MUTANTS}
