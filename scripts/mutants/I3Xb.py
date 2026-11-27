"""I3Xb (#1035): the oracle of a held block reads every way to and from the attacker (docs/design/reaffirmation.md
§5, E4; I3X's open side). `_attacker_flows` — the judge of `blocked`, « reposé une fois », « reste bloquée »,
`verify_block_ip` true and `_open_said` — read the probes: TCP all, none out to the attacker but on 443. It reads
now `ATTACKER_WAYS` (tests/unit/fake_azure.py: in and out, 22, 443 and another port, TCP and UDP), the world's
NSGs evaluated, never the code's verification (A0). Each mutant has the product read an allow before our deny
closed where the code's model says it lets the threat through (`_shadowing_rules`, `threat_port_open`): M7054 an
outbound allow on 22, M7055 an outbound allow on UDP, M7056 an inbound allow on UDP on the threat port. On the
probes, the three went unseen: no probe goes out to the attacker on 22, none is UDP. Measured by the machine's own
I3 — the oracle, never a card's text: on its composite rule `a_way_narrowed_then_turned` scripted (the frozen
`test_a_held_block_is_judged_on_every_way_to_and_from_the_attacker`, one variant each: green on the old oracle with
the mutant in, red on the new), then on the machine itself, at 200 sequences, which catches each on some seeds
alone (M7054 on 3 of 4, not on 11; M7055 on 1 of 2; M7056 on 1 of 3): flaky by the machine alone, hence the
frozen first, which holds the criterion."""
_NSG = "glorfindel/providers/azure/nsg.py"
_OPEN = "                    port is None or direction == \"outbound\" or _rule_covers_port(r, port)),\n"
_PROTO = "_enum_text(getattr(r, \"protocol\", \"*\"))"

MUTANTS = [
    ("M7054", "an outbound allow on 22 before our `-out` read closed: « reste bloquée », `blocked`, the check true, "
              "while the VM reaches the attacker on 22 (I3Xb, E4: no probe went out to it on 22)",
     _NSG, _OPEN,
     "                    port is None or (direction == \"outbound\" and getattr(r, \"destination_port_range\", None)"
     " != \"22\")\n                    or (direction != \"outbound\" and _rule_covers_port(r, port))),\n"),
    ("M7055", "an outbound allow on UDP before our `-out` read closed: « reste bloquée », `blocked`, the check true, "
              "while the VM reaches the attacker on UDP (I3Xb, E4: the probes were TCP)",
     _NSG, _OPEN,
     f"                    port is None or (direction == \"outbound\" and {_PROTO} != \"udp\")\n"
     "                    or (direction != \"outbound\" and _rule_covers_port(r, port))),\n"),
    ("M7056", "an inbound allow on UDP on the threat port before our deny read closed: the attacker reaches the VM "
              "on UDP, the block said held (I3Xb, E4; I3X's `in-protocol`: the probes were TCP)",
     _NSG, _OPEN,
     "                    port is None or direction == \"outbound\"\n"
     f"                    or (_rule_covers_port(r, port) and {_PROTO} != \"udp\")),\n"),
]
_FROZEN = "tests/unit/test_invariant_regressions.py::test_a_held_block_is_judged_on_every_way_to_and_from_the_attacker"
TESTS = {"M7054": f"{_FROZEN}[port] tests/unit/test_invariants.py",
         "M7055": f"{_FROZEN}[protocol] tests/unit/test_invariants.py",
         "M7056": f"{_FROZEN}[in-protocol] tests/unit/test_invariants.py"}
