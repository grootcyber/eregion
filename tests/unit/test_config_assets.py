"""PRI2a (#1219): the section `assets:` and the former `autonomy:`, one model (glorfindel/config_assets.py); the
priority of a VM, `level_of` (glorfindel/config.py); the class of a change on the model (glorfindel/config_class.py);
the writers that keep the file's format and `glorfindel config migrate` (glorfindel/config_edit.py,
glorfindel/config_migrate.py); the note at the watch's start and in /api/config. docs/design/classification.md,
§5, §6, §8 (PR5, PR7, PR8). M7789–M7805, scripts/mutants/PRI2a.py; PR1's guard of structure is
tests/unit/test_priority_boundary.py."""
from __future__ import annotations

import textwrap

import pytest
import yaml
from click.testing import CliRunner
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from glorfindel.config import AutonomyConfig, AutonomyRule, ConfigError, _parse_config
from glorfindel.config_class import classify
from glorfindel.config_edit import EditRefused, apply_change, inverse
from glorfindel.config_migrate import migrate

MIGRATE = {"op": "migrate", "args": {"to": "assets"}}
BACK = {"op": "migrate", "args": {"to": "autonomy"}}


def _cfg(text: str):
    return _parse_config(yaml.safe_load(textwrap.dedent(text)) or {})


def _refused(text: str) -> str:
    with pytest.raises(ConfigError) as exc:
        _cfg(text)
    return str(exc.value)


# ── the reading: assets:, strict ─────────────────────────────────────────────────────────────────

def test_an_entry_gives_a_mode_a_priority_or_both_each_optional():
    a = _cfg("""
        assets:
          default_mode: non_disruptive
          allow_destructive: [vm-lab-01]
          list:
            - match: vm-db-prod
              mode: human_only
              priority: essential
              reason: the ERP database
            - match: "vm-dev-*"
              priority: quiet
    """).autonomy
    assert a.form == "assets" and a.notes == [] and a.allow_destructive == ["vm-lab-01"]
    assert (a.resolve("vm-db-prod"), a.level_of("VM-DB-PROD")) == ("human_only", "essential")
    assert (a.resolve("vm-dev-07"), a.level_of("vm-dev-07")) == ("non_disruptive", "quiet")
    assert a.level_of("vm-web-01") == "standard" and a.assets[0].reason == "the ERP database"


def test_an_unknown_priority_is_refused_named_and_all_problems_said_at_once():
    """M7789: `priority: critical` (the former word, a gravity of the cards), a typo, a number — refused, the
    file whole, every problem said at once (A3)."""
    said = _refused("""
        assets:
          list:
            - {match: vm-a, priority: critical}
            - {match: vm-b, priority: esential}
            - {match: vm-c, priority: 1}
            - {match: vm-d, mode: full_auto}
    """)
    assert "4 problèmes" in said and 'unknown priority "critical"' in said
    assert 'did you mean "essential"' in said and "a priority (text) is expected, not 1" in said
    assert "full_auto" in said


def test_an_entry_that_says_nothing_and_a_match_written_twice_are_refused():
    """M7793: an entry with neither mode nor priority is refused (« an entry that says nothing »); so is the
    same match twice, case ignored — one entry per name or pattern; and any other key."""
    assert "an entry that says nothing" in _refused("assets:\n  list:\n    - match: vm-a\n      reason: why\n")
    said = _refused("assets:\n  list:\n    - {match: VM-A, mode: human_only}\n    - {match: vm-a, priority: quiet}\n")
    assert "one entry per name or pattern" in said and "assets.list[0]" in said
    assert "critical" in _refused("assets:\n  list:\n    - {match: vm-a, mode: human_only, critical: true}\n")
    assert "deflt" in _refused("assets:\n  deflt: human_only\n")


