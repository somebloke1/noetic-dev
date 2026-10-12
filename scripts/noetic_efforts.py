"""Installation-owned ordinal namespace adapter; native transcripts stay native."""
from pathlib import Path
import os

from scripts.noetic_scope import Scope, ScopeError, ScopeStore, Target


class Efforts:
    def __init__(self, source_root, *, namespace_path=None):
        self.path = (Path(namespace_path).expanduser().resolve() if namespace_path else
                     Path(os.environ["NOETIC_APP_HOME"]).expanduser().resolve() / "state" / "ordinals.sqlite3"
                     if os.environ.get("NOETIC_APP_HOME") else
                     Path(source_root).resolve() / "ordinals.sqlite3")

    def store(self, *, create=False):
        if not self.path.exists() and not create:
            raise ScopeError("Application namespace has not been registered")
        return ScopeStore(self.path, root_mandate={"purpose": "Coordinate explicitly registered human efforts"},
                          human_ref={"origin": "local-human-operator"},
                          source_ref={"adapter": "developer-sessions", "act": "register-application"})

    def scope(self, effort_root=None):
        if effort_root:
            return Scope.effort(effort_root)
        store = self.store()
        roots, after = [], 0
        while True:
            page = store.branch("0", after=after, limit=1000)
            if not page["records"]:
                break
            roots.extend(p["ordinal"] for p in page["records"] if p["ordinal"] == p["effort"])
            after = page["next_after"]
        return Scope.application(tuple(roots), root_mandate_version=store.position("0")["mandate_version"])

    def create(self, body):
        if not isinstance(body, dict) or set(body) - {"intent", "environment", "mandate", "human_ref", "source_ref"}:
            raise ScopeError("Unknown effort registration option")
        environment = body.get("environment")
        if not isinstance(environment, dict) or not isinstance(environment.get("cwd"), str):
            raise ScopeError("Effort environment requires an explicit absolute cwd")
        cwd = Path(environment["cwd"]).expanduser()
        if not cwd.is_absolute():
            raise ScopeError("Effort environment cwd must be absolute")
        return self.store(create=True).create_effort(
            intent=body.get("intent"), environment={**environment, "cwd": str(cwd.resolve())},
            mandate=body.get("mandate", {"purpose": body.get("intent")}), origin="human",
            human_ref=body.get("human_ref", {"origin": "local-human-operator"}),
            source_ref=body.get("source_ref", {"adapter": "developer-sessions", "act": "register-effort"}))
