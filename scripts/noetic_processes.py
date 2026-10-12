"""Private stdin delivery and conservative Linux process-group ownership."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from uuid import UUID

if __package__:
    from scripts.noetic_storage import open_private
else:
    from noetic_storage import open_private


def identity(pid):
    # comm may contain spaces and parentheses; the remaining fields start at state.
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "pgid": int(fields[2]), "start_ticks": int(fields[19]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def save(path, data):
    temporary = path.with_name(path.name + ".tmp")
    with open_private(temporary) as stream:
        json.dump(data, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def spawn(argv, *, cwd, env, stdout, stderr, ownership_path, stdin_text=None):
    environment = dict(os.environ if env is None else env)
    environment.pop("USER_PROVIDED_PASSWORD", None)
    # A regular anonymous 0600 file cannot fill a pipe while the actor is busy.
    # Its descriptor, not its contents or pathname, crosses the process boundary.
    with ExitStack() as stack:
        source = subprocess.DEVNULL
        if stdin_text is not None:
            source = stack.enter_context(tempfile.TemporaryFile(mode="w+b", dir=ownership_path.parent))
            source.write(stdin_text.encode("utf-8"))
            source.seek(0)
        process = subprocess.Popen(argv, cwd=cwd, env=environment, stdin=source,
                                   stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            owner = identity(process.pid)
            save(ownership_path, {"identity": owner, "observed_at": time.time(), "state": "spawned"})
        except BaseException:
            # Still the original Popen owner; never leave a child on recording failure.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return process


def inspect(path):
    result = {"state": "unknown", "cleanup_confirmed": False, "observed_at": time.time()}
    try:
        owner = json.loads(path.read_text())["identity"]
        if (not isinstance(owner, dict) or set(owner) != {"pid", "pgid", "start_ticks", "boot_id"}
                or any(type(owner.get(k)) is not int or owner[k] <= 0 for k in ("pid", "pgid", "start_ticks"))
                or owner["pid"] != owner["pgid"] or not isinstance(owner.get("boot_id"), str)):
            return result
        current_boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        for boot_id in (owner["boot_id"], current_boot_id):
            parsed = UUID(boot_id)
            if str(parsed) != boot_id or parsed.version != 4:
                return result
        result["identity"] = owner
        if owner["boot_id"] != current_boot_id:
            # Kernel processes cannot survive their boot; reused numbers are unrelated.
            return {**result, "state": "boot_ended", "cleanup_confirmed": True,
                    "current_boot_id": current_boot_id}
        try:
            current = identity(owner["pid"])
        except FileNotFoundError:
            current = None
        if current is not None and current != owner:
            return {**result, "state": "mismatched"}
        try:
            os.killpg(owner["pgid"], 0)
        except ProcessLookupError:
            return {**result, "state": "absent", "cleanup_confirmed": True}
        return {**result, "state": "owned" if current == owner else "uncertain"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return result


def reconcile(path, *, terminate=False, timeout=3.0):
    """Inspect only the recorded PID/group; recheck identity before each signal."""
    result = inspect(path)
    if terminate and result["state"] == "owned":
        deadline = time.monotonic() + timeout
        for sig in (signal.SIGTERM, signal.SIGKILL):
            result = inspect(path)
            if result["state"] != "owned":
                break
            try:
                os.killpg(result["identity"]["pgid"], sig)
            except ProcessLookupError:
                break
            except PermissionError:
                break
            until = min(deadline, time.monotonic() + timeout / 2)
            while time.monotonic() < until:
                result = inspect(path)
                if result["state"] != "owned":
                    break
                time.sleep(0.05)
        result = inspect(path)
    save(path.with_name(path.stem + "-cleanup.json"), result)
    return result
