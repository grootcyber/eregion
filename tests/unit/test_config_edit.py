"""CFG4 (#1129): the round-trip write of glorfindel-config.yaml, and the class of a change.

docs/design/configuration-console.md, §3.2, §5: a change is applied to the text, never to a dictionary dumped
again — the comments stay, an operation then its inverse give back the file to the byte; a result the strict
reading refuses is never written; the console writes exact names, never a pattern; the class of a change
(relax, tighten, neutral) is a pure function of the two texts, without the discovery and without the name of
the operation. `set_asset_mode`, `set_default_mode` and `glorfindel activate` write through it.
No Azure, no LLM.
"""
from __future__ import annotations

import inspect
import re
import textwrap
from pathlib import Path

import pytest
import yaml

from glorfindel.config import _EXCEPTION_KEYS, load_glorfindel_config, set_asset_mode, set_default_mode
from glorfindel.config_class import MASS_VMS, classify, loud
from glorfindel.config_edit import EditRefused, apply_change, digest, inverse

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = (ROOT / "glorfindel-config.yaml.example").read_text(encoding="utf-8")
# The example of the note (§3.2), a hand-written block list with its comment.
NOTE = textwrap.dedent("""\
    exceptions:
      # Les VM de dev : recréées chaque nuit (Jonathan, 12/11)
      - asset_pattern: "vm-dev-*"
        exclude_rules: [ssh-brute-force]
    autonomy:
      default: human_only   # le geste d'urgence
      assets:
        - match: 'vm-web-01'   # le front
          mode: non_disruptive
    never_block: ["10.0.0.5", "192.0.2.0/24"]
    # la fin du fichier
""")


def _terraform_fragment() -> str:
    tf = (ROOT / "infra" / "terraform" / "outputs.tf").read_text()
    fragment = re.search(r"<<-YAML\n(.*?)\n\s*YAML", tf, re.S).group(1)
    return re.sub(r"\$\{[^}]+\}", "x", textwrap.dedent(fragment)) + "\n"


FILES = {"example": EXAMPLE, "note": NOTE, "terraform": _terraform_fragment(), "empty": ""}
OPS = [
    {"op": "set_mode", "args": {"vm": "vm-db-02", "mode": "non_disruptive"}},
    {"op": "set_mode", "args": {"vm": "vm-web-01", "mode": "human_only"}},
    {"op": "set_default_mode", "args": {"mode": "non_disruptive"}},
    {"op": "exclude", "args": {"vm": "vm-lab-02", "rules": "all", "reason": ""}},
    {"op": "exclude", "args": {"vm": "vm-lab-03", "rules": ["ssh-brute-force", "ransomware-disk-write"], "reason": ""}},
    {"op": "never_block_add", "args": {"address": "198.51.100.10"}},
    {"op": "never_block_add", "args": {"address": "10.0.0.6"}},
]


def _op(name, **args) -> dict:
    return {"op": name, "args": args}


# ── the round trip ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("where", ["example", "note"])
@pytest.mark.parametrize("op", OPS, ids=lambda o: f"{o['op']}-{next(iter(o['args'].values()))}")
def test_an_operation_then_its_inverse_give_back_the_file_to_the_byte(where, op):
    text = FILES[where]
    if op["op"] == "set_mode" and op["args"]["vm"] == "vm-web-01" and where != "note":
        op = _op("set_mode", vm="vm-web-01", mode="non_disruptive")
    changed = apply_change(text, op)
    assert changed != text
    assert apply_change(changed, inverse(text, op)) == text


@pytest.mark.parametrize("where", ["example", "note", "terraform"])
def test_every_comment_stays_and_the_rest_to_the_byte(where):
    text = FILES[where]

    def comments(t: str) -> list[str]:
        return [line[line.index("#"):] for line in t.splitlines() if "#" in line]
    for op in OPS:
        changed = apply_change(text, op)
        assert comments(changed) == comments(text), op       # each one, in its order
        # Every line of the file is there, in its order, but the one the operation changes (a mode, `[]`).
        import difflib
        ops = difflib.SequenceMatcher(None, text.splitlines(), changed.splitlines(), autojunk=False).get_opcodes()
        assert sum(i2 - i1 for tag, i1, i2, _, _ in ops if tag in ("replace", "delete")) <= 1, op


