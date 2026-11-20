"""FR1 (Ferme #1006): the fault rate declares « not measured », with its reason, a fault started in
a technique's exercise window on one of its targets, its grace included, or a wire of a Dagorlad
request — what Glorfindel decides then may answer the technique. M6900–M6909, measured by
tests/unit/test_fault_rate.py."""
FRATE = "analysis/fault_rate.py"
_T = "tests/unit/test_fault_rate.py"
_FILES = f"{_T}::test_the_rate_reads_the_techniques_window_from_this_hosts_files"

MUTANTS = [
    ("M6900", "a fault behind a technique on its VM, in its window, measured: the technique's cards "
     "counted against it, or the fault's hidden (FR1)", FRATE,
     "    for rid, targets, lo, hi, bounded in exercised or ():\n",
     "    for rid, targets, lo, hi, bounded in ():\n"),
    ("M6901", "a wire of a Dagorlad request measured as a fault played alone (FR1)", FRATE,
     '    if f.get("request"):\n'
     '        return f"{REQUESTED} ({str(f[\'request\'])[:40]})"\n',
     ""),
    ("M6902", "the technique's target compared with its case: the same VM, written otherwise, "
     "another (FR1)", FRATE,
     '    return str(rid or "").strip().rstrip("/").lower()\n',
     '    return str(rid or "").strip().rstrip("/")\n'),
    ("M6903", "the technique's window read without its grace: a fault 10 min after it closed "
     "measured (FR1)", FRATE,
     '    return {rid: (run_report.epoch(w.get("start")), w["last"],\n',
     '    return {rid: (run_report.epoch(w.get("start")), run_report.epoch(w.get("end")) or w["last"],\n'),
    ("M6904", "a technique's window not held here bounded without its grace (FR1)", FRATE,
     '            out.append((r["run_id"], targets, at, at + UNKNOWN_SPAN_S, False))\n',
     '            out.append((r["run_id"], targets, at, at + MAX_DURATION_S, False))\n'),
    ("M6905", "the reason a fault is not measured lost in the text (FR1)", FRATE,
     "        lines.append(f\"- non mesurée : `{u['run_id']}` ({u['fault'] or 'panne'}) — {u['why']}\")\n",
     "        lines.append(f\"- non mesurée : `{u['run_id']}` ({u['fault'] or 'panne'})\")\n"),
    ("M6906", "a technique's window narrower than BL1's [T0, T0 + grace] taken on its word (FR1)", FRATE,
     '            out.append((r["run_id"], targets, min(w[0], at), max(w[1], at + containment.HOLD_WATCH_S), True))\n',
     '            out.append((r["run_id"], targets, w[0], w[1], True))\n'),
    ("M6907", "the rate never reads the techniques' windows on this host: each bounded from its T0 "
     "alone (FR1)", FRATE,
     "                                         exercised=exercised))}\n",
     "                                         exercised=None))}\n"),
    ("M6908", "a technique started before the period left out: the period's first fault, in its "
     "window, measured (FR1)", FRATE,
     '                  and since - UNKNOWN_SPAN_S - containment.CLOCK_SKEW_S <= r["at"]]\n',
     '                  and since <= r["at"]]\n'),
    ("M6909", "a technique on a resource group's scope (a Stratus run) holds none of its VMs (FR1)", FRATE,
     '            if f and (f == t or f.rsplit("/", 1)[-1] == t.rsplit("/", 1)[-1] or f.startswith(t + "/")):\n',
     '            if f and (f == t or f.rsplit("/", 1)[-1] == t.rsplit("/", 1)[-1]):\n'),
]

TESTS = {
    "M6900": f"{_T}::test_a_fault_behind_a_technique_on_its_vm_in_its_window_is_not_measured",
    "M6901": f"{_T}::test_a_wire_of_a_dagorlad_request_is_not_measured",
    "M6902": f"{_T}::test_the_technique_target_is_compared_without_case",
    "M6903": _FILES,
    "M6904": f"{_T}::test_the_techniques_grace_is_part_of_its_window",
    "M6905": f"{_T}::test_the_render_says_why_a_fault_behind_a_technique_is_not_measured",
    "M6906": f"{_T}::test_a_technique_window_never_narrows_bl1s_bounds",
    "M6907": _FILES,
    "M6908": _FILES,
    "M6909": f"{_T}::test_the_technique_target_is_compared_without_case",
}
