# M5 subset (real reference data) — owner-approved exception

Real data from the Kaggle competition **M5 Forecasting Accuracy**
(<https://www.kaggle.com/competitions/m5-forecasting-accuracy/data>), subset CA_1 / FOODS_3 / top 50
items, extracted with `scripts/m5_subset_standalone.py` (see `SOURCE.json` for filters, original file
hashes and download date).

- Committed by decision of the project owner on 2026-09-27 (option B); the repository is to be made
  private. Kaggle competition rules apply: **do not redistribute**.
- This is the only raw external data allowed in Git (CLAUDE.md §13). Everything else stays in
  git-ignored `data/raw/`.
- Used by `uv run pytest -m m5_local` and for local runs. Unit and CI tests of the framework still use
  the synthetic fixture in `tests/fixtures/m5_like/`.