@pytest.mark.parametrize("op", OPS, ids=lambda o: f"{o['op']}-{next(iter(o['args'].values()))}")
def test_a_section_the_file_did_not_have_comes_back_empty(op):
    """The known limit: a section absent (the fragment of Celebrimbor has neither exceptions nor autonomy)
    comes back from the inverse empty (`exceptions: []`, `default: human_only`) — the same configuration,
    not the same bytes; from there, an operation and its inverse are exact again."""
    text = FILES["terraform"]
    once = apply_change(apply_change(text, op), inverse(text, op))
    assert load_glorfindel_config_text(once) == load_glorfindel_config_text(text)
    assert apply_change(apply_change(once, op), inverse(once, op)) == once


def test_the_note_s_example_reads_as_the_note_says():
    out = apply_change(NOTE, _op("exclude", vm="vm-lab-02", rules="all", reason=""))
    assert out.startswith(textwrap.dedent("""\
        exceptions:
          # Les VM de dev : recréées chaque nuit (Jonathan, 12/11)
          - asset_pattern: "vm-dev-*"
            exclude_rules: [ssh-brute-force]
          - asset_pattern: "vm-lab-02"
            exclude_all: true
        autonomy:
          default: human_only   # le geste d'urgence
    """))
    # A mode set where the entry was quoted keeps its quotes and its comment; the default its comment.
    assert "- match: 'vm-web-01'   # le front\n      mode: human_only\n" in \
        apply_change(NOTE, _op("set_mode", vm="vm-web-01", mode="human_only"))
    assert "  default: non_disruptive   # le geste d'urgence\n" in apply_change(NOTE, _op("set_default_mode", mode="non_disruptive"))
    assert 'never_block: ["10.0.0.5", "192.0.2.0/24", "198.51.100.10/32"]\n' in \
        apply_change(NOTE, _op("never_block_add", address="198.51.100.10"))


@pytest.mark.skipif("reason" not in _EXCEPTION_KEYS, reason="exceptions[].reason comes with CFG2 (#1128)")
def test_an_exclusion_with_its_reason_round_trips():
    op = _op("exclude", vm="vm-lab-02", rules="all", reason="Labo de formation, sans données")
    out = apply_change(NOTE, op)
    assert '    exclude_all: true\n    reason: "Labo de formation, sans données"\n' in out
    assert apply_change(out, inverse(NOTE, op)) == NOTE
    assert inverse(out, _op("unexclude", vm="vm-lab-02")) == op


def test_the_inverse_of_each_operation():
    assert inverse(NOTE, _op("set_mode", vm="vm-db-02", mode="non_disruptive")) == _op("unset_mode", vm="vm-db-02")
    assert inverse(NOTE, _op("set_mode", vm="VM-WEB-01", mode="human_only")) == \
        _op("set_mode", vm="VM-WEB-01", mode="non_disruptive")
    assert inverse(NOTE, _op("unset_mode", vm="vm-web-01")) == _op("set_mode", vm="vm-web-01", mode="non_disruptive")
    assert inverse(NOTE, _op("set_default_mode", mode="non_disruptive")) == _op("set_default_mode", mode="human_only")
    assert inverse(NOTE, _op("exclude", vm="x", rules="all", reason="")) == _op("unexclude", vm="x")
    assert inverse(NOTE, _op("never_block_add", address="1.2.3.4")) == _op("never_block_remove", address="1.2.3.4")
    # unset, then set again: the mode comes back; the entry at the end of the list.
    gone = apply_change(NOTE, _op("unset_mode", vm="vm-web-01"))
    assert "vm-web-01" not in gone and "  assets: []\n" in gone
    back = apply_change(gone, inverse(NOTE, _op("unset_mode", vm="vm-web-01")))
    assert load_glorfindel_config_text(back).autonomy.resolve("vm-web-01") == "non_disruptive"


def load_glorfindel_config_text(text: str):
    from glorfindel.config import _parse_config
    return _parse_config(yaml.safe_load(text) or {})


def test_an_empty_or_absent_section_is_created_and_read_back():
    out = apply_change("", _op("set_mode", vm="vm-a", mode="non_disruptive"))
    assert out == 'autonomy:\n  assets:\n    - match: "vm-a"\n      mode: non_disruptive\n'
    out = apply_change("autonomy: {}\n", _op("set_default_mode", mode="non_disruptive"))
    assert out == "autonomy:\n  default: non_disruptive\n"
    out = apply_change("exceptions:\n# rien encore\n", _op("exclude", vm="vm-a", rules=["r"], reason=""))
    assert load_glorfindel_config_text(out).exceptions[0].exclude_rules == ["r"] and "# rien encore" in out


