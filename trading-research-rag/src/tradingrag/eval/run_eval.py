"""Runs the full retrieval eval and (optionally) gates CI on a regression.

`make eval` runs this to print the metrics table. `make eval-gate` additionally
compares the hybrid Recall@10 mean against `config/eval/baseline_metrics.json`
and exits non-zero if it has regressed beyond `REGRESSION_TOLERANCE` — the
production-engineering piece, not just a one-off notebook number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tradingrag.config import get_settings
from tradingrag.eval.gold import GoldQuery, load_gold_json
from tradingrag.eval.metrics import (
    bootstrap_ci,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from tradingrag.retrieval.index import Index

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "eval"
BASELINE_PATH = CONFIG_DIR / "baseline_metrics.json"
REGRESSION_TOLERANCE = 0.02  # absolute drop in hybrid Recall@10 allowed before CI fails
K = 10
MODES = ("bm25", "dense", "hybrid")


def _load_all_gold() -> dict[str, list[GoldQuery]]:
    return {
        "analyst": load_gold_json(CONFIG_DIR / "analyst_gold.json", tier="analyst"),
        "heading": load_gold_json(CONFIG_DIR / "heading_gold.json", tier="heading"),
    }


def _validate_gold_ids_exist(gold_by_tier: dict[str, list[GoldQuery]], index: Index) -> None:
    known_ids = {c.chunk_id for c in index.chunks}
    missing = sorted(
        {
            chunk_id
            for queries in gold_by_tier.values()
            for q in queries
            for chunk_id in q.relevant_chunk_ids
            if chunk_id not in known_ids
        }
    )
    if missing:
        raise ValueError(
            f"{len(missing)} gold chunk_ids are not present in the current index "
            f"(corpus changed since the gold set was written?): {missing[:5]}..."
        )


def evaluate(index: Index, queries: list[GoldQuery], mode: str) -> dict[str, list[float]]:
    metric_names = ("recall_at_10", "precision_at_10", "mrr", "ndcg_at_10")
    per_query: dict[str, list[float]] = {name: [] for name in metric_names}
    for gold in queries:
        relevant = set(gold.relevant_chunk_ids)
        retrieved = [r.chunk.chunk_id for r in index.search(gold.query, top_k=K, mode=mode)]
        per_query["recall_at_10"].append(recall_at_k(retrieved, relevant, K))
        per_query["precision_at_10"].append(precision_at_k(retrieved, relevant, K))
        per_query["mrr"].append(reciprocal_rank(retrieved, relevant))
        per_query["ndcg_at_10"].append(ndcg_at_k(retrieved, relevant, K))
    return per_query


def summarize(per_query: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    summary = {}
    for metric_name, values in per_query.items():
        mean, lo, hi = bootstrap_ci(values)
        summary[metric_name] = {"mean": mean, "ci_lo": lo, "ci_hi": hi}
    return summary


def run_full_eval() -> dict[str, dict[str, dict[str, dict[str, float]]]]:
    settings = get_settings()
    index = Index.load(settings.index_dir)
    gold_by_tier = _load_all_gold()
    _validate_gold_ids_exist(gold_by_tier, index)

    results: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for tier_name, queries in gold_by_tier.items():
        results[tier_name] = {}
        for mode in MODES:
            results[tier_name][mode] = summarize(evaluate(index, queries, mode))

    all_queries = [q for queries in gold_by_tier.values() for q in queries]
    results["pooled"] = {mode: summarize(evaluate(index, all_queries, mode)) for mode in MODES}
    return results


def print_table(results: dict[str, dict[str, dict[str, dict[str, float]]]]) -> None:
    for tier_name, by_mode in results.items():
        print(f"\n=== {tier_name} ===")
        print(f"{'mode':<8}{'recall@10':<22}{'precision@10':<22}{'mrr':<22}{'ndcg@10':<22}")
        for mode, metrics in by_mode.items():
            row = mode.ljust(8)
            for metric_name in ("recall_at_10", "precision_at_10", "mrr", "ndcg_at_10"):
                m = metrics[metric_name]
                cell = f"{m['mean']:.3f} [{m['ci_lo']:.3f},{m['ci_hi']:.3f}]"
                row += cell.ljust(22)
            print(row)


def check_regression_gate(results: dict[str, dict[str, dict[str, dict[str, float]]]]) -> bool:
    if not BASELINE_PATH.exists():
        print(f"no baseline at {BASELINE_PATH}; run with --write-baseline first")
        return False
    baseline = json.loads(BASELINE_PATH.read_text())
    current = results["pooled"]["hybrid"]["recall_at_10"]["mean"]
    baseline_value = baseline["pooled_hybrid_recall_at_10"]
    regressed = current < baseline_value - REGRESSION_TOLERANCE
    print(f"hybrid pooled recall@10: current={current:.4f} baseline={baseline_value:.4f}")
    if regressed:
        print(f"REGRESSION: dropped more than {REGRESSION_TOLERANCE} below baseline")
    return not regressed


def write_baseline(results: dict[str, dict[str, dict[str, dict[str, float]]]]) -> None:
    value = results["pooled"]["hybrid"]["recall_at_10"]["mean"]
    BASELINE_PATH.write_text(json.dumps({"pooled_hybrid_recall_at_10": value}, indent=2) + "\n")
    print(f"wrote baseline: pooled_hybrid_recall_at_10={value:.4f} -> {BASELINE_PATH}")


def main() -> None:
    results = run_full_eval()
    print_table(results)

    if "--write-baseline" in sys.argv:
        write_baseline(results)
        return

    if "--gate" in sys.argv:
        ok = check_regression_gate(results)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
