"""ROT2 (#968): the console token of Imladris turned in one command — its line alone rewritten, 0600 and
atomic, checked as the push checks it, never printed nor on a command line, refused in a code session;
pushed, the console alone restarted, the old token refused; the day to turn it again noted on Imladris
and reminded by its CD in #deploy. M6656–M6670, measured by tests/unit/test_console_rotate.py."""
ROTATE = "scripts/console_rotate.py"
CD = "infra/glorfindel-host/cd/eregion_cd.py"
_T = "tests/unit/test_console_rotate.py"
_MAIN = f"{_T}::test_a_rotation_changes_the_token_s_line_alone_restarts_the_console_alone_and_refuses_the_old_one"

MUTANTS = [
    ("M6656", "another line of host.env rewritten: each line written back trimmed — a CRLF, a trailing blank, "
     "the last line without its break, changed (ROT2)", ROTATE,
     "            out.append(ln)\n    return \"\".join(out)\n",
     "            out.append(ln.rstrip() + \"\\n\")\n    return \"\".join(out)\n"),
    ("M6657", "the comments and the blank lines of host.env dropped with the token's line (ROT2)", ROTATE,
     "        elif _key(ln) not in names:\n",
     "        elif _key(ln) and _key(ln) not in names:\n"),
    ("M6658", "a line of the other name kept beside the new token: a token no longer in use left in host.env "
     "and pushed to Imladris (ROT2)", ROTATE,
     "        elif _key(ln) not in names:\n",
     "        elif _key(ln) != name:\n"),
    ("M6659", "the new token printed on the screen (ROT2)", ROTATE,
     "    say(f\"✓ {HOST_ENV} : un nouveau jeton de la console{renamed}, 0600",
     "    say(f\"✓ {HOST_ENV} : un nouveau jeton de la console {new}{renamed}, 0600"),
    ("M6660", "the tokens on ssh's command line for the probe, seen by `ps` here and on Imladris (ROT2)", ROTATE,
     "    res = _run([*shlex.split(ctx.ssh), PROBE], ctx, stdin=f\"{new}\\n{old}\\n\", timeout=120)\n",
     "    res = _run([*shlex.split(ctx.ssh), f\"printf '%s\\\\n' {new} {old} | {{ {PROBE}; }}\"], ctx, timeout=120)\n"),
    ("M6661", "host.env written readable by all: its mode 0600 lost (ROT2)", ROTATE,
     "            os.fchmod(fd, 0o600)\n",
     "            os.fchmod(fd, 0o644)\n"),
    ("M6662", "the refusal of a code session gone: an agent turns the console's token (ROT2)", ROTATE,
     "    why = bs.session_refusal(ctx.env, ctx.cwd, ctx.here, never=NEVER)\n",
     "    why = \"\"\n"),
    ("M6663", "the day to turn it again never noted on Imladris: no reminder ever leaves (ROT2)", ROTATE,
     "    noted, said = note_on_imladris(end, ctx, ROTATE)\n",
     "    noted, said = True, []\n"),
    ("M6664", "the console never restarted: it keeps the old token, the new one refused (ROT2)", ROTATE,
     "    ok, why = restart(ctx)\n",
     "    ok, why = True, \"\"\n"),
    ("M6665", "the probe not heeded: a console still on the old token taken for a rotation, and noted (ROT2)",
     ROTATE,
     "    if got_new != \"200\" or got_old != \"401\":\n",
     "    if not got_new:\n"),
    ("M6666", "host.env not checked before it replaces the old one: a file the push refuses written (ROT2)", ROTATE,
     "        if why := _checked(tmp, path):\n",
     "        if why := \"\":\n"),
    ("M6667", "the temporary file left behind on a refusal or a Ctrl-C: a token lying beside host.env (ROT2)",
     ROTATE,
     "        tmp.unlink(missing_ok=True)\n        raise\n",
     "        raise\n"),
    ("M6668", "host.env written in place instead of renamed over: a write cut short leaves it half written, "
     "its mode kept (ROT2)", ROTATE,
     "        os.replace(tmp, path)\n",
     "        path.write_text(text, encoding=\"utf-8\")\n        tmp.unlink()\n"),
    ("M6669", "the CD reads the three pairs only: the console token's day noted, never reminded (ROT2)", CD,
     "REMIND_PAIRS = (\"watch\", \"console\", \"bot\", CONSOLE_TOKEN)\n",
     "REMIND_PAIRS = (\"watch\", \"console\", \"bot\")\n"),
    ("M6670", "the console token reminded as a pair: `make pair-rotate PAIR=console-token`, a command that does "
     "not exist (ROT2)", CD,
     "    if pair == CONSOLE_TOKEN:\n        return token_card(end, days_left)\n",
     ""),
]
TESTS = {
    "M6656": _MAIN,
    "M6657": _MAIN,
    "M6658": f"{_T}::test_the_token_under_its_new_name_beside_the_former_takes_the_new_and_the_former_goes",
    "M6659": _MAIN,
    "M6660": _MAIN,
    "M6661": f"{_T}::test_host_env_is_written_0600_whatever_it_was",
    "M6662": f"{_T}::test_refused_in_a_code_session_before_anything",
    "M6663": _MAIN,
    "M6664": _MAIN,
    "M6665": f"{_T}::test_a_console_still_on_the_old_token_is_said_and_nothing_noted",
    "M6666": f"{_T}::test_a_host_env_the_push_would_refuse_is_never_written",
    "M6667": f"{_T}::test_a_host_env_the_push_would_refuse_is_never_written",
    "M6668": f"{_T}::test_a_write_cut_short_leaves_host_env_as_it_was_and_no_temporary_file",
    "M6669": f"{_T}::test_the_token_s_reminders_leave_at_j14_j7_j1_and_on_the_day_once_each",
    "M6670": f"{_T}::test_the_token_s_reminders_leave_at_j14_j7_j1_and_on_the_day_once_each",
}
