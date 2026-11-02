# HDB evaluation of the retrieval-view models (test split only)

**Does each variant beat persistence on Brier score?**

- Variant A BEATS persistence on Brier, overall: 0.01072 vs 0.01494.
- Variant A BEATS persistence on Brier, low-count subset (current_available <= 10): 0.08457 vs 0.12005.
- Variant B BEATS persistence on Brier, overall: 0.01015 vs 0.01494.
- Variant B BEATS persistence on Brier, low-count subset (current_available <= 10): 0.07993 vs 0.12005.

**This evaluation says nothing yet about LTA and URA carparks.** Both variants were trained and tested on HDB data reshaped to look like an LTA/URA feed. Whether the reshaping is faithful is exactly what validation on collected LTA/URA readings has to show.

Test split: decisions 2026-09-27 to 2026-10-07 14:30 Asia/Singapore. Nothing below was tuned on the test split: hyperparameters and calibrators were chosen on validation. Log loss clips probabilities to [1e-15, 1-1e-15]; persistence outputs exactly 0 or 1, so its log loss is dominated by the clip. AP is average precision for the "not free" class. Always-free predicts the train base rate 0.95061.

## Base rate of label_free (share free) per split

| Split | Rows | Share free | Share not free |
|---|---|---|---|
| train | 57,954,784 | 0.9506 | 0.0494 |
| validation | 10,051,287 | 0.9524 | 0.0476 |
| test | 9,729,888 | 0.9509 | 0.0491 |

## 1. All test rows

| Horizon (min) | Method | Rows | Brier | Log loss | ROC AUC | AP (not free) |
|---|---|---|---|---|---|---|
| all | variant_a | 9,729,888 | 0.0107 | 0.0370 | 0.9951 | 0.9160 |
| all | variant_b | 9,729,888 | 0.0102 | 0.0340 | 0.9958 | 0.9351 |
| all | persistence | 9,729,888 | 0.0149 | 0.5159 | 0.9197 | 0.7264 |
| all | always_free | 9,729,888 | 0.0467 | 0.1960 | 0.5000 | 0.0491 |
| 15 | variant_a | 1,946,818 | 0.0077 | 0.0271 | 0.9973 | 0.9500 |
| 15 | variant_b | 1,946,818 | 0.0075 | 0.0257 | 0.9977 | 0.9600 |
| 15 | persistence | 1,946,818 | 0.0104 | 0.3607 | 0.9437 | 0.8038 |
| 15 | always_free | 1,946,818 | 0.0467 | 0.1959 | 0.5000 | 0.0491 |
| 30 | variant_a | 1,945,415 | 0.0095 | 0.0329 | 0.9961 | 0.9298 |
| 30 | variant_b | 1,945,415 | 0.0091 | 0.0307 | 0.9966 | 0.9453 |
| 30 | persistence | 1,945,415 | 0.0131 | 0.4532 | 0.9293 | 0.7570 |
| 30 | always_free | 1,945,415 | 0.0467 | 0.1958 | 0.5000 | 0.0491 |
| 45 | variant_a | 1,952,690 | 0.0108 | 0.0372 | 0.9950 | 0.9134 |
| 45 | variant_b | 1,952,690 | 0.0102 | 0.0343 | 0.9958 | 0.9337 |
| 45 | persistence | 1,952,690 | 0.0151 | 0.5200 | 0.9192 | 0.7246 |
| 45 | always_free | 1,952,690 | 0.0467 | 0.1961 | 0.5000 | 0.0492 |
| 60 | variant_a | 1,945,017 | 0.0118 | 0.0407 | 0.9941 | 0.8986 |
| 60 | variant_b | 1,945,017 | 0.0111 | 0.0372 | 0.9950 | 0.9237 |
| 60 | persistence | 1,945,017 | 0.0166 | 0.5729 | 0.9108 | 0.6992 |
| 60 | always_free | 1,945,017 | 0.0468 | 0.1961 | 0.5000 | 0.0492 |
| 90 | variant_a | 1,939,948 | 0.0138 | 0.0469 | 0.9920 | 0.8709 |
| 90 | variant_b | 1,939,948 | 0.0127 | 0.0423 | 0.9934 | 0.9046 |
| 90 | persistence | 1,939,948 | 0.0195 | 0.6733 | 0.8952 | 0.6520 |
| 90 | always_free | 1,939,948 | 0.0467 | 0.1959 | 0.5000 | 0.0491 |

