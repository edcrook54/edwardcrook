.PHONY: install index eval eval-gate eval-baseline sweep serve lint typecheck test

install:
	python -m pip install -e ".[dev,notebooks]"

index:
	python -m tradingrag.build_index

eval:
	python -m tradingrag.eval.run_eval

eval-gate:
	python -m tradingrag.eval.run_eval --gate

eval-baseline:
	python -m tradingrag.eval.run_eval --write-baseline

sweep:
	python -m tradingrag.eval.sweep

serve:
	uvicorn tradingrag.api:app --reload --port 8010

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest
