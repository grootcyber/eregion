"""ROT3 (#1170): a pair's secret, or the console's token, renewed after a reminder left is confirmed once by
Imladris's CD in #deploy, in green, under the reminder it answers — a later end only, never the first date
nor a nearer one; refused or without the webhook, tried again; status says « renouvelé le … ».
M7516–M7525 and M7531–M7535, measured by tests/unit/test_pair_rotate.py and tests/unit/test_console_rotate.py."""
CD = "infra/glorfindel-host/cd/eregion_cd.py"
_T = "tests/unit/test_pair_rotate.py"
_C = "tests/unit/test_console_rotate.py"

MUTANTS = [
    ("M7516", "a nearer end confirmed as a renewal: the pair said renewed while it ends sooner (ROT3)", CD,
     "    if before is None or not end > before:\n",
     "    if before is None or end == before:\n"),
    ("M7517", "a renewal confirmed though no reminder had left: noise in #deploy for a pair never reminded "
     "(ROT3)", CD,
     "    elif prev[\"sent\"]:\n",
     "    elif True:\n"),
    ("M7518", "the confirmation never counted sent: posted again at every pass of the timer (ROT3)", CD,
     " or ren.get(\"posted\") or ren.get(\"dropped\"):\n",
     " or ren.get(\"dropped\"):\n"),
    ("M7519", "the confirmation never saved: posted again at the next pass, and after a reboot (ROT3)", CD,
     "        save_reminders(doc)                   # said once, even after a reboot\n",
     "        pass\n"),
    ("M7520", "a confirmation Discord refused counted sent: never tried again, the stale reminder left alone "
     "in #deploy (ROT3)", CD,
     "    if not say(title, text, color=nd.GREEN):\n",
     "    if not say(title, text, color=nd.GREEN) and False:\n"),
    ("M7521", "without #deploy's webhook the confirmation counted sent: never posted once the webhook is "
     "there, never said (ROT3)", CD,
     "    if not hook:\n        return [f\"  rappels · {pair} : renouvellement non confirmé",
     "    if False:\n        return [f\"  rappels · {pair} : renouvellement non confirmé"),
    ("M7522", "a confirmation still waiting lost by a second rotation: the stale reminder never answered "
     "(ROT3)", CD,
     "    if isinstance(waiting, dict) and not waiting.get(\"posted\")",
     "    if False and isinstance(waiting, dict) and not waiting.get(\"posted\")"),
    ("M7523", "the console's token confirmed in a pair's words: « la paire « console-token » » (ROT3)", CD,
     "    if pair == CONSOLE_TOKEN:\n        # the CD sees a later day",
     "    if False:\n        # the CD sees a later day"),
    ("M7524", "status never says « renouvelé le … »: a confirmation sent shown with an unreadable day (ROT3)", CD,
     "(f\" ; renouvelé le {posted}\" if isinstance(posted, str)",
     "(f\" ; renouvelé le {posted}\" if False and isinstance(posted, str)"),
    ("M7525", "the confirmation pings Jonathan: good news with the mention, like a reminder (ROT3)", CD,
     "    if not say(title, text, color=nd.GREEN):\n",
     "    if not say(title, text, color=nd.GREEN, alert=True):\n"),
    ("M7531", "a full disk after the confirmation left: the OSError out of remind(), the confirmation posted "
     "at every pass and the pair's due tier skipped (ROT3)", CD,
     "    except OSError:\n        return [f\"  rappels · {pair} : {what}",
     "    except ZeroDivisionError:\n        return [f\"  rappels · {pair} : {what}"),
    ("M7532", "a confirmation still waiting past the new end posted: « renouvelé … (déjà passée) » beside "
     "« a expiré » (ROT3)", CD,
     "    if days_left < 0:\n        ren[\"dropped\"]",
     "    if False:\n        ren[\"dropped\"]"),
    ("M7533", "a dropped confirmation never counted dropped: its line in the journal at every pass (ROT3)", CD,
     " or ren.get(\"posted\") or ren.get(\"dropped\"):\n",
     " or ren.get(\"posted\"):\n"),
    ("M7534", "the confirmation's lines lost when the pair's tier leaves in the same pass: a full disk "
     "never said (ROT3)", CD,
     "            return lines                         # say() wrote it in the journal\n",
     "            return []                            # say() wrote it in the journal\n"),
    ("M7535", "status shows a confirmation day that does not read as it is (ROT3)", CD,
     "if isinstance(posted, str) and DAY_RE.fullmatch(posted)\n",
     "if posted\n"),
]
_DROPPED = f"{_T}::test_a_confirmation_still_waiting_when_the_new_end_has_passed_is_dropped_never_said"
_ONCE = f"{_T}::test_a_later_end_after_a_reminder_is_confirmed_once_in_green_and_status_says_renewed"
TESTS = {
    "M7516": f"{_T}::test_no_confirmation_for_a_nearer_end_nor_the_same",
    "M7517": f"{_T}::test_no_confirmation_when_no_reminder_had_left",
    "M7518": _ONCE,
    "M7519": _ONCE,
    "M7520": f"{_T}::test_a_confirmation_discord_refuses_is_tried_again_at_the_next_pass",
    "M7521": f"{_T}::test_without_the_webhook_the_confirmation_is_said_and_waits_for_it",
    "M7522": f"{_T}::test_a_confirmation_still_waiting_follows_a_second_rotation",
    "M7523": f"{_C}::test_the_token_turned_after_its_reminder_is_confirmed_once_with_its_own_words",
    "M7524": _ONCE,
    "M7525": _ONCE,
    "M7531": f"{_T}::test_a_disk_that_refuses_the_confirmation_s_state_is_said_and_the_tier_still_leaves",
    "M7532": _DROPPED,
    "M7533": _DROPPED,
    "M7534": f"{_T}::test_a_disk_that_refuses_the_confirmation_s_state_is_said_and_the_tier_still_leaves",
    "M7535": f"{_T}::test_a_confirmation_day_that_does_not_read_is_never_shown_as_it_is",
}
