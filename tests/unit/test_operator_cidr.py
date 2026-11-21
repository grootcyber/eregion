"""SEC-G (audit of 13/11, V-40): the one SSH source toward Imladris and Orodruin — the operator's public
IPv4 address, in /32.

OPERATOR_CIDR was, by default, a third-party service's answer suffixed « /32 », and both modules'
validation refused 0.0.0.0/0 alone: 0.0.0.0/1, ::/0, a private range passed. Now scripts/operator_cidr.py
checks the value (or the service's answer, said) before any plan, and both modules' validation refuses
the same: tests here for the script and the Makefile (a fake terraform, a local HTTP server standing for
the service — no network); infra/*/tests/*.tftest.hcl for Terraform's own validation.
"""
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "operator_cidr.py"
MODULES = (ROOT / "infra" / "glorfindel-host" / "variables.tf", ROOT / "infra" / "orodruin" / "variables.tf")
needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")


def _script(value=None, url=None):
    env = {k: v for k, v in os.environ.items() if k not in ("EREGION_OPERATOR_CIDR", "EREGION_OPERATOR_IP_URL")}
    if value is not None:
        env["EREGION_OPERATOR_CIDR"] = value
    env["EREGION_OPERATOR_IP_URL"] = url or "http://127.0.0.1:9/unreachable"
    return subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("value", ["203.0.113.7/32", "198.51.100.1/32", "8.8.8.8/32", "1.0.0.1/32",
                                   "100.63.255.255/32", "100.128.0.1/32", "172.32.0.1/32", "223.255.255.255/32"])
def test_one_public_address_in_32_passes(value):
    res = _script(value)
    assert res.returncode == 0, res.stderr
    assert res.stdout == f"{value}\n" and res.stderr == ""


@pytest.mark.parametrize("value, said", [
    ("0.0.0.0/0", "pas un /32"), ("0.0.0.0/1", "pas un /32"), ("128.0.0.0/1", "pas un /32"),
    ("203.0.113.0/24", "pas un /32"), ("203.0.113.7/31", "pas un /32"), ("203.0.113.7", "pas un /32"),
    ("::/0", "une IPv6"), ("2001:db8::7/128", "une IPv6"), ("/32", "pas une adresse IPv4"),
    ("10.1.2.3/32", "10.0.0.0/8"), ("172.16.0.1/32", "172.16.0.0/12"), ("172.31.255.255/32", "172.16.0.0/12"),
    ("192.168.1.20/32", "192.168.0.0/16"), ("127.0.0.1/32", "127.0.0.0/8"), ("169.254.169.254/32", "169.254.0.0/16"),
    ("100.64.0.1/32", "100.64.0.0/10"), ("100.127.255.254/32", "100.64.0.0/10"), ("0.1.2.3/32", "0.0.0.0/8"),
    ("192.0.0.9/32", "192.0.0.0/24"), ("198.18.0.1/32", "198.18.0.0/15"), ("224.0.0.1/32", "224.0.0.0/4"),
    ("255.255.255.255/32", "240.0.0.0/4"), ("203.0.113.256/32", "pas une adresse IPv4"),
    ("203.0.113.07/32", "pas une adresse IPv4"), (" 203.0.113.7/32", "pas une adresse IPv4"),
    ("203.0.113.7/32\n", "pas un /32"), ("$(touch x)/32", "pas une adresse IPv4"),
])
def test_a_range_an_ipv6_a_private_or_reserved_address_is_refused(value, said):
    res = _script(value)
    assert res.returncode == 1 and res.stdout == ""
    assert "OPERATOR_CIDR refusé" in res.stderr and said in res.stderr, res.stderr


class _Service:
    """The third-party service, local: answers `body` (bytes) with `status`."""

    def __init__(self, body=b"203.0.113.9\n", status=200):
        outer = self
        self.body, self.status, self.asked = body, status, 0

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                outer.asked += 1
                self.send_response(outer.status)
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def service():
    made = []

    def make(*a, **k):
        made.append(_Service(*a, **k))
        return made[-1]
    yield make
    for s in made:
        s.close()


def test_without_operator_cidr_the_service_s_answer_is_checked_and_said(service):
    svc = service()
    res = _script(url=svc.url)
    assert res.returncode == 0, res.stderr
    assert res.stdout == "203.0.113.9/32\n" and svc.asked == 1
    assert "OPERATOR_CIDR non posé" in res.stderr and "un service tiers" in res.stderr
    assert "203.0.113.9" not in res.stderr                    # said, the address never printed but on stdout


@pytest.mark.parametrize("body, status", [
    (b"10.0.0.1", 200), (b"192.168.1.1\n", 200), (b"", 200), (b"<html>blocked</html>", 200),
    (b"2001:db8::1", 200), (b"203.0.113.9/24", 200), (b"9" * 200, 200), (b"203.0.113.9", 503),
    (b"\xff\xfe", 200), (b"203.0.113.9 203.0.113.10", 200),
])
def test_a_service_answer_that_is_not_one_public_address_is_refused_never_suffixed(service, body, status):
    """The old default: `$(shell curl …)/32` — an empty answer became « /32 », a range « …/24/32 »."""
    res = _script(url=service(body, status).url)
    assert res.returncode == 1 and res.stdout == ""
    assert "OPERATOR_CIDR refusé" in res.stderr


