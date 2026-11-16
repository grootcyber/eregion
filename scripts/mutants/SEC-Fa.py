"""SEC-Fa (#852): what Annatar prints from the outside is said as it is, and no print fails a run —
one console that never raises on markup, `outside()` escaping the markup and showing the controls,
on each path that prints what a target, the cloud, the channel or a file said. M5630–M5649, measured
by tests/unit/test_annatar_console.py."""
CON = "annatar/console.py"
VM = "annatar/executors/azure_vm.py"
STRATUS = "annatar/executors/stratus_host.py"
ENGINE = "annatar/runner/engine.py"
REPORT = "annatar/runner/report.py"
PARSER = "annatar/runner/parser.py"
CLI = "annatar/cli.py"
_T = "tests/unit/test_annatar_console.py"

MUTANTS = [
    ("M5630", "outside() escapes no markup: a closing tag a VM sends is read as markup again (SEC-Fa)",
     CON,
     "    return escape(text)\n",
     "    return text\n"),
    ("M5631", "outside() shows no control: a VM's escape sequence reaches the operator's terminal, "
     "obeyed (SEC-Fa)", CON,
     '    text = _CONTROL.sub(lambda m: f"\\\\x{ord(m.group()):02x}", text)\n',
     ""),
    ("M5632", "outside() shows the C0 controls only: a one-byte CSI (0x9b) is obeyed (SEC-Fa)", CON,
     '_CONTROL = re.compile(r"[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f-\\x9f]")\n',
     '_CONTROL = re.compile(r"[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]")\n'),
    ("M5633", "the console raises on markup again: a closing tag in any value printed kills the run "
     "(SEC-Fa, the defect back)", CON,
     '            return super().render_str(text, **{**kwargs, "markup": False})\n',
     "            raise\n"),
    ("M5634", "the console reads emoji codes: `:x:` in a value said as an emoji (SEC-Fa)", CON,
     "console = AnnatarConsole(emoji=False)\n",
     "console = AnnatarConsole()\n"),
    ("M5635", "Run Command's output printed as markup (SEC-Fa, the defect the audit measured)", VM,
     '                console.print(f"  [dim]{outside(output.strip()[-200:])}[/dim]")   # what the VM answered\n',
     '                console.print(f"  [dim]{output.strip()[-200:]}[/dim]")\n'),
    ("M5636", "a failed integrity check prints the VM's output as markup (SEC-Fa)", VM,
     '            console.print(f"  [dim]{outside(output.strip())}[/dim]")\n',
     '            console.print(f"  [dim]{output.strip()}[/dim]")\n'),
    ("M5637", "Stratus's output printed as markup (SEC-Fa)", STRATUS,
     '        console.print(f"  [dim]{outside(out.strip()[-200:])}[/dim]")   # what Stratus answered\n',
     '        console.print(f"  [dim]{out.strip()[-200:]}[/dim]")\n'),
    ("M5638", "a Stratus phase's error printed raw: its own print raises over it (SEC-Fa, the defect "
     "back)", ENGINE,
     '            console.print(f"[red]Stratus phase failed:[/red] {type(e).__name__}: {outside(e)}")\n',
     '            console.print(f"[red]Stratus phase failed:[/red] {type(e).__name__}: {e}")\n'),
    ("M5639", "an atomic command's error printed raw (SEC-Fa)", ENGINE,
     '            console.print(f"[red]Atomic command failed:[/red] {type(e).__name__}: {outside(e)}")\n',
     '            console.print(f"[red]Atomic command failed:[/red] {type(e).__name__}: {e}")\n'),
    ("M5640", "a module prints through a console of its own, which raises on markup (SEC-Fa)", VM,
     "from annatar.console import console, outside\n",
     "from rich.console import Console\n\nfrom annatar.console import outside\n\nconsole = Console()\n"),
    ("M5641", "a step's action between the code's brackets read as a tag: it vanishes from the dry "
     "run (SEC-Fa)", ENGINE,
     "                console.print(f\"  {i}. \\\\[{outside(step.get('action'))}] {outside(step.get('name', ''))}\")\n",
     "                console.print(f\"  {i}. [{outside(step.get('action'))}] {outside(step.get('name', ''))}\")\n"),
    ("M5642", "a campaign's state between the code's brackets read as a tag: it vanishes from the "
     "list (SEC-Fa)", CLI,
     '            f"{outside(m.campaign_id)}  \\\\[{outside(m.state)}]  {len(m.scenarios)} scenario(s)  "\n',
     '            f"{outside(m.campaign_id)}  [{outside(m.state)}]  {len(m.scenarios)} scenario(s)  "\n'),
    ("M5643", "a run's report prints its detection, as its file holds it, as markup (SEC-Fa)", REPORT,
     "            console.print(f\"[bold]Detection:[/bold] {outside(self.metrics['detection'])}{after}\")\n",
     "            console.print(f\"[bold]Detection:[/bold] {self.metrics['detection']}{after}\")\n"),
    ("M5644", "a scenario listed is written into the table's cells as markup (SEC-Fa)", PARSER,
     '            table.add_row(outside(s.name), outside(s.mitre), outside(s.target.get("type", "?")), outside(rel))\n',
     '            table.add_row(s.name, s.mitre, s.target.get("type", "?"), rel)\n'),
    ("M5645", "the CLI's boundary prints an operational failure raw (SEC-Fa)", CLI,
     '            console.print(f"[red]✗ {type(e).__name__}: {outside(e)}[/red]")\n',
     '            console.print(f"[red]✗ {type(e).__name__}: {e}[/red]")\n'),
    ("M5646", "a detection the channel refuses printed without markup only: its escape sequence is "
     "obeyed (SEC-Fa)", ENGINE,
     '            console.print(f"A detection on the return channel refused — never counted (SEC21): {outside(why)}",\n'
     '                          style="yellow")\n',
     '            console.print(f"A detection on the return channel refused — never counted (SEC21): {why}",\n'
     '                          markup=False, style="yellow")\n'),
    ("M5647", "a preflight issue, which quotes what the cloud said, printed raw (SEC-Fa)", ENGINE,
     '                    console.print(f"[red]✗[/red] {outside(issue)}")\n',
     '                    console.print(f"[red]✗[/red] {issue}")\n'),
    ("M5648", "the inscription's refusal, which quotes a tag of the cloud, printed raw (SEC-Fa)", ENGINE,
     '            console.print(f"[red]Safety check failed:[/red] {outside(guard.reason)}")\n',
     '            console.print(f"[red]Safety check failed:[/red] {guard.reason}")\n'),
    ("M5649", "a run's report prints what the channel refused without markup only: its escape "
     "sequence is obeyed (SEC-Fa)", REPORT,
     '                console.print("  - " + outside(str(why)[:400]), style="yellow")\n',
     '                console.print("  - " + str(why)[:400], markup=False, style="yellow")\n'),
]

