"""ENG1a (#1184): the product's output in English, surface by surface — a ratchet that only comes down.

The maintainer's decision (25/11): « tout en anglais, cli, discord, console, titre comme message, la
totale », in fifteen lots, in order; the docs, the comments and the docstrings stay as they are.
``scripts/french_output.py`` counts, file by file of the product, the strings that still read French,
and ``tests/unit/french_ceiling.json`` holds each file's ceiling, by surface (S0 to S14, and the
console's). Held here:
- no file over its ceiling, and a file absent from it at 0: a new file of the product is in English,
  and a file brought to 0 stays there;
- a file under its ceiling has its ceiling lowered in the same change (``--lower``): never raised;
- each file under its own surface, each surface with the lot that takes it;
- what the model sees out of the count, by name; the texts some code reads back not counted, each still
  where it is said to be;
- the first leftovers (S0: the TUI, the injectors' CLI, three files of the core) at 0.
The convention itself: CONTRIBUTING.md, « The product's output, in English ».
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("french_output", ROOT / "scripts" / "french_output.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["french_output"] = mod
    spec.loader.exec_module(mod)
    return mod


fo = _load()


@pytest.fixture(scope="module")
def counts():
    return fo.count()


@pytest.fixture(scope="module")
def ceiling():
    return fo.load_ceiling()


# ── the repository, under its ceilings ────────────────────────────────────────────────────────

def test_no_product_file_reads_more_french_than_its_ceiling(counts, ceiling):
    """A file over its ceiling, or one absent from it (at 0) that reads French: write it in English."""
    assert fo.over_ceiling(counts, fo.flat(ceiling)) == []


def test_a_ceiling_comes_down_with_its_file(counts, ceiling):
    """The ratchet: a file under its ceiling has it lowered in the same change, never left loose."""
    assert fo.ceiling_to_lower(counts, fo.flat(ceiling)) == []


def test_each_file_is_under_its_own_surface_and_each_surface_has_its_lot(counts, ceiling):
    assert fo.misfiled(ceiling) == []
    assert [rel for rel in counts if fo.surface_of(rel) is None] == []
    lots = {sid: lot for sid, lot, _name, _globs in fo.SURFACES}
    assert [lots[f"S{i}"] for i in range(15)] == [f"ENG1{c}" for c in "abcdefghijklmno"]
    assert lots["SC"] == "Console"
    assert set(ceiling) <= set(lots) and all(ceiling.values())    # no surface written empty


def test_the_texts_read_back_are_still_there_and_not_counted():
    assert fo.unfound() == []
    said = {(rel, text) for rel, text, _why in fo.READ_BACK}
    for rel, text in [("glorfindel/escalations.py", "Compte peut-être compromis"),       # COMPROMISE_MARK
                      ("glorfindel/response/policy.py", "zone exposée"),
                      ("glorfindel/exposed_zone.py", "réservée"),
                      ("eregion_console/api.py", "(?i)(?:étape|step)\\s+\\d+\\s*[–\\-:]"),
                      ("scripts/bench_preflight.py", "référence déployée"),
                      ("scripts/notify_discord.py", "[^\\w .,:;!?'’«»/=+-]|_"),
                      ("infra/glorfindel-host/cd/eregion_cd.py", "[^\\w .,:;!?'’«»()/=+-]")]:
        assert (rel, text) in said
        assert all(why for *_, why in fo.READ_BACK)
        found = [s for _, s in fo.strings_of(rel, (ROOT / rel).read_text(encoding="utf-8"))]
        assert text in found and fo.reads_french(text) and not fo.read_back(rel, text + " ")


def test_what_the_model_sees_is_out_of_the_count_by_name():
    assert fo.MODEL["glorfindel/agent.py"][0] == "_build_user_message"
    assert {"_SYSTEM_PROMPT", "_DECISION_TOOL"} <= set(fo.MODEL["glorfindel/agent.py"])
    assert fo.MODEL["glorfindel/enquiry/**"] is None and fo.MODEL["glorfindel/memory_keys.py"] is None
    assert fo.MODEL["analysis/campaign_report.py"] == ("_SYSTEM",) == fo.MODEL["analysis/triage.py"]
    assert fo.strings_of("glorfindel/enquiry/loop.py", "x = 'la carte est lue'\n") == []
    source = ("def _build_user_message(s):\n    return f'## État actuel de la VM {s}'\n"
              "def said():\n    return 'Étape suivante'\n")
    assert [s for _, s in fo.python_strings(source, fo.MODEL["glorfindel/agent.py"])] == ["Étape suivante"]


def test_the_first_leftovers_are_in_english(counts, ceiling):
    """S0 (ENG1a): the TUI, the injectors' CLI, three files of the core — all at 0, out of the ceilings."""
    assert "S0" not in ceiling
    for rel in ("glorfindel/tui.py", "annatar/cli.py", "gothmog/cli.py", "eregion_core/runs_layout.py",
                "eregion_core/rule_routing.py", "eregion_core/store_guard.py"):
        assert fo.surface_of(rel) == "S0" and rel not in counts, rel
    assert fo.surface_of("eregion_core/channel_reader.py") == "S6"     # with runs_channel, in ENG1g


