"""DOC7 (#989; tenth review pass, question C): the docs draw the graph the code wires. M6825, M6848."""
MUTANTS = [
    ("M6825", "docs/architecture.md draws the graph without confirm_facts again (DOC7)",
     "docs/architecture.md", '    PD --> CF["confirm_facts"]\n    CF --> INV["investigate"]\n',
     '    PD --> INV["investigate"]\n'),
    ("M6848", "docs/architecture.md drops the edge of an action that could not be written to the escalation (DOC7)",
     "docs/architecture.md", '    EX -->|"write_blocked,<br/>action_failed"| ESC\n', ""),
]
TESTS = {"M6825": "tests/unit/test_agent_nodes.py::test_the_docs_draw_the_nodes_the_graph_wires",
         "M6848": "tests/unit/test_agent_nodes.py::test_the_docs_draw_the_nodes_the_graph_wires"}
