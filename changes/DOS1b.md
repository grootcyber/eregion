### Changed
- **Design of the record of an isolation: the operator's nine decisions of 12/11 and the first bench
  measure written in** (DOS1b, #1041; `docs/design/dossier-isolation.md`). The record serves
  judgment only, with no guard in the first version; it is composed for every isolation executed and
  every card that proposes an isolation or an address block without executing it; it never reaches
  the model in the first version; in Discord it comes as a message in the VM's thread at each step,
  not as a field of the card; a VM isolated without an answer is recalled in its thread 4 h after the
  isolation, then every 12 h, until its card is acknowledged, lifted or restored; the recurrence is
  read over 10 days, a record kept 30 days after the lift, at most 6 records an hour for the whole
  watch. The measure of 12/11, read-only on kept data, compared the guest and the host on the same
  quantity, the mean of the minute: they agree within about 15 %, the host one minute late. The
  earlier comparison of a 10-second guest sample against the host's one-minute mean was wrong and is
  removed: the bench night of 10/11 was a false positive by its duration, a peak of 10 to 20 s, while
  the write of 11/11 was real, sustained and confirmed by the host. A guard by the host would have
  stopped neither. The host also saw the bench encryption on a data disk. The measure noted an
  ingestion delay of up to 20 min 34 s after a network cut, the subject of the late-measure design.
  The code lots DOS2 to DOS8 are aligned with the decisions, with the file ceilings of WCH1, and with
  the 0.7 direction (ENQ1, #1040), where the record becomes one source of the knowledge base; DOS4
  and DOS5 wait for its catalogue. The isolation-record paragraph of `docs/glorfindel.md` follows.
  No code yet.
