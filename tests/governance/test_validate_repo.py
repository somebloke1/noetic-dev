from __future__ import annotations

import unittest

from scripts.validate_repo import (
    LEDGER_STATUS_VOCABULARIES,
    REQUIRED,
    ROOT,
    ledger_status_errors,
    required_declaration_errors,
)


def crud_block(entry_id: str, status_lines: list[str]) -> str:
    metadata = "\n".join(status_lines)
    return (
        f"<!-- governance-crud:start id={entry_id} -->\n"
        f"## {entry_id}: Test entry\n\n"
        f"- Ledger: test\n{metadata}\n"
        f"<!-- governance-crud:end id={entry_id} -->\n"
    )


class LedgerStatusValidationTests(unittest.TestCase):
    def test_repository_ledgers_use_allowed_statuses(self) -> None:
        for relative in LEDGER_STATUS_VOCABULARIES:
            with self.subTest(relative=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual(ledger_status_errors(relative, text), [])

    def test_each_declared_status_is_accepted_only_by_its_ledger(self) -> None:
        for relative, allowed in LEDGER_STATUS_VOCABULARIES.items():
            for index, status in enumerate(allowed, 1):
                with self.subTest(relative=relative, status=status):
                    text = crud_block(f"test-20260801-{index:04d}", [f"- Status: {status}"])
                    self.assertEqual(ledger_status_errors(relative, text), [])

    def test_unknown_and_cross_ledger_statuses_are_rejected(self) -> None:
        unknown = crud_block("test-20260801-0001", ["- Status: unknown"])
        cross_ledger = crud_block("test-20260801-0002", ["- Status: open"])
        self.assertIn("unsupported status 'unknown'", ledger_status_errors("KNOWNS.md", unknown)[0])
        self.assertIn(
            "unsupported status 'open'",
            ledger_status_errors("DECISIONS.md", cross_ledger)[0],
        )

    def test_missing_multiple_and_non_scalar_statuses_are_rejected(self) -> None:
        cases = {
            "missing": crud_block("test-20260801-0001", []),
            "multiple": crud_block(
                "test-20260801-0002",
                ["- Status: accepted", "- Status: superseded"],
            ),
            "non_scalar": crud_block(
                "test-20260801-0003",
                ['- Status: ["accepted"]'],
            ),
            "wrong_case": crud_block("test-20260801-0004", ["- Status: Accepted"]),
            "empty_with_continuation": crud_block(
                "test-20260801-0005",
                ["- Status:", "accepted"],
            ),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                self.assertTrue(ledger_status_errors("DECISIONS.md", text))


class RequiredDeclarationValidationTests(unittest.TestCase):
    def test_repository_required_declarations_are_unique(self) -> None:
        self.assertEqual(required_declaration_errors(REQUIRED), [])

    def test_duplicate_errors_are_deterministic_and_sorted(self) -> None:
        self.assertEqual(
            required_declaration_errors(["z", "a", "z", "b", "a", "a"]),
            [
                "duplicate required file declaration: a",
                "duplicate required file declaration: z",
            ],
        )


if __name__ == "__main__":
    unittest.main()
