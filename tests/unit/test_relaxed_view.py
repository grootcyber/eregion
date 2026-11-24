"""CFG3 (#1139): the view « Relaxed » — everything glorfindel-config.yaml relaxes, shown from the file alone, by a
writer the console is not (docs/design/configuration-console.md, §6, §9).

The watch computes it (glorfindel/relaxed.py: each entry classed by CFG4's pure function, `classify`) and
writes it in its own directory, runs/glorfindel/config/relaxed.json, every minute and at its start; the console
reads it (/api/config/relaxed) and shows it on /config, escaped. A file refused, a discovery unreadable, a view
absent, unreadable or old: said, never read as « nothing relaxed ». No Azure, no LLM.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from glorfindel import relaxed

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "eregion_console" / "static"
NOW = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)
VMS = ("vm-db-01", "vm-dev-01", "vm-dev-02", "vm-web-01")

FILE = """\
# a comment the view never needs
autonomy:
  default: human_only
  assets:
    - match: "vm-*"
      mode: non_disruptive
    - match: vm-web-01
      mode: non_disruptive
    - match: vm-db-01
      mode: human_only
exceptions:
  - asset_pattern: "vm-dev-*"
    exclude_all: true
    reason: "VM de dev, recréée chaque nuit"
  - asset_pattern: vm-lab-07
    exclude_rules: [ssh-brute-force]
never_block:
  - 10.0.0.4
  - 198.51.100.10
  - dmz
networks:
  dmz: {subnet: "vnet-hub/snet-dmz"}
  bastion: [10.1.0.0/26]
  unused: [10.9.0.0/24]
expected_sudo:
  admins:
    - match: vm-web-01
      accounts: [admin1]
      origins: [bastion]
isolation:
  forensic_sources: [10.1.0.0/26]
network_zones:
  exposed: [dmz, 203.0.113.0/26]
"""


@pytest.fixture()
def registry():
    """The discovery's registry (redirected by the conftest), with VMS."""
    from glorfindel import discovery

    def write(names=VMS, raw=None):
        discovery._CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        discovery._CACHE_FILE.write_text(raw if raw is not None else json.dumps(
            [{"name": n, "resource_id": f"/x/{n}", "monitoring_backend": "law", "last_seen": "t"} for n in names]))
    write()
    return write


def _cfg(tmp_path, text=FILE) -> Path:
    path = tmp_path / "glorfindel-config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _view(tmp_path, text=FILE) -> dict:
    return relaxed.compute(NOW, _cfg(tmp_path, text))


def _by(view, kind) -> dict:
    return {e["object"]: e for e in view["entries"] if e["kind"] == kind}


# ── what the view shows: each entry that relaxes, classed by CFG4 ─────────────────────────────────

def test_every_entry_that_relaxes_is_shown_and_none_that_tightens(tmp_path, registry):
    view = _view(tmp_path)
    assert view["config"]["state"] == "read" and view["count"] == len(view["entries"])
    got = sorted((e["kind"], e["object"]) for e in view["entries"])
    assert got == sorted([
        ("mode", "vm-*"), ("mode", "vm-web-01"),
        ("exclusion", "vm-dev-*"), ("exclusion", "vm-lab-07"),
        ("never_block", "198.51.100.10"), ("never_block", "dmz"),          # Q10: a public address, a name
        ("expected_admins", "vm-web-01"), ("forensic_access", "10.1.0.0/26"),
        ("exposed_zone", "dmz"), ("exposed_zone", "203.0.113.0/26"),
        ("named_network", "bastion"), ("named_network", "dmz"),            # cited by a line that relaxes
    ])
    # Tightening, never in the view: an exact human_only entry, one private host in never_block (Q10),
    # the default human_only; a named network nothing cites is neutral.
    assert "vm-db-01" not in _by(view, "mode") and "10.0.0.4" not in _by(view, "never_block")
    assert not _by(view, "default_mode") and "unused" not in _by(view, "named_network")


def test_a_latent_bold_mode_is_shown_latent(tmp_path, registry):
    """§5.3: an exact entry under a pattern, or a default, of the same mode changes nothing today, but screens
    the VM — the day the pattern or the default goes back to human_only, it stays autonomous."""
    web = _by(_view(tmp_path), "mode")["vm-web-01"]
    assert web["latent"] is True and "screens it" in " ".join(web["why"])
    assert _by(_view(tmp_path), "mode")["vm-*"]["latent"] is False
    bold_default = "autonomy:\n  default: non_disruptive\n  assets:\n    - {match: vm-x, mode: non_disruptive}\n"
    view = _view(tmp_path, bold_default)
    assert _by(view, "default_mode")["default"]["what"] == "mode non_disruptive"
    assert _by(view, "mode")["vm-x"]["latent"] is True


