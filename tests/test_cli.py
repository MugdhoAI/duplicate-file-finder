import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from duplicate_file_finder.cli import build_parser, main
from duplicate_file_finder.core import find_duplicates


class CliTests(unittest.TestCase):
    def test_short_command_parser_uses_dupes(self) -> None:
        self.assertEqual(build_parser().prog, "dupes")

    def test_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("same", encoding="utf-8")
            (root / "second.txt").write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--json"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["duplicate_group_count"], 1)
            self.assertEqual(report["scanned"], 2)
            self.assertEqual(report["reclaimable_bytes"], 4)

    def test_summary_only_hides_file_listing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("Scanned 2 files", output.getvalue())
            self.assertNotIn(str(first), output.getvalue())

    def test_multiple_directories_and_min_size(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            a, b = Path(first_dir) / "a.txt", Path(second_dir) / "b.txt"
            a.write_text("duplicate", encoding="utf-8")
            b.write_text("duplicate", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", first_dir, second_dir, "--min-size", "5", "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("found 1 duplicate groups", output.getvalue())

    def test_no_hidden_skips_hidden_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".hidden").write_text("same", encoding="utf-8")
            (root / "visible").write_text("same", encoding="utf-8")
            groups, scanned, _ = find_duplicates(root, include_hidden=False)
            self.assertEqual(scanned, 1)
            self.assertEqual(groups, [])

    def test_hardlinks_are_not_reported_as_reclaimable_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            first.write_text("same", encoding="utf-8")
            try:
                os.link(first, second)
            except OSError:
                self.skipTest("hard links are unavailable")
            groups, _, _ = find_duplicates(root)
            self.assertEqual(groups, [])

    def test_workers_flag_is_accepted(self) -> None:
        args = build_parser().parse_args([".", "--workers", "2"])
        self.assertEqual(args.workers, 2)


    def test_delete_is_dry_run_without_yes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--delete"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertTrue(second.exists())
            self.assertIn("Dry run only", output.getvalue())

    def test_delete_with_yes_removes_only_redundant_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            with patch("sys.argv", ["dupes", str(root), "--delete", "--yes"]):
                self.assertEqual(main(), 0)
            self.assertTrue(first.exists())
            self.assertFalse(second.exists())

    def test_yes_without_delete_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["dupes", directory, "--yes"]):
                with self.assertRaises(SystemExit):
                    main()

    def test_version_flag_uses_package_version(self) -> None:
        with self.assertRaises(SystemExit) as error:
            build_parser().parse_args(["--version"])
        self.assertEqual(error.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
