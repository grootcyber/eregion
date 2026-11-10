"""DRN1 (#677) and BL1: a session cut followed on Azure, as the containment's analysis reads it.

Moved out of tests/unit/test_drain_follow.py (D1): these read `analysis`, absent when Glorfindel's
tests run alone (scripts/component_check.py) — listed in TOGETHER. The world and its fixtures are
test_drain_follow.py's: the in-memory Azure, a Run Command held running, then ended by the test.
"""
from __future__ import annotations

from azure.core.exceptions import HttpResponseError

from glorfindel import escalations
from glorfindel.reassert import reassert_pass

from . import test_drain_follow as _follow
from .fake_azure import _error

_ACT, _WEB = _follow._ACT, _follow._WEB
# The fixtures, test_drain_follow.py's: the in-memory Azure, and no drain followed from another test.
azure = _follow.azure
_no_drain_followed = _follow._no_drain_followed


def test_a_failure_after_the_first_wait_counts_as_a_containment_that_did_not_hold(azure):
    """BL1 (analysis/containment.py): the cycle verified on the NSG, then the cut that failed —
    never counted « contenu seul »."""
    from analysis.containment import not_holding
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) agent"))
    reassert_pass(c, _ACT)
    assert not_holding(_WEB, 0.0, 4e9, escalations.all_escalations()) is not None


def test_a_pending_card_never_counts_against_the_containment(azure):
    from analysis.containment import not_holding
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    f.end_run_commands()
    reassert_pass(c, _ACT)
    assert not_holding(_WEB, 0.0, 4e9, escalations.all_escalations()) is None
