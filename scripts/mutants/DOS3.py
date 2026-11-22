"""DOS3 (#1043): the dossier of an isolation, step 0 — its local facts, its file, its scope (Q2), its
ceiling (Q9) and its retention (Q7), apart from the signal, the memory and the model
(glorfindel/dossier.py, glorfindel/dossier_local.py). M6980–M6983: an unreadable source written
empty; the dossier in the signal; a cycle out of scope composed; the file written through a link. And,
from its review, M7075–M7077: a VM isolated again taken for lifted (its first dossier removed while it is
in quarantine); store_cycle calling every cycle one of the data plane; the ceiling's lock removed.
Measured by tests/unit/test_dossier.py."""
AGENT = "glorfindel/agent.py"
DOSSIER = "glorfindel/dossier.py"
LOCAL = "glorfindel/dossier_local.py"
_T = "tests/unit/test_dossier.py"

MUTANTS = [
    ("M6980", "an unreadable store of cards written empty: « no past card » where none could be read (DOS3)",
     LOCAL,
     '        return fact("F3c", "past_cards", etat=ILLISIBLE, dit="cartes passées non lues",\n'
     '                    pourquoi=f"le magasin des cartes ne se lit pas : {_first_line(exc)}", **common)\n',
     '        return fact("F3c", "past_cards", etat=VIDE, dit="0 carte(s)", **common)\n'),
    ("M6981", "the dossier in the signal: the signal reaches the model through _build_user_message (DOS3)",
     DOSSIER,
     "            _write(path, doc)\n        return path.name\n",
     '            _write(path, doc)\n        signal["dossier"] = path.name\n        return path.name\n'),
    ("M6982", "a cycle out of scope composed: a control-plane or identity cycle gets a dossier (DOS3)", DOSSIER,
     '    if state.get("dry_run") or not data_plane:\n',
     '    if state.get("dry_run"):\n'),
    ("M6983", "the dossier's file written through a link in its place: what it points to rewritten (DOS3)",
     DOSSIER,
     "    _atomic_write_text(path, json.dumps(doc, indent=1, sort_keys=True, default=str))\n",
     "    path.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str))\n"),
    ("M7075", "a VM isolated again while isolated taken for lifted: its first dossier removed 30 days later, "
     "the VM still in quarantine (DOS3)", DOSSIER,
     "        if at is not None and at >= since:\n",
     "        if at is not None and at == since:\n"),
    ("M7076", "store_cycle calls every cycle one of the data plane: a cycle of the control plane or of an "
     "identity gets a dossier (DOS3)", AGENT,
     "    data_plane = not (_is_control_plane(signal) or _is_identity(signal))\n",
     "    data_plane = True\n"),
    ("M7077", "the ceiling's lock removed: the VMs' threads each count the hour before any writes, and more "
     "than the ceiling compose (DOS3)", DOSSIER,
     "        with _LOCK:\n            _own_dir()\n",
     "        with threading.Lock():\n            _own_dir()\n"),
]
TESTS = {
    "M6980": f"{_T}::test_a_store_that_cannot_be_read_is_unreadable_never_empty",
    "M6981": f"{_T}::test_the_dossier_never_enters_the_signal "
             f"{_T}::test_a_cycle_with_its_dossier_leaves_the_message_to_the_model_unchanged_to_the_byte",
    "M6982": f"{_T}::test_a_cycle_of_the_control_plane_or_an_identity_has_none",
    "M6983": f"{_T}::test_the_file_is_never_written_through_a_link",
    "M7075": f"{_T}::test_a_vm_isolated_again_while_isolated_keeps_this_dossier",
    "M7076": f"{_T}::test_store_cycle_of_the_control_plane_or_an_identity_writes_no_dossier",
    "M7077": f"{_T}::test_the_ceiling_holds_with_more_threads_than_it",
}
