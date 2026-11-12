### Added
- **Design: a measure that arrives late is judged** (ING1, #738; `docs/design/mesure-en-retard.md`).
  Founded on the bench on 11/11: after bree's lift, its `Perf` samples arrived in one block, up to
  27 minutes after their time, while `Heartbeat` kept arriving within seconds. Every shipped rule
  selects its lines by `TimeGenerated`, and so does the query window the RulePoller asks for: the
  samples above the threshold from 15:56 to 16:06 were never in the rule's window, and the detection
  came only because the write was still going on after 16:07. The design inventories the eighteen
  shipped rules and the bench's three copies, with their window, their source and what is known of
  its lateness (measured, documented or unknown), and weighs the ways to judge a late line, including
  a catch-up window that would cover every rule unchanged. It recommends judging a line at its
  arrival (`ingestion_time()`, written by the platform), up to a lateness horizon the rule declares
  (`late_s`, two hours proposed), while aggregating on its time, so that a pair of samples or ten
  failures in ten minutes keep their meaning, whatever the order of arrival; an aggregate is judged
  when its last line arrives. Deduplication is split: an event's identity is kept for the whole
  window, so a line is never judged twice, and an aggregate's for the selection window as today, so a
  second burst on the same VM after a lift still makes a card. The correlation looks for logins from
  the time of the failures, so a login delivered late with its brute force is not lost. No query
  more per pass; the server reads thirteen times more lines for the ten-minute rules (twenty-five for
  the five-minute one) and returns as many as before; the model's message keeps its shape, the
  lateness facts kept in a file of their own. If the quarantine holds the guest's telemetry back (a
  hypothesis to measure first), a detection before the lift cannot come from the guest, and a late
  human lift needs a catch-up read with absolute bounds. The lateness itself is shown per VM and per
  table, read over 48 hours of event time, with a card only when entering the state of lines beyond the horizon, or of a sampled table
  gone silent while `Heartbeat` arrives (never for `Syslog`, which follows events), and as a fact of
  the isolation record. Twelve hypotheses to measure, most of them read-only on data kept until early
  December; the code lots ING2 to ING7; ten questions for the operator. Linked from
  `docs/glorfindel.md`. No code yet.
