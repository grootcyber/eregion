"""JUG1 (#760): a disruptive action Glorfindel takes alone, once verified, makes one card to judge —
TO JUDGE, the indicator of the disruptive actions taken wrongly —, one per action after a restart
too, nothing to approve on it; its announcement in the VM's thread when the bot is configured, by
the webhook otherwise, never both; the console opens a line of TO JUDGE and shows every card of a
folded tile. M4910–M4929. Measured by tests/unit/test_judge_card.py and
tests/unit/test_judge_console.py."""
AGENT = "glorfindel/agent.py"
ESC = "glorfindel/escalations.py"
BOT = "glorfindel/bot.py"
GJS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_judge_card.py"
_C = "tests/unit/test_judge_console.py"

MUTANTS = [
    ("M4910", "an autonomous isolation verified leaves no card: the bench of 12/11 back, TO JUDGE empty, the "
     "indicator blind to it (JUG1)", AGENT,
     "            card = _record_executed(state, source, exercise_run)\n",
     '            card = ""\n'),
    ("M4911", "a snapshot or a release makes a card to judge: what disrupts nothing counted among the "
     "disruptive actions (JUG1)", AGENT,
     "    if (action not in _EXECUTED_ACTIONS or state.get(\"dry_run\") or state.get(\"escalate\")\n",
     "    if (state.get(\"dry_run\") or state.get(\"escalate\")\n"),
    ("M4912", "the note given in the opened card is lost: the verdict recorded without its why (JUG1)", GJS,
     "  judgeFromModal(id, verdict) { judgeCard(id, verdict, 'judge-modal-note'); closeModal(); },\n",
     "  judgeFromModal(id, verdict) { judgeCard(id, verdict); closeModal(); },\n"),
    ("M4913", "the action's key never read: the same action replayed after a restart makes a second card "
     "once the first is acknowledged (JUG1)", ESC,
     "            if isinstance(e, dict) and action_key in _keys_of(e):\n",
     "            if False:\n"),
    ("M4914", "a card forgets the action it stands for: a replay after a restart makes a second card (JUG1)",
     ESC,
     '        esc["action_keys"] = [action_key]\n',
     "        pass\n"),
    ("M4915", "a second action folded into the first one's card: judged and counted once for two (JUG1)",
     ESC,
     "                and escalation_type != EXECUTED_TYPE\n",
     ""),
    ("M4916", "without the bot, the card's own notification speaks too: the action said twice in the "
     "channel (JUG1)", ESC,
     "    if esc.get(\"escalation_type\") == EXECUTED_TYPE:\n"
     "        return      # JUG1: the action's announcement says it, once (notify_action) — never twice\n",
     ""),
    ("M4917", "the announcement's key dropped: said again for the same action after a restart (JUG1)", ESC,
     '        return vm_notices.say(resource_id, key or f"action:{uuid.uuid4()}", EXECUTED_TYPE, title, text,\n',
     '        return vm_notices.say(resource_id, f"action:{uuid.uuid4()}", EXECUTED_TYPE, title, text,\n'),
    ("M4918", "the notices' store refused, the bot configured: the announcement goes to the channel by the "
     "webhook (JUG1)", ESC,
     '        if discord_bot_configured() or not os.environ.get("GLORFINDEL_WEBHOOK_URL", ""):\n',
     '        if not os.environ.get("GLORFINDEL_WEBHOOK_URL", ""):\n'),
    ("M4919", "the notices' store refused, no bot: the autonomous action announced nowhere (JUG1)", ESC,
     '        vm_notices.post_webhook(payload, key)\n        return "webhook"\n',
     '        return "none"\n'),
    ("M4920", "the announcement never names the card to judge (JUG1)", ESC,
     '    card_said = f"Carte à juger : {card[:8]} (console, TO JUDGE)." if card else ""\n',
     '    card_said = ""\n'),
    ("M4921", "the card does not say the mode the action was taken in (JUG1)", AGENT,
     '    mode = state.get("autonomy_mode", "") or "?"\n',
     '    mode = "?"\n'),
    ("M4922", "the card keeps none of the evidence the action was taken on (JUG1)", AGENT,
     '"evidence": _evidence(signal),',
     '"evidence": [],'),
    ("M4923", "Discord says « Recommandé … (non exécuté) » of an action that ran and held (JUG1)", BOT,
     "    if etype == esc_module.EXECUTED_TYPE:\n"
     "        # JUG1: it ran alone and its check held — said done, to judge.\n",
     "    if False:\n"),
    ("M4924", "Discord says « Pourquoi rien n'est exécuté » on an action that ran, without its mode nor its "
     "check (JUG1)", BOT,
     "    if isinstance(executed, dict):\n        fields += _executed_fields(executed, why)\n",
     "    if False:\n        fields += _executed_fields(executed, why)\n"),
    ("M4925", "the evidence of the row written raw in Discord: a name from outside pings @everyone or hides "
     "a link (SEC6, JUG1)", BOT,
     '            line = f"• {discord_text(x)}"\n',
     '            line = f"• {x}"\n'),
    ("M4926", "a line of TO JUDGE does not open: its card is read only in Discord (bench, 12/11, JUG1)", GJS,
     "id=\"judge-${id}\" ${_on('click', 'openJudgeCard', c.id)} title=\"Open the card\">",
     "id=\"judge-${id}\">"),
    ("M4927", "a tile folding several cards shows the first one's details only (bench, 12/11: « ×6 », "
     "JUG1)", GJS,
     "         ${group.map(g => _cardDetail(g, vmName, true)).join('')}`\n",
     "         ${_cardDetail(e, vmName, true)}`\n"),
    ("M4928", "the evidence of the row written raw into the console: a name from outside runs in it (XSS, "
     "JUG1)", GJS,
     "padding:1px 0 1px 8px\">• ${_attr(w)}</div>`",
     "padding:1px 0 1px 8px\">• ${w}</div>`"),
    ("M4929", "TO JUDGE carries neither the card's steps nor what the action did: an acknowledged card "
     "opens empty (JUG1)", ESC,
     '            "suggested_steps", "executed", "run_id", "signal_id")}\n',
     '            "run_id", "signal_id")}\n'),
]
TESTS = {**{mid: _T for mid in ("M4910", "M4911", "M4913", "M4914", "M4915", "M4916", "M4917", "M4918",
                                 "M4919", "M4920", "M4921", "M4922", "M4923", "M4924", "M4925")},
         **{mid: _C for mid in ("M4912", "M4926", "M4927", "M4928", "M4929")}}
