"""CRT1 (#1215): a VM's priority shown — the tile, the page Config, the note of the former format, the view
« Relaxed », the watch's start (docs/design/classification.md §7, Q2, Q4).

- The server reads each VM's level as the watch does (`level_of`: the exact entry, then the longest pattern):
  /api/state `priority_levels` (the VMs not standard), /api/config `glorfindel_config.priorities` (the entries by
  level, what each designates, the graves' reserve, the essential VMs that may be isolated on their own).
- The reserve is the budget's one reckoning (`model_budget.reserve_of`, the ledger's own): never a figure copied —
  it follows the real's envelope and its cap.
- The tile: `ESSENTIAL` beside the mode, a thin line, never an alarm colour; `quiet` in grey; nothing for
  `standard`. The page Config: « Priorities », « may be isolated on its own », « none », the note of the former
  format at its head, the sentence on CFG5. The view « Relaxed »: the kind `priority` labelled, its text the
  watch's. The watch's start: the essential entries and their reserve.

The page's functions run as they are (tests/unit/js_engine.py); the server through its routes. No Azure, no model.
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from glorfindel.config import _parse_config
from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
PRIO = (STATIC / "priorities.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")

CONFIG = """
    assets:
      default_mode: {default}
      list:
        - match: vm-db-prod
          mode: non_disruptive
          priority: essential
          reason: the ERP database
        - match: "vm-erp-*"
          priority: essential
        - match: vm-erp-qa
          priority: standard
        - match: "vm-dev-*"
          priority: quiet
          reason: recreated each night
