"""Project preparation and retained controller-owned development workspaces."""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
import shutil
import stat
import subprocess
import uuid

from scripts.noetic_storage import ensure_private_directory


DEFAULT_PROJECT_ROOT = Path.home() / "workspace"
DEFAULT_WORK_ROOT = Path.home() / ".local/share/noetic-dev-work/task-worktrees"


class ProjectError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _git(directory, *args, input=None, check=True):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"USER_PROVIDED_PASSWORD", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(["git", "-C", str(directory), *args], input=input,
                                capture_output=True, timeout=60, env=environment)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProjectError(f"Git project preparation failed: {exc}") from exc
    if check and result.returncode:
        raise ProjectError(result.stderr.decode("utf-8", errors="replace").strip() or "Git project preparation failed.")
    return result


def _directory(directory, projects_root=None):
    if not isinstance(directory, (str, Path)) or not str(directory).strip() or "\0" in str(directory):
        raise ProjectError("Choose a project folder.")
    try:
        path = Path(directory).expanduser()
        if not path.is_absolute():
            if len(path.parts) != 1 or path.name in (".", ".."):
                raise ProjectError("Use a project name or an absolute project folder path.")
            root = Path(projects_root or DEFAULT_PROJECT_ROOT).expanduser()
            if not root.is_absolute():
                raise ProjectError("Choose an absolute projects location.")
            path = root / path
        path = path.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ProjectError(f"Invalid project folder: {exc}") from exc
    if path == Path(path.anchor):
        raise ProjectError("Choose a project folder beneath the filesystem root.")
    if path.exists() and not path.is_dir():
        raise ProjectError("Project folder is a file, not a directory.")
    return path


def validate_workspace(directory, *, projects_root=None):
    path = _directory(directory, projects_root)
    if not path.exists():
        raise ProjectError("Project folder does not exist. Create a new project explicitly.")
    return path


def prepare_project(directory, *, create=False, projects_root=None):
    path = _directory(directory, projects_root)
    try:
        if not path.exists():
            if not create:
                raise ProjectError("Project folder does not exist. Create a new project explicitly.")
            path.mkdir(parents=True, mode=0o755)
            _git(path, "init", "--quiet")
        probe = _git(path, "rev-parse", "--is-inside-work-tree", check=False)
        if probe.returncode:
            _git(path, "init", "--quiet")
        elif probe.stdout.strip() != b"true":
            raise ProjectError("Choose a normal project folder, not a bare repository or Git metadata directory.")
        repository = Path(os.fsdecode(_git(path, "rev-parse", "--show-toplevel").stdout).strip()).resolve()
        if repository != path:
            raise ProjectError(f"This folder belongs to parent project {repository}. Open that project root, or create a separate new project explicitly.")
        return path
    except OSError as exc:
        raise ProjectError(f"Could not prepare project folder: {exc}") from exc


def create_project(directory, *, projects_root=None):
    path = _directory(directory, projects_root)
    try:
        if path.exists() and any(path.iterdir()):
            raise ProjectError("Project folder is not empty. Open it as an existing project; its files were preserved.", 409)
        path.mkdir(parents=True, mode=0o755, exist_ok=True)
        _git(path, "init", "--quiet")
    except OSError as exc:
        raise ProjectError(f"Could not create the chosen project folder: {exc}") from exc
    return path


def fingerprint(path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode):
        data = os.fsencode(os.readlink(path))
        return {"kind": "symlink", "sha256": hashlib.sha256(data).hexdigest(), "mode": stat.S_IMODE(mode)}
    if not stat.S_ISREG(mode):
        return {"kind": "unsupported", "mode": stat.S_IMODE(mode)}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(65536):
            digest.update(data)
    return {"kind": "file", "sha256": digest.hexdigest(), "mode": stat.S_IMODE(mode)}


def selected_paths(workspace):
    listed = _git(workspace, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout
    return [os.fsdecode(part) for part in listed.split(b"\0") if part]


def working_files(workspace):
    files = {}
    for directory, names, filenames in os.walk(workspace, followlinks=False):
        names[:] = [name for name in names if name != ".git"]
        for name in [*filenames, *(name for name in names if (Path(directory) / name).is_symlink())]:
            path = Path(directory) / name
            if name == ".git":
                continue
            files[str(path.relative_to(workspace))] = fingerprint(path)
    return files


def task_worktree(project, *, work_root=None, exclude=()):
    project = prepare_project(project, create=False)
    repository = Path(os.fsdecode(_git(project, "rev-parse", "--show-toplevel").stdout).strip()).resolve()
    area = Path(work_root or DEFAULT_WORK_ROOT).expanduser().resolve()
    if ".runtime" in area.parts or area.is_relative_to(repository):
        raise ProjectError("The owned task work area must be outside the project and adopted .runtime state.")
    ensure_private_directory(area)
    worktree = area / uuid.uuid4().hex
    excluded = tuple(Path(path).resolve() for path in exclude)
    head = _git(repository, "rev-parse", "--verify", "HEAD^{commit}", check=False)
    if head.returncode:
        tree = _git(repository, "hash-object", "-t", "tree", "--stdin", input=b"").stdout.strip()
        head = _git(repository, "-c", "user.name=noetic-dev", "-c", "user.email=noetic-dev@localhost",
                    "-c", "commit.gpgsign=false", "commit-tree", tree.decode(), "-m", "noetic-dev empty task seed")
    base = head.stdout.decode().strip()
    try:
        _git(repository, "worktree", "add", "--quiet", "--detach", "--no-checkout", str(worktree), base)
        worktree.chmod(0o700)
        _git(worktree, "read-tree", base)
        listed = _git(repository, "ls-files", "--cached", "--others", "-z").stdout
        for name in sorted({os.fsdecode(part) for part in listed.split(b"\0") if part}):
            source = repository / name
            if ".git" in Path(name).parts or any(source.is_relative_to(path) for path in excluded):
                continue
            target = worktree / name
            if not source.exists() and not source.is_symlink():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = source.lstat().st_mode
            if stat.S_ISLNK(mode):
                target.symlink_to(os.readlink(source))
            elif stat.S_ISREG(mode):
                shutil.copy2(source, target)
            elif stat.S_ISDIR(mode):
                def ignored(directory, names):
                    return [entry for entry in names if entry == ".git" or any((Path(directory) / entry).is_relative_to(path) for path in excluded)]
                shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True, ignore=ignored)
            else:
                raise ProjectError(f"Project contains an unsupported file type: {source}")
        workspace = worktree / project.relative_to(repository)
        workspace.mkdir(parents=True, exist_ok=True)
    except (OSError, ProjectError) as exc:
        raise ProjectError(f"Task workspace preparation failed; retained at {worktree}: {exc}") from exc
    return {"project": str(project), "workspace": str(workspace), "owned_worktree": str(worktree), "base_commit": base,
            "initial_files": working_files(workspace),
            "selected_paths": [name for name in selected_paths(project) if not any((project / name).is_relative_to(path) for path in excluded)],
            "excluded_paths": [str(path) for path in excluded]}
