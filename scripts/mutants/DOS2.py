"""DOS2 (#1042): the decision noted on the cycle's debug line — the model, its sampling, the settings, the
version of Glorfindel and the rule's fingerprint (glorfindel/cycle_line.py) — and never in the memory's
cycle, which feeds the model. M6977–M6979, measured by tests/unit/test_cycle_line.py."""
LINE = "glorfindel/cycle_line.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_cycle_line.py"

MUTANTS = [
    ("M6977", "the model absent from the debug line: nobody can say which model decided (DOS2)", LINE,
     '        out["decision_model"] = str(state["decision_model"])\n',
     ""),
    ("M6978", "the version absent from the debug line: nobody can say which Glorfindel decided (DOS2)", LINE,
     '    out["glorfindel_version"] = glorfindel_version()\n',
     ""),
    ("M6979", "a field of the line leaks into the memory's cycle: it reaches the model by past_cycles (DOS2)",
     AGENT,
     '        "corroborated": False,\n    }\n',
     '        "corroborated": False,\n        "decision_model": state.get("decision_model", ""),\n    }\n'),
]
TESTS = {
    "M6977": f"{_T}::test_the_model_called_is_on_the_line",
    "M6978": f"{_T}::test_the_version_of_glorfindel_that_decided",
    "M6979": f"{_T}::test_the_memory_s_cycle_is_unchanged_to_the_byte "
             f"{_T}::test_a_whole_cycle_keeps_the_new_fields_out_of_the_memory_and_the_signal",
}
