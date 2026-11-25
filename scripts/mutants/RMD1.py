"""RMD1 (#1171): a Discord script never writes on an argument it does not know — roadmap_discord.py
read by argparse, --help and an unknown argument stopped before GitHub and Discord, every
scripts/*_discord.py run as the command line runs it (tests/unit/test_discord_args.py). M7526–M7530."""
ROADMAP = "scripts/roadmap_discord.py"
NOTIFY = "scripts/notify_discord.py"
_GUARD = "tests/unit/test_discord_args.py"
_TESTS = f"{_GUARD} tests/unit/test_roadmap_discord.py"

MUTANTS = [
    ("M7526", "the arguments looked through by hand again: --help (and any other) rewrites #roadmap for real, "
     "the bug of 24/11 (RMD1)", ROADMAP,
     "    dry = parse(argv).dry_run\n",
     '    dry = "--dry-run" in (sys.argv[1:] if argv is None else argv)\n'),
    ("M7527", "an argument roadmap_discord does not know ignored: the run goes on and writes (RMD1)", ROADMAP,
     "    return ap.parse_args(argv)\n",
     "    return ap.parse_known_args(argv)[0]\n"),
    ("M7528", "--dry-run lost: a dry run writes #roadmap and #lots (RMD1)", ROADMAP,
     "    dry = parse(argv).dry_run\n",
     "    dry = parse(argv) and False\n"),
    ("M7529", "the command line never read: main() alone parses, `roadmap_discord.py --help` writes (RMD1)",
     ROADMAP,
     "    return ap.parse_args(argv)\n",
     "    return ap.parse_args(argv or [])\n"),
    ("M7530", "notify_discord's command line never read: `notify_discord.py --help` runs the check, which "
     "reads the forum (RMD1)", NOTIFY,
     "    a = ap.parse_args(argv)\n",
     '    a = ap.parse_args(argv or ["check"])\n'),
]
TESTS = {m[0]: _TESTS for m in MUTANTS}
