#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SEED = 20260728


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-mapping", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--answer", required=True, type=Path)
    args = parser.parse_args()

    source_rows = json.loads(args.source_mapping.read_text())["turns"]
    cards = json.loads(args.cards.read_text())["cards"]
    card_by_excerpt = {
        card["excerpt_id"]: card for card in cards
    }
    transcript_order = list(range(len(source_rows)))
    random.Random(SEED).shuffle(transcript_order)
    transcript_id_by_turn = {
        source_index: f"transcript_{position + 1:03d}"
        for position, source_index in enumerate(transcript_order)
    }
    transcripts = [
        {
            "transcript_id": transcript_id_by_turn[source_index],
            "language_code": source_rows[source_index]["language_code"],
            "text": source_rows[source_index]["full_text_private"],
        }
        for source_index in transcript_order
    ]
    card_rows = [
        {
            "card_id": card["card_id"],
            "text": card["text"],
        }
        for card in cards
    ]
    random.Random(SEED + 1).shuffle(card_rows)

    prompt = f"""# Semantic-card ceiling control

This is not the benchmark task. You receive 86 complete official intervention
transcripts in their original languages and 86 shuffled English inference cards.
Each card is entailed by exactly one transcript. Match every card to exactly one
transcript using multilingual semantic reasoning. Do not use the internet, public
figures, speaker identity, or turn order. The identifiers are independently
shuffled and carry no relationship.

Write `/workspace/output/solution.json`:

```json
{{
  "matches": [
    {{"card_id": "v4_card_001", "transcript_id": "transcript_001"}}
  ]
}}
```

Requirements:
- exactly 86 rows;
- every supplied card_id exactly once;
- every supplied transcript_id exactly once;
- use only the content below.

## Cards

{json.dumps(card_rows, ensure_ascii=False, separators=(",", ":"))}

## Complete official transcripts

{json.dumps(transcripts, ensure_ascii=False, separators=(",", ":"))}
"""
    args.prompt.write_text(prompt)
    args.answer.write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "card_id": card_by_excerpt[
                            row["excerpt_id"]
                        ]["card_id"],
                        "transcript_id": transcript_id_by_turn[index],
                    }
                    for index, row in enumerate(source_rows)
                ]
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
