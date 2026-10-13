"""Local-only private Linux release assembly, installation and code rollback."""

import argparse
import base64
from contextlib import ExitStack, contextmanager
import csv
from email.parser import BytesParser
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
import zipfile

from scripts.noetic_archive import (MAX_BYTES, MAX_FILES, read_regular, safe_name, private_directory,
                                   read_bundle, write_bundle, extract_files, quiescent_run)
from scripts.noetic_storage import open_private, inspect_tree
from scripts import noetic_opermem_component as opermem_component

BOOTSTRAP = ("scripts/__init__.py", "scripts/noetic_storage.py", "scripts/noetic_processes.py",
             "scripts/noetic_archive.py", "scripts/noetic_release.py",
             "scripts/noetic_opermem_component.py",
             "scripts/noetic_opermem_application.py", "scripts/noetic_opermem.py", "scripts/noetic_opermem_scope.py",
             "scripts/noetic_opermem_checking.py", "scripts/noetic_opermem_judgment.py",
             "scripts/noetic_opermem_practical.py", "scripts/noetic_opermem_decision.py",
             "scripts/noetic_opermem_acting.py", "scripts/noetic_act_observation.py",
             "scripts/noetic_run.py", "scripts/noetic_controller.py",
             "scripts/noetic_harness.py", "scripts/noetic_changes.py",
             "scripts/noetic_develop.py", "scripts/noetic_telos.py",
             "scripts/noetic_disciplines.py", "scripts/noetic_scope.py", "scripts/noetic_projects.py",
             "scripts/noetic_purpose_binding.py", "scripts/noetic_purposes.py", "scripts/noetic_efforts.py")
REQUIRED_ASSETS = (*BOOTSTRAP, "scripts/noetic.py", "scripts/noetic_harness.py",
                   "scripts/noetic_application.py", "scripts/noetic_access.py",
                   "scripts/noetic_local.py", "scripts/noetic_semantic.py",
                   "scripts/noetic_web.py", "scripts/noetic_memory.py",
                   "scripts/noetic_changes.py", "scripts/noetic_develop.py",
                   "scripts/noetic_batch.py", "scripts/noetic_telos.py",
                   "scripts/telos_bridge.mjs", "scripts/patterns/cognition.json",
                   "scripts/patterns/development.json", "scripts/web/index.html",
                   "scripts/web/app.js", "scripts/web/sessions.js", "scripts/web/style.css",
                   "scripts/web/shell.js", "scripts/web/shell-agentics.js", "scripts/web/shell-agentics.css",
                   "scripts/web/shell-library.js", "scripts/web/shell-library.css",
                   "scripts/web/fonts/inter-latin.woff2", "scripts/web/fonts/dm-mono-latin.woff2",
                   "scripts/web/fonts/dm-mono-medium-latin.woff2", "scripts/web/THIRD_PARTY_NOTICES.txt",
                   "scripts/noetic_genus.py", "scripts/noetic_opermem.py",
                   "scripts/noetic_opermem_checking.py", "scripts/noetic_opermem_judgment.py",
                   "scripts/noetic_checking_tests.py", "scripts/noetic_opermem_practical.py", "scripts/noetic_opermem_decision.py",
                   "scripts/noetic_opermem_acting.py", "scripts/noetic_act_observation.py",
                   "scripts/noetic_sessions.py", "scripts/noetic_usage.py", "scripts/noetic_costs.py", "scripts/noetic_projects.py", "scripts/noetic_session_extension.mjs",
                   "scripts/noetic_efforts.py", "scripts/noetic_purposes.py", "scripts/noetic_recall.py")


