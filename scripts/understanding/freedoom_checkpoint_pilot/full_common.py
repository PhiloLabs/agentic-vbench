"""Shared package builder for the final Doom checkpoint task."""

from __future__ import annotations

import binascii
import struct
import subprocess
import zlib
import zipfile
from pathlib import Path


def _chunk(name: bytes, data: bytes) -> bytes:
    body = name + data
    return (
        struct.pack(">I", len(data))
        + body
        + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)
    )


def _png(
    width: int,
    height: int,
    pixels: bytearray,
    offset_x: int,
    offset_y: int,
) -> bytes:
    rows = b"".join(
        b"\0" + bytes(pixels[row * width * 4 : (row + 1) * width * 4])
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
        )
        + _chunk(b"grAb", struct.pack(">ii", offset_x, offset_y))
        + _chunk(b"IDAT", zlib.compress(rows, 9))
        + _chunk(b"IEND", b"")
    )


def _canvas(width: int, height: int) -> bytearray:
    return bytearray(width * height * 4)


def _pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
) -> None:
    if 0 <= x < width and 0 <= y < height:
        index = (y * width + x) * 4
        pixels[index : index + 4] = bytes(color)


def _rect(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(width, x1)):
            _pixel(pixels, width, height, x, y, color)


def _line(
    pixels: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int, int],
    thickness: int = 3,
) -> None:
    x0, y0 = start
    x1, y1 = end
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for step in range(steps + 1):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        _rect(
            pixels,
            width,
            height,
            x - thickness,
            y - thickness,
            x + thickness + 1,
            y + thickness + 1,
            color,
        )


