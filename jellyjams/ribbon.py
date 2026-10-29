# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""The JellyJams ribbon, a tabbed command bar in the style of the SolidWorks CommandManager.

Other modules use this API: show/hide for the lifecycle, the visibility guard
for the window layout, find_button() for live tooltips, and run_entry(), which
every ribbon click goes through. The test harness reads the state services.

Widgets are created the first time the ribbon is shown and kept afterwards.
While visible, a timer updates which buttons are enabled and jumps to the
Sketch, Assembly or Drawing tab when the user starts working in that context.
"""

import FreeCAD

from jellyjams import console, constants, fcgui
from jellyjams import icons, ribbon_layout, ribbon_model, ribbon_widgets

REFRESH_MS = constants.RIBBON_REFRESH_MS
CONTEXT_TABS = {
    "sketch": constants.TAB_SKETCH,
    "assembly": constants.TAB_ASSEMBLY,
    "drawing": constants.TAB_DRAWING,
}

_ui = None              # ribbon_widgets.RibbonUI after the first build
_requested = False      # True between show() and hide()
_skipped = []           # entry ids missing from FreeCAD at the last build
_refresh_failure = None


class _ContextState:
    """What the previous refresh saw, so the next one can detect changes."""

    def __init__(self):
        self.sketch = False
        self.assembly = False
        self.sheet = None
        self.pre_sketch_tab = None


_context = _ContextState()


# --- state queries --------------------------------------------------------------------------

def _live_ui():
    ui = _ui
    if ui is None:
        return None
    try:
        return ui if ui.is_alive() else None
    except Exception:
        return None


def is_requested():
    return _requested


def is_built():
    return _live_ui() is not None


def dock():
    ui = _live_ui()
    return ui.dock if ui is not None else None


def find_button(cmd_id):
    """The plain QToolButton of entry `cmd_id` while it exists, else None."""
    ui = _live_ui()
    return ui.find_button(cmd_id) if ui is not None else None


def tab_titles():
    ui = _live_ui()
    return ui.tab_titles() if ui is not None else []


def current_tab_title():
    ui = _live_ui()
    return ui.current_title() if ui is not None else ""


def context_tabs():
    return dict(CONTEXT_TABS)


# --- test services --------------------------------------------------------------------------

def entry_ids():
    """Ids of the plain buttons, followed by all flyout variants and all toggle variants."""
    ui = _live_ui()
    return ui.entry_ids() if ui is not None else []


def skipped_ids():
    return list(_skipped)


def flyout_states():
    ui = _live_ui()
    return ui.flyout_states() if ui is not None else []


def toggle_states():
    ui = _live_ui()
    return ui.toggle_states() if ui is not None else []


# --- build ----------------------------------------------------------------------------------

def _preload_modules():
    try:
        gui_failures, assembly_failures = fcgui.preload_command_modules()
    except Exception as exc:
        console.warning("FreeCAD's command modules did not load: {}".format(exc))
        return [], []
    for module, reason in gui_failures:
        console.warning("FreeCAD module {} did not load, so some of its buttons may be "
                        "missing: {}".format(module, reason))
    return list(gui_failures), list(assembly_failures)


def _available_commands():
    gui = fcgui.gui()
    if gui is None:
        return set()
    try:
        return set(gui.listCommands())
    except Exception as exc:
        console.warning("FreeCAD did not return its command list: {}".format(exc))
        return set()


def _report_skipped(skipped, assembly_failures):
    # Missing Assembly ids are expected when the Assembly modules are absent: log them only.
    assembly_ids = [i for i in skipped if i.startswith("Assembly_")] if assembly_failures else []
    other_ids = [i for i in skipped if i not in assembly_ids]
    if assembly_failures:
        text = "Assembly command modules unavailable ({})".format(", ".join(assembly_failures))
        if assembly_ids:
            text += "; Assembly buttons not shown: {}".format(", ".join(assembly_ids))
        console.log(text)
    if other_ids:
        console.warning("this FreeCAD build lacks {} ribbon command(s); their buttons are "
                        "not shown: {}".format(len(other_ids), ", ".join(other_ids)))


def _build():
    global _ui, _skipped
    main_window = fcgui.main_window()
    if main_window is None:
        console.warning("ribbon not built: FreeCAD has no main window yet")
        return None
    _gui_failures, assembly_failures = _preload_modules()
    # Freshly imported modules add icons under ':/icons', so the icon index starts over.
    icons.reset_index()
    resolved = ribbon_model.resolve(ribbon_layout.TABS, _available_commands())
    for missing, used in resolved.substitutions:
        console.log("{} is missing; its ribbon button runs {} instead".format(missing, used))
    ui = ribbon_widgets.RibbonUI(main_window, resolved, run_entry)
    ui.timer.timeout.connect(_on_timer)
    ui.dock.visibilityChanged.connect(_on_visibility_changed)
    _ui = ui
    _skipped = list(resolved.skipped)
    _report_skipped(resolved.skipped, assembly_failures)
    counts = ui.counts()
    console.message("ribbon ready with {tabs} tabs: {buttons} buttons, {flyouts} flyouts "
                    "holding {variants} tools, {toggles} toggle(s)".format(**counts))
    return ui


def _start(ui):
    ui.dock.show()
    ui.timer.start(REFRESH_MS)
    _refresh(ui)


# --- show / hide ----------------------------------------------------------------------------

def show():
    """Create the ribbon if needed, show it and start the periodic refresh."""
    global _requested
    with console.guard("display the ribbon"):
        ui = _live_ui() or _build()
        if ui is None:
            return
        _requested = True
        _start(ui)


def hide():
    """Hide the ribbon and stop the refresh; the widgets stay for the next show()."""
    global _requested
    _requested = False
    with console.guard("hide the ribbon dock"):
        ui = _live_ui()
        if ui is None:
            return
        ui.timer.stop()
        ui.dock.hide()


def show_if_requested():
    """Re-show a requested ribbon; FreeCAD's restore of the window state can hide docks."""
    if _requested:
        show()


