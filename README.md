# Duplicate File Finder

A small, dependency-free Python CLI for finding duplicate files by content.

Duplicate File Finder scans a directory recursively, groups files by size before hashing their contents, and reports duplicate groups together with the storage space that could be reclaimed.

## Features

- Recursive directory scanning
- Size-based filtering before content hashing
- SHA-256 content comparison
- Duplicate groups with file paths
- Reclaimable-space calculation
- Graceful handling of inaccessible files
- No files are deleted or modified
- Standard-library-only implementation

## Requirements

- Python 3.10 or newer

## Usage

```bash
python -m duplicate_file_finder /path/to/directory
```

The first file in each duplicate group is treated as the file to keep when calculating reclaimable space. The tool does not remove anything.

## Development

```bash
python -m unittest discover -s tests
```

The project intentionally starts with the Python standard library so the core file-scanning and hashing behavior remains easy to inspect, test, and extend.
