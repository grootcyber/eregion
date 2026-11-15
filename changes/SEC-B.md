### Security
- **The signed action queue is ready to be turned on: the five points the audit of 06/11 left open
  are closed** (SEC-B, #634; `docs/design/file-actions-signee.md` §2.4, §2.8, §2.9, §10). The flag
  `EREGION_ACTION_QUEUE` stays off by default; turning it on, after its measure on the bench, is
  not part of this change.
  - **A proposal is signed from the watch's own state only** (audit du 06/11, V-06): from its
    decision when it writes a card, and, when a card is seen again, from the proposal it signed on
    that card while the card still carries it — remembered by the card's id, never by its signal's.
    A card another writer of the store made, or whose proposal was replaced, is never signed. The
    port signed is the decision's, and the card says it (§2.4, its nuance closed for the port; the
    text of such a card stays unsigned until FS1f, said).
  - **What runs is the target of the signed proposal, compared at the byte** (audit du 06/11,
    V-08): the guards, the VM's lock, the connector and the receipt take the proposal's target and
    address; a request that names it in another spelling is refused (`proposal_mismatch`), an
    identifier out of ASCII too (`not_ascii`). The console and the bot copy the proposal's target.
  - **The watch's relève never freezes** (audit du 06/11, V-09): judging, refusing and writing the
    receipt never wait for an execution. An accepted request waits in a bounded wait list, in
    priority (a containment before a lift); full, it is refused at once (`busy`); its turn come
    after its end of life, refused and said (`no_slot`), never run late, its proposal not consumed.
    The signed status stays fresh and says what runs and what waits.
  - **The registers are under a lock between processes** (audit du 06/11, V-10): the nonces seen
    and the proposals consumed under an `flock`, and a second watch on the same HOME, the queue on,
    is refused, said, and stops before its first heartbeat.
  - **A line of the escalations' store that is not a card fails nothing** (audit du 06/11, V-12):
    every read passes it, every rewrite keeps it as it is, to the byte, and it is said once by its
    length and a digest. The receipt of an action done no longer says `failed` because its card
    could not be settled, and `/api/state` stands.
  - Tests: `tests/unit/test_action_proposal.py`, `test_action_queue_watch.py`, `test_locks.py`;
    mutants M5426–M5445 (`scripts/mutants/SEC-B.py`).