# ── the guards: nothing is written that is not what was asked ───────────────────────────────

def test_a_pattern_is_never_written():
    for vm in ("vm-dev-*", "vm-?", "vm-[ab]"):
        with pytest.raises(EditRefused) as exc:
            apply_change(NOTE, _op("exclude", vm=vm, rules="all", reason=""))
        assert exc.value.code == "pattern"
    with pytest.raises(EditRefused) as exc:
        apply_change(NOTE, _op("set_mode", vm="vm-*", mode="human_only"))
    assert exc.value.code == "pattern"
    # The pattern written by hand is never removed here either.
    with pytest.raises(EditRefused):
        apply_change(NOTE, _op("unexclude", vm="vm-dev-*"))


def test_a_result_the_strict_reading_refuses_is_never_produced(tmp_path):
    """A reason the reader refuses (too long, two lines — or, before CFG2, the key itself): refused."""
    for reason in ("x" * 300, "deux\nlignes"):
        with pytest.raises(EditRefused) as exc:
            apply_change(NOTE, _op("exclude", vm="vm-a", rules="all", reason=reason))
        assert exc.value.code == "config_refused"
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(NOTE)
    from glorfindel.config import edit_config
    with pytest.raises(EditRefused):
        edit_config(cfg, _op("exclude", vm="vm-a", rules="all", reason="x" * 300))
    assert cfg.read_text() == NOTE                                   # nothing written


def test_a_file_already_refused_is_never_rewritten(tmp_path):
    bad = "isolation:\n  quarantine_nsg: \"false\"\n# un commentaire\n"
    with pytest.raises(EditRefused) as exc:
        apply_change(bad, _op("set_mode", vm="vm-a", mode="human_only"))
    assert exc.value.code == "config_refused"
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(bad)
    with pytest.raises(ValueError):
        set_asset_mode("vm-a", "human_only", path=cfg)
    assert cfg.read_text() == bad


@pytest.mark.parametrize("text, code", [
    ("base: &b\n  x: 1\nautonomy: *b\n", "layout"),
    ("autonomy:\n  default: human_only\nautonomy:\n  default: non_disruptive\n", "layout"),
    ("never_block: [{a: 1}]\n", "config_refused"),
])
def test_a_layout_this_module_does_not_know_is_refused(text, code):
    with pytest.raises(EditRefused) as exc:
        apply_change(text, _op("set_default_mode", mode="human_only"))
    assert exc.value.code in (code, "config_refused")


def test_the_closed_list_and_its_exact_fields():
    for bad in ({"op": "yaml", "args": {}}, {"op": "set_mode", "args": {"vm": "a"}},
                {"op": "set_mode", "args": {"vm": "a", "mode": "full_auto"}},
                {"op": "set_mode", "args": {"vm": "a", "mode": "human_only", "extra": 1}},
                {"op": "exclude", "args": {"vm": "a", "rules": "some", "reason": ""}}):
        with pytest.raises(EditRefused):
            apply_change(NOTE, bad)
    with pytest.raises(EditRefused) as exc:
        apply_change(NOTE, _op("exclude", vm="VM-DEV-*", rules="all", reason=""))
    assert exc.value.code == "pattern"


def test_the_digest_is_the_hash_of_the_bytes_and_a_stale_base_is_refused(tmp_path):
    import hashlib
    assert digest(NOTE) == "sha256:" + hashlib.sha256(NOTE.encode()).hexdigest() == digest(NOTE.encode())
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(NOTE)
    from glorfindel.config import edit_config
    with pytest.raises(EditRefused) as exc:
        edit_config(cfg, _op("set_default_mode", mode="non_disruptive"), base=digest("autre chose"))
    assert exc.value.code == "config_changed" and cfg.read_text() == NOTE
    out = edit_config(cfg, _op("set_default_mode", mode="non_disruptive"), base=digest(NOTE))
    assert out["before"] == digest(NOTE) and out["after"] == digest(cfg.read_bytes())
    assert out["class"] == "relax"


# ── the writers of today ─────────────────────────────────────────────────────────────────────