def check_node24():
    """Probe the installed runtime without opening a database or invoking Telos."""
    try:
        version = subprocess.run(["node", "--version"], check=True, capture_output=True,
                                 text=True, timeout=10).stdout.strip()
        if not re.fullmatch(r"v24\.[0-9]+\.[0-9]+", version):
            raise ValueError(f"Requires Node 24 with node:sqlite; found {version}")
        subprocess.run(["node", "--input-type=module", "-e",
                        "import { DatabaseSync } from 'node:sqlite'; "
                        "if (typeof DatabaseSync !== 'function') process.exit(1);"],
                       check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Requires an available Node 24 runtime with node:sqlite") from exc


def wheel_info(data, filename):
    if not re.fullmatch(r"noetic_dev-[0-9][A-Za-z0-9.]*-py3-none-any\.whl", filename):
        raise ValueError("Expected a pure-Python noetic_dev wheel")
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        entries = wheel.infolist()
        if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_BYTES:
            raise ValueError("Wheel exceeds limits")
        names = set()
        for entry in entries:
            safe_name(entry.filename)
            if entry.filename in names or stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG):
                raise ValueError("Invalid wheel member")
            names.add(entry.filename)
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected one wheel metadata document")
        prefix = metadata[0].rsplit("/", 1)[0]
        meta = BytesParser().parsebytes(wheel.read(metadata[0]))
        version = meta["Version"]
        if meta["Name"] != "noetic-dev" or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version or ""):
            raise ValueError("Invalid Noetic identity/version")
        optional_sdk = r"mcp\s*>=\s*1\.0\s*;\s*extra\s*==\s*([\"'])genus\1"
        requirements = meta.get_all("Requires-Dist", [])
        if (filename != f"noetic_dev-{version}-py3-none-any.whl"
                or any("genus" not in meta.get_all("Provides-Extra", [])
                       or not re.fullmatch(optional_sdk, requirement.strip()) for requirement in requirements)):
            raise ValueError("Only dependency-free Noetic wheels are supported")
        wheel_meta = BytesParser().parsebytes(wheel.read(prefix + "/WHEEL"))
        if wheel_meta["Root-Is-Purelib"] != "true" or wheel_meta.get_all("Tag") != ["py3-none-any"]:
            raise ValueError("Unsupported wheel format")
        records = list(csv.reader(io.StringIO(wheel.read(prefix + "/RECORD").decode())))
        seen = set()
        for name, digest, size in records:
            if name in seen or name not in names:
                raise ValueError("Invalid wheel RECORD membership")
            seen.add(name)
            if name == prefix + "/RECORD":
                if digest or size:
                    raise ValueError("Invalid wheel RECORD self-entry")
                continue
            content = wheel.read(name)
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
            if digest != expected or size != str(len(content)):
                raise ValueError("Wheel RECORD checksum mismatch")
        if seen != names:
            raise ValueError("Wheel has unrecorded files")
        for name in REQUIRED_ASSETS:
            if name not in names:
                raise ValueError(f"Wheel missing runtime asset: {name}")
        return version, {name: wheel.read(name) for name in BOOTSTRAP}


def validate_assets(files, manifest):
    wheel_name = manifest["wheel"]
    if not wheel_name.startswith("wheel/") or len(Path(wheel_name).parts) != 2:
        raise ValueError("Invalid wheel path")
    version, bootstrap = wheel_info(files[wheel_name], Path(wheel_name).name)
    if version != manifest["release_version"] or manifest.get("controller_schema") != 1:
        raise ValueError("Incompatible release/schema")
    if any(files.get(name) != data for name, data in bootstrap.items()):
        raise ValueError("Bootstrap must be identical to the wheel modules")
    telos = json.loads(files["components/telos-core.manifest.json"])
    if any(telos.get(k) != v for k, v in {"module": "telos-core.mjs", "format": "esm", "target": "node24", "platform": "node"}.items()):
        raise ValueError("Unsupported Telos manifest")
    core = files["components/telos-core.mjs"]
    if hashlib.sha256(core).hexdigest() != telos.get("sha256") or "createPiCoreGoalChainStore" not in core.decode():
        raise ValueError("Telos module/hash mismatch")
    if hashlib.sha256(files["LICENSE.md"]).hexdigest() != "78802d87feef90aec2e3336d7d82ef18d336fb061c74f48635ae0088e3187753":
        raise ValueError("Supply the unchanged Noetic all-rights-reserved LICENSE.md")
    if hashlib.sha256(files["THIRD_PARTY_NOTICES.txt"]).hexdigest() != "e8fb9203c118cf58ff1ff8f1937beaa6c8e923855a5abde4d50fa5cd9f2e755d":
        raise ValueError("Supply the exact Telos MIT notice from docs/THIRD_PARTY_NOTICES.txt")
    allowed = {wheel_name, *BOOTSTRAP, "components/telos-core.mjs", "components/telos-core.manifest.json",
               "LICENSE.md", "THIRD_PARTY_NOTICES.txt"}
    native_prefix = opermem_component.COMPONENT + "/"
    native_names = {native_prefix + n for n in (*opermem_component.EXECUTABLES, "component.json", "NOTICES.txt")}
    present = {n for n in files if n.startswith("components/opermem/")}
    if present:
        if present != native_names:
            raise ValueError("Opermem component requires exact host, child, manifest and private notices")
        native_manifest = json.loads(files[native_prefix + "component.json"])
        opermem_component.validate_component({n: files[native_prefix + n] for n in opermem_component.EXECUTABLES}, native_manifest)
        if not files[native_prefix + "NOTICES.txt"].strip():
            raise ValueError("Opermem requires truthful component notices")
        allowed |= native_names
    docs = [n for n in files if n.startswith("docs/") and len(Path(n).parts) == 2 and Path(n).suffix in (".md", ".txt")]
    if not docs or set(files) != allowed | set(docs):
        raise ValueError("Release must contain only specified code, notices and documentation")
    return version


