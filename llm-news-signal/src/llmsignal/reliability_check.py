"""Entry point for `make reliability`: validates the LLM extractions against
my own independent hand labels (`data/reliability_labels.json`) before
trusting them in any downstream statistical test.

`run_reliability_check` is also imported directly by `analyze.py`, which
refuses to proceed if this doesn't pass - CLAUDE.md's non-negotiable rule is
that reliability must be validated *before* downstream claims are trusted,
not merely computed alongside them, so that has to be an enforced gate, not
just a separate `make` target someone might forget to run.
"""

from __future__ import annotations

import json
from pathlib import Path

from llmsignal.config import get_settings
from llmsignal.reliability.kappa import cohens_kappa, continuous_agreement

# Landis & Koch (1977): kappa > 0.4 is "moderate" agreement, the usual
# minimum bar for treating a categorical labeler as usable at all.
KAPPA_THRESHOLD = 0.4


def run_reliability_check(
    extractions_path: Path, reliability_labels_path: Path
) -> dict[str, object]:
    if not extractions_path.exists():
        raise SystemExit(
            f"no extractions found at {extractions_path} - run `make extract` first "
            "(requires ANTHROPIC_API_KEY, or a fully-populated recorded-response cache)"
        )

    extractions = {r["meeting_date"]: r for r in json.loads(extractions_path.read_text())}
    labels = {r["meeting_date"]: r for r in json.loads(reliability_labels_path.read_text())}
    common_dates = sorted(set(extractions) & set(labels))
    if not common_dates:
        raise SystemExit("no overlapping meeting_dates between extractions and reliability labels")

    llm_sentiment = [extractions[d]["sentiment"] for d in common_dates]
    human_sentiment = [labels[d]["sentiment"] for d in common_dates]
    kappa = cohens_kappa(llm_sentiment, human_sentiment)

    llm_scores = [extractions[d]["hawkish_dovish_score"] for d in common_dates]
    human_scores = [labels[d]["hawkish_dovish_score"] for d in common_dates]
    agreement = continuous_agreement(llm_scores, human_scores)

    return {"n": len(common_dates), "kappa": kappa, **agreement, "passes": kappa > KAPPA_THRESHOLD}


def main() -> None:
    settings = get_settings()
    result = run_reliability_check(settings.extractions_path, settings.reliability_labels_path)

    verdict = "PASS" if result["passes"] else "FAIL"
    print(f"n = {result['n']}")
    print(
        f"Cohen's kappa (sentiment categories): {result['kappa']:.3f}  "
        f"[{verdict}: threshold is kappa > {KAPPA_THRESHOLD} (Landis & Koch 'moderate' agreement)]"
    )
    print(
        f"hawkish_dovish_score agreement: pearson_r={result['pearson_r']:.3f} "
        f"mae={result['mae']:.3f} bias={result['bias']:.3f}"
    )
    if not result["passes"]:
        raise SystemExit(
            f"kappa={result['kappa']:.3f} does not clear the {KAPPA_THRESHOLD} threshold - "
            "do not trust `make analyze`'s output until this improves (better prompt, "
            "or re-examine the hand labels for ambiguous cases)"
        )


if __name__ == "__main__":
    main()