def test_both_formats_in_one_file_are_refused_even_when_they_agree():
    """M7791, §5.4: `autonomy:` and `assets:` in one file — two places for the same modes: refused, whatever
    they say."""
    said = _refused("""
        autonomy:
          default: human_only
        assets:
          default_mode: human_only
    """)
    assert "assets: and the former autonomy: in one file" in said
    # M7823: each section's own problems said in the same message — one fix, not three runs.
    said = _refused("""
        autonomy:
          default: full_auto
        assets:
          list:
            - {match: vm-a, priority: critical}
    """)
    assert "3 problèmes" in said and 'unknown priority "critical"' in said and "full_auto" in said


def test_the_former_format_is_read_in_the_same_model_with_its_note():
    """§5.4: `critical: true` read as `priority: essential`; a note, in English, never an error — the
    former format and each `critical: true`."""
    a = _cfg("""
        autonomy:
          default: non_disruptive
          assets:
            - {match: "vm-db-*", mode: human_only, critical: true}
            - {match: vm-web-01, mode: non_disruptive, critical: false}
    """).autonomy
    assert a.form == "autonomy" and a.level_of("vm-db-07") == "essential" and a.is_critical("vm-db-07")
    assert a.level_of("vm-web-01") == "standard" and a.critical_count() == 1
    assert a.notes == ["autonomy: is the former format of assets: — migrate it (glorfindel config migrate)",
                       "autonomy.assets[0] says `critical: true`, the former name of priority: essential"]
    assert _cfg("exceptions: []\n").autonomy.notes == [] and _cfg("exceptions: []\n").autonomy.form == ""


# ── the priority: the exact entry, then the longest pattern, tied the highest (Q6) ─────────────────

def test_the_priority_takes_the_exact_entry_then_the_longest_pattern_tied_the_highest():
    """M7794, M7795, M7796, §5.3: `vm-erp-qa: quiet` under `vm-erp-*: essential` is quiet — an exemption the
    confirmation will hold (CFG5); a longer pattern wins; two patterns as long, the highest; an entry with
    no priority never takes part."""
    a = _cfg("""
        assets:
          list:
            - {match: "vm-erp-*", priority: essential}
            - {match: vm-erp-test, mode: non_disruptive}
            - {match: vm-erp-qa, priority: quiet}
            - {match: "vm-erp-qa-*", priority: standard}
            - {match: "vm-a*", priority: quiet}
            - {match: "vm-*a", priority: essential}
    """).autonomy
    assert a.level_of("vm-erp-test") == "essential" and a.resolve("vm-erp-test") == "non_disruptive"
    assert a.level_of("vm-erp-prod-01") == "essential" and a.resolve("vm-erp-prod-01") == "human_only"
    assert a.level_of("VM-ERP-QA") == "quiet"
    assert a.level_of("vm-erp-qa-02") == "standard"         # longer than vm-erp-*
    assert a.level_of("vm-aa") == "essential"               # vm-a* and vm-*a as long: the highest
    assert a.level_of("vm-ab") == "quiet" and a.level_of("db-01") == "standard"


_NAMES = ("vm-a", "VM-A", "vm-b", "vm-ab", "vm-*", "vm-a*", "vm-?b", "*", "vm-[*]")
_MODES = ("human_only", "non_disruptive")


@st.composite
def _former(draw):
    """A file in the former format: entries over a few names and patterns, duplicates and case included."""
    entries = []
    for _ in range(draw(st.integers(0, 6))):
        e = {"match": draw(st.sampled_from(_NAMES)), "mode": draw(st.sampled_from(_MODES))}
        if draw(st.booleans()):
            e["critical"] = draw(st.booleans())
        entries.append(e)
    autonomy: dict = {"default": draw(st.sampled_from(_MODES))}
    if entries:
        autonomy["assets"] = entries
    if draw(st.booleans()):
        autonomy["allow_destructive"] = draw(st.lists(st.sampled_from(("vm-lab-01", "vm-x")), max_size=2))
    return yaml.safe_dump({"exceptions": [], "autonomy": autonomy}, sort_keys=False)


