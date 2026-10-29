# Hand-labelling guide

> **STATUS: APPROVED 2026-10-26** by the human labeller, with the five open choices accepted as written: marketing roles `not_signal` (E17); pre-sales SE and partner roles with a sourced-revenue quota `ae_hiring` (E4, E6); internships `no` (E10); paid contract SDR `yes` (E11); reposts labelled like the original (E12).

These labels are the reference the gate measures skill outputs against (spec stories 14–19). Words follow `GLOSSARY.md`: a **signal** is an observable, dated change at a company that suggests it may buy now; an **ambiguous role** is a title where it's unclear whether it shows sales investment.

## 1. What you are deciding

For each job post you give two labels:

- **signal**: `yes` or `no`
- **signal type**: one of `sdr_bdr_hiring`, `ae_hiring`, `sales_leadership`, `revops_gtm_eng`, or `not_signal`. `no` always goes with `not_signal`, and `not_signal` only goes with `no`. The tools reject any other pairing.

### Definition: buying signal for a GTM agency selling Frontal's offer

The offer is fixed (`config/facts/offer.md`, verbatim from frontal.so): senior GTM engineers embedded in a **B2B tech** company's team, who build and run **outbound, signal tracking and the sales workflows** in the CRM, with the agency responsible for **qualified pipeline**.

A post is a signal (`yes`) only if all three are true:

1. **It is a real opening at a named B2B company.** The hiring company itself sells to businesses. It is not a staffing agency hiring for an unnamed client, a general "talent pool" ad, or a consumer/retail sales job.
2. **The job's main purpose is new-business revenue or the systems behind it.** Most of the role is one of these: finding and booking new prospects, closing new deals, leading the people who do that, or running the GTM data, CRM, routing and tooling those people use. "Main" means more than half of the responsibilities as written, or the quota as written.
3. **The hire is committed headcount.** A permanent or fixed-term role (full- or part-time, employee or paid contractor). Not an internship, and not a commission-only "independent rep" arrangement.

If any one fails, the label is `no` / `not_signal`.

The test behind the rule: *would a GTM agency selling this offer have a credible, specific reason to contact this company because of this post?* A company paying for outbound, closing or GTM systems headcount is spending on the exact problem Frontal sells against. A company hiring people to keep existing customers happy is not.

### What you do NOT judge

- **Age.** Do not mark a post `no` because it is old. Freshness is measured separately from the collection date (see `GLOSSARY.md`, Freshness window). Label what the post is, not when it was posted.
- **Company fit.** Size, funding, industry within B2B, whether they already use an agency, whether Frontal would win: all out of scope.
- **What the skill would say.** Do not try to predict the model.
- **Seniority inside a type.** A junior AE and an enterprise AE are both `ae_hiring`.

## 2. Signal types

Pick the type from the job's main purpose (the same reading as rule 2), not from the title alone.

| Type | The job is mainly... | Typical titles |
|---|---|---|
| `sdr_bdr_hiring` | Prospecting and qualifying: outbound, inbound qualification, booking meetings for others. Does not own closing. | SDR, BDR, LDR, Sales/Business Development Representative or Associate, Outbound Rep, Inside Sales Rep (prospecting), Appointment Setter |
| `ae_hiring` | Owning and closing new deals, or being the named pre-sales or partner resource on new deals. | Account Executive, Founding AE, Sales Executive, Inside Sales Rep (closing), Sales Engineer (pre-sales), Partner Manager with sourced-revenue quota |
| `sales_leadership` | Managing sellers or owning the sales/revenue number. | SDR/BDR Manager or Team Lead, Sales Manager, Head/Director/VP of Sales, Revenue or Business Development, CRO, GM with a sales mandate |
| `revops_gtm_eng` | Running the systems, data and process behind the sales team. | RevOps, Sales Ops, GTM Engineer, GTM/Sales Systems, CRM (Salesforce/HubSpot) Admin owned by sales, Sales Enablement, lead routing / GTM data ops |
| `not_signal` | Anything that fails rules 1–3. | |

**One post, several roles** (e.g. "SDRs and AEs, multiple openings"): use the role named first in the title. If the title names none (e.g. "Join our sales team"), use the role with the most responsibilities in the text.

**A title that says one thing and a body that says another:** the body wins. A title only decides when the body is missing, unreadable, or generic boilerplate.

## 3. Worked edge cases

Each case gives a typical post, the label, and why. Ambiguous-role families match the sampler's (`scripts/titles.py`): Account Manager, CSM, Solutions Engineer, Partnerships, RevOps.

**E1. Account Manager, expansion of existing accounts only.**
"Own a book of 60 existing customers, drive renewals and upsell, quota on net revenue retention."
→ `no` / `not_signal`. All existing customers. No new-business motion for an outbound agency to serve.

