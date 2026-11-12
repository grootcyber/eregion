"""IML1c (#752): the follow-ups of IML1b (decisions of Jonathan, 12/11) — `console-url` gives Imladris's
console while the workstation's tunnel holds 127.0.0.1:7007 (back on IML1b's exit 1), `imladris-url`
names the foreground tunnel as the fallback, the guard of the name sees a former command after an
option, a variable or in an argv, and `glorfindel restore` says the VM by its name and group, never the
subscription's id. M4870–M4879, measured by tests/unit/test_mobile.py, tests/unit/test_host_name.py and
tests/unit/test_entries_calls.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
MAKEFILE = "Makefile"
GUARD = "scripts/host_name.py"
CLI = "glorfindel/cli.py"
_MOB = "tests/unit/test_mobile.py"
_NAME = "tests/unit/test_host_name.py"
_CALLS = "tests/unit/test_entries_calls.py"

MUTANTS = [
    ("M4870", "console-url back to IML1b's exit 1 under the tunnel: no URL for the console the phone "
     "reaches (IML1c)", MAKEFILE,
     "\t   $(MAKE) --no-print-directory imladris-url; \\\n",
     "\t   exit 1; \\\n"),
    ("M4871", "console-url gives the local console's token for the port the tunnel holds: Imladris's console "
     "refuses it (IML1c)", MAKEFILE,
     "\t   $(MAKE) --no-print-directory imladris-url; \\\n",
     "\t   $(MAKE) --no-print-directory console-url-local; \\\n"),
    ("M4872", "console-url silent on whose console it gives: Imladris's URL, unsaid (IML1c)", MAKEFILE,
     "\t   echo \"  ℹ le tunnel d'Imladris tient 7007 : c'est sa console (make imladris-url)\" >&2; \\\n",
     "\t   true; \\\n"),
    ("M4873", "imladris-url names no fallback: on a workstation without a user systemd, only a tunnel it "
     "cannot arm (IML1c)", MAKEFILE,
     "puis make imladris-tunnel-on (ou make imladris-tunnel au premier plan)\" >&2; fi\n",
     "puis make imladris-tunnel-on\" >&2; fi\n"),
    ("M4874", "the guard blind to an argv: [\"make\", \"glorfindel-host-…\"] in a script never read (IML1c)",
     GUARD,
     '_GAP = r"""(?:\\s+|["\']\\s*,\\s*["\'])"""\n',
     '_GAP = r"""(?:\\s+)"""\n'),
    ("M4875", "the guard blind to an option's word: make -C . glorfindel-host-… never read (IML1c)", GUARD,
     '_OPTION = r"""-[^\\s"\',]+(?:""" + _GAP + r"""(?!-)[^\\s"\',=]+(?=""" + _GAP + r"""))?"""\n',
     '_OPTION = r"""-[^\\s"\',]+"""\n'),
    ("M4876", "the guard blind to a variable: make YES=1 glorfindel-host-up never read (IML1c)", GUARD,
     '_VARIABLE = r"""[A-Za-z_][A-Za-z0-9_]*=[^\\s"\',]*"""\n',
     '_VARIABLE = r"""(?!)"""\n'),
    ("M4877", "the guard takes any word between: « make help puis glorfindel-host-up » said a command "
     "(IML1c)", GUARD,
     '_VARIABLE = r"""[A-Za-z_][A-Za-z0-9_]*=[^\\s"\',]*"""\n',
     '_VARIABLE = r"""[^\\s"\',]+"""\n'),
    ("M4878", "glorfindel restore says the VM by its full id again: the subscription's id pasted with its "
     "output (IML1c)", CLI,
     '            return f"{name} (groupe {parts[i + 1]})"\n',
     '            return resource_id\n'),
    ("M4879", "the hint of a fire-and-forget restore gives the full id: the subscription's id on the "
     "terminal (IML1c)", CLI,
     "glorfindel jobs {_esc_markup(_short_name(resource_id))} --refresh",
     "glorfindel jobs {_esc_markup(resource_id)} --refresh"),
]
TESTS = {
    "M4870": f"{_MOB}::test_make_console_url_gives_imladris_s_url_when_the_tunnel_holds_the_port",
    "M4871": f"{_MOB}::test_make_console_url_gives_imladris_s_url_when_the_tunnel_holds_the_port",
    "M4872": f"{_MOB}::test_make_console_url_gives_imladris_s_url_when_the_tunnel_holds_the_port",
    "M4873": f"{_MOB}::test_make_imladris_url_gives_the_url_and_says_when_the_tunnel_is_not_armed",
    "M4874": f"{_NAME}::test_a_former_command_in_a_live_text_is_said",
    "M4875": f"{_NAME}::test_a_former_command_in_a_live_text_is_said",
    "M4876": f"{_NAME}::test_a_former_command_in_a_live_text_is_said",
    "M4877": f"{_NAME}::test_a_former_command_in_a_live_text_is_said",
    "M4878": f"{_CALLS}::test_a_vm_is_said_by_its_name_and_group "
             f"{_CALLS}::test_restore_says_the_vm_by_its_name_and_group_never_the_subscription",
    "M4879": f"{_CALLS}::test_restore_says_the_vm_by_its_name_and_group_never_the_subscription",
}