def test_the_console_and_the_cli_write_keep_the_comments(tmp_path):
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(EXAMPLE)
    set_asset_mode("vm-web-01", "non_disruptive", path=cfg)
    set_default_mode("non_disruptive", path=cfg)
    out = cfg.read_text()
    assert [line for line in EXAMPLE.splitlines() if line.lstrip().startswith("#")] == \
        [line for line in out.splitlines() if line.lstrip().startswith("#")]
    auto = load_glorfindel_config(cfg).autonomy
    assert auto.default == "non_disruptive" and auto.resolve("vm-web-01") == "non_disruptive"
    set_default_mode("human_only", path=cfg)
    set_asset_mode("vm-web-01", "human_only", path=cfg)
    assert apply_change(cfg.read_text(), _op("unset_mode", vm="vm-web-01")) == EXAMPLE


def test_glorfindel_activate_writes_through_set_asset_mode():
    from glorfindel import cli
    assert "set_asset_mode(a[\"vm\"], \"non_disruptive\")" in inspect.getsource(cli)
    src = inspect.getsource(__import__("glorfindel.config", fromlist=["x"]).set_asset_mode)
    assert "edit_config(cfg_path, {\"op\": \"set_mode\"" in src and "safe_dump" not in src


# ── the class: relax, tighten, neutral — from the two texts alone ────────────────────────────

def _class(before: str, op: dict) -> dict:
    return classify(before, apply_change(before, op))


def test_the_class_depends_on_neither_the_discovery_nor_the_operation():
    assert list(inspect.signature(classify).parameters) == ["before", "after"]
    src = inspect.getsource(__import__("glorfindel.config_class", fromlist=["x"]))
    assert "discovery" not in src.split('"""', 2)[2] and "AssetRegistry" not in src
    # The same change by two roads: the same class.
    once = apply_change(NOTE, _op("set_mode", vm="vm-web-01", mode="human_only"))
    assert classify(NOTE, once) == classify(NOTE, NOTE.replace("mode: non_disruptive", "mode: human_only"))


def test_critical_set_tightens_taken_away_relaxes_and_an_edit_keeps_it():
    """PRT2 (#1160), M7428: `critical: true` set on an entry tightens; taken away (false, or the key gone)
    relaxes — whatever the mode beside it; the console's change of mode keeps it, to the byte."""
    critical = NOTE.replace("      mode: non_disruptive\n", "      mode: non_disruptive\n      critical: true\n")
    assert critical != NOTE
    out = classify(NOTE, critical)
    assert out["class"] == "tighten" and "vm-web-01: priority essential" in out["reasons"]
    out = classify(critical, NOTE)
    assert out["class"] == "relax" and any("essential to standard" in r for r in out["reasons"])
    assert classify(critical, critical.replace("critical: true", "critical: false"))["class"] == "relax"
    held = apply_change(critical, _op("set_mode", vm="vm-web-01", mode="human_only"))
    assert "critical: true" in held and load_glorfindel_config_text(held).autonomy.is_critical("vm-web-01")


def test_an_exclusion_relaxes_whatever_the_name_and_removing_it_tightens():
    out = _class(NOTE, _op("exclude", vm="vm-lab-07", rules="all", reason=""))        # discovered by no one
    assert out["class"] == "relax" and not out["latent"]
    assert _class(NOTE, _op("exclude", vm="vm-lab-07", rules=["ssh-brute-force"], reason=""))["class"] == "relax"
    excluded = apply_change(NOTE, _op("exclude", vm="vm-lab-07", rules="all", reason=""))
    assert _class(excluded, _op("unexclude", vm="vm-lab-07"))["class"] == "tighten"


def test_the_default_both_ways_and_to_human_only_loud():
    bold = _class(NOTE, _op("set_default_mode", mode="non_disruptive"))
    assert bold["class"] == "relax" and not bold["loud"]
    back = apply_change(NOTE, _op("set_default_mode", mode="non_disruptive"))
    prudent = _class(back, _op("set_default_mode", mode="human_only"))
    assert prudent["class"] == "tighten" and prudent["loud"]                         # Q11: at once, said loud
    assert _class(NOTE, _op("set_mode", vm="vm-web-01", mode="human_only"))["class"] == "tighten"


def test_an_exact_entry_under_a_pattern_of_the_same_mode_relaxes_latent():
    text = "autonomy:\n  default: human_only\n  assets:\n    - match: \"vm-*\"\n      mode: non_disruptive\n"
    out = _class(text, _op("set_mode", vm="vm-web-01", mode="non_disruptive"))
    assert out["class"] == "relax" and out["latent"]
    assert _class(text, _op("set_mode", vm="vm-web-01", mode="human_only"))["class"] == "tighten"


