"""Command-line interface for Duplicate File Finder."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .core import find_duplicates, reclaimable_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dupes",
        description="Find duplicate files by comparing their content.",
    )
    parser.add_argument("directories", nargs="+", type=Path, help="directories to scan recursively")
    parser.add_argument("--json", action="store_true", help="print results as machine-readable JSON")
    parser.add_argument("--summary-only", action="store_true", help="print only the scan summary")
    parser.add_argument("--min-size", type=int, default=0, metavar="BYTES", help="ignore files smaller than BYTES")
    parser.add_argument("--exclude", action="append", type=Path, default=[], metavar="PATH", help="exclude PATH and its descendants; repeatable")
    parser.add_argument("--no-hidden", action="store_true", help="skip hidden files and directories")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    return parser


def package_version() -> str:
    try:
        return version("duplicate-file-finder")
    except PackageNotFoundError:
        return "0.1.0"


def format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def build_report(roots: list[Path], groups: list[list[Path]], scanned: int, skipped: int) -> dict:
    return {
        "directories": [str(root) for root in roots],
        "scanned": scanned,
        "skipped": skipped,
        "duplicate_group_count": len(groups),
        "reclaimable_bytes": reclaimable_bytes(groups),
        "duplicate_groups": [
            {
                "size": group[0].stat().st_size,
                "files": [str(path) for path in group],
                "reclaimable_bytes": group[0].stat().st_size * (len(group) - 1),
            }
            for group in groups
        ],
    }


def print_human_report(groups: list[list[Path]], scanned: int, skipped: int, summary_only: bool) -> None:
    if not summary_only:
        if groups:
            print("Duplicate files\n")
            for index, group in enumerate(groups, start=1):
                size = group[0].stat().st_size
                print(f"Group {index} ({len(group)} files, {format_size(size * (len(group) - 1))} reclaimable)")
                for path in group:
                    print(f"  {path}")
                print()
        else:
            print("No duplicate files found.\n")
    print(f"Scanned {scanned} files and found {len(groups)} duplicate groups.")
    print(f"Potentially reclaimable space: {format_size(reclaimable_bytes(groups))}")
    if skipped:
        print(f"Skipped {skipped} files that could not be accessed.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    for root in args.directories:
        if not root.exists():
            parser.error(f"directory does not exist: {root}")
        if not root.is_dir():
            parser.error(f"not a directory: {root}")
    if args.min_size < 0:
        parser.error("--min-size must be >= 0")

    groups, scanned, skipped = find_duplicates(
        args.directories,
        min_size=args.min_size,
        include_hidden=not args.no_hidden,
        exclude=args.exclude,
    )

    if args.json:
        print(json.dumps(build_report(args.directories, groups, scanned, skipped), indent=2))
    else:
        print_human_report(groups, scanned, skipped, args.summary_only)
    return 0
