# Documentation finding: freshness windows

The windows differ across files, so here's a single one to pin.

Which window a run applies depends on which file it was given. Each file is self-consistent for the job it describes; pinning one window just makes runs comparable.

Distinct stale-after windows stated: 14 days, 28 days, 30 days.

## Every window stated

Paths are relative to `evals/skills/`. Quotes are the source line verbatim.

| Source | Applies to | Says | Quoted line |
|---|---|---|---|
| `intent-signals/SKILL.md:98` | all signals | recency band High: up to 7 days | \| **Recency** \| Last 7 days \| Last 30 days \| 30-90 days \| |
| `intent-signals/SKILL.md:98` | all signals | recency band Medium: up to 30 days | \| **Recency** \| Last 7 days \| Last 30 days \| 30-90 days \| |
| `intent-signals/SKILL.md:98` | all signals | recency band Low: up to 90 days | \| **Recency** \| Last 7 days \| Last 30 days \| 30-90 days \| |
| `intent-signals/SKILL.md:245` | all signals | contact within 2 days | - The best time to email someone is within 48 hours of a signal firing. After 2 weeks, the signal is stale and your "I noticed..." line sounds like a lie. |
| `intent-signals/SKILL.md:245` | all signals | stale after 14 days | - The best time to email someone is within 48 hours of a signal firing. After 2 weeks, the signal is stale and your "I noticed..." line sounds like a lie. |
| `trigger-mapping/SKILL.md:39` | New Funding Round | contact within 14 days | \| **Urgency window** \| Contact within 2 weeks of announcement. After 30 days, the signal is stale. \| |
| `trigger-mapping/SKILL.md:39` | New Funding Round | stale after 30 days | \| **Urgency window** \| Contact within 2 weeks of announcement. After 30 days, the signal is stale. \| |
| `trigger-mapping/SKILL.md:50` | Hiring for Target Role | contact within 7 days | \| **Urgency window** \| Contact within 1 week of posting. After 4 weeks, the role may be filled or paused. \| |
| `trigger-mapping/SKILL.md:50` | Hiring for Target Role | stale after 28 days | \| **Urgency window** \| Contact within 1 week of posting. After 4 weeks, the role may be filled or paused. \| |
| `trigger-mapping/SKILL.md:72` | Tech Stack Change | contact within 14 days | \| **Urgency window** \| Contact within 2 weeks of detection. Stack changes take 3-6 months to settle. \| |
| `trigger-mapping/SKILL.md:127` | Content Publication | contact within 2 days | \| **Urgency window** \| Within 48 hours of publication. Reference stale content and you look like a stalker, not a peer. \| |
| `lead-prioritization/SKILL.md:78` | Competitor evaluation (G2, reviews) | loses 5 points per week (no fixed cutoff) | \| Competitor evaluation (G2, reviews) \| 20 \| Detected = 20 \| -5/week \| |
| `lead-prioritization/SKILL.md:79` | Hiring for target role | loses 3 points per week (no fixed cutoff) | \| Hiring for target role \| 15 \| Active posting = 15, Recently filled = 8 \| -3/week \| |
| `lead-prioritization/SKILL.md:80` | Recent funding | loses 2 points per month (no fixed cutoff) | \| Recent funding \| 15 \| < 30 days = 15, 30-90 days = 10, 90-180 = 5 \| -2/month \| |
| `lead-prioritization/SKILL.md:81` | Website visit (pricing/product pages) | loses 5 points per week (no fixed cutoff) | \| Website visit (pricing/product pages) \| 15 \| Multiple visits = 15, Single = 8 \| -5/week \| |
| `lead-prioritization/SKILL.md:82` | Leadership change in target dept | loses 2 points per month (no fixed cutoff) | \| Leadership change in target dept \| 10 \| < 60 days = 10, 60-120 days = 5 \| -2/month \| |
| `lead-prioritization/SKILL.md:83` | Content consumption (your content) | loses 3 points per week (no fixed cutoff) | \| Content consumption (your content) \| 10 \| Multiple pieces = 10, Single = 5 \| -3/week \| |
| `lead-prioritization/SKILL.md:84` | Social signals (posts about pain) | loses 5 points per week (no fixed cutoff) | \| Social signals (posts about pain) \| 10 \| Specific post = 10, Engagement = 5 \| -5/week \| |
| `lead-prioritization/SKILL.md:85` | Tech stack change | loses 1 point per month (no fixed cutoff) | \| Tech stack change \| 5 \| Detected = 5 \| -1/month \| |

## Proposed pin

**Pin: stale after 28 days, contact within 7 days**, from `trigger-mapping/SKILL.md:50`, because it is the only window stated for job postings, and job posts are the signals this gate scores.

Stating this one window in every file (or passing it to every run) means the freshness call no longer depends on which file was loaded.
