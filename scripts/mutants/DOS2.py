"""DOS2 (#1042): the decision noted on the cycle's debug line — the model, its sampling, the settings, the
version of Glorfindel and the rule's fingerprint (glorfindel/cycle_line.py) — and never in the memory's
cycle, which feeds the model. M6977–M6979; and, from its review, M7068–M7070: the fingerprint read on
disk instead of the poller's own queries, a fallback removed (the settings, the version). Measured by
tests/unit/test_cycle_line.py."""
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
    ("M7068", "the fingerprint read on disk, not from the poller's own queries: after an approve or an "
     "edited client layer, the line names a query that never fired (DOS2)", LINE,
     "    if name and name in _POLLED:\n",
     "    if False:\n"),
    ("M7069", "the settings' fallback removed: settings that cannot be read cost the debug line (DOS2)", LINE,
     "    try:\n        out.update(settings())\n"
     "    except Exception as exc:              # the settings never cost the line\n"
     "        out.update(confidence_threshold=None, decision_draws_required=None,\n"
     "                   settings_unreadable=_first_line(exc))\n",
     "    out.update(settings())\n"),
    ("M7070", "the version's fallback removed: a version that cannot be read costs the debug line (DOS2)", LINE,
     "    try:\n        from eregion_core.version import version\n        v = version()\n"
     '        return {k: str(v.get(k) or "") for k in ("ref", "revision", "package")}\n'
     "    except Exception as exc:              # said, never the line lost\n"
     '        return {"ref": "", "revision": "", "package": "", "unreadable": _first_line(exc)}\n',
     "    from eregion_core.version import version\n    v = version()\n"
     '    return {k: str(v.get(k) or "") for k in ("ref", "revision", "package")}\n'),
]
TESTS = {
    "M6977": f"{_T}::test_the_model_called_is_on_the_line",
    "M6978": f"{_T}::test_the_version_of_glorfindel_that_decided",
    "M6979": f"{_T}::test_the_memory_s_cycle_is_unchanged_to_the_byte "
             f"{_T}::test_a_whole_cycle_keeps_the_new_fields_out_of_the_memory_and_the_signal",
    "M7068": f"{_T}::test_the_client_layer_changed_after_the_poller_started_keeps_the_query_that_fired",
    "M7069": f"{_T}::test_settings_that_cannot_be_read_never_cost_the_line",
    "M7070": f"{_T}::test_a_version_that_cannot_be_read_never_costs_the_line",
}
