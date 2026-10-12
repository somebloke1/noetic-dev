#!/usr/bin/env python3
"""Run exact unittest identities and emit actual per-test observations."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest


class CapturedResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.observed = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.observed[test.id()] = "passed"

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.observed[test.id()] = "failed"

    def addError(self, test, error):
        super().addError(test, error)
        self.observed[test.id()] = "error"

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.observed[test.id()] = "skipped"

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.observed[test.id()] = "failed" if issubclass(error[0], test.failureException) else "error"

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self.observed[test.id()] = "skipped"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.observed[test.id()] = "error"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-dir", action="append", type=Path, default=[])
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args(argv)
    if len(set(args.tests)) != len(args.tests):
        parser.error("test identities must be unique")
    for path in args.module_dir:
        sys.path.insert(0, str(path.resolve(strict=True)))
    result = CapturedResult()
    printed = io.StringIO()
    with redirect_stdout(printed):
        suite = unittest.defaultTestLoader.loadTestsFromNames(args.tests)
        suite.run(result)
    observations = [{"kind": "actual-unittest-telemetry", "tests_run": result.testsRun,
                     "skips": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
                     "failures": len(result.failures), "errors": len(result.errors),
                     "expected_failures": len(result.expectedFailures),
                     "unexpected_successes": len(result.unexpectedSuccesses)}]
    for name in dict.fromkeys(t.split(".")[0] for t in args.tests):
        module = sys.modules.get(name)
        observations.extend(getattr(module, "CHECKING_OBSERVATIONS", []))
    print(json.dumps({"version": "noetic-checking-observations/v1",
                      "tests": [{"id": key, "status": status} for key, status in result.observed.items()],
                      "observations": observations}, sort_keys=True))
    for test, text in result.failures + result.errors:
        print(test.id() + "\n" + text, file=sys.stderr)
    if printed.getvalue():
        print(printed.getvalue(), file=sys.stderr, end="")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
