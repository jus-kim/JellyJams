# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Lifecycle tests for the close guard and autoload handling. Run inside the
full FreeCAD GUI with a throwaway config; the environment variable
JELLYJAMS_LIFECYCLE_MODE picks the mode:

    cancel    quit with unsaved changes, press Cancel in the prompt:
              the SolidWorks-style UI must come back afterwards.
    discard   quit with unsaved changes, wait past the quit-prompt poll
              INSIDE the prompt (must stay restored), press Discard.
              Then inspect the saved user.cfg with
                  python check_saved_cfg.py <user.cfg> <nav> <assembly> <partdesign> <techdraw>
              (<nav> is info.nav_before; the other three are the
              Assembly, PartDesign and TechDraw entries of
              info.switch_before in lifecycle_discard.json) and
              relaunch with JELLYJAMS_LIFECYCLE_MODE=after.
    after     fresh start after a discard-quit: stock toolbars must be
              visible in Part Design (no persisted SolidWorks layout).
    autoload  FreeCAD autoloads JellyJams at startup: the layout must
              apply only after the window is shown, and leaving must
              bring back the user's toolbars.

Results: <JELLYJAMS_RESULTS_DIR>/lifecycle_<mode>.json (default <repo>/scratch).
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

MODE = os.environ.get("JELLYJAMS_LIFECYCLE_MODE", "cancel")
OUT_DIR = os.environ.get(
    "JELLYJAMS_RESULTS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch"),
)
os.makedirs(OUT_DIR, exist_ok=True)
RES = {"mode": MODE, "checks": {}, "info": {}, "errors": []}
WB = "JellyJamsWorkbench"
OWN_PARAMS = "User parameter:BaseApp/Preferences/Mod/JellyJams"
# Preference groups whose Bool SwitchToWB JellyJams holds at false while active (switch_prefs)
SWITCH_GROUPS = {
    "Assembly": "User parameter:BaseApp/Preferences/Mod/Assembly",
    "PartDesign": "User parameter:BaseApp/Preferences/Mod/PartDesign",
    "TechDraw": "User parameter:BaseApp/Preferences/Mod/TechDraw/General",
}
BACKUP_KEYS = ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors", "OriginalSwitchToWB",
               "OriginalPartDesignSwitchToWB", "OriginalTechDrawSwitchToWB")
THEME_OPEN = "/* @jellyjams-stylesheet-open */"
# Pause between a workbench switch and the next look at the window. The window-layout spec
# reads the state no sooner than 3.5 s after a switch, when every delayed re-dock has run.
SWITCH_SETTLE_MS = 4000


def note(name, ok, detail=""):
    RES["checks"][name] = {"ok": bool(ok), "detail": str(detail)[:600]}
    App.Console.PrintMessage(f"JellyJams-lifecycle {name}: {'OK' if ok else 'FAIL'} {detail}\n")


def save():
    RES["ok"] = bool(RES["checks"]) and all(c["ok"] for c in RES["checks"].values()) and not RES["errors"]
    with open(os.path.join(OUT_DIR, f"lifecycle_{MODE}.json"), "w", encoding="utf-8") as f:
        json.dump(RES, f, indent=2)


def quit_app():
    save()
    QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)


def guarded(fn):
    def run():
        try:
            fn()
        except Exception:
            RES["errors"].append(f"{fn.__name__}: {traceback.format_exc()}")
            quit_app()
    return run


def mw():
    return Gui.getMainWindow()


def visible_toolbars():
    return sorted(tb.objectName() for tb in mw().findChildren(QtWidgets.QToolBar) if tb.isVisible())


def nav():
    return App.ParamGet("User parameter:BaseApp/Preferences/View").GetString("NavigationStyle", "")


def fit_shortcut():
    return App.ParamGet("User parameter:BaseApp/Preferences/Shortcut").GetString("Std_ViewFitAll", "")


def ribbon_visible():
    d = mw().findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
    return d is not None and d.isVisible()


def switch_to_wb():
    """SwitchToWB of Assembly, PartDesign and TechDraw: True/False, or "absent" when the key is not set."""
    states = {}
    for module, path in SWITCH_GROUPS.items():
        grp = App.ParamGet(path)
        states[module] = grp.GetBool("SwitchToWB", True) if "SwitchToWB" in grp.GetBools() else "absent"
    return states


def all_switches_off(states):
    return all(value is False for value in states.values())