def test_an_exact_entry_of_the_default_s_mode_relaxes_latent():
    text = "autonomy:\n  default: non_disruptive\n"
    out = _class(text, _op("set_mode", vm="vm-x", mode="non_disruptive"))
    assert out["class"] == "relax" and out["latent"]
    # Removing it: the screen gone, a tightening, latent too.
    screened = apply_change(text, _op("set_mode", vm="vm-x", mode="non_disruptive"))
    assert _class(screened, _op("unset_mode", vm="vm-x"))["class"] == "tighten"


def test_never_block_one_private_host_tightens_the_rest_relaxes():
    assert _class(NOTE, _op("never_block_add", address="10.0.0.6"))["class"] == "tighten"
    assert _class(NOTE, _op("never_block_add", address="fd00::6"))["class"] == "tighten"
    for wide in ("198.51.100.10", "10.0.0.0/24", "0.0.0.0/1", "2001:db8::1"):
        assert _class(NOTE, _op("never_block_add", address=wide))["class"] == "relax", wide
    assert _class(NOTE, _op("never_block_remove", address="10.0.0.5"))["class"] == "relax"


def test_a_mixed_change_relaxes_and_an_unclassified_one_never_tightens():
    mixed = NOTE.replace("default: human_only", "default: non_disruptive").replace("mode: non_disruptive", "mode: human_only")
    assert classify(NOTE, mixed)["class"] == "relax"
    other = NOTE + "memory:\n  max_age_days: 10\n"
    assert classify(NOTE, other)["class"] == "relax"
    assert classify(NOTE, NOTE)["class"] == "neutral"


def test_many_vms_to_human_only_at_once_are_loud():
    text = "autonomy:\n  assets:\n" + "".join(f"    - match: vm-{i}\n      mode: non_disruptive\n" for i in range(6))
    out = classify(text, text.replace("non_disruptive", "human_only"))
    assert out["class"] == "tighten" and out["loud"]


# ── the review of CFG4 ───────────────────────────────────────────────────────────────────────

def test_a_text_that_reads_back_otherwise_than_asked_is_refused_mismatch():
    """A reason holding U+0085 (NEL): PyYAML folds it in a double-quoted scalar — the text written would
    not say what was asked. Only the guard « read back equal to the dictionary » holds this one."""
    with pytest.raises(EditRefused) as exc:
        apply_change(NOTE, _op("exclude", vm="vm-a", rules="all", reason="deux\u0085lignes"))
    assert exc.value.code == "mismatch"


BLOCK = textwrap.dedent("""\
    exceptions:
      - asset_pattern: >-
          vm-old
        exclude_all: true
      # le commentaire après un scalaire en bloc
    autonomy:
      assets:
        - match: vm-web-01
          mode: >-
            non_disruptive
        # après le mode en bloc
      default: human_only
    # la fin
""")


@pytest.mark.parametrize("op", [
    _op("unexclude", vm="vm-old"), _op("unset_mode", vm="vm-web-01"),
    _op("set_mode", vm="vm-web-01", mode="human_only"), _op("set_mode", vm="vm-new", mode="human_only"),
    _op("exclude", vm="vm-new", rules="all", reason=""),
], ids=lambda o: o["op"] + "-" + o["args"]["vm"])
def test_a_comment_after_a_block_scalar_stays_where_it_was(op):
    out = apply_change(BLOCK, op)
    for comment in ("  # le commentaire après un scalaire en bloc\n", "    # après le mode en bloc\n", "# la fin\n"):
        assert out.count(comment) == 1, (comment, out)
    lines = out.splitlines()
    assert lines.index("  # le commentaire après un scalaire en bloc") < lines.index("autonomy:")
    assert lines.index("    # après le mode en bloc") < lines.index("  default: human_only")
    if op["op"] == "exclude":                     # the new entry before the comment, after the old one
        assert out.index('- asset_pattern: "vm-new"') < out.index("# le commentaire après")


def test_set_mode_on_an_empty_autonomy():
    for empty in ("autonomy:\n", "autonomy: ~\n", "autonomy: null\n"):
        out = apply_change(empty, _op("set_mode", vm="vm-a", mode="non_disruptive"))
        assert out == 'autonomy:\n  assets:\n    - match: "vm-a"\n      mode: non_disruptive\n', empty
    out = apply_change("autonomy:\n  assets: ~\n", _op("set_mode", vm="vm-a", mode="human_only"))
    assert out == 'autonomy:\n  assets:\n    - match: "vm-a"\n      mode: human_only\n'      # no space left


