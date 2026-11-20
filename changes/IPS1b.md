### Added
- **A VM's own addresses on its card in the Glorfindel page: its private IPs and its public one** (IPS1b, #931; `docs/design/console.md`, « Les adresses d'une VM sur sa carte »). Jonathan's choice on a mockup (19/11, option A): an alert names an address, and the operator must find its VM and know whether the Internet can reach it.
  - Folded and unfolded, a line under the VM's name: its private addresses (four at most, then « +N »), then its public one behind 🌐, in yellow. Browser search (Ctrl+F) finds the VM of an address without unfolding a card, up to four addresses.
  - Unfolded, each NIC with its addresses, and the age of the read (« read by the NSG audit … »).
  - An address is copied in one click, and the card does not unfold. In a secure context (the loopback, the SSH tunnel) the page writes the clipboard; elsewhere (a plain http address of the tailnet) the browser copies the selected address during the click itself, since a selection left for Ctrl+C would go with the next refresh. The address is selectable on its draggable card, and the toast says « copied » or « not copied » from the browser's answer.
  - What did not read is said: « ip — » and its reason when the VM's NSG audit failed; « 🌐 ? » and its reason when a public address did not read, so the VM is still shown exposed.
  - The VM's addresses are plain text; the filled orange badge stays an attacker's blocked address.
  - The addresses are the NSG audit's (`nsgs[].ips`, and `nsgs[].public_ips` from IPS1a), read again with it every 5 minutes. Everything from Azure is escaped; no inline script; the Discord bot is unchanged.
  - Tests: `tests/unit/test_console_ips.py`; mutants M6431–M6442 (`scripts/mutants/IPS1b.py`).
