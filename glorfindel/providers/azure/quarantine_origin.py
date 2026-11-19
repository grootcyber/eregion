"""The original NSG of a NIC in our quarantine, as our tag on the quarantine NSG keeps it (moved from
quarantine.py, SEC-H): its key (128 bits of the NIC's id; the 48 an earlier version wrote, read only),
what a tag may name, and the lookup of a bare NIC's — in the group our quarantine NSGs are made in only.
"""
from __future__ import annotations

import hashlib
import os

from glorfindel.providers.azure.sdk import _is_not_found
from glorfindel.response.ids import _parse_nsg_resource_id, _subscription_of
from glorfindel.response.state import _UNKNOWN


class OriginMixin:
    """The original's tag (part of QuarantineMixin, of AzureConnector)."""

    @staticmethod
    def _orig_tag(nic_id: str) -> str:
        """The key of a NIC's original on our quarantine NSG, shared by every NIC of the region:
        128 bits of the NIC's id (SEC-H) — on 48, two NICs that met shared one original."""
        return "glorfindel-orig-" + hashlib.sha256(nic_id.rstrip("/").lower().encode()).hexdigest()[:32]

    @staticmethod
    def _older_orig_tag(nic_id: str) -> str:
        """The key an earlier version wrote (48 bits of SHA-1): read when ours isn't there, never
        written again, removed with ours."""
        return "glorfindel-orig-" + hashlib.sha1(nic_id.rstrip("/").lower().encode()).hexdigest()[:12]

    def _orig_tags(self, nic_id: str) -> set[str]:
        """Both keys of a NIC's original: ours and the earlier version's."""
        return {self._orig_tag(nic_id), self._older_orig_tag(nic_id)}

    def _not_an_original(self, value: str) -> str:
        """Why the NSG a tag names can't be a NIC's original (SEC-H), "" when it can: an NSG's id,
        in the subscription Glorfindel acts in, not one of our quarantine NSGs. Its region is
        Azure's to hold: an NSG of another region is refused on the NIC, and the release says so."""
        from glorfindel.providers.azure.quarantine import _is_quarantine_nsg
        parts = [x.lower() for x in str(value).strip("/").split("/")]
        if (len(parts) != 8 or parts[0] != "subscriptions" or parts[2] != "resourcegroups"
                or parts[4:7] != ["providers", "microsoft.network", "networksecuritygroups"]):
            return "pas l'id d'un NSG"
        mine = (getattr(self, "_subscription_id", "") or os.environ.get("AZURE_SUBSCRIPTION_ID", "")).lower()
        if mine and _subscription_of(value).lower() != mine:
            return f"un NSG de l'abonnement {_subscription_of(value)}, Glorfindel agit dans {mine}"
        if _is_quarantine_nsg(value):
            return "un de nos NSG de quarantaine"
        return ""

    def _bare_nic_original(self, t0: dict, vm_rg: str):
        """A NIC with no NSG at all that was in our quarantine: someone took our NSG off
        and left it bare (seventh review, U2). Our tag still says what it carried — it
        goes only once the original is back. (original or None, the quarantine NSG) when
        a tag is found, (_UNKNOWN, None) otherwise. Looked up on the region's quarantine
        NSG in the group our quarantine NSGs are made in — the configured one, else the
        VM's (`_ensure_quarantine_nsg`) — and nowhere else (SEC-H): searched in the whole
        subscription, an NSG anyone could name and tag like ours, in a group of theirs,
        chose the NSG put back on the NIC, and won over the authentic "none". A tag that
        names an NSG it can't be (another subscription, one of our quarantine NSGs, not an
        NSG's id) counts for none.

        One of another group naming an NSG for this NIC — another host's, configured with
        another quarantine group (I8S), or anyone's decoy — never chooses: OriginalConflict,
        the NIC kept as it is and said, until the operator writes the original on our tag."""
        from glorfindel.providers.azure.quarantine import QUARANTINE_NSG_PREFIX
        if t0.get("quarantine") or t0.get("own_nsg_id"):
            return _UNKNOWN, None
        name = f"{QUARANTINE_NSG_PREFIX}-{(t0.get('location') or 'unknown').lower()}"
        q_rg = vm_rg
        try:
            q_rg = self._quarantine_settings()[1] or vm_rg
        except Exception:
            pass                                  # the config unreadable: the default group, the VM's
        found: tuple = (_UNKNOWN, None)
        try:
            nsg = self._network.network_security_groups.get(q_rg, name)
        except Exception as exc:
            if not _is_not_found(exc):
                raise
            nsg = None
        value = self._tagged(nsg, t0["nic_id"]) if nsg is not None else None
        if value:
            q_rg, q_name = _parse_nsg_resource_id(nsg.id)
            found = ((None if value == self._NO_ORIGINAL else value),
                     {"nsg_rg": q_rg, "nsg_name": q_name, "nsg_id": nsg.id})
            if found[0]:
                return found
        own = (nsg.id if nsg is not None else "").rstrip("/").lower()
        elsewhere = [(n.id, v) for n in self._network.network_security_groups.list_all()
                     if (getattr(n, "name", "") or "").lower() == name and n.id.rstrip("/").lower() != own
                     and (v := self._tagged(n, t0["nic_id"])) and v != self._NO_ORIGINAL]
        if elsewhere:
            where, value = elsewhere[0]
            key = self._orig_tag(t0["nic_id"])
            raise OriginalConflict(
                f"{t0.get('nic_short') or t0['nic_id'].rsplit('/', 1)[-1]} : le NSG de quarantaine "
                f"{'/'.join(_parse_nsg_resource_id(where))}, hors du groupe {q_rg}, nomme "
                f"{value.rstrip('/').rsplit('/', 1)[-1]} comme son NSG d'origine — un autre hôte Glorfindel "
                "configuré sur un autre groupe, ou un leurre : jamais suivi. La carte reste telle quelle ; si "
                f"c'est bien son NSG, poser le tag {key}=<id du NSG> sur {name} ({q_rg}), puis relancer")
        return found

    def _tagged(self, nsg, nic_id: str) -> str | None:
        """What our tag on this quarantine NSG says of the NIC (an NSG's id, or "none"), only on an NSG
        that says it is ours, and only an original it can be (`_not_an_original`); else None."""
        tags = getattr(nsg, "tags", None) or {}
        if tags.get("managed-by") != "glorfindel":
            return None
        value = tags.get(self._orig_tag(nic_id)) or tags.get(self._older_orig_tag(nic_id))
        if not value or (value != self._NO_ORIGINAL and self._not_an_original(value)):
            return None
        return value


class OriginalConflict(RuntimeError):
    """A quarantine NSG outside our group names the original of a bare NIC (SEC-H): never followed,
    the NIC kept as it is until the operator writes the original on our tag."""
