# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Native FreeCAD Dark/Light integration; run through run_gui.py's theme suites."""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

MODE = os.environ["JELLYJAMS_LIFECYCLE_MODE"]
OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
DARK = MODE == "theme_dark"
RES = {"checks": {}, "errors": [], "info": {"version": App.Version()}}
STATE = {}


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}


def later(fn, ms=1000):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, run)


def color(widget, role):
    widget.ensurePolished()
    return widget.palette().color(role).name()


def native_settings():
    # FreeCAD itself updates window geometry while docks move. Theme settings must
    # stay untouched; layout changes are exercised by the lifecycle suite.
    return sorted(entry for entry in
                  (App.ParamGet("User parameter:BaseApp/Preferences/MainWindow").GetContents() or [])
                  if entry[1] in ("Theme", "StyleSheet", "ThemeStyleParametersFile"))


def start():
    from jellyjams import palette, viewport, constants
    mw, app = Gui.getMainWindow(), QtWidgets.QApplication.instance()
    menu = mw.menuBar()
    role = QtGui.QPalette.ColorRole
    native_dark = palette.relative_luminance(color(menu, role.Window)) < palette.relative_luminance(
        color(menu, role.WindowText))
    note("native_theme_loaded", native_dark == DARK,
         {"background": color(menu, role.Window), "text": color(menu, role.WindowText)})
    STATE.update(app_sheet=app.styleSheet(), window_sheet=mw.styleSheet(), settings=native_settings(),
                 menu_colors=(color(menu, role.Window), color(menu, role.WindowText)),
                 view_colors=viewport._snapshot(App.ParamGet(constants.PARAM_VIEW)))
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(active, 4000)


def active():
    from jellyjams import constants, palette, theme, ribbon, viewport
    mw, app = Gui.getMainWindow(), QtWidgets.QApplication.instance()
    colors = palette.widget_colors(DARK)
    role = QtGui.QPalette.ColorRole
    note("selected_palette", theme.widget_colors().PANEL == colors.PANEL)
    note("app_stylesheet_untouched", app.styleSheet() == STATE["app_sheet"])
    note("theme_preferences_untouched", native_settings() == STATE["settings"])
    note("native_menu_untouched", (color(mw.menuBar(), role.Window), color(mw.menuBar(), role.WindowText))
         == STATE["menu_colors"])
    dock = ribbon.dock()
    note("ribbon_surface", color(dock, role.Window) == colors.RIBBON_SURFACE, color(dock, role.Window))
    button = ribbon.find_button(constants.CMD_NEW_ASSEMBLY)
    note("ribbon_text", button is not None and color(button, role.ButtonText) == colors.TEXT)
    titles = [d.titleBarWidget() for d in mw.findChildren(QtWidgets.QDockWidget)
              if d.titleBarWidget() and d.titleBarWidget().metaObject().className() == "Gui::OverlayTitleBar"]
    note("dock_title_colors", bool(titles) and all(color(w, role.WindowText) == colors.TEXT_SECONDARY for w in titles))
    view_params = App.ParamGet(constants.PARAM_VIEW)
    note("viewport_palette_values", all(getattr(view_params, "Get" + suffix)(key) == value
                                        for key, suffix, value in viewport.managed_keys(DARK)))
    mw.grab().save(os.path.join(OUT, MODE + "_active.png"))
    doc = App.newDocument("ThemeCheck")
    doc.addObject("Part::Box", "Box")
    doc.recompute()
    later(open_orientation)


def open_orientation():
    from jellyjams import constants

    Gui.SendMsgToActiveView("ViewFit")
    Gui.runCommand(constants.CMD_ORIENTATION)
    later(popup)


def popup():
    from jellyjams import palette, orientation, context_sketch
    colors = palette.widget_colors(DARK)
    role = QtGui.QPalette.ColorRole
    panel = orientation._panel
    note("orientation_open", orientation.is_open())
    note("orientation_surface", panel is not None and color(panel, role.Window) == colors.PANEL)
    note("orientation_text", panel is not None and color(panel.pin_button, role.ButtonText) == colors.TEXT)
    if panel is not None:
        panel.grab().save(os.path.join(OUT, MODE + "_orientation.png"))
    orientation.close()
    sketch_popup = context_sketch._ensure_popup()
    note("sketch_popup_surface", sketch_popup is not None and color(sketch_popup, role.Window) == colors.PANEL)
    later(sketch_setup)


