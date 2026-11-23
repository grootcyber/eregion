"""DOS3b (#1063): the dossier of a block of an internal address — its scope (a block executed alone has none,
but for an internal address; one that cannot be read, a dossier not composed that says so) and its
retention (30 days after the unblock seen), the decisions of 23/11 (glorfindel/dossier.py,
glorfindel/dossier_block.py). M7091–M7094: a public address said internal; an internal block out of the
scope; the retention without waiting for the unblock; an unreadable address said public. Measured by
tests/unit/test_dossier_block.py."""
DOSSIER = "glorfindel/dossier.py"
BLOCK = "glorfindel/dossier_block.py"
_T = "tests/unit/test_dossier_block.py"

MUTANTS = [
    ("M7091", "a public address said internal: every executed block gets a dossier (DOS3b)", BLOCK,
     "        if addr.version == net.version and addr in net:\n",
     "        if True:\n"),
    ("M7092", "an internal block out of the scope: the block of a private address has no dossier (DOS3b)",
     DOSSIER,
     '        return ("", "") if public else (BLOCAGE, action)\n',
     '        return "", ""\n'),
    ("M7093", "the retention without waiting for the unblock: a block's dossier removed 30 days after its "
     "first pass, the block still held (DOS3b)", DOSSIER,
     "                kept = dossier_block.held(doc, blocks)\n",
     "                kept = False\n"),
    ("M7094", "an unreadable address said public: its block has no dossier at all, in silence (DOS3b)", BLOCK,
     '        return ILLISIBLE, f"ni une adresse IPv4 ni une adresse IPv6 : {text[:80]!r}"\n',
     '        return PUBLIQUE, ""\n'),
]
TESTS = {
    "M7091": f"{_T}::test_a_public_address_is_public {_T}::test_a_block_of_a_public_address_has_no_dossier",
    "M7092": f"{_T}::test_a_block_of_a_private_address_is_composed",
    "M7093": f"{_T}::test_a_block_still_held_is_never_removed",
    "M7094": f"{_T}::test_an_address_that_cannot_be_read_is_neither_internal_nor_public "
             f"{_T}::test_an_unreadable_address_is_neither_composed_nor_lost",
}
