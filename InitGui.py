# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Adds the JellyJams workbench to the FreeCAD GUI and repairs settings a crash left behind.

FreeCAD exec()s this file: __file__ does not exist, and top-level names cannot be seen from
the class body or its methods. So the class body holds literals only, each method imports what
it uses, and the icon path is assigned after the class. Widgets, commands and the theme wait
until the workbench is selected.
"""

import inspect
import os

import FreeCAD
import FreeCADGui

_JELLYJAMS_DIR = None
try:
    _jj_source = inspect.currentframe().f_code.co_filename
    if os.path.basename(_jj_source).lower() == "initgui.py" and os.path.isfile(_jj_source):
        _JELLYJAMS_DIR = os.path.dirname(os.path.abspath(_jj_source))
except Exception:
    _JELLYJAMS_DIR = None
if _JELLYJAMS_DIR is None:
    try:
        from jellyjams import paths as _jj_paths

        _JELLYJAMS_DIR = _jj_paths.addon_dir()
    except Exception:
        _JELLYJAMS_DIR = None


class JellyJamsWorkbench(FreeCADGui.Workbench):
    """FreeCAD with a SolidWorks-style interface."""

    MenuText = "JellyJams"
    ToolTip = "FreeCAD with a SolidWorks-style interface"
    Icon = ""

    def Initialize(self):
        try:
            from jellyjams import lifecycle

            lifecycle.initialize(self)
        except Exception:
            import traceback

            import FreeCAD

            FreeCAD.Console.PrintError(
                "JellyJams: Initialize raised an error\n" + traceback.format_exc()
            )

    def Activated(self):
        try:
            from jellyjams import lifecycle

            lifecycle.activated()
        except Exception:
            import traceback

            import FreeCAD

            FreeCAD.Console.PrintError(
                "JellyJams: Activated raised an error\n" + traceback.format_exc()
            )

    def Deactivated(self):
        try:
            from jellyjams import lifecycle

            lifecycle.deactivated()
        except Exception:
            import traceback

            import FreeCAD

            FreeCAD.Console.PrintError(
                "JellyJams: Deactivated raised an error\n" + traceback.format_exc()
            )

    def GetClassName(self):
        return "Gui::PythonWorkbench"


JellyJamsWorkbench.Icon = ""
if _JELLYJAMS_DIR:
    _jj_icon = os.path.join(_JELLYJAMS_DIR, "resources", "icons", "jellyjams.svg")
    if os.path.isfile(_jj_icon):
        JellyJamsWorkbench.Icon = _jj_icon

try:
    if "JellyJamsWorkbench" in FreeCADGui.listWorkbenches():
        FreeCAD.Console.PrintWarning(
            "JellyJams: a JellyJams workbench is registered already; ignoring the duplicate in %s\n"
            % (_JELLYJAMS_DIR or "an unknown folder")
        )
    else:
        FreeCADGui.addWorkbench(JellyJamsWorkbench())
        if _JELLYJAMS_DIR:
            FreeCAD.Console.PrintMessage("JellyJams: workbench added, loaded from %s\n" % _JELLYJAMS_DIR)
        else:
            FreeCAD.Console.PrintMessage("JellyJams: workbench added; its folder could not be found\n")
except Exception:
    import traceback

    FreeCAD.Console.PrintError(
        "JellyJams: adding the workbench failed\n" + traceback.format_exc()
    )

try:
    from jellyjams import recovery as _jj_recovery

    _jj_recovery.run_startup_recovery()
except Exception:
    import traceback

    FreeCAD.Console.PrintError("JellyJams: crash repair at startup failed\n" + traceback.format_exc())
