### Added
- **Design: the alerts of Microsoft Defender for Cloud and Microsoft Sentinel as signals, nothing turned
  on** (DEF1, #1020; `docs/design/alertes-hebergeur.md`). Glorfindel detects with its own 20 rules, and
  reads none of what the host's products see. The design prepares an adapter, on the maintainer's
  decision of 21/11, through the signal contract (`eregion_core/signals.py`). The recommended way is a
  source of its own on the `SecurityAlert` table of the workspace Glorfindel already reads, fed by
  Defender for Cloud's continuous export, which does not depend on Sentinel's portal: no new right,
  `Log Analytics Reader` is enough. The alerts API of Azure Resource Manager is measured beside it as the
  fallback; Microsoft Graph is set aside, for its permission reads the whole tenant. An alert becomes a
  signal inside the watch, never through the `runs/` channel. Only the shipped query, by its name and its
  fingerprint, has its columns read as the service wrote them. An alert is kept by its type, in a closed
  list written in the repository, and attributed to a VM by its resource (`ResourceId`), never by a name;
  otherwise it is attributed to none and follows SLF1. The product's name proves nothing, since a
  Sentinel rule rewrites it, and the workspace is written down as a root of trust: whoever can write an
  analytics rule or a transformation there can forge an alert, while Glorfindel's identities only read
  it. Its decision is built by the code, like the control plane's and the identities': a card, no
  autonomous action, no call to the model, no incident fed, no precedent in memory, never the grave class
  of the decision queue. That decision skips the chain of guards, so what holds is said: the builder
  proposes nothing aimed at a VM without an attribution, and ATT1 refuses in one click any unattributed
  card aimed at a VM. Its text comes from outside and is escaped and bounded wherever it is shown. A
  shipped rule is never held back by an alert: when both see the same thing, the alert becomes a fact on
  the rule's card, by a correspondence written in the repository; the host's silence proves nothing, and
  the coverage stays that of Glorfindel's rules. Everything said of Microsoft's products is a hypothesis
  (twenty-one, each with its public source) until measured: the first lot is a paid bench measure by the
  maintainer (Defender for Servers Plan 1 on one bench VM for the test, the continuous export, sample
  alerts, the EICAR test file, then two techniques already played), judged on criteria written before
  it. Eight questions for the maintainer, and the code lots DEF3 to DEF7 if the measure says so. Linked
  from `docs/glorfindel.md` and `CLAUDE.md`. No code.
