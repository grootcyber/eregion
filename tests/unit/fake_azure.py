"""An in-memory Azure network for the invariant tests (L24).

Just enough of azure-mgmt-network and azure-mgmt-compute for AzureConnector's
isolation paths, with Azure's semantics where they matter:
- a `get` returns a copy: changing it does nothing until `begin_create_or_update`;
- a missing resource raises ResourceNotFoundError (status 404); deleting a missing rule
  succeeds, as an ARM DELETE does;
- names are case-insensitive (ARM resource names are; assumed for rule names too);
- an NSG lists the NICs and subnets attached to it;
- two rules of one NSG can't share a priority in the same direction;
- a rule to Azure's DNS must have "*" as its source (InvalidDNSExfilSourceTag, measured);
- attaching an NSG that doesn't exist fails, and so does attaching one of another
  region (the error code is assumed, not measured); a NIC can carry an Azure Policy
  that refuses any NSG other than the one the customer designed for it;
- an NSG attached to a NIC or a subnet can't be deleted (assumed:
  InUseNetworkSecurityGroupCannotBeDeleted);
- `write_denied`: every write is refused (403) — the role was removed, a deny
  assignment, a resource lock;
- `unreadable`: NSGs the identity can no longer read (its role removed on their group,
  expired under PIM) — a HYPOTHESIS, not measured (I1S, #231): ARM filters a
  subscription-wide listing by the caller's rights, so `list_all` leaves them out
  WITHOUT an error, while a call on one of them (get, its rules, a write, a NIC joined
  to it) is refused (403);
- Run Command's shell script doesn't run on a Windows VM (assumed); held running on demand
  (`hold_run_commands`, DRN1: 302 s under the quarantine, measured once, 09/11), ended by the test;
- Azure Backup (REC1, #668): a vault's restore jobs (`backup_jobs.list`, `job_details.get`, the
  point a job restored in its property bag — by its time, US style with a trailing space in the
  key, or by its id: both unmeasured — and its « Job Type »), the VM's recovery points, its power
  state, its OS disk and when it was created (a restore in place puts a new one), the activity log
  (each Run Command, who ran it: `caller`, its operation; one tried on a VM that does not run is
  refused, logged Started then Failed, `Conflict`, `OperationNotAllowed`, the model as it was —
  measured 09/11, REC1b), and what Run Command v1 last said (the GUEST's word: the output of the
  last command, written again when a restored disk boots and replays it — measured once,
  2026-10-05, the ransomware replayed —, or whatever root writes). The instance view carries it
  only when a test sets `view_run_command`: on the bench (09/11), it never does.

`open_flows` evaluates traffic as Azure does, independently of the connector's own
helpers: inbound crosses the subnet's NSG then the NIC's, outbound the reverse; in each
NSG the first rule that matches, by priority, decides; the default rules come last; no
NSG lets everything through. Azure's platform addresses (DNS, IMDS) are left out of the
probes: an NSG doesn't filter them without their service tags.

Faults: `chaos(op, phase, write)` is called before every call and after every write. It
can raise a transient error (429) or `Crash` — a BaseException, so it goes through the
connector's `except Exception` the way a killed process would.
"""
from __future__ import annotations

import copy
import ipaddress
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

SUB = "/subscriptions/s"
RUN_COMMAND_ACTION = "Microsoft.Compute/virtualMachines/runCommand/action"


class Crash(BaseException):
    """The process dies here."""


def vm_id(rg: str, name: str) -> str:
    return f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


def nic_id(rg: str, name: str) -> str:
    return f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Network/networkInterfaces/{name}"


def nsg_id(rg: str, name: str) -> str:
    return f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Network/networkSecurityGroups/{name}"


def subnet_id(rg: str, vnet: str, name: str) -> str:
    return f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{name}"


def key(resource_id: str) -> str:
    return (resource_id or "").rstrip("/").lower()


def _error(cls, status: int, message: str):
    exc = cls(message=message)
    exc.status_code = status
    return exc


def not_found(what: str):
    return _error(ResourceNotFoundError, 404, f"(ResourceNotFound) {what} was not found.")


def throttled(op: str):
    return _error(HttpResponseError, 429, f"(TooManyRequests) {op}: retry later")


_RULE_FIELDS = (
    "name", "priority", "direction", "access", "protocol",
    "source_address_prefix", "source_address_prefixes",
    "destination_address_prefix", "destination_address_prefixes",
    "source_port_range", "destination_port_range", "destination_port_ranges",
    "source_application_security_groups", "destination_application_security_groups",
    "description",
)


def _text(value) -> str:
    return str(getattr(value, "value", value) or "")


def _rule_record(rule) -> dict:
    rec = {f: copy.deepcopy(getattr(rule, f, None)) for f in _RULE_FIELDS}
    rec["direction"] = _text(rec["direction"])
    rec["access"] = _text(rec["access"])
    rec["protocol"] = _text(rec["protocol"]) or None
    return rec