def test_a_twin_entry_is_shown_latent_never_hidden(tmp_path, registry):
    """Taken out alone, a twin changes nothing: classed alone in its list, it relaxes — shown, latent."""
    twins = ("exceptions:\n  - {asset_pattern: vm-dev-01, exclude_all: true}\n"
             "  - {asset_pattern: vm-dev-01, exclude_all: true}\nnever_block: [198.51.100.10, 198.51.100.10/32]\n")
    view = _view(tmp_path, twins)
    excl = [e for e in view["entries"] if e["kind"] == "exclusion"]
    assert [e["where"] for e in excl] == ["exceptions[0]", "exceptions[1]"] and all(e["latent"] for e in excl)
    assert len([e for e in view["entries"] if e["kind"] == "never_block"]) == 2


def test_the_class_is_cfg4s_and_an_entry_not_classed_is_shown(tmp_path, registry, monkeypatch):
    from glorfindel import config_class
    raw = yaml.safe_load(FILE)
    for i in range(3):
        mine = relaxed.entry_class(raw, ("autonomy", "assets", i))
        assert mine == config_class.classify(relaxed._dump(relaxed._drop(raw, ("autonomy", "assets", i))),
                                             relaxed._dump(raw))
    monkeypatch.setattr(config_class, "classify", lambda b, a: {"class": "tighten", "latent": False, "loud": False,
                                                                "reasons": []})
    assert _view(tmp_path)["entries"] == []                     # the view follows the class, nothing else

    def boom(b, a):
        raise RuntimeError("no class")
    monkeypatch.setattr(config_class, "classify", boom)
    view = _view(tmp_path)
    assert len(view["entries"]) >= 10 and all(e["why"][0].startswith("not classified (") for e in view["entries"]
                                              if e["kind"] != "named_network")


def test_a_removal_that_empties_a_list_never_makes_a_refused_file(tmp_path, registry):
    """`exposed: []` is refused by the strict reading: the entry's class is read on a file without the key."""
    view = _view(tmp_path, "network_zones:\n  exposed: [203.0.113.0/26]\n")
    [zone] = view["entries"]
    assert zone["kind"] == "exposed_zone" and not any(w.startswith("not classified (") for w in zone["why"])
    assert relaxed._drop({"network_zones": {"exposed": ["x"]}}, ("network_zones", "exposed", 0)) == {}


# ── each line: its reason, its author, what it designates ─────────────────────────────────────────

def test_each_line_carries_its_reason_and_an_unknown_author(tmp_path, registry):
    view = _view(tmp_path)
    excl = _by(view, "exclusion")
    assert excl["vm-dev-*"]["reason"] == "VM de dev, recréée chaque nuit" and excl["vm-lab-07"]["reason"] == ""
    assert excl["vm-dev-*"]["what"] == "excluded from every rule applied to all VMs"
    assert excl["vm-lab-07"]["what"] == "excluded from ssh-brute-force"
    assert {(e["by"], e["since"]) for e in view["entries"]} == {(relaxed.AUTHOR_UNKNOWN, "")}
    assert relaxed.AUTHOR_UNKNOWN == "unknown"


def test_a_pattern_says_what_it_designates_today(tmp_path, registry):
    view = _view(tmp_path)
    dev = _by(view, "exclusion")["vm-dev-*"]["designates"]
    assert dev == {"vms": ["vm-dev-01", "vm-dev-02"], "said": "2 VMs today: vm-dev-01, vm-dev-02"}
    assert _by(view, "exclusion")["vm-lab-07"]["designates"]["said"] == "not found by the discovery today"
    # A mode pattern designates the VMs whose mode it is: never one an exact entry holds.
    assert _by(view, "mode")["vm-*"]["designates"]["vms"] == ["vm-dev-01", "vm-dev-02"]
    assert _by(view, "mode")["vm-web-01"]["designates"]["said"] == "found by the discovery"
    assert _by(view, "named_network")["bastion"]["designates"]["ranges"] == ["10.1.0.0/26"]
    assert "vnet-hub/snet-dmz" in _by(view, "exposed_zone")["dmz"]["designates"]["said"]
    assert _by(view, "forensic_access")["10.1.0.0/26"]["what"] == "reaches an isolated VM on ports 22, 3389"
    registry(names=[f"vm-dev-{i:02}" for i in range(12)])
    many = _by(_view(tmp_path), "exclusion")["vm-dev-*"]["designates"]["said"]
    assert many.startswith("12 VMs today: vm-dev-00,") and many.endswith(" …")