_PROBES = ("vm-a", "vm-b", "vm-ab", "vm-aa", "vm-x", "vm-*", "db-01")


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_former())
def test_pr7_the_former_format_migrated_gives_each_name_the_same_mode_and_level(text):
    """PR7: for any file in the former format — duplicates and patterns included —, its migration gives each
    name the same mode and the same level, the same count of essential entries, and CFG4 classes it
    neutral; the way back never gives a bolder mode."""
    new = apply_change(text, MIGRATE)
    before, after = _parse_config(yaml.safe_load(text)).autonomy, _parse_config(yaml.safe_load(new)).autonomy
    assert after.form == "assets" and "autonomy" not in yaml.safe_load(new)
    for name in (*_PROBES, *_NAMES):
        assert after.resolve(name) == before.resolve(name), name
        assert after.level_of(name) == before.level_of(name), name
    assert after.critical_count() == before.critical_count()
    assert after.allow_destructive == before.allow_destructive
    assert classify(text, new)["class"] == "neutral"
    back = _parse_config(yaml.safe_load(apply_change(new, BACK))).autonomy
    for name in (*_PROBES, *_NAMES):
        assert back.resolve(name) == after.resolve(name), name


@st.composite
def _assets(draw):
    entries, seen = [], set()
    for _ in range(draw(st.integers(0, 5))):
        match = draw(st.sampled_from(_NAMES))
        if match.lower() in seen:
            continue
        seen.add(match.lower())
        e = {"match": match}
        if draw(st.booleans()):
            e["mode"] = draw(st.sampled_from(_MODES))
        if "mode" not in e or draw(st.booleans()):
            e["priority"] = draw(st.sampled_from(("essential", "standard", "quiet")))
        entries.append(e)
    return {"default_mode": draw(st.sampled_from(_MODES)), "list": entries}


@settings(max_examples=150, deadline=None)
@given(_assets(), st.sampled_from(("vm-c", "vm-a", "vm-*", "vm-c*")), st.sampled_from(("essential", "quiet")))
def test_pr8_an_entry_without_a_mode_changes_no_mode_and_one_without_a_priority_no_level(section, match, level):
    """PR8 (M7792): adding an entry that gives only a priority leaves `resolve` unchanged for every name — an
    exact entry `vm-a: essential` never screens `vm-a` from a pattern's mode —; one that gives only a mode
    leaves `level_of` unchanged."""
    if any(e["match"].lower() == match.lower() for e in section["list"]):
        return
    base = _parse_config({"assets": section}).autonomy
    with_priority = _parse_config({"assets": {**section, "list": [*section["list"], {"match": match,
                                                                                   "priority": level}]}}).autonomy
    with_mode = _parse_config({"assets": {**section, "list": [*section["list"], {"match": match,
                                                                               "mode": "non_disruptive"}]}}).autonomy
    for name in (*_PROBES, *_NAMES, match):
        assert with_priority.resolve(name) == base.resolve(name), name
        assert with_mode.level_of(name) == base.level_of(name), name


def test_a_priority_alone_never_screens_the_vm_from_a_pattern_s_mode():
    """PR8, the example of §5.3: `vm-db-prod: essential` under `vm-*: non_disruptive` keeps its mode."""
    a = _cfg("""
        assets:
          list:
            - {match: "vm-*", mode: non_disruptive}
            - {match: vm-db-prod, priority: essential}
    """).autonomy
    assert a.resolve("vm-db-prod") == "non_disruptive" and a.level_of("vm-db-prod") == "essential"


# ── CFG4 on the model ────────────────────────────────────────────────────────────────────────────

FORMER = textwrap.dedent("""\
    # the client's file
    exceptions: []
    autonomy:
      default: non_disruptive
      allow_destructive: [vm-lab-01]
      assets:
        - match: "vm-db-*"
          mode: human_only
          critical: true
        - match: VM-WEB-01
          mode: non_disruptive
        - match: vm-web-01
          mode: human_only
          critical: true
        - match: "vm-erp-*"
          mode: non_disruptive
    never_block: []
""")


