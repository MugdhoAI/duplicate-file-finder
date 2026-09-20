import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from duplicate_file_finder.cli import main
from duplicate_file_finder.core import (
    file_hash,
    find_duplicates,
    partial_file_hash,
    reclaimable_bytes,
    select_keep_file,
)


class DuplicateFinderTests(unittest.TestCase):
    def test_file_hash_matches_identical_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "second.txt"
            first.write_text("same content", encoding="utf-8")
            second.write_text("same content", encoding="utf-8")
            self.assertEqual(file_hash(first), file_hash(second))

    def test_partial_hash_only_uses_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"a" * 64 + b"first")
            second.write_bytes(b"a" * 64 + b"second")
            self.assertEqual(partial_file_hash(first, chunk_size=64), partial_file_hash(second, chunk_size=64))
            self.assertNotEqual(file_hash(first), file_hash(second))

    def test_find_duplicates_groups_identical_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "nested" / "second.txt"
            different = root / "different.txt"
            second.parent.mkdir()
            first.write_text("duplicate", encoding="utf-8")
            second.write_text("duplicate", encoding="utf-8")
            different.write_text("different", encoding="utf-8")
            groups, scanned, skipped = find_duplicates(root)
            self.assertEqual(scanned, 3)
            self.assertEqual(skipped, 0)
            self.assertEqual(groups, [[first, second]])

    def test_same_size_and_prefix_is_not_enough(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            prefix = b"shared prefix"
            first.write_bytes(prefix + b"A")
            second.write_bytes(prefix + b"B")
            groups, scanned, skipped = find_duplicates(root)
            self.assertEqual(groups, [])
            self.assertEqual(scanned, 2)
            self.assertEqual(skipped, 0)

    def test_small_files_are_still_exact_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"small")
            second.write_bytes(b"small")
            groups, _, skipped = find_duplicates(root)
            self.assertEqual(groups, [[first, second]])
            self.assertEqual(skipped, 0)

    def test_symlinks_are_skipped_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            link = root / "link.txt"
            first.write_text("same", encoding="utf-8")
            try:
                link.symlink_to(first)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are not available")
            groups, scanned, skipped = find_duplicates(root)
            self.assertEqual(groups, [])
            self.assertEqual(scanned, 1)
            self.assertEqual(skipped, 0)

    def test_max_size_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "small.txt").write_text("same", encoding="utf-8")
            (root / "large.txt").write_text("same" * 100, encoding="utf-8")
            groups, scanned, skipped = find_duplicates(root, max_size=10)
            self.assertEqual(groups, [])
            self.assertEqual(scanned, 1)
            self.assertEqual(skipped, 0)

    def test_keep_strategy_selects_expected_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oldest = root / "old.txt"
            newest = root / "new.txt"
            oldest.write_text("same", encoding="utf-8")
            newest.write_text("same", encoding="utf-8")
            self.assertEqual(select_keep_file([newest, oldest], "path"), oldest)
            self.assertEqual(select_keep_file([oldest, newest], "oldest"), oldest)
            self.assertEqual(select_keep_file([oldest, newest], "newest"), newest)

    def test_reclaimable_bytes_keeps_one_file_per_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            third = root / "third.bin"
            first.write_bytes(b"1234")
            second.write_bytes(b"1234")
            third.write_bytes(b"1234")
            self.assertEqual(reclaimable_bytes([[first, second, third]]), 8)

    def test_fail_if_duplicates_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("same", encoding="utf-8")
            (root / "second.txt").write_text("same", encoding="utf-8")
            original = sys.argv
            try:
                sys.argv = ["dupes", str(root), "--fail-if-duplicates"]
                with redirect_stdout(StringIO()):
                    self.assertEqual(main(), 1)
            finally:
                sys.argv = original

    def test_json_report_can_be_written_to_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "reports" / "scan.json"
            (root / "first.txt").write_text("same", encoding="utf-8")
            (root / "second.txt").write_text("same", encoding="utf-8")
            original = sys.argv
            try:
                sys.argv = ["dupes", str(root), "--json", "--output", str(output)]
                with redirect_stdout(StringIO()):
                    self.assertEqual(main(), 0)
            finally:
                sys.argv = original
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["report_version"], 1)
            self.assertEqual(report["duplicate_group_count"], 1)
            self.assertTrue(report["duplicate_groups"][0]["verified_same_hash"])


if __name__ == "__main__":
    unittest.main()
