"""CFG2 (#1128): a VM `exceptions[]` takes never vanishes in silence from the console.

The maintainer's remark of 23/11 (docs/design/configuration-console.md, §1.5): `exclude_all` took a VM out
of every rule applied to all VMs, and the console said it nowhere but in a green « exclue » of its audit —
which also counted a rule written for the VM, that still watches it. Here: `exceptions[].reason`, read
strictly; what an exclusion takes and what still watches the VM (glorfindel/exclusions.py); the audit line
in yellow, and right; /api/state and /api/exclusions; the card greyed with its band, the Overview's count.
Nothing is written. No Azure, no LLM.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from glorfindel.config import ConfigError, ExceptionConfig, GlorfindelConfig, _parse_config
from glorfindel.exclusions import exclusion_of, exclusions

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "eregion_console" / "static"
_RID = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-dev-01"


class _Rule:
    def __init__(self, name, *, auto_apply=True, resource_id="", enabled=True, asset_name="", query="Syslog | x"):
        self.name, self.auto_apply, self.resource_id = name, auto_apply, resource_id
        self.enabled, self.asset_name, self.query, self.ttp = enabled, asset_name, query, "T0000"


_AUTO = [_Rule("ransomware-disk-write", query="Perf | x"), _Rule("ssh-brute-force"),
         _Rule("off", enabled=False)]
_OWN = _Rule("pinned-here", auto_apply=False, resource_id=_RID.upper())
_ELSEWHERE = _Rule("pinned-elsewhere", auto_apply=False, resource_id=_RID + "-other")


def _cfg(*entries) -> GlorfindelConfig:
    return GlorfindelConfig(exceptions=[ExceptionConfig(**e) for e in entries])


# ── the reason, read strictly ────────────────────────────────────────────────────────────────

def test_a_reason_is_read_and_kept():
    cfg = _parse_config({"exceptions": [{"asset_pattern": "vm-dev-01", "exclude_all": True,
                                         "reason": "  VM de dev, recréée chaque nuit "}]})
    assert cfg.exceptions[0].reason == "VM de dev, recréée chaque nuit"
    assert _parse_config({"exceptions": [{"asset_pattern": "vm"}]}).exceptions[0].reason == ""


@pytest.mark.parametrize("bad, said", [
    (42, "un texte est attendu"), (["a"], "un texte est attendu"),
    ("deux\nlignes", "une seule ligne"), ("x" * 201, "au plus 200"),
])
def test_a_reason_of_the_wrong_kind_refuses_the_file(bad, said):
    with pytest.raises(ConfigError) as exc:
        _parse_config({"exceptions": [{"asset_pattern": "vm", "reason": bad}]})
    assert "exceptions[0].reason" in str(exc.value) and said in str(exc.value)


def test_the_doc_says_an_older_version_refuses_the_reason():
    ops = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    assert "`exceptions` (`asset_pattern`, `exclude_all`, `exclude_rules`, `reason`)" in ops
    assert "une version d'avant CFG2 refuse le fichier" in ops


# ── what an exclusion takes, and what still watches the VM ───────────────────────────────────

def test_a_pattern_takes_the_vm_and_the_band_says_so():
    view = exclusion_of(_cfg({"asset_pattern": "VM-DEV-*", "exclude_all": True}), "vm-dev-01", _RID, _AUTO)
    assert view is not None and view["all"] and view["rules"] == ["ransomware-disk-write", "ssh-brute-force"]
    assert view["entries"] == [{"pattern": "VM-DEV-*", "reason": "", "by_pattern": True}]
    assert view["said"].startswith("EXCLUDED from all 2 rules applied to every VM, and from the posture checks")
    assert "by the pattern VM-DEV-*" in view["said"] and "no reason given (written by hand)" in view["said"]
    assert exclusion_of(_cfg({"asset_pattern": "vm-prod-*", "exclude_all": True}), "vm-dev-01", _RID, _AUTO) is None


def test_a_partial_exclusion_is_never_read_as_a_total_one():
    view = exclusion_of(_cfg({"asset_pattern": "vm-dev-01", "exclude_rules": ["ssh-brute-force"],
                              "reason": "bruit du bastion"}), "vm-dev-01", _RID, _AUTO)
    assert not view["all"] and view["rules"] == ["ssh-brute-force"] and not view["posture"]
    assert view["said"].startswith("EXCLUDED from ssh-brute-force (1 of the 2 rules applied to every VM)")
    assert "« bruit du bastion »" in view["said"] and "no detection watches it" not in view["said"]
    out = exclusions(_cfg({"asset_pattern": "vm-dev-01", "exclude_rules": ["ssh-brute-force"]}), _AUTO,
                     [("vm-dev-01", _RID)])
    assert out["count"] == {"vms": 1, "all": 0, "partial": 1}


def test_the_band_names_the_rules_written_for_the_vm_that_still_watch_it():
    rules = [*_AUTO, _OWN, _ELSEWHERE]
    view = exclusion_of(_cfg({"asset_pattern": "vm-dev-01", "exclude_all": True, "reason": "labo"}),
                        "vm-dev-01", _RID, rules)
    assert view["still_watching"] == ["pinned-here"]
    assert "1 rule written for it still watches it: pinned-here" in view["said"]
    assert "no detection watches it" not in view["said"]
    alone = exclusion_of(_cfg({"asset_pattern": "vm-dev-01", "exclude_all": True}), "vm-dev-01", _RID, _AUTO)
    assert alone["still_watching"] == [] and "no rule written for it: no detection watches it" in alone["said"]
    # Known by its name only (no resource id): a rule written for that name still watches it.
    by_name = _Rule("by-name", auto_apply=False, asset_name="VM-DEV-01")
    assert exclusion_of(_cfg({"asset_pattern": "vm-dev-01", "exclude_all": True}), "vm-dev-01", "",
                        [*_AUTO, by_name])["still_watching"] == ["by-name"]


def test_a_name_no_rule_bears_is_said_and_an_entry_no_vm_matches_is_counted():
    view = exclusion_of(_cfg({"asset_pattern": "vm-dev-01", "exclude_rules": ["ssh-brute-forse"]}),
                        "vm-dev-01", _RID, _AUTO)
    assert view["rules"] == [] and view["unknown"] == ["ssh-brute-forse"]
    assert view["said"].startswith("EXCLUDED from no rule applied to every VM")
    assert "names no rule: ssh-brute-forse" in view["said"]
    out = exclusions(_cfg({"asset_pattern": "vm-lab-*", "exclude_all": True}), _AUTO, [("vm-dev-01", _RID)])
    assert out["vms"] == {} and out["count"]["vms"] == 0 and out["idle_entries"] == ["vm-lab-*"]


def test_the_counts_take_each_vm_once():
    cfg = _cfg({"asset_pattern": "vm-*", "exclude_all": True}, {"asset_pattern": "vm-a", "exclude_rules": ["x"]})
    out = exclusions(cfg, _AUTO, [("vm-a", ""), ("vm-b", ""), ("vm-a", ""), ("web", "")])
    assert sorted(out["vms"]) == ["vm-a", "vm-b"] and out["count"] == {"vms": 2, "all": 2, "partial": 0}


# ── the audit line: yellow, and right ────────────────────────────────────────────────────────

def test_the_audit_never_counts_a_rule_written_for_the_vm_excluded():
    from glorfindel.audit import rule_coverage
    cfg = _cfg({"asset_pattern": "vm-dev-*", "exclude_all": True})
    cov = {r["name"]: r["state"] for r in rule_coverage([*_AUTO, _OWN], _RID, {"perf": True, "syslog": True}, {},
                                                        cfg.is_excluded)}
    assert cov == {"ransomware-disk-write": "excluded", "ssh-brute-force": "excluded", "off": "disabled",
                   "pinned-here": "covered"}


def test_the_audit_line_of_an_excluded_vm_is_yellow_with_its_reason(monkeypatch):
    from glorfindel import audit
    from glorfindel.audit import AuditCheck
    cfg = _cfg({"asset_pattern": "vm-dev-01", "exclude_rules": ["ssh-brute-force"], "reason": "bruit du bastion"})
    monkeypatch.setattr(audit, "_load_rules", lambda: ([*_AUTO, _OWN], cfg))
    monkeypatch.setattr("glorfindel.detection_rules._load_status", lambda: {})
    seen = [AuditCheck("detection", "Disk write sampling", "ok", "", data={"present": True}),
            AuditCheck("detection", "Syslog", "ok", "", data={"present": True})]
    line = audit._check_rule_coverage(_RID, seen)
    assert line.status == "warn"
    assert "exclue par exceptions[] (« bruit du bastion ») : ssh-brute-force" in line.message
    assert "exceptions[]" in line.fix
    monkeypatch.setattr(audit, "_load_rules", lambda: ([*_AUTO, _OWN], _cfg()))
    assert audit._check_rule_coverage(_RID, seen).status == "ok"
    no_reason = _cfg({"asset_pattern": "vm-dev-01", "exclude_all": True})
    monkeypatch.setattr(audit, "_load_rules", lambda: ([*_AUTO, _OWN], no_reason))
    assert "exclues par exceptions[] (sans raison) : ransomware-disk-write, ssh-brute-force" in \
        audit._check_rule_coverage(_RID, seen).message


# ── the console: /api/state, /api/exclusions ─────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import eregion_console.api as api
    from glorfindel.discovery import AssetRegistry, DiscoveredAsset

    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    rules = tmp_path / "detection_rules.yaml"
    rules.write_text("rules:\n"
                     "  - name: ssh-brute-force\n    ttp: T1110\n    workspace_id: ws\n    query: \"Syslog | project _ResourceId\"\n"
                     "  - name: ransomware-disk-write\n    ttp: T1486\n    workspace_id: ws\n    query: \"Perf | project _ResourceId\"\n")
    monkeypatch.setattr(api, "_base_rules_path", lambda: rules)
    AssetRegistry().update([DiscoveredAsset("vm-dev-01", _RID, "law", "2026-11-24T09:00:00+00:00"),
                            DiscoveredAsset("vm-web-01", _RID.replace("vm-dev-01", "vm-web-01"), "law",
                                            "2026-11-24T09:00:00+00:00")])
    return console()


def _with(monkeypatch, cfg):
    monkeypatch.setattr("glorfindel.config.load_glorfindel_config", lambda *a, **k: cfg)


def test_the_state_carries_each_excluded_vm_and_its_band(client, monkeypatch):
    _with(monkeypatch, _cfg({"asset_pattern": "vm-dev-*", "exclude_all": True, "reason": "<b>dev</b>"}))
    x = client.get("/api/state").json()["exclusions"]
    assert x["error"] == "" and sorted(x["vms"]) == ["vm-dev-01"]
    assert x["vms"]["vm-dev-01"]["said"].startswith("EXCLUDED from all 2 rules applied to every VM")
    assert "« <b>dev</b> »" in x["vms"]["vm-dev-01"]["said"]          # raw here: the page escapes it
    assert x["count"] == {"vms": 1, "all": 1, "partial": 0}


def test_the_overview_route_counts_and_says_what_it_cannot_read(client, monkeypatch):
    _with(monkeypatch, _cfg({"asset_pattern": "vm-web-01", "exclude_rules": ["ssh-brute-force"]},
                            {"asset_pattern": "vm-lab-*", "exclude_all": True}))
    x = client.get("/api/exclusions").json()
    assert x["count"] == {"vms": 1, "all": 0, "partial": 1} and x["idle_entries"] == ["vm-lab-*"]

    def boom(*a, **k):
        raise ConfigError("exceptions[0].reason : un texte est attendu, pas 42")
    monkeypatch.setattr("glorfindel.config.load_glorfindel_config", boom)
    x = client.get("/api/exclusions").json()
    assert x["count"] is None and x["vms"] == {} and "un texte est attendu" in x["error"]
    assert "un texte est attendu" in client.get("/api/state").json()["exclusions"]["error"]


# ── the page: the card greyed and its band, the Overview's count ─────────────────────────────

JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
OV = (STATIC / "overview.js").read_text(encoding="utf-8")


def _body(src: str, head: str) -> str:
    assert head in src, head
    return src.split(head, 1)[1].split("\n}\n", 1)[0]


def test_the_card_of_an_excluded_vm_is_greyed_with_its_chip_and_band():
    card = _body(JS, "function _renderAssetNode(")
    assert "${isExpanded ? 'expanded' : ''}${_exclusionOf(vm_name) ? ' excluded' : ''}\"" in card
    assert "        ${staleBadge}\n        ${_exclusionChip(vm_name)}\n        ${modeBadge}" in card
    assert "      ${_addrLine(net)}\n      ${_exclusionBand(vm_name)}\n" in card
    band = _body(JS, "function _exclusionBand(name) {")
    assert "${_attr(x.said)}</div>" in band and 'title="${_attr(_EXCL_TIP)}"' in band
    chip = _body(JS, "function _exclusionChip(name) {")
    assert "${x.all ? 'EXCLUDED' : 'PARTLY EXCLUDED'}" in chip
    assert "return Object.hasOwn(vms, name) ? vms[name] : null;" in _body(JS, "function _exclusionOf(name) {")
    assert ".node-asset.excluded { border-style: dashed; }" in HTML and ".excl-band {" in HTML


def test_exclusions_not_read_are_said_above_the_cards():
    assert "      ${_exclusionsBand()}\n      ${_auditBand()}\n" in _body(JS, "function renderInfra() {")
    assert "⚠ exceptions[] not read: ${_attr(err)}" in _body(JS, "function _exclusionsBand() {")


def test_the_overview_counts_the_excluded_vms():
    assert "  lines.push(exclusionLine());\n" in _body(OV, "function glorfindelRow(s) {")
    line = _body(OV, "function exclusionLine() {")
    assert "⚠ exceptions[] not read: ${esc(x.error || 'no count')}" in line
    assert "excluded from detection rules ▸" in line and "${Number(x.count.all)} from every rule" in line
    assert "${idle.map(esc).join(', ')}" in line
    assert "get('/api/exclusions')," in _body(OV, "async function refresh() {")
