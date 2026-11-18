"""R2BGb (#897): an Orodruin plan/apply never destroys the Stratus guardrails by omission.

``scripts/stratus_guard.py``, run before ``orodruin-plan``/``-up``/``-lock`` (Makefile), reads the
Terraform state and the effective ``stratus_guardrails_enabled`` flag: if the state HOLDS Stratus
guardrail resources but the flag is OFF, it refuses before the plan (an apply would otherwise see
``count = 0`` and destroy them, blinding the bench's activity-log detection). The vars live in
``infra/orodruin/stratus.auto.tfvars`` (Terraform loads it every plan). Tests here: the guard's logic
on a fake state list (no terraform), and the Makefile wiring (the guard on plan/up/lock, not on down).
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "stratus_guard.py"
MAKEFILE = ROOT / "Makefile"
EXAMPLE = ROOT / "infra" / "orodruin" / "stratus.auto.tfvars.example"
VARIABLES = ROOT / "infra" / "orodruin" / "variables.tf"

_spec = importlib.util.spec_from_file_location("stratus_guard", SCRIPT)
sg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sg)

BUDGET = "azurerm_consumption_budget_subscription.stratus[0]"
DIAG = "azurerm_monitor_diagnostic_setting.stratus_activity_log[0]"
POLICY = "azurerm_subscription_policy_assignment.stratus_allowed_locations[0]"
ACTION = "azurerm_monitor_action_group.stratus_budget[0]"
DEFN = "azurerm_policy_definition.stratus_deny_nic_public_ip[0]"
GUARD = "terraform_data.stratus_guard"          # no count — stays in state even when disabled
OTHER = "azurerm_linux_virtual_machine.orodruin"


@pytest.mark.parametrize("res", [BUDGET, DIAG, POLICY, ACTION, DEFN])
def test_each_guardrail_resource_is_detected(res):
    assert sg.has_guardrails([GUARD, OTHER, res]) is True


def test_the_inert_stratus_guard_alone_is_not_a_guardrail():
    """``terraform_data.stratus_guard`` has no count — matching it would make every plan look guarded."""
    assert sg.has_guardrails([GUARD, OTHER]) is False


def test_refuses_when_the_state_holds_guardrails_and_the_flag_is_off():
    refuse, reason = sg.decide([GUARD, BUDGET, DIAG], enabled=False)
    assert refuse is True
    assert "DESTROY" in reason and "stratus.auto.tfvars" in reason


def test_allows_when_the_flag_is_on():
    refuse, _ = sg.decide([GUARD, BUDGET, DIAG], enabled=True)
    assert refuse is False


def test_allows_when_the_state_holds_no_guardrails():
    refuse, _ = sg.decide([GUARD, OTHER], enabled=False)
    assert refuse is False


def test_the_flag_is_read_from_the_env():
    assert sg.guardrails_enabled({"TF_VAR_stratus_guardrails_enabled": "true"}, "") is True
    assert sg.guardrails_enabled({"TF_VAR_stratus_guardrails_enabled": "1"}, "") is True


def test_the_flag_is_read_from_the_auto_tfvars():
    assert sg.guardrails_enabled({}, "stratus_guardrails_enabled = true\n") is True
    assert sg.guardrails_enabled({}, "foo = 1\nstratus_guardrails_enabled=true\n") is True


def test_the_flag_is_off_when_neither_says_true():
    assert sg.guardrails_enabled({}, "stratus_guardrails_enabled = false\n") is False
    assert sg.guardrails_enabled({}, "") is False
    assert sg.guardrails_enabled({"TF_VAR_stratus_guardrails_enabled": "no"}, "") is False


def test_the_auto_tfvars_wins_over_the_env():
    """Terraform gives *.auto.tfvars precedence over TF_VAR_* : a file saying `false` with the env
    saying `true` is OFF — so the guard refuses (the transition case that would otherwise destroy)."""
    env_true = {"TF_VAR_stratus_guardrails_enabled": "true"}
    file_false = "stratus_guardrails_enabled = false\n"
    assert sg.guardrails_enabled(env_true, file_false) is False
    # a quoted bool is coerced to false by Terraform too — the guard must read it off as well
    assert sg.guardrails_enabled(env_true, 'stratus_guardrails_enabled = "false"\n') is False
    refuse, _ = sg.decide([GUARD, BUDGET], enabled=sg.guardrails_enabled(env_true, file_false))
    assert refuse is True


def test_main_refuses_when_the_state_is_guarded_and_the_flag_is_off(tmp_path, monkeypatch):
    """main returns 1 (the Makefile's `&&` then stops the plan). The oro dir is tmp_path (no
    stratus.auto.tfvars there), so the test never reads the operator's real file; state injected."""
    monkeypatch.delenv("TF_VAR_stratus_guardrails_enabled", raising=False)
    monkeypatch.delenv("STRATUS_GUARD_ACK", raising=False)
    assert sg.main([str(tmp_path)], state_reader=lambda oro_dir: [GUARD, BUDGET]) == 1


def test_ack_bypasses_the_guard_even_when_it_would_refuse(tmp_path, monkeypatch):
    """STRATUS_GUARD_ACK=1 for an intentional removal — main returns 0 even on a guarded state."""
    monkeypatch.delenv("TF_VAR_stratus_guardrails_enabled", raising=False)
    monkeypatch.setenv("STRATUS_GUARD_ACK", "1")
    assert sg.main([str(tmp_path)], state_reader=lambda oro_dir: [GUARD, BUDGET]) == 0


def _tfvars_value(text, name):
    m = re.search(rf'^\s*{name}\s*=\s*"([^"]*)"', text, re.MULTILINE)
    return m.group(1) if m else None


def _variable_regex(text, name):
    block = re.search(rf'variable "{name}".*?(?=\nvariable |\Z)', text, re.DOTALL)
    m = re.search(r'regex\("([^"]+)"', block.group(0)) if block else None
    return m.group(1) if m else None


@pytest.mark.parametrize("name", ["stratus_subscription_id", "stratus_budget_start_date"])
def test_the_example_values_pass_the_variable_validation(name):
    """constat 2: copying the example must not break an apply — its values satisfy the validations
    of infra/orodruin/variables.tf (a variable validation runs whatever the flag's value)."""
    pattern = _variable_regex(VARIABLES.read_text(encoding="utf-8"), name)
    value = _tfvars_value(EXAMPLE.read_text(encoding="utf-8"), name)
    assert pattern and value is not None, (name, pattern, value)
    assert re.match(pattern, value), f"{name}={value!r} fails {pattern!r}"


def test_the_guard_is_wired_on_the_converging_applies_not_on_destroy():
    mk = MAKEFILE.read_text(encoding="utf-8")
    assert "STRATUS_GUARD = python3 scripts/stratus_guard.py" in mk
    seen_apply = seen_destroy = 0
    for ln in mk.splitlines():
        s = ln.strip()
        if "$(ORO_TF) plan " in s or "$(ORO_TF) apply " in s:
            seen_apply += 1
            assert s.startswith("$(STRATUS_GUARD)"), f"guard missing on: {s}"
        if "$(ORO_TF) destroy " in s:
            seen_destroy += 1
            assert "$(STRATUS_GUARD)" not in s, f"guard wrongly on a deliberate teardown: {s}"
    assert seen_apply == 3 and seen_destroy == 1   # plan + up + lock guarded; down (destroy) not
