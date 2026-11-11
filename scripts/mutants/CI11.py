"""CI11: the jobs that install Terraform from HashiCorp's apt repository refresh that source alone, so an
outage of Ubuntu's mirrors (11/11: security.ubuntu.com unresolved for hours) no longer fails them. M4814
and M4815, measured by tests/unit/test_workflows.py."""
CI = ".github/workflows/ci.yml"
CANARY = ".github/workflows/canary-azurerm.yml"
_WF = "tests/unit/test_workflows.py"
_LIMITED = ("            -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/hashicorp.list \\\n"
            "            -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0\n")
_EVERY = "            -o APT::Get::List-Cleanup=0\n"

MUTANTS = [
    ("M4814", "CI's Terraform job refreshes every apt source again: an outage of Ubuntu's mirrors fails it "
     "(CI11)", CI, _LIMITED, _EVERY),
    ("M4815", "the canary's Terraform job refreshes every apt source again: an outage of Ubuntu's mirrors "
     "fails the canary (CI11)", CANARY, _LIMITED, _EVERY),
]
TESTS = {
    "M4814": f"{_WF}::test_the_jobs_that_install_terraform_refresh_hashicorp_s_source_alone",
    "M4815": f"{_WF}::test_the_jobs_that_install_terraform_refresh_hashicorp_s_source_alone",
}
