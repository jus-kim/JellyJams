# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Qt message filter that silences "render glyph failed" while JellyJams is
active.

At very high zoom on a TechDraw page, text grows too big for the font rasterizer and Qt
prints one harmless "render glyph failed" warning per character. The enabled
filter drops those. All other messages pass through unchanged, either to a
Python handler that was installed earlier or to the Report view in the same
form FreeCAD's own forwarder uses.

Python cannot put FreeCAD's C++ forwarder back after replacing it, so the
handler stays for the whole session and simply passes everything on while
disabled.
"""

import FreeCAD

from jellyjams import console, constants, params

GLYPH_PREFIX = "render glyph failed"
PROBE_MARK = "JellyJams self-test"
PROBE_TEXT = "render glyph failed (JellyJams self-test)"

_installed = False
_enabled = False
_previous = None
_first_drop_logged = False
_probe_seen = False

_LEVEL_BY_NAME = {
    "QtDebugMsg": "log",
    "QtInfoMsg": "log",
    "QtWarningMsg": "warning",
    "QtCriticalMsg": "error",
    "QtSystemMsg": "error",
    "QtFatalMsg": "error",
}
_LEVEL_BY_VALUE = {0: "log", 1: "warning", 2: "error", 3: "error", 4: "log"}


def install_and_enable() -> None:
    """Install the handler on first use unless the user opted out, then start filtering."""
    global _enabled
    try:
        if not _installed:
            if not params.get_bool(constants.PARAM_ROOT, constants.KEY_QT_FILTER, True):
                console.log("Qt message filter left off (SilenceGlyphWarnings is false)")
                return
            if not _install():
                return
        _enabled = True
    except Exception as exc:
        console.warning("Qt message filter unavailable: %s" % exc)


def disable() -> None:
    """Stop filtering; the handler stays and forwards everything."""
    global _enabled
    _enabled = False


def is_installed() -> bool:
    return _installed


def is_enabled() -> bool:
    return _enabled


def handle(msg_type, context, message) -> None:
    """The Qt message handler. Qt can call it on any thread, so it has to stay
    fast, never raise and never touch widgets."""
    global _probe_seen, _first_drop_logged
    try:
        text = message if isinstance(message, str) else str(message)
        if text.startswith(GLYPH_PREFIX):
            if PROBE_MARK in text:
                _probe_seen = True
                return
            if _enabled:
                if not _first_drop_logged:
                    _first_drop_logged = True
                    console.log(
                        "suppressing Qt 'render glyph failed' warnings; they come from "
                        "text too large to rasterize at extreme drawing zoom and do "
                        "no harm")
                return
        _forward(msg_type, context, text)
    except Exception:
        pass


def format_forward(category: str, message: str) -> str:
    """Forwarded text in FreeCAD's own format: "(category) message", or only the
    message for the default category, ending in a newline."""
    text = "" if message is None else str(message)
    category = "" if category is None else str(category)
    if category and category != "default":
        text = "(%s) %s" % (category, text)
    return text + "\n"


def _install() -> bool:
    global _installed, _previous, _probe_seen
    installer, emit_warning = _message_api()
    if installer is None:
        console.warning("Qt message filter unavailable: this Qt binding has no "
                        "qInstallMessageHandler")
        return False
    try:
        previous = installer(handle)
    except Exception as exc:
        console.warning("Qt message filter unavailable: qInstallMessageHandler "
                        "raised: %s" % exc)
        return False
    _previous = previous if callable(previous) and previous is not handle else None
    _installed = True

    _probe_seen = False
    if emit_warning is not None:
        try:
            emit_warning(PROBE_TEXT)
        except Exception:
            pass
    if _probe_seen:
        console.message("Qt message filter in place; self-test ok")
    else:
        console.message("Qt message filter in place; self-test inconclusive "
                        "(the probe message never reached the handler)")
    return True


def _message_api():
    """(qInstallMessageHandler, qWarning), tried from PySide6 first and then
    from FreeCAD's PySide shim; (None, None) if neither has the handler API."""
    for loader in (_pyside6_qtcore, _shim_qtcore):
        try:
            qtcore = loader()
        except Exception:
            continue
        installer = getattr(qtcore, "qInstallMessageHandler", None)
        if callable(installer):
            emit_warning = getattr(qtcore, "qWarning", None)
            return installer, emit_warning if callable(emit_warning) else None
    return None, None


def _pyside6_qtcore():
    from PySide6 import QtCore

    return QtCore


def _shim_qtcore():
    from PySide import QtCore

    return QtCore


def _forward(msg_type, context, text) -> None:
    previous = _previous
    if previous is not None:
        try:
            previous(msg_type, context, text)
        except Exception:
            pass
        return
    category = getattr(context, "category", "") if context is not None else ""
    line = format_forward(category, text)
    level = _level(msg_type)
    out = FreeCAD.Console
    if level == "log":
        out.PrintLog(line)
    elif level == "error":
        out.PrintError(line)
    else:
        out.PrintWarning(line)


def _level(msg_type) -> str:
    name = getattr(msg_type, "name", None)
    if name in _LEVEL_BY_NAME:
        return _LEVEL_BY_NAME[name]
    try:
        return _LEVEL_BY_VALUE.get(int(getattr(msg_type, "value", msg_type)), "warning")
    except Exception:
        return "warning"
