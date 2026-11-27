"""NOC1 (#1251): the night's Orchestre, prepared and never installed — its systemd --user unit and timer,
install.sh, its deny rules, the make targets, and the patch of the nightly mutation that Jonathan applies
(scripts/night/; docs/sessions.md, « La nuit »). Nothing here runs systemctl or claude, nor install.sh but
under DRY_RUN=1, in a copy of scripts/night/ under tmp_path, with a disposable HOME, a fake claude and a
systemctl that only records (NOC1c): a dry run writes nothing and starts nothing."""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
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
    "gh pr merge 12 --admin --squash", "gh pr merge 12 --auto --squash", "terraform apply", "az vm list", "ssh imladris", "sudo true",
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
    "python3 /tmp/night/night_guard.py check --repo /repo --base origin/main --head abc --pr 12",
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


# NOC1c (#1276): the pass runs on the subscription, the CLI's claude.ai login, never on an API key. Claude
# Code's own order (code.claude.com/docs/en/authentication, « Authentication precedence »): a cloud provider
# (CLAUDE_CODE_USE_*), ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY, apiKeyHelper, CLAUDE_CODE_OAUTH_TOKEN, an
# Anthropic profile or federation, then the /login subscription. The profile named by ANTHROPIC_PROFILE and
# the federation variables rank above that login; CLAUDE_CODE_OAUTH_TOKEN is a subscription's token.
KEY_SOURCES = {
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_PROFILE", "ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_MANTLE",
    "CLAUDE_CODE_USE_ANTHROPIC_AWS", "CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD",
}


def test_the_unit_unsets_every_key_source_and_keeps_the_subscription_s_token():
    d = _directives(SERVICE)
    (unset,) = d["UnsetEnvironment"]                      # one line, which install.sh reads back
    names = unset.split()
    assert set(names) == KEY_SOURCES and len(names) == len(set(names)), names
    assert all("=" not in n for n in names)               # a bare name unsets whatever value it has
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in unset           # a subscription's login (claude setup-token)
    assert not any(e.split("=", 1)[0] in KEY_SOURCES for e in d["Environment"])


def _exe(path: Path, text: str = "#!/bin/sh\nexit 0\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def _night_copy(tmp_path: Path) -> tuple[Path, Path, Path]:
    """scripts/night/ copied under tmp_path (outside any worktree), a disposable HOME, and a bin whose
    systemctl only records that it was called."""
    repo, home, fakebin = tmp_path / "repo", tmp_path / "home", tmp_path / "bin"
    (repo / "scripts" / "night").mkdir(parents=True)
    for name in ("install.sh", "eregion-night.service", "eregion-night.timer"):
        shutil.copy(NIGHT / name, repo / "scripts" / "night" / name)
    home.mkdir()
    _exe(fakebin / "systemctl", f'#!/bin/sh\necho "$@" >> {tmp_path}/systemctl.called\n')
    return repo, home, fakebin


def _dry_run(tmp_path: Path, repo: Path, home: Path, fakebin: Path, *, claude_bin: Path | None = None,
             path_first: Path | None = None) -> subprocess.CompletedProcess:
    """install.sh install under DRY_RUN=1, its environment written whole: no EREGION_AGENT_SESSION, no key."""
    env = {"HOME": str(home), "DRY_RUN": "1", "LANG": "C.UTF-8",
           "PATH": os.pathsep.join(str(p) for p in (path_first, fakebin) if p) + ":/usr/bin:/bin"}
    if claude_bin:
        env["CLAUDE_BIN"] = str(claude_bin)
    out = subprocess.run(["bash", str(repo / "scripts" / "night" / "install.sh"), "install"], env=env,
                         capture_output=True, text=True, timeout=30)
    assert not (tmp_path / "systemctl.called").exists()     # a dry run starts nothing
    assert not (home / ".config").exists()                  # and writes nothing
    return out


def _line(out: subprocess.CompletedProcess, prefix: str) -> str:
    (line,) = [x for x in out.stdout.splitlines() if x.startswith(prefix)]
    return line[len(prefix):]


def test_install_s_dry_run_shows_the_unset_line(tmp_path):
    repo, home, fakebin = _night_copy(tmp_path)
    claude = _exe(home / ".local" / "bin" / "claude")
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=claude)
    assert out.returncode == 0, out.stderr
    assert set(_line(out, "UnsetEnvironment=").split()) == KEY_SOURCES
    assert "@CLAUDE@" not in out.stdout and f" {claude} -p " in out.stdout


def test_the_unit_s_path_names_each_directory_once_with_local_bin_first(tmp_path):
    repo, home, fakebin = _night_copy(tmp_path)
    claude = _exe(home / ".local" / "bin" / "claude")      # where the native installer puts it
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=claude)
    assert _line(out, "Environment=PATH=").split(":") == [f"{home}/.local/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    # claude elsewhere: its directory comes second, after ~/.local/bin, each once
    other = _exe(tmp_path / "opt" / "claude" / "bin" / "claude")
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=other)
    assert _line(out, "Environment=PATH=").split(":") == [f"{home}/.local/bin", str(other.parent),
                                                          "/usr/local/bin", "/usr/bin", "/bin"]
    # claude in /usr/bin (any executable stands for it in a dry run): /usr/bin kept once, in its first place
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=Path("/usr/bin/true"))
    assert _line(out, "Environment=PATH=").split(":") == [f"{home}/.local/bin", "/usr/bin", "/usr/local/bin", "/bin"]


