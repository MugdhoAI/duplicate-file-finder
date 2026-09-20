# Duplicate File Finder

A small, dependency free Python CLI for safely auditing and reclaiming wasted storage from exact duplicate files.

Duplicate File Finder runs locally, scans files by content, and reports exactly what it found before any cleanup. It narrows candidates by file size and partial SHA-256 hashing, confirms matches with full SHA-256, and reports storage that could be reclaimed. **It does not upload your files or send file contents to a remote service.**

## Features

- Recursive scanning across one or more directories
- Staged duplicate detection: size → partial SHA-256 → full SHA-256
- Hard link aware duplicate reporting
- Minimum and maximum size filtering
- Optional hidden file exclusion
- Repeatable path exclusions
- Configurable parallel hashing workers
- Human readable and JSON output
- Versioned audit reports with per file SHA-256 hashes
- Atomic JSON report export
- Summary only mode
- Automation friendly duplicate exit status
- Read only scanning by default
- Safe cleanup preview with explicit `--delete --yes` confirmation
- Backup cleanup mode with configurable keep strategy
- Standard library only implementation

## Installation

```bash
python -m pip install -e .
```

## Usage

```bash
dupes /path/to/directory
dupes /path/one /path/two
dupes /path/to/directory --min-size 1048576
dupes /path/to/directory --max-size 1073741824
dupes /path/to/directory --no-hidden
dupes /path/to/directory --exclude /path/to/directory/cache

dupes /path/to/directory --workers 4
dupes /path/to/directory --json
dupes /path/to/directory --json --output report.json
dupes /path/to/directory --fail-if-duplicates

dupes /path/to/directory --delete
dupes /path/to/directory --delete --yes
dupes /path/to/directory --backup-dir ./duplicate-backup --keep oldest --yes
dupes /path/to/directory --summary-only
dupes --version
```

The original `duplicate-file-finder` command remains available.

Scanning is read only by default. Symlinked files are skipped unless `--follow-symlinks` is explicitly enabled. `--delete` shows the exact cleanup plan first; actual deletion requires explicit `--yes` confirmation. Before deleting each file, the tool rechecks its size and full hash against the file being preserved. Hard links to the same underlying inode are not counted as separate duplicate files, because they do not represent additional file data.

Cleanup supports `path`, `oldest`, and `newest` keep strategies. `--backup-dir` moves redundant files into a backup directory after the same size/hash verification used by deletion, giving destructive cleanup a reversible alternative.

JSON reports include a schema version, scan statistics, duplicate group hashes, and per-file SHA-256 values. `--output` writes the report atomically so an interrupted write does not leave a partial report. `--fail-if-duplicates` returns exit status 1 when duplicates are found, which makes the scanner usable in scripts and CI.

## Development

```bash
python -m unittest discover -s tests
```

The project intentionally uses only the Python standard library.
