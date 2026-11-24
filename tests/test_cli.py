import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from duplicate_file_finder.cli import build_parser, format_size, main, parse_size, write_json_atomic
from duplicate_file_finder.core import find_duplicates


class CliTests(unittest.TestCase):
    def test_format_size_units_and_boundaries(self) -> None:
        self.assertEqual(format_size(0), "0.0 B")
        self.assertEqual(format_size(512), "512.0 B")
        self.assertEqual(format_size(1023), "1023.0 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1536), "1.5 KB")
        self.assertEqual(format_size(1024 ** 2), "1.0 MB")
        self.assertEqual(format_size(1024 ** 3), "1.0 GB")
        self.assertEqual(format_size(1024 ** 4), "1.0 TB")
        self.assertEqual(format_size(1024 ** 5), "1024.0 TB")

    def test_atomic_write_failure_leaves_no_partial_report(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "report.json"
            with patch.object(json, "dump", side_effect=OSError("simulated write failure")):
                with self.assertRaises(OSError):
                    write_json_atomic({"report_version": 1}, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [])

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

    def test_summary_uses_plural_for_multiple_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a1.txt").write_text("alpha", encoding="utf-8")
            (root / "a2.txt").write_text("alpha", encoding="utf-8")
            (root / "b1.txt").write_text("beta", encoding="utf-8")
            (root / "b2.txt").write_text("beta", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("found 2 duplicate groups", output.getvalue())

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
            self.assertIn("found 1 duplicate group", output.getvalue())

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

    def test_same_directory_twice_reports_each_file_once_in_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("same", encoding="utf-8")
            (root / "second.txt").write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), str(root), "--json"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["scanned"], 2)
            self.assertEqual(report["duplicate_group_count"], 1)
            self.assertEqual(report["reclaimable_bytes"], 4)

    def test_workers_flag_is_accepted(self) -> None:
        args = build_parser().parse_args([".", "--workers", "2"])
        self.assertEqual(args.workers, 2)

    def test_parse_size_accepts_plain_bytes_and_suffixes(self) -> None:
        self.assertEqual(parse_size("2048"), 2048)
        self.assertEqual(parse_size("512B"), 512)
        self.assertEqual(parse_size("1KB"), 1024)
        self.assertEqual(parse_size("1kb"), 1024)
        self.assertEqual(parse_size("2 MB"), 2 * 1024 ** 2)
        self.assertEqual(parse_size("1.5KB"), 1536)
        self.assertEqual(parse_size("1GB"), 1024 ** 3)

    def test_parse_size_rejects_unknown_suffixes(self) -> None:
        import argparse

        for value in ("10XB", "abc", "", "-5", "1.5.2KB"):
            with self.assertRaises(argparse.ArgumentTypeError, msg=value):
                parse_size(value)

    def test_min_size_suffix_filters_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("same", encoding="utf-8")
            (root / "second.txt").write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--min-size", "1KB", "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("Scanned 0 files", output.getvalue())


    def test_delete_with_failed_removal_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with (
                patch("sys.argv", ["dupes", str(root), "--delete", "--yes"]),
                patch("duplicate_file_finder.cli.remove_duplicates", return_value=([], [second])),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main(), 1)
            self.assertIn("Failed to remove 1 files", output.getvalue())

    def test_backup_with_failed_move_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "backup"
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with (
                patch("sys.argv", ["dupes", str(root), "--backup-dir", str(backup), "--yes"]),
                patch("duplicate_file_finder.cli.backup_duplicates", return_value=([], [second])),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(main(), 1)
            self.assertIn("Failed to move 1 files", output.getvalue())

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

    def test_summary_only_hides_listing_in_delete_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--delete", "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("Scanned 2 files", output.getvalue())
            self.assertNotIn("Group 1", output.getvalue())
            self.assertNotIn("Duplicate files", output.getvalue())

    def test_summary_only_hides_listing_in_backup_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "backup"
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--backup-dir", str(backup), "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            self.assertIn("Scanned 2 files", output.getvalue())
            self.assertNotIn("Group 1", output.getvalue())
            self.assertNotIn("Duplicate files", output.getvalue())

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

    def test_json_delete_with_yes_removes_only_redundant_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--json", "--delete", "--yes"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["planned_removals"], [str(second)])
            self.assertTrue(first.exists())
            self.assertFalse(second.exists())

    def test_json_delete_without_yes_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--json", "--delete"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["planned_removals"], [str(second)])
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_json_backup_with_yes_moves_only_redundant_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            root.mkdir()
            backup_dir = Path(directory) / "backup"
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--json", "--backup-dir", str(backup_dir), "--yes"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["planned_backups"], [str(second)])
            self.assertTrue(first.exists())
            self.assertFalse(second.exists())
            self.assertTrue((backup_dir / "second.txt").exists())

    def test_json_backup_without_yes_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "data"
            root.mkdir()
            backup_dir = Path(directory) / "backup"
            first, second = root / "first.txt", root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")
            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--json", "--backup-dir", str(backup_dir)]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["planned_backups"], [str(second)])
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertFalse((backup_dir / "second.txt").exists())

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
