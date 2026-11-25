"""OOR1 (#1202): a VM of another subscription than the watch's, said by the console — never a 500.

A VM's readiness (`/api/readiness`, `/api/activate`) reads its rights through the connector, which refuses
any subscription but the watch's (`_same_subscription`: WrongSubscriptionError, glorfindel/response/policy.py).
Unread, that refusal reached the browser as a 500. Said here: the VM is out of reach, detect only — on its
tile the page already shows no « Review & turn on » (GRP1); this answers a call from anywhere else. No
identifier in the answer: the exception's text names both subscriptions whole.
"""
from __future__ import annotations

OUT_OF_REACH = ("out of reach, detect only: this VM is in another subscription than the watch's, "
                "which acts only in its own")


def assess(resource_id: str, connector, quarantine_nsg: bool = True) -> dict:
    """`glorfindel.readiness.assess`, its refusal of another subscription said as an error."""
    from glorfindel.readiness import assess as _assess
    from glorfindel.response.policy import WrongSubscriptionError
    try:
        return _assess(resource_id, connector, quarantine_nsg=quarantine_nsg)
    except WrongSubscriptionError:
        return {"error": OUT_OF_REACH}
