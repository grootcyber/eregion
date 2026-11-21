"""The suite's network guard (tests/unit/network_guard.py, SDK1b's review): nothing leaves the machine
in a test — a connection, a name resolved, a datagram, by any path the audit hook sees —, while this
machine stays reachable (a test's own server). Only the loopback is touched here.
"""
from __future__ import annotations

import socket
import sys
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
    """By hand, `connect` and `connect_ex` alike, and a name resolved: refused by the hook, before
    the system call."""
    s = socket.socket()
    try:
        with pytest.raises(ConnectionRefusedError, match=REFUSED):
            s.connect(OUTSIDE)
        with pytest.raises(ConnectionRefusedError, match=REFUSED):
            s.connect_ex(OUTSIDE)
    finally:
        s.close()
    with pytest.raises(ConnectionRefusedError, match=REFUSED):
        socket.getaddrinfo("example.org", 443)


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
