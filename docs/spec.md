> Planning spec for this build, written with Claude Code before the build started and kept as written. References to tickets, "research NN" notes and `.scratch/` paths point to private planning notes that are not in this repo. Where the build differs from this spec (for example the 90-day population and the sign_off check), the README and code comments say so.

# Spec: Build 2, the signal + draft quality gate

Status: ready-for-agent

Source decisions: `.scratch/frontal-hire/issues/07-lock-build2-spec.md` (locked 2026-10-22), with supporting facts from `.scratch/frontal-hire/map.md` and research notes 02, 04 and 05 in `.scratch/frontal-hire/research/`. Vocabulary follows `GLOSSARY.md`. Nothing here adds a decision that isn't in those sources. Anything not decided is listed under **Open questions**.

## Problem Statement

Frontal runs Kenny's public `kenny589/gtm-flywheel` skills (MIT) to score buying signals and write cold email. They route work to the cheapest model that is good enough. Nobody can currently say whether a model switch (e.g. Haiku vs Sonnet) or a model upgrade changes which companies get flagged as signals, how they get scored, or whether the drafts pass Kenny's own copy rules. The skills are prompt-only markdown with no tests, so a change of model is an unmeasured risk. Their freshness windows also differ from file to file, so which window gets applied depends on which file was loaded.

The user (a candidate pitching Frontal for a paid GTM engineering internship) needs a method that measures this on real data and produces numbers anyone can reproduce. It also has to produce a useful gift: 50 accounts Frontal should email this week.

## Solution

A quality gate, published in the user's own public repo, that:

