# Evaluation (test split only)

**The model BEATS persistence on Brier score in the near-full subset (current_free_ratio < 0.10): 0.11045 vs 0.16256.**

Overall test Brier: model 0.01146, persistence 0.01624, always-free 0.04363 (model better overall).

Test split: decisions 2026-09-27 to 2026-10-07 14:30 Asia/Singapore. Nothing below was tuned on the test split.
Log loss clips probabilities to [1e-15, 1-1e-15]; persistence outputs exactly 0 or 1, so its log loss is dominated by the clip and is not comparable. AP is average precision for the "not free" class.

## Base rate of label_free = 1 (share free) and rows per split

| Split | Rows | Share free | Share not free |
|---|---|---|---|
| train | 47,479,218 | 0.95276 | 0.04724 |
| validation | 8,211,818 | 0.95498 | 0.04502 |
| test | 7,945,332 | 0.95428 | 0.04572 |

Always-free baseline predicts the train base rate 0.95276.

## 1. All test rows, overall and per horizon

| Horizon (min) | Method | Rows | Brier | Log loss | ROC AUC | AP (not free) |
|---|---|---|---|---|---|---|
| all | model | 7,945,332 | 0.0115 | 0.0397 | 0.9926 | 0.9031 |
| all | persistence | 7,945,332 | 0.0162 | 0.5608 | 0.9067 | 0.6844 |
| all | always_free | 7,945,332 | 0.0436 | 0.1857 | 0.5000 | 0.0457 |
| 15 | model | 1,566,204 | 0.0098 | 0.0342 | 0.9946 | 0.9222 |
| 15 | persistence | 1,566,204 | 0.0121 | 0.4196 | 0.9290 | 0.7541 |
| 15 | always_free | 1,566,204 | 0.0430 | 0.1835 | 0.5000 | 0.0450 |
| 30 | model | 1,629,066 | 0.0109 | 0.0376 | 0.9935 | 0.9115 |
| 30 | persistence | 1,629,066 | 0.0144 | 0.4988 | 0.9170 | 0.7162 |
| 30 | always_free | 1,629,066 | 0.0436 | 0.1858 | 0.5000 | 0.0457 |
| 45 | model | 1,597,230 | 0.0115 | 0.0399 | 0.9928 | 0.9060 |
| 45 | persistence | 1,597,230 | 0.0161 | 0.5548 | 0.9095 | 0.6931 |
| 45 | always_free | 1,597,230 | 0.0444 | 0.1885 | 0.5000 | 0.0466 |
| 60 | model | 1,578,279 | 0.0121 | 0.0419 | 0.9916 | 0.8941 |
| 60 | persistence | 1,578,279 | 0.0178 | 0.6159 | 0.8974 | 0.6566 |
| 60 | always_free | 1,578,279 | 0.0436 | 0.1857 | 0.5000 | 0.0457 |
| 90 | model | 1,574,553 | 0.0131 | 0.0451 | 0.9902 | 0.8790 |
| 90 | persistence | 1,574,553 | 0.0207 | 0.7161 | 0.8805 | 0.6066 |
| 90 | always_free | 1,574,553 | 0.0435 | 0.1851 | 0.5000 | 0.0455 |

## 2. Near-full subset (current_free_ratio < 0.10)

| Horizon (min) | Method | Rows | Brier | Log loss | ROC AUC | AP (not free) |
|---|---|---|---|---|---|---|
| all | model | 543,734 | 0.1104 | 0.3681 | 0.9227 | 0.9441 |
| all | persistence | 543,734 | 0.1626 | 5.6147 | 0.8173 | 0.8057 |
| all | always_free | 543,734 | 0.5396 | 1.8310 | 0.5000 | 0.5934 |
| 15 | model | 105,467 | 0.1027 | 0.3450 | 0.9304 | 0.9533 |
| 15 | persistence | 105,467 | 0.1291 | 4.4600 | 0.8510 | 0.8496 |
| 15 | always_free | 105,467 | 0.5608 | 1.9014 | 0.5000 | 0.6168 |
| 30 | model | 111,723 | 0.1085 | 0.3615 | 0.9251 | 0.9478 |
| 30 | persistence | 111,723 | 0.1473 | 5.0880 | 0.8326 | 0.8257 |
| 30 | always_free | 111,723 | 0.5488 | 1.8615 | 0.5000 | 0.6036 |
| 45 | model | 111,541 | 0.1097 | 0.3649 | 0.9242 | 0.9460 |
| 45 | persistence | 111,541 | 0.1585 | 5.4731 | 0.8213 | 0.8109 |
| 45 | always_free | 111,541 | 0.5420 | 1.8390 | 0.5000 | 0.5961 |
| 60 | model | 107,966 | 0.1140 | 0.3796 | 0.9185 | 0.9393 |
| 60 | persistence | 107,966 | 0.1769 | 6.1096 | 0.8036 | 0.7877 |
| 60 | always_free | 107,966 | 0.5315 | 1.8041 | 0.5000 | 0.5844 |
| 90 | model | 107,037 | 0.1173 | 0.3897 | 0.9146 | 0.9318 |
| 90 | persistence | 107,037 | 0.2012 | 6.9506 | 0.7814 | 0.7546 |
| 90 | always_free | 107,037 | 0.5147 | 1.7484 | 0.5000 | 0.5659 |

