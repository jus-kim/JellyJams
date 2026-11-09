# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
GUI test of the Orientation panel (Space) and Normal To (Ctrl+8). Run inside the full
FreeCAD GUI with a throwaway config:

    FreeCAD.exe -u <copy of user.cfg> -s <copy of system.cfg> <absolute path>/tests/gui_orientation.py

Parts, in the order they run:

    keys     Space and Ctrl+8 on the JellyJams commands, Hide/Show unbound,
             Std_AlignToSelection untouched, Normal To in the JellyJams menu,
             key repeat off for View Orientation.
    panel    a real Space key press opens the panel; Top, pinned Front, Esc; Space on a view
             button reached with Tab applies that view though the pointer is over the 3D view.
    outside  activating the main window after the 0.3 s settle closes the unpinned panel; a
             pinned one stays; a deactivation right after opening does not close it, the
             panel takes the keyboard back, and a later click elsewhere closes it.
    normal   Normal To with nothing selected changes nothing and shows the hint in the
             status bar and as a tool tip; the panel's Normal To button with nothing selected
             closes the unpinned panel and shows the hint; with a box face selected Normal
             To looks straight at the face.
    pick     Normal To with a whole sketch, an origin plane, two faces (hint, view kept);
             the Evaluate tab's Normal To button is JellyJams_NormalTo and works on a face;
             a cylinder's curved face, a whole datum line and a whole origin axis turn the
             view exactly as FreeCAD's Align to Selection does; a whole sketch reached
             through a rotated App::Link is looked at along the link-transformed normal.
    combo    Space on the focused workbench selector opens the panel, not the combo popup.
    undock   an undocked 3D view keeps both commands enabled and Space opens the panel there;
             Esc and a view button give the keyboard back to the undocked view.
    start    with the Start page in front both commands are disabled and Space opens nothing.
    dark     an application stylesheet with white text leaves the panel's text dark.
    sketch   in sketch edit both commands stay enabled, Space opens the panel, Esc and
             Space close it, Normal To and a real Ctrl+8 look at the sketch plane.
    pad      in a Pad dialog Space toggles the focused Reversed check box with the pointer
             over the task panel, opens the panel instead with the pointer over the 3D view,
             still toggles it when the Tasks dock floats; Space in the 3D view opens the panel.
    hole     Hole in an empty body starts nothing and says a solid is needed; with two padded
             bodies and none active the press goes to FreeCAD (which asks for a body) and
             JellyJams does not say a solid is needed.
    late     a floating dock made after activation gets the Space filter once its check box
             takes the focus, and Space toggles that check box.
    leave    switching to Part Design closes the panel, gives the keys back and removes
             the Space filter; Space still toggles a focused check box in a plain dock.

Who gets Space depends on the real mouse pointer, so every Space key press first moves the
pointer onto the widget the case is about (QCursor.setPos).

Results: <JELLYJAMS_RESULTS_DIR>/orientation.json and orientation_dark_panel.png (the
panel under the white-text rule); default <repo>/scratch.
"""

import json
import os
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT_DIR = os.environ.get(
    "JELLYJAMS_RESULTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"),
)
os.makedirs(OUT_DIR, exist_ok=True)
RES = {"checks": {}, "info": {}, "errors": []}
CMD = "JellyJams_ViewOrientation"
NORMAL_TO = "JellyJams_NormalTo"
PANEL = "JellyJamsOrientation"
RIBBON = "JellyJamsCommandManager"
RIBBON_TABS = "JellyJamsCommandManagerTabs"
RIBBON_BUTTON = "JellyJamsButton-"
UNDOCK = "Std_ViewDockUndockFullscreen"   # sub-command 0 docked, 1 undocked, 2 fullscreen
ALIGN = "Std_AlignToSelection"
VIEW3D_CLASS = "Gui::View3DInventor"
START_CLASS = "StartGui::StartView"
Z_AXIS = App.Vector(0, 0, 1)
NEEDS_SOLID = "needs a solid to cut into"   # JellyJams' refusal of a cutting feature
PARAM_SHORTCUT = "User parameter:BaseApp/Preferences/Shortcut"
PARAM_VIEW = "User parameter:BaseApp/Preferences/View"
PARAM_OWN = "User parameter:BaseApp/Preferences/Mod/JellyJams"
# A camera that looks along no axis, so every Normal To result is a visible change.
SKEW = App.Rotation(App.Vector(1, 2, 3), 37)
# What a dark theme does to text: white everywhere unless a closer rule says otherwise.
DARK_RULE = "* { color: #ffffff; }"
CONTRAST_MIN = 4.5
SETTLED_MS = 600     # longer than orientation.OPEN_SETTLE_S after opening
CTX = {}
DOCS = []   # documents this script created; closed before FreeCAD quits


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)[:600]}
    App.Console.PrintMessage(f"JellyJams-orientation {name}: {'OK' if ok else 'FAIL'} {detail}\n")


def finish():
    RES["ok"] = bool(RES["checks"]) and all(c["ok"] for c in RES["checks"].values()) and not RES["errors"]
    RES["info"]["seconds"] = round(time.monotonic() - CTX.get("t0", time.monotonic()), 1)
    with open(os.path.join(OUT_DIR, "orientation.json"), "w", encoding="utf-8") as f:
        json.dump(RES, f, indent=2)
    tidy_up()
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


def tidy_up():
    """Put back what the script changed for itself, so FreeCAD can quit without a prompt."""
    try:
        if "style" in CTX and QtWidgets.QApplication.instance().styleSheet() != CTX["style"]:
            QtWidgets.QApplication.instance().setStyleSheet(CTX["style"])
        if "animations_before" in RES["info"]:
            App.ParamGet(PARAM_VIEW).SetBool("UseNavigationAnimations", RES["info"]["animations_before"])
        dock = CTX.get("task_dock")
        if dock is not None and dock.isFloating():
            dock.setFloating(False)
        if Gui.Control.activeDialog():
            Gui.Control.closeDialog()
    except Exception:
        App.Console.PrintError(f"JellyJams-orientation tidy_up: {traceback.format_exc()}\n")
    for name in DOCS:
        try:
            App.closeDocument(name)
        except Exception:
            pass


def guarded(fn):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(f"{fn.__name__}: {traceback.format_exc()}")
            finish()
    return run


def later(ms, fn):
    QtCore.QTimer.singleShot(ms, fn)


def qtest():
    from PySide6 import QtTest

    return QtTest.QTest


def process():
    QtWidgets.QApplication.processEvents()


def shortcut(cmd):
    c = Gui.Command.get(cmd)
    return c.getShortcut() if c is not None else None


def shortcut_override(cmd):
    """The command's entry in Preferences/Shortcut, or None when it has none."""
    grp = App.ParamGet(PARAM_SHORTCUT)
    return grp.GetString(cmd) if cmd in grp.GetStrings() else None


def backup_commands():
    """Command ids recorded in JellyJams' OriginalShortcuts backup."""
    raw = App.ParamGet(PARAM_OWN).GetString("OriginalShortcuts", "")
    return sorted(json.loads(raw)) if raw else []


def action(cmd):
    c = Gui.Command.get(cmd)
    actions = list(c.getAction() or []) if c is not None else []
    return actions[0] if actions else None


def refresh_commands():
    """Let FreeCAD recompute every command's enabled state now instead of on its timer."""
    Gui.Command.update()
    process()


def command_states():
    states = {}
    for cmd in (CMD, NORMAL_TO):
        a = action(cmd)
        states[cmd] = a.isEnabled() if a is not None else "no action"
    return states


def jellyjams_menu():
    for item in Gui.getMainWindow().menuBar().actions():
        if item.text().replace("&", "") == "JellyJams" and item.menu() is not None:
            return [a for a in item.menu().actions() if not a.isSeparator()]
    return []


def panel():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == PANEL:
            return w
    return None


def panel_visible():
    p = panel()
    return p is not None and p.isVisible()


def open_panel():
    """Open the panel unless it is open already (the command toggles), so one failed check
    does not flip the next one."""
    if not panel_visible():
        Gui.runCommand(CMD)


def close_panel():
    if panel_visible():
        Gui.runCommand(CMD)


def escape_panel():
    if panel_visible():
        qtest().keyClick(panel(), QtCore.Qt.Key.Key_Escape)


def class_name(widget):
    return widget.metaObject().className() if widget is not None else None


def window_name(widget):
    if widget is None:
        return None
    return widget.objectName() or class_name(widget)


def ancestor(widget, test):
    """`widget` or its nearest parent for which test(widget) is true, else None."""
    for _ in range(60):
        if widget is None:
            return None
        if test(widget):
            return widget
        widget = widget.parentWidget()
    return None


def raw_dir():
    d = Gui.ActiveDocument.ActiveView.getViewDirection()
    return (d.x, d.y, d.z)


def rounded(d):
    return tuple(round(v, 3) for v in d)


def view_dir():
    return rounded(raw_dir())


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def same_dir(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) < 1e-6


def vec(v):
    return (v.x, v.y, v.z)


def no_animation():
    view = Gui.ActiveDocument.ActiveView
    try:
        view.setAnimationEnabled(False)
        RES["info"].setdefault("animation_enabled", []).append(view.isAnimationEnabled())
    except Exception as exc:
        RES["info"].setdefault("animation_enabled", []).append(f"not settable: {exc}")


