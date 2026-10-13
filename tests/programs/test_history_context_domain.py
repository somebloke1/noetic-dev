import tempfile
import unittest
from pathlib import Path

from scripts.noetic_scope import Scope
from scripts.noetic_sessions import SessionError, SessionService


class HistoryContextDomainTests(unittest.TestCase):
    def test_structured_exact_context_does_not_become_a_native_recipient(self):
        with tempfile.TemporaryDirectory(prefix="noetic-context-domain-") as directory:
            home = Path(directory)
            service = SessionService(home / "runs", namespace_path=home / "namespace.sqlite3", pi_command=["/bin/false"])
            root = service.create_effort({"intent": "Structured source fixture", "environment": {"cwd": str(home)}})["ordinal"]
            store, scope = service.registry.domain.store(), Scope.effort(root)
            store.instantiate(root, scope=scope, native_ref={"client": "fixture-actor", "run_id": "source-run", "activation_id": "activation-6"}, source_ref={"fixture": "no-provider"})
            target = store.open_session(root, 1, scope=scope, native_ref={"client": "fixture-actor", "session_id": "source-context"}, source_ref={"fixture": "no-provider"})
            with self.assertRaises(SessionError) as unavailable:
                service.select(target.as_dict(), effort_root=root)
            self.assertEqual(unavailable.exception.status, 409)
            self.assertIn("no native conversation registry backing", str(unavailable.exception))
            self.assertEqual(service.registry.list(), [])
            self.assertEqual(store.resolve(root, scope=scope, instantiation=1, session=1), target)


if __name__ == "__main__":
    unittest.main()
