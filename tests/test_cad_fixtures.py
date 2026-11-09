# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Network-free tests for fixture provenance, integrity and fail-closed checks."""

import copy
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from cad_fixtures import close_number, fetch, load_manifest, safe_name, verify_bytes, verify_cache


def pinned(payload):
    return {"sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}


class TestCadFixtures(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.data = load_manifest()

    def changed_manifest(self, change):
        value = copy.deepcopy(self.data)
        change(value)
        path = self.root / "manifest.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_catalog_coverage_is_deliberate(self):
        ids = {case["id"] for case in self.data["cases"]}
        self.assertEqual(ids, {"cylinder", "cylinder_seam", "cylinder_inch", "cone_point",
                              "cone_point_vertex", "dome", "washer", "tiny_pin", "sheet_disc",
                              "far_cylinder", "cylinder_placed", "cylinder_twice", "plate_100_holes",
                              "grooved_shaft", "nist_ftc_07_asme1_rd", "nist_ftc_08_asme1_rc",
                              "nist_ftc_09_asme1_rd", "nist_ftc_10_asme1_rb",
                              "nist_ctc_02_asme1_rc", "nist_ctc_04_asme1_rd"})
        self.assertEqual(sum(bool(case.get("rebuild")) for case in self.data["cases"]), 7)

    def test_sources_use_immutable_revision_or_archive_hash(self):
        for source in self.data["sources"]:
            if source.get("archive") != "zip":
                self.assertRegex(source["url"], r"/[a-f0-9]{40}/")
            else:
                self.assertTrue(all(asset.get("member") for asset in source["files"]))

    def test_nist_snapshots_are_not_claimed_as_analytic_truth(self):
        for case in self.data["cases"]:
            if case["id"].startswith("nist_"):
                self.assertIn("snapshot", case["reference"])
                self.assertIsNone(case["rebuild"])
            else:
                self.assertIn("Analytic", case["reference"])

    def test_known_discrepancies_are_not_passing_cases(self):
        active = {case["id"] for case in self.data["cases"]}
        self.assertTrue(all(case["id"] not in active and case["reason"]
                            for case in self.data["excluded_candidates"]))

    def test_duplicate_case_rejected(self):
        path = self.changed_manifest(lambda data: data["cases"].append(data["cases"][0]))
        with self.assertRaises(ValueError):
            load_manifest(path)

    def test_nonfinite_reference_rejected(self):
        path = self.changed_manifest(lambda data: data["cases"][0].update(volume_mm3=float("nan")))
        with self.assertRaises(ValueError):
            load_manifest(path)

    def test_unpinned_source_rejected(self):
        path = self.changed_manifest(lambda data: data["sources"][0].update(sha256=""))
        with self.assertRaises(ValueError):
            load_manifest(path)

    def test_inverted_bounds_rejected(self):
        path = self.changed_manifest(lambda data: data["cases"][0].update(bbox_mm=[10, 10, 10, 0, 0, 0]))
        with self.assertRaises(ValueError):
            load_manifest(path)

    def test_unsafe_names_rejected(self):
        for name in ("../escape.step", "C:/escape.step", "\\escape.step", "a/b", "..", "a:b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_name(name)

    def test_missing_fixture_fails_without_skipping(self):
        with self.assertRaisesRegex(ValueError, "Missing fixture"):
            verify_cache(self.root, self.data)

    def test_corrupt_bytes_and_truncated_bytes_fail(self):
        pin = pinned(b"reference")
        for bad in (b"", b"referenc", b"referencX"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                verify_bytes(bad, pin)

    def test_finite_scale_aware_tolerances(self):
        self.assertTrue(close_number(100000 + 1e-7, 100000))
        self.assertFalse(close_number(100000 + 1, 100000))
        self.assertFalse(close_number(.4, .3926990817))
        for value in (float("nan"), float("inf"), float("-inf")):
            self.assertFalse(close_number(value, value))

    def test_independent_washer_and_plate_formulas(self):
        by_id = {case["id"]: case for case in self.data["cases"]}
        self.assertAlmostEqual(by_id["washer"]["volume_mm3"], math.pi * (20**2 - 5**2) * 3)
        area = 100**2 - 4 * (4**2 - math.pi * 4**2 / 4) - 100 * math.pi * 3**2
        self.assertAlmostEqual(by_id["plate_100_holes"]["volume_mm3"], area * 10)
        self.assertEqual(by_id["cylinder"]["volume_mm3"], by_id["cylinder_inch"]["volume_mm3"])

    def test_fetch_caches_verified_bytes_and_is_offline_on_repeat(self):
        payload = b"ISO-10303-21; fixture"
        asset = {"path": "part.step", **pinned(payload)}
        manifest = {"sources": [{"url": "https://example.test/part.step", **pinned(payload), "files": [asset]}]}
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            return io.BytesIO(payload)
        fetch(self.root, manifest, opener)
        fetch(self.root, manifest, opener)
        self.assertEqual(len(calls), 1)
        self.assertEqual((self.root / "part.step").read_bytes(), payload)

    def test_bad_download_never_replaces_existing_file(self):
        payload = b"known reference"
        target = self.root / "part.step"
        target.write_bytes(b"old bytes")
        manifest = {"sources": [{"url": "https://example.test/part.step", **pinned(payload),
                                 "files": [{"path": target.name, **pinned(payload)}]}]}
        with self.assertRaises(ValueError):
            fetch(self.root, manifest, lambda *args, **kwargs: io.BytesIO(b"new bad bytes"))
        self.assertEqual(target.read_bytes(), b"old bytes")

    def test_zip_extracts_only_named_members(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("public/part.step", b"reference")
            archive.writestr("../../escape.py", b"must not extract or execute")
        payload = data.getvalue()
        manifest = {"sources": [{"url": "https://example.test/data.zip", "archive": "zip", **pinned(payload),
                                 "files": [{"path": "part.step", "member": "public/part.step",
                                            **pinned(b"reference") }]}]}
        fetch(self.root, manifest, lambda *args, **kwargs: io.BytesIO(payload))
        self.assertEqual([path.name for path in self.root.iterdir()], ["part.step"])

    def test_gui_gate_requires_full_native_catalog(self):
        from run_gui import SUITES, validate_result
        self.assertEqual(SUITES["cad_baseline"], ("gui_cad_baseline.py", "cad_baseline.json", 333))
        checks = {str(i): {"ok": True} for i in range(332)}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_result({"checks": checks}, SUITES["cad_baseline"][2])


class TestBaselineGate(unittest.TestCase):
    def test_wrong_profile_is_reported_without_closing_the_session(self):
        tests = Path(__file__).resolve().parent
        scratch = tests.parent / "scratch"
        scratch.mkdir(exist_ok=True)
        for unsafe_key in ("UserParameter", "SystemParameter"):
            with self.subTest(unsafe_key=unsafe_key), tempfile.TemporaryDirectory(dir=scratch) as directory:
                out = Path(directory)
                profiles = {key: str(out / (key + ".cfg"))
                            for key in ("UserParameter", "SystemParameter")}
                profiles[unsafe_key] = str(tests.parent / "unowned_profile.cfg")
                app = mock.Mock(Version=lambda: ["test"], ConfigGet=profiles.__getitem__)
                gui, core, widgets = mock.Mock(), mock.Mock(), mock.Mock()
                modules = {"FreeCAD": app, "FreeCADGui": gui,
                           "PySide": mock.Mock(QtCore=core, QtWidgets=widgets)}
                with mock.patch.dict(sys.modules, modules), \
                        mock.patch.dict(os.environ, {"JELLYJAMS_RESULTS_DIR": directory}), \
                        mock.patch.object(sys, "path", list(sys.path)):
                    runpy.run_path(str(tests / "gui_cad_baseline.py"))
                    core.QTimer.singleShot.call_args.args[1]()
                result = json.loads((out / "cad_baseline.json").read_text())
                self.assertFalse(result["ok"])
                self.assertIn("runner-owned scratch configs", result["errors"][0])
                app.closeDocument.assert_not_called()
                gui.activateWorkbench.assert_not_called()
                gui.Control.activeDialog.assert_not_called()
                widgets.QApplication.instance.assert_not_called()
                self.assertEqual(core.QTimer.singleShot.call_count, 1)

    def run_gate(self, native_exit=0, cache_error=None, extra_args=()):
        import run_baseline
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "FreeCAD.exe"
            executable.write_bytes(b"placeholder; never executed")
            outcomes = [mock.Mock(returncode=value) for value in (0, 0, 0, native_exit)]
            with mock.patch.object(run_baseline, "REPO", root), \
                    mock.patch.object(run_baseline, "verify_cache", side_effect=cache_error) as verify, \
                    mock.patch.object(run_baseline, "fetch") as download, \
                    mock.patch.object(run_baseline.subprocess, "run", side_effect=outcomes) as process, \
                    mock.patch.object(run_baseline.sys, "argv", ["run_baseline", "--offline", "--freecad", str(executable), *extra_args]), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = run_baseline.main()
            summary = json.loads(next((root / "scratch").glob("baseline_*/summary.json")).read_text())
            return code, summary, process.call_args_list, verify.call_count, download.call_count

    def test_native_failure_cannot_be_hidden_by_passing_unit_tests(self):
        code, result, calls, _, _ = self.run_gate(native_exit=1)
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertTrue(result["stages"]["headless"]["ok"])
        self.assertFalse(result["stages"]["native"]["ok"])
        self.assertEqual(len(calls), 4)

    def test_offline_missing_data_fails_before_launch_without_download(self):
        code, result, calls, verifications, downloads = self.run_gate(cache_error=ValueError("Missing fixture"))
        self.assertEqual(code, 1)
        self.assertFalse(result["ok"])
        self.assertEqual((calls, verifications, downloads), ([], 1, 0))

    def test_default_keeps_cad_and_restore_checks(self):
        code, result, calls, _, downloads = self.run_gate()
        self.assertEqual(code, 0)
        self.assertTrue(result["ok"])
        native = calls[-1].args[0]
        self.assertEqual(native[native.index("--suites") + 1:], ["cad_baseline", "smoke"])
        self.assertEqual(result["native_suites"], ["cad_baseline", "smoke"])
        self.assertEqual(downloads, 0)

    def test_extra_suites_extend_core_once(self):
        code, result, calls, _, _ = self.run_gate(extra_args=(
            "--extra-suites", "sketch", "smoke", "features", "sketch"))
        self.assertEqual(code, 0)
        expected = ["cad_baseline", "smoke", "sketch", "features"]
        self.assertEqual(result["native_suites"], expected)
        self.assertEqual(calls[-1].args[0][-4:], expected)
        self.assertEqual(calls[-1].kwargs["timeout"], 600 * 4 + 60)

    def test_full_run_includes_all_suites_once_with_matching_timeout(self):
        from run_gui import SUITES
        code, result, calls, _, _ = self.run_gate(extra_args=("--full",))
        self.assertEqual(code, 0)
        self.assertEqual(result["native_suites"], list(SUITES))
        self.assertEqual(calls[-1].args[0][-len(SUITES):], list(SUITES))
        self.assertEqual(calls[-1].kwargs["timeout"], 600 * len(SUITES) + 60)

    def test_plan_needs_neither_freecad_nor_downloads(self):
        import run_baseline
        with mock.patch.object(sys, "argv", ["run_baseline", "--plan", "--freecad", "missing.exe"]), \
                mock.patch.object(run_baseline, "fetch") as download, \
                mock.patch.object(run_baseline, "verify_cache") as verify, \
                mock.patch.object(run_baseline.subprocess, "run") as launch, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_baseline.main(), 0)
        self.assertIn("cad_baseline, smoke", output.getvalue())
        download.assert_not_called()
        verify.assert_not_called()
        launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
