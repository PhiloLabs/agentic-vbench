#!/usr/bin/env python3
"""Offline shortcut diagnostic; never reads verifier ground truth."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from speechbrain.inference.classifiers import EncoderClassifier

HOP_S = 0.02
THRESHOLD_DB = -38.0
MINIMUM_SILENCE_S = 2.5
MINIMUM_TURN_S = 28.0
FRAME_FRACTIONS = (0.20, 0.35, 0.50, 0.65, 0.80)
LANGUAGE_CODES = (
    "bg cs da de el en es fi fr hr hu it lt lv nl pl pt ro sk sl sv"
).split()


def run(*arguments: str) -> None:
    subprocess.run(arguments, check=True)


def detect_segments(media: Path, work: Path) -> list[tuple[float, float]]:
    raw = work / "floor.raw"
    run(
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(media),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "s16le",
        str(raw),
    )
    samples = np.fromfile(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = int(HOP_S * 16000)
    count = len(samples) // hop
    frames = samples[: count * hop].reshape(count, hop)
    decibels = 20 * np.log10(
        np.sqrt((frames**2).mean(axis=1)) + 1e-12
    )
    speech = decibels > THRESHOLD_DB
    cuts = np.flatnonzero(np.diff(speech.astype(np.int8)))
    edges = np.concatenate(([0], cuts + 1, [len(speech)]))
    merged: list[tuple[int, int, bool]] = []
    for start, end in zip(edges[:-1], edges[1:], strict=True):
        voiced = bool(speech[start])
        if (
            merged
            and not voiced
            and (end - start) * HOP_S < MINIMUM_SILENCE_S
            and merged[-1][2]
        ):
            merged[-1] = (merged[-1][0], end, True)
        elif merged and voiced and merged[-1][2]:
            merged[-1] = (merged[-1][0], end, True)
        else:
            merged.append((start, end, voiced))
    return [
        (round(start * HOP_S, 2), round(end * HOP_S, 2))
        for start, end, voiced in merged
        if voiced and (end - start) * HOP_S >= MINIMUM_TURN_S
    ]


def face_embedder(yunet: Path, sface: Path):
    detector = cv2.FaceDetectorYN.create(
        str(yunet), "", (320, 320), 0.6, 0.3, 5000
    )
    recognizer = cv2.FaceRecognizerSF.create(str(sface), "")

    def embed(image):
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        face = max(faces, key=lambda row: row[2] * row[3])
        vector = recognizer.feature(
            recognizer.alignCrop(image, face)
        ).ravel()
        return vector / np.linalg.norm(vector)

    return embed


def match_faces(
    media: Path,
    roster: Path,
    segments: list[tuple[float, float]],
    yunet: Path,
    sface: Path,
    work: Path,
) -> list[dict]:
    embed = face_embedder(yunet, sface)
    speaker_ids = []
    vectors = []
    for portrait in sorted(roster.glob("speaker_*.jpg")):
        vector = embed(cv2.imread(str(portrait)))
        if vector is not None:
            speaker_ids.append(portrait.stem)
            vectors.append(vector)
    matrix = np.vstack(vectors)
    rows = []
    for start, end in segments:
        best_score = -1.0
        best_id = speaker_ids[0]
        for fraction in FRAME_FRACTIONS:
            frame = work / "frame.jpg"
            run(
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                f"{start + (end - start) * fraction:.2f}",
                "-i",
                str(media),
                "-frames:v",
                "1",
                str(frame),
            )
            vector = embed(cv2.imread(str(frame)))
            if vector is None:
                continue
            scores = matrix @ vector
            index = int(np.argmax(scores))
            if float(scores[index]) > best_score:
                best_score = float(scores[index])
                best_id = speaker_ids[index]
        rows.append(
            {
                "start_time_s": start,
                "end_time_s": end,
                "speaker_id": best_id,
            }
        )
    return rows


def classify_languages(
    media: Path,
    rows: list[dict],
    model_path: Path,
    work: Path,
) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    classifier = EncoderClassifier.from_hparams(
        source=str(model_path),
        savedir=str(model_path),
        run_opts={"device": "cpu"},
    )
    labels = {
        label.split(":", 1)[0]: index
        for index, label in classifier.hparams.label_encoder.ind2lab.items()
    }
    permitted = torch.tensor([labels[code] for code in LANGUAGE_CODES])
    for row in rows:
        start = row["start_time_s"] + 2
        end = row["end_time_s"] - 2
        duration = min(60.0, end - start)
        start = max(start, (start + end) / 2 - duration / 2)
        audio = work / "language.wav"
        run(
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            f"{start:.2f}",
            "-t",
            f"{duration:.2f}",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio),
        )
        probabilities, _, _, _ = classifier.classify_file(str(audio))
        row["language_code"] = LANGUAGE_CODES[
            int(torch.argmax(probabilities[0, permitted]))
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--roster", required=True, type=Path)
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--yunet", required=True, type=Path)
    parser.add_argument("--sface", required=True, type=Path)
    parser.add_argument("--voxlingua", required=True, type=Path)
    parser.add_argument("--whisper-cache", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)

    rows = match_faces(
        args.media,
        args.roster,
        detect_segments(args.media, args.work),
        args.yunet,
        args.sface,
        args.work,
    )
    classify_languages(args.media, rows, args.voxlingua, args.work)
    turns = [
        {"turn_index": index, **row}
        for index, row in enumerate(rows, start=1)
    ]
    perception = args.work / "perception_solution.json"
    perception.write_text(json.dumps({"turns": turns}, indent=2) + "\n")
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("evaluate_base_semantic_baseline.py")),
            "--media",
            str(args.media),
            "--perception-solution",
            str(perception),
            "--cards",
            str(args.cards),
            "--model-cache",
            str(args.whisper_cache),
            "--work",
            str(args.work / "semantic_matching"),
            "--output",
            str(args.output),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