def skew_camera():
    Gui.ActiveDocument.ActiveView.setCameraOrientation(SKEW.Q)


def undocked_view():
    """A 3D view that is a window of its own (undocked or fullscreen), else None."""
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.isVisible() and w.inherits(VIEW3D_CLASS):
            return w
    return None


def mdi_area():
    return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)


def mdi_view():
    area = mdi_area()
    sub = area.activeSubWindow() or area.currentSubWindow()
    return sub.widget() if sub is not None else None


def sub_window(test):
    """The first MDI sub-window whose widget passes test(widget), else None."""
    for sub in mdi_area().subWindowList():
        if sub.widget() is not None and test(sub.widget()):
            return sub
    return None


def is_own_window_3d_view(widget):
    """True when `widget` is a 3D view that is a window of its own (undocked or fullscreen)."""
    return widget is not None and widget.isWindow() and widget.inherits(VIEW3D_CLASS)


def tooltip_text():
    """The text of the tool tip on screen, or None when none is shown."""
    return QtWidgets.QToolTip.text() if QtWidgets.QToolTip.isVisible() else None


def in_filtered(widget):
    """True when JellyJams' Space filter sits on `widget` (orientation._filtered)."""
    from jellyjams import orientation

    return any(t is widget for t in orientation._filtered)


def view3d_widget():
    """The 3D view the keys go to: an undocked one first, else the MDI area's current window."""
    return undocked_view() or mdi_view()


def gl_widget():
    """The OpenGL widget of the active 3D view (the view itself if none is found).

    The view's Python wrapper is kept: an undocked view is a top-level widget nobody else
    holds, and when its wrapper goes, PySide invalidates the wrappers findChildren() gave out.
    """
    view = CTX["key_view"] = view3d_widget()
    for w in view.findChildren(QtWidgets.QWidget):
        if w.inherits("QOpenGLWidget") and w.isVisible():
            return w
    return view


def pointer_info():
    """What is under the mouse pointer: the widget, and whether it lies in a 3D view."""
    w = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
    first = window_name(w)
    classes = []
    while w is not None and len(classes) < 60:
        classes.append(class_name(w))
        w = w.parentWidget()
    return {"under_pointer": first, "pointer_over_3d_view": VIEW3D_CLASS in classes}


def point_at(widget):
    """Place the pointer on an exposed part of the widget and verify native hit testing."""
    # The no-screen overload uses the primary screen. Explicitly use this
    # widget's screen for native coordinate conversion on mixed-DPI desktops.
    attempts = []
    for x, y in ((.5, .5), (.25, .25), (.75, .75), (.25, .75), (.75, .25)):
        point = widget.mapToGlobal(QtCore.QPoint(int(widget.width() * x), int(widget.height() * y)))
        QtGui.QCursor.setPos(widget.screen(), point)
        qtest().qWait(50)
        hit = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        attempts.append((point.x(), point.y(), window_name(hit)))
        if hit is widget or (hit is not None and widget.isAncestorOf(hit)):
            break
    info = pointer_info()
    actual = QtGui.QCursor.pos()
    info.update(requested_pointer=(point.x(), point.y()), actual_pointer=(actual.x(), actual.y()),
                target=window_name(widget), target_visible=widget.isVisible(),
                target_screen=widget.screen().name(), pointer_attempts=attempts)
    return info


def make_active(widget):
    """Activate the window of `widget` unless it is already the active one."""
    if not widget.isActiveWindow():
        widget.window().raise_()
        widget.window().activateWindow()
        process()


def press_in_view(key, modifier=QtCore.Qt.KeyboardModifier.NoModifier):
    """A real key press in the active 3D view: pointer over its GL widget, focus there, then
    the key to whatever holds the keyboard focus, as the keyboard does."""
    widget = gl_widget()
    make_active(widget)
    RES["info"]["view_key_pointer"] = point_at(widget)
    widget.setFocus()
    process()
    target = QtWidgets.QApplication.focusWidget() or widget
    RES["info"]["view_key_target"] = (class_name(widget), class_name(target))
    qtest().keyClick(target, key, modifier)


def override_accepted(widget):
    """True when a plain Space ShortcutOverride sent to `widget` is accepted on its way up to
    its window (JellyJams' Space filter on the main window does that for focused buttons)."""
    event = QtGui.QKeyEvent(QtCore.QEvent.Type.ShortcutOverride, QtCore.Qt.Key.Key_Space,
                            QtCore.Qt.KeyboardModifier.NoModifier, " ")
    event.ignore()
    QtWidgets.QApplication.sendEvent(widget, event)
    return event.isAccepted()


def activate_main_window():
    """What a click into FreeCAD's main window does to the window activation."""
    Gui.getMainWindow().activateWindow()
    process()


def since_opened():
    from jellyjams import orientation

    return round(time.monotonic() - orientation._opened_at, 3)


def button(cmd_id):
    return panel().findChild(QtWidgets.QToolButton, "JellyJamsOrientation_" + cmd_id)


def new_doc(name):
    doc = App.newDocument(name)
    DOCS.append(doc.Name)
    return doc


def plane(body, role):
    return next(f for f in body.Origin.OriginFeatures if getattr(f, "Role", "") == role)


def sketch_on_xy(body):
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = (plane(body, "XY_Plane"), [""])
    sketch.MapMode = "FlatFace"
    return sketch


def draw_rectangle(sketch, w=30.0, h=20.0):
    import Part

    pts = [App.Vector(0, 0, 0), App.Vector(w, 0, 0), App.Vector(w, h, 0), App.Vector(0, h, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)


def padded_body(doc):
    """A Body with a 30 x 20 rectangle sketch on its XY plane and a 10 mm Pad of it."""
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = sketch_on_xy(body)
    draw_rectangle(sketch)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10.0
    doc.recompute()
    return body, sketch, pad


def sketch_in_edit():
    vp = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument else None
    obj = vp.Object if vp is not None else None
    return obj if obj is not None and obj.TypeId == "Sketcher::SketchObject" else None


def selection_summary():
    return [(s.ObjectName, [n for n in s.SubElementNames]) for s in Gui.Selection.getSelectionEx()]


def normal_of(obj):
    """The +Z axis of `obj`'s global placement: the normal of a sketch or plane."""
    return vec(obj.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1)))


def close_task_dialog(accept=False):
    """Press OK (accept) or Cancel in the open task dialog; fall back to closeDialog()."""
    wanted = QtWidgets.QDialogButtonBox.StandardButton.Ok if accept else QtWidgets.QDialogButtonBox.StandardButton.Cancel
    mw = Gui.getMainWindow()
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() not in ("Tasks", "Combo View", "ComboView"):
            continue
        for box in dock.findChildren(QtWidgets.QDialogButtonBox):
            b = box.button(wanted)
            if b is not None and b.isVisible():
                b.click()
                return
    try:
        Gui.Control.closeDialog()
    except Exception:
        pass


def when_no_dialog(fn, waited=0):
    """Run fn once no task dialog is open (gives up waiting after 5 s)."""
    if Gui.Control.activeDialog() and waited < 5000:
        later(200, lambda: when_no_dialog(fn, waited + 200))
    else:
        fn()


def task_check_box(object_name):
    """The visible check box `object_name` of the open task dialog, or None."""
    for box in Gui.getMainWindow().findChildren(QtWidgets.QCheckBox, object_name):
        if box.isVisible() and box.isEnabled():
            return box
    return None


def task_area(widget):
    """The task panel around `widget` (FreeCAD's Gui::TaskView::TaskView), else its dock."""
    return (ancestor(widget, lambda w: class_name(w) == "Gui::TaskView::TaskView")
            or ancestor(widget, lambda w: isinstance(w, QtWidgets.QDockWidget))
            or widget.window())


def close_stray_modal():
    """Close a modal dialog nobody expected, so a failing step cannot hang the run."""
    w = QtWidgets.QApplication.activeModalWidget()
    if w is not None:
        RES["info"].setdefault("stray_modal", []).append(f"{window_name(w)}: {w.windowTitle()}")
        if hasattr(w, "reject"):
            w.reject()
        else:
            w.close()


def text_contrast(widget, inside):
    """How well the text of the tool button `widget` stands out from what is painted behind it.

    `inside` (the panel) paints the button twice, with and without its text; only the pixels
    the text changes count. Returns {"contrast": best text/background ratio (1.0 when the
    text changes nothing), "text_pixels": how many pixels it changes, "text", "behind"}.
    """
    from jellyjams import palette

    rect = QtCore.QRect(widget.mapTo(inside, QtCore.QPoint(0, 0)), widget.size())
    with_text = inside.grab(rect).toImage()
    label = widget.text()
    widget.setText("")
    try:
        without_text = inside.grab(rect).toImage()
    finally:
        widget.setText(label)
    found = {"contrast": 1.0, "text_pixels": 0, "text": None, "behind": None}
    for y in range(min(with_text.height(), without_text.height())):
        for x in range(min(with_text.width(), without_text.width())):
            text, behind = with_text.pixel(x, y), without_text.pixel(x, y)
            if text == behind:
                continue
            found["text_pixels"] += 1
            text, behind = QtGui.QColor(text).name(), QtGui.QColor(behind).name()
            ratio = round(palette.contrast_ratio(text, behind), 2)
            if ratio > found["contrast"]:
                found.update(contrast=ratio, text=text, behind=behind)
    return found


