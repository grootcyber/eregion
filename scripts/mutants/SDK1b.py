"""SDK1b (#1017): the ten azure.mgmt operations the adapters read most, read on the pinned SDKs' own
objects — an enum read as its text, a field the body leaves out read as if it were there, a
polymorphic job or point read by its order or its class — and the maintainer's capture of their
bodies (scripts/sdk_capture.py, its anonymization scripts/sdk_anonymize.py): a write let through, the
closed list opened, a real GUID or address left in the files. M6962–M6976, measured by
tests/unit/test_sdk_mgmt_contracts.py and tests/unit/test_sdk_capture.py; after the review,
M7061–M7065: an IPv6 address left, a domain outside Azure's let through by the check, a name resolved
past the suite's network guard (tests/unit/test_network_guard.py), a retried response kept twice, an
output under a git checkout accepted; after its second round, M7066–M7067: a domain shaped like an
operation's name taken for one, a reverse resolution past the guard."""
_T = "tests/unit/test_sdk_mgmt_contracts.py"
_C = "tests/unit/test_sdk_capture.py"
_S = "scripts/sdk_capture.py"
_A = "scripts/sdk_anonymize.py"
_G = "tests/unit/network_guard.py"
_N = "tests/unit/test_network_guard.py"
_AZ = "glorfindel/providers/azure"

