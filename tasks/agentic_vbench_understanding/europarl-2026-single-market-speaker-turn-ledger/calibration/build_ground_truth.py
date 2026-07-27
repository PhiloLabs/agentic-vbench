#!/usr/bin/env python3
import argparse
import hashlib
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup

DEBATE_START = "09:59:32"
EXPECTED_RECORDS = 170
EXPECTED_TURNS = 86
EXPECTED_SPEAKERS = 79
MINIMUM_DURATION_S = 30
SEED = 20260715
TARGET_INTERNAL_ID = "2017076952270"
ROW = re.compile(
    r"^\s*(?P<name>\S(?:.*?\S)?)\s{2,}"
    r"(?P<role>.*?)\s+"
    r"(?P<duration>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<start>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2})\s*$"
)


@dataclass(frozen=True)
class Turn:
    name: str
    role: str
    duration: str
    start: str
    end: str


def clock_seconds(value):
    parsed = datetime.strptime(value, "%H:%M:%S")
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second


def parse_pdf(path):
    turns = []
    with pdfplumber.open(path) as document:
        if len(document.pages) != 3:
            raise ValueError("speaker list must contain three pages")
        for page in document.pages:
            lines = (page.extract_text(layout=True) or "").splitlines()
            for index, line in enumerate(lines):
                match = ROW.match(line)
                if match is None:
                    continue
                role = match.group("role").strip()
                if (
                    role.endswith(" of")
                    and index + 1 < len(lines)
                    and lines[index + 1].strip() == "the Commission"
                ):
                    role += " the Commission"
                turn = Turn(
                    name=match.group("name").strip(),
                    role=role,
                    duration=match.group("duration"),
                    start=match.group("start"),
                    end=match.group("end"),
                )
                if clock_seconds(turn.duration) != (
                    clock_seconds(turn.end) - clock_seconds(turn.start)
                ):
                    raise ValueError("PDF duration mismatch")
                turns.append(turn)
    if len(turns) != EXPECTED_RECORDS:
        raise ValueError(f"expected {EXPECTED_RECORDS} PDF records")
    return turns


def text(element, selector):
    selected = element.select_one(selector)
    if selected is None:
        raise ValueError(f"missing {selector}")
    return " ".join(selected.get_text(" ", strip=True).split())


def parse_html(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    link = soup.find(
        "a",
        href=re.compile(rf"internalEPId={TARGET_INTERNAL_ID}(?:&|$)"),
    )
    if link is None:
        raise ValueError("target debate not found")
    heading = link.find_parent("h3")
    section = heading.find_next_sibling("div")
    turns = []
    for notice in section.select("div.notice_debates"):
        times = [item.get_text(strip=True) for item in notice.select("time")]
        turns.append(
            Turn(
                name=text(notice, "p.title"),
                role=text(notice, "p.role").removeprefix("Role :").strip(),
                duration=text(notice, "p.duration"),
                start=times[0],
                end=times[1],
            )
        )
    if len(turns) != EXPECTED_RECORDS:
        raise ValueError(f"expected {EXPECTED_RECORDS} HTML records")
    return turns


def build(pdf_path, html_path):
    pdf_turns = parse_pdf(pdf_path)
    html_turns = parse_html(html_path)
    if pdf_turns != html_turns:
        raise ValueError("PDF and HTML records differ")

    selected = [
        turn
        for turn in pdf_turns
        if turn.role != "Vice-President"
        and clock_seconds(turn.duration) >= MINIMUM_DURATION_S
    ]
    speakers = list(dict.fromkeys(turn.name for turn in selected))
    random.Random(SEED).shuffle(speakers)
    mapping = {
        name: f"speaker_{index:03d}"
        for index, name in enumerate(speakers, start=1)
    }
    debate_start = clock_seconds(DEBATE_START)
    turns = [
        {
            "turn_index": index,
            "speaker_id": mapping[turn.name],
            "start_time_s": float(clock_seconds(turn.start) - debate_start),
            "end_time_s": float(clock_seconds(turn.end) - debate_start),
        }
        for index, turn in enumerate(selected, start=1)
    ]
    if len(turns) != EXPECTED_TURNS or len(speakers) != EXPECTED_SPEAKERS:
        raise ValueError("unexpected selected turn or speaker count")
    return {"turns": turns}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build(args.pdf, args.html)
    rendered = json.dumps(result, indent=2) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "turns": len(result["turns"]),
                "speakers": len(
                    {turn["speaker_id"] for turn in result["turns"]}
                ),
                "sha256": hashlib.sha256(rendered.encode()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
