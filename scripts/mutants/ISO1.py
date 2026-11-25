"""ISO1 (#1194): RSM3's night of 25/11 (run 45620147549, ubuntu) red on « I3: release said released,
Db--01 is not back to its design » — the product's, on main since A1. The quarantine off, a NIC with no NSG
at all (none of its own, none on its subnet) after another isolated by rules: isolate_vm refused it with a
bare RuntimeError, after the other NIC's denies, and recorded nothing. The card said the VM not isolated, a
NIC cut off; an NSG taken off its NIC or subnet since kept the pair for ever. It is now recorded `partial`,
as any later NIC's failure, and raises PartialActionError; a first NIC bare still refuses before any write.
M7681: the bare refusal back, nothing recorded — measured by the unit test, the machine's I8 (raised after
isolating part of the VM, no fault played) and the sequences frozen in test_invariant_regressions.py.
M7682: a first NIC bare said partial — the card would tell a containment nothing holds."""
ISO = "glorfindel/providers/azure/isolation.py"
_UNIT = ("tests/unit/test_glorfindel.py::test_a_nic_with_no_nsg_after_another_records_what_landed "
         "tests/unit/test_glorfindel.py::test_a_first_nic_with_no_nsg_still_refuses_before_any_write")
_FROZEN = ("tests/unit/test_invariant_regressions.py::test_an_isolation_refused_on_a_bare_nic_records_what_it_wrote "
           "tests/unit/test_invariant_regressions.py::"
           "test_a_partial_isolation_on_an_nsg_taken_off_its_nic_since_is_released")

MUTANTS = [
    ("M7681", "a NIC with no NSG after another isolated refused bare: the denies already placed recorded "
     "nowhere, the card says the VM not isolated (ISO1)", ISO,
     "add an NSG)\")\n"
     "                failed = {\"nic_id\": t[\"nic_id\"], \"applied\": [], \"bumped\": []}\n"
     "                partial = self._record_partial_isolation(\n"
     "                    vm_name, resource_id, placements, failed, exc, total=len(targets), disks=disks,\n"
     "                    rules=nsg_rules_at_isolation(rules_seen, prior, resource_id))\n"
     "                if partial is None:\n                    raise exc\n                raise partial from exc\n",
     "add an NSG)\")\n"
     "                raise exc\n"),
    ("M7682", "a first NIC with no NSG said a partial isolation: nothing holds, the card tells a containment "
     "(ISO1)", ISO,
     "                if partial is None:\n                    raise exc\n",
     "                if partial is None:\n"
     "                    raise PartialActionError(str(exc), cause=exc, covered=[], failed_nic=t[\"nic_short\"])\n"),
]
TESTS = {"M7681": f"{_UNIT} {_FROZEN}", "M7682": _UNIT}