**E2. Account Manager with a new-logo quota.**
"Account Manager, SMB. 70% of your quota is net-new logos; prospect into your territory."
→ `yes` / `ae_hiring`. The body says most of the job is closing new business (rule 2). Body beats title.

**E3. Customer Success Manager, even with expansion targets.**
"CSM: onboarding, adoption, QBRs, identify expansion opportunities and hand them to Sales."
→ `no` / `not_signal`. Retention role. "Identify expansion" is a minor duty and stays inside the installed base. Only label a CSM `yes` if the body puts most of the quota on new logos (then it's E2: `ae_hiring`). That's rare.

**E4. Solutions Engineer / Sales Engineer, pre-sales.**
"Partner with Account Executives on discovery and demos for new prospects, own technical win."
→ `yes` / `ae_hiring`. Closing capacity for new deals: the company is scaling new-business sales.

**E5. Solutions Engineer, post-sales.**
"Solutions Engineer: implementation, integrations and technical support for live customers."
→ `no` / `not_signal`. Post-sale delivery, despite the same title as E4. Also `no`: Solutions Architect in a professional-services team, Support Engineer, Implementation Consultant.

**E6. Partnerships with a sourced-pipeline number.**
"Partner Manager: recruit resellers and agencies, owns partner-sourced pipeline target of $2M."
→ `yes` / `ae_hiring`. A revenue target met through partners is still new pipeline. If the role manages the partner team or the whole channel number, it's `sales_leadership`.

**E7. Partnerships with no revenue number.**
"Strategic Alliances Manager: manage our technology integrations and co-marketing with platform partners."
→ `no` / `not_signal`. Product or marketing partnerships, not a pipeline motion.

**E8. RevOps / Sales Ops / GTM Engineer.**
"RevOps Analyst: own Salesforce hygiene, lead routing, pipeline reporting, outbound tooling (Clay, Outreach)."
→ `yes` / `revops_gtm_eng`. This is the work in Frontal's offer (signal tracking, sales workflows in the CRM). It's the most direct signal of the five types.

**E9. Sales-adjacent ops: draw the line at the sales team's systems.**
- Sales Enablement Manager (training, playbooks and tooling for reps) → `yes` / `revops_gtm_eng`.
- Marketing Ops that owns CRM lead routing and handoff to SDRs → `yes` / `revops_gtm_eng`.
- Marketing Ops for email campaigns or the website only → `no` / `not_signal`.
- Deal Desk, order management, billing or contracts ops → `no` / `not_signal`. These are back-office steps after the deal, not pipeline.
- Salesforce Developer in IT/engineering building internal apps → `no` / `not_signal`.

**E10. Internships and graduate programmes.**
"Sales Development Intern (summer, 12 weeks)" → `no` / `not_signal`. Fails rule 3: no committed headcount.
"Associate SDR (graduate, full-time, permanent)" → `yes` / `sdr_bdr_hiring`. Entry level, but a real hire.

**E11. Contract roles.**
- "Contract SDR, 6 months, paid day rate" → `yes` / `sdr_bdr_hiring`. The company is buying outbound capacity, the same problem an agency sells against.
- "Fractional Head of Sales, 2 days/week" → `yes` / `sales_leadership`.
- "Independent Sales Agent, commission-only, 1099" → `no` / `not_signal`. No spend committed (rule 3).
- A recruiter or staffing firm posting "AE for a stealth SaaS client" → `no` / `not_signal`. The buying company is not named (rule 1).

**E12. Reposts and evergreen posts.**
- The same role re-posted with a new date, or one of three near-identical posts → label each copy on its content, normally the same as the original (`yes` + type). Do not mark a copy `no` because it's a duplicate. De-duplication and freshness are handled elsewhere.
- "General application: Sales" / "Join our talent community" with no specific opening → `no` / `not_signal`. Fails rule 1: there's no real opening.

**E13. Non-English posts.**
Apply the same rules. You may translate the text yourself with any tool you trust. Pasting posts into outside tools is your call, since the text is public. If you still can't tell the main purpose, decide from the title using the table in section 2, and add the note `lang`. Examples: "Vertriebsmitarbeiter Neukundengewinnung (m/w/d)" (sales rep, new-customer acquisition) → `yes` / `ae_hiring`. "Chargé(e) de clientèle" (customer account handler, existing clients) → `no` / `not_signal` unless the body says new business.

**E14. Consumer and retail sales.**
"Retail Sales Associate", "Car Sales Executive", "Inside Sales, home solar for homeowners" → `no` / `not_signal`. Fails rule 1: the buyer is a consumer and Frontal sells to B2B tech.

**E15. Business Development that is really partnerships or strategy.**
"Business Development Manager: corporate development, M&A scouting, strategic deals" → `no` / `not_signal`. "Business Development Rep: outbound to mid-market prospects, book meetings for AEs" → `yes` / `sdr_bdr_hiring`. Read the body: "BD" means either.

**E16. Renewals AE.**
"Account Executive, Renewals" → `no` / `not_signal`. Same as E1. Retention despite the AE title.

**E17. Head of Growth.**
Owns the sales team or outbound targets → `yes` / `sales_leadership`. Marketing-only (paid, SEO, lifecycle) → `no` / `not_signal`. In this gate, marketing roles are `not_signal` because none of the four signal types covers them.

**E18. Founding / first sales hire.**
"Founding Account Executive, first sales hire" → `yes` / `ae_hiring`. This is often the strongest signal, but the type stays `ae_hiring`. Strength is not a label here.

**When unsure after about a minute:** apply rules 1–3 to the title alone with the section 2 table, label it, and add the note `unsure`. Don't skip it, and don't come back later. The disputed-case step (section 6) is where hard calls get revisited.

## 4. Time budget (about 5 hours in total)

| Step | Posts | Pace | Time |
|---|---|---|---|
| Read this guide, approve it, label 10 practice posts and throw them away | 10 | | 25 min |
| Pass 1: natural sample (target 200) + ambiguous subset (target 60–80) | ~280 | ~45 s | ~3 h 30 min |
| Blind re-label, at least 3 days after pass 1 | 50 | ~45 s | ~40 min |
| Disputed items only, if kappa < 0.80 (Resolution 7) | ≤ 15 | ~60 s | ≤ 15 min |
| **Total** | | | **~4 h 50 min** |

Actual sample sizes are a FACT set by the day-1 pilot. If they come out bigger, the pace stays the same and the budget grows with them, so say so in the README.

To keep the pace at ~45 s: read the title, then the "What you'll do" or responsibilities block and the quota line if there is one. Skip benefits and the company boilerplate. Work in sittings of at most 60 minutes with a break, because tiredness changes labels.

## 5. Tools

From `builds/quality-gate` (with `src` on `PYTHONPATH`, or after `pip install -e .`). Sheets and post caches are local files under `data/`, which is gitignored. The sheet holds URL, company, title, dates and labels only. Post text stays in the local posts JSONL and is shown in the terminal, never written to a sheet.

```
python -m quality_gate.labels export   --posts <posts.jsonl> --out <pass1.csv>
python -m quality_gate.labels label    --posts <posts.jsonl> --sheet <pass1.csv>
python -m quality_gate.labels validate --posts <posts.jsonl> --sheet <pass1.csv>
```

- `label` shows one unlabelled post at a time. Answer `y` or `n`. After `y`, pick the type: `1` sdr_bdr_hiring, `2` ae_hiring, `3` sales_leadership, `4` revops_gtm_eng. Any text after the answer, separated by a space, is saved as a note (e.g. `n lang`, `2 unsure`). `q`, Ctrl-D or Ctrl-Z quits. Every label is saved as soon as you give it, so re-running `label` resumes where you stopped.
- You can also fill the CSV in a spreadsheet: `signal` = yes/no, `signal_type` as above, `labelled_on` = YYYY-MM-DD. `validate` checks that every expected post appears exactly once with a valid pairing.

## 6. Blind re-label and agreement

```
python -m quality_gate.labels draw-relabel --posts <posts.jsonl> --pass1 <pass1.csv> --out <relabel.csv>
python -m quality_gate.labels label --posts <posts.jsonl> --sheet <relabel.csv> --blind
python -m quality_gate.labels validate --expected <relabel.csv> --sheet <relabel.csv>
```

- `draw-relabel` refuses unless pass 1 is complete and valid, and at least **3 days** have passed since the latest pass-1 `labelled_on` date. It draws 50 posts with a fixed seed into a blank sheet in random order. Pass-1 labels are not copied.
- `--blind` never shows prior labels. During the blind pass, do not open the pass-1 sheet or your notes. Re-read this guide first: the guide is allowed, your earlier answers are not.
- Agreement is Cohen's kappa on the yes/no label. The gate needs ≥ 0.80. Kappa on signal type is reported but not gated (Resolution 6). If kappa < 0.80: change this guide only for the cases you disagreed with yourself on, re-label only those items once, and recompute. If it's still below 0.80, publish with the low kappa disclosed (Resolution 7). Log any guide change at the bottom of this file with its date.

## Change log

- 2026-10-22: first draft. Awaiting approval.
- 2026-10-26: approved by the labeller; no rule changed.
