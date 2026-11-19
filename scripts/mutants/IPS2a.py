"""IPS2a (Partie de #950): the NSG audit gives the addresses of a VM without NSG — the check stays a
failure, carries `data.nsgs[]` (a NIC without NSG said `nsg_scope: "none"`), and a failed public IP
read carries its `code` beside its French text. A failure that carries data stays a failure for
every reader (the audit's verdict, the readiness, the posture). M6511–M6520, M6531–M6532."""
PUBLIC_IPS = "glorfindel/providers/azure/public_ips.py"
READERS = "glorfindel/providers/azure/readers.py"
NETWORK = "glorfindel/providers/azure/network.py"
AUDIT = "glorfindel/audit.py"
READINESS = "glorfindel/readiness.py"
POSTURE = "glorfindel/posture.py"
_TEST = "tests/unit/test_audit_no_nsg.py"

MUTANTS = [
    ("M6511", "the NIC without NSG loses its `nsg_scope: \"none\"`: the page cannot tell it (IPS2a)", READERS,
     '                    "nsg_scope": t["scope"],\n',
     '                    **({"nsg_scope": t["scope"]} if t["scope"] != "none" else {}),\n'),
    ("M6512", "a VM without NSG said ok once its addresses are read (IPS2a)", READERS,
     '                return {**failed, "nsgs": nsgs}\n',
     '                return {**failed, "ok": True, "nsgs": nsgs}\n'),
    ("M6513", "the audit's « NSG access » check turned ok when it carries data (IPS2a)", AUDIT,
     '        status="fail",\n        message=f"NSG not found or VM has no NSG — {err}",\n',
     '        status="ok" if bare else "fail",\n        message=f"NSG not found or VM has no NSG — {err}",\n'),
    ("M6514", "the readiness takes the data of a failed NSG audit for an NSG that reads: no reserve "
     "for blocks (IPS2a)", READINESS,
     '        if not nsg.get("ok"):\n',
     '        if not (nsg.get("ok") or nsg.get("nsgs")):\n'),
    ("M6515", "the posture takes the data of a failed NSG audit for a success: the critical gap "
     "lost (IPS2a)", POSTURE,
     '                self._mark_inconclusive(vm, "nsg_reachable")\n            elif not res.get("ok"):\n',
     '                self._mark_inconclusive(vm, "nsg_reachable")\n'
     '            elif not (res.get("ok") or res.get("nsgs")):\n'),
    ("M6516", "the audit takes the data of a failed NSG read for a success (IPS2a)", AUDIT,
     '    res = connector.check_nsg_access(resource_id)\n\n    if res.get("ok"):\n',
     '    res = connector.check_nsg_access(resource_id)\n\n    if res.get("ok") or res.get("nsgs"):\n'),
    ("M6517", "a refused read (403) coded `not_found`: the missing right hidden from the page (IPS2a)",
     PUBLIC_IPS,
     '        return FORBIDDEN, f"lecture refusée (droits) : {said}"\n',
     '        return GONE, f"lecture refusée (droits) : {said}"\n'),
    ("M6518", "a read address carries a code, as if it had failed (IPS2a)", PUBLIC_IPS,
     '                cache[k] = ({"address": address} if address\n',
     '                cache[k] = ({"address": address, "code": UNREADABLE} if address\n'),
    ("M6519", "the audit's failed check drops the addresses read: `data` empty (IPS2a)", AUDIT,
     '        data={"nsgs": bare} if bare else {},\n',
     '        data={},\n'),
    ("M6520", "a NIC whose subnet did not read said without NSG, its addresses claimed (IPS2a)", READERS,
     '                    return failed             # unknown, not "none": no address claimed\n',
     '                    pass\n'),
    # The review of IPS2a (PR #952): ids handed out by the Orchestre.
    ("M6531", "a NIC without NSG read before a NIC whose read fails no longer said « no NSG »: the "
     "reserve loosened by the order of the NICs (IPS2a)", READERS,
     '            if bare:                  # a NIC without NSG read already: that, not the error\n',
     '            if False:\n'),
    ("M6532", "`iam` computed on the message of a VM without NSG, not False: a NIC's name makes it "
     "an IAM failure (IPS2a)", NETWORK,
     '    return {"ok": False, "iam": False, "no_nsg": True,\n',
     '    from glorfindel.providers.azure.sdk import _is_iam_error\n'
     '    return {"ok": False, "iam": _is_iam_error(bare[0]["nic_short"]), "no_nsg": True,\n'),
]
TESTS = {m[0]: _TEST for m in MUTANTS}
