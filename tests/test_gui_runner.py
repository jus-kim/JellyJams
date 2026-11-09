# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Result validation must never report a partial or failed GUI run as passing."""

import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from run_gui import autoload_config, select_suites, validate_result


class TestGuiResults(unittest.TestCase):
    def test_repeated_suites_run_once_in_first_requested_order(self):
        self.assertEqual(select_suites(["smoke", "sketch", "smoke", "features", "sketch"]),
                         ["smoke", "sketch", "features"])

    def test_empty_and_unknown_suite_selections_fail(self):
        for requested in ([], ["smoke", "typo"]):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                select_suites(requested)

    def test_dependent_suites_still_require_prior_run_in_same_session(self):
        for before, after in (("discard", "after"), ("crash", "recover"), ("report_view", "report_startup")):
            with self.subTest(suite=after):
                self.assertEqual(select_suites([before, after, before]), [before, after])
                for requested in ([after], [after, before], [after, before, after]):
                    with self.assertRaisesRegex(ValueError, "must follow"):
                        select_suites(requested)

    def test_success(self):
        self.assertEqual(validate_result({"checks": {"one": {"ok": True}}, "errors": []}), 1)

    def test_empty_run_fails(self):
        with self.assertRaises(ValueError):
            validate_result({"checks": {}, "errors": []})

    def test_truncated_run_fails(self):
        with self.assertRaises(ValueError):
            validate_result({"checks": {"one": {"ok": True}}}, 2)

    def test_exception_fails_even_with_passing_checks(self):
        with self.assertRaises(ValueError):
            validate_result({"checks": {"one": {"ok": True}}, "errors": ["traceback"]})

    def test_failed_check_fails(self):
        with self.assertRaises(ValueError):
            validate_result({"checks": {"one": {"ok": False}}})

    def test_missing_ok_fails(self):
        with self.assertRaises(ValueError):
            validate_result({"checks": {"one": {"detail": "unfinished"}}})

    def test_explicit_unsuccessful_run_fails(self):
        with self.assertRaises(ValueError):
            validate_result({"ok": False, "checks": {"one": {"ok": True}}})

    def test_missing_tab_record_fails(self):
        with self.assertRaises(ValueError):
            validate_result({}, 0)

    def test_tabs_must_all_be_present_in_order(self):
        tabs = [{"name": name} for name in ("Features", "Sketch", "Evaluate", "Assembly", "Drawing")]
        self.assertEqual(validate_result({"tabs": tabs}, 0), 0)
        for incomplete in ([], tabs[:-1], list(reversed(tabs))):
            with self.subTest(tabs=incomplete), self.assertRaises(ValueError):
                validate_result({"tabs": incomplete}, 0)

    def test_autoload_profile_is_standalone(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "user.cfg"
            autoload_config(path)
            node = ET.parse(path).find(
                "./FCParamGroup/FCParamGroup/FCParamGroup/FCParamGroup/FCText")
            self.assertEqual(node.get("Name"), "AutoloadModule")
            self.assertEqual(node.text, "JellyJamsWorkbench")


if __name__ == "__main__":
    unittest.main()
