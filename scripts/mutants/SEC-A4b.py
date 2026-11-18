"""SEC-A4b (#660): a proposed rule judged as soon as the model proposes it — one whose rows carry
neither `_ResourceId` nor `CallerIpAddress` as Azure wrote them is recorded unapprovable, with its
reason, and never enters the queue of proposals to approve; the routing key asked of the model in
the proposal prompt; the harness that measures the share of proposals carrying it. M5901–M5908,
measured by tests/unit/test_proposed_rules.py, test_detection_authoring.py and test_llm_smoke.py.
The approval's own refusal (defence in depth) stays M4543 (SEC-A4)."""
PROPOSED = "glorfindel/proposed_rules.py"
AUTHORING = "glorfindel/detection_authoring.py"
AGENT = "glorfindel/agent.py"
CLI = "glorfindel/cli.py"
SMOKE = "scripts/llm_smoke.py"
_P = "tests/unit/test_proposed_rules.py"
_A = "tests/unit/test_detection_authoring.py"
_S = "tests/unit/test_llm_smoke.py"

MUTANTS = [
    ("M5901", "the judgment at proposal removed: a rule routed by the host name recorded pending, "
     "approvable in appearance until its approval (SEC-A4b)", PROPOSED,
     "    refused = approval_refusal(source, query)\n",
     '    refused = ""\n'),
    ("M5902", "an unapprovable proposal back in the queue to approve: `glorfindel pending`, the "
     "console and the bot present it (SEC-A4b)", PROPOSED,
     '    out = [p for p in all_proposals() if p["status"] == "pending"\n'
     '           and not approval_refusal(p.get("source") or "", p.get("query") or "")]\n',
     '    out = [p for p in all_proposals() if p["status"] in ("pending", UNAPPROVABLE)]\n'),
    ("M5903", "a proposal left pending before the judgment at proposal, without the key, presented "
     "as approvable (SEC-A4b)", PROPOSED,
     '    out = [p for p in all_proposals() if p["status"] == "pending"\n'
     '           and not approval_refusal(p.get("source") or "", p.get("query") or "")]\n',
     '    out = [p for p in all_proposals() if p["status"] == "pending"]\n'),
    ("M5904", "the routing key no longer asked of the model that proposes rules (SEC-A4b)", AUTHORING,
     '""" + ROUTING_KEY_INSTRUCTION + """\n',
     '""" + """\n'),
    ("M5905", "the card of a missed detection offers an unapprovable rule: its proposal id, Approve "
     "in the console, approve-rule in its steps (SEC-A4b)", AGENT,
     "    if unapprovable:\n"
     "        # Said on the card, never offered:",
     "    if False:\n"
     "        # Said on the card, never offered:"),
    ("M5906", "an approval of an unapprovable proposal says « not found » instead of why (SEC-A4b)",
     PROPOSED,
     '        elif p["id"] == proposal_id and p["status"] == UNAPPROVABLE:\n',
     "        elif False:\n"),
    ("M5907", "`glorfindel propose-rules` offers approve-rule for an unapprovable proposal (SEC-A4b)",
     CLI,
     "            if refused:\n"
     '                console.print(f"  [dim]proposal {pid} — inscrite non approuvable, "\n',
     "            if False:\n"
     '                console.print(f"  [dim]proposal {pid} — inscrite non approuvable, "\n'),
    ("M5908", "the harness counts every proposal as carrying the key: no before/after to read "
     "(SEC-A4b)", SMOKE,
     '    return {"carries_key": not refusal, "error": None,',
     '    return {"carries_key": True, "error": None,'),
]
TESTS = {
    "M5901": f"{_P}::test_a_proposal_without_the_key_is_recorded_unapprovable_with_its_reason "
             f"{_P}::test_propose_rules_says_an_unapprovable_proposal_and_keeps_it_out_of_pending",
    "M5902": f"{_P}::test_a_proposal_without_the_key_is_recorded_unapprovable_with_its_reason",
    "M5903": f"{_P}::test_a_pending_proposal_recorded_before_the_judgment_never_enters_pending",
    "M5904": f"{_A}::test_the_proposal_prompt_asks_to_keep_the_routing_key_to_the_byte "
             f"{_A}::test_the_bullet_reaches_the_model_that_proposes_rules",
    "M5905": f"{_P}::test_the_propose_node_never_offers_an_unapprovable_rule",
    "M5906": f"{_P}::test_an_unapprovable_proposal_is_never_approved_and_says_why",
    "M5907": f"{_P}::test_propose_rules_says_an_unapprovable_proposal_and_keeps_it_out_of_pending",
    "M5908": f"{_S}::test_the_harness_measures_the_share_that_carries_the_key_before_and_after",
}
