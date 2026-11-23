### Added
- **Design: the configuration edited from the console** (CFG1, #1090;
  `docs/design/configuration-console.md`). Today the console only sets a VM's autonomy mode and the
  default one, by rewriting `glorfindel-config.yaml` itself, which loses its comments; everything else
  is edited by hand. The note inventories every key of the file (what it does, who writes it, what the
  console shows, when the watch reads it again), the discovery and what the console already knows. It
  proposes that the console start from what the discovery found (a VM, then the networks and public
  addresses), writing exact names, never a pattern; that the file stay the reference, edited by a
  round-trip write that keeps its comments, its version being the hash of its bytes, so a stale request
  or an edit by hand is never overwritten; that the console ask and the watch write, through a new kind
  of signed request in the action queue, the result read by the strict reader before it is written, with
  a history (who, when, the operation, the way back by its inverse operation), all of that state in a
  directory only the watch writes, read-only for the console and the bot; that tightening apply at once
  and relaxing (an exclusion, an expected origin, a bolder mode) wait for a typed confirmation, a reason
  and a delay or a second factor, said on the console and on Discord, its class computed from the
  configuration's meaning for every name it targets, never from the discovery nor the request, and
  applied only once the bot has posted the announcement; and that everything relaxed stay visible, an
  excluded VM greyed on the map with its reason. It says what changes at the console's boundary, asks
  eleven questions of the maintainer, and proposes eight lots of code, CFG2 to CFG9. No code changes.