def build_release(output, *, wheel, telos_module, telos_manifest, license_file, notices, docs,
                  opermem_host=None, opermem_child=None, opermem_manifest=None, opermem_notices=None):
    check_node24()
    wheel = Path(wheel)
    wheel_data = read_regular(wheel)
    version, bootstrap = wheel_info(wheel_data, wheel.name)
    files = {**bootstrap, f"wheel/{wheel.name}": wheel_data,
             "components/telos-core.mjs": read_regular(telos_module),
             "components/telos-core.manifest.json": read_regular(telos_manifest),
             "LICENSE.md": read_regular(license_file), "THIRD_PARTY_NOTICES.txt": read_regular(notices)}
    native_inputs = (opermem_host, opermem_child, opermem_manifest, opermem_notices)
    if any(value is not None for value in native_inputs):
        if not all(value is not None for value in native_inputs):
            raise ValueError("Supply the exact Opermem host/child pair, manifest and private notices together")
        for name, source in zip((*opermem_component.EXECUTABLES, "component.json", "NOTICES.txt"), native_inputs):
            files[opermem_component.COMPONENT + "/" + name] = read_regular(source)
    for doc in docs:
        name = "docs/" + Path(doc).name
        if name in files:
            raise ValueError("Duplicate documentation basename")
        files[name] = read_regular(doc)
        if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
            raise ValueError("Release exceeds bundle limits")
    manifest = {"format": "noetic-private-release", "version": 1, "release_version": version,
                "controller_schema": 1, "wheel": f"wheel/{wheel.name}", "privacy": "PRIVATE OWNER DELIVERY"}
    validate_assets(files, manifest)
    subprocess.run(["node", "--check", str(Path(telos_module).absolute())], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return write_bundle(output, files, manifest)


def status(home):
    home = Path(home).absolute()
    current = home / "current"
    release = None
    if current.is_symlink():
        target = os.readlink(current)
        if target == "legacy" and (home / "adoption.json").is_file():
            release = "legacy"
        elif not re.fullmatch(r"releases/[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{16}", target):
            raise ValueError("Invalid current release pointer")
        else:
            release = target.split("/")[1]
        if release != "legacy" and (not (home / target).is_dir() or (home / target).is_symlink()):
            raise ValueError("Current release missing or linked outside home")
    elif current.exists():
        raise ValueError("Current must be a managed symlink")
    adoption = json.loads(read_regular(home / "adoption.json")) if (home / "adoption.json").exists() else {}
    result = json.loads(read_regular(home / "maintenance-result.json")) if (home / "maintenance-result.json").exists() else {}
    return {"home": str(home), "current": release, "state": adoption.get("state", str(home / "state")),
            "adoption": adoption, "last_maintenance": result,
            "releases": sorted(p.name for p in (home / "releases").glob("*") if p.is_dir() and not p.is_symlink())}


@contextmanager
def maintenance(home, allow_held, *, code_only=False, adoption=None, coexist=None, coexist_state=None):
    home = Path(home).absolute()
    if home == Path.home() or home == Path(home.anchor) or any((home / n).exists() for n in (".git", "pyproject.toml")):
        raise ValueError("Select a dedicated private app home, not a home directory or checkout")
    home = private_directory(home)
    with ExitStack() as stack:
        lock = stack.enter_context(open_private(home / ".maintenance.lock", "a"))
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another release operation is active") from exc
        if adoption:
            # Retain the selected scope even if a later gate/build fails. A retry
            # must never fall back to a new, empty home/state.
            with open_private(home / "adoption.json", "x") as stream:
                json.dump(adoption, stream, sort_keys=True)
        for name in ("releases", "bin"):
            private_directory(home / name)
        state = Path((adoption or status(home)["adoption"]).get("state", str(home / "state")))
        if code_only:
            paths = _code_state_paths(state)
        else:
            if state == home / "state":
                private_directory(state)
            elif not state.is_dir():
                raise ValueError("Adopted external state is missing; refusing an empty replacement")
            report = inspect_tree(state)
            if report["skipped"]:
                raise ValueError("Selected state contains links or unsupported entries")
            paths = sorted(state.rglob("*.lock"))
        # Independent drivers survive server closure. The operator must also stop
        # launchers and noncooperating writers; these locks are not a daemon manager.
        recognized = set()
        if code_only and coexist:
            _, recognized_brokers = _coexist_plan(state, home, coexist)
            if coexist_state is not None:
                coexist_state["expected"] = recognized_brokers
            recognized = set(recognized_brokers)
        for path in (p for p in paths if p.name.endswith(".lock")):
            if not code_only and path.name in ("driver.lock", "application-driver.lock") and (path.parent / "events.sqlite3").is_file():
                continue
            # Only the exact recognized live broker's own session lock is exempt.
            if code_only and path.name == "broker.lock" and _coexist_shape(path, state) and path.parent.name in recognized:
                continue
            stream = stack.enter_context(path.open("rb") if code_only else open_private(path, "a"))
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError(f"Owned state lock: {path}") from exc
        yield home


def _check_state(home, stack, allow_held):
    state = Path(status(home)["state"])
    for journal in sorted(state.rglob("events.sqlite3")):
        stack.enter_context(quiescent_run(journal.parent, allow_held))
    for store in state.rglob("controller.sqlite3"):
        if not (store.parent / "events.sqlite3").is_file():
            raise ValueError("Controller without a run journal")


def _code_state_paths(state_root):
    """Inventory existing entries without reading product histories or creating state."""
    state_root = Path(state_root).absolute()
    if state_root == Path(state_root.anchor) or state_root == Path.home() or state_root in Path.home().parents:
        raise ValueError("Select only a Noetic-owned state directory, not home or an ancestor")
    if any(p.is_symlink() for p in (state_root, *state_root.parents)):
        raise ValueError("Selected state contains links or unsupported entries")
    try:
        info = state_root.stat()
    except FileNotFoundError:
        return []
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise ValueError("Selected state is not an owned directory")
    paths = []

    def fail(error):
        raise error

    for directory, directories, files in os.walk(state_root, followlinks=False, onerror=fail):
        if any(name in directories + files for name in (".git", "pyproject.toml", "package.json")):
            raise ValueError(f"Refusing source/workspace directory: {directory}")
        for name in directories + files:
            path = Path(directory) / name
            info = path.lstat()
            if (info.st_uid != os.geteuid() or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
                    or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
                raise ValueError("Selected state contains links or unsupported entries")
            if stat.S_ISREG(info.st_mode):
                paths.append(path)
    return sorted(paths)


def _proc_link(pid, name):
    return os.readlink(f"/proc/{pid}/{name}")


def _proc_cmdline(pid):
    return Path(f"/proc/{pid}/cmdline").read_bytes()


_COEXIST_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _coexist_shape(path, state_root):
    """Exact developer-session broker ownership path shape; no history reading."""
    session = path.parent
    return (path.name in ("broker.lock", "broker-ownership.json")
            and re.fullmatch(_COEXIST_UUID, session.name) is not None
            and session.parent == Path(state_root) / "runs" / "developer-sessions")


def _coexist_release(home, coexist):
    """Verify the named retained release root, payload and interpreter; read-only."""
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{16}", coexist or ""):
        raise ValueError("Select an installed retained broker release ID from status")
    home = Path(home).absolute()
    root = home / "releases" / coexist
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Named retained broker release is missing")
    manifest = json.loads(read_regular(root / "release.json"))
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    if coexist != manifest["release_version"] + "-" + identity:
        raise ValueError("Named retained broker release identity mismatch")
    files = {name: read_regular(root / name) for name in manifest["files"]}
    if manifest["files"] != {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}:
        raise ValueError("Named retained broker release checksum mismatch")
    validate_assets(files, manifest)
    python = root / "venv/bin/python"
    if not python.is_file():
        raise ValueError("Named retained broker release interpreter missing")
    check_installed_files(root, files[manifest["wheel"]])
    sites = [p for p in (root / "venv/lib").glob("python*/site-packages") if p.is_dir()]
    if len(sites) != 1:
        raise ValueError("Named retained broker release site-packages is unresolved")
    return {"home": str(home), "release": coexist, "root": str(root),
            "exe": str(python), "site_packages": str(sites[0])}


def _coexist_recognize(path, evidence, state_root, record):
    """Recognize one live developer-session broker of the named release via /proc."""
    from scripts import noetic_processes
    session = path.parent.name
    if record.get("state") != "owned" or "identity" not in record:
        raise ValueError(f"Known live or unverifiable owned group; code switch refused: {path}")
    pid = record["identity"]["pid"]
    cwd = _proc_link(pid, "cwd")
    if cwd != evidence["site_packages"]:
        raise ValueError(f"Recognized broker cwd does not match the named release: {path}")
    if Path(_proc_link(pid, "exe")) != Path(os.path.realpath(evidence["exe"])):
        raise ValueError(f"Broker executable does not match the named release: {path}")
    try:
        argv = [item.decode("utf-8") for item in _proc_cmdline(pid).split(b"\0") if item]
    except UnicodeDecodeError:
        raise ValueError(f"Broker command line is not decodable: {path}")
    alias = str(Path(evidence["home"]) / "current" / "venv" / "bin" / "python")
    # argv0 is accepted only lexically; the managed current alias moves after a
    # pointer switch and is never resolved here.
    if not argv or argv[0] not in (alias, evidence["exe"]):
        raise ValueError(f"Broker argv0 is neither the named release interpreter nor the managed current alias: {path}")
    if argv[1:6] != ["-m", "scripts.noetic_sessions", "broker", str(Path(state_root) / "runs"), session]:
        raise ValueError(f"Broker command line does not match this session and runs root: {path}")
    if len(argv) != 8 or not argv[6].isdigit() or not argv[7].startswith("/"):
        raise ValueError(f"Broker namespace descriptor/path is invalid: {path}")
    return {"session": session, "pid": pid, "start_ticks": record["identity"]["start_ticks"],
            "namespace_path": argv[7]}


def _coexist_plan(state_root, home, coexist):
    """Named-release evidence plus currently recognized live broker sessions."""
    from scripts import noetic_processes
    evidence = _coexist_release(home, coexist)
    recognized = {}
    for path in (p for p in _code_state_paths(state_root) if _coexist_shape(p, state_root)):
        record = noetic_processes.inspect(path)
        if record["state"] == "owned":
            broker = _coexist_recognize(path, evidence, state_root, record)
            recognized[path.parent.name] = broker
    return evidence, recognized


def _check_code_state(state_root, allow_held, *, coexist=None, coexist_home=None, expected=None):
    """Check recorded process safety; leave historical semantics and compatibility unknown."""
    from scripts import noetic_processes
    paths = _code_state_paths(state_root)
    ownership = [p for p in paths if p.name.endswith("-ownership.json")]
    evidence = _coexist_release(coexist_home, coexist) if coexist else None
    recognized = []
    for path in ownership:
        record = noetic_processes.inspect(path)
        # Only an exact recognized live developer-session broker of the named
        # retained release is exempt; every other record follows the ordinary gate.
        if evidence and _coexist_shape(path, state_root) and record["state"] == "owned":
            recognized.append(_coexist_recognize(path, evidence, state_root, record))
            continue
        if not record["cleanup_confirmed"]:
            raise ValueError("Known live or unverifiable owned group; code switch refused")
    # Missing identity cannot be counted without interpreting potentially broken
    # histories. Even ended recorded groups do not certify all historical cleanup.
    result = {"mode": "code-only" if not evidence else "code-only-coexistence",
              "retained_state": "available" if state_root.is_dir() else "absent",
            "history_assessment": "not_performed", "data_compatibility": "unknown",
            "process_inspection": "existing ownership records and cooperative locks only",
            "ownership_records_inspected": len(ownership),
            "historical_cleanup_confirmed": False, "unknown_ownership_records": None,
            "message": "code updated, historical cleanup unconfirmed"}
    if evidence:
        # Pre-switch recheck: recognition above re-read live identities and the
        # named retained root was re-verified; nothing else is exempt. The final
        # live set must exactly match the initial recognition (same sessions,
        # pid/start_ticks and namespace); any change refuses before the switch.
        if expected is not None and {b["session"]: b for b in recognized} != expected:
            raise ValueError("Recognized broker set or identity changed during maintenance; refusing before switch")
        result["coexistence"] = {"broker_release": evidence["release"],
                                 "recognized_brokers": recognized}
        result["message"] = "code updated, recognized live brokers preserved, historical cleanup unconfirmed"
    return result


def _switch(home, release):
    temporary = home / ".current-next"
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("Unfinished pointer operation; inspect .current-next")
    os.symlink("legacy" if release == "legacy" else "releases/" + release, temporary)
    os.replace(temporary, home / "current")


def check_installed_files(target, wheel_data):
    """Check the pure-Python payload the launcher uses, not just its retained wheel."""
    target = Path(target).absolute()
    result = subprocess.run([str(target / "venv/bin/python"), "-I", "-c",
                             "import sysconfig; print(sysconfig.get_path('purelib'))"],
                            check=True, capture_output=True, text=True, timeout=10)
    installed = Path(result.stdout.strip()).absolute()
    if not installed.is_relative_to(target / "venv"):
        raise ValueError("Installed package directory is outside the release venv")
    with zipfile.ZipFile(io.BytesIO(wheel_data)) as wheel:
        for name in wheel.namelist():
            # pip rewrites RECORD and adds its own metadata/bytecode. All original
            # wheel payload files other than RECORD must remain byte-identical.
            if name.endswith(".dist-info/RECORD"):
                continue
            try:
                data = read_regular(installed / name)
            except OSError as exc:
                raise ValueError(f"Installed runtime file missing: {name}") from exc
            if data != wheel.read(name):
                raise ValueError(f"Installed runtime file changed: {name}")


def _launcher_text(home, binding, *, generation=3):
    text = (f"#!/bin/sh\n# noetic-private-launcher-v{generation}\nset -eu\numask 077\n"
            f"APP_HOME={shlex.quote(str(home))}\n"
            'RELEASE=$(readlink -f "$APP_HOME/current")\n'
            'export NOETIC_TELOS_SOURCE="${NOETIC_TELOS_SOURCE:-$RELEASE/components/telos-core.mjs}"\n'
            'export NOETIC_APP_HOME="$APP_HOME"\n'
            'export NOETIC_STATE_HOME="$APP_HOME/state"\n'
            'unset PYTHONPATH PYTHONHOME\n'
            'exec "$RELEASE/venv/bin/python" -I -m scripts.noetic "$@"\n')
    if generation >= 3:
        text = text.replace('export NOETIC_APP_HOME=', 'export NOETIC_OPERMEM_HOST="${NOETIC_OPERMEM_HOST:-$RELEASE/components/opermem/linux-x86_64-gnu/opermem-operation-host}"\nexport NOETIC_APP_HOME=')
    if binding:
        legacy_context = (f'cd {shlex.quote(binding["legacy_cwd"])}\n'
            f'if [ ! -d {shlex.quote(str(Path(binding["state"]) / "runs"))} ]; then\n'
            '  printf "%s\\n" "Adopted external state/runs is missing; refusing an empty replacement" >&2\n'
            '  exit 2\nfi\n')
        legacy_selection = 'if [ "$(readlink "$APP_HOME/current")" = legacy ]; then\n'
        # Generation 1 is retained exactly for recognition of managed upgrades.
        # Only explicit legacy selection inherits that working environment now.
        invocation = (legacy_context + legacy_selection if generation == 1 else
                      legacy_selection + legacy_context)
        text = text.replace('RELEASE=$(readlink -f "$APP_HOME/current")\n',
            invocation + f'  exec {shlex.quote(binding["legacy_launcher"])} "$@"\nfi\n'
            'RELEASE=$(readlink -f "$APP_HOME/current")\n')
        text = text.replace('export NOETIC_STATE_HOME="$APP_HOME/state"',
                            f'export NOETIC_STATE_HOME={shlex.quote(binding["state"])}')
    return text


def install_release(archive, home, *, allow_held=False, python=sys.executable,
                    code_only=False, adopt_state=None, legacy_launcher=None, legacy_cwd=None,
                    coexist=None):
    if coexist is not None and not code_only:
        raise ValueError("Broker coexistence requires --code-only")
    if sys.platform != "linux" or sys.version_info < (3, 10):
        raise ValueError("Requires POSIX Linux and Python 3.10+")
    check_node24()
    files, manifest = read_bundle(archive, "noetic-private-release")
    version = validate_assets(files, manifest)
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
    release = version + "-" + identity
    adoption = None
    if any(p is not None for p in (adopt_state, legacy_launcher, legacy_cwd)):
        if not code_only or not all(p is not None for p in (adopt_state, legacy_launcher, legacy_cwd)):
            raise ValueError("Adoption requires --code-only, --adopt-state, --legacy-launcher and --legacy-cwd")
        if Path(home).exists():
            raise ValueError("Adoption requires a new dedicated app home")
        state, launcher, cwd = (Path(p).absolute() for p in (adopt_state, legacy_launcher, legacy_cwd))
        if not cwd.is_dir() or not launcher.is_file() or not os.access(launcher, os.X_OK):
            raise ValueError("Adoption requires a legacy working directory and executable launcher")
        resolved_home, resolved_state = Path(home).resolve(), state.resolve()
        if resolved_state.is_relative_to(resolved_home) or resolved_home.is_relative_to(resolved_state):
            raise ValueError("Code home and external state must be disjoint")
        adoption = {"state": str(state), "legacy_launcher": str(launcher), "legacy_cwd": str(cwd)}
    coexist_state = {}
    with maintenance(home, allow_held, code_only=code_only, adoption=adoption, coexist=coexist,
                     coexist_state=coexist_state) as home, ExitStack() as stack:
        binding = adoption or status(home)["adoption"]
        state_root = Path(binding.get("state", str(home / "state")))
        if code_only:
            result = _check_code_state(state_root, allow_held, coexist=coexist, coexist_home=home,
                                       expected=coexist_state.get("expected"))
        else:
            _check_state(home, stack, allow_held)
            result = {"mode": "strict", "message": "code updated"}
        before = status(home)
        target = home / "releases" / release
        if target.exists() or target.is_symlink():
            raise FileExistsError("Release already installed; select it with rollback")
        wrapper = home / "bin/noetic"
        wrapper_text = _launcher_text(home, binding)
        previous_wrapper = read_regular(wrapper) if wrapper.exists() or wrapper.is_symlink() else None
        previous_mode = stat.S_IMODE(wrapper.stat().st_mode) if previous_wrapper is not None else None
        if previous_wrapper is not None and previous_wrapper not in (
                wrapper_text.encode(), _launcher_text(home, binding, generation=1).encode(),
                _launcher_text(home, binding, generation=2).encode()):
            raise ValueError("Refusing to overwrite an unmanaged home/bin/noetic")
        wrapper_started = False
        private_directory(target)
        try:
            extract_files(target, files)
            native_host = target / opermem_component.COMPONENT / "opermem-operation-host"
            if native_host.exists():
                opermem_component.check_platform()
                for name in opermem_component.EXECUTABLES:
                    (native_host.parent / name).chmod(0o700)
                configured = opermem_component.host_configuration(native_host)
                if not configured["available"]:
                    raise ValueError(configured["reason"])
            subprocess.run(["node", "--check", str(target / "components/telos-core.mjs")], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with open_private(target / "release.json", "x") as stream:
                json.dump(manifest, stream, sort_keys=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("PIP_", "PYTHON")) and k != "USER_PROVIDED_PASSWORD"}
            env["PIP_CONFIG_FILE"] = os.devnull
            subprocess.run([str(python), "-m", "venv", "--copies", str(target / "venv")], check=True, env=env)
            subprocess.run([str(target / "venv/bin/python"), "-m", "pip", "--isolated", "install",
                            "--no-index", "--no-deps", "--no-cache-dir", "--disable-pip-version-check",
                            str(target / manifest["wheel"])], check=True, env=env)
            for directory, _, names in os.walk(target):
                os.chmod(directory, 0o700)
                for name in names:
                    path = Path(directory) / name
                    if not path.is_symlink():
                        os.chmod(path, 0o700 if path.stat().st_mode & 0o111 else 0o600)
            subprocess.run([str(target / "venv/bin/python"), "-I", "-m", "scripts.noetic", "--help"],
                           check=True, env=env, cwd=home, stdout=subprocess.DEVNULL)
            check_installed_files(target, files[manifest["wheel"]])
            if code_only:
                result = _check_code_state(state_root, allow_held, coexist=coexist, coexist_home=home,
                                           expected=coexist_state.get("expected"))
            wrapper_started = True
            with open_private(wrapper, "w") as stream:
                stream.write(wrapper_text)
            wrapper.chmod(0o700)
            _switch(home, release)
            with open_private(home / "maintenance-result.json", "w") as stream:
                json.dump(result, stream, sort_keys=True)
        except BaseException:
            if status(home)["current"] != release:
                if wrapper_started:
                    if previous_wrapper is None:
                        wrapper.unlink(missing_ok=True)
                    else:
                        with open_private(wrapper, "wb") as stream:
                            stream.write(previous_wrapper)
                        wrapper.chmod(previous_mode)
                shutil.rmtree(target)
            raise
    return {**status(home), "previous": before["current"], "advanced": False}


def rollback(home, release, *, allow_held=False, code_only=False, coexist=None):
    if release != "legacy" and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[a-f0-9]{16}", release):
        raise ValueError("Select an installed release ID from status")
    if coexist is not None and not code_only:
        raise ValueError("Broker coexistence requires --code-only")
    check_node24()
    coexist_state = {}
    with maintenance(home, allow_held, code_only=code_only, coexist=coexist,
                     coexist_state=coexist_state) as home, ExitStack() as stack:
        if code_only:
            result = _check_code_state(Path(status(home)["state"]), allow_held, coexist=coexist, coexist_home=home,
                                       expected=coexist_state.get("expected"))
        else:
            _check_state(home, stack, allow_held)
            result = {"mode": "strict", "message": "code updated"}
        previous = status(home)["current"]
        if release == "legacy":
            binding = status(home)["adoption"]
            if not binding or not Path(binding["legacy_launcher"]).is_file() or not os.access(binding["legacy_launcher"], os.X_OK):
                raise ValueError("Retained legacy launcher unavailable")
            _switch(home, release)
            with open_private(home / "maintenance-result.json", "w") as stream:
                json.dump(result, stream, sort_keys=True)
            return {**status(home), "previous": previous, "advanced": False}
        target = home / "releases" / release
        manifest = json.loads(read_regular(target / "release.json"))
        identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:16]
        if release != manifest["release_version"] + "-" + identity:
            raise ValueError("Installed release identity mismatch")
        files = {name: read_regular(target / name) for name in manifest["files"]}
        if manifest["files"] != {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}:
            raise ValueError("Installed release checksum mismatch")
        validate_assets(files, manifest)
        if not (target / "venv/bin/python").is_file():
            raise ValueError("Installed interpreter missing")
        check_installed_files(target, files[manifest["wheel"]])
        if code_only:
            result = _check_code_state(Path(status(home)["state"]), allow_held, coexist=coexist, coexist_home=home,
                                       expected=coexist_state.get("expected"))
        _switch(home, release)
        with open_private(home / "maintenance-result.json", "w") as stream:
            json.dump(result, stream, sort_keys=True)
    return {**status(home), "previous": previous, "advanced": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("output", type=Path)
    for name in ("wheel", "telos-module", "telos-manifest", "license-file", "notices"):
        build.add_argument("--" + name, type=Path, required=True)
    for name in ("opermem-host", "opermem-child", "opermem-manifest", "opermem-notices"):
        build.add_argument("--" + name, type=Path)
    build.add_argument("--doc", dest="docs", type=Path, action="append", required=True)
    install = commands.add_parser("install", help="Install or update using a local release ZIP")
    install.add_argument("archive", type=Path)
    install.add_argument("--python", default=sys.executable)
    install.add_argument("--adopt-state", type=Path, help="Bound external Noetic state path, possibly absent (no copying or migration)")
    install.add_argument("--legacy-launcher", type=Path, help="Retained original executable, not the public symlink to be switched")
    install.add_argument("--legacy-cwd", type=Path, help="Original invocation working/configuration root")
    back = commands.add_parser("rollback", help="Explicitly select a retained release")
    back.add_argument("release")
    for command in (install, back, commands.add_parser("status")):
        command.add_argument("--home", type=Path, default=os.environ.get("NOETIC_APP_HOME"),
                             required=not os.environ.get("NOETIC_APP_HOME"))
    for command in (install, back):
        command.add_argument("--allow-held", action="store_true")
        command.add_argument("--code-only", action="store_true", help="Switch code without assessing retained history; require existing locks and recorded process safety")
        command.add_argument("--coexist-brokers-from", metavar="RELEASE_ID", default=None,
                             help="Explicit retained-broker coexistence: code-only only; recognize live developer-session brokers of this installed release; caller declares the compatible code pair")
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    if command in ("install", "rollback"):
        args["coexist"] = args.pop("coexist_brokers_from")
    try:
        result = {"build": build_release, "install": install_release, "rollback": rollback, "status": status}[command](**args)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        parser.exit(2, f"release: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