## 3. Reliability, short-horizon model on test (10 bins)

| Bin | Mean predicted | Observed share free | Rows |
|---|---|---|---|
| 0.0-0.1 | 0.0274 | 0.0350 | 193,938 |
| 0.1-0.2 | 0.1505 | 0.1638 | 50,583 |
| 0.2-0.3 | 0.2455 | 0.2682 | 34,924 |
| 0.3-0.4 | 0.3525 | 0.3561 | 31,545 |
| 0.4-0.5 | 0.4529 | 0.4508 | 27,990 |
| 0.5-0.6 | 0.5433 | 0.5555 | 28,937 |
| 0.6-0.7 | 0.6365 | 0.6602 | 35,082 |
| 0.7-0.8 | 0.7451 | 0.7636 | 54,854 |
| 0.8-0.9 | 0.8550 | 0.8550 | 80,246 |
| 0.9-1.0 | 0.9976 | 0.9969 | 7,407,233 |

Validation reliability (used to choose the threshold and bands):

| Bin | Mean predicted | Observed share free | Rows |
|---|---|---|---|
| 0.0-0.1 | 0.0276 | 0.0276 | 195,450 |
| 0.1-0.2 | 0.1508 | 0.1508 | 52,737 |
| 0.2-0.3 | 0.2454 | 0.2454 | 36,613 |
| 0.3-0.4 | 0.3522 | 0.3522 | 32,718 |
| 0.4-0.5 | 0.4530 | 0.4530 | 29,069 |
| 0.5-0.6 | 0.5429 | 0.5429 | 30,415 |
| 0.6-0.7 | 0.6355 | 0.6355 | 35,932 |
| 0.7-0.8 | 0.7452 | 0.7452 | 53,530 |
| 0.8-0.9 | 0.8555 | 0.8555 | 80,034 |
| 0.9-1.0 | 0.9977 | 0.9977 | 7,665,320 |

## 4. Threshold and confidence bands

Rule (applied to validation data only, on calibrated p_free):
- free_threshold = **0.5**: the lowest reliability-bin lower edge from which every bin above it has an observed free share of at least 0.5.
- High lower bound = **0.99**: the lowest 0.01 bin edge from which every validation bin of width 0.01 (with at least 500 rows) has an observed free share of at least 99%.
- Medium lower bound = **0.9**: the same with 90%, capped at the High bound. Below Medium is Low.
- The first version of this rule used the free share of all rows at or above a cut. It gave High = 0.45 on validation, because about 7.4M rows near p = 1 swamp the average. I found that on validation data, replaced it with the per-bin rule above, and reran. The test split was not used to choose either rule.

Test split, rows and observed share free per band:

| Band | Rows | Observed share free |
|---|---|---|
| High (p >= high) | 7,052,293 | 0.9996 |
| Medium (medium <= p < high) | 354,940 | 0.9434 |
| Low (p < medium) | 538,099 | 0.3680 |
| Predicted free (p >= free_threshold) | 7,606,352 | 0.9905 |
| Predicted not free (p < free_threshold) | 338,980 | 0.1425 |

Same bands on validation (for comparison):

| Band | Rows | Observed share free |
|---|---|---|
| High (p >= high) | 7,309,730 | 0.9996 |
| Medium (medium <= p < high) | 355,590 | 0.9587 |
| Low (p < medium) | 546,498 | 0.3563 |
| Predicted free (p >= free_threshold) | 7,865,231 | 0.9911 |
| Predicted not free (p < free_threshold) | 346,587 | 0.1357 |

## 5. Profile model, 24-hour horizon, test dates

The profile uses only train and validation dates, so the horizon does not change its prediction. Every test-date observation (stale ones excluded, each counted once at its observed_at) is scored against its carpark, day type and slot cell. Observations with no profile cell: 6,171 of 5,145,312, excluded from the metrics. Observed share free on the scored rows: 0.95358.

| Method | Rows | Brier | Log loss | ROC AUC | AP (not free) |
|---|---|---|---|---|---|
| profile | 5,139,141 | 0.0172 | 0.0669 | 0.9817 | 0.8230 |
| always_free | 5,139,141 | 0.0443 | 0.1879 | 0.5000 | 0.0464 |

## 6. Coverage

- Carparks in observations.parquet: 2,006
- With at least 1 train row: 1,996
- With a profile cell for at least 80 of the 96 weekday slots: 1,997
- With neither (no usable data), written to `ml/reports/uncovered_carparks.csv` with the last observed_at each reported: 9

Carparks that were rejected in every raw file never reach observations.parquet, so they are not in this count and have no last update time.
