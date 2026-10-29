# Part A gate results

Terms: "model switch" = a different model (e.g. Haiku vs Sonnet); "model upgrade" = a newer version of the same model; "repeat noise" = two runs of one model on the same post.

## Verdicts

- **natural sample**, model switch sonnet-5-5 -> haiku-5-5 (200 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.550 -> 0.765: drop of -21.5 points within the 14.5-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 3.4, haiku-5-5 7.3; largest is haiku-5-5. Threshold = max(2 x 7.3, 3) = 14.5 points.
  - flip_rate: pass. model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 29/200 labels changed = 14.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0; within the 22.1-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 17.1, haiku-5-5 6.5; largest is sonnet-5-5. Threshold = 17.1 + 5 = 22.1 points.
- **natural sample**, model upgrade haiku-4-5 -> haiku-5-5 (200 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.593 -> 0.765: drop of -17.3 points within the 14.5-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-4-5 3.4, haiku-5-5 7.3; largest is haiku-5-5. Threshold = max(2 x 7.3, 3) = 14.5 points.
  - flip_rate: pass. model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 27/199 labels changed = 13.6%; failures excluded: claude-haiku-4-5-20251001 1, claude-haiku-5-5 0; within the 19.8-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-4-5 14.8, haiku-5-5 6.5; largest is haiku-4-5. Threshold = 14.8 + 5 = 19.8 points.
- **natural sample**, model switch opus-5-5 -> sonnet-5-5 (50 posts): FAIL
  - macro_f1_drop: FAIL. macro-F1 0.823 -> 0.527: drop of 29.6 points exceeds the 6.8-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 3.4; largest is sonnet-5-5. Threshold = max(2 x 3.4, 3) = 6.8 points.
  - flip_rate: pass. model switch (claude-opus-5-5 vs claude-sonnet-5-5): 8/50 labels changed = 16.0%; failures excluded: claude-opus-5-5 0, claude-sonnet-5-5 0; within the 22.1-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 17.1; largest is sonnet-5-5. Threshold = 17.1 + 5 = 22.1 points.
- **natural sample**, model switch opus-5-5 -> haiku-5-5 (50 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.823 -> 0.923: drop of -10.1 points within the 14.5-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-5-5 7.3; largest is haiku-5-5. Threshold = max(2 x 7.3, 3) = 14.5 points.
  - flip_rate: pass. model switch (claude-opus-5-5 vs claude-haiku-5-5): 1/50 labels changed = 2.0%; failures excluded: claude-opus-5-5 0, claude-haiku-5-5 0; within the 11.5-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-5-5 6.5; largest is haiku-5-5. Threshold = 6.5 + 5 = 11.5 points.
- **ambiguous subset**, model switch sonnet-5-5 -> haiku-5-5 (80 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.836 -> 0.805: drop of 3.1 points within the 14.5-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 7.2, haiku-5-5 3.1; largest is sonnet-5-5. Threshold = max(2 x 7.2, 3) = 14.5 points.
  - flip_rate: pass. model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 10/80 labels changed = 12.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0; within the 15.0-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 7.5, haiku-5-5 10.0; largest is haiku-5-5. Threshold = 10.0 + 5 = 15.0 points.
- **ambiguous subset**, model upgrade haiku-4-5 -> haiku-5-5 (80 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.641 -> 0.805: drop of -16.4 points within the 6.2-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-4-5 0.9, haiku-5-5 3.1; largest is haiku-5-5. Threshold = max(2 x 3.1, 3) = 6.2 points.
  - flip_rate: pass. model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 19/78 labels changed = 24.4%; failures excluded: claude-haiku-4-5-20251001 2, claude-haiku-5-5 0; within the 41.4-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-4-5 36.4, haiku-5-5 10.0; largest is haiku-4-5. Threshold = 36.4 + 5 = 41.4 points.
- **natural sample, posted within 90 days**, model switch sonnet-5-5 -> haiku-5-5 (115 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.679 -> 0.731: drop of -5.2 points within the 19.7-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 9.9, haiku-5-5 1.9; largest is sonnet-5-5. Threshold = max(2 x 9.9, 3) = 19.7 points.
  - flip_rate: pass. model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 3/115 labels changed = 2.6%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0; within the 8.5-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 3.5, haiku-5-5 2.6; largest is sonnet-5-5. Threshold = 3.5 + 5 = 8.5 points.
- **natural sample, posted within 90 days**, model upgrade haiku-4-5 -> haiku-5-5 (115 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.608 -> 0.731: drop of -12.4 points within the 11.3-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-4-5 5.6, haiku-5-5 1.9; largest is haiku-4-5. Threshold = max(2 x 5.6, 3) = 11.3 points.
  - flip_rate: pass. model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 9/114 labels changed = 7.9%; failures excluded: claude-haiku-4-5-20251001 1, claude-haiku-5-5 0; within the 14.7-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-4-5 9.7, haiku-5-5 2.6; largest is haiku-4-5. Threshold = 9.7 + 5 = 14.7 points.
- **natural sample, posted within 90 days**, model switch opus-5-5 -> sonnet-5-5 (27 posts): FAIL
  - macro_f1_drop: FAIL. macro-F1 0.890 -> 0.669: drop of 22.0 points exceeds the 19.7-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 9.9; largest is sonnet-5-5. Threshold = max(2 x 9.9, 3) = 19.7 points.
  - flip_rate: pass. model switch (claude-opus-5-5 vs claude-sonnet-5-5): 2/27 labels changed = 7.4%; failures excluded: claude-opus-5-5 0, claude-sonnet-5-5 0; within the 8.5-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 3.5; largest is sonnet-5-5. Threshold = 3.5 + 5 = 8.5 points.
- **natural sample, posted within 90 days**, model switch opus-5-5 -> haiku-5-5 (27 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.890 -> 0.890: drop of 0.0 points within the 3.8-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-5-5 1.9; largest is haiku-5-5. Threshold = max(2 x 1.9, 3) = 3.8 points.
  - flip_rate: pass. model switch (claude-opus-5-5 vs claude-haiku-5-5): 0/27 labels changed = 0.0%; failures excluded: claude-opus-5-5 0, claude-haiku-5-5 0; within the 7.6-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-5-5 2.6; largest is haiku-5-5. Threshold = 2.6 + 5 = 7.6 points.
- **ambiguous subset, posted within 90 days**, model switch sonnet-5-5 -> haiku-5-5 (54 posts): FAIL
  - macro_f1_drop: pass. macro-F1 0.786 -> 0.747: drop of 3.9 points within the 18.3-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): sonnet-5-5 9.2, haiku-5-5 6.0; largest is sonnet-5-5. Threshold = max(2 x 9.2, 3) = 18.3 points.
  - flip_rate: FAIL. model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 10/54 labels changed = 18.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0; exceeds the 18.0-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): sonnet-5-5 11.1, haiku-5-5 13.0; largest is haiku-5-5. Threshold = 13.0 + 5 = 18.0 points.
- **ambiguous subset, posted within 90 days**, model upgrade haiku-4-5 -> haiku-5-5 (54 posts): PASS
  - macro_f1_drop: pass. macro-F1 0.553 -> 0.747: drop of -19.3 points within the 12.0-point threshold. Fail if macro-F1 vs hand labels drops by more than max(2 x measured repeat noise in F1, 3 points). Measured repeat noise in F1 (points): haiku-4-5 4.1, haiku-5-5 6.0; largest is haiku-5-5. Threshold = max(2 x 6.0, 3) = 12.0 points.
  - flip_rate: pass. model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 18/54 labels changed = 33.3%; failures excluded: claude-haiku-4-5-20251001 0, claude-haiku-5-5 0; within the 46.5-point threshold. Fail if the flip rate between arms exceeds measured repeat noise + 5 points. Measured repeat noise (points): haiku-4-5 41.5, haiku-5-5 13.0; largest is haiku-4-5. Threshold = 41.5 + 5 = 46.5 points.

## Metrics by population

### natural sample (200 posts)

| arm | repeat | runs | failed | excluded | macro-F1 yes/no | macro-F1 type |
|---|---|---|---|---|---|---|
| haiku-5-5 | 1 | 200 | 0 | 0 | 0.765 | 0.732 |
| haiku-5-5 | 2 | 200 | 0 | 0 | 0.693 | 0.717 |
| sonnet-5-5 | 1 | 200 | 0 | 0 | 0.550 | 0.655 |
| sonnet-5-5 | 2 | 200 | 1 | 0 | 0.584 | 0.680 |
| opus-5-5 | 1 | 50 | 0 | 0 | 0.823 | 0.864 |
| haiku-4-5 | 1 | 200 | 1 | 0 | 0.593 | 0.619 |
| haiku-4-5 | 2 | 200 | 3 | 0 | 0.559 | 0.556 |

- repeat noise (claude-haiku-5-5 run 1 vs claude-haiku-5-5 run 2): 13/200 labels changed = 6.5%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-sonnet-5-5 run 1 vs claude-sonnet-5-5 run 2): 34/199 labels changed = 17.1%; failures excluded: run 1 0, run 2 1
- repeat noise (claude-haiku-4-5-20251001 run 1 vs claude-haiku-4-5-20251001 run 2): 29/196 labels changed = 14.8%; failures excluded: run 1 1, run 2 3
- model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 29/200 labels changed = 14.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 18.0%
- model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 27/199 labels changed = 13.6%; failures excluded: claude-haiku-4-5-20251001 1, claude-haiku-5-5 0 (yes/no); signal type: 21.6%
- model switch (claude-opus-5-5 vs claude-sonnet-5-5): 8/50 labels changed = 16.0%; failures excluded: claude-opus-5-5 0, claude-sonnet-5-5 0 (yes/no); signal type: 18.0%
- model switch (claude-opus-5-5 vs claude-haiku-5-5): 1/50 labels changed = 2.0%; failures excluded: claude-opus-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 10.0%

### ambiguous subset (80 posts)

| arm | repeat | runs | failed | excluded | macro-F1 yes/no | macro-F1 type |
|---|---|---|---|---|---|---|
| haiku-5-5 | 1 | 80 | 0 | 0 | 0.805 | 0.603 |
| haiku-5-5 | 2 | 80 | 0 | 0 | 0.836 | 0.580 |
| sonnet-5-5 | 1 | 80 | 0 | 0 | 0.836 | 0.635 |
| sonnet-5-5 | 2 | 80 | 0 | 0 | 0.908 | 0.685 |
| haiku-4-5 | 1 | 80 | 2 | 0 | 0.641 | 0.435 |
| haiku-4-5 | 2 | 80 | 1 | 0 | 0.632 | 0.390 |

- repeat noise (claude-haiku-5-5 run 1 vs claude-haiku-5-5 run 2): 8/80 labels changed = 10.0%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-sonnet-5-5 run 1 vs claude-sonnet-5-5 run 2): 6/80 labels changed = 7.5%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-haiku-4-5-20251001 run 1 vs claude-haiku-4-5-20251001 run 2): 28/77 labels changed = 36.4%; failures excluded: run 1 2, run 2 1
- model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 10/80 labels changed = 12.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 15.0%
- model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 19/78 labels changed = 24.4%; failures excluded: claude-haiku-4-5-20251001 2, claude-haiku-5-5 0 (yes/no); signal type: 29.5%

### natural sample, posted within 90 days (115 posts)

| arm | repeat | runs | failed | excluded | macro-F1 yes/no | macro-F1 type |
|---|---|---|---|---|---|---|
| haiku-5-5 | 1 | 115 | 0 | 0 | 0.731 | 0.737 |
| haiku-5-5 | 2 | 115 | 0 | 0 | 0.750 | 0.758 |
| sonnet-5-5 | 1 | 115 | 0 | 0 | 0.679 | 0.729 |
| sonnet-5-5 | 2 | 115 | 0 | 0 | 0.778 | 0.780 |
| opus-5-5 | 1 | 27 | 0 | 0 | 0.890 | 0.859 |
| haiku-4-5 | 1 | 115 | 1 | 0 | 0.608 | 0.632 |
| haiku-4-5 | 2 | 115 | 1 | 0 | 0.664 | 0.637 |

- repeat noise (claude-haiku-5-5 run 1 vs claude-haiku-5-5 run 2): 3/115 labels changed = 2.6%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-sonnet-5-5 run 1 vs claude-sonnet-5-5 run 2): 4/115 labels changed = 3.5%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-haiku-4-5-20251001 run 1 vs claude-haiku-4-5-20251001 run 2): 11/113 labels changed = 9.7%; failures excluded: run 1 1, run 2 1
- model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 3/115 labels changed = 2.6%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 7.0%
- model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 9/114 labels changed = 7.9%; failures excluded: claude-haiku-4-5-20251001 1, claude-haiku-5-5 0 (yes/no); signal type: 18.4%
- model switch (claude-opus-5-5 vs claude-sonnet-5-5): 2/27 labels changed = 7.4%; failures excluded: claude-opus-5-5 0, claude-sonnet-5-5 0 (yes/no); signal type: 7.4%
- model switch (claude-opus-5-5 vs claude-haiku-5-5): 0/27 labels changed = 0.0%; failures excluded: claude-opus-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 7.4%

### ambiguous subset, posted within 90 days (54 posts)

| arm | repeat | runs | failed | excluded | macro-F1 yes/no | macro-F1 type |
|---|---|---|---|---|---|---|
| haiku-5-5 | 1 | 54 | 0 | 0 | 0.747 | 0.563 |
| haiku-5-5 | 2 | 54 | 0 | 0 | 0.807 | 0.567 |
| sonnet-5-5 | 1 | 54 | 0 | 0 | 0.786 | 0.614 |
| sonnet-5-5 | 2 | 54 | 0 | 0 | 0.877 | 0.666 |
| haiku-4-5 | 1 | 54 | 0 | 0 | 0.553 | 0.381 |
| haiku-4-5 | 2 | 54 | 1 | 0 | 0.595 | 0.380 |

- repeat noise (claude-haiku-5-5 run 1 vs claude-haiku-5-5 run 2): 7/54 labels changed = 13.0%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-sonnet-5-5 run 1 vs claude-sonnet-5-5 run 2): 6/54 labels changed = 11.1%; failures excluded: run 1 0, run 2 0
- repeat noise (claude-haiku-4-5-20251001 run 1 vs claude-haiku-4-5-20251001 run 2): 22/53 labels changed = 41.5%; failures excluded: run 1 0, run 2 1
- model switch (claude-sonnet-5-5 vs claude-haiku-5-5): 10/54 labels changed = 18.5%; failures excluded: claude-sonnet-5-5 0, claude-haiku-5-5 0 (yes/no); signal type: 22.2%
- model upgrade (claude-haiku-4-5-20251001 vs claude-haiku-5-5): 18/54 labels changed = 33.3%; failures excluded: claude-haiku-4-5-20251001 0, claude-haiku-5-5 0 (yes/no); signal type: 40.7%