def test_the_migration_is_neutral_and_merges_the_duplicates_said():
    """§6, M7798, M7799: a file that mixes modes, patterns, duplicates, `critical: true` and allow_destructive —
    its migration classed neutral on the model: CFG4 compares levels name by name (never `critical: true`
    entry by entry) and `allow_destructive` on the model (never at its former path)."""
    new = apply_change(FORMER, MIGRATE)
    assert classify(FORMER, new) == {"class": "neutral", "latent": False, "loud": False, "reasons": []}
    data = yaml.safe_load(new)
    assert data["assets"]["list"] == [
        {"match": "vm-db-*", "mode": "human_only", "priority": "essential"},
        {"match": "VM-WEB-01", "mode": "human_only", "priority": "essential"},
        {"match": "vm-erp-*", "mode": "non_disruptive"}]
    assert data["assets"]["allow_destructive"] == ["vm-lab-01"] and new.startswith("# the client's file\n")
    assert new.endswith("never_block: []\n")


def test_a_level_down_relaxes_up_tightens_name_by_name_and_quiet_relaxes_by_prudence():
    """§6, M7797, M7428: on the model — `standard` → `quiet` relaxes (by prudence: a label today),
    `quiet` → `standard` tightens, an exact `quiet` under an `essential` pattern relaxes the VM it names
    (the entries that say essential unchanged), posing `essential` tightens; a reason reworded is neutral."""
    base = apply_change(FORMER, MIGRATE)
    quiet = base.replace("  list:\n", "  list:\n    - match: vm-dev-01\n      priority: quiet\n")
    out = classify(base, quiet)
    assert out["class"] == "relax" and "vm-dev-01: priority standard to quiet" in out["reasons"]
    assert classify(quiet, base)["class"] == "tighten"
    under = base.replace("  list:\n", "  list:\n    - match: vm-db-qa\n      priority: quiet\n")
    out = classify(base, under)
    assert out["class"] == "relax" and "vm-db-qa: priority essential to quiet, its grave detections lose the " \
                                       "graves' reserve" in out["reasons"]
    essential = base.replace("  list:\n", "  list:\n    - match: vm-app-01\n      priority: essential\n")
    assert classify(base, essential)["class"] == "tighten"
    reason = quiet.replace("priority: quiet\n", "priority: quiet\n      reason: recreated each night\n")
    assert classify(quiet, reason)["class"] == "neutral"


def test_a_pattern_s_text_changed_relaxes_and_fewer_essential_entries_too():
    """§6, M7800: `vm-db-*` → `vm-d*` (essential both) relaxes, without the discovery — a longer pattern of
    another level could lower a VM no text names; an essential entry fewer shrinks the reserve: relaxes."""
    base = apply_change(FORMER, MIGRATE)
    widened = base.replace('match: "vm-db-*"', 'match: "vm-d*"')
    out = classify(base, widened)
    assert out["class"] == "relax" and any("a pattern's priority changed" in r for r in out["reasons"])
    redundant = base.replace("  list:\n", "  list:\n    - match: vm-db-01\n      priority: essential\n")
    out = classify(redundant, base)
    assert out["class"] == "relax" and "essential entries 3 to 2: the graves' reserve shrinks" in out["reasons"]


def test_every_section_no_function_classes_relaxes_when_it_changes():
    """Constat 4 of the note: a section of the strict reading that no function of config_class classes is
    never neutral — it relaxes when it changes."""
    from glorfindel.config import _SECTIONS
    from glorfindel.config_class import CLASSIFIED
    assert set(CLASSIFIED) <= set(_SECTIONS) and {"assets", "autonomy"} <= set(CLASSIFIED)
    out = classify("memory:\n  max_age_days: 90\n", "memory:\n  max_age_days: 30\n")
    assert out["class"] == "relax" and "memory changed: not classified, taken as relaxing" in out["reasons"]


# ── the writers keep the file's format ───────────────────────────────────────────────────────────

NEW = textwrap.dedent("""\
    assets:
      default_mode: human_only   # the default
      list:
        - match: vm-db-prod
          priority: essential
          reason: the ERP database
        - match: "vm-dev-*"
          priority: quiet
""")