def test_a_pattern_s_human_only_entry_removed_is_never_latent():
    text = "autonomy:\n  default: human_only\n  assets:\n    - match: \"vm-*\"\n      mode: human_only\n"
    gone = "autonomy:\n  default: human_only\n  assets: []\n"
    out = classify(text, gone)
    assert out["class"] == "relax" and not out["latent"]
    exact = text.replace('"vm-*"', '"vm-a"')
    assert classify(exact, gone)["latent"]                                     # an exact name: latent


def test_inverse_of_an_ambiguous_unexclude_is_refused_so():
    text = "exceptions:\n  - asset_pattern: vm-a\n    exclude_all: true\n  - asset_pattern: VM-A\n    exclude_rules: [r]\n"
    with pytest.raises(EditRefused) as exc:
        inverse(text, _op("unexclude", vm="vm-a"))
    assert exc.value.code == "ambiguous"


def test_activate_says_a_refused_write_as_a_click_error():
    from glorfindel import cli
    src = inspect.getsource(cli.activate.callback)
    assert "    except ValueError as exc:" in src and "raise click.ClickException(str(exc)) from exc" in src


def test_the_class_is_read_before_the_write(tmp_path, monkeypatch):
    from glorfindel import config
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(NOTE)

    def boom(before, after):
        raise RuntimeError("class unreadable")
    monkeypatch.setattr("glorfindel.config_class.classify", boom)
    with pytest.raises(RuntimeError):
        config.edit_config(cfg, _op("set_default_mode", mode="non_disruptive"))
    assert cfg.read_text() == NOTE


# ── CFG4b (#1136): « en masse » counted in VMs really touched (Q11) ─────────────────────────────

BOLD = "autonomy:\n  default: non_disruptive\n  assets: []\n"
SIX = [f"vm-web-{i:02d}" for i in range(6)]


def test_a_pattern_that_touches_six_discovered_vms_is_loud():
    after = BOLD.replace("assets: []", "assets:\n    - match: \"vm-*\"\n      mode: human_only")
    assert classify(BOLD, after)["class"] == "tighten" and not classify(BOLD, after)["loud"]   # one entry
    assert loud(BOLD, after, SIX) == "response disarmed on 6 VMs"                            # six VMs


def test_four_exact_entries_are_not_loud_five_are():
    four = BOLD
    for vm in SIX[:4]:
        four = apply_change(four, _op("set_mode", vm=vm, mode="human_only"))
    assert loud(BOLD, four, SIX) is None
    five = apply_change(four, _op("set_mode", vm=SIX[4], mode="human_only"))
    assert MASS_VMS == 5 and loud(BOLD, five, SIX) == "response disarmed on 5 VMs"


def test_the_default_to_human_only_is_loud_whatever_the_count():
    after = apply_change(BOLD, _op("set_default_mode", mode="human_only"))
    assert loud(BOLD, after, []) == "response disarmed on 0 VMs, and on every VM the default governs"
    assert loud(BOLD, after, SIX[:2]).startswith("response disarmed on 2 VMs")
    assert loud(after, BOLD, SIX) is None                                     # the other way: a relaxation


def test_a_vm_no_discovery_knows_counts_for_nothing():
    six = BOLD
    for vm in SIX:
        six = apply_change(six, _op("set_mode", vm=vm, mode="human_only"))
    assert classify(BOLD, six)["loud"]                                         # the class counts entries
    assert loud(BOLD, six, []) is None and loud(BOLD, six, SIX[:4] + ["vm-db-01"]) is None
    assert loud(BOLD, six, [v.upper() for v in SIX]) == "response disarmed on 6 VMs"   # case ignored


def test_a_vm_already_human_only_is_not_touched():
    held = "autonomy:\n  default: human_only\n  assets: []\n"
    after = held.replace("assets: []", "assets:\n    - match: \"vm-*\"\n      mode: human_only")
    assert loud(held, after, SIX) is None


