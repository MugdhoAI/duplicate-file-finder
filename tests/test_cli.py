import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from duplicate_file_finder.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_short_command_parser_uses_dupes(self) -> None:
        parser = build_parser()
        self.assertEqual(parser.prog, "dupes")

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
            self.assertEqual(len(report["duplicate_groups"]), 1)

    def test_summary_only_hides_file_listing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "second.txt"
            first.write_text("same", encoding="utf-8")
            second.write_text("same", encoding="utf-8")

            output = io.StringIO()
            with patch("sys.argv", ["dupes", str(root), "--summary-only"]), contextlib.redirect_stdout(output):
                self.assertEqual(main(), 0)

            text = output.getvalue()
            self.assertIn("Scanned 2 files", text)
            self.assertNotIn(str(first), text)
            self.assertNotIn(str(second), text)
            self.assertNotIn("Group 1", text)

    def test_version_flag_uses_package_version(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as error:
            parser.parse_args(["--version"])
        self.assertEqual(error.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