def hide_if_not_requested():
    """Hide the dock if something made it visible while JellyJams does not want it."""
    try:
        if _requested:
            return
        ui = _live_ui()
        if ui is None:
            return
        ui.timer.stop()
        if not ui.dock.isHidden():
            ui.dock.hide()
    except Exception:
        pass


def _on_visibility_changed(visible):
    try:
        if visible and not _requested:
            # Qt is still delivering this signal; hiding the dock from inside it is not safe.
            fcgui.defer(hide_if_not_requested, 0)
    except Exception:
        pass


def rebuild():
    """Throw away the widgets and build them again, keeping tab position and visibility."""
    global _ui, _skipped
    if _ui is None:
        return
    with console.guard("recreate the ribbon"):
        old = _ui
        index = 0
        try:
            index = old.tabs.currentIndex()
        except Exception:
            pass
        old.dispose(fcgui.main_window())
        _ui = None
        _skipped = []
        ui = _build()
        if ui is None:
            return
        count = ui.tabs.count()
        if count:
            ui.tabs.setCurrentIndex(max(0, min(index, count - 1)))
        if _requested:
            _start(ui)


# --- refresh --------------------------------------------------------------------------------

def refresh_now():
    """Run one refresh immediately: context tabs, enabled states and toggles."""
    ui = _live_ui()
    if ui is not None:
        _refresh(ui)


def _on_timer():
    ui = _live_ui()
    if ui is not None:
        _refresh(ui)


def _refresh(ui):
    global _refresh_failure
    try:
        sketch = _sketch_editing()
        _update_context(ui, sketch, _assembly_active(), _active_sheet())
        ui.refresh_states(sketch)
        _refresh_failure = None
    except Exception as exc:
        text = str(exc)
        # Log each distinct error once; the timer would otherwise repeat it every tick.
        if text != _refresh_failure:
            _refresh_failure = text
            console.log("ribbon update error: {}".format(text))


def _sketch_editing():
    try:
        return fcgui.sketch_in_edit() is not None
    except Exception:
        return False


def _assembly_active():
    try:
        import UtilsAssembly
        return UtilsAssembly.activeAssembly() is not None
    except Exception:
        return False


def _active_sheet():
    try:
        return fcgui.active_sheet_window()
    except Exception:
        return None


def _same_widget(a, b):
    if a is b:
        return True
    if a is None or b is None:
        return False
    try:
        import shiboken6
        return shiboken6.getCppPointer(a)[0] == shiboken6.getCppPointer(b)[0]
    except Exception:
        return False


def _update_context(ui, sketch, assembly, sheet):
    state = _context

    if sheet is not None:
        _attach_sheet_drag(sheet)
    entered_sheet = sheet is not None and not _same_widget(sheet, state.sheet)
    state.sheet = sheet
    if entered_sheet:
        ui.select_tab(constants.TAB_DRAWING)
        _on_sheet_entered()

    if assembly and not state.assembly and not sketch:
        ui.select_tab(constants.TAB_ASSEMBLY)
    state.assembly = assembly

    # Checked last on purpose: entering a sketch beats a sheet or assembly change in the same tick.
    if sketch and not state.sketch:
        if ui.tab_index(constants.TAB_SKETCH) >= 0:
            state.pre_sketch_tab = ui.current_title()
            ui.select_tab(constants.TAB_SKETCH)
    elif state.sketch and not sketch:
        if state.pre_sketch_tab:
            ui.select_tab(state.pre_sketch_tab)
        state.pre_sketch_tab = None
    state.sketch = sketch


def _attach_sheet_drag(window):
    try:
        from jellyjams import sheet_drag
        sheet_drag.attach(window)
    except Exception:
        pass


def _on_sheet_entered():
    doc = getattr(FreeCAD, "ActiveDocument", None)
    try:
        from jellyjams import projected_view
        projected_view.make_groups_movable(doc)
    except Exception:
        pass
    try:
        from jellyjams import naming
        naming.refresh_drawing(doc)
    except Exception:
        pass


# --- click dispatch -------------------------------------------------------------------------

def _stop_sketch_tool(cmd_id):
    try:
        from jellyjams import sketch_tools
        sketch_tools.stop_running(except_cmd=cmd_id)
    except Exception as exc:
        console.log("the Centerline / Midpoint Line tool did not stop: {}".format(exc))


def _gesture_took_over(cmd_id):
    try:
        from jellyjams import sketch_gesture
        return bool(sketch_gesture.try_run(cmd_id))
    except Exception as exc:
        console.log("handing the open sketch to {} failed: {}".format(cmd_id, exc))
        return False


def run_entry(cmd_id, index=None):
    """Carry out a ribbon click. Every button, flyout and toggle calls this.

    Order: first stop a running Centerline / Midpoint Line tool (unless the
    click is for that same tool); then, for clicks without an index, let the
    open-sketch gesture take over a profile feature; otherwise run the command
    with FreeCADGui.runCommand(cmd_id[, index]).
    """
    try:
        _stop_sketch_tool(cmd_id)
        if index is None and _gesture_took_over(cmd_id):
            return
        fcgui.run_command(cmd_id, index)
    except Exception:
        console.error("the ribbon could not start {}".format(cmd_id), with_traceback=True)
