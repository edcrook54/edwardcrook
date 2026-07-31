# GARCH Volatility Model

Volatility forecasting on equity/index returns using the GARCH family
(GARCH, EGARCH, GJR-GARCH), compared against a realized-volatility
benchmark.

## Contents

- `notebooks/garch-model.ipynb` — main analysis notebook

## Setup

```bash
uv sync --extra garch --extra dev
uv run jupyter lab notebooks/garch-model.ipynb
```

## TODO

- [ ] Move reusable model-fitting code into `src/`
- [ ] Add out-of-sample forecast evaluation vs. realized vol
- [ ] Write up findings at the top of the notebook / in this README
