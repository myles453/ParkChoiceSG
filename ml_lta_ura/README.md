# LTA and URA availability model

An experimental second model for LTA and URA carparks. Their feeds give a lot count at retrieval time, with no update time, no capacity and no history endpoint. The model is trained on HDB snapshots reshaped to look like those feeds, then tested on LTA and URA readings collected from 7 to 15 October 2026.

## Result

| Carparks | Verdict, weekdays only |
|---|---|
| URA | Beats the current reading. Brier 0.041 against 0.056, from 11,433 "not free" rows. |
| LTA | Not tested in practice. Only 60 "not free" rows from 3 carparks. Show the current reading. |

The Singapore Grand Prix closed roads from 7 to 13 October. Those rows are reported separately in `reports/evaluation_target.md` and are not part of the verdict. No normal weekend was tested.

Variant A is the recommended model. Variant B adds a 72-hour maximum count and needs at least 24 hours of live history before that feature works.

## Files

| File | Purpose |
|---|---|
| `collect.py` | Saves LTA and URA availability every 5 minutes. `collect.py --status` reports coverage. |
| `build_retrieval_view.py` | Builds the HDB training pairs from `ml/data/raw/hdb/`. |
| `features.py` | Feature and label code shared by training and testing. |
| `train.py`, `evaluate.py` | Train variants A and B and score them on HDB test dates. |
| `build_target_pairs.py`, `evaluate_target.py` | Score both variants on collected LTA and URA data. |
| `models/` | Trained variants and `model_card.json`. |
| `reports/` | HDB and LTA/URA evaluation results. |

## Commands

Use the environment from `ml/` (see `ml/README.md`). `collect.py` needs `LTA_ACCOUNT_KEY` and `URA_ACCESS_KEY` in `data-pipeline/.env`.

From the repository root:

```
ml/.venv/bin/python ml_lta_ura/build_retrieval_view.py
ml/.venv/bin/python ml_lta_ura/train.py
ml/.venv/bin/python ml_lta_ura/evaluate.py
```

From `ml_lta_ura/`:

```
../ml/.venv/bin/python collect.py
../ml/.venv/bin/python collect.py --status
../ml/.venv/bin/python build_target_pairs.py
../ml/.venv/bin/python evaluate_target.py
../ml/.venv/bin/python -m pytest
```

`data/` is not in the repository. The scripts rebuild it.