## 2. Low-count subset (current_available <= 10)

Replaces the first model's near-full subset, because no capacity exists here.

| Horizon (min) | Method | Rows | Brier | Log loss | ROC AUC | AP (not free) |
|---|---|---|---|---|---|---|
| all | variant_a | 1,121,195 | 0.0846 | 0.2795 | 0.9504 | 0.9250 |
| all | variant_b | 1,121,195 | 0.0799 | 0.2566 | 0.9582 | 0.9437 |
| all | persistence | 1,121,195 | 0.1201 | 4.1466 | 0.8780 | 0.7910 |
| all | always_free | 1,121,195 | 0.3781 | 1.2834 | 0.5000 | 0.4168 |
| 15 | variant_a | 224,323 | 0.0645 | 0.2194 | 0.9692 | 0.9531 |
| 15 | variant_b | 224,323 | 0.0629 | 0.2075 | 0.9729 | 0.9630 |
| 15 | persistence | 224,323 | 0.0880 | 3.0380 | 0.9102 | 0.8465 |
| 15 | always_free | 224,323 | 0.3841 | 1.3032 | 0.5000 | 0.4235 |
| 30 | variant_a | 224,087 | 0.0771 | 0.2581 | 0.9576 | 0.9355 |
| 30 | variant_b | 224,087 | 0.0742 | 0.2405 | 0.9635 | 0.9507 |
| 30 | persistence | 224,087 | 0.1084 | 3.7434 | 0.8896 | 0.8121 |
| 30 | always_free | 224,087 | 0.3816 | 1.2948 | 0.5000 | 0.4207 |
| 45 | variant_a | 225,086 | 0.0858 | 0.2838 | 0.9487 | 0.9218 |
| 45 | variant_b | 225,086 | 0.0814 | 0.2610 | 0.9567 | 0.9417 |
| 45 | persistence | 225,086 | 0.1219 | 4.2119 | 0.8760 | 0.7888 |
| 45 | always_free | 225,086 | 0.3790 | 1.2864 | 0.5000 | 0.4179 |
| 60 | variant_a | 224,250 | 0.0922 | 0.3025 | 0.9415 | 0.9099 |
| 60 | variant_b | 224,250 | 0.0864 | 0.2754 | 0.9514 | 0.9345 |
| 60 | persistence | 224,250 | 0.1318 | 4.5530 | 0.8662 | 0.7713 |
| 60 | always_free | 224,250 | 0.3760 | 1.2766 | 0.5000 | 0.4146 |
| 90 | variant_a | 223,449 | 0.1033 | 0.3339 | 0.9282 | 0.8880 |
| 90 | variant_b | 223,449 | 0.0948 | 0.2987 | 0.9420 | 0.9212 |
| 90 | persistence | 223,449 | 0.1503 | 5.1902 | 0.8479 | 0.7382 |
| 90 | always_free | 223,449 | 0.3698 | 1.2560 | 0.5000 | 0.4076 |

## 3. Reliability (10 bins of calibrated p_free, test)

Variant A:

| Bin | Mean predicted | Observed share free | Rows |
|---|---|---|---|
| 0.0-0.1 | 0.0512 | 0.0513 | 269,590 |
| 0.1-0.2 | 0.1362 | 0.1452 | 91,213 |
| 0.2-0.3 | 0.2465 | 0.2479 | 43,985 |
| 0.3-0.4 | 0.3513 | 0.3460 | 25,881 |
| 0.4-0.5 | 0.4570 | 0.4574 | 33,042 |
| 0.5-0.6 | 0.5527 | 0.5478 | 29,216 |
| 0.6-0.7 | 0.6564 | 0.6482 | 48,856 |
| 0.7-0.8 | 0.7501 | 0.7495 | 46,538 |
| 0.8-0.9 | 0.8530 | 0.8464 | 108,142 |
| 0.9-1.0 | 0.9982 | 0.9980 | 9,033,425 |

Variant B:

| Bin | Mean predicted | Observed share free | Rows |
|---|---|---|---|
| 0.0-0.1 | 0.0309 | 0.0301 | 264,156 |
| 0.1-0.2 | 0.1427 | 0.1452 | 81,414 |
| 0.2-0.3 | 0.2486 | 0.2439 | 41,744 |
| 0.3-0.4 | 0.3480 | 0.3447 | 39,402 |
| 0.4-0.5 | 0.4529 | 0.4533 | 36,924 |
| 0.5-0.6 | 0.5542 | 0.5496 | 34,790 |
| 0.6-0.7 | 0.6521 | 0.6486 | 45,385 |
| 0.7-0.8 | 0.7504 | 0.7455 | 48,568 |
| 0.8-0.9 | 0.8522 | 0.8483 | 103,647 |
| 0.9-1.0 | 0.9984 | 0.9983 | 9,033,858 |

## 4. State unchanged vs changed between decision and arrival

"State" is the free status: current_available >= 1 versus label_free. Unchanged means they agree.

| Group | Rows | Brier A | Brier B | Brier persistence |
|---|---|---|---|---|
| unchanged | 9,584,550 | 0.0025 | 0.0027 | 0.0000 |
| changed | 145,338 | 0.5535 | 0.5036 | 1.0000 |

## 5. First model (reference only)

Copied from ml/reports/evaluation.md. **The row sets differ**: the first model uses the per-carpark HDB history, capacity, reading age (up to 15 minutes) and source-time readings; these variants use retrieval-time readings at most 6 minutes old and a different label tolerance, so the numbers are not a like-for-like comparison.

| Horizon (min) | First model Brier | Variant A Brier | Variant B Brier |
|---|---|---|---|
| all | 0.0115 | 0.0107 | 0.0102 |
| 15 | 0.0098 | 0.0077 | 0.0075 |
| 30 | 0.0109 | 0.0095 | 0.0091 |
| 45 | 0.0115 | 0.0108 | 0.0102 |
| 60 | 0.0121 | 0.0118 | 0.0111 |
| 90 | 0.0131 | 0.0138 | 0.0127 |

## 6. Feature importance

Share of total gain, and split count.

Variant A:

| Feature | Gain share | Splits |
|---|---|---|
| current_available | 0.8958 | 5,508 |
| available_lag_15min | 0.0338 | 5,515 |
| available_lag_30min | 0.0266 | 6,769 |
| arrival_slot_15min | 0.0124 | 10,316 |
| available_lag_60min | 0.0110 | 5,948 |
| delta_60min | 0.0100 | 7,214 |
| delta_15min | 0.0052 | 5,935 |
| horizon_minutes | 0.0038 | 3,118 |
| arrival_weekday | 0.0012 | 3,475 |
| arrival_is_weekend | 0.0001 | 262 |
| arrival_is_public_holiday | 0.0001 | 314 |

Variant B:

