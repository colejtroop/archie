from __future__ import annotations

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .blueprint import BlockSpec, Blueprint, Position


class StructureFormatError(ValueError):
    pass


@dataclass
class _Reader:
    data: bytes
    offset: int = 0

    def take(self, length: int) -> bytes:
        if length < 0 or self.offset + length > len(self.data):
            raise StructureFormatError(
                f"truncated NBT payload at byte {self.offset}: requested {length}, "
                f"available {len(self.data) - self.offset}"
            )
        value = self.data[self.offset : self.offset + length]
        self.offset += length
        return value

    def unpack(self, pattern: str) -> Any:
        size = struct.calcsize(pattern)
        return struct.unpack(pattern, self.take(size))[0]

    def string(self) -> str:
        length = self.unpack("<H")
        try:
            return self.take(length).decode("utf-8")
        except UnicodeDecodeError as error:
            raise StructureFormatError("invalid UTF-8 in NBT string") from error


def _payload(reader: _Reader, tag: int, depth: int = 0) -> Any:
    if depth > 64:
        raise StructureFormatError("NBT nesting limit exceeded")
    if tag == 1:
        return reader.unpack("<b")
    if tag == 2:
        return reader.unpack("<h")
    if tag == 3:
        return reader.unpack("<i")
    if tag == 4:
        return reader.unpack("<q")
    if tag == 5:
        return reader.unpack("<f")
    if tag == 6:
        return reader.unpack("<d")
    if tag == 7:
        length = reader.unpack("<i")
        return reader.take(length)
    if tag == 8:
        return reader.string()
    if tag == 9:
        child_tag = reader.unpack("<b")
        length = reader.unpack("<i")
        if length < 0 or length > 1_000_000:
            raise StructureFormatError("invalid NBT list length")
        return [_payload(reader, child_tag, depth + 1) for _ in range(length)]
    if tag == 10:
        result: dict[str, Any] = {}
        while True:
            child_tag = reader.unpack("<b")
            if child_tag == 0:
                return result
            child_name = reader.string()
            result[child_name] = _payload(reader, child_tag, depth + 1)
    if tag == 11:
        length = reader.unpack("<i")
        if length < 0 or length > 1_000_000:
            raise StructureFormatError("invalid NBT int-array length")
        return [reader.unpack("<i") for _ in range(length)]
    if tag == 12:
        length = reader.unpack("<i")
        if length < 0 or length > 1_000_000:
            raise StructureFormatError("invalid NBT long-array length")
        return [reader.unpack("<q") for _ in range(length)]
    raise StructureFormatError(f"unsupported NBT tag {tag}")


def read_little_endian_nbt(data: bytes) -> dict[str, Any]:
    reader = _Reader(data)
    if reader.unpack("<b") != 10:
        raise StructureFormatError("root NBT tag must be a compound")
    reader.string()  # Root name is normally empty.
    root = _payload(reader, 10)
    if reader.offset != len(data):
        raise StructureFormatError("unexpected bytes after root NBT compound")
    return root


def load_mcstructure(path: Path) -> Blueprint:
    root = read_little_endian_nbt(path.read_bytes())
    try:
        size_x, size_y, size_z = (int(value) for value in root["size"])
        structure = root["structure"]
        primary = structure["block_indices"][0]
        palette = structure["palette"]["default"]["block_palette"]
    except (KeyError, TypeError, ValueError) as error:
        raise StructureFormatError("missing required mcstructure fields") from error
    volume = size_x * size_y * size_z
    if min(size_x, size_y, size_z) < 1 or volume > 32_768:
        raise StructureFormatError("structure dimensions are invalid or too large")
    if len(primary) != volume:
        raise StructureFormatError("primary block-index layer does not match structure size")

    blocks: dict[Position, BlockSpec] = {}
    for index, palette_index in enumerate(primary):
        if palette_index == -1:
            continue
        if not isinstance(palette_index, int) or not 0 <= palette_index < len(palette):
            raise StructureFormatError("block palette index is out of range")
        entry = palette[palette_index]
        block_type = entry.get("name")
        if not isinstance(block_type, str) or not block_type:
            raise StructureFormatError("block palette entry has no name")
        # Bedrock stores X outermost, then Y, then Z.
        x = index // (size_y * size_z)
        remainder = index % (size_y * size_z)
        y = remainder // size_z
        z = remainder % size_z
        states = entry.get("states", {})
        blocks[Position(x, y, z)] = BlockSpec(block_type, states if isinstance(states, dict) else {})
    return Blueprint(path.stem.replace("_", "-"), blocks)


def blueprint_payload(blueprint: Blueprint) -> dict[str, Any]:
    palette: list[dict[str, Any]] = []
    palette_indexes: dict[tuple[str, str], int] = {}
    cells: list[list[int]] = []
    for position, block in sorted(blueprint.blocks.items()):
        state_json = json.dumps(dict(block.states), sort_keys=True, separators=(",", ":"))
        key = (block.block_type, state_json)
        if key not in palette_indexes:
            palette_indexes[key] = len(palette)
            palette.append({"name": block.block_type, "states": dict(block.states)})
        cells.append([position.x, position.y, position.z, palette_indexes[key]])
    return {"name": blueprint.name, "palette": palette, "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or convert a Bedrock .mcstructure blueprint")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    blueprint = load_mcstructure(args.path)
    print(json.dumps(blueprint_payload(blueprint), separators=(",", ":")))


if __name__ == "__main__":
    main()