def backups_pending():
    own = App.ParamGet(OWN_PARAMS)
    return sorted(key for key in BACKUP_KEYS if own.GetString(key, ""))


def jj_state():
    from jellyjams import orbit, fcgui, appearances
    report = mw().findChild(QtWidgets.QDockWidget, "Report view")

    return {
        "orbit": fcgui.is_alive(orbit._filter) and orbit._filter.running,
        "appearances": appearances.dock() is not None,
        "report_closed": report is not None and report.isHidden(),
        "theme": THEME_OPEN in mw().styleSheet(),
        "theme_blocks": mw().styleSheet().count(THEME_OPEN),
        "nav": nav(),
        "fit": fit_shortcut(),
        "switch": switch_to_wb(),
        "ribbon": ribbon_visible(),
        "toolbars": visible_toolbars(),
    }


def find_button(dialog, *words):
    if isinstance(dialog, QtWidgets.QMessageBox):
        for sb in ("Cancel", "Discard") if "Cancel" in words else ("Discard", "No"):
            btn = dialog.button(getattr(QtWidgets.QMessageBox.StandardButton, sb))
            if btn is not None and sb.lower() in " ".join(words).lower():
                return btn
    for btn in dialog.findChildren(QtWidgets.QAbstractButton):
        text = btn.text().replace("&", "").lower()
        if any(w.lower() in text for w in words):
            return btn
    return None


# --- cancel / discard -----------------------------------------------------

@guarded
def close_start():
    Gui.activateWorkbench("PartDesignWorkbench")
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, close_record_stock)


@guarded
def close_record_stock():
    report = mw().findChild(QtWidgets.QDockWidget, "Report view")
    if report is not None:
        report.hide()
    RES["info"]["stock_toolbars"] = visible_toolbars()
    RES["info"]["nav_before"] = nav()
    RES["info"]["switch_before"] = switch_to_wb()
    Gui.activateWorkbench(WB)
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, close_make_dirty)


@guarded
def close_make_dirty():
    st = jj_state()
    note("active_before_close", st["theme"] and st["ribbon"] and st["orbit"] and st["appearances"]
         and st["nav"] == "Gui::SolidWorksNavigationStyle", st)
    note("switch_to_wb_off_before_close", all_switches_off(st["switch"]), st["switch"])
    doc = App.newDocument("Dirty")
    doc.addObject("Part::Box", "Box")
    doc.recompute()
    if MODE == "save":
        doc.saveAs(os.path.join(OUT_DIR, "quit_saved.FCStd"))
        doc.getObject("Box").Length = 17
        doc.recompute()
    # The prompt runs a nested event loop inside close(); our timers keep firing.
    QtCore.QTimer.singleShot(1500, during_prompt)
    QtCore.QTimer.singleShot(0, mw().close)


@guarded
def during_prompt():
    modal = QtWidgets.QApplication.activeModalWidget()
    RES["info"]["modal"] = type(modal).__name__ if modal else None
    note("prompt_is_open", modal is not None, RES["info"]["modal"])
    if modal is None:
        quit_app()
        return
    st = jj_state()
    RES["info"]["state_during_prompt"] = st
    note("jellyjams_kept_inside_prompt", st["theme"] and st["ribbon"] and st["orbit"] and st["appearances"] and st["report_closed"], st)
    note("nav_kept_inside_prompt", st["nav"] == "Gui::SolidWorksNavigationStyle", st["nav"])
    note("shortcut_kept_inside_prompt", st["fit"] == "F", st["fit"])
    note("switch_to_wb_kept_inside_prompt", all_switches_off(st["switch"]), st["switch"])
    note("backups_pending_inside_prompt", bool(backups_pending()), backups_pending())
    if MODE == "cancel":
        btn = find_button(modal, "Cancel")
        note("found_cancel", btn is not None)
        save()
        if btn is not None:
            btn.click()
            # window-layout AC 15: the re-apply is complete within 2.5 s of Cancel.
            QtCore.QTimer.singleShot(2500, after_cancel)
        else:
            quit_app()
    elif MODE == "save":
        btn = modal.button(QtWidgets.QMessageBox.StandardButton.Save)
        note("found_save", btn is not None)
        save()
        if btn is not None:
            btn.click()
        else:
            quit_app()
    else:
        btn = find_button(modal, "Discard", "Don't save", "Do not save", "No")
        note("found_discard", btn is not None)
        save()  # the app is about to go away
        if btn is not None:
            btn.click()
        else:
            quit_app()


