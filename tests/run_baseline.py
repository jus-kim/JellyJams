# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Mandatory local gate before feature work and before submitting that work.

Runs stub/unit checks followed by native CAD and smoke. Add area suites with
--extra-suites, or use --full for all native coverage in one run.
Missing FreeCAD/data or a partial run is a failure.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from cad_fixtures import CACHE, REPO, fetch, verify_cache
from run_gui import CORE_SUITES, SUITES, select_suites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freecad", default="C:/Program Files/FreeCAD 1.1/bin/FreeCAD.exe")
    parser.add_argument("--python", dest="python_exe", help="Python with PySide6; defaults to FreeCAD's sibling python")
    parser.add_argument("--offline", action="store_true", help="require the existing verified cache, with no downloads")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per native suite")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--extra-suites", nargs="+", choices=SUITES,
                           help="area checks added to CAD/smoke, with duplicates removed")
    selection.add_argument("--full", action="store_true", help="all native suites, including the core, once")
    parser.add_argument("--plan", action="store_true", help="show native selection without downloads or test launches")
    args = parser.parse_args()
    try:
        suites = select_suites(SUITES if args.full else [*CORE_SUITES, *(args.extra_suites or [])])
    except ValueError as exc:
        parser.error(str(exc))
    print("Native suites: " + ", ".join(suites), flush=True)
    if args.plan:
        return 0
    freecad = Path(args.freecad).resolve()
    if not freecad.is_file():
        parser.error("FreeCAD executable is missing: " + str(freecad))
    sibling = freecad.with_name("python.exe" if sys.platform == "win32" else "python3")
    python = args.python_exe or (str(sibling) if sibling.is_file() else sys.executable)
    (REPO / "scratch").mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="baseline_", dir=REPO / "scratch"))
    summary = {"ok": False, "started_utc": datetime.now(timezone.utc).isoformat(),
               "freecad": str(freecad), "cache": str(CACHE), "native_suites": suites, "stages": {}}
    print("Baseline results: " + str(out), flush=True)
    try:
        verify_cache() if args.offline else fetch()
        summary["stages"]["fixtures"] = {"ok": True}
        jobs = [
            ("fixture_units", [python, "tests/test_cad_fixtures.py"], 120),
            ("runner_units", [python, "tests/test_gui_runner.py"], 120),
            ("headless", [python, "tests/test_headless.py", "-q"], 300),
            ("native", [python, "tests/run_gui.py", "--freecad", str(freecad), "--timeout", str(args.timeout),
                        "--suites", *suites], args.timeout * len(suites) + 60),
        ]
        for name, command, timeout in jobs:
            started = time.perf_counter()
            log_path = out / (name + ".log")
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.run(command, cwd=REPO, stdout=log, stderr=log,
                                         timeout=timeout, check=False)
            ok = process.returncode == 0
            summary["stages"][name] = {"ok": ok, "exit_code": process.returncode, "log": str(log_path),
                                       "elapsed_seconds": round(time.perf_counter() - started, 3)}
            print("%s: %s" % (name, "PASS" if ok else "FAIL; " + str(log_path)), flush=True)
            if not ok:
                raise RuntimeError(name + " failed; see " + str(log_path))
        summary["ok"] = True
    except Exception as exc:
        summary["error"] = str(exc)
        print("Baseline failed: " + str(exc), flush=True)
    finally:
        summary["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
