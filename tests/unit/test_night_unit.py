"""NOC1 (#1251): the night's Orchestre, prepared and never installed — its systemd --user unit and timer,
install.sh, its deny rules, the make targets, and the patch of the nightly mutation that Jonathan applies
(scripts/night/; docs/sessions.md, « La nuit »). Read only: nothing here runs install.sh, systemctl or claude."""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path

import pytest
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


RULE = re.compile(r"^(Bash|Read|Edit|Write)\((.+)\)$")


def _denied(command: str) -> list[str]:
    """The Bash deny rules a command matches, read as shell globs (`*` any run of characters): an
    approximation of Claude Code's own matching, enough to see a hole or a rule too wide."""
    return [r for r in SETTINGS["permissions"]["deny"]
            if (m := RULE.match(r)) and m.group(1) == "Bash" and fnmatch.fnmatchcase(command, m.group(2))]


def test_the_settings_load_and_every_rule_has_the_form_tool_of_pattern():
    """Claude Code ignores, without a word in -p, a settings file it cannot read: the JSON loads, it holds
    deny rules only, each `Tool(pattern)`, none twice."""
    assert set(SETTINGS) == {"permissions"} and set(SETTINGS["permissions"]) == {"deny"}
    deny = SETTINGS["permissions"]["deny"]
    assert deny and all(isinstance(r, str) and RULE.match(r) for r in deny), [r for r in deny if not RULE.match(r)]
    assert len(deny) == len(set(deny))


@pytest.mark.parametrize("command", [
    "git push --force origin lot/x", "git -C /repo/.claude/worktrees/x push --force origin lot/x",
    "git push -f origin lot/x", "git push origin +lot/x", "git push origin x:main",
    "git push origin HEAD:refs/heads/main", "git -C /repo push origin HEAD:main", "git push origin main",
    "git push origin v0.6.12", "git push origin refs/tags/v0.6.12", "git push --tags", "git tag v0.6.12",
    "git -C /repo tag v0.6.12",
    "gh release create v0.6.12 --notes x", "gh release edit v0.6.12 --draft=false", "gh workflow run release-gate.yml",
    "gh run rerun 123", "gh api repos/o/r/rulesets -X POST", "gh api -X DELETE repos/o/r/git/refs/tags/v1",
    "gh api --method PATCH repos/o/r", "gh api repos/o/r/issues -f title=x", "gh api graphql -f query=x",
    "gh pr merge 12 --admin --squash", "terraform apply", "az vm list", "ssh imladris", "sudo true",
    "systemctl --user start eregion-night.service", "claude -p x", "make imladris-start REF=v1",
    "make celebrimbor-up YES=1", "make night-install", "make llm-compare",
    "python3 scripts/llm_smoke.py", "annatar run x", "gothmog run x", "glorfindel watch", "python -m annatar run x",
    "cat .envrc", "source ~/eregion/.envrc", "cat infra/glorfindel-host/host.env", "cat ~/.claude/.credentials.json",
    "ls ~/.config/eregion-agents", "cat ~/.config/gh/hosts.yml",
    "python3 scripts/roadmap_discord.py publish", "python3 scripts/bench_reader.py x",
])
def test_a_gesture_left_to_jonathan_is_denied(command):
    assert _denied(command), command


@pytest.mark.parametrize("command", [
    "gh pr merge 12 --squash --match-head-commit 0123456789abcdef0123456789abcdef01234567",
    "git push -u origin lot/n1127a-mutant", "git -C /repo/.claude/worktrees/x push -u origin lot/n1127a-mutant",
    "make release VERSION=0.6.12 TITLE=\"the night, awake\"", "make release-draft VERSION=0.6.12",
    "python3 /tmp/night/night_guard.py check --repo /repo --base origin/main --head abc",
    "git show origin/main:scripts/night_guard.py", "gh pr comment 12 --body-file verdict.md",
    "gh pr view 12 --json headRefOid,comments", "gh pr checks 12", "gh issue create --title t --body-file b.md",
    "gh run list --branch main --event schedule --json databaseId,headSha", "gh run view 123 --json jobs",
    "gh run view 123 --log-failed", "git merge-base --is-ancestor abc origin/main",
    "rtk proxy python -m pytest tests/unit/test_glorfindel.py -n 4", "ruff check .",
    "python scripts/mutation_check.py --jobs 2 --only M1,M2", "python3 scripts/agents_discord.py run-end x",
    "git commit -q -F msg.txt", "git fetch origin", "make manuel",
])
def test_what_the_night_does_is_not_denied(command):
    assert not _denied(command), _denied(command)


def test_the_rails_and_the_secrets_are_denied_to_the_file_tools_in_a_worktree_too():
    deny = set(SETTINGS["permissions"]["deny"])
    for rule in ("Read(./.envrc)", "Read(**/.envrc)", "Read(**/host.env)", "Read(~/.config/eregion/**)",
                 "Read(~/.config/eregion-agents/**)", "Read(~/.config/gh/**)", "Read(~/.claude/.credentials.json)",
                 "Edit(~/.claude/settings.json)", "Edit(**/.github/workflows/**)", "Edit(**/scripts/night/**)",
                 "Edit(**/scripts/night_guard.py)", "Edit(**/scripts/review_verdict.py)", "Edit(**/.claude/skills/**)",
                 "Edit(**/.claude/agents/**)"):
        assert rule in deny, rule


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
    # the workflow and its test only: a PR that moves the docs' context never turns this red (the review)
    only = ["--include=.github/workflows/mutants.yml", "--include=tests/unit/test_workflows.py"]
    forward = subprocess.run(["git", "-C", str(ROOT), "apply", "--check", *only, str(patch)], capture_output=True)
    backward = subprocess.run(["git", "-C", str(ROOT), "apply", "--check", "-R", *only, str(patch)],
                              capture_output=True)
    assert forward.returncode == 0 or backward.returncode == 0, (forward.stderr, backward.stderr)
