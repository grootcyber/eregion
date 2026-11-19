"""SEC-Ib (#910, V-09): the readiness audit reads a VM by its resource id, never by its host name.
The Perf and Syslog checks of ``glorfindel audit`` filtered ``_ResourceId =~ <id> or Computer =~
<name>``: a host of the workspace named like the VM made a VM whose telemetry is absent look
present — a blind VM passed for ready. A VM whose lines carry no resource id (SEC-I's hypothesis
SI5) is absent, its lines under the host name counted and said, never taken for the VM's. Each
mutant brings the host name back on one check (whole, or for the lines without an id), takes the
unattributed lines for presence or for an unknown, hides them, counts a namesake under another id,
reads them in the wrong table, or lets their unreadable count break the check. M6301–M6310,
measured by tests/unit/test_audit.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
AUD = "glorfindel/audit.py"

_T = "tests/unit/test_audit.py"

MUTANTS = [
    # ── The host name back in the check's own query ──
    ("M6301", "the Perf check finds the VM by its host name again: a namesake makes it present (SEC-Ib)", AUD,
     '        _PERF_ROWS\n        + f" | where _ResourceId =~ {scope[0]}"',
     '        _PERF_ROWS\n        + f" | where _ResourceId =~ {scope[0]} or Computer =~ {scope[1]}"'),
    ("M6302", "the Syslog check finds the VM by its host name again: a namesake makes it present (SEC-Ib)", AUD,
     '        _SYSLOG_ROWS\n        + f" | where _ResourceId =~ {scope[0]}"',
     '        _SYSLOG_ROWS\n        + f" | where _ResourceId =~ {scope[0]} or Computer =~ {scope[1]}"'),
    ("M6303", "the Perf check takes the lines without a resource id under its host name for the VM's (SEC-Ib)",
     AUD,
     '        _PERF_ROWS\n        + f" | where _ResourceId =~ {scope[0]}"',
     '        _PERF_ROWS\n        + f" | where _ResourceId =~ {scope[0]} or isempty(_ResourceId) and Computer =~ {scope[1]}"'),
    ("M6304", "the Syslog check takes the lines without a resource id under its host name for the VM's (SEC-Ib)",
     AUD,
     '        _SYSLOG_ROWS\n        + f" | where _ResourceId =~ {scope[0]}"',
     '        _SYSLOG_ROWS\n        + f" | where _ResourceId =~ {scope[0]} or isempty(_ResourceId) and Computer =~ {scope[1]}"'),
    # ── The label of a VM whose lines carry no resource id ──
    ("M6305", "lines without a resource id make the VM « unreadable », not absent: its rules unknown, not blind"
     " (SEC-Ib)", AUD,
     '    if unattributed:\n        data["unattributed"] = unattributed\n',
     '    if unattributed:\n        data["present"] = None\n        data["unattributed"] = unattributed\n'),
    ("M6306", "lines without a resource id make the check ok: a blind VM passes for ready (SEC-Ib)", AUD,
     '    return AuditCheck("detection", name, "warn", message, fix, data=data)',
     '    return AuditCheck("detection", name, "ok" if unattributed else "warn", message, fix, data=data)'),
    ("M6307", "the lines without a resource id are never said: the operator only looks at the DCR (SEC-Ib)", AUD,
     '    if unattributed:\n        data["unattributed"] = unattributed\n',
     '    if False:\n        data["unattributed"] = unattributed\n'),
    # ── The count of the unattributed lines ──
    ("M6308", "a namesake under another resource id is counted as the VM's unattributed lines (SEC-Ib)", AUD,
     '{rows} | where isempty(_ResourceId) and Computer =~ {name}',
     '{rows} | where Computer =~ {name}'),
    ("M6309", "the Perf check counts its unattributed lines in Syslog (SEC-Ib)", AUD,
     '_unattributed(detector, _PERF_ROWS, scope[1])', '_unattributed(detector, _SYSLOG_ROWS, scope[1])'),
    ("M6310", "an unreadable count of the unattributed lines breaks the check instead of leaving it absent"
     " (SEC-Ib)", AUD,
     '        return int((out[0].get("n") if out else 0) or 0)\n    except Exception:\n        return 0\n',
     '        return int((out[0].get("n") if out else 0) or 0)\n    except Exception:\n        raise\n'),
]

TESTS = {mid: _T for mid, *_ in MUTANTS}
