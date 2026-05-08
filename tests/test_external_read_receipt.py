import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.external.read_receipt import (
    ReadReceiptError,
    build_read_receipt,
    verify_read_receipt,
    write_read_receipt,
)


class ReadReceiptTests(unittest.TestCase):
    def test_builds_sha256_hashes_for_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs" / "architecture").mkdir(parents=True)
            (root / "CLAUDE.md").write_bytes(b"claude rules\n")
            (root / "docs" / "architecture" / "current_mvp.md").write_bytes(b"mvp\n")

            receipt = build_read_receipt(
                str(root),
                ("CLAUDE.md", "docs\\architecture\\current_mvp.md"),
            )

        self.assertEqual(
            receipt["CLAUDE.md"],
            hashlib.sha256(b"claude rules\n").hexdigest(),
        )
        self.assertEqual(
            receipt["docs/architecture/current_mvp.md"],
            hashlib.sha256(b"mvp\n").hexdigest(),
        )

    def test_missing_required_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ReadReceiptError, "Required-read file not found"):
                build_read_receipt(tmp, ("AGENTS.md",))

    def test_verify_read_receipt_detects_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_bytes(b"before\n")
            receipt = build_read_receipt(str(root), ("AGENTS.md",))
            (root / "AGENTS.md").write_bytes(b"after\n")

            with self.assertRaisesRegex(ReadReceiptError, "changed since preflight"):
                verify_read_receipt(str(root), receipt)

    def test_write_read_receipt_creates_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_read_receipt(
                tmp,
                {
                    "target": "example",
                    "required_read_hashes": {"AGENTS.md": "abc"},
                },
            )
            data = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(data["target"], "example")
        self.assertEqual(data["required_read_hashes"], {"AGENTS.md": "abc"})


if __name__ == "__main__":
    unittest.main()