"""
NAMES = ["vm-db-prod", "vm-dev-01", "vm-erp-01", "vm-erp-02", "vm-erp-qa", "vm-web-01"]


def _cfg(default: str = "human_only", text: str = CONFIG):
    return _parse_config(yaml.safe_load(textwrap.dedent(text.format(default=default))) or {})


# ── the server: the level of each VM, the section « Priorities » ────────────────────────────────────

def test_the_level_of_each_vm_is_the_watch_s_reading_a_pattern_included():
    """M7772: the level by `level_of` — a pattern makes its VMs essential, an exact entry takes one out of it; a
    standard VM is not listed (the tile says nothing of it)."""
    from eregion_console import config_state
    discovered = [{"name": n, "resource_id": f"/x/{n}"} for n in NAMES]
    got = config_state.levels(_cfg(), discovered, [], [{"resource_id": "/x/vm-erp-07"}])
    assert got == {"vm-db-prod": "essential", "vm-erp-01": "essential", "vm-erp-02": "essential",
                   "vm-erp-07": "essential", "vm-dev-01": "quiet"}
    assert config_state.levels(None, discovered, [], []) == {}


def test_the_section_says_each_entry_by_level_and_what_it_designates_today():
    from eregion_console import config_state
    p = config_state.priorities(_cfg().autonomy, NAMES)
    assert p["error"] == "" and p["essential_count"] == 2
    ess = {e["match"]: e for e in p["levels"]["essential"]}
    assert ess["vm-db-prod"]["reason"] == "the ERP database"
    assert ess["vm-db-prod"]["designates"]["said"] == "found by the discovery"
    assert ess["vm-erp-*"]["designates"]["said"] == "2 VMs today: vm-erp-01, vm-erp-02"     # vm-erp-qa taken out
    assert [e["match"] for e in p["levels"]["quiet"]] == ["vm-dev-*"]
    assert [e["match"] for e in p["levels"]["standard"]] == ["vm-erp-qa"]
    unknown = config_state.priorities(_cfg().autonomy, None, "discovery not read (OSError)", discover=False)
    assert unknown["discovery"] == "discovery not read (OSError)"
    assert unknown["levels"]["essential"][0]["designates"] == {"vms": None, "said": "not known: discovery not read (OSError)"}


def test_the_reserve_comes_from_the_budget_s_one_reckoning(monkeypatch, tmp_path):
    """M7773: the reserve the page shows is `model_budget.reserve_of`'s, the ledger's own — it follows the real's
    envelope (its variable) and the cap, never a figure copied."""
    from eregion_console import config_state
    from glorfindel import model_budget as mb
    autonomy = _cfg().autonomy
    assert config_state.priorities(autonomy, NAMES)["reserve"] == {"usd": 2.0, "floor_usd": 1.0, "essential_usd": 1.0}
    ledger = mb.Ledger(tmp_path / "b.json", source=lambda d: ("real", ""), zone=lambda rid: "bench",
                       autonomy=lambda: autonomy)
    ledger.judge({"resource_id": "/x/vm-web-01", "event": "detection", "ttp": "T1000"}, 1)
    assert ledger.reserve() == config_state.priorities(autonomy, NAMES)["reserve"]["usd"]
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "1.5")
    assert config_state.priorities(autonomy, NAMES)["reserve"] == {"usd": 1.5, "floor_usd": 1.0, "essential_usd": 0.5}
    monkeypatch.delenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY")
    many = "assets:\n  list:\n" + "".join(f"    - match: vm-{i}\n      priority: essential\n" for i in range(6))
    capped = config_state.priorities(_cfg(text=many).autonomy, [])["reserve"]
    assert capped == {"usd": mb.RESERVE_MAX_USD, "floor_usd": mb.GRAVE_FLOOR_USD,
                      "essential_usd": mb.RESERVE_MAX_USD - mb.GRAVE_FLOOR_USD}
    assert mb.reserve_of(6) == (2.5, 1.0, 1.5) and mb.reserve_of(0) == (1.0, 1.0, 0.0)


def test_an_essential_vm_that_may_be_isolated_on_its_own_is_said_and_none_otherwise():
    """M7777, Q4: one line per essential VM whose mode is not human_only — its own entry, or the default; the
    combination said, never corrected. None when none."""
    from eregion_console import config_state
    said = [i["said"] for i in config_state.priorities(_cfg().autonomy, NAMES)["isolable"]]
    assert said == ["vm-db-prod may be isolated on its own (non_disruptive): its service stops while it is isolated"]
    by_default = [i["vm"] for i in config_state.priorities(_cfg("non_disruptive").autonomy, NAMES)["isolable"]]
    assert by_default == ["vm-db-prod", "vm-erp-01", "vm-erp-02"]          # vm-erp-qa is standard, vm-web-01 too
    alone = config_state.priorities(_cfg().autonomy, [])["isolable"]       # an exact entry the discovery does not know
    assert [i["vm"] for i in alone] == ["vm-db-prod"]
    held = "assets:\n  list:\n    - match: vm-db-prod\n      mode: human_only\n      priority: essential\n"
    assert config_state.priorities(_cfg(text=held).autonomy, NAMES)["isolable"] == []


@pytest.fixture()
def client(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import eregion_console.api as api
    from glorfindel.discovery import AssetRegistry, DiscoveredAsset

    from .console_client import console
    monkeypatch.setattr(api, "_base_rules_path", lambda: "")
    AssetRegistry().update([DiscoveredAsset(n, f"/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/"
                                                f"virtualMachines/{n}", "law", "2026-11-26T09:00:00+00:00")
                            for n in NAMES])
    monkeypatch.setattr("glorfindel.config.load_glorfindel_config", lambda *a, **k: _cfg())
    return console()


def test_the_routes_carry_each_vm_s_level_and_the_section(client):
    state = client.get("/api/state").json()
    assert state["priority_levels"] == {"vm-db-prod": "essential", "vm-dev-01": "quiet", "vm-erp-01": "essential",
                                        "vm-erp-02": "essential"}
    g = client.get("/api/config").json()["glorfindel_config"]
    assert g["assets_format"] == "assets" and g["assets_notes"] == []
    p = g["priorities"]
    assert p["reserve"]["usd"] == 2.0 and [i["vm"] for i in p["isolable"]] == ["vm-db-prod"]
    assert {e["match"]: e["designates"]["said"] for e in p["levels"]["essential"]}["vm-erp-*"].startswith("2 VMs today")


# ── the watch's start ────────────────────────────────────────────────────────────────────────────────

class _Console:
    def __init__(self):
        self.lines: list[str] = []

    def print(self, text="", *a, **k):
        self.lines.append(str(text))


def test_the_watch_says_the_priorities_at_its_start(monkeypatch):
    """M7774, M7776, §7.3: the essential entries, the reserve their graves keep (the budget's reckoning), the
    others by level; nothing when no entry carries a priority, nor for a config that cannot be read."""
    from glorfindel.watch import startup
    monkeypatch.setattr("glorfindel.escalations.alerting_configured", lambda: True)
    console = _Console()
    startup._say_autonomy(console, SimpleNamespace(autonomy=_cfg().autonomy, config_error=""), None, True)
    line = next(x for x in console.lines if "Priorities:" in x)
    assert line == ("[bold]Priorities:[/bold] 2 essential (vm-db-prod, vm-erp-*) — their grave detections keep a "
                    "2.00 $ reserve; 1 quiet (vm-dev-*); 1 standard (vm-erp-qa); every other VM standard")
    marked = "assets:\n  list:\n    - match: \"[red]vm\"\n      priority: quiet\n"
    assert "\\[red]vm" in startup.priorities_line(_cfg(text=marked).autonomy)      # a name's markup escaped
    bare = _cfg(text="assets:\n  list:\n    - match: vm-a\n      mode: non_disruptive\n").autonomy
    console = _Console()
    startup._say_autonomy(console, SimpleNamespace(autonomy=bare, config_error=""), None, True)
    assert not any("Priorities:" in x for x in console.lines)
    console = _Console()
    startup._say_autonomy(console, SimpleNamespace(autonomy=_cfg().autonomy, config_error="bad"), None, True)
    assert not any("Priorities:" in x for x in console.lines)


# ── the page, run ────────────────────────────────────────────────────────────────────────────────────

MODE = '<span class="mode">⚡ NON-DISRUPTIVE</span>'
_RELAXED = ("_RELAXED_KIND", "_LATENT_TIP", "_OFF_TIP", "_ON_TIP", "_forceBadge", "_relaxedRow")
_HARNESS = r"""
const out = {};
const levels = { 'vm-db-prod': 'essential', 'vm-dev-01': 'quiet' };
out.lv = ['vm-db-prod', 'vm-dev-01', 'vm-web-01'].map(v => _priorityOf(levels, v));
out.lv_none = _priorityOf(undefined, 'vm-db-prod');
out.essential = _priorityMark('essential', MODE);
out.quiet = _priorityMark('quiet', MODE);
out.standard = _priorityMark('standard', MODE);
out.line_e = _priorityLine('essential'); out.line_q = _priorityLine('quiet'); out.line_s = _priorityLine('standard');
out.cfg = _prioritiesConfig(G);
out.cfg_none = _prioritiesConfig({ priorities: { levels: { essential: [], quiet: [], standard: [] }, reserve: { usd: 1, floor_usd: 1, essential_usd: 0 }, isolable: [], discovery: '', error: '' } });
out.cfg_unread = _prioritiesConfig({});
out.notes = _assetsNotes({ assets_notes: ['autonomy: is the former format of assets: — migrate it (glorfindel config migrate)', '<b>x</b>'] });
out.no_notes = _assetsNotes({ assets_notes: [] });
out.relaxed = _relaxedRow({ kind: 'priority', object: 'vm-dev-*', what: 'quiet: shown grey, no effect on the defence today', reason: '', by: 'unknown', where: 'assets.list[3]', designates: { said: '4 VMs today' } });
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    from eregion_console import config_state
    g = {"priorities": config_state.priorities(_cfg().autonomy, NAMES)}
    script = (js_engine.take(JS, "_attr", *_RELAXED) + PRIO + f"const MODE = {json.dumps(MODE)};\n"
              + f"const G = {json.dumps(g)};\n" + _HARNESS)
    return json.loads(js_engine.run(script))


def test_the_tile_marks_essential_beside_the_mode_and_nothing_for_standard(ran):
    """M7771, M7776: `ESSENTIAL · <mode>`, one piece; the mode alone for standard; the level as the server read it."""
    assert ran["lv"] == ["essential", "quiet", "standard"] and ran["lv_none"] == "standard"
    e = ran["essential"]
    assert re.search(r'<span class="prio-mark essential" title="Essential \(priority\): [^"]*">ESSENTIAL</span>'
                     r'<span class="prio-sep">·</span>' + re.escape(MODE), e), e
    assert "model budget&#39;s reserve" in e and "served first" not in e      # the effect of today, nothing more
    assert ran["standard"] == MODE
    assert ran["line_e"] == ('<div class="prio-line essential">ESSENTIAL: its grave detections keep the model '
                             'budget&#39;s reserve</div>')
    assert ran["line_q"] == '<div class="prio-line quiet">quiet: shown quiet: same rules, same budget</div>'
    assert ran["line_s"] == ""


def _rule(selector: str) -> str:
    m = re.search(r"^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", HTML, re.M)
    assert m, selector
    return m.group(1)


def test_quiet_is_grey_and_essential_never_an_alarm_colour(ran):
    """M7775, M7778, Q2: `ESSENTIAL` a thin line, never filled, never --red, --orange nor --yellow; `quiet` lower
    case, in --dim."""
    essential = _rule(".prio-mark.essential")
    assert "border: 1px solid var(--cyan)" in essential and "background: transparent" in essential
    for alarm in ("--red", "--orange", "--yellow"):
        assert alarm not in essential and alarm not in _rule(".prio-mark") and alarm not in _rule(".prio-combo")
    assert "color: var(--dim)" in _rule(".prio-mark.quiet")
    assert '<span class="prio-mark quiet" title="Quiet (priority): ' in ran["quiet"] and ">quiet</span>" in ran["quiet"]
    assert ran["quiet"].endswith(MODE + "</span>")
    phone = HTML[HTML.index("@media (max-width: 759px)"):]
    assert ".prio-row { flex-direction: column; gap: 2px; }" in phone       # §7.4: one column on a phone


def test_the_config_page_says_the_priorities_the_reserve_and_who_may_be_isolated(ran):
    cfg = ran["cfg"]
    assert '<div class="cfg-section-title">Priorities</div>' in cfg
    assert ("essential · 2 entries · graves' reserve 2.00 $ (1.00 $ floor + 1.00 $ for these VMs)") in cfg
    assert "“the ERP database”" in cfg and "2 VMs today: vm-erp-01, vm-erp-02" in cfg
    assert "quiet · 1 entry · a label only: watched, decided and budgeted as standard" in cfg
    assert "standard · every other VM (the default)" in cfg
    assert ("isolated on their own</span><span class=\"cfg-val\">vm-db-prod may be isolated on its own "
            "(non_disruptive): its service stops while it is isolated</span>") in cfg
    assert "Set in the config file for now; the console will write it with the signed queue (CFG5)." in cfg
    assert "<button" not in cfg and "data-on-" not in cfg                     # read only: no button, no write
    none = ran["cfg_none"]
    assert "none · every VM standard (the default)" in none
    assert '<span class="cfg-val">none</span>' in none
    assert "Not read: the config could not be read." in ran["cfg_unread"]


def test_the_note_of_the_former_format_heads_the_config_page(ran):
    """M7779, PRI2a: the watch's own note, escaped, at the head of the page; nothing for a file in `assets:`."""
    assert ("note · autonomy: is the former format of assets: — migrate it (glorfindel config migrate)"
            in ran["notes"])
    assert "&lt;b&gt;x&lt;/b&gt;" in ran["notes"] and "<b>" not in ran["notes"]
    assert ran["no_notes"] == ""
    refresh = JS[JS.index("async function refreshConfig()"):]
    assert "panel.innerHTML = `${_assetsNotes(d.glorfindel_config)}" in refresh
    assert "${_prioritiesConfig(d.glorfindel_config)}" in refresh


def test_the_relaxed_view_labels_the_priority_kind_its_text_the_watch_s(ran):
    """M7780: the kind `priority` (an entry that gives a priority only) gets its label; its text, the watch's."""
    assert "priority level · quiet: shown grey, no effect on the defence today" in ran["relaxed"]


def test_the_page_loads_the_marks_and_the_tile_wears_them():
    assert '<script src="/static/priorities.js"></script>\n<script src="/static/console.js"></script>' in HTML
    tile = JS[JS.index("function _renderAssetNode("):]
    tile = tile[:tile.index("\n}\n")]
    assert "const priority = _priorityOf(_state?.priority_levels, vm_name);" in tile
    assert "${_priorityMark(priority, modeBadge)}" in tile and "${isExpanded ? _priorityLine(priority) : ''}" in tile
