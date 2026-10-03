.PHONY: install extract reliability analyze lint typecheck test

install:
	python -m pip install -e ".[dev,notebooks]"

extract:
	python -m llmsignal.extract

reliability:
	python -m llmsignal.reliability_check

analyze:
	python -m llmsignal.analyze

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest
