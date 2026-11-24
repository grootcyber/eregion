"""PRT2 (#1160): the watch's breaker in dollars — two envelopes, three buckets, the criticality in the config
(glorfindel/model_budget.py; the reading and the class of `critical`, glorfindel/config.py and
glorfindel/config_class.py; the code's path and the draws' context, glorfindel/agent.py). M7413–M7432, measured
by tests/unit/test_model_budget.py, tests/unit/test_config.py and tests/unit/test_config_edit.py. PRT1's
(scripts/mutants/PRT1.py) still hold: the gate's bounds are behind the breaker, unchanged."""
MB = "glorfindel/model_budget.py"
CFG = "glorfindel/config.py"
CLS = "glorfindel/config_class.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_model_budget.py"

MUTANTS = [
    ("M7413", "no reserve for the graves: the ordinaries spend the whole real, a grave on a critical object goes "
     "the code's path with the others (PRT2)", MB,
     "        return min(self.real_usd * RESERVE_MAX, self._critical_count * CRITICAL_USD)\n",
     "        return 0.0\n"),
    ("M7414", "a grave on a critical object held by the others' bucket: it waits for money like them (PRT2)", MB,
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
    ("M7428", "critical never classed: taking it away is not a relaxation (PRT2)", CLS,
     "    _critical(b, a, said)\n", ""),
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
     '        return ("real", "real/rest", f"real/vm/{vm}")\n',
     '        return ("real", "real/rest")\n'),
]
TESTS = {f"M{n}": _T for n in range(7413, 7433) if n not in (7427, 7428)}
TESTS["M7427"] = "tests/unit/test_config.py::test_critical_is_read_strictly_and_by_name_or_pattern"
TESTS["M7428"] = "tests/unit/test_config_edit.py::test_critical_set_tightens_taken_away_relaxes_and_an_edit_keeps_it"
