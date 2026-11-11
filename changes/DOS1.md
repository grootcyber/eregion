### Added
- **Design: the record of an isolation, the facts read after the action so a human only has to
  judge** (DOS1, #727; `docs/design/dossier-isolation.md`). Founded on the bench night of 10/11: bree
  isolated itself on a 20-second write burst that started 31 s after its nightly backup, which the
  host's metric saw far lower. Every guard was right about what it reads, none reads the platform, and
  under Linux the investigation's backup-agent query always returns nothing. The design defines a
  record for every isolation and every card that proposes one: facts, never a verdict, each with its
  source, its author (the platform, the guest, which a local user can forge in `Syslog`, or Glorfindel)
  and its state (read, empty, not applicable, unreadable, pending; unreadable is never empty). The
  facts cover the platform's context (a vault job, an extension, a reboot, a maintenance), a second
  opinion from the host compared minute by minute, the recurrence over ten days and against the
  backups, the accepted connections, the aftermath (Glorfindel's own operations, the session cut, the
  check, the cards) and the decision as it was taken (the model and the sampling, which the debug line
  does not say plainly today, the version, the rule). It is composed after the action, in a thread of
  its own, under the rights Imladris already holds, and bounded. It shows on the console's card and in
  Discord, and never in what the model sees. Whether a fact becomes a guard is the operator's
  question; the design recommends judgment only until the host's divergence is measured. Eight
  questions for the operator, twelve hypotheses to measure, most of them read-only on data kept until
  early December, and the code lots DOS2 to DOS8. Linked from `docs/glorfindel.md`. No code yet.
