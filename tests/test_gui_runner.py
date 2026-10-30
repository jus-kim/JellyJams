# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Result validation must never report a partial or failed GUI run as passing."""

import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from run_gui import autoload_config, validate_result


class TestGuiResults(unittest.TestCase):
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
