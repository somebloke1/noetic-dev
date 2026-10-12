import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.noetic_scope import Scope, ScopeStore
from scripts.noetic_sessions import SessionService


class EffortBranchProjectionTests(unittest.TestCase):
    def test_paginated_roots_include_fresh_metadata_without_enriching_scope_scan(self):
        with tempfile.TemporaryDirectory(prefix="noetic-effort-projection-") as home:
            root = Path(home)
            service = SessionService(root / "runs", namespace_path=root / "namespace.sqlite3", pi_command=["/bin/false"])
            for number in range(200):
                service.create_effort({"intent": f"Effort {number}", "environment": {"cwd": str(root)}})
            store = service.registry.domain.store()
            child = store.delegate("0.0", scope=Scope.effort("0.0"), mandate={"title": "Child"}, origin="human",
                                   human_ref={"owner": "fixture"}, source_ref={"fixture": "child"})
            described = []
            original = ScopeStore._describe
            def describe(instance, db, ordinal):
                described.append(ordinal)
                return original(instance, db, ordinal)
            records, after = [], 0
            with patch.object(ScopeStore, "_describe", describe):
                while True:
                    page = service.branch("0", after=after, limit=37)
                    if not page["records"]:
                        break
                    self.assertGreater(page["next_after"], after)
                    after = page["next_after"]
                    records.extend(page["records"])
            roots = [row for row in records if row["effort"] == row["ordinal"]]
            self.assertEqual(len(roots), 200)
            self.assertEqual(len(records), 202)
            self.assertEqual(len({row["allocation"] for row in records}), 202)
            self.assertEqual(roots[0]["environment"], {"cwd": str(root)})
            self.assertEqual(roots[-1]["intent"], "Effort 199")
            self.assertEqual([ordinal for ordinal in described if ordinal != "0"], [row["ordinal"] for row in roots], "only outer projection roots are enriched")
            self.assertNotIn("environment", next(row for row in records if row["ordinal"] == child["ordinal"]))
            self.assertNotIn("environment", store.branch("0")["records"][1], "default scope enumeration remains raw")
            store.set_environment("0.0", scope=Scope.effort("0.0"), environment={"cwd": str(root / "changed")}, source_ref={"fixture": "change"})
            store.revise_mandate("0.0", scope=Scope.effort("0.0"), mandate={"title": "Revised"}, origin="human",
                                 human_ref={"owner": "fixture"}, source_ref={"fixture": "change"})
            fresh = service.branch("0", limit=37)["records"][1]
            self.assertEqual(fresh["environment_version"], 2)
            self.assertEqual(fresh["environment"], {"cwd": str(root / "changed")})
            self.assertEqual(fresh["mandate"]["mandate"], {"title": "Revised"})
            scoped = service.branch("0.0", effort_root="0.0")["records"]
            self.assertEqual({row["effort"] for row in scoped}, {"0.0"})
            self.assertEqual(scoped[0]["environment_version"], 2)
            self.assertEqual(service.list(), [], "metadata reads do not create native sessions")


if __name__ == "__main__":
    unittest.main()