TESTS = {
    "M5630": f"{_T}::test_outside_says_the_tags_and_shows_the_controls",
    "M5631": f"{_T}::test_outside_says_the_tags_and_shows_the_controls",
    "M5632": f"{_T}::test_outside_says_the_tags_and_shows_the_controls",
    "M5633": f"{_T}::test_the_console_never_fails_a_run_on_markup",
    "M5634": f"{_T}::test_the_console_never_fails_a_run_on_markup",
    "M5635": f"{_T}::test_what_a_vm_answers_is_said_as_it_is",
    "M5636": f"{_T}::test_a_failed_integrity_check_says_the_vm_s_output_as_it_is",
    "M5637": f"{_T}::test_what_stratus_answers_is_said_as_it_is",
    "M5638": f"{_T}::test_a_phase_that_fails_on_the_outside_s_words_fails_as_itself "
             f"{_T}::test_no_exception_is_printed_without_outside",
    "M5639": f"{_T}::test_no_exception_is_printed_without_outside",
    "M5640": f"{_T}::test_annatar_prints_through_its_one_console "
             f"{_T}::test_what_a_vm_answers_is_said_as_it_is",
    "M5641": f"{_T}::test_a_step_s_action_is_shown_between_its_brackets "
             f"{_T}::test_no_bracket_of_the_code_holds_a_raw_value",
    "M5642": f"{_T}::test_a_campaign_s_state_is_shown_between_its_brackets "
             f"{_T}::test_no_bracket_of_the_code_holds_a_raw_value",
    "M5643": f"{_T}::test_a_run_s_report_says_what_its_file_holds_as_it_is",
    "M5644": f"{_T}::test_a_scenario_listed_is_said_as_it_is",
    "M5645": f"{_T}::test_an_operational_failure_is_said_as_it_is "
             f"{_T}::test_no_exception_is_printed_without_outside",
    "M5646": f"{_T}::test_a_detection_the_channel_refuses_is_said_as_it_is",
    "M5647": f"{_T}::test_a_preflight_issue_is_said_as_it_is",
    "M5648": f"{_T}::test_a_refusal_quoting_a_tag_of_the_cloud_says_it_as_it_is",
    "M5649": f"{_T}::test_a_run_s_report_says_what_its_file_holds_as_it_is",
}

# The console's fallback (M5633) makes these two of #358 blind to their test's holder (`[/x]`, an
# unreadable string, said as it is all the same): valid markup tells them apart.
TESTS_ALSO = {
    "M2494": f"{_T}::test_a_refusal_busy_says_the_holder_as_it_is",
    "M2495": f"{_T}::test_a_refusal_busy_says_the_holder_as_it_is",
}