def test_the_writers_keep_the_file_s_format_never_migrating_it():
    """M7802, §5.4: in a file written in `assets:`, the console's mode selector writes `assets.list` (a mode
    added to an entry that gives only a priority, taken away with its priority kept), the default
    `assets.default_mode`; in the former format, `autonomy:` as before."""
    set_mode = {"op": "set_mode", "args": {"vm": "vm-db-prod", "mode": "non_disruptive"}}
    out = apply_change(NEW, set_mode)
    assert "autonomy" not in yaml.safe_load(out) and "# the default" in out
    assert yaml.safe_load(out)["assets"]["list"][0] == {"match": "vm-db-prod", "priority": "essential",
                                                       "reason": "the ERP database", "mode": "non_disruptive"}
    assert apply_change(out, inverse(NEW, set_mode)) == NEW
    added = apply_change(NEW, {"op": "set_mode", "args": {"vm": "vm-web-01", "mode": "non_disruptive"}})
    assert yaml.safe_load(added)["assets"]["list"][-1] == {"match": "vm-web-01", "mode": "non_disruptive"}
    dflt = apply_change(NEW, {"op": "set_default_mode", "args": {"mode": "non_disruptive"}})
    assert yaml.safe_load(dflt)["assets"]["default_mode"] == "non_disruptive" and "# the default" in dflt
    with pytest.raises(EditRefused):            # an entry with no mode: nothing to unset
        apply_change(NEW, {"op": "unset_mode", "args": {"vm": "vm-db-prod"}})
    former = apply_change(FORMER, set_mode)
    assert "assets" not in yaml.safe_load(former)
    assert yaml.safe_load(former)["autonomy"]["assets"][-1] == {"match": "vm-db-prod", "mode": "non_disruptive"}


def test_the_way_back_to_the_former_format_never_writes_a_bolder_mode():
    """M7801, §5.6: `essential` without a mode on a pattern is written `human_only` — never the mode its text
    resolves to (a pattern `vm-[*]` that matches the text `vm-*` would give it non_disruptive, and every VM
    under `vm-*` with it); `quiet` and `reason` dropped, said."""
    text = textwrap.dedent("""\
        assets:
          default_mode: human_only
          list:
            - {match: "vm-[*]", mode: non_disruptive}
            - {match: "vm-*", priority: essential}
            - {match: vm-db-prod, priority: essential, reason: the ERP database}
            - {match: vm-dev-01, priority: quiet}
    """)
    back = yaml.safe_load(apply_change(text, BACK))
    assert back["autonomy"]["assets"] == [
        {"match": "vm-[*]", "mode": "non_disruptive"}, {"match": "vm-*", "mode": "human_only", "critical": True},
        {"match": "vm-db-prod", "mode": "human_only", "critical": True}]
    assert _parse_config(back).autonomy.resolve("vm-x") == "human_only"


def test_glorfindel_config_migrate_shows_the_change_writes_it_and_says_imladris(tmp_path):
    """The command: the change shown (a diff), its notes (the duplicates merged, each critical: true), the
    class neutral, Imladris not to be pushed yet; written under the lock — and refused, nothing written, on a
    file already migrated or one the strict reading refuses."""
    path = tmp_path / "glorfindel-config.yaml"
    path.write_text(FORMER)
    out = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert out.exit_code == 0, out.output
    assert "+assets:" in out.output and "-autonomy:" in out.output and "class: neutral" in out.output
    assert "merged into one entry" in out.output and "critical: true written priority: essential" in out.output
    assert "do not push this file yet" in out.output and "written:" in out.output
    assert yaml.safe_load(path.read_text())["assets"]["list"][0]["priority"] == "essential"
    again = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert again.exit_code != 0 and "already written in assets:" in again.output
    no = CliRunner().invoke(migrate, ["--path", str(path), "--to", "autonomy"], input="n\n")
    assert no.exit_code != 0 and "assets" in yaml.safe_load(path.read_text())
    both = tmp_path / "both.yaml"
    both.write_text("autonomy: {}\nassets: {}\n")
    refused = CliRunner().invoke(migrate, ["--path", str(both), "--yes"])
    assert refused.exit_code != 0 and both.read_text() == "autonomy: {}\nassets: {}\n"


