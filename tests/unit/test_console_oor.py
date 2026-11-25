"""OOR1 (#1202): what is out of reach, finished — the limits the relecture of GRP1 left (#1189).

- A held card on a tile out of reach says « out of reach: detect only », judged by the tile it is shown on, as
  its buttons are taken off: a card whose id is a bare name said « pending approval » beside no button.
- Its Cmd window gives no command that acts — aimed by its name, `glorfindel isolate <vm>` would reach a VM of
  the watch's subscription bearing the same one —, its acknowledgement only.
- The bar « the watch's subscription unknown » is said once /api/config was read without one, or could not be
  read — never before its first answer (it flashed at each load).
- A VM's readiness, for another subscription than the watch's: the connector's refusal
  (WrongSubscriptionError) said as an error, never a 500 — /api/readiness, /api/activate.

The page's functions run as they are (tests/unit/js_engine.py); the server through its routes. No Azure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
GROUPS = (STATIC / "infra_groups.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")

WATCH = "abcdef01…cdef"
DEV = "/subscriptions/aaaabbbb-1111-2222-3333-444455556666/resourceGroups/rg-dev/providers/Microsoft.Compute/virtualMachines/dev-1"
PROD = "/subscriptions/abcdef01-0000-0000-0000-00000000cdef/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/web-1"


# ── The page, run ──────────────────────────────────────────────────────────────────────────────────────

_TAKEN = ("_attr", "_on", "_watchSub", "_isOor", "_SUB_UNKNOWN", "_GROUP_SAID", "_groupBar", "_heldWord", "_oorCommand")
_HARNESS = r"""
let _cfgData = null, _cfgFailed = false, _groupBy = 'none';
const ESC_LABELS = { low_confidence: 'low confidence' };
const escLabel = t => ESC_LABELS[t] || t;
const out = {};
const bar = () => _groupBar().includes('subscription unknown');
out.bar_before_config = bar();
_cfgFailed = true; out.bar_config_failed = bar(); _cfgFailed = false;
_cfgData = { azure: { subscription_id: '' } }; out.bar_no_subscription = bar();
_cfgData = { azure: { subscription_id: WATCH } }; out.bar_configured = bar();
const devTile = { vm_name: 'dev-1', resource_id: DEV }, prodTile = { vm_name: 'web-1', resource_id: PROD };
// A card filed by a bare name, as some detections are: its own id says no subscription.
const bare = { id: 'abcdef0123456789', resource_id: 'dev-1', escalation_type: 'mode_hold', action: 'isolate_vm' };
out.held_on_oor = _heldWord(bare, _isOor(devTile));
out.held_on_prod = _heldWord(bare, _isOor(prodTile));
out.held_other = _heldWord({ ...bare, escalation_type: 'low_confidence' }, _isOor(prodTile));
out.cmd = _oorCommand(bare);
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    script = (GROUPS + js_engine.take(JS, *_TAKEN) + f"const WATCH = {json.dumps(WATCH)};\nconst DEV = {json.dumps(DEV)};\n"
              + f"const PROD = {json.dumps(PROD)};\n" + _HARNESS)
    return json.loads(js_engine.run(script))


def test_a_held_card_is_judged_by_the_tile_it_is_shown_on(ran):
    assert ran["held_on_oor"] == "out of reach: detect only"
    assert ran["held_on_prod"] == "pending approval" and ran["held_other"] == "held: low confidence"


def test_the_cmd_window_of_a_card_out_of_reach_gives_its_acknowledgement_only(ran):
    cmd = ran["cmd"]
    assert cmd.splitlines()[-1] == "glorfindel ack abcdef01", cmd
    assert all(line.startswith("#") for line in cmd.splitlines()[:-1]), cmd
    for verb in ("isolate", "block", "release", "snapshot", "restore"):
        assert f"glorfindel {verb}" not in cmd, verb


