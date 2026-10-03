"""One-off script that writes my own hand-labels (not the LLM's) for every
FOMC statement, used to validate LLM extraction reliability. Read directly
against the statement text in data/fomc_statements.json, independently of
any LLM output — see README "Scope and limits" for the labeling rationale
(action + rate-path position sets a baseline; forward-guidance language
shifts it) and a disclosed limitation (surprise is a regime-transition
heuristic, not real-time market-implied probabilities).

Not part of the installed package - this is a provenance record for how
data/reliability_labels.json was produced, kept for reproducibility/audit,
not meant to be re-run to reproduce different numbers (it would produce the
same file every time; it's not a general tool).
"""

import json
from pathlib import Path

LABELS = [
    # (meeting_date, score, surprise, sentiment, confidence, rationale)
    ("2022-01-26", 0.5, 0.3, "hawkish", 0.85, "Hold, but first explicit 'soon appropriate to raise' pivot."),
    ("2022-03-16", 0.6, 0.3, "hawkish", 0.85, "First hike (25bp); well-telegraphed by January's pivot."),
    ("2022-05-04", 0.65, 0.35, "hawkish", 0.85, "Step-up to 50bp; 'highly attentive to inflation risks' added."),
    ("2022-06-15", 0.75, 0.55, "hawkish", 0.9, "Historic 75bp hike, biggest step yet; 'strongly committed' added."),
    ("2022-07-27", 0.7, 0.2, "hawkish", 0.85, "Second consecutive 75bp hike; continuation of established pace."),
    ("2022-09-21", 0.7, 0.15, "hawkish", 0.85, "Third consecutive 75bp hike; fully expected continuation."),
    ("2022-11-02", 0.55, 0.3, "hawkish", 0.75, "Fourth 75bp hike, but new 'cumulative tightening/lags' language hints at future deceleration."),
    ("2022-12-14", 0.45, 0.35, "hawkish", 0.8, "Step down to 50bp from 75bp; meaningful deceleration."),
    ("2023-02-01", 0.35, 0.2, "hawkish", 0.8, "Further deceleration to 25bp; 'inflation has eased somewhat' is first softening."),
    ("2023-03-22", 0.25, 0.3, "hawkish", 0.7, "25bp hike but guidance softened to 'may be appropriate'; banking-stress caveat added."),
    ("2023-05-03", 0.15, 0.3, "hawkish", 0.7, "25bp hike but 'may be appropriate' now fully conditional; read as signaling a pause."),
    ("2023-06-14", 0.0, 0.45, "neutral", 0.75, "First hold after 10 consecutive hikes; genuine regime pivot."),
    ("2023-07-26", 0.35, 0.45, "hawkish", 0.75, "Hike resumes after the pause ('hawkish skip'); reversal is itself surprising."),
    ("2023-09-20", 0.05, 0.2, "neutral", 0.75, "Second hold; 'job gains have slowed' but inflation-risk language unchanged."),
    ("2023-11-01", 0.0, 0.15, "neutral", 0.75, "Third hold; well-established pause, minimal new signal."),
    ("2023-12-13", -0.1, 0.2, "neutral", 0.7, "First explicit 'inflation has eased over the past year' framing; dovish tilt (this was the 'dot plot pivot' meeting)."),
    ("2024-01-31", -0.15, 0.25, "neutral", 0.75, "First explicit mention that cuts are being considered, even while saying not yet appropriate."),
    ("2024-03-20", -0.15, 0.1, "neutral", 0.75, "Near-identical language to January; repeat, low surprise."),
    ("2024-05-01", 0.1, 0.3, "neutral", 0.7, "'Lack of further progress' on inflation reverses the recent softening trend."),
    ("2024-06-12", -0.05, 0.2, "neutral", 0.7, "'Modest further progress' - improvement from May's 'lack of progress'."),
    ("2024-07-31", -0.25, 0.3, "dovish", 0.75, "New 'risks to both sides' framing drops the inflation-only focus; sets up the September cut."),
    ("2024-09-18", -0.6, 0.6, "dovish", 0.85, "First cut of the cycle, and a 50bp cut (vs. the more typical 25bp) - high surprise on size."),
    ("2024-11-07", -0.35, 0.3, "dovish", 0.8, "25bp cut; deceleration in pace from September's 50bp."),
    ("2024-12-18", -0.15, 0.35, "neutral", 0.7, "25bp cut but 'extent and timing' language reads cautious; markets took this as hawkish-leaning guidance alongside the cut."),
    ("2025-01-29", 0.0, 0.35, "neutral", 0.75, "First hold after three consecutive cuts; genuine pause signal."),
    ("2025-03-19", 0.0, 0.1, "neutral", 0.75, "Second hold; 'uncertainty has increased' is the only new note."),
    ("2025-05-07", -0.05, 0.25, "neutral", 0.7, "New explicit dual-risk framing: 'risks of higher unemployment AND higher inflation have risen'."),
    ("2025-06-18", 0.0, 0.15, "neutral", 0.75, "'Uncertainty has diminished but remains elevated' - slight de-escalation."),
    ("2025-07-30", -0.1, 0.2, "neutral", 0.7, "'Growth moderated in the first half' - a growth-outlook downgrade."),
    ("2025-09-17", -0.4, 0.4, "dovish", 0.8, "First cut after six holds; 'downside risks to employment have risen' justification."),
    ("2025-10-29", -0.45, 0.3, "dovish", 0.8, "Second consecutive cut, plus announced end of balance-sheet runoff (QT) - an added dovish/liquidity signal."),
    ("2025-12-10", -0.5, 0.35, "dovish", 0.8, "Third consecutive cut, plus a new reserve-management Treasury-purchase program - further dovish/liquidity easing."),
    ("2026-01-28", 0.0, 0.3, "neutral", 0.75, "First hold after three cuts; pause signal."),
    ("2026-03-18", 0.0, 0.15, "neutral", 0.7, "New Middle East geopolitical-risk mention added; otherwise unchanged."),
    ("2026-04-29", 0.15, 0.2, "neutral", 0.7, "Inflation concern escalates, explicitly tied to global energy prices from the geopolitical shock."),
    ("2026-06-17", 0.2, 0.3, "neutral", 0.6, "Notably terser statement format/style shift; 'will deliver price stability' reads as a harder commitment despite holding."),
    ("2026-07-29", 0.15, 0.15, "neutral", 0.65, "Same terse format repeated; less surprising now that it's established."),
    ("2026-09-16", 0.55, 0.6, "hawkish", 0.8, "Hike resumes after a cutting-then-holding regime; a major, surprising reversal."),
]


def main() -> None:
    out_path = Path(__file__).resolve().parents[1] / "data" / "reliability_labels.json"
    records = [
        {
            "meeting_date": date,
            "hawkish_dovish_score": score,
            "surprise_magnitude": surprise,
            "sentiment": sentiment,
            "confidence": confidence,
            "rationale": rationale,
        }
        for date, score, surprise, sentiment, confidence, rationale in LABELS
    ]
    out_path.write_text(json.dumps(records, indent=2) + "\n")
    print(f"wrote {len(records)} hand labels -> {out_path}")


if __name__ == "__main__":
    main()
