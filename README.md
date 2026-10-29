# quality-gate: does a GTM skill still give the same answers on a different model?

A team picks a Claude skill for signal scoring, tunes it on one model, then moves to a cheaper model or a newer version. This gate measures what changes when they do. It runs one skill on real job posts with several models, compares every answer with hand labels and with the skill's own rules, and reports which model changes stay inside the run-to-run noise.

The skill under test is `intent-signals` from Kenny's [gtm-flywheel](https://github.com/kenny589/gtm-flywheel) (MIT, vendored unedited; see `evals/skills/SOURCE.md`). The posts are open sales roles at funded B2B tech companies, collected from their public Ashby, Greenhouse and Lever boards.

**Limits, up front:**
- **One labeller.** All 318 hand labels are mine, made against a written guide (`evals/labelling/guide.md`). The guide's blind re-label (Cohen's kappa ≥ 0.80) has **not** been done, so label reliability is unmeasured. Every macro-F1 below is "agreement with one person's labels".
- **Few "no" posts.** The natural sample is 200 sales-ish posts, of which I labelled 187 as signals. Macro-F1 averages the yes and no classes, so a handful of no-posts moves it a lot. The flip rate (how often two models give different answers) does not depend on the labels and is the steadier number.
- **Small Opus subset.** Opus ran on 50 posts, 27 of them recent.
- **One skill, one prompt, the CLI's default effort**, Claude Code 2.1.302 headless on a Pro plan, Windows 10. Costs are Claude Code's list-price estimates, not a bill.

## What it found (runs 2026-10-27 to 10-29)

**1. The skill's recency rule splits the models, and 41% of the "sales hiring" posts were old.** Of 824 sales posts at 118 companies, 335 (41%) had been up for more than 90 days when collected. The skill says recency "trumps everything". On the 81 old posts I labelled as signals, Sonnet 5.5 said "not a signal" on 27; Haiku 5.5 on 2. My labels ignore age on purpose (the guide labels what a post is, not when it was posted), so on the full sample Sonnet looks far worse than Haiku (macro-F1 0.55 vs 0.77). On posts at most 90 days old, the gap closes (0.68 vs 0.73) and the two models change only 3 of 115 answers. The gate now reports every population both ways.

**2. Haiku 4.5 disagrees with itself on ambiguous roles; Haiku 5.5 much less.** On recent Account Manager, CSM and Solutions Engineer posts, running Haiku 4.5 twice on the same input changed 22 of 53 answers (41.5%). Haiku 5.5 changed 7 of 54 (13%), Sonnet 5.5 6 of 54 (11%). Upgrading 4.5 to 5.5 changed 18 of 54 answers (33%), and agreement with my labels rose (macro-F1 0.55 to 0.75). The gate marks that upgrade PASS, but only because its threshold is set by the noisier model's own noise (41.5 + 5 points). A baseline that noisy lets almost anything pass; read the upgrade as "5.5 is steadier", not "nothing changed". On clear sales roles the upgrade changed 8% of answers (9/114).

**3. Repeating the same run is not free of noise either.** Sonnet 5.5 gave a different yes/no on 17% of the natural sample between two identical runs; 30 of those 34 changes were on posts more than 90 days old. On recent posts it was 3.5%. Each threshold is set from noise measured like this, never from a fixed number.

**4. On recent posts, Haiku 5.5 matched Opus 5.5.** On the 27 recent Opus-subset posts, the two changed 0 answers. Opus to Sonnet changed 2 and failed the F1 threshold, but with 3 "no" posts in that set I would not lean on it.

**5. Sonnet to Haiku on recent ambiguous roles sits right on the line.** 10 of 54 answers changed (18.5%) against a threshold of 18.0 points: a FAIL by half a point. On 54 posts that is one answer either way.

Full verdicts, metrics and per-run rule checks: `evals/results/part-a/summary.md`, `metrics.json`, `checks.csv`.

## Part B: cold-email drafts against Kenny's copy checklist

