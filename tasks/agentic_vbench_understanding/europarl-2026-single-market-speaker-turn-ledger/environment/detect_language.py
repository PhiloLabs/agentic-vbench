#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

import torch
from speechbrain.inference.classifiers import EncoderClassifier

LANGUAGES = [
    "bg",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "es",
    "fi",
    "fr",
    "hr",
    "hu",
    "it",
    "lt",
    "lv",
    "nl",
    "pl",
    "pt",
    "ro",
    "sk",
    "sl",
    "sv",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="+", type=Path)
    args = parser.parse_args()

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    classifier = EncoderClassifier.from_hparams(
        source="/opt/voxlingua107",
        savedir="/opt/voxlingua107",
        run_opts={"device": "cpu"},
    )
    label_to_index = {
        label.split(":", 1)[0]: index
        for index, label in classifier.hparams.label_encoder.ind2lab.items()
    }
    indices = torch.tensor([label_to_index[code] for code in LANGUAGES])
    results = []
    for path in args.audio:
        probabilities, _, _, _ = classifier.classify_file(str(path))
        restricted = probabilities[0, indices]
        order = torch.argsort(restricted, descending=True)[:3]
        results.append(
            {
                "file": str(path),
                "language_code": LANGUAGES[int(order[0])],
                "top3": [
                    {
                        "language_code": LANGUAGES[int(index)],
                        "score": round(float(restricted[index]), 6),
                    }
                    for index in order
                ],
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
