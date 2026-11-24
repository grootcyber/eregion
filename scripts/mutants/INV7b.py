"""INV7b (follow-up of #1099): the release of a NIC left bare, traced by our tag on the quarantine NSG
of the configured group (glorfindel/providers/azure/release.py, the stateless sweep, seventh review U2).
M7196–M7198: the original never put back yet our tag forgotten — the NIC left bare for good, nothing left
to say what it carried; the original gone swallowed — the same, said released; the tag forgotten before
the original is put back — the failure said once, the way out lost with the tag.
Measured by the sequences frozen in tests/unit/test_invariant_regressions.py, which catch all three; the
machine does not hold them (measured on 23/11, the machine alone as their target): M7196 caught in one round
of three at 60 sequences (seed 439094684), in none of two at 300 (seed 9564655); M7197 and M7198 in none
(0/3 at 60, 0/2 at 300) — the review of INV7 found the same hole. Nor do the unit tests measured beside them
(test_glorfindel.py, test_release_away.py, test_orphan_sweep.py, test_unreadable_state.py, test_full_id_keys.py,
test_audit_no_nsg.py).
"""
REL = "glorfindel/providers/azure/release.py"
_R = "tests/unit/test_invariant_regressions.py::"

_SET = ('                        if original:\n'
        '                            try:\n'
        '                                self._set_nic_nsg(t0["nic_id"], original)\n')
_GONE = ('                            except Exception as exc:\n'
         '                                raise self._original_gone(q_bare, t0["nic_id"], original, exc)\n'
         '                            if not _same_id(self._nic_nsg_id(t0["nic_id"]) or "", original):\n'
         '                                raise RuntimeError("NSG d\'origine non remis (carte sans NSG)")\n'
         '                            restored = True\n')
_FORGET = '                        self._forget_original(q_bare, t0["nic_id"])\n'

MUTANTS = [
    ("M7196", "a bare NIC traced by our tag never gets its original back, and the tag is forgotten all the "
              "same: left bare for good, nothing says what it carried (INV7b)", REL,
     _SET, _SET.replace("if original:", "if False:")),
    ("M7197", "a bare NIC traced by our tag to an original gone: the failure swallowed, the tag forgotten, "
              "the NIC said released and left bare (INV7b)", REL,
     _GONE, ('                            except Exception:\n'
             '                                pass\n'
             '                            else:\n'
             '                                restored = True\n')),
    ("M7198", "our tag on a bare NIC forgotten before its original is put back: the original gone, the "
              "failure said once, the way out lost with the tag (INV7b)", REL,
     _SET + _GONE + _FORGET, _FORGET + _SET + _GONE),
]

_GONE_SAID = _R + "test_an_original_gone_says_how_to_get_out"
TESTS = {
    "M7196": " ".join((_R + "test_a_tag_written_again_ties_the_nic_back", _R + "test_a_tag_never_lost_ties_the_nic",
                       _GONE_SAID, _R + "test_two_hosts_a_stale_none_never_leaves_the_nic_bare")),
    "M7197": _GONE_SAID,
    "M7198": _GONE_SAID,
}
