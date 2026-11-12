"""What the CLI shows a human: never a subscription's id (MSK2, #762; IML1c before it).

The output of a command is pasted in an issue or a thread of a public repository. An ARM id
names its subscription; Azure's own error text cites it (a 403: « over scope
'/subscriptions/…' »), and so may a model's explanation that copied the signal's id. Here, at
the display only, each ARM id becomes what a human reads it for — the resource's name and its
resource group — and a subscription's id left bare becomes « <abonnement> ».

Nothing else changes: the signal, the state files and the machine's journals (JSONL) keep the
full id, and a command still takes one. What the model sees is never filtered here: this module
is called by the rendering, after the decision.
"""
from __future__ import annotations

import os
import re

_GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# An ARM id, with or without its leading slash, up to what cannot be in one: a blank, a quote,
# a bracket, a comma, the query of a URL (« ?api-version=… »). A ';' can (a recovery point's
# protected item: « vm;iaasvmcontainerv2;rg;vm »); one that ends it is a sentence's.
_ARM_ID = re.compile(r"/?(?<![A-Za-z0-9])subscriptions/[^\s'\"`,()\[\]{}<>?#&|\\]+", re.IGNORECASE)
# A URL's too, encoded whole (« %2Fsubscriptions%2F<guid> »): after « %2F », no word boundary.
_SUB_IN_ID = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=%2F))subscriptions(?:/|%2F)(" + _GUID + ")", re.IGNORECASE)
# « The subscription 'guid' could not be found », « subscription identifier 'guid' », the JSON
# « "subscriptionId": "guid" », « abonnement guid » : a bare one, named.
_SUB_NAMED = re.compile(r"(?<![A-Za-z0-9])((?:subscription|abonnement)s?(?:[ _-]?(?:identifier|id))?)"
                        r"([\s\"'=:(«»/]{1,4})(" + _GUID + r")(?![0-9A-Za-z])", re.IGNORECASE)
_PATH_BEFORE = re.compile(r"[A-Za-z0-9_.~@#%-]")      # the id's « / » then separates it from a path
_TRAILING = ".;:!"
SUBSCRIPTION = "<abonnement>"


def resource_said(resource_id: str) -> str:
    """An ARM id as a human reads it: the resource's name (a child's after its parent's,
    « nsg-a/rule-x »), then its group — « vm-01 (groupe rg-a) ». A group alone: « groupe rg-a »;
    the subscription alone: « l'abonnement ». A short name is returned as it is."""
    text = str(resource_id or "").strip().strip("/")
    parts = [p for p in text.split("/") if p]
    low = [p.lower() for p in parts]
    if not low or low[0] != "subscriptions":
        return parts[-1] if parts else ""
    group = ""
    if "resourcegroups" in low:
        i = low.index("resourcegroups")
        group = parts[i + 1] if i + 1 < len(parts) and low[i + 1] != "providers" else ""
    names: list[str] = []
    if "providers" in low:
        rest = parts[low.index("providers") + 1:]
        names = rest[2::2]
    if names:
        name = "/".join(names)
        return f"{name} (groupe {group})" if group else name
    if group:
        return f"groupe {group}"
    return "l'abonnement"


def subscriptions_known(text: str = "", environ=None, subscriptions=()) -> set[str]:
    """The subscriptions' ids to keep off a terminal: those this environment names (any
    `…SUBSCRIPTION_ID` that is a GUID), those the caller knows (`subscriptions`: a connector's)
    and those an ARM id of `text` carries. Lower case."""
    env = os.environ if environ is None else environ
    known = {m.group(1).lower() for m in _SUB_IN_ID.finditer(str(text or ""))}
    known |= {str(s).strip().lower() for s in subscriptions or () if re.fullmatch(_GUID, str(s or "").strip())}
    for name, value in env.items():
        if name.upper().endswith("SUBSCRIPTION_ID") and re.fullmatch(_GUID, str(value or "").strip()):
            known.add(str(value).strip().lower())
    return known


def _id_said(match: re.Match) -> str:
    raw = match.group(0)
    core = raw.rstrip(_TRAILING)
    start = match.start()
    # « …/resource/subscriptions/… » keeps its « / »: the name never sticks to the path before it.
    lead = "/" if raw.startswith("/") and start and _PATH_BEFORE.match(match.string[start - 1]) else ""
    return lead + resource_said(core) + raw[len(core):]


def ids_masked(text, environ=None, subscriptions=()) -> str:
    """`text` without a subscription's id: each ARM id said by `resource_said`, each id of a
    known subscription (`subscriptions_known`), or a GUID a « subscription » names, « <abonnement> »."""
    out = str(text if text is not None else "")
    known = subscriptions_known(out, environ, subscriptions)
    out = _ARM_ID.sub(_id_said, out)
    out = _SUB_NAMED.sub(lambda m: f"{m.group(1)}{m.group(2)}{SUBSCRIPTION}", out)
    for sub in known:
        out = re.sub(re.escape(sub), SUBSCRIPTION, out, flags=re.IGNORECASE)
    return out