def test_a_migration_that_would_change_the_defence_is_refused_nothing_written(tmp_path, monkeypatch):
    """M7821, PR7's net: a migration CFG4 would not class neutral — here a `_to_assets` that loses a priority —
    is refused (`mismatch`), by `apply_change` and by the command, and the file is never written."""
    from glorfindel import config_migrate
    real = config_migrate._to_assets

    def loses_a_priority(data, cfg):
        section, notes = real(data, cfg)
        section["list"] = [{k: v for k, v in e.items() if k != "priority"} for e in section.get("list", [])]
        return section, notes
    monkeypatch.setattr(config_migrate, "_to_assets", loses_a_priority)
    with pytest.raises(EditRefused) as exc:
        apply_change(FORMER, MIGRATE)
    assert exc.value.code == "mismatch" and "would change the defence" in str(exc.value)
    path = tmp_path / "glorfindel-config.yaml"
    path.write_text(FORMER)
    out = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert out.exit_code != 0 and "would change the defence" in out.output and "written:" not in out.output
    assert path.read_text() == FORMER


def test_the_command_says_the_comments_inside_the_former_section_are_not_carried_over(tmp_path):
    """M7824: a comment written inside `autonomy:` is not carried over — said; one outside it stays, to the
    byte, and nothing is said of it."""
    path = tmp_path / "glorfindel-config.yaml"
    path.write_text(FORMER.replace("  default: non_disruptive\n", "  default: non_disruptive   # since 12/11\n"))
    out = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert out.exit_code == 0 and "note: the comments inside the former section are not carried over" in out.output
    assert "# since 12/11" not in path.read_text() and path.read_text().startswith("# the client's file\n")
    path.write_text(FORMER)
    out = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert out.exit_code == 0 and "not carried over" not in out.output


@pytest.mark.parametrize("err", ["EROFS", "EACCES"])
def test_a_config_that_can_t_be_written_is_said_in_one_sentence_nothing_written(tmp_path, monkeypatch, err):
    """M7826: a config mounted read-only (the watch's container, `:ro`) or not ours to write — the command
    says it in one sentence, no traceback, exits non-zero, and writes nothing."""
    import errno
    import os

    def refused(*a, **k):
        raise OSError(getattr(errno, err), os.strerror(getattr(errno, err)))
    monkeypatch.setattr("glorfindel.config.edit_config", refused)
    path = tmp_path / "glorfindel-config.yaml"
    path.write_text(FORMER)
    out = CliRunner().invoke(migrate, ["--path", str(path), "--yes"])
    assert out.exit_code == 1 and not isinstance(out.exception, OSError), out.exception
    assert "can't be written" in out.output and "nothing is written" in out.output and "Traceback" not in out.output
    assert path.read_text() == FORMER


def test_the_command_is_glorfindel_s():
    from glorfindel.cli import cli
    out = CliRunner().invoke(cli, ["config", "migrate", "--help"])
    assert out.exit_code == 0 and "--to" in out.output


# ── the note: at the watch's start, and in /api/config ───────────────────────────────────────────

class _Console:
    def __init__(self):
        self.lines: list[str] = []

    def print(self, text="", *a, **k):
        self.lines.append(str(text))


def test_the_watch_says_the_former_format_at_its_start_and_counts_only_the_modes(monkeypatch):
    """M7805: the note at the start, once per note; the per-asset count is the entries that give a mode — a
    priority alone is no override."""
    from types import SimpleNamespace
    from glorfindel.watch import startup
    monkeypatch.setattr("glorfindel.escalations.alerting_configured", lambda: True)
    former = _cfg(FORMER).autonomy
    console = _Console()
    startup._say_autonomy(console, SimpleNamespace(autonomy=former, config_error=""), None, True)
    said = "\n".join(console.lines)
    assert "note: autonomy: is the former format of assets: — migrate it (glorfindel config migrate)" in said
    assert said.count("the former name of priority: essential") == 2
    console = _Console()
    new = _cfg(NEW).autonomy
    startup._say_autonomy(console, SimpleNamespace(autonomy=new, config_error=""), None, False)
    said = "\n".join(console.lines)
    assert "note:" not in said and "override" not in said and "Readiness gate" not in said


