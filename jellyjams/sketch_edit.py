# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Stop sketch editing from leaving JellyJams.

FreeCAD opens a sketch by calling ``Show.mTempoVis.TempoVis.activateWorkbench``
with the sketch's ``EditingWorkbench`` (normally the Sketcher). While JellyJams
is the active workbench, the wrapper installed here drops that call, so the
user stays where they are and nothing needs switching back on close. Under any
other workbench the call goes through untouched.

``install()`` swaps the class attribute for the wrapper. ``uninstall()`` puts
the saved function object back, unless another add-on has replaced the
attribute since. The sketch's ``EditingWorkbench`` property is never touched.
"""

import importlib

from jellyjams import console, fcgui

TEMPOVIS_MODULE = "Show.mTempoVis"
METHOD_NAME = "activateWorkbench"

_original = None    # function the wrapper forwards to; uninstall() puts it back
_in_chain = False   # the wrapper sits somewhere in the attribute chain
_armed = False      # the wrapper blocks switches (only while JellyJams is active)


def _keep_jellyjams(self, wb_name, *args, **kwargs):
    """Stand-in for TempoVis.activateWorkbench that ignores the call inside JellyJams."""
    if _armed and _jellyjams_is_active():
        return None
    return _original(self, wb_name, *args, **kwargs)


_keep_jellyjams.__name__ = METHOD_NAME
_keep_jellyjams.__qualname__ = "TempoVis." + METHOD_NAME


def _jellyjams_is_active():
    try:
        return bool(fcgui.jellyjams_active())
    except Exception:
        return False


def _tempovis_class(report):
    """Return the TempoVis class or None; with `report`, warn when it is missing."""
    try:
        module = importlib.import_module(TEMPOVIS_MODULE)
        cls = module.TempoVis
        if not callable(getattr(cls, METHOD_NAME, None)):
            raise AttributeError("TempoVis has no %s()" % METHOD_NAME)
        return cls
    except Exception as exc:
        if report:
            console.warning(
                "the switch to the Sketcher workbench cannot be blocked because "
                "Show.mTempoVis is not available (%s). Sketches will open in the "
                "Sketcher workbench, as in plain FreeCAD." % exc
            )
        return None


def install():
    """Put the wrapper in place, or re-arm it if it is already there. Safe to repeat."""
    global _original, _in_chain, _armed
    cls = _tempovis_class(report=True)
    if cls is None:
        return
    current = cls.__dict__.get(METHOD_NAME, getattr(cls, METHOD_NAME))
    if current is _keep_jellyjams or _in_chain:
        # Already installed, maybe underneath another add-on's wrapper:
        # re-arm it rather than adding a second layer.
        _armed = True
        return
    _original = current
    setattr(cls, METHOD_NAME, _keep_jellyjams)
    _in_chain = True
    _armed = True
    console.log("TempoVis workbench switch is now blocked while JellyJams is active")


def uninstall():
    """Put the saved TempoVis method back. Does nothing when not installed."""
    global _in_chain, _armed
    _armed = False
    if not _in_chain:
        return
    cls = _tempovis_class(report=False)
    if cls is None:
        return
    current = cls.__dict__.get(METHOD_NAME)
    if current is _keep_jellyjams:
        setattr(cls, METHOD_NAME, _original)
        _in_chain = False
        console.log("TempoVis workbench switch handed back to FreeCAD")
    else:
        # Someone else wrapped the method after us. Keep their version; ours
        # stays beneath it, disarmed, and only forwards calls.
        console.log(
            "another add-on has replaced TempoVis.%s since; keeping its version "
            "(the JellyJams wrapper underneath now only forwards calls)" % METHOD_NAME
        )


def is_installed():
    """True while the wrapper is in place and armed."""
    return _in_chain and _armed