1. Collects real sales-ish job posts from about 80 Frontal-ICP companies via the public Greenhouse, Lever and Ashby job-board endpoints, and records the collection date for every post.
2. Runs Kenny's `signal-scoring` skill on each post, one post per run, with the collection date and Frontal's offer (in Frontal's own site wording), on several models via headless `claude -p` on the user's Claude Pro plan.
3. Checks every output: against hand labels, between models (flip rate), between two runs of the same model (repeat noise), and against the skill's own deterministic rules (evidence exists in the post, the score matches the formula, recency matches dates, the tier matches the score).
4. Checks a small set of `copy-frameworks` drafts in code against Kenny's copy QA checklist (Part B).
5. Outputs the gift: a CSV and one HTML page listing 50 accounts with a short "why now" line, the skill's score and tier, and our check results. Company-level only.
6. Ships a small PR to Kenny's repo (the copy checklist as one checker, one fixture, and a link). The pitch must not depend on it being merged.

Framing: "a method you can point at your own setup, shown on your public skills."

## User Stories

### Data collection

1. As the gate operator, I want to fetch every published job from a company's Greenhouse, Lever or Ashby board in one list call, so that collection stays to about one request per company.
2. As the gate operator, I want each fetched post stamped with its collection date, so that a signal's age is always measured from the day it was fetched.
3. As the gate operator, I want the post date taken from Greenhouse `first_published`, Ashby `publishedAt` and Lever `createdAt`, so that freshness isn't skewed by edits (`updated_at`).
4. As the gate operator, I want Ashby jobs with `isListed=false` dropped, so that only publicly listed posts are used.
5. As the gate operator, I want Greenhouse's HTML-entity-escaped content unescaped and stripped to plain text, so that the model and the evidence checker see the same text.
6. As the gate operator, I want fetches done politely (one list call per company, about a 1 s delay, a descriptive User-Agent, an on-disk cache), so that collection isn't bulk scraping and can be re-run offline.
7. As the gate operator, I want board tokens resolved and checked against the returned company name, so that a same-slug wrong company doesn't get into the sample.
8. As the gate operator, I want recruiter names or emails in post text redacted before anything leaves my machine, so that no personal data gets published.
9. As the gate operator, I want full post text stored only locally, so that employers' copyrighted descriptions are never republished.

### Sampling

10. As the gate operator, I want a natural random sample of sales-ish posts (target about 200), so that the headline numbers describe what the skill really sees.
11. As the gate operator, I want a separately reported ambiguous-role subset (Account Manager, CSM, Solutions Engineer, Partnerships, RevOps; target 60–80), so that hard cases are measured without skewing the headline numbers.
12. As the gate operator, I want the final sample sizes set from the day-1 pilot, so that the run count fits within Pro limits.
13. As a reader of the results, I want the natural sample and the ambiguous subset reported separately, so that I can tell the typical behaviour apart from the edge cases.

### Hand labelling

14. As the labeller, I want a labelling guide written before I label anything, with worked edge cases, so that my labels are consistent.
15. As the labeller, I want to label each post as a buying signal for a GTM agency (yes/no), so that the skill's decisions can be compared with mine.
16. As the labeller, I want to label each post's signal type as one of `sdr_bdr_hiring`, `ae_hiring`, `sales_leadership`, `revops_gtm_eng`, `not_signal`, so that type agreement can be measured.
17. As the labeller, I want to blind re-label 50 posts at least 3 days after the first pass, so that my own consistency is measured.
18. As a reader of the results, I want the re-label agreement score reported and required to reach 0.80, so that I can trust the hand labels as a reference.
19. As the labeller, I want the whole labelling job to fit in about 5 hours, so that it's realistic alongside the build.

### Running the skill

20. As the gate operator, I want each run to get exactly one post, the collection date and Frontal's offer, so that runs are independent and comparable.
21. As the gate operator, I want the skill's SKILL.md injected with `--append-system-prompt-file` and the output constrained by a JSON schema, so that every model gets the same instructions and returns parseable output.
22. As the gate operator, I want to run Haiku 5.5 and Sonnet 5.5 twice each on every post, so that I can measure both flip rate (between models) and repeat noise (within a model).
23. As the gate operator, I want Opus 5.5 run on a 50-post subset as just another model, so that a third comparison point exists without treating Opus as the truth.
24. As the gate operator, I want an old-vs-new Haiku comparison if Pro can still run the older Haiku, so that a real model upgrade can be measured alongside the model switch.
25. As the gate operator, I want full model IDs pinned (not aliases), plus the CLI version, skill file hash and model per run recorded, so that every number can be reproduced.
26. As the gate operator, I want a day-1 pilot of 20 runs per model that reads the 5-hour and weekly usage before and after, so that I know the per-run cost against Pro limits.
27. As the gate operator, I want runs to stop on a rate-limit and resume after the reset, with usage credits left off, so that a runaway loop can never spend money.
28. As the gate operator, I want runs to be cheap and isolated (no tools, few turns, no session persistence, an empty working directory, no fallback model), so that nothing other than the model differs between arms.
29. As the gate operator, I want a run with no valid structured output recorded as a failure rather than dropped, so that failure rates are visible per model.

### Checks (Part A)

30. As a reader, I want each run's signal yes/no and signal type compared with the hand labels, so that I can see accuracy per model.
31. As a reader, I want the flip rate between Haiku and Sonnet (and against the Opus subset), so that I can see how much a model switch changes decisions.
32. As a reader, I want the old-vs-new Haiku flip rate reported as a model upgrade (if measured), so that it isn't confused with a model switch.
33. As a reader, I want repeat noise within each model, so that I can tell real model-switch differences apart from run-to-run randomness.
34. As a reader, I want a check that every evidence quote the model gives actually appears in the post, so that invented evidence is caught.
35. As a reader, I want a check that the stated score out of 50 equals `Recency×3 + Directness×3 + Frequency×2 + Specificity×1 + Source×1` from the model's own factor ratings, so that arithmetic errors are caught.
36. As a reader, I want a check that the recency rating matches the post date vs the collection date under the skill file's bands, so that wrong freshness calls are caught.
37. As a reader, I want a check that the tier matches the score (40+ Critical, 30–39 High, 20–29 Medium, 10–19 Low, under 10 Noise), so that tiering errors are caught.
38. As a reader, I want each run judged only against the rules in the file it was given, so that the gate is fair to the skill.
39. As a reader, I want the conflicting freshness windows across Kenny's files reported separately as a documentation finding, framed as "the windows differ across files, so here's a single one to pin," so that it's useful and not an attack.
40. As a reader, I want arithmetic errors reported but not made the headline, so that the headline stays on decision quality.

### Copy checks (Part B)

41. As the gate operator, I want about 60 drafts generated with `copy-frameworks` using only Frontal's site offer wording (no numbers, no claims about Frontal), so that no claims are invented for Frontal.
42. As a reader, I want each draft checked in code against Kenny's copy QA checklist (subject 3–5 words, lowercase, no brackets, no `!`, no emoji; under 120 words, 150 maximum; exactly one CTA that is a question and not "book a call"; every `{{variable}}` resolved; no spam words such as free, guarantee, act now, limited time; plus the remaining checklist items where they can be checked in code), so that rule breaks are found automatically.
43. As a reader, I want the drafts clearly labelled as samples, so that nobody mistakes them for emails sent as or for Frontal.

### The gift

44. As Frontal, I want 50 accounts we should email this week, so that the work is useful to us right away.
45. As Frontal, I want each account to show company, domain, role title, post URL, posted date, collection date, signal type, a "why now" line of 20 words or fewer taken from the evidence, the skill's score and tier, and the gate's check results, so that I can act on it and judge how far to trust each row.
46. As Frontal, I want the gift as a CSV plus one HTML page, so that I can import it or just read it.
47. As anyone, I want no person names or contact data in the gift, so that it stays company-level only.

### Publishing

48. As a reviewer, I want a public repo with fixtures (URLs + labels only, no post text), schemas, checkers, the runner, results and a README, so that I can reproduce every number.
49. As a reviewer, I want the README's first screen to state the limits, so that I know what the numbers do and don't show before reading on.
50. As Kenny, I want a small PR to `kenny589/gtm-flywheel` containing the copy checklist as one checker, one fixture and a link, so that my repo gains a test without a large review burden.
51. As the user, I want the pitch to stand on its own whether or not the PR is merged, so that it doesn't depend on Kenny's response.
52. As a reader, I want results written using "model switch" for Haiku vs Sonnet and "model upgrade" only for a version change of the same model, never "drift", so that the terms stay precise.

## Implementation Decisions

### Modules

- **Collector**: one adapter per ATS (Greenhouse, Lever global/EU, Ashby) behind a single interface: given a board token, return normalised posts (company, title, URL, post date, plain text) plus the collection date. Handles unescaping, `isListed`, token probe (200/404) and company-name check, caching, delay and User-Agent. Redacts personal data from text.
- **Sampler**: builds the natural random sample of sales-ish posts and the separate ambiguous-role subset from collected posts. Sizes are parameters set after the pilot.
- **Fixture store**: what gets published. Post URL, metadata and hand labels (signal yes/no, signal type), no post text. Text lives only in the local cache and is re-fetchable from the URL list.
- **Runner**: for each (post, model, repeat) builds one `claude -p` call. The call has the pinned model ID, the SKILL.md via `--append-system-prompt-file`, our JSON output schema, and a prompt holding one post, its collection date and Frontal's offer wording. It records the structured output (or the failure), model ID from `system/init`, CLI version, skill file hash, effort, cost estimate. Runs sequentially (2-way parallel at most) and stops on rate-limit until `resets_at`. Never uses `--bare`, `--fallback-model` or usage credits. The model invocation sits behind one interface so the rest of the gate can run on recorded outputs.
- **Output schema (signal scoring)**: JSON schema covering at minimum the fields the checks need: signal yes/no, signal type, evidence quote(s), the five factor ratings, total score, recency rating, tier, action. Exact field names are an implementation detail.
- **Checkers**: pure functions over (run output, post, rules from the given skill file), each returning pass/fail with a reason:
  - label match (vs hand labels)
  - evidence exists in post text
  - score equals the formula
  - recency rating matches post date vs collection date under the given file's bands (High = last 7 days, Medium = 30 days, Low = 30–90 days for `intent-signals`)
  - tier matches score
  - Each run is judged only against the rules in the file it was given.
- **Comparison metrics**: flip rate between models (and between Haiku versions if available, reported as a model upgrade), repeat noise within each model, accuracy vs hand labels, label-agreement score for the 50-post re-label. Reported separately for the natural sample and the ambiguous subset.
- **Copy checker (Part B)**: deterministic checks of a draft against Kenny's copy QA checklist. This is the same unit that goes into the PR to Kenny's repo.
- **Gift builder**: selects 50 accounts and writes the CSV and the HTML page with the locked fields. The "why now" line is 20 words or fewer and is taken from the evidence. No person names or contact data.
- **Report / README**: results, limits on the first screen, the freshness-window documentation finding as a separate section.

### Ordering and run setup

- Deterministic checks run in code. Model judgement is only what the skill produces. The gate itself uses no LLM judge.
- Day-1 pilot of 20 runs per model (Haiku, Sonnet, Opus) measures % of the 5-hour and weekly limits per run. Sample sizes and the Opus subset are fixed from that. Budget rule from research 02: total eval usage at or under 60–70% of the weekly limit, and at or under about 80% of any 5-hour window.
- Cheap, isolated runs per research 02: no tools, one or two max turns, no session persistence, empty working directory, the same effort level on every arm, and any `model:` frontmatter stripped from the injected skill.
- Gate thresholds are set from the repeat noise measured in the pilot, not picked in advance.

### Artifacts

- The user's own public repo is the main artifact: fixtures (URLs + labels only), schemas, checkers, runner, results, README with limits on the first screen.
- PR to `kenny589/gtm-flywheel`: the copy checklist as one checker, one fixture, and a link to the main repo. Keep the MIT licence on anything copied.

### Standing rules (from the map)

- Real data only for any quality claim. Every number measured and reproducible.
- Publish only company name, posting URL, title, date, labels and at most a short evidence quote. Never a dump of descriptions.
- Never quote Alex's numbers back to him. Never publish anything written "as Alex". Drafts use only Frontal's site offer wording.
- No personal contact data in any deliverable.

## Testing Decisions

- Good tests check external behaviour only: given inputs (a post, a run output, a skill's rules), the gate returns the right check results and metrics. They don't assert on internal structure.
- **Proposed seam (one, at the highest point):** the gate takes recorded run outputs plus fixtures and returns check results, metrics and the gift. The model call sits behind the runner's invocation interface, so tests feed in recorded or hand-written outputs and never call `claude -p`. Collector adapters are tested against saved API responses (Greenhouse escaped HTML, Lever bare array, Ashby `isListed=false`) without network access. This seam is proposed and not yet confirmed with the user (see Open questions).
- Modules under test: checkers (each rule, with passing and failing cases, including off-by-one at recency band and tier edges), comparison metrics (flip rate, repeat noise, agreement), copy checker (each checklist item), collector normalisation, gift builder (field set, 20-word limit, no personal data).
- Prior art: none. The repo has only one-off Python scripts (`scrape.py`, `merge.py`, `export_text.py`) and a spend-stop spike, with no tests. Kenny's repo has no tests either. Build with `/tdd`.

## Out of Scope

- Validating Signal Finder (private early access).
- A client-boundary / contamination guard, a voice drift grader, a reply-manager eval.
- Fable and 1M-context model variants (usage credits only on Pro).
- Any paid API calls or usage credits.
- Personal contact data (emails, phones, person names) anywhere.
- Sending any email to the 50 accounts, or contacting anyone through this pipeline.
- Publishing post text.
- Build 1 (spend stop) and the pitch package (separate specs).
- Breaking this spec into tickets (`/to-tickets` is a separate step).

## Open questions

These are not decided in the source material. Each needs a decision before or during implementation.

1. **Test seam confirmation**: the to-spec skill asks to check with the user that the proposed seam (recorded run outputs + fixtures in, results out; model call behind one invocation interface) matches expectations. Not yet confirmed.
2. **Sonnet 5.5 full model ID**: not in the docs. Read it from `system/init` of one `--model sonnet` run, then pin it (⚠️ in ticket 07).
3. **Old Haiku on Pro**: can Pro still run the older Haiku version? If not, the model upgrade comparison is dropped (⚠️ in ticket 07). Also, which older version exactly?
4. **Final sample sizes**: natural sample (target ~200) and ambiguous subset (target 60–80) are set by the day-1 pilot.
5. **Gate thresholds**: what the pass/fail thresholds are and how exactly they're derived from measured repeat noise (e.g. which multiple or margin).
6. **Agreement score metric**: which statistic the 0.80 bar uses (raw percent agreement vs Cohen's kappa), and whether it applies to the yes/no label, the signal type, or both.
7. **If re-label agreement is below 0.80**: revise the guide and re-label, or something else?
8. **Opus 50-post subset**: how those 50 are picked (random from the natural sample, or stratified with ambiguous items).
9. **Which signal-scoring file(s) Part A runs**: `intent-signals` is the one with the formula, tiers and recency bands. Does Part A also run `trigger-mapping` and/or `lead-prioritization`, or only `intent-signals`?
10. **Gift selection rule**: how the 50 accounts are chosen and ranked (skill score, hand label, check results, freshness, one row per company?), and which model's output supplies the score and tier shown.
11. **"Why now" generation**: whether the line is a trimmed evidence quote or a rewrite grounded in the evidence, and who/what writes it.
12. **Domain field**: where the company domain comes from (seed list, ATS data, or manual).
13. **Part B inputs**: which prospects/signals the ~60 drafts are built from (e.g. gift accounts), and which model(s) write them.
14. **Part B code-checkable items**: how "reading level grade 5–7" and "first line references a real signal" are checked in code (a readability formula? matching against the evidence?), or whether they're excluded.
15. **Ranking drafts worst-first**: the map says Build 2 "ranks drafts so a person reads the worst 50 first" (10-80-10 fit). Ticket 07 doesn't lock this for Part B. Is it in scope?
16. **Effort level**: which `--effort` setting is used (same on every arm, per research 02).
17. **"Sales-ish" filter**: the exact title rule that defines the natural sample's population.
18. **ICP company count**: ticket 07 says about 80 companies; research 04 planned a seed list of about 120. Which is the target, and what qualification criteria from research 04 apply?
19. **Frontal's offer wording**: the exact site text to pass in every run, and the date it was captured.
20. **Results delivery to Slack**: the map notes "all alerts and results go to Slack". Ticket 07 doesn't include it in Build 2's artifacts. Is it in scope?
21. **Public repo name and licence**.

## Further Notes

- Public framing of the freshness finding: "the windows differ across files, so here's a single one to pin," never "the skills are wrong".
- Post 2 of the public sequence uses Build 2's real numbers plus the 50 accounts.
- Pro publishes no absolute run counts, so every capacity figure in research 02 is an estimate until the pilot replaces it.
- No ATS grants republication rights. The "store locally, publish URLs + labels" stance is a conservative inference.

## Resolutions to open questions (2026-10-22)

Decided by the agent under the user's delegation ("start doing everything") unless marked FACT, which is filled by research or the pilot. Never guessed.

1. **Test seam: confirmed.** Recorded run outputs + fixtures go in, results come out. The model call sits behind one invocation interface, so the checkers and scorer are fully testable offline.
2. **Sonnet 5.5 ID: FACT.** Comes from the model-IDs research (02a), or from `system/init` of the first pilot run. Pin it in config.
3. **Old Haiku on Pro: FACT** (02a). If it's unavailable, drop the model-upgrade comparison and say so in the README.
4. **Sample sizes: FACT** from the day-1 pilot. Targets: 200 natural + 60–80 ambiguous.
5. **Gate thresholds:**
   - Fail if macro-F1 (vs hand labels) drops by more than **max(2× measured repeat noise in F1, 3 points)**.
   - Fail if the flip rate between arms exceeds **measured repeat noise + 5 points**.
   - Both thresholds are computed from the pilot and repeat runs, then written to config with their derivation.
6. **Agreement metric:** Cohen's kappa. **Gate on the yes/no label (≥ 0.80)**; report kappa on signal type, but don't gate on it.
7. **If kappa < 0.80:** revise the guide for the disagreeing cases, re-label only the disputed items once, and recompute. If it's still below 0.80, report it honestly and publish with the low kappa disclosed.
8. **Opus subset:** 50 posts drawn uniformly at random from the natural sample, with a fixed seed.
9. **Part A runs `intent-signals` only.** It's the file with the formula, tiers and recency bands. `trigger-mapping`/`lead-prioritization` are out of scope; their conflicting windows go into the documentation finding.
10. **Gift selection:**
    - Hand label = signal yes.
    - Posted ≤ 14 days before the collection date.
    - One row per company, keeping its freshest qualifying post.
    - Ranked by the Sonnet 5.5 run-1 score, ties broken by recency.
    - The score and tier shown come from Sonnet run 1.
    - Top 50.
11. **"Why now":** a deterministic template, **no model**: `<role title> posted <N> days ago: "<≤12-word evidence quote>"`. Nothing gets made up.
12. **Domain: FACT,** from the seed list (data agent).
13. **Part B inputs:** the 50 gift accounts plus up to 10 more qualifying ones (about 60). One draft each, written by Sonnet 5.5 with `copy-frameworks` + Frontal's offer wording.
14. **Part B checks in code:**
    - Reading level uses the Flesch–Kincaid grade formula, implemented in-repo.
    - "First line references a real signal" is a **heuristic**: the first line must contain the role title or a key term from the evidence. It's reported as a heuristic.
    - Everything else is exact.
15. **Worst-first ranking: in scope.** Sort drafts by number of failed checks, then severity. This is the 10-80-10 demo.
16. **Effort:** the CLI default, recorded and identical on every arm. ⚠️ FACT: confirm the flag/setting exists (02a).
17. **"Sales-ish" filter:** a title regex covering SDR, BDR, Account Executive, Sales, Revenue, RevOps, GTM, Account Manager, Customer Success, Solutions Engineer/Consultant, Partnerships, and Head/VP/Director/Chief of Sales/Revenue/Growth. Excludes engineering/design/finance titles. The exact list is in config. FACT for counts: data agent.
18. **Company count: FACT** from the data agent. Use every qualifying company (expect about 80–120). The criteria are the ones in research 04.
19. **Frontal's offer wording: FACT.** Captured verbatim from frontal.so with a capture date (offer agent).
20. **Slack: out of scope for Build 2.** Results go to the report and the HTML page. Slack belongs to Build 1.
21. **Public repo name and licence:** licence **MIT**. Repo name is the **USER's call** (default proposal: `gtm-skill-quality-gate`). It doesn't block building.
