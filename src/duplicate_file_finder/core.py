"""Core duplicate-file detection logic."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable

CHUNK_SIZE = 1024 * 1024

def iter_files(root: Path) -> Iterable[Path]:
    """Yield regular files below root, skipping inaccessible entries."""
    try:
        for path in root.rglob("*"):
            try:
                if path.is_file():
                    yield path
            except OSError:
                continue
    except OSError:
        return

def file_hash(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()

def find_duplicates(root: Path) -> tuple[list[list[Path]], int, int]:
    """Find duplicate files under root."""
    by_size: dict[int, list[Path]] = defaultdict(list)
    scanned = 0
    skipped = 0

    for path in iter_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            skipped += 1
            continue
        by_size[size].append(path)
        scanned += 1

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for paths in by_size.values():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                by_hash[file_hash(path)].append(path)
            except OSError:
                skipped += 1

    duplicates = [
        sorted(paths, key=lambda item: str(item))
        for paths in by_hash.values()
        if len(paths) > 1
    ]
    duplicates.sort(key=lambda group: str(group[0]))
    return duplicates, scanned, skipped

def reclaimable_bytes(groups: list[list[Path]]) -> int:
    """Return bytes that could be reclaimed by keeping one file per group."""
    total = 0
    for group in groups:
        for path in group[1:]:
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total