def test_the_convention_is_written_where_the_guard_points():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "## The product's output, in English" in text
    for said in ("python scripts/french_output.py", "tests/unit/french_ceiling.json", "YYYY-MM-DD",
                 "notify_discord", "ENG1h", "ENG1o", "“…”"):
        assert said in text, said


# ── the detector ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "cette carte n'offre pas de restore", "déjà", "« Stop all »", "l'IP du poste", "qu'il relance",
    "la carte est là", "jamais lu", "rien", "Resource · : ·", "· : sessions", "un lien, une table",
])
def test_a_string_that_reads_french(text):
    assert fo.reads_french(text)


@pytest.mark.parametrize("text", [
    "this card offers no restore", "don't", "users' names", "  Engine  : · / ·", "  Dry-run : ·",
    "LIMIT ?", "a la", "en-US", "the “Stop all” button", "2026-11-25 10:00 UTC",
    "docs/operations.md, “Une sonde d'agent n'écrit jamais dans le vrai ~/.glorfindel”",
])
def test_a_string_that_does_not(text):
    assert not fo.reads_french(text)


def test_a_line_of_shell_has_no_spacing_rule():
    """`[ -f "$f" ] ; then` is shell, not French typography: the spacing is read in strings only."""
    assert fo.reads_french("[ -f \"$f\" ] ; then") and not fo.reads_french("[ -f \"$f\" ] ; then", spacing=False)
    assert fo.french_in("infra/x.sh", "[ -f \"$f\" ] ; then\necho 'déjà'\n") == [(2, "echo 'déjà'")]


def test_python_strings_never_a_docstring_nor_a_comment_and_an_fstring_is_one():
    source = ('"""Le module, en français."""\n'
              "# un commentaire en français\n"
              "def f(vm):\n"
              '    """La fonction."""\n'
              "    return f\"{vm} : jamais lu ({vm!s:.40})\"\n"
              "X = 'ok'\n")
    assert [s for _, s in fo.python_strings(source)] == ["· : jamais lu (·)", "ok"]


def test_js_strings_a_template_is_one_and_comments_and_regexes_are_aside():
    source = ("const a = `x ${b ? `la carte est ${c}` : 'non'} y`; // é commentaire\n"
              "let r = /'é/g; f('d\\'un'); x = a / 2 / 3; /* é */ g(\"ok\")\n")
    assert sorted(s for _, s in fo.js_strings(source)) == sorted(["x · y", "la carte est ·", "non", "d'un", "ok"])


def test_html_lines_and_yaml():
    assert [s for _, s in fo.html_strings('<!-- é --><p title="Fermer">Close</p><style>p{}</style>')] == \
        ["Fermer", "Close"]
    assert [s for _, s in fo.line_strings("# é\necho 'x # y' # é\n\n")] == ["echo 'x # y' "]
    rules = "rules:\n  - name: r\n    description: Une règle\n    query: |\n      T | where x == 'é'\n"
    assert [s for _, s in fo.yaml_strings(rules)] == ["r", "Une règle"]


