"""Command-line interface for Duplicate File Finder."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .core import duplicate_removal_plan, file_hash, find_duplicates, reclaimable_bytes, remove_duplicates


REPORT_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dupes",
        description="Find duplicate files by comparing their content.",
    )
    parser.add_argument("directories", nargs="+", type=Path, help="directories to scan recursively")
    parser.add_argument("--json", action="store_true", help="print results as machine-readable JSON")
    parser.add_argument("--output", type=Path, metavar="FILE", help="write the JSON report atomically to FILE")
    parser.add_argument("--summary-only", action="store_true", help="print only the scan summary")
    parser.add_argument("--fail-if-duplicates", action="store_true", help="exit with status 1 when duplicates are found")
    parser.add_argument("--min-size", type=int, default=0, metavar="BYTES", help="ignore files smaller than BYTES")
    parser.add_argument("--max-size", type=int, metavar="BYTES", help="ignore files larger than BYTES")
    parser.add_argument("--exclude", action="append", type=Path, default=[], metavar="PATH", help="exclude PATH and its descendants; repeatable")
    parser.add_argument("--no-hidden", action="store_true", help="skip hidden files and directories")
    parser.add_argument("--follow-symlinks", action="store_true", help="include symlinked files in scans; disabled by default")
    parser.add_argument("--workers", type=int, metavar="N", help="number of hashing workers; default is automatic")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument("--delete", action="store_true", help="preview redundant files; requires --yes to actually delete")
    parser.add_argument("--yes", action="store_true", help="confirm deletion when used with --delete")
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
    duplicate_groups = []
    for group in groups:
        size = group[0].stat().st_size
        hashes = [file_hash(path) for path in group]
        duplicate_groups.append(
            {
                "size": size,
                "sha256": hashes[0],
                "verified_same_hash": len(set(hashes)) == 1,
                "files": [
                    {"path": str(path), "sha256": digest}
                    for path, digest in zip(group, hashes)
                ],
                "reclaimable_bytes": size * (len(group) - 1),
            }
        )
    return {
        "report_version": REPORT_VERSION,
        "directories": [str(root) for root in roots],
        "scanned": scanned,
        "skipped": skipped,
        "duplicate_group_count": len(duplicate_groups),
        "reclaimable_bytes": reclaimable_bytes(groups),
        "duplicate_groups": duplicate_groups,
    }


def write_json_atomic(report: dict, output: Path) -> None:
    """Write a JSON report without leaving a partial destination on failure."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, output)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


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
    if args.max_size is not None and args.max_size < 0:
        parser.error("--max-size must be >= 0")
    if args.max_size is not None and args.max_size < args.min_size:
        parser.error("--max-size must be >= --min-size")
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.output is not None and not args.json:
        parser.error("--output requires --json")
    if args.yes and not args.delete:
        parser.error("--yes requires --delete")

    groups, scanned, skipped = find_duplicates(
        args.directories,
        min_size=args.min_size,
        max_size=args.max_size,
        include_hidden=not args.no_hidden,
        exclude=args.exclude,
        workers=args.workers,
        follow_symlinks=args.follow_symlinks,
    )

    report = build_report(args.directories, groups, scanned, skipped) if (args.json or args.output) else None

    if args.delete:
        plan = duplicate_removal_plan(groups)
        if args.json:
            report["planned_removals"] = [str(path) for path in plan]
        if args.output:
            write_json_atomic(report, args.output)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_human_report(groups, scanned, skipped, summary_only=False)
            print("\nCleanup plan (one file preserved per group):")
            for path in plan:
                print(f"  REMOVE {path}")
            if not plan:
                print("  Nothing to remove.")
            elif not args.yes:
                print("\nDry run only. Re-run with --delete --yes to remove these files.")
            else:
                removed, failed = remove_duplicates(groups)
                print(f"\nRemoved {len(removed)} files.")
                if failed:
                    print(f"Failed to remove {len(failed)} files.")
        return 1 if args.fail_if_duplicates and groups else 0

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.output:
        write_json_atomic(report, args.output)
    else:
        print_human_report(groups, scanned, skipped, args.summary_only)

    return 1 if args.fail_if_duplicates and groups else 0
