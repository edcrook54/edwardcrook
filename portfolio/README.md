# Ed Crook — Quant / Fintech Portfolio

Trading & Operations Transformation Analyst at IG Group, building toward
quantitative strategy or technical product roles. This repo collects
self-directed projects demonstrating financially-literate, production-grade
ML/AI engineering — not just notebooks that run once.

One shared environment (`uv` + `pyproject.toml`), one CI pipeline, one
Docker image — every project is independently browsable but built the
same way.

## Projects

| Project | What it demonstrates | Status |
|---|---|---|
| [`options-bma-sdf`](projects/options-bma-sdf) | Bayesian model averaging SDF for equity options (replication + extension of Käfer, Mörke, Weigert & Wiest, 2026), custom Gibbs sampler, delta-hedged return construction | 🚧 in progress |
| [`garch-vol-model`](projects/garch-vol-model) | Volatility forecasting with GARCH family models | 🚧 in progress |
| [`credit-risk-service`](projects/credit-risk-service) | Productionised credit/lending risk scoring service (API + model) | 🚧 planned |

## Working with this repo

```bash
# clone, then from repo root:
uv sync --extra <project-extra> --extra dev   # e.g. --extra bma-sdf
uv run jupyter lab
```

See each project's own README for scope, data sources, and how to run it.

## Stack

Python (uv, ruff, mypy, pytest), Docker, GitHub Actions CI. C++/pybind11
components (where used) are documented in the relevant project's README.
