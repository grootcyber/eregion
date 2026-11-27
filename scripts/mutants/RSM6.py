"""RSM6 (#1263): the reassertion keeps its word (docs/design/reaffirmation.md §3.1 R3, §3.2, §3.6). A perimeter pair
deferred for want of a read is put back once at the first pass that reads, also when nothing was written; the card
of a VM skipped closes at the first pass that reads it, after a restart too, or once it is lifted — never while it
is still skipped. Each mutant puts back a way it could go wrong: M8113 leaves the deferral unmarked where every write
failed (the next pass silent, the pair gone till a restart: the defect); M8114 glues the note to the sentence before
it (« — rien n'est posé Sa règle … »); M8115 has the first time put the pair back alone after a put-back where
nothing was written (a merged entry's VM rules, failed, never written again); M8116 keeps a card « sautée » pending
once its VM is lifted; M8117 keeps it pending once its VM is read again after a restart; M8118 closes it while the
VM is still skipped; M8119 closes it as « levée » while a state can't be read (SEC4b); M8120 keeps a run of skips
across a lift (a VM isolated again later said early, or never). Measured by tests/unit/test_reassert_promise.py."""
_R = "glorfindel/reassert.py"
_RP = "glorfindel/reassert_perimeters.py"
_G = "glorfindel/reassert_gone.py"
_S = "glorfindel/reassert_skipped.py"
_P = "tests/unit/test_reassert_promise.py::"

MUTANTS = [
    ("M8113", "a pair deferred where every write failed left unmarked: its card promises it at the next pass, which "
              "reads the drift « already said » and is silent — the pair gone till a restart (RSM6, the defect)",
     _R, "        if deferred:\n            # Nothing written, its pair deferred all the same",
     "        if False:\n            # Nothing written, its pair deferred all the same"),
    ("M8114", "the deferral's note glued to the sentence before it: « — rien n'est posé Sa règle … » (RSM6)",
     _G, 'f"{_sentence(reason)} {note}"', 'f"{reason} {note}"'),
    ("M8115", "the pair deferred after a put-back where nothing was written put back alone: a merged entry's VM "
              "rules, failed too, never written again, their put-back spent by the pair's (RSM6)",
     _RP, ('                                                       **({"unspent": True} if b.get("pair_deferred")\n'
           '                                                          and not b.get("reasserted_at") else {})}\n'),
     "                                                       }\n"),
    ("M8116", "a card « sautée » kept pending once its VM is lifted or unblocked while skipped: no pass reads it "
              "again, the card waits for the operator (RSM6)",
     _S, '                _resolve(e["id"], note=LIFTED)        # lifted or unblocked while skipped (RSM6)\n',
     "                pass\n"),
    ("M8117", "a card « sautée » kept pending when its VM is read again: after a restart, the count at 0, it never "
              "closes (RSM6)",
     _S, ('                _resolve(e["id"], note="La réaffirmation relit la VM de nouveau.")\n'
          "                continue\n"),
     "                continue\n"),
    # Without the skip guard alone, a VM skipped is still recorded, its card kept as held (RSM6's review): the
    # guard is what keeps a VM skipped from being read as read.
    ("M8118", "a card « sautée » closed as read while its VM is still skipped: the VM unread, its card gone (RSM6)",
     _S, (' or e.get("status") != "pending" or sid in skipped_now:\n', "            if sid in read_now:\n"),
     (' or e.get("status") != "pending":\n', "            if sid in read_now or sid in skipped_now:\n")),
    ("M8119", "a card « sautée » closed as « levée » while a state can't be read: what it holds is unknown (RSM6, "
              "SEC4b)",
     _S, "                held, looked = (None if unreadable_states() else _held(active_isolations, active_blocks)), True\n",
     "                held, looked = _held(active_isolations, active_blocks), True\n"),
    ("M8120", "a run of skips kept across a lift: a VM isolated again later said before its count, or never (RSM6)",
     _S, "    for sid in [s for s in _SKIPPED if s not in skipped_now]:\n        _SKIPPED.pop(sid, None)\n", ""),
    # Its first review (27/11): M8129 closes a card « sautée » as lifted on « neither read nor skipped » (a lock
    # that raised an OSError), not on what is recorded; M8130 never notes the VM read (closed as lifted, never
    # while another state is unreadable); M8131 says « sa règle de périmètre … reportée » of a merged entry whose
    # VM rules were written with the pair (`unspent`); M8132 settles on the pass's cache, a card the operator
    # acknowledged during the pass closed again.
    ("M8129", "a card « sautée » closed as « Levé » on a VM neither read nor skipped — its lock raised an "
              "OSError —, still recorded (RSM6's review)",
     _S, "            if held is not None and sid not in held:\n", "            if held is not None:\n"),
    ("M8130", "the VM read never noted: its card closed as lifted, never while another state is unreadable "
              "(RSM6's review)",
     _S, '    _PASS["read"].add(sid)\n', ""),
    ("M8131", "the pair deferred where nothing was written, put back with the VM's rules, said « sa règle de "
              "périmètre reposée une fois, reportée » (RSM6's review)",
     _G, "    if pair_alone(pair) and not deferred:\n", '    if (pair or {}).get("pair_only") and not deferred:\n'),
    ("M8132", "the cards « sautée » settled on the pass's cache: a card acknowledged during the pass closed again, "
              "the operator's word overwritten (RSM6's review)",
     _S, "        new_pass()           # read now: a card the operator acknowledged during the pass is never closed "
         "again\n", ""),
    # M8133 puts back RSM3's « tried once »: the deferred pair refused unread again read as tried — the second time
    # neither keeps it deferred nor brings its card up to date: a new card each pass, its promise gone. (Its
    # first-time half, the mark dropped there alone, survives: the second time marks it again, `defer_marks`.)
    ("M8133", "the deferred pair refused unread again (`PairUnread`) read as tried once: never deferred again by "
              "the second time, a new card each pass, its promise dropped (RSM6's review, Jonathan's decision of "
              "27/11)",
     _G, '    return bool((pair or {}).get("deferred") and (pair or {}).get("pair_only"))\n', "    return False\n"),
]
TESTS = {
    "M8113": f"{_P}test_a_perimeter_alone_refused_unread_is_put_back_once_at_the_next_pass",
    "M8114": f"{_P}test_the_note_ends_the_sentence_before_it",
    "M8115": f"{_P}test_a_merged_entry_whose_writes_all_failed_puts_both_back_once",
    "M8116": f"{_P}test_the_skip_card_closes_once_the_vm_is_lifted",
    "M8117": f"{_P}test_the_skip_card_closes_at_the_first_read_after_a_restart",
    "M8118": f"{_P}test_the_skip_card_closes_at_the_first_read_after_a_restart",
    "M8119": f"{_P}test_the_skip_card_stays_while_a_state_is_unreadable",
    "M8120": f"{_P}test_a_lifted_vm_skipped_again_counts_from_one",
    "M8129": f"{_P}test_a_lock_that_raises_an_oserror_never_closes_the_card_as_lifted",
    "M8130": f"{_P}test_a_vm_read_while_another_state_is_unreadable_has_its_card_closed_as_read",
    "M8131": f"{_P}test_a_merged_entry_unspent_put_back_in_part_says_its_rules_written_once",
    "M8132": f"{_P}test_a_card_acknowledged_during_the_pass_is_never_closed_again",
    "M8133": f"{_P}test_a_deferred_pair_refused_unread_again_stays_deferred_until_the_read_passes",
}
