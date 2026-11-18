"""SEC-H (#849): REC1 and the local state, by the full identifier — our rule names end with 128 bits
of the NIC's id, the names of an earlier version read and never trusted on the name alone, the reset
lifting an older name its state records (glorfindel/providers/azure/nsg.py, network.py, release.py,
sweep.py, verify_block.py); the original's tag on 128 bits, the earlier key read, a tag naming only an
NSG of the subscription, a quarantine NSG of another group never followed (quarantine.py,
quarantine_origin.py); a state file a VM's only when it records its id, an unreadable block file set
aside, never deleted with the other addresses' entries (glorfindel/response/state_files.py, state.py);
REC1's callers by object id, its next pages on ARM (recovery.py); the jobs, the claims and the last
restore by the full id, the vault's job by its container (glorfindel/jobs.py, backup.py); the ARM
writes and the writers' lock waited a bounded time, the VM the reassertion skips said (sdk.py,
glorfindel/reassert.py). M5801–M5820; M5941–M5945 for the review (an earlier version's names on
the NSG a bare NIC left and for a deleted VM, a name per IPv6 address, the conflict said at the
release — numbers handed by the Orchestre), measured by tests/unit/test_wide_marks.py,
tests/unit/test_full_id_keys.py and the frozen two hosts of tests/unit/test_invariant_regressions.py."""
NSG = "glorfindel/providers/azure/nsg.py"
REL = "glorfindel/providers/azure/release.py"
SWP = "glorfindel/providers/azure/sweep.py"
VBL = "glorfindel/providers/azure/verify_block.py"
QUA = "glorfindel/providers/azure/quarantine.py"
QOR = "glorfindel/providers/azure/quarantine_origin.py"
REC = "glorfindel/providers/azure/recovery.py"
BCK = "glorfindel/providers/azure/backup.py"
SDK = "glorfindel/providers/azure/sdk.py"
STF = "glorfindel/response/state_files.py"
STA = "glorfindel/response/state.py"
JOBS = "glorfindel/jobs.py"
AWY = "glorfindel/providers/azure/away.py"
GON = "glorfindel/providers/azure/gone.py"
NET = "glorfindel/providers/azure/network.py"
RA = "glorfindel/reassert.py"
_W = "tests/unit/test_wide_marks.py"
_K = "tests/unit/test_full_id_keys.py"
_R = "tests/unit/test_invariant_regressions.py"

