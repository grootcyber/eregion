"""PRI2b (#1225): the push to Imladris reads `assets:` as the watch reads it, writes the format Imladris's
release reads, migrates Imladris at the push and back, and never lowers a level
(docs/design/classification.md §5.5, §5.6; PR4, PR5).

The oracle is the watch's own reading (`glorfindel.config._parse_config`), never host_config.py's: the
two readers are compared on the same configs, and what the push writes is read back by the watch. The
order of the modes and of the levels is written here.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from glorfindel.config import ConfigError, _parse_config

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "infra" / "glorfindel-host"
_spec = importlib.util.spec_from_file_location("host_config_pri2b", HOST / "host_config.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)

PRUDENCE = {"human_only": 0, "non_disruptive": 1}
RANK = {"quiet": 0, "standard": 1, "essential": 2}
NEW = "/eregion-watch v0.6.10\n/eregion-war-room v0.6.10\n/eregion-bot v0.6.10\n"
OLD = "/eregion-watch v0.6.9\n/eregion-war-room v0.6.9\n/eregion-bot v0.6.9\n"
PROBES = ("vm-a", "vm-a1", "vm-ab", "vm-b", "vm-1ax", "vm-erp-qa", "vm-erp-01", "x")


def watch(data: dict):
    """What the watch reads: its one model of the two formats, or ConfigError."""
    return _parse_config(data).autonomy


def names(*cfgs) -> list[str]:
    """Each name and pattern cited by these configs (case ignored), and a few names no config cites."""
    cited = [r["match"].lower() for c in cfgs for r in hc.rules_of(c)]
    return list(dict.fromkeys([*cited, *PROBES]))


def push(local, h0=None, *, release=NEW, human_only=False, to=""):
    reads, said = hc.read_release(release)
    h0_cfg, why = (None, "absent, empty or unread") if h0 is None else hc.read_h0(yaml.safe_dump(h0), reads)
    return hc.host_config(local, h0_cfg, h0_why=why, human_only=human_only, reads_assets=reads,
                          release_why=said, to=to)


def rows(report) -> dict[str, tuple[str, str, str]]:
    return {name: (mode, level, why) for name, mode, level, why in report if name != "*"}


def said(report) -> str:
    return "\n".join(why for *_, why in report)


# ── PR5: the two readers, the same verdict, the same modes, the same levels ──────────────────────

MATCHES = st.sampled_from(["vm-a", "VM-A", "vm-b", "vm-*", "vm-a*", "vm-?", "", "  ", 5, None])
MODES = st.sampled_from(["human_only", "non_disruptive", "full_auto", "Human_only", None, 3])
PRIORITIES = st.sampled_from(["essential", "standard", "quiet", "critical", "Essential", None, 1])
REASONS = st.sampled_from(["", "the ERP database", "two\nlines", "x" * 201, "x" * 200, "a b", None, 2])
FLAGS = st.sampled_from([True, False, None, "true", 1])
NAMES = st.sampled_from([[], ["vm-*"], "vm-*", [3], None])
ANY_ENTRY = st.one_of(
    st.fixed_dictionaries({}, optional={"match": MATCHES, "mode": MODES, "priority": PRIORITIES,
                                        "reason": REASONS, "critical": FLAGS, "until": st.just("x")}),
    st.sampled_from(["not a table", 3]))
ANY_LIST = st.one_of(st.lists(ANY_ENTRY, max_size=4), st.sampled_from(["x", {}, None]))
ANY_ASSETS = st.one_of(
    st.fixed_dictionaries({}, optional={"default_mode": MODES, "allow_destructive": NAMES, "list": ANY_LIST,
                                        "ttl": st.just(3)}),
    st.sampled_from([None, "x", []]))
ANY_AUTONOMY = st.one_of(
    st.fixed_dictionaries({}, optional={"default": MODES, "allow_destructive": NAMES, "assets": ANY_LIST,
                                        "ttl": st.just(3)}),
    st.sampled_from([None, "x", []]))
ANY_CONFIG = st.fixed_dictionaries({}, optional={"assets": ANY_ASSETS, "autonomy": ANY_AUTONOMY})

# What the watch accepts, to compare the models and to push.
GOOD_MATCH = st.sampled_from(["vm-a", "VM-A", "vm-b", "vm-*", "vm-a*", "vm-?", "vm-1*", "vm-??x", "vm-erp-*",
                              "vm-erp-qa"])
GOOD_MODE = st.sampled_from(["human_only", "non_disruptive"])
GOOD_LEVEL = st.sampled_from(["essential", "standard", "quiet"])
ASSET_ENTRY = st.fixed_dictionaries({"match": GOOD_MATCH}, optional={
    "mode": GOOD_MODE, "priority": GOOD_LEVEL, "reason": st.just("why")}).filter(
    lambda e: "mode" in e or "priority" in e)
FORMER_ENTRY = st.fixed_dictionaries({"match": GOOD_MATCH, "mode": GOOD_MODE}, optional={"critical": st.booleans()})
GOOD_ASSETS = st.fixed_dictionaries({}, optional={
    "default_mode": GOOD_MODE, "allow_destructive": st.just(["vm-*"]),
    "list": st.lists(ASSET_ENTRY, max_size=5, unique_by=lambda e: e["match"].lower())}).map(lambda s: {"assets": s})
GOOD_FORMER = st.fixed_dictionaries({}, optional={
    "default": GOOD_MODE, "allow_destructive": st.just(["vm-*"]),
    "assets": st.lists(FORMER_ENTRY, max_size=5)}).map(lambda s: {"autonomy": s})
GOOD_CONFIG = st.one_of(GOOD_ASSETS, GOOD_FORMER, st.just({}))


def _default(data: dict) -> str:
    return ((data.get("assets") or {}).get("default_mode") or (data.get("autonomy") or {}).get("default")
            or "human_only")


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.one_of(ANY_CONFIG, GOOD_CONFIG))
def test_the_two_readers_give_the_same_verdict_modes_and_levels(data):
    """PR5: the watch refuses a config exactly when the push refuses it whole — the keys, the
    modes, the priorities, a reason that is not one line, an entry that says nothing, a match twice, both
    formats; one it reads, the two give each name and pattern the same mode and the same level."""
    try:
        model = watch(data)
    except ConfigError:
        model = None
    why = hc.refusal(data)
    assert (why == "") is (model is not None), (why, data)
    if model is None:
        return
    rules = hc.rules_of(data)
    for name in names(data):
        assert hc.resolve(rules, name, _default(data)) == model.resolve(name), name
        assert hc.level_of(rules, name) == model.level_of(name), name


@pytest.mark.parametrize("section", [
    {"list": [{"match": "vm-a", "priority": "critical"}]},                   # an unknown priority
    {"list": [{"match": "", "priority": "essential"}]},                      # an empty match
    {"list": [{"match": "vm-a", "priority": "essential"}, {"match": "VM-A", "mode": "human_only"}]},
    {"list": [{"match": "vm-a"}]},                                           # neither mode nor priority
    {"list": [{"match": "vm-a", "priority": "essential", "critical": True}]},  # a key more
    {"list": [{"match": "vm-a", "priority": "essential", "reason": "two\nlines"}]},
], ids=["priority-unknown", "match-empty", "match-twice", "says-nothing", "key-more", "reason-two-lines"])
def test_an_imladris_config_the_watch_refuses_keeps_nothing_of_it(section):
    """M7828, M7829 (§5.5, PR5): a config of Imladris the watch would refuse is unknown whole — every VM in human_only, none
    of its levels kept (only the workstation's essential), and said; never one entry dropped and the rest
    kept. Its essential vm-db is not kept beside the entry refused."""
    h0 = {"assets": {"list": [{"match": "vm-db", "mode": "non_disruptive", "priority": "essential"},
                              *section["list"]]}}
    with pytest.raises(ConfigError):
        watch(h0)
    local = {"assets": {"list": [{"match": "vm-new", "priority": "essential"}]}}
    out, report = push(local, h0)
    model = watch(out)
    assert model.resolve("vm-db") == "human_only" and model.level_of("vm-db") == "standard"
    assert model.level_of("vm-new") == "essential"
    assert "Imladris's config of an unknown shape" in said(report)


def test_both_formats_on_imladris_keep_nothing():
    """M7827: both formats in Imladris's file — the watch refuses it whole, so nothing of it is kept."""
    h0 = {"autonomy": {"assets": [{"match": "vm-db", "mode": "non_disruptive", "critical": True}]},
          "assets": {"list": [{"match": "vm-db", "mode": "non_disruptive", "priority": "essential"}]}}
    out, report = push({}, h0)
    assert watch(out).level_of("vm-db") == "standard" and watch(out).resolve("vm-db") == "human_only"
    assert "both formats" in said(report)


@pytest.mark.parametrize("local", [
    {"autonomy": {"assets": [{"match": "vm-a", "mode": "human_only"}]},
     "assets": {"list": [{"match": "vm-a", "priority": "essential"}]}},
    {"assets": {"list": [{"match": "vm-a", "priority": "critical"}]}},
    {"assets": {"list": [{"match": "vm-a", "priority": "essential"}, {"match": "VM-A", "mode": "human_only"}]}},
], ids=["both-formats", "priority-unknown", "match-twice"])
def test_a_workstation_config_the_watch_refuses_is_never_pushed(tmp_path, capsys, local):
    """M7827 (§5.5): a file of the workstation the watch would refuse — both formats in
    it, an unknown priority, a match twice — is never pushed: the push stops, nothing written, and says it.
    Under HUMAN_ONLY=1 the gesture goes on, none of its entries carried, said."""
    src, dst, h0 = tmp_path / "local.yaml", tmp_path / "out.yaml", tmp_path / "h0.yaml"
    src.write_text(yaml.safe_dump(local), encoding="utf-8")
    h0.write_text(yaml.safe_dump({"autonomy": {"assets": [{"match": "vm-b", "mode": "non_disruptive"}]}}))
    assert hc.main([str(src), str(dst), "--h0", str(h0)]) == 1
    assert not dst.exists()
    err = capsys.readouterr().err
    assert "the workstation's config is of an unknown shape" in err and "nothing sent" in err
    assert hc.main([str(src), str(dst), "--h0", str(h0), "--human-only"]) == 0
    model = watch(yaml.safe_load(dst.read_text(encoding="utf-8")))
    assert model.resolve("vm-b") == "human_only" and model.level_of("vm-a") == "standard"
    assert "none of its entries carried (HUMAN_ONLY=1)" in capsys.readouterr().out


def test_a_workstation_file_in_assets_is_never_copied_beside_autonomy():
    """PRI2a's finding: `out = dict(cfg)` copied a workstation's assets: and added autonomy: — both formats,
    a file the watch refuses whole. The section is computed, never copied, in the format Imladris reads."""
    local = {"monitoring_backends": [{"name": "law"}],
             "assets": {"default_mode": "non_disruptive", "list": [{"match": "vm-a", "mode": "non_disruptive"}]}}
    for release, section in ((NEW, "assets"), (OLD, "autonomy")):
        out, _ = push(local, {"autonomy": {"assets": []}}, release=release)
        assert set(out) == {"monitoring_backends", section}
        assert watch(out).resolve("vm-a") == "human_only"


# ── PR4: never a level lowered, name by name, patterns included ──────────────────────────────────

ERP = {"assets": {"list": [{"match": "vm-erp-*", "priority": "essential"},
                           {"match": "vm-dev-*", "priority": "quiet", "reason": "the developers' VMs"},
                           {"match": "vm-gondolin", "mode": "non_disruptive"}]}}


def test_a_workstation_level_that_lowers_imladris_is_not_pushed_and_said():
    """M7830 (PR4): `vm-erp-qa: standard` on the workstation would lower vm-erp-qa, essential on Imladris by
    its pattern: not pushed, said « lowers vm-erp-qa on Imladris: not pushed »; a raise is pushed
    (`vm-dev-01: standard` above `vm-dev-*: quiet`); Imladris's own levels kept, quiet and patterns too."""
    local = {"assets": {"list": [{"match": "vm-erp-qa", "priority": "standard"},
                                 {"match": "vm-dev-01", "priority": "standard"}]}}
    out, report = push(local, ERP)
    model = watch(out)
    assert model.level_of("vm-erp-qa") == "essential" and model.level_of("vm-erp-01") == "essential"
    assert model.level_of("vm-dev-01") == "standard" and model.level_of("vm-dev-02") == "quiet"
    assert "lowers vm-erp-qa on Imladris: not pushed" in rows(report)["vm-erp-qa"][2]
    assert model.resolve("vm-gondolin") == "non_disruptive"


def test_a_workstation_pattern_that_says_standard_is_never_pushed():
    """M7831, the safe side the note proposes: a pattern of the workstation that says standard could lower a
    VM no name shows — `vm-??x` is longer than Imladris's `vm-1*: essential`, and would take vm-1ax, which
    neither config names. Name by name, nothing is lowered; the VM would be: never pushed, said."""
    h0 = {"assets": {"list": [{"match": "vm-1*", "priority": "essential"}]}}
    local = {"assets": {"list": [{"match": "vm-??x", "priority": "standard"}]}}
    assert watch({"assets": {"list": [*h0["assets"]["list"], *local["assets"]["list"]]}}).level_of("vm-1ax") \
        == "standard"                                   # what it would do
    out, report = push(local, h0)
    assert watch(out).level_of("vm-1ax") == "essential"
    assert "standard on a pattern from the workstation: not pushed" in rows(report)["vm-??x"][2]


def test_quiet_comes_from_imladris_only():
    """M7832: a quiet of the workstation is never pushed, a name or a pattern — not even under an Imladris
    pattern already quiet, where it would lower nothing today and hold the VM quiet once Imladris raises
    the pattern; Imladris's quiet, posed by hand on the host, is kept by every push (its exemption under an
    essential pattern too)."""
    h0 = {"assets": {"list": [{"match": "vm-erp-*", "priority": "essential"},
                              {"match": "vm-erp-qa", "priority": "quiet"},
                              {"match": "vm-dev-*", "priority": "quiet"}]}}
    local = {"assets": {"list": [{"match": "vm-b", "priority": "quiet"}, {"match": "vm-c*", "priority": "quiet"},
                                 {"match": "vm-dev-01", "priority": "quiet"}]}}
    out, report = push(local, h0)
    model = watch(out)
    assert model.level_of("vm-erp-qa") == "quiet" and model.level_of("vm-erp-01") == "essential"
    assert model.level_of("vm-b") == "standard" and model.level_of("vm-c1") == "standard"
    assert model.level_of("vm-dev-01") == "quiet"                          # Imladris's pattern
    assert {e["match"] for e in out["assets"]["list"]} == {"vm-erp-*", "vm-erp-qa", "vm-dev-*"}
    for name in ("vm-b", "vm-c*", "vm-dev-01"):
        assert "quiet comes from Imladris only" in rows(report)[name][2], name


def test_imladris_s_levels_are_kept_its_patterns_and_reasons_included():
    """M7833: every level of Imladris kept — a pattern's level although its mode is never carried, its
    reason; an entry that carries only a level pushed without a mode (the push never writes a mode it has
    not)."""
    h0 = {"assets": {"list": [{"match": "vm-erp-*", "mode": "non_disruptive", "priority": "essential",
                               "reason": "the ERP"}, {"match": "vm-db", "priority": "essential"}]}}
    out, _ = push({}, h0)
    entries = {e["match"]: e for e in out["assets"]["list"]}
    assert entries == {"vm-erp-*": {"match": "vm-erp-*", "priority": "essential", "reason": "the ERP"},
                       "vm-db": {"match": "vm-db", "priority": "essential"}}
    assert watch(out).resolve("vm-erp-01") == "human_only"


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(GOOD_CONFIG, GOOD_CONFIG, st.sampled_from([NEW, OLD, "", "/eregion-watch 0123abc\n"]),
       st.booleans(), st.sampled_from(["", "autonomy"]))
def test_the_push_never_lowers_a_level_nor_makes_a_mode_bolder(h0, local, release, human_only, to):
    """PR4, read by the watch: for any pair (Imladris, workstation), any release, HUMAN_ONLY=1 or not, the
    config pushed is one the watch reads, in the format the release reads; for each name and pattern cited
    (and names no one cites), its level is at least Imladris's and its mode never bolder; a quiet only
    where Imladris says it; every essential entry of either kept; HUMAN_ONLY=1 every mode human_only, the
    levels left as without it; each row of the report says what the watch reads."""
    reads, _ = hc.read_release(release)
    out, report = push(local, h0, release=release, human_only=human_only, to=to)
    pushed = watch(out)                                     # never a config the watch refuses
    assert ("assets" in out) is (reads and to != "autonomy") and ("autonomy" in out) is not ("assets" in out)
    trusted = hc.refusal(h0, reads) == ""
    on_h0 = watch(h0) if trusted else None
    for name in names(h0, local):
        if on_h0 is not None:
            assert RANK[pushed.level_of(name)] >= RANK[on_h0.level_of(name)], name
            assert PRUDENCE[pushed.resolve(name)] <= PRUDENCE[on_h0.resolve(name)], name
        else:
            assert pushed.resolve(name) == "human_only", name
        if pushed.level_of(name) == "quiet":
            assert on_h0 is not None and on_h0.level_of(name) == "quiet", name
        if human_only:
            assert pushed.resolve(name) == "human_only", name
    essentials = {r.match.lower() for r in pushed.assets if r.priority == "essential"}
    assert {r.match.lower() for r in watch(local).assets if r.priority == "essential"} <= essentials
    if on_h0 is not None:
        assert {r.match.lower() for r in on_h0.assets if r.priority == "essential"} <= essentials
    if human_only:
        plain = watch(push(local, h0, release=release, to=to)[0])
        assert all(pushed.level_of(n) == plain.level_of(n) for n in names(h0, local))
    for name, (mode, level, _) in rows(report).items():
        assert (mode, level) == (pushed.resolve(name), pushed.level_of(name)), name


# ── the version guard ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, reads", [
    (NEW, True),
    ("/eregion-watch v0.6.10\n", True),                                         # the others not running
    ("/eregion-watch v1.0.0\n/eregion-bot v0.7.2\n/eregion-restore v0.6.10\n", True),
    (OLD, False),
    ("/eregion-watch v0.6.10\n/eregion-war-room v0.6.9\n", False),              # one container behind
    ("/eregion-watch v0.6.10\n/eregion-restore v0.5.12\n", False),
    ("/eregion-watch 9ebda6af3c1d\n", False),                                    # a commit deployed by hand
    ("/eregion-watch <no value>\n", False),
    ("/eregion-watch v0.6.10-rc1\n", False),
    ("/eregion-watch\n", False),
    ("/eregion-war-room v0.6.10\n/eregion-bot v0.6.10\n", False),               # no watch read
    ("/eregion-other v0.5.0\n/eregion-watch v0.6.10\n", True),                  # a container that reads nothing
    ("", False),
], ids=["all", "watch-alone", "later", "before", "one-behind", "restore-behind", "a-commit", "no-label",
        "candidate", "empty-label", "no-watch", "another", "unread"])