def text_color(widget, role):
    return widget.palette().color(QtGui.QPalette.ColorGroup.Active, role).name()


# --- keys -------------------------------------------------------------------------------------

@guarded
def start():
    CTX["t0"] = time.monotonic()
    RES["info"]["toggle_visibility_before"] = shortcut("Std_ToggleVisibility")
    RES["info"]["align_override_before"] = shortcut_override("Std_AlignToSelection")
    view = App.ParamGet(PARAM_VIEW)
    RES["info"]["animations_before"] = view.GetBool("UseNavigationAnimations", True)
    view.SetBool("UseNavigationAnimations", False)   # camera changes finish at once
    Gui.activateWorkbench("JellyJamsWorkbench")
    later(4000, setup_doc)


@guarded
def setup_doc():
    doc = new_doc("Orient")
    doc.addObject("Part::Box", "Box")
    doc.recompute()
    Gui.SendMsgToActiveView("ViewFit")
    no_animation()
    note("space_bound_to_orientation", shortcut(CMD) == "Space", shortcut(CMD))
    note("ctrl8_normal_to", shortcut(NORMAL_TO) == "Ctrl+8", shortcut(NORMAL_TO))
    align = {"shortcut": shortcut("Std_AlignToSelection"), "override": shortcut_override("Std_AlignToSelection"),
             "override_before": RES["info"]["align_override_before"], "backup": backup_commands()}
    note("align_to_selection_untouched",
         align["shortcut"] != "Ctrl+8" and align["override"] == align["override_before"]
         and "Std_AlignToSelection" not in align["backup"], align)
    note("toggle_visibility_unbound_while_active", shortcut("Std_ToggleVisibility") in ("", None),
         shortcut("Std_ToggleVisibility"))
    menu = jellyjams_menu()
    names = [a.objectName() or a.text() for a in menu]
    note("menu_has_normal_to", NORMAL_TO in names or action(NORMAL_TO) in menu, names)
    normal_action = action(NORMAL_TO)
    keys = normal_action.shortcut().toString() if normal_action is not None else None
    note("normal_to_action_has_ctrl8", keys == "Ctrl+8", keys)
    orient_action = action(CMD)
    repeat = orient_action.autoRepeat() if orient_action is not None else None
    note("orientation_no_auto_repeat", repeat is False, repeat)
    try:
        from jellyjams import orientation

        RES["info"]["space_filter_on"] = [window_name(t) for t in orientation._filtered]
    except Exception as exc:
        RES["info"]["space_filter_on"] = f"not readable: {exc}"
    Gui.getMainWindow().activateWindow()
    later(500, open_with_space)


# --- panel ------------------------------------------------------------------------------------

@guarded
def open_with_space():
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, check_open)


@guarded
def check_open():
    opened_by_key = panel_visible()
    if not opened_by_key:
        Gui.runCommand(CMD)   # fall back so the rest of the panel is still tested
    note("space_opens_panel", opened_by_key, RES["info"].get("view_key_pointer"))
    p = panel()
    buttons = [b.objectName() for b in p.findChildren(QtWidgets.QToolButton) if b.objectName().startswith("JellyJamsOrientation_")]
    note("panel_has_13_view_buttons", len(buttons) == 13, buttons)
    normal = button(NORMAL_TO)
    note("panel_has_normal_to_button", normal is not None and normal.isEnabled(), buttons[:1])
    RES["info"]["before_top"] = view_dir()
    button("Std_ViewTop").click()
    later(700, check_top)


@guarded
def check_top():
    d = view_dir()
    note("top_view_applied", d == (0.0, 0.0, -1.0), d)
    note("unpinned_panel_closes_after_choice", not panel_visible())
    open_panel()
    later(400, pin_and_front)


@guarded
def pin_and_front():
    p = panel()
    p.pin_button.setChecked(True)
    button("Std_ViewFront").click()
    later(700, check_front)


@guarded
def check_front():
    d = view_dir()
    note("front_view_applied", d != (0.0, 0.0, -1.0) and abs(d[2]) < 1e-6, d)
    note("pinned_panel_stays_open", panel_visible())
    qtest().keyClick(panel(), QtCore.Qt.Key.Key_Escape)
    later(400, check_escape)


@guarded
def check_escape():
    note("escape_closes_panel", not panel_visible())
    panel().pin_button.setChecked(False)
    skew_camera()
    later(300, tab_focus_open)


@guarded
def tab_focus_open():
    # A tool window can be active while its main window is behind another app.
    # Expose the view before opening the panel; keep the native hit-test assertion.
    main = Gui.getMainWindow()
    main.raise_()
    main.activateWindow()
    qtest().qWait(150)
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, tab_focus_press)


@guarded
def tab_focus_press():
    """Space on the Top button reached with Tab, the pointer still over the 3D view beside
    the panel (where Space left it)."""
    opened = panel_visible()
    if not opened:
        Gui.runCommand(CMD)
    p = panel()
    make_active(p)
    top = button("Std_ViewTop")
    top.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
    process()
    seen = point_at(gl_widget())
    focus = QtWidgets.QApplication.focusWidget()
    seen.update(opened_by_space=opened, panel_active=p.isActiveWindow(), focus=window_name(focus),
                focus_is_top_button=focus is top)
    CTX["tab_before"], CTX["tab_seen"] = raw_dir(), seen
    qtest().keyClick(top, QtCore.Qt.Key.Key_Space)
    later(600, tab_focus_check)


@guarded
def tab_focus_check():
    d = view_dir()
    detail = dict(CTX["tab_seen"], before=rounded(CTX["tab_before"]), after=d, open_after=panel_visible())
    note("panel_tab_focus_space_applies_view",
         d == (0.0, 0.0, -1.0) and not same_dir(CTX["tab_before"], raw_dir())
         and detail["focus_is_top_button"] and detail["pointer_over_3d_view"], detail)
    note("panel_tab_focus_space_closes_unpinned_panel", not panel_visible(), detail)
    close_panel()
    later(400, outside_open)


@guarded
def outside_open():
    open_panel()
    later(SETTLED_MS, outside_unpinned)


# --- outside ------------------------------------------------------------------------------------

@guarded
def outside_unpinned():
    from jellyjams import orientation

    RES["info"]["active_window_with_panel_open"] = window_name(QtWidgets.QApplication.activeWindow())
    CTX["unpinned_was_open"] = panel_visible()
    CTX["unpinned_after_s"] = since_opened()
    activate_main_window()
    CTX["unpinned_settle_s"] = orientation.OPEN_SETTLE_S
    later(400, check_outside_unpinned)


@guarded
def check_outside_unpinned():
    active = window_name(QtWidgets.QApplication.activeWindow())
    note("click_outside_closes_unpinned_panel",
         CTX["unpinned_was_open"] and not panel_visible() and CTX["unpinned_after_s"] > CTX["unpinned_settle_s"],
         {"open_before": CTX["unpinned_was_open"], "open_after": panel_visible(), "active_window": active,
          "activated_after_s": CTX["unpinned_after_s"], "settle_s": CTX["unpinned_settle_s"]})
    panel().pin_button.setChecked(True)
    open_panel()
    later(SETTLED_MS, outside_pinned)


@guarded
def outside_pinned():
    CTX["pinned_was_open"] = panel_visible()
    activate_main_window()
    later(400, check_outside_pinned)


@guarded
def check_outside_pinned():
    active = window_name(QtWidgets.QApplication.activeWindow())
    note("click_outside_keeps_pinned_panel", CTX["pinned_was_open"] and panel_visible(),
         {"open_before": CTX["pinned_was_open"], "open_after": panel_visible(), "active_window": active})
    panel().pin_button.setChecked(False)
    close_panel()
    later(400, outside_early)


@guarded
def outside_early():
    """Open the unpinned panel and take the activation away as soon as it has it."""
    open_panel()
    CTX["early_polls"] = 0
    later(5, outside_early_wait)


@guarded
def outside_early_wait():
    from jellyjams import orientation

    p = panel()
    if not p.isActiveWindow() and CTX["early_polls"] < 25:
        CTX["early_polls"] += 1
        later(10, outside_early_wait)
        return
    CTX["early"] = {"panel_was_active": p.isActiveWindow(), "seen_active": orientation._seen_active,
                    "open_before": panel_visible()}
    activate_main_window()
    CTX["early"].update(deactivated_after_s=since_opened(), settle_s=orientation.OPEN_SETTLE_S,
                        active_window=window_name(QtWidgets.QApplication.activeWindow()))
    later(500, check_outside_early)


@guarded
def check_outside_early():
    early = dict(CTX["early"], open_after=panel_visible(), panel_active_again=panel().isActiveWindow(),
                 active_window_after=window_name(QtWidgets.QApplication.activeWindow()))
    in_time = early["deactivated_after_s"] < early["settle_s"]
    note("deactivation_right_after_opening_keeps_panel",
         early["open_before"] and early["panel_was_active"] and early["open_after"] and in_time, early)
    note("deactivation_right_after_opening_takes_keyboard_back",
         early["open_after"] and early["panel_active_again"] and in_time, early)
    # The next click elsewhere, well after the settle time, must close the panel.
    CTX["late_click_after_s"] = since_opened()
    activate_main_window()
    later(400, check_outside_late_click)


