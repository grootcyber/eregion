"""IPS1a (#931): the public IP of each network interface in the NSG audit — `check_nsg_access`
gives `nsgs[].public_ips`, an unreadable address said with its reason, never a failed audit
(glorfindel/providers/azure/public_ips.py). M6421–M6430."""
PUBLIC_IPS = "glorfindel/providers/azure/public_ips.py"
READERS = "glorfindel/providers/azure/readers.py"
NETWORK = "glorfindel/providers/azure/network.py"
_TEST = "tests/unit/test_public_ips.py"

MUTANTS = [
    ("M6421", "a public IP whose read fails makes the whole NSG audit fail (IPS1a)", PUBLIC_IPS,
     "            except Exception as exc:\n",
     "            except ZeroDivisionError as exc:\n"),
    ("M6422", "`public_ips` absent from an entry of nsgs[] when the NIC has no public IP (IPS1a)", READERS,
     '                    "public_ips": read_public_ips(self._network, t.get("public_ip_ids") or [], read),\n',
     '                    **({"public_ips": read_public_ips(self._network, t["public_ip_ids"], read)}\n'
     '                       if t.get("public_ip_ids") else {}),\n'),
    ("M6423", "the public IP read in the VM's resource group instead of its own (IPS1a)", READERS,
     '                    "public_ips": read_public_ips(self._network, t.get("public_ip_ids") or [], read),\n',
     '                    "public_ips": read_public_ips(self._network, [\n'
     '                        f\'/resourceGroups/{rg}/{p.rsplit("/", 1)[-1]}\'\n'
     '                        for p in t.get("public_ip_ids") or []], read),\n'),
    ("M6424", "the reason of a failed read lost: the address said null, nothing said why (IPS1a)", PUBLIC_IPS,
     '                cache[k] = {"address": None, "error": reason, "code": code}\n',
     '                cache[k] = {"address": None, "code": code}\n'),
    ("M6425", "an address not allocated yet said null without its reason (IPS1a)", PUBLIC_IPS,
     '                            else {"address": None, "error": NOT_ALLOCATED, "code": UNALLOCATED})\n',
     '                            else {"address": None, "code": UNALLOCATED})\n'),
    ("M6426", "a public IP read again for every NIC that names it, within one call (IPS1a)", PUBLIC_IPS,
     "        if k not in cache:\n",
     "        if True:\n"),
    ("M6427", "a refused read (403) said « not found »: the missing right hidden (IPS1a)", PUBLIC_IPS,
     "    if _is_not_found(exc):\n",
     "    if True:\n"),
    ("M6428", "Azure's refusal carried with its ids, the subscription included (IPS1a)", PUBLIC_IPS,
     "    said = masked(_first_line(exc))[:_REASON_MAX]\n",
     "    said = _first_line(exc)[:_REASON_MAX]\n"),
    ("M6429", "only the NIC's first IP configuration looked at for a public IP (IPS1a)", PUBLIC_IPS,
     '    for c in getattr(nic, "ip_configurations", None) or []:\n',
     '    for c in (getattr(nic, "ip_configurations", None) or [])[:1]:\n'),
    ("M6430", "the NIC's public IPs dropped from its target: none ever read (IPS1a)", NETWORK,
     '                "public_ip_ids": public_ip_ids(nic),\n',
     '                "public_ip_ids": [],\n'),
]
TESTS = {m[0]: _TEST for m in MUTANTS}
