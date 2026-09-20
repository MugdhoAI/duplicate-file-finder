import tempfile
import unittest
from pathlib import Path

from duplicate_file_finder.core import (
    file_hash,
    find_duplicates,
    partial_file_hash,
    reclaimable_bytes,
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


if __name__ == "__main__":
    unittest.main()
