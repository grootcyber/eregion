"""SEC-A1 (#630, V-02, V-21): what Glorfindel and Annatar read of runs/ is read as the channel is
read (eregion_core/channel_reader.py) — the exercise windows, the signals `glorfindel respond`
reads, a campaign's manifest —, a local window is bounded in the past by its file's mtime, and the
windows chained on one VM by CHAIN_MAX_S. M4520–M4524. The review (M4563–M4566): the chain counted
on the watch's record, the window files bounded in number, the console's windows local in an
injector's directory, a JSON nested too deep refused.

Each caught by tests/unit/test_bounded_reads.py (M4565: tests/unit/test_console_exercises.py): a
read that blocks on a pipe fails there within seconds, never hangs the run.
"""
EXERCISE = "eregion_core/exercise.py"
SIGNALS = "glorfindel/signals.py"
MANIFEST = "annatar/campaign/manifest.py"
CONSOLE = "eregion_console/api.py"
_TESTS = "tests/unit/test_bounded_reads.py"

MUTANTS = [
    ("M4520", "the windows read by name again: a pipe stops the watch's loop, a link is followed (SEC-A1)",
     EXERCISE,
     '    data, st = read_regular(path, WINDOW_BYTES)\n'
     '    return json.loads(data.decode("utf-8")), datetime.fromtimestamp(st.st_mtime, timezone.utc)\n',
     '    return (json.loads(path.read_text(encoding="utf-8")),\n'
     '            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))\n'),
    ("M4521", "the signals `glorfindel respond` reads opened by name: a pipe blocks it, a link is followed (SEC-A1)",
     SIGNALS,
     '    for line in read_text(path).split("\\n"):',
     "    for line in open(path):"),
    ("M4522", "a campaign's manifest read by name: a pipe blocks the runner and the replay (SEC-A1)",
     MANIFEST,
     '        return cls.from_dict(read_json(Path(campaign_dir) / "manifest.json"))\n',
     '        return cls.from_dict(json.loads((Path(campaign_dir) / "manifest.json").read_text()))\n'),
    ("M4523", "a local window bounded toward the future only: written now, dated back, it is believed (SEC-A1)",
     EXERCISE,
     "    if declared_at is not None and (local or CHANNEL_CREATED not in window):\n",
     "    if False:\n"),
    ("M4524", "the windows on one VM chained without a bound: a VM stays in exercise for good (SEC-A1)",
     EXERCISE,
     "        if covered > CHAIN_MAX_S:\n",
     "        if False:\n"),
    ("M4563", "the chain counted on the files alone: deleted, a VM's spent windows count no more (SEC-A1)",
     EXERCISE,
     "        r: (s, last) for r, (targets, s, last) in _record_spans.items() if rid in targets}\n",
     "        r: (s, last) for r, (targets, s, last) in {}.items() if rid in targets}\n"),
    ("M4564", "every window file read at each read: a flood of files holds the watch's loop (SEC-A1)",
     EXERCISE,
     "    if len(paths) > MAX_WINDOW_FILES:",
     "    if False:"),
    ("M4565", "the console takes a channel_created in an injector's directory at its word (SEC-A1)",
     CONSOLE,
     '                out[-1]["refusal"] = window_refusal(w, now, declared, local=True)\n',
     '                out[-1]["refusal"] = window_refusal(w, now, declared, local=False)\n'),
    ("M4566", "a window nested too deep stops the read of every window (SEC-A1)",
     EXERCISE,
     "        except (OSError, ValueError, RecursionError) as e:\n",
     "        except (OSError, ValueError) as e:\n"),
]
TESTS = {**{mid: _TESTS for mid in ("M4520", "M4521", "M4522", "M4523", "M4524", "M4563", "M4564", "M4566")},
         "M4565": "tests/unit/test_console_exercises.py"}
