"""Sales-ish title classifier. Ambiguous families follow spec story 11:
Account Manager, CSM, Solutions Engineer, Partnerships, RevOps."""
import re

EXCLUDE = re.compile(r"salesforce|marketing|\blegal\b|counsel|engineer(ing)? manager|software engineer|"
                     r"data (engineer|scientist)|product manager|designer|recruit|talent|"
                     r"payroll|accountant|accounting|finance manager|tax\b|people partner|hr business partner", re.I)

AMBIGUOUS = [
    ("account_manager", re.compile(r"\baccount manag|\baccount director|\bclient partner|\bkey account|"
                                   r"\bclient (success )?manager|\brelationship manager", re.I)),
    ("csm", re.compile(r"customer success|\bcsm\b|client success", re.I)),
    ("solutions_engineer", re.compile(r"solutions? (engineer|architect|consultant)|sales engineer|pre-?sales|"
                                      r"value engineer", re.I)),
    ("partnerships", re.compile(r"partnership|partner (manager|development|sales|success)|\bchannel\b|alliance", re.I)),
    ("revops", re.compile(r"rev(enue)?\s?ops|revenue operations|sales operations|sales ops|gtm (operations|ops|engineer)|"
                          r"go-to-market (operations|engineer)|sales enablement|deal desk|sales systems|crm (admin|manager)", re.I)),
]

CORE = re.compile(r"account executive|\bae\b|\bsdr\b|\bbdr\b|sales development|business development|"
                  r"\bsales\b|\bseller\b|chief revenue|\bcro\b|head of revenue|\bvp,? revenue|"
                  r"new business|growth representative|commercial (lead|director|manager)", re.I)


# Spec Resolution 17 (aligned with the Build 2 sampler, config/title_filter.toml):
# Head/VP/Director/Chief of Sales/Revenue/Growth, plus any Revenue, RevOps or GTM title.
# Checked before EXCLUDE so these are never dropped; over-inclusion is fine (the sampler re-classifies).
R17 = re.compile(r"\b(head|vp|svp|evp|vice president|director|chief)\b.*\b(sales|revenue|growth)\b|"
                 r"\b(sales|revenue|growth)\b.*\b(head|vp|director|officer)\b|"
                 r"\brevenue\b|\brev\s?ops\b|\bgtm\b|go-to-market|\bcro\b", re.I)


def classify(title):
    """Return (is_sales_ish, ambiguous_family_or_None)."""
    t = title or ""
    for fam, rx in AMBIGUOUS:
        if rx.search(t) and not re.search(r"salesforce", t, re.I):
            # "Sales Engineer"/"Solutions Engineer" is in the ambiguous list; marketing/legal excluded
            if re.search(r"marketing|\blegal\b|counsel", t, re.I):
                return False, None
            return True, fam
    if R17.search(t) and not re.search(r"salesforce", t, re.I):
        return True, None
    if EXCLUDE.search(t):
        return False, None
    if CORE.search(t):
        return True, None
    return False, None