def test_the_product_and_what_is_not():
    for rel in ("glorfindel/tui.py", "annatar/cli.py", "eregion_core/x.py", "scripts/doctor.py", "Makefile",
                "infra/glorfindel-host/deploy.sh", ".github/workflows/ci.yml", "eregion_console/static/a.js"):
        assert fo.is_product(rel), rel
    for rel in ("tests/unit/test_x.py", "infra/orodruin/tests/test_x.py", "scripts/mutation_check.py",
                "scripts/mutants/ENG1a.py", "scripts/french_output.py", "docs/operations.md"):
        assert not fo.is_product(rel), rel
    assert fo.strings_of("infra/terraform/main.tf", "") is None       # Terraform: out of ENG1
    assert fo.surface_of("glorfindel/providers/azure/entra.py") == "S12"
    assert fo.surface_of("glorfindel/providers/azure/release.py") == "S13"
    assert fo.surface_of("infra/glorfindel-host/client_rules.bench.yaml") == "S11"


# ── the ratchet, on a tree of its own ────────────────────────────────────────────────────────

def _tree(tmp_path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_new_file_or_one_brought_to_0_must_stay_at_0(tmp_path):
    root = _tree(tmp_path, {"glorfindel/a.py": "X = 'la carte est lue'\nY = 'jamais'\n",
                            "glorfindel/b.py": "Z = 'déjà'\n"})
    counts = fo.count(root)
    assert counts == {"glorfindel/a.py": 2, "glorfindel/b.py": 1}
    [said] = fo.over_ceiling(counts, {"glorfindel/a.py": 2})
    assert said.startswith("glorfindel/b.py: 1 string(s) that read French, over its ceiling of 0")
    assert fo.over_ceiling(counts, {"glorfindel/a.py": 2, "glorfindel/b.py": 1}) == []
    assert fo.over_ceiling(counts, {"glorfindel/a.py": 1, "glorfindel/b.py": 1})[0].startswith(
        "glorfindel/a.py: 2 string(s) that read French, over its ceiling of 1")


def test_a_ceiling_is_lowered_never_raised_and_a_file_at_0_leaves(tmp_path):
    assert fo.ceiling_to_lower({"a.py": 2}, {"a.py": 2}) == []
    [said] = fo.ceiling_to_lower({"a.py": 1}, {"a.py": 2, "b.py": 0})
    assert said.startswith("a.py: 1 string(s) that read French, under its ceiling of 2 — lower it")
    assert fo.ceiling_to_lower({}, {"b.py": 1})[0].startswith("b.py: 0 string(s)")
    assert fo.lowered({"a.py": 1, "c.py": 5}, {"a.py": 2, "b.py": 3}) == {"a.py": 1}
    assert fo.lowered({"a.py": 9}, {"a.py": 2}) == {"a.py": 2}       # a file that grew: its ceiling holds
    path = tmp_path / "ceiling.json"
    fo.write_ceiling({"glorfindel/bot.py": 3, "glorfindel/agent.py": 1}, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["surfaces"] == {"S1": {"glorfindel/bot.py": 3}, "S4": {"glorfindel/agent.py": 1}}
    assert fo.flat(fo.load_ceiling(path)) == {"glorfindel/bot.py": 3, "glorfindel/agent.py": 1}


def test_a_file_under_another_surface_is_misfiled():
    assert fo.misfiled({"S1": {"glorfindel/bot.py": 3}}) == []
    [said] = fo.misfiled({"S4": {"glorfindel/bot.py": 3}})
    assert said.startswith("glorfindel/bot.py: under S4, its surface is S1")


def test_a_text_read_back_that_left_its_file_is_said(tmp_path, monkeypatch):
    root = _tree(tmp_path, {"glorfindel/a.py": "MARK = 'Compte peut-être compromis'\n"})
    monkeypatch.setattr(fo, "READ_BACK", (("glorfindel/a.py", "Compte peut-être compromis", "why"),))
    assert fo.unfound(root) == [] and fo.count(root) == {}
    (root / "glorfindel/a.py").write_text("MARK = 'Account maybe compromised'\n", encoding="utf-8")
    [said] = fo.unfound(root)
    assert said.startswith("glorfindel/a.py: « Compte peut-être compromis » is no longer read back there")
    monkeypatch.setattr(fo, "READ_BACK", (("glorfindel/a.py", "Account maybe compromised", "why"),))
    assert fo.unfound(root)[0].startswith("glorfindel/a.py: « Account maybe compromised »")   # not French


def test_the_command_says_what_the_test_says(capsys):
    assert fo.main([]) == 0
    assert "no file over its ceiling" in capsys.readouterr().out
    assert fo.main(["--show", "glorfindel/tui.py"]) == 0 and capsys.readouterr().out == ""
