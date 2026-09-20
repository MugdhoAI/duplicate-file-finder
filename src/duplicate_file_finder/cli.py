"""Command-line interface for Duplicate File Finder."""

from __future__ import annotations

import argparse
from pathlib import Path

from .core import find_duplicates, reclaimable_bytes

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="duplicate-file-finder",
        description="Find duplicate files by comparing their content.",
    )
    parser.add_argument("directory", type=Path, help="directory to scan recursively")
    return parser

def format_size(size: int) -> str:
    """Format a byte count for human-readable output."""
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = args.directory

    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    groups, scanned, skipped = find_duplicates(root)

    if groups:
        print("Duplicate files\n")
        for index, group in enumerate(groups, start=1):
            size = group[0].stat().st_size
            reclaimable = size * (len(group) - 1)
            print(f"Group {index} ({len(group)} files, {format_size(reclaimable)} reclaimable)")
            for path in group:
                print(f"  {path}")
            print()
    else:
        print("No duplicate files found.\n")

    print(f"Scanned {scanned} files and found {len(groups)} duplicate groups.")
    print(f"Potentially reclaimable space: {format_size(reclaimable_bytes(groups))}")
    if skipped:
        print(f"Skipped {skipped} files that could not be accessed.")
    return 0
