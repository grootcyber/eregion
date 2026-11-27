"""The bot's verdict buttons (observation, docs/observation.md) — out of glorfindel/bot.py (WCH1: no button
added there), with VRD1's finer verdict (#1285).

A decision card's message carries ✓ Right, ✗ False alarm, ✗ Too strong — only on a card that made a gesture
(glorfindel/verdict_cause.py) — and ? Unsure: a « wrong » says its cause, the one clicked, never another.
Each button writes as the console's does (`escalations.set_verdict`, in the bot's own store, as before VRD1:
one path, no request signed), then the card is acknowledged and its buttons greyed (`bot._judged`).

**A message posted before VRD1** carries ✗ Wrong (``glorfindel_verdict_wrong_<id>``). The view a restarted
bot gives it back (`buttons(…, legacy=True)`, `GlorfindelBot._restore_views`) keeps that button, unseen —
a view given back to a message only listens, it draws nothing until a click: a click on ✗ Wrong writes a
« wrong » without a cause, as it did, never « interaction failed ». A limit (the relecture of VRD1): the first
click on a message given back greys the whole view it was given, its unseen buttons drawn too. The next edit of the message (its card's state changed)
draws the buttons of today. The signature of a card (`bot._card_signature`) is the one of before: no
message is edited for VRD1 alone.
"""
from __future__ import annotations

import discord

from glorfindel import escalations as esc_module, verdict_cause
from glorfindel.chat_text import discord_text

# What a button says — by what it writes: a verdict, or a « wrong » with its cause.
WORDS = {"right": "✓ Right", "wrong": "✗ Wrong", "unsure": "? Unsure",
         verdict_cause.FALSE_ALARM: "✗ False alarm", verdict_cause.TOO_STRONG: "✗ Too strong"}
PREFIX = "glorfindel_verdict_"        # a judge's button (bot._JUDGE_PREFIX): greyed once the card is judged


class VerdictButton(discord.ui.Button):
    """The observation's verdict, from Discord: was the recommendation right — and, wrong, why (VRD1).
    Independent of the ack, like in the War Room. ``cause``: the one this button writes, "" for none."""

    def __init__(self, esc: dict, verdict: str, style: discord.ButtonStyle, cause: str = "") -> None:
        what = cause or verdict
        super().__init__(label=WORDS[what], style=style, custom_id=f"{PREFIX}{what}_{esc['id'][:8]}", row=2)
        self.esc = esc
        self.verdict = verdict
        self.cause = cause

    async def callback(self, interaction: discord.Interaction) -> None:
        from glorfindel.bot import _judged, _masked
        try:
            esc_module.set_verdict(self.esc["id"], self.verdict, "", cause=self.cause or None)
        except (KeyError, ValueError) as exc:
            await interaction.response.send_message(f"✗ {discord_text(_masked(exc, self.esc))}", ephemeral=True)
            return
        await _judged(self, interaction,
                      f"{WORDS[self.cause or self.verdict]} — jugé par **{discord_text(interaction.user.display_name)}**")


def buttons(esc: dict, legacy: bool = False) -> list[VerdictButton]:
    """A decision card's verdict buttons: right, the false alarm, the action too strong after a gesture
    only, unsure. ``legacy``: the view given back to a posted message also listens to the ✗ Wrong of
    before VRD1 (a « wrong » without a cause)."""
    out = [VerdictButton(esc, "right", discord.ButtonStyle.success),
           VerdictButton(esc, "wrong", discord.ButtonStyle.danger, verdict_cause.FALSE_ALARM)]
    if verdict_cause.gesture(esc.get("action")):
        out.append(VerdictButton(esc, "wrong", discord.ButtonStyle.danger, verdict_cause.TOO_STRONG))
    out.append(VerdictButton(esc, "unsure", discord.ButtonStyle.secondary))
    if legacy:
        out.append(VerdictButton(esc, "wrong", discord.ButtonStyle.danger))
    return out


def causes_said(disruptive: dict) -> str:
    """The Monday summary's split of the disruptive ones judged wrong (VRD1), in the words of `glorfindel
    report`: « (1 false alarm · 2 too strong · 0 cause unsaid) » — both count in the rate; "" when none is
    judged wrong, or a report of before."""
    c = disruptive.get("causes") if isinstance(disruptive, dict) else None
    if not isinstance(c, dict) or not any(type(v) is int and v > 0 for v in c.values()):
        return ""
    return f" ({verdict_cause.counts_said(c)})"