@guarded
def check_outside_late_click():
    from jellyjams import orientation

    detail = {"activated_after_s": CTX["late_click_after_s"], "settle_s": orientation.OPEN_SETTLE_S,
              "open_after": panel_visible(), "active_window": window_name(QtWidgets.QApplication.activeWindow())}
    note("later_click_elsewhere_closes_panel",
         not panel_visible() and CTX["late_click_after_s"] > orientation.OPEN_SETTLE_S, detail)
    close_panel()
    later(400, normal_nothing_selected)


# --- normal: Normal To outside a sketch -----------------------------------------------------------

@guarded
def normal_nothing_selected():
    Gui.Selection.clearSelection()
    skew_camera()
    later(300, normal_nothing_run)


@guarded
def normal_nothing_run():
    sb = Gui.getMainWindow().statusBar()
    sb.clearMessage()
    QtWidgets.QToolTip.hideText()
    CTX["nothing_before"] = raw_dir()
    Gui.runCommand(NORMAL_TO)
    CTX["nothing_message"] = sb.currentMessage()
    later(600, normal_nothing_check)


@guarded
def normal_nothing_check():
    from jellyjams import orientation

    before, after = CTX["nothing_before"], raw_dir()
    note("normal_to_nothing_selected_keeps_view", same_dir(before, after), (rounded(before), rounded(after)))
    message = CTX["nothing_message"]
    note("normal_to_nothing_selected_hint", message == orientation.NORMAL_TO_HINT, message)
    tip = tooltip_text()
    note("normal_to_nothing_selected_tooltip", tip == orientation.NORMAL_TO_HINT,
         {"tooltip_after_600_ms": tip, "pointer": pointer_info()})
    QtWidgets.QToolTip.hideText()
    later(300, normal_panel_open)


@guarded
def normal_panel_open():
    """The unpinned panel opened beside the pointer over the 3D view, nothing selected."""
    Gui.Selection.clearSelection()
    skew_camera()
    if panel() is not None:
        panel().pin_button.setChecked(False)
    make_active(Gui.getMainWindow())
    point_at(gl_widget())
    open_panel()
    later(SETTLED_MS, normal_panel_click)


@guarded
def normal_panel_click():
    sb = Gui.getMainWindow().statusBar()
    sb.clearMessage()
    QtWidgets.QToolTip.hideText()
    p = panel()
    CTX["panel_nothing_before"] = raw_dir()
    CTX["panel_nothing"] = {"open_before": panel_visible(), "panel_active": p.isActiveWindow(),
                            "pinned": p.pin_button.isChecked(), "selection": selection_summary()}
    button(NORMAL_TO).click()
    CTX["panel_nothing"].update(message_right_after=sb.currentMessage(), tooltip_right_after=tooltip_text())
    later(300, normal_panel_check)


@guarded
def normal_panel_check():
    from jellyjams import orientation

    hint = orientation.NORMAL_TO_HINT
    before, after = CTX["panel_nothing_before"], raw_dir()
    detail = dict(CTX["panel_nothing"], open_after=panel_visible(),
                  message_after_300_ms=Gui.getMainWindow().statusBar().currentMessage(),
                  tooltip_after_300_ms=tooltip_text(), before=rounded(before), after=rounded(after),
                  active_window=window_name(QtWidgets.QApplication.activeWindow()))
    note("panel_normal_to_nothing_closes_panel",
         detail["open_before"] and not detail["pinned"] and not detail["open_after"] and same_dir(before, after),
         detail)
    note("panel_normal_to_nothing_hint",
         detail["message_right_after"] == hint and detail["message_after_300_ms"] == hint, detail)
    note("panel_normal_to_nothing_tooltip", detail["tooltip_after_300_ms"] == hint, detail)
    QtWidgets.QToolTip.hideText()
    close_panel()
    Gui.Selection.addSelection("Orient", "Box", "Face2")
    skew_camera()
    later(300, normal_face_run)


@guarded
def normal_face_run():
    CTX["face_before"] = raw_dir()
    Gui.runCommand(NORMAL_TO)
    later(600, normal_face_check)


@guarded
def normal_face_check():
    n = App.getDocument("Orient").getObject("Box").Shape.Face2.normalAt(0, 0)   # +X
    d = raw_dir()
    alignment = dot(d, (n.x, n.y, n.z))
    note("normal_to_face_aligns", abs(alignment) > 0.999 and not same_dir(d, CTX["face_before"]),
         {"face_normal": rounded((n.x, n.y, n.z)), "before": rounded(CTX["face_before"]), "after": rounded(d),
          "dot": round(alignment, 4)})
    Gui.Selection.clearSelection()
    # Done with Orient: closing it leaves OrientPick's the only 3D view, so once that one is
    # undocked no 3D view is left in the MDI area (the undock part depends on this).
    App.closeDocument("Orient")
    DOCS.remove("Orient")
    later(300, pick_setup)


# --- pick: Normal To on a whole sketch, a plane, two faces, and from the ribbon ---------------------

@guarded
def pick_setup():
    doc = new_doc("OrientPick")
    body, sketch, pad = padded_body(doc)
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    Gui.SendMsgToActiveView("ViewFit")
    no_animation()
    xz = plane(body, "XZ_Plane")
    CTX["pick"] = {"doc": doc.Name, "body": body.Name, "origin": body.Origin.Name, "sketch": sketch.Name,
                   "pad": pad.Name, "xz": xz.Name}
    RES["info"]["pick_xz_plane_label"] = xz.Label
    later(800, pick_sketch_select)


def pick_obj(key):
    p = CTX["pick"]
    return App.getDocument(p["doc"]).getObject(p[key])


def start_pick(select, then):
    """Skewed camera, then the selection `select()` makes, then `then` 300 ms later."""
    Gui.Selection.clearSelection()
    skew_camera()
    select()
    later(300, then)


def run_normal_to():
    CTX["pick_before"] = raw_dir()
    CTX["pick_selection"] = selection_summary()
    sb = Gui.getMainWindow().statusBar()
    sb.clearMessage()
    Gui.runCommand(NORMAL_TO)
    CTX["pick_message"] = sb.currentMessage()


def aligned_detail(normal):
    d = raw_dir()
    return {"normal": rounded(normal), "before": rounded(CTX["pick_before"]), "after": rounded(d),
            "dot": round(dot(d, normal), 4), "selection": CTX["pick_selection"]}


def is_aligned(detail):
    return abs(detail["dot"]) > 0.999 and detail["after"] != rounded(CTX["pick_before"])


@guarded
def pick_sketch_select():
    p = CTX["pick"]
    # A click on the sketch in the model tree selects it below its body: (Body, "Sketch.").
    start_pick(lambda: Gui.Selection.addSelection(p["doc"], p["body"], p["sketch"] + "."), pick_sketch_run)


@guarded
def pick_sketch_run():
    CTX["pick_in_edit"] = sketch_in_edit() is not None
    run_normal_to()
    later(600, pick_sketch_check)


@guarded
def pick_sketch_check():
    detail = aligned_detail(normal_of(pick_obj("sketch")))
    detail["sketch_in_edit"] = CTX["pick_in_edit"]
    note("normal_to_whole_sketch_aligns", is_aligned(detail) and not CTX["pick_in_edit"], detail)
    p = CTX["pick"]
    start_pick(lambda: Gui.Selection.addSelection(p["doc"], p["body"], "%s.%s." % (p["origin"], p["xz"])),
               pick_plane_run)


@guarded
def pick_plane_run():
    run_normal_to()
    later(600, pick_plane_check)


@guarded
def pick_plane_check():
    xz = pick_obj("xz")
    detail = aligned_detail(normal_of(xz))
    detail["label"] = xz.Label
    note("normal_to_origin_plane_aligns", is_aligned(detail), detail)
    p = CTX["pick"]

    def two_faces():
        Gui.Selection.addSelection(p["doc"], p["pad"], "Face1")
        Gui.Selection.addSelection(p["doc"], p["pad"], "Face2")

    start_pick(two_faces, pick_two_run)


@guarded
def pick_two_run():
    run_normal_to()
    later(600, pick_two_check)


@guarded
def pick_two_check():
    from jellyjams import orientation

    before, after = CTX["pick_before"], raw_dir()
    note("normal_to_two_faces_keeps_view", same_dir(before, after),
         {"before": rounded(before), "after": rounded(after), "selection": CTX["pick_selection"]})
    note("normal_to_two_faces_hint", CTX["pick_message"] == orientation.NORMAL_TO_HINT, CTX["pick_message"])
    Gui.Selection.clearSelection()
    later(300, pick_ribbon)


def side_face(shape):
    """(name, normal) of the first face of `shape` that faces along X."""
    for index, face in enumerate(shape.Faces, start=1):
        n = face.normalAt(0, 0)
        if abs(abs(n.x) - 1.0) < 1e-9:
            return "Face%d" % index, vec(n)
    return None, None


