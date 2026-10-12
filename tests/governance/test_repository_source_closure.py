from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import validate_repo


class RepositorySourceClosureTests(unittest.TestCase):
    def validate(self, files: dict[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for name, body in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)
            output = io.StringIO()
            with (
                patch.object(validate_repo, "ROOT", root),
                patch.object(validate_repo, "REQUIRED", []),
                patch.object(validate_repo, "inspect_worktree", return_value={"errors": []}),
                patch.object(validate_repo, "load_json_strict", return_value={}),
                patch.object(validate_repo, "validate_schema", return_value=[]),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
            ):
                status = validate_repo.main()
            for name, body in files.items():
                self.assertEqual((root / name).read_text(), body)
            return status, output.getvalue()

    def test_external_research_reference_does_not_require_owner_host(self):
        status, output = self.validate({
            "docs/scope.md": "[Research](/owner-only/research/decision.md)\n",
        })
        self.assertEqual(status, 0, output)

    def test_relative_reference_must_exist(self):
        status, output = self.validate({"docs/scope.md": "[Contract](missing.md)\n"})
        self.assertEqual(status, 1)
        self.assertIn("broken local link", output)
        status, output = self.validate({
            "docs/scope.md": "[Contract](contract.md)\n",
            "docs/contract.md": "# Contract\n",
        })
        self.assertEqual(status, 0, output)

    def test_relative_reference_cannot_escape_repository(self):
        status, output = self.validate({"docs/scope.md": "[Contract](../../contract.md)\n"})
        self.assertEqual(status, 1)
        self.assertIn("local link escapes repository", output)

    def test_original_bundled_license_formatting_is_preserved(self):
        status, output = self.validate({
            "scripts/web/THIRD_PARTY_NOTICES.txt": "Copyright holder  \nLicense text\n",
        })
        self.assertEqual(status, 0, output)

    def test_unrelated_whitespace_remains_a_failure(self):
        status, output = self.validate({"docs/contract.md": "Contract  \n"})
        self.assertEqual(status, 1)
        self.assertIn("trailing whitespace", output)


if __name__ == "__main__":
    unittest.main()
