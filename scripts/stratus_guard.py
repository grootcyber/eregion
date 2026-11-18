#!/usr/bin/env python3
"""stratus_guard — refuse an Orodruin plan/apply that would SILENTLY DESTROY the Stratus guardrails
(R2BGb, #897).

The dedicated test subscription's guardrails — the budget, the activity-log diagnostic to the bench
workspace (what the AL detection reads), and the Azure Policy limits on regions / resource types / VM
SKUs and a public IP on a NIC — exist in Terraform only while ``stratus_guardrails_enabled`` is true
and the ``stratus_*`` vars are passed (``infra/orodruin/stratus_guardrails.tf`` — their ``count`` keys
on the flag). An Orodruin apply run WITHOUT them sees ``count = 0`` and plans to DESTROY them: on
18/11 a ``make orodruin-lock`` for another change, with the stratus vars unset in the shell, wiped the
guardrails and blinded the bench's activity-log detection.

The vars belong in ``infra/orodruin/stratus.auto.tfvars`` (Terraform loads every ``*.auto.tfvars``
itself on each plan, like ``session_drain.auto.tfvars``), so they are always passed. This guard is the
backstop for when that file is missing or the flag is off: run before every ``orodruin-plan`` /
``-up`` / ``-lock`` (Makefile), it reads the Terraform state and the effective flag — if the state
HOLDS Stratus guardrail resources but the flag is OFF, it refuses before the plan, so the guardrails
are never torn down by omission. An intentional removal sets ``STRATUS_GUARD_ACK=1``. Standard library
only.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ORO_DIR = "infra/orodruin"
TFVARS = "stratus.auto.tfvars"

# The guardrail resource addresses (``count`` keyed on stratus_guardrails_enabled). NOT
# ``terraform_data.stratus_guard`` — it has no count and stays in state even when the guardrails are
# off, so matching it would make every plan look guarded.
GUARDRAIL_PREFIXES = (
    "azurerm_policy_definition.stratus_",
    "azurerm_subscription_policy_assignment.stratus_",
    "azurerm_monitor_diagnostic_setting.stratus_",
    "azurerm_monitor_action_group.stratus_",
    "azurerm_consumption_budget_subscription.stratus",
)

_TFVARS_ENABLED = re.compile(r"^\s*stratus_guardrails_enabled\s*=\s*true\b", re.MULTILINE)
_TRUE = ("1", "true", "yes", "on")


def has_guardrails(resources) -> bool:
    """True when the Terraform state holds at least one Stratus guardrail resource."""
    return any(any(r.startswith(p) for p in GUARDRAIL_PREFIXES) for r in resources)


def guardrails_enabled(environ, tfvars_text: str) -> bool:
    """The effective flag: the ``TF_VAR_stratus_guardrails_enabled`` env var, or
    ``stratus_guardrails_enabled = true`` in ``stratus.auto.tfvars``."""
    if (environ.get("TF_VAR_stratus_guardrails_enabled") or "").strip().lower() in _TRUE:
        return True
    return bool(_TFVARS_ENABLED.search(tfvars_text or ""))


def decide(resources, enabled: bool) -> tuple[bool, str]:
    """``(refuse, reason)`` — refuse when the state holds guardrails but they are not enabled, so the
    plan would destroy them."""
    if has_guardrails(resources) and not enabled:
        return True, (
            "the Terraform state holds the Stratus guardrails (budget, activity-log diagnostic, "
            "policy limits) but stratus_guardrails_enabled is off — this plan would DESTROY them and "
            f"blind the bench's activity-log detection. Put the stratus_* vars in {ORO_DIR}/{TFVARS} "
            "(Terraform loads it every plan), or export TF_VAR_stratus_guardrails_enabled=true and the "
            "rest; an intentional removal sets STRATUS_GUARD_ACK=1. Not planning."
        )
    return False, ""


def _state_resources(oro_dir: str) -> list[str]:
    """The Terraform state's resource addresses, or ``[]`` when there is no state to read (a first
    apply) or it cannot be read — the guard never blocks on a state-read failure (the
    ``.auto.tfvars`` is the primary protection); it only acts on a state it could read."""
    try:
        out = subprocess.run(["terraform", f"-chdir={oro_dir}", "state", "list"],
                             capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"stratus_guard: terraform state list did not run ({e}); not blocking", file=sys.stderr)
        return []
    if out.returncode != 0:
        return []   # no state yet, or a backend error: fail open
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main(argv: list[str]) -> int:
    if (os.environ.get("STRATUS_GUARD_ACK") or "").strip().lower() in _TRUE:
        print("stratus_guard: STRATUS_GUARD_ACK set — guard bypassed (intentional removal)",
              file=sys.stderr)
        return 0
    oro_dir = argv[0] if argv else ORO_DIR
    try:
        tfvars_text = (Path(oro_dir) / TFVARS).read_text(encoding="utf-8")
    except OSError:
        tfvars_text = ""
    refuse, reason = decide(_state_resources(oro_dir), guardrails_enabled(os.environ, tfvars_text))
    if refuse:
        print(f"✗ stratus guard: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
