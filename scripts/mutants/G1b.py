"""G1b (Partie de #76): the preflight says whether a fault could run, and be seen — Orodruin's
rights on the experiment, the Chaos agent on each VM it reaches that way, each series the effect
reads collected; reads only, one not held or unreadable: not ready. M6586–M6605 and M6616 (after
the review), measured by tests/unit/test_gothmog_readiness.py."""
CS = "gothmog/engines/chaos_studio.py"
PR = "gothmog/probes.py"
EN = "gothmog/runner/engine.py"
_T = "tests/unit/test_gothmog_readiness.py"

MUTANTS = [
    ("M6586", "a right one role takes back is held all the same: its notActions ignored (G1b)", CS,
     '        and not any(fnmatch.fnmatch(a, str(x).lower()) for x in (p.get("notActions") or []))\n',
     ""),
    ("M6587", "the preflight asks the start alone: a fault that starts and can never be cancelled "
     "is ready (G1b)", CS,
     'EXPERIMENT_WRITES = ("Microsoft.Chaos/experiments/start/action",\n'
     '                     "Microsoft.Chaos/experiments/cancel/action")\n',
     'EXPERIMENT_WRITES = ("Microsoft.Chaos/experiments/start/action",)\n'),
    ("M6588", "rights that go on past their first page held on half of them (G1b)", CS,
     '        if body.get("nextLink"):\n'
     '            raise RuntimeError("the rights go on past their first page: not read")\n',
     ""),
    ("M6589", "rights that cannot be read held (G1b)", EN,
     '            out.append(ProbeResult(f"{name} rights", False,\n',
     '            out.append(ProbeResult(f"{name} rights", True,\n'),
    ("M6590", "a right not held said held: orodruin-lock forgotten, the start answers 403 on the "
     "bench (G1b)", EN,
     "                ok = held(action, perms)\n",
     "                ok = True\n"),
    ("M6591", "the Chaos agent never asked: an experiment through it is ready on a VM without "
     "it (G1b)", CS,
     '            if m and _AGENT_TARGET.search(tid) and tid[:m.end("vm")].lower() not in {v.lower() for v in vms}:\n',
     "            if False:\n"),
    ("M6592", "an agent whose extension failed, or is still being installed, said installed "
     "(G1b)", EN,
     "            out.append(ProbeResult(f\"{vm.rsplit('/', 1)[-1]} chaos agent\", status == AGENT_INSTALLED,\n",
     "            out.append(ProbeResult(f\"{vm.rsplit('/', 1)[-1]} chaos agent\", status.startswith(\"ProvisioningState/\"),\n"),
    ("M6593", "the agent's status read from the VM's first extension, whichever it is (G1b)", CS,
     '        if (str(ext.get("name") or "").lower() == CHAOS_AGENT_EXTENSION\n'
     '                or str(ext.get("type") or "").lower() == CHAOS_AGENT_TYPE):\n',
     "        if True:\n"),
    ("M6594", "an agent that cannot be read said installed (G1b)", EN,
     '                status = f"{UNREADABLE}: {type(e).__name__}: {e}"[:200]\n',
     "                status = AGENT_INSTALLED\n"),
    ("M6595", "the series asked above its threshold, idle: a bench ready to run said not ready "
     "(G1b)", PR,
     "            ok = _number(peak)\n",
     "            ok = _number(peak) and peak > 0\n"),
    ("M6596", "a series that gives nothing said collected: the noise runs ten minutes, unseen "
     "(G1b)", PR,
     "            ok = _number(peak)\n",
     "            ok = True\n"),
    ("M6597", "the series read over no time at all (G1b)", PR,
     '            rows = bench.query(_effect_query(p["verify"], target, now - window, now))\n',
     '            rows = bench.query(_effect_query(p["verify"], target, now, now))\n'),
    ("M6598", "a series that cannot be read said collected (G1b)", PR,
     "        except Exception as e:  # unreadable is not collected\n"
     '            observed, ok = f"{UNREADABLE}: {type(e).__name__}: {e}"[:200], False\n',
     "        except Exception as e:  # unreadable is not collected\n"
     '            observed, ok = f"{UNREADABLE}: {type(e).__name__}: {e}"[:200], True\n'),
    ("M6599", "no series asked at all (G1b)", PR,
     '        if p["verify"] == "power_state":\n'
     "            continue\n",
     "        if True:\n"
     "            continue\n"),
    ("M6600", "the preflight says ready over what it found missing (G1b)", EN,
     "        if missing:\n",
     "        if False:\n"),
    ("M6601", "the agent asked on every target, a shutdown's included: G0 refused for an agent it "
     "never needs (G1b)", EN,
     '        seen["experiment"] = {"name": name, "duration_s": duration, "agents": agent_vms(experiment)}\n',
     '        seen["experiment"] = {"name": name, "duration_s": duration, "agents": list(vms)}\n'),
    ("M6602", "the preflight reads the experiment again for its agents: answering {}, no agent asked, "
     "a VM without one ready (G1b, review 1)", EN,
     '        for vm in seen["experiment"]["agents"]:\n',
     '        for vm in agent_vms(bench.experiment(name)):\n'),
    ("M6603", "an agent absent from the VM said installed (G1b)", CS,
     "    return AGENT_ABSENT\n",
     "    return AGENT_INSTALLED\n"),
    ("M6604", "the extension looked for under a name Celebrimbor never gives it (G1b)", CS,
     'CHAOS_AGENT_EXTENSION = "chaoslinuxagent"\n',
     'CHAOS_AGENT_EXTENSION = "chaosagent"\n'),
    ("M6605", "the rights read on the bench's group, not on the experiment: a right granted "
     "experiment by experiment never seen (G1b)", EN,
     "            perms = bench.permissions(bench.experiment_id(name))\n",
     '            perms = bench.permissions(bench.experiment_id(name).rsplit("/providers/", 1)[0])\n'),
    ("M6616", "a rights answer that lists nothing read as no right: « orodruin-lock » said where "
     "the rights were unreadable (G1b, review 2)", CS,
     "        if not isinstance(value, list):\n"
     '            raise RuntimeError("the rights answer holds no list of them: not read")\n'
     "        return value\n",
     "        return value or []\n"),
]

