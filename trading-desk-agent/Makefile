.PHONY: install eval-live lint typecheck test

install:
	python -m pip install -e ".[dev]"

eval-live:
	python -m deskagent.eval.run_eval

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest
