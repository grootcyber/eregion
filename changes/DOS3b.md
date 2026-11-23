### Changed
- **The design of the isolation dossier records the operator's decisions of 23/11** (DOS3b, #1063; `docs/design/dossier-isolation.md` §4.6, §11, §12; `docs/glorfindel.md`, « Le dossier d'une isolation »). No code changes.
  - A block executed alone has no dossier: its card, its reasoning and its decision line already say why. The exception first asked for an internal address never arises: the never-block list never lets a private address be blocked, whatever the provider, and lateral movement is answered by isolating the source VM. It would come back only if blocking an address of the client's network outside the private ranges became possible, which first needs the discovery to keep the client's networks.
  - A detection with no attributed VM keeps its local dossier of step 0; the reads of Azure (DOS4) will never be made for it, and its dossier will say so.
  - The hourly ceiling of dossiers is to be asked again when DOS4 is framed, with the proposal written in the design.
  - An open point is noted for DOS4 or DOS6: a proposed block approved later from the console starts its dossier's clock at the first pass, whether the block holds or not.