def sketch_setup():
    import Part
    import Sketcher

    doc = App.ActiveDocument
    doc.getObject("Box").Visibility = False
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    for y in (0, 10, 20, 30):
        sketch.addGeometry(Part.LineSegment(App.Vector(-20, y, 0), App.Vector(20, y, 0)), y == 20)
    sketch.addConstraint(Sketcher.Constraint("Block", 0))
    sketch.addConstraint(Sketcher.Constraint("Distance", 1, 40.0))
    reference = sketch.addConstraint(Sketcher.Constraint("Distance", 3, 40.0))
    sketch.setDriving(reference, False)
    doc.recompute()
    STATE["sketch"] = sketch
    Gui.ActiveDocument.setEdit(sketch.Name)
    later(sketch_check, 1500)


def sketch_check():
    import collections
    import struct
    from jellyjams import fcgui, palette

    sketch = STATE["sketch"]
    note("sketch_in_edit", fcgui.sketch_in_edit() is not None and
         fcgui.sketch_in_edit().Name == sketch.Name)
    note("sketch_solver_valid", sketch.solve() == 0)
    Gui.SendMsgToActiveView("ViewFit")
    path = os.path.join(OUT, MODE + "_sketch.png")
    Gui.activeDocument().activeView().saveImage(path, 1000, 700, "Current")
    image = QtGui.QImage(path)
    corners = [image.pixelColor(x, y).name() for x, y in
               ((5, 5), (image.width() // 2, 5), (5, image.height() - 5))]
    note("rendered_sketch_background_matches_mode", not image.isNull() and all(
        (palette.relative_luminance(c) < 0.2) == DARK for c in corners), corners)
    rgba = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
    pixels = collections.Counter(struct.iter_unpack("4B", rgba.constBits()))
    colors = palette.viewport_colors(DARK)
    counts = {name: pixels[tuple(int(getattr(colors, name)[i:i + 2], 16) for i in (1, 3, 5)) + (255,)]
              for name in ("UNDER_DEFINED", "FULLY_DEFINED", "CONSTRUCTION",
                           "DRIVING_DIMENSION", "DRIVEN_DIMENSION")}
    note("rendered_sketch_status_and_dimension_colors", all(n >= 3 for n in counts.values()), counts)
    Gui.getMainWindow().grab().save(os.path.join(OUT, MODE + "_sketch_window.png"))
    Gui.ActiveDocument.resetEdit()
    Gui.activateWorkbench("PartDesignWorkbench")
    later(restored, 4000)


def restored():
    from jellyjams import viewport, constants

    mw, app = Gui.getMainWindow(), QtWidgets.QApplication.instance()
    note("window_stylesheet_restored", mw.styleSheet() == STATE["window_sheet"])
    note("app_stylesheet_restored", app.styleSheet() == STATE["app_sheet"])
    note("preferences_restored", native_settings() == STATE["settings"])
    role = QtGui.QPalette.ColorRole
    note("native_menu_restored", (color(mw.menuBar(), role.Window), color(mw.menuBar(), role.WindowText))
         == STATE["menu_colors"])
    note("viewport_colors_restored_exactly", viewport._snapshot(App.ParamGet(constants.PARAM_VIEW))
         == STATE["view_colors"])
    mw.grab().save(os.path.join(OUT, MODE + "_restored.png"))
    finish()


def finish():
    try:
        from jellyjams import orientation
        orientation.close()
        if App.ActiveDocument:
            if Gui.ActiveDocument.getInEdit():
                Gui.ActiveDocument.resetEdit()
            App.closeDocument(App.ActiveDocument.Name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        RES["errors"].append(traceback.format_exc())
    RES["ok"] = not RES["errors"] and bool(RES["checks"]) and all(c["ok"] for c in RES["checks"].values())
    with open(os.path.join(OUT, MODE + ".json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


later(start, 4000)