MUTANTS = [
    ("M5801", "our rule names end with 6 hex of SHA-1 again: two NICs that meet share their rules (SEC-H)", NSG,
     '    return hashlib.sha256(nic_id.rstrip("/").lower().encode()).hexdigest()[:MARK_SIZE]\n',
     '    return hashlib.sha1(nic_id.rstrip("/").lower().encode()).hexdigest()[:6]\n'),
    ("M5802", "an older name read as ours by the name alone: a homonym's deny under it taken off (SEC-H)", REL,
     '        hashed = {n for b in self._placement_rule_bases("glorfindel-iso", vm_name, t["nic_short"], t["nic_id"])\n'
     '                  for n in (b, f"{b}-out")}\n',
     '        hashed = {n for b in (*self._placement_rule_bases("glorfindel-iso", vm_name, t["nic_short"], t["nic_id"]),\n'
     '                              *self._older_rule_bases("glorfindel-iso", vm_name, t["nic_short"], t["nic_id"]))\n'
     '                  for n in (b, f"{b}-out")}\n'),
    ("M5803", "an isolation placed under the older names, its state lost, never read (SEC-H)", REL,
     '                 *self._older_rule_bases("glorfindel-iso", vm_name, t["nic_short"], t["nic_id"]),\n', ""),
    ("M5804", "the reset ignores the older names its state records: their deny left on the old address (SEC-H)",
     SWP,
     '                hashed = hashed | recorded.get((nsg_key, t["nic_id"].rstrip("/").lower()), set())\n',
     "                hashed = hashed\n"),
    ("M5805", "a block placed under the older names, its state lost, read missing (SEC-H)", VBL,
     '                     *self._older_rule_bases(prefix, vm_name, t0["nic_short"], t0["nic_id"]),\n', ""),
    ("M5806", "the orphan sweep reads the older marks only: an orphan under ours never found (SEC-H)", NSG,
     '    return len(text) in (6, 8, MARK_SIZE) and all(c in "0123456789abcdef" for c in text)\n',
     '    return len(text) in (6, 8) and all(c in "0123456789abcdef" for c in text)\n'),
    ("M5807", "a state file whose 8 hex meet another id's written over: one homonym's state replaces the "
     "other's (SEC-H)", STF,
     '    if owner and owner != rid.rstrip("/").lower():\n', "    if False:\n"),
    ("M5808", "a state file under its 128-bit key never found again (SEC-H)", STF,
     '    files = {f for pattern in (f"*--{_rid_hash(rid)}.json", f"*--{_rid_key(rid)}.json")\n',
     '    files = {f for pattern in (f"*--{_rid_hash(rid)}.json",)\n'),
    ("M5809", "the original's tag keyed on 48 bits again (SEC-H)", QOR,
     '        return "glorfindel-orig-" + hashlib.sha256(nic_id.rstrip("/").lower().encode()).hexdigest()[:32]\n',
     '        return "glorfindel-orig-" + hashlib.sha1(nic_id.rstrip("/").lower().encode()).hexdigest()[:12]\n'),
    ("M5810", "the original an earlier version tagged never read: its NIC kept in quarantine (SEC-H)", QUA,
     "        value = tags.get(key) or tags.get(self._older_orig_tag(nic_id))\n",
     "        value = tags.get(key)\n"),
    ("M5811", "REC1 reads a token's appid as its caller: a user through the application of a principal that "
     "restores counts for it (SEC-H)", REC,
     '    ids = [claims.get(_OID_CLAIM), claims.get("oid")]\n',
     '    ids = [claims.get(_OID_CLAIM), claims.get("oid"), claims.get("appid")]\n'),
    ("M5812", "the reassertion skips a VM whose lock is held in silence again (SEC-H)", RA,
     '            skips.skipped(report, snapshot["vm_name"], snapshot["resource_id"])\n', ""),
    ("M5813", "REC1 follows a next page off Azure Resource Manager with its token (SEC-H)", REC,
     "            if not str(url).startswith(ARM_PREFIX):\n", "            if False:\n"),
    ("M5814", "a new block writes over an unreadable block file (SEC-H)", STA,
     "    _set_aside_unreadable(resource_id or vm_name, _BLOCK_STATE_DIR)\n", ""),
    ("M5815", "unblocking one address deletes an unreadable block file with the others' entries (SEC-H)", STA,
     "    if f is None or _unreadable_in(_BLOCK_STATE_DIR, vm_ref):\n        return\n    entries = [",
     "    if f is None:\n        return\n    entries = ["),
    ("M5816", "a tag naming an NSG of another subscription taken for the original (SEC-H)", QOR,
     "        if mine and _subscription_of(value).lower() != mine:\n", "        if False:\n"),
    ("M5817", "a re-isolation that meets another group's original keeps our stale « none »: the release "
     "leaves the NIC bare (SEC-H)", QUA,
     '                        self._forget_original(q, t["nic_id"], strict=True)\n', ""),
    ("M5818", "the jobs and the last restore keyed by the short name again (SEC-H)", JOBS,
     '    return f"{name.lower()}--{_rid_key(rid)}" if rid else name\n', "    return name\n"),
    ("M5819", "the vault's job of a homonym in another group taken for this VM's (SEC-H)", BCK,
     "                if (vm_rg and isinstance(container, str) and container\n",
     "                if (False and isinstance(container, str) and container\n"),
    ("M5820", "an ARM write not done by its deadline read done (SEC-H)", SDK,
     "    if callable(done) and done() is False:\n", "    if False:\n"),
    ("M5941", "a bare NIC's NSG out of sight read for the new names only: an earlier version's pair left, "
     "the release said done (SEC-H, review)", AWY,
     "                    t0 = older.get(name.lower())\n", "                    t0 = None\n"),
    ("M5942", "an older name on an NSG out of sight taken whatever it aims at (SEC-H, review)", AWY,
     '                    if not _deny_applies(r, t0.get("private_ips") or None):\n', "                    if False:\n"),
    ("M5943", "a deleted VM's older pair never looked for (SEC-H, review)", GON,
     "                    names.add(name.lower())\n", "                    continue\n"),
    ("M5944", "two IPv6 blocks cut to one name (SEC-H, review)", NET,
     '                base = f"{prefix[:80 - 4 - 1 - len(mark) - 1 - len(held)]}-{held}-{mark}"\n',
     '                base = f"{prefix[:80 - 4 - 1 - len(mark)]}-{mark}"\n'),
    ("M5945", "the conflict met at the isolation forgotten at the release (SEC-H, review)", REL,
     '                            if p.get("original_conflict"):\n', "                            if False:\n"),
]
TESTS = {
    "M5801": f"{_W}::test_the_two_nics_meet_on_the_older_mark_never_on_ours "
             f"{_W}::test_the_release_of_one_never_takes_off_the_others_deny",
    "M5802": f"{_W}::test_a_homonyms_rule_under_the_shared_older_name_stays",
    "M5803": f"{_W}::test_an_isolation_under_the_older_names_its_state_lost_is_still_found",
    "M5804": f"{_W}::test_the_reset_lifts_an_older_name_its_state_records_after_the_address_moved",
    "M5805": f"{_W}::test_a_block_under_the_older_names_its_state_lost_is_still_found",
    "M5806": f"{_W}::test_an_orphan_under_the_new_mark_is_found",
    "M5807": f"{_K}::test_two_homonyms_whose_keys_meet_keep_two_states",
    "M5808": f"{_K}::test_the_second_homonym_finds_its_file_once_the_first_is_gone",
    "M5809": f"{_W}::test_the_original_is_kept_under_128_bits_and_read_under_the_older_key",
    "M5810": f"{_W}::test_the_original_is_kept_under_128_bits_and_read_under_the_older_key",
    "M5811": f"{_K}::test_a_users_delegated_token_is_never_its_applications_principal "
             f"{_K}::test_a_user_through_the_trusted_application_neutralizes_nothing",
    "M5812": f"{_K}::test_a_vm_skipped_pass_after_pass_is_said_on_one_card",
    "M5813": f"{_K}::test_a_next_page_outside_arm_is_refused_before_the_token_goes_there",
    "M5814": f"{_K}::test_a_new_block_sets_an_unreadable_file_aside_never_writes_over_it",
    "M5815": f"{_K}::test_unblocking_one_address_of_an_unreadable_file_keeps_the_file",
    "M5816": f"{_K}::test_a_tag_that_names_what_cant_be_an_original_is_unknown",
    "M5817": f"{_R}::test_two_hosts_a_stale_none_never_leaves_the_nic_bare",
    "M5818": f"{_K}::test_a_homonyms_restore_is_never_this_vms",
    "M5819": f"{_K}::test_the_vaults_job_of_a_homonym_is_never_this_vms",
    "M5820": f"{_K}::test_an_arm_write_that_does_not_end_is_never_read_done",
    "M5941": f"{_W}::test_an_older_isolation_on_the_nsg_a_bare_nic_left_is_lifted",
    "M5942": f"{_W}::test_an_older_name_on_that_nsg_aimed_elsewhere_is_left_and_said",
    "M5943": f"{_W}::test_a_gone_vms_older_pair_its_record_rewritten_is_lifted_by_its_recorded_address",
    "M5944": f"{_W}::test_two_long_ipv6_blocks_never_share_a_name",
    "M5945": f"{_K}::test_the_conflict_met_at_the_isolation_is_said_again_at_the_release",
}