@guarded
def pick_ribbon():
    mw = Gui.getMainWindow()
    dock = mw.findChild(QtWidgets.QDockWidget, RIBBON)
    btn = dock.findChild(QtWidgets.QToolButton, RIBBON_BUTTON + NORMAL_TO) if dock is not None else None
    align = dock.findChild(QtWidgets.QToolButton, RIBBON_BUTTON + "Std_AlignToSelection") if dock is not None else None
    tabs = dock.findChild(QtWidgets.QTabWidget, RIBBON_TABS) if dock is not None else None
    title = None
    if btn is not None and tabs is not None:
        for i in range(tabs.count()):
            if tabs.widget(i).isAncestorOf(btn):
                title = tabs.tabText(i).replace("&", "")
                tabs.setCurrentIndex(i)   # show the page, as a user does before clicking
    detail = {"dock": dock is not None, "button": btn.objectName() if btn is not None else None,
              "text": btn.text() if btn is not None else None, "tab": title,
              "std_align_to_selection_button": align is not None}
    note("evaluate_ribbon_normal_to_is_jellyjams",
         btn is not None and title == "Evaluate" and align is None, detail)
    CTX["ribbon_button"] = btn
    name, normal = side_face(pick_obj("pad").Shape)
    CTX["ribbon_face"] = (name, normal)
    p = CTX["pick"]
    start_pick(lambda: name and Gui.Selection.addSelection(p["doc"], p["pad"], name), pick_ribbon_run)


@guarded
def pick_ribbon_run():
    btn = CTX["ribbon_button"]
    CTX["pick_before"] = raw_dir()
    CTX["pick_selection"] = selection_summary()
    CTX["ribbon_enabled"] = btn.isEnabled() if btn is not None else None
    if btn is not None:
        btn.click()
    later(600, pick_ribbon_check)


@guarded
def pick_ribbon_check():
    name, normal = CTX["ribbon_face"]
    if normal is None:
        note("evaluate_ribbon_normal_to_face_aligns", False, "no face of the Pad faces along X")
    else:
        detail = aligned_detail(normal)
        detail.update(face=name, button_enabled=CTX["ribbon_enabled"])
        note("evaluate_ribbon_normal_to_face_aligns", CTX["ribbon_button"] is not None and is_aligned(detail), detail)
    Gui.Selection.clearSelection()
    later(300, pick_more_setup)


@guarded
def pick_more_setup():
    """A cylinder beside the Pad and a datum line in the body, for the picks FreeCAD decides."""
    p = CTX["pick"]
    doc = App.getDocument(p["doc"])
    body = pick_obj("body")
    cylinder = doc.addObject("Part::Cylinder", "Cylinder")
    cylinder.Placement.Base = App.Vector(60, 0, 0)
    line = body.newObject("PartDesign::Line", "DatumLine")
    line.MapMode = "Deactivated"
    line.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    doc.recompute()
    p.update(cylinder=cylinder.Name, line=line.Name, x_axis=plane(body, "X_Axis").Name)
    RES["info"]["pick_cylinder_face1"] = cylinder.Shape.Face1.Surface.TypeId
    later(500, pick_curved_face)


def freecad_case(check, select, then):
    """Normal To with select()'s pick from the skewed camera, then FreeCAD's own Align to
    Selection with the same pick from the same camera. Normal To must turn the view, and
    exactly as FreeCAD does: FreeCAD decides for these picks."""
    CTX["case"] = {"check": check, "select": select, "then": then}
    start_pick(select, freecad_case_run)


@guarded
def freecad_case_run():
    from jellyjams import orientation

    case = CTX["case"]
    case["target"] = repr(orientation.normal_to_target())
    run_normal_to()
    later(600, freecad_case_align)


@guarded
def freecad_case_align():
    case = CTX["case"]
    case.update(before=CTX["pick_before"], selection=CTX["pick_selection"], message=CTX["pick_message"],
                after=raw_dir())
    start_pick(case["select"], freecad_case_align_run)


@guarded
def freecad_case_align_run():
    CTX["case"]["align_before"] = raw_dir()
    Gui.runCommand(ALIGN)
    later(600, freecad_case_check)


@guarded
def freecad_case_check():
    case = CTX["case"]
    by_freecad = raw_dir()
    detail = {"target": case["target"], "selection": case["selection"], "before": rounded(case["before"]),
              "after": rounded(case["after"]), "freecad_after": rounded(by_freecad), "message": case["message"]}
    note(case["check"], not same_dir(case["before"], case["after"]) and same_dir(case["before"], case["align_before"])
         and max(abs(a - b) for a, b in zip(case["after"], by_freecad)) < 1e-4, detail)
    Gui.Selection.clearSelection()
    later(300, case["then"])


@guarded
def pick_curved_face():
    p = CTX["pick"]
    freecad_case("normal_to_curved_face_turns_view",
                 lambda: Gui.Selection.addSelection(p["doc"], p["cylinder"], "Face1"), pick_datum_line)


@guarded
def pick_datum_line():
    p = CTX["pick"]
    freecad_case("normal_to_datum_line_turns_view",
                 lambda: Gui.Selection.addSelection(p["doc"], p["body"], p["line"] + "."), pick_origin_axis)


@guarded
def pick_origin_axis():
    p = CTX["pick"]
    freecad_case("normal_to_origin_axis_turns_view",
                 lambda: Gui.Selection.addSelection(p["doc"], p["body"], "%s.%s." % (p["origin"], p["x_axis"])),
                 pick_link_setup)


@guarded
def pick_link_setup():
    """The body turned 30 degrees about Z, and an App::Link to it with its own placement turned
    90 degrees about X (a link's placement replaces the linked body's)."""
    p = CTX["pick"]
    doc = App.getDocument(p["doc"])
    body = pick_obj("body")
    body.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(Z_AXIS, 30))
    link = doc.addObject("App::Link", "Link")
    link.LinkedObject = body
    link.Placement = App.Placement(App.Vector(0, 80, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    doc.recompute()
    p["link"] = link.Name
    later(500, pick_link_select)


@guarded
def pick_link_select():
    p = CTX["pick"]
    # The sketch selected through the link, as a click on it below the link in the tree does.
    start_pick(lambda: Gui.Selection.addSelection(p["doc"], p["link"], p["sketch"] + "."), pick_link_run)


@guarded
def pick_link_run():
    from jellyjams import orientation

    CTX["link_target"] = repr(orientation.normal_to_target())
    CTX["link_path"] = [(s.ObjectName, list(s.SubElementNames)) for s in Gui.Selection.getSelectionEx("", 0)]
    run_normal_to()
    later(600, pick_link_check)


@guarded
def pick_link_check():
    sketch, link = pick_obj("sketch"), pick_obj("link")
    through_link = App.GeoFeature.getGlobalPlacementOf(sketch, link, sketch.Name + ".").Rotation
    own = sketch.getGlobalPlacement().Rotation
    link_normal, own_normal = vec(through_link.multVec(Z_AXIS)), vec(own.multVec(Z_AXIS))
    camera = Gui.ActiveDocument.ActiveView.getCameraOrientation()
    detail = aligned_detail(link_normal)
    detail.update(own_normal=rounded(own_normal), expected_q=tuple(round(v, 4) for v in through_link.Q),
                  camera_q=tuple(round(v, 4) for v in camera.Q), target=CTX["link_target"],
                  selection_path=CTX["link_path"], message=CTX["pick_message"])
    note("normal_to_linked_sketch_follows_link",
         is_aligned(detail) and abs(dot(raw_dir(), own_normal)) < 0.999 and camera.isSame(through_link, 1e-4),
         detail)
    Gui.Selection.clearSelection()
    later(300, combo_space)


# --- combo: Space on the focused workbench selector ---------------------------------------------------

@guarded
def combo_space():
    mw = Gui.getMainWindow()
    combos = [c for c in mw.findChildren(QtWidgets.QComboBox) if class_name(c) == "Gui::WorkbenchComboBox"]
    combo = next((c for c in combos if c.isVisible()), None)
    if combo is None:
        detail = {"workbench_combo_boxes": len(combos), "visible": 0}
        note("workbench_combo_space_opens_panel", False, detail)
        note("workbench_combo_space_no_popup", False, detail)
        later(300, undock_start)
        return
    activate_main_window()
    combo.setFocus()
    process()
    # The pointer rests on the status bar: neither a 3D view nor the model tree, so the
    # toolbar rule alone has to decide.
    spot = mw.statusBar() if mw.statusBar().isVisible() else mw.findChild(QtWidgets.QDockWidget, RIBBON)
    pointer = point_at(spot)
    toolbar = ancestor(combo, lambda w: isinstance(w, QtWidgets.QToolBar))
    CTX["combo"], CTX["combo_text"] = combo, combo.currentText()
    CTX["combo_detail"] = dict(pointer, toolbar=window_name(toolbar),
                               focus_is_combo=QtWidgets.QApplication.focusWidget() is combo)
    qtest().keyClick(combo, QtCore.Qt.Key.Key_Space)
    later(600, combo_check)


@guarded
def combo_check():
    combo = CTX["combo"]
    popup = combo.view().isVisible()
    if popup:
        combo.hidePopup()
    note("workbench_combo_space_opens_panel", panel_visible(), CTX["combo_detail"])
    note("workbench_combo_space_no_popup", not popup and combo.currentText() == CTX["combo_text"],
         {"popup": popup, "before": CTX["combo_text"], "after": combo.currentText()})
    escape_panel()
    later(400, undock_start)


# --- undock: an undocked 3D view -------------------------------------------------------------------

@guarded
def undock_start():
    RES["info"]["undock_command"] = UNDOCK in Gui.listCommands()
    Gui.runCommand(UNDOCK, 1)
    later(1500, undock_check)


@guarded
def undock_check():
    view = undocked_view()
    note("view_undocked", view is not None and view.isWindow(),
         {"title": view.windowTitle() if view is not None else None, "mdi_view": class_name(mdi_view())})
    if view is not None:
        RES["info"]["undocked_view_children"] = [
            (class_name(w), w.isVisible()) for w in view.findChildren(QtWidgets.QWidget)
            if w.inherits("QOpenGLWidget") or class_name(w).startswith("Gui::")]
    if view is None:
        note("undocked_commands_enabled", False, "no undocked 3D view")
        note("undocked_space_opens_panel", False, "no undocked 3D view")
        later(100, undock_redock)
        return
    make_active(view)
    later(400, undock_commands)


@guarded
def undock_commands():
    from jellyjams import orientation

    no_animation()
    refresh_commands()
    states = command_states()
    detail = dict(states, view3d_active=orientation.view3d_active(),
                  active_window=window_name(QtWidgets.QApplication.activeWindow()))
    note("undocked_commands_enabled", all(states[c] is True for c in (CMD, NORMAL_TO)), detail)
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, undock_space_check)


@guarded
def undock_space_check():
    from jellyjams import orientation

    opened = panel_visible()
    note("undocked_space_opens_panel", opened,
         {"target": RES["info"].get("view_key_target"), "pointer": RES["info"].get("view_key_pointer")})
    if not opened:
        Gui.runCommand(CMD)   # so the keyboard checks below still run
    CTX["undock_escape"] = {"opened_by_space": opened, "panel_active": panel().isActiveWindow(),
                            "return_to": window_name(orientation._return_to)}
    escape_panel()
    later(400, undock_escape_check)


@guarded
def undock_escape_check():
    active = QtWidgets.QApplication.activeWindow()
    detail = dict(CTX["undock_escape"], open_after=panel_visible(), active_window=window_name(active),
                  active_is_undocked_view=is_own_window_3d_view(active))
    note("undocked_escape_gives_keyboard_back_to_view", not panel_visible() and is_own_window_3d_view(active), detail)
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, undock_choose)


