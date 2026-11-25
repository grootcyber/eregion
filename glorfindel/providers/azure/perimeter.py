"""The perimeter block an entry carries next to its VM's own block (RB1): a `block` and
a `block_perimeter` of one IP share one entry (`scoped: false`). Where it covers a NIC
whose own rules are gone, the IP is still blocked there; an entry lost, the one no other
VM's entry records may have been the gone VM's.
"""
from __future__ import annotations

from glorfindel.providers.azure.nsg import _dropped_first
from glorfindel.providers.azure.turned import _held_by_turned
from glorfindel.response.policy import _ERR_MAX, _first_line


class PerimeterMixin:
    """The merged perimeter block (part of AzureConnector)."""

    @staticmethod
    def _merged_perimeter(entry: dict) -> tuple[str, str, str] | None:
        """(rg, NSG, rule) of the perimeter block an entry carries next to its VM's
        placements — a `block` and a `block_perimeter` of one IP share one entry
        (`scoped: false`, RB1). None for any other entry."""
        if entry.get("scoped") is not False or not entry.get("nsg") or not entry.get("rule") or "/" not in entry["nsg"]:
            return None
        rg, name = entry["nsg"].split("/", 1)
        if any((p.get("nsg_rg"), p.get("nsg_name"), p.get("rule")) == (rg, name, entry["rule"])
               for p in entry.get("placements") or []):
            return None
        return rg, name, entry["rule"]

    def _perimeter_holds(self, cache: dict, t0: dict | None, ip: str, port) -> str:
        """'holds' | 'no' | 'unknown': a perimeter block of `ip` cuts it off this NIC — the
        entry's own or another VM's of the same subnet (one rule for the whole subnet, its
        name the IP alone): on an NSG that governs the NIC now, both rules present and
        whole, no allow before them letting the threat through. One holds: it holds.
        An allow a customer's deny before it already drops for the attacker lets nothing
        through: read as passing, the card said « n'est plus bloquée » of a NIC the
        perimeter still cut off (I3P, #366)."""
        if t0 is None:
            return "no"
        rule, out = self._block_rule_prefix(ip), "no"
        ips = t0.get("private_ips") or None
        for v in self._nic_nsg_views(t0):
            st, _ = self._block_pair_state(cache, v["nsg_rg"], v["nsg_name"], rule, ip, None)
            if st == "present":
                found = self._shadowed_deny(cache, v["nsg_rg"], v["nsg_name"], rule, inbound_src=[ip],
                                            inbound_dst=ips, outbound_src=ips, outbound_dst=[ip], port=port)
                if found is not None:
                    rules = self._list_rules(cache, v["nsg_rg"], v["nsg_name"])
                    found = [f for f in found if not _dropped_first(rules, f, ip, ips)]
                if found is not None and not self._threat_open(found):
                    return "holds"
                st = "unknown" if found is None else st
            out = "unknown" if st == "unknown" else out
        # Its subnet's NSG unread (a 429), absent from its views: a perimeter there is not
        # known — never « no », which said the IP reached a NIC it cut off (I3N, #746).
        return "unknown" if out == "no" and t0.get("subnet_unreadable") else out

    def _left_to_perimeter(self, cache: dict, perimeter, t0: dict | None, ip: str, port) -> bool:
        """A NIC of a merged entry with no placement of its own, behind the entry's perimeter
        — on an NSG that governs it, the pair holding: covered by design, nothing missing.
        A promotion leaves it so (its own block taken off, RB1): read as a NIC added since,
        its rules gone, the next pass said a drift that wasn't, and put them back over the
        promotion (RB1, second review)."""
        if perimeter is None or t0 is None:
            return False
        governs = (perimeter[0].lower(), perimeter[1].lower()) in {
            (v["nsg_rg"].lower(), v["nsg_name"].lower()) for v in self._nic_nsg_views(t0) if v.get("nsg_rg")}
        return governs and self._perimeter_holds(cache, t0, ip, port) == "holds"

    def _off_perimeter(self, rg: str, vm_name: str, nsg_rg: str, nsg_name: str,
                       seen: list | None = None) -> list[dict]:
        """The VM's NICs no NSG of which is the perimeter's: on another subnet (the perimeter
        lies on the primary NIC's). A perimeter block said `blocked` while one of them stayed
        open, and its promotion took their own block off them (RB1, review). Unreadable
        NICs RAISE: never "all covered" on a guess — nor "not covered": a NIC whose subnet
        couldn't be read (a 429) has no NSG of its subnet in its views, and was named off the
        perimeter it sits behind (L1Qs, I3G's seed 9). `seen`: every NIC read, appended to it —
        all of them off, the pair's NSG governs none of them (`_pair_at_home`, RSM3)."""
        home = (nsg_rg.lower(), nsg_name.lower())
        targets = self._get_vm_nic_targets(rg, vm_name, allow_no_nsg=True)
        if unread := [t["nic_short"] for t in targets if t.get("subnet_unreadable")]:
            raise RuntimeError(f"subnet of {', '.join(unread)} unreadable")
        if seen is not None:
            seen.extend(targets)
        return [t for t in targets
                if home not in {(v["nsg_rg"].lower(), v["nsg_name"].lower())
                                for v in self._nic_nsg_views(t) if v.get("nsg_rg")}]

    def _pair_off(self, cache: dict, perimeter, targets: dict, unread: list, ip: str) -> dict:
        """A merged entry's perimeter pair (RB1) on an NSG that governs none of the VM's NICs now —
        the subnet's NSG taken off it, or another put in its place (E7; RSM2a's night n° 50, #1057):
        gone for where it lies, whatever its content (docs/design/reaffirmation.md §2.3), never put
        back there (`perimeter_off`, its NSG « rg/name »). The check read its content alone, on the
        NSG it names: the VM held by its own block, `True`, the subnet's other VMs reached, nothing
        said. Its listing read all the same, for `rules_seen` (L1N). None of the NICs governed and the
        subnet of one unread (a 429), or the NICs themselves unread (`targets` empty, `nics_unread`): not
        known (A0) — a pair there whole is unread, by name, into `unread`, never gone nor held, nor « at
        home »; one absent or altered on its NSG is gone wherever that NSG is ({}: read as before), and
        never put back while this is unread (`reassert_gone._pair_not_home`): read « at home », a pair gone
        was put back on whatever NSG the subnet carries now (the review of RSM3). Governing one: {}."""
        if perimeter is None:
            return {}
        home = (perimeter[0].lower(), perimeter[1].lower())
        if targets and any(home in {(v["nsg_rg"].lower(), v["nsg_name"].lower()) for v in self._nic_nsg_views(t)
                                    if v.get("nsg_rg")} for t in targets.values()):
            return {}
        names = [perimeter[2], f"{perimeter[2]}-out"]
        if not targets or any(t.get("subnet_unreadable") for t in targets.values()):
            if self._block_pair_state(cache, *perimeter, ip, None)[0] != "present":
                return {}                     # gone (or unread) by its content, wherever its NSG is
            unread += [f"{n} ({perimeter[1]} : son rattachement au sous-réseau illisible)" for n in names]
            return {"pair_unread": names, "perimeter_nsg": perimeter[1], "pair_whole": True}
        self._list_rules(cache, perimeter[0], perimeter[1])
        return {"perimeter_off": f"{perimeter[0]}/{perimeter[1]}", "perimeter_nsg": perimeter[1]}

    def perimeter_nsg_now(self, resource_id: str) -> str | None:
        """« rg/name » of the NSG the VM's primary NIC's subnet carries now, None when it carries none; a
        read that fails RAISES. What a put-back of the reassertion asks before it writes a perimeter pair:
        never on an NSG other than the one its entry records (RSM3's review, `reassert_gone.refused_elsewhere`)."""
        from glorfindel.response.ids import _parse_nic_resource_id, _parse_vm_resource_id
        self._ensure_clients()
        nic_id = self._get_primary_nic_id(*_parse_vm_resource_id(resource_id))
        now = self._subnet_nsg_of(self._network.network_interfaces.get(*_parse_nic_resource_id(nic_id)))
        return f"{now[0]}/{now[1]}" if now else None

    def _pair_at_home(self, rg: str, vm_name: str, nsg_rg: str, nsg_name: str, reach: dict) -> dict:
        """A perimeter block alone (RB1): whether its pair's NSG still governs the VM's subnet, asked
        first — before its content and its precedence (RSM3, #1057, E7). The customer took that NSG
        off the subnet, an allow added there: the block was said « contourné », the pair intact on an
        NSG that governs nothing; without the allow, « ne couvre pas … (autre subnet) » — both false on
        their cause, and a pair read gone was put back on whatever NSG the subnet carries now. Every
        NIC of the VM off that NSG: gone for where it lies (`perimeter_off`), said, never put back.
        The NICs off it into `reach["off"]`, read once. Answers what stops the check here — the NICs
        unreadable (their subnet too: A0, never gone nor held), the pair's NSG off the subnet —, {}
        otherwise."""
        seen: list = []
        try:
            reach["off"] = self._off_perimeter(rg, vm_name, nsg_rg, nsg_name, seen=seen)
        except Exception as exc:
            return {"verified": None, "method": "nsg_check",
                    "error": f"blocage non vérifiable : cartes illisibles ({_first_line(exc)[:_ERR_MAX]})"}
        if not seen or len(reach["off"]) < len(seen):
            return {}
        return {"verified": False, "method": "nsg_check", "perimeter_off": f"{nsg_rg}/{nsg_name}",
                "perimeter_nsg": nsg_name,
                "error": f"la règle de périmètre est sur {nsg_name}, qui ne gouverne plus aucune carte de "
                         f"{vm_name} (ôté de son sous-réseau, ou remplacé)"}

    def _promote(self, prev: dict | None, off_ids: set | None, nic_id: str, nsg: str,
                 rule_name: str, resource_id: str = "") -> tuple[list[str], list[dict], list[str]]:
        """A promotion's drop of the VM block `prev` once the perimeter `rule_name` stands on
        `nsg` (rg/name): (dropped, kept, guarded). Each placement of a NIC behind it goes —
        but each of its two rules asks first the guard every removal by name asks
        (_held_by_turned, I4B; I4P, #466): one someone turned into an allow that lets the
        attacker reach another live NIC (an old address taken up, a NIC's NSG shared with a
        VM of another subnet, off the perimeter), taken off, cut that VM off where no
        perimeter reaches. One kept, the pair stays whole, on Azure and in the state
        (`kept`), for the unblock, which asks again — half taken off, the next pass read our
        own delete as a disappearance. A delete that fails stops the pair's: the first refused,
        the second is not tried, the pair stays whole; the second refused, the first is gone —
        either way the placement stays in the state and the unblock reads it again (before,
        swallowed: the rule left on Azure, unknown to the state). `guarded`: what stays, said
        (« …/rule gardée : … », or the delete's error). A NIC off the perimeter (`off_ids`),
        or unknown (None): kept as before. A legacy single-rule entry: the primary NIC's. A rule
        under an earlier version's name goes only when proven the placement's (older_names,
        SEC-H): written over since by a homonym whose hash met, the pair stays whole, said."""
        dropped: list[str] = []
        kept: list[dict] = []
        guarded: list[str] = []
        guard: dict = {}
        mates = [x.get("nic_id", "") for x in (prev or {}).get("placements", [])]

        from glorfindel.providers.azure.older_names import older_undo_refusal, recorded_names
        from glorfindel.response.state import _load_block_entries
        placed = recorded_names({}, _load_block_entries(resource_id) if resource_id else [], resource_id)

        def drops(nsg_rg: str, nsg_name: str, rule: str, nic: str, mates) -> bool:
            names = (rule, f"{rule}-out")
            short = nic.rstrip("/").rsplit("/", 1)[-1]
            said = [w for n in names if (w := older_undo_refusal(self._network, nsg_rg, nsg_name, n, nic, short,
                                                                 placed, "promotion non vérifiée"))]
            if said:
                guarded.extend(said)
                return False
            held = [w for n in names if (w := _held_by_turned(self._network, guard, nsg_rg, nsg_name, n, nic, mates))]
            held = held or next(([e] for n in names if (e := self._delete_rule(nsg_rg, nsg_name, n))), [])
            guarded.extend(held)
            return not held
        for pl in (prev or {}).get("placements", []):
            if off_ids is None or (pl.get("nic_id") or "").rstrip("/").lower() in off_ids:
                kept.append(pl)               # not behind the perimeter (or unknown): kept
            elif drops(pl["nsg_rg"], pl["nsg_name"], pl["rule"], pl.get("nic_id", ""), mates):
                dropped.append(pl["rule"])
            else:
                kept.append(pl)
        if prev and prev.get("rule") and not prev.get("placements") and prev["rule"] != rule_name:
            old_rg, old_name = (prev.get("nsg") or nsg).split("/", 1)
            if drops(old_rg, old_name, prev["rule"], nic_id, [nic_id]):
                dropped.append(prev["rule"])
            else:
                kept.append({"nic_id": nic_id, "nsg_rg": old_rg, "nsg_name": old_name,
                             "scope": prev.get("nsg_scope") or "nic", "shared_nsg": False, "ips": [],
                             "rule": prev["rule"]})
        return dropped, kept, guarded

    @staticmethod
    def _perimeters_recorded(ip: str, but: str) -> set[tuple[str, str]]:
        """(rg, NSG) of the perimeter blocks of `ip` another VM's entry records — theirs."""
        from glorfindel.response.state import active_blocks
        return {tuple(e["nsg"].lower().split("/", 1)) for e in active_blocks()
                if e.get("ip") == ip and e.get("scoped") is False and "/" in (e.get("nsg") or "")
                and (e.get("resource_id") or "").rstrip("/").lower() != but.rstrip("/").lower()}