## Runs excluded from metrics

None: every run's modelUsage matched its arm's pinned model.

## Failed runs (kept, counted as failures)

- ashby:sanity:05920588-9b6e-4d13-b527-89fe5ade9847 / haiku-4-5 / repeat 1: error result (subtype error_max_turns): 
- greenhouse:reachdesk:4923515101 / haiku-4-5 / repeat 1: error result (subtype error_max_turns): 
- ashby:levelpath:5d5d69c5-7977-4c74-9ba3-e26be06be081 / haiku-4-5 / repeat 1: error result (subtype error_max_turns): 
- ashby:vendelux:51060e70-da86-4b08-a4c3-08bdfb0eff79 / sonnet-5-5 / repeat 2: error result (subtype error_max_turns): 
- ashby:wonderful:e10595c8-2e68-40e5-8c26-68bcecada2d5 / haiku-4-5 / repeat 2: error result (subtype error_max_turns): 
- greenhouse:observeai:5107653008 / haiku-4-5 / repeat 2: error result (subtype error_max_turns): 
- ashby:attio:acbedaad-aa1e-4c9f-bce2-cca372cd2751 / haiku-4-5 / repeat 2: error result (subtype error_max_turns): 
- ashby:abacum:8fdce4e8-0219-40a0-9475-e95e4d3c47e8 / haiku-4-5 / repeat 2: error result (subtype error_max_turns): 

