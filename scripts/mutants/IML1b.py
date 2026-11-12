"""IML1b (#747): the commands of Imladris are all `make imladris-*` (decision of Jonathan, 12/11); the
former names, `glorfindel-host-*` and `mobile-*`, stay silent aliases until IML2 — the same recipe, its
guards included —, `console-url` gives the local console only, `imladris-url` says when the tunnel is not
armed, and a live text never cites a former command (scripts/host_name.py). M4840–M4849, measured by
tests/unit/test_host_name.py and tests/unit/test_mobile.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
MAKEFILE = "Makefile"
GUARD = "scripts/host_name.py"
_NAME = "tests/unit/test_host_name.py"
_MOB = "tests/unit/test_mobile.py"

MUTANTS = [
    ("M4840", "make mobile-check gone: the former name of imladris-tunnel-check has no rule (IML1b)", MAKEFILE,
     "mobile-check: imladris-tunnel-check ;\n",
     ""),
    ("M4841", "make mobile-tunnel-<x> gone: the tunnel's former names have no rule (IML1b)", MAKEFILE,
     "mobile-tunnel-%: imladris-tunnel-% ;\n",
     ""),
    ("M4842", "the alias no longer silent: a former name says it is one, its output no longer the new "
     "name's (IML1b)", MAKEFILE,
     "glorfindel-host-%: imladris-% ;\n",
     'glorfindel-host-%: imladris-%\n\t@echo "  (un ancien nom : make imladris-$*)"\n'),
    ("M4843", "the tunnel's guard handed the target's name, not its gesture: scripts/mobile.py refuses its "
     "arguments, the code session never told (IML1b)", MAKEFILE,
     "\t@$(PYTHON) scripts/mobile.py $(@:imladris-%=%) --guard-only\n",
     "\t@$(PYTHON) scripts/mobile.py $(@:mobile-%=%) --guard-only\n"),
    ("M4844", "a former command across a line's end never read: « make » at the end of a line, the "
     "former name on the next (IML1b)", GUARD,
     '_GAP = r"""(?:\\s+|["\']\\s*,\\s*["\'])"""\n',
     '_GAP = r"""(?:[ \\t]+|["\']\\s*,\\s*["\'])"""\n'),
    ("M4845", "the history read for the former commands: the CHANGELOG said, what each version shipped "
     "renamed (IML1b)", GUARD,
     '    return not any(rel.startswith(key) if key.endswith("/") else rel == key for key in OLD_NOT_READ)\n',
     "    return True\n"),
    ("M4846", "a text kept read anyway: a published release's line in ROADMAP.md, said by every session "
     "(IML1b)", GUARD,
     "        if _within(text, kept, m.start(), m.end()):\n            continue\n",
     "        if False:\n            continue\n"),
    ("M4847", "the CD left unread again: its messages in #deploy could say H0 (IML1b)", GUARD,
     '    "infra/glorfindel-host/deploy.sh": "deployed on the host: it runs there (IML2)",\n',
     '    "infra/glorfindel-host/cd/": "the CD (IML2)",\n'
     '    "infra/glorfindel-host/deploy.sh": "deployed on the host: it runs there (IML2)",\n'),
    ("M4848", "imladris-url silent on a tunnel not armed: the URL given, the phone's Safari finds nothing "
     "behind 127.0.0.1:7007 (IML1b)", MAKEFILE,
     '\t $(TUNNEL_ACTIVE) || if [ -f "$(MOBILE_UNIT)" ]; then \\\n',
     '\t true || if [ -f "$(MOBILE_UNIT)" ]; then \\\n'),
    ("M4849", "console-url blind to the tunnel: it gives the local console's token for the port the tunnel "
     "holds, Imladris's console behind it (IML1b)", MAKEFILE,
     '\t@if [ -f "$(MOBILE_UNIT)" ] && [ "$${EREGION_CONSOLE_PORT:-7007}" = 7007 ] && $(TUNNEL_ACTIVE); then \\\n',
     '\t@if false; then \\\n'),
]
TESTS = {
    "M4840": f"{_NAME}::test_make_imladris_is_make_glorfindel_host",
    "M4841": f"{_NAME}::test_make_imladris_is_make_glorfindel_host {_MOB}::test_make_refuses_in_an_agent_session_before_anything_runs",
    "M4842": f"{_NAME}::test_make_imladris_is_make_glorfindel_host",
    "M4843": f"{_MOB}::test_make_refuses_in_an_agent_session_before_anything_runs",
    "M4844": f"{_NAME}::test_a_former_command_in_a_live_text_is_said",
    "M4845": f"{_NAME}::test_a_former_command_is_read_but_in_the_history_and_the_kept_texts",
    "M4846": f"{_NAME}::test_a_former_command_is_read_but_in_the_history_and_the_kept_texts",
    "M4847": f"{_NAME}::test_the_history_is_the_one_exception_for_the_name",
    "M4848": f"{_MOB}::test_make_imladris_url_gives_the_url_and_says_when_the_tunnel_is_not_armed",
    "M4849": f"{_MOB}::test_make_console_url_names_imladris_url_when_the_tunnel_holds_the_port",
}