@guarded
def undock_choose():
    opened = panel_visible()
    if not opened:
        Gui.runCommand(CMD)
    p = panel()
    p.pin_button.setChecked(False)
    CTX["undock_choice"] = {"opened_by_space": opened, "panel_active": p.isActiveWindow()}
    button("Std_ViewTop").click()
    later(500, undock_choice_check)


@guarded
def undock_choice_check():
    active = QtWidgets.QApplication.activeWindow()
    detail = dict(CTX["undock_choice"], open_after=panel_visible(), active_window=window_name(active),
                  active_is_undocked_view=is_own_window_3d_view(active), direction=view_dir())
    note("undocked_choice_gives_keyboard_back_to_view", not panel_visible() and is_own_window_3d_view(active), detail)
    close_panel()
    later(400, undock_redock)


@guarded
def undock_redock():
    view = undocked_view()
    if view is not None:
        make_active(view)   # the command acts on the active view
    later(300, undock_redock_run)


@guarded
def undock_redock_run():
    if undocked_view() is not None:
        Gui.runCommand(UNDOCK, 0)
    later(1500, undock_redock_check)


@guarded
def undock_redock_check():
    undocked = undocked_view()
    RES["info"].setdefault("redock", []).append({"undocked": undocked is not None,
                                                 "active_window": window_name(QtWidgets.QApplication.activeWindow())})
    if undocked is not None and len(RES["info"]["redock"]) == 1:
        # FreeCAD's own other way back: Esc in an undocked view docks it.
        make_active(undocked)
        qtest().keyClick(gl_widget(), QtCore.Qt.Key.Key_Escape)
        later(1500, undock_redock_check)
        return
    view = mdi_view()
    note("view_docked_again", undocked_view() is None and view is not None and view.inherits(VIEW3D_CLASS),
         {"undocked": window_name(undocked_view()), "mdi_view": class_name(view)})
    activate_main_window()
    no_animation()
    later(500, start_page)


# --- start: the Start page in front ------------------------------------------------------------------

def start_sub_window():
    return sub_window(lambda w: class_name(w) == START_CLASS)


@guarded
def start_page():
    sub = start_sub_window()
    RES["info"]["start_page"] = {"already_open": sub is not None}
    if sub is None and "Start_Start" in Gui.listCommands():
        Gui.runCommand("Start_Start")
        process()
        sub = start_sub_window()
    if sub is None:
        note("start_page_commands_disabled", False, "no Start page")
        note("start_page_space_keeps_panel_closed", False, "no Start page")
        later(100, start_page_done)
        return
    CTX["start_sub"] = sub
    mdi_area().setActiveSubWindow(sub)
    activate_main_window()
    later(500, start_page_commands)


@guarded
def start_page_commands():
    from jellyjams import orientation

    refresh_commands()
    states = command_states()
    front = Gui.getMainWindow().getActiveWindow()
    detail = dict(states, view3d_active=orientation.view3d_active(), main_window_active=type(front).__name__,
                  freecad_active_view=type(Gui.activeView()).__name__, mdi_current=class_name(mdi_view()))
    note("start_page_commands_disabled", all(states[c] is False for c in (CMD, NORMAL_TO)), detail)
    page = CTX["start_sub"].widget()
    make_active(page)
    page.setFocus()
    process()
    seen = point_at(page)
    focus = QtWidgets.QApplication.focusWidget()
    seen.update(focus=window_name(focus), focus_class=class_name(focus))
    CTX["start_seen"], CTX["start_docs"] = seen, sorted(App.listDocuments())
    if focus is None or isinstance(focus, (QtWidgets.QAbstractButton, QtWidgets.QComboBox)):
        seen["skipped"] = "the focus is on a control of the Start page; Space there would start something"
    else:
        qtest().keyClick(focus, QtCore.Qt.Key.Key_Space)
    later(600, start_page_space_check)


@guarded
def start_page_space_check():
    docs = sorted(App.listDocuments())
    seen = dict(CTX["start_seen"], open_after=panel_visible(), documents_unchanged=docs == CTX["start_docs"])
    note("start_page_space_keeps_panel_closed",
         "skipped" not in seen and not panel_visible() and seen["documents_unchanged"], seen)
    close_panel()
    later(100, start_page_done)


@guarded
def start_page_done():
    view = sub_window(lambda w: w.inherits(VIEW3D_CLASS))
    if view is not None:
        mdi_area().setActiveSubWindow(view)
    activate_main_window()
    no_animation()
    RES["info"]["start_page"]["back_to"] = class_name(mdi_view())
    later(500, dark_theme)


# --- dark -----------------------------------------------------------------------------------------

@guarded
def dark_theme():
    app = QtWidgets.QApplication.instance()
    CTX["style"] = app.styleSheet()
    RES["info"]["app_stylesheet_length"] = len(CTX["style"])
    app.setStyleSheet(DARK_RULE)
    open_panel()
    later(600, dark_check)


@guarded
def dark_check():
    from jellyjams import theme

    palette = theme.widget_colors()

    p = panel()
    want = QtGui.QColor(palette.TEXT).name()
    # A tool button outside the panel shows that the white-text rule is in force.
    control = QtWidgets.QToolButton()
    control.ensurePolished()
    control_text = text_color(control, QtGui.QPalette.ColorRole.ButtonText)
    control.deleteLater()
    pin = p.pin_button
    title = p.findChild(QtWidgets.QLabel, "title")
    front = button("Std_ViewFront")
    seen = {
        "control_button_text": control_text,
        "pin_button_text": text_color(pin, QtGui.QPalette.ColorRole.ButtonText),
        "front_button_text": text_color(front, QtGui.QPalette.ColorRole.ButtonText),
        "title_text": text_color(title, QtGui.QPalette.ColorRole.WindowText) if title is not None else None,
    }
    note("dark_rule_in_force", control_text == "#ffffff", seen)
    note("dark_panel_text_color", seen["pin_button_text"] == want and seen["front_button_text"] == want
         and seen["title_text"] == want, dict(seen, wanted=want))
    readable = text_contrast(pin, p)
    note("dark_pin_text_readable", readable["contrast"] >= CONTRAST_MIN and readable["text_pixels"] > 0, readable)
    p.grab().save(os.path.join(OUT_DIR, "orientation_dark_panel.png"))
    close_panel()
    app = QtWidgets.QApplication.instance()
    app.setStyleSheet(CTX["style"])
    note("app_stylesheet_restored", app.styleSheet() == CTX["style"], len(app.styleSheet()))
    later(500, sketch_setup)


# --- sketch -----------------------------------------------------------------------------------------

@guarded
def sketch_setup():
    doc = new_doc("OrientSketch")
    body = doc.addObject("PartDesign::Body", "Body")
    sketch = sketch_on_xy(body)
    doc.recompute()
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    no_animation()
    CTX["sketch"] = sketch.Name
    Gui.Selection.clearSelection()
    Gui.ActiveDocument.setEdit(sketch.Name)
    later(1500, sketch_commands)


