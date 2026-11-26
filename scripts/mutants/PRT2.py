"""PRT2 (#1160): the watch's breaker in dollars — two envelopes, three buckets, the criticality in the config
(glorfindel/model_budget.py; the reading and the class of `critical`, glorfindel/config.py and
glorfindel/config_class.py; the code's path and the draws' context, glorfindel/agent.py). M7413–M7432, measured
by tests/unit/test_model_budget.py, tests/unit/test_config.py and tests/unit/test_config_edit.py. PRT1's
(scripts/mutants/PRT1.py) still hold: the gate's bounds are behind the breaker, unchanged."""
MB = "glorfindel/model_budget.py"
CFG = "glorfindel/config_assets.py"     # PRI2a: the strict reading of both formats moved there
CLS = "glorfindel/config_class.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_model_budget.py"

MUTANTS = [
    ("M7413", "no reserve for the graves: the ordinaries spend the whole real, a grave goes the code's path "
     "(PRT2)", MB,
     "        return min(self.real_usd, RESERVE_MAX_USD, GRAVE_FLOOR_USD + self._critical_count * CRITICAL_USD)\n",
     "        return 0.0\n"),
    ("M7414", "a grave on a critical object held by the others' bucket: a burst of graves elsewhere leaves it "
     "nothing (PRT2)", MB,
     '        if grave and critical:\n            return ("real", "real/critical")\n',
     '        if False:\n            return ("real", "real/critical")\n'),
    ("M7415", "an exercise believed in zone production: a real attack there paused with the exercises (PRT2)", MB,
     "        if zone not in _ZONES:\n",
     "        if not zone:\n"),
    ("M7416", "the exercises charged to the real: a campaign exhausts the real's budget (PRT2)", MB,
     "            return (\"exercise\", f\"exercise/run/{campaign or '?'}\")\n",
     "            return (\"real\", f\"exercise/run/{campaign or '?'}\")\n"),
    ("M7417", "the real exhausted, a grave becomes a card: no snapshot, nothing done by the code (PRT2)", MB,
     '        if grave:\n            said = f"budget du modèle épuisé, {why}"\n',
     '        if False:\n            said = f"budget du modèle épuisé, {why}"\n'),
    ("M7418", "an unknown cost counted 0: a model LiteLLM cannot price is free, the breaker never trips (PRT2)",
     MB, "            charged = self.unknown_usd if cost is None else cost\n",
     "            charged = 0.0 if cost is None else cost\n"),
    ("M7419", "a call refused by the provider's limit charged as unknown: a burst of 429 spends the day (PRT2)",
     MB, "            cost = 0.0 if limited else (",
     "            cost = None if limited else ("),
    ("M7420", "the share of a decision admitted never passes: its draws refused halfway past the count (PRT2)",
     MB, "            elif decision.share > 0:\n",
     "            elif False:\n"),
    ("M7421", "the shares in flight not counted at the admission: decisions admitted together pass the budget "
     "(PRT2)", MB,
     "        return sum((d.share + d.calls) * self.unknown_usd for d in self._flight if key in d.keys)\n",
     "        return 0.0\n"),
    ("M7422", "no check before a call beyond its share: the budget passed without bound (PRT2)", MB,
     "                hit = self._refusal(decision.keys, 1)\n",
     "                hit = None\n"),
    ("M7423", "the code's path makes its call all the same: the provider's limit called again (PRT2)", MB,
     "            if decision.refused:\n                why = decision.refused\n",
     "            if False:\n                why = decision.refused\n"),
    ("M7424", "the count lost at the restart: a watch restarted spends its budget again (PRT2)", MB,
     "        self._state = self._load()\n",
     "        self._state = self._fresh()\n"),
    ("M7425", "no reset at midnight UTC: a watch that runs across it stays exhausted (PRT2)", MB,
     '        if self._state.get("day") != self._today():\n            self._state = self._fresh()\n',
     '        if False:\n            self._state = self._fresh()\n'),
    ("M7426", "the alert said at every refusal, not once a day for its breaker (PRT2)", MB,
     '        if key in self._state["tripped"]:\n            return []\n',
     '        if False:\n            return []\n'),
    ("M7427", "critical read loosely: « \"true\" », 1 are taken for true — the strict reading lost (PRT2)", CFG,
     '        critical = check.flag(a, "critical", where, False)\n',
     '        critical = bool(a.get("critical"))\n'),
    ("M7428", "critical never classed: taking it away is not a relaxation (PRT2; PRI2a: the class by level)", CLS,
     "    _priority(b, a, said)\n", ""),
    ("M7429", "the draws out of their decision's context: counted on no VM, beyond the decision's share (PRT2)",
     AGENT,
     "        results = list(pool.map(lambda c: c.run(one, 0), [contextvars.copy_context() for _ in range(n)]))\n",
     "        results = list(pool.map(one, range(n)))\n"),
    ("M7430", "the provider's limit a failed cycle again: a 429 ends as cycle_failed, no snapshot (PRT2)", AGENT,
     "        if model_budget.refused(exc):\n",
     "        if isinstance(exc, model_budget.Refused):\n"),
    ("M7431", "a grave on a critical object waits the provider's cool-down (PRT2)", MB,
     "        if critical or self._strikes >= 2:\n",
     "        if self._strikes >= 2:\n"),
    ("M7432", "no part per VM: one noisy VM's ordinaries spend the others' (PRT2)", MB,
     '        return ("real", "real/noncritical", "real/rest", f"real/vm/{vm}")\n',
     '        return ("real", "real/noncritical", "real/rest")\n'),
    # The review of PRT2, and the maintainer's decision of 24/11 on the reserve (M7473–M7480).
    ("M7473", "no floor for the graves: without a critical VM the ordinaries take the graves' last dollar (PRT2, "
     "decision of 24/11)", MB,
     "        return min(self.real_usd, RESERVE_MAX_USD, GRAVE_FLOOR_USD + self._critical_count * CRITICAL_USD)\n",
     "        return min(self.real_usd, RESERVE_MAX_USD, self._critical_count * CRITICAL_USD)\n"),
    ("M7474", "a 429 the code's path without the watch's guard: the harness counts a snapshot as a valid "
     "decision (PRT2 review)", MB,
     "    return isinstance(exc, Refused) or (llm_call._GUARD is not None and provider_limited(exc))\n",
     "    return isinstance(exc, Refused) or provider_limited(exc)\n"),
    ("M7475", "the release on the code's path without its precondition: a replay or an origin not vouched for "
     "never said (PRT2 review)", MB,
     "        agent._apply_release_precondition(d, signal)        # its warnings on the card\n", ""),
    ("M7476", "the code's snapshot without the attribution's guard: run alone on a VM the detection does not "
     "name (PRT2 review)", MB,
     "    agent._apply_attribution_guard(d, signal)\n    mode_hold = agent._apply_autonomy_mode(d, mode, gate)\n",
     "    mode_hold = agent._apply_autonomy_mode(d, mode, gate)\n"),
    ("M7477", "B3a's floor not played on the code's path: the isolation never proposed where root was taken "
     "(PRT2 review)", MB,
     '    floor = "" if release or ordinary else agent._root_compromise_floor(d, signal, state.get("incident"))\n',
     '    floor = ""\n'),
    ("M7478", "the card of a detection not contained on a VM already isolated (PRT2 review)", MB,
     "        contained, note = agent._contained_now(signal)\n",
     '        contained, note = False, ""\n'),
    ("M7479", "an ordinary on the code's path takes a snapshot alone (PRT2 review)", MB,
     "    ordinary = not release and call_class(signal) == LOW\n",
     "    ordinary = False\n"),
    ("M7480", "a response without usage priced by LiteLLM: a call that read nothing counted at its word (PRT2 "
     "review)", MB,
     "price(litellm, response, model) if _used(response) else None",
     "price(litellm, response, model) if response is not None else None"),
    ("M7481", "the critical objects' part open to every grave: a burst on VMs not critical empties it (PRT2, "
     "decision of 24/11)", MB,
     "            return self.real_usd - self.critical_part()\n",
     "            return self.real_usd\n"),
]
TESTS = {f"M{n}": _T for n in (*range(7413, 7433), *range(7473, 7482)) if n not in (7427, 7428)}
TESTS["M7427"] = "tests/unit/test_config.py::test_critical_is_read_strictly_and_by_name_or_pattern"
TESTS["M7428"] = "tests/unit/test_config_edit.py::test_critical_set_tightens_taken_away_relaxes_and_an_edit_keeps_it"
