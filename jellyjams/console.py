# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Report view printing with the "JellyJams: " prefix, plus helpers that catch
and report exceptions.

No function here raises. Without FreeCAD, output goes to sys.stderr.
"""

import contextlib
import functools
import inspect
import sys
import traceback

from jellyjams import constants

LEVELS = ("error", "warning", "log", "silent")


def _format(text):
    try:
        line = str(text)
    except Exception:
        line = "<message not printable>"
    if not line.startswith(constants.LOG_PREFIX):
        line = constants.LOG_PREFIX + line
    if not line.endswith("\n"):
        line += "\n"
    return line


def _emit(printer_name, line):
    try:
        import FreeCAD

        getattr(FreeCAD.Console, printer_name)(line)
        return
    except Exception:
        pass
    try:
        sys.stderr.write(line)
    except Exception:
        pass


def message(text):
    """Report view line at normal message level."""
    _emit("PrintMessage", _format(text))


def warning(text):
    """Report view warning."""
    _emit("PrintWarning", _format(text))


def error(text, with_traceback=False):
    """Report view error; with_traceback adds the traceback of the exception being handled."""
    line = _format(text)
    if with_traceback:
        details = traceback_text()
        if details:
            line += details if details.endswith("\n") else details + "\n"
    _emit("PrintError", line)


def log(text):
    """Log-level line; the Report view shows it only when log output is switched on."""
    _emit("PrintLog", _format(text))


def traceback_text():
    """Formatted traceback of the exception being handled; "" when there is none."""
    try:
        if sys.exc_info()[0] is None:
            return ""
        return traceback.format_exc()
    except Exception:
        return ""


def _describe(exc):
    try:
        return str(exc) or type(exc).__name__
    except Exception:
        return "exception without printable text"


def _name_of(fn):
    try:
        return getattr(fn, "__qualname__", None) or getattr(fn, "__name__", None) or repr(fn)
    except Exception:
        return "a function"


def _report_failure(what, level, exc):
    """Print a caught exception at `level`. Call it inside the except block,
    where the traceback is still available."""
    if level == "silent":
        return
    text = "could not %s: %s" % (what, _describe(exc))
    if level == "warning":
        warning(text)
    elif level == "log":
        log(text)
    else:
        error(text, with_traceback=True)


@contextlib.contextmanager
def guard(what, level="error"):
    """Context manager that swallows an Exception from its block and prints
    'JellyJams: could not <what>: <exc>' at `level`: 'error' (adds the
    traceback), 'warning', 'log', or 'silent' (prints nothing)."""
    try:
        yield
    except Exception as exc:
        _report_failure(what, level, exc)


def _positional_limit(fn):
    """Number of positional parameters of fn; None for *args or when it cannot be inspected."""
    try:
        parameters = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return None
    count = 0
    for parameter in parameters:
        if parameter.kind == parameter.VAR_POSITIONAL:
            return None
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD):
            count += 1
    return count


def guarded(what, level="error", default=None):
    """guard() as a decorator, for Qt slots, observer callbacks and timer
    callbacks. Returns `default` when the wrapped function raised.

    Surplus positional arguments are dropped: PySide hands every signal
    argument to a *args wrapper even when the slot accepts fewer.
    """

    def decorate(fn):
        limit = _positional_limit(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if limit is not None and len(args) > limit:
                args = args[:limit]
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                _report_failure(what, level, exc)
                return default

        return wrapper

    return decorate


def safe_call(fn, *args, what="", level="log", default=None, **kwargs):
    """fn(*args, **kwargs) under guard(); its result, or `default` if it raised."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        _report_failure(what or "run %s" % _name_of(fn), level, exc)
        return default