def test_the_unknown_bar_waits_for_the_first_answer_of_config(ran):
    assert ran["bar_before_config"] is False            # not read yet: nothing said
    assert ran["bar_config_failed"] is True and ran["bar_no_subscription"] is True
    assert ran["bar_configured"] is False


def test_the_page_passes_the_tile_to_the_card_and_its_cmd():
    group = JS.split("function _renderEscGroup(group, tile) {", 1)[1].split("\n}\n", 1)[0]
    assert "  const oor   = _isOor(tile);" in group and "_heldWord(e, oor)" in group
    assert group.count("_on('click', 'openCommandModal', e.id, tile ? tile.vm_name : '')") == 5
    assert "_on('click', 'openCommandModal', e.id)" not in JS
    assert JS.count("_groupEscs(myEscs).map(g => _renderEscGroup(g, resource))") == 2
    assert "_groupEscs(myDetEscs).map(g => _renderEscGroup(g, resource))" in JS
    cmd = JS.split("function openCommandModal(escId, tileName) {", 1)[1].split("\n}\n", 1)[0]
    assert "  const oor = _isOor(_tiles.get(tileName));" in cmd
    assert "  const cmd = oor ? _oorCommand(esc) : cliCommand(esc);" in cmd
    modal = JS.split("function showEscModal(vmName) {", 1)[1].split("\n}\n", 1)[0]
    assert "_heldWord(e, _isOor(tile))" in modal and modal.count("'openCommandModal', e.id, vmName)") == 4
    assert "  } catch (e) { _cfgFailed = true; renderInfra(); }" in JS.split("async function refreshCfgData() {", 1)[1]


# ── The server ─────────────────────────────────────────────────────────────────────────────────────────

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


@pytest.fixture()
def client(monkeypatch):
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    return console()


def _refused(monkeypatch):
    """The connector's refusal, as `_same_subscription` raises it: both subscriptions named whole."""
    import eregion_console.api as api
    from glorfindel.response.policy import WrongSubscriptionError

    def refuse(resource_id, connector, quarantine_nsg=True):
        raise WrongSubscriptionError("dev-1 est dans l'abonnement aaaabbbb-1111-2222-3333-444455556666, Glorfindel "
                                     "agit dans abcdef01-0000-0000-0000-00000000cdef : action refusée")
    monkeypatch.setattr(api, "_resolve_vm", lambda vm: DEV)
    monkeypatch.setattr("glorfindel.actions.AzureConnector", lambda **k: object())
    monkeypatch.setattr("glorfindel.readiness.assess", refuse)


def test_readiness_and_activation_of_another_subscription_said_never_a_500(client, monkeypatch):
    from eregion_console.reach import OUT_OF_REACH
    _refused(monkeypatch)
    switched = []
    monkeypatch.setattr("glorfindel.config.set_asset_mode", lambda vm, mode: switched.append((vm, mode)) or "cfg.yaml")
    for r in (client.get("/api/readiness/dev-1"), client.post("/api/activate/dev-1", json={"acknowledged": []})):
        assert r.status_code == 200, r.text
        assert r.json() == {"error": OUT_OF_REACH}
        assert "aaaabbbb" not in r.text and "abcdef01" not in r.text     # no identifier in the answer
    assert switched == []


def test_a_vm_of_the_watch_s_subscription_still_reads_its_readiness(monkeypatch):
    from eregion_console import reach
    seen = []
    monkeypatch.setattr("glorfindel.readiness.assess",
                        lambda rid, connector, quarantine_nsg=True: seen.append((rid, quarantine_nsg)) or {"verdict": "ready"})
    assert reach.assess(PROD, object(), quarantine_nsg=False) == {"verdict": "ready"}
    assert seen == [(PROD, False)]
    api_src = (Path(__file__).resolve().parents[2] / "eregion_console" / "api.py").read_text(encoding="utf-8")
    assert "    from eregion_console.reach import assess   # OOR1" in api_src.split("def _assess_vm(", 1)[1].split("\n\n\n", 1)[0]