def test_the_release_is_read_where_the_cd_reads_it(text, reads):
    """M7834, M7835: assets: only when the watch is read and every container that mounts the config runs a
    release at ASSETS_SINCE or after — an older one, a commit, no label, nothing read: the former format."""
    assert hc.read_release(text)[0] is reads


def test_an_old_or_unreadable_release_receives_the_former_format_never_bolder():
    """M7836 (§5.5): toward a release before the guard, or one that does not read, the push writes the former
    format, converted as `glorfindel config migrate --to autonomy` converts — the levels kept as critical:
    true, never a bolder mode — and says it; Imladris in assets: on such a release is refused by its watch:
    nothing of it kept."""
    h0 = {"autonomy": {"assets": [{"match": "vm-gondolin", "mode": "non_disruptive", "critical": True},
                                  {"match": "vm-erp-*", "mode": "non_disruptive", "critical": True}]}}
    for release in (OLD, "/eregion-watch 9ebda6af\n", ""):
        out, report = push({"assets": {"list": [{"match": "vm-new", "priority": "essential"}]}}, h0,
                           release=release)
        assert "assets" not in out
        model = watch(out)
        assert model.resolve("vm-gondolin") == "non_disruptive" and model.resolve("vm-erp-01") == "human_only"
        assert {n for n in ("vm-gondolin", "vm-erp-01", "vm-new") if model.level_of(n) == "essential"} == {
            "vm-gondolin", "vm-erp-01", "vm-new"}
        assert "the former format autonomy: written" in said(report)
    out, report = push({}, ERP, release=OLD)
    assert watch(out).level_of("vm-erp-01") == "standard" and watch(out).resolve("vm-gondolin") == "human_only"
    assert "assets:, which Imladris's release does not read" in said(report)