## Rule checks (reported, not the headline)

Failures among runs that returned output, per population and arm.

- natural sample, haiku-5-5: structured_output 0, evidence 97, score 3, recency 2, tier 0, label_signal 27, label_type 41
- natural sample, sonnet-5-5: structured_output 0, evidence 97, score 65, recency 14, tier 15, label_signal 78, label_type 89
- natural sample, opus-5-5: structured_output 0, evidence 4, score 0, recency 0, tier 0, label_signal 2, label_type 4
- natural sample, haiku-4-5: structured_output 1, evidence 140, score 23, recency 15, tier 29, label_signal 59, label_type 107
- ambiguous subset, haiku-5-5: structured_output 0, evidence 5, score 6, recency 1, tier 0, label_signal 18, label_type 20
- ambiguous subset, sonnet-5-5: structured_output 0, evidence 5, score 34, recency 5, tier 17, label_signal 12, label_type 12
- ambiguous subset, haiku-4-5: structured_output 1, evidence 54, score 15, recency 16, tier 27, label_signal 48, label_type 52
- natural sample, posted within 90 days, haiku-5-5: structured_output 0, evidence 53, score 1, recency 2, tier 0, label_signal 15, label_type 24
- natural sample, posted within 90 days, sonnet-5-5: structured_output 0, evidence 60, score 42, recency 13, tier 5, label_signal 16, label_type 26
- natural sample, posted within 90 days, opus-5-5: structured_output 0, evidence 3, score 0, recency 0, tier 0, label_signal 1, label_type 3
- natural sample, posted within 90 days, haiku-4-5: structured_output 0, evidence 87, score 12, recency 9, tier 7, label_signal 21, label_type 54
- ambiguous subset, posted within 90 days, haiku-5-5: structured_output 0, evidence 5, score 5, recency 1, tier 0, label_signal 17, label_type 19
- ambiguous subset, posted within 90 days, sonnet-5-5: structured_output 0, evidence 4, score 23, recency 5, tier 11, label_signal 12, label_type 12
- ambiguous subset, posted within 90 days, haiku-4-5: structured_output 1, evidence 40, score 12, recency 12, tier 17, label_signal 42, label_type 45