MUTANTS = [
    ("M6962", "an SDK enum read by its str(): every allow the SDK hands on reads « securityruleaccess.allow », "
     "the precedence check finds none — the 06/10 bug (SDK1b)", f"{_AZ}/sdk.py",
     '    return str(getattr(value, "value", value) or "").lower()\n',
     '    return str(value or "").lower()\n'),
    ("M6963", "the OS type read by its str(): « operatingsystemtypes.linux », the readiness knows no OS (SDK1b)",
     f"{_AZ}/readers.py",
     '        return _enum_text(getattr(getattr(vm.storage_profile, "os_disk", None), "os_type", ""))\n',
     '        return str(getattr(getattr(vm.storage_profile, "os_disk", None), "os_type", "")).lower()\n'),
    ("M6964", "`dataDisks` left out of the body read as a list: the audit says the VM unreadable (SDK1b)",
     f"{_AZ}/readers.py",
     "                for d in (vm.storage_profile.data_disks or [])\n",
     "                for d in vm.storage_profile.data_disks\n"),
    ("M6965", "a subnet without NSG read as if it had one: its NIC's subnet said unreadable, never « none » (SDK1b)",
     f"{_AZ}/network.py",
     "        if subnet.network_security_group is None:\n            return None\n"
     "        return _parse_nsg_resource_id(subnet.network_security_group.id)\n",
     "        return _parse_nsg_resource_id(subnet.network_security_group.id)\n"),
    ("M6966", "a property bag's keys no longer folded: « Recovery point time  » with its trailing space, the "
     "point a restore restored not found (SDK1b)", f"{_AZ}/recovery.py",
     '    return {" ".join(str(k).split()).lower(): str(v) for k, v in dict(bag).items()}\n',
     "    return {str(k).lower(): str(v) for k, v in dict(bag).items()}\n"),
    ("M6967", "a job's details without `extendedInfo` read as if they had it: an error, never an empty bag (SDK1b)",
     f"{_AZ}/recovery.py",
     '    bag = getattr(info, "property_bag", None) or {}\n',
     "    bag = info.property_bag or {}\n"),
    ("M6968", "the posture's age read from the first point Azure lists, not the newest: they come in no "
     "order (SDK1b)", f"{_AZ}/backup.py",
     "            latest = max((t for t in times if t), default=None)\n",
     "            latest = next((t for t in times if t), None)\n"),
    ("M6969", "a point's tier read by its str(): no point in the vault tier, a restore takes a snapshot's (SDK1b)",
     f"{_AZ}/restore.py",
     '        t.type == "HardenedRP" and getattr(t, "status", "") == "Valid"\n',
     '        str(t.type) == "HardenedRP" and getattr(t, "status", "") == "Valid"\n'),
    ("M6970", "an NSG with our quarantine's name and no tags read as if it had some: the pass's quarantine "
     "check raises (SDK1b)", f"{_AZ}/quarantine.py",
     '                    or (getattr(nsg, "tags", None) or {}).get("managed-by") != "glorfindel"):\n',
     '                    or nsg.tags.get("managed-by") != "glorfindel"):\n'),
    ("M6971", "a NIC without NSG of its own read as if it had one: the orphan sweep of the pass raises (SDK1b)",
     f"{_AZ}/sweep.py",
     '            nic_nsg[nid] = (getattr(getattr(nic, "network_security_group", None), "id", None) or "")'
     '.rstrip("/").lower()\n',
     '            nic_nsg[nid] = nic.network_security_group.id.rstrip("/").lower()\n'),
    ("M6972", "an NSG whose body leaves out `subnets` read as a list: the NSG audit and every verification of "
     "the VM fail (SDK1b)", f"{_AZ}/network.py",
     '        subnets = list(getattr(nsg, "subnets", None) or [])\n',
     "        subnets = list(nsg.subnets)\n"),
    ("M6973", "the capture's transport lets a PUT and a PATCH through: only DELETE refused (SDK1b)", _S,
     '            if str(request.method).upper() != "GET":\n',
     '            if str(request.method).upper() == "DELETE":\n'),
    ("M6974", "the capture's closed list opened to a write (SDK1b)", _S,
     '    "network.subnets.get",\n',
     '    "network.subnets.get",\n    "network.security_rules.begin_delete",\n'),
    ("M6975", "the anonymization blind to an uppercase GUID: a real one left in the files (SDK1b)", _A,
     'GUID = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"\n',
     'GUID = re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"\n'),
    ("M6976", "the anonymization blind to a dashed address: a block's name keeps its real attacker (SDK1b)", _A,
     '        out = _sub_all(out, {k.replace(".", "-"): v.replace(".", "-") for k, v in self.ips.items()},\n'
     '                       r"(?<![0-9])", r"(?![0-9])")\n',
     ""),
    ("M7061", "the anonymization blind to IPv6: a real address left in the files (SDK1b, review)", _A,
     "        out = IPV6.sub(lambda m: self.ipv6(m.group(0)), out)\n", ""),
    ("M7062", "the check blind to a domain outside Azure's: `check` says clean (SDK1b, review)", _A,
     "             any(_is_domain(v, m) and not _domain_kept(m.group(1).lower())\n"
     "                 for k, v in _strings(cap) if not _operation(k, v) for m in DOMAIN.finditer(v))),\n",
     "             False),\n"),
    ("M7063", "the suite's network guard lets a name be resolved beyond the machine (SDK1b, review)", _G,
     '"socket.sendmsg": 1, "socket.getaddrinfo": 0,', '"socket.sendmsg": 1,'),
    ("M7064", "a response the SDK retried kept from its first attempt: the 429, not the 200 (SDK1b, review)", _S,
     "        if 200 <= p.http_response.status_code < 300:\n            kept[p.http_request.url] = p\n",
     "        kept.setdefault(p.http_request.url, p)\n"),
    ("M7065", "the capture writes under a git checkout, this repository's aside (SDK1b, review)", _S,
     '        if folder == REPO or (folder / ".git").exists():\n', "        if folder == REPO:\n"),
    ("M7066", "the broad exclusion back: `compute.acmecorp.fr` taken for an operation's name, left as it is "
     "(SDK1b, second round)", _A,
     '    return token.rsplit(".", 1)[-1].lower() not in FILE_ENDINGS\n',
     '    return token.rsplit(".", 1)[-1].lower() not in FILE_ENDINGS and not re.fullmatch(\n'
     '        r"(?:network|compute|backup)\\.[a-z_]+\\.[a-z_]+", token.lower())\n'),
    ("M7067", "the suite's network guard lets an address be resolved back beyond the machine (SDK1b, second round)",
     _G, '"socket.gethostbyaddr": 0, "socket.getnameinfo": 2}', '"socket.gethostbyaddr": 0}'),
]
TESTS = {
    "M6962": f"{_T}::test_the_nsg_audit_through_the_sdk",
    "M6963": f"{_T}::test_the_vm_through_the_sdk_names_its_nic_its_os_and_its_disks",
    "M6964": f"{_T}::test_a_vm_whose_body_leaves_out_its_data_disks",
    "M6965": f"{_T}::test_a_subnet_without_nsg_is_read_as_none_and_an_unread_one_as_unknown",
    "M6966": f"{_T}::test_a_job_s_details_through_the_sdk",
    "M6967": f"{_T}::test_a_job_whose_details_carry_no_extended_info",
    "M6968": f"{_T}::test_the_recovery_points_through_the_sdk",
    "M6969": f"{_T}::test_the_recovery_points_through_the_sdk",
    "M6970": f"{_T}::test_an_nsg_with_our_name_and_no_tag_is_not_ours",
    "M6971": f"{_T}::test_the_orphan_sweep_reads_the_nic_listing_through_the_sdk",
    "M6972": f"{_T}::test_the_nsg_audit_through_the_sdk",
    "M6973": f"{_C}::test_the_transport_refuses_any_method_but_get_before_it_leaves",
    "M6974": f"{_C}::test_the_script_reads_only_from_a_closed_list",
    "M6975": f"{_C}::test_nothing_real_leaves_the_anonymization",
    "M6976": f"{_C}::test_a_rule_of_glorfindel_still_names_its_nic_and_its_attacker",
    "M7061": f"{_C}::test_a_body_made_to_trap_the_anonymization_comes_out_clean",
    "M7062": f"{_C}::test_check_refuses_each_form_the_anonymization_must_not_leave",
    "M7063": f"{_N}::test_the_rule_reaches_this_machine_only "
             f"{_N}::test_a_connection_beyond_this_machine_is_refused_before_it_leaves",
    "M7064": f"{_C}::test_a_response_retried_by_the_sdk_is_kept_once",
    "M7065": f"{_C}::test_the_out_folder_is_under_no_git_checkout",
    "M7066": f"{_C}::test_a_domain_shaped_like_an_operation_a_namespace_or_a_file_is_a_domain",
    "M7067": f"{_N}::test_the_rule_reaches_this_machine_only "
             f"{_N}::test_a_connection_beyond_this_machine_is_refused_before_it_leaves",
}
