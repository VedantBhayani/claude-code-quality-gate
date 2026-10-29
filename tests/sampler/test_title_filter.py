import pytest

from quality_gate.config import load_config
from quality_gate.sampler import classify_title


@pytest.fixture
def rules(package_root):
    return load_config(package_root).title_filter()


@pytest.mark.parametrize("title", [
    "Sales Development Representative",
    "SDR, EMEA",
    "BDR",
    "Account Executive, Mid-Market",
    "Enterprise Sales Manager",
    "Revenue Lead",
    "GTM Lead",
    "Head of Sales",
    "VP of Revenue",
    "Director of Growth",
    "Chief Revenue Officer",
])
def test_core_sales_titles_are_sales_ish_and_not_ambiguous(rules, title):
    assert classify_title(title, rules) == (True, None)


@pytest.mark.parametrize("title, family", [
    ("Sales Engineer", "solutions_engineer"),
    ("Solutions Consultant", "solutions_engineer"),
    ("Senior Account Manager", "account_manager"),
    ("Customer Success Manager", "csm"),
    ("Partnerships Lead", "partnerships"),
    ("RevOps Manager", "revops"),
    ("GTM Engineer", "revops"),
])
def test_ambiguous_roles_are_sales_ish_with_their_family(rules, title, family):
    assert classify_title(title, rules) == (True, family)


@pytest.mark.parametrize("title", [
    "Software Engineer",
    "Senior Data Engineer",
    "Engineering Manager, Payments",
    "Product Designer",
    "Finance Manager",
    "Revenue Accountant",
    "Salesforce Developer",
    "Growth Marketing Manager",
    "Partner Marketing Manager",
    "Sales Recruiter",
    "Legal Counsel, Commercial",
    "",
])
def test_engineering_design_finance_and_other_titles_are_out(rules, title):
    assert classify_title(title, rules) == (False, None)
