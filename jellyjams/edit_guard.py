# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Keep JellyJams active while FreeCAD opens a feature for editing.

Part Design's view providers switch to the Part Design workbench every time a
feature enters edit (there is no preference for it) and switch back when the
edit ends. FreeCAD does that by running ``Gui.activateWorkbench('...')`` as a
command string, the same way the workbench selector and View > Workbench do.

While JellyJams is active, ``FreeCADGui.activateWorkbench`` is wrapped. A call
that comes from a FreeCAD command string is held for one event-loop turn: if an
object has entered edit by then, the request was part of opening that edit and
JellyJams stays; otherwise it was a real request and the switch happens. Calls
from Python code (macros, scripts, the console) pass straight through. A command
string is recognized a few frames up as well, in case other add-ons have wrapped
the same function after JellyJams.
"""

import sys

from jellyjams import console, constants, fcgui

COMMAND_STRING_FILE = "<string>"   # code object filename of FreeCAD command strings
# Frames searched above the wrapper, so other add-ons' wrappers in between still let a
# command string be recognized.
FRAME_SEARCH_DEPTH = 6

_original = None
_in_chain = False   # the wrapper sits somewhere in the attribute chain
_armed = False


def install():
    """Wrap FreeCADGui.activateWorkbench (or re-arm the wrapper). Safe to repeat."""
    global _original, _in_chain, _armed
    gui = fcgui.gui()
    if gui is None:
        return
    current = getattr(gui, "activateWorkbench", None)
    if current is None:
        return
    if current is not _guarded and not _in_chain:
        _original = current
        gui.activateWorkbench = _guarded
        _in_chain = True
    # Already in the chain, possibly under another add-on's wrapper: re-arm, never re-wrap
    # (wrapping that add-on's wrapper would make the two call each other forever).
    _armed = True


def uninstall():
    """Disarm the wrapper and hand FreeCAD's own function back when it is still on top."""
    global _armed, _in_chain
    _armed = False
    gui = fcgui.gui()
    if gui is not None and getattr(gui, "activateWorkbench", None) is _guarded and _original is not None:
        gui.activateWorkbench = _original
        _in_chain = False


def is_installed():
    return _armed


def _from_command_string():
    try:
        frame = sys._getframe(2)
    except Exception:
        return False
    for _ in range(FRAME_SEARCH_DEPTH):
        if frame is None:
            return False
        if frame.f_code.co_filename == COMMAND_STRING_FILE:
            return True
        frame = frame.f_back
    return False


def _edit_key():
    obj = fcgui.object_in_edit()
    if obj is None:
        return None
    try:
        return (obj.Document.Name, obj.Name)
    except Exception:
        return None


def _guarded(name, *args, **kwargs):
    if (not _armed or _original is None or name == constants.WORKBENCH_KEY
            or not fcgui.jellyjams_active() or not _from_command_string()):
        return (_original or (lambda *a, **k: None))(name, *args, **kwargs)
    before = _edit_key()
    fcgui.defer(lambda: _decide(name, before, args, kwargs), 0)
    return None


def _decide(name, before, args, kwargs):
    if not fcgui.jellyjams_active():
        return   # something else changed the workbench meanwhile
    after = _edit_key()
    if after is not None and after != before:
        console.log("stayed in JellyJams while %s opened for editing (FreeCAD asked for %s)" % (after[1], name))
        return
    try:
        _original(name, *args, **kwargs)
    except Exception as exc:
        console.warning("could not switch to %s: %s" % (name, exc))
