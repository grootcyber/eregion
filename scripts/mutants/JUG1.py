"""JUG1 (#760): a disruptive action Glorfindel takes alone, once verified, makes one card to judge —
TO JUDGE, the indicator of the disruptive actions taken wrongly —, one per action after a restart
too, nothing to approve on it; its announcement in the VM's thread when the bot is configured, by
the webhook otherwise, never both; the console opens a line of TO JUDGE and shows every card of a
folded tile. M4910–M4929; the review, and the card's ping in the VM's thread (Jonathan, 12/11):
M4940–M4946. Measured by tests/unit/test_judge_card.py and
tests/unit/test_judge_console.py."""
AGENT = "glorfindel/agent.py"
ESC = "glorfindel/escalations.py"
BOT = "glorfindel/bot.py"
GJS = "eregion_console/static/glorfindel.js"
PLAN = "glorfindel/restore_plan.py"
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
     # JUG2: its anchors follow the fallback's code (the key drawn once, the bot alive or mute).
     '    key = key or f"action:{uuid.uuid4()}"\n',
     '    key = f"action:{uuid.uuid4()}"\n'),
    ("M4918", "the notices' store refused, the bot configured and the card written: the action said in "
     "the channel too, the bot posting its card in the thread (JUG1)", ESC,
     '        if bot and card and not why:\n            return "none"\n',
     ""),
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
# The review (round 1) and Jonathan's answer on the ping (12/11): M4940–M4946.
MUTANTS += [
    ("M4940", "a full disk with the bot configured: neither card nor notice written, and the webhook "
     "silent — the action alerts nowhere (JUG1 review)", ESC,
     '        if bot and card and not why:\n',
     '        if bot and not why:\n'),
    ("M4941", "the card of an action taken alone pings nobody: a VM whose thread is open isolated in "
     "silence (JUG1, Jonathan 12/11)", BOT,
     '            ping = ({"content": f"<@&{self.ping_role}>", "allowed_mentions": self._role_mentions()}\n'
     '                    if self.ping_role and not vm_notices.relayed_ping(esc.get("action_keys")) else {})\n',
     "            ping = {}\n"),
    ("M4942", "the role pinged twice for one action: the thread opened with « Incident opened », then the "
     "card's ping (JUG1)", BOT,
     "            thread = await self._get_or_create_thread(channel, _thread_key(esc), ping=False)\n",
     "            thread = await self._get_or_create_thread(channel, _thread_key(esc))\n"),
    ("M4943", "the card's ping mentions everyone and every user, not the role alone (JUG1)", BOT,
     "        return discord.AllowedMentions(everyone=False, users=False, replied_user=False, roles=[\n",
     "        return discord.AllowedMentions(everyone=True, users=True, replied_user=False, roles=[\n"),
    ("M4944", "two identity cards on their tile: each one's plan and its « Verify » gone (IR1a, JUG1 "
     "review)", GJS,
     "  const rest = own ? `${e.identity_plan ? _identityPlan(e) : _cardSteps(e)}${_cardQuery(e)}` : '';\n",
     "  const rest = own ? _cardSteps(e) : '';\n"),
    ("M4945", "`glorfindel restore` without --before takes its moment from the card of an action taken "
     "alone: a VM isolated alone restored with no moment given (SEC4c, JUG1 review)", PLAN,
     '        cards = [e for e in cards if e.get("escalation_type") != escalations.EXECUTED_TYPE]\n',
     ""),
    ("M4946", "an action taken alone grouped with a held card: the group's Ack acknowledges the card to "
     "judge unread (JUG1 review)", GJS,
     "    const kind = _isExecuted(e) ? `executed|${origin}` : origin;\n",
     "    const kind = origin;\n"),
]
TESTS = {**{mid: _T for mid in ("M4910", "M4911", "M4913", "M4914", "M4915", "M4916", "M4917", "M4918",
                                 "M4919", "M4920", "M4921", "M4922", "M4923", "M4924", "M4925")},
         **{mid: _T for mid in ("M4940", "M4941", "M4942", "M4943", "M4945")},
         **{mid: _C for mid in ("M4912", "M4926", "M4927", "M4928", "M4929", "M4944", "M4946")}}
