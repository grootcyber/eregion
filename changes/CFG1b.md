### Changed
- **Design: the eleven questions on the configuration edited from the console are answered** (CFG1b,
  #1112; `docs/design/configuration-console.md`). The maintainer chose the recommended option each
  time (23/11): the watch writes through the signed queue, the console keeps writing the mode directly
  until CFG5, relaxing waits for a typed confirmation, the bot's announcement and a 10-minute delay,
  and the note now says "decided" where these answers settle a point. No code changes.
