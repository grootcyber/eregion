"""The watch (WCH1, #1019): `glorfindel watch`'s loop, out of glorfindel/cli.py — its state in objects,
each part reachable alone by a test. Nothing changed in what it does: the same lines said, the same
signals and threads, in the same order.

  loop.py          Watch: the startup in its order, one tick of the loop, the loop until Ctrl+C
  startup.py       what it says and checks before its loop: logs, config, TTL, autonomy, identity,
                   the signed action queue, the return channel, its own writes set aside
  runs_channel.py  runs/ read as an input it does not trust: a line parsed, admitted or refused;
                   the channel's bounds (SEC8) and its rate
  dispatch.py      a detection to its VM's queue, the queue's thread: shown, decided, its decision shown
  housekeeping.py  every minute: TTL, jobs, reassertion, recoveries, the door's facts, the notices,
                   the windows, the verdicts, the drill; « Verify » every 5 polls
  dossier_tasks.py the dossiers' part of the housekeeping: retention, reads of Azure, budgets (WCH2)
  local_reads.py   its local part: the windows, the verdicts, the drill, the view « Relaxed » (WCH2)
  passes.py        the passes over Azure, each in a thread of its own, one at a time (Solo)
  beat.py          the heartbeats, the watch's and the injectors' signed copy; their directory
  rules.py         the detection rules: loaded, polled, expanded on discovery; the startup audit

`glorfindel watch` (glorfindel/cli.py) stays the command: it hands its console and the CLI's own
displays (a signal's head, a decision) to `loop.run`. tests/unit/test_file_sizes.py holds every
function here to a few dozen lines.
"""
