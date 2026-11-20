"""DOC7 (#989; tenth review pass, question C): the docs draw the graph the code wires. M6825."""
MUTANTS = [
    ("M6825", "docs/architecture.md draws the graph without confirm_facts again (DOC7)",
     "docs/architecture.md", '    PD --> CF["confirm_facts"]\n    CF --> INV["investigate"]\n',
     '    PD --> INV["investigate"]\n'),
]
TESTS = {"M6825": "tests/unit/test_agent_nodes.py::test_the_docs_draw_the_nodes_the_graph_wires"}