TESTS = {
    "M6586": f"{_T}::test_a_right_its_role_takes_back_is_not_held",
    "M6587": f"{_T}::test_without_orodruin_lock_the_preflight_says_a_start_would_be_refused "
             f"{_T}::test_the_names_read_are_those_celebrimbor_and_orodruin_declare",
    "M6588": f"{_T}::test_rights_that_cannot_be_read_are_not_held",
    "M6589": f"{_T}::test_rights_that_cannot_be_read_are_not_held",
    "M6590": f"{_T}::test_without_orodruin_lock_the_preflight_says_a_start_would_be_refused",
    "M6591": f"{_T}::test_a_chaos_agent_not_installed_is_not_ready "
             f"{_T}::test_the_agent_is_read_only_on_the_vms_it_reaches",
    "M6592": f"{_T}::test_a_chaos_agent_not_installed_is_not_ready",
    "M6593": f"{_T}::test_the_agent_is_read_only_on_the_vms_it_reaches",
    "M6594": f"{_T}::test_an_agent_that_cannot_be_read_is_not_installed",
    "M6595": f"{_T}::test_an_idle_series_is_collected_far_below_its_threshold",
    "M6596": f"{_T}::test_a_series_never_collected_under_the_effect_s_names_is_not_ready",
    "M6597": f"{_T}::test_a_noise_ready_to_run_says_each_thing_it_read_and_writes_nothing",
    "M6598": f"{_T}::test_a_series_that_cannot_be_read_is_not_collected",
    "M6599": f"{_T}::test_a_series_never_collected_under_the_effect_s_names_is_not_ready",
    "M6600": f"{_T}::test_without_orodruin_lock_the_preflight_says_a_start_would_be_refused",
    "M6601": f"{_T}::test_a_fault_on_the_vm_itself_asks_its_rights_and_no_agent_nor_series",
    "M6602": f"{_T}::test_the_agent_is_asked_on_the_experiment_the_gate_validated",
    "M6603": f"{_T}::test_a_chaos_agent_not_installed_is_not_ready "
             f"{_T}::test_the_agent_is_read_only_on_the_vms_it_reaches",
    "M6604": f"{_T}::test_the_names_read_are_those_celebrimbor_and_orodruin_declare",
    "M6605": f"{_T}::test_a_noise_ready_to_run_says_each_thing_it_read_and_writes_nothing",
    "M6616": f"{_T}::test_rights_that_cannot_be_read_are_not_held",
}
