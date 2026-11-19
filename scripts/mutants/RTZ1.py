"""RTZ1 (#923): on the restore path, a time without its time zone is refused, never taken for UTC —
a moment given (--before, the TUI, the console, the bot), a card's first detection, the VM's isolation,
the provider last. M6556–M6570: the naive time taken for UTC at each point, a zero offset written wrong
let through, a time with its zone refused, the message lost. After the review, M6621–M6623."""
PLAN = "glorfindel/restore_plan.py"
GCLI = "glorfindel/cli.py"
TUI = "glorfindel/tui.py"
BOT = "glorfindel/bot.py"
CON = "eregion_console/api.py"
RST = "glorfindel/providers/azure/restore.py"
_T = ("tests/unit/test_restore_time_zone.py tests/unit/test_restore_moment.py "
      "tests/unit/test_entries_calls.py")

MUTANTS = [
    ("M6556", "a moment without its zone taken for UTC: the point restored chosen on a guess (RTZ1)", PLAN,
     '            raise NoTimeZone(f"{text[:60]!r} : {NO_ZONE}")\n',
     "            dt = dt.replace(tzinfo=timezone.utc)\n"),
    ("M6557", "the refusal of a time without its zone no longer asks for one, nor gives the example (RTZ1)", PLAN,
     'NO_ZONE = ("heure sans fuseau, jamais devinée — donner un instant ISO 8601 avec fuseau "\n'
     '           "(ex. 2026-11-19T14:05:00Z)")\n',
     'NO_ZONE = "pas un instant ISO 8601"\n'),
    ("M6558", "a time at a zero offset (Z, +00:00) refused as if it had no zone (RTZ1)", PLAN,
     "        if dt.tzinfo is None:\n            raise NoTimeZone(",
     "        if not dt.utcoffset():\n            raise NoTimeZone("),
    ("M6559", "a zero offset written wrong (« UTC », « GMT », a lower-case z) taken for UTC (RTZ1)", PLAN,
     '        dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))\n        if dt.tzinfo is None:\n',
     '        dt = datetime.fromisoformat(__import__("re").sub(r"\\s*(?:UTC|GMT|z)$", "+00:00", text.strip())'
     '.replace("Z", "+00:00"))\n        if dt.tzinfo is None:\n'),
    ("M6560", "`glorfindel restore --before` without its zone taken for UTC (RTZ1)", GCLI,
     '            return restore_plan.parse_moment(before), "--before"\n',
     '            return restore_plan.parse_moment(before + ("+00:00" if restore_plan.zone_missing(before) else "")), '
     '"--before"\n'),
    ("M6561", "the TUI takes a moment without its zone for UTC (RTZ1)", TUI,
     '                pending["before"] = restore_plan.parse_moment(pending["buffer"])\n',
     '                pending["before"] = restore_plan.parse_moment(pending["buffer"] + ("+00:00" if '
     'restore_plan.zone_missing(pending["buffer"]) else ""))\n'),
    ("M6562", "the console restores before a moment without its zone, taken for UTC (RTZ1)", CON,
     '        before = restore_plan.parse_moment(body.get("before"))\n',
     '        before = restore_plan.parse_moment(str(body.get("before")) + ("+00:00" if '
     'restore_plan.zone_missing(body.get("before")) else ""))\n'),
    ("M6563", "the bot's form takes a moment without its zone for UTC (RTZ1)", BOT,
     "            before = restore_plan.parse_moment(self.moment.value)\n",
     '            before = restore_plan.parse_moment(self.moment.value + ("+00:00" if '
     'restore_plan.zone_missing(self.moment.value) else ""))\n'),
    ("M6564", "a card's time without its zone guessed as UTC: `glorfindel pending` copies a guessed --before (RTZ1)",
     PLAN,
     '        return "", _unzoned_card_why(esc, text)\n',
     '        return parse_moment(text + "+00:00"), ""\n'),
    ("M6565", "a card's first detection without its zone read as UTC: the incident dated on a guess (RTZ1)", PLAN,
     '        return float("-inf")\n',
     '        return datetime.fromisoformat(str(esc.get("first_seen") or esc.get("timestamp")) + "+00:00").timestamp()\n'),
    ("M6566", "the restore's field filled with a card's time without its zone, taken for UTC (RTZ1)", PLAN,
     "    except NoTimeZone:   # RTZ1: what the card carries, said; no moment proposed\n"
     '        return {"before": "", "source": "", "no_zone": first[:60],\n'
     '                "why": _unzoned_card_why(esc, first)}\n',
     "    except NoTimeZone:   # RTZ1: what the card carries, said; no moment proposed\n"
     '        before = parse_moment(first + "+00:00")\n'),
    ("M6567", "an isolation without its zone passed over: the card's moment proposed, unbounded by it (RTZ1)", PLAN,
     "    if loose:            # RTZ1: the earliest safe moment can't be told — asked, never guessed\n",
     "    if False:\n"),
    ("M6568", "the isolation's time without its zone read as the host's local time (RTZ1)", PLAN,
     '    if zone_missing(text):\n        return None, ""\n',
     ""),
    ("M6569", "the provider restores before a moment without its zone, taken for UTC (RTZ1)", RST,
     "        if attack_dt.tzinfo is None:\n            raise RuntimeError(\n",
     "        if attack_dt.tzinfo is None:\n            attack_dt = attack_dt.replace(tzinfo=timezone.utc)\n"
     "        if False:\n            raise RuntimeError(\n"),
    ("M6570", "`glorfindel pending` no longer says why a card's restore names no moment (RTZ1)", GCLI,
     '    return [] if moment else [f"--before: {why}"]\n',
     "    return []\n"),
]
# After the review (#956): M6621–M6623 — an earlier card without zone beside the one clicked, the
# console's copied command, the recovery watch's step.
JSP = "eregion_console/static/glorfindel.js"
REC = "glorfindel/recovery_watch.py"
MUTANTS += [
    ("M6621", "an earlier pending card of the VM without its zone passed over: the console, the bot and the "
     "TUI propose the clicked card's moment, or the isolation's (RTZ1 review)", PLAN,
     '    if earliest is not None and _first_seen(earliest) == float("-inf"):\n',
     "    if False:\n"),
    ("M6622", "the console's 📋 Cmd copies a card's time without its zone (RTZ1 review)", JSP,
     "  return _ZONED_TIME.test(text) ? text : otherwise;\n",
     "  return text || otherwise;\n"),
    ("M6623", "the recovery watch's step writes `--before ?` when the incident's start is unknown (RTZ1 review)",
     REC,
     'tz=timezone.utc).isoformat() if first is not None else "<ISO8601>")\n',
     'tz=timezone.utc).isoformat() if first is not None else "?")\n'),
]
TESTS = {f"M{n}": _T for n in range(6556, 6571)}
TESTS.update({"M6621": _T, "M6622": _T, "M6623": "tests/unit/test_recovery_watch.py"})