def test_an_unreadable_discovery_is_said_never_read_as_no_vm(tmp_path, registry):
    registry(raw="{not json")
    view = _view(tmp_path)
    assert view["discovery"]["state"] == "not_read" and "registry unreadable" in view["discovery"]["error"]
    dev = _by(view, "exclusion")["vm-dev-*"]["designates"]
    assert dev["vms"] is None and dev["said"].startswith("not known: registry unreadable")
    assert len(view["entries"]) == 12                      # the class never reads the discovery (§5.3)
    from glorfindel import discovery
    discovery._CACHE_FILE.unlink()
    assert relaxed.discovered() == (None, "the discovery has not run (no registry)")


# ── a file refused, a file absent ─────────────────────────────────────────────────────────────────

def test_a_refused_file_is_said_never_read_as_nothing_relaxed(tmp_path, registry):
    view = _view(tmp_path, "exceptions:\n  - {asset_pattern: vm, reason: 42}\n")
    assert view["entries"] is None and view["count"] is None
    assert view["config"]["state"] == "refused" and "un texte est attendu" in view["config"]["error"]
    assert view["config"]["digest"].startswith("sha256:")


def test_no_file_is_said_absent_and_the_defaults_relax_nothing(tmp_path, registry, monkeypatch):
    from glorfindel import config
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [tmp_path / "none.yaml"])
    view = relaxed.compute(NOW)
    assert view["config"]["state"] == "absent" and view["entries"] == [] and view["count"] == 0


# ── the watch writes it, in its own directory ─────────────────────────────────────────────────────

def test_the_watch_writes_it_whole_in_its_own_directory(tmp_path, registry):
    source = (ROOT / "glorfindel" / "relaxed.py").read_text(encoding="utf-8")
    assert "_STORE = runs_layout.dir_of(runs_layout.GLORFINDEL).joinpath(*STORE_PARTS)\n" in source
    assert relaxed.STORE_PARTS == ("config", "relaxed.json")
    from eregion_core import runs_layout
    assert "config" in runs_layout._DIRS["glorfindel"]
    view = relaxed.publish(NOW, cfg_path=_cfg(tmp_path))
    assert json.loads(relaxed._STORE.read_text(encoding="utf-8")) == view
    assert [p.name for p in relaxed._STORE.parent.iterdir()] == ["relaxed.json"]      # no temporary file left


def _hk(**over):
    """The parts of the watch's housekeeping the view needs: its thread, its --mode, its console."""
    import threading
    from glorfindel.watch.housekeeping import Housekeeping
    from glorfindel.watch.passes import Solo
    printed: list = []
    ns = SimpleNamespace(mode_override=None, _relaxed_said=False, _relaxed_thread=Solo("relaxed-view"),
                         _output_lock=threading.Lock(), console=SimpleNamespace(print=printed.append))
    ns.__dict__.update(over)
    ns.__dict__.setdefault("_relaxed_run", lambda: Housekeeping._relaxed_run(ns))
    return ns, printed


def test_the_watch_computes_it_in_a_thread_of_its_own_never_the_loops():
    """The review of CFG3: classing a long file takes seconds — never in the loop that answers « Verify »."""
    import threading
    from glorfindel.watch.housekeeping import Housekeeping
    ran: list = []
    hk, _ = _hk(_relaxed_run=lambda: ran.append(threading.current_thread().name))
    Housekeeping._publish_relaxed(hk)
    hk._relaxed_thread._thread.join(5)
    assert ran == ["relaxed-view"]
    gate = threading.Event()
    hk, _ = _hk(_relaxed_run=lambda: (ran.append("slow"), gate.wait(5)))
    Housekeeping._publish_relaxed(hk)
    Housekeeping._publish_relaxed(hk)                       # one pass at a time: the second is skipped
    gate.set()
    hk._relaxed_thread._thread.join(5)
    assert ran == ["relaxed-view", "slow"]


