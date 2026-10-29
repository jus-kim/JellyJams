# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""JellyJams_Diagnostics: a summary of the setup, ready to paste into an issue.

The summary is printed to the Report view and also shown in a modal dialog
whose button copies it to the clipboard.
"""

import importlib
import platform
import re
import sys

import FreeCAD
from PySide import QtCore, QtGui, QtWidgets

import jellyjams
from jellyjams import commands, console, constants, fcgui, paths

TITLE = "JellyJams Diagnostics"
RULE = "=" * 40
DIALOG_SIZE = (640, 460)

# The order is fixed; add new rows at the end only.
ROW_LABELS = (
    "Add-on version",
    "FreeCAD version",
    "FreeCAD build",
    "Python",
    "Platform",
    "Qt binding",
    "Qt version",
    "Add-on path",
    "Path is a symlink",
    "Icons found",
    "User AppData",
    "Draft available",
    "Sketcher available",
    "Coin3D (pivy)",
)

_LEADING_INT = re.compile(r"\s*(\d+)")


class DiagnosticsCommand(commands.BaseCommand):
    command_id = constants.CMD_DIAGNOSTICS
    menu_text = "Diagnostics"
    tooltip = ("List the versions, paths and modules of this FreeCAD and "
               "JellyJams setup for a bug report")
    active_on_error = True

    def run(self) -> None:
        show_diagnostics()

    def is_active(self) -> bool:
        return True


class DiagnosticsDialog(QtWidgets.QDialog):
    """Shows the diagnostics text read-only, in a monospace font."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setObjectName(constants.OBJ_DIAGNOSTICS_DIALOG)
        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.resize(*DIALOG_SIZE)

        view = QtWidgets.QPlainTextEdit(self)
        view.setReadOnly(True)
        view.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        view.setFont(_fixed_font())
        view.setPlainText(text)

        self.copy_button = QtWidgets.QPushButton("Copy to clipboard", self)
        self.close_button = QtWidgets.QPushButton("Close", self)
        self.copy_button.setAutoDefault(False)
        self.close_button.setDefault(True)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.copy_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view, 1)
        layout.addLayout(buttons)

        self.copy_button.clicked.connect(self._copy)
        self.close_button.clicked.connect(self.accept)

    def text(self) -> str:
        return self._text

    def _copy(self, *args) -> None:
        with console.guard("put the diagnostics text on the clipboard"):
            QtWidgets.QApplication.clipboard().setText(self._text)
            self.copy_button.setText("Copied")


def get_commands() -> dict:
    return {constants.CMD_DIAGNOSTICS: DiagnosticsCommand()}


def show_diagnostics() -> None:
    """Gather the rows, print them to the Report view, then open the dialog."""
    block = format_block(collect_rows())
    console.message("\n" + block)
    dialog = DiagnosticsDialog(block, fcgui.main_window())
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()


def freecad_version() -> tuple:
    """(major, minor, patch) from FreeCAD.Version(): leading digits of each part, else 0."""
    try:
        parts = list(FreeCAD.Version())
    except Exception:
        parts = []
    numbers = []
    for index in range(3):
        value = parts[index] if index < len(parts) else ""
        match = _LEADING_INT.match(str(value))
        numbers.append(int(match.group(1)) if match else 0)
    return tuple(numbers)


def freecad_build() -> str:
    try:
        parts = list(FreeCAD.Version())
        build = str(parts[3]).strip() if len(parts) > 3 else ""
    except Exception:
        build = ""
    return build or "-"


def qt_binding() -> str:
    """Binding name and version, e.g. "PySide6 6.8.3 (FreeCAD PySide shim)"."""
    try:
        binding = QtCore.QObject.__module__.split(".")[0]
    except Exception:
        return "unknown"
    version = ""
    try:
        version = str(getattr(sys.modules.get(binding), "__version__", "") or "")
    except Exception:
        pass
    text = "%s %s" % (binding, version) if version else binding
    try:
        if QtCore.__name__.split(".")[0] != binding:
            text += " (FreeCAD PySide shim)"
    except Exception:
        pass
    return text


def qt_version() -> str:
    try:
        return str(QtCore.qVersion())
    except Exception:
        return "unknown"


def environment_line() -> str:
    """One-line summary printed at Initialize."""
    return "release %s on FreeCAD %s, Qt binding %s" % (
        _addon_version(), _dotted(freecad_version()), qt_binding())


def collect_rows() -> list:
    """[(label, value)] in ROW_LABELS order. Never raises."""
    addon = _safe(paths.addon_dir, None)
    values = (
        _addon_version,
        lambda: _dotted(freecad_version()),
        freecad_build,
        platform.python_version,
        platform.platform,
        qt_binding,
        qt_version,
        lambda: addon or "unknown",
        lambda: str(bool(addon) and bool(paths.is_link(addon))),
        lambda: str(bool(paths.icons_dir())),
        lambda: FreeCAD.getUserAppDataDir(),
        lambda: _module_status("Draft"),
        lambda: _module_status("Sketcher"),
        _coin_status,
    )
    return [(label, _one_line(_safe(getter, "unknown")))
            for label, getter in zip(ROW_LABELS, values)]


def format_block(rows) -> str:
    """Title line, a line of 40 '=', then one 'label : value' line per row, colons aligned."""
    rows = list(rows)
    width = max((len(str(label)) for label, _ in rows), default=0)
    lines = [TITLE, RULE]
    lines.extend("%s : %s" % (str(label).ljust(width), value) for label, value in rows)
    return "\n".join(lines)


def _addon_version() -> str:
    return str(getattr(jellyjams, "__version__", "unknown"))


def _dotted(parts) -> str:
    return ".".join(str(part) for part in parts)


def _module_status(name: str) -> str:
    try:
        importlib.import_module(name)
    except Exception as exc:
        return "NO - %s" % (exc or type(exc).__name__)
    return "yes"


def _coin_status() -> str:
    try:
        from pivy import coin
    except Exception as exc:
        return "NO - %s" % (exc or type(exc).__name__)
    version = getattr(coin, "COIN_VERSION", None)
    if not version:
        try:
            version = coin.SoDB.getVersion()
        except Exception:
            version = None
    return str(version) if version else "present"


def _safe(getter, default):
    try:
        return getter()
    except Exception as exc:
        return default if default is None else "%s (%s)" % (default, exc)


def _one_line(value) -> str:
    return " ".join(str(value).splitlines()) if value is not None else ""


def _fixed_font():
    try:
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
    except Exception:
        font = QtGui.QFont()
    if not QtGui.QFontInfo(font).fixedPitch():
        for family in ("Consolas", "Courier New", "DejaVu Sans Mono", "Menlo", "Courier"):
            candidate = QtGui.QFont(family)
            if QtGui.QFontInfo(candidate).fixedPitch():
                font = candidate
                break
    font.setStyleHint(QtGui.QFont.StyleHint.TypeWriter)
    font.setFixedPitch(True)
    return font
