#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame-sheets", required=True, type=Path)
    parser.add_argument("--roster-sheets", required=True, type=Path)
    parser.add_argument("--yunet", required=True, type=Path)
    parser.add_argument("--sface", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    detector = cv2.FaceDetectorYN.create(
        str(args.yunet), "", (320, 320), 0.5, 0.3, 5000
    )
    recognizer = cv2.FaceRecognizerSF.create(str(args.sface), "")

    def embed(path: Path):
        image = cv2.imread(str(path))
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is None:
            raise ValueError(f"no face in {path}")
        face = max(faces, key=lambda row: row[2] * row[3])
        vector = recognizer.feature(
            recognizer.alignCrop(image, face)
        ).ravel()
        return vector / np.linalg.norm(vector)

    timestamp_s = 1125
    frame_index = timestamp_s // 15
    frame_sheet = frame_index // 64 + 1
    frame_position = frame_index % 64
    frame_row, frame_column = divmod(frame_position, 8)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        query_path = work / "query.jpg"
        frame = Image.open(
            args.frame_sheets / f"sheet_{frame_sheet:02d}.jpg"
        )
        x = 2 + frame_column * 242
        y = 2 + frame_row * 137
        frame.crop((x, y, x + 240, y + 135)).save(query_path)
        query = embed(query_path)

        scores = {}
        for speaker_id in (212, 274):
            zero_based = speaker_id - 1
            sheet = zero_based // 36 + 1
            position = zero_based % 36
            row, column = divmod(position, 6)
            crop_path = work / f"speaker_{speaker_id:03d}.jpg"
            roster = Image.open(
                args.roster_sheets / f"roster_{sheet:02d}.jpg"
            )
            roster.crop(
                (
                    column * 260,
                    row * 275,
                    (column + 1) * 260,
                    (row + 1) * 275,
                )
            ).save(crop_path)
            scores[f"speaker_{speaker_id:03d}"] = round(
                float(query @ embed(crop_path)),
                6,
            )

    expected = "speaker_274"
    predicted = max(scores, key=scores.get)
    result = {
        "timestamp_s": timestamp_s,
        "source": "exact pixels from the attached 15-second frame-index sheet and attached readable roster sheets",
        "candidates": [
            "speaker_212",
            "speaker_274"
        ],
        "expected": expected,
        "predicted": predicted,
        "scores": scores,
        "margin": round(
            scores["speaker_274"] - scores["speaker_212"], 6
        ),
        "status": "pass" if predicted == expected else "fail",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