@guarded
def after_cancel():
    st = jj_state()
    from jellyjams import layout
    RES["info"]["layout_after_cancel"] = {
        "hidden": [bar.objectName() for bar in layout._hidden],
        "generation": layout._generation,
    }
    note("reapplied_after_cancel", st["theme_blocks"] == 1 and st["ribbon"] and st["orbit"] and st["appearances"] and st["report_closed"], st)
    note("nav_reapplied_after_cancel", st["nav"] == "Gui::SolidWorksNavigationStyle", st["nav"])
    note("shortcut_reapplied_after_cancel", st["fit"] == "F", st["fit"])
    note("switch_to_wb_reapplied_after_cancel", all_switches_off(st["switch"]), st["switch"])
    App.closeDocument("Dirty")
    Gui.activateWorkbench("PartDesignWorkbench")
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, finish_cancel)


@guarded
def finish_cancel():
    st = jj_state()
    RES["info"]["state_after_leave"] = st
    missing = sorted(set(RES["info"]["stock_toolbars"]) - set(st["toolbars"]))
    note("stock_restored_after_leave", not missing and not st["theme"] and not st["orbit"] and not st["appearances"], f"missing={missing}")
    note("switch_to_wb_restored_after_leave", st["switch"] == RES["info"]["switch_before"],
         f"now={st['switch']!r} was={RES['info']['switch_before']!r}")
    note("backups_cleared_after_leave", not backups_pending(), backups_pending())
    quit_app()


# --- after (relaunch following a discard-quit) ------------------------------

@guarded
def after_start():
    prev = {}
    try:
        with open(os.path.join(OUT_DIR, "lifecycle_discard.json"), encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        pass
    Gui.activateWorkbench("PartDesignWorkbench")
    RES["info"]["expected"] = prev.get("info", {}).get("stock_toolbars", [])
    RES["info"]["switch_expected"] = prev.get("info", {}).get("switch_before")
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, after_check)


@guarded
def after_check():
    vis = visible_toolbars()
    expected = RES["info"]["expected"]
    missing = sorted(set(expected) - set(vis))
    note("expected_known", bool(expected), expected)
    note("stock_toolbars_visible_after_relaunch", bool(expected) and not missing, f"visible={vis} missing={missing}")
    note("ribbon_not_visible", not ribbon_visible())
    note("backups_cleared_after_relaunch", not backups_pending(), backups_pending())
    switch_expected = RES["info"]["switch_expected"]
    if switch_expected is not None:
        now = switch_to_wb()
        if not isinstance(switch_expected, dict):   # a discard run that recorded only the Assembly value
            now = now["Assembly"]
        note("switch_to_wb_kept_after_relaunch", now == switch_expected,
             f"now={now!r} expected={switch_expected!r}")
    quit_app()


# --- autoload ---------------------------------------------------------------

@guarded
def autoload_check():
    from jellyjams import layout

    active_wb = Gui.activeWorkbench().name()
    note("autoloaded_into_jellyjams", active_wb == WB, active_wb)
    st = jj_state()
    RES["info"]["state_autoloaded"] = st
    note("layout_active_after_show", layout._active and layout._saved_state is not None)
    note("ribbon_visible_after_show", st["ribbon"] and st["orbit"] and st["appearances"])
    kept = {"File", "Edit", "Workbench"}
    extra = [t for t in st["toolbars"] if t not in kept]
    note("stock_toolbars_hidden_after_show", not extra, f"visible={st['toolbars']}")
    Gui.activateWorkbench("PartDesignWorkbench")
    QtCore.QTimer.singleShot(SWITCH_SETTLE_MS, autoload_after_leave)


@guarded
def autoload_after_leave():
    st = jj_state()
    RES["info"]["state_after_leave"] = st
    note("toolbars_back_after_leave", len(st["toolbars"]) > 3, st["toolbars"])
    note("theme_removed_after_leave", not st["theme"] and not st["orbit"] and not st["appearances"])
    quit_app()


App.Console.PrintMessage(f"JellyJams-lifecycle mode={MODE} out={OUT_DIR}\n")
START = {"cancel": close_start, "discard": close_start, "save": close_start,
         "after": after_start, "autoload": autoload_check}[MODE]
QtCore.QTimer.singleShot(6000 if MODE == "autoload" else 4000, START)
