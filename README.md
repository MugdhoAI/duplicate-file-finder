# Duplicate File Finder

A small, dependency-free Python CLI for finding duplicate files by content.

Duplicate File Finder recursively scans directories, narrows candidates by file size and partial SHA-256 hashing, confirms matches with full SHA-256, and reports storage that could be reclaimed.

## Features

- Recursive scanning across one or more directories
- Staged duplicate detection: size → partial SHA-256 → full SHA-256
- Hard-link aware duplicate reporting
- Minimum-size filtering
- Optional hidden-file exclusion
- Repeatable path exclusions
- Configurable parallel hashing workers
- Human-readable and JSON output
- Summary-only mode
- No files are deleted or modified
- Standard-library-only implementation

## Installation

```bash
python -m pip install -e .
```

## Usage

```bash
dupes /path/to/directory
dupes /path/one /path/two
dupes /path/to/directory --min-size 1048576
dupes /path/to/directory --no-hidden
dupes /path/to/directory --exclude /path/to/directory/cache

dupes /path/to/directory --workers 4
dupes /path/to/directory --json
dupes /path/to/directory --summary-only
dupes --version
```

The original `duplicate-file-finder` command remains available.

The tool is read-only: it never deletes or modifies files. Hard links to the same underlying inode are not counted as separate duplicate files, because they do not represent additional file data.

## Development

```bash
python -m unittest discover -s tests
```

The project intentionally uses only the Python standard library.
