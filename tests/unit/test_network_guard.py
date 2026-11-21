"""The suite's network guard (tests/unit/network_guard.py, SDK1b's review): nothing leaves the machine
in a test — a connection, a name resolved, a datagram, by any path the audit hook sees —, while this
machine stays reachable (a test's own server). Only the loopback is touched here.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from . import network_guard as guard

OUTSIDE = ("203.0.113.9", 443)              # a documentation address: never a real one
TCP, TCP6 = SimpleNamespace(family=socket.AF_INET), SimpleNamespace(family=socket.AF_INET6)
UNIX = SimpleNamespace(family=getattr(socket, "AF_UNIX", -1))


def test_the_guard_is_installed_in_this_process():
    assert getattr(sys, "_eregion_network_guard", False) is True


@pytest.mark.parametrize("event, args, ok", [
    ("socket.connect", (TCP, OUTSIDE), False),
    ("socket.connect", (TCP, ("example.org", 443)), False),
    ("socket.connect", (TCP6, ("2001:db8::9", 443, 0, 0)), False),
    ("socket.sendto", (TCP, ("198.51.100.4", 53)), False),
    ("socket.getaddrinfo", ("management.azure.com", 443, 0, 0, 0), False),
    ("socket.gethostbyname", ("example.org",), False),
    ("socket.connect", (TCP, ("127.0.0.1", 8080)), True),
    ("socket.connect", (TCP, ("127.0.0.53", 53)), True),
    ("socket.connect", (TCP6, ("::1", 8080, 0, 0)), True),
    ("socket.connect", (TCP, ("localhost", 8080)), True),
    ("socket.getaddrinfo", ("localhost", 8080, 0, 0, 0), True),
    ("socket.getaddrinfo", (None, 8080, 0, 0, 0), True),
    ("socket.sendmsg", (TCP, None), True),
    ("socket.connect", (UNIX, "/run/some.sock"), True),
    ("open", ("/tmp/x", "r", 0), True),
], ids=["ipv4", "a-name", "ipv6", "udp", "dns", "dns-by-name", "loopback", "loopback-range", "ipv6-loopback",
        "localhost", "dns-localhost", "dns-none", "connected", "unix", "not-a-socket"])
def test_the_rule_reaches_this_machine_only(event, args, ok):
    assert guard.allowed(event, args) is ok


# The hook the conftest installed is its own copy of the module (loaded by its path): its refusal
# is a ConnectionRefusedError that says so.
REFUSED = "the network is refused"


def test_a_connection_beyond_this_machine_is_refused_before_it_leaves():
    """By hand, `connect` and `connect_ex` alike: refused by the hook, before the system call. A name
    to resolve: its audit event refused — raised by `sys.audit` itself, which resolves nothing (a
    guard that let it through, a mutant's, must never send a query)."""
    s = socket.socket()
    try:
        with pytest.raises(ConnectionRefusedError, match=REFUSED):
            s.connect(OUTSIDE)
        with pytest.raises(ConnectionRefusedError, match=REFUSED):
            s.connect_ex(OUTSIDE)
    finally:
        s.close()
    with pytest.raises(ConnectionRefusedError, match=REFUSED):
        sys.audit("socket.getaddrinfo", "example.org", 443, 0, 0, 0)
    with pytest.raises(ConnectionRefusedError, match=REFUSED):
        sys.audit("socket.gethostbyname", "example.org")


def test_a_server_of_this_machine_is_reached():
    """A test's own server on the loopback: listened to, connected to, answered."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.create_connection(server.getsockname(), timeout=5)
    try:
        conn, _ = server.accept()
        client.sendall(b"ping")
        assert conn.recv(4) == b"ping"
        conn.close()
    finally:
        client.close()
        server.close()


# ── beside HY2b (eregion_core/store_guard.py): each refuses what it guards, in either order ────────

ROOT = Path(__file__).resolve().parents[2]
_BOTH = r"""
import importlib.util, json, socket, sys
from pathlib import Path
order, home = sys.argv[1], Path(sys.argv[2])

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Each by its path: importing eregion_core would install HY2b on the operator's real home.
net = load("probe_network_guard", sys.argv[3])
store = load("probe_store_guard", sys.argv[4])
guards = {"net": net.install,
          "store": lambda: store.install(env={store.SESSION_VAR: "1"}, cwd=str(home), home=home)}
target = home / ".glorfindel" / "notices.jsonl"
target.parent.mkdir(parents=True, exist_ok=True)      # before the guards: HY2b refuses it too
for name in order.split(","):
    guards[name]()
said = {}
try:
    open(target, "w").close()
    said["store"] = "written"
except Exception as exc:
    said["store"] = type(exc).__name__ + ": " + str(exc)[:60]
said["store_file"] = target.exists()
s = socket.socket()
try:
    s.connect(("203.0.113.9", 443))
    said["net"] = "connected"
except Exception as exc:
    said["net"] = type(exc).__name__ + ": " + str(exc)[:60]
finally:
    s.close()
print(json.dumps(said))
"""


@pytest.mark.parametrize("order", ["net,store", "store,net"])
def test_beside_hy2b_each_guard_refuses_what_it_guards_in_either_order(tmp_path, order):
    """The two audit hooks in one interpreter, installed in either order (in the suite, this one
    first: the conftest installs it on its import, before any collection; HY2b on the first import of
    eregion_core, at collection): a write in the operator's store stays refused by HY2b, a connection
    beyond the machine by this guard — their events are apart, neither refusal hides the other."""
    driver = tmp_path / "both.py"
    driver.write_text(_BOTH)
    home = tmp_path / "operator"
    home.mkdir()
    proc = subprocess.run([sys.executable, str(driver), order, str(home), str(ROOT / "tests/unit/network_guard.py"),
                           str(ROOT / "eregion_core/store_guard.py")], capture_output=True, text=True, timeout=60,
                          cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:]
    said = json.loads(proc.stdout.strip().splitlines()[-1])
    assert said["store"].startswith(("Refused", "PermissionError")) and "HY2b" in said["store"], said
    assert said["store_file"] is False, said
    assert said["net"].startswith("Refused") and "network is refused" in said["net"], said


def test_in_the_suite_this_guard_is_installed_before_eregion_core_is_imported():
    """The order in the suite: the conftest installs this guard as it is imported, before any test
    module is collected — eregion_core not imported yet —, so HY2b, when it is installed (an agent
    session, on eregion_core's first import), runs second, in every process (each xdist worker loads
    the conftest before it collects) and whatever the collection."""
    assert sys._eregion_network_guard_after_hy2b is False
