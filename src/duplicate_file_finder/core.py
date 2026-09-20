"""Core duplicate-file detection logic."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Iterable

CHUNK_SIZE = 1024 * 1024
PARTIAL_HASH_SIZE = 64 * 1024


def iter_files(
    root: Path,
    *,
    min_size: int = 0,
    include_hidden: bool = True,
    exclude: Iterable[Path] = (),
) -> Iterable[Path]:
    """Yield regular files below root, skipping inaccessible entries."""
    excluded = {path.resolve() for path in exclude}
    try:
        for path in root.rglob("*"):
            try:
                resolved = path.resolve()
                if any(resolved == item or item in resolved.parents for item in excluded):
                    continue
                if not include_hidden and any(part.startswith(".") for part in path.relative_to(root).parts):
                    continue
                if path.is_file() and path.stat().st_size >= min_size:
                    yield path
            except OSError:
                continue
    except OSError:
        return


def _hash_stream(file, *, limit: int | None = None, chunk_size: int = CHUNK_SIZE) -> str:
    digest = hashlib.sha256()
    remaining = limit
    while True:
        read_size = chunk_size if remaining is None else min(chunk_size, remaining)
        if read_size == 0:
            break
        chunk = file.read(read_size)
        if not chunk:
            break
        digest.update(chunk)
        if remaining is not None:
            remaining -= len(chunk)
    return digest.hexdigest()


def file_hash(path: Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Return the SHA-256 digest of a file."""
    with path.open("rb") as file:
        return _hash_stream(file, chunk_size=chunk_size)


def partial_file_hash(path: Path, chunk_size: int = PARTIAL_HASH_SIZE) -> str:
    """Return a SHA-256 digest of the first part of a file."""
    with path.open("rb") as file:
        return _hash_stream(file, limit=chunk_size, chunk_size=chunk_size)


def _normalize_roots(root: Path | Iterable[Path]) -> list[Path]:
    if isinstance(root, Path):
        return [root]
    return list(root)


def find_duplicates(
    root: Path | Iterable[Path],
    *,
    min_size: int = 0,
    include_hidden: bool = True,
    exclude: Iterable[Path] = (),
) -> tuple[list[list[Path]], int, int]:
    """Find exact duplicate files using staged hashing and safe file selection."""
    roots = _normalize_roots(root)
    by_size: dict[int, list[Path]] = defaultdict(list)
    scanned = 0
    skipped = 0

    for current_root in roots:
        for path in iter_files(
            current_root,
            min_size=min_size,
            include_hidden=include_hidden,
            exclude=exclude,
        ):
            try:
                size = path.stat().st_size
            except OSError:
                skipped += 1
                continue
            by_size[size].append(path)
            scanned += 1

    by_partial_hash: dict[tuple[int, str], list[Path]] = defaultdict(list)
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                by_partial_hash[(size, partial_file_hash(path))].append(path)
            except OSError:
                skipped += 1

    by_hash: dict[str, list[Path]] = defaultdict(list)
    for paths in by_partial_hash.values():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                by_hash[file_hash(path)].append(path)
            except OSError:
                skipped += 1

    duplicates: list[list[Path]] = []
    for paths in by_hash.values():
        unique_files: dict[tuple[int, int], Path] = {}
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            unique_files.setdefault((stat.st_dev, stat.st_ino), path)
        if len(unique_files) > 1:
            duplicates.append(sorted(unique_files.values(), key=lambda item: str(item)))

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
