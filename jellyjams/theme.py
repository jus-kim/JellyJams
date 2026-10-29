# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Widget theme: a light, SolidWorks-like look on the main-window stylesheet.

All rules form one block framed by constants.THEME_BEGIN and THEME_END and
placed after the sheet's existing content (the "base sheet"). Only the main
window's own sheet changes; the application stylesheet and the MainWindow
preferences are left alone.
"""

from jellyjams import console, constants, palette

# FreeCAD class names as Qt style sheets spell them ("::" becomes "--").
_MAIN_WINDOW = "Gui--MainWindow"
_MODEL_TREE = "Gui--TreeWidget"

_applied = False
_base_sheet = None      # the main-window sheet minus any JellyJams block, taken at apply
_separator = ""         # text put between the base sheet and the block
_block = None           # the block exactly as appended
_applied_sheet = None   # the whole sheet as apply() set it


# --- rule table ----------------------------------------------------------------


def _rules():
    """[(selectors, [(property, value), ...]), ...] in cascade order."""
    p = palette
    ribbon = "QDockWidget#" + constants.OBJ_RIBBON
    tabs = "QTabWidget#" + constants.OBJ_RIBBON_TABS
    panel = "QFrame#" + constants.OBJ_PANEL
    title = "QLabel#" + constants.OBJ_PANEL_TITLE
    heading = "QLabel#" + constants.OBJ_PANEL_HEADING
    plist = "QListWidget#" + constants.OBJ_PANEL_LIST
    tree = "QDockWidget#%s %s" % (constants.MODEL_DOCK_CANDIDATES[0], _MODEL_TREE)
    dock = _MAIN_WINDOW + " > QDockWidget"
    dock_tabs = _MAIN_WINDOW + " > QTabBar"
    split = (tabs + ' QToolButton[popupMode="1"]',)

    def each(selectors, suffix):
        return tuple(sel + suffix for sel in selectors)

    menus = (tabs + " QMenu", ribbon + " QMenu")
    heading_look = [
        ("background-color", p.PANEL),
        ("color", p.TEXT_SECONDARY),
        ("border", "none"),
        ("border-bottom", "1px solid " + p.BORDER),
        ("padding-top", "4px"),
    ]

    return [
        # A. CommandManager (ribbon)
        ((ribbon,), [
            ("background-color", p.RIBBON_SURFACE),
            ("color", p.TEXT),
            ("border", "none"),
        ]),
        ((ribbon + " > QWidget", tabs + " QStackedWidget", tabs + " QStackedWidget > QWidget"), [
            ("background-color", p.RIBBON_SURFACE),
            ("color", p.TEXT),
        ]),
        ((tabs + " QStackedWidget",), [
            ("border", "none"),
            ("border-bottom", "1px solid " + p.BORDER),
        ]),
        ((tabs + "::pane",), [
            ("background-color", p.RIBBON_SURFACE),
            ("border", "none"),
        ]),
        ((tabs + " QTabBar",), [
            ("background-color", p.TAB_STRIP),
            ("color", p.TEXT_SECONDARY),
        ]),
        ((tabs + " QTabBar::tab",), [
            ("background-color", p.TAB_STRIP),
            ("color", p.TEXT_SECONDARY),
            ("border", "none"),
            ("border-bottom", "2px solid transparent"),
            ("padding", "3px 14px"),
            ("min-width", "60px"),
        ]),
        ((tabs + " QTabBar::tab:hover",), [
            ("color", p.TEXT),
        ]),
        ((tabs + " QTabBar::tab:selected",), [
            ("background-color", p.RIBBON_SURFACE),
            ("color", p.TEXT),
            ("border-bottom", "2px solid " + p.ACCENT),
        ]),
        ((tabs + " QToolButton",), [
            ("background-color", "transparent"),
            ("color", p.TEXT),
            ("border", "1px solid transparent"),
            ("border-radius", "3px"),
            ("padding", "2px 4px"),
            ("font-size", "8pt"),
        ]),
        ((tabs + " QToolButton:hover",), [
            ("background-color", p.HOVER),
            ("border", "1px solid " + p.ACCENT),
        ]),
        ((tabs + " QToolButton:pressed",), [
            ("background-color", p.PRESSED),
            ("border", "1px solid " + p.ACCENT_DARK),
        ]),
        ((tabs + " QToolButton:disabled",), [
            ("color", p.TEXT_DISABLED),
        ]),
        (split, [
            ("padding-right", "16px"),
        ]),
        (each(split, "::menu-button"), [
            ("border", "none"),
            ("width", "12px"),
        ]),
        (each(split, "::menu-button:hover"), [
            ("background-color", p.PRESSED),
        ]),
        (menus, [
            ("background-color", p.PANEL),
            ("color", p.TEXT),
            ("border", "1px solid " + p.BORDER),
        ]),
        (each(menus, "::item"), [
            ("background-color", "transparent"),
            ("color", p.TEXT),
            ("padding", "4px 18px 4px 8px"),
        ]),
        (each(menus, "::item:selected"), [
            ("background-color", p.SELECTION),
            ("color", p.TEXT),
        ]),
        (("QFrame#" + constants.OBJ_RIBBON_SEPARATOR,), [
            ("background-color", p.BORDER),
            ("border", "none"),
            ("min-width", "1px"),
            ("max-width", "1px"),
            ("margin", "4px 3px"),
        ]),

        # B. PropertyManager-style panels (Add Relations, Mate)
        ((panel,), [
            ("background-color", p.PANEL),
            ("color", p.TEXT),
            ("border", "1px solid " + p.ACCENT),
            ("border-radius", "3px"),
        ]),
        ((panel + " QLabel",), [
            ("background-color", "transparent"),
            ("color", p.TEXT),
        ]),
        ((title,), [
            ("font-weight", "bold"),
            ("padding-bottom", "2px"),
        ]),
        ((heading, panel + " " + heading), heading_look),
        ((plist,), [
            ("background-color", p.WINDOW),
            ("color", p.TEXT),
            ("border", "1px solid " + p.BORDER),
            ("selection-background-color", p.SELECTION),
            ("selection-color", p.TEXT),
        ]),
        ((plist + "::item:selected",), [
            ("background-color", p.SELECTION),
            ("color", p.TEXT),
        ]),
        ((panel + " QToolButton",), [
            ("background-color", "transparent"),
            ("color", p.TEXT),
            ("text-align", "left"),
            ("padding", "2px 4px"),
            ("border", "1px solid transparent"),
            ("border-radius", "3px"),
        ]),
        ((panel + " QToolButton:hover",), [
            ("background-color", p.HOVER),
            ("border", "1px solid " + p.ACCENT),
        ]),

        # C. Main window and docks
        ((_MAIN_WINDOW,), [
            ("background-color", p.WINDOW),
        ]),
        ((_MAIN_WINDOW + "::separator",), [
            ("background-color", p.WINDOW),
            ("width", "4px"),
            ("height", "4px"),
        ]),
        ((_MAIN_WINDOW + "::separator:hover",), [
            ("background-color", p.ACCENT),
        ]),
        # Qt paints the dock title text in the dock's color; a ::title color alone has no effect.
        ((dock,), [
            ("color", p.TEXT_SECONDARY),
        ]),
        ((dock + "::title",), [
            ("background-color", p.WINDOW),
            ("color", p.TEXT_SECONDARY),
            ("padding", "3px 6px"),
            ("text-align", "left"),
        ]),
        ((dock_tabs,), [
            ("background-color", p.WINDOW),
        ]),
        ((dock_tabs + "::tab",), [
            ("background-color", p.WINDOW),
            ("color", p.TEXT_SECONDARY),
            ("border", "none"),
            ("border-top", "2px solid transparent"),
            ("padding", "4px 12px"),
        ]),
        ((dock_tabs + "::tab:hover",), [
            ("color", p.TEXT),
        ]),
        ((dock_tabs + "::tab:selected",), [
            ("background-color", p.PANEL),
            ("color", p.TEXT),
            ("border-top", "2px solid " + p.ACCENT),
        ]),

        # D. FeatureManager-style model tree
        ((tree,), [
            ("background-color", p.PANEL),
            ("color", p.TREE_TEXT),
            ("border", "none"),
            ("selection-background-color", p.SELECTION),
            ("selection-color", p.TEXT),
        ]),
        ((tree + "::item:hover",), [
            ("background-color", p.HOVER),
            ("color", p.TREE_TEXT),
        ]),
        ((tree + "::item:selected",), [
            ("background-color", p.SELECTION),
            ("color", p.TEXT),
        ]),
    ]


def _format_rule(selectors, declarations):
    body = "".join("    %s: %s;\n" % (prop, value) for prop, value in declarations)
    return ",\n".join(selectors) + " {\n" + body + "}\n"


def build_block():
    """Begin marker, every rule, end marker; each marker on a line of its own."""
    rules = "".join(_format_rule(sel, decl) for sel, decl in _rules())
    return constants.THEME_BEGIN + "\n" + rules + constants.THEME_END + "\n"


def strip_block(sheet):
    """Cut every complete JellyJams block out of `sheet`. A begin marker with
    no end marker after it cuts everything up to the end of the sheet."""
    text = sheet or ""
    begin, end = constants.THEME_BEGIN, constants.THEME_END
    removed_at_end = False
    while True:
        start = text.find(begin)
        if start < 0:
            break
        stop = text.find(end, start + len(begin))
        if stop < 0:
            text = text[:start]
            removed_at_end = True
            break
        rest = text[stop + len(end):]
        if rest.startswith("\r\n"):
            rest = rest[2:]
        elif rest.startswith("\n"):
            rest = rest[1:]
        text = text[:start] + rest
        removed_at_end = not rest.strip()
    if removed_at_end:
        text = text.rstrip()
    return text


def _main_window():
    import FreeCADGui
    window = FreeCADGui.getMainWindow()
    if window is None:
        raise RuntimeError("FreeCAD has no main window yet")
    return window


def _holds_single_block(sheet, block):
    return (block in sheet
            and sheet.count(constants.THEME_BEGIN) == 1
            and sheet.count(constants.THEME_END) == 1)


def apply():
    """Add the JellyJams block to the main-window sheet; repeated calls keep one block."""
    global _applied, _base_sheet, _separator, _block, _applied_sheet
    try:
        window = _main_window()
        current = window.styleSheet() or ""
        block = build_block()
        if _applied and _holds_single_block(current, block):
            return
        base = strip_block(current)
        separator = "" if not base or base.endswith("\n") else "\n"
        sheet = base + separator + block
        window.setStyleSheet(sheet)
        _base_sheet, _separator, _block, _applied_sheet = base, separator, block, sheet
        _applied = True
    except Exception as exc:
        console.error("the light theme was not applied: %s" % exc)


def _sheet_without_block(current):
    """The sheet to set when the theme comes off."""
    if _applied_sheet is not None and current == _applied_sheet:
        return _base_sheet
    if _block is not None:
        ours = _separator + _block
        if ours and ours in current:
            current = current.replace(ours, "", 1)
        elif _block in current:
            current = current.replace(_block, "", 1)
    if constants.THEME_BEGIN in current:
        return strip_block(current)
    return current


def _strip_leftover():
    """With no base sheet on record, only cut a block found on the current sheet."""
    try:
        window = _main_window()
        current = window.styleSheet() or ""
    except Exception:
        return
    if constants.THEME_BEGIN not in current:
        return
    try:
        window.setStyleSheet(strip_block(current))
    except Exception as exc:
        console.error("the light theme was not taken off: %s" % exc)


def remove():
    """Take the JellyJams block off the main-window sheet. When nobody else
    edited the sheet meanwhile, the original comes back byte for byte."""
    global _applied, _base_sheet, _separator, _block, _applied_sheet
    if not _applied:
        _strip_leftover()
        return
    try:
        window = _main_window()
        current = window.styleSheet() or ""
        target = _sheet_without_block(current)
        if target != current:
            window.setStyleSheet(target)
        _applied = False
        _base_sheet = _block = _applied_sheet = None
        _separator = ""
    except Exception as exc:
        console.error("the light theme was not taken off: %s" % exc)


def is_applied():
    return _applied
