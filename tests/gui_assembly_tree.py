# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Exercise new-assembly tree triangles: tests/run_gui.py --suites assembly_tree.

Uses real pointer events on the Assembly and Origin branch indicators. Every
click is checked after returning to the event loop. Writes partial results and
periodic Python stacks so a stalled run is distinguishable from a completed one.
Run only with disposable -u / -s configs, as provided by run_gui.py.
"""

import faulthandler
import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

OUT = os.environ["JELLYJAMS_RESULTS_DIR"]
RES = {"checks": {}, "errors": [], "info": {"version": App.Version()}}
STATE = {"clicks": 0}
CLICK_COUNT = 100
STACK = open(os.path.join(OUT, "assembly_tree_stacks.txt"), "w", encoding="utf-8")


def save():
    with open(os.path.join(OUT, "assembly_tree.json"), "w", encoding="utf-8") as stream:
        json.dump(RES, stream, indent=2)


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)}
    save()


def later(fn, ms=100):
    def guarded():
        try:
            fn()
        except Exception:
            RES["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            finish()
    QtCore.QTimer.singleShot(ms, guarded)


def start():
    faulthandler.dump_traceback_later(20, repeat=True, file=STACK)
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(create, 3500)


def create():
    App.newDocument("Unnamed")
    Gui.runCommand("JellyJams_NewAssembly")
    later(find_tree, 2000)


def find_tree():
    from jellyjams import constants

    doc = App.ActiveDocument
    assemblies = [obj for obj in doc.Objects if obj.TypeId == constants.TYPE_ASSEMBLY]
    note("new_assembly_in_separate_document", doc.Name == "Assembly1" and len(assemblies) == 1)
    assembly = assemblies[0]
    STATE["assembly"] = assembly
    trees = [widget for widget in Gui.getMainWindow().findChildren(QtWidgets.QTreeWidget)
             if widget.inherits("Gui::TreeWidget") and widget.isVisible()]
    tree = trees[0]
    STATE.update(tree=tree)
    item = branch_index(False)
    tree.expand(item)
    origin = branch_index(True)
    note("assembly_and_origin_branches_found", item.isValid() and origin.isValid())
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(assembly)
    later(click_branch)


def click_branch():
    tree = STATE["tree"]
    # Alternate blocks of clicks on the two triangles. Expand the assembly
    # before targeting its Origin, so the indicator is visible and on screen.
    origin = (STATE["clicks"] // 10) % 2 == 1
    item = branch_index(False)
    if origin:
        tree.expand(item)
        item = branch_index(True)
    rect = tree.visualRect(item)
    point = QtCore.QPoint(rect.left() - tree.indentation() // 2, rect.center().y())
    STATE.update(target_origin=origin, before=tree.isExpanded(item))
    RES["info"]["pending_click"] = {
        "number": STATE["clicks"] + 1, "row": item.data(),
        "point": [point.x(), point.y()], "expanded_before": tree.isExpanded(item),
    }
    save()
    QtTest.QTest.mouseMove(tree.viewport(), point)
    QtTest.QTest.mouseClick(tree.viewport(), QtCore.Qt.MouseButton.LeftButton,
                          QtCore.Qt.KeyboardModifier.NoModifier, point)
    later(check_branch)


def check_branch():
    STATE["clicks"] += 1
    item = branch_index(STATE["target_origin"])
    note("triangle_click_%03d" % STATE["clicks"],
         STATE["tree"].isExpanded(item) != STATE["before"], RES["info"]["pending_click"])
    if STATE["clicks"] < CLICK_COUNT:
        later(click_branch, 20)
        return
    note("stayed_in_jellyjams", Gui.activeWorkbench().name() == "JellyJamsWorkbench")
    import UtilsAssembly
    note("assembly_still_active", UtilsAssembly.activeAssembly() == STATE["assembly"])
    Gui.getMainWindow().grab().save(os.path.join(OUT, "assembly_tree.png"))
    finish()


def branch_index(origin):
    # Use model indexes rather than generic wrappers for FreeCAD's native
    # QTreeWidgetItem subclasses. Re-resolve after every event-loop turn.
    assembly = STATE["assembly"]
    model = STATE["tree"].model()
    matches = model.match(model.index(0, 0), QtCore.Qt.ItemDataRole.DisplayRole,
                          assembly.Label, -1, QtCore.Qt.MatchFlag.MatchExactly
                          | QtCore.Qt.MatchFlag.MatchRecursive)
    item = matches[-1]
    if origin:
        return next(model.index(row, 0, item) for row in range(model.rowCount(item))
                    if model.index(row, 0, item).data() == assembly.Origin.Label)
    return item


def finish():
    faulthandler.cancel_dump_traceback_later()
    try:
        if Gui.ActiveDocument and Gui.ActiveDocument.getInEdit():
            Gui.ActiveDocument.resetEdit()
        for name in list(App.listDocuments()):
            App.closeDocument(name)
        Gui.activateWorkbench("PartDesignWorkbench")
    except Exception:
        RES["errors"].append("cleanup: " + traceback.format_exc())
    RES["ok"] = (STATE["clicks"] == CLICK_COUNT and not RES["errors"]
                 and all(check["ok"] for check in RES["checks"].values()))
    save()
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.instance().quit)


later(start, 2500)
