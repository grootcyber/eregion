"""HY2c (#800): the guard of an agent session's probes (HY2b) covers the operator's real ~/.eregion and
~/.annatar too — the watch's key, the queue's service keys and registers, the analysis index (ChromaDB,
refused before it is opened), Annatar's shell — names the folder refused, and says leaving the worktree
to the operator alone, never as a way out for a probe. M5235–M5244, measured by
tests/unit/test_store_guard.py: probes in fresh interpreters over an operator simulated in tmp (its
system home a folder of tmp_path), never this workstation's.
"""
GUARD = "eregion_core/store_guard.py"
ANALYSIS = "analysis/campaign_report.py"
T = "tests/unit/test_store_guard.py::"
KEY = T + "test_an_agent_session_s_probe_never_draws_the_watch_s_key_in_the_operator_s_eregion"
ANNATAR = T + "test_an_agent_session_s_probe_never_writes_in_the_operator_s_annatar"
INDEX = T + "test_the_analysis_index_is_refused_before_chromadb_opens_it_in_the_operator_s_eregion"
PINNED = T + "test_the_operator_s_eregion_is_guarded_whatever_home_says"
WORKTREE = T + "test_from_a_worktree_the_way_out_is_said_to_the_operator_never_offered_to_the_probe"
OPERATOR_ONLY = T + "test_leaving_the_worktree_is_said_to_the_operator_alone_never_to_a_probe"
LINK = T + "test_a_key_published_by_a_link_or_a_file_replaced_is_a_write"
PLACED = T + "test_the_operator_s_eregion_and_annatar_are_placed_as_given_or_resolved_and_named"

MUTANTS = [
    ("M5235", "~/.eregion no longer guarded: an agent session's probe draws the watch's signing key, a "
              "service's key of the queue, its registers in the operator's folder (HY2c)", GUARD,
     'STORES = (STORE, ".eregion", ".annatar")\n', 'STORES = (STORE, ".annatar")\n'),
    ("M5236", "~/.annatar no longer guarded: a probe writes in the history of Annatar's shell (HY2c)", GUARD,
     'STORES = (STORE, ".eregion", ".annatar")\n', 'STORES = (STORE, ".eregion")\n'),
    ("M5237", "the folder refused no longer named: a write in ~/.eregion said as one in ~/.glorfindel "
              "(HY2c)", GUARD,
     "            return message(found[0], why, found[1])\n", "            return message(found[0], why)\n"),
    ("M5238", "leaving the worktree offered to the probe again as its way out (HY2c, the defect the review "
              "of HY2b found)", GUARD,
     '    operator = OPERATOR_ONLY if why == WORKTREE_CWD else ""\n',
     '    operator = " ou lance la commande hors du worktree" if why == WORKTREE_CWD else ""\n'),
    ("M5239", "the advice to the operator said for every reason: a probe of an agent session (its variable, "
              "its code) is told of leaving the worktree, which it never may (HY2c)", GUARD,
     '    operator = OPERATOR_ONLY if why == WORKTREE_CWD else ""\n',
     '    operator = OPERATOR_ONLY if why else ""\n'),
    ("M5240", "the analysis index no longer checked: an agent session opens ChromaDB in the operator's "
              "~/.eregion/analysis/chroma, its store written from Rust, unseen (HY2c)", ANALYSIS,
     "    store_guard.check(p)\n", ""),
    ("M5241", "the analysis index checked once ChromaDB has opened it: its sqlite already written in the "
              "operator's ~/.eregion when the refusal comes (HY2c)", ANALYSIS,
     "    store_guard.check(p)\n    p.mkdir(parents=True, exist_ok=True)\n"
     "    return chromadb.PersistentClient(path=str(p)).get_or_create_collection(\n",
     "    p.mkdir(parents=True, exist_ok=True)\n"
     "    _c = chromadb.PersistentClient(path=str(p))\n"
     "    store_guard.check(p)\n"
     "    return _c.get_or_create_collection(\n"),
    ("M5242", "a link no longer a write: the watch's key, drawn apart, published into ~/.eregion by "
              "os.link, passes (HY2c)", GUARD,
     '    "os.link": ((1,), (2, 3)),\n', ""),
    ("M5243", "the operator's home taken from HOME, not from the system: a probe with a throwaway HOME "
              "writes the operator's ~/.eregion by its path (HY2c)", GUARD,
     "        return Path(pwd.getpwuid(os.getuid()).pw_dir)\n",
     '        return Path(os.path.expanduser("~"))\n'),
    ("M5244", "~/.eregion and ~/.annatar guarded as given only, never resolved: a write through the "
              "resolved home passes (HY2c)", GUARD,
     "        roots += [given, os.path.realpath(given)]\n", "        roots += [given]\n"),
]
TESTS = {
    "M5235": KEY,
    "M5236": ANNATAR,
    "M5237": KEY,
    "M5238": WORKTREE,
    "M5239": OPERATOR_ONLY,
    "M5240": INDEX,
    "M5241": INDEX,
    "M5242": LINK,
    "M5243": PINNED,
    "M5244": PLACED,
}