# ── the budget: the same on both formats; quiet is standard's ────────────────────────────────────

def test_the_reserve_and_the_buckets_are_the_same_on_both_formats_and_quiet_is_standard(tmp_path):
    """PR7 on PRT2, and PR1's budget: the same reserve, the same buckets from the former format and its
    migration; `quiet` and `standard` the same buckets, the same verdict — `essential` alone changes them."""
    from glorfindel import model_budget as mb
    from glorfindel.decision_queue import GRAVE_TTPS

    grave = {"vm_name": "vm-db-07", "resource_id": "/x/vm-db-07", "event": "detection", "ttp": sorted(GRAVE_TTPS)[0]}

    def judged(autonomy: AutonomyConfig, data: dict, name: str):
        ledger = mb.Ledger(tmp_path / f"{name}.json", source=lambda d: ("real", ""), zone=lambda rid: "bench",
                           autonomy=lambda: autonomy)
        verdict = ledger.judge(data, 1)
        return verdict.kind, getattr(verdict.decision, "keys", None), ledger.reserve()

    former, migrated = _cfg(FORMER).autonomy, _cfg(apply_change(FORMER, MIGRATE)).autonomy
    assert judged(former, grave, "a") == judged(migrated, grave, "b")
    assert judged(former, grave, "a")[1] == ("real", "real/critical")


_BUCKETS = ("real", "real/rest", "real/noncritical", "real/critical", "real/vm/vm-db-07", "exercise")


@st.composite
def _account(draw):
    """A state of the day's count: buckets filled (up to past their limit), breakers tripped, the provider's
    cool-down on or off, and an essential entry or none elsewhere (the reserve grows)."""
    spent = {k: draw(st.floats(0, 6, allow_nan=False)) for k in draw(st.lists(st.sampled_from(_BUCKETS),
                                                                          unique=True))}
    tripped = {k: "2026-11-26T00:00:00+00:00" for k in draw(st.lists(st.sampled_from(_BUCKETS), unique=True))}
    return spent, tripped, draw(st.integers(0, 3)), draw(st.booleans()), draw(st.booleans()), draw(st.integers(1, 4))


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(_account())
def test_pr1_quiet_and_standard_give_the_same_verdict_and_buckets_at_any_state_of_the_count(tmp_path, account):
    """PR1, the budget: for any state of the count — buckets filled, breakers tripped, the provider's
    cool-down, another VM essential —, a grave and an ordinary on a VM `quiet` get the verdict, the reason
    and the buckets (`_keys`) of the same VM `standard`, or of no entry at all."""
    from glorfindel import model_budget as mb
    from glorfindel.decision_queue import GRAVE_TTPS
    spent, tripped, strikes, cooling, other, share = account

    def judged(level: str | None, data: dict):
        rules = [AutonomyRule(match="vm-db-07", priority=level)] if level else []
        rules += [AutonomyRule(match="vm-erp-*", priority="essential")] if other else []
        ledger = mb.Ledger(tmp_path / "budget.json", clock=lambda: 1_795_000_000.0, dry_run=True,
                           source=lambda d: ("real", ""), zone=lambda rid: "bench",
                           autonomy=lambda: AutonomyConfig(assets=rules))
        ledger._state.update(spent=dict(spent), tripped=dict(tripped))
        ledger._strikes, ledger._until = strikes, (1_795_000_030.0 if cooling else 0.0)
        v = ledger.judge(data, share)
        return v.kind, v.why, v.card, getattr(v.decision, "keys", None), ledger.reserve()

    grave = {"resource_id": "/x/vm-db-07", "event": "detection", "ttp": sorted(GRAVE_TTPS)[0]}
    for data in (grave, {**grave, "ttp": "T0000"}):
        assert judged("quiet", data) == judged("standard", data) == judged(None, data)