def test_a_service_that_does_not_answer_is_refused():
    res = _script(url="http://127.0.0.1:9/")
    assert res.returncode == 1 and res.stdout == "" and "ne répond pas" in res.stderr


def test_the_service_is_never_asked_when_operator_cidr_is_set(service):
    svc = service(b"198.51.100.200")
    assert _script("203.0.113.7/32", url=svc.url).stdout == "203.0.113.7/32\n" and svc.asked == 0


# ── the same check in both modules' validation ───────────────────────────────────────

def _validation(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    block = text[text.index('variable "operator_cidr"'):]
    return block[:block.index("\n}\n")]


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.parent.name)
def test_both_modules_refuse_the_same_ranges_as_the_script(path):
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import operator_cidr
    finally:
        sys.path.pop(0)
    block = _validation(path)
    ranges = re.search(r"for r in \[([^\]]*)\]", block)
    assert ranges, block
    assert tuple(re.findall(r'"([^"]+)"', ranges.group(1))) == operator_cidr.RESERVED
    form = re.search(r'can\(regex\("\^(.*)/32\$", var\.operator_cidr\)\)', block)
    assert form and form.group(1).replace("\\\\", "\\") == operator_cidr.FORM.pattern
    assert "0.0.0.0/0" not in block.split("condition", 1)[1].split("error_message", 1)[0]   # never the only refusal


# ── the Makefile: checked before any plan, never expanded by make ─────────────────────

def _make(tmp_path, target, *args, environ=None):
    env = {k: v for k, v in os.environ.items() if k not in ("OPERATOR_CIDR", "EREGION_OPERATOR_CIDR", "NO_WATCH",
                                                           "WATCH_PRINCIPALS", "EREGION_OPERATOR_IP_URL")}
    env["EREGION_OPERATOR_IP_URL"] = "http://127.0.0.1:9/unreachable"
    env.update(environ or {})
    fake = tmp_path / "tf"
    fake.write_text('#!/bin/sh\necho "No state" >&2; exit 1\n')
    fake.chmod(0o755)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, "HOST_TF=echo terraform",
                          "ORO_TF=echo terraform", "NO_WATCH=1", *args],
                         env=env, capture_output=True, text=True, timeout=60)
    return res


TARGETS = ("imladris-plan", "imladris-up", "imladris-down", "orodruin-plan", "orodruin-up", "orodruin-lock",
           "orodruin-down")


@needs_make
@pytest.mark.parametrize("target", TARGETS)
def test_every_terraform_target_hands_the_checked_address(tmp_path, target):
    res = _make(tmp_path, target, "OPERATOR_CIDR=203.0.113.7/32")
    assert res.returncode == 0, res.stderr
    verb = {"plan": "plan", "up": "apply", "lock": "apply", "down": "destroy"}[target.split("-", 1)[1]]
    (line,) = [ln for ln in res.stdout.splitlines() if ln.startswith(f"terraform {verb}")]
    assert "-var=operator_cidr=203.0.113.7/32" in line.split()


@needs_make
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("value", ["0.0.0.0/1", "::/0", "10.0.0.5/32", "203.0.113.0/24"])
def test_a_wide_or_private_operator_cidr_stops_every_terraform_target(tmp_path, target, value):
    res = _make(tmp_path, target, f"OPERATOR_CIDR={value}")
    assert res.returncode != 0 and "OPERATOR_CIDR refusé" in res.stderr
    assert not re.search(r"^terraform (plan|apply|destroy)", res.stdout, re.M), res.stdout


@needs_make
def test_without_operator_cidr_the_service_answers_checked(tmp_path, service):
    svc = service(b"198.51.100.20\n")
    res = _make(tmp_path, "imladris-plan", environ={"EREGION_OPERATOR_IP_URL": svc.url})
    assert res.returncode == 0, res.stderr
    assert "-var=operator_cidr=198.51.100.20/32" in res.stdout and "un service tiers" in res.stderr
    svc_bad = service(b"")
    res = _make(tmp_path, "orodruin-plan", environ={"EREGION_OPERATOR_IP_URL": svc_bad.url})
    assert res.returncode != 0 and "terraform plan" not in res.stdout and "OPERATOR_CIDR refusé" in res.stderr


@needs_make
def test_operator_cidr_is_never_expanded_by_make(tmp_path):
    marker = tmp_path / "ran"
    res = _make(tmp_path, "imladris-plan", f"OPERATOR_CIDR=$(shell touch {marker})/32")
    assert res.returncode != 0 and not marker.exists() and "terraform plan" not in res.stdout


@needs_make
def test_operator_cidr_from_the_environment_is_read_too(tmp_path):
    """.envrc may set it: read from the environment as from the command line, and checked the same."""
    res = _make(tmp_path, "imladris-plan", environ={"OPERATOR_CIDR": "203.0.113.8/32"})
    assert res.returncode == 0 and "-var=operator_cidr=203.0.113.8/32" in res.stdout
    res = _make(tmp_path, "imladris-plan", environ={"OPERATOR_CIDR": "0.0.0.0/0"})
    assert res.returncode != 0 and "OPERATOR_CIDR refusé" in res.stderr


def test_the_makefile_no_longer_suffixes_a_service_answer():
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "api.ipify.org" not in text.split("OPERATOR_CIDR ?=", 1)[1].split("\n", 1)[0]
    assert "$(shell curl" not in text and '-var="operator_cidr=$(OPERATOR_CIDR)"' not in text