def test_the_first_release_that_reads_assets_is_the_guard_s():
    """ASSETS_SINCE is the release that brings PRI2a and PRI2b together (one release, §5.5): until
    it is cut, above every version the CHANGELOG has released; once cut, the first that names them."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = re.findall(r"^## \[(\d+)\.(\d+)\.(\d+)\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    released = [tuple(int(x) for x in s[:3]) for s in sections]
    bringing = [(tuple(int(x) for x in s[:3]), s[3]) for s in sections if "(PRI2a" in s[3]]
    if not bringing:
        assert hc.ASSETS_SINCE > max(released)
        return
    first, body = min(bringing)
    assert first == hc.ASSETS_SINCE and "(PRI2b" in body


def test_the_containers_read_are_those_that_mount_the_config():
    """The push reads the release of each container docker-compose.yml mounts glorfindel-config.yaml in — the
    watch first —, the CD's three among them, and its version as the CD's TAG_RE reads it."""
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    mounting = {s["container_name"].replace("${EREGION_INSTANCE:-eregion}", "eregion")
                for s in compose["services"].values()
                if any("glorfindel-config.yaml" in str(v) for v in s.get("volumes") or [])}
    assert set(hc.CONTAINERS) == mounting and hc.CONTAINERS[0] == "eregion-watch"
    cd = (HOST / "cd" / "eregion_cd.py").read_text(encoding="utf-8")
    assert re.search(r'^TAG_RE = r"(.*)"$', cd, re.M).group(1) == hc.VERSION_RE.pattern
    three = re.search(r"^CONTAINERS = \((.*)\)$", cd, re.M).group(1)
    assert set(re.findall(r'"([^"]+)"', three)) <= set(hc.CONTAINERS)


def test_a_release_label_reaches_the_terminal_printable_only(tmp_path, capsys):
    src, dst, rel = tmp_path / "local.yaml", tmp_path / "out.yaml", tmp_path / "rel"
    src.write_text("{}\n", encoding="utf-8")
    rel.write_text("/eregion-watch v0.6\x1b[2J\n", encoding="utf-8")
    assert hc.main([str(src), str(dst), "--release", str(rel)]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out and "v0.6?[2J" in out


# ── the migration at the push, and the way back ───────────────────────────────────────────────────

FORMER = {"autonomy": {"default": "human_only", "assets": [
    {"match": "vm-gondolin", "mode": "non_disruptive", "critical": True},
    {"match": "vm-bree", "mode": "non_disruptive"},
    {"match": "VM-BREE", "mode": "human_only"},
    {"match": "vm-erp-*", "mode": "human_only", "critical": True}]}}


def test_imladris_in_autonomy_is_migrated_by_the_push_at_equal_values():
    """M7837 (§5.5): Imladris still in autonomy:, toward a release that reads assets: — assets: written, each
    name's mode and level equal (the duplicates merged as Imladris reads them: the most prudent mode), said."""
    out, report = push({}, FORMER)
    assert "autonomy" not in out and out["assets"]["default_mode"] == "human_only"
    before, after = watch(FORMER), watch(out)
    for name in ("vm-gondolin", "vm-bree", "vm-erp-01", "vm-erp-*"):
        assert after.level_of(name) == before.level_of(name), name
    for name in ("vm-gondolin", "vm-bree"):
        assert after.resolve(name) == before.resolve(name), name
    assert "Imladris: autonomy: migrated to assets:, at equal values" in said(report)


def test_the_way_back_writes_the_former_format_by_the_same_conversion():
    """M7838 (§5.6): `--to autonomy` (make imladris-push CONFIG_FORMAT=autonomy) on a release that reads assets: —
    Imladris's assets: written in the former format, its exact modes kept, never a bolder one, each level
    at least kept (quiet and standard dropped, said, its reason too)."""
    h0 = {"assets": {"list": [{"match": "vm-gondolin", "mode": "non_disruptive", "priority": "essential"},
                              {"match": "vm-erp-*", "priority": "essential"},
                              {"match": "vm-erp-qa", "priority": "quiet", "reason": "the QA copy"},
                              {"match": "vm-db", "priority": "essential"}]}}
    out, report = push({}, h0, to="autonomy")
    assert "assets" not in out
    model = watch(out)
    assert model.resolve("vm-gondolin") == "non_disruptive" and model.resolve("vm-db") == "human_only"
    assert {n: model.level_of(n) for n in ("vm-gondolin", "vm-erp-01", "vm-erp-qa", "vm-db")} == {
        n: "essential" for n in ("vm-gondolin", "vm-erp-01", "vm-erp-qa", "vm-db")}
    why = rows(report)["vm-erp-qa"][2]
    assert "priority quiet dropped" in why and "its reason dropped" in why
    assert "--to autonomy: the former format written (the way back)" in said(report)


@settings(max_examples=200, deadline=None)
@given(GOOD_ASSETS)
def test_the_conversion_is_glorfindel_config_migrate_s(data):
    """The push's conversion to the former format is the one of `glorfindel config migrate --to autonomy`
    (glorfindel/config_migrate.py `_to_autonomy`): the same entries, for any assets: section."""
    from glorfindel.config_migrate import migrated
    expected = migrated(data, "autonomy")[0]["autonomy"].get("assets", [])
    assert hc.to_autonomy(hc.rules_of(data), _default(data))[0] == expected


# ── HUMAN_ONLY=1 ──────────────────────────────────────────────────────────────────────────────────

def test_human_only_is_never_blocked_and_leaves_the_levels(tmp_path, capsys):
    """M7839: HUMAN_ONLY=1, whatever the release read says (nothing, a commit, an old one): every mode human_only,
    the levels as without it, the gesture never refused."""
    src, dst, h0, rel = (tmp_path / n for n in ("local.yaml", "out.yaml", "h0.yaml", "rel"))
    src.write_text(yaml.safe_dump({"assets": {"list": [{"match": "vm-new", "priority": "essential"}]}}))
    h0.write_text(yaml.safe_dump(FORMER), encoding="utf-8")
    for text in ("", "/eregion-watch 9ebda6af\n", OLD, NEW):
        rel.write_text(text, encoding="utf-8")
        assert hc.main([str(src), str(dst), "--h0", str(h0), "--release", str(rel), "--human-only"]) == 0
        model = watch(yaml.safe_load(dst.read_text(encoding="utf-8")))
        assert {model.resolve(n) for n in ("vm-gondolin", "vm-bree", "vm-new")} == {"human_only"}
        assert {n for n in ("vm-gondolin", "vm-erp-01", "vm-new", "vm-bree") if model.level_of(n) == "essential"} \
            == {"vm-gondolin", "vm-erp-01", "vm-new"}
        assert "HUMAN_ONLY=1: every VM back to human_only" in capsys.readouterr().out


# ── the report ────────────────────────────────────────────────────────────────────────────────────

def test_the_report_never_says_kept_for_what_imladris_will_refuse():
    """M7840, PRI2a's finding: the report said « kept » for a workstation's file already migrated, which Imladris's
    watch would refuse. Each row is now read on the config written, as the watch reads it; a mode not
    carried, a level not pushed, a format converted: said."""
    local = {"assets": {"list": [{"match": "vm-gondolin", "mode": "human_only", "priority": "essential"},
                                 {"match": "vm-erp-qa", "priority": "standard"}]}}
    out, report = push(local, ERP, release=OLD)          # ERP is in assets: — refused by a release before
    model = watch(out)
    for name, (mode, level, why) in rows(report).items():
        assert (mode, level) == (model.resolve(name), model.level_of(name))
        assert "kept from Imladris" not in why
    out, report = push(local, ERP)
    assert rows(report)["vm-gondolin"] == ("non_disruptive", "essential",
                                           "kept from Imladris; essential from the workstation")
    assert rows(report)["vm-erp-*"][:2] == ("human_only", "essential")
