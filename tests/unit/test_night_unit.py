"""NOC1 (#1251): the night's Orchestre, prepared and never installed — its systemd --user unit and timer,
install.sh, its deny rules, the make targets, and the patch of the nightly mutation that Jonathan applies
(scripts/night/; docs/sessions.md, « La nuit »). Read only: nothing here runs install.sh, systemctl or claude."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
NIGHT = ROOT / "scripts" / "night"
SERVICE = (NIGHT / "eregion-night.service").read_text(encoding="utf-8")
TIMER = (NIGHT / "eregion-night.timer").read_text(encoding="utf-8")
INSTALL = (NIGHT / "install.sh").read_text(encoding="utf-8")
SETTINGS = json.loads((NIGHT / "settings.json").read_text(encoding="utf-8"))


def _directives(text: str) -> dict[str, list[str]]:
    """Each `Key=value` of a unit, continuation lines joined, comments aside."""
    out: dict[str, list[str]] = {}
    joined = re.sub(r"\\\n\s*", " ", text)
    for line in joined.splitlines():
        if line.startswith(("#", "[")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), []).append(value.strip())
    return out


def test_the_service_runs_one_pass_of_elrond_night_headless_at_the_repository_s_root():
    d = _directives(SERVICE)
    (start,) = d["ExecStart"]
    assert d["Type"] == ["oneshot"] and d["WorkingDirectory"] == ["@REPO@"]
    assert start.startswith("/usr/bin/flock -n %h/.local/state/eregion-night/lock @CLAUDE@ -p \"/elrond night\" ")
    for part in ("--permission-mode @MODE@", "--permission-prompts none", "--model claude-opus-5-5",
                 "--settings @REPO@/scripts/night/settings.json", "--max-budget-usd @BUDGET@"):
        assert part in start, part
    assert "--no-session-persistence" not in start          # palantir reads the transcripts
    assert d["NoNewPrivileges"] == ["yes"] and d["TimeoutStartSec"] == ["5h"]
    assert d["Environment"][0] == "PATH=@PATH@"


def test_never_bypass_permissions_anywhere_the_night_is_written():
    # the units' directives (their comments say why it is never there) and the deny rules
    for text in (json.dumps(_directives(SERVICE)), json.dumps(_directives(TIMER)), json.dumps(SETTINGS)):
        assert "bypassPermissions" not in text and "dangerously" not in text and "skip-permissions" not in text
    # install.sh names it once, to refuse it: its modes are auto and dontAsk, nothing else
    assert re.search(r"^\s+auto\|dontAsk\) ;;$", INSTALL, re.M)
    assert "dangerously" not in INSTALL
    assert INSTALL.count("bypassPermissions") == 2 and "never bypassPermissions" in INSTALL


def test_the_timer_is_at_05_30_utc_after_main_s_night_workflows_and_never_caught_up_at_boot():
    d = _directives(TIMER)
    assert d["OnCalendar"] == ["*-*-* 05:30:00 UTC"] and d["Persistent"] == ["false"]
    assert d["Unit"] == ["eregion-night.service"] and d["WantedBy"] == ["timers.target"]
    for wf in ("ci.yml", "invariants.yml", "mutants-night.yml"):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8"))
        for entry in (doc.get("on") or doc.get(True))["schedule"]:      # PyYAML reads `on:` as True
            minute, hour = (int(x) for x in entry["cron"].split()[:2])
            assert hour * 60 + minute < 5 * 60 + 30, (wf, entry)


def test_install_refuses_in_an_agent_session_and_in_a_lot_s_worktree_and_parses():
    assert 'EREGION_AGENT_SESSION:-' in INSTALL and "*/.claude/worktrees/*)" in INSTALL
    assert "install) guard; install_units ;;" in INSTALL and "uninstall) guard; uninstall_units ;;" in INSTALL
    assert 'if [ "${DRY_RUN:-}" = 1 ]' in INSTALL
    assert subprocess.run(["bash", "-n", str(NIGHT / "install.sh")], capture_output=True).returncode == 0
    for placeholder in ("@REPO@", "@CLAUDE@", "@MODE@", "@BUDGET@", "@PATH@"):
        assert placeholder in INSTALL, placeholder
    assert set(re.findall(r"@[A-Z]+@", SERVICE + TIMER)) <= {"@REPO@", "@CLAUDE@", "@MODE@", "@BUDGET@", "@PATH@"}


def test_the_deny_rules_hold_the_gestures_left_to_jonathan():
    assert set(SETTINGS) == {"permissions"} and set(SETTINGS["permissions"]) == {"deny"}
    deny = set(SETTINGS["permissions"]["deny"])
    for rule in ("Bash(git push --force *)", "Bash(git push * --force *)", "Bash(git push * main)",
                 "Bash(git tag *)", "Bash(gh release create *)", "Bash(gh release edit *)", "Bash(gh workflow *)",
                 "Bash(terraform *)", "Bash(az *)", "Bash(ssh *)", "Bash(sudo *)", "Bash(make imladris-*)",
                 "Bash(make orodruin-*)", "Bash(make celebrimbor-*)", "Bash(make night-*)", "Bash(claude *)",
                 "Read(./.envrc)", "Read(**/host.env)", "Read(~/.config/eregion/**)",
                 "Read(~/.config/eregion-agents/**)", "Read(~/.config/gh/**)", "Edit(~/.claude/settings.json)",
                 "Edit(./.github/workflows/**)", "Edit(./scripts/night/**)"):
        assert rule in deny, rule
    assert not any(r.startswith(("Bash(gh pr merge", "Bash(make release", "Bash(git push -u")) for r in deny)


def test_the_make_targets_only_call_install_sh():
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target, verb in (("night-install", "install"), ("night-uninstall", "uninstall"), ("night-status", "status")):
        recipe = re.search(rf"^{target}:\n((?:\t.*\n)+)", make, re.M)
        assert recipe and recipe.group(1) == f"\t@bash scripts/night/install.sh {verb}\n", target
        assert target in make.split("# ── Help")[0], f"{target} not .PHONY"


def test_the_nightly_mutation_patch_applies_or_is_applied_and_never_lands_in_a_branch_of_the_app():
    patch = NIGHT / "mutants-nightly.patch"
    text = patch.read_text(encoding="utf-8")
    assert '+    - cron: "41 23 * * *"' in text and '-    - cron: "41 4 * * 1"' in text
    files = re.findall(r"^diff --git a/(\S+) b/", text, re.M)
    assert files[0] == ".github/workflows/mutants.yml" and "tests/unit/test_workflows.py" in files
    forward = subprocess.run(["git", "-C", str(ROOT), "apply", "--check", str(patch)], capture_output=True)
    backward = subprocess.run(["git", "-C", str(ROOT), "apply", "--check", "-R", str(patch)], capture_output=True)
    assert forward.returncode == 0 or backward.returncode == 0, (forward.stderr, backward.stderr)
