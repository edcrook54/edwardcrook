.PHONY: install up down logs psql ingest-once lint typecheck test image notebooks bars train backtest load-scores price-now

install:
	python -m pip install -e ".[dev]"

up:
	docker compose up -d --wait

down:
	docker compose down

logs:
	docker compose logs -f ingest

ingest-once:
	python -m pmq.ingest once

bars:
	python -c "from pmq.crypto import ticks; from pmq.config import get_settings as g; s=g(); [ticks.build_bar_cache(s.ticks_dir/f'{a}USD.csv', s.bars_dir/f'{a}_1m.parquet') for a in ('XBT','ETH','SOL')]"

train:
	python -m pmq.crypto.train --config config/btc.yaml

backtest:
	for a in btc eth sol; do python -m pmq.crypto.backtest --config config/$$a.yaml; done

load-scores:
	python -m pmq.crypto.load_scores

price-now:
	python -m pmq.pricer.run dry

notebooks:
	jupyter lab notebooks/

psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-pmq} -d $${POSTGRES_DB:-pmq}

lint:
	ruff check . && ruff format --check .

typecheck:
	mypy

test:
	pytest

image:
	docker build -f docker/Dockerfile.app -t pmq-app:dev .