def test_the_watch_says_its_lines_once_bounded_and_escaped(tmp_path, registry, monkeypatch):
    from glorfindel import config
    from glorfindel.watch.housekeeping import Housekeeping
    evil = "exceptions:\n" + "".join(f"  - {{asset_pattern: vm-{i:02}, exclude_all: true, reason: \"[red]x{i}\"}}\n"
                                     for i in range(25))
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [_cfg(tmp_path, evil)])
    hk, printed = _hk(mode_override="non_disruptive")
    Housekeeping._relaxed_run(hk)
    assert relaxed._STORE.exists()
    assert printed[0].startswith("[yellow]⚠ the watch runs with --mode non_disruptive")
    assert printed[1] == "[dim]Relaxed : 25 entrée(s) relâchée(s) — ⚙ Config ▸ Relaxed[/dim]"
    assert len(printed) == 2 + 20 + 1 and printed[-1] == "[dim]  · … et 5 de plus, sur ⚙ Config ▸ Relaxed[/dim]"
    assert "« \\[red]x0 »" in printed[2]                        # its markup escaped, never obeyed
    Housekeeping._relaxed_run(hk)
    assert len(printed) == 23                                   # said once, at the start


def test_the_first_pass_starts_the_view_and_a_failure_never_stops_the_watch():
    from glorfindel.watch.loop import Watch
    calls: list = []

    def boom():
        calls.append("windows")
        raise RuntimeError("no windows")
    printed: list = []
    hk = SimpleNamespace(_observe_windows=boom, _publish_relaxed=lambda: calls.append("relaxed"))
    Watch._first_pass(SimpleNamespace(housekeeping=hk, console=SimpleNamespace(print=printed.append)))
    assert calls == ["windows", "relaxed"]


def test_it_is_computed_again_only_when_what_it_reads_changed(tmp_path, registry, monkeypatch):
    """The review of CFG3: each `classify` parses the whole file — quadratic. Nothing changed, no class."""
    from glorfindel import config_class
    calls: list = []
    real = config_class.classify
    monkeypatch.setattr(config_class, "classify", lambda b, a: (calls.append(1), real(b, a))[1])
    cfg = _cfg(tmp_path)
    first = relaxed.publish(NOW, cfg_path=cfg)
    n = len(calls)
    assert n >= 12
    again = relaxed.publish(NOW + timedelta(minutes=1), cfg_path=cfg)
    assert len(calls) == n                                       # nothing changed: not one class
    assert again["entries"] == first["entries"] and again["computed_at"] == first["computed_at"]
    assert relaxed.load(NOW + timedelta(minutes=1), cfg_path=cfg)["state"] == "fresh"    # its `at` written
    registry(names=VMS + ("vm-dev-03",))                          # the discovery changed
    relaxed.publish(NOW + timedelta(minutes=2), cfg_path=cfg)
    assert len(calls) == 2 * n
    relaxed.publish(NOW + timedelta(minutes=3), cfg_path=cfg, mode_override="human_only")
    assert len(calls) == 3 * n                                   # the session's --mode
    cfg.write_text(FILE + "# edited\n", encoding="utf-8")
    relaxed.publish(NOW + timedelta(minutes=4), cfg_path=cfg, mode_override="human_only")
    assert len(calls) == 4 * n                                   # the file
    relaxed.publish(NOW + timedelta(minutes=4, seconds=relaxed.RECOMPUTE_S), cfg_path=cfg,
                    mode_override="human_only")
    assert len(calls) == 5 * n                                   # at most RECOMPUTE_S between two


def test_the_sessions_mode_is_said_in_the_view(tmp_path, registry):
    view = relaxed.compute(NOW, _cfg(tmp_path), mode_override="non_disruptive")
    assert view["override"]["mode"] == "non_disruptive" and "--mode non_disruptive" in view["override"]["said"]
    assert relaxed.compute(NOW, _cfg(tmp_path))["override"] is None
    assert "(view.override || {}).said" in JS


def test_a_registry_the_watch_may_not_read_is_said_never_raised(registry, monkeypatch):
    from glorfindel import discovery
    real = Path.exists

    def denied(self, *a, **k):
        if self == discovery._CACHE_FILE:
            raise PermissionError(13, "Permission denied")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "exists", denied)
    names, why = relaxed.discovered()
    assert names is None and why.startswith("registry unreadable (PermissionError")


def test_a_mode_pattern_designates_a_vm_only_when_resolve_gives_its_mode(tmp_path, registry):
    """Two patterns as long that disagree give the most prudent mode (`resolve`): the bold one never holds the VM."""
    registry(names=["vm-aa", "vm-ab"])
    text = ("autonomy:\n  assets:\n    - {match: \"vm-a*\", mode: non_disruptive}\n"
            "    - {match: \"vm-*a\", mode: human_only}\n")
    assert _by(_view(tmp_path, text), "mode")["vm-a*"]["designates"]["vms"] == ["vm-ab"]


def test_conflicting_twins_are_said_without_a_false_reason(tmp_path, registry):
    text = "autonomy:\n  assets:\n    - {match: vm-a, mode: human_only}\n    - {match: vm-a, mode: non_disruptive}\n"
    [line] = _view(tmp_path, text)["entries"]
    assert line["where"] == "autonomy.assets[1]" and line["latent"] is True
    assert "another entry holds the same VM today: it relaxes the day that one goes" in line["why"]
    assert not any("gives the same" in w for w in line["why"])


# ── the console reads it, never computes nor writes it ────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    return console()


def test_the_route_reads_the_view_and_never_writes_it(client, tmp_path, registry, monkeypatch):
    from glorfindel import config
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [_cfg(tmp_path)])
    out = client.get("/api/config/relaxed").json()
    assert out["state"] == "absent" and out["view"] is None and "what is relaxed is not known" in out["said"]
    assert not relaxed._STORE.exists()                         # absent it was, absent it stays
    relaxed.publish()                                          # the watch writes it
    before = relaxed._STORE.read_bytes()
    out = client.get("/api/config/relaxed").json()
    assert out["state"] == "fresh" and out["said"] == "" and out["file_changed"] is False
    assert out["view"]["count"] == 12 and relaxed._STORE.read_bytes() == before


def test_a_view_old_unreadable_refused_or_of_another_file_is_said(tmp_path, registry):
    store, cfg = tmp_path / "relaxed.json", _cfg(tmp_path)
    relaxed.publish(NOW, store, cfg)
    assert relaxed.load(NOW + timedelta(seconds=60), store, cfg)["state"] == "fresh"
    old = relaxed.load(NOW + timedelta(minutes=12), store, cfg)
    assert old["state"] == "stale" and old["said"].startswith("computed 12 min ago") and old["view"]["count"] == 12
    cfg.write_text(FILE + "# edited by hand\n", encoding="utf-8")
    assert relaxed.load(NOW, store, cfg)["file_changed"] is True
    for bad in ("{not json", json.dumps({"v": 1, "at": NOW.isoformat(), "config": {"state": "read"}, "entries": 3}),
                json.dumps([1])):
        store.write_text(bad, encoding="utf-8")
        out = relaxed.load(NOW, store, cfg)
        assert out["state"] == "unreadable" and out["view"] is None and "can't be read" in out["said"]
    relaxed.publish(NOW, store, _cfg(tmp_path, "exceptions: 3\n"))
    out = relaxed.load(NOW, store, cfg)
    assert out["state"] == "refused" and "refused by the strict reading" in out["said"]


def test_the_console_never_computes_nor_writes_the_view():
    for path in (ROOT / "eregion_console").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for call in ("relaxed.publish", "relaxed.compute", "relaxed.entries"):
            assert call not in text, f"{path.name} calls {call}: the watch alone computes and writes the view"
    services = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    mounts = [v for v in services["war-room"]["volumes"] if isinstance(v, str)]
    assert any(v.endswith("/glorfindel:/app/runs/glorfindel:ro") for v in mounts)


# ── the page: /config, each line escaped, nothing read as « nothing relaxed » ────────────────────

JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")


def _body(head: str) -> str:
    assert head in JS, head
    return JS.split(head, 1)[1].split("\n}\n", 1)[0]


def test_the_config_page_shows_the_view_read_from_the_route():
    page = _body("async function refreshConfig() {")
    assert "await Promise.all([fetch('/api/config'), _fetchRelaxed()]);" in page
    assert "      ${_relaxedConfig()}\n\n      ${_sectionsConfig()}\n" in page
    assert "const r = await fetch('/api/config/relaxed');" in _body("async function _fetchRelaxed() {")


def test_the_page_says_what_is_wrong_and_shows_nothing_relaxed_only_from_a_list():
    view = _body("function _relaxedConfig() {")
    assert "const entries = Array.isArray(view.entries) ? view.entries : null;" in view
    assert "const none = entries && !entries.length" in view
    assert "map(w => `<div class=\"relaxed-warn\">⚠ ${_attr(w)}</div>`)" in view
    assert "d.file_changed ?" in view and "disc.state !== 'read'" in view
    row = _body("function _relaxedRow(e) {")
    for shown in ("${_attr(e.object)}", "${_attr(e.what)}", "« ${_attr(e.reason)} »", "no reason",
                  "${_attr((e.designates || {}).said || '')}", "by ${_attr(e.by)}", "${_attr(e.where)}"):
        assert shown in row, shown
    assert "e.latent" in row and "title=\"${_attr(_LATENT_TIP)}\">latent</span>" in row