def _switch_sprite(
    color: tuple[int, int, int, int],
    shape: str,
    active: bool,
) -> bytes:
    width, height = 64, 80
    pixels = _canvas(width, height)
    panel = (18, 22, 28, 255)
    rim = color if active else tuple(max(45, value // 3) for value in color[:3]) + (255,)
    _rect(pixels, width, height, 5, 8, 59, 75, (5, 7, 10, 235))
    _rect(pixels, width, height, 8, 11, 56, 72, panel)
    _rect(pixels, width, height, 8, 11, 56, 15, rim)
    _rect(pixels, width, height, 8, 68, 56, 72, rim)
    _rect(pixels, width, height, 8, 11, 12, 72, rim)
    _rect(pixels, width, height, 52, 11, 56, 72, rim)
    glyph = color if active else rim
    if shape == "circle":
        for y in range(24, 60):
            for x in range(16, 48):
                distance = (x - 32) ** 2 + (y - 42) ** 2
                if 145 <= distance <= 245:
                    _pixel(pixels, width, height, x, y, glyph)
    elif shape == "triangle":
        _line(pixels, width, height, (32, 22), (15, 58), glyph)
        _line(pixels, width, height, (15, 58), (49, 58), glyph)
        _line(pixels, width, height, (49, 58), (32, 22), glyph)
    elif shape == "diamond":
        for left, right in (
            ((32, 20), (13, 42)),
            ((13, 42), (32, 63)),
            ((32, 63), (51, 42)),
            ((51, 42), (32, 20)),
        ):
            _line(pixels, width, height, left, right, glyph)
    else:
        _rect(pixels, width, height, 27, 20, 37, 64, glyph)
        _rect(pixels, width, height, 12, 37, 52, 47, glyph)
    return _png(width, height, pixels, 32, 76)


def _checkpoint_sprite(
    color: tuple[int, int, int, int],
    beta: bool,
) -> bytes:
    width, height = 72, 96
    pixels = _canvas(width, height)
    halo = tuple(min(255, value + 70) for value in color[:3]) + (170,)
    for y in range(10, 86):
        for x in range(7, 65):
            distance = (x - 36) ** 2 + (y - 48) ** 2
            if 770 <= distance <= 1225:
                _pixel(pixels, width, height, x, y, halo)
    points = (
        [(36, 15), (58, 30), (58, 65), (36, 82), (14, 65), (14, 30)]
        if beta
        else [(36, 13), (43, 36), (66, 36), (47, 50), (55, 78), (36, 61), (17, 78), (25, 50), (6, 36), (29, 36)]
    )
    for index, point in enumerate(points):
        _line(
            pixels,
            width,
            height,
            point,
            points[(index + 1) % len(points)],
            color,
            4,
        )
    return _png(width, height, pixels, 36, 92)


def _door_sprite(
    color: tuple[int, int, int, int],
    open_frame: bool,
) -> bytes:
    width, height = 96, 128
    pixels = _canvas(width, height)
    left, right = ((41, 55) if open_frame else (8, 88))
    _rect(pixels, width, height, left, 4, right, 124, (16, 18, 23, 255))
    _rect(pixels, width, height, left + 5, 9, right - 5, 119, color)
    if not open_frame:
        _rect(pixels, width, height, 34, 53, 62, 82, (12, 14, 18, 255))
        _rect(pixels, width, height, 39, 40, 57, 64, (12, 14, 18, 255))
        _rect(pixels, width, height, 44, 58, 52, 72, (230, 235, 240, 255))
    return _png(width, height, pixels, 48, 124)


def _exit_sprite(active: bool) -> bytes:
    width, height = 80, 112
    pixels = _canvas(width, height)
    colors = (
        ((80, 245, 255, 255), (200, 70, 255, 255))
        if active
        else ((25, 110, 125, 255), (85, 30, 110, 255))
    )
    for y in range(6, 106):
        for x in range(6, 74):
            value = ((x - 40) / 30) ** 2 + ((y - 56) / 48) ** 2
            if 0.70 <= value <= 1.12:
                _pixel(pixels, width, height, x, y, colors[(x + y) % 2])
    return _png(width, height, pixels, 40, 108)


def sprite_files() -> dict[str, bytes]:
    switches = {
        "SAMA": ((238, 174, 47, 255), "circle"),
        "SCYA": ((40, 225, 235, 255), "triangle"),
        "SVIO": ((190, 70, 235, 255), "diamond"),
        "SWHI": ((240, 240, 240, 255), "cross"),
    }
    files: dict[str, bytes] = {}
    for name, (color, shape) in switches.items():
        files[f"sprites/{name}A0.png"] = _switch_sprite(color, shape, False)
        files[f"sprites/{name}B0.png"] = _switch_sprite(color, shape, True)
    files["sprites/CPALA0.png"] = _checkpoint_sprite(
        (80, 240, 100, 255), False
    )
    files["sprites/CPBEA0.png"] = _checkpoint_sprite(
        (70, 130, 255, 255), True
    )
    for name, color in (
        ("DBLU", (40, 90, 225, 255)),
        ("DYEL", (230, 190, 35, 255)),
        ("DRED", (220, 45, 45, 255)),
    ):
        files[f"sprites/{name}A0.png"] = _door_sprite(color, False)
        files[f"sprites/{name}B0.png"] = _door_sprite(color, True)
    files["sprites/EXPTA0.png"] = _exit_sprite(False)
    files["sprites/EXPTB0.png"] = _exit_sprite(True)
    return files


def build_package(
    package_path: Path,
    acc: Path,
    acc_include: Path,
) -> None:
    source_dir = Path(__file__).with_name("full_assets")
    object_path = package_path.with_suffix(".o")
    subprocess.run(
        [
            str(acc),
            "-i",
            str(acc_include),
            str(source_dir / "avbench.acs"),
            str(object_path),
        ],
        check=True,
    )
    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(source_dir / "DECORATE", "DECORATE")
        archive.writestr("LOADACS", "AVBENCH\n")
        archive.write(object_path, "acs/avbench.o")
        for name, data in sprite_files().items():
            archive.writestr(name, data)
