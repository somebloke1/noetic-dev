#!/usr/bin/env python3
"""One entry point for noetic-dev's local development workflow."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys


VERSION = "0.3.0"
COMMANDS = {
    "sessions": ("noetic_sessions", None),
    "harness": ("noetic_harness", None),
    "disciplines": ("noetic_disciplines", None),
    "purposes": ("noetic_purposes", None),
    "recall": ("noetic_recall", None),
    "local": ("noetic_local", None),
    "semantic": ("noetic_semantic", None),
    "storage": ("noetic_storage", None),
    "release": ("noetic_release", None),
    "archive": ("noetic_archive", None),
    "run": ("noetic_run", "run"),
    "list": ("noetic_run", "list"),
    "status": ("noetic_run", "status"),
    "events": ("noetic_run", "events"),
    "review": ("noetic_run", "review"),
    "develop": ("noetic_develop", None),
    "inquire": ("noetic_develop", "--inquiry"),
    "batch": ("noetic_batch", None),
    "goal": ("noetic_telos", None),
    "genus": ("noetic_genus", None),
    "opermem": ("noetic_opermem", None),
    "search": ("noetic_memory", "search"),
    "index": ("noetic_memory", "index"),
    "serve": ("noetic_web", None),
    "open": ("noetic_web", "open"),
}


def _has_option(arguments: list[str], name: str) -> bool:
    return any(value == name or value.startswith(name + "=") for value in arguments)


def _option_value(arguments: list[str], name: str) -> str | None:
    for index in range(len(arguments) - 1, -1, -1):
        value = arguments[index]
        if value.startswith(name + "="):
            return value[len(name) + 1:]
        if value == name:
            return arguments[index + 1] if index + 1 < len(arguments) else None
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in COMMANDS:
        command, arguments = argv[0], argv[1:]
        state = os.environ.get("NOETIC_STATE_HOME")
        harness_start = command == "harness" and arguments[:1] == ["start"]
        options = arguments
        if harness_start:
            remainder = next((index for index, value in enumerate(arguments)
                              if value == "--verify" or value.startswith("--verify=")), len(arguments))
            options = arguments[:remainder]
        uses_runs = command in ("serve", "open", "list", "sessions", "recall") or harness_start
        if state and uses_runs and not _has_option(options, "--runs-dir"):
            default = ["--runs-dir", str(Path(state) / "runs")]
            arguments = ([arguments[0], *default, *arguments[1:]] if harness_start else [*arguments, *default])
        app = os.environ.get("NOETIC_APP_HOME")
        if app and command in ("disciplines", "purposes", "recall") and not _has_option(arguments, "--namespace-path"):
            arguments = ["--namespace-path", str(Path(app) / "state" / "ordinals.sqlite3"), *arguments]
        if command == "recall" and not _has_option(arguments, "--sessions-home"):
            runs = _option_value(arguments, "--runs-dir")
            if runs is not None:
                arguments = [*arguments, "--sessions-home", runs]
        module, prefix = COMMANDS[command]
        implementation = importlib.import_module(f"scripts.{module}")
        return implementation.main(([prefix] if prefix else []) + arguments)
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Conversational developer sessions: sessions. Structured pattern controller: harness. Effort-scoped operations: disciplines, purposes, recall. Commands: goal, genus, opermem, list, status, events, search, index, local, semantic, storage, release, archive, serve, open, doctor. "
        "Legacy task utilities (not the pattern harness): run, develop, inquire, batch, review. "
        "Use noetic COMMAND --help for options."
    ))
    parser.add_argument("--version", action="version", version=f"noetic-dev {VERSION}")
    parser.add_argument("command", nargs="?", choices=[*COMMANDS, "doctor"])
    args = parser.parse_args(argv)
    if args.command == "doctor":
        from scripts.noetic_telos import source_path
        source = source_path()
        module_mode = source.suffix == ".mjs" and not source.is_dir()
        with sqlite3.connect(":memory:") as connection:
            try:
                connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
                fts5 = True
            except sqlite3.Error:
                fts5 = False
        print(json.dumps({
            "version": VERSION, "python": sys.version.split()[0], "sqlite_fts5": fts5,
            "clients": {name: shutil.which(name) for name in ("opencode", "pi")},
            "node": shutil.which("node"), "telos_source": str(source),
            "telos_mode": "module" if module_mode else "source",
            "telos_factory_present": (source if module_mode else source / "packages/pi-runtime/src/core-goal-chain-store.ts").is_file(),
            "telos_loader_required": not module_mode,
            "telos_loader_present": None if module_mode else (source / "node_modules/tsx/dist/loader.mjs").is_file(),
            "model_access": "not probed; use a configured client model",
        }, indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
