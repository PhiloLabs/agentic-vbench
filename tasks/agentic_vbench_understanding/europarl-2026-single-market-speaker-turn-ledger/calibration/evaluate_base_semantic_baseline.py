"""Evaluate card matching on a public perception-only solution without GT."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import whisper
from scipy.optimize import linear_sum_assignment

MEDIA_SHA256 = (
    "fef8b986d03d35d2d61b2ed8104f130dbc125f95cfee8704cee121cc5a2f4e8e"
)
MODEL_SHA256 = (
    "ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e"
)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def words(value: str) -> list[str]:
    return [word for word in normalize(value).split() if len(word) > 1]


def trigrams(value: str) -> set[str]:
    normalized = normalize(value).replace(" ", "_")
    return {
        normalized[index : index + 3]
        for index in range(max(0, len(normalized) - 2))
    }


def jaccard(first: set[str], second: set[str]) -> float:
    return len(first & second) / len(first | second) if first | second else 0.0


def tfidf_vectors(documents: list[str]) -> list[dict[str, float]]:
    counts = [Counter(words(document)) for document in documents]
    document_frequency = Counter(
        token for count in counts for token in count
    )
    total = len(documents)
    vectors = []
    for count in counts:
        vector = {
            token: frequency
            * (math.log((total + 1) / (document_frequency[token] + 1)) + 1)
            for token, frequency in count.items()
        }
        norm = math.sqrt(sum(value * value for value in vector.values()))
        vectors.append(
            {
                token: value / norm
                for token, value in vector.items()
            }
            if norm
            else {}
        )
    return vectors


def cosine(first: dict[str, float], second: dict[str, float]) -> float:
    if len(first) > len(second):
        first, second = second, first
    return sum(value * second.get(token, 0.0) for token, value in first.items())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--perception-solution", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--model-cache", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    args.work.mkdir(parents=True, exist_ok=True)
    transcript_cache = args.work / "transcripts"
    transcript_cache.mkdir(exist_ok=True)

    solution = json.loads(args.perception_solution.read_text())
    rows = solution["turns"]
    cards = json.loads(args.cards.read_text())["excerpts"]
    model = whisper.load_model(
        "base", download_root=str(args.model_cache)
    )
    transcripts = []
    for index, row in enumerate(rows, start=1):
        start = row["start_time_s"] + 2
        duration = max(
            5.0,
            row["end_time_s"] - row["start_time_s"] - 4,
        )
        key = hashlib.sha256(
            (
                f"{MEDIA_SHA256}|{MODEL_SHA256}|translate|"
                f"{start:.3f}|{duration:.3f}"
            ).encode()
        ).hexdigest()
        cache = transcript_cache / f"{key}.json"
        if cache.is_file():
            result = json.loads(cache.read_text())
        else:
            audio = args.work / f"turn_{index:03d}.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(start),
                    "-i",
                    str(args.media),
                    "-t",
                    str(duration),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(audio),
                ],
                check=True,
            )
            translated = model.transcribe(
                str(audio),
                language=row["language_code"],
                fp16=False,
                task="translate",
                temperature=0,
            )["text"].strip()
            result = {
                "start_time_s": start,
                "duration_s": duration,
                "language_code": row["language_code"],
                "translation": translated,
            }
            cache.write_text(json.dumps(result, ensure_ascii=False) + "\n")
            audio.unlink()
        transcripts.append(result["translation"])
        print(f"{index}/{len(rows)}", flush=True)

    card_texts = [item["text"] for item in cards]
    (args.work / "translations.json").write_text(
        json.dumps(
            {
                "model": "whisper-base",
                "media_sha256": MEDIA_SHA256,
                "turns": [
                    {
                        "predicted_turn_index": index,
                        "start_time_s": row["start_time_s"],
                        "end_time_s": row["end_time_s"],
                        "predicted_language_code": row["language_code"],
                        "translation": translation,
                    }
                    for index, (row, translation) in enumerate(
                        zip(rows, transcripts, strict=True),
                        start=1,
                    )
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    vectors = tfidf_vectors(transcripts + card_texts)
    transcript_vectors = vectors[: len(transcripts)]
    card_vectors = vectors[len(transcripts) :]
    transcript_words = [set(words(value)) for value in transcripts]
    card_words = [set(words(value)) for value in card_texts]
    transcript_grams = [trigrams(value) for value in transcripts]
    card_grams = [trigrams(value) for value in card_texts]
    scores = np.zeros((len(rows), len(cards)), dtype=np.float64)
    for row_index in range(len(rows)):
        for card_index in range(len(cards)):
            scores[row_index, card_index] = (
                0.55
                * cosine(
                    transcript_vectors[row_index],
                    card_vectors[card_index],
                )
                + 0.30
                * jaccard(
                    transcript_grams[row_index],
                    card_grams[card_index],
                )
                + 0.15
                * jaccard(
                    transcript_words[row_index],
                    card_words[card_index],
                )
            )

    row_indices, card_indices = linear_sum_assignment(
        scores, maximize=True
    )
    card_by_row = {
        int(row_index): cards[int(card_index)]["excerpt_id"]
        for row_index, card_index in zip(
            row_indices, card_indices, strict=True
        )
    }
    for row_index, row in enumerate(rows):
        row["excerpt_id"] = card_by_row[row_index]
    args.output.write_text(json.dumps(solution, indent=2) + "\n")
    (args.work / "matching.json").write_text(
        json.dumps(
            {
                "media_sha256": MEDIA_SHA256,
                "model_sha256": MODEL_SHA256,
                "model": "whisper-base",
                "window": "full predicted turn minus 2 seconds per edge",
                "matcher": (
                    "maximum-weight one-to-one assignment over "
                    "0.55 TF-IDF cosine + 0.30 character-trigram Jaccard "
                    "+ 0.15 word Jaccard"
                ),
                "assignments": [
                    {
                        "turn_index": row_index + 1,
                        "excerpt_id": card_by_row[row_index],
                        "score": round(
                            float(
                                scores[
                                    row_index,
                                    next(
                                        index
                                        for index, item in enumerate(cards)
                                        if item["excerpt_id"]
                                        == card_by_row[row_index]
                                    ),
                                ]
                            ),
                            6,
                        ),
                    }
                    for row_index in range(len(rows))
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