def test_edit_config_says_loud_by_the_vms_not_by_the_entries(tmp_path):
    from glorfindel import config
    cfg = tmp_path / "glorfindel-config.yaml"
    text = BOLD
    for vm in SIX[:5]:
        text = apply_change(text, _op("set_mode", vm=vm, mode="non_disruptive"))
    cfg.write_text(text)
    out = config.edit_config(cfg, _op("set_mode", vm=SIX[0], mode="human_only"), vms=SIX)
    assert out["class"] == "tighten" and not out["loud"] and out["loud_said"] is None
    out = config.edit_config(cfg, _op("set_default_mode", mode="human_only"), vms=SIX)
    assert out["loud"] and out["loud_said"].startswith("response disarmed on 1 VMs")   # vm-web-05 only


def test_edit_config_reads_the_registry_when_no_list_is_given(tmp_path):
    import json
    from glorfindel import config, discovery
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(BOLD)
    to_prudent = _op("set_default_mode", mode="human_only")
    said = config.edit_config(cfg, to_prudent)["loud_said"]                   # no registry: by entry, said why
    assert said == ("response disarmed on 0 entries, and on every VM the default governs "
                    "(the discovery's registry is absent: counted by entry)")
    cfg.write_text(BOLD)
    discovery._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    discovery._CACHE_FILE.write_text(json.dumps([{"name": vm, "resource_id": f"/x/{vm}", "monitoring_backend": "law",
                                                  "last_seen": "2026-11-24T00:00:00+00:00"} for vm in SIX]))
    assert config._discovered_names() == (SIX, None)
    assert config.edit_config(cfg, to_prudent)["loud_said"].startswith("response disarmed on 6 VMs")


# ── the review of CFG4b: a registry empty or unreadable falls back on the entries (Jonathan, 24/11) ──

def test_loud_without_a_list_counts_the_entries_as_cfg4():
    six = BOLD
    for vm in SIX:
        six = apply_change(six, _op("set_mode", vm=vm, mode="human_only"))
    assert loud(BOLD, six, None) == "response disarmed on 6 entries"
    four = BOLD
    for vm in SIX[:4]:
        four = apply_change(four, _op("set_mode", vm=vm, mode="human_only"))
    assert loud(BOLD, four, None) is None
    assert loud(BOLD, six, []) is None                         # a list read with no VM: loud() counts none


@pytest.mark.parametrize("content, why", [
    (None, "the discovery's registry is absent"),
    ("[]", "the discovery lists no VM"),
    ("not json", "the discovery's registry could not be read"),
    ("{}", "the discovery's registry could not be read"),
    ('[{"bogus": 1}]', "the discovery's registry could not be read"),       # AssetRegistry._load swallowed it
])
def test_a_registry_absent_empty_or_unreadable_is_told_apart(content, why):
    from glorfindel import config, discovery
    if content is not None:
        discovery._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        discovery._CACHE_FILE.write_text(content)
    assert config._discovered_names() == ([], why)


def test_edit_config_on_an_empty_registry_counts_the_entries_and_says_so(tmp_path):
    from glorfindel import config, discovery
    discovery._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    discovery._CACHE_FILE.write_text("[]")
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text(BOLD)
    out = config.edit_config(cfg, _op("set_default_mode", mode="human_only"))
    assert out["loud"] and out["loud_said"] == ("response disarmed on 0 entries, and on every VM the default "
                                                "governs (the discovery lists no VM: counted by entry)")
    cfg.write_text(BOLD)
    out = config.edit_config(cfg, _op("set_default_mode", mode="human_only"), vms=[])
    assert out["loud_said"].endswith("(the list of VMs given is empty: counted by entry)")


def test_edit_config_s_loud_is_the_announcement_never_the_class_s_count(tmp_path, monkeypatch):
    # The closed list (one exact name, or the default, per operation; two modes) never makes the two counts
    # differ through edit_config today: the class's count is made to differ, as a later gesture could.
    from glorfindel import config, config_class
    real = config_class.classify

    def other_count(before, after):
        out = real(before, after)
        return {**out, "loud": not out["loud"]}
    monkeypatch.setattr(config_class, "classify", other_count)
    cfg = tmp_path / "glorfindel-config.yaml"
    for op, quiet in ((_op("set_mode", vm=SIX[0], mode="human_only"), True),
                      (_op("set_default_mode", mode="human_only"), False)):
        cfg.write_text(BOLD)
        out = config.edit_config(cfg, op, vms=SIX)
        assert out["loud"] is (out["loud_said"] is not None) and out["loud"] is not quiet
