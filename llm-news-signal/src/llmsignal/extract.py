"""Entry point for `make extract`: run the LLM extraction over every FOMC
statement and write the results (plus provenance metadata) to disk.

Requires `ANTHROPIC_API_KEY` (or `LLMSIGNAL_ANTHROPIC_API_KEY`) unless every
statement is already in the recorded-response cache.
"""

from __future__ import annotations

import json

from llmsignal.config import get_settings
from llmsignal.extraction.client import ExtractionClient


def main() -> None:
    settings = get_settings()
    statements = json.loads(settings.fomc_statements_path.read_text())

    client = ExtractionClient(
        model=settings.model,
        api_key=settings.anthropic_api_key,
        recorded_responses_path=settings.recorded_responses_path,
    )

    records = []
    for statement in statements:
        result, metadata = client.extract(statement["statement_excerpt"])
        records.append(
            {
                "meeting_date": statement["meeting_date"],
                **result.model_dump(),
                "metadata": metadata,
            }
        )
        source = "cache" if metadata["from_cache"] else "live"
        print(f"{statement['meeting_date']}: {result.sentiment} ({source})")

    settings.extractions_path.parent.mkdir(parents=True, exist_ok=True)
    settings.extractions_path.write_text(json.dumps(records, indent=2))
    print(f"wrote {len(records)} extractions -> {settings.extractions_path}")


if __name__ == "__main__":
    main()