| Feature | Gain share | Splits |
|---|---|---|
| current_available | 0.3580 | 6,286 |
| available_lag_15min | 0.2881 | 7,306 |
| ratio_to_trailing_max | 0.2225 | 9,115 |
| available_lag_30min | 0.0575 | 9,157 |
| trailing_max_72h | 0.0210 | 15,055 |
| arrival_slot_15min | 0.0166 | 19,667 |
| delta_15min | 0.0130 | 7,059 |
| available_lag_60min | 0.0092 | 8,782 |
| delta_60min | 0.0078 | 9,194 |
| horizon_minutes | 0.0041 | 4,863 |
| arrival_weekday | 0.0019 | 6,042 |
| arrival_is_weekend | 0.0002 | 472 |
| arrival_is_public_holiday | 0.0001 | 380 |

## 7. Training summary

```json
{
 "a": {
  "train_rows_used": 7901231,
  "train_share_free": 0.9506703449120776,
  "validation_rows": 10051287,
  "validation_share_free": 0.9523517734594584,
  "best_iteration": 877,
  "chosen_config": {
   "learning_rate": 0.05,
   "num_leaves": 63,
   "min_data_in_leaf": 1000,
   "feature_fraction": 0.8
  },
  "configs_tried": [
   {
    "learning_rate": 0.1,
    "num_leaves": 63,
    "min_data_in_leaf": 200,
    "feature_fraction": 1.0,
    "best_iteration": 68,
    "validation_log_loss": 0.03680044404017673,
    "seconds": 32.4
   },
   {
    "learning_rate": 0.1,
    "num_leaves": 127,
    "min_data_in_leaf": 500,
    "feature_fraction": 0.9,
    "best_iteration": 189,
    "validation_log_loss": 0.03642667054959231,
    "seconds": 68.9
   },
   {
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 1000,
    "feature_fraction": 0.8,
    "best_iteration": 877,
    "validation_log_loss": 0.03628581920736423,
    "seconds": 240.7
   },
   {
    "learning_rate": 0.05,
    "num_leaves": 255,
    "min_data_in_leaf": 2000,
    "feature_fraction": 0.8,
    "best_iteration": 308,
    "validation_log_loss": 0.03630990364183348,
    "seconds": 117.4
   },
   {
    "learning_rate": 0.1,
    "num_leaves": 31,
    "min_data_in_leaf": 100,
    "feature_fraction": 1.0,
    "best_iteration": 68,
    "validation_log_loss": 0.037336853997665065,
    "seconds": 18.1
   }
  ]
 },
 "b": {
  "train_rows_used": 7901231,
  "train_share_free": 0.9506703449120776,
  "validation_rows": 10051287,
  "validation_share_free": 0.9523517734594584,
  "best_iteration": 407,
  "chosen_config": {
   "learning_rate": 0.05,
   "num_leaves": 255,
   "min_data_in_leaf": 2000,
   "feature_fraction": 0.8
  },
  "configs_tried": [
   {
    "learning_rate": 0.1,
    "num_leaves": 63,
    "min_data_in_leaf": 200,
    "feature_fraction": 1.0,
    "best_iteration": 68,
    "validation_log_loss": 0.03426720701676075,
    "seconds": 23.5
   },
   {
    "learning_rate": 0.1,
    "num_leaves": 127,
    "min_data_in_leaf": 500,
    "feature_fraction": 0.9,
    "best_iteration": 117,
    "validation_log_loss": 0.03363491810481765,
    "seconds": 36.4
   },
   {
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 1000,
    "feature_fraction": 0.8,
    "best_iteration": 727,
    "validation_log_loss": 0.03330280486605186,
    "seconds": 144.2
   },
   {
    "learning_rate": 0.05,
    "num_leaves": 255,
    "min_data_in_leaf": 2000,
    "feature_fraction": 0.8,
    "best_iteration": 407,
    "validation_log_loss": 0.03327913496445318,
    "seconds": 137.2
   },
   {
    "learning_rate": 0.1,
    "num_leaves": 31,
    "min_data_in_leaf": 100,
    "feature_fraction": 1.0,
    "best_iteration": 66,
    "validation_log_loss": 0.03481111527909385,
    "seconds": 19.1
   }
  ]
 }
}
```