@guarded
def sketch_commands():
    sketch = sketch_in_edit()
    note("sketch_in_edit", sketch is not None and sketch.Name == CTX["sketch"], sketch.Name if sketch else None)
    RES["info"]["sketch_alter_document_allowed"] = Gui.Control.isAllowedAlterDocument()
    refresh_commands()
    states = command_states()
    note("sketch_commands_enabled", all(v is True for v in states.values()), states)
    Gui.Selection.clearSelection()
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, sketch_space_check)


@guarded
def sketch_space_check():
    opened = panel_visible()
    detail = {"target": RES["info"].get("view_key_target"), "pointer": RES["info"].get("view_key_pointer")}
    if not opened:
        a = action(CMD)
        if a is not None:
            a.trigger()   # what the key would do; lets the close checks still run
        detail["opened_by_action_trigger"] = panel_visible()
    note("sketch_space_opens_panel", opened, detail)
    qtest().keyClick(panel(), QtCore.Qt.Key.Key_Escape)
    later(400, sketch_escape_check)


@guarded
def sketch_escape_check():
    note("sketch_escape_closes_panel", not panel_visible())
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, sketch_space_close)


@guarded
def sketch_space_close():
    CTX["sketch_reopened"] = panel_visible()
    open_panel()
    qtest().keyClick(panel(), QtCore.Qt.Key.Key_Space)
    later(400, sketch_space_close_check)


@guarded
def sketch_space_close_check():
    note("sketch_space_closes_panel", not panel_visible(), {"reopened_by_space": CTX["sketch_reopened"]})
    Gui.Selection.clearSelection()
    skew_camera()
    later(300, sketch_normal_run)


def sketch_normal():
    return normal_of(App.ActiveDocument.getObject(CTX["sketch"]))


@guarded
def sketch_normal_run():
    CTX["sketch_before"] = raw_dir()
    Gui.runCommand(NORMAL_TO)
    later(600, sketch_normal_check)


@guarded
def sketch_normal_check():
    d, n = raw_dir(), sketch_normal()
    note("sketch_normal_to_aligns_to_sketch", abs(dot(d, n)) > 0.999 and not same_dir(d, CTX["sketch_before"]),
         {"sketch_normal": rounded(n), "before": rounded(CTX["sketch_before"]), "after": rounded(d)})
    skew_camera()
    later(300, sketch_ctrl8_run)


@guarded
def sketch_ctrl8_run():
    CTX["sketch_before"] = raw_dir()
    press_in_view(QtCore.Qt.Key.Key_8, QtCore.Qt.KeyboardModifier.ControlModifier)
    later(600, sketch_ctrl8_check)


@guarded
def sketch_ctrl8_check():
    d, n = raw_dir(), sketch_normal()
    note("sketch_ctrl8_aligns_to_sketch", abs(dot(d, n)) > 0.999 and not same_dir(d, CTX["sketch_before"]),
         {"sketch_normal": rounded(n), "before": rounded(CTX["sketch_before"]), "after": rounded(d),
          "target": RES["info"].get("view_key_target")})
    Gui.runCommand("Sketcher_LeaveSketch")
    later(800, lambda: when_no_dialog(pad_setup))


# --- pad ---------------------------------------------------------------------------------------------

@guarded
def pad_setup():
    doc = new_doc("OrientPad")
    body, _sketch, pad = padded_body(doc)
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    no_animation()
    Gui.Selection.clearSelection()
    Gui.ActiveDocument.setEdit(pad.Name)
    later(1500, pad_space_on_check_box)


def focus_check_box(box, pointer_target):
    """Give `box` the keyboard focus, then put the pointer on `pointer_target`; returns what
    the Space key will see."""
    make_active(box)
    box.setFocus()
    process()
    pointer = point_at(pointer_target)
    focus = QtWidgets.QApplication.focusWidget()
    return dict(pointer, focus=window_name(focus), focus_is_check_box=focus is box)


@guarded
def pad_space_on_check_box():
    box = task_check_box("checkBoxReversed")
    note("pad_dialog_open", bool(Gui.Control.activeDialog()) and box is not None,
         {"dialog": bool(Gui.Control.activeDialog()), "check_box": box.text() if box is not None else None})
    if box is None:
        later(100, pad_view_space)
        return
    CTX["pad_box"] = box
    seen = focus_check_box(box, task_area(box))
    CTX["pad_before"], CTX["pad_seen"] = box.isChecked(), seen
    note("space_filter_active_in_jellyjams", override_accepted(box), seen)
    qtest().keyClick(box, QtCore.Qt.Key.Key_Space)
    later(600, pad_check_box_check)


@guarded
def pad_check_box_check():
    box = CTX["pad_box"]
    note("pad_space_toggles_check_box", box.isChecked() != CTX["pad_before"],
         dict(CTX["pad_seen"], before=CTX["pad_before"], after=box.isChecked()))
    note("pad_space_on_check_box_keeps_panel_closed", not panel_visible())
    close_panel()
    later(400, pad_pointer_over_view)


@guarded
def pad_pointer_over_view():
    box = CTX["pad_box"]
    seen = focus_check_box(box, gl_widget())
    CTX["pad_before"], CTX["pad_seen"] = box.isChecked(), seen
    qtest().keyClick(box, QtCore.Qt.Key.Key_Space)
    later(600, pad_pointer_over_view_check)


@guarded
def pad_pointer_over_view_check():
    box = CTX["pad_box"]
    note("pad_pointer_over_view_space_opens_panel", panel_visible(), CTX["pad_seen"])
    note("pad_pointer_over_view_check_box_unchanged", box.isChecked() == CTX["pad_before"],
         {"before": CTX["pad_before"], "after": box.isChecked()})
    escape_panel()
    later(400, pad_view_space)


@guarded
def pad_view_space():
    press_in_view(QtCore.Qt.Key.Key_Space)
    later(600, pad_view_space_check)


@guarded
def pad_view_space_check():
    note("pad_dialog_space_in_view_opens_panel", panel_visible(),
         {"target": RES["info"].get("view_key_target"), "pointer": RES["info"].get("view_key_pointer")})
    escape_panel()
    if "pad_box" not in CTX:
        later(400, pad_float_done)
        return
    later(400, pad_float)


@guarded
def pad_float():
    dock = ancestor(CTX["pad_box"], lambda w: isinstance(w, QtWidgets.QDockWidget))
    CTX["task_dock"] = dock
    RES["info"]["task_dock"] = {"name": window_name(dock), "floating_before": dock.isFloating() if dock else None}
    if dock is None:
        note("floating_task_dock_space_toggles_check_box", False, "the check box is in no dock")
        note("floating_task_dock_space_keeps_panel_closed", False, "the check box is in no dock")
        later(100, pad_float_done)
        return
    dock.setFloating(True)
    later(800, pad_float_space)


@guarded
def pad_float_space():
    from jellyjams import orientation

    dock, box = CTX["task_dock"], CTX["pad_box"]
    seen = focus_check_box(box, dock)
    seen.update(dock=window_name(dock), floating=dock.isFloating(), dock_is_window=dock.isWindow(),
                filter_on_dock=dock.objectName() in [t.objectName() for t in orientation._filtered])
    CTX["pad_before"], CTX["pad_seen"] = box.isChecked(), seen
    qtest().keyClick(box, QtCore.Qt.Key.Key_Space)
    later(600, pad_float_check)


@guarded
def pad_float_check():
    box = CTX["pad_box"]
    note("floating_task_dock_space_toggles_check_box", box.isChecked() != CTX["pad_before"],
         dict(CTX["pad_seen"], before=CTX["pad_before"], after=box.isChecked()))
    note("floating_task_dock_space_keeps_panel_closed", not panel_visible())
    close_panel()
    CTX["task_dock"].setFloating(False)
    later(800, pad_float_done)


@guarded
def pad_float_done():
    dock = CTX.get("task_dock")
    if dock is not None:
        RES["info"]["task_dock"]["floating_after"] = dock.isFloating()
    activate_main_window()
    close_task_dialog(accept=False)
    later(500, lambda: when_no_dialog(hole_setup))


# --- hole: a cutting feature with nothing to cut ------------------------------------------------------

@guarded
def hole_setup():
    doc = new_doc("OrientHole")
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    Gui.Selection.clearSelection()
    CTX["hole_doc"] = doc.Name
    later(500, hole_press)


@guarded
def hole_press():
    from jellyjams import ribbon

    doc = App.getDocument(CTX["hole_doc"])
    CTX["hole_before"] = sorted(o.Name for o in doc.Objects)
    sb = Gui.getMainWindow().statusBar()
    sb.clearMessage()
    later(2500, close_stray_modal)   # a FreeCAD message box would otherwise hang the run
    ribbon.run_entry("PartDesign_Hole")   # exactly what a click on Hole Wizard does
    CTX["hole_message"] = sb.currentMessage()
    later(1500, hole_check)


