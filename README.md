# Duplicate File Finder

A small, dependency-free Python CLI for finding duplicate files by content.

Duplicate File Finder recursively scans a directory, narrows candidates by file size and partial SHA-256 hashing, confirms matches with full SHA-256, and reports the storage space that could be reclaimed.

## Features

- Recursive directory scanning
- Staged duplicate detection: size → partial SHA-256 → full SHA-256
- Human-readable and JSON output
- Summary-only mode for scripts and quick checks
- Reclaimable-space calculation
- Graceful handling of inaccessible files
- No files are deleted or modified
- Standard-library-only implementation

## Requirements

- Python 3.10 or newer

## Installation

Clone the repository and install it locally:

```bash
python -m pip install -e .
```

## Usage

The recommended command is:

```bash
dupes /path/to/directory
```

The original command name remains available:

```bash
duplicate-file-finder /path/to/directory
```

Show only the summary:

```bash
dupes /path/to/directory --summary-only
```

Export a machine-readable report:

```bash
dupes /path/to/directory --json
```

Show the installed version:

```bash
dupes --version
```

The first file in each duplicate group is treated as the file to keep when calculating reclaimable space. The tool does not remove or modify any files.

## Development

Run the test suite with:

```bash
python -m unittest discover -s tests
```

The project intentionally uses the Python standard library so the scanning, hashing, and reporting behavior remains easy to inspect, test, and extend.