class _Done:
    def __init__(self, value=None):
        self._value = value

    def result(self, timeout=None):
        return self._value

    def done(self):
        return True


class _Running:
    """A Run Command Azure accepted and still runs (DRN1: 302 s under the quarantine, 09/11): not
    done, its result the last poll's — no output, as `LROPoller.result(timeout)` gives it at its
    deadline — until the test ends it (`FakeAzure.end_run_commands`)."""

    def __init__(self, az, value, vm: dict, op: str):
        self.az, self._value, self._vm, self._error, self._done, self._op = az, value, vm, None, False, op

    def result(self, timeout=None):
        if not self._done:
            return SimpleNamespace(value=None)
        if self._error is not None:
            raise self._error
        return self._value

    def done(self):
        return self._done

    def status(self):
        return ("Failed" if self._error is not None else "Succeeded") if self._done else "InProgress"

    def end(self, error=None) -> None:
        self._done, self._error = True, error
        self.az.log_run_command(self._vm["id"], ("Failed" if error is not None else "Succeeded",),
                                {"http": "Conflict", "message": str(error)} if error is not None else None,
                                op=self._op)


class FakeAzure:
    def __init__(self, chaos=None):
        self.chaos = chaos or (lambda op, phase, write: None)
        self.nsgs: dict[str, dict] = {}
        self.nics: dict[str, dict] = {}
        self.subnets: dict[str, dict] = {}
        self.vms: dict[str, dict] = {}
        self.write_denied = False
        self.unreadable: set[str] = set()       # NSG keys: left out of a listing, 403 on a call
        # Every write that went through the API — Glorfindel's, since the test plays
        # everyone else by editing the dicts — and the rules it wrote (nsg key, name):
        # I2 by author, without asking the code what it meant to do.
        self.journal: list[dict] = []
        self.authored: set[tuple[str, str]] = set()
        self.network = SimpleNamespace(
            network_interfaces=_Nics(self), network_security_groups=_Nsgs(self),
            security_rules=_Rules(self), subnets=_Subnets(self))
        self.compute = SimpleNamespace(virtual_machines=_Vms(self), virtual_machine_extensions=_Extensions(self),
                                       virtual_machine_run_commands=_ManagedRunCommands(self))
        # Azure Backup (REC1): one vault, its restore jobs, each VM's recovery points.
        self.jobs: list[dict] = []
        self.points: dict[str, list[dict]] = {}
        self.backup = SimpleNamespace(backup_jobs=_Jobs(self), job_details=_JobDetails(self),
                                      recovery_points=_Points(self), protected_items=_Items(self))
        # The control plane's memory (REC1): each managed disk's creation, and the activity log —
        # who ran each Run Command (`caller`: the identity the next calls are made under; the test
        # sets it) and when (`clock`, which a test may move).
        self.disks: dict[str, dict] = {}
        self.activity: list[dict] = []
        self.operations = 0
        self.caller = "h0-identity"
        # Whether the instance view carries Run Command v1's word (`instanceView.extensions`):
        # measured on the bench (09/11, REC1b), never — before a restore, after it, after a replayed
        # neutralization. A test that reads the guest's word sets it.
        self.view_run_command = False
        self.clock = lambda: datetime.now(timezone.utc)
        self.compute.disks = _Disks(self)
        # DRN1: Run Commands held running until the test ends them (`end_run_commands`).
        self.hold_run_commands = False
        self.running: list[_Running] = []

    # ── building the customer's world ──────────────────────────────────────────

    def add_nsg(self, rg: str, name: str, rules=(), location="westeurope", tags=None) -> str:
        rid = nsg_id(rg, name)
        self.nsgs[key(rid)] = {"id": rid, "location": location, "tags": dict(tags or {}),
                               "rules": {}}
        for r in rules:
            self._put_rule(self.nsgs[key(rid)], _rule_record(r))
        return rid

    def add_subnet(self, rg: str, vnet: str, name: str, nsg: str | None) -> str:
        rid = subnet_id(rg, vnet, name)
        self.subnets[key(rid)] = {"id": rid, "nsg": nsg}
        return rid

    def add_vm(self, rg: str, name: str, nics: list[dict], os_type="Linux") -> str:
        """nics: [{rg, name, ips, subnet, nsg, policy, location, forwarding}] — `policy`: an
        Azure Policy refusing any NSG on this NIC other than its own `nsg`; `forwarding`: IP
        forwarding on (`enable_ip_forwarding`: an appliance, a hub's firewall — SEC-A4)."""
        ids = []
        for n in nics:
            rid = nic_id(n["rg"], n["name"])
            self.nics[key(rid)] = {"id": rid, "location": n.get("location", "westeurope"),
                                   "nsg": n.get("nsg"),
                                   "design_nsg": n.get("nsg"), "ips": list(n["ips"]),
                                   "subnet": n["subnet"], "policy": bool(n.get("policy")),
                                   "forwarding": bool(n.get("forwarding"))}
            ids.append(rid)
        rid = vm_id(rg, name)
        disk = self._new_disk(rg, f"{name}-osdisk", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.vms[key(rid)] = {"id": rid, "nics": ids, "os": os_type, "power": "running",
                              "last_output": "", "said": None, "extensions": [], "managed": [],
                              "os_disk": disk}
        return rid

    def _new_disk(self, rg: str, name: str, created: datetime) -> str:
        rid = f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Compute/disks/{name}"
        self.disks[key(rid)] = {"id": rid, "time_created": created}
        return rid

    def end_run_commands(self, error=None) -> None:
        """Every Run Command held running ends now: succeeded, or failed with `error` (DRN1)."""
        for r in self.running:
            r.end(error)
        self.running.clear()

    def cut_run_command(self, vm: str, text: str, status: str = "Accepted",
                        http: str | None = None, message: str | None = None) -> None:
        """A Run Command by `caller` that never finished — cut by the deallocation (`Accepted`,
        `Started`) or `Failed` (`http`, `message`: its `properties.statusCode` and
        `statusMessage`; by default an agent's failure once begun): logged so, and its settings
        left in the VM model all the same (a restored disk replays them); the guest said nothing
        of it."""
        v = self.vms[key(vm)]
        v["last_output"] = f"Enable succeeded:\n[stdout]\n{text}\n[stderr]\n"
        failed = {"http": http, "message": message if message is not None else (
            '{"status":"Failed","error":{"code":"VMAgentStatusCommunicationError",'
            '"message":"VM has reported a failure when processing extension RunCommandLinux."}}')}
        self.log_run_command(v["id"], ("Started", status) if status != "Started" else ("Started",),
                             failed if status == "Failed" else None)

    def log_run_command(self, resource_id: str, statuses, failed: dict | None = None,
                        op: str | None = None) -> str:
        """One Run Command operation in the activity log, by `caller`, now: its events (`statuses`,
        under one `operationId`), the `Failed` one carrying `failed` ({"http", "message"}). `op`: an
        operation already logged, its later events (DRN1: a Run Command held running, then ended)."""
        if op is None:
            self.operations += 1
            op = f"op-{self.operations:05d}"
        at = self.clock()
        for s in statuses:
            self.activity.append({"resource_id": resource_id, "op": RUN_COMMAND_ACTION, "status": s, "at": at,
                                  "caller": self.caller, "op_id": op,
                                  "failed": failed if s == "Failed" else None})
        return op

    def deallocate(self, vm: str) -> None:
        """The VM deallocated (`az vm deallocate`, what `glorfindel restore` does before the vault
        restores): a Run Command on it is refused (REC1b)."""
        self.vms[key(vm)]["power"] = "deallocated"

    def activity_log(self, resource_id: str, since: str) -> list[dict]:
        """The activity log's events on a resource since a moment, as its REST API gives them: the
        caller as the bench measured it for every identity (09/11: `caller` and `claims.oid` the
        object id, `claims.appid` its appId — the fake gives one id for both), and, on a failure,
        `properties.statusCode`, `subStatus` and `properties.statusMessage` (their shape: assumed
        from ARM's documented events, unmeasured)."""
        start = datetime.fromisoformat(since.replace("Z", "+00:00"))
        out = []
        for e in self.activity:
            if key(e["resource_id"]) != key(resource_id) or e["at"] < start:
                continue
            ev = {"caller": e["caller"], "claims": {"appid": e["caller"], "oid": e["caller"]},
                  "operationName": {"value": e["op"]}, "status": {"value": e["status"]},
                  "operationId": e.get("op_id", ""), "eventTimestamp": e["at"].isoformat(),
                  "resourceId": e["resource_id"], "subStatus": {"value": ""}, "properties": {}}
            failed = e.get("failed")
            if failed:
                ev["properties"] = {"eventCategory": "Administrative", "statusMessage": failed["message"],
                                    **({"statusCode": failed["http"]} if failed["http"] else {})}
                ev["subStatus"] = {"value": failed["http"] or "", "localizedValue": failed["http"] or ""}
            out.append(ev)
        return out

    # ── Azure Backup (REC1) ─────────────────────────────────────────────────────

    def add_point(self, vm: str, name: str, at: datetime) -> None:
        """A recovery point of the VM, taken at `at` (UTC)."""
        self.points.setdefault(key(vm), []).append({"name": name, "time": at})

    def restore(self, vm: str, point: str, start: datetime, end: datetime | None,
                status: str = "Completed", bag: str = "time", power: str = "running",
                boot_after_s: float = 60.0, kind: str = "replace", container: bool = True) -> str:
        """The vault restores `point` from start to end (None: still running). `kind`: "replace"
        (« Replace disks », in place: new disks on the VM, created during the job; done, the VM
        is left `power`; running, its restored disk replays the last Run Command of the VM model
        `boot_after_s` after the end — the agent writes its output again, 2026-10-05), "disks"
        (« Restore disks ») or "new_vm" (« Create new virtual machine »): elsewhere, the isolated
        VM as it was. `bag`: how the job names the point — "time" (« Recovery point time  »,
        US style), "id" (« Recovery Point Id »), "none". `container`: the job names its
        container. Returns the job's name."""
        v = self.vms[key(vm)]
        name = f"job-{len(self.jobs) + 1:04d}"
        self.jobs.append({"name": name, "vm": key(vm), "status": status if end is not None else "InProgress",
                          "start": start, "end": end, "point": point, "bag": bag, "kind": kind,
                          "container": container})
        if kind != "replace" or end is None:
            return name
        # Its disks swapped mid-job, whatever its end: a job that fails late (the VM not started
        # again, a step after the swap) has replaced them too — assumed, never a proof of success.
        rg = vm.split("/")[4]
        v["os_disk"] = self._new_disk(rg, f"{vm.rsplit('/', 1)[-1]}-osdisk-{name}", start + (end - start) / 2)
        if status == "Completed":
            v["power"] = power
            if power == "running" and v["last_output"]:
                v["said"] = {"message": v["last_output"], "time": end + timedelta(seconds=boot_after_s)}
        return name

    def delete_nsg(self, rid: str) -> bool:
        """The customer deletes an NSG — refused while it governs a NIC or a subnet."""
        if any(key(n["nsg"]) == key(rid) for n in self.nics.values()) or \
                any(key(s["nsg"]) == key(rid) for s in self.subnets.values()):
            return False
        return self.nsgs.pop(key(rid), None) is not None

    def snapshot(self) -> dict:
        return copy.deepcopy({"nsgs": self.nsgs, "nics": self.nics, "subnets": self.subnets,
                              "vms": self.vms})

    # ── plumbing ────────────────────────────────────────────────────────────────

    def call(self, op: str, write: bool, fn):
        self.chaos(op, "before", write)
        if write and self.write_denied:
            raise _error(HttpResponseError, 403,
                         f"(AuthorizationFailed) {op}: the client does not have authorization")
        out = fn()
        if write:
            self.chaos(op, "after", write)
        return out

    def nsg(self, rg: str, name: str) -> dict:
        self.readable(nsg_id(rg, name))
        n = self.nsgs.get(key(nsg_id(rg, name)))
        if n is None:
            raise not_found(f"networkSecurityGroups/{name}")
        return n

    def readable(self, rid: str) -> None:
        if key(rid) in self.unreadable:
            raise _error(HttpResponseError, 403, f"(AuthorizationFailed) {rid.rsplit('/', 1)[-1]}: "
                                                 "the client does not have authorization")

    @staticmethod
    def _put_rule(nsg: dict, rec: dict) -> None:
        # Measured on the bench (2026-10-08): a rule to Azure's DNS must have "*" as its
        # source — it can't be scoped to one VM's addresses.
        dst = [rec.get("destination_address_prefix")] + list(rec.get("destination_address_prefixes") or [])
        src = [rec.get("source_address_prefix")] + list(rec.get("source_address_prefixes") or [])
        if any((d or "").lower() == "azureplatformdns" for d in dst) and [v for v in src if v] != ["*"]:
            raise _error(HttpResponseError, 400,
                         f"(InvalidDNSExfilSourceTag) {rec['name']}: DNS Exfiltration Tags must have "
                         '"*" as a sourceaddressPrefix')
        for other in nsg["rules"].values():
            if (other["name"].lower() != rec["name"].lower()
                    and other["direction"].lower() == rec["direction"].lower()
                    and other["priority"] == rec["priority"]):
                raise _error(HttpResponseError, 400,
                             f"(SecurityRuleConflict) {rec['name']} and {other['name']} share "
                             f"priority {rec['priority']} ({rec['direction']})")
        nsg["rules"][rec["name"].lower()] = rec

    def nsg_view(self, n: dict):
        return SimpleNamespace(
            id=n["id"], name=n["id"].rsplit("/", 1)[-1], location=n["location"],
            tags=dict(n["tags"]),
            security_rules=[SimpleNamespace(**r) for r in n["rules"].values()],
            network_interfaces=[SimpleNamespace(id=c["id"]) for c in self.nics.values()
                                if key(c["nsg"]) == key(n["id"])],
            subnets=[SimpleNamespace(id=s["id"]) for s in self.subnets.values()
                     if key(s["nsg"]) == key(n["id"])],
        )


class _Nics:
    def __init__(self, az: FakeAzure):
        self.az = az

    def _get(self, rg, name) -> dict:
        n = self.az.nics.get(key(nic_id(rg, name)))
        if n is None:
            raise not_found(f"networkInterfaces/{name}")
        return n

    def get(self, rg, name):
        def read():
            n = self._get(rg, name)
            vm = next((v["id"] for v in self.az.vms.values() if key(n["id"]) in {key(x) for x in v["nics"]}), None)
            return SimpleNamespace(
                id=n["id"], location=n["location"],
                enable_ip_forwarding=n.get("forwarding", False),
                virtual_machine=SimpleNamespace(id=vm) if vm else None,
                network_security_group=SimpleNamespace(id=n["nsg"]) if n["nsg"] else None,
                ip_configurations=[SimpleNamespace(private_ip_address=ip,
                                                   subnet=SimpleNamespace(id=n["subnet"]))
                                   for ip in n["ips"]])
        return self.az.call("nic.get", False, read)

    def begin_create_or_update(self, rg, name, nic):
        def write():
            n = self._get(rg, name)
            new = getattr(getattr(nic, "network_security_group", None), "id", None)
            if new:
                self.az.readable(new)
                if key(new) not in self.az.nsgs:
                    raise _error(HttpResponseError, 400,
                                 f"(InvalidResourceReference) {new} referenced by {name} was not found.")
                if self.az.nsgs[key(new)]["location"] != n["location"]:
                    raise _error(HttpResponseError, 400,
                                 f"(InvalidResourceReference) {new} is not in the region of {name}")
                if n["policy"] and key(new) != key(n["design_nsg"]):
                    raise _error(HttpResponseError, 403,
                                 f"(RequestDisallowedByPolicy) NSG on {name} not allowed")
            before = n["nsg"]
            n["nsg"] = self.az.nsgs[key(new)]["id"] if new else None
            self.az.journal.append({"op": "nic.write", "nic": key(n["id"]), "before": before, "after": n["nsg"]})
            return _Done()
        return self.az.call("nic.write", True, write)

    def list_all(self):
        return self.az.call("nic.list", False, lambda: [self.get(*_rg_name(n["id"]))
                                                        for n in self.az.nics.values()])


class _Nsgs:
    def __init__(self, az: FakeAzure):
        self.az = az

    def get(self, rg, name):
        return self.az.call("nsg.get", False, lambda: self.az.nsg_view(self.az.nsg(rg, name)))

    def begin_create_or_update(self, rg, name, model):
        def write():
            rid = nsg_id(rg, name)
            self.az.readable(rid)
            n = {"id": rid, "location": getattr(model, "location", None) or "westeurope",
                 "tags": dict(getattr(model, "tags", None) or {}), "rules": {}}
            for r in getattr(model, "security_rules", None) or []:
                FakeAzure._put_rule(n, _rule_record(r))
            before = self.az.nsgs.get(key(rid))
            self.az.journal.append({"op": "nsg.write", "nsg": key(rid), "before_tags": (
                dict(before["tags"]) if before else None), "after_tags": dict(n.get("tags") or {})})
            self.az.nsgs[key(rid)] = n
            self.az.authored |= {(key(rid), r) for r in n["rules"]}
            return _Done(self.az.nsg_view(n))
        return self.az.call("nsg.write", True, write)

    def list_all(self):
        return self.az.call("nsg.list", False, lambda: [self.az.nsg_view(n) for k, n in self.az.nsgs.items()
                                                        if k not in self.az.unreadable])

    def update_tags(self, rg, name, tags_object):
        def write():
            n = self.az.nsg(rg, name)
            after = dict(getattr(tags_object, "tags", None) or {})
            self.az.journal.append({"op": "nsg.tags", "nsg": key(n["id"]), "before_tags": dict(n["tags"]),
                                    "after_tags": after})
            n["tags"] = after
            return self.az.nsg_view(n)
        return self.az.call("nsg.tags", True, write)


class _Rules:
    def __init__(self, az: FakeAzure):
        self.az = az

    def list(self, rg, nsg_name):
        return self.az.call("rule.list", False, lambda: [
            SimpleNamespace(**r) for r in self.az.nsg(rg, nsg_name)["rules"].values()])

    def get(self, rg, nsg_name, name):
        def read():
            r = self.az.nsg(rg, nsg_name)["rules"].get(name.lower())
            if r is None:
                raise not_found(f"securityRules/{name}")
            return SimpleNamespace(**r)
        return self.az.call("rule.get", False, read)

    def begin_create_or_update(self, rg, nsg_name, name, rule):
        def write():
            rec = _rule_record(rule)
            rec["name"] = name
            nsg = self.az.nsg(rg, nsg_name)
            before = nsg["rules"].get(name.lower())
            FakeAzure._put_rule(nsg, rec)
            k = (key(nsg["id"]), name.lower())
            self.az.journal.append({"op": "rule.write", "nsg": k[0], "rule": k[1],
                                    "existed": before is not None, "authored": k in self.az.authored})
            self.az.authored.add(k)
            return _Done(SimpleNamespace(**rec))
        return self.az.call("rule.write", True, write)

    def begin_delete(self, rg, nsg_name, name):
        def write():
            nsg = self.az.nsg(rg, nsg_name)
            k = (key(nsg["id"]), name.lower())
            if nsg["rules"].pop(name.lower(), None) is not None:
                self.az.journal.append({"op": "rule.delete", "nsg": k[0], "rule": k[1],
                                        "existed": True, "authored": k in self.az.authored})
            return _Done()
        return self.az.call("rule.delete", True, write)


class _Subnets:
    def __init__(self, az: FakeAzure):
        self.az = az

    def get(self, rg, vnet, name):
        def read():
            s = self.az.subnets.get(key(subnet_id(rg, vnet, name)))
            if s is None:
                raise not_found(f"subnets/{name}")
            return SimpleNamespace(id=s["id"], network_security_group=(
                SimpleNamespace(id=s["nsg"]) if s["nsg"] else None))
        return self.az.call("subnet.get", False, read)


class _Vms:
    def __init__(self, az: FakeAzure):
        self.az = az

    def _get(self, rg, name) -> dict:
        v = self.az.vms.get(key(vm_id(rg, name)))
        if v is None:
            raise not_found(f"virtualMachines/{name}")
        return v

    def get(self, rg, name):
        def read():
            v = self._get(rg, name)
            return SimpleNamespace(
                id=v["id"],
                network_profile=SimpleNamespace(network_interfaces=[
                    SimpleNamespace(id=n, primary=i == 0) for i, n in enumerate(v["nics"])]),
                storage_profile=SimpleNamespace(os_disk=SimpleNamespace(
                    os_type=v["os"], managed_disk=SimpleNamespace(id=v.get("os_disk")) if v.get("os_disk") else None)))
        return self.az.call("vm.get", False, read)

    def begin_run_command(self, rg, name, command):
        def run():
            v = self._get(rg, name)
            if v["os"] == "Windows" and getattr(command, "command_id", "") == "RunShellScript":
                raise _error(HttpResponseError, 409,
                             f"(Conflict) RunShellScript is not supported on the Windows VM {name}")
            if v.get("power", "running") != "running":
                # Measured on the bench (09/11, REC1b): on a deallocated VM, ARM refuses the command —
                # logged Started then Failed, Conflict, OperationNotAllowed, under its real caller —
                # and the VM model is left as it was. The message's text is assumed.
                text = (f"Operation 'RunCommand' is not allowed on VM '{name}' since the VM is "
                        f"{v['power']}.")
                self.az.log_run_command(v["id"], ("Started", "Failed"), {
                    "http": "Conflict",
                    "message": '{"error":{"code":"OperationNotAllowed","message":"' + text + '"}}'})
                raise _error(HttpResponseError, 409, f"(OperationNotAllowed) {text}")
            script = list(getattr(command, "script", None) or [])
            # One `echo '<text>'` prints its text (the neutralization, REC1); anything else is the
            # session drain, as before.
            line = script[0] if len(script) == 1 else ""
            said = (line.split("'", 2)[1] if line.startswith(("echo '", "Write-Output '")) and line.count("'") == 2
                    else "glorfindel-drain-remaining=0")
            message = f"Enable succeeded:\n[stdout]\n{said}\n[stderr]\n"
            # The VM model's last command, the agent's word of it (the instance view), and the
            # control plane's record of who ran it (the activity log, REC1).
            v["last_output"] = message
            v["said"] = {"message": message, "time": self.az.clock()}
            value = SimpleNamespace(value=[SimpleNamespace(message=message)])
            if self.az.hold_run_commands:               # DRN1: Started now, its end when the test ends it
                op = self.az.log_run_command(v["id"], ("Started",))
                self.az.running.append(_Running(self.az, value, v, op))
                return self.az.running[-1]
            self.az.log_run_command(v["id"], ("Started", "Succeeded"))    # as ARM logs a long operation
            return _Done(SimpleNamespace(value=[SimpleNamespace(message=message)]))
        return self.az.call("vm.run_command", True, run)

    def instance_view(self, rg, name):
        def read():
            v = self._get(rg, name)
            handler = "RunCommandWindows" if v["os"] == "Windows" else "RunCommandLinux"
            exts = [SimpleNamespace(name=handler, type=f"Microsoft.CPlat.Core.{handler}", statuses=[
                SimpleNamespace(code="ProvisioningState/succeeded", message=v["said"]["message"],
                                time=v["said"]["time"])])] if v.get("said") and self.az.view_run_command else []
            return SimpleNamespace(statuses=[SimpleNamespace(code="ProvisioningState/succeeded"),
                                             SimpleNamespace(code=f"PowerState/{v.get('power', 'running')}")],
                                   extensions=exts)
        return self.az.call("vm.instance_view", False, read)


class _Extensions:
    """The VM's extensions (`extensions`: [(name, publisher, type)]), Run Command's handler once it ran."""

    def __init__(self, az: FakeAzure):
        self.az = az

    def list(self, rg, name):
        def read():
            v = self.az.compute.virtual_machines._get(rg, name)
            items = [SimpleNamespace(name=n, as_dict=(lambda p=p, t=t: {"properties": {"publisher": p, "type": t}}))
                     for n, p, t in v.get("extensions", [])]
            if v.get("said"):
                handler = "RunCommandWindows" if v["os"] == "Windows" else "RunCommandLinux"
                items.append(SimpleNamespace(name=handler, as_dict=lambda h=handler: {
                    "properties": {"publisher": "Microsoft.CPlat.Core", "type": h}}))
            return SimpleNamespace(value=items)
        return self.az.call("vm.extensions", False, read)


class _Disks:
    def __init__(self, az: FakeAzure):
        self.az = az

    def get(self, rg, name):
        def read():
            d = self.az.disks.get(key(f"{SUB}/resourceGroups/{rg}/providers/Microsoft.Compute/disks/{name}"))
            if d is None:
                raise not_found(f"disks/{name}")
            return SimpleNamespace(id=d["id"], time_created=d["time_created"])
        return self.az.call("disk.get", False, read)


class _ManagedRunCommands:
    def __init__(self, az: FakeAzure):
        self.az = az

    def list_by_virtual_machine(self, rg, name):
        return self.az.call("vm.run_commands", False, lambda: [
            SimpleNamespace(name=n) for n in self.az.compute.virtual_machines._get(rg, name).get("managed", [])])


def _vm_of_item(az: FakeAzure, item: str) -> dict:
    """The VM a backup item names (`VM;iaasvmcontainerv2;<rg>;<vm>`), whatever its case."""
    parts = str(item or "").split(";")
    if len(parts) < 4:
        raise not_found(f"protectedItems/{item}")
    v = az.vms.get(key(vm_id(parts[-2], parts[-1])))
    if v is None:
        raise not_found(f"protectedItems/{item}")
    return v


class _Items:
    def __init__(self, az: FakeAzure):
        self.az = az

    def get(self, vault, rg, fabric, container, item):
        def read():
            v = _vm_of_item(self.az, item)
            vrg, vname = _rg_name(v["id"])
            return SimpleNamespace(id=(f"{SUB}/resourceGroups/{rg}/providers/Microsoft.RecoveryServices/vaults/"
                                       f"{vault}/backupFabrics/Azure/protectionContainers/"
                                       f"IaasVMContainer;iaasvmcontainerv2;{vrg};{vname}/protectedItems/"
                                       f"VM;iaasvmcontainerv2;{vrg};{vname}"))
        return self.az.call("backup.item", False, read)


class _Points:
    def __init__(self, az: FakeAzure):
        self.az = az

    def list(self, vault, rg, fabric, container, item):
        def read():
            v = _vm_of_item(self.az, item)
            return [SimpleNamespace(name=p["name"], properties=SimpleNamespace(
                recovery_point_time=p["time"], recovery_point_tier_details=[]))
                for p in self.az.points.get(key(v["id"]), [])]
        return self.az.call("backup.points", False, read)


# What a job's property bag calls each kind of restore (« Replace disks » as the fake has it since
# REC1; the others as the portal names the options — unmeasured).
_JOB_TYPES = {"replace": "Replace disks", "disks": "Restore disks", "new_vm": "Create new virtual machine"}


def _job_view(az: FakeAzure, j: dict, details: bool = False):
    v = az.vms[j["vm"]]
    vrg, vname = _rg_name(v["id"])
    bag = {}
    if details:
        at = next((p["time"] for p in az.points.get(j["vm"], []) if p["name"] == j["point"]), None)
        bag = {"Job Type": _JOB_TYPES[j.get("kind", "replace")]}
        if j["bag"] == "time" and at is not None:
            bag["Recovery point time "] = at.strftime("%m/%d/%Y %I:%M:%S %p")
        elif j["bag"] == "id":
            bag["Recovery Point Id"] = j["point"]
    return SimpleNamespace(name=j["name"], properties=SimpleNamespace(
        operation="Restore", status=j["status"], entity_friendly_name=vname,
        container_name=f"iaasvmcontainerv2;{vrg};{vname}" if j.get("container", True) else None,
        start_time=j["start"], end_time=j["end"],
        extended_info=SimpleNamespace(property_bag=bag) if details else None))


class _Jobs:
    def __init__(self, az: FakeAzure):
        self.az = az

    def list(self, vault, rg, filter=None):
        return self.az.call("backup.jobs", False, lambda: [_job_view(self.az, j) for j in self.az.jobs])


class _JobDetails:
    def __init__(self, az: FakeAzure):
        self.az = az

    def get(self, vault, rg, name):
        def read():
            j = next((j for j in self.az.jobs if j["name"] == name), None)
            if j is None:
                raise not_found(f"backupJobs/{name}")
            return _job_view(self.az, j, details=True)
        return self.az.call("backup.job", False, read)


def _rg_name(resource_id: str) -> tuple[str, str]:
    parts = resource_id.split("/")
    return parts[parts.index("resourceGroups") + 1], parts[-1]


# ── traffic, evaluated as Azure does ─────────────────────────────────────────────

INTERNET = "203.0.113.7"          # documentation range (RFC 5737), outside the 3 private blocks
LATERAL = "10.9.9.9"
AZURE_DNS = "168.63.129.16"
AZURE_IMDS = "169.254.169.254"
# (direction, peer, port): an attacker on the internet (SSH, HTTPS), a neighbour in the
# VNet (lateral movement), the VM calling out (exfiltration, C2, lateral), and Azure's
# DNS (a tunnel) and IMDS (managed-identity tokens).
# The IP a block targets: public for Python's `ipaddress` too (the RFC 5737 ranges read as
# private there, and an `Internet` allow then never "covered" the attacker) — the AS112
# blackhole range (RFC 7534), no real host behind it.
ATTACKER = "192.31.196.7"
PROBES = (("in", INTERNET, 22), ("in", INTERNET, 443), ("in", LATERAL, 22),
          ("out", INTERNET, 443), ("out", LATERAL, 445),
          ("out", AZURE_DNS, 53), ("out", AZURE_IMDS, 80),
          ("in", ATTACKER, 22), ("in", ATTACKER, 443), ("out", ATTACKER, 443))
# Platform addresses: no rule filters them unless it names their service tag — a
# deny-all, the default rules included, lets them through (measured on the bench).
_PLATFORM = {AZURE_DNS: "azureplatformdns", AZURE_IMDS: "azureplatformimds"}

_PRIVATE = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
_DEFAULTS = {
    "in": [(65000, "allow", "VirtualNetwork", "VirtualNetwork", "*"),
           (65001, "allow", "AzureLoadBalancer", "*", "*"),
           (65500, "deny", "*", "*", "*")],
    "out": [(65000, "allow", "VirtualNetwork", "VirtualNetwork", "*"),
            (65001, "allow", "*", "Internet", "*"),
            (65500, "deny", "*", "*", "*")],
}


def _private(ip: str) -> bool:
    return any(ipaddress.ip_address(ip) in n for n in _PRIVATE)


def _covers(prefix: str, ip: str) -> bool:
    p = (prefix or "").strip()
    low = p.lower()
    if low in ("*", "any"):
        return True
    if low == "virtualnetwork":
        return _private(ip)
    if low == "internet":
        return not _private(ip)
    if low.startswith("azure"):            # platform and service tags: never these probes
        return False
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(p, strict=False)
    except ValueError:
        return False


def _side(rule: dict, side: str, ip: str) -> bool:
    values = [rule.get(f"{side}_address_prefix")] + list(rule.get(f"{side}_address_prefixes") or [])
    values = [v for v in values if v]
    return any(_covers(v, ip) for v in values) if values else True


def _port(rule: dict, port: int) -> bool:
    ranges = [rule.get("destination_port_range")] + list(rule.get("destination_port_ranges") or [])
    for pr in (str(r).strip() for r in ranges if r):
        if pr in ("*", "Any", "any"):
            return True
        lo, _, hi = pr.partition("-")
        if int(lo) <= port <= int(hi or lo):
            return True
    return False


def _names_tag(rule: dict, tag: str) -> bool:
    values = [rule.get("destination_address_prefix")] + list(rule.get("destination_address_prefixes") or [])
    return any((v or "").strip().lower() == tag for v in values)


def _proto(rule: dict, port: int) -> bool:
    """The rule's protocol covers the probe's: DNS (53) is UDP, the rest TCP."""
    p = _text(rule.get("protocol") or "*").lower()
    return p in ("*", "any") or p == ("udp" if port == 53 else "tcp")


def _nsg_allows(nsg: dict, direction: str, src: str, dst: str, port: int) -> bool:
    rules = [(r["priority"], r["access"].lower(), r) for r in nsg["rules"].values()
             if r["direction"].lower() == ("inbound" if direction == "in" else "outbound") and _proto(r, port)]
    if direction == "out" and dst in _PLATFORM:
        tag = _PLATFORM[dst]
        for _, access, r in sorted(rules, key=lambda x: x[0]):
            if _names_tag(r, tag) and _side(r, "source", src) and _port(r, port):
                return access == "allow"
        return True
    rules += [(p, a, {"source_address_prefix": s, "destination_address_prefix": d,
                      "destination_port_range": pr})
              for p, a, s, d, pr in _DEFAULTS[direction]]
    for _, access, r in sorted(rules, key=lambda x: x[0]):
        if _side(r, "source", src) and _side(r, "destination", dst) and _port(r, port):
            return access == "allow"
    return False


def open_flows(world: dict, vm: str) -> frozenset:
    """The probes that get through, for every IP of every NIC of the VM."""
    v = world["vms"][key(vm)]
    out = set()
    for n_id in v["nics"]:
        nic = world["nics"][key(n_id)]
        sub = world["subnets"][key(nic["subnet"])]
        chain = [sub["nsg"], nic["nsg"]]
        for direction, peer, port in PROBES:
            for ip in nic["ips"]:
                src, dst = (peer, ip) if direction == "in" else (ip, peer)
                order = chain if direction == "in" else list(reversed(chain))
                if all(_nsg_allows(world["nsgs"][key(g)], direction, src, dst, port)
                       for g in order if g):
                    out.add((nic["id"].rsplit("/", 1)[-1], ip, direction, peer, port))
    return frozenset(out)