Sonnet 5.5 wrote one sample draft per gift account (34) with Kenny's `copy-frameworks` skill and Frontal's own site wording. Each was checked in code against the skill's Copy QA Checklist (`evals/results/part-b/summary.md`):

- Reading level was the rule broken most: 19 of 34 drafts were above grade 5-7 (Flesch-Kincaid). Length failed 2 (25 more were over 120 words but under the 150 maximum), subject 1. CTA, spam words, merge fields and the first-line signal check (a heuristic) failed none.
- **What went wrong first, and the fix.** The first 34 drafts had no sign-off instruction. 15 were signed with my own first name, which Claude Code had from my account, and 12 as "Frontal". So samples read as if a real person had sent them. The prompt now fixes `{{firstName}}` and `{{senderName}}`, and a `sign_off` check (this eval's rule, not Kenny's) fails any draft that signs with a name. The first run is kept in `evals/results/drafts/drafts-v1-before-sign-off-fix.jsonl` and `part-b-v1-before-sign-off-fix/`.
- No draft was sent. Frontal did not ask for or review them.

## The gift: accounts to email this week

`evals/results/gift/gift.html` lists the companies whose open sales role was a hand-labelled signal, posted 14 days or less before collection (Oct 22-23), one row per company, ranked by the skill's Sonnet 5.5 score. Each row has a why-now line quoting the post itself and the results of every check. No person names or contact data. On 2026-10-29, every listed job was still open, checked against each board's own API.

## How it works

1. **Collect** (`scripts/`, `quality_gate.collector`): public ATS list endpoints, a title filter (`config/title_filter.toml`) that keeps sales-ish roles and marks ambiguous ones.
2. **Sample** (`python -m quality_gate sample`): a natural sample of 200, an ambiguous-role subset of 80 and an Opus subset of 50, from fixed seeds.
3. **Run** (`python -m quality_gate run --arm <arm> --repeats 2`): `claude -p` headless, the skill appended to the system prompt, structured output against a JSON schema, no tools, one turn. Every run records the model that actually answered. Claude Code also makes a small background Haiku call on every run, so the gate judges by the answering model, not by every model in `modelUsage`.
4. **Gate** (`python -m quality_gate gate`): per population, arm and repeat: macro-F1 against hand labels, flip rates between repeats and between arms, and rule checks (evidence quoted from the post, score arithmetic, recency band against the post date, tier against the score). A model change fails if F1 drops by more than max(2 × repeat noise, 3 points) or the flip rate exceeds repeat noise + 5 points.
5. **Gift** (`python -m quality_gate gift`): as above.

Runs pause on their own at 80% of the plan's 5-hour window or 70% of the weekly limit, read from Claude Code's `rate_limit_event`. They stop if a run reports billing overage. A run where Claude Code never started (Windows `0xC0000142` after sleep) is skipped and retried, never recorded as a model failure.

## Cost

1,768 recorded signal runs, about $57 at list price (Sonnet 5.5 $29.68, Haiku 4.5 $20.61, Opus 5.5 $4.95, Haiku 5.5 $1.79), plus 34 drafts ($1.19), on a Pro plan inside its limits. 8 runs failed (`error_max_turns`): 1 Sonnet, 7 Haiku 4.5. They are counted as failures, not dropped.

## Run it

Requires Python 3.11+ and Claude Code logged in to a Claude plan. API-key environment variables are removed before each call so a run cannot bill an API account.

```bash
pip install -e .
python -m pytest -q                       # offline, no model calls
python -m quality_gate gate --help
```

The collected posts are not in this repo (they hold full job-post text), so the gate can't be re-run from a clone as is. The run logs are (`evals/results/runs/runs.jsonl`, `evals/results/drafts/`), with the hand labels (`evals/fixtures/labels_pass1.csv`) and every results file, so each metric can be recomputed from them. The planning spec is in `docs/spec.md`.

## License

MIT. The vendored skills keep their own MIT licence (Copyright (c) 2026 ColdIQ).
