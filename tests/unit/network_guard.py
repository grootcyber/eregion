"""The suite's network guard (SDK1b's review, #1017): nothing leaves the machine in a test. A
connection, a name resolved, a datagram sent to anything but this machine is refused — whatever
opens it (requests, urllib3, an SDK's transport, a socket made by hand), through Python's audit hook,
which sees `socket.connect` (connect and connect_ex), `socket.getaddrinfo`, `socket.gethostbyname`,
`socket.gethostbyaddr`, `socket.sendto` and `socket.sendmsg` before the system call. This machine stays
reachable — 127.0.0.0/8, ::1, `localhost`, a Unix socket: a test's own server.

The conftest installs it once per interpreter (each xdist worker loads it), never removed; `allowed`
is the rule, tested alone (tests/unit/test_network_guard.py). Loaded by its path beside the conftest,
like tests/unit/home_sandbox.py.
Measured 21/11: installed before HY2b, events apart, each refuses in either order; -n 4 263.6 s vs 252.9 s on main (+4.2 %).
"""
from __future__ import annotations

import ipaddress
import socket
import sys

LOCAL_NAMES = frozenset({"", "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"})
# The events of the audit hook that reach out, and where each one names its target.
_TARGETS = {"socket.connect": 1, "socket.sendto": 1, "socket.sendmsg": 1, "socket.getaddrinfo": 0,
            "socket.gethostbyname": 0, "socket.gethostbyaddr": 0}


class Refused(ConnectionRefusedError):
    """A test reached for the network: refused before anything was sent."""


def _local(host) -> bool:
    """`host` is this machine: a loopback address, its name, the unspecified address."""
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    text = str(host).strip("[]").lower().split("%")[0]
    if text in LOCAL_NAMES:
        return True
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_unspecified


def allowed(event: str, args: tuple) -> bool:
    """Whether the audit event `event` may go on: anything but reaching beyond this machine."""
    where = _TARGETS.get(event)
    if where is None:
        return True
    if where == 1:                                   # a socket and its address
        sock, address = args[0], args[1] if len(args) > 1 else None
        if getattr(socket, "AF_UNIX", None) is not None and getattr(sock, "family", None) == socket.AF_UNIX:
            return True
        if address is None or isinstance(address, (str, bytes)):
            return True                              # connected already, or a Unix path
        return _local(address[0] if isinstance(address, tuple) and address else None)
    return _local(args[0] if args else None)


def _hook(event: str, args: tuple) -> None:
    if event.startswith("socket.") and not allowed(event, args):
        raise Refused(f"tests: the network is refused — {event} beyond this machine "
                      "(tests/unit/network_guard.py)")


def install() -> None:
    """The hook, once per interpreter: an audit hook is never removed. Whether HY2b's was there before
    it (`eregion_core.store_guard` imported already) is kept: the order the hooks run in."""
    if not getattr(sys, "_eregion_network_guard", False):
        sys._eregion_network_guard_after_hy2b = "eregion_core.store_guard" in sys.modules
        sys.addaudithook(_hook)
        sys._eregion_network_guard = True