@guarded
def hole_check():
    from jellyjams import sketch_gesture

    doc = App.getDocument(CTX["hole_doc"])
    after = sorted(o.Name for o in doc.Objects)
    editing = sketch_in_edit()
    state = {"objects_before": CTX["hole_before"], "objects_after": after,
             "sketch_in_edit": editing.Name if editing is not None else None,
             "task_dialog": bool(Gui.Control.activeDialog()),
             "sketch_first_pending": sketch_gesture._intent is not None,
             "stray_modal": RES["info"].get("stray_modal")}
    # FreeCAD's own Hole would answer with a modal "No sketch to work on" message box.
    note("hole_without_solid_starts_nothing",
         after == CTX["hole_before"] and editing is None and not state["task_dialog"]
         and not state["sketch_first_pending"] and not state["stray_modal"], state)
    info = Gui.Command.get("PartDesign_Hole").getInfo()
    name = (info.get("menuText") or "PartDesign_Hole").replace("&", "")
    expected = "%s needs a solid to cut into: create a boss or base feature first." % name
    message = CTX["hole_message"]
    note("hole_without_solid_hint", message == expected,
         {"message": message, "expected": expected,
          "still_shown_after_1_5_s": Gui.getMainWindow().statusBar().currentMessage() == expected})
    if Gui.Control.activeDialog():
        close_task_dialog(accept=False)
    later(500, lambda: when_no_dialog(hole2_setup))


@guarded
def hole2_setup():
    """Two padded bodies, none active, nothing selected: FreeCAD does not know which body to
    cut into, so the press is FreeCAD's (it asks for a body)."""
    doc = new_doc("OrientHole2")
    padded_body(doc)
    padded_body(doc)
    Gui.Selection.clearSelection()
    view = Gui.ActiveDocument.ActiveView
    active = view.getActiveObject("pdbody")
    if active is not None:
        view.setActiveObject("pdbody", None)
    after = view.getActiveObject("pdbody")
    CTX["hole2_doc"] = doc.Name
    RES["info"]["hole2"] = {"bodies": [o.Name for o in doc.Objects if o.isDerivedFrom("PartDesign::Body")],
                            "active_body_at_creation": active.Name if active is not None else None,
                            "active_body": after.Name if after is not None else None}
    later(500, hole2_press)


def hole2_watch_modal(waited=0):
    """Record and reject the modal dialogs FreeCAD shows for the press, for up to 4 s."""
    try:
        w = QtWidgets.QApplication.activeModalWidget()
        if w is not None:
            CTX["hole2_modal"].append({"class": class_name(w), "title": w.windowTitle()})
            if hasattr(w, "reject"):
                w.reject()
            else:
                w.close()
        if waited < 4000 and not CTX.get("hole2_done"):
            later(200, lambda: hole2_watch_modal(waited + 200))
    except Exception:
        RES["errors"].append(f"hole2_watch_modal: {traceback.format_exc()}")


@guarded
def hole2_press():
    from jellyjams import ribbon

    doc = App.getDocument(CTX["hole2_doc"])
    CTX["hole2_before"] = sorted(o.Name for o in doc.Objects)
    sb = Gui.getMainWindow().statusBar()
    sb.clearMessage()
    CTX["hole2_messages"], CTX["hole2_modal"] = [], []

    def record(text):
        if text:
            CTX["hole2_messages"].append(text)

    CTX["hole2_record"] = record
    sb.messageChanged.connect(record)
    later(300, hole2_watch_modal)   # FreeCAD's dialog would otherwise hang the run
    ribbon.run_entry("PartDesign_Hole")   # exactly what a click on Hole Wizard does
    CTX["hole2_message"] = sb.currentMessage()
    later(1500, hole2_check)


@guarded
def hole2_check():
    from jellyjams import sketch_gesture

    CTX["hole2_done"] = True
    sb = Gui.getMainWindow().statusBar()
    try:
        sb.messageChanged.disconnect(CTX["hole2_record"])
    except Exception:
        pass
    doc = App.getDocument(CTX["hole2_doc"])
    after = sorted(o.Name for o in doc.Objects)
    editing = sketch_in_edit()
    messages = CTX["hole2_messages"] + [CTX["hole2_message"], sb.currentMessage()]
    state = {"freecad_dialogs": CTX["hole2_modal"], "messages": [m for m in messages if m],
             "objects_unchanged": after == CTX["hole2_before"],
             "sketch_in_edit": editing.Name if editing is not None else None,
             "task_dialog": bool(Gui.Control.activeDialog()),
             "sketch_first_pending": sketch_gesture._intent is not None}
    note("hole_two_bodies_no_needs_solid_text", not any(NEEDS_SOLID in m for m in messages), state)
    note("hole_two_bodies_left_to_freecad",
         bool(CTX["hole2_modal"]) and not state["sketch_first_pending"] and state["objects_unchanged"]
         and editing is None, state)
    if Gui.Control.activeDialog():
        close_task_dialog(accept=False)
    later(500, lambda: when_no_dialog(late_dock))


# --- late: a dock made after activation -----------------------------------------------------------------

@guarded
def late_dock():
    mw = Gui.getMainWindow()
    dock = QtWidgets.QDockWidget("Orientation late dock", mw)
    dock.setObjectName("OrientationLateDock")
    box = QtWidgets.QCheckBox("Late check box", dock)
    box.setObjectName("OrientationLateCheckBox")
    dock.setWidget(box)
    mw.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    dock.setFloating(True)
    dock.resize(260, 90)
    dock.move(mw.geometry().center() - QtCore.QPoint(130, 45))
    dock.show()
    CTX["late_dock"], CTX["late_box"] = dock, box
    CTX["late_filtered_at_creation"] = in_filtered(dock)
    later(800, late_dock_space)


@guarded
def late_dock_space():
    dock, box = CTX["late_dock"], CTX["late_box"]
    seen = focus_check_box(box, box)
    seen.update(dock=window_name(dock), floating=dock.isFloating(), dock_is_window=dock.isWindow(),
                filter_on_dock_at_creation=CTX["late_filtered_at_creation"], filter_on_dock=in_filtered(dock))
    note("late_dock_gets_space_filter", seen["filter_on_dock"], seen)
    CTX["late_before"], CTX["late_seen"] = box.isChecked(), seen
    qtest().keyClick(box, QtCore.Qt.Key.Key_Space)
    later(600, late_dock_check)


@guarded
def late_dock_check():
    dock, box = CTX["late_dock"], CTX["late_box"]
    note("late_dock_space_toggles_check_box", box.isChecked() != CTX["late_before"],
         dict(CTX["late_seen"], before=CTX["late_before"], after=box.isChecked()))
    note("late_dock_space_keeps_panel_closed", not panel_visible())
    close_panel()
    Gui.getMainWindow().removeDockWidget(dock)
    dock.close()
    dock.deleteLater()
    activate_main_window()
    later(500, leave)


# --- leave -------------------------------------------------------------------------------------------

@guarded
def leave():
    panel().pin_button.setChecked(True)   # the panel closes on leave even when pinned
    open_panel()
    later(400, leave_switch)


@guarded
def leave_switch():
    CTX["open_before_leave"] = panel_visible()
    Gui.activateWorkbench("PartDesignWorkbench")
    later(3500, check_after_leave)


@guarded
def check_after_leave():
    from jellyjams import orientation

    note("panel_closed_on_leave", CTX["open_before_leave"] and not panel_visible(),
         {"open_before": CTX["open_before_leave"], "open_after": panel_visible()})
    before = RES["info"]["toggle_visibility_before"]
    note("space_back_to_toggle_visibility", shortcut("Std_ToggleVisibility") == before,
         (shortcut("Std_ToggleVisibility"), before))
    note("orientation_shortcut_removed", shortcut(CMD) in ("", None), shortcut(CMD))
    note("normal_to_shortcut_removed", shortcut(NORMAL_TO) in ("", None), shortcut(NORMAL_TO))
    note("space_filter_dropped_on_leave", orientation._space_filter is None and not orientation._filtered,
         {"filter": orientation._space_filter, "filtered": len(orientation._filtered)})
    mw = Gui.getMainWindow()
    dock = QtWidgets.QDockWidget("Orientation test", mw)
    dock.setObjectName("OrientationTestDock")
    box = QtWidgets.QCheckBox("Plain check box", dock)
    box.setObjectName("OrientationTestCheckBox")
    dock.setWidget(box)
    mw.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
    dock.show()
    CTX["dock"], CTX["dock_box"] = dock, box
    Gui.Selection.clearSelection()
    mw.activateWindow()
    later(500, dock_space)


@guarded
def dock_space():
    box = CTX["dock_box"]
    seen = focus_check_box(box, CTX["dock"])
    refresh_commands()   # Hide/Show is disabled while nothing is selected
    hide_show = action("Std_ToggleVisibility")
    RES["info"]["dock_space"] = dict(seen, hide_show_enabled=hide_show.isEnabled() if hide_show is not None else None)
    note("no_space_filter_after_leave", not override_accepted(box), RES["info"]["dock_space"])
    CTX["dock_before"] = box.isChecked()
    qtest().keyClick(box, QtCore.Qt.Key.Key_Space)
    later(400, dock_space_check)


@guarded
def dock_space_check():
    box, dock = CTX["dock_box"], CTX["dock"]
    note("plain_dock_space_toggles_after_leave", box.isChecked() != CTX["dock_before"],
         {"before": CTX["dock_before"], "after": box.isChecked()})
    note("panel_stays_closed_after_leave", not panel_visible())
    Gui.getMainWindow().removeDockWidget(dock)
    dock.deleteLater()
    finish()


App.Console.PrintMessage(f"JellyJams-orientation starting, results -> {OUT_DIR}\n")
later(4000, start)