@pytest.mark.parametrize("editor", [".vscode-server/extensions", ".vscode/extensions", ".cursor-server/extensions"])
@pytest.mark.parametrize("given", ["CLAUDE_BIN", "command -v", "a link"])
def test_claude_inside_an_editor_s_extension_is_said_under_dry_run(tmp_path, editor, given):
    repo, home, fakebin = _night_copy(tmp_path)
    inside = _exe(home / editor / "anthropic.claude-code-9.9.9-linux-x64" / "resources" / "native-binary" / "claude")
    if given == "CLAUDE_BIN":
        out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=inside)
    elif given == "command -v":
        out = _dry_run(tmp_path, repo, home, fakebin, path_first=inside.parent)
    else:                                                   # a stable link into the extension breaks too
        link = home / ".local" / "bin" / "claude"
        link.parent.mkdir(parents=True)
        link.symlink_to(inside)
        out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=link)
    assert out.returncode == 0, out.stderr                  # said, not refused: DRY_RUN=1
    assert "inside an editor's extension" in out.stderr and "DRY_RUN=1: said, not refused" in out.stderr
    assert "~/.local/bin/claude" in out.stderr and "[Service]" in out.stdout


def test_claude_installed_apart_is_not_said(tmp_path):
    repo, home, fakebin = _night_copy(tmp_path)
    version = _exe(home / ".local" / "share" / "claude" / "versions" / "9.9.9")
    link = home / ".local" / "bin" / "claude"               # the native installer's launcher, a link
    link.parent.mkdir(parents=True)
    link.symlink_to(version)
    out = _dry_run(tmp_path, repo, home, fakebin, path_first=link.parent)
    assert out.returncode == 0 and "extension" not in out.stderr, out.stderr
    assert f" {link} -p " in out.stdout


@pytest.mark.parametrize("where", ["home", "project", "local"])
@pytest.mark.parametrize("key", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "apiKeyHelper"])
def test_a_settings_file_that_sets_a_key_is_said_by_name_never_by_value(tmp_path, where, key):
    repo, home, fakebin = _night_copy(tmp_path)
    claude = _exe(home / ".local" / "bin" / "claude")
    target = {"home": home / ".claude" / "settings.json", "project": repo / ".claude" / "settings.json",
              "local": repo / ".claude" / "settings.local.json"}[where]
    target.parent.mkdir(parents=True, exist_ok=True)
    body = ({"apiKeyHelper": "/bin/echo not-a-real-key"} if key == "apiKeyHelper"
            else {"env": {key: "not-a-real-key", "GH_CONFIG_DIR": "/x"}})
    target.write_text(json.dumps(body, indent=2), encoding="utf-8")
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=claude)
    assert out.returncode == 0, out.stderr
    assert f"{target} sets {key}:" in out.stderr and "DRY_RUN=1: said, not refused" in out.stderr
    assert "not-a-real-key" not in out.stderr + out.stdout


def test_a_settings_file_that_sets_no_key_is_not_said(tmp_path):
    repo, home, fakebin = _night_copy(tmp_path)
    claude = _exe(home / ".local" / "bin" / "claude")
    (home / ".claude").mkdir()
    (home / ".claude" / "settings.json").write_text(json.dumps(
        {"env": {"GH_CONFIG_DIR": "/x"}, "permissions": {"deny": ["Bash(echo $ANTHROPIC_API_KEY)"]}}),
        encoding="utf-8")
    out = _dry_run(tmp_path, repo, home, fakebin, claude_bin=claude)
    assert out.returncode == 0 and " sets " not in out.stderr, out.stderr


def _function(name: str) -> str:
    body = re.search(rf"^{name}\(\) {{\n.*?^}}\n", INSTALL, re.M | re.S)
    assert body, name
    return body.group(0)


def test_refuse_dies_outside_a_dry_run_and_only_says_it_under_one():
    """install's refusals without running install: die() and refuse() alone, in a bash."""
    script = re.search(r"^die\(\) \{.*\}\n", INSTALL, re.M).group(0)       # a one-line function
    script += _function("refuse") + 'refuse "claude moved"; echo after\n'
    hard = subprocess.run(["bash", "-c", script], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
                          timeout=10)
    assert hard.returncode == 1 and "after" not in hard.stdout and "night-install: claude moved" in hard.stderr
    soft = subprocess.run(["bash", "-c", script], env={"PATH": "/usr/bin:/bin", "DRY_RUN": "1"},
                          capture_output=True, text=True, timeout=10)
    assert soft.returncode == 0 and "after" in soft.stdout and "⚠ claude moved" in soft.stderr
    # install runs both checks before its dry run's early return
    units = _function("install_units")
    dry = units.index('if [ "${DRY_RUN:-}" = 1 ]')
    assert units.index("  check_claude_path\n") < dry and units.index("  check_settings_keys\n") < dry
