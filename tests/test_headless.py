# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""
Headless test harness for JellyJams.

Run with FreeCAD's own interpreter, from any working directory:

    "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_headless.py [-v] [-k PATTERN]

FreeCAD and FreeCADGui are replaced by the stubs of headless_stubs.py and Qt runs
on the offscreen platform, so no FreeCAD window opens. Every suite imports the
modules it exercises inside its tests: a missing or broken module fails its own
tests and the run continues. Every test starts from fresh stub state (parameters,
console, recorded calls, active workbench and a new main window).

Exit code 0 means every test passed. Set JELLYJAMS_ECHO_CONSOLE=1 to echo the captured
FreeCAD console output to stderr.
"""

import ast
import builtins
import codecs
import contextlib
import datetime
import faulthandler
import importlib
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import headless_stubs  # noqa: E402

STUBS = headless_stubs.install()

from PySide import QtCore, QtGui, QtSvg, QtWidgets  # noqa: E402

REPO = STUBS.repo
PACKAGE_DIR = os.path.join(REPO, "jellyjams")
ICONS_DIR = os.path.join(REPO, "resources", "icons")
WATCHDOG_SECONDS = 300

HEADER = [
    "# -*- coding: utf-8 -*-",
    "# SPDX-License-Identifier: MIT",
    "# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>",
]
WB = "JellyJamsWorkbench"
PREFIX = "JellyJams: "
P_OWN = "User parameter:BaseApp/Preferences/Mod/JellyJams"
P_RIBBON = P_OWN + "/FlyoutChoices"
P_VIEW = "User parameter:BaseApp/Preferences/View"
P_SHORTCUT = "User parameter:BaseApp/Preferences/Shortcut"
P_ASSEMBLY = "User parameter:BaseApp/Preferences/Mod/Assembly"
P_PARTDESIGN = "User parameter:BaseApp/Preferences/Mod/PartDesign"
P_TECHDRAW_GENERAL = "User parameter:BaseApp/Preferences/Mod/TechDraw/General"
# FreeCAD preference group -> JellyJams backup key of its Bool SwitchToWB (switch_prefs)
SWITCH_BACKUPS = {
    P_ASSEMBLY: "OriginalSwitchToWB",
    P_PARTDESIGN: "OriginalPartDesignSwitchToWB",
    P_TECHDRAW_GENERAL: "OriginalTechDrawSwitchToWB",
}
SW_NAV = "Gui::SolidWorksNavigationStyle"
THEME_BEGIN = "/* @jellyjams-stylesheet-open */"
THEME_END = "/* @jellyjams-stylesheet-close */"
NS_FREECAD_SVG = "https://www.freecad.org/wiki/index.php?title=Svg_Namespace"
EM_DASH = "\u2014"
EN_DASH = "\u2013"
_MISSING = object()

# --------------------------------------------------------------------------
# Expected public facts (architecture sections 4-6, the specs)
# --------------------------------------------------------------------------

# The five sketch shapes for the drawing sheet, keyed by their FreeCAD menu text.
SHEET_SHAPES = {
    "Line": "JellyJams_LineOnSheet", "Rectangle": "JellyJams_CornerRectangleOnSheet",
    "Circle": "JellyJams_CircleOnSheet", "Arc": "JellyJams_CenterpointArcOnSheet",
    "Polygon": "JellyJams_PolygonOnSheet",
}

EXPECTED_COMMANDS = [
    "JellyJams_Diagnostics", "JellyJams_Centerline", "JellyJams_MidpointLine", "JellyJams_NewAssembly",
    "JellyJams_RotateComponent", "JellyJams_MakeDrawing", "JellyJams_SheetProperties",
    "JellyJams_InsertPicture", "JellyJams_ProjectedView", "JellyJams_ViewScale", "JellyJams_SurfaceFinish",
    "JellyJams_WeldSymbol", "JellyJams_LineFormat", "JellyJams_LineOnSheet",
    "JellyJams_CornerRectangleOnSheet", "JellyJams_CircleOnSheet", "JellyJams_CenterpointArcOnSheet",
    "JellyJams_PolygonOnSheet", "JellyJams_Note", "JellyJams_SaveAsPDF", "JellyJams_SaveAsDXF",
    "JellyJams_ViewOrientation", "JellyJams_NormalTo", "JellyJams_Appearances",
]

# JellyJams commands without a ribbon button: View Orientation (Space) is in the JellyJams menu
# only. Normal To (Ctrl+8) is on the Evaluate tab, in the JellyJams menu and in the Orientation
# panel; FreeCAD's own Align to selection is on no tab
OFF_RIBBON_COMMANDS = {"JellyJams_ViewOrientation", "JellyJams_Appearances"}

EXPECTED_PROVIDERS = {
    "jellyjams.appearances": ("JellyJams_Appearances",),
    "jellyjams.diagnostics": ("JellyJams_Diagnostics",),
    "jellyjams.sketch_tools": ("JellyJams_Centerline", "JellyJams_MidpointLine"),
    "jellyjams.assembly_commands": ("JellyJams_NewAssembly", "JellyJams_RotateComponent"),
    "jellyjams.make_drawing": ("JellyJams_MakeDrawing",),
    "jellyjams.sheet_properties": ("JellyJams_SheetProperties",),
    "jellyjams.sheet_sketch": tuple(SHEET_SHAPES.values()),
    "jellyjams.sheet_text": ("JellyJams_Note",),
    "jellyjams.insert_picture": ("JellyJams_InsertPicture",),
    "jellyjams.projected_view": ("JellyJams_ProjectedView",),
    "jellyjams.view_scale": ("JellyJams_ViewScale",),
    "jellyjams.surface_finish": ("JellyJams_SurfaceFinish",),
    "jellyjams.weld_symbol": ("JellyJams_WeldSymbol",),
    "jellyjams.line_format": ("JellyJams_LineFormat",),
    "jellyjams.drawing_export": ("JellyJams_SaveAsPDF", "JellyJams_SaveAsDXF"),
    "jellyjams.orientation": ("JellyJams_ViewOrientation", "JellyJams_NormalTo"),
}

EXPECTED_MENU_TEXTS = {
    "JellyJams_Appearances": "Appearances",
    "JellyJams_Diagnostics": "Diagnostics", "JellyJams_Centerline": "Centerline",
    "JellyJams_MidpointLine": "Midpoint Line", "JellyJams_NewAssembly": "New Assembly",
    "JellyJams_RotateComponent": "Rotate Component", "JellyJams_MakeDrawing": "Make Drawing",
    "JellyJams_SheetProperties": "Sheet Properties", "JellyJams_InsertPicture": "Insert Picture",
    "JellyJams_ProjectedView": "Projected View", "JellyJams_ViewScale": "Scale",
    "JellyJams_SurfaceFinish": "Surface Finish", "JellyJams_WeldSymbol": "Weld Symbol",
    "JellyJams_LineFormat": "Line Format", "JellyJams_Note": "Text",
    "JellyJams_SaveAsPDF": "Save as PDF", "JellyJams_SaveAsDXF": "Export DXF",
    "JellyJams_ViewOrientation": "View Orientation", "JellyJams_NormalTo": "Normal To",
}
EXPECTED_MENU_TEXTS.update({cmd: text for text, cmd in SHEET_SHAPES.items()})

COMMAND_ICONS = {
    "JellyJams_Appearances": "appearances",
    "JellyJams_Diagnostics": "diagnostics", "JellyJams_Centerline": "centerline",
    "JellyJams_MidpointLine": "midpoint_line", "JellyJams_NewAssembly": "new_assembly",
    "JellyJams_RotateComponent": "rotate_component", "JellyJams_MakeDrawing": "make_drawing",
    "JellyJams_SheetProperties": "sheet_properties", "JellyJams_InsertPicture": "insert_picture",
    "JellyJams_ProjectedView": "projected_view", "JellyJams_ViewScale": "view_scale",
    "JellyJams_SurfaceFinish": "surface_finish", "JellyJams_WeldSymbol": "weld_symbol",
    "JellyJams_LineFormat": "line_format", "JellyJams_LineOnSheet": "sheet_line",
    "JellyJams_CornerRectangleOnSheet": "sheet_rectangle", "JellyJams_CircleOnSheet": "sheet_circle",
    "JellyJams_CenterpointArcOnSheet": "sheet_arc", "JellyJams_PolygonOnSheet": "sheet_polygon",
    "JellyJams_Note": "sheet_text", "JellyJams_SaveAsPDF": "export_pdf", "JellyJams_SaveAsDXF": "export_dxf",
    "JellyJams_ViewOrientation": "orientation", "JellyJams_NormalTo": "normal_to",
}
# FreeCAD's CmdType of the commands that declare one: only the two orientation commands, which
# change nothing but the camera and so stay available while a sketch or task dialog is open
COMMAND_CMD_TYPES = {"JellyJams_ViewOrientation": "Alter3DView", "JellyJams_NormalTo": "Alter3DView"}
RELATION_ICONS ={"Collinear": "relation_collinear", "Concentric": "relation_concentric",
                  "Midpoint": "relation_midpoint"}
# Orientation panel buttons for FreeCAD commands that ship no icon (orientation.FALLBACK_ICONS)
ORIENTATION_FALLBACK_ICONS = {"Std_ViewSaveCamera": "view_save", "Std_ViewRestoreCamera": "view_restore"}

PROJECTION_VIEW_LABELS = {
    "Front": "Front View", "Top": "Top View", "Bottom": "Bottom View", "Left": "Left View",
    "Right": "Right View", "Rear": "Back View", "FrontTopLeft": "Isometric View",
    "FrontTopRight": "Isometric View", "FrontBottomLeft": "Isometric View",
    "FrontBottomRight": "Isometric View",
}

PROFILE_FEATURES = (
    "PartDesign_Pad", "PartDesign_Pocket", "PartDesign_Revolution", "PartDesign_Groove",
    "PartDesign_Hole", "PartDesign_AdditivePipe", "PartDesign_SubtractivePipe",
    "PartDesign_AdditiveLoft", "PartDesign_SubtractiveLoft", "PartDesign_AdditiveHelix",
    "PartDesign_SubtractiveHelix",
)
# Profile features that open a new sketch first when there is nothing to use as the profile
SKETCH_FIRST_FEATURES = (
    "PartDesign_Pad", "PartDesign_Pocket", "PartDesign_Revolution", "PartDesign_Groove", "PartDesign_Hole",
)

CONSTANT_VALUES = {
    "SKETCH_DIMENSION_COMMAND": "Sketcher_Dimension",
    "ADDON_NAME": "JellyJams", "WORKBENCH_KEY": WB, "MENU_TEXT": "JellyJams", "MENU_NAME": "JellyJams",
    "WORKBENCH_TOOLTIP": "FreeCAD with a SolidWorks-style interface", "LOG_PREFIX": PREFIX,
    "PARAM_ROOT": P_OWN, "PARAM_RIBBON": P_RIBBON, "PARAM_VIEW": P_VIEW, "PARAM_SHORTCUT": P_SHORTCUT,
    "PARAM_ASSEMBLY": P_ASSEMBLY, "PARAM_PARTDESIGN": P_PARTDESIGN, "PARAM_TECHDRAW_GENERAL": P_TECHDRAW_GENERAL,
    "PARAM_TECHDRAW_REZ": "User parameter:BaseApp/Preferences/Mod/TechDraw/Rez",
    "PARAM_TECHDRAW_FILES": "User parameter:BaseApp/Preferences/Mod/TechDraw/Files",
    "PARAM_DOCUMENT": "User parameter:BaseApp/Preferences/Document",
    "PARAM_GENERAL": "User parameter:BaseApp/Preferences/General",
    "PARAM_SKETCH_SNAP": "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap",
    "KEY_SKETCH_SNAP": "Snap", "KEY_SKETCH_SNAP_OBJECTS": "SnapToObjects",
    "PROP_AUTO_CONSTRAINTS": "Autoconstraints",
    "CLASS_AUTO_SAVER": "Gui::AutoSaver",
    "CLASS_FEATURE_PICK": "PartDesignGui::TaskFeaturePick", "OBJ_FEATURE_PICK_LIST": "listWidget",
    "CLASS_TASK_ATTACHER": "PartGui::TaskAttacher",
    "KEY_QT_FILTER": "SilenceGlyphWarnings", "KEY_CONTEXT_SKETCH": "ShowSketchButtonOnFace",
    "KEY_VIEW_BACKUP": "OriginalViewColors", "KEY_NAV_BACKUP": "OriginalNavigationStyle",
    "KEY_SHORTCUT_BACKUP": "OriginalShortcuts", "KEY_ASSEMBLY_BACKUP": "OriginalSwitchToWB",
    "KEY_PARTDESIGN_BACKUP": "OriginalPartDesignSwitchToWB", "KEY_TECHDRAW_BACKUP": "OriginalTechDrawSwitchToWB",
    "KEY_SKETCH_ASSIST_BACKUP": "OriginalSketchSnapping",
    "KEY_NOTE_HEIGHT": "LastNoteHeight", "KEY_NOTE_UNIT": "LastNoteUnit",
    "BACKUP_KEYS": ("OriginalViewColors", "OriginalNavigationStyle", "OriginalShortcuts", "OriginalSwitchToWB",
                    "OriginalPartDesignSwitchToWB", "OriginalTechDrawSwitchToWB", "OriginalSketchSnapping"),
    "THEME_BEGIN": THEME_BEGIN, "THEME_END": THEME_END,
    "OBJ_PREFIX": "JellyJams", "OBJ_RIBBON": "JellyJamsCommandManager",
    "OBJ_RIBBON_TABS": "JellyJamsCommandManagerTabs", "OBJ_RIBBON_STACK": "JellyJamsToolStack",
    "OBJ_RIBBON_SEPARATOR": "JellyJamsGroupDivider", "OBJ_BTN_PREFIX": "JellyJamsButton-",
    "OBJ_FLY_PREFIX": "JellyJamsFlyout-", "OBJ_TOG_PREFIX": "JellyJamsToggle-",
    "OBJ_PANEL": "JellyJamsPropertyManager", "OBJ_PANEL_TITLE": "JellyJamsPropertyManagerTitle",
    "OBJ_PANEL_HEADING": "JellyJamsSectionCaption", "OBJ_PANEL_LIST": "JellyJamsItemList",
    "OBJ_PANEL_DOCK": "JellyJamsPropertyManagerDock", "OBJ_CONTEXT_TOOLBAR": "JellyJamsContextToolbar",
    "OBJ_LINE_WIDTH_PRESETS": "JellyJamsLineWidthPresets", "OBJ_SHEET_PROPERTIES": "JellyJamsSheetPropertiesForm",
    "OBJ_PICTURE_FORM": "JellyJamsPictureForm", "OBJ_SURFACE_FINISH": "JellyJamsSurfaceFinishForm",
    "OBJ_WELD_SYMBOL": "JellyJamsWeldSymbolForm", "OBJ_DIAGNOSTICS_DIALOG": "JellyJamsDiagnosticsDialog",
    "OBJ_NOTE_DIALOG": "JellyJamsNoteDialog", "OBJ_SCALE_MENU": "JellyJamsViewScaleMenu",
    "OBJ_APPEARANCES": "JellyJamsAppearances",
    "DOCK_TASKS": "Tasks", "TASK_DOCK_CANDIDATES": ("Tasks", "TaskView", "TaskList", "Task"),
    "DOCK_REPORT": "Report view", "MODEL_DOCK_CANDIDATES": ("Model", "Combo View", "Tree view"),
    "KEPT_TOOLBAR_WORDS": ("File", "Edit", "Workbench"), "CLASS_TASK_PANEL": "Gui::TaskView::TaskPanel",
    "CLASS_SHEET_WINDOW": "TechDrawGui::MDIViewPage", "CLASS_VIEW3D": "Gui::View3DInventor",
    "TYPE_SKETCH": "Sketcher::SketchObject", "TYPE_ASSEMBLY": "Assembly::AssemblyObject",
    "TYPE_ASSEMBLY_LINK": "Assembly::AssemblyLink", "TYPE_JOINT_GROUP": "Assembly::JointGroup",
    "TYPE_LINK": "App::Link", "TYPE_PART": "App::Part", "TYPE_BODY": "PartDesign::Body",
    "TYPE_PART_FEATURE": "Part::Feature", "TYPE_GROUP": "App::DocumentObjectGroup",
    "TYPE_PAGE": "TechDraw::DrawPage", "TYPE_TEMPLATE": "TechDraw::DrawSVGTemplate",
    "TYPE_PROJ_GROUP": "TechDraw::DrawProjGroup", "TYPE_PROJ_ITEM": "TechDraw::DrawProjGroupItem",
    "TYPE_VIEW_PART": "TechDraw::DrawViewPart", "TYPE_VIEW_SECTION": "TechDraw::DrawViewSection",
    "TYPE_COMPLEX_SECTION": "TechDraw::DrawComplexSection", "TYPE_VIEW_DETAIL": "TechDraw::DrawViewDetail",
    "TYPE_BROKEN_VIEW": "TechDraw::DrawBrokenView", "TYPE_ANNOTATION": "TechDraw::DrawViewAnnotation",
    "TYPE_SYMBOL": "TechDraw::DrawViewSymbol", "TYPE_IMAGE": "TechDraw::DrawViewImage",
    "TYPE_DIMENSION": "TechDraw::DrawViewDimension", "TYPE_BALLOON": "TechDraw::DrawViewBalloon",
    "TYPE_LEADER": "TechDraw::DrawLeaderLine",
    "CMD_PREFIX": "JellyJams_", "CMD_DIAGNOSTICS": "JellyJams_Diagnostics", "CMD_CENTERLINE": "JellyJams_Centerline",
    "CMD_MIDPOINT_LINE": "JellyJams_MidpointLine", "CMD_NEW_ASSEMBLY": "JellyJams_NewAssembly",
    "CMD_ROTATE_COMPONENT": "JellyJams_RotateComponent", "CMD_MAKE_DRAWING": "JellyJams_MakeDrawing",
    "CMD_SHEET_PROPERTIES": "JellyJams_SheetProperties", "CMD_INSERT_PICTURE": "JellyJams_InsertPicture",
    "CMD_PROJECTED_VIEW": "JellyJams_ProjectedView", "CMD_VIEW_SCALE": "JellyJams_ViewScale",
    "CMD_SURFACE_FINISH": "JellyJams_SurfaceFinish", "CMD_WELD_SYMBOL": "JellyJams_WeldSymbol",
    "CMD_LINE_FORMAT": "JellyJams_LineFormat", "CMD_SHEET_LINE": "JellyJams_LineOnSheet",
    "CMD_SHEET_RECTANGLE": "JellyJams_CornerRectangleOnSheet", "CMD_SHEET_CIRCLE": "JellyJams_CircleOnSheet",
    "CMD_SHEET_ARC": "JellyJams_CenterpointArcOnSheet", "CMD_SHEET_POLYGON": "JellyJams_PolygonOnSheet",
    "CMD_NOTE": "JellyJams_Note", "CMD_SAVE_PDF": "JellyJams_SaveAsPDF", "CMD_SAVE_DXF": "JellyJams_SaveAsDXF",
    "CMD_ORIENTATION": "JellyJams_ViewOrientation", "CMD_NORMAL_TO": "JellyJams_NormalTo",
    "CMD_APPEARANCES": "JellyJams_Appearances",
    "ALL_COMMANDS": tuple(EXPECTED_COMMANDS),
    "WORKBENCH_ICON": "jellyjams", "COMMAND_ICONS": COMMAND_ICONS, "RELATION_ICONS": RELATION_ICONS,
    "PROFILE_FEATURES": PROFILE_FEATURES, "SKETCH_FIRST_FEATURES": SKETCH_FIRST_FEATURES,
    "NEW_SKETCH_COMMAND": "PartDesign_NewSketch", "ACTIVE_BODY_KEY": "pdbody",
    "GUI_COMMAND_MODULES": ("PartGui", "SketcherGui", "PartDesignGui", "TechDrawGui"),
    "OPTIONAL_GUI_COMMAND_MODULES": ("AssemblyGui",),
    "ASSEMBLY_COMMAND_MODULES": ("CommandCreateAssembly", "CommandInsertLink", "CommandInsertNewPart",
                                 "CommandCreateJoint", "CommandSolveAssembly", "CommandCreateView",
                                 "CommandCreateSimulation", "CommandCreateBom"),
    "TAB_FEATURES": "Features", "TAB_SKETCH": "Sketch", "TAB_EVALUATE": "Evaluate",
    "TAB_ASSEMBLY": "Assembly", "TAB_DRAWING": "Drawing",
    "TAB_TITLES": ("Features", "Sketch", "Evaluate", "Assembly", "Drawing"), "START_TAB": "Features",
    "PROP_GROUP": "JellyJams", "PROP_HOST_SHEET": "HostSheet", "PROP_SHOWN_SKETCH": "ShownSketch",
    "PROP_BORDER_INDEX": "BorderLineIndex", "PROP_SHEET_NOTE": "SheetNote", "PROP_CAPTION_FOR": "CaptionFor",
    "PROP_SYMBOL_TYPE": "SymbolType", "PROP_MATERIAL_REMOVAL": "MaterialRemoval",
    "PROP_ALL_AROUND": "AllAroundOutline", "PROP_WELD_SETTINGS": "WeldSettings",
    "PROP_ARROWHEAD_X": "ArrowheadX", "PROP_ARROWHEAD_Y": "ArrowheadY",
    "KIND_SURFACE": "surface", "KIND_WELD": "weld",
    "PROJECTION_VIEW_LABELS": PROJECTION_VIEW_LABELS,
    "RIBBON_REFRESH_MS": 450, "QUIT_PROMPT_POLL_MS": 600, "DIALOG_TERMS_MS": 250,
}

EXPECTED_MODULES = [
    "surface_boolean",
    "local_fillet",
    "surface_geometry", "surface_feature", "surface_rules",
    "measure",
    "appearances", "appearance_rules",
    "constants", "console", "params", "paths", "fcgui", "doc_utils", "commands", "recovery",
    "navigation", "orbit", "orbit_rules", "shortcuts", "lifecycle", "quit_guard", "qt_filter", "diagnostics", "palette",
    "theme", "viewport", "layout", "ribbon", "ribbon_layout", "ribbon_model", "ribbon_text",
    "ribbon_widgets", "icons", "naming", "naming_rules", "dialog_terms", "dialog_terms_data",
    "sketch_edit", "sketch_assist", "sketch_dimension", "edit_guard", "sketch_gesture", "sketch_tools", "context_sketch", "panel_host",
    "relations_rules", "relations_panel", "mate_rules", "mate_panel", "switch_prefs",
    "assembly_drop", "assembly_commands", "drawing_common", "sheet_pick", "templates",
    "make_drawing", "sheet_properties", "sheet_sketch", "sheet_text", "insert_picture",
    "zoom_lines", "projected_view", "view_labels", "view_scale", "sheet_drag", "surface_finish",
    "weld_symbol", "line_format", "drawing_export", "pdf_merge", "orientation",
]

PURE_MODULES = ["__init__", "constants", "palette", "appearance_rules", "surface_rules", "ribbon_layout", "ribbon_model", "ribbon_text",
                "naming_rules", "relations_rules", "mate_rules", "dialog_terms_data", "pdf_merge", "orbit_rules", "access_rules"]
NOT_IN_PURE = {"FreeCAD", "FreeCADGui", "PySide", "PySide2", "PySide6", "shiboken2", "shiboken6"}

API_NAMES = {
    "jellyjams.surface_boolean": ["create", "build", "BooleanFeature", "CUT", "FUSE"],
    "jellyjams.local_fillet": ["create", "build", "LocalFilletTool", "ADD", "REMOVE", "FULL"],
    "jellyjams.surface_geometry": ["encode", "decode", "encode_surface", "decode_surface", "face_from_data"],
    "jellyjams.surface_feature": ["create", "definition_for", "GeometryFeature"],
    "jellyjams.surface_rules": ["pole_grid", "surfaces"],
    "jellyjams.measure": ["start", "stop", "toggle", "is_active", "MeasureTask", "selected_items",
                           "measurement", "single_measurement", "shortest_distance", "callout_image"],
    "jellyjams.appearances": ["get_commands", "targets", "apply_appearance", "enable", "disable",
                              "show", "dock", "suspend_for_quit", "resume_after_cancel"],
    "jellyjams.appearance_rules": ["Appearance", "LIBRARY", "FINISHES", "rgb", "face_index", "material_values"],
    "jellyjams": ["__version__", "MIN_FREECAD_VERSION"],
    "jellyjams.console": ["message", "warning", "error", "log", "traceback_text", "guard", "guarded",
                          "safe_call"],
    "jellyjams.params": ["TYPE_SUFFIXES", "CONTENTS_TYPE_NAMES", "group", "own", "contents", "has_key",
                         "get_value", "set_value", "remove_value", "get_bool", "get_float", "get_string",
                         "backup_pending", "load_backup", "save_backup", "clear_backup"],
    "jellyjams.paths": ["addon_dir", "icons_dir", "icon_path", "is_link", "user_cache_dir"],
    "jellyjams.fcgui": ["qt", "gui", "main_window", "active_workbench_name", "jellyjams_active",
                        "task_dialog_open", "active_gui_document", "object_in_edit", "sketch_in_edit",
                        "find_dock", "task_dock", "task_panel", "mdi_area", "active_mdi_widget",
                        "is_sheet_window", "active_sheet_window", "sheet_graphics_view",
                        "techdraw_tool_running", "rez", "scene_to_sheet", "status_message",
                        "clear_status", "is_alive", "defer", "selection", "selection_ex",
                        "command_exists", "command_info", "run_command", "preload_command_modules"],
    "jellyjams.doc_utils": ["CONTAINER_TYPES", "MODEL_PRIORITY", "is_alive", "type_id", "is_derived",
                            "is_contained", "root_objects", "primary_model_objects", "pages",
                            "parent_page", "add_property", "transaction"],
    "jellyjams.commands": ["PROVIDERS", "BaseCommand", "register_all", "registered_ids"],
    "jellyjams.recovery": ["run_startup_recovery"],
    "jellyjams.navigation": ["install", "uninstall", "recover", "BACKUP_KEY"],
    "jellyjams.shortcuts": ["install", "uninstall", "recover", "BACKUP_KEY", "SHORTCUTS"],
    "jellyjams.lifecycle": ["INIT_HELPERS", "ACTIVATION_STEPS", "DEACTIVATION_STEPS",
                            "QUIT_REVERT_STEPS", "QUIT_REAPPLY_STEPS", "run_steps", "initialize",
                            "activated", "deactivated", "is_active", "revert_for_quit",
                            "reapply_after_cancel"],
    "jellyjams.quit_guard": ["install", "is_installed"],
    "jellyjams.qt_filter": ["GLYPH_PREFIX", "PROBE_TEXT", "_installed", "_enabled", "_previous",
                            "_first_drop_logged", "_probe_seen", "install_and_enable", "disable",
                            "is_installed", "is_enabled", "handle", "format_forward"],
    "jellyjams.diagnostics": ["get_commands", "freecad_version", "qt_binding", "qt_version",
                              "environment_line", "collect_rows", "format_block"],
    "jellyjams.palette": ["WINDOW", "PANEL", "RIBBON_SURFACE", "TAB_STRIP", "BORDER", "TEXT",
                          "TEXT_SECONDARY", "TEXT_DISABLED", "ACCENT", "ACCENT_DARK", "HOVER", "PRESSED",
                          "SELECTION", "TREE_TEXT", "GRADIENT_TOP", "GRADIENT_BOTTOM",
                          "SKETCH_UNDER_DEFINED", "SKETCH_FULLY_DEFINED", "SKETCH_OVER_DEFINED",
                          "SKETCH_CONSTRUCTION", "SKETCH_CONSTRUCTION_DEFINED", "DIM_DRIVING",
                          "DIM_DRIVEN", "RELATION_SYMBOLS", "WIDGET_PALETTE", "VIEWPORT_PALETTE",
                          "TEXT_PAIRS", "NONTEXT_PAIRS", "SKETCH_COLORS", "relative_luminance",
                          "contrast_ratio", "packed_rgba"],
    "jellyjams.theme": ["build_block", "strip_block", "apply", "remove", "is_applied"],
    "jellyjams.viewport": ["MANAGED_KEYS", "apply", "restore", "recover", "is_applied"],
    "jellyjams.layout": ["DEFER_POLL_MS", "DEFER_POLL_LIMIT", "REDOCK_DELAYS_MS", "SECOND_PASS_MS",
                         "_active", "_saved_state", "apply", "revert", "is_applied", "is_deferred",
                         "is_kept_toolbar"],
    "jellyjams.ribbon_layout": ["Cmd", "Flyout", "Toggle", "Stack", "Group", "Tab", "TABS",
                                "all_command_ids"],
    "jellyjams.ribbon_model": ["entry_id", "object_name", "RButton", "RFlyout", "RToggle", "RStack",
                               "RGroup", "RTab", "Resolved", "resolve"],
    "jellyjams.ribbon_text": ["one_line", "tooltip_name", "plain_text", "same_name", "compose_tooltip"],
    "jellyjams.icons": ["jj_icon", "resource_icon", "command_icon"],
    "jellyjams.ribbon": ["show", "hide", "is_requested", "is_built", "show_if_requested",
                         "hide_if_not_requested", "rebuild", "refresh_now", "refresh_measure_button", "dock", "find_button",
                         "tab_titles", "current_tab_title", "context_tabs", "run_entry", "entry_ids",
                         "skipped_ids", "flyout_states", "toggle_states"],
    "jellyjams.naming": ["enable", "disable", "is_enabled", "refresh_drawing"],
    "jellyjams.naming_rules": ["TYPE_BASE_NAMES", "PLANE_NAMES", "FOLDER_NAMES", "MATE_BASES",
                               "STANDARD_3_VIEW", "next_number", "numbered_name", "fixed_name",
                               "standard3_name", "instance_base", "instance_name", "fixed_marker",
                               "mate_base", "default_mate_labels", "mate_label",
                               "is_default_projection_label", "is_default_template_label"],
    "jellyjams.dialog_terms": ["start", "stop", "is_running", "process_once", "process_form",
                               "format_weight"],
    "jellyjams.dialog_terms_data": ["FORMS", "WEIGHT_PRESETS_MM", "WEIGHT_LABEL", "PLACEHOLDER"],
    "jellyjams.sketch_edit": ["install", "uninstall", "is_installed"],
    "jellyjams.sketch_assist": ["enable", "disable", "recover", "SNAP_KEYS"],
    "jellyjams.sketch_dimension": ["run", "stop", "preview_gap"],
    "jellyjams.edit_guard": ["COMMAND_STRING_FILE", "FRAME_SEARCH_DEPTH", "install", "uninstall", "is_installed"],
    "jellyjams.sketch_gesture": ["is_profile_feature", "try_run", "needs_new_sketch", "advance", "PICKING",
                                 "EDITING", "PICK_GRACE_S", "WATCH_MS", "SUBTRACTIVE_FEATURES",
                                 "REFUSED_BY_FREECAD", "NEEDS_SOLID_MS"],
    "jellyjams.sketch_tools": ["get_commands", "stop_running", "running_tool", "mirrored_end"],
    "jellyjams.context_sketch": ["enable", "disable", "opacity_for_distance", "popup_position"],
    "jellyjams.panel_host": ["PanelHost"],
    "jellyjams.relations_rules": ["Entity", "GEOMETRY_KINDS", "RELATION_COMMANDS", "RELATION_CAPABILITIES",
                                  "CONSTRAINT_NAMES", "parse_selection", "accepts", "offered_relations",
                                  "existing_relations", "deletion_order"],
    "jellyjams.relations_panel": ["enable", "disable", "refresh_now"],
    "jellyjams.mate_rules": ["MATE_COMMANDS", "MATE_CAPABILITIES", "kind_from", "removed_freedoms",
                             "offered_mates", "hint"],
    "jellyjams.mate_panel": ["enable", "disable", "refresh_now"],
    "jellyjams.switch_prefs": ["SWITCH_KEY", "TARGETS", "apply", "restore", "recover", "is_applied"],
    "jellyjams.assembly_drop": ["enable", "disable", "is_enabled", "filter_fcstd", "is_portal_path",
                                "target_assembly"],
    "jellyjams.assembly_commands": ["get_commands", "stop_rotate_component", "is_rotating",
                                    "next_assembly_name", "drag_rotation"],
    "jellyjams.drawing_common": ["scale_text", "parse_scale", "has_page", "drawing_tools_enabled",
                                 "page_of_active_window", "target_sheet", "sheet_size", "sheet_center",
                                 "owning_page", "open_sheet_window"],
    "jellyjams.sheet_pick": ["start", "set_status", "cancel", "is_active", "current_owner"],
    "jellyjams.templates": ["templates_dir", "catalog", "display_name", "new_drawing_template",
                            "is_third_angle_variant", "resolve_for_method", "transform_symbol",
                            "derive_third_angle"],
    "jellyjams.make_drawing": ["get_commands", "default_format", "document_name_for",
                               "title_block_values"],
    "jellyjams.sheet_properties": ["get_commands", "FIELD_LABELS", "field_label", "ordered_keys"],
    "jellyjams.sheet_sketch": ["get_commands", "install_watcher", "find_sheet_sketch", "frame_points"],
    "jellyjams.sheet_text": ["get_commands", "split_lines", "mm_to_pt", "pt_to_mm", "ISO_HEIGHTS_MM"],
    "jellyjams.insert_picture": ["get_commands", "svg_natural_size", "bitmap_natural_size",
                                 "initial_scale"],
    "jellyjams.zoom_lines": ["start", "stop", "restore_all", "reduction_step"],
    "jellyjams.projected_view": ["get_commands", "VIEW_DIRECTIONS", "REAR_SLOT", "effective_method",
                                 "click_step", "sheet_slot", "projection_toward", "owning_group",
                                 "placed_offset", "apply_start_layout", "make_groups_movable"],
    "jellyjams.view_labels": ["install", "SECTION_LETTERS", "next_letter", "follows_scheme",
                              "label_text", "tree_label"],
    "jellyjams.view_scale": ["get_commands", "STANDARD_SCALES", "scale_target"],
    "jellyjams.sheet_drag": ["attach", "is_dragging"],
    "jellyjams.surface_finish": ["get_commands", "open_editor", "DEFAULT_DATA", "build_svg",
                                 "parse_rotation"],
    "jellyjams.weld_symbol": ["get_commands", "open_editor", "install_watcher", "DEFAULT_DATA",
                              "merge_data", "build_svg"],
    "jellyjams.line_format": ["get_commands", "has_view_edge"],
    "jellyjams.drawing_export": ["get_commands", "sanitize", "suggested_base", "per_sheet_paths"],
    "jellyjams.pdf_merge": ["UnsupportedPdf", "merge"],
    "jellyjams.orientation": ["OBJ_PANEL", "CMD_TYPE_VIEW", "VIEW_GRID", "AXONOMETRIC", "TOOLS", "FALLBACK_ICONS",
                              "ALIGN_COMMAND", "SKETCH_VIEW_COMMAND", "NORMAL_TO_HINT", "MODEL_TREE_CLASS",
                              "SKETCH_TYPES", "DATUM_TYPES", "SPACE_FOR_PANEL_CLASSES", "OPEN_SETTLE_S", "HINT_MS",
                              "get_commands", "view3d_active", "normal_to_target", "normal_to", "is_open",
                              "toggle", "close", "open_at_cursor", "keeps_space", "install", "uninstall"],
}
API_NAMES["jellyjams.constants"] = sorted(CONSTANT_VALUES)

INIT_HELPERS = [
    ("view_labels", "start lettering section and detail views", "jellyjams.view_labels", "install"),
    ("zoom_lines", "start matching drawing line widths to the zoom level", "jellyjams.zoom_lines", "start"),
    ("weld_watcher", "start keeping weld symbols on their arrows", "jellyjams.weld_symbol", "install_watcher"),
    ("sheet_sketch_watcher", "start watching for edits of sheet sketches", "jellyjams.sheet_sketch",
     "install_watcher"),
]
ACTIVATION_STEPS = [
    ("layout", "set up the window layout", "jellyjams.layout", "apply"),
    ("theme", "add the light theme", "jellyjams.theme", "apply"),
    ("viewport", "set the 3D view background and sketch colors", "jellyjams.viewport", "apply"),
    ("navigation", "turn on the SolidWorks navigation style", "jellyjams.navigation", "install"),
    ("shortcuts", "set the SolidWorks-style keyboard shortcuts", "jellyjams.shortcuts", "install"),
    ("orientation", "let focused buttons and lists keep the Space key", "jellyjams.orientation", "install"),
    ("ribbon", "display the CommandManager ribbon", "jellyjams.ribbon", "show"),
    ("appearances", "display the Appearances tab", "jellyjams.appearances", "enable"),
    ("naming", "turn on FeatureManager-style tree names", "jellyjams.naming", "enable"),
    ("sketch_edit", "keep JellyJams active while a sketch is edited", "jellyjams.sketch_edit", "install"),
    ("sketch_assist", "enable snapping and automatic sketch constraints", "jellyjams.sketch_assist", "enable"),
    ("edit_guard", "keep JellyJams active while a feature is edited", "jellyjams.edit_guard", "install"),
    ("context_sketch", "turn on the Sketch context icon", "jellyjams.context_sketch", "enable"),
    ("relations_panel", "turn on the Add Relations panel", "jellyjams.relations_panel", "enable"),
    ("mate_panel", "turn on the Mate panel", "jellyjams.mate_panel", "enable"),
    ("assembly_drop", "accept files dropped onto an assembly", "jellyjams.assembly_drop", "enable"),
    ("switch_prefs", "stop Assembly, Part Design and TechDraw from switching workbenches",
     "jellyjams.switch_prefs", "apply"),
    ("dialog_terms", "start relabeling FreeCAD dialogs with SolidWorks terms", "jellyjams.dialog_terms",
     "start"),
    ("qt_filter", "set up the Qt message filter", "jellyjams.qt_filter", "install_and_enable"),
    ("quit_guard", "set up the quit guard", "jellyjams.quit_guard", "install"),
]
DEACTIVATION_STEPS = [
    ("appearances", "remove the Appearances tab", "jellyjams.appearances", "disable"),
    ("qt_filter", "turn off the Qt message filter", "jellyjams.qt_filter", "disable"),
    ("dialog_terms", "stop relabeling FreeCAD dialogs", "jellyjams.dialog_terms", "stop"),
    ("assembly_drop", "stop accepting files dropped onto an assembly", "jellyjams.assembly_drop", "disable"),
    ("switch_prefs", "put back the workbench-switch preferences", "jellyjams.switch_prefs", "restore"),
    ("mate_panel", "turn off the Mate panel", "jellyjams.mate_panel", "disable"),
    ("relations_panel", "turn off the Add Relations panel", "jellyjams.relations_panel", "disable"),
    ("context_sketch", "turn off the Sketch context icon", "jellyjams.context_sketch", "disable"),
    ("sheet_pick", "cancel picking a point on the sheet", "jellyjams.sheet_pick", "cancel"),
    ("rotate_component", "stop Rotate Component", "jellyjams.assembly_commands", "stop_rotate_component"),
    ("sketch_tools", "stop a running Centerline or Midpoint Line tool", "jellyjams.sketch_tools",
     "stop_running"),
    ("edit_guard", "let feature editing switch workbenches again", "jellyjams.edit_guard", "uninstall"),
    ("sketch_edit", "let sketch editing switch workbenches again", "jellyjams.sketch_edit", "uninstall"),
    ("sketch_assist", "restore sketch snapping and automatic constraints", "jellyjams.sketch_assist", "disable"),
    ("naming", "pause FeatureManager-style tree names", "jellyjams.naming", "disable"),
    ("orientation", "close the Orientation panel and stop watching the Space key", "jellyjams.orientation",
     "uninstall"),
    ("ribbon", "hide the CommandManager ribbon", "jellyjams.ribbon", "hide"),
    ("shortcuts", "put back the user's keyboard shortcuts", "jellyjams.shortcuts", "uninstall"),
    ("navigation", "put back the user's navigation style", "jellyjams.navigation", "uninstall"),
    ("viewport", "put back the user's 3D view colors", "jellyjams.viewport", "restore"),
    ("theme", "take off the light theme", "jellyjams.theme", "remove"),
    ("layout", "put back the window layout", "jellyjams.layout", "revert"),
]
QUIT_REVERT_STEPS = [
    ("sketch_assist", "jellyjams.sketch_assist", "disable"),
    ("appearances", "jellyjams.appearances", "suspend_for_quit"),
    ("switch_prefs", "jellyjams.switch_prefs", "restore"), ("ribbon", "jellyjams.ribbon", "hide"),
    ("shortcuts", "jellyjams.shortcuts", "uninstall"), ("navigation", "jellyjams.navigation", "uninstall"),
    ("viewport", "jellyjams.viewport", "restore"), ("theme", "jellyjams.theme", "remove"),
    ("layout", "jellyjams.layout", "revert"),
]
QUIT_REAPPLY_STEPS = [
    ("layout", "jellyjams.layout", "apply"), ("theme", "jellyjams.theme", "apply"),
    ("viewport", "jellyjams.viewport", "apply"), ("navigation", "jellyjams.navigation", "install"),
    ("shortcuts", "jellyjams.shortcuts", "install"), ("ribbon", "jellyjams.ribbon", "show"),
    ("appearances", "jellyjams.appearances", "resume_after_cancel"),
    ("switch_prefs", "jellyjams.switch_prefs", "apply"),
    ("sketch_assist", "jellyjams.sketch_assist", "enable"),
]

# ribbon-content: the CommandManager arrangement, every list in ribbon order
RIBBON_PLAIN = {
    "Features": ["PartDesign_Pad", "PartDesign_Revolution", "PartDesign_AdditivePipe",
                 "PartDesign_AdditiveLoft", "PartDesign_AdditiveHelix", "PartDesign_Pocket", "PartDesign_Hole",
                 "PartDesign_Groove", "PartDesign_SubtractivePipe", "PartDesign_SubtractiveLoft",
                 "PartDesign_SubtractiveHelix", "PartDesign_Draft", "PartDesign_Thickness", "PartDesign_Mirrored",
                 "PartDesign_Body", "PartDesign_Boolean", "PartDesign_SubShapeBinder"],
    "Sketch": ["Sketcher_Dimension", "Sketcher_CreateRegularPolygon", "Sketcher_CreatePoint", "Sketcher_Offset",
               "Sketcher_Symmetry", "Sketcher_ToggleConstruction", "Sketcher_ValidateSketch",
               "Sketcher_ViewSketch", "Sketcher_ViewSection"],
    "Evaluate": ["Std_Measure", "Part_CheckGeometry", "Std_ViewFront", "Std_ViewTop", "Std_ViewRight",
                 "Std_ViewRear", "Std_ViewBottom", "Std_ViewLeft", "Std_ViewIsometric", "Std_ViewDimetric",
                 "Std_ViewTrimetric", "JellyJams_NormalTo", "Std_ViewFitAll", "Std_ViewBoxZoom",
                 "Std_DrawStyle#6", "Std_DrawStyle#5", "Std_DrawStyle#3", "Std_DrawStyle#2",
                 "Std_PerspectiveCamera", "Std_OrthographicCamera", "JellyJams_Diagnostics"],
    "Assembly": ["JellyJams_NewAssembly", "JellyJams_MakeDrawing#1", "Assembly_ActivateAssembly", "Assembly_SolveAssembly",
                 "Std_TransformManip", "JellyJams_RotateComponent", "Assembly_ToggleGrounded", "Assembly_CreateSimulation",
                 "Assembly_CreateBom", "Assembly_CreateView"],
    "Drawing": ["JellyJams_MakeDrawing", "JellyJams_SheetProperties", "TechDraw_PageDefault", "JellyJams_InsertPicture",
                "TechDraw_ProjectionGroup", "TechDraw_View", "JellyJams_ProjectedView", "TechDraw_DetailView",
                "TechDraw_BrokenView", "TechDraw_ClipGroup", "JellyJams_ViewScale", "TechDraw_Balloon",
                "JellyJams_SurfaceFinish", "JellyJams_WeldSymbol", "TechDraw_LeaderLine", "TechDraw_SpreadsheetView",
                "JellyJams_LineOnSheet", "JellyJams_CornerRectangleOnSheet", "JellyJams_CircleOnSheet", "JellyJams_CenterpointArcOnSheet",
                "JellyJams_PolygonOnSheet", "JellyJams_LineFormat", "JellyJams_SaveAsPDF", "JellyJams_SaveAsDXF"],
}
RIBBON_FLYOUTS = {
    "PartDesign_Fillet": ["PartDesign_Fillet", "PartDesign_Chamfer"],
    "PartDesign_LinearPattern": ["PartDesign_LinearPattern", "PartDesign_PolarPattern",
                                 "PartDesign_MultiTransform"],
    "Part_DatumPlane": ["Part_DatumPlane", "Part_DatumLine", "Part_CoordinateSystem", "Part_DatumPoint"],
    "Part_ProjectionOnSurface": ["Part_ProjectionOnSurface", "Part_Section"],
    "Sketcher_CreateLine": ["Sketcher_CreateLine", "JellyJams_Centerline", "JellyJams_MidpointLine", "Sketcher_CreatePolyline"],
    "Sketcher_CreateRectangle": ["Sketcher_CreateRectangle", "Sketcher_CreateRectangle_Center",
                                 "Sketcher_CreateOblong"],
    "Sketcher_CreateSlot": ["Sketcher_CreateSlot", "Sketcher_CreateArcSlot"],
    "Sketcher_CreateCircle": ["Sketcher_CreateCircle", "Sketcher_Create3PointCircle"],
    "Sketcher_CreateArc": ["Sketcher_CreateArc", "Sketcher_Create3PointArc"],
    "Sketcher_CreateBSplineByInterpolation": ["Sketcher_CreateBSplineByInterpolation", "Sketcher_CreateBSpline",
                                              "Sketcher_CreatePeriodicBSplineByInterpolation",
                                              "Sketcher_CreatePeriodicBSpline"],
    "Sketcher_CreateEllipseByCenter": ["Sketcher_CreateEllipseByCenter", "Sketcher_CreateArcOfEllipse",
                                       "Sketcher_CreateArcOfParabola", "Sketcher_CreateArcOfHyperbola"],
    "Sketcher_CreateFillet": ["Sketcher_CreateFillet", "Sketcher_CreateChamfer"],
    "Sketcher_Trimming": ["Sketcher_Trimming", "Sketcher_Extend", "Sketcher_Split"],
    "Sketcher_Projection": ["Sketcher_Projection", "Sketcher_Intersection", "Sketcher_CarbonCopy"],
    "Sketcher_Translate": ["Sketcher_Translate", "Sketcher_Rotate", "Sketcher_Scale"],
    "Sketcher_SelectConstraints": ["Sketcher_SelectConstraints", "Sketcher_SelectElementsWithDoFs",
                                   "Sketcher_DeleteAllConstraints"],
    "Std_ToggleClipPlane": ["Std_ToggleClipPlane", "Part_SectionCut"],
    "Assembly_InsertLink": ["Assembly_InsertLink", "Assembly_InsertNewPart"],
    "Assembly_CreateJointDistance": ["Assembly_CreateJointDistance", "Assembly_CreateJointParallel",
                                     "Assembly_CreateJointPerpendicular", "Assembly_CreateJointCylindrical",
                                     "Assembly_CreateJointFixed", "Assembly_CreateJointAngle"],
    "Assembly_CreateJointRevolute": ["Assembly_CreateJointRevolute", "Assembly_CreateJointSlider",
                                     "Assembly_CreateJointBall", "Assembly_CreateJointGears",
                                     "Assembly_CreateJointRackPinion", "Assembly_CreateJointScrew",
                                     "Assembly_CreateJointBelt"],
    "TechDraw_SectionView": ["TechDraw_SectionView", "TechDraw_ComplexSection"],
    "TechDraw_Dimension": ["TechDraw_Dimension", "TechDraw_HorizontalDimension", "TechDraw_VerticalDimension",
                           "TechDraw_ExtensionCreateHorizChainDimension",
                           "TechDraw_ExtensionCreateHorizCoordDimension",
                           "TechDraw_ExtensionCreateHorizChamferDimension"],
    "JellyJams_Note": ["JellyJams_Note", "TechDraw_RichTextAnnotation"],
    "TechDraw_ExtensionCircleCenterLines": ["TechDraw_ExtensionCircleCenterLines", "TechDraw_ExtensionHoleCircle"],
    "TechDraw_FaceCenterLine": ["TechDraw_FaceCenterLine", "TechDraw_2LineCenterLine", "TechDraw_2PointCenterLine"],
    "TechDraw_Hatch": ["TechDraw_Hatch", "TechDraw_GeometricHatch"],
    "TechDraw_ExtensionThreadHoleSide": ["TechDraw_ExtensionThreadHoleSide", "TechDraw_ExtensionThreadHoleBottom",
                                         "TechDraw_ExtensionThreadBoltSide", "TechDraw_ExtensionThreadBoltBottom"],
}
RIBBON_FLYOUT_TITLES = {  # flyouts whose caption stays fixed; every other flyout has none
    "Part_DatumPlane": "Reference\nGeometry", "Part_ProjectionOnSurface": "Curves",
    "Assembly_CreateJointDistance": "Mate", "Assembly_CreateJointRevolute": "Mechanical\nMates",
    "TechDraw_ExtensionThreadHoleSide": "Cosmetic Thread",
}
RIBBON_TAB_COUNTS = {  # plain, flyouts, variants, toggles, separators
    "Features": (17, 4, 11, 0, 3), "Sketch": (9, 12, 35, 1, 3), "Evaluate": (21, 1, 2, 0, 3),
    "Assembly": (10, 3, 15, 0, 3), "Drawing": (24, 7, 21, 0, 4),
}
RIBBON_TOTALS = {"plain": 81, "flyouts": 27, "variants": 84, "toggles": 1, "entry_ids": 167}
RIBBON_TOGGLE = ["PartDesign_NewSketch", "Sketcher_LeaveSketch"]
# layout id -> the id used when FreeCAD lacks it (older builds); these appear only as fallbacks
RIBBON_FALLBACKS = {
    "Sketcher_Projection": "Sketcher_External", "Part_DatumPlane": "PartDesign_Plane",
    "Part_DatumLine": "PartDesign_Line", "Part_CoordinateSystem": "PartDesign_CoordinateSystem",
    "Part_DatumPoint": "PartDesign_Point", "TechDraw_Dimension": "TechDraw_LengthDimension",
    "PartDesign_NewSketch": "Sketcher_NewSketch",
}
# shortcuts.SHORTCUTS, in order: the SolidWorks keys JellyJams sets while it is active
EXPECTED_SHORTCUTS = [
    ("Std_ViewFitAll", "F"), ("Std_ViewZoomOut", "Z"), ("Std_ViewZoomIn", "Shift+Z"), ("Std_Refresh", "Ctrl+B"),
    ("Std_ViewFront", "Ctrl+1"), ("Std_ViewRear", "Ctrl+2"), ("Std_ViewLeft", "Ctrl+3"), ("Std_ViewRight", "Ctrl+4"),
    ("Std_ViewTop", "Ctrl+5"), ("Std_ViewBottom", "Ctrl+6"), ("Std_ViewIsometric", "Ctrl+7"),
    ("JellyJams_NormalTo", "Ctrl+8"), ("JellyJams_ViewOrientation", "Space"),
]
ORIENTATION_CMD = "JellyJams_ViewOrientation"
NORMAL_TO_CMD = "JellyJams_NormalTo"
# FreeCAD's own Normal To; it had Ctrl+8 before JellyJams_NormalTo took the key over
ALIGN_CMD = "Std_AlignToSelection"
# The JellyJams commands among them, registered by JellyJams itself
JJ_SHORTCUT_COMMANDS = [NORMAL_TO_CMD, ORIENTATION_CMD]
# The FreeCAD commands among them
SHORTCUT_COMMANDS = [cmd for cmd, _keys in EXPECTED_SHORTCUTS if cmd not in JJ_SHORTCUT_COMMANDS]
# FreeCAD 1.1 commands that own one of those keys by default: unbound while JellyJams is active
DEFAULT_KEY_OWNERS = {"Std_ViewBoxZoom": "Ctrl+B", "Std_ToggleVisibility": "Space"}


def ribbon_command_ids():
    """FreeCAD 1.1.4 command set for the ribbon: every primary layout command. The
    fallback-only ids of RIBBON_FALLBACKS (older FreeCAD builds) are not part of it."""
    ids = set(RIBBON_TOGGLE)
    for tab_ids in RIBBON_PLAIN.values():
        ids.update(entry.split("#")[0] for entry in tab_ids)
    for variants in RIBBON_FLYOUTS.values():
        ids.update(variants)
    return ids


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def param(path):
    return STUBS.app.ParamGet(path)


def has_param(path, suffix, name):
    return name in getattr(param(path), "Get%ss" % suffix)()


def norm_path(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def flat_text(text):
    return " ".join(str(text).split())


def strings_in(value):
    """Every string inside a (nested) constant value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings_in(key)
            yield from strings_in(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from strings_in(item)


def fake_module(name, **attributes):
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module


@contextlib.contextmanager
def fake_modules(modules):
    """Temporarily replace modules (sys.modules entry and parent package
    attribute) so lazy imports inside the code under test get the fakes."""
    saved = []
    for name, module in modules.items():
        parent_name, _, short = name.rpartition(".")
        parent = None
        if parent_name:
            parent = sys.modules.get(parent_name)
            if parent is None and parent_name == "jellyjams":
                parent = importlib.import_module("jellyjams")
        old_attr = getattr(parent, short, _MISSING) if parent is not None else _MISSING
        saved.append((name, sys.modules.get(name, _MISSING), parent, short, old_attr))
        sys.modules[name] = module
        if parent is not None:
            setattr(parent, short, module)
    try:
        yield
    finally:
        for name, old_module, parent, short, old_attr in reversed(saved):
            if old_module is _MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
            if parent is not None:
                if old_attr is _MISSING:
                    with contextlib.suppress(AttributeError):
                        delattr(parent, short)
                else:
                    setattr(parent, short, old_attr)


def try_import(name):
    """(module, None) or (None, traceback text)."""
    try:
        return importlib.import_module(name), None
    except BaseException as exc:  # noqa: BLE001 - a broken module must not stop the run
        if isinstance(exc, KeyboardInterrupt):
            raise
        return None, traceback.format_exc()


def imported_roots(path):
    """Top-level module names a source file imports anywhere (also lazily)."""
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in ("__import__", "import_module") and isinstance(node.args[0].value, str):
                roots.add(node.args[0].value.split(".")[0])
    return roots


MODULE_DUNDERS = {"__name__", "__file__", "__doc__", "__path__", "__spec__", "__loader__",
                  "__package__", "__dict__"}


def top_level_names(tree):
    """Names a parsed module defines at its top level: functions, classes, assigned and
    imported names, also inside top-level if/try/for/with blocks, plus `global` names."""
    names = set(MODULE_DUNDERS)

    def collect(statements):
        for node in statements:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    names.update(sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
            elif isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                if isinstance(node, ast.For):
                    names.update(sub.id for sub in ast.walk(node.target) if isinstance(sub, ast.Name))
                collect(node.body)
                collect(getattr(node, "orelse", []))
                collect(getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    collect(handler.body)

    collect(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            names.update(node.names)
    return names


def unresolved_package_references(repo):
    """`module.name` uses and `from jellyjams.module import name` imports in jellyjams/*.py and
    InitGui.py whose name the JellyJams module does not define at its top level, as
    "file:line module.name". `module` is bound by `from jellyjams import module [as alias]`,
    `import jellyjams.module as alias` or `import jellyjams` (then `jellyjams.module.name`)."""
    package = os.path.join(repo, "jellyjams")
    sources = []
    for name in sorted(os.listdir(package)):
        if name.endswith(".py"):
            sources.append((name[:-3], os.path.join(package, name)))
    sources.append((None, os.path.join(repo, "InitGui.py")))
    trees = {}
    for module, path in sources:
        with open(path, encoding="utf-8") as handle:
            trees[path] = (module, ast.parse(handle.read(), path))
    defined = {module: top_level_names(tree) for module, tree in trees.values() if module}
    problems = []
    for path, (_module, tree) in trees.items():
        relpath = os.path.relpath(path, repo).replace("\\", "/")

        def report(node, text):
            problems.append((relpath, node.lineno, text))

        aliases = {}  # local name -> JellyJams module ("__init__" for the package itself)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                parts = node.module.split(".")
                if parts[0] != "jellyjams":
                    continue
                if len(parts) == 1:
                    for alias in node.names:
                        if alias.name in defined and alias.name != "__init__":
                            aliases[alias.asname or alias.name] = alias.name
                        elif alias.name != "*" and alias.name not in defined["__init__"]:
                            report(node, "from jellyjams import %s" % alias.name)
                elif parts[1] not in defined:
                    report(node, "from %s (no such module)" % node.module)
                else:
                    for alias in node.names:
                        if alias.name != "*" and alias.name not in defined[parts[1]]:
                            report(node, "from %s import %s" % (node.module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if parts[0] != "jellyjams":
                        continue
                    if alias.asname:
                        aliases[alias.asname] = parts[1] if len(parts) > 1 else "__init__"
                    else:
                        aliases["jellyjams"] = "__init__"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            if isinstance(value, ast.Name) and value.id in aliases:
                module = aliases[value.id]
                if module == "__init__" and node.attr in defined:
                    continue  # jellyjams.<module>, checked one level up
                if module in defined and node.attr not in defined[module]:
                    report(node, "%s.%s" % (value.id, node.attr))
            elif (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                  and aliases.get(value.value.id) == "__init__" and value.attr in defined
                  and value.attr != "__init__"):
                if node.attr not in defined[value.attr]:
                    report(node, "%s.%s.%s" % (value.value.id, value.attr, node.attr))
    return ["%s:%d %s" % problem for problem in sorted(set(problems))]


def point_xy(point):
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y)
    values = list(point)
    return float(values[0]), float(values[1])


class FakeContext:
    """Stand-in for QMessageLogContext."""

    def __init__(self, category="default"):
        self.category = category
        self.file = ""
        self.line = 0
        self.function = ""


class HarnessCase(unittest.TestCase):
    """Base class: fresh stub state for every test, helpers for patching."""

    maxDiff = None

    def setUp(self):
        STUBS.reset()

    def tearDown(self):
        STUBS.active_dialog = None

    # imports -----------------------------------------------------------------
    def module(self, name, fresh=False):
        try:
            if fresh and name in sys.modules:
                return importlib.reload(sys.modules[name])
            return importlib.import_module(name)
        except BaseException as exc:  # noqa: BLE001
            if isinstance(exc, KeyboardInterrupt):
                raise
            self.fail("cannot import %s:\n%s" % (name, traceback.format_exc()))

    # patching ----------------------------------------------------------------------
    def patch(self, obj, name, value):
        try:
            namespace = vars(obj)
            had = name in namespace
            old = namespace.get(name)
        except TypeError:
            had, old = hasattr(obj, name), getattr(obj, name, None)
        setattr(obj, name, value)

        def undo():
            if had:
                setattr(obj, name, old)
            else:
                with contextlib.suppress(AttributeError):
                    delattr(obj, name)

        self.addCleanup(undo)

    def fakes(self, modules):
        stack = contextlib.ExitStack()
        stack.enter_context(fake_modules(modules))
        self.addCleanup(stack.close)

    def tmpdir(self):
        path = tempfile.mkdtemp(prefix="jj_headless_")
        self.addCleanup(shutil.rmtree, path, True)
        return path

    # console -------------------------------------------------------------------------
    def lines(self, level=None):
        return STUBS.console_lines(level)

    def jj(self, level=None):
        """Console lines printed by JellyJams (prefixed) at one level."""
        return [text for text in self.lines(level) if text.startswith(PREFIX)]

    def assertNoJellyJamsProblems(self):
        self.assertEqual(self.jj("warning") + self.jj("error"), [],
                         "unexpected JellyJams warnings/errors")

    def assertAllPrefixed(self):
        unprefixed = [text for text in self.lines() if not text.startswith(PREFIX)]
        self.assertEqual(unprefixed, [], "console output without the 'JellyJams: ' prefix")


def make_recorder(calls, tag, result=None, error=None):
    def recorder(*args, **kwargs):
        calls.append((tag, args, kwargs))
        if error is not None:
            raise error
        return result
    return recorder


# ==========================================================================
# 1. Release metadata
# ==========================================================================


class Test01ReleaseMetadata(HarnessCase):
    NS = "https://wiki.freecad.org/Package_Metadata"

    def q(self, tag):
        return "{%s}%s" % (self.NS, tag)

    def package(self):
        path = os.path.join(REPO, "package.xml")
        self.assertTrue(os.path.isfile(path), "package.xml is missing")
        try:
            return ET.parse(path).getroot()
        except ET.ParseError as exc:
            self.fail("package.xml does not parse: %s" % exc)

    def text(self, root, tag):
        element = root.find(self.q(tag))
        self.assertIsNotNone(element, "<%s> missing in package.xml" % tag)
        return (element.text or "").strip()

    def test_root_format_namespace_and_name(self):
        root = self.package()
        self.assertEqual(root.tag, self.q("package"))
        self.assertEqual(root.get("format"), "1")
        self.assertEqual(self.text(root, "name"), "JellyJams")

    def test_version_date_and_freecadmin(self):
        jellyjams = self.module("jellyjams")
        root = self.package()
        self.assertRegex(jellyjams.__version__, r"^\d+\.\d+\.\d+$")
        self.assertEqual(self.text(root, "version"), jellyjams.__version__)
        date = self.text(root, "date")
        self.assertRegex(date, r"^\d{4}-\d{2}-\d{2}$")
        datetime.date.fromisoformat(date)
        self.assertEqual(tuple(jellyjams.MIN_FREECAD_VERSION), (1, 1))
        freecadmin = self.text(root, "freecadmin")
        self.assertTrue(freecadmin.startswith("%d.%d" % tuple(jellyjams.MIN_FREECAD_VERSION)), freecadmin)
        self.assertEqual(freecadmin, "1.1.0")

    def test_repository_url_and_maintainer(self):
        root = self.package()
        urls = root.findall(self.q("url"))
        repository = [url for url in urls if url.get("type") == "repository"]
        self.assertEqual(len(repository), 1)
        self.assertEqual(repository[0].get("branch"), "main")
        self.assertEqual((repository[0].text or "").strip(), "https://github.com/jus-kim/JellyJams")
        for url in urls:
            if url.get("type") == "readme":
                self.assertIn("/blob/main/", url.text or "")
        maintainer = root.find(self.q("maintainer"))
        self.assertIsNotNone(maintainer)
        self.assertEqual(maintainer.get("email"), "hi@jus.kim")
        self.assertEqual((maintainer.text or "").strip(), "jus-kim")

    def test_licenses_exist(self):
        root = self.package()
        licenses = root.findall(self.q("license"))
        self.assertTrue(licenses, "no <license>")
        for element in licenses:
            self.assertRegex((element.text or "").strip(), r"^[A-Za-z0-9.+-]+$")
            self.assertTrue(element.get("file"), "license without file attribute")
            self.assertTrue(os.path.isfile(os.path.join(REPO, element.get("file"))), element.get("file"))
        self.assertEqual([((element.text or "").strip(), element.get("file"))
                          for element in licenses], [("MIT", "LICENSE")])
        with open(os.path.join(REPO, "LICENSE"), encoding="utf-8") as handle:
            license_text = handle.read()
        with open(os.path.join(REPO, "LICENSES", "MIT.txt"), encoding="utf-8") as handle:
            self.assertEqual(license_text, handle.read())
        for required in ("MIT License", "Copyright (c) 2026 jus-kim",
                         "Permission is hereby granted, free of charge",
                         "copyright notice and this permission notice",
                         'THE SOFTWARE IS PROVIDED "AS IS"'):
            self.assertIn(required, license_text)

    def test_content_workbench(self):
        root = self.package()
        workbenches = root.findall("%s/%s" % (self.q("content"), self.q("workbench")))
        self.assertEqual(len(workbenches), 1)
        workbench = workbenches[0]
        self.assertEqual(self.text(workbench, "classname"), WB)
        self.assertEqual(self.text(workbench, "subdirectory"), "./")
        self.assertEqual(self.text(workbench, "name"), "JellyJams")
        self.assertIn("solidworks", self.text(workbench, "description").lower())

    def test_icon_paths_exist(self):
        root = self.package()
        icons = [element for element in root.iter() if element.tag == self.q("icon")]
        self.assertGreaterEqual(len(icons), 2)
        for element in icons:
            relative = (element.text or "").strip()
            self.assertEqual(relative, "resources/icons/jellyjams.svg")
            self.assertTrue(os.path.isfile(os.path.join(REPO, relative)), relative)

    def test_tags(self):
        tags = {(element.text or "").strip() for element in self.package().iter(self.q("tag"))}
        self.assertTrue({"ribbon", "ui", "theme", "solidworks-style", "commandmanager"} <= tags, tags)

    def test_trademark_note_in_description_and_readme(self):
        note = "not affiliated with or endorsed by dassault syst\u00e8mes"
        description = flat_text(self.text(self.package(), "description")).casefold()
        self.assertIn(note, description)
        with open(os.path.join(REPO, "README.md"), encoding="utf-8") as handle:
            self.assertIn(note, flat_text(handle.read()).casefold())

    def test_changelog_heading(self):
        root = self.package()
        version, date = self.text(root, "version"), self.text(root, "date")
        with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as handle:
            changelog = handle.read()
        pattern = r"^## %s (%s|-) %s\s*$" % (re.escape(version), EM_DASH, re.escape(date))
        self.assertRegex(changelog, re.compile(pattern, re.MULTILINE))

    def test_initgui_class_menu_text_and_registration(self):
        path = os.path.join(REPO, "InitGui.py")
        self.assertTrue(os.path.isfile(path), "InitGui.py is missing")
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn(WB, classes)
        attributes = {}
        for node in classes[WB].body:
            if isinstance(node, ast.Assign):
                self.assertIsInstance(node.value, ast.Constant,
                                      "class bodies may contain only literals (InitGui is exec'd)")
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        attributes[target.id] = node.value.value
        workbench_name = self.text(self.package().find(self.q("content")).find(self.q("workbench")), "name")
        self.assertEqual(attributes.get("MenuText"), workbench_name)
        self.assertIn("solidworks", str(attributes.get("ToolTip", "")).lower())
        constants = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)]
        self.assertIn(WB, constants, "the registration key must be checked against listWorkbenches()")
        self.assertIn("Gui::PythonWorkbench", constants)
        registrations = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "addWorkbench"
        ]
        self.assertTrue(registrations, "no addWorkbench(...) call")
        self.assertTrue(any(
            isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == WB
            for call in registrations for arg in call.args
        ), "addWorkbench must register a JellyJamsWorkbench instance")


# ==========================================================================
# 2. Hygiene
# ==========================================================================


class Test02Hygiene(HarnessCase):
    def source_files(self):
        files = []
        if os.path.isdir(PACKAGE_DIR):
            for base, dirs, names in os.walk(PACKAGE_DIR):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                files.extend(os.path.join(base, name) for name in names if name.endswith(".py"))
        files.extend(os.path.join(TESTS_DIR, name) for name in os.listdir(TESTS_DIR) if name.endswith(".py"))
        files.extend(os.path.join(REPO, name) for name in ("InitGui.py", "Init.py"))
        return sorted(files)

    def test_three_line_header(self):
        self.assertTrue(os.path.isdir(PACKAGE_DIR), "jellyjams/ package is missing")
        bad = []
        for path in self.source_files():
            if not os.path.isfile(path):
                bad.append("%s (missing)" % os.path.relpath(path, REPO))
                continue
            with open(path, "rb") as handle:
                head = handle.read(512)
            if head.startswith(codecs.BOM_UTF8):
                bad.append("%s (BOM)" % os.path.relpath(path, REPO))
                continue
            if head.decode("utf-8", "replace").splitlines()[:3] != HEADER:
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(bad, [], "files without the three-line header")

    def test_no_solidworks_in_file_names(self):
        offenders = []
        for base, dirs, names in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "scratch")]
            offenders.extend(os.path.join(base, name) for name in names + dirs if "solidworks" in name.lower())
        self.assertEqual(offenders, [])

    def test_no_solidworks_in_identifiers(self):
        constants = self.module("jellyjams.constants")
        commands = self.module("jellyjams.commands")
        offenders = []
        identifier_names = [
            name for name in dir(constants)
            if name.startswith(("OBJ_", "CMD_", "KEY_", "PARAM_", "PROP_", "TYPE_", "KIND_"))
            or name in ("WORKBENCH_KEY", "ALL_COMMANDS", "COMMAND_ICONS", "RELATION_ICONS",
                        "WORKBENCH_ICON", "BACKUP_KEYS")
        ]
        for name in identifier_names:
            offenders.extend("%s: %s" % (name, value) for value in strings_in(getattr(constants, name))
                             if "solidworks" in value.lower())
        for module_name, ids in dict(commands.PROVIDERS).items():
            offenders.extend("%s: %s" % (module_name, value) for value in strings_in(ids)
                             if "solidworks" in value.lower())
        self.assertEqual(offenders, [])

    def test_constant_values(self):
        constants = self.module("jellyjams.constants")
        wrong = []
        for name, expected in CONSTANT_VALUES.items():
            actual = getattr(constants, name, _MISSING)
            if actual is _MISSING:
                wrong.append("%s missing" % name)
                continue
            if isinstance(expected, tuple):
                actual = tuple(actual)
            elif isinstance(expected, dict):
                actual = dict(actual)
            if actual != expected:
                wrong.append("%s = %r (expected %r)" % (name, actual, expected))
        self.assertEqual(wrong, [])

    def test_init_py_is_headless(self):
        path = os.path.join(REPO, "Init.py")
        self.assertTrue(os.path.isfile(path), "Init.py is missing")
        forbidden = imported_roots(path) & {"FreeCADGui", "PySide", "PySide2", "PySide6", "shiboken6",
                                            "jellyjams"}
        self.assertEqual(forbidden, set())

    def test_pure_modules_import_no_freecad_or_qt(self):
        offenders = {}
        for name in PURE_MODULES:
            path = os.path.join(PACKAGE_DIR, name + ".py")
            if not os.path.isfile(path):
                offenders[name] = "missing"
                continue
            bad = imported_roots(path) & NOT_IN_PURE
            if bad:
                offenders[name] = sorted(bad)
        self.assertEqual(offenders, {})

    def test_pure_modules_run_in_plain_python(self):
        script = (
            "import importlib, sys\n"
            "BLOCKED = %r\n"
            "class Blocker:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name.split('.')[0] in BLOCKED:\n"
            "            raise ImportError('not available in a plain interpreter: ' + name)\n"
            "        return None\n"
            "sys.meta_path.insert(0, Blocker())\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "failed = []\n"
            "for name in sys.argv[2:]:\n"
            "    try:\n"
            "        importlib.import_module(name)\n"
            "    except BaseException as exc:\n"
            "        failed.append('%%s: %%s: %%s' %% (name, type(exc).__name__, exc))\n"
            "print('\\n'.join(failed))\n"
            "sys.exit(1 if failed else 0)\n"
        ) % (sorted(NOT_IN_PURE),)
        names = ["jellyjams" if name == "__init__" else "jellyjams." + name for name in PURE_MODULES]
        process = subprocess.run([sys.executable, "-I", "-c", script, REPO] + names,
                                 capture_output=True, text=True, timeout=120)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_cross_module_references_resolve(self):
        """Every `module.name` between JellyJams modules, and every `from jellyjams.module
        import name`, names something that module defines at its top level. Lazy uses inside
        functions are found too, before they fail at run time with an AttributeError."""
        self.assertEqual(unresolved_package_references(REPO), [],
                         "references to names the JellyJams module does not define")


def _make_import_test(module_name):
    def test(self):
        self.module(module_name)
    test.__doc__ = "%s imports under the stubs" % module_name
    return test


def _make_api_test(module_name, names):
    def test(self):
        module = self.module(module_name)
        missing = [name for name in names if not hasattr(module, name)]
        self.assertEqual(missing, [], "public names missing in %s" % module_name)
    test.__doc__ = "%s defines its documented public names" % module_name
    return test


def _modules_on_disk():
    if not os.path.isdir(PACKAGE_DIR):
        return []
    return [name[:-3] for name in os.listdir(PACKAGE_DIR) if name.endswith(".py") and name != "__init__.py"]


for _name in sorted(set(EXPECTED_MODULES) | set(_modules_on_disk())):
    # An API test already imports its module before checking the public names.
    # Keep import-only tests for modules without an API contract, including new files.
    if "jellyjams." + _name not in API_NAMES:
        setattr(Test02Hygiene, "test_import_%s" % _name, _make_import_test("jellyjams." + _name))
if "jellyjams" not in API_NAMES:
    setattr(Test02Hygiene, "test_import___package__", _make_import_test("jellyjams"))
for _module_name, _names in API_NAMES.items():
    setattr(Test02Hygiene, "test_api_%s" % _module_name.replace(".", "_"), _make_api_test(_module_name, _names))


# ==========================================================================
# 3. InitGui
# ==========================================================================


class Test03InitGui(HarnessCase):
    def exec_initgui(self):
        path = os.path.join(REPO, "InitGui.py")
        self.assertTrue(os.path.isfile(path), "InitGui.py is missing")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        code = compile(source, path, "exec")
        # FreeCAD exec()s InitGui.py inside a function: separate globals and locals,
        # no __file__, so top-level names are invisible to methods.
        exec_globals = {"__builtins__": builtins, "__name__": "FreeCADGuiInit", "FreeCAD": STUBS.app,
                        "FreeCADGui": STUBS.gui, "App": STUBS.app, "Gui": STUBS.gui,
                        "Workbench": STUBS.gui.Workbench}
        exec_locals = {}
        exec(code, exec_globals, exec_locals)  # noqa: S102 - this is how FreeCAD loads it
        return exec_locals

    def seed_navigation_leftover(self):
        param(P_OWN).SetString("OriginalNavigationStyle", json.dumps({"existed": False, "value": None}))
        param(P_VIEW).SetString("NavigationStyle", SW_NAV)

    def assertRecoveryRan(self):
        self.assertNotIn("NavigationStyle", param(P_VIEW).GetStrings())
        self.assertEqual(param(P_OWN).GetString("OriginalNavigationStyle", ""), "")

    def test_first_exec_registers_once_with_path_and_icon(self):
        self.seed_navigation_leftover()
        self.exec_initgui()
        workbenches = STUBS.gui.listWorkbenches()
        self.assertEqual(list(workbenches), [WB])
        workbench = workbenches[WB]
        self.assertEqual(workbench.GetClassName(), "Gui::PythonWorkbench")
        self.assertEqual(type(workbench).MenuText, "JellyJams")
        self.assertIn("solidworks", type(workbench).ToolTip.lower())
        icon = type(workbench).Icon
        self.assertTrue(icon and os.path.isfile(icon), icon)
        self.assertEqual(norm_path(icon), norm_path(os.path.join(ICONS_DIR, "jellyjams.svg")))
        repo = REPO.replace("\\", "/").rstrip("/").lower()
        self.assertTrue(any(repo in line.replace("\\", "/").lower() for line in self.jj("message")),
                        "no registration message naming %s: %r" % (REPO, self.lines()))
        self.assertNoJellyJamsProblems()
        self.assertRecoveryRan()

    def test_second_exec_warns_once_and_keeps_one_entry(self):
        self.exec_initgui()
        first = STUBS.gui.listWorkbenches()[WB]
        STUBS.records.clear()
        self.exec_initgui()
        self.assertEqual(list(STUBS.gui.listWorkbenches()), [WB])
        self.assertIs(STUBS.gui.listWorkbenches()[WB], first)
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(self.jj("error"), [])

    def test_raising_add_workbench_reports_error_and_recovery_still_runs(self):
        def refuse(_workbench):
            raise RuntimeError("addWorkbench refused by the harness")

        self.patch(STUBS.gui, "addWorkbench", refuse)
        self.seed_navigation_leftover()
        self.exec_initgui()
        self.assertEqual(len(self.jj("error")), 1, self.lines())
        self.assertRecoveryRan()

    def test_workbench_methods_delegate_to_lifecycle_and_never_raise(self):
        calls = []
        lifecycle = fake_module(
            "jellyjams.lifecycle",
            initialize=make_recorder(calls, "initialize"),
            activated=make_recorder(calls, "activated"),
            deactivated=make_recorder(calls, "deactivated"),
        )
        self.exec_initgui()
        workbench = STUBS.gui.listWorkbenches()[WB]
        with fake_modules({"jellyjams.lifecycle": lifecycle}):
            workbench.Initialize()
            workbench.Activated()
            workbench.Deactivated()
        self.assertEqual([call[0] for call in calls], ["initialize", "activated", "deactivated"])
        self.assertIs(calls[0][1][0], workbench)

        broken = fake_module(
            "jellyjams.lifecycle",
            initialize=make_recorder([], "initialize", error=RuntimeError("init boom")),
            activated=make_recorder([], "activated", error=RuntimeError("act boom")),
            deactivated=make_recorder([], "deactivated", error=RuntimeError("deact boom")),
        )
        STUBS.records.clear()
        with fake_modules({"jellyjams.lifecycle": broken}):
            workbench.Initialize()
            workbench.Activated()
            workbench.Deactivated()
        self.assertEqual(len(self.jj("error")), 3, self.lines())


# ==========================================================================
# 4. Startup recovery
# ==========================================================================


class Test04Recovery(HarnessCase):
    def setUp(self):
        super().setUp()
        self.module("jellyjams.navigation", fresh=True)
        self.module("jellyjams.shortcuts", fresh=True)
        self.recovery = self.module("jellyjams.recovery")

    def seed_010_leftovers(self):
        own, view, shortcut = param(P_OWN), param(P_VIEW), param(P_SHORTCUT)
        own.SetString("OriginalNavigationStyle", '{"existed": false, "value": null}')
        view.SetString("NavigationStyle", SW_NAV)
        own.SetString("OriginalShortcuts", '{"Std_ViewTop": [false, null], "Std_ViewFront": [true, "1"]}')
        shortcut.SetString("Std_ViewTop", "Ctrl+5")
        shortcut.SetString("Std_ViewFront", "Ctrl+1")
        own.SetString("OriginalViewColors", '{"Gradient": ["Bool", false, null]}')
        view.SetBool("Gradient", True)

    def assertBackupCleared(self, key):
        self.assertEqual(param(P_OWN).GetString(key, ""), "", key)

    def test_clean_start_prints_nothing(self):
        self.recovery.run_startup_recovery()
        self.assertEqual(self.lines(), [])

    def test_010_leftovers_restored_exactly(self):
        self.seed_010_leftovers()
        self.recovery.run_startup_recovery()
        self.assertNotIn("NavigationStyle", param(P_VIEW).GetStrings())
        self.assertNotIn("Gradient", param(P_VIEW).GetBools())
        self.assertNotIn("Std_ViewTop", param(P_SHORTCUT).GetStrings())
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFront"), "1")
        for key in ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors"):
            self.assertBackupCleared(key)
        for key in ("OriginalNavigationStyle", "OriginalShortcuts"):
            self.assertNotIn(key, param(P_OWN).GetStrings(), "a restored backup is removed, not emptied")
        messages = " ".join(self.jj("message")).lower()
        for words in ("3d background", "unclean exit", "navigation style", "shortcuts"):
            self.assertIn(words, messages)
        self.assertNoJellyJamsProblems()
        self.assertAllPrefixed()

    def test_corrupt_navigation_backup_warns_once_and_is_discarded(self):
        self.seed_010_leftovers()
        param(P_OWN).SetString("OriginalNavigationStyle", "{not json")
        self.recovery.run_startup_recovery()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertBackupCleared("OriginalNavigationStyle")
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
        self.assertNotIn("Std_ViewTop", param(P_SHORTCUT).GetStrings())
        self.assertNotIn("Gradient", param(P_VIEW).GetBools())
        STUBS.records.clear()
        self.recovery.run_startup_recovery()
        self.assertEqual(self.lines(), [])

    def test_wrong_backup_structures_are_discarded(self):
        cases = [
            ("OriginalNavigationStyle", '["existed", false]'),
            ("OriginalNavigationStyle", '{"value": "Gui::BlenderNavigationStyle"}'),
            ("OriginalShortcuts", '{"Std_ViewTop": "Ctrl+5"}'),
            ("OriginalShortcuts", '{"Std_ViewTop": ["yes", "Ctrl+5"]}'),
        ]
        for key, raw in cases:
            with self.subTest(key=key, raw=raw):
                STUBS.reset()
                param(P_SHORTCUT).SetString("Std_ViewTop", "T")
                param(P_OWN).SetString(key, raw)
                self.recovery.run_startup_recovery()
                self.assertEqual(len(self.jj("warning")), 1, self.lines())
                self.assertBackupCleared(key)
                self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewTop"), "T")

    def test_assembly_switch_to_wb_backup(self):
        cases = [("1", True), ("0", False), ("absent", None)]
        for record, expected in cases:
            with self.subTest(record=record):
                STUBS.reset()
                param(P_ASSEMBLY).SetBool("SwitchToWB", False)
                param(P_OWN).SetString("OriginalSwitchToWB", record)
                self.recovery.run_startup_recovery()
                if expected is None:
                    self.assertNotIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
                else:
                    self.assertIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
                    self.assertEqual(param(P_ASSEMBLY).GetBool("SwitchToWB", not expected), expected)
                self.assertNotIn("OriginalSwitchToWB", param(P_OWN).GetStrings())
                self.assertTrue(any("assembly" in line.lower() for line in self.jj("message")), self.lines())
                self.assertNoJellyJamsProblems()

    def test_every_switch_to_wb_backup(self):
        names = {P_ASSEMBLY: "assembly", P_PARTDESIGN: "part design", P_TECHDRAW_GENERAL: "techdraw"}
        for group, key in SWITCH_BACKUPS.items():
            for record, expected in (("1", True), ("0", False), ("absent", None)):
                with self.subTest(group=group, record=record):
                    STUBS.reset()
                    for other in SWITCH_BACKUPS:
                        param(other).SetBool("SwitchToWB", False)
                    param(P_OWN).SetString(key, record)
                    self.recovery.run_startup_recovery()
                    if expected is None:
                        self.assertNotIn("SwitchToWB", param(group).GetBools())
                    else:
                        self.assertIn("SwitchToWB", param(group).GetBools())
                        self.assertEqual(param(group).GetBool("SwitchToWB", not expected), expected)
                    self.assertNotIn(key, param(P_OWN).GetStrings())
                    for other in SWITCH_BACKUPS:
                        if other != group:   # no backup pending: left exactly as it was
                            self.assertFalse(param(other).GetBool("SwitchToWB", True), other)
                    messages = self.jj("message")
                    self.assertEqual(len(messages), 1, self.lines())
                    self.assertIn(names[group], messages[0].lower())
                    self.assertNoJellyJamsProblems()

    def test_some_switch_to_wb_backups(self):
        param(P_ASSEMBLY).SetBool("SwitchToWB", False)
        param(P_PARTDESIGN).SetBool("SwitchToWB", False)
        param(P_TECHDRAW_GENERAL).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalPartDesignSwitchToWB", "absent")
        param(P_OWN).SetString("OriginalTechDrawSwitchToWB", "1")
        self.recovery.run_startup_recovery()
        self.assertNotIn("SwitchToWB", param(P_PARTDESIGN).GetBools())
        self.assertTrue(param(P_TECHDRAW_GENERAL).GetBool("SwitchToWB", False))
        self.assertIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True), "no Assembly backup: left alone")
        for key in SWITCH_BACKUPS.values():
            self.assertNotIn(key, param(P_OWN).GetStrings())
        self.assertEqual(len(self.jj("message")), 2, self.lines())
        self.assertNoJellyJamsProblems()
        STUBS.records.clear()
        self.recovery.run_startup_recovery()
        self.assertEqual(self.lines(), [], "a second start has nothing left to repair")

    def test_corrupt_assembly_backup(self):
        param(P_ASSEMBLY).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalSwitchToWB", "maybe")
        self.recovery.run_startup_recovery()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertNotIn("OriginalSwitchToWB", param(P_OWN).GetStrings())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))

    def test_corrupt_switch_backup_leaves_the_others_working(self):
        for group in SWITCH_BACKUPS:
            param(group).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalSwitchToWB", "0")
        param(P_OWN).SetString("OriginalPartDesignSwitchToWB", "yes please")
        param(P_OWN).SetString("OriginalTechDrawSwitchToWB", "absent")
        self.recovery.run_startup_recovery()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertIn("part design", self.jj("warning")[0].lower())
        self.assertFalse(param(P_PARTDESIGN).GetBool("SwitchToWB", True), "a damaged backup changes nothing")
        self.assertIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))
        self.assertNotIn("SwitchToWB", param(P_TECHDRAW_GENERAL).GetBools())
        for key in SWITCH_BACKUPS.values():
            self.assertNotIn(key, param(P_OWN).GetStrings())
        self.assertEqual(self.jj("error"), [])

    def test_failing_recovery_step_does_not_block_the_others(self):
        viewport = self.module("jellyjams.viewport")

        def broken():
            raise RuntimeError("viewport recovery broken by the harness")

        self.patch(viewport, "recover", broken)
        self.seed_010_leftovers()
        self.recovery.run_startup_recovery()
        self.assertGreaterEqual(len(self.jj("warning")), 1)
        self.assertEqual(self.jj("error"), [])
        self.assertNotIn("NavigationStyle", param(P_VIEW).GetStrings())
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFront"), "1")


# ==========================================================================
# 5. Commands
# ==========================================================================


class Test04BackupFailurePaths(HarnessCase):
    def test_backup_read_failure_preserves_settings_and_record(self):
        for area, action, key in (
                ('navigation', 'install', 'OriginalNavigationStyle'),
                ('navigation', 'recover', 'OriginalNavigationStyle'),
                ('shortcuts', 'install', 'OriginalShortcuts'),
                ('shortcuts', 'recover', 'OriginalShortcuts'),
                ('viewport', 'apply', 'OriginalViewColors'),
                ('viewport', 'recover', 'OriginalViewColors'),
                ('sketch_assist', 'recover', 'OriginalSketchSnapping')):
            with self.subTest(area=area, action=action):
                STUBS.reset()
                STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS)
                module = self.module('jellyjams.' + area, fresh=True)
                own, view = param(P_OWN), param(P_VIEW)
                if area == 'navigation':
                    record = {'existed': True, 'value': 'original'}
                elif area == 'shortcuts':
                    record = {'Std_ViewFront': [True, 'original']}
                elif area == 'viewport':
                    record = {'BackgroundColor2': ['Unsigned', True, 123]}
                else:
                    record = {key: [False, None] for key in module.SNAP_KEYS}
                raw = json.dumps(record)
                own.SetString(key, raw)
                view.SetString('NavigationStyle', 'current')
                before = view.GetContents()
                with mock.patch.object(own, 'GetString', side_effect=OSError('read unavailable')):
                    getattr(module, action)()
                self.assertEqual(own.GetString(key), raw)
                self.assertEqual(view.GetContents(), before)
                self.assertFalse(param(P_SHORTCUT).GetContents())
                self.assertTrue(self.jj('warning') + self.jj('error'))
                module.recover()
                self.assertFalse(own.GetString(key), 'a readable retry must finish recovery')

    def test_unreadable_preference_is_not_backed_up_as_absent(self):
        navigation = self.module('jellyjams.navigation', fresh=True)
        view = param(P_VIEW)
        view.SetString('NavigationStyle', 'original')
        with mock.patch.object(view, 'GetContents', side_effect=OSError('unavailable')):
            with mock.patch.object(view, 'GetStrings', side_effect=OSError('unavailable')):
                navigation.install()
        self.assertEqual(view.GetString('NavigationStyle'), 'original')
        self.assertFalse(param(P_OWN).GetString('OriginalNavigationStyle'))

    def test_partial_viewport_backup_defers_new_overrides(self):
        viewport = self.module('jellyjams.viewport', fresh=True)
        own, view = param(P_OWN), param(P_VIEW)
        raw = json.dumps({'BackgroundColor2': ['Unsigned', True, 123]})
        own.SetString('OriginalViewColors', raw)
        view.SetUnsigned('BackgroundColor2', 456)
        before = view.GetContents()
        viewport.apply()
        self.assertEqual(view.GetContents(), before)
        self.assertEqual(own.GetString('OriginalViewColors'), raw)
        self.assertFalse(viewport.is_applied())
        viewport.recover()
        self.assertEqual(view.GetContents(), [('Unsigned Long', 'BackgroundColor2', 123)])

    def test_partial_shortcut_backup_defers_new_overrides(self):
        shortcuts = self.module('jellyjams.shortcuts', fresh=True)
        STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS)
        own, group = param(P_OWN), param(P_SHORTCUT)
        raw = json.dumps({'Std_ViewFront': [True, '1']})
        own.SetString('OriginalShortcuts', raw)
        group.SetString('Std_ViewFront', 'current')
        before = group.GetContents()
        shortcuts.install()
        self.assertEqual(group.GetContents(), before)
        self.assertEqual(own.GetString('OriginalShortcuts'), raw)
        self.assertFalse(shortcuts.is_installed())
        self.module('jellyjams.shortcuts', fresh=True).recover()
        self.assertEqual(group.GetContents(), [('String', 'Std_ViewFront', '1')])

    def test_navigation_rejects_non_boolean_backup_flag(self):
        for flag in ('false', 1, None):
            for startup in (False, True):
                with self.subTest(flag=flag, startup=startup):
                    param(P_VIEW).SetString('NavigationStyle', 'original')
                    param(P_OWN).SetString('OriginalNavigationStyle',
                                             json.dumps({'existed': flag, 'value': 'bad'}))
                    if startup:
                        self.module('jellyjams.recovery').run_startup_recovery()
                    else:
                        self.module('jellyjams.navigation', fresh=True).recover()
                    self.assertEqual(param(P_VIEW).GetString('NavigationStyle'), 'original')
                    self.assertFalse(param(P_OWN).GetString('OriginalNavigationStyle'))

    def test_complete_pending_backups_can_reapply_and_recover(self):
        for area, apply, active, group_path, key in (
                ('viewport', 'apply', 'is_applied', P_VIEW, 'OriginalViewColors'),
                ('shortcuts', 'install', 'is_installed', P_SHORTCUT, 'OriginalShortcuts')):
            with self.subTest(area=area):
                STUBS.reset()
                STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS)
                module = self.module('jellyjams.' + area, fresh=True)
                before = param(group_path).GetContents()
                getattr(module, apply)()
                raw = param(P_OWN).GetString(key)
                self.assertTrue(raw)
                module = self.module('jellyjams.' + area, fresh=True)
                getattr(module, apply)()
                self.assertTrue(getattr(module, active)())
                self.assertEqual(param(P_OWN).GetString(key), raw)
                self.module('jellyjams.' + area, fresh=True).recover()
                self.assertEqual(param(group_path).GetContents(), before)


class Test05Commands(HarnessCase):
    def setUp(self):
        super().setUp()
        self.commands = self.module("jellyjams.commands", fresh=True)

    def instances(self):
        found = {}
        for module_name in EXPECTED_PROVIDERS:
            module, error = try_import(module_name)
            if module is None:
                self.fail("cannot import %s:\n%s" % (module_name, error))
            found.update(module.get_commands())
        return found

    def test_register_all_registers_every_command_once(self):
        ids = self.commands.register_all()
        self.assertEqual(sorted(ids), sorted(EXPECTED_COMMANDS))
        self.assertEqual(sorted(STUBS.registered), sorted(EXPECTED_COMMANDS))
        self.assertTrue(all(cmd.startswith("JellyJams_") for cmd in STUBS.registered))
        self.assertEqual(STUBS.duplicate_commands, [])
        self.assertEqual(self.jj("error"), [])
        self.assertTrue(any("registered" in line for line in self.jj("log")), self.lines())
        self.assertEqual(sorted(self.commands.registered_ids()), sorted(EXPECTED_COMMANDS))
        STUBS.records.clear()
        self.assertEqual(list(self.commands.register_all()), [])
        self.assertEqual(self.lines(), [])
        self.assertEqual(STUBS.duplicate_commands, [])

    def test_already_listed_commands_are_not_added_again(self):
        STUBS.set_commands(["JellyJams_Diagnostics"])
        ids = self.commands.register_all()
        self.assertNotIn("JellyJams_Diagnostics", ids)
        self.assertEqual(STUBS.duplicate_commands, [])

    def test_providers_table_and_get_commands(self):
        providers = {name: tuple(ids) for name, ids in dict(self.commands.PROVIDERS).items()}
        self.assertEqual(providers, EXPECTED_PROVIDERS)
        self.assertEqual(sorted(cmd for ids in providers.values() for cmd in ids), sorted(EXPECTED_COMMANDS))
        for module_name, ids in EXPECTED_PROVIDERS.items():
            with self.subTest(module=module_name):
                module, error = try_import(module_name)
                self.assertIsNotNone(module, error)
                commands = module.get_commands()
                self.assertEqual(sorted(commands), sorted(ids))
                for command in commands.values():
                    for method in ("GetResources", "Activated", "IsActive"):
                        self.assertTrue(callable(getattr(command, method, None)), method)

    def test_resources_menu_text_and_pixmaps(self):
        for cmd_id, command in sorted(self.instances().items()):
            with self.subTest(command=cmd_id):
                resources = command.GetResources()
                self.assertEqual(resources.get("MenuText"), EXPECTED_MENU_TEXTS[cmd_id])
                self.assertTrue(resources.get("ToolTip"))
                self.assertFalse(resources.get("Accel"), "JellyJams commands have no default shortcut")
                pixmap = resources.get("Pixmap", "")
                self.assertTrue(os.path.isfile(pixmap), "missing icon %r" % pixmap)
                self.assertEqual(norm_path(pixmap), norm_path(os.path.join(ICONS_DIR, COMMAND_ICONS[cmd_id] + ".svg")))

    def test_cmd_type_only_where_declared(self):
        # Without a CmdType FreeCAD counts a Python command as changing the document and disables
        # it while a task dialog (a sketch included) is open; the orientation commands only move
        # the camera. Every other command keeps exactly the three resources it always had.
        for cmd_id, command in sorted(self.instances().items()):
            with self.subTest(command=cmd_id):
                resources = command.GetResources()
                if cmd_id in COMMAND_CMD_TYPES:
                    self.assertEqual(resources.get("CmdType"), COMMAND_CMD_TYPES[cmd_id])
                    self.assertEqual(set(resources), {"MenuText", "ToolTip", "Pixmap", "CmdType"})
                else:
                    self.assertEqual(set(resources), {"MenuText", "ToolTip", "Pixmap"})
                    self.assertFalse(getattr(command, "cmd_type", ""))

    def test_missing_or_empty_icons_give_empty_pixmap(self):
        paths = self.module("jellyjams.paths")
        empty_addon = self.tmpdir()
        icons = os.path.join(empty_addon, "resources", "icons")
        os.makedirs(icons)
        open(os.path.join(icons, "diagnostics.svg"), "w").close()
        self.patch(paths, "icons_dir", lambda: icons)
        self.patch(paths, "addon_dir", lambda: empty_addon)
        self.assertEqual(paths.icon_path("diagnostics"), "")
        self.assertEqual(paths.icon_path("make_drawing"), "")
        for cmd_id, command in sorted(self.instances().items()):
            with self.subTest(command=cmd_id):
                self.assertEqual(command.GetResources().get("Pixmap"), "")

    def test_activated_accepts_an_index(self):
        for cmd_id, command in sorted(self.instances().items()):
            with self.subTest(command=cmd_id):
                calls = []
                self.patch(command, "run", lambda _calls=calls: _calls.append("run"))
                command.Activated()
                command.Activated(1)
                self.assertEqual(calls, ["run", "run"])
        self.assertEqual(self.jj("error"), [])

    def test_is_active_never_raises(self):
        for cmd_id, command in sorted(self.instances().items()):
            with self.subTest(command=cmd_id):
                self.assertIsInstance(command.IsActive(), bool)

                def broken():
                    raise RuntimeError("is_active broken by the harness")

                self.patch(command, "is_active", broken)
                self.assertIsInstance(command.IsActive(), bool)
        self.assertTrue(self.instances()["JellyJams_Diagnostics"].IsActive(), "Diagnostics is always active")

    def test_base_command_contract(self):
        commands = self.commands

        class Probe(commands.BaseCommand):
            command_id = "JellyJams_Probe"
            menu_text = "Probe"
            tooltip = "Harness probe"
            icon = "jellyjams"

            def run(self):
                raise RuntimeError("probe run failure")

            def is_active(self):
                raise RuntimeError("probe is_active failure")

        probe = Probe()
        resources = probe.GetResources()
        self.assertEqual(resources["MenuText"], "Probe")
        self.assertEqual(resources["ToolTip"], "Harness probe")
        self.assertEqual(norm_path(resources["Pixmap"]), norm_path(os.path.join(ICONS_DIR, "jellyjams.svg")))
        self.assertNotIn("Accel", resources)
        self.assertEqual(commands.BaseCommand.cmd_type, "", "no CmdType unless a command sets one")
        self.assertNotIn("CmdType", resources)
        probe.accel = "Ctrl+Alt+J"
        self.assertEqual(probe.GetResources().get("Accel"), "Ctrl+Alt+J")
        probe.cmd_type = "Alter3DView"
        self.assertEqual(probe.GetResources().get("CmdType"), "Alter3DView")
        probe.Activated()
        errors = self.jj("error")
        self.assertEqual(len(errors), 1)
        self.assertIn("Probe", errors[0])
        self.assertIs(probe.IsActive(), False)
        probe.active_on_error = True
        self.assertIs(probe.IsActive(), True)


# ==========================================================================
# 6. Lifecycle
# ==========================================================================


def _area_fakes(calls, lifecycle, raising=None):
    modules = {}
    for table in (INIT_HELPERS, ACTIVATION_STEPS, DEACTIVATION_STEPS):
        for key, _what, module_name, function in table:
            module = modules.setdefault(module_name, types.ModuleType(module_name))

            def step(*_args, _key=key, _function=function, **_kwargs):
                calls.append((_key, _function, lifecycle.is_active()))
                if raising == (_key, _function):
                    raise RuntimeError("boom in %s" % _key)

            setattr(module, function, step)
    return modules


class Test06Lifecycle(HarnessCase):
    def setUp(self):
        super().setUp()
        self.lifecycle = self.module("jellyjams.lifecycle", fresh=True)

    def tearDown(self):
        super().tearDown()
        with contextlib.suppress(Exception):
            importlib.reload(sys.modules["jellyjams.lifecycle"])

    def test_step_tables(self):
        lifecycle = self.lifecycle
        self.assertEqual([tuple(step) for step in lifecycle.INIT_HELPERS], INIT_HELPERS)
        self.assertEqual([tuple(step) for step in lifecycle.ACTIVATION_STEPS], ACTIVATION_STEPS)
        self.assertEqual([tuple(step) for step in lifecycle.DEACTIVATION_STEPS], DEACTIVATION_STEPS)
        self.assertEqual([(s[0], s[2], s[3]) for s in lifecycle.QUIT_REVERT_STEPS], QUIT_REVERT_STEPS)
        self.assertEqual([(s[0], s[2], s[3]) for s in lifecycle.QUIT_REAPPLY_STEPS], QUIT_REAPPLY_STEPS)

    def test_activation_fault_isolation(self):
        calls = []
        with fake_modules(_area_fakes(calls, self.lifecycle, raising=("theme", "apply"))):
            self.lifecycle.activated()
        self.assertEqual([call[0] for call in calls], [step[0] for step in ACTIVATION_STEPS])
        self.assertTrue(all(call[2] for call in calls), "is_active() must be True during activation")
        errors = self.jj("error")
        self.assertEqual(len(errors), 1, self.lines())
        self.assertIn("could not add the light theme", errors[0])
        self.assertIn("boom in theme", errors[0])

    def test_deactivation_fault_isolation(self):
        calls = []
        with fake_modules(_area_fakes(calls, self.lifecycle, raising=("ribbon", "hide"))):
            self.lifecycle.activated()
            del calls[:]
            self.lifecycle.deactivated()
        self.assertEqual([call[0] for call in calls], [step[0] for step in DEACTIVATION_STEPS])
        self.assertFalse(any(call[2] for call in calls), "is_active() must be False during deactivation")
        errors = self.jj("error")
        self.assertEqual(len(errors), 1, self.lines())
        self.assertIn("could not hide the CommandManager ribbon", errors[0])

    def test_run_steps_reports_import_and_attribute_errors(self):
        calls = []
        module = fake_module("jellyjams.harness_area", go=make_recorder(calls, "go"))
        with fake_modules({"jellyjams.harness_area": module}):
            failed = self.lifecycle.run_steps([
                ("missing_module", "use a missing module", "jellyjams.harness_missing_area", "go"),
                ("missing_function", "use a missing function", "jellyjams.harness_area", "absent"),
                ("fine", "run a working step", "jellyjams.harness_area", "go"),
            ])
        self.assertEqual(list(failed), ["missing_module", "missing_function"])
        errors = self.jj("error")
        self.assertEqual(len(errors), 2, self.lines())
        self.assertIn("could not use a missing module", errors[0])
        self.assertIn("could not use a missing function", errors[1])
        self.assertEqual(len(calls), 1)

    def test_repeated_and_unpaired_calls_are_harmless(self):
        calls = []
        with fake_modules(_area_fakes(calls, self.lifecycle)):
            self.assertFalse(self.lifecycle.is_active())
            self.lifecycle.deactivated()
            self.assertFalse(self.lifecycle.is_active())
            self.lifecycle.activated()
            self.lifecycle.activated()
            self.assertTrue(self.lifecycle.is_active())
            self.lifecycle.deactivated()
            self.lifecycle.deactivated()
            self.assertFalse(self.lifecycle.is_active())
        self.assertEqual(self.jj("error"), [])

    def test_quit_tables_run_through_run_steps(self):
        calls = []
        modules = {}
        for key, module_name, function in QUIT_REVERT_STEPS + QUIT_REAPPLY_STEPS:
            module = modules.setdefault(module_name, types.ModuleType(module_name))
            setattr(module, function, make_recorder(calls, (key, function)))
        with fake_modules(modules):
            self.lifecycle.revert_for_quit()
            self.assertEqual([call[0] for call in calls], [(key, fn) for key, _m, fn in QUIT_REVERT_STEPS])
            del calls[:]
            self.lifecycle.reapply_after_cancel()
            self.assertEqual([call[0] for call in calls], [(key, fn) for key, _m, fn in QUIT_REAPPLY_STEPS])

    def _initialize_fakes(self, calls, version=(1, 1, 4)):
        modules = {}
        for key, _what, module_name, function in INIT_HELPERS:
            module = modules.setdefault(module_name, types.ModuleType(module_name))
            setattr(module, function, make_recorder(calls, key))
        modules["jellyjams.diagnostics"] = fake_module(
            "jellyjams.diagnostics",
            environment_line=lambda: "version 9.9.9, FreeCAD %s, Qt binding harness" % ".".join(map(str, version)),
            freecad_version=lambda: tuple(version),
            get_commands=lambda: {},
        )
        return modules

    def _workbench(self, calls):
        workbench = types.SimpleNamespace()
        workbench.appendMenu = make_recorder(calls, "appendMenu")
        workbench.appendToolbar = make_recorder(calls, "appendToolbar")
        return workbench

    def test_initialize_order_and_once_per_process(self):
        commands = self.module("jellyjams.commands")
        calls = []
        self.patch(commands, "register_all", make_recorder(calls, "register_all", result=[]))
        with fake_modules(self._initialize_fakes(calls)):
            lifecycle = self.module("jellyjams.lifecycle", fresh=True)
            workbench = self._workbench(calls)
            lifecycle.initialize(workbench)
            tags = [call[0] for call in calls if call[0] != "register_all"]
            self.assertEqual(tags, [step[0] for step in INIT_HELPERS] + ["appendMenu"])
            menu_call = [call for call in calls if call[0] == "appendMenu"][0]
            self.assertEqual(menu_call[1][0], "JellyJams")
            # FreeCAD creates a command's QAction (and so its shortcut) only for commands in a
            # menu or toolbar: View Orientation and Normal To must be listed for Space and Ctrl+8.
            self.assertEqual(list(menu_call[1][1]), [ORIENTATION_CMD, NORMAL_TO_CMD, "JellyJams_Appearances", "JellyJams_Diagnostics"])
            messages = self.jj("message")
            self.assertTrue(messages and "version 9.9.9" in messages[0], messages)
            self.assertIn("workbench set up and ready", messages[-1])
            self.assertNoJellyJamsProblems()
            del calls[:]
            lifecycle.initialize(workbench)
            self.assertEqual([call[0] for call in calls if call[0] != "register_all"], [])
            other = self._workbench(calls)
            lifecycle.initialize(other)
            self.assertEqual([call[0] for call in calls if call[0] != "register_all"], ["appendMenu"])
        self.assertFalse([call for call in calls if call[0] == "appendToolbar"], "JellyJams adds no toolbars")

    def test_initialize_warns_on_old_freecad(self):
        commands = self.module("jellyjams.commands")
        calls = []
        self.patch(commands, "register_all", make_recorder(calls, "register_all", result=[]))
        with fake_modules(self._initialize_fakes(calls, version=(1, 0, 2))):
            lifecycle = self.module("jellyjams.lifecycle", fresh=True)
            lifecycle.initialize(self._workbench(calls))
        warnings = self.jj("warning")
        self.assertEqual(len(warnings), 1, self.lines())
        self.assertIn("1.1", warnings[0])
        self.assertTrue(any("workbench set up and ready" in line for line in self.jj("message")))

    def test_initialize_survives_failing_steps(self):
        commands = self.module("jellyjams.commands")
        calls = []
        self.patch(commands, "register_all", make_recorder(calls, "register_all", error=RuntimeError("reg boom")))
        modules = self._initialize_fakes(calls)
        modules["jellyjams.view_labels"].install = make_recorder(calls, "view_labels", error=RuntimeError("vl"))
        with fake_modules(modules):
            lifecycle = self.module("jellyjams.lifecycle", fresh=True)
            lifecycle.initialize(self._workbench(calls))
        tags = [call[0] for call in calls]
        self.assertIn("appendMenu", tags)
        self.assertIn("zoom_lines", tags)
        self.assertGreaterEqual(len(self.jj("error")), 2, self.lines())
        self.assertTrue(any("workbench set up and ready" in line for line in self.jj("message")))

    def test_real_activation_cycle_under_stubs(self):
        fcgui = self.module("jellyjams.fcgui")
        self.patch(fcgui, "preload_command_modules", lambda: ([], []))
        # FreeCAD's commands; the orientation commands are JellyJams' own and get registered below
        freecad_ids = (ribbon_command_ids() - set(JJ_SHORTCUT_COMMANDS)) | {ALIGN_CMD}
        STUBS.set_commands(sorted(freecad_ids | set(SHORTCUT_COMMANDS) | set(DEFAULT_KEY_OWNERS)),
                           shortcuts=DEFAULT_KEY_OWNERS)
        STUBS.set_active_workbench(WB)
        self.addCleanup(QtCore.qInstallMessageHandler, None)

        def original_activate(self_, *_args):
            return "switched"

        tempo_class = type("TempoVis", (), {"activateWorkbench": original_activate})
        original = tempo_class.__dict__["activateWorkbench"]
        gui_activate = STUBS.gui.activateWorkbench
        self.addCleanup(setattr, STUBS.gui, "activateWorkbench", gui_activate)
        param(P_PARTDESIGN).SetBool("SwitchToWB", True)
        show = fake_module("Show", __path__=[])
        tempo_module = fake_module("Show.mTempoVis", TempoVis=tempo_class)
        show.mTempoVis = tempo_module
        show.TempoVis = tempo_class
        self.module("jellyjams.commands", fresh=True)   # registration runs once per process
        orientation = self.module("jellyjams.orientation", fresh=True)
        self.addCleanup(orientation.close)
        with fake_modules({"Show": show, "Show.mTempoVis": tempo_module}):
            lifecycle = self.lifecycle
            workbench = STUBS.gui.Workbench()
            lifecycle.initialize(workbench)
            self.assertEqual(workbench._menus, [("JellyJams", [ORIENTATION_CMD, NORMAL_TO_CMD,
                                                               "JellyJams_Appearances", "JellyJams_Diagnostics"])])
            self.assertIn(ORIENTATION_CMD, STUBS.registered)
            self.assertIn(NORMAL_TO_CMD, STUBS.registered)
            window = STUBS.main_window
            box = QtWidgets.QCheckBox("harness check box", window)
            self.assertTrue(focus_on(box), QtWidgets.QApplication.focusWidget())
            self.assertFalse(override_accepted(box, space_event()), "no Space filter before activation")
            lifecycle.deactivated()
            lifecycle.activated()
            lifecycle.activated()
            STUBS.pump(100)
            self.assertTrue(lifecycle.is_active())
            self.assertEqual(window.styleSheet().count(THEME_BEGIN), 1)
            self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
            self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFitAll"), "F")
            self.assertEqual(param(P_SHORTCUT).GetString(ORIENTATION_CMD), "Space")
            self.assertEqual(param(P_SHORTCUT).GetString(NORMAL_TO_CMD), "Ctrl+8")
            self.assertNotIn(ALIGN_CMD, param(P_SHORTCUT).GetStrings(), "FreeCAD's Align to selection is left alone")
            self.assertIn("Std_ToggleVisibility", param(P_SHORTCUT).GetStrings(), "Space is taken from Show/Hide")
            self.assertEqual(param(P_SHORTCUT).GetString("Std_ToggleVisibility", "missing"), "")
            self.assertEqual(len(space_filters(window)), 1, "activating twice installs one Space filter")
            self.assertIs(orientation._filtered[0], window, "the filter sits on the main window and its docks")
            self.assertTrue(focus_on(box))
            self.assertTrue(override_accepted(box, space_event()), "a focused check box keeps Space")
            STUBS.registered[ORIENTATION_CMD].Activated()   # what Space runs
            self.assertTrue(orientation.is_open())
            for group in SWITCH_BACKUPS:
                self.assertFalse(param(group).GetBool("SwitchToWB", True), group)
            for key in ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors") + tuple(
                    SWITCH_BACKUPS.values()):
                self.assertTrue(param(P_OWN).GetString(key, ""), key)
            self.assertEqual(param(P_OWN).GetString("OriginalPartDesignSwitchToWB", ""), "1")
            self.assertEqual(param(P_OWN).GetString("OriginalTechDrawSwitchToWB", ""), "absent")
            self.assertIsNot(STUBS.gui.activateWorkbench, gui_activate, "edit_guard wraps activateWorkbench")
            self.assertTrue(sys.modules["jellyjams.edit_guard"].is_installed())
            dock = window.findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
            self.assertIsNotNone(dock)
            self.assertTrue(dock.isVisible())
            lifecycle.deactivated()
            lifecycle.deactivated()
            STUBS.pump(400)
            self.assertFalse(lifecycle.is_active())
            self.assertNotIn(THEME_BEGIN, window.styleSheet())
            self.assertNotIn("NavigationStyle", param(P_VIEW).GetStrings())
            self.assertNotIn("Std_ViewFitAll", param(P_SHORTCUT).GetStrings())
            for command in (ORIENTATION_CMD, NORMAL_TO_CMD, ALIGN_CMD, "Std_ToggleVisibility", "Std_ViewBoxZoom"):
                self.assertNotIn(command, param(P_SHORTCUT).GetStrings(), command)
            self.assertFalse(orientation.is_open(), "leaving JellyJams closes the Orientation panel")
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
            self.assertEqual(space_filters(window), [], "leaving JellyJams removes the Space filter")
            self.assertEqual(orientation._filtered, [])
            self.assertTrue(focus_on(box))
            self.assertFalse(override_accepted(box, space_event()), "Space is FreeCAD's again")
            self.assertNotIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
            self.assertNotIn("SwitchToWB", param(P_TECHDRAW_GENERAL).GetBools())
            self.assertIn("SwitchToWB", param(P_PARTDESIGN).GetBools())
            self.assertTrue(param(P_PARTDESIGN).GetBool("SwitchToWB", False))
            for key in ("OriginalNavigationStyle", "OriginalShortcuts", "OriginalViewColors") + tuple(
                    SWITCH_BACKUPS.values()):
                self.assertEqual(param(P_OWN).GetString(key, ""), "", key)
            self.assertFalse(dock.isVisible())
            self.assertIs(tempo_class.__dict__["activateWorkbench"], original)
            self.assertIs(STUBS.gui.activateWorkbench, gui_activate, "FreeCAD's own function is back")
            self.assertFalse(sys.modules["jellyjams.edit_guard"].is_installed())
        self.assertEqual(self.jj("error"), [])


# ==========================================================================
# 7. Quit guard (logic level)
# ==========================================================================


class Test07QuitGuard(HarnessCase):
    def setUp(self):
        super().setUp()
        self.lifecycle = self.module("jellyjams.lifecycle")
        self.guard = self.module("jellyjams.quit_guard", fresh=True)
        self.calls = []
        self.active = True
        self.patch(self.lifecycle, "is_active", lambda: self.active)
        self.patch(self.lifecycle, "revert_for_quit", lambda: self.calls.append("revert"))
        self.patch(self.lifecycle, "reapply_after_cancel", lambda: self.calls.append("reapply"))
        STUBS.set_active_workbench(WB)
        self.window = STUBS.main_window
        self.guard.install()
        self.assertTrue(self.guard.is_installed())

    def modal_prompt(self):
        dialog = QtWidgets.QDialog(self.window)
        dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        dialog.show()
        self.addCleanup(dialog.close)
        STUBS.pump(0)
        self.assertIs(QtWidgets.QApplication.activeModalWidget(), dialog)
        return dialog

    def test_cancel_reapplies_once_after_the_prompt(self):
        self.window.accept_close = False
        prompt = self.modal_prompt()
        self.window.close()
        self.assertEqual(self.calls, ["revert"])
        self.assertIn(self.window, STUBS.closed_windows, "the guard must not consume the Close event")
        STUBS.pump(1300)
        self.assertEqual(self.calls, ["revert"], "nothing may be re-applied while a modal dialog is open")
        prompt.close()
        self.assertTrue(STUBS.wait_until(lambda: "reapply" in self.calls, 2000), self.calls)
        STUBS.pump(900)
        self.assertEqual(self.calls, ["revert", "reapply"])

    def test_discard_reapplies_nothing(self):
        self.window.accept_close = True
        self.window.close()
        self.assertFalse(self.window.isVisible())
        STUBS.pump(1200)
        self.assertEqual(self.calls, ["revert"])

    def test_inactive_jellyjams_is_left_alone(self):
        self.active = False
        self.window.accept_close = False
        self.window.close()
        STUBS.pump(900)
        self.assertEqual(self.calls, [])

    def test_workbench_switched_before_recheck(self):
        self.window.accept_close = False
        self.window.close()
        STUBS.set_active_workbench("PartDesignWorkbench")
        STUBS.pump(1200)
        self.assertEqual(self.calls, ["revert"])

    def test_second_close_while_pending_and_double_install(self):
        self.guard.install()
        self.window.accept_close = False
        prompt = self.modal_prompt()
        self.window.close()
        self.window.close()
        self.assertEqual(self.calls, ["revert"])
        prompt.close()
        self.assertTrue(STUBS.wait_until(lambda: "reapply" in self.calls, 2000), self.calls)
        STUBS.pump(600)
        self.assertEqual(self.calls, ["revert", "reapply"])

    def test_failing_revert_never_blocks_the_close(self):
        def broken():
            raise RuntimeError("revert broken by the harness")

        self.patch(self.lifecycle, "revert_for_quit", broken)
        self.window.accept_close = True
        self.window.close()
        self.assertIn(self.window, STUBS.closed_windows)
        self.assertFalse(self.window.isVisible())
        self.assertEqual(self.jj("error"), [])


# ==========================================================================
# 8. Qt message filter
# ==========================================================================


class Test07AcceptedQuitGuard(HarnessCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        self.lifecycle = self.module("jellyjams.lifecycle")
        self.patch(self.lifecycle, "is_active", lambda: True)
        self.patch(self.lifecycle, "revert_for_quit", lambda: self.calls.append("restore"))
        self.patch(self.lifecycle, "reapply_after_cancel", lambda: self.calls.append("reapply"))
        calls = self.calls

        class Window(QtWidgets.QMainWindow):
            mainWindowClosed = QtCore.Signal()
            accept_close = False

            def closeEvent(self, event):
                if self.accept_close:
                    self.mainWindowClosed.emit()
                    self.at_save = list(calls)
                    event.accept()
                else:
                    event.ignore()

        self.window = Window()
        self.window.show()
        self.addCleanup(self.window.deleteLater)
        self.patch(self.module("jellyjams.fcgui"), "main_window", lambda: self.window)
        self.guard = self.module("jellyjams.quit_guard", fresh=True)
        self.guard.install()
        self.assertTrue(self.guard._watcher.accepted_close_connected)

    def test_cancel_keeps_interface_and_never_runs_restore_or_reapply(self):
        self.window.close()
        STUBS.pump(750)
        self.assertTrue(self.window.isVisible())
        self.assertEqual(self.calls, [])

    def test_accepted_close_restores_synchronously_before_settings_are_saved(self):
        self.window.accept_close = True
        self.window.close()
        self.assertEqual(self.window.at_save, ["restore"])
        STUBS.pump(750)
        self.assertEqual(self.calls, ["restore"])

    def test_duplicate_install_and_accepted_signal_restore_only_once(self):
        self.guard.install()
        self.window.mainWindowClosed.emit()
        self.window.mainWindowClosed.emit()
        self.assertEqual(self.calls, ["restore"])

    def test_inactive_workbench_is_untouched_on_accepted_close(self):
        self.patch(self.lifecycle, "is_active", lambda: False)
        self.window.accept_close = True
        self.window.close()
        self.assertEqual(self.window.at_save, [])


class Test08QtFilter(HarnessCase):
    GLYPH = "render glyph failed err=40 headless sample"

    def setUp(self):
        super().setUp()
        self.filter = self.module("jellyjams.qt_filter", fresh=True)
        self.filter._previous = None

    def test_format_forward(self):
        self.assertEqual(self.filter.format_forward("default", "hello"), "hello\n")
        self.assertEqual(self.filter.format_forward("", "hello"), "hello\n")
        self.assertEqual(self.filter.format_forward("qt.svg", "hello"), "(qt.svg) hello\n")

    def test_glyph_messages_dropped_only_when_enabled(self):
        self.filter._enabled = True
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.GLYPH)
        self.assertEqual(self.lines("warning"), [])
        logs = self.lines("log")
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].startswith(PREFIX))
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.GLYPH)
        self.assertEqual(len(self.lines()), 1, "only the first dropped message is logged")
        self.filter._enabled = False
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.GLYPH)
        self.assertEqual(self.lines("warning"), [self.filter.format_forward("default", self.GLYPH)])

    def test_probe_always_dropped_and_not_counted(self):
        self.filter._enabled = False
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.filter.PROBE_TEXT)
        self.assertEqual(self.lines(), [])
        self.assertTrue(self.filter._probe_seen)
        self.assertFalse(self.filter._first_drop_logged)
        self.filter._enabled = True
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.filter.PROBE_TEXT)
        self.assertEqual(self.lines(), [])
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), self.GLYPH)
        self.assertEqual(len(self.lines("log")), 1)
        self.assertTrue(self.filter.PROBE_TEXT.startswith(self.filter.GLYPH_PREFIX))
        self.assertEqual(self.filter.GLYPH_PREFIX, "render glyph failed")

    def test_forwarding_levels_without_prefix(self):
        self.filter._enabled = True
        cases = [(QtCore.QtMsgType.QtDebugMsg, "log"), (QtCore.QtMsgType.QtInfoMsg, "log"),
                 (QtCore.QtMsgType.QtWarningMsg, "warning"), (QtCore.QtMsgType.QtCriticalMsg, "error"),
                 (QtCore.QtMsgType.QtFatalMsg, "error")]
        for msg_type, level in cases:
            with self.subTest(level=level, msg_type=msg_type):
                STUBS.records.clear()
                self.filter.handle(msg_type, FakeContext("qt.harness"), "unrelated message")
                self.assertEqual(STUBS.records, [(level, "(qt.harness) unrelated message\n")])
        STUBS.records.clear()
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext("default"), "unrelated warning")
        self.assertEqual(STUBS.records, [("warning", "unrelated warning\n")])

    def test_previous_handler_is_chained(self):
        received = []
        self.filter._previous = lambda *args: received.append(args)
        self.filter._enabled = True
        context = FakeContext("qt.harness")
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, context, "unrelated warning")
        self.assertEqual(received, [(QtCore.QtMsgType.QtWarningMsg, context, "unrelated warning")])
        self.assertEqual(self.lines("warning"), [])
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, context, self.GLYPH)
        self.assertEqual(len(received), 1)
        self.filter._enabled = False
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, context, self.GLYPH)
        self.assertEqual(len(received), 2)

    def test_handler_never_raises(self):
        def broken(*_args):
            raise RuntimeError("previous handler broken by the harness")

        self.filter._previous = broken
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, FakeContext(), "plain x")
        self.filter._previous = None
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, object(), "plain y")
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, None, None)
        self.filter._enabled = True
        self.filter.handle(QtCore.QtMsgType.QtWarningMsg, None, self.GLYPH)

    def test_parameter_false_registers_nothing(self):
        param(P_OWN).SetBool("SilenceGlyphWarnings", False)
        self.filter.install_and_enable()
        self.assertFalse(self.filter.is_installed())
        self.assertFalse(self.filter.is_enabled())
        self.assertTrue(self.jj("log"), self.lines())
        self.assertEqual(self.jj("message"), [])
        self.filter.disable()
        self.assertFalse(param(P_OWN).GetBool("SilenceGlyphWarnings", True))
        self.assertEqual(param(P_OWN).GetBools(), ["SilenceGlyphWarnings"])

    def test_real_install_self_test_and_enable_disable(self):
        self.addCleanup(QtCore.qInstallMessageHandler, None)
        self.filter.install_and_enable()
        self.assertTrue(self.filter.is_installed())
        self.assertTrue(self.filter.is_enabled())
        self.assertTrue(any("self-test ok" in line for line in self.jj("message")), self.lines())
        self.assertFalse(any("self-test" in line for line in self.lines("warning")))
        STUBS.records.clear()
        self.filter.install_and_enable()
        self.assertEqual(self.jj("message"), [], "installed once per process")
        QtCore.qWarning(self.GLYPH)
        self.assertEqual(self.lines("warning"), [])
        self.assertEqual(len(self.jj("log")), 1)
        QtCore.qWarning("unrelated warning")
        self.assertEqual(self.lines("warning"), ["unrelated warning\n"])
        self.filter.disable()
        self.assertFalse(self.filter.is_enabled())
        self.assertTrue(self.filter.is_installed())
        QtCore.qWarning(self.GLYPH)
        self.assertIn(self.GLYPH + "\n", self.lines("warning"))
        self.assertNotIn("SilenceGlyphWarnings", param(P_OWN).GetBools(), "JellyJams never writes SilenceGlyphWarnings")


# ==========================================================================
# 9. Diagnostics
# ==========================================================================

DIAGNOSTICS_LABELS = ["Add-on version", "FreeCAD version", "FreeCAD build", "Python", "Platform", "Qt binding",
                      "Qt version", "Add-on path", "Path is a symlink", "Icons found", "User AppData",
                      "Draft available", "Sketcher available", "Coin3D (pivy)"]


class Test09Diagnostics(HarnessCase):
    def setUp(self):
        super().setUp()
        self.diagnostics = self.module("jellyjams.diagnostics")

    def test_rows_in_order_with_values(self):
        jellyjams = self.module("jellyjams")
        rows = [(label, str(value)) for label, value in self.diagnostics.collect_rows()]
        self.assertEqual([label for label, _value in rows], DIAGNOSTICS_LABELS)
        values = dict(rows)
        self.assertEqual(values["Add-on version"], jellyjams.__version__)
        self.assertEqual(values["FreeCAD version"], "1.1.4")
        self.assertEqual(values["FreeCAD build"], "20260928 (Git shallow)")
        self.assertTrue(values["Python"].startswith("%d.%d" % sys.version_info[:2]))
        self.assertTrue(values["Platform"])
        self.assertTrue(values["Qt binding"])
        self.assertTrue(values["Qt version"])
        self.assertEqual(norm_path(values["Add-on path"]), norm_path(REPO))
        self.assertIn(values["Path is a symlink"], ("True", "False"))
        self.assertEqual(values["Icons found"], str(os.path.isdir(ICONS_DIR)))
        self.assertEqual(values["User AppData"], STUBS.app.getUserAppDataDir())
        for label in ("Draft available", "Sketcher available"):
            self.assertRegex(values[label], r"^(yes|NO - .+)$")
        self.assertTrue(values["Coin3D (pivy)"])

    def test_freecad_version_parsing(self):
        self.assertEqual(tuple(self.diagnostics.freecad_version()), (1, 1, 4))
        self.patch(STUBS.app, "Version", lambda: ["2", "0dev", "abc", "x"])
        self.assertEqual(tuple(self.diagnostics.freecad_version()), (2, 0, 0))

    def test_format_block(self):
        block = self.diagnostics.format_block([("A", "1"), ("Longer", "two")])
        lines = block.splitlines()
        self.assertEqual(lines[:4], ["JellyJams Diagnostics", "=" * 40, "A      : 1", "Longer : two"])
        full = self.diagnostics.format_block(self.diagnostics.collect_rows()).splitlines()
        self.assertEqual(full[0], "JellyJams Diagnostics")
        self.assertEqual(full[1], "=" * 40)
        columns = {line.index(" : ") for line in full[2:2 + len(DIAGNOSTICS_LABELS)]}
        self.assertEqual(len(columns), 1, "colons must line up")

    def test_environment_line_and_command(self):
        jellyjams = self.module("jellyjams")
        line = self.diagnostics.environment_line()
        self.assertIn(jellyjams.__version__, line)
        self.assertIn("1.1.4", line)
        commands = self.diagnostics.get_commands()
        self.assertEqual(list(commands), ["JellyJams_Diagnostics"])
        command = commands["JellyJams_Diagnostics"]
        self.assertEqual(command.GetResources()["MenuText"], "Diagnostics")
        self.assertTrue(command.IsActive())


# ==========================================================================
# 10. Look: palette, theme, viewport
# ==========================================================================

PALETTE_VALUES = {
    "WINDOW": "#f2f4f6", "PANEL": "#ffffff", "RIBBON_SURFACE": "#fbfcfd", "TAB_STRIP": "#f2f4f6",
    "BORDER": "#c9ced6", "TEXT": "#1f2328", "TEXT_SECONDARY": "#5a6572", "TEXT_DISABLED": "#9aa4af",
    "ACCENT": "#1a76c4", "ACCENT_DARK": "#115a99", "HOVER": "#e8f2fb", "PRESSED": "#cfe6f8",
    "SELECTION": "#cfe6f8", "TREE_TEXT": "#1f2328", "GRADIENT_TOP": "#fdfdfd", "GRADIENT_BOTTOM": "#dfe6ec",
    "SKETCH_UNDER_DEFINED": "#1a76c4", "SKETCH_FULLY_DEFINED": "#000000", "SKETCH_OVER_DEFINED": "#ff0000",
    "SKETCH_CONSTRUCTION": "#5c6bd1", "SKETCH_CONSTRUCTION_DEFINED": "#454a52", "DIM_DRIVING": "#000000",
    "DIM_DRIVEN": "#6b7178", "RELATION_SYMBOLS": "#2a8048",
}
WIDGET_KEYS = {"window": "WINDOW", "panel": "PANEL", "ribbon_surface": "RIBBON_SURFACE",
               "tab_strip": "TAB_STRIP", "border": "BORDER", "text": "TEXT", "text_secondary": "TEXT_SECONDARY",
               "text_disabled": "TEXT_DISABLED", "accent": "ACCENT", "accent_dark": "ACCENT_DARK",
               "hover": "HOVER", "pressed": "PRESSED", "selection": "SELECTION", "tree_text": "TREE_TEXT"}
VIEWPORT_KEYS = {"gradient_top": "GRADIENT_TOP", "gradient_bottom": "GRADIENT_BOTTOM",
                 "under_defined": "SKETCH_UNDER_DEFINED", "fully_defined": "SKETCH_FULLY_DEFINED",
                 "over_defined": "SKETCH_OVER_DEFINED", "construction": "SKETCH_CONSTRUCTION",
                 "construction_defined": "SKETCH_CONSTRUCTION_DEFINED", "driving_dimension": "DIM_DRIVING",
                 "driven_dimension": "DIM_DRIVEN", "relation_symbols": "RELATION_SYMBOLS"}
MANAGED_KEYS = [
    ("Gradient", "Bool", True), ("RadialGradient", "Bool", False), ("UseBackgroundColorMid", "Bool", False),
    ("BackgroundColor2", "Unsigned", 4261281279), ("BackgroundColor3", "Unsigned", 3756453119),
    ("EditedEdgeColor", "Unsigned", 443991295), ("FullyConstraintElementColor", "Unsigned", 255),
    ("FullyConstrainedColor", "Unsigned", 255), ("InvalidSketchColor", "Unsigned", 4278190335),
    ("ConstructionColor", "Unsigned", 1550569983),
    ("FullyConstraintConstructionElementColor", "Unsigned", 1162498815),
    ("ConstrainedDimColor", "Unsigned", 255), ("NonDrivingConstrDimColor", "Unsigned", 1802598655),
    ("ConstrainedIcoColor", "Unsigned", 713050367),
]


def w3c_luminance(color):
    color = color.lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def w3c_contrast(a, b):
    high, low = sorted((w3c_luminance(a), w3c_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def qss_rules(block):
    """(selector, [declarations]) of a Qt style sheet; asserts the brace structure."""
    text = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    rules = []
    position = 0
    while True:
        start = text.find("{", position)
        if start == -1:
            if text[position:].strip():
                raise AssertionError("text after the last rule: %r" % text[position:].strip()[:80])
            return rules
        end = text.find("}", start)
        if end == -1:
            raise AssertionError("unbalanced brace after %r" % text[position:start].strip()[:80])
        selector, body = text[position:start].strip(), text[start + 1:end]
        if "{" in body:
            raise AssertionError("nested brace in rule %r" % selector)
        if not selector or "}" in selector:
            raise AssertionError("empty or broken selector before %r" % body[:60])
        rules.append((selector, [part.strip() for part in body.split(";") if part.strip()]))
        position = end + 1


class Test10Look(HarnessCase):
    def palette_module(self):
        return self.module("jellyjams.palette")

    def test_palette_values(self):
        palette = self.palette_module()
        for name, value in PALETTE_VALUES.items():
            self.assertEqual(str(getattr(palette, name)).lower(), value, name)
        self.assertEqual({k: v.lower() for k, v in dict(palette.WIDGET_PALETTE).items()},
                         {k: PALETTE_VALUES[v] for k, v in WIDGET_KEYS.items()})
        self.assertEqual({k: v.lower() for k, v in dict(palette.VIEWPORT_PALETTE).items()},
                         {k: PALETTE_VALUES[v] for k, v in VIEWPORT_KEYS.items()})

    def test_luminance_contrast_and_packing(self):
        palette = self.palette_module()
        self.assertAlmostEqual(palette.relative_luminance("#ffffff"), 1.0, places=9)
        self.assertAlmostEqual(palette.relative_luminance("#000000"), 0.0, places=9)
        for color in PALETTE_VALUES.values():
            self.assertAlmostEqual(palette.relative_luminance(color), w3c_luminance(color), places=9)
        self.assertAlmostEqual(palette.contrast_ratio("#1f2328", "#ffffff"), 15.80, places=2)
        self.assertAlmostEqual(palette.contrast_ratio("#ffffff", "#1f2328"),
                               palette.contrast_ratio("#1f2328", "#ffffff"), places=9)
        self.assertEqual(palette.packed_rgba("#1a76c4"), 443991295)
        self.assertEqual(palette.packed_rgba("#fdfdfd"), 4261281279)
        self.assertEqual(palette.packed_rgba("#000000"), 255)
        reference = [("#1f2328", "#fbfcfd", 15.38), ("#1f2328", "#f2f4f6", 14.33), ("#1f2328", "#e8f2fb", 13.94),
                     ("#1f2328", "#cfe6f8", 12.28), ("#5a6572", "#ffffff", 5.93), ("#5a6572", "#f2f4f6", 5.38),
                     ("#1a76c4", "#ffffff", 4.74), ("#1a76c4", "#e8f2fb", 4.18), ("#115a99", "#cfe6f8", 5.54)]
        for fg, bg, ratio in reference:
            self.assertAlmostEqual(w3c_contrast(fg, bg), ratio, delta=0.006)

    def test_contrast_requirements(self):
        palette = self.palette_module()
        text_pairs = {(a.lower(), b.lower()) for a, b in palette.TEXT_PAIRS}
        required_text = {("#1f2328", c) for c in ("#ffffff", "#fbfcfd", "#f2f4f6", "#e8f2fb", "#cfe6f8")}
        required_text |= {("#5a6572", c) for c in ("#ffffff", "#fbfcfd", "#f2f4f6")}
        self.assertTrue(required_text <= text_pairs, required_text - text_pairs)
        for fg, bg in text_pairs:
            self.assertGreaterEqual(w3c_contrast(fg, bg), 4.5, (fg, bg))
        nontext = {(a.lower(), b.lower()) for a, b in palette.NONTEXT_PAIRS}
        required_nontext = {("#1a76c4", c) for c in ("#ffffff", "#fbfcfd", "#f2f4f6", "#e8f2fb")}
        required_nontext.add(("#115a99", "#cfe6f8"))
        self.assertTrue(required_nontext <= nontext, required_nontext - nontext)
        for fg, bg in nontext:
            self.assertGreaterEqual(w3c_contrast(fg, bg), 3.0, (fg, bg))
        sketch = {c.lower() for c in palette.SKETCH_COLORS}
        self.assertTrue({"#1a76c4", "#000000", "#ff0000", "#5c6bd1", "#454a52", "#6b7178", "#2a8048"} <= sketch)
        for color in sketch:
            for end in ("#fdfdfd", "#dfe6ec"):
                self.assertGreaterEqual(w3c_contrast(color, end), 3.0, (color, end))
        self.assertGreater(w3c_luminance("#9aa4af"), w3c_luminance("#1f2328"))

    def test_theme_block_syntax_and_colors(self):
        theme = self.module("jellyjams.theme")
        block = theme.build_block()
        lines = block.strip().splitlines()
        self.assertEqual(lines[0].strip(), THEME_BEGIN)
        self.assertEqual(lines[-1].strip(), THEME_END)
        self.assertEqual(block.count(THEME_BEGIN), 1)
        self.assertEqual(block.count(THEME_END), 1)
        self.assertNotRegex(block, r"\{[A-Za-z_][A-Za-z0-9_]*\}|%\(|\$\{", "unreplaced placeholder")
        rules = qss_rules(block)
        self.assertTrue(rules)
        allowed = {value for value in PALETTE_VALUES.values()}
        for selector, declarations in rules:
            for declaration in declarations:
                self.assertRegex(declaration, r"^[A-Za-z-]+\s*:\s*\S", "%s: %r" % (selector, declaration))
                value = declaration.split(":", 1)[1]
                for color in re.findall(r"#[0-9A-Za-z]+", value):
                    digits = color[1:].lower()
                    self.assertRegex(digits, r"^([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$", color)
                    if len(digits) == 6:
                        self.assertIn("#" + digits, allowed, "%s uses a non-palette color" % selector)
                    elif len(digits) == 8 and digits[:2] != "00":
                        self.assertIn("#" + digits[2:], allowed, "%s uses a non-palette color" % selector)
        selectors = " ".join(selector for selector, _declarations in rules)
        for needed in ("JellyJamsCommandManager", "JellyJamsCommandManagerTabs", "JellyJamsGroupDivider", "JellyJamsPropertyManager",
                       "JellyJamsPropertyManagerTitle", "JellyJamsSectionCaption", "JellyJamsItemList", "popupMode",
                       "MainWindow", "QDockWidget", "Gui--OverlayTitleBar", "Model"):
            self.assertIn(needed, selectors)

    def test_theme_apply_remove_exact(self):
        theme = self.module("jellyjams.theme", fresh=True)
        window = STUBS.main_window
        base = "QLabel#HarnessBase { color: red; }"
        window.setStyleSheet(base)
        app_sheet = STUBS.qapp.styleSheet()
        for _cycle in range(10):
            theme.apply()
            theme.apply()
            sheet = window.styleSheet()
            self.assertTrue(sheet.startswith(base))
            self.assertEqual(sheet.count(THEME_BEGIN), 1)
            self.assertEqual(sheet.count(THEME_END), 1)
            self.assertTrue(theme.is_applied())
            theme.remove()
            self.assertEqual(window.styleSheet(), base)
            self.assertFalse(theme.is_applied())
        theme.remove()
        self.assertEqual(window.styleSheet(), base)
        self.assertEqual(STUBS.qapp.styleSheet(), app_sheet)
        self.assertNoJellyJamsProblems()

    def test_dark_widget_palette_contrast_and_role_coverage(self):
        palette = self.palette_module()
        self.assertEqual(set(palette.DARK_WIDGET_PALETTE), set(palette.WIDGET_PALETTE))
        colors = palette.widget_colors(dark=True)
        for text in (colors.TEXT, colors.TEXT_SECONDARY, colors.TREE_TEXT):
            for background in (colors.WINDOW, colors.PANEL, colors.RIBBON_SURFACE,
                               colors.TAB_STRIP, colors.HOVER, colors.SELECTION):
                self.assertGreaterEqual(w3c_contrast(text, background), 4.5, (text, background))
        for background in (colors.PANEL, colors.RIBBON_SURFACE, colors.HOVER, colors.PRESSED):
            self.assertGreaterEqual(w3c_contrast(colors.ACCENT, background), 3.0)

    def test_theme_follows_native_dark_light_and_restores_exactly(self):
        theme = self.module("jellyjams.theme", fresh=True)
        palette = self.palette_module()
        app, window = STUBS.qapp, STUBS.main_window
        original = app.styleSheet()
        self.addCleanup(app.setStyleSheet, original)
        self.addCleanup(theme.remove)
        base = "QLabel#Foreign { padding: 3px; }"
        window.setStyleSheet(base)
        for dark, background, foreground in ((True, "#191919", "#ffffff"),
                                              (False, "#ffffff", "#191919"),
                                              (True, "#191919", "#ffffff")):
            with self.subTest(dark=dark):
                native = "* { background: %s; color: %s; }" % (background, foreground)
                app.setStyleSheet(native)
                expected = palette.widget_colors(dark)
                self.assertEqual(theme.widget_colors().RIBBON_SURFACE, expected.RIBBON_SURFACE)
                theme.apply()
                first = window.styleSheet()
                self.assertIn("background-color: " + expected.RIBBON_SURFACE, first)
                theme.apply()
                self.assertEqual(window.styleSheet(), first, "mode detection must not read our override")
                self.assertEqual(first.count(THEME_BEGIN), 1)
                self.assertEqual(app.styleSheet(), native)
                theme.remove()
                self.assertEqual(window.styleSheet(), base)
                self.assertEqual(app.styleSheet(), native)

    def test_floating_sketch_popup_uses_native_dark_colors(self):
        context = self.module("jellyjams.context_sketch")
        palette = self.palette_module().widget_colors(dark=True)
        app = STUBS.qapp
        self.addCleanup(app.setStyleSheet, app.styleSheet())
        app.setStyleSheet("* { background: #191919; color: #ffffff; }")
        self.assertEqual(context._colors()["PANEL"], palette.PANEL)
        self.assertIn(palette.PANEL, context._style_sheet())

    def test_stale_and_truncated_blocks(self):
        theme = self.module("jellyjams.theme", fresh=True)
        window = STUBS.main_window
        base = "QLabel#HarnessBase { color: red; }"
        stale = base + "\n" + THEME_BEGIN + "\nQWidget#Old { color: #000000; }\n" + THEME_END + "\n"
        window.setStyleSheet(stale)
        theme.apply()
        self.assertEqual(window.styleSheet().count(THEME_BEGIN), 1)
        self.assertEqual(window.styleSheet().count(THEME_END), 1)
        self.assertNotIn("QWidget#Old", window.styleSheet())
        theme.remove()
        self.assertEqual(window.styleSheet().rstrip(), base)
        window.setStyleSheet(base + "\n" + THEME_BEGIN + "\nQWidget#Old { color: #000; }")
        theme.apply()
        self.assertEqual(window.styleSheet().count(THEME_BEGIN), 1)
        self.assertEqual(window.styleSheet().count(THEME_END), 1)
        theme.remove()
        self.assertNotIn(THEME_BEGIN, window.styleSheet())
        self.assertNotIn(THEME_END, window.styleSheet())
        self.assertEqual(theme.strip_block(stale).rstrip(), base)
        self.assertEqual(theme.strip_block(base), base)
        self.assertNotIn(THEME_BEGIN, theme.strip_block(base + "\n" + THEME_BEGIN + "\nQWidget { }"))

    def test_foreign_changes_survive_removal(self):
        theme = self.module("jellyjams.theme", fresh=True)
        window = STUBS.main_window
        theme.apply()
        window.setStyleSheet(window.styleSheet() + "\nQLabel#Foreign { }\n")
        theme.remove()
        self.assertNotIn(THEME_BEGIN, window.styleSheet())
        self.assertIn("QLabel#Foreign", window.styleSheet())
        theme.apply()
        window.setStyleSheet("QLabel#Replaced { }")
        theme.remove()
        self.assertEqual(window.styleSheet(), "QLabel#Replaced { }")

    def test_raising_set_style_sheet_logs_error(self):
        theme = self.module("jellyjams.theme", fresh=True)
        viewport = self.module("jellyjams.viewport", fresh=True)

        class RefusingWindow(QtWidgets.QMainWindow):
            def setStyleSheet(self, _sheet):
                raise RuntimeError("stylesheet refused by the harness")

        STUBS.set_main_window(RefusingWindow())
        theme.apply()
        self.assertGreaterEqual(len(self.jj("error")), 1, self.lines())
        viewport.apply()
        self.assertTrue(param(P_VIEW).GetBool("Gradient", False))
        theme.remove()
        viewport.restore()

    def assertManagedAbsent(self):
        view = param(P_VIEW)
        for key, suffix, _value in MANAGED_KEYS:
            self.assertNotIn(key, getattr(view, "Get%ss" % suffix)(), key)

    def test_viewport_managed_keys(self):
        viewport = self.module("jellyjams.viewport")
        palette = self.palette_module()
        self.assertEqual([tuple(entry) for entry in viewport.MANAGED_KEYS], MANAGED_KEYS)
        self.assertEqual(palette.packed_rgba(palette.GRADIENT_TOP), 4261281279)
        self.assertEqual(palette.packed_rgba(palette.SKETCH_CONSTRUCTION), 1550569983)

    def test_dark_viewport_palette_is_readable_and_manages_the_same_keys(self):
        palette = self.palette_module()
        viewport = self.module("jellyjams.viewport")
        colors = palette.DARK_VIEWPORT_PALETTE
        self.assertEqual(set(colors), set(palette.VIEWPORT_PALETTE))
        for role, color in colors.items():
            if role.startswith("gradient_"):
                continue
            for background in (colors["gradient_top"], colors["gradient_bottom"]):
                minimum = 4.5 if "dimension" in role else 3.0
                self.assertGreaterEqual(w3c_contrast(color, background), minimum, role)
        self.assertEqual([(key, suffix) for key, suffix, _value in viewport.managed_keys(True)],
                         [(key, suffix) for key, suffix, _value in MANAGED_KEYS])

    def test_dark_viewport_round_trip_and_crash_recovery(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        app = STUBS.qapp
        self.addCleanup(app.setStyleSheet, app.styleSheet())
        app.setStyleSheet("* { background: #191919; color: #ffffff; }")
        view = param(P_VIEW)
        view.SetUnsigned("BackgroundColor2", 123456)
        view.SetUnsigned("ConstrainedDimColor", 654321)
        before = list(view.GetContents() or [])
        viewport.apply()
        for key, suffix, value in viewport.managed_keys(True):
            self.assertEqual(getattr(view, "Get" + suffix)(key), value, key)
        saved = param(P_OWN).GetString("OriginalViewColors")
        viewport.apply()
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors"), saved)
        viewport.restore()
        self.assertEqual(list(view.GetContents() or []), before)
        viewport.apply()
        # A fresh module must recover from the stable persisted backup alone.
        viewport = self.module("jellyjams.viewport", fresh=True)
        viewport.recover()
        self.assertEqual(list(view.GetContents() or []), before)
        self.assertFalse(param(P_OWN).GetString("OriginalViewColors"))

    def test_viewport_apply_restore_absent_keys(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        view = param(P_VIEW)
        view.SetString("NavigationStyle", "Gui::BlenderNavigationStyle")
        view.SetUnsigned("BackgroundColor", 1234)
        viewport.apply()
        self.assertTrue(viewport.is_applied())
        for key, suffix, value in MANAGED_KEYS:
            self.assertIn(key, getattr(view, "Get%ss" % suffix)(), key)
            self.assertEqual(getattr(view, "Get" + suffix)(key), value, key)
        record = json.loads(param(P_OWN).GetString("OriginalViewColors"))
        self.assertEqual(sorted(record), sorted(key for key, _s, _v in MANAGED_KEYS))
        for key, suffix, _value in MANAGED_KEYS:
            self.assertEqual(record[key], [suffix, False, None], key)
        viewport.restore()
        self.assertFalse(viewport.is_applied())
        self.assertManagedAbsent()
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")
        self.assertEqual(view.GetString("NavigationStyle"), "Gui::BlenderNavigationStyle")
        self.assertEqual(view.GetUnsigned("BackgroundColor"), 1234)
        self.assertNoJellyJamsProblems()

    def test_viewport_custom_values_and_type_presence(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        view = param(P_VIEW)
        view.SetUnsigned("BackgroundColor2", 123456)
        view.SetBool("Gradient", False)
        view.SetString("RadialGradient", "not a bool")
        viewport.apply()
        record = json.loads(param(P_OWN).GetString("OriginalViewColors"))
        self.assertEqual(record["BackgroundColor2"], ["Unsigned", True, 123456])
        self.assertEqual(record["Gradient"], ["Bool", True, False])
        self.assertEqual(record["RadialGradient"], ["Bool", False, None])
        STUBS.records.clear()
        counter = []
        for name in ("SetBool", "SetUnsigned"):
            original = getattr(view, name)
            setattr(view, name, lambda key, value, _o=original: (counter.append(key), _o(key, value))[1])
        viewport.apply()
        self.assertEqual(counter, [], "a second apply must not rewrite parameters")
        for name in ("SetBool", "SetUnsigned"):
            delattr(view, name)
        viewport.restore()
        self.assertEqual(view.GetUnsigned("BackgroundColor2"), 123456)
        self.assertIn("Gradient", view.GetBools())
        self.assertFalse(view.GetBool("Gradient", True))
        self.assertNotIn("RadialGradient", view.GetBools())
        self.assertEqual(view.GetString("RadialGradient"), "not a bool")

    def test_viewport_leftover_backup_not_overwritten(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        record = {name: [suffix, False, None] for name, suffix, _value in viewport.MANAGED_KEYS}
        record["BackgroundColor2"] = ["Unsigned", True, 123456]
        leftover = json.dumps(record)
        param(P_OWN).SetString("OriginalViewColors", leftover)
        viewport.apply()
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors"), leftover)
        self.assertEqual(param(P_VIEW).GetUnsigned("BackgroundColor2"), 4261281279)
        viewport.restore()
        self.assertEqual(param(P_VIEW).GetUnsigned("BackgroundColor2"), 123456)
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")

    def test_viewport_setter_failing_on_fifth_key(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        view = param(P_VIEW)
        writes = []
        for name in ("SetBool", "SetUnsigned"):
            original = getattr(view, name)

            def failing(key, value, _original=original):
                writes.append(key)
                if len(writes) == 5:
                    raise RuntimeError("parameter write refused by the harness")
                return _original(key, value)

            setattr(view, name, failing)
        viewport.apply()
        self.assertGreaterEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(self.jj("error"), [])
        self.assertTrue(param(P_OWN).GetString("OriginalViewColors", ""))
        for name in ("SetBool", "SetUnsigned"):
            delattr(view, name)
        viewport.restore()
        self.assertManagedAbsent()
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")

    def test_viewport_restore_failure_keeps_record(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        view = param(P_VIEW)
        viewport.apply()

        def refuse(_key):
            raise RuntimeError("remove refused by the harness")

        view.RemBool = refuse
        viewport.restore()
        self.assertGreaterEqual(len(self.jj("warning")), 1)
        self.assertTrue(param(P_OWN).GetString("OriginalViewColors", ""))
        del view.RemBool
        viewport.restore()
        self.assertManagedAbsent()
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")

    def test_viewport_recover(self):
        viewport = self.module("jellyjams.viewport", fresh=True)
        viewport.recover()
        self.assertEqual(self.lines(), [])
        param(P_OWN).SetString("OriginalViewColors", '{"Gradient": ["Bool", false, null]}')
        param(P_VIEW).SetBool("Gradient", True)
        viewport.recover()
        self.assertNotIn("Gradient", param(P_VIEW).GetBools())
        messages = " ".join(self.jj("message"))
        self.assertIn("3D background", messages)
        self.assertIn("unclean exit", messages)
        STUBS.records.clear()
        param(P_OWN).SetString("OriginalViewColors", "not json")
        param(P_VIEW).SetBool("Gradient", True)
        viewport.recover()
        self.assertEqual(len(self.jj("warning")), 1)
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")
        self.assertTrue(param(P_VIEW).GetBool("Gradient", False))
        STUBS.records.clear()
        param(P_OWN).SetString("OriginalViewColors", json.dumps({
            "Gradient": ["Bool", False, None], "Bogus": ["Colour", True, 1], "Short": ["Bool"]}))
        viewport.recover()
        self.assertNotIn("Gradient", param(P_VIEW).GetBools())
        self.assertGreaterEqual(len(self.jj("warning")), 1)
        self.assertEqual(param(P_OWN).GetString("OriginalViewColors", ""), "")


# ==========================================================================
# 11. Window layout
# ==========================================================================


class Test11Layout(HarnessCase):
    TOOLBARS = ("File", "Edit", "Workbench", "View", "Macro", "Structure", "Navigation")

    def setUp(self):
        super().setUp()
        self.ribbon_calls = []
        ribbon = fake_module(
            "jellyjams.ribbon",
            show_if_requested=make_recorder(self.ribbon_calls, "show_if_requested"),
            hide_if_not_requested=make_recorder(self.ribbon_calls, "hide_if_not_requested"),
            show=make_recorder(self.ribbon_calls, "show"),
            hide=make_recorder(self.ribbon_calls, "hide"),
            is_requested=lambda: False,
        )
        self.fakes({"jellyjams.ribbon": ribbon})
        self.layout = self.module("jellyjams.layout", fresh=True)
        self.addCleanup(self.quiet_revert)
        STUBS.set_active_workbench(WB)

    def quiet_revert(self):
        with contextlib.suppress(Exception):
            self.layout.revert()
        STUBS.pump(0)

    def build_window(self, visible=True):
        window = STUBS.new_main_window(visible=False)
        Area = QtCore.Qt.ToolBarArea
        self.toolbars = {}
        for name in self.TOOLBARS:
            toolbar = QtWidgets.QToolBar(name, window)
            toolbar.setObjectName(name)
            toolbar.addAction(name)
            window.addToolBar(Area.TopToolBarArea, toolbar)
            self.toolbars[name] = toolbar
        Dock = QtCore.Qt.DockWidgetArea
        self.docks = {}
        for name, area in (("Model", Dock.LeftDockWidgetArea), ("Tasks", Dock.LeftDockWidgetArea),
                           ("Report view", Dock.BottomDockWidgetArea),
                           ("Python console", Dock.BottomDockWidgetArea)):
            dock = QtWidgets.QDockWidget(name, window)
            dock.setObjectName(name)
            content = QtWidgets.QWidget()
            QtWidgets.QVBoxLayout(content)
            dock.setWidget(content)
            window.addDockWidget(area, dock)
            self.docks[name] = dock
        window.tabifyDockWidget(self.docks["Model"], self.docks["Tasks"])
        self.inner = QtWidgets.QToolBar("Inner", self.docks["Model"].widget())
        self.inner.setObjectName("HarnessInnerTools")
        self.docks["Model"].widget().layout().addWidget(self.inner)
        self.toolbars["Navigation"].hide()
        self.docks["Python console"].hide()
        if visible:
            window.show()
        STUBS.pump(20)
        return window

    def visible_main_toolbars(self, window):
        return sorted(tb.objectName() for tb in window.findChildren(QtWidgets.QToolBar)
                      if tb.isVisible() and window.toolBarArea(tb) != QtCore.Qt.ToolBarArea.NoToolBarArea)

    def test_kept_toolbar_matching(self):
        for name, kept in (("File", True), ("Edit", True), ("Workbench", True), ("file", True),
                           ("WORKBENCH", True), ("MyEditTools", True), ("View", False), ("Macro", False),
                           ("Sketcher", False), ("", False)):
            self.assertIs(bool(self.layout.is_kept_toolbar(name)), kept, name)

    def test_apply_hides_visible_non_kept_toolbars_only(self):
        window = self.build_window()
        model_area = window.dockWidgetArea(self.docks["Model"])
        self.layout.apply()
        self.assertTrue(self.layout.is_applied())
        self.assertTrue(self.layout._active)
        self.assertIsNotNone(self.layout._saved_state)
        self.assertEqual(self.visible_main_toolbars(window), ["Edit", "File", "Workbench"])
        self.assertTrue(self.toolbars["Navigation"].isHidden())
        self.assertTrue(self.inner.isVisible(), "toolbars inside docks are never touched")
        self.assertEqual(window.dockWidgetArea(self.docks["Model"]), model_area)
        self.assertTrue(any("Macro" in line for line in self.jj("log")), "no log line naming hidden toolbars")
        snapshot = self.layout._saved_state
        self.layout.apply()
        self.assertIs(self.layout._saved_state, snapshot, "a second apply must not take a new snapshot")

    def test_apply_docks_tasks_above_report_on_the_right(self):
        window = self.build_window()
        self.layout.apply()
        STUBS.pump(50)
        right = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        tasks, report = self.docks["Tasks"], self.docks["Report view"]
        for dock in (tasks, report):
            self.assertEqual(window.dockWidgetArea(dock), right, dock.objectName())
            self.assertFalse(dock.isFloating())
            self.assertTrue(dock.isVisible(), dock.objectName())
        self.assertNotIn(report, window.tabifiedDockWidgets(tasks))
        self.assertLess(tasks.geometry().top(), report.geometry().top())
        self.assertTrue(self.docks["Python console"].isHidden())

    def test_closed_report_stays_closed_through_apply_and_delayed_passes(self):
        window = self.build_window()
        report = self.docks["Report view"]
        report.hide()
        before = window.dockWidgetArea(report)
        self.layout.apply()
        for _ in range(2):
            self.layout._redock(self.layout._generation)
        self.assertTrue(report.isHidden())
        self.assertEqual(window.dockWidgetArea(report), before)
        self.assertTrue(self.docks["Tasks"].isVisible())
        self.layout.revert()
        STUBS.pump(450)
        self.assertTrue(report.isHidden())

    def test_report_closed_after_activation_is_not_reopened_by_redocking(self):
        self.build_window()
        report = self.docks["Report view"]
        self.layout.apply()
        report.hide()
        self.layout._redock(self.layout._generation)
        self.assertTrue(report.isHidden())
        report.show()
        self.layout._redock(self.layout._generation)
        self.assertTrue(report.isVisible(), "an explicitly reopened Report view stays open")

    def test_report_visibility_choice_survives_both_restore_passes(self):
        window = self.build_window()
        report = self.docks["Report view"]
        original_area = window.dockWidgetArea(report)
        for initially_visible in (True, False):
            with self.subTest(initially_visible=initially_visible):
                report.setVisible(initially_visible)
                self.layout.apply()
                report.setVisible(not initially_visible)
                self.layout.revert()
                self.assertEqual(report.isVisible(), not initially_visible)
                STUBS.pump(450)
                self.assertEqual(report.isVisible(), not initially_visible)
                self.assertEqual(window.dockWidgetArea(report), original_area)

    def test_delayed_pass_hides_late_toolbars_and_restores_them_once(self):
        window = self.build_window()
        self.layout.apply()
        self.toolbars["View"].show()
        late = QtWidgets.QToolBar("Late", window)
        late.setObjectName("HarnessLateTools")
        late.addAction("Late")
        window.addToolBar(late)
        late.show()
        self.layout._redock(self.layout._generation)
        self.assertTrue(late.isHidden())
        self.assertTrue(self.toolbars["View"].isHidden())
        self.assertTrue(self.toolbars["Navigation"].isHidden())
        self.assertTrue(self.inner.isVisible())
        self.toolbars["View"].show()
        self.layout._redock(self.layout._generation)
        self.assertEqual(sum(bar is self.toolbars["View"] for bar in self.layout._hidden), 1)
        self.layout.revert()
        self.assertTrue(late.isVisible())
        self.assertTrue(self.toolbars["View"].isVisible())
        self.assertTrue(self.toolbars["Navigation"].isHidden())

    def test_delayed_pass_leaves_the_next_workbenchs_toolbars_alone(self):
        self.build_window()
        self.layout.apply()
        self.toolbars["View"].show()
        STUBS.set_active_workbench("PartDesignWorkbench")
        self.layout._redock(self.layout._generation)
        self.assertTrue(self.toolbars["View"].isVisible())

    def test_stale_delayed_pass_does_not_hide_toolbars_after_reentry(self):
        self.build_window()
        self.layout.apply()
        previous = self.layout._generation
        self.layout.revert()
        self.layout.apply()
        self.toolbars["View"].show()
        self.layout._redock(previous)
        self.assertTrue(self.toolbars["View"].isVisible())

    def test_revert_restores_only_what_was_hidden(self):
        window = self.build_window()
        self.layout.apply()
        self.toolbars["Navigation"].show()
        self.toolbars["Edit"].hide()
        self.layout.revert()
        self.assertFalse(self.layout.is_applied())
        self.assertFalse(self.layout._active)
        for name in ("View", "Macro", "Structure", "File", "Workbench", "Navigation"):
            self.assertTrue(self.toolbars[name].isVisible(), name)
        self.assertTrue(self.toolbars["Edit"].isHidden(), "a kept toolbar hidden inside JellyJams stays hidden")
        STUBS.pump(450)
        self.assertTrue(self.toolbars["Navigation"].isVisible(), "the second pass must keep current visibility")
        self.assertTrue(self.toolbars["View"].isVisible())
        self.assertIn("hide_if_not_requested", [call[0] for call in self.ribbon_calls])
        self.assertEqual(self.jj("error"), [])

    def test_revert_restores_docks(self):
        window = self.build_window()
        report = self.docks["Report view"]
        report.setFloating(True)
        STUBS.pump(20)
        self.layout.apply()
        STUBS.pump(20)
        self.assertFalse(report.isFloating())
        self.layout.revert()
        STUBS.pump(450)
        self.assertTrue(report.isFloating())
        self.assertEqual(window.dockWidgetArea(self.docks["Tasks"]), QtCore.Qt.DockWidgetArea.LeftDockWidgetArea)
        self.assertIn(self.docks["Model"], window.tabifiedDockWidgets(self.docks["Tasks"]))
        self.assertTrue(self.docks["Python console"].isHidden())

    def test_second_restore_reopens_bars_hidden_late_by_freecad(self):
        window = self.build_window()
        self.layout.apply()
        self.layout.revert()
        # Native workbench handling can hide general bars after Deactivated.
        self.toolbars["View"].hide()
        self.toolbars["Edit"].hide()
        STUBS.pump(450)
        self.assertTrue(self.toolbars["View"].isVisible(), "restore a toolbar JellyJams hid")
        self.assertTrue(self.toolbars["Structure"].isVisible())
        self.assertFalse(self.toolbars["Edit"].isVisible(), "leave unrelated current visibility alone")

    def test_quick_reentry_is_not_undone_by_the_second_pass(self):
        window = self.build_window()
        self.layout.apply()
        self.layout.revert()
        STUBS.pump(30)
        self.layout.apply()
        STUBS.pump(600)
        self.assertTrue(self.layout.is_applied())
        self.assertEqual(self.visible_main_toolbars(window), ["Edit", "File", "Workbench"])

    def test_revert_when_not_applied_is_silent(self):
        self.build_window()
        self.layout.revert()
        STUBS.pump(300)
        self.assertEqual(self.jj(), [])

    def deferral_window(self):
        self.patch(self.layout, "DEFER_POLL_MS", 10)
        self.patch(self.layout, "DEFER_POLL_LIMIT", 8)
        return self.build_window(visible=False)

    def test_deferral_cancelled_by_revert(self):
        window = self.deferral_window()
        self.layout.apply()
        self.assertTrue(self.layout.is_deferred())
        self.assertFalse(self.layout._active)
        self.assertIsNone(self.layout._saved_state)
        self.layout.revert()
        self.assertFalse(self.layout.is_deferred())
        window.show()
        STUBS.pump(200)
        self.assertFalse(self.layout._active)
        self.assertIsNone(self.layout._saved_state)
        self.assertTrue(self.toolbars["View"].isVisible())
        self.assertNotIn("show_if_requested", [call[0] for call in self.ribbon_calls])

    def test_deferral_cancelled_by_workbench_switch(self):
        window = self.deferral_window()
        self.layout.apply()
        STUBS.set_active_workbench("PartDesignWorkbench")
        window.show()
        STUBS.pump(200)
        self.assertFalse(self.layout._active)
        self.assertFalse(self.layout.is_deferred())
        self.assertTrue(self.toolbars["View"].isVisible())
        self.assertEqual(self.jj("warning"), [])

    def test_deferred_apply_runs_once_the_window_is_shown(self):
        window = self.deferral_window()
        self.patch(self.layout, "DEFER_POLL_LIMIT", 200)
        self.layout.apply()
        self.assertFalse(self.layout._active)
        window.show()
        self.assertTrue(STUBS.wait_until(lambda: self.layout._active, 1500))
        self.assertIsNotNone(self.layout._saved_state)
        self.assertEqual(self.visible_main_toolbars(window), ["Edit", "File", "Workbench"])
        self.assertIn("show_if_requested", [call[0] for call in self.ribbon_calls])

    def test_deferral_timeout_warns_once_and_changes_nothing(self):
        self.deferral_window()
        self.layout.apply()
        STUBS.pump(400)
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertFalse(self.layout._active)
        self.assertFalse(self.layout.is_deferred())
        for name in ("View", "Macro", "Structure"):
            self.assertFalse(self.toolbars[name].isHidden(), name)

    def test_missing_tasks_dock_warns_and_still_hides_toolbars(self):
        window = self.build_window()
        self.docks["Tasks"].setObjectName("HarnessRenamedPanel")
        report_area = window.dockWidgetArea(self.docks["Report view"])
        self.layout.apply()
        warnings = self.jj("warning")
        self.assertEqual(len(warnings), 1, self.lines())
        self.assertIn("Report view", warnings[0])
        self.assertEqual(self.visible_main_toolbars(window), ["Edit", "File", "Workbench"])
        self.assertEqual(window.dockWidgetArea(self.docks["Report view"]), report_area)


# ==========================================================================
# 12. Navigation and shortcuts
# ==========================================================================


class Test12NavigationShortcuts(HarnessCase):

    def test_orbit_drag_uses_the_shorter_dimension_on_both_axes(self):
        rules = self.module("jellyjams.orbit_rules")
        for width, height in ((1001, 1001), (4001, 1001), (1001, 4001)):
            with self.subTest(size=(width, height)):
                drag = rules.OrbitDrag(0, 0)
                x, y = drag.move(100, 100, width, height)
                self.assertAlmostEqual(x / (width - 1), 0.1)
                self.assertAlmostEqual(y / (height - 1), 0.1)

    def test_orbit_drag_modifier_changes_preserve_native_pan_deltas(self):
        rules = self.module("jellyjams.orbit_rules")
        drag = rules.OrbitDrag(100, 100)
        self.assertEqual(drag.move(120, 110, 4001, 1001), (180, 110))
        # Ctrl-pan starts from the same virtual position, with physical deltas.
        self.assertEqual(drag.move(125, 115, 4001, 1001, orbit=False), (185, 115))
        self.assertEqual(drag.move(130, 120, 4001, 1001), (205, 120))
        self.assertEqual(drag.move(130, 120, 4001, 1001, orbit=False), (205, 120))

    def test_orbit_drag_negative_motion_resize_and_degenerate_sizes(self):
        rules = self.module("jellyjams.orbit_rules")
        drag = rules.OrbitDrag(100, 100)
        self.assertEqual(drag.move(90, 80, 4001, 1001), (60, 80))
        self.assertEqual(drag.move(90, 70, 1001, 4001), (60, 40))
        self.assertEqual(drag.move(90, 70, 0, 0), (60, 40))

    def test_orbit_filter_scope_and_lifecycle(self):
        orbit = self.module("jellyjams.orbit", fresh=True)
        self.addCleanup(orbit.uninstall)
        orbit.install()
        first = orbit._filter
        self.assertIsNotNone(first)
        orbit.install()
        self.assertIs(orbit._filter, first)
        self.assertFalse(orbit._is_viewport(QtWidgets.QWidget()))
        orbit.uninstall()
        self.assertIsNone(orbit._filter)
        self.assertFalse(first.running)
        self.assertFalse(first.watched)
        self.assertFalse(first.timer.isActive())
        orbit.uninstall()

    def test_navigation_recovery_removes_runtime_orbit_filter(self):
        orbit = self.module("jellyjams.orbit")
        self.addCleanup(orbit.uninstall)
        self.navigation.install()
        self.assertIsNotNone(orbit._filter)
        self.navigation.recover()
        self.assertIsNone(orbit._filter)
        self.assertFalse(self.navigation.is_installed())

    def test_orbit_focus_discovery_is_deferred_coalesced_and_cancelled_on_stop(self):
        orbit = self.module("jellyjams.orbit", fresh=True)
        self.addCleanup(orbit.uninstall)
        orbit.install()
        watcher = orbit._filter
        calls = []
        # The focus callback must schedule discovery without traversing widgets
        # while a native task control may still be inside its destructor.
        self.patch(watcher, "refresh", lambda: calls.append("scanned"))
        watcher.focus_timer.timeout.disconnect()
        watcher.focus_timer.timeout.connect(watcher.refresh)
        watcher.schedule_refresh()
        watcher.schedule_refresh()
        self.assertEqual(calls, [])
        STUBS.qapp.processEvents()
        self.assertEqual(calls, ["scanned"])
        watcher.schedule_refresh()
        orbit.uninstall()
        STUBS.qapp.processEvents()
        self.assertEqual(calls, ["scanned"])

    def setUp(self):
        super().setUp()
        self.navigation = self.module("jellyjams.navigation", fresh=True)
        self.shortcuts = self.module("jellyjams.shortcuts", fresh=True)
        STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS + list(DEFAULT_KEY_OWNERS) + [ALIGN_CMD],
                           shortcuts=DEFAULT_KEY_OWNERS)

    def test_shortcut_table(self):
        self.assertEqual([tuple(entry) for entry in self.shortcuts.SHORTCUTS], EXPECTED_SHORTCUTS)
        self.assertEqual(len({cmd for cmd, _keys in EXPECTED_SHORTCUTS}), len(EXPECTED_SHORTCUTS), "one key per command")
        self.assertEqual(len({keys.lower() for _cmd, keys in EXPECTED_SHORTCUTS}), len(EXPECTED_SHORTCUTS),
                         "no key is used twice")
        self.assertEqual(dict(self.shortcuts.SHORTCUTS)[NORMAL_TO_CMD], "Ctrl+8", "Ctrl+8 is JellyJams' Normal To")
        self.assertNotIn(ALIGN_CMD, dict(self.shortcuts.SHORTCUTS))

    def test_navigation_absent_key_round_trip(self):
        self.navigation.install()
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
        self.assertEqual(json.loads(param(P_OWN).GetString("OriginalNavigationStyle")), {"existed": False, "value": None})
        self.navigation.install()
        self.navigation.uninstall()
        self.assertNotIn("NavigationStyle", param(P_VIEW).GetStrings())
        self.assertEqual(param(P_OWN).GetString("OriginalNavigationStyle", ""), "")

    def test_navigation_user_style_round_trip(self):
        param(P_VIEW).SetString("NavigationStyle", "Gui::BlenderNavigationStyle")
        self.navigation.install()
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
        self.navigation.uninstall()
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), "Gui::BlenderNavigationStyle")

    def test_navigation_leftover_backup_not_overwritten(self):
        leftover = json.dumps({"existed": True, "value": "Gui::OpenInventorNavigationStyle"})
        param(P_OWN).SetString("OriginalNavigationStyle", leftover)
        param(P_VIEW).SetString("NavigationStyle", "Gui::CADNavigationStyle")
        self.navigation.install()
        self.assertEqual(param(P_OWN).GetString("OriginalNavigationStyle"), leftover)
        self.navigation.uninstall()
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), "Gui::OpenInventorNavigationStyle")

    def test_shortcuts_round_trip_with_user_override_and_conflict(self):
        group = param(P_SHORTCUT)
        group.SetString("Std_ViewTop", "T")
        group.SetString("Std_Unrelated", "Ctrl+U")
        self.shortcuts.install()
        expected = dict(self.shortcuts.SHORTCUTS)
        for command, keys in expected.items():
            self.assertEqual(group.GetString(command), keys, command)
        for owner in DEFAULT_KEY_OWNERS:
            self.assertIn(owner, group.GetStrings())
            self.assertEqual(group.GetString(owner), "", owner)
        backup = json.loads(param(P_OWN).GetString("OriginalShortcuts"))
        self.assertEqual(backup["Std_ViewTop"], [True, "T"])
        self.assertEqual(backup["Std_ViewFitAll"], [False, None])
        self.assertEqual(backup["Std_ToggleVisibility"], [False, None])
        self.shortcuts.uninstall()
        self.assertEqual(group.GetString("Std_ViewTop"), "T")
        self.assertEqual(group.GetString("Std_Unrelated"), "Ctrl+U")
        for command in expected:
            if command != "Std_ViewTop":
                self.assertNotIn(command, group.GetStrings(), command)
        for owner, keys in DEFAULT_KEY_OWNERS.items():
            self.assertNotIn(owner, group.GetStrings(), owner)
            self.assertEqual(STUBS.gui.Command.get(owner).getShortcut(), keys, "built-in key is live again")
        self.assertEqual(param(P_OWN).GetString("OriginalShortcuts", ""), "")

    def test_shortcuts_leftover_backup_not_overwritten(self):
        leftover = json.dumps({"Std_ViewFront": [True, "1"]})
        param(P_OWN).SetString("OriginalShortcuts", leftover)
        self.shortcuts.install()
        self.assertEqual(param(P_OWN).GetString("OriginalShortcuts"), leftover)
        self.shortcuts.uninstall()
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFront"), "1")
        for command in dict(self.shortcuts.SHORTCUTS):
            if command != "Std_ViewFront":
                self.assertNotIn(command, param(P_SHORTCUT).GetStrings(), command)
        self.assertNotIn("Std_ViewBoxZoom", param(P_SHORTCUT).GetStrings())
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())

    def test_backups_are_removed_after_restore(self):
        self.navigation.install()
        self.shortcuts.install()
        self.assertTrue(self.navigation.is_installed())
        self.assertTrue(self.shortcuts.is_installed())
        self.navigation.uninstall()
        self.shortcuts.uninstall()
        self.assertFalse(self.navigation.is_installed())
        self.assertFalse(self.shortcuts.is_installed())
        for key in ("OriginalNavigationStyle", "OriginalShortcuts"):
            self.assertNotIn(key, param(P_OWN).GetStrings(), key)
            self.assertEqual(param(P_OWN).GetString(key, ""), "")
        self.assertEqual(self.navigation.STYLE_KEY, "NavigationStyle")
        self.assertEqual(self.navigation.SW_STYLE, SW_NAV)
        self.assertNoJellyJamsProblems()

    def test_shortcuts_unbind_clashing_commands_and_restore_them(self):
        group = param(P_SHORTCUT)
        STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS + ["Std_ViewBoxZoom", "Std_ToggleVisibility",
                                                                       "Std_HarnessPick", "Std_HarnessOther"],
                           shortcuts={"Std_ViewBoxZoom": "ctrl+b", "Std_ViewTop": "Ctrl+5",
                                      "Std_ToggleVisibility": "space", "Std_HarnessOther": "Ctrl+9"})
        group.SetString("Std_HarnessPick", "shift+z")
        self.shortcuts.install()
        self.assertTrue(self.shortcuts.is_installed())
        for command, keys in dict(self.shortcuts.SHORTCUTS).items():
            self.assertEqual(group.GetString(command), keys, command)
        self.assertEqual(group.GetString("Std_ViewBoxZoom", "missing"), "")
        self.assertEqual(group.GetString("Std_ToggleVisibility", "missing"), "", "space is the same key as Space")
        self.assertEqual(group.GetString("Std_HarnessPick"), "")
        self.assertNotIn("Std_HarnessOther", group.GetStrings())
        backup = json.loads(param(P_OWN).GetString("OriginalShortcuts"))
        self.assertEqual(list(backup)[:3], ["Std_HarnessPick", "Std_ToggleVisibility", "Std_ViewBoxZoom"],
                         "clashing commands are recorded before JellyJams' own commands")
        self.assertEqual(backup["Std_ViewBoxZoom"], [False, None])
        self.assertEqual(backup["Std_ToggleVisibility"], [False, None])
        self.assertEqual(backup["Std_HarnessPick"], [True, "shift+z"])
        self.assertNotIn("Std_HarnessOther", backup)
        logs = " ".join(self.jj("log"))
        self.assertIn("Std_ViewBoxZoom", logs)
        self.assertIn("Std_ToggleVisibility", logs)
        self.assertIn("Std_HarnessPick", logs)
        self.assertNoJellyJamsProblems()
        self.shortcuts.uninstall()
        self.assertFalse(self.shortcuts.is_installed())
        self.assertNotIn("Std_ViewBoxZoom", group.GetStrings())
        self.assertNotIn("Std_ToggleVisibility", group.GetStrings())
        self.assertEqual(group.GetString("Std_HarnessPick"), "shift+z")
        for command in dict(self.shortcuts.SHORTCUTS):
            self.assertNotIn(command, group.GetStrings(), command)
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())

    def test_space_moves_from_show_hide_to_view_orientation(self):
        cases = [
            ("built-in Space", None, True),             # FreeCAD 1.1 default: no override, key Space
            ("user set Space explicitly", "Space", True),
            ("user moved Show/Hide to H", "H", False),
            ("user unbound Show/Hide", "", False),
        ]
        for label, override, clashes in cases:
            with self.subTest(label):
                STUBS.reset()
                STUBS.set_commands(SHORTCUT_COMMANDS + JJ_SHORTCUT_COMMANDS + list(DEFAULT_KEY_OWNERS),
                                   shortcuts=DEFAULT_KEY_OWNERS)
                group = param(P_SHORTCUT)
                toggle = STUBS.gui.Command.get("Std_ToggleVisibility")
                if override is not None:
                    group.SetString("Std_ToggleVisibility", override)
                before = toggle.getShortcut()
                self.shortcuts.install()
                self.assertEqual(STUBS.gui.Command.get(ORIENTATION_CMD).getShortcut(), "Space")
                self.assertEqual(STUBS.gui.Command.get(NORMAL_TO_CMD).getShortcut(), "Ctrl+8")
                self.assertNotIn(ALIGN_CMD, group.GetStrings(), "FreeCAD's Align to selection is not touched")
                self.assertEqual(toggle.getShortcut(), "" if clashes else before)
                self.shortcuts.uninstall()
                self.assertEqual(toggle.getShortcut(), before)
                if override is None:
                    self.assertNotIn("Std_ToggleVisibility", group.GetStrings())
                else:
                    self.assertEqual(group.GetString("Std_ToggleVisibility"), override)
                for command in JJ_SHORTCUT_COMMANDS + [ALIGN_CMD]:
                    self.assertNotIn(command, group.GetStrings(), command)
                self.assertNoJellyJamsProblems()

    def test_space_is_left_alone_without_view_orientation(self):
        # JellyJams' own command missing (for example its registration failed): its key is not
        # set, so Show/Hide keeps Space.
        STUBS.set_commands(SHORTCUT_COMMANDS + list(DEFAULT_KEY_OWNERS), shortcuts=DEFAULT_KEY_OWNERS)
        self.shortcuts.install()
        for command in JJ_SHORTCUT_COMMANDS:
            self.assertNotIn(command, param(P_SHORTCUT).GetStrings(), command)
        self.assertNotIn("Std_ToggleVisibility", param(P_SHORTCUT).GetStrings())
        self.assertEqual(STUBS.gui.Command.get("Std_ToggleVisibility").getShortcut(), "Space")
        self.assertTrue(any(ORIENTATION_CMD in line for line in self.jj("log")), self.lines())
        self.assertTrue(any(NORMAL_TO_CMD in line for line in self.jj("log")), self.lines())
        self.shortcuts.uninstall()
        self.assertEqual(param(P_SHORTCUT).GetStrings(), [])

    def test_space_and_ctrl8_recovered_after_a_crash(self):
        param(P_SHORTCUT).SetString(ALIGN_CMD, "Shift+A")          # the user's own key for Align to selection
        self.shortcuts.install()
        self.assertEqual(param(P_SHORTCUT).GetString(ORIENTATION_CMD), "Space")
        self.assertEqual(param(P_SHORTCUT).GetString(NORMAL_TO_CMD), "Ctrl+8")
        shortcuts = self.module("jellyjams.shortcuts", fresh=True)   # a new session: nothing in memory
        shortcuts.recover()
        for command in (ORIENTATION_CMD, NORMAL_TO_CMD, "Std_ToggleVisibility", "Std_ViewBoxZoom"):
            self.assertNotIn(command, param(P_SHORTCUT).GetStrings(), command)
        self.assertEqual(param(P_SHORTCUT).GetString(ALIGN_CMD), "Shift+A", "never part of the backup")
        self.assertEqual(STUBS.gui.Command.get("Std_ToggleVisibility").getShortcut(), "Space")
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())
        self.assertTrue(any("shortcuts" in line for line in self.jj("message")), self.lines())

    def test_user_ctrl8_on_align_to_selection_is_unbound_and_given_back(self):
        group = param(P_SHORTCUT)
        group.SetString(ALIGN_CMD, "Ctrl+8")
        self.shortcuts.install()
        self.assertEqual(group.GetString(NORMAL_TO_CMD), "Ctrl+8")
        self.assertEqual(group.GetString(ALIGN_CMD, "missing"), "", "Qt runs neither of two actions on one key")
        self.assertEqual(json.loads(param(P_OWN).GetString("OriginalShortcuts"))[ALIGN_CMD], [True, "Ctrl+8"])
        self.shortcuts.uninstall()
        self.assertEqual(group.GetString(ALIGN_CMD), "Ctrl+8")
        self.assertNotIn(NORMAL_TO_CMD, group.GetStrings())
        self.assertNoJellyJamsProblems()

    def write_cfg(self, overrides):
        """A user.cfg as FreeCAD writes it, holding `overrides` in Preferences/Shortcut."""
        root = ET.Element("FCParameters")
        group = ET.SubElement(root, "FCParamGroup", Name="Root")
        for name in ("BaseApp", "Preferences", "Shortcut"):
            group = ET.SubElement(group, "FCParamGroup", Name=name)
        for command, keys in overrides.items():
            ET.SubElement(group, "FCText", Name=command).text = keys
        path = os.path.join(self.tmpdir(), "user.cfg")
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def run_cfg_check(self, path):
        checker = self.module("check_saved_cfg")
        self.patch(sys, "argv", ["check_saved_cfg.py", path, "-", "-", "-", "-"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as exit_info:
            checker.main()
        return exit_info.exception.code, json.loads(out.getvalue())

    def test_saved_cfg_check_looks_for_every_jellyjams_key(self):
        checker = self.module("check_saved_cfg")
        touched = {cmd for cmd, _keys in EXPECTED_SHORTCUTS if cmd in JJ_SHORTCUT_COMMANDS}
        touched |= set(DEFAULT_KEY_OWNERS) | {ALIGN_CMD}   # FreeCAD's Normal To must stay untouched too
        self.assertLessEqual(touched, set(checker.JELLYJAMS_SHORTCUTS))
        code, report = self.run_cfg_check(self.write_cfg({"Std_Unrelated": "Ctrl+U"}))
        self.assertEqual((code, report["checks"]["no_jj_shortcut_overrides"]), (0, True), report)
        for command in sorted(touched):
            with self.subTest(command=command):
                code, report = self.run_cfg_check(self.write_cfg({command: ""}))
                self.assertEqual((code, report["checks"]["no_jj_shortcut_overrides"]), (1, False), report)

    def test_shortcuts_for_missing_commands_are_skipped(self):
        STUBS.set_commands([c for c in SHORTCUT_COMMANDS if c != "Std_Refresh"])
        self.shortcuts.install()
        self.assertNotIn("Std_Refresh", param(P_SHORTCUT).GetStrings())
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFitAll"), "F")
        self.assertTrue(any("Std_Refresh" in line for line in self.jj("log")), self.lines())
        self.assertNoJellyJamsProblems()
        self.shortcuts.uninstall()
        self.assertEqual(param(P_SHORTCUT).GetStrings(), [])

    def test_shortcuts_without_a_command_list_set_every_key(self):
        def broken():
            raise RuntimeError("listCommands broken by the harness")

        self.patch(STUBS.gui, "listCommands", broken)
        self.shortcuts.install()
        for command, keys in dict(self.shortcuts.SHORTCUTS).items():
            self.assertEqual(param(P_SHORTCUT).GetString(command), keys, command)
        self.assertEqual(len(self.jj("log")), 1, self.lines())
        self.assertNoJellyJamsProblems()
        self.shortcuts.uninstall()
        self.assertEqual(param(P_SHORTCUT).GetStrings(), [])

    def test_partial_shortcut_restore_keeps_the_backup(self):
        group = param(P_SHORTCUT)
        self.shortcuts.install()

        def refuse(name, _real=group.RemString):
            if name == "Std_ViewFitAll":
                raise RuntimeError("remove refused by the harness")
            return _real(name)

        group.RemString = refuse
        self.shortcuts.uninstall()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertTrue(param(P_OWN).GetString("OriginalShortcuts", ""), "the backup must survive a failed restore")
        self.assertNotIn("Std_ViewTop", group.GetStrings())
        del group.RemString
        STUBS.records.clear()
        self.shortcuts.uninstall()
        self.assertEqual(group.GetStrings(), [])
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())
        self.assertNoJellyJamsProblems()

    def test_unreadable_backups_found_at_install_are_replaced(self):
        param(P_OWN).SetString("OriginalNavigationStyle", "{not json")
        param(P_VIEW).SetString("NavigationStyle", "Gui::BlenderNavigationStyle")
        self.navigation.install()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(json.loads(param(P_OWN).GetString("OriginalNavigationStyle")),
                         {"existed": True, "value": "Gui::BlenderNavigationStyle"})
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
        self.navigation.uninstall()
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), "Gui::BlenderNavigationStyle")
        STUBS.records.clear()
        param(P_OWN).SetString("OriginalShortcuts", '["not", "a", "record"]')
        param(P_SHORTCUT).SetString("Std_ViewTop", "T")
        self.shortcuts.install()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(json.loads(param(P_OWN).GetString("OriginalShortcuts"))["Std_ViewTop"], [True, "T"])
        self.shortcuts.uninstall()
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewTop"), "T")
        self.assertEqual(len(self.jj("warning")), 1, self.lines())

    def test_unreadable_backups_found_at_uninstall_change_nothing(self):
        param(P_VIEW).SetString("NavigationStyle", SW_NAV)
        param(P_OWN).SetString("OriginalNavigationStyle", '{"value": 3}')
        self.navigation.uninstall()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(param(P_VIEW).GetString("NavigationStyle"), SW_NAV)
        self.assertNotIn("OriginalNavigationStyle", param(P_OWN).GetStrings())
        STUBS.records.clear()
        param(P_SHORTCUT).SetString("Std_ViewTop", "Ctrl+5")
        param(P_OWN).SetString("OriginalShortcuts", "not json")
        self.shortcuts.uninstall()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewTop"), "Ctrl+5")
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())

    def test_malformed_shortcut_entries_are_skipped(self):
        param(P_SHORTCUT).SetString("Std_ViewTop", "Ctrl+5")
        param(P_SHORTCUT).SetString("Std_ViewFront", "Ctrl+1")
        param(P_OWN).SetString("OriginalShortcuts", json.dumps({
            "Std_ViewTop": [True, "T"], "Std_ViewFront": "Ctrl+1", "Std_ViewRear": [True, None]}))
        self.shortcuts.uninstall()
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertIn("Std_ViewFront", self.jj("warning")[0])
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewTop"), "T")
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewFront"), "Ctrl+1")
        self.assertEqual(param(P_SHORTCUT).GetString("Std_ViewRear", "missing"), "", "[true, null] means unbound")
        self.assertNotIn("OriginalShortcuts", param(P_OWN).GetStrings())


# ==========================================================================
# 13. Ribbon: model, text and an offscreen build
# ==========================================================================


class Test13RibbonModel(HarnessCase):
    def setUp(self):
        super().setUp()
        self.layout_data = self.module("jellyjams.ribbon_layout")
        self.model = self.module("jellyjams.ribbon_model")

    def resolve(self, available=None):
        if available is None:
            available = ribbon_command_ids()
        return self.model.resolve(self.layout_data.TABS, set(available))

    def items(self, items):
        for item in items:
            if isinstance(item, self.model.RStack):
                yield from self.items(item.cells)
            else:
                yield item

    def tab(self, resolved, title):
        return [tab for tab in resolved.tabs if tab.title == title][0]

    def stacks(self, tab):
        return [item for group in tab.groups for item in group.items if isinstance(item, self.model.RStack)]

    def all_items(self, resolved):
        buttons, flyouts, toggles = {}, {}, []
        for tab in resolved.tabs:
            for group in tab.groups:
                for item in self.items(group.items):
                    if isinstance(item, self.model.RButton):
                        buttons[item.entry_id] = item
                    elif isinstance(item, self.model.RFlyout):
                        flyouts[item.flyout_id] = item
                    elif isinstance(item, self.model.RToggle):
                        toggles.append(item)
        return buttons, flyouts, toggles

    def test_counts_ids_and_tabs(self):
        resolved = self.resolve()
        self.assertEqual([tab.title for tab in resolved.tabs], ["Features", "Sketch", "Evaluate", "Assembly", "Drawing"])
        self.assertEqual(len(resolved.plain_ids()), RIBBON_TOTALS["plain"])
        self.assertEqual(len(resolved.flyouts()), RIBBON_TOTALS["flyouts"])
        self.assertEqual(sum(len(variants) for _id, variants in resolved.flyouts()), RIBBON_TOTALS["variants"])
        self.assertEqual([list(variants) for variants in resolved.toggles()], [RIBBON_TOGGLE])
        all_ids = list(resolved.all_ids())
        self.assertEqual(len(all_ids), RIBBON_TOTALS["entry_ids"])
        self.assertEqual(len(set(all_ids)), RIBBON_TOTALS["entry_ids"])
        self.assertEqual(list(resolved.skipped), [])
        self.assertEqual(list(resolved.substitutions), [])
        self.assertEqual(list(resolved.plain_ids()), [i for ids in RIBBON_PLAIN.values() for i in ids])
        self.assertEqual([(fid, list(variants)) for fid, variants in resolved.flyouts()], list(RIBBON_FLYOUTS.items()))
        self.assertNotIn("Assembly_CreateAssembly", all_ids)
        self.assertIn("JellyJams_Diagnostics", resolved.plain_ids())
        # The totals of the per-tab table and the overall numbers agree.
        self.assertEqual(sum(c[0] for c in RIBBON_TAB_COUNTS.values()), RIBBON_TOTALS["plain"])
        self.assertEqual(sum(c[1] for c in RIBBON_TAB_COUNTS.values()), RIBBON_TOTALS["flyouts"])
        self.assertEqual(sum(c[2] for c in RIBBON_TAB_COUNTS.values()), RIBBON_TOTALS["variants"])

    def test_layout_primary_ids_are_the_command_set(self):
        commands = list(self.layout_data.iter_commands())
        self.assertEqual({c.cmd for c in commands}, ribbon_command_ids())
        entries = [self.model.entry_id(c.cmd, c.index) for c in commands]
        self.assertEqual(len(entries), len(set(entries)), "an entry id appears twice in the layout")
        fallbacks = {c.cmd: tuple(c.fallbacks) for c in commands if c.fallbacks}
        self.assertEqual(fallbacks, {cmd: (fallback,) for cmd, fallback in RIBBON_FALLBACKS.items()})
        self.assertFalse(set(RIBBON_FALLBACKS.values()) & ribbon_command_ids(), "fallbacks are not primary ids")

    def test_layout_constructors_validate_input(self):
        layout = self.layout_data
        with self.assertRaises(ValueError):
            layout.Cmd("", "Empty")
        with self.assertRaises(ValueError):
            layout.Flyout([])
        with self.assertRaises(ValueError):
            layout.Stack("grid", [layout.Cmd("Std_ViewTop", "Top")])
        for style in ("text", "icon"):
            self.assertEqual(layout.Stack(style, []).style, style)
        broken = [layout.Tab("Broken", [layout.Group("Group", ["not an entry"])])]
        with self.assertRaises(TypeError):
            self.model.resolve(broken, set())

    def test_per_tab_counts_and_separators(self):
        resolved = self.resolve()
        for title, (plain, flyouts, variants, toggles, separators) in RIBBON_TAB_COUNTS.items():
            with self.subTest(tab=title):
                tab = self.tab(resolved, title)
                items = [item for group in tab.groups for item in self.items(group.items)]
                buttons = [item for item in items if isinstance(item, self.model.RButton)]
                fly = [item for item in items if isinstance(item, self.model.RFlyout)]
                tog = [item for item in items if isinstance(item, self.model.RToggle)]
                self.assertEqual([b.entry_id for b in buttons], RIBBON_PLAIN[title])
                self.assertEqual((len(buttons), len(fly), sum(len(f.variants) for f in fly), len(tog)),
                                 (plain, flyouts, variants, toggles))
                self.assertEqual(resolved.separators(title), separators)

    def test_stacks(self):
        resolved = self.resolve()
        expected = {"Features": [("text", 3)] * 4,
                    "Sketch": [("icon", 10), ("text", 3), ("text", 4)],
                    "Evaluate": [("icon", 9), ("text", 3), ("text", 6)],
                    "Assembly": [("text", 2), ("text", 3)],
                    "Drawing": [("text", 3)] * 5 + [("icon", 5)]}
        for title, stacks in expected.items():
            with self.subTest(tab=title):
                self.assertEqual([(s.style, len(s.cells)) for s in self.stacks(self.tab(resolved, title))], stacks)

        def cell_ids(stack):
            return [cell.flyout_id if isinstance(cell, self.model.RFlyout) else cell.entry_id for cell in stack.cells]

        sketch_stacks = self.stacks(self.tab(resolved, "Sketch"))
        self.assertEqual(cell_ids(sketch_stacks[0]), [
            "Sketcher_CreateLine", "Sketcher_CreateRectangle", "Sketcher_CreateSlot", "Sketcher_CreateCircle",
            "Sketcher_CreateArc", "Sketcher_CreateRegularPolygon", "Sketcher_CreateBSplineByInterpolation",
            "Sketcher_CreateEllipseByCenter", "Sketcher_CreateFillet", "Sketcher_CreatePoint"])
        move = sketch_stacks[1].cells[1]
        self.assertIsInstance(move, self.model.RFlyout)
        self.assertEqual(move.variants[0].one_line, "Move Entities")
        self.assertEqual(cell_ids(self.stacks(self.tab(resolved, "Evaluate"))[0]), [
            "Std_ViewFront", "Std_ViewTop", "Std_ViewRight", "Std_ViewRear", "Std_ViewBottom", "Std_ViewLeft",
            "Std_ViewIsometric", "Std_ViewDimetric", "Std_ViewTrimetric"])
        self.assertEqual(cell_ids(self.stacks(self.tab(resolved, "Drawing"))[-1]), [
            "JellyJams_LineOnSheet", "JellyJams_CornerRectangleOnSheet", "JellyJams_CircleOnSheet", "JellyJams_CenterpointArcOnSheet",
            "JellyJams_PolygonOnSheet"])

    def test_labels_icons_and_indices(self):
        buttons, flyouts, toggles = self.all_items(self.resolve())
        pad = buttons["PartDesign_Pad"]
        self.assertEqual((pad.cmd, pad.index, pad.label, pad.one_line), ("PartDesign_Pad", None, "Extruded\nBoss/Base",
                                                                       "Extruded Boss/Base"))
        self.assertIsNone(pad.jj_icon)
        for index, icon in ((6, "DrawStyleFlatLines"), (5, "DrawStyleShaded"), (3, "DrawStyleHiddenLine"),
                            (2, "DrawStyleWireFrame")):
            button = buttons["Std_DrawStyle#%d" % index]
            self.assertEqual((button.cmd, button.index, button.fc_icon), ("Std_DrawStyle", index, icon))
        self.assertEqual(buttons["Std_DrawStyle#2"].one_line, "Wireframe")
        labels = {"PartDesign_Hole": "Hole\nWizard", "PartDesign_Groove": "Revolved\nCut",
                  "Sketcher_Dimension": "Smart\nDimension", "Sketcher_Symmetry": "Mirror Entities",
                  "Std_DrawStyle#6": "Shaded With Edges", "TechDraw_ProjectionGroup": "Standard\n3 View",
                  "JellyJams_SaveAsPDF": "Save as\nPDF", "JellyJams_SaveAsDXF": "Save as\nDXF", "JellyJams_ViewScale": "View Scale",
                  "JellyJams_CornerRectangleOnSheet": "Corner Rectangle", "JellyJams_CenterpointArcOnSheet": "Centerpoint Arc",
                  "JellyJams_Diagnostics": "Diagnostics"}
        self.assertEqual({entry: buttons[entry].label for entry in labels}, labels)
        mate = flyouts["Assembly_CreateJointDistance"]
        concentric = [v for v in mate.variants if v.entry_id == "Assembly_CreateJointCylindrical"][0]
        self.assertEqual(concentric.one_line, "Concentric")
        self.assertNotIn("Assembly_CreateJointCylindrical", buttons, "Concentric lives in the Mate flyout")
        self.assertNotIn("Sketcher_CreateBSpline", buttons, "Style Spline lives in the spline flyout")
        copy = buttons["JellyJams_MakeDrawing#1"]
        self.assertEqual((copy.cmd, copy.index, copy.jj_icon), ("JellyJams_MakeDrawing", 1, "make_drawing"))
        self.assertEqual(buttons["JellyJams_MakeDrawing"].jj_icon, "make_drawing")
        self.assertEqual(buttons["JellyJams_Diagnostics"].jj_icon, "diagnostics")
        normal_to = buttons["JellyJams_NormalTo"]
        self.assertEqual((normal_to.cmd, normal_to.label, normal_to.jj_icon), ("JellyJams_NormalTo", "Normal To",
                                                                               "normal_to"))
        self.assertEqual((buttons["Sketcher_ViewSketch"].label, buttons["Sketcher_ViewSketch"].jj_icon),
                         ("Normal To", None), "the Sketch tab keeps FreeCAD's View sketch")
        self.assertNotIn("Std_AlignToSelection", buttons, "JellyJams' Normal To replaces Align to selection")
        for shape in SHEET_SHAPES.values():
            self.assertEqual(buttons[shape].jj_icon, COMMAND_ICONS[shape])
        line = flyouts["Sketcher_CreateLine"]
        self.assertEqual([v.one_line for v in line.variants], ["Line", "Centerline", "Midpoint Line", "Polyline"])
        self.assertEqual([v.jj_icon for v in line.variants], [None, "centerline", "midpoint_line", None])
        self.assertEqual([v.one_line for v in flyouts["PartDesign_LinearPattern"].variants],
                         ["Linear Pattern", "Circular Pattern", "Multi-Transform"])
        self.assertEqual(flyouts["JellyJams_Note"].variants[0].label, "Note")
        self.assertEqual({fid: f.title for fid, f in flyouts.items() if f.title}, RIBBON_FLYOUT_TITLES)
        self.assertEqual([v.label for v in toggles[0].variants], ["Sketch", "Exit\nSketch"])

    def test_missing_commands_are_skipped_without_gaps(self):
        available = ribbon_command_ids() - {"PartDesign_SubtractiveLoft", "Sketcher_CreateArcSlot"}
        resolved = self.resolve(available)
        self.assertEqual(sorted(resolved.skipped), ["PartDesign_SubtractiveLoft", "Sketcher_CreateArcSlot"])
        self.assertEqual(len(resolved.plain_ids()), RIBBON_TOTALS["plain"] - 1)
        self.assertEqual(dict(resolved.flyouts())["Sketcher_CreateSlot"], ["Sketcher_CreateSlot"])
        cut_stack = [s for s in self.stacks(self.tab(resolved, "Features"))
                     if "PartDesign_SubtractivePipe" in [c.entry_id for c in s.cells]][0]
        self.assertEqual([c.entry_id for c in cut_stack.cells], ["PartDesign_SubtractivePipe",
                                                                 "PartDesign_SubtractiveHelix"])

    def test_fallback_substitution(self):
        available = (ribbon_command_ids() - {"Sketcher_Projection"}) | {"Sketcher_External"}
        resolved = self.resolve(available)
        flyouts = dict(resolved.flyouts())
        self.assertNotIn("Sketcher_Projection", flyouts)
        self.assertEqual(flyouts["Sketcher_External"], ["Sketcher_External", "Sketcher_Intersection",
                                                        "Sketcher_CarbonCopy"])
        self.assertIn(("Sketcher_Projection", "Sketcher_External"), [tuple(s) for s in resolved.substitutions])
        self.assertEqual(list(resolved.skipped), [])
        neither = self.resolve(ribbon_command_ids() - {"Sketcher_Projection"})
        self.assertEqual(dict(neither.flyouts())["Sketcher_Intersection"], ["Sketcher_Intersection",
                                                                            "Sketcher_CarbonCopy"])
        self.assertIn("Sketcher_Projection", neither.skipped)

    def test_every_fallback_substitutes(self):
        """An older FreeCAD that only has the fallback ids still gets every entry."""
        available = (ribbon_command_ids() - set(RIBBON_FALLBACKS)) | set(RIBBON_FALLBACKS.values())
        resolved = self.resolve(available)
        self.assertEqual(sorted(tuple(s) for s in resolved.substitutions), sorted(RIBBON_FALLBACKS.items()))
        self.assertEqual(list(resolved.skipped), [])
        self.assertEqual(len(list(resolved.all_ids())), RIBBON_TOTALS["entry_ids"])
        flyouts = dict(resolved.flyouts())
        self.assertEqual(flyouts["PartDesign_Plane"], ["PartDesign_Plane", "PartDesign_Line",
                                                       "PartDesign_CoordinateSystem", "PartDesign_Point"])
        self.assertEqual(flyouts["TechDraw_LengthDimension"][0], "TechDraw_LengthDimension")
        self.assertEqual([list(v) for v in resolved.toggles()], [["Sketcher_NewSketch", "Sketcher_LeaveSketch"]])
        _buttons, resolved_flyouts, _toggles = self.all_items(resolved)
        self.assertEqual(resolved_flyouts["PartDesign_Plane"].title, "Reference\nGeometry")
        substituted = resolved_flyouts["PartDesign_Plane"].variants[0]
        self.assertEqual((substituted.cmd, substituted.substituted_from), ("PartDesign_Plane", "Part_DatumPlane"))

    def test_assembly_commands_missing(self):
        available = {cmd for cmd in ribbon_command_ids() if not cmd.startswith("Assembly_")}
        resolved = self.resolve(available)
        self.assertFalse([i for i in resolved.all_ids() if i.startswith("Assembly_")])
        tab = self.tab(resolved, "Assembly")
        ids = {item.entry_id for group in tab.groups for item in self.items(group.items)
               if isinstance(item, self.model.RButton)}
        self.assertEqual(ids, {"JellyJams_NewAssembly", "JellyJams_MakeDrawing#1", "Std_TransformManip", "JellyJams_RotateComponent"})
        self.assertFalse([item for group in tab.groups for item in self.items(group.items)
                          if not isinstance(item, self.model.RButton)])
        self.assertTrue(all(i.startswith("Assembly_") for i in resolved.skipped))

    def test_toggle_degrades_and_empty_groups_vanish(self):
        resolved = self.resolve(ribbon_command_ids() - {"Sketcher_LeaveSketch"})
        self.assertEqual(list(resolved.toggles()), [])
        self.assertIn("PartDesign_NewSketch", resolved.plain_ids())
        resolved = self.resolve(ribbon_command_ids() - set(RIBBON_TOGGLE))
        self.assertNotIn("PartDesign_NewSketch", resolved.all_ids())
        resolved = self.resolve(ribbon_command_ids() - {"JellyJams_Diagnostics"})
        self.assertEqual(resolved.separators("Evaluate"), 2)
        resolved = self.resolve(ribbon_command_ids() - {"Std_Measure"})
        self.assertEqual(resolved.separators("Evaluate"), 3)
        resolved = self.resolve(ribbon_command_ids() - set(RIBBON_FLYOUTS["TechDraw_Dimension"]))
        self.assertNotIn("TechDraw_Dimension", dict(resolved.flyouts()))
        self.assertEqual(resolved.separators("Drawing"), 4)
        resolved = self.resolve(ribbon_command_ids() - {"JellyJams_SaveAsPDF", "JellyJams_SaveAsDXF"})
        self.assertEqual(resolved.separators("Drawing"), 3)
        shapes = set(SHEET_SHAPES.values())
        resolved = self.resolve(ribbon_command_ids() - shapes)
        self.assertEqual([s.style for s in self.stacks(self.tab(resolved, "Drawing"))], ["text"] * 5)
        self.assertEqual(resolved.separators("Drawing"), 4, "Line Format keeps the sheet sketch group")

    def test_entry_ids_object_names_and_command_ids(self):
        self.assertEqual(self.model.entry_id("Std_DrawStyle", 6), "Std_DrawStyle#6")
        self.assertEqual(self.model.entry_id("PartDesign_Pad"), "PartDesign_Pad")
        self.assertEqual(self.model.object_name("JellyJamsButton-", "Std_DrawStyle#6"), "JellyJamsButton-Std_DrawStyle-6")
        self.assertEqual(self.model.object_name("JellyJamsFlyout-", "Sketcher_CreateLine"), "JellyJamsFlyout-Sketcher_CreateLine")
        ids = list(self.layout_data.all_command_ids())
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), ribbon_command_ids() | set(RIBBON_FALLBACKS.values()))
        self.assertEqual({i for i in ids if i.startswith("JellyJams_")}, set(EXPECTED_COMMANDS) - OFF_RIBBON_COMMANDS)


class Test13RibbonText(HarnessCase):
    def setUp(self):
        super().setUp()
        self.text = self.module("jellyjams.ribbon_text")

    def test_one_line(self):
        cases = {"Center-\nline": "Centerline", "Wire-\nframe": "Wireframe", "Concen-\ntric": "Concentric",
                 "Dash-\nDot": "Dash-Dot", "Center\nRectangle": "Center Rectangle", "3 Point\nArc": "3 Point Arc",
                 "Extruded\nBoss/Base": "Extruded Boss/Base", "Fillet": "Fillet"}
        for label, expected in cases.items():
            self.assertEqual(self.text.one_line(label), expected, label)

    def test_tooltip_name(self):
        self.assertEqual(self.text.tooltip_name("Con\u00adcentric"), "Concentric")
        self.assertEqual(self.text.tooltip_name("Con\u00ad\ncentric"), "Concentric")
        self.assertEqual(self.text.tooltip_name("Zoom  to\nFit"), "Zoom to Fit")
        self.assertEqual(self.text.tooltip_name("Center-\nline"), "Centerline")

    def test_plain_text(self):
        cases = {"&Pad...": "Pad", "<b>Makes</b> a thick solid": "Makes a thick solid", "Save &&Close": "Save &Close",
                 "Fish &amp; Chips": "Fish & Chips", "Export\u2026": "Export", "  a \n b ": "a b"}
        for raw, expected in cases.items():
            self.assertEqual(self.text.plain_text(raw), expected, raw)

    def test_same_name(self):
        self.assertTrue(self.text.same_name("Mate", "mate."))
        self.assertTrue(self.text.same_name("Zoom  to fit", "zoom to fit"))
        self.assertFalse(self.text.same_name("Extruded Boss/Base", "Pad"))

    def test_compose_tooltip(self):
        compose = self.text.compose_tooltip
        self.assertEqual(compose("Extruded\nBoss/Base", "&Pad...", ""), "Extruded Boss/Base %s (FreeCAD: Pad)" % EM_DASH)
        self.assertEqual(compose("Mate", "Mate", ""), "Mate")
        self.assertIsNone(compose("Fillet", "", ""))
        self.assertEqual(compose("Shell", "Thickness", "<b>Makes</b> a thick solid"),
                         "Shell %s (FreeCAD: Thickness)\nMakes a thick solid" % EM_DASH)
        self.assertEqual(compose("Fillet", "Fillet", "Fillet"), "Fillet")
        self.assertEqual(compose("", "Pad", ""), "Pad")


RIBBON_INFO = {
    "PartDesign_Pad": {"menuText": "&Pad...", "toolTip": ""},
    "PartDesign_Thickness": {"menuText": "Thickness", "toolTip": "<b>Makes</b> a thick solid"},
}


class Test13RibbonBuild(HarnessCase):
    def setUp(self):
        super().setUp()
        self.fcgui = self.module("jellyjams.fcgui")
        self.preload = []
        self.patch(self.fcgui, "preload_command_modules", lambda: (self.preload.append(1), ([], []))[1])
        STUBS.set_active_workbench(WB)
        STUBS.set_commands(sorted(ribbon_command_ids()), info=RIBBON_INFO)
        self.ribbon = self.module("jellyjams.ribbon", fresh=True)
        self.addCleanup(self.quiet_hide)

    def quiet_hide(self):
        with contextlib.suppress(Exception):
            self.ribbon.hide()

    def show(self):
        self.ribbon.show()
        STUBS.pump(10)
        dock = STUBS.main_window.findChild(QtWidgets.QDockWidget, "JellyJamsCommandManager")
        self.assertIsNotNone(dock, "no JellyJamsCommandManager dock")
        return dock

    def buttons(self, dock, prefix=None):
        found = [b for b in dock.findChildren(QtWidgets.QToolButton)
                 if not isinstance(b.parent(), QtWidgets.QTabBar)]
        if prefix:
            found = [b for b in found if b.objectName().startswith(prefix)]
        return found

    def tabs(self, dock):
        tabs = dock.findChild(QtWidgets.QTabWidget, "JellyJamsCommandManagerTabs")
        self.assertIsNotNone(tabs)
        return tabs

    def test_dock_tabs_and_object_names(self):
        dock = self.show()
        window = STUBS.main_window
        self.assertIs(self.ribbon.dock(), dock)
        self.assertEqual(window.dockWidgetArea(dock), QtCore.Qt.DockWidgetArea.TopDockWidgetArea)
        self.assertEqual(dock.features(), QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.assertIsNotNone(dock.titleBarWidget())
        self.assertTrue(dock.isVisible())
        tabs = self.tabs(dock)
        self.assertEqual(tabs.tabPosition(), QtWidgets.QTabWidget.TabPosition.South)
        self.assertTrue(tabs.documentMode())
        titles = [tabs.tabText(i) for i in range(tabs.count())]
        self.assertEqual(titles, ["Features", "Sketch", "Evaluate", "Assembly", "Drawing"])
        self.assertEqual(tabs.tabText(tabs.currentIndex()), "Features")
        self.assertEqual(list(self.ribbon.tab_titles()), titles)
        self.assertEqual(self.ribbon.current_tab_title(), "Features")
        self.assertEqual(dict(self.ribbon.context_tabs()), {"sketch": "Sketch", "assembly": "Assembly",
                                                             "drawing": "Drawing"})
        for button in self.buttons(dock):
            self.assertTrue(button.objectName().startswith(("JellyJamsButton-", "JellyJamsFlyout-", "JellyJamsToggle-")), button.objectName())
            self.assertTrue(button.autoRaise())
        self.assertEqual(len(self.buttons(dock, "JellyJamsButton-")), RIBBON_TOTALS["plain"])
        self.assertEqual(len(self.buttons(dock, "JellyJamsFlyout-")), RIBBON_TOTALS["flyouts"])
        self.assertEqual(len(self.buttons(dock, "JellyJamsToggle-")), RIBBON_TOTALS["toggles"])
        for index, title in enumerate(titles):
            page = tabs.widget(index)
            separators = page.findChildren(QtWidgets.QFrame, "JellyJamsGroupDivider")
            self.assertEqual(len(separators), RIBBON_TAB_COUNTS[title][4], title)
            plain, flyouts, _variants, toggles, _separators = RIBBON_TAB_COUNTS[title]
            names = [b.objectName() for b in page.findChildren(QtWidgets.QToolButton)]
            self.assertEqual((len([n for n in names if n.startswith("JellyJamsButton-")]),
                              len([n for n in names if n.startswith("JellyJamsFlyout-")]),
                              len([n for n in names if n.startswith("JellyJamsToggle-")])), (plain, flyouts, toggles), title)
        self.assertEqual(len(list(self.ribbon.entry_ids())), RIBBON_TOTALS["entry_ids"])
        self.assertEqual(list(self.ribbon.skipped_ids()), [])
        self.assertTrue(self.preload)
        self.assertNoJellyJamsProblems()
        messages = self.jj("message")
        self.assertTrue(messages, "no info line after the build")
        for number in ("%d buttons" % RIBBON_TOTALS["plain"], "%d flyouts" % RIBBON_TOTALS["flyouts"],
                       "%d tools" % RIBBON_TOTALS["variants"], "5 tabs"):
            self.assertIn(number, messages[-1])

    def test_button_kinds_texts_and_tooltips(self):
        self.show()
        pad = self.ribbon.find_button("PartDesign_Pad")
        self.assertIsNotNone(pad)
        self.assertEqual(pad.objectName(), "JellyJamsButton-PartDesign_Pad")
        self.assertEqual(pad.text(), "Extruded\nBoss/Base")
        self.assertEqual(pad.iconSize(), QtCore.QSize(32, 32))
        self.assertEqual(pad.toolButtonStyle(), QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.assertTrue(pad.toolTip().startswith("Extruded Boss/Base %s (FreeCAD: Pad)" % EM_DASH), pad.toolTip())
        shell = self.ribbon.find_button("PartDesign_Thickness")
        self.assertEqual(shell.toolTip(), "Shell %s (FreeCAD: Thickness)\nMakes a thick solid" % EM_DASH)
        sweep = self.ribbon.find_button("PartDesign_AdditivePipe")
        self.assertEqual(sweep.toolButtonStyle(), QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.assertEqual(sweep.text(), "Swept Boss/Base")
        self.assertEqual(sweep.iconSize(), QtCore.QSize(20, 20))
        point = self.ribbon.find_button("Sketcher_CreatePoint")
        self.assertEqual(point.iconSize(), QtCore.QSize(20, 20))
        self.assertEqual(self.ribbon.find_button("Std_DrawStyle#6").objectName(), "JellyJamsButton-Std_DrawStyle-6")
        self.assertEqual(self.ribbon.find_button("JellyJams_MakeDrawing#1").objectName(), "JellyJamsButton-JellyJams_MakeDrawing-1")
        hint = self.module("jellyjams.ribbon_text").MORE_VARIANTS_HINT
        self.assertTrue(hint and "\n" not in hint)
        for button in self.buttons(self.ribbon.dock()):
            tip = button.toolTip()
            self.assertTrue(tip, button.objectName())
            self.assertNotRegex(tip, r"<[A-Za-z/]", button.objectName())
            self.assertNotIn("&P", tip)
            if button.objectName().startswith("JellyJamsFlyout-"):
                self.assertTrue(tip.endswith("\n" + hint), "a flyout tooltip ends with the arrow hint")
                self.assertEqual(button.popupMode(), QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            else:
                self.assertNotIn(hint, tip, button.objectName())
        mate = self.ribbon.dock().findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Assembly_CreateJointDistance")
        self.assertIsNotNone(mate)
        self.assertEqual(mate.text(), "Mate")
        self.assertTrue(mate.toolTip().startswith("Mate: "), mate.toolTip())
        mechanical = self.ribbon.dock().findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Assembly_CreateJointRevolute")
        self.assertEqual(mechanical.text(), "Mechanical\nMates")
        self.assertTrue(mechanical.toolTip().startswith("Mechanical Mates: "), mechanical.toolTip())
        self.assertIsNone(self.ribbon.dock().findChild(QtWidgets.QToolButton, "JellyJamsFlyout-JellyJams_LineOnSheet"))
        circle = self.ribbon.find_button("JellyJams_CircleOnSheet")
        self.assertIsNotNone(circle, "the sheet shapes are plain buttons")
        self.assertEqual(circle.objectName(), "JellyJamsButton-JellyJams_CircleOnSheet")
        self.assertEqual(circle.toolButtonStyle(), QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.assertEqual(circle.iconSize(), QtCore.QSize(20, 20))
        self.assertTrue(circle.toolTip().startswith("Circle"), circle.toolTip())
        self.assertIsNone(self.ribbon.find_button("Sketcher_CreateBSpline"), "Style Spline is a flyout variant")
        self.assertIsNone(self.ribbon.find_button("Assembly_CreateJointCylindrical"), "Concentric is a Mate variant")
        diagnostics = self.ribbon.find_button("JellyJams_Diagnostics")
        self.assertIsNotNone(diagnostics)
        self.assertEqual(diagnostics.text(), "Diagnostics")
        self.assertEqual(diagnostics.iconSize(), QtCore.QSize(32, 32))

    def icon_stack_positions(self, tab_index=1, member="JellyJamsFlyout-Sketcher_CreateCircle"):
        dock = self.ribbon.dock()
        tabs = self.tabs(dock)
        page = tabs.widget(tab_index)
        circle = page.findChild(QtWidgets.QToolButton, member)
        self.assertIsNotNone(circle, member)
        stack = circle.parentWidget()
        while stack is not None and stack.objectName() != "JellyJamsToolStack":
            stack = stack.parentWidget()
        self.assertIsNotNone(stack, "%s is not inside a JellyJamsToolStack" % member)
        grid = stack.layout()
        self.assertIsInstance(grid, QtWidgets.QGridLayout)
        positions = {}
        for index in range(grid.count()):
            widget = grid.itemAt(index).widget()
            if widget is None:
                continue
            buttons = [widget] if isinstance(widget, QtWidgets.QToolButton) else widget.findChildren(QtWidgets.QToolButton)
            row, column, _rows, _columns = grid.getItemPosition(index)
            for button in buttons:
                positions[button.objectName()] = (row, column)
        return positions

    def test_icon_stack_three_rows_column_by_column(self):
        self.show()
        stacks = {
            (1, "JellyJamsFlyout-Sketcher_CreateCircle"): [
                "JellyJamsFlyout-Sketcher_CreateLine", "JellyJamsFlyout-Sketcher_CreateRectangle", "JellyJamsFlyout-Sketcher_CreateSlot",
                "JellyJamsFlyout-Sketcher_CreateCircle", "JellyJamsFlyout-Sketcher_CreateArc", "JellyJamsButton-Sketcher_CreateRegularPolygon",
                "JellyJamsFlyout-Sketcher_CreateBSplineByInterpolation", "JellyJamsFlyout-Sketcher_CreateEllipseByCenter",
                "JellyJamsFlyout-Sketcher_CreateFillet", "JellyJamsButton-Sketcher_CreatePoint"],
            (2, "JellyJamsButton-Std_ViewFront"): [
                "JellyJamsButton-Std_ViewFront", "JellyJamsButton-Std_ViewTop", "JellyJamsButton-Std_ViewRight", "JellyJamsButton-Std_ViewRear",
                "JellyJamsButton-Std_ViewBottom", "JellyJamsButton-Std_ViewLeft", "JellyJamsButton-Std_ViewIsometric",
                "JellyJamsButton-Std_ViewDimetric", "JellyJamsButton-Std_ViewTrimetric"],
            (4, "JellyJamsButton-JellyJams_LineOnSheet"): [
                "JellyJamsButton-JellyJams_LineOnSheet", "JellyJamsButton-JellyJams_CornerRectangleOnSheet", "JellyJamsButton-JellyJams_CircleOnSheet",
                "JellyJamsButton-JellyJams_CenterpointArcOnSheet", "JellyJamsButton-JellyJams_PolygonOnSheet"],
        }
        for (tab_index, member), expected in stacks.items():
            with self.subTest(member=member):
                positions = self.icon_stack_positions(tab_index, member)
                self.assertEqual(positions, {name: (index % 3, index // 3) for index, name in enumerate(expected)})

    def test_flyout_choice_runs_and_persists(self):
        self.show()
        dock = self.ribbon.dock()
        button = dock.findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Sketcher_CreateRectangle")
        self.assertIsNotNone(button)
        actions = {action.text(): action for action in button.menu().actions()}
        self.assertEqual(list(actions), ["Corner Rectangle", "Center Rectangle", "Rounded Rectangle"])
        actions["Center Rectangle"].trigger()
        STUBS.pump(10)
        self.assertEqual(STUBS.run_calls[-1], ("Sketcher_CreateRectangle_Center", None))
        self.assertEqual(param(P_RIBBON).GetString("Sketcher_CreateRectangle"), "Sketcher_CreateRectangle_Center")
        self.assertEqual(button.objectName(), "JellyJamsFlyout-Sketcher_CreateRectangle_Center")
        button.click()
        STUBS.pump(10)
        self.assertEqual(STUBS.run_calls[-1], ("Sketcher_CreateRectangle_Center", None))
        state = [s for s in self.ribbon.flyout_states() if s["id"] == "Sketcher_CreateRectangle"][0]
        self.assertEqual(list(state["variants"])[state["current"]] if isinstance(state["current"], int)
                         else state["current"], "Sketcher_CreateRectangle_Center")

    def test_remembered_choice_and_unknown_value(self):
        param(P_RIBBON).SetString("Sketcher_CreateCircle", "Sketcher_Create3PointCircle")
        param(P_RIBBON).SetString("Sketcher_CreateArc", "Sketcher_DoesNotExist")
        dock = self.show()
        self.assertIsNotNone(dock.findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Sketcher_Create3PointCircle"))
        self.assertIsNotNone(dock.findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Sketcher_CreateArc"))
        self.assertEqual(param(P_RIBBON).GetString("Sketcher_CreateArc"), "Sketcher_DoesNotExist")
        self.assertNoJellyJamsProblems()

    def test_titled_flyout_keeps_its_title(self):
        dock = self.show()
        mate = dock.findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Assembly_CreateJointDistance")
        self.assertIsNotNone(mate)
        self.assertEqual([a.text() for a in mate.menu().actions()],
                         ["Coincident/Distance", "Parallel", "Perpendicular", "Concentric", "Lock", "Angle"])
        concentric = [a for a in mate.menu().actions() if a.text() == "Concentric"][0]
        concentric.trigger()
        STUBS.pump(10)
        self.assertEqual(mate.objectName(), "JellyJamsFlyout-Assembly_CreateJointCylindrical")
        self.assertEqual(mate.text(), "Mate")
        self.assertTrue(mate.toolTip().startswith("Mate: Concentric"), mate.toolTip())
        self.assertEqual(STUBS.run_calls[-1], ("Assembly_CreateJointCylindrical", None))
        self.assertEqual(param(P_RIBBON).GetString("Assembly_CreateJointDistance"), "Assembly_CreateJointCylindrical")
        reference = dock.findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Part_DatumPlane")
        axis = [a for a in reference.menu().actions() if a.text() == "Axis"][0]
        axis.trigger()
        STUBS.pump(10)
        self.assertEqual(reference.text(), "Reference\nGeometry")
        self.assertEqual(STUBS.run_calls[-1], ("Part_DatumLine", None))

    def test_normal_to_button_on_the_evaluate_tab(self):
        dock = self.show()
        evaluate = self.tabs(dock).widget(2)
        button = evaluate.findChild(QtWidgets.QToolButton, "JellyJamsButton-JellyJams_NormalTo")
        self.assertIsNotNone(button, "Normal To sits on the Evaluate tab")
        self.assertIs(self.ribbon.find_button("JellyJams_NormalTo"), button)
        self.assertEqual(button.text(), "Normal To")
        self.assertIsNone(self.ribbon.find_button("Std_AlignToSelection"), "FreeCAD's Align to selection is gone")
        sketch_page = self.tabs(dock).widget(1)
        self.assertIsNotNone(sketch_page.findChild(QtWidgets.QToolButton, "JellyJamsButton-Sketcher_ViewSketch"),
                             "the Sketch tab keeps View sketch")
        button.click()
        STUBS.pump(10)
        self.assertEqual(STUBS.run_calls[-1], ("JellyJams_NormalTo", None))

    def test_indexed_entry_runs_with_index(self):
        self.show()
        self.ribbon.find_button("Std_DrawStyle#5").click()
        STUBS.pump(10)
        self.assertEqual(STUBS.run_calls[-1], ("Std_DrawStyle", 5))

    def test_enabled_state_follows_is_active(self):
        self.show()
        STUBS.set_command_active("Sketcher_CreatePoint", False)
        STUBS.set_command_active("Sketcher_CreateRegularPolygon", RuntimeError("isActive broken"))
        STUBS.set_command_active("Sketcher_CreateRectangle", False)
        self.ribbon.refresh_now()
        self.assertFalse(self.ribbon.find_button("Sketcher_CreatePoint").isEnabled())
        self.assertTrue(self.ribbon.find_button("Sketcher_CreateRegularPolygon").isEnabled())
        rectangle = self.ribbon.dock().findChild(QtWidgets.QToolButton, "JellyJamsFlyout-Sketcher_CreateRectangle")
        self.assertFalse(rectangle.isEnabled())
        self.assertTrue(self.ribbon.find_button("Std_DrawStyle#6").isEnabled())

    def test_sketch_context_and_toggle(self):
        dock = self.show()
        tabs = self.tabs(dock)
        tabs.setCurrentIndex(2)
        sketch = types.SimpleNamespace(TypeId="Sketcher::SketchObject", Name="Sketch", Label="Sketch1")
        STUBS.gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=sketch))
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Sketch")
        toggle = dock.findChild(QtWidgets.QToolButton, "JellyJamsToggle-Sketcher_LeaveSketch")
        self.assertIsNotNone(toggle)
        self.assertEqual(flat_text(toggle.text()), "Exit Sketch")
        tabs.setCurrentIndex(0)
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Features")
        STUBS.gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Evaluate")
        self.assertIsNotNone(dock.findChild(QtWidgets.QToolButton, "JellyJamsToggle-PartDesign_NewSketch"))
        pad = types.SimpleNamespace(TypeId="PartDesign::Pad", Name="Pad", Label="Boss-Extrude1")
        STUBS.gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=pad))
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Evaluate")

    def test_assembly_context(self):
        assembly = types.SimpleNamespace(TypeId="Assembly::AssemblyObject", Name="Assembly", Label="Assembly1",
                                         isDerivedFrom=lambda type_id: type_id == "Assembly::AssemblyObject")
        state = {"active": None}
        utils = fake_module("UtilsAssembly", activeAssembly=lambda: state["active"])
        self.fakes({"UtilsAssembly": utils})
        self.show()
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Features")
        state["active"] = assembly
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Assembly")
        state["active"] = None
        self.ribbon.refresh_now()
        self.assertEqual(self.ribbon.current_tab_title(), "Assembly")

    def test_show_twice_hide_and_visibility_guard(self):
        dock = self.show()
        count = len(self.buttons(dock))
        self.ribbon.show()
        STUBS.pump(10)
        self.assertIs(self.ribbon.dock(), dock)
        self.assertEqual(len(self.buttons(dock)), count)
        self.assertTrue(self.ribbon.is_built())
        self.assertTrue(self.ribbon.is_requested())
        self.ribbon.hide()
        self.assertFalse(dock.isVisible())
        self.assertFalse(self.ribbon.is_requested())
        dock.show()
        STUBS.pump(100)
        self.assertFalse(dock.isVisible(), "the visibility guard must hide an unrequested ribbon")
        self.ribbon.hide_if_not_requested()
        self.assertFalse(dock.isVisible())
        self.ribbon.show()
        STUBS.pump(50)
        self.assertTrue(dock.isVisible())
        self.ribbon.hide_if_not_requested()
        STUBS.pump(50)
        self.assertTrue(dock.isVisible())

    def test_rebuild(self):
        dock = self.show()
        self.tabs(dock).setCurrentIndex(3)
        count = len(self.buttons(dock))
        self.ribbon.rebuild()
        STUBS.pump(10)
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        new = self.ribbon.dock()
        self.assertIsNot(new, dock)
        self.assertTrue(new.isVisible())
        self.assertEqual(len(self.buttons(new)), count)
        self.assertEqual(self.ribbon.current_tab_title(), "Assembly")
        docks = [d for d in STUBS.main_window.findChildren(QtWidgets.QDockWidget, "JellyJamsCommandManager") if d.isVisible()]
        self.assertEqual(docks, [new])

    def test_unbuilt_ribbon_is_inert(self):
        self.ribbon.hide()
        self.ribbon.hide_if_not_requested()
        self.ribbon.rebuild()
        self.assertFalse(self.ribbon.is_built())
        self.assertIsNone(self.ribbon.dock())
        self.assertEqual(self.lines(), [])

    def test_missing_commands_warning(self):
        STUBS.set_commands(sorted(ribbon_command_ids() - {"PartDesign_SubtractiveLoft", "Sketcher_CreateArcSlot"}))
        self.show()
        warnings = self.jj("warning")
        self.assertEqual(len(warnings), 1, self.lines())
        self.assertIn("PartDesign_SubtractiveLoft", warnings[0])
        self.assertIn("Sketcher_CreateArcSlot", warnings[0])
        self.assertIsNone(self.ribbon.find_button("PartDesign_SubtractiveLoft"))

    def test_assembly_modules_missing_only_logs(self):
        self.patch(self.fcgui, "preload_command_modules", lambda: ([], ["CommandCreateJoint"]))
        STUBS.set_commands(sorted(c for c in ribbon_command_ids() if not c.startswith("Assembly_")))
        dock = self.show()
        self.assertEqual(self.jj("warning"), [], self.lines())
        self.assertTrue(self.jj("log"))
        assembly_page = self.tabs(dock).widget(3)
        names = {b.objectName() for b in assembly_page.findChildren(QtWidgets.QToolButton)}
        self.assertTrue({"JellyJamsButton-JellyJams_NewAssembly", "JellyJamsButton-JellyJams_RotateComponent", "JellyJamsButton-JellyJams_MakeDrawing-1"} <= names, names)

    def test_run_entry_dispatch_order(self):
        calls = []
        tools = fake_module("jellyjams.sketch_tools",
                            stop_running=lambda except_cmd=None: calls.append(("stop_running", except_cmd)))
        gesture = fake_module("jellyjams.sketch_gesture",
                              try_run=lambda cmd: (calls.append(("try_run", cmd)), cmd == "PartDesign_Pad")[1])
        self.fakes({"jellyjams.sketch_tools": tools, "jellyjams.sketch_gesture": gesture})
        self.ribbon.run_entry("PartDesign_Pad")
        self.assertEqual(calls, [("stop_running", "PartDesign_Pad"), ("try_run", "PartDesign_Pad")])
        self.assertEqual(STUBS.run_calls, [])
        del calls[:]
        self.ribbon.run_entry("PartDesign_Fillet")
        self.assertEqual(calls, [("stop_running", "PartDesign_Fillet"), ("try_run", "PartDesign_Fillet")])
        self.assertEqual(STUBS.run_calls, [("PartDesign_Fillet", None)])
        del calls[:]
        self.ribbon.run_entry("Std_DrawStyle", 5)
        self.assertEqual(calls, [("stop_running", "Std_DrawStyle")])
        self.assertEqual(STUBS.run_calls[-1], ("Std_DrawStyle", 5))
        STUBS.run_errors["PartDesign_Chamfer"] = RuntimeError("command refused by the harness")
        self.ribbon.run_entry("PartDesign_Chamfer")
        errors = self.jj("error")
        self.assertEqual(len(errors), 1)
        self.assertIn("PartDesign_Chamfer", errors[0])


# ==========================================================================
# 14. Naming rules
# ==========================================================================


class Test26Measure(HarnessCase):
    def setUp(self):
        super().setUp()
        self.measure = self.module("jellyjams.measure")
        self.patch(self.measure, "_session", None)

    def task(self):
        task = self.measure.MeasureTask(types.SimpleNamespace(Name="Board"), None)
        self.addCleanup(task.form.deleteLater)
        selected = []
        selection = types.SimpleNamespace(
            getSelectionEx=lambda *args: [types.SimpleNamespace(
                Object=obj, SubElementNames=[sub]) for obj, sub in selected],
            addSelection=lambda obj, sub: selected.append((obj, sub)))
        self.patch(STUBS.gui, "Selection", selection)
        self.patch(self.module("jellyjams.fcgui"), "defer", lambda fn, ms=0: None)
        return task, selected

    def test_flatten_same_object_and_whole_object(self):
        obj = object()
        other = object()
        entries = [types.SimpleNamespace(Object=obj, SubElementNames=["Edge1", "Edge2", "Edge1"]),
                   types.SimpleNamespace(Object=other, SubElementNames=[])]
        self.assertEqual(self.measure.selected_items(entries),
                         [(obj, "Edge1"), (obj, "Edge2"), (other, "")])

    def test_normal_click_restores_first_pick_after_native_clear_add(self):
        task, selected = self.task()
        obj = object()
        task.items = [(obj, "Edge1")]
        task.clearSelection()
        selected.append((obj, "Edge2"))
        task.addSelection()
        # Avoid geometry; only inspect which paths reach the kernel boundary.
        seen = []
        def distance(items, *args):
            seen.extend(items)
            raise ValueError("unsupported test geometry")
        self.patch(self.measure, "measurement", distance)
        task.refresh()
        self.assertCountEqual(selected, [(obj, "Edge1"), (obj, "Edge2")])
        self.assertCountEqual(seen, selected)

    def test_click_empty_clears_result_and_annotation(self):
        task, selected = self.task()
        task.items = [(object(), "Edge1")]
        task.result.setText("previous distance")
        nodes = []
        task.node = object()
        task.view = types.SimpleNamespace(getSceneGraph=lambda: types.SimpleNamespace(
            removeChild=lambda node: nodes.append(node)))
        task.clearSelection()
        task.refresh()
        self.assertEqual(len(nodes), 1)
        self.assertIsNone(task.node)
        self.assertEqual(task.result.text(), "")
        self.assertEqual(task.items, [])

    def test_remove_pick_does_not_restore_it(self):
        task, selected = self.task()
        obj = object()
        task.items = [(obj, "Edge1"), (obj, "Edge2")]
        selected.append((obj, "Edge1"))
        task.removeSelection()
        task.refresh()
        self.assertEqual(task.items, [(obj, "Edge1")])
        self.assertIsNone(task.node)

    def test_kernel_uses_unresolved_paths_and_nearest_points(self):
        calls = []
        first = types.SimpleNamespace(isNull=lambda: False,
                                      distToShape=lambda other: (4.0, [("near1", "near2")], []))
        second = types.SimpleNamespace(isNull=lambda: False)
        shapes = iter((first, second))
        def shape(obj, sub, **kwargs):
            calls.append((obj, sub, kwargs))
            return next(shapes)
        self.fakes({"Part": fake_module("Part", getShape=shape)})
        self.assertEqual(self.measure.shortest_distance([(1, "Link.Edge1"), (2, "Edge2")]),
                         (4.0, ("near1", "near2")))
        self.assertEqual(calls, [(1, "Link.Edge1", {"needSubElement": True}),
                                 (2, "Edge2", {"needSubElement": True})])

    def test_ribbon_routes_measure_without_running_native_command(self):
        calls = []
        self.patch(self.measure, "start", lambda: calls.append("start"))
        ribbon = self.module("jellyjams.ribbon")
        ribbon.run_entry("Std_Measure")
        self.assertEqual(calls, ["start"])
        self.assertEqual(STUBS.run_calls, [])

    def test_ribbon_measure_checked_state_tracks_session_and_stays_stoppable(self):
        button = QtWidgets.QToolButton()
        self.addCleanup(button.deleteLater)
        ui = types.SimpleNamespace(find_button=lambda cmd: button)
        ribbon = self.module("jellyjams.ribbon")
        ribbon._refresh_measure_button(ui)
        self.assertTrue(button.isCheckable())
        self.assertFalse(button.isChecked())
        self.patch(self.measure, "_session", types.SimpleNamespace(closed=False))
        button.setEnabled(False)  # Native Measure is disabled while its task is open.
        ribbon._refresh_measure_button(ui)
        self.assertTrue(button.isChecked())
        self.assertTrue(button.isEnabled())
        self.measure._session.closed = True
        ribbon._refresh_measure_button(ui)
        self.assertFalse(button.isChecked())

    def test_measure_toggle_starts_then_stops(self):
        calls = []
        def start():
            calls.append("start")
            self.measure._session = types.SimpleNamespace(closed=False)
        def stop():
            calls.append("stop")
            self.measure._session = None
        self.patch(self.measure, "start", start)
        self.patch(self.measure, "stop", stop)
        self.measure.toggle()
        self.measure.toggle()
        self.assertEqual(calls, ["start", "stop"])
        self.assertFalse(self.measure.is_active())

    def test_circular_edges_and_arcs_use_their_center(self):
        class Circle:
            Center = "world centre"
        shape = types.SimpleNamespace(ShapeType="Edge", Curve=Circle())
        part = types.SimpleNamespace(Circle=Circle, Vertex=lambda center: ("vertex", center))
        self.assertEqual(self.measure._reference_shape(shape, part), ("vertex", "world centre"))

    def test_clearance_mode_keeps_the_original_circular_geometry(self):
        shape = types.SimpleNamespace(isNull=lambda: False,
            distToShape=lambda other: (0.8, [("rim", "edge")], []))
        self.fakes({"Part": fake_module("Part", getShape=lambda *args, **kwargs: shape)})
        self.patch(self.measure, "_reference_shape", lambda *args: self.fail("clearance must keep the rim"))
        self.assertEqual(self.measure.shortest_distance([(1, "Edge1"), (1, "Edge2")], False),
                         (0.8, ("rim", "edge")))

    def test_cylinder_axis_uses_its_offset_origin_direction_and_negative_parameters(self):
        class Vector:
            def __init__(self, *values):
                self.values = values
            def __add__(self, other):
                return Vector(*(a + b for a, b in zip(self.values, other.values)))
            def __mul__(self, scale):
                return Vector(*(a * scale for a in self.values))
        class Cylinder:
            Center = Vector(184.331627927, -129.148101334, 5.306402814)
            Axis = Vector(0, 0, -1)
        shape = types.SimpleNamespace(ShapeType="Face", Surface=Cylinder(),
                                      ParameterRange=(0, 6.283185307, -1.04263952, 0))
        part = types.SimpleNamespace(Cylinder=Cylinder, makeLine=lambda a, b: (a.values, b.values))
        first, last = self.measure._reference_shape(shape, part)
        self.assertAlmostEqual(first[2], 6.349042334)
        self.assertEqual(last, Cylinder.Center.values)
        self.assertEqual(first[:2], (184.331627927, -129.148101334))

    def test_task_result_uses_bold_larger_text(self):
        task, selected = self.task()
        self.assertTrue(task.result.font().bold())
        base = task.form.font()
        if base.pointSizeF() > 0:
            self.assertGreaterEqual(task.result.font().pointSizeF(), base.pointSizeF() + 2)
        else:
            self.assertGreater(task.result.font().pixelSize(), base.pixelSize())

    def test_callout_has_white_background_black_rectangle_and_black_text(self):
        rows = [("Radius", "1.25 mm"), ("Center", "1 mm, 2 mm, 3 mm")]
        bitmap = self.measure.callout_image(rows)
        self.assertEqual(bitmap.pixelColor(0, 0).name(), "#000000")
        self.assertEqual(bitmap.pixelColor(2, 2).name(), "#ffffff")
        self.assertEqual(bitmap.pixelColor(bitmap.width() - 1, bitmap.height() - 1).name(), "#000000")
        interior_dark = sum(bitmap.pixelColor(x, y).lightness() < 128
                            for x in range(8, bitmap.width() - 8) for y in range(5, bitmap.height() - 5))
        self.assertGreater(interior_dark, 100, "Labels and values must be painted inside the box")

    def test_callout_expands_for_coordinates_and_multiple_rows(self):
        short = self.measure.callout_image([("Length", "1 mm")])
        long = self.measure.callout_image([("Radius", "1.25 mm"), ("Center", "698.36 mm, 883.79 mm, 1303.9 mm")])
        self.assertGreater(long.width(), short.width())
        self.assertGreater(long.height(), short.height())

    def test_single_line_has_length_instead_of_distance(self):
        class Circle:
            pass
        self.fakes({"Part": fake_module("Part", Circle=Circle)})
        self.patch(self.measure, "_quantity", lambda value, power=1: str(value))
        edge = types.SimpleNamespace(ShapeType="Edge", Curve=object(), Length=17.05,
            CenterOfMass="midpoint", FirstParameter=0, LastParameter=1, valueAt=lambda value: "on edge")
        rows, points = self.measure.single_measurement(edge)
        self.assertEqual(rows, [("Length", "17.05")])
        self.assertEqual(points, ("on edge", "on edge"))

    def test_single_vertex_reports_coordinates(self):
        self.fakes({"Part": fake_module("Part")})
        self.patch(self.measure, "_quantity", lambda value, power=1: str(value))
        vertex = types.SimpleNamespace(ShapeType="Vertex", Point=(1, 2, 3))
        rows, _ = self.measure.single_measurement(vertex)
        self.assertEqual(rows, [("X", "1"), ("Y", "2"), ("Z", "3")])

    def test_face_perimeter_counts_inner_and_outer_loops(self):
        face = types.SimpleNamespace(Edges=[types.SimpleNamespace(Length=5, isSeam=lambda face: False),
                                            types.SimpleNamespace(Length=2, isSeam=lambda face: False),
                                            types.SimpleNamespace(Length=10, isSeam=lambda face: True)])
        self.assertEqual(self.measure._perimeter(face), 7)

    def test_stop_is_idempotent_and_disposes_before_closing_task(self):
        calls = []
        self.patch(self.measure, "_session", types.SimpleNamespace(
            doc=types.SimpleNamespace(Name="Owner"),
            dispose=lambda: calls.append("dispose")))
        self.patch(STUBS.gui, "getDocument", lambda name: object())
        self.patch(STUBS.gui.Control, "closeDialog", lambda: calls.append("close"))
        self.measure.stop()
        self.measure.stop()
        self.assertEqual(calls, ["dispose", "close"])

    def test_stop_closes_owner_dialog_after_switch_without_closing_active_dialog(self):
        owner, active, calls = object(), object(), []
        self.patch(STUBS.gui, "ActiveDocument", active)
        self.patch(STUBS.gui, "getDocument", lambda name: owner if name == "Owner" else active)
        self.patch(STUBS.gui.Control, "closeDialog", lambda doc: calls.append(doc))
        self.patch(self.measure, "_session", types.SimpleNamespace(
            doc=types.SimpleNamespace(Name="Owner"), dispose=lambda: None))
        self.measure.stop()
        self.assertEqual(calls, [owner])
        self.assertIs(STUBS.gui.ActiveDocument, active)

    def test_stop_with_deleted_owner_leaves_other_dialog_untouched(self):
        calls = []
        self.patch(STUBS.gui, "activeDocument", lambda: object())
        self.patch(STUBS.gui.Control, "activeDialog", lambda doc: True)
        self.patch(STUBS.gui.Control, "closeDialog", lambda *args: calls.append(args))
        self.patch(self.measure, "_session", types.SimpleNamespace(doc=None, dispose=lambda: None))
        self.measure.stop()
        self.assertEqual(calls, [])

    def test_stop_with_deleted_owner_closes_legacy_global_dialog(self):
        calls = []
        self.patch(STUBS.gui, "activeDocument", lambda: object())
        self.patch(STUBS.gui.Control, "activeDialog", lambda: True)
        self.patch(STUBS.gui.Control, "closeDialog", lambda: calls.append("close"))
        self.patch(self.measure, "_session", types.SimpleNamespace(doc=None, dispose=lambda: None))
        self.measure.stop()
        self.assertEqual(calls, ["close"])
        self.assertNoJellyJamsProblems()

    def test_stop_with_deleted_owner_and_no_active_document_closes_global_task(self):
        calls = []
        self.patch(STUBS.gui, "activeDocument", lambda: None)
        self.patch(STUBS.gui.Control, "closeDialog", lambda: calls.append("close"))
        self.patch(self.measure, "_session", types.SimpleNamespace(doc=None, dispose=lambda: None))
        self.measure.stop()
        self.assertEqual(calls, ["close"])
        self.assertNoJellyJamsProblems()

    def test_dispose_detaches_once_and_cancels_pending_refresh(self):
        task, selected = self.task()
        calls = []
        self.patch(STUBS.gui.Selection, "removeObserver", lambda obj: calls.append(obj))
        task.timer.start(100)
        task.queue()
        task.dispose()
        task.dispose()
        self.assertEqual(calls, [task])
        self.assertFalse(task.timer.isActive())
        task.result.setText("closed")
        task.refresh()
        self.assertEqual(task.result.text(), "closed")

    def test_destroyed_form_releases_session_and_annotation(self):
        task, selected = self.task()
        calls = []
        self.patch(STUBS.gui.Selection, "removeObserver", lambda obj: calls.append(obj))
        self.patch(self.measure, "_session", task)
        task.on_destroyed()
        self.assertIsNone(self.measure._session)
        self.assertTrue(task.closed)
        self.assertEqual(calls, [task])

    def test_closed_task_timer_cannot_stop_a_later_session(self):
        task, selected = self.task()
        task.closed = True
        calls = []
        self.patch(self.measure, "stop", lambda: calls.append("stop"))
        task.check()
        self.assertEqual(calls, [])

    def test_plain_then_additive_picks_keep_chronological_order_for_three_point_angle(self):
        task, selected = self.task()
        obj = object()
        def unsupported(*args):
            raise ValueError("geometry is stubbed")
        self.patch(self.measure, "measurement", unsupported)
        selected.append((obj, "Vertex1"))
        task.addSelection()
        task.refresh()
        selected.clear()
        task.clearSelection()
        selected.append((obj, "Vertex2"))
        task.addSelection()
        task.refresh()
        selected.append((obj, "Vertex3"))
        task.addSelection()
        task.refresh()
        self.assertEqual(task.items, [(obj, "Vertex1"), (obj, "Vertex2"), (obj, "Vertex3")])

    def test_front_window_change_ends_measure_even_if_document_keeps_last_view(self):
        task, selected = self.task()
        task.view = object()
        self.patch(self.measure, "_session", task)
        self.patch(STUBS.app, "ActiveDocument", task.doc)
        self.patch(STUBS.gui, "ActiveDocument", types.SimpleNamespace(activeView=lambda: task.view))
        fc = self.module("jellyjams.fcgui")
        self.patch(fc, "jellyjams_active", lambda: True)
        self.patch(fc, "main_window", lambda: types.SimpleNamespace(getActiveWindow=lambda: None))
        calls = []
        self.patch(self.measure, "stop", lambda: calls.append("stop"))
        task.check()
        self.assertEqual(calls, ["stop"])

    def test_dispose_forgets_scene_data_when_view_already_deleted(self):
        task, selected = self.task()
        self.patch(STUBS.gui.Selection, "removeObserver", lambda obj: None)
        def deleted():
            raise RuntimeError("the old view has been deleted")
        task.view = types.SimpleNamespace(getSceneGraph=deleted)
        task.node = object()
        task.callout_rows = [("Length", "5 mm")]
        task.callout_bitmap = object()
        task.dispose()
        self.assertIsNone(task.node)
        self.assertEqual(task.callout_rows, [])
        self.assertIsNone(task.callout_bitmap)


class Test14NamingRules(HarnessCase):
    def setUp(self):
        super().setUp()
        self.rules = self.module("jellyjams.naming_rules")

    def test_numbered_names(self):
        rules = self.rules
        self.assertEqual(rules.next_number("Sketch", ["Sketch1", "Sketch4", "Boss-Extrude1"]), 5)
        self.assertEqual(rules.numbered_name("Sketch", ["Sketch1", "Sketch4", "Boss-Extrude1"]), "Sketch5")
        self.assertEqual(rules.numbered_name("Boss-Extrude", ["Sketch1", "Sketch4", "Boss-Extrude1"]), "Boss-Extrude2")
        self.assertEqual(rules.numbered_name("Boss-Extrude", ["Sketch1"]), "Boss-Extrude1")
        self.assertEqual(rules.next_number("Sketch", ["Sketch001"]), 2)
        self.assertEqual(rules.next_number("Sketch", ["Sketch"]), 1)
        self.assertEqual(rules.next_number("Sketch", ["MySketch3", "Sketch 2", "Sketch2a"]), 1)
        self.assertEqual(rules.next_number("Fillet", ["Fillet7"]), 8)
        self.assertEqual(rules.numbered_name("Dimension", []), "Dimension1")
        self.assertEqual(rules.numbered_name("Sheet Format", ["Sheet Format1"]), "Sheet Format2")

    def test_fixed_names(self):
        fixed = self.rules.fixed_name
        self.assertEqual(fixed("Top Plane", "XY_Plane", []), "Top Plane")
        self.assertEqual(fixed("Top Plane", "Top Plane001", ["Top Plane"]), "Top Plane2")
        self.assertEqual(fixed("Mates", "Joints", ["Mates"]), "Mates2")
        self.assertEqual(fixed("Top Plane", "Top Plane3", ["Top Plane"]), "Top Plane3")
        self.assertEqual(fixed("Top Plane", "Top Plane", []), "Top Plane")
        self.assertEqual(fixed("Top Plane", "Top Plane3", ["Top Plane3"]), "Top Plane")
        self.assertEqual(fixed("Top Plane", "XY_Plane", ["Top Plane", "Top Plane2"]), "Top Plane3")
        self.assertEqual(fixed("Front Plane", "XZ_Plane", ["Front Plane", "Front Plane5"]), "Front Plane6")

    def test_standard_3_view(self):
        name = self.rules.standard3_name
        self.assertEqual(self.rules.STANDARD_3_VIEW, "Standard 3 View")
        self.assertEqual(name([]), "Standard 3 View")
        self.assertEqual(name(["Standard 3 View"]), "Standard 3 View2")
        self.assertEqual(name(["Standard 3 View2"]), "Standard 3 View3")
        self.assertEqual(name(["Standard 3 View", "Standard 3 View2"]), "Standard 3 View3")

    def test_components_and_fixed_marker(self):
        rules = self.rules
        self.assertEqual(rules.instance_base("(f) Plate<2>"), "Plate")
        self.assertEqual(rules.instance_base("Shaft<12>"), "Shaft")
        self.assertEqual(rules.instance_base("Plate"), "Plate")
        self.assertEqual(rules.instance_name("Shaft", []), "Shaft<1>")
        self.assertEqual(rules.instance_name("Shaft", ["(f) Shaft<1>", "Shaft<2>"]), "Shaft<3>")
        self.assertEqual(rules.instance_name("Plate", ["Shaft<1>", "Shaft<2>"]), "Plate<1>")
        self.assertEqual(rules.fixed_marker("Motor", True), "(f) Motor")
        self.assertEqual(rules.fixed_marker("(f) Motor", False), "Motor")
        self.assertEqual(rules.fixed_marker("(f) Motor", True), "(f) Motor")
        self.assertEqual(rules.fixed_marker("Motor", False), "Motor")

    def test_mate_bases(self):
        base = self.rules.mate_base
        quantity = types.SimpleNamespace(Value=5.0)
        zero = types.SimpleNamespace(Value=0.0)
        cases = [("Fixed", None, "Lock"), ("Revolute", None, "Hinge"), ("Cylindrical", None, "Concentric"),
                 ("Slider", None, "Slider"), ("Ball", None, "Ball Joint"), ("Distance", 0, "Coincident"),
                 ("Distance", 1e-10, "Coincident"), ("Distance", "abc", "Coincident"), ("Distance", zero, "Coincident"),
                 ("Distance", 5, "Distance"), ("Distance", quantity, "Distance"), ("Parallel", None, "Parallel"),
                 ("Perpendicular", None, "Perpendicular"), ("Angle", None, "Angle"), ("RackPinion", None, "Rack Pinion"),
                 ("Screw", None, "Screw"), ("Gears", None, "Gear"), ("Belt", None, "Belt"), ("Weird", None, None)]
        for joint_type, distance, expected in cases:
            self.assertEqual(base(joint_type, distance), expected, (joint_type, distance))

    def test_default_mate_labels(self):
        defaults = self.rules.default_mate_labels()
        for label in ("Joint", "Fixed", "Lock", "Ball Joint", "BallJoint", "Coincident / Distance",
                      "Coincident/Distance", "RackPinion", "Rack Pinion", "Distance", "Gears", "Gear"):
            self.assertIn(label, defaults)
        self.assertNotIn("Front bearing", defaults)
        self.assertNotIn("Coaxial", defaults, "words of other UI languages arrive only through `extra`")
        extra = self.rules.default_mate_labels(("Mi Junta",))
        self.assertIn("Mi Junta", extra)
        self.assertIn("MiJunta", extra)

    def test_joint_type_word_labels(self):
        """A JointType change makes FreeCAD rewrite "Ball Joint1" as "Fixed Joint1"; such
        labels are still defaults and get the SolidWorks mate name."""
        rules = self.rules
        defaults = rules.default_mate_labels()
        self.assertEqual(len(defaults), 48)
        for joint_type in rules.JOINT_TYPES:
            self.assertIn(joint_type + " Joint", defaults)
            self.assertIn(joint_type + "Joint", defaults)
        for label in ("Fixed Joint", "FixedJoint", "RackPinion Joint", "RackPinionJoint", "Gears Joint"):
            self.assertIn(label, defaults)
        extra = rules.default_mate_labels(("Mi Junta",))
        for label in ("Mi Junta Joint", "Mi JuntaJoint", "MiJuntaJoint"):
            self.assertIn(label, extra)
        self.assertTrue(defaults < extra)
        self.assertEqual(rules.mate_label("Fixed Joint1", "Lock", [], defaults), "Lock1")
        self.assertEqual(rules.mate_label("RevoluteJoint3", "Hinge", [], defaults), "Hinge1")
        self.assertEqual(rules.mate_label("Gears Joint2", "Gear", ["Gear1"], defaults), "Gear2")
        self.assertEqual(rules.mate_label("Ball Joint1", "Ball Joint", [], defaults), "Ball Joint1")
        self.assertEqual(rules.mate_label("Ball Joint1", "Lock", ["Lock1"], defaults), "Lock2")
        self.assertEqual(rules.mate_label("Bearing Joint1", "Lock", [], defaults), "Bearing Joint1")

    def test_mate_label_worked_example(self):
        defaults = self.rules.default_mate_labels()
        labels = ["Coincident1", "Joint", "Joint001", "CylindricalJoint4", "Front bearing"]
        bases = ["Coincident", "Coincident", "Distance", "Concentric", "Concentric"]
        for index, base in enumerate(bases):
            others = labels[:index] + labels[index + 1:]
            labels[index] = self.rules.mate_label(labels[index], base, others, defaults)
        self.assertEqual(labels, ["Coincident1", "Coincident2", "Distance1", "Concentric1", "Front bearing"])
        label = self.rules.mate_label
        self.assertEqual(label("Coincident1", "Distance", [], defaults), "Distance1")
        self.assertEqual(label("Distance1", "Coincident", [], defaults), "Coincident1")
        self.assertEqual(label("Coincident012", "Coincident", [], defaults), "Coincident1")
        self.assertEqual(label("Lock12", "Lock", [], defaults), "Lock12")
        self.assertEqual(label("Bearing2", "Hinge", [], defaults), "Bearing2")
        self.assertEqual(label("Joint", "Coincident", ["Coincident1", "Coincident4"], defaults), "Coincident5")
        translated = self.rules.default_mate_labels(("Coaxial",))
        self.assertEqual(label("Coaxial3", "Concentric", [], translated), "Concentric1")
        self.assertEqual(label("Coaxial3", "Concentric", [], defaults), "Coaxial3")

    def test_default_drawing_labels(self):
        projection = self.rules.is_default_projection_label
        for label in ("Left", "Left001", "Top 2", "Rear002", "ProjItem", "FrontTopLeft"):
            self.assertTrue(projection(label), label)
        for label in ("My View", "Left View", "left", "Front View", "", "Top ", "Side view", "Xview001"):
            self.assertFalse(projection(label), label)
        self.assertTrue(projection("Xview001", ("Xview",)), "translated Type words come in through `extra`")
        template = self.rules.is_default_template_label
        for label in ("Template", "Template001"):
            self.assertTrue(template(label), label)
        for label in ("Sheet Format1", "My Template", "Templates", "Xsheet 2"):
            self.assertFalse(template(label), label)
        self.assertTrue(template("Xsheet 2", ("Xsheet",)))

    def test_tables(self):
        rules = self.rules
        expected = {
            "Sketcher::SketchObject": "Sketch", "PartDesign::Pad": "Boss-Extrude", "PartDesign::Pocket": "Cut-Extrude",
            "PartDesign::Revolution": "Revolve", "PartDesign::Groove": "Cut-Revolve", "PartDesign::AdditivePipe": "Sweep",
            "PartDesign::SubtractivePipe": "Cut-Sweep", "PartDesign::AdditiveLoft": "Loft",
            "PartDesign::SubtractiveLoft": "Cut-Loft", "PartDesign::Hole": "Hole", "PartDesign::Fillet": "Fillet",
            "PartDesign::Chamfer": "Chamfer", "PartDesign::Draft": "Draft", "PartDesign::Thickness": "Shell",
            "PartDesign::LinearPattern": "LPattern", "PartDesign::PolarPattern": "CirPattern",
            "PartDesign::Mirrored": "Mirror", "PartDesign::MultiTransform": "MultiPattern", "PartDesign::Plane": "Plane",
            "PartDesign::Line": "Axis", "PartDesign::Point": "Point", "Assembly::AssemblyObject": "Assembly",
            "Assembly::BomObject": "Bill of Materials", "TechDraw::DrawPage": "Sheet",
            "TechDraw::DrawSVGTemplate": "Sheet Format", "TechDraw::DrawViewPart": "Drawing View",
            "TechDraw::DrawViewDimension": "Dimension", "TechDraw::DrawViewBalloon": "Balloon",
            "TechDraw::DrawRichAnno": "Note", "TechDraw::DrawLeaderLine": "Leader", "TechDraw::DrawHatch": "Area Hatch",
            "TechDraw::DrawGeomHatch": "Area Hatch", "TechDraw::DrawWeldSymbol": "Weld Symbol",
            "TechDraw::DrawViewClip": "Crop Frame", "TechDraw::DrawViewImage": "Picture",
            "TechDraw::DrawViewSymbol": "Picture",
        }
        names = dict(rules.TYPE_BASE_NAMES)
        self.assertEqual({key: names.get(key) for key in expected}, expected)
        for absent in ("PartDesign::Body", "PartDesign::AdditiveHelix", "TechDraw::DrawViewSection",
                       "TechDraw::DrawViewDetail", "TechDraw::DrawProjGroupItem"):
            self.assertNotIn(absent, names)
        self.assertEqual(dict(rules.PLANE_NAMES), {"XY_Plane": "Top Plane", "XZ_Plane": "Front Plane",
                                                   "YZ_Plane": "Right Plane"})
        self.assertEqual(dict(rules.FOLDER_NAMES), {"Assembly::JointGroup": "Mates", "Assembly::ViewGroup": "Exploded Views",
                                                    "Assembly::BomGroup": "Bills of Materials",
                                                    "Assembly::SimulationGroup": "Motion Studies"})


# ==========================================================================
# 15. Relations rules
# ==========================================================================


class FakeGeometry:
    def __init__(self, type_id):
        self.TypeId = type_id


class FakeConstraint:
    def __init__(self, type_name, first=-2000, first_pos=0, second=-2000, second_pos=0, third=-2000, third_pos=0):
        self.Type = type_name
        self.First, self.FirstPos = first, first_pos
        self.Second, self.SecondPos = second, second_pos
        self.Third, self.ThirdPos = third, third_pos


class FakeSketch:
    """Reference sketch of relations 4.3: Line1, Line2, Circle3, Arc4, Ellipse5,
    Point6, Spline7, plus Partial ellipse8, a hyperbola (Edge9) and one external
    line (Converted1)."""

    TypeId = "Sketcher::SketchObject"

    def __init__(self):
        self.Geometry = [FakeGeometry(t) for t in (
            "Part::GeomLineSegment", "Part::GeomLineSegment", "Part::GeomCircle", "Part::GeomArcOfCircle",
            "Part::GeomEllipse", "Part::GeomPoint", "Part::GeomBSplineCurve", "Part::GeomArcOfEllipse",
            "Part::GeomArcOfHyperbola")]
        self.ExternalGeo = [FakeGeometry("Part::GeomLineSegment"), FakeGeometry("Part::GeomLineSegment"),
                            FakeGeometry("Part::GeomLineSegment")]
        self.vertices = [(0, 1), (0, 2), (1, 1), (1, 2), (2, 3), (3, 1), (3, 2), (3, 3), (4, 3), (5, 1), (6, 1),
                         (6, 2), (-3, 1), (-3, 2), (-1, 1)]
        self.Constraints = []

    def getGeoVertexIndex(self, index):
        return self.vertices[index]


# The 14 relation labels in the catalogue order of relations 4.3 (also the button order).
RELATION_CATALOGUE = ("Horizontal", "Vertical", "Collinear", "Perpendicular", "Parallel", "Tangent",
                      "Concentric", "Midpoint", "Coincident", "Equal", "Symmetric", "Fix", "On entity",
                      "Block")

# Every row of the worked reference table in relations 4.3, in the table's order. In FakeSketch,
# Vertex1 and Vertex2 are the start and end of Line1, Vertex3 and Vertex4 those of Line2, and
# Vertex10 is the sketch point Point6.
RELATION_CASES = [
    (["Edge1"], ["Horizontal", "Vertical", "Block"]),
    (["Edge1", "Edge2"], ["Horizontal", "Vertical", "Collinear", "Perpendicular", "Parallel", "Equal", "Block"]),
    (["Edge1", "H_Axis"], ["Collinear", "Perpendicular", "Parallel"]),
    (["Edge1", "Edge2", "H_Axis"], ["Parallel"]),
    (["ExternalEdge1", "H_Axis"], []),
    (["ExternalEdge1", "Edge1"], ["Collinear", "Perpendicular", "Parallel", "Equal"]),
    (["Edge3", "Edge4"], ["Tangent", "Concentric", "Equal", "Block"]),
    (["Edge1", "Edge3"], ["Tangent", "Block"]),
    (["Edge3", "Edge5"], ["Tangent", "Concentric", "Block"]),
    (["Edge3", "Edge4", "Edge5"], ["Concentric", "Block"]),
    (["Edge7"], ["Block"]),
    (["Edge4", "Edge7"], ["Block"]),
    (["Vertex1"], ["Fix"]),
    (["RootPoint"], []),
    (["Vertex1", "Vertex3"], ["Horizontal", "Vertical", "Coincident"]),
    (["Vertex1", "Vertex2"], ["Horizontal", "Vertical"]),
    (["Vertex1", "RootPoint"], ["Horizontal", "Vertical", "Coincident"]),
    (["Vertex1", "Vertex3", "Vertex10"], ["Horizontal", "Vertical", "Coincident", "Symmetric"]),
    (["Vertex3", "Edge1"], ["Midpoint", "On entity"]),
    (["Vertex3", "ExternalEdge1"], ["Midpoint", "On entity"]),
    (["Vertex3", "H_Axis"], ["On entity"]),
    (["RootPoint", "Edge1"], ["Midpoint", "On entity"]),
    (["RootPoint", "H_Axis"], []),
    (["Vertex1", "Edge1"], []),
    (["Vertex10", "Edge1", "Edge2"], ["On entity"]),
    (["Vertex1", "Edge1", "Edge2"], []),
    (["Vertex3", "Vertex4", "Edge1"], ["Symmetric", "On entity"]),
    (["Vertex1", "Vertex2", "Edge1"], []),
    (["Vertex3", "Edge3"], ["On entity"]),
]


class Test15RelationsRules(HarnessCase):
    def setUp(self):
        super().setUp()
        self.rules = self.module("jellyjams.relations_rules")
        self.sketch = FakeSketch()

    def parse(self, names):
        return self.rules.parse_selection(self.sketch, names)

    def test_worked_reference_table(self):
        for names, expected in RELATION_CASES:
            with self.subTest(selection=names):
                self.assertEqual(list(self.rules.offered_relations(self.parse(names))), expected)
        self.assertEqual(self.parse(["Constraint1"]), [])

    def test_offer_is_the_same_for_every_selection_order(self):
        for names, expected in RELATION_CASES:
            for order in itertools.permutations(names):
                with self.subTest(selection=list(order)):
                    self.assertEqual(list(self.rules.offered_relations(self.parse(order))), expected)

    def test_catalogue_order_and_capability_coverage(self):
        commands = list(self.rules.RELATION_COMMANDS)
        self.assertEqual(len(RELATION_CATALOGUE), 14)
        self.assertEqual(commands, list(RELATION_CATALOGUE))
        self.assertEqual(list(self.rules.RELATION_CAPABILITIES), commands)
        for label, shapes in self.rules.RELATION_CAPABILITIES.items():
            self.assertGreater(len(tuple(shapes)), 0, label)

    def test_offered_relations_agree_with_accepts(self):
        for names, _expected in RELATION_CASES:
            entities = self.parse(names)
            offered = list(self.rules.offered_relations(entities))
            with self.subTest(selection=names):
                for label in offered:
                    self.assertTrue(self.rules.accepts(label, entities), label)
                accepted = [label for label in RELATION_CATALOGUE if self.rules.accepts(label, entities)]
                self.assertEqual(accepted, offered)
        self.assertFalse(self.rules.accepts("Not a relation", self.parse(["Edge1"])))

    def test_entity_labels_and_identity(self):
        labels = [e.label for e in self.parse(["Edge1", "Edge3", "Vertex5", "RootPoint", "H_Axis", "ExternalEdge1"])]
        self.assertEqual(labels, ["Line1", "Circle3", "Point5", "Origin", "Horizontal axis", "Converted1"])
        labels = [e.label for e in self.parse(["Edge4", "Edge5", "Edge6", "Edge7", "Edge8", "Edge9", "V_Axis", "Vertex15",
                                                "Vertex99", "Edge99", "Constraint2", "Bogus"])]
        self.assertEqual(labels, ["Arc4", "Ellipse5", "Point6", "Spline7", "Partial ellipse8", "Edge9",
                                  "Vertical axis", "Origin"])
        line, vertex, external, origin, axis = self.parse(["Edge1", "Vertex3", "ExternalEdge1", "RootPoint", "H_Axis"])
        self.assertEqual((line.is_point, line.geo_id), (False, 0))
        self.assertEqual((vertex.is_point, vertex.geo_id, vertex.pos_id), (True, 1, 1))
        self.assertEqual((external.geo_id, bool(external.external)), (-3, True))
        self.assertEqual((origin.is_point, origin.geo_id, origin.pos_id, bool(origin.origin)), (True, -1, 1, True))
        self.assertEqual((axis.geo_id, bool(axis.axis)), (-1, True))
        self.assertEqual(self.parse(["V_Axis"])[0].geo_id, -2)

    def test_existing_relations(self):
        constraints = [FakeConstraint("Horizontal", 0), FakeConstraint("Coincident", 0, 2, 1, 1),
                       FakeConstraint("Distance", 0), FakeConstraint("Block", 1),
                       FakeConstraint("PointOnObject", 2, 3, 0), FakeConstraint("InternalAlignment", 4, 0, 7),
                       FakeConstraint("Coincident", 0, 1, -1, 1)]
        existing = self.rules.existing_relations
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["Edge1"]))],
                         [(0, "Horizontal"), (1, "Coincident"), (4, "On entity"), (6, "Coincident")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["Vertex2"]))], [(1, "Coincident")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["Vertex1"]))], [(6, "Coincident")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["Edge2"]))],
                         [(1, "Coincident"), (3, "Blocked")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["Edge5"]))], [(5, "Internal alignment")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["H_Axis"]))], [(6, "Coincident")])
        self.assertEqual([tuple(r) for r in existing(constraints, self.parse(["RootPoint"]))], [(6, "Coincident")])

    def test_deletion_order(self):
        self.assertEqual(list(self.rules.deletion_order([1, 3, 1, 2])), [3, 2, 1])
        self.assertEqual(list(self.rules.deletion_order([])), [])

    def test_tables(self):
        self.assertEqual(dict(self.rules.RELATION_COMMANDS), {
            "Horizontal": "Sketcher_ConstrainHorizontal", "Vertical": "Sketcher_ConstrainVertical",
            "Collinear": "Sketcher_ConstrainTangent", "Parallel": "Sketcher_ConstrainParallel",
            "Perpendicular": "Sketcher_ConstrainPerpendicular", "Tangent": "Sketcher_ConstrainTangent",
            "Concentric": "Sketcher_ConstrainCoincident", "Coincident": "Sketcher_ConstrainCoincident",
            "On entity": "Sketcher_ConstrainPointOnObject", "Midpoint": "Sketcher_ConstrainSymmetric",
            "Symmetric": "Sketcher_ConstrainSymmetric", "Equal": "Sketcher_ConstrainEqual",
            "Fix": "Sketcher_ConstrainLock", "Block": "Sketcher_ConstrainBlock"})
        names = dict(self.rules.CONSTRAINT_NAMES)
        self.assertEqual(names.get("PointOnObject"), "On entity")
        self.assertEqual(names.get("Block"), "Blocked")
        self.assertNotIn("Distance", names)
        stems = {key: value[1] for key, value in dict(self.rules.GEOMETRY_KINDS).items()}
        self.assertEqual(stems.get("Part::GeomLineSegment"), "Line")
        self.assertEqual(stems.get("Part::GeomArcOfEllipse"), "Partial ellipse")
        self.assertEqual(stems.get("Part::GeomBSplineCurve"), "Spline")


# ==========================================================================
# 16. Mate rules
# ==========================================================================

DISTANCE = "Distance\u2026"


class Test16MateRules(HarnessCase):
    def setUp(self):
        super().setUp()
        self.rules = self.module("jellyjams.mate_rules")

    def test_kind_from(self):
        cases = [(("Face", "Part::GeomPlane"), "Planar face"), (("Face", "Plane"), "Planar face"),
                 (("Face", "Cylinder"), "Cylindrical face"), (("Face", "Cone"), "Conical face"),
                 (("Face", "Sphere"), "Spherical face"), (("Face", "Toroid"), "Face"),
                 (("Face", "BSplineSurface"), "Face"), (("Edge", "Line"), "Linear edge"),
                 (("Edge", "LineSegment"), "Linear edge"), (("Edge", "Part::GeomLineSegment"), "Linear edge"),
                 (("Edge", "Circle"), "Circular edge"), (("Edge", "ArcOfCircle"), "Circular edge"),
                 (("Edge", "Ellipse"), "Edge"), (("Vertex", None), "Point"), ((None, None), "Component")]
        for args, expected in cases:
            self.assertEqual(self.rules.kind_from(*args), expected, args)

    def test_capability_matrix(self):
        offered = self.rules.offered_mates
        cases = [
            ("Planar face", "Planar face", ["Coincident", DISTANCE, "Parallel", "Perpendicular", "Angle"]),
            ("Cylindrical face", "Cylindrical face", ["Hinge", "Slider", "Concentric", "Tangent", DISTANCE,
                                                      "Parallel", "Perpendicular", "Angle"]),
            ("Circular edge", "Conical face", ["Concentric", "Parallel", "Perpendicular", "Angle"]),
            ("Cylindrical face", "Planar face", ["Tangent", DISTANCE]),
            ("Planar face", "Cylindrical face", ["Tangent", DISTANCE]),
            ("Linear edge", "Cylindrical face", ["Slider", "Concentric", "Parallel", "Perpendicular", "Angle"]),
            ("Point", "Planar face", ["Coincident", DISTANCE]),
            ("Spherical face", "Spherical face", ["Ball Joint", "Tangent", DISTANCE]),
            ("Point", "Point", ["Coincident", DISTANCE]),
            ("Spherical face", "Point", ["Ball Joint", "Coincident", DISTANCE]),
            ("Linear edge", "Linear edge", ["Slider", "Coincident", DISTANCE, "Parallel", "Perpendicular", "Angle"]),
            ("Linear edge", "Planar face", ["Coincident", DISTANCE]),
            ("Face", "Face", []),
            ("Spherical face", "Planar face", ["Tangent", DISTANCE]),
            ("Cylindrical face", "Edge", []),
            ("Component", "Planar face", []),
        ]
        rules = self.rules
        for kind_a, kind_b, expected in cases:
            mates = list(offered(kind_a, kind_b))
            self.assertEqual(mates, expected, (kind_a, kind_b))
            self.assertEqual(list(offered(kind_b, kind_a)), mates, "the order of the picks does not matter")
            removed = [rules.removed_freedoms(mate, kind_a, kind_b) for mate in mates]
            self.assertEqual(removed, sorted(removed, reverse=True), "most constraining mate first")
        self.assertEqual(list(offered("Planar face", "Planar face", True)), [])
        self.assertIsNone(rules.removed_freedoms("Hinge", "Planar face", "Planar face"))
        self.assertIsNone(rules.removed_freedoms("No such mate", "Point", "Point"))
        self.assertEqual(set(rules.MATE_CAPABILITIES), set(rules.MATE_COMMANDS))

    def test_commands_and_hints(self):
        self.assertEqual(dict(self.rules.MATE_COMMANDS), {
            "Coincident": "Assembly_CreateJointDistance", "Parallel": "Assembly_CreateJointParallel",
            "Perpendicular": "Assembly_CreateJointPerpendicular", "Concentric": "Assembly_CreateJointCylindrical",
            DISTANCE: "Assembly_CreateJointDistance", "Angle": "Assembly_CreateJointAngle",
            "Hinge": "Assembly_CreateJointRevolute", "Slider": "Assembly_CreateJointSlider",
            "Ball Joint": "Assembly_CreateJointBall", "Tangent": "Assembly_CreateJointDistance"})
        hint = self.rules.hint
        texts = [hint(1, False, []), hint(3, False, []), hint(2, True, []), hint(2, False, [])]
        for text in texts:
            self.assertTrue(text)
        self.assertEqual(len(set(texts)), 4)
        self.assertIsNone(hint(2, False, ["Coincident"]))


# ==========================================================================
# 17. Workbench-switch preferences and assembly helpers
# ==========================================================================

SWITCH_NAMES = {P_ASSEMBLY: "Assembly", P_PARTDESIGN: "Part Design", P_TECHDRAW_GENERAL: "TechDraw"}
SWITCH_STATES = ("absent", True, False)   # what a user's SwitchToWB can be


def set_switch(group, state):
    if state == "absent":
        param(group).RemBool("SwitchToWB")
    else:
        param(group).SetBool("SwitchToWB", state)


def switch_state(group):
    """"absent", True or False, read the way FreeCAD stores it."""
    if "SwitchToWB" not in param(group).GetBools():
        return "absent"
    return param(group).GetBool("SwitchToWB", None)


def record_for(state):
    return {"absent": "absent", True: "1", False: "0"}[state]


class Test17SwitchPrefs(HarnessCase):
    def setUp(self):
        super().setUp()
        self.prefs = self.module("jellyjams.switch_prefs", fresh=True)

    def backup(self, group=P_ASSEMBLY):
        return param(P_OWN).GetString(SWITCH_BACKUPS[group], "")

    def pending(self):
        return {group: self.backup(group) for group in SWITCH_BACKUPS}

    def test_targets(self):
        self.assertEqual(self.prefs.SWITCH_KEY, "SwitchToWB")
        self.assertEqual([tuple(target) for target in self.prefs.TARGETS],
                         [(group, key, SWITCH_NAMES[group]) for group, key in SWITCH_BACKUPS.items()])

    def test_absent_key_round_trip(self):
        self.assertFalse(self.prefs.is_applied())
        self.prefs.apply()
        self.assertTrue(self.prefs.is_applied())
        for group in SWITCH_BACKUPS:
            self.assertIn("SwitchToWB", param(group).GetBools(), group)
            self.assertFalse(param(group).GetBool("SwitchToWB", True), group)
            self.assertEqual(self.backup(group), "absent", group)
        self.prefs.restore()
        self.assertFalse(self.prefs.is_applied())
        for group, key in SWITCH_BACKUPS.items():
            self.assertNotIn("SwitchToWB", param(group).GetBools(), group)
            self.assertNotIn(key, param(P_OWN).GetStrings())
        self.assertNoJellyJamsProblems()

    def test_explicit_values_round_trip(self):
        for value in (True, False):
            with self.subTest(value=value):
                STUBS.reset()
                self.prefs = self.module("jellyjams.switch_prefs", fresh=True)
                param(P_ASSEMBLY).SetBool("SwitchToWB", value)
                self.prefs.apply()
                self.assertEqual(self.backup(), "1" if value else "0")
                self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))
                self.prefs.restore()
                self.assertIn("SwitchToWB", param(P_ASSEMBLY).GetBools())
                self.assertEqual(param(P_ASSEMBLY).GetBool("SwitchToWB", not value), value)
                self.assertNotIn("OriginalSwitchToWB", param(P_OWN).GetStrings())

    def test_every_combination_round_trips_exactly(self):
        groups = list(SWITCH_BACKUPS)
        for states in itertools.product(SWITCH_STATES, repeat=len(groups)):
            with self.subTest(states=states):
                STUBS.reset()
                self.prefs = self.module("jellyjams.switch_prefs", fresh=True)
                for group, state in zip(groups, states):
                    set_switch(group, state)
                self.prefs.apply()
                self.assertTrue(self.prefs.is_applied())
                for group, state in zip(groups, states):
                    self.assertIs(switch_state(group), False, group)
                    self.assertEqual(self.backup(group), record_for(state), group)
                self.prefs.restore()
                self.assertFalse(self.prefs.is_applied())
                self.assertEqual([switch_state(group) for group in groups], list(states))
                for key in SWITCH_BACKUPS.values():
                    self.assertNotIn(key, param(P_OWN).GetStrings())
                self.assertEqual(self.lines(), [], "apply and restore print nothing")

    def test_quit_revert_and_reapply_cycle(self):
        set_switch(P_PARTDESIGN, True)
        self.prefs.apply()
        self.prefs.restore()   # quit guard: Close pressed
        self.assertTrue(param(P_PARTDESIGN).GetBool("SwitchToWB", False))
        self.prefs.apply()     # quit cancelled
        self.assertEqual(self.backup(P_PARTDESIGN), "1", "the re-apply takes a fresh record")
        self.assertFalse(param(P_PARTDESIGN).GetBool("SwitchToWB", True))
        self.prefs.restore()
        self.assertEqual(switch_state(P_PARTDESIGN), True)
        self.assertEqual(switch_state(P_ASSEMBLY), "absent")
        self.assertEqual(switch_state(P_TECHDRAW_GENERAL), "absent")

    def test_pending_record_not_overwritten(self):
        for group, key in SWITCH_BACKUPS.items():
            with self.subTest(group=group):
                STUBS.reset()
                self.prefs = self.module("jellyjams.switch_prefs", fresh=True)
                param(group).SetBool("SwitchToWB", False)
                param(P_OWN).SetString(key, "1")
                self.prefs.apply()
                self.prefs.apply()
                self.assertEqual(self.backup(group), "1")
                self.prefs.restore()
                self.assertTrue(param(group).GetBool("SwitchToWB", False))
                self.assertNotIn(key, param(P_OWN).GetStrings())

    def test_restore_without_record_touches_nothing(self):
        for group in SWITCH_BACKUPS:
            param(group).SetBool("SwitchToWB", False)
        self.prefs.restore()
        for group in SWITCH_BACKUPS:
            self.assertFalse(param(group).GetBool("SwitchToWB", True), group)
        self.assertEqual(self.lines(), [])

    def test_restore_with_only_some_records(self):
        for group in SWITCH_BACKUPS:
            param(group).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalTechDrawSwitchToWB", "absent")
        self.prefs.restore()
        self.assertNotIn("SwitchToWB", param(P_TECHDRAW_GENERAL).GetBools())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))
        self.assertFalse(param(P_PARTDESIGN).GetBool("SwitchToWB", True))
        self.assertEqual(self.pending(), {group: "" for group in SWITCH_BACKUPS})
        self.assertEqual(self.lines(), [], "restore() is quiet; only recover() announces")

    def test_recover(self):
        self.prefs.recover()
        self.assertEqual(self.lines(), [])
        for group, key in SWITCH_BACKUPS.items():
            for record, expected in (("1", True), ("0", False), ("absent", None)):
                with self.subTest(group=group, record=record):
                    STUBS.records.clear()
                    param(group).SetBool("SwitchToWB", False)
                    param(P_OWN).SetString(key, record)
                    self.prefs.recover()
                    if expected is None:
                        self.assertNotIn("SwitchToWB", param(group).GetBools())
                    else:
                        self.assertEqual(param(group).GetBool("SwitchToWB", not expected), expected)
                    self.assertNotIn(key, param(P_OWN).GetStrings())
                    messages = self.jj("message")
                    self.assertEqual(len(messages), 1, self.lines())
                    self.assertIn(SWITCH_NAMES[group], messages[0])
                    self.assertNoJellyJamsProblems()
        STUBS.records.clear()
        param(P_ASSEMBLY).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalSwitchToWB", "garbage")
        self.prefs.recover()
        self.assertEqual(len(self.jj("warning")), 1)
        self.assertNotIn("OriginalSwitchToWB", param(P_OWN).GetStrings())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))

    def test_recover_with_only_some_records(self):
        for group in SWITCH_BACKUPS:
            param(group).SetBool("SwitchToWB", False)
        param(P_OWN).SetString("OriginalSwitchToWB", "1")
        param(P_OWN).SetString("OriginalPartDesignSwitchToWB", "absent")
        self.prefs.recover()
        self.assertTrue(param(P_ASSEMBLY).GetBool("SwitchToWB", False))
        self.assertNotIn("SwitchToWB", param(P_PARTDESIGN).GetBools())
        self.assertIn("SwitchToWB", param(P_TECHDRAW_GENERAL).GetBools())
        self.assertFalse(param(P_TECHDRAW_GENERAL).GetBool("SwitchToWB", True), "no record: untouched")
        messages = self.jj("message")
        self.assertEqual(len(messages), 2, self.lines())
        self.assertIn("Assembly", messages[0])
        self.assertIn("Part Design", messages[1])
        self.assertNoJellyJamsProblems()

    def test_corrupt_records(self):
        for group, key in SWITCH_BACKUPS.items():
            with self.subTest(group=group, when="recover"):
                STUBS.reset()
                self.prefs = self.module("jellyjams.switch_prefs", fresh=True)
                param(group).SetBool("SwitchToWB", False)
                param(P_OWN).SetString(key, "garbage")
                self.prefs.recover()
                warnings = self.jj("warning")
                self.assertEqual(len(warnings), 1, self.lines())
                self.assertIn(SWITCH_NAMES[group], warnings[0])
                self.assertNotIn(key, param(P_OWN).GetStrings())
                self.assertFalse(param(group).GetBool("SwitchToWB", True), "the setting is left as it is")
            with self.subTest(group=group, when="apply"):
                STUBS.reset()
                self.prefs = self.module("jellyjams.switch_prefs", fresh=True)
                param(group).SetBool("SwitchToWB", True)
                param(P_OWN).SetString(key, "  2  ")
                self.prefs.apply()
                self.assertEqual(len(self.jj("warning")), 1, self.lines())
                self.assertEqual(self.backup(group), "1", "a damaged record is replaced by a fresh one")
                self.assertFalse(param(group).GetBool("SwitchToWB", True))
                self.prefs.restore()
                self.assertTrue(param(group).GetBool("SwitchToWB", False))
                self.assertNotIn(key, param(P_OWN).GetStrings())

    def test_blank_record_counts_as_none(self):
        param(P_PARTDESIGN).SetBool("SwitchToWB", True)
        param(P_OWN).SetString("OriginalPartDesignSwitchToWB", "   ")
        self.prefs.recover()
        self.assertEqual(self.lines(), [])
        self.assertTrue(param(P_PARTDESIGN).GetBool("SwitchToWB", False))
        self.prefs.apply()
        self.assertEqual(self.backup(P_PARTDESIGN), "1")
        self.prefs.restore()
        self.assertEqual(switch_state(P_PARTDESIGN), True)

    def test_one_failing_group_does_not_stop_the_others(self):
        params_module = self.module("jellyjams.params")
        real_group = params_module.group

        def group(path):
            if path == P_TECHDRAW_GENERAL:
                raise RuntimeError("TechDraw preferences refused by the harness")
            return real_group(path)

        self.patch(params_module, "group", group)
        self.prefs.apply()
        warnings = self.jj("warning")
        self.assertEqual(len(warnings), 1, self.lines())
        self.assertIn("TechDraw", warnings[0])
        self.assertTrue(self.prefs.is_applied())
        self.assertFalse(param(P_ASSEMBLY).GetBool("SwitchToWB", True))
        self.assertFalse(param(P_PARTDESIGN).GetBool("SwitchToWB", True))
        self.assertEqual(self.backup(P_TECHDRAW_GENERAL), "")
        self.prefs.restore()
        self.assertEqual(switch_state(P_ASSEMBLY), "absent")
        self.assertEqual(switch_state(P_PARTDESIGN), "absent")
        self.assertEqual(self.pending(), {group: "" for group in SWITCH_BACKUPS})
        self.assertEqual(self.jj("error"), [])


class Test17Assembly(HarnessCase):
    def test_pure_helpers(self):
        commands = self.module("jellyjams.assembly_commands")
        drop = self.module("jellyjams.assembly_drop")
        self.assertEqual(commands.next_assembly_name(["Part", "Assembly1"]), "Assembly2")
        self.assertEqual(commands.next_assembly_name([]), "Assembly1")
        self.assertEqual(commands.next_assembly_name(["Assembly1", "Assembly3"]), "Assembly2")
        self.assertEqual(commands.next_assembly_name(["Assembly2"]), "Assembly1")
        for (dx, dy), (axis, angle) in (((30, 0), ((0, 1, 0), 12.0)), ((0, 10), ((-1, 0, 0), 4.0)),
                                        ((3, 4), ((-0.8, 0.6, 0), 2.0))):
            got_axis, got_angle = commands.drag_rotation(dx, dy)
            for got, want in zip(got_axis, axis):
                self.assertAlmostEqual(got, want, places=9)
            self.assertAlmostEqual(got_angle, angle, places=9)
            # The axis lies in the screen plane at right angles to the drag; the angle grows
            # linearly with the drag length.
            self.assertAlmostEqual(got_axis[0] * dx + got_axis[1] * dy, 0.0, places=9)
            self.assertAlmostEqual(commands.drag_rotation(2 * dx, 2 * dy)[1], 2 * got_angle, places=9)
        self.assertIsNone(commands.drag_rotation(0, 0))
        self.assertEqual(list(drop.filter_fcstd(["a.FCStd", "b.fcstd", "c.step", "d.FCSTD", "e.png", "fcstd"])),
                         ["a.FCStd", "b.fcstd", "d.FCSTD"])
        self.assertTrue(drop.is_portal_path("/run/user/1000/doc/abc123/Shaft.FCStd"))
        self.assertFalse(drop.is_portal_path("/home/user/Shaft.FCStd"))
        self.assertFalse(drop.is_portal_path("/run/user/1000/Shaft.FCStd"))


# ==========================================================================
# 18. Dialog terms
# ==========================================================================

PAD_FORM = "PartDesignGui::TaskPadPocketParameters"
FORM_ROOTS = [PAD_FORM, "PartDesignGui::TaskRevolutionParameters", "TaskAssemblyCreateJoint",
              "TaskAssemblyInsertLink", "TechDrawGui::TaskProjGroup", "TechDrawGui::TaskSectionView",
              "TechDrawGui::TaskDetail", "TechDrawGui::TaskComplexSection", "TechDrawGui::TaskDimension",
              "TechDrawGui::TaskBalloon", "TechDrawGui::TaskRichAnno", "TechDrawGui::TaskLeaderLine",
              "TechDrawGui::TaskHatch", "TechDrawGui::TaskCenterLine", "TaskWeldingSymbol",
              "TechDrawGui::TaskSurfaceFinishSymbols", "TechDrawGui::TaskLineDecor"]
PRESETS = [EN_DASH, "0.13 mm", "0.18 mm", "0.25 mm", "0.35 mm", "0.5 mm", "0.7 mm", "1 mm"]


class FakeQuantitySpinBox(QtWidgets.QDoubleSpinBox):
    """Python stand-in for Gui::QuantitySpinBox with its 'rawValue' property."""

    def _raw(self):
        return self.value()

    def _set_raw(self, value):
        self.setValue(float(value))

    rawValue = QtCore.Property(float, _raw, _set_raw)


def named(widget, name, text=None):
    widget.setObjectName(name)
    if text is not None:
        if isinstance(widget, QtWidgets.QGroupBox):
            widget.setTitle(text)
        else:
            widget.setText(text)
    return widget


def combo(name, items, current=0):
    box = QtWidgets.QComboBox()
    box.setObjectName(name)
    for index, item in enumerate(items):
        box.addItem(item, "data-%d" % index)
    box.setCurrentIndex(current)
    return box


def form(root, widgets, parent=None):
    widget = QtWidgets.QWidget(parent)
    widget.setObjectName(root)
    layout = QtWidgets.QVBoxLayout(widget)
    for child in widgets:
        layout.addWidget(child)
    return widget


def pad_form(parent=None, change_mode_items=5):
    widgets = [named(QtWidgets.QLabel(), "sidesLabel", "Sides"), named(QtWidgets.QLabel(), "side1Label", "Side 1"),
               named(QtWidgets.QLabel(), "textLabel1", "Type"), named(QtWidgets.QLabel(), "labelLength", "Length"),
               named(QtWidgets.QCheckBox(), "checkBoxReversed", "Reversed"),
               named(QtWidgets.QGroupBox(), "groupBox", "Direction"),
               combo("changeMode", ["Dimension", "To last", "To first", "Up to face", "Up to shape",
                                    "Extra"][:change_mode_items], current=2),
               combo("changeMode2", ["Dimension", "To last", "To first", "Up to face", "Up to shape"]),
               combo("sidesMode", ["One sided", "Two sided", "Symmetric"], current=1)]
    return form(PAD_FORM, widgets, parent)


def items(box):
    return [box.itemText(i) for i in range(box.count())]


class Test18DialogTerms(HarnessCase):
    def setUp(self):
        super().setUp()
        STUBS.set_active_workbench(WB)
        self.terms = self.module("jellyjams.dialog_terms", fresh=True)
        self.addCleanup(self.quiet_stop)

    def quiet_stop(self):
        with contextlib.suppress(Exception):
            self.terms.stop()

    def test_catalog(self):
        data = self.module("jellyjams.dialog_terms_data")
        forms = dict(data.FORMS)
        self.assertEqual(sorted(forms), sorted(FORM_ROOTS))
        pad = forms[PAD_FORM]
        self.assertEqual(list(pad["combos"]["changeMode"]), ["Blind", "Through All", "Up To Next", "Up To Surface",
                                                            "Up To Body"])
        self.assertEqual(list(pad["combos"]["sidesMode"]), ["Direction 1", "Direction 1 and 2", "Mid Plane"])
        self.assertNotIn("sidesLabel", pad["texts"], "SolidWorks has no counterpart of FreeCAD's 'Mode' label")
        self.assertEqual(list(forms["TaskAssemblyCreateJoint"]["combos"]["jointType"]), [
            "Lock", "Hinge", "Concentric", "Slider", "Ball", "Coincident / Distance", "Parallel", "Perpendicular",
            "Angle", "Rack Pinion", "Screw", "Gear", "Belt"])
        self.assertNotIn("distanceLabel", forms["TaskAssemblyCreateJoint"]["texts"])
        self.assertNotIn("pbTracker", forms["TechDrawGui::TaskLeaderLine"]["texts"])
        for name in ("pbArrowSymbol", "pbOtherSymbol"):
            self.assertNotIn(name, forms["TaskWeldingSymbol"]["texts"])
        # Widgets FreeCAD rewrites itself are never in the catalog texts.
        for root, names in dict(data.STATE_WIDGETS).items():
            for name in names:
                self.assertNotIn(name, forms[root]["texts"], (root, name))
        tips = dict(forms["TechDrawGui::TaskProjGroup"]["tooltips"])
        self.assertEqual(sorted(tips), sorted("chkView%d" % index for index in range(10)))
        self.assertEqual(dict(tips["chkView9"])["FrontBottomRight"], "Isometric (front bottom right)")
        self.assertEqual(dict(tips["chkView0"])["LeftFrontTop"], "Isometric (front top left)")
        self.assertEqual(dict(tips["chkView4"])["Rear"], "Back")
        for plain in ("Top", "Bottom", "Left", "Right", "Front"):
            self.assertNotIn(plain, dict(tips["chkView4"]), plain)
        for root, entry in forms.items():
            fix = entry.get("scale_fix")
            if root in ("TechDrawGui::TaskSectionView", "TechDrawGui::TaskComplexSection"):
                self.assertEqual(tuple(fix), ("cmbScaleType", "sbScale"), root)
            else:
                self.assertFalse(fix, root)
            self.assertEqual(bool(entry.get("weight_presets")), root == "TechDrawGui::TaskLineDecor", root)
        self.assertEqual(tuple(data.WEIGHT_PRESETS_MM), (0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0))
        self.assertEqual(data.WEIGHT_LABEL, "ISO 128 preset")
        self.assertEqual(data.PLACEHOLDER, EN_DASH)

    def test_relabel_and_no_second_write(self):
        pad = pad_form()
        self.assertGreater(self.terms.process_form(pad), 0)
        texts = {name: pad.findChild(QtWidgets.QWidget, name) for name in
                 ("sidesLabel", "side1Label", "textLabel1", "labelLength", "checkBoxReversed")}
        self.assertEqual({name: widget.text() for name, widget in texts.items()}, {
            "sidesLabel": "Sides", "side1Label": "Direction 1", "textLabel1": "End Condition",
            "labelLength": "Depth", "checkBoxReversed": "Reverse Direction"})
        self.assertEqual(pad.findChild(QtWidgets.QGroupBox, "groupBox").title(), "Direction of Extrusion")
        change = pad.findChild(QtWidgets.QComboBox, "changeMode")
        self.assertEqual(items(change), ["Blind", "Through All", "Up To Next", "Up To Surface", "Up To Body"])
        self.assertEqual(change.currentIndex(), 2)
        self.assertEqual([change.itemData(i) for i in range(5)], ["data-%d" % i for i in range(5)])
        sides = pad.findChild(QtWidgets.QComboBox, "sidesMode")
        self.assertEqual(items(sides), ["Direction 1", "Direction 1 and 2", "Mid Plane"])
        self.assertEqual(sides.currentIndex(), 1)
        self.assertEqual(self.terms.process_form(pad), 0)
        texts["side1Label"].setText("Side 1")
        self.assertEqual(self.terms.process_form(pad), 1)
        self.assertEqual(texts["side1Label"].text(), "Direction 1")

    def test_combo_count_safety_rule(self):
        pad = pad_form(change_mode_items=6)
        self.terms.process_form(pad)
        self.assertEqual(items(pad.findChild(QtWidgets.QComboBox, "changeMode")),
                         ["Dimension", "To last", "To first", "Up to face", "Up to shape", "Extra"])
        self.assertEqual(items(pad.findChild(QtWidgets.QComboBox, "sidesMode")),
                         ["Direction 1", "Direction 1 and 2", "Mid Plane"])
        self.assertEqual(pad.findChild(QtWidgets.QLabel, "side1Label").text(), "Direction 1")
        partial = form(PAD_FORM, [named(QtWidgets.QLabel(), "side2Label", "Side 2")])
        self.assertEqual(self.terms.process_form(partial), 1)
        self.assertEqual(self.jj("warning") + self.jj("error"), [])

    def test_new_host_drawing_labels_preserve_checkbox_and_group_state(self):
        balloon = form("TechDrawGui::TaskBalloon", [
            named(QtWidgets.QLabel(), "lText", "Text"),
            named(QtWidgets.QLabel(), "lBShape", "Bubble shape"),
            named(QtWidgets.QLabel(), "lSymbol", "Symbol"),
            named(QtWidgets.QLabel(), "lWidth", "Width"),
            named(QtWidgets.QLabel(), "lKink", "Kink length")])
        self.terms.process_form(balloon)
        self.assertEqual([w.text() for w in balloon.findChildren(QtWidgets.QLabel)],
                         ["Balloon text", "Style", "Arrow style", "Leader thickness", "Bent leader length"])
        border = named(QtWidgets.QGroupBox(), "gbFrame")
        border.setTitle("Frame")
        border.setCheckable(True)
        border.setChecked(False)
        annotation = form("TechDrawGui::TaskRichAnno", [border,
            named(QtWidgets.QLabel(), "label_frameThickness", "Thickness"),
            named(QtWidgets.QLabel(), "label_patternThickness", "Style"),
            named(QtWidgets.QLabel(), "label_colorThickness", "Color")])
        self.terms.process_form(annotation)
        self.assertEqual(border.title(), "Border")
        self.assertFalse(border.isChecked())
        self.assertEqual([w.text() for w in annotation.findChildren(QtWidgets.QLabel)],
                         ["Line thickness", "Line style", "Line color"])
        visible = named(QtWidgets.QCheckBox(), "cb_Visible", "Visible")
        visible.setChecked(True)
        decor = form("TechDrawGui::TaskLineDecor", [visible])
        self.terms.process_form(decor)
        self.assertEqual(visible.text(), "Show Edges")
        self.assertTrue(visible.isChecked())

    def test_compiled_form_names_from_new_qt_are_discovered_and_relabelled(self):
        root = QtWidgets.QWidget()
        pad = pad_form(parent=root)
        pad.setObjectName(PAD_FORM.replace("::", "__"))
        self.assertEqual(self.terms._find_forms(root), [pad])
        self.assertGreater(self.terms.process_form(pad), 0)
        self.assertEqual(items(pad.findChild(QtWidgets.QComboBox, "changeMode")),
                         ["Blind", "Through All", "Up To Next", "Up To Surface", "Up To Body"])
        self.assertEqual(self.terms.process_form(pad), 0)

    def test_scale_field_fix(self):
        def section(index, combo_enabled=True, spin_enabled=False):
            box = combo("cmbScaleType", ["Page", "Automatic", "Custom"], current=index)
            box.setEnabled(combo_enabled)
            spin = named(QtWidgets.QDoubleSpinBox(), "sbScale")
            spin.setEnabled(spin_enabled)
            return form("TechDrawGui::TaskSectionView", [box, spin]), spin

        widget, spin = section(2)
        self.terms.process_form(widget)
        self.assertTrue(spin.isEnabled())
        self.assertEqual(items(widget.findChild(QtWidgets.QComboBox, "cmbScaleType")),
                         ["Sheet scale", "Automatic", "Custom"])
        widget, spin = section(0)
        self.terms.process_form(widget)
        self.assertFalse(spin.isEnabled())
        widget, spin = section(2, combo_enabled=False)
        self.terms.process_form(widget)
        self.assertFalse(spin.isEnabled())
        widget, spin = section(0, spin_enabled=True)
        self.terms.process_form(widget)
        self.assertTrue(spin.isEnabled())

    def test_projection_tooltips_follow_freecad_text(self):
        first_angle = ("FrontTopLeft", "Top", "FrontTopRight", "Left", "Front", "Right", "Rear",
                       "FrontBottomLeft", "Bottom", "FrontBottomRight")
        boxes = []
        for index, tip in enumerate(first_angle):
            box = named(QtWidgets.QCheckBox(), "chkView%d" % index)
            box.setToolTip(tip)
            boxes.append(box)
        root = form("TechDrawGui::TaskProjGroup", boxes)
        self.terms.process_form(root)
        self.assertEqual([box.toolTip() for box in boxes], [
            "Isometric (front top left)", "Top", "Isometric (front top right)", "Left", "Front", "Right", "Back",
            "Isometric (front bottom left)", "Bottom", "Isometric (front bottom right)"])
        self.assertEqual(self.terms.process_form(root), 0, "a translated tooltip is not written again")
        # FreeCAD writes new tooltips when the projection type changes; they are mapped again.
        boxes[0].setToolTip("LeftFrontTop")
        boxes[2].setToolTip("RightFrontTop")
        boxes[9].setToolTip("RightFrontBottom")
        boxes[4].setToolTip("Some future text")
        self.assertEqual(self.terms.process_form(root), 3)
        self.assertEqual([boxes[i].toolTip() for i in (0, 2, 9, 4)], [
            "Isometric (front top left)", "Isometric (front top right)", "Isometric (front bottom right)",
            "Some future text"])
        self.assertNoJellyJamsProblems()

    def line_decor_form(self, weight=0.5, with_spin=True, with_layout=True):
        grid_holder = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_holder)
        labels = [("label_4", "View"), ("label_10", "Lines"), ("label_6", "Style"), ("label_15", "Weight"),
                  ("label_14", "Color"), ("label", "Visible")]
        for row, (name, text) in enumerate(labels):
            grid.addWidget(named(QtWidgets.QLabel(), name, text), row, 0)
        grid.addWidget(combo("cb_Visible", ["False", "True"]), 5, 1)
        spin = None
        if with_spin:
            spin = FakeQuantitySpinBox()
            spin.setObjectName("dsb_Weight")
            spin.setDecimals(4)
            spin.setValue(weight)
            grid.addWidget(spin, 3, 1)
        if with_layout:
            root = form("TechDrawGui::TaskLineDecor", [grid_holder, QtWidgets.QLabel("trailer")])
        else:
            root = QtWidgets.QWidget()
            root.setObjectName("TechDrawGui::TaskLineDecor")
            grid_holder.setParent(root)
        return root, spin

    def test_weight_presets_row(self):
        root, spin = self.line_decor_form(0.5)
        self.terms.process_form(root)
        rows = root.findChildren(QtWidgets.QWidget, "JellyJamsLineWidthPresets")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIs(root.layout().itemAt(1).widget(), row)
        self.assertTrue(any(label.text() == "ISO 128 preset" for label in row.findChildren(QtWidgets.QLabel)))
        presets = row.findChild(QtWidgets.QComboBox)
        self.assertEqual(items(presets), PRESETS)
        self.assertEqual(presets.currentText(), "0.5 mm")
        self.assertAlmostEqual(spin.value(), 0.5)
        self.assertEqual(root.findChild(QtWidgets.QLabel, "label_15").text(), "Line thickness")
        self.assertEqual(root.findChild(QtWidgets.QLabel, "label_14").text(), "Line color")
        self.assertEqual(root.findChild(QtWidgets.QLabel, "label_6").text(), "Line style")
        self.assertEqual(root.findChild(QtWidgets.QLabel, "label").text(), "Hide/Show Edges")
        self.assertEqual(items(root.findChild(QtWidgets.QComboBox, "cb_Visible")), ["Hide", "Show"])
        self.terms.process_form(root)
        self.assertEqual(len(root.findChildren(QtWidgets.QWidget, "JellyJamsLineWidthPresets")), 1)
        presets.setCurrentIndex(6)
        presets.activated.emit(6)
        presets.textActivated.emit("0.7 mm")
        self.assertAlmostEqual(spin.value(), 0.7)
        presets.setCurrentIndex(0)
        presets.activated.emit(0)
        presets.textActivated.emit(EN_DASH)
        self.assertAlmostEqual(spin.value(), 0.7)

    def test_weight_presets_edge_cases(self):
        root, _spin = self.line_decor_form(0.42)
        self.terms.process_form(root)
        presets = root.findChild(QtWidgets.QWidget, "JellyJamsLineWidthPresets").findChild(QtWidgets.QComboBox)
        self.assertEqual(presets.currentText(), EN_DASH)
        root, _spin = self.line_decor_form(with_spin=False)
        self.terms.process_form(root)
        self.assertEqual(root.findChildren(QtWidgets.QWidget, "JellyJamsLineWidthPresets"), [])
        root, _spin = self.line_decor_form(with_layout=False)
        self.terms.process_form(root)
        self.assertEqual(root.findChildren(QtWidgets.QWidget, "JellyJamsLineWidthPresets"), [])

    def test_process_once_is_idle_without_dialog(self):
        fcgui = self.module("jellyjams.fcgui")
        lookups = []
        real_main_window = fcgui.main_window
        real_get = STUBS.gui.getMainWindow
        self.patch(fcgui, "main_window", lambda: (lookups.append("fcgui"), real_main_window())[1])
        self.patch(STUBS.gui, "getMainWindow", lambda: (lookups.append("gui"), real_get())[1])
        pad = pad_form(STUBS.main_window)
        STUBS.set_active_dialog(None)
        self.assertEqual(self.terms.process_once(), 0)
        self.assertEqual(lookups, [], "no widget lookup while no task dialog is open")
        self.assertEqual(pad.findChild(QtWidgets.QLabel, "side1Label").text(), "Side 1")
        second = pad_form(STUBS.main_window)
        STUBS.set_active_dialog(object())
        self.assertGreater(self.terms.process_once(), 0)
        self.assertEqual(pad.findChild(QtWidgets.QLabel, "side1Label").text(), "Direction 1")
        self.assertEqual(second.findChild(QtWidgets.QLabel, "side1Label").text(), "Direction 1")

    def test_format_weight_and_service(self):
        for value, text in ((0.13, "0.13 mm"), (0.5, "0.5 mm"), (1.0, "1 mm"), (0.7, "0.7 mm"), (0.35, "0.35 mm")):
            self.assertEqual(self.terms.format_weight(value), text)
        self.terms.start()
        self.terms.start()
        self.assertTrue(self.terms.is_running())
        self.terms.stop()
        self.assertFalse(self.terms.is_running())
        self.terms.stop()
        self.assertNoJellyJamsProblems()


# ==========================================================================
# 19. Drawing pure helpers
# ==========================================================================


def svg_doc(attributes):
    return '<svg xmlns="http://www.w3.org/2000/svg" %s><rect x="0" y="0" width="1" height="1"/></svg>' % attributes


class Test19DrawingHelpers(HarnessCase):
    def test_open_sheet_bypasses_workbench_switch_preference(self):
        common = self.module("jellyjams.drawing_common")
        calls = []
        provider = types.SimpleNamespace(
            show=lambda: calls.append("show"),
            doubleClicked=lambda: self.fail("doubleClicked is a no-op with SwitchToWB false"))
        common.open_sheet_window(types.SimpleNamespace(ViewObject=provider))
        self.assertEqual(calls, ["show"])

    def test_scale_text_and_parse(self):
        common = self.module("jellyjams.drawing_common")
        for value, text in ((2, "2:1"), (1, "1:1"), (0.5, "1:2"), (0.4, "1:2.5"), (0.3, "1:3.33"), (2.5, "2.5:1"),
                            (0.25, "1:4"), (10, "10:1"), (0.02, "1:50"), (1 / 3.0, "1:3"), (0, ""), (-1, ""),
                            ("abc", ""), (None, "")):
            self.assertEqual(common.scale_text(value), text, value)
        for text, value in (("1:5", 0.2), ("2:1", 2.0), ("0,5", 0.5), (" 1 : 2 ", 0.5), ("2.5", 2.5),
                            ("1:3", 1 / 3.0)):
            self.assertAlmostEqual(common.parse_scale(text), value, places=9, msg=text)
        for text in ("1:0", "abc", "-2", "", "0", "1:-2"):
            self.assertIsNone(common.parse_scale(text), text)

    def test_template_names_and_catalog(self):
        templates = self.module("jellyjams.templates")
        cases = {"A4_Portrait_ISO5457_advanced.svg": "A4 portrait %s title block ISO 7200" % EN_DASH,
                 "A3_Landscape_ISO5457_minimal.svg": "A3 landscape %s small title block" % EN_DASH,
                 "A4_Portrait_ISO5457_notitleblock.svg": "A4 portrait %s no title block" % EN_DASH,
                 "A4_Landscape_blank.svg": "A4 landscape %s blank" % EN_DASH,
                 "A4_Landscape_TD.svg": "A4 landscape %s TechDraw" % EN_DASH,
                 "A2_Landscape_my_variant.svg": "A2 landscape %s my variant" % EN_DASH,
                 "A0_Portrait.svg": "A0 portrait",
                 "Default_Template_A4_Landscape.svg": "Default_Template_A4_Landscape"}
        for file_name, display in cases.items():
            self.assertEqual(templates.display_name(file_name), display, file_name)
        self.assertTrue(templates.is_third_angle_variant("x/A4_Portrait_ISO5457_advanced_third_angle.svg"))
        self.assertFalse(templates.is_third_angle_variant("x/A4_Portrait_ISO5457_advanced.svg"))
        self.assertTrue(templates.is_third_angle_variant("x/A3_Landscape_blank_Third_Angle.SVG"))
        expected_dir = os.path.join(STUBS.app.getResourceDir(), "Mod", "TechDraw", "Templates")
        self.assertEqual(norm_path(templates.templates_dir()), norm_path(expected_dir))
        iso = os.path.join(expected_dir, "ISO")
        if not os.path.isdir(iso):
            self.skipTest("FreeCAD's ISO templates are not installed")
        catalog = list(templates.catalog())
        names = [display for display, _path in catalog]
        self.assertEqual(names[:2], ["A4 portrait %s title block ISO 7200" % EN_DASH,
                                     "A3 landscape %s title block ISO 7200" % EN_DASH])
        files = [os.path.basename(path) for _display, path in catalog]
        self.assertFalse([f for f in files if f.lower().endswith("_m3.svg")])
        for _display, path in catalog:
            self.assertEqual(norm_path(os.path.dirname(path)), norm_path(iso))
        self.assertIn(files[2:], (sorted(files[2:]), sorted(files[2:], key=str.lower)))
        on_disk = sorted(f for f in os.listdir(iso) if f.lower().endswith(".svg") and not f[:-4].endswith("_third_angle"))
        self.assertEqual(sorted(files), on_disk)
        new = templates.new_drawing_template("A4 portrait")
        self.assertIn(os.path.basename(new), ("A4_Portrait_ISO5457_advanced.svg", "A4_Portrait_ISO5457_advanced_third_angle.svg"))

    def svg_bounds(self, svg_text, element_id):
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_text.encode("utf-8")))
        self.assertTrue(renderer.isValid())
        self.assertTrue(renderer.elementExists(element_id), element_id)
        return renderer.transformForElement(element_id).mapRect(renderer.boundsOnElement(element_id))

    def test_third_angle_symbol_on_installed_template(self):
        templates = self.module("jellyjams.templates")
        path = os.path.join(STUBS.app.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO",
                            "A4_Portrait_ISO5457_advanced.svg")
        if not os.path.isfile(path):
            self.skipTest("FreeCAD's ISO templates are not installed")
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        derived = templates.transform_symbol(original)
        self.assertIsInstance(derived, str)
        self.assertNotIn("first_angle_", derived)
        ids = ["third_angle_trapezoid", "third_angle_inner circle", "third_angle_outer circle",
               "third_angle_horizontal", "third_angle_vertical"]
        for element_id in ids:
            self.assertEqual(derived.count('id="%s"' % element_id), 1, element_id)
        trapezoid = self.svg_bounds(derived, "third_angle_trapezoid")
        outer = self.svg_bounds(derived, "third_angle_outer circle")
        inner = self.svg_bounds(derived, "third_angle_inner circle")
        vertical = self.svg_bounds(derived, "third_angle_vertical")
        self.assertLess(outer.center().x(), trapezoid.left(), "circles must sit left of the trapezoid")
        self.assertAlmostEqual(inner.center().x(), outer.center().x(), places=3)
        self.assertAlmostEqual(vertical.center().x(), outer.center().x(), delta=0.2)
        old_horizontal = self.svg_bounds(original, "first_angle_horizontal")
        new_horizontal = self.svg_bounds(derived, "third_angle_horizontal")
        self.assertAlmostEqual(new_horizontal.left(), old_horizontal.left(), delta=0.01)
        self.assertAlmostEqual(new_horizontal.right(), old_horizontal.right(), delta=0.01)
        old_union = self.svg_bounds(original, "first_angle_trapezoid").united(self.svg_bounds(original, "first_angle_outer circle"))
        new_union = trapezoid.united(outer)
        self.assertAlmostEqual(new_union.left(), old_union.left(), delta=1.0)
        self.assertAlmostEqual(new_union.right(), old_union.right(), delta=1.0)
        root = ET.fromstring(derived.encode("utf-8"))
        path_element = [el for el in root.iter() if el.get("id") == "third_angle_trapezoid"][0]
        transform = path_element.get("transform", "")
        if not transform or transform.startswith("translate"):
            numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", path_element.get("d", ""))]
            self.assertTrue(numbers)
            points = self.path_points(path_element.get("d"))
            xs = [p[0] for p in points]
            left = [p[1] for p in points if abs(p[0] - min(xs)) < 1e-6]
            right = [p[1] for p in points if abs(p[0] - max(xs)) < 1e-6]
            self.assertLess(max(left) - min(left), max(right) - min(right),
                            "the trapezoid's narrow end must face the circles (left)")
        editable = 'freecad:editable="'
        self.assertEqual(derived.count(editable), original.count(editable))
        self.assertIsNone(templates.transform_symbol(svg_doc('width="10mm" height="10mm"')))

    @staticmethod
    def path_points(d):
        tokens = re.findall(r"[MmLlHhVvZz]|-?\d+(?:\.\d+)?", d)
        points, x, y, command, index, start = [], 0.0, 0.0, "M", 0, (0.0, 0.0)
        while index < len(tokens):
            token = tokens[index]
            if token.isalpha():
                command = token
                index += 1
                if command in "Zz":
                    x, y = start
                continue
            if command in "MmLl":
                dx, dy = float(tokens[index]), float(tokens[index + 1])
                index += 2
                x, y = (x + dx, y + dy) if command.islower() else (dx, dy)
                if command in "Mm":
                    start = (x, y)
                    command = "l" if command == "m" else "L"
            elif command in "Hh":
                value = float(token)
                index += 1
                x = x + value if command == "h" else value
            elif command in "Vv":
                value = float(token)
                index += 1
                y = y + value if command == "v" else value
            points.append((x, y))
        return points

    def test_third_angle_derivation_files(self):
        templates = self.module("jellyjams.templates")
        base = os.path.join(STUBS.app.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO",
                            "A4_Portrait_ISO5457_advanced.svg")
        if not os.path.isfile(base):
            self.skipTest("FreeCAD's ISO templates are not installed")
        derived = templates.resolve_for_method(base, "Third angle")
        expected = os.path.join(STUBS.app.getUserAppDataDir(), "JellyJams", "templates",
                                "A4_Portrait_ISO5457_advanced_third_angle.svg")
        self.assertEqual(norm_path(derived), norm_path(expected))
        with open(derived, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("third_angle_", content)
        self.assertNotIn("first_angle_", content)
        self.assertEqual(norm_path(templates.resolve_for_method(derived, "First angle")), norm_path(base))
        self.assertEqual(norm_path(templates.resolve_for_method(base, "First angle")), norm_path(base))
        self.assertEqual(norm_path(templates.derive_third_angle(base)), norm_path(expected))

    def test_make_drawing_and_sheet_properties_helpers(self):
        make = self.module("jellyjams.make_drawing")
        props = self.module("jellyjams.sheet_properties")
        for extent, fmt in ((120, "A3 landscape"), (119.99, "A4 portrait"), (149.99, "A3 landscape"),
                            (220, "A3 landscape"), (40, "A4 portrait"), (None, "A4 portrait"),
                            ("not a number", "A4 portrait")):
            self.assertEqual(make.default_format(extent), fmt, extent)
        self.assertEqual(make.document_name_for("Shaft Drawing"), "Shaft_Drawing")
        self.assertEqual(make.document_name_for(""), "Drawing")
        self.assertEqual(make.document_name_for("Bracket-\u00e9"), "Bracket__")
        self.assertEqual(props.field_label("creator"), "Drawn by")
        self.assertEqual(props.field_label("title"), "Title")
        self.assertEqual(props.field_label("legal_owner_1"), "Legal owner (line 1)")
        self.assertEqual(props.field_label("language_code"), "Language")
        self.assertEqual(props.field_label("my_custom_key"), "My custom key")
        self.assertEqual(list(props.ordered_keys(["zeta", "creator", "title", "alpha_key", "legal_owner_2", "scale"])),
                         ["title", "scale", "creator", "legal_owner_2", "alpha_key", "zeta"])

    def test_sheet_content_helpers(self):
        sketch = self.module("jellyjams.sheet_sketch")
        text = self.module("jellyjams.sheet_text")
        picture = self.module("jellyjams.insert_picture")
        frame = [(point_xy(a), point_xy(b)) for a, b in sketch.frame_points(420, 297)]
        self.assertEqual(frame, [((0, 0), (420, 0)), ((420, 0), (420, 297)), ((420, 297), (0, 297)), ((0, 297), (0, 0))])
        frame = [(point_xy(a), point_xy(b)) for a, b in sketch.frame_points(10, 20, (-50, -30))]
        self.assertEqual(frame, [((-50, -30), (-40, -30)), ((-40, -30), (-40, -10)), ((-40, -10), (-50, -10)),
                                 ((-50, -10), (-50, -30))])
        self.assertEqual(list(text.split_lines("Line 1\\nLine 2")), ["Line 1", "Line 2"])
        self.assertEqual(list(text.split_lines("Deburr all holes")), ["Deburr all holes"])
        self.assertAlmostEqual(text.mm_to_pt(5), 14.1732, places=3)
        self.assertAlmostEqual(text.mm_to_pt(7), 19.8425, places=3)
        self.assertAlmostEqual(text.pt_to_mm(10), 3.5278, places=3)
        self.assertEqual(tuple(text.ISO_HEIGHTS_MM), (2.5, 3.5, 5, 7, 10, 14, 20))
        sizes = [('width="64mm" height="24mm" viewBox="0 0 64 24"', (64, 24)),
                 ('width="64mm" height="24mm" viewBox="0 0 128 48"', (128, 48)),
                 ('viewBox="0 0 300 150"', (30, 15)), ('width="100%" height="100%" viewBox="0 0 200 100"', (20, 10)),
                 ('width="200" height="100"', (20, 10)), ('width="200px" height="100px"', (20, 10)),
                 ('width="72pt" height="36pt"', (9.6, 4.8)), ('width="1in" height="2in"', (9.6, 19.2)),
                 ('width="2.54cm" height="2.54cm"', (9.6, 9.6)), ('width="10pc" height="5pc"', (16, 8)),
                 ('width="25.4mm" height="25.4mm"', (9.6, 9.6))]
        for attributes, expected in sizes:
            size = picture.svg_natural_size(svg_doc(attributes), 10.0)
            self.assertIsNotNone(size, attributes)
            self.assertAlmostEqual(size[0], expected[0], places=6, msg=attributes)
            self.assertAlmostEqual(size[1], expected[1], places=6, msg=attributes)
        self.assertIsNone(picture.svg_natural_size(svg_doc('width="100%" height="50%"'), 10.0))
        self.assertIsNone(picture.svg_natural_size("this is not svg", 10.0))
        self.assertEqual(tuple(picture.bitmap_natural_size(2000, 1000, 10.0)), (200.0, 100.0))
        self.assertAlmostEqual(picture.initial_scale(200, 420), 0.525)
        self.assertEqual(picture.initial_scale(None, 420), 1)
        self.assertEqual(picture.initial_scale(50, 420), 1)

    def test_zoom_steps_and_projection_rules(self):
        zoom = self.module("jellyjams.zoom_lines")
        for px, step in ((4, 0), (5, 0), (6, 1), (13, 2), (48, 4), (1e9, 6)):
            self.assertEqual(zoom.reduction_step(px), step, px)
        projected = self.module("jellyjams.projected_view")
        third_angle = {"Front": (0, 0), "Right": (1, 0), "Left": (-1, 0), "Top": (0, 1), "Bottom": (0, -1),
                       "FrontTopLeft": (-1, 1), "FrontTopRight": (1, 1), "FrontBottomLeft": (-1, -1),
                       "FrontBottomRight": (1, -1)}
        for proj_type, slot in third_angle.items():
            self.assertEqual(tuple(projected.sheet_slot(proj_type, "Third angle")), slot, proj_type)
            mirrored = (-slot[0], -slot[1])
            self.assertEqual(tuple(projected.sheet_slot(proj_type, "First angle")), mirrored, proj_type)
        for method in ("First angle", "Third angle"):
            self.assertEqual(tuple(projected.sheet_slot("Rear", method)), tuple(projected.REAR_SLOT), method)
            slots = [tuple(projected.sheet_slot(name, method)) for name in projected.VIEW_DIRECTIONS]
            self.assertEqual(len(slots), len(set(slots)), "every projection type has a slot of its own")
        self.assertEqual(tuple(projected.REAR_SLOT), (2, 0))
        self.assertEqual(tuple(projected.sheet_slot("Left", "First angle")), (1, 0))
        self.assertIsNone(projected.sheet_slot("Bogus", "First angle"))
        self.assertIsNone(projected.sheet_slot("Front", "Bogus method"))
        for (dx, dy), step in (((10, 2), (1, 0)), ((-30, 1), (-1, 0)), ((10, 5), (1, 1)), ((-3, -20), (0, -1)),
                               ((1, 40), (0, 1)), ((-5, 4), (-1, 1)), ((0, 0), None)):
            result = projected.click_step(dx, dy)
            self.assertEqual(tuple(result) if result is not None else None, step, (dx, dy))
        target = projected.projection_toward
        self.assertEqual(target("Front", (1, 0), "First angle"), "Left")
        self.assertEqual(target("Left", (1, 0), "First angle"), "Rear")
        self.assertEqual(target("Front", (-1, -1), "First angle"), "FrontTopRight")
        self.assertEqual(target("Front", (1, 0), "Third angle"), "Right")
        self.assertEqual(target("Front", (0, 1), "Third angle"), "Top")
        self.assertIsNone(target("Top", (0, -1), "First angle"))
        self.assertIsNone(target("Rear", (1, 0), "First angle"))
        self.assertIsNone(target("Rear", (1, 1), "Third angle"))

    def test_view_labels_and_scales(self):
        labels = self.module("jellyjams.view_labels")
        letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
        self.assertEqual(labels.SECTION_LETTERS, letters)
        self.assertEqual(labels.next_letter(set(), "section"), "A")
        self.assertEqual(labels.next_letter({"A"}, "section"), "B")
        self.assertEqual(labels.next_letter(set("ABCDEFGH"), "section"), "J")
        self.assertEqual(labels.next_letter(set(), "detail"), "Z")
        self.assertEqual(labels.next_letter({"Z"}, "detail"), "Y")
        self.assertEqual(labels.next_letter({"Z"}, "section"), "A")
        self.assertEqual(labels.next_letter({"A"}, "detail"), "Z")
        self.assertEqual(labels.next_letter(set(letters), "section"), "AA")
        self.assertEqual(labels.next_letter(set(letters) | {"AA"}, "section"), "AB")
        self.assertEqual(labels.next_letter(set(letters), "detail"), "ZZ")
        self.assertEqual(labels.next_letter(set(letters) | {"ZZ"}, "detail"), "ZY")
        everything = set(letters) | {a + b for a in letters for b in letters}
        self.assertEqual(labels.next_letter(everything, "section"), "?")
        for text in ("A-A", "Z (2:1)", "Y(5:1)", "AB-AB", "K", " A - A ", "Z ( 1:2.5 )", "Z (1,5:1)"):
            self.assertTrue(labels.follows_scheme(text), text)
        for text in ("Detail Y, rotated", "Section A-A", "A-A\nB", "a-a", "ABC", ""):
            self.assertFalse(labels.follows_scheme(text), text)
        self.assertEqual(labels.label_text("section", "A", ""), "A-A")
        self.assertEqual(labels.label_text("detail", "Z", "2:1"), "Z (2:1)")
        self.assertEqual(labels.label_text("detail", "Z", ""), "Z")
        self.assertEqual(labels.tree_label("section", "A", "1:1"), "Section View A-A")
        self.assertEqual(labels.tree_label("detail", "Z", "2:1"), "Detail View Z (2:1)")
        self.assertEqual(labels.tree_label("detail", "Z", ""), "Detail View Z")
        scale = self.module("jellyjams.view_scale")
        self.assertEqual(tuple(scale.STANDARD_SCALES), ("50:1", "20:1", "10:1", "5:1", "2:1", "1:1", "1:2", "1:5",
                                                        "1:10", "1:20", "1:50", "1:100"))

    def editable(self, svg):
        root = ET.fromstring(svg.encode("utf-8"))
        attribute = "{%s}editable" % NS_FREECAD_SVG
        return [(el.get(attribute), "".join(el.itertext())) for el in root.iter() if el.get(attribute) is not None]

    def test_surface_finish_svg(self):
        surface = self.module("jellyjams.surface_finish")
        self.assertEqual(dict(surface.DEFAULT_DATA), {"type": "any", "all_around": False, "a": "Rz 16", "b": "",
                                                      "c": "", "d": "", "e": ""})
        svg = surface.build_svg(dict(surface.DEFAULT_DATA))
        self.assertIn(NS_FREECAD_SVG, svg)
        self.assertEqual(self.editable(svg), [("a", "Rz 16"), ("b", ""), ("c", ""), ("d", ""), ("e", "")])
        root = ET.fromstring(svg.encode("utf-8"))
        self.assertTrue(root.get("width") and root.get("height") and root.get("viewBox"))
        data = dict(surface.DEFAULT_DATA, a="Rz <16> & \"x\"", c="ground", e="0.5")
        self.assertEqual(self.editable(surface.build_svg(data))[0], ("a", "Rz <16> & \"x\""))
        variants = {surface.build_svg(dict(surface.DEFAULT_DATA, type=kind)) for kind in ("any", "required", "prohibited")}
        self.assertEqual(len(variants), 3)
        self.assertNotEqual(surface.build_svg(dict(surface.DEFAULT_DATA, all_around=True)), svg)
        for text, value in (("90", 90.0), ("12,5", 12.5), ("abc", 0.0), ("", 0.0), ("-45", -45.0)):
            self.assertAlmostEqual(surface.parse_rotation(text), value, places=9, msg=text)

    def test_surface_finish_tables(self):
        surface = self.module("jellyjams.surface_finish")
        self.assertEqual([key for key, _label in surface.SURFACE_TYPES], ["any", "required", "prohibited"])
        self.assertTrue(all(label for _key, label in surface.SURFACE_TYPES))
        quick = list(surface.QUICK_VALUES)
        self.assertIn(surface.DEFAULT_DATA["a"], quick)
        self.assertEqual(quick, ["Rz 4", "Rz 6.3", "Rz 16", "Rz 25", "Rz 63",
                                 "Ra 0.8", "Ra 1.6", "Ra 3.2", "Ra 6.3", "Ra 12.5"])
        self.assertEqual([character for character, _label in surface.LAY_CHOICES],
                         ["", "=", "⊥", "X", "M", "C", "R", "P"])
        for character, label in surface.LAY_CHOICES:
            self.assertEqual(surface.lay_character(label), character, label)
            if character:
                self.assertTrue(label.startswith(character + " "), label)
        self.assertEqual(surface.lay_character(" M "), "M")
        self.assertEqual(surface.lay_character("custom lay"), "custom lay")

    def test_weld_symbol_data_and_svg(self):
        weld = self.module("jellyjams.weld_symbol")

        def copied(data):
            return json.loads(json.dumps(data))

        defaults = copied(weld.DEFAULT_DATA)
        # A new symbol: a fillet with throat "a5" on the arrow side, nothing on the other
        # side, every mark off and an empty tail note (drawing-symbols-export 2.5.6).
        self.assertEqual(sorted(defaults), ["format", "marks", "note", "sides"])
        self.assertEqual(defaults["format"], 1)
        self.assertEqual(len(defaults["sides"]), 2)
        arrow, other = defaults["sides"]
        self.assertEqual(sorted(arrow), sorted(other))
        self.assertEqual((arrow["symbol"], arrow["dimension"]), ("fillet", "a5"))
        self.assertEqual(other["symbol"], "")
        self.assertTrue(all(value == "" for value in other.values()), other)
        self.assertEqual(sorted(defaults["marks"]), ["dashed_line", "peripheral", "site"])
        self.assertFalse(any(defaults["marks"].values()))
        self.assertEqual(defaults["note"], "")
        # Values of the wrong type fall back to the new-symbol default (2.5.6).
        for raw in ('{"sides": [{"symbol": null}]}', '{"note": 135}',
                    '{"sides": [{"dimension": 5}]}', '{"marks": {"site": 1}}'):
            self.assertEqual(weld.merge_data(raw, []), weld.merge_data("", []), raw)

        # Empty, malformed or non-object JSON reads as all defaults.
        for raw in ("", "not json", "[1, 2]", "7", None):
            self.assertEqual(copied(weld.merge_data(raw, [])), defaults, raw)
        # A partial object keeps the defaults for everything it leaves out.
        merged = weld.merge_data('{"sides": [{"dimension": "a7"}]}', [])
        self.assertEqual(merged["sides"][0]["dimension"], "a7")
        self.assertEqual(merged["sides"][0]["symbol"], "fillet")
        self.assertEqual(merged["sides"][1], defaults["sides"][1])
        self.assertEqual((merged["marks"], merged["note"]), (defaults["marks"], ""))
        # Wrong types fall back, unknown ids read as "", extra sides and keys are dropped.
        raw = json.dumps({"sides": [{"symbol": "no_such_weld", "dimension": ["a4"]}, {"symbol": "butt_v"},
                                    {"symbol": "fillet"}],
                          "marks": {"site": True, "peripheral": "yes"}, "note": ["x"], "colour": "red"})
        merged = copied(weld.merge_data(raw, []))
        self.assertEqual(sorted(merged), sorted(defaults))
        self.assertEqual(len(merged["sides"]), 2)
        self.assertEqual((merged["sides"][0]["symbol"], merged["sides"][0]["dimension"]), ("", "a5"))
        self.assertEqual(merged["sides"][1]["symbol"], "butt_v")
        self.assertEqual(merged["marks"], dict(defaults["marks"], site=True))
        self.assertEqual(merged["note"], "")

        # EditableTexts override by position; a side's texts count only while it has a weld type.
        merged = weld.merge_data(json.dumps(defaults), ["a7", "", "s5", "", "111"])
        self.assertEqual(merged["sides"][0]["dimension"], "a7")
        self.assertEqual(merged["sides"][1]["dimension"], "")
        self.assertEqual(merged["note"], "111")
        two_sided = copied(defaults)
        two_sided["sides"][1]["symbol"] = "butt_v"
        merged = weld.merge_data(json.dumps(two_sided), ["a7", "60", "s5", "", "111"])
        self.assertEqual([(side["dimension"], side["extent"]) for side in merged["sides"]],
                         [("a7", "60"), ("s5", "")])
        # A shorter list leaves the stored values behind it alone.
        stored = copied(two_sided)
        stored["sides"][1]["dimension"], stored["note"] = "s3", "135"
        merged = weld.merge_data(json.dumps(stored), ["a9"])
        self.assertEqual((merged["sides"][0]["dimension"], merged["sides"][1]["dimension"], merged["note"]),
                         ("a9", "s3", "135"))

        svg = weld.build_svg(defaults, 0.0, 0.0)
        editable = self.editable(svg)
        self.assertEqual(list(weld.EDITABLE_IDS), ["dim_arrow", "extent_arrow", "dim_other", "extent_other", "note"])
        self.assertEqual([name for name, _text in editable], list(weld.EDITABLE_IDS))
        self.assertEqual(editable[0], ("dim_arrow", "a5"))
        # Reading the drawn texts back changes nothing.
        self.assertEqual(copied(weld.merge_data(json.dumps(defaults), [text for _name, text in editable])),
                         defaults)
        root = ET.fromstring(svg.encode("utf-8"))
        self.assertTrue(root.get("width", "").endswith("mm") and root.get("height", "").endswith("mm"))
        for tip in ((-12.0, -10.0), (30.0, 25.0)):
            tipped = ET.fromstring(weld.build_svg(defaults, *tip).encode("utf-8"))
            box = [float(n) for n in re.split(r"[\s,]+", tipped.get("viewBox").strip())]
            self.assertAlmostEqual(box[0], -box[2] / 2.0, places=6)
            self.assertAlmostEqual(box[1], -box[3] / 2.0, places=6)
        self.assertNotIn("dasharray", svg)
        dashed = copied(defaults)
        dashed["marks"]["dashed_line"] = True
        dashed["note"] = "<A&B>"
        dashed_svg = weld.build_svg(dashed, -12.0, -10.0)
        self.assertIn("dasharray", dashed_svg)
        self.assertEqual([name for name, _text in self.editable(dashed_svg)], list(weld.EDITABLE_IDS))
        self.assertEqual(self.editable(dashed_svg)[-1], ("note", "<A&B>"))
        seams = [key for key, _text in weld.WELD_TYPES if key]
        self.assertEqual(sorted(weld.GLYPHS), sorted(seams), "every weld type has exactly one glyph")
        for seam in seams:
            left, right, depth = weld.glyph_extent(seam)
            self.assertLessEqual(left, right, seam)
            self.assertGreater(depth, 0.0, seam)
        self.assertEqual(tuple(weld.glyph_extent("")), (0.0, 0.0, 0.0))
        self.assertIn(defaults["sides"][0]["dimension"], weld.SIZE_PRESETS)

    def test_export_naming(self):
        export = self.module("jellyjams.drawing_export")
        for name, clean in (("DWG-0042/B", "DWG-0042_B"), ("a//b", "a_b"), ('a:*?"<>|b', "a_b"), ("  .name.  ", "name"),
                            ("", "Drawing"), ("...", "Drawing"), ("My Sheet", "My Sheet"), ("a\\b", "a_b")):
            self.assertEqual(export.sanitize(name), clean, name)
        self.assertEqual(export.suggested_base("DWG-0042/B", "Doc", "Doc"), "DWG-0042_B")
        self.assertEqual(export.suggested_base("", "MyLabel", "Name"), "MyLabel")
        self.assertEqual(export.suggested_base("   ", "", "Name"), "Name")
        self.assertEqual(export.suggested_base("", "", ""), "Drawing")
        folder = self.tmpdir()
        chosen = os.path.join(folder, "T.pdf")
        paths = export.per_sheet_paths
        self.assertEqual([norm_path(p) for p in paths(chosen, ["Sheet1", "Sheet2"])],
                         [norm_path(os.path.join(folder, n)) for n in ("T_Sheet1.pdf", "T_Sheet2.pdf")])
        chosen_dxf = os.path.join(folder, "T.dxf")
        self.assertEqual([norm_path(p) for p in paths(chosen_dxf, ["My Sheet", "Sheet1"])],
                         [norm_path(os.path.join(folder, n)) for n in ("T_Sheet1.dxf", "T_Sheet2.dxf")])
        self.assertEqual([norm_path(p) for p in paths(chosen, ["Sheet2", "Sheet2"])],
                         [norm_path(os.path.join(folder, n)) for n in ("T_Sheet2.pdf", "T_Sheet3.pdf")])
        # Only labels of the form Sheet<N> keep their name; any other label gets a number.
        self.assertEqual([norm_path(p) for p in paths(chosen, ["Page3", "Sheet9"])],
                         [norm_path(os.path.join(folder, n)) for n in ("T_Sheet1.pdf", "T_Sheet9.pdf")])
        self.assertEqual([norm_path(p) for p in paths(chosen, ["Only"])], [norm_path(chosen)])

    def test_sketching_helpers(self):
        tools = self.module("jellyjams.sketch_tools")
        self.assertEqual(tuple(point_xy(tools.mirrored_end((10, 5), (40, 25)))), (-20.0, -15.0))
        context = self.module("jellyjams.context_sketch")
        for distance, opacity in ((0, 1.0), (50, 1.0), (115, 0.5), (147.5, 0.25)):
            self.assertAlmostEqual(context.opacity_for_distance(distance), opacity, places=9)
        self.assertIsNone(context.opacity_for_distance(180))
        self.assertIsNone(context.opacity_for_distance(500))
        fade = [context.opacity_for_distance(distance) for distance in range(0, 180, 5)]
        self.assertTrue(all(a >= b for a, b in zip(fade, fade[1:])), "the popup only fades with distance")
        self.assertEqual(tuple(context.popup_position(100, 200)), (116, 160))
        gesture = self.module("jellyjams.sketch_gesture")
        for cmd in PROFILE_FEATURES:
            self.assertTrue(gesture.is_profile_feature(cmd), cmd)
        for cmd in ("PartDesign_Fillet", "Sketcher_CreateLine", ""):
            self.assertFalse(gesture.is_profile_feature(cmd), cmd)


# ==========================================================================
# 20. PDF merge
# ==========================================================================


class MiniPdf:
    """Just enough classic-xref PDF reading to verify merged files."""

    def __init__(self, data):
        self.data = data
        found = list(re.finditer(rb"startxref\s+(\d+)\s+%%EOF", data[-2048:]))
        if not found:
            raise AssertionError("no startxref/%%EOF at the end")
        self.xref_offset = int(found[-1].group(1))
        if data[self.xref_offset:self.xref_offset + 4] != b"xref":
            raise AssertionError("startxref does not point at an xref table")
        trailer_at = data.index(b"trailer", self.xref_offset)
        tokens = data[self.xref_offset + 4:trailer_at].split()
        self.entries, index = {}, 0
        while index < len(tokens):
            start, count = int(tokens[index]), int(tokens[index + 1])
            index += 2
            for number in range(start, start + count):
                offset, generation, kind = tokens[index:index + 3]
                index += 3
                if kind == b"n":
                    self.entries[number] = (int(offset), int(generation))
        self.trailer = data[trailer_at:data.index(b"startxref", trailer_at)]

    def head(self, number):
        offset, generation = self.entries[number]
        match = re.match(rb"\s*%d\s+%d\s+obj" % (number, generation), self.data[offset:offset + 64])
        if not match:
            raise AssertionError("xref offset of object %d does not point at its 'obj'" % number)
        start = offset + match.end()
        stream_at, end_at = self.data.find(b"stream", start), self.data.find(b"endobj", start)
        return self.data[start:stream_at if 0 <= stream_at < end_at else end_at]

    def ref(self, number, key):
        match = re.search(rb"/%s\s+(\d+)\s+\d+\s+R" % key, self.head(number))
        return int(match.group(1)) if match else None

    def kids(self, number):
        match = re.search(rb"/Kids\s*\[(.*?)\]", self.head(number), re.S)
        return [int(n) for n in re.findall(rb"(\d+)\s+\d+\s+R", match.group(1))]

    def numbers(self, number, key):
        match = re.search(rb"/%s\s*\[([^\]]*)\]" % key, self.head(number))
        return [float(n) for n in match.group(1).split()] if match else None

    def stream(self, number):
        head = self.head(number)
        match = re.search(rb"/Length\s+(\d+)(\s+(\d+)\s+R)?", head)
        length = int(self.head(int(match.group(1))).strip()) if match.group(2) else int(match.group(1))
        offset = self.entries[number][0]
        start = self.data.index(b"stream", offset) + len(b"stream")
        start += 2 if self.data[start:start + 2] == b"\r\n" else 1
        return self.data[start:start + length]

    def root(self):
        return int(re.search(rb"/Root\s+(\d+)\s+\d+\s+R", self.trailer).group(1))

    def first_page(self):
        return self.kids(self.ref(self.root(), b"Pages"))[0]


def write_qt_pdf(path, size_id, landscape, text):
    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(size_id))
    orientation = QtGui.QPageLayout.Orientation
    writer.setPageOrientation(orientation.Landscape if landscape else orientation.Portrait)
    painter = QtGui.QPainter(writer)
    painter.drawText(300, 300, text)
    painter.drawRect(200, 200, 2400, 1200)
    painter.end()
    del painter, writer


class Test20PdfMerge(HarnessCase):
    def setUp(self):
        super().setUp()
        self.merge = self.module("jellyjams.pdf_merge")
        self.folder = self.tmpdir()
        self.a4 = os.path.join(self.folder, "sheet_a4.pdf")
        self.a3 = os.path.join(self.folder, "sheet_a3.pdf")
        write_qt_pdf(self.a4, QtGui.QPageSize.PageSizeId.A4, False, "Sheet one, A4 portrait")
        write_qt_pdf(self.a3, QtGui.QPageSize.PageSizeId.A3, True, "Sheet two, A3 landscape")

    def read(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def test_merge_two_qt_pdfs(self):
        output = os.path.join(self.folder, "merged.pdf")
        self.assertEqual(self.merge.merge([self.a4, self.a3], output), 2)
        data = self.read(output)
        version = re.match(rb"%PDF-(\d+)\.(\d+)", data)
        self.assertTrue(version)
        self.assertGreaterEqual((int(version.group(1)), int(version.group(2))), (1, 4))
        pdf = MiniPdf(data)
        for number in pdf.entries:
            pdf.head(number)
        self.assertEqual(pdf.root(), 1)
        catalog = pdf.head(1)
        self.assertRegex(catalog, rb"/Type\s*/Catalog")
        self.assertEqual(pdf.ref(1, b"Pages"), 2)
        pages = pdf.head(2)
        self.assertRegex(pages, rb"/Type\s*/Pages")
        self.assertRegex(pages, rb"/Count\s+2\b")
        kids = pdf.kids(2)
        self.assertEqual(len(kids), 2)
        size = int(re.search(rb"/Size\s+(\d+)", pdf.trailer).group(1))
        self.assertGreater(size, max(pdf.entries))
        for kid, source in zip(kids, (self.a4, self.a3)):
            head = pdf.head(kid)
            self.assertRegex(head, rb"/Type\s*/Page(?![a-zA-Z])")
            self.assertEqual(pdf.ref(kid, b"Parent"), 2)
            original = MiniPdf(self.read(source))
            page = original.first_page()
            self.assertEqual(pdf.numbers(kid, b"MediaBox"), original.numbers(page, b"MediaBox"))
            self.assertEqual(pdf.stream(pdf.ref(kid, b"Contents")), original.stream(original.ref(page, b"Contents")))
        first, second = (pdf.numbers(kid, b"MediaBox") for kid in kids)
        self.assertLess(first[2], first[3], "the A4 portrait sheet comes first")
        self.assertGreater(second[2], second[3], "the A3 landscape sheet comes second")
        again = os.path.join(self.folder, "merged_again.pdf")
        self.assertEqual(self.merge.merge([output], again), 2)

    def test_incremental_update_is_rejected(self):
        data = self.read(self.a4)
        self.assertIn(b"trailer\n<<\n", data)
        broken = os.path.join(self.folder, "prev.pdf")
        with open(broken, "wb") as handle:
            handle.write(data.replace(b"trailer\n<<\n", b"trailer\n<<\n/Prev 9\n"))
        output = os.path.join(self.folder, "never.pdf")
        with self.assertRaises(self.merge.UnsupportedPdf):
            self.merge.merge([self.a3, broken], output)
        self.assertFalse(os.path.exists(output), "an unsupported input must not leave an output file")

    def test_xref_stream_and_garbage_are_rejected(self):
        parts = [b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"]
        objects = [b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
                   b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
                   b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>\nendobj\n"]
        for obj in objects:
            parts.append(obj)
        xref_at = sum(len(p) for p in parts)
        stream = b"\x01\x00\x0f\x00"
        parts.append(b"4 0 obj\n<< /Type /XRef /Size 5 /W [1 2 1] /Root 1 0 R /Length %d >>\nstream\n" % len(stream)
                     + stream + b"\nendstream\nendobj\n")
        parts.append(b"startxref\n%d\n%%%%EOF\n" % xref_at)
        xref_stream = os.path.join(self.folder, "xrefstream.pdf")
        with open(xref_stream, "wb") as handle:
            handle.write(b"".join(parts))
        garbage = os.path.join(self.folder, "garbage.pdf")
        with open(garbage, "wb") as handle:
            handle.write(b"%PDF-1.4\nthis is not a pdf\n")
        for bad in (xref_stream, garbage):
            with self.subTest(input=os.path.basename(bad)):
                output = os.path.join(self.folder, "never_%s" % os.path.basename(bad))
                with self.assertRaises(self.merge.UnsupportedPdf):
                    self.merge.merge([self.a4, bad], output)
                self.assertFalse(os.path.exists(output))


# ==========================================================================
# 21. Icons
# ==========================================================================


class Test20FilePublication(HarnessCase):
    def test_merge_does_not_clobber_neighboring_partial_file(self):
        folder = Path(self.tmpdir())
        source, target = folder / 'source.pdf', folder / 'merged.pdf'
        neighbor = folder / 'merged.pdf.part'
        neighbor.write_bytes(b'unrelated data')
        write_qt_pdf(str(source), QtGui.QPageSize.PageSizeId.A4, False, 'Audit')
        merge = self.module('jellyjams.pdf_merge')
        self.assertEqual(merge.merge([source, source], target), 2)
        self.assertEqual(neighbor.read_bytes(), b'unrelated data')
        self.assertEqual(set(p.name for p in folder.iterdir()),
                         {'source.pdf', 'merged.pdf', 'merged.pdf.part'})

    def test_native_export_failure_preserves_existing_output(self):
        export = self.module('jellyjams.drawing_export')
        for kind, module, function in (('pdf', 'TechDrawGui', 'exportPageAsPdf'),
                                       ('dxf', 'TechDraw', 'writeDXFPage')):
            for failure in ('partial', 'empty', 'replace'):
                with self.subTest(kind=kind, failure=failure):
                    folder = Path(self.tmpdir())
                    target = folder / ('drawing.' + kind)
                    target.write_bytes(b'previous valid drawing')
                    def writer(page, path):
                        Path(path).write_bytes(b'' if failure == 'empty' else b'new output')
                        if failure == 'partial':
                            raise OSError('renderer failed')
                    with fake_modules({module: fake_module(module, **{function: writer})}):
                        replacement = (mock.patch.object(export.os, 'replace', side_effect=OSError('locked'))
                                       if failure == 'replace' else contextlib.nullcontext())
                        with replacement, self.assertRaises(OSError):
                            getattr(export, 'write_' + kind)([types.SimpleNamespace(Label='Sheet1')], str(target))
                    self.assertEqual(target.read_bytes(), b'previous valid drawing')
                    self.assertEqual(list(folder.iterdir()), [target])

    def test_template_cache_does_not_clobber_neighboring_temporary_file(self):
        templates = self.module('jellyjams.templates')
        folder = Path(self.tmpdir())
        source = folder / 'drawing.svg'
        source.write_text('original', encoding='utf-8')
        target = folder / 'drawing_third_angle.svg'
        neighbor = folder / 'drawing_third_angle.svg.tmp'
        neighbor.write_bytes(b'unrelated data')
        with mock.patch.object(templates, 'transform_symbol', return_value='derived'):
            with mock.patch.object(templates.paths, 'user_cache_dir', return_value=str(folder)):
                self.assertEqual(templates.derive_third_angle(str(source)), str(target))
        self.assertEqual(target.read_text(encoding='utf-8'), 'derived')
        self.assertEqual(neighbor.read_bytes(), b'unrelated data')
        target.write_text('previous template', encoding='utf-8')
        with mock.patch.object(templates, 'transform_symbol', return_value='derived'):
            with mock.patch.object(templates.paths, 'user_cache_dir', return_value=str(folder)):
                with mock.patch.object(templates.os, 'replace', side_effect=OSError('locked')):
                    self.assertIsNone(templates.derive_third_angle(str(source)))
        self.assertEqual(target.read_text(encoding='utf-8'), 'previous template')
        self.assertEqual(neighbor.read_bytes(), b'unrelated data')
        self.assertEqual(set(folder.iterdir()), {source, target, neighbor})

    def test_failed_replace_preserves_output_and_cleans_owned_temporaries(self):
        folder = Path(self.tmpdir())
        source, target = folder / 'source.pdf', folder / 'merged.pdf'
        target.write_bytes(b'previous output')
        write_qt_pdf(str(source), QtGui.QPageSize.PageSizeId.A4, False, 'Audit')
        merge = self.module('jellyjams.pdf_merge')
        with mock.patch.object(merge.os, 'replace', side_effect=OSError('destination locked')):
            with self.assertRaises(OSError):
                merge.merge([source, source], target)
        self.assertEqual(target.read_bytes(), b'previous output')
        self.assertEqual(set(p.name for p in folder.iterdir()), {'source.pdf', 'merged.pdf'})

    def test_pdf_fallback_cannot_publish_empty_sheets(self):
        export = self.module('jellyjams.drawing_export')
        folder = Path(self.tmpdir())
        target, first = folder / 'drawing.pdf', folder / 'drawing_Sheet1.pdf'
        for path in (target, first):
            path.write_bytes(b'previous drawing')
        def empty(page, path):
            Path(path).write_bytes(b'')
        with fake_modules({'TechDrawGui': fake_module('TechDrawGui', exportPageAsPdf=empty)}):
            with self.assertRaises(OSError):
                export.write_pdf([types.SimpleNamespace(Label='Sheet1'),
                                  types.SimpleNamespace(Label='Sheet2')], str(target))
        self.assertEqual(target.read_bytes(), b'previous drawing')
        self.assertEqual(first.read_bytes(), b'previous drawing')
        self.assertEqual(set(folder.iterdir()), {target, first})


class Test21Icons(HarnessCase):
    FORBIDDEN = ("<text", "<style", "<image", "<script", "<filter", "<mask", "<pattern", "<marker",
                 "<foreignobject", "data:image")

    def icon_names(self):
        constants = self.module("jellyjams.constants")
        orientation = self.module("jellyjams.orientation")
        self.assertEqual(dict(orientation.FALLBACK_ICONS), ORIENTATION_FALLBACK_ICONS)
        names = (list(dict(constants.COMMAND_ICONS).values()) + list(dict(constants.RELATION_ICONS).values())
                 + list(dict(orientation.FALLBACK_ICONS).values()))
        self.assertEqual(sorted(names), sorted(list(COMMAND_ICONS.values()) + list(RELATION_ICONS.values())
                                               + list(ORIENTATION_FALLBACK_ICONS.values())))
        return names

    def test_icon_folder_holds_exactly_the_used_icons(self):
        on_disk = sorted(name[:-4] for name in os.listdir(ICONS_DIR) if name.lower().endswith(".svg"))
        self.assertEqual(on_disk, sorted(set(self.icon_names()) | {"jellyjams"}), "unused or unlisted icon files")
        others = [name for name in os.listdir(ICONS_DIR) if not name.lower().endswith(".svg")]
        self.assertEqual(others, [], "only SVG icons are shipped")

    def test_every_icon_exists_renders_and_is_clean(self):
        for name in self.icon_names() + ["jellyjams"]:
            with self.subTest(icon=name):
                path = os.path.join(ICONS_DIR, name + ".svg")
                self.assertTrue(os.path.isfile(path), "missing %s" % path)
                self.assertNotIn("solidworks", name.lower())
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                self.assertTrue(QtSvg.QSvgRenderer(path).isValid(), path)
                body = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", text)
                self.assertTrue(body.startswith("<!--"), "the SPDX comment must follow the XML declaration")
                comment = body[:body.index("-->")]
                # AGENTS.md R1: both SPDX lines in the one comment directly after the declaration
                self.assertIn("SPDX-License-Identifier: MIT", comment, path)
                self.assertIn("SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>", comment,
                              "%s: the copyright line must be in the same comment as the license line" % path)
                lowered = text.lower()
                for forbidden in self.FORBIDDEN:
                    self.assertNotIn(forbidden, lowered)
                self.assertNotIn("solidworks", re.sub(r"<!--.*?-->", "", lowered, flags=re.S))
                if name != "jellyjams":
                    root = ET.fromstring(text.encode("utf-8"))
                    self.assertEqual(root.get("viewBox"), "0 0 64 64")


# ==========================================================================
# 22. Document behaviour with fake FreeCAD documents
# ==========================================================================

# type -> parent type; enough of FreeCAD's type tree for the isDerivedFrom() checks
FAKE_TYPE_PARENTS = {
    "App::GeoFeature": "App::DocumentObject",
    "App::DocumentObjectGroup": "App::DocumentObject",
    "App::FeaturePython": "App::DocumentObject",
    "App::Link": "App::DocumentObject",
    "App::Part": "App::GeoFeature",
    "Assembly::AssemblyObject": "App::Part",
    "Assembly::JointGroup": "App::DocumentObjectGroup",
    "Part::Feature": "App::GeoFeature",
    "Part::Box": "Part::Feature",
    "Part::Part2DObject": "Part::Feature",
    "Part::Part2DObjectPython": "Part::Part2DObject",
    "Sketcher::SketchObject": "Part::Part2DObject",
    "Part::BodyBase": "Part::Feature",
    "PartDesign::Body": "Part::BodyBase",
    "App::DatumElement": "App::GeoFeature",
    "App::Plane": "App::DatumElement",
    "App::Line": "App::DatumElement",
    "App::Point": "App::DatumElement",
    "Part::Datum": "Part::Feature",
    "PartDesign::Plane": "Part::Datum",
    "PartDesign::Line": "Part::Datum",
    "PartDesign::Point": "Part::Datum",
    "Part::Cylinder": "Part::Feature",
    "Part::Plane": "Part::Feature",
    "Part::Circle": "Part::Feature",
    "PartDesign::Feature": "Part::Feature",
    "PartDesign::FeatureAddSub": "PartDesign::Feature",
    "PartDesign::ProfileBased": "PartDesign::FeatureAddSub",
    "PartDesign::FeatureExtrude": "PartDesign::ProfileBased",
    "PartDesign::Pad": "PartDesign::FeatureExtrude",
    "PartDesign::Pocket": "PartDesign::FeatureExtrude",
    "App::LocalCoordinateSystem": "App::GeoFeature",
    "App::Origin": "App::LocalCoordinateSystem",
    "TechDraw::DrawPage": "App::DocumentObject",
    "TechDraw::DrawTemplate": "App::DocumentObject",
    "TechDraw::DrawSVGTemplate": "TechDraw::DrawTemplate",
    "TechDraw::DrawView": "App::DocumentObject",
    "TechDraw::DrawViewPart": "TechDraw::DrawView",
    "TechDraw::DrawViewSection": "TechDraw::DrawViewPart",
    "TechDraw::DrawViewDetail": "TechDraw::DrawViewPart",
    "TechDraw::DrawViewAnnotation": "TechDraw::DrawView",
    "TechDraw::DrawViewSymbol": "TechDraw::DrawView",
    "TechDraw::DrawViewClip": "TechDraw::DrawView",
    "TechDraw::DrawViewDimension": "TechDraw::DrawView",
}


def fake_type_chain(type_id):
    chain = []
    while type_id and type_id not in chain:
        chain.append(type_id)
        type_id = FAKE_TYPE_PARENTS.get(type_id)
    return chain


class FakeObject:
    """A FreeCAD document object, as far as JellyJams looks at it. Every write of a
    public attribute is recorded in `_writes` and reported to `_hook(obj, name, old, new)`."""

    def __init__(self, doc, name, type_id, label=None, **values):
        state = self.__dict__
        state.update(Document=doc, Name=name, TypeId=type_id, Label=name if label is None else label,
                     InList=[], _props=["Label"] + list(values), _writes=[], _hook=None, _tooltips={})
        state.update(values)
        if doc is not None:
            doc.Objects.append(self)

    def __repr__(self):
        return "<FakeObject %s>" % self.__dict__.get("Name")

    @property
    def PropertiesList(self):
        return list(self._props)

    def isDerivedFrom(self, type_id):
        return type_id in fake_type_chain(self.TypeId)

    def addProperty(self, _prop_type, name, _group="", tooltip="", *_args):
        if name not in self._props:
            self._props.append(name)
            self.__dict__[name] = None
        self._tooltips[name] = tooltip
        return self

    def __setattr__(self, name, value):
        if name.startswith("_"):
            self.__dict__[name] = value
            return
        old = self.__dict__.get(name)
        self._writes.append((name, value))
        self.__dict__[name] = value
        if name not in self._props:
            self._props.append(name)
        if self._hook is not None:
            self._hook(self, name, old, value)

    def writes(self, name):
        return [value for prop, value in self._writes if prop == name]


class FakePage(FakeObject):
    def __init__(self, doc, name="Page", label="Sheet1", **values):
        values.setdefault("Views", [])
        super().__init__(doc, name, "TechDraw::DrawPage", label, **values)
        self._refuse_add = None

    def addView(self, view):
        if self._refuse_add is not None:
            raise self._refuse_add
        self.Views.append(view)
        view.InList.append(self)
        return len(self.Views) - 1


class DeadObject:
    """A deleted document object: reading any property raises, as in FreeCAD."""

    def __getattr__(self, name):
        raise RuntimeError("This object has been deleted (%s)" % name)


class FakeTransactions:
    """FreeCAD's application-wide undo transaction. openTransaction() starts one when none
    is active; a document closes it only when it recorded a change in the step, which
    `closes_on_commit` stands for."""

    def __init__(self, closes_on_commit=False):
        self.active = None
        self.next_id = 41
        self.closed = []
        self.closes_on_commit = closes_on_commit

    def open(self, name):
        if self.active is None:
            self.active = (name, self.next_id)
            self.next_id += 1

    def document_done(self):
        if self.closes_on_commit:
            self.active = None

    def getActiveTransaction(self):
        return self.active

    def closeActiveTransaction(self, abort=False, transaction_id=0):
        self.closed.append((bool(abort), transaction_id))
        if self.active is not None and (not transaction_id or self.active[1] == transaction_id):
            self.active = None


class FakeDocument:
    """A FreeCAD document whose transaction, addObject and recompute calls are recorded."""

    def __init__(self, name, label=None, file_name="", transactions=None):
        self.Name = name
        self.Label = name if label is None else label
        self.FileName = file_name
        self.Objects = []
        self.Restoring = False
        self.Transacting = False
        self.HasPendingTransaction = False
        self.calls = []
        self.transactions = transactions
        self.recompute_error = None

    def __repr__(self):
        return "<FakeDocument %s>" % self.Name

    def getObject(self, name):
        for obj in self.Objects:
            if obj.Name == name:
                return obj
        return None

    def addObject(self, type_id, name):
        unique, number = name, 0
        while self.getObject(unique) is not None:
            number += 1
            unique = "%s%03d" % (name, number)
        self.calls.append(("addObject", type_id))
        return FakeObject(self, unique, type_id)

    def openTransaction(self, name=""):
        self.calls.append(("openTransaction", name))
        if self.transactions is not None:
            self.transactions.open(name)

    def commitTransaction(self):
        self.calls.append(("commitTransaction",))
        if self.transactions is not None:
            self.transactions.document_done()

    def abortTransaction(self):
        self.calls.append(("abortTransaction",))
        if self.transactions is not None:
            self.transactions.document_done()

    def recompute(self, *_args):
        self.calls.append(("recompute",))
        if self.recompute_error is not None:
            raise self.recompute_error
        return 0

    def call_names(self):
        return [call[0] for call in self.calls]


class DocumentCase(HarnessCase):
    def use_transactions(self, closes_on_commit=False):
        """Give the FreeCAD stub the application transaction API (1.1 has it, the stub not)."""
        transactions = FakeTransactions(closes_on_commit)
        self.patch(STUBS.app, "getActiveTransaction", transactions.getActiveTransaction)
        self.patch(STUBS.app, "closeActiveTransaction", transactions.closeActiveTransaction)
        return transactions

    def open_documents(self, *docs):
        table = {doc.Name: doc for doc in docs}

        def get_document(name):
            if name not in table:
                raise NameError("Unknown document '%s'" % name)
            return table[name]

        self.patch(STUBS.app, "listDocuments", lambda: dict(table))
        self.patch(STUBS.app, "getDocument", get_document)
        return table


class Test22DocumentHelpers(DocumentCase):
    def setUp(self):
        super().setUp()
        self.doc_utils = self.module("jellyjams.doc_utils")

    def test_primary_model_objects_skip_2d_profiles(self):
        primary = self.doc_utils.primary_model_objects
        self.assertEqual(self.doc_utils.PROFILE_2D_TYPE, "Part::Part2DObject")
        sketches = FakeDocument("Sketches")
        FakeObject(sketches, "Sketch", "Sketcher::SketchObject")
        FakeObject(sketches, "Wire", "Part::Part2DObjectPython")
        self.assertEqual(primary(sketches), [], "a document of 2D profiles has no model")
        mixed = FakeDocument("Mixed")
        FakeObject(mixed, "Sketch", "Sketcher::SketchObject")
        box = FakeObject(mixed, "Box", "Part::Box")
        feature = FakeObject(mixed, "Feature", "Part::Feature")
        self.assertEqual(primary(mixed), [box, feature])
        bodies = FakeDocument("Bodies")
        body = FakeObject(bodies, "Body", "PartDesign::Body", Group=[])
        inner = FakeObject(bodies, "Sketch", "Sketcher::SketchObject")
        body.Group.append(inner)
        inner.InList.append(body)
        FakeObject(bodies, "Loose", "Sketcher::SketchObject")
        self.assertEqual(primary(bodies), [body])
        assemblies = FakeDocument("Assemblies")
        assembly = FakeObject(assemblies, "Assembly", "Assembly::AssemblyObject", Group=[])
        FakeObject(assemblies, "Box", "Part::Box")
        self.assertEqual(primary(assemblies), [assembly])

    def test_transaction_closes_a_step_the_document_left_open(self):
        transactions = self.use_transactions(closes_on_commit=False)
        doc = FakeDocument("Doc", transactions=transactions)
        with self.doc_utils.transaction(doc, "Harness Step") as opened:
            self.assertIs(opened, True)
            self.assertEqual(transactions.active, ("Harness Step", 41))
        self.assertEqual(doc.call_names(), ["openTransaction", "commitTransaction"])
        self.assertEqual(transactions.closed, [(False, 41)])
        self.assertIsNone(transactions.active, "no application transaction may stay open")
        self.assertNoJellyJamsProblems()

    def test_transaction_leaves_a_closed_step_alone(self):
        transactions = self.use_transactions(closes_on_commit=True)
        doc = FakeDocument("Doc", transactions=transactions)
        with self.doc_utils.transaction(doc, "Harness Step"):
            pass
        self.assertEqual(transactions.closed, [])
        self.assertIsNone(transactions.active)

    def test_transaction_inside_an_outer_step_does_not_close_it(self):
        transactions = self.use_transactions()
        transactions.active = ("Outer Command", 5)
        doc = FakeDocument("Doc", transactions=transactions)
        with self.doc_utils.transaction(doc, "Harness Step"):
            pass
        self.assertEqual(doc.call_names(), ["openTransaction", "commitTransaction"])
        self.assertEqual(transactions.closed, [])
        self.assertEqual(transactions.active, ("Outer Command", 5))

    def test_transaction_error_aborts_or_commits_and_closes(self):
        for abort, expected in ((True, "abortTransaction"), (False, "commitTransaction")):
            with self.subTest(abort_on_error=abort):
                transactions = self.use_transactions()
                doc = FakeDocument("Doc", transactions=transactions)
                with self.assertRaises(RuntimeError):
                    with self.doc_utils.transaction(doc, "Harness Step", abort_on_error=abort):
                        raise RuntimeError("block failed in the harness")
                self.assertEqual(doc.call_names(), ["openTransaction", expected])
                self.assertEqual(transactions.closed, [(abort, 41)])
                self.assertIsNone(transactions.active)

    def test_transaction_without_the_application_transaction_api(self):
        self.assertFalse(hasattr(STUBS.app, "getActiveTransaction"))
        doc = FakeDocument("Doc")
        with self.doc_utils.transaction(doc, "Harness Step") as opened:
            self.assertIs(opened, True)
        self.assertEqual(doc.call_names(), ["openTransaction", "commitTransaction"])
        self.assertNoJellyJamsProblems()

    def test_transaction_joins_a_pending_step(self):
        transactions = self.use_transactions()
        doc = FakeDocument("Doc", transactions=transactions)
        doc.HasPendingTransaction = True
        with self.doc_utils.transaction(doc, "Harness Step", join_pending=True) as opened:
            self.assertIs(opened, False)
        self.assertEqual(doc.calls, [])
        self.assertEqual(transactions.closed, [])
        with self.doc_utils.transaction(None, "Harness Step") as opened:
            self.assertIs(opened, False)

    def test_sheet_sketch_watcher_adds_one_undo_observer(self):
        sketch = self.module("jellyjams.sheet_sketch")
        self.patch(sketch, "_watcher", object())
        self.patch(sketch, "_undo_watcher", None)
        sketch.install_watcher()
        sketch.install_watcher()
        observers = [o for o in STUBS.doc_observers if type(o).__name__ == "_UndoObserver"]
        self.assertEqual(len(observers), 1)
        self.assertNoJellyJamsProblems()


class Test22TreeNaming(DocumentCase):
    def setUp(self):
        super().setUp()
        STUBS.set_active_workbench(WB)
        self.naming = self.module("jellyjams.naming", fresh=True)
        self.naming.enable()
        self.addCleanup(self.naming.disable)
        self.assertTrue(self.naming.is_enabled())
        self.observer = self.naming._observer
        self.assertIn(self.observer, STUBS.doc_observers)
        self.doc = FakeDocument("Asm")
        self.assembly = FakeObject(self.doc, "Assembly", "Assembly::AssemblyObject", "Assembly1", Group=[])
        self.joints = FakeObject(self.doc, "Joints", "Assembly::JointGroup", "Mates", Group=[])
        self.joints.InList.append(self.assembly)
        self.open_documents(self.doc)

    def settle(self):
        STUBS.pump(30)

    def new_link(self, name="Link"):
        link = FakeObject(self.doc, name, "App::Link", name, LinkedObject=None)
        link.InList.append(self.assembly)
        self.assembly.Group.append(link)
        self.observer.slotCreatedObject(link)
        self.settle()
        return link

    def new_joint(self, name, label, joint_type):
        joint = FakeObject(self.doc, name, "App::FeaturePython", label, JointType=joint_type, Distance=0.0)
        joint.InList.append(self.joints)
        self.joints.Group.append(joint)
        return joint

    def test_new_part_is_named_when_its_link_target_arrives(self):
        link = self.new_link()
        self.assertEqual(link.Label, "Link", "a link without a target cannot be named yet")
        self.assertEqual(list(self.naming._pending_links), [("Asm", "Link")])
        part = FakeObject(self.doc, "Part", "App::Part", "Plate")
        link.LinkedObject = part
        self.observer.slotChangedObject(link, "LinkedObject")
        self.settle()
        self.assertEqual(link.Label, "Plate<1>")
        self.assertEqual(list(self.naming._pending_links), [])
        second = self.new_link("Link001")
        second.LinkedObject = part
        self.observer.slotChangedObject(second, "LinkedObject")
        self.settle()
        self.assertEqual(second.Label, "Plate<2>")
        link.LinkedObject = FakeObject(self.doc, "Part001", "App::Part", "Shaft")
        self.observer.slotChangedObject(link, "LinkedObject")
        self.settle()
        self.assertEqual(link.Label, "Plate<1>", "a named component keeps its name when its target changes")
        self.assertNoJellyJamsProblems()

    def test_pending_links_wait_out_undo_and_are_dropped(self):
        link = self.new_link()
        self.doc.Transacting = True
        link.LinkedObject = FakeObject(self.doc, "Part", "App::Part", "Plate")
        self.observer.slotChangedObject(link, "LinkedObject")
        self.settle()
        self.assertEqual(link.Label, "Link", "undo/redo must not rename")
        self.assertEqual(list(self.naming._pending_links), [("Asm", "Link")])
        self.doc.Transacting = False
        self.observer.slotDeletedDocument(self.doc)
        self.assertEqual(list(self.naming._pending_links), [])
        other = self.new_link("Link001")
        self.assertEqual(list(self.naming._pending_links), [("Asm", "Link001")])
        STUBS.set_active_workbench("PartDesignWorkbench")
        self.observer.slotDeletedObject(other)
        self.assertEqual(list(self.naming._pending_links), [], "a deleted link is forgotten even while inactive")
        self.assertNoJellyJamsProblems()

    def test_joint_type_change_renames_a_default_mate_label(self):
        lock = self.new_joint("Joint", "Lock1", "Fixed")
        # FreeCAD swapped the type word when "Ball Joint1" became a Fixed joint.
        changed = self.new_joint("Joint001", "Fixed Joint1", "Fixed")
        custom = self.new_joint("Joint002", "Front bearing", "Fixed")
        self.observer.slotChangedObject(changed, "JointType")
        self.settle()
        self.assertEqual([j.Label for j in (lock, changed, custom)], ["Lock1", "Lock2", "Front bearing"])
        changed.JointType = "Ball"
        self.observer.slotChangedObject(changed, "JointType")
        self.settle()
        self.assertEqual(changed.Label, "Ball Joint1")
        STUBS.set_active_workbench("PartDesignWorkbench")
        changed.JointType = "Revolute"
        self.observer.slotChangedObject(changed, "JointType")
        self.settle()
        self.assertEqual(changed.Label, "Ball Joint1", "nothing is renamed while JellyJams is inactive")
        self.assertNoJellyJamsProblems()


class Test22AssemblySelection(DocumentCase):
    def setUp(self):
        super().setUp()
        self.doc = FakeDocument("Asm")
        self.assembly = FakeObject(self.doc, "Assembly", "Assembly::AssemblyObject", Group=[])
        self.component = FakeObject(self.doc, "Link", "App::Link", "Plate<1>")
        self.assembly.Group.append(self.component)
        self.component.InList.append(self.assembly)
        self.other = FakeDocument("Other")
        # Object names are unique per document only: this one matches the assembly's.
        self.twin = FakeObject(self.other, "Assembly", "Assembly::AssemblyObject", Group=[])
        self.twin_link = FakeObject(self.other, "Link", "App::Link")
        self.calls = []

    def reference(self, _assembly, root, sub):
        self.calls.append((root.Document.Name, sub))
        return self.component, sub.split(".", 1)[-1]

    def test_mate_panel_ignores_other_documents_and_dead_entries(self):
        mate_panel = self.module("jellyjams.mate_panel")
        utils = types.SimpleNamespace(getComponentReference=self.reference)

        class BrokenEntry:
            SubElementNames = ("Link.Face1",)

            @property
            def Object(self):
                raise RuntimeError("selection entry broken by the harness")

        STUBS.selection_ex[:] = [
            types.SimpleNamespace(Object=None, SubElementNames=["Link.Face1"]),
            types.SimpleNamespace(Object=DeadObject(), SubElementNames=["Link.Face1"]),
            BrokenEntry(),
            types.SimpleNamespace(Object=self.twin, SubElementNames=["Link.Face1"]),
            types.SimpleNamespace(Object=self.assembly, SubElementNames=["Link.Face1", "Link.Edge2"]),
        ]
        entities = mate_panel._selected_entities(utils, self.assembly)
        self.assertEqual(self.calls, [("Asm", "Link.Face1"), ("Asm", "Link.Edge2")],
                         "components are looked up only for roots of the assembly's document")
        self.assertEqual(len(entities), 2)
        self.assertTrue(all(entity.component is self.component for entity in entities))
        del self.calls[:]
        self.assertEqual(mate_panel._selected_entities(utils, types.SimpleNamespace(Name="Assembly")), [])
        self.assertEqual(self.calls, [])
        self.assertNoJellyJamsProblems()

    def test_rotate_component_ignores_other_documents(self):
        commands = self.module("jellyjams.assembly_commands")
        self.fakes({"UtilsAssembly": fake_module("UtilsAssembly", getComponentReference=self.reference,
                                                 activeAssembly=lambda: self.assembly)})
        assembly = self.assembly

        class BrokenSubs:
            Object = assembly

            @property
            def SubElementNames(self):
                raise RuntimeError("sub-elements broken by the harness")

        STUBS.selection_ex[:] = [
            types.SimpleNamespace(Object=self.twin, SubElementNames=["Link.Face1"]),
            types.SimpleNamespace(Object=self.twin_link, SubElementNames=[]),
            types.SimpleNamespace(Object=DeadObject(), SubElementNames=[]),
            BrokenSubs(),
            types.SimpleNamespace(Object=self.assembly, SubElementNames=["Link.Face1"]),
            types.SimpleNamespace(Object=self.component, SubElementNames=[]),
        ]
        self.assertEqual(commands.selected_components(self.assembly), [self.component])
        self.assertEqual(self.calls, [("Asm", "Link.Face1")])
        del self.calls[:]
        self.assertEqual(commands.selected_components(types.SimpleNamespace(Name="Assembly")), [])
        self.assertEqual(self.calls, [])


    def test_failed_rotation_releases_its_empty_application_transaction(self):
        commands = self.module("jellyjams.assembly_commands")
        transactions = self.use_transactions(closes_on_commit=False)
        doc = FakeDocument("RotationFailure", transactions=transactions)
        doc.openTransaction("Rotate Component")
        opened = transactions.active[1]
        tool = commands._RotateTool.__new__(commands._RotateTool)
        tool.document = lambda: doc
        tool.left_down = True
        tool.in_transaction = True
        tool._transaction_id = opened
        tool.finish_drag()
        tool.finish_drag()
        self.assertIsNone(transactions.active)
        self.assertEqual(transactions.closed, [(False, opened)])
        self.assertFalse(tool.in_transaction)
        self.assertFalse(tool.left_down)
        self.assertEqual(tool._transaction_id, 0)


class Test22MakeDrawing(DocumentCase):
    def setUp(self):
        super().setUp()
        self.make = self.module("jellyjams.make_drawing")
        self.dialogs = []
        self.save_answer = ("", "")
        self.format_answer = ("", False)
        widgets = types.SimpleNamespace(
            QFileDialog=types.SimpleNamespace(getSaveFileName=self.save_file_name),
            QMessageBox=types.SimpleNamespace(information=lambda *args: self.dialogs.append("information")),
            QInputDialog=types.SimpleNamespace(getItem=self.get_item),
        )
        self.patch(self.make, "QtWidgets", widgets)
        self.new_documents = []
        self.patch(STUBS.app, "newDocument", lambda *args: self.new_documents.append(args))

    def save_file_name(self, *_args):
        self.dialogs.append("getSaveFileName")
        return self.save_answer

    def get_item(self, *_args):
        self.dialogs.append("getItem")
        return self.format_answer

    def test_sketch_only_document_has_nothing_to_draw(self):
        doc = FakeDocument("Sketches", file_name=os.path.join(self.tmpdir(), "Sketches.FCStd"))
        FakeObject(doc, "Sketch", "Sketcher::SketchObject")
        STUBS.app.ActiveDocument = doc
        command = self.make.get_commands()["JellyJams_MakeDrawing"]
        self.assertIs(command.IsActive(), False)
        self.make.make_drawing()
        self.assertEqual(self.dialogs, ["information"])
        self.assertEqual((STUBS.run_calls, self.new_documents, doc.calls), ([], [], []))
        FakeObject(doc, "Box", "Part::Box")
        self.assertIs(command.IsActive(), True)
        self.assertNoJellyJamsProblems()

    def test_file_of_an_open_document_is_refused(self):
        folder = self.tmpdir()
        model = FakeDocument("Shaft", label="Shaft", file_name=os.path.join(folder, "Shaft.FCStd"))
        FakeObject(model, "Box", "Part::Box")
        other = FakeDocument("Bracket_Drawing", label="Bracket Drawing",
                             file_name=os.path.join(folder, "Bracket_Drawing.FCStd"))
        self.open_documents(model, other)
        STUBS.app.ActiveDocument = model
        self.format_answer = (self.make.FORMATS[0], True)
        self.save_answer = (os.path.join(folder, "BRACKET_DRAWING"), "")
        self.make.make_drawing()
        self.assertEqual(self.dialogs, ["getItem", "getSaveFileName"])
        self.assertEqual(self.new_documents, [], "no drawing document may be created")
        errors = self.jj("error")
        self.assertEqual(len(errors), 1, self.lines())
        self.assertIn("Bracket Drawing", errors[0])
        cases = [(os.path.join(folder, "bracket_drawing.fcstd"), "Bracket Drawing"),
                 (os.path.join(folder, "sub", os.pardir, "SHAFT.FCStd"), "Shaft")]
        for chosen, owner in cases:
            with self.subTest(chosen=chosen):
                STUBS.records.clear()
                self.save_answer = (chosen, "")
                self.assertIsNone(self.make._ask_drawing_path(None, model))
                errors = self.jj("error")
                self.assertEqual(len(errors), 1, self.lines())
                self.assertIn('"%s"' % owner, errors[0])
        STUBS.records.clear()
        self.save_answer = (os.path.join(folder, "Shaft_Drawing"), "")
        path = self.make._ask_drawing_path(None, model)
        self.assertEqual(norm_path(path), norm_path(os.path.join(folder, "Shaft_Drawing.FCStd")))
        self.assertTrue(path.endswith(".FCStd"))
        self.save_answer = ("", "")
        self.assertIsNone(self.make._ask_drawing_path(None, model))
        self.assertEqual(self.jj("error"), [])


class Test22ViewLabels(DocumentCase):
    def setUp(self):
        super().setUp()
        STUBS.set_active_workbench(WB)
        self.labels = self.module("jellyjams.view_labels", fresh=True)
        self.transactions = self.use_transactions()
        self.doc = FakeDocument("Drawing", transactions=self.transactions)
        self.page = FakePage(self.doc)
        self.open_documents(self.doc)

    def add_view(self, name, type_id, **values):
        properties = dict(X=100.0, Y=80.0, Scale=1.0)
        properties.update(values)
        view = FakeObject(self.doc, name, type_id, name, **properties)
        self.page.addView(view)
        return view

    def queue(self, *views):
        for view in views:
            self.labels._queue.append((self.doc.Name, view.Name))

    def captions(self):
        return {obj.CaptionFor.Name: obj for obj in self.doc.Objects if "CaptionFor" in obj.PropertiesList}

    def test_new_views_are_labelled_in_one_closed_undo_step(self):
        section = self.add_view("SectionView", "TechDraw::DrawViewSection", SectionSymbol="", BaseView=None)
        detail = self.add_view("DetailView", "TechDraw::DrawViewDetail", Reference="", Scale=2.0, Radius=10.0)
        self.queue(section, detail)
        self.labels._process_queue()
        names = self.doc.call_names()
        self.assertEqual(self.labels.UNDO_NAME, "View Label")
        self.assertEqual(self.doc.calls[0], ("openTransaction", "View Label"))
        self.assertEqual(names.count("openTransaction"), 1, self.doc.calls)
        self.assertEqual(names.count("addObject"), 2)
        self.assertEqual(names[-2:], ["recompute", "commitTransaction"])
        self.assertEqual(self.transactions.closed, [(False, 41)],
                         "the step is closed even when the document left it open")
        self.assertIsNone(self.transactions.active)
        self.assertEqual((section.SectionSymbol, section.Label), ("A", "Section View A-A"))
        self.assertEqual((detail.Reference, detail.Label), ("Z", "Detail View Z (2:1)"))
        captions = self.captions()
        self.assertEqual(sorted(captions), ["DetailView", "SectionView"])
        self.assertEqual(captions["SectionView"].Text, ["A-A"])
        self.assertEqual(captions["DetailView"].Text, ["Z (2:1)"])
        # Radius 10 at scale 2 reaches 20 mm below the view's anchor (Y 80); the caption
        # anchor sits the clearance below that.
        self.assertEqual(self.labels.CAPTION_CLEARANCE_MM, 6.0)
        self.assertEqual(captions["DetailView"].Y, 80.0 - (10.0 * 2.0 + 6.0))
        self.assertEqual(self.labels.CAPTION_HEIGHT_MM, 5.0)
        self.assertEqual(self.labels.QUEUE_POLL_MS, 250)
        for caption in captions.values():
            self.assertIn(caption, self.page.Views)
            self.assertEqual(caption.TextSize, self.labels.CAPTION_HEIGHT_MM)
            self.assertEqual(caption._tooltips["CaptionFor"], self.labels.LABEL_TOOLTIP)
        self.assertEqual(list(self.labels._queue), [])
        self.assertNoJellyJamsProblems()

    def test_failed_labelling_still_closes_the_step(self):
        section = self.add_view("SectionView", "TechDraw::DrawViewSection", SectionSymbol="", BaseView=None)
        self.page._refuse_add = RuntimeError("addView refused by the harness")
        self.doc.recompute_error = RuntimeError("recompute refused by the harness")
        self.queue(section)
        self.labels._process_queue()
        names = self.doc.call_names()
        self.assertEqual((names[0], names[-1]), ("openTransaction", "commitTransaction"))
        self.assertEqual(names.count("commitTransaction"), 1)
        self.assertEqual(self.transactions.closed, [(False, 41)])
        self.assertIsNone(self.transactions.active)
        self.assertEqual(self.jj("warning") + self.jj("error"), [])
        self.assertTrue(self.jj("log"))

    def test_labelling_waits_for_a_view_drag(self):
        sheet_drag = self.module("jellyjams.sheet_drag")
        dragging = [True]
        self.patch(sheet_drag, "is_dragging", lambda: dragging[0])
        section = self.add_view("SectionView", "TechDraw::DrawViewSection", SectionSymbol="", BaseView=None)
        self.queue(section)
        self.labels._process_queue()
        self.assertEqual(self.doc.calls, [])
        self.assertEqual(list(self.labels._queue), [("Drawing", "SectionView")])
        dragging[0] = False
        self.labels._process_queue()
        self.assertEqual(section.SectionSymbol, "A")
        self.assertEqual(list(self.labels._queue), [])


class Test22SheetFormat(DocumentCase):
    def setUp(self):
        super().setUp()
        self.props = self.module("jellyjams.sheet_properties")
        self.transactions = self.use_transactions()
        self.doc = FakeDocument("Drawing", transactions=self.transactions)
        self.template = FakeObject(self.doc, "Template", "TechDraw::DrawSVGTemplate", "Sheet Format1",
                                   Template=os.path.join(self.tmpdir(), "A4_Landscape.svg"), Width=200.0,
                                   Height=100.0, EditableTexts={"title": "Old title", "scale": "1:1"})
        self.page = FakePage(self.doc, Template=self.template, ProjectionType="First angle")
        self.view = self.free("View", "TechDraw::DrawViewPart", 100.0, 50.0)
        self.clip = self.free("Clip", "TechDraw::DrawViewClip", 150.0, 60.0, Views=[])
        self.inner = self.free("Inner", "TechDraw::DrawViewPart", 10.0, 5.0)
        self.clip.Views.append(self.inner)
        self.inner.InList.append(self.clip)
        self.dimension = self.free("Dimension", "TechDraw::DrawViewDimension", 1.0, 2.0)
        self.weld = self.free("Weld", "TechDraw::DrawViewSymbol", 120.0, 60.0, SymbolType="weld", ArrowheadX=90.0,
                              ArrowheadY=40.0)
        self.caption = self.free("ViewLabel", "TechDraw::DrawViewAnnotation", 100.0, 20.0, CaptionFor=self.view)
        self.view.InList.append(self.caption)
        # Like the view-label observer: a caption follows every move of its view.
        self.view._hook = self.caption_follows

    def free(self, name, type_id, x, y, **values):
        obj = FakeObject(self.doc, name, type_id, name, X=x, Y=y, **values)
        self.page.addView(obj)
        return obj

    def caption_follows(self, _view, prop, old, new):
        if prop in ("X", "Y") and old is not None:
            setattr(self.caption, prop, getattr(self.caption, prop) + (new - old))

    def test_snapshot_skips_attached_and_cropped_views(self):
        snapshot = self.props._position_snapshot(self.page)
        self.assertEqual([entry[0].Name for entry in snapshot], ["View", "Clip", "Weld", "ViewLabel"],
                         "free views first, view captions last")
        self.assertEqual(snapshot[2][1:], (120.0, 60.0, (90.0, 40.0)))
        self.assertIsNone(snapshot[0][3])

    def test_rescale_writes_every_position_once_from_the_snapshot(self):
        snapshot = self.props._position_snapshot(self.page)
        self.props._rescale_positions(snapshot, (200.0, 100.0), (400.0, 300.0))
        self.assertEqual((self.view.X, self.view.Y), (200.0, 150.0))
        self.assertEqual((self.clip.X, self.clip.Y), (300.0, 180.0))
        self.assertEqual((self.inner.X, self.inner.Y), (10.0, 5.0), "a cropped view keeps its offset")
        self.assertEqual(self.inner._writes, [])
        self.assertEqual(self.dimension._writes, [])
        self.assertEqual((self.weld.X, self.weld.Y), (240.0, 180.0))
        self.assertEqual((self.weld.ArrowheadX, self.weld.ArrowheadY), (180.0, 120.0), "the weld arrow tip is scaled too")
        self.assertEqual((self.caption.X, self.caption.Y), (200.0, 60.0), "the caption is not moved twice")
        for obj in (self.view, self.clip, self.weld, self.caption):
            obj._writes.clear()
        self.props._rescale_positions(self.props._position_snapshot(self.page), (400.0, 300.0), (400.0, 300.0))
        self.assertEqual([obj._writes for obj in (self.view, self.clip, self.weld, self.caption)], [[], [], [], []])

    def test_switching_the_sheet_format_is_one_undo_step(self):
        templates = self.module("jellyjams.templates")
        self.patch(templates, "resolve_for_method", lambda path, _method: path)
        new_path = os.path.join(self.tmpdir(), "A3_Landscape.svg")

        def load_template(template, prop, _old, _new):
            if prop == "Template":
                template.__dict__.update(Width=400.0, Height=300.0, EditableTexts={
                    "title": "Sample", "scale": "Sample", "sheet_number": "Sample"})

        self.template._hook = load_template
        self.props.apply_sheet_properties(self.page, new_path, "Third angle", {"title": "Bracket"})
        self.assertEqual(self.template.Template, new_path)
        self.assertEqual(self.template.EditableTexts, {"title": "Bracket", "scale": "1:1", "sheet_number": ""})
        self.assertEqual(self.page.ProjectionType, "Third angle")
        self.assertEqual((self.view.X, self.view.Y), (200.0, 150.0))
        self.assertEqual((self.caption.X, self.caption.Y), (200.0, 60.0))
        self.assertEqual((self.weld.ArrowheadX, self.weld.ArrowheadY), (180.0, 120.0))
        self.assertEqual((self.inner.X, self.inner.Y), (10.0, 5.0))
        self.assertEqual(self.doc.calls, [("openTransaction", "Sheet Properties"), ("recompute",),
                                          ("commitTransaction",)])
        self.assertEqual(self.transactions.closed, [(False, 41)])
        self.assertNoJellyJamsProblems()


class Test22ViewDrag(DocumentCase):
    def setUp(self):
        super().setUp()
        self.sheet_drag = self.module("jellyjams.sheet_drag")
        self.transactions = self.use_transactions()
        self.doc = FakeDocument("Drawing", transactions=self.transactions)
        self.view = FakeObject(self.doc, "View", "TechDraw::DrawViewPart", X=100.0, Y=50.0)
        self.scene = QtWidgets.QGraphicsScene()
        self.graphics = QtWidgets.QGraphicsView(self.scene)
        self.graphics.resize(400, 300)
        self.addCleanup(self.graphics.deleteLater)
        self.patch(self.sheet_drag, "_drag", None)

    def start(self, axis=None):
        start = self.graphics.mapToScene(QtCore.QPoint(10, 10))
        drag = self.sheet_drag._Drag(self.graphics.viewport(), self.graphics, self.doc, self.view, axis, start)
        self.sheet_drag._drag = drag
        return drag

    def test_a_drag_without_movement_leaves_no_undo_step(self):
        self.start()
        self.assertTrue(self.sheet_drag.is_dragging())
        self.sheet_drag._drag_to(QtCore.QPointF(10, 10))
        self.assertTrue(self.sheet_drag._finish_drag())
        self.assertEqual(self.doc.calls, [], "no undo step, no recompute")
        self.assertEqual(self.view._writes, [])
        self.assertIsNone(self.transactions.active)
        self.assertFalse(self.sheet_drag.is_dragging())

    def test_a_drag_is_one_closed_undo_step(self):
        drag = self.start(axis="x")
        self.assertFalse(drag.undo_open)
        self.sheet_drag._drag_to(QtCore.QPointF(60, 40))
        self.sheet_drag._drag_to(QtCore.QPointF(70, 40))
        self.assertAlmostEqual(self.view.X, 106.0)
        self.assertEqual(self.view.writes("Y"), [], "a horizontal-only drag never writes Y")
        self.assertTrue(self.sheet_drag._finish_drag())
        self.assertEqual(self.doc.calls, [("openTransaction", "Move View"), ("commitTransaction",), ("recompute",)])
        self.assertEqual(self.transactions.closed, [(False, 41)])
        self.assertIsNone(self.transactions.active)
        self.assertFalse(self.sheet_drag._finish_drag())


class Test22InsertPicture(DocumentCase):
    def setUp(self):
        super().setUp()
        self.picture = self.module("jellyjams.insert_picture")
        self.folder = self.tmpdir()

    def write(self, name, data):
        path = os.path.join(self.folder, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def test_unusable_files_are_rejected_before_an_undo_step(self):
        drawing_common = self.module("jellyjams.drawing_common")
        transactions = self.use_transactions()
        self.patch(STUBS.app, "setActiveTransaction", lambda *args: transactions.open(args[0]))
        doc = FakeDocument("Drawing", transactions=transactions)
        page = FakePage(doc)
        self.patch(drawing_common, "target_sheet", lambda *_args: page)
        cases = [self.write("logo.gif", b"GIF89a"),
                 self.write("latin.svg", "<svg>é</svg>".encode("latin-1")),
                 os.path.join(self.folder, "missing.png")]
        for path in cases:
            with self.subTest(file=os.path.basename(path)):
                STUBS.records.clear()
                self.patch(self.picture, "_ask_file", lambda _doc, _path=path: _path)
                self.picture._insert_picture()
                errors = self.jj("error")
                self.assertEqual(len(errors), 1, self.lines())
                self.assertIn(os.path.basename(path), errors[0])
                self.assertEqual(doc.calls, [])
                self.assertIsNone(transactions.active, "no undo step may be opened for a rejected file")
        svg = self.write("logo.svg", svg_doc('width="64mm" height="24mm" viewBox="0 0 64 24"').encode("utf-8"))
        kind, data, natural = self.picture._read_picture(svg)
        self.assertEqual(kind, "svg")
        self.assertIn("<svg", data)
        self.assertAlmostEqual(natural[0], 64.0)
        self.assertAlmostEqual(natural[1], 24.0)
        with self.assertRaises(self.picture.PictureError):
            self.picture._read_picture(os.path.join(self.folder, "drawing.dxf"))


# ==========================================================================
# 23. Sketch first, and staying in JellyJams while a feature is edited
# ==========================================================================


class Test23SmartDimension(HarnessCase):
    def setUp(self):
        super().setUp()
        self.dimension = self.module("jellyjams.sketch_dimension", fresh=True)
        self.fcgui = self.module("jellyjams.fcgui")
        self.addCleanup(self.dimension.stop)

    def preview(self):
        state = {"selected": True, "native_calls": 0, "distance": 6.0, "writes": []}
        sketch = types.SimpleNamespace(
            Constraints=[types.SimpleNamespace(Type="DistanceX")], Geometry=[],
            getLabelDistance=lambda i: state["distance"],
            setLabelDistance=lambda i, value: (state["writes"].append((i, value)),
                                              state.update(distance=value)))
        self.patch(self.fcgui, "jellyjams_active", lambda: True)
        self.patch(self.fcgui, "sketch_in_edit", lambda: sketch)
        self.patch(self.fcgui, "selection", lambda: [sketch] if state["selected"] else [])
        self.patch(self.dimension, "_gap", lambda view, widget: 1.0)

        class Viewport(QtWidgets.QWidget):
            def mouseMoveEvent(self, event):
                state["native_calls"] += 1
                state["distance"] = 6.0
                super().mouseMoveEvent(event)

        viewport = Viewport()
        viewport.setMouseTracking(True)
        self.addCleanup(viewport.deleteLater)
        session = self.dimension._PreviewFilter(sketch, object(), viewport, 0)
        self.dimension._session = session
        return session, viewport, sketch, state

    def move(self, widget):
        event = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(12, 18),
                                  QtCore.QPointF(12, 18), QtCore.Qt.MouseButton.NoButton,
                                  QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(widget, event)

    def test_native_gap_landscape_portrait_and_invalid_camera(self):
        gap = self.dimension.preview_gap
        self.assertAlmostEqual(gap(40, 2), 1.2)
        self.assertAlmostEqual(gap(40, .5), 1.2)
        self.assertAlmostEqual(gap(40, 1), .8)
        for height, aspect in ((0, 1), (40, 0), (-1, 1), (float("nan"), 1)):
            with self.assertRaises(ValueError):
                gap(height, aspect)

    def test_native_delivery_once_and_repeated_moves_do_not_accumulate(self):
        session, widget, sketch, state = self.preview()
        self.move(widget)
        self.move(widget)
        self.assertEqual(state["native_calls"], 2)
        self.assertEqual(state["writes"], [(0, 7.0), (0, 7.0)])

    def test_confirmed_and_preexisting_labels_are_never_shifted(self):
        session, widget, sketch, state = self.preview()
        state["selected"] = False  # native tool cleared its selection on confirm
        session.correct()
        state["selected"] = True
        session.correct()
        self.assertEqual(session.floor, 1)
        self.assertEqual(state["writes"], [])

    def test_only_linear_dimensions_and_not_arc_length(self):
        sketch = types.SimpleNamespace(Geometry=[types.SimpleNamespace(TypeId="Part::GeomArcOfCircle")])
        for kind, expected in (("Radius", False), ("Angle", False), ("DistanceX", True),
                               ("DistanceY", True), ("Distance", False)):
            c = types.SimpleNamespace(Type=kind, First=0, FirstPos=0, SecondPos=0)
            self.assertEqual(self.dimension._linear(sketch, c), expected)
        sketch.Geometry[0].TypeId = "Part::GeomLineSegment"
        self.assertTrue(self.dimension._linear(sketch, c))

    def test_failed_correction_does_not_deliver_native_event_twice(self):
        session, widget, sketch, state = self.preview()

        def broken():
            raise RuntimeError("failed label lookup")

        self.patch(session, "correct", broken)
        self.move(widget)
        self.assertEqual(state["native_calls"], 1)
        self.assertIsNone(self.dimension._session)
        self.assertEqual(len(self.jj("warning")), 1)

    def test_leaving_edit_and_stop_remove_filter_idempotently(self):
        session, widget, sketch, state = self.preview()
        self.patch(self.fcgui, "sketch_in_edit", lambda: None)
        self.move(widget)
        self.assertIsNone(self.dimension._session)
        self.assertEqual(state["writes"], [])
        self.dimension.stop()
        self.dimension.stop()

    def test_modal_arrow_does_not_stop_continuous_dimension_but_other_tool_does(self):
        session, widget, sketch, state = self.preview()
        session.cursor = QtGui.QImage(32, 32, QtGui.QImage.Format.Format_ARGB32)
        session.cursor.fill(QtGui.QColor("red"))
        widget.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        self.assertTrue(session.same_cursor())
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtGui.QColor("green"))
        widget.setCursor(QtGui.QCursor(pixmap))
        self.move(widget)
        self.assertIsNone(self.dimension._session)
        self.assertEqual(state["writes"], [])

    def test_ribbon_routes_dimension_once_and_other_commands_stop_correction(self):
        calls = []
        self.patch(self.dimension, "run", lambda: calls.append("dimension"))
        self.patch(self.dimension, "stop", lambda: calls.append("stop"))
        ribbon = self.module("jellyjams.ribbon")
        ribbon.run_entry("Sketcher_Dimension")
        self.assertEqual(calls, ["stop", "dimension"])
        self.assertEqual(STUBS.run_calls, [])
        ribbon.run_entry("Sketcher_CreateLine")
        self.assertEqual(calls[-1], "stop")
        self.assertEqual(STUBS.run_calls[-1][0], "Sketcher_CreateLine")


class Test23SketchAssist(HarnessCase):
    def setUp(self):
        super().setUp()
        STUBS.active_workbench = WB
        self.assist = self.module("jellyjams.sketch_assist", fresh=True)
        self.constants = self.module("jellyjams.constants")
        self.fcgui = self.module("jellyjams.fcgui")
        self.current = None
        self.patch(self.fcgui, "sketch_in_edit", lambda: self.current)
        self.gui_observers = []
        self.patch(STUBS.gui, "addDocumentObserver", self.gui_observers.append)
        self.patch(STUBS.gui, "removeDocumentObserver", self.gui_observers.remove)
        self.addCleanup(self.assist.disable)
        self.group = param(self.constants.PARAM_SKETCH_SNAP)
        self.key = self.constants.KEY_SKETCH_ASSIST_BACKUP

    def sketch(self, auto=False, name="Sketch"):
        doc = types.SimpleNamespace(Name="Doc")
        obj = types.SimpleNamespace(Name=name, Document=doc, TypeId="Sketcher::SketchObject",
                                    isDerivedFrom=lambda kind: kind == "Sketcher::SketchObject")
        obj.ViewObject = types.SimpleNamespace(Object=obj, Autoconstraints=auto)
        return obj

    def enter(self, auto=False):
        self.current = self.sketch(auto)
        self.assist.enable()
        return self.current.ViewObject

    def test_only_sketch_edit_enables_aids_and_does_not_touch_grid(self):
        self.group.SetBool("SnapToGrid", False)
        self.group.SetBool("Snap", False)
        self.assist.enable()
        self.assertFalse(self.group.GetBool("Snap"))
        self.assertNotIn(self.key, param(P_OWN).GetStrings())
        view = self.enter()
        self.assertTrue(view.Autoconstraints)
        self.assertTrue(all(self.group.GetBool(key) for key in self.assist.SNAP_KEYS))
        self.assertFalse(self.group.GetBool("SnapToGrid"))
        self.assertEqual(len(self.gui_observers), 1)
        self.assertEqual(len(STUBS.doc_observers), 1)

    def test_round_trip_absent_false_true_and_repeat(self):
        for value in (None, False, True):
            with self.subTest(value=value):
                for key in self.assist.SNAP_KEYS:
                    self.group.RemBool(key)
                    if value is not None:
                        self.group.SetBool(key, value)
                view = self.enter(auto=bool(value))
                backup = param(P_OWN).GetString(self.key)
                self.assist.enable()
                self.assist._poll()
                self.assertEqual(param(P_OWN).GetString(self.key), backup)
                self.current = None
                self.assist._poll()
                self.assertEqual(view.Autoconstraints, bool(value))
                for key in self.assist.SNAP_KEYS:
                    self.assertEqual(key in self.group.GetBools(), value is not None)
                    if value is not None:
                        self.assertEqual(self.group.GetBool(key), value)
                self.assertNotIn(self.key, param(P_OWN).GetStrings())

    def test_observer_entry_exit_and_non_sketch(self):
        self.assist.enable()
        observer = self.gui_observers[0]
        observer.slotInEdit(types.SimpleNamespace(Object=None))
        self.assertNotIn(self.key, param(P_OWN).GetStrings())
        view = self.sketch().ViewObject
        observer.slotInEdit(view)
        self.assertTrue(view.Autoconstraints)
        observer.slotResetEdit(types.SimpleNamespace(Object=None))
        self.assertTrue(view.Autoconstraints)
        observer.slotResetEdit(view)
        self.assertFalse(view.Autoconstraints)
        self.assertNotIn(self.key, param(P_OWN).GetStrings())

    def test_leave_quit_and_cancel_with_open_sketch(self):
        view = self.enter()
        self.assist.disable()
        self.assist.disable()
        self.assertFalse(view.Autoconstraints)
        self.assertFalse(self.gui_observers)
        self.assertFalse(STUBS.doc_observers)
        self.assist.enable()  # early-close fallback Cancel
        self.assertTrue(view.Autoconstraints)
        self.assist.disable()
        self.assertFalse(view.Autoconstraints)
        self.assertNotIn(self.key, param(P_OWN).GetStrings())

    def test_save_restores_file_value_and_resumes_only_same_session(self):
        view = self.enter()
        observer = self.assist._observer
        other = types.SimpleNamespace(Name="Other")
        observer.slotStartSaveDocument(other, "other.FCStd")
        self.assertTrue(view.Autoconstraints)
        observer.slotStartSaveDocument(view.Object.Document, "model.FCStd")
        self.assertFalse(view.Autoconstraints)
        self.assist._poll()
        self.assertFalse(view.Autoconstraints)
        observer.slotFinishSaveDocument(view.Object.Document, "model.FCStd")
        self.assertTrue(view.Autoconstraints)
        observer.slotStartSaveDocument(view.Object.Document, "model.FCStd")
        self.assist.disable()
        observer.slotFinishSaveDocument(view.Object.Document, "model.FCStd")
        self.assertFalse(view.Autoconstraints)

    def test_user_can_turn_aids_off_until_next_edit(self):
        view = self.enter()
        view.Autoconstraints = False
        self.group.SetBool("Snap", False)
        self.assist._poll()
        self.assertFalse(view.Autoconstraints)
        self.assertFalse(self.group.GetBool("Snap"))
        self.assist._observer.slotResetEdit(view)
        self.assist._observer.slotInEdit(view)
        self.assertTrue(view.Autoconstraints)
        self.assertTrue(self.group.GetBool("Snap"))

    def test_saving_preserves_user_disabled_auto_constraints(self):
        view = self.enter(auto=True)
        view.Autoconstraints = False
        observer = self.assist._observer
        observer.slotStartSaveDocument(view.Object.Document, "model.FCStd")
        self.assertTrue(view.Autoconstraints)  # original file value
        observer.slotFinishSaveDocument(view.Object.Document, "model.FCStd")
        self.assertFalse(view.Autoconstraints)  # current edit's choice

    def test_recovery_save_filter_restores_then_resumes_and_uninstalls(self):
        class FakeAutoSaver(QtCore.QObject):
            pass

        saver = FakeAutoSaver(STUBS.qapp)
        self.addCleanup(saver.deleteLater)
        self.patch(self.constants, "CLASS_AUTO_SAVER", "FakeAutoSaver")
        callbacks = []
        self.patch(self.fcgui, "defer", lambda fn, *args: callbacks.append(fn))
        view = self.enter()
        self.assertIs(self.assist._autosaver, saver)
        event = QtCore.QTimerEvent(12345)
        self.assertFalse(self.assist._save_filter.eventFilter(saver, event))
        self.assertFalse(view.Autoconstraints)
        self.assist._poll()
        self.assertFalse(view.Autoconstraints)
        callbacks.pop()()
        self.assertTrue(view.Autoconstraints)
        self.assist._save_filter.eventFilter(saver, event)
        self.assist.disable()
        callbacks.pop()()
        self.assertFalse(view.Autoconstraints)
        self.assertIsNone(self.assist._autosaver)

    def test_temporary_property_writes_preserve_status_flags(self):
        self.current = self.sketch()
        view = self.current.ViewObject
        status = {"ReadOnly"}
        calls = []
        view.getPropertyStatus = lambda name: list(status)

        def set_status(name, value):
            calls.append((name, value))
            if value.startswith("-"):
                status.discard(value[1:])
            else:
                status.add(value)

        view.setPropertyStatus = set_status
        self.assist.enable()
        self.assist.disable()
        self.assertEqual(status, {"ReadOnly"})
        self.assertEqual([value for name, value in calls],
                         ["NoModify", "-NoModify", "NoModify", "-NoModify"])

    def test_property_restore_failure_does_not_block_preference_restore(self):
        self.group.SetBool("Snap", False)
        view = self.enter()
        original = self.assist._set_auto

        def broken(value):
            raise RuntimeError("cannot write view property")

        self.patch(self.assist, "_set_auto", broken)
        self.assist.disable()
        self.assertFalse(self.group.GetBool("Snap"))
        self.assertIs(self.assist._view, view)  # keep original for retry
        self.patch(self.assist, "_set_auto", original)
        self.assist.disable()
        self.assertFalse(view.Autoconstraints)

    def test_recovery_restores_pending_backup_without_overwriting_it(self):
        raw = json.dumps({"Snap": [True, False], "SnapToObjects": [False, None]})
        param(P_OWN).SetString(self.key, raw)
        for key in self.assist.SNAP_KEYS:
            self.group.SetBool(key, True)
        self.assist._apply_snapping()
        self.assertEqual(param(P_OWN).GetString(self.key), raw)
        self.module("jellyjams.recovery").run_startup_recovery()
        self.assertFalse(self.group.GetBool("Snap"))
        self.assertNotIn("SnapToObjects", self.group.GetBools())
        self.assertNotIn(self.key, param(P_OWN).GetStrings())

    def test_corrupt_backups_warn_once_without_changing_preferences(self):
        self.group.SetBool("Snap", False)
        for raw in ("{bad", "[]", '{"Snap": [true, false]}',
                    '{"Snap": [true, 1], "SnapToObjects": [false, null]}'):
            with self.subTest(raw=raw):
                STUBS.records.clear()
                param(P_OWN).SetString(self.key, raw)
                self.assist.recover()
                self.assist.recover()
                self.assertEqual(len(self.jj("warning")), 1)
                self.assertFalse(self.group.GetBool("Snap"))
                self.assertNotIn(self.key, param(P_OWN).GetStrings())

    def test_failed_restore_keeps_backup_for_retry(self):
        self.group.SetBool("Snap", False)
        self.enter()
        original = self.group.SetBool

        def broken(*args):
            raise RuntimeError("cannot write preference")

        self.patch(self.group, "SetBool", broken)
        self.assist.recover()
        self.assertTrue(param(P_OWN).GetString(self.key))
        self.patch(self.group, "SetBool", original)
        self.assist.recover()
        self.assertFalse(self.group.GetBool("Snap"))

    def test_failed_backup_prevents_preference_writes(self):
        params = self.module("jellyjams.params")

        def broken(*args):
            raise RuntimeError("cannot save backup")

        self.patch(params, "save_backup", broken)
        self.group.SetBool("Snap", False)
        view = self.enter()
        self.assertFalse(view.Autoconstraints)
        self.assertFalse(self.group.GetBool("Snap"))

    def test_inactive_workbench_leaves_sketch_unchanged(self):
        STUBS.active_workbench = "PartDesignWorkbench"
        view = self.enter()
        self.assertFalse(view.Autoconstraints)
        self.assertNotIn(self.key, param(P_OWN).GetStrings())


class Test23SketchFirstRules(HarnessCase):
    """The pure decisions of sketch_gesture: when to start a new sketch and the
    state machine that follows the plane pick and the sketch edit."""

    def setUp(self):
        super().setUp()
        self.gesture = self.module("jellyjams.sketch_gesture")

    def test_sketch_first_features(self):
        constants = self.module("jellyjams.constants")
        self.assertEqual(tuple(constants.SKETCH_FIRST_FEATURES), SKETCH_FIRST_FEATURES)
        self.assertTrue(set(SKETCH_FIRST_FEATURES) <= set(PROFILE_FEATURES))
        for cmd in ("PartDesign_AdditivePipe", "PartDesign_SubtractiveLoft", "PartDesign_AdditiveHelix"):
            self.assertNotIn(cmd, constants.SKETCH_FIRST_FEATURES, "needs more than one input")
        self.assertEqual(constants.NEW_SKETCH_COMMAND, "PartDesign_NewSketch")
        self.assertEqual(constants.ACTIVE_BODY_KEY, "pdbody")

    def test_needs_new_sketch_truth_table(self):
        needs = self.gesture.needs_new_sketch
        # (selection kinds, free sketches) -> new sketch first?
        table = [
            ([], 0, True),                          # nothing to use: start a sketch
            ([], 1, False),                         # FreeCAD takes the one free sketch
            ([], 3, False),                         # FreeCAD lets the user pick one
            (["plane"], 0, True),
            (["plane"], 2, True),                   # a selected plane wins over free sketches
            (["flat_face"], 0, True),
            (["flat_face"], 1, True),
            (["plane", "flat_face"], 0, True),
            (["plane", "plane"], 1, True),
            (["sketch"], 0, False),                 # the selected sketch is the profile
            (["sketch"], 1, False),
            (["other"], 0, False),                  # FreeCAD decides (edges, curved faces, bodies)
            (["other"], 2, False),
            (["plane", "sketch"], 0, False),
            (["flat_face", "other"], 0, False),
        ]
        for cmd in PROFILE_FEATURES + ("PartDesign_Fillet", "Sketcher_CreateLine", ""):
            for kinds, free, expected in table:
                with self.subTest(cmd=cmd, kinds=kinds, free=free):
                    want = expected and cmd in SKETCH_FIRST_FEATURES
                    self.assertIs(bool(needs(cmd, list(kinds), free)), want)

    def test_advance_truth_table(self):
        g = self.gesture
        grace = g.PICK_GRACE_S
        self.assertGreater(grace, 0)
        picking = {"cmd": "PartDesign_Pad", "state": g.PICKING, "sketch": None, "since": 100.0,
                   "doc": "Part1", "before": {"Sketch"}}
        editing = dict(picking, state=g.EDITING, sketch="Sketch001", since=101.0)
        same, moved = "same", "moved"
        # intent, sketch in edit, task dialog open, sketches created since the press, now -> (intent, action)
        cases = [
            ("nothing pending", None, None, False, set(), 0.0, None, None),
            ("nothing pending, sketch open", None, "Sketch001", True, {"Sketch001"}, 0.0, None, None),
            ("picker not open yet", picking, None, False, set(), 100.0, same, None),
            ("picker not open yet, half the grace", picking, None, False, set(), 100.0 + grace / 2, same, None),
            ("picker open long", picking, None, True, set(), 100.0 + 60.0, same, None),
            ("picker cancelled at the grace", picking, None, False, set(), 100.0 + grace, None, "drop"),
            ("picker cancelled", picking, None, False, set(), 100.0 + 60.0, None, "drop"),
            ("old sketch open while picking", picking, "Sketch", True, set(), 100.0 + 60.0, same, None),
            ("old sketch open, no dialog", picking, "Sketch", False, {"Sketch001"}, 100.0 + 60.0, same, None),
            ("new sketch opened with its dialog", picking, "Sketch001", True, {"Sketch001"}, 100.5, moved, None),
            ("new sketch opened", picking, "Sketch001", False, {"Sketch001"}, 100.5, moved, None),
            ("drawing", editing, "Sketch001", True, {"Sketch001"}, 500.0, same, None),
            ("drawing, no dialog", editing, "Sketch001", False, {"Sketch001"}, 500.0, same, None),
            ("sketch closing", editing, None, True, {"Sketch001"}, 500.0, same, None),
            ("sketch exited", editing, None, False, {"Sketch001"}, 500.0, None, "start"),
            ("sketch exited at once", editing, None, False, set(), 101.0, None, "start"),
            ("another sketch opened", editing, "Sketch", False, {"Sketch001"}, 101.5, None, "drop"),
            ("another sketch opened with dialog", editing, "Sketch", True, set(), 101.5, None, "drop"),
        ]
        for label, intent, edit_name, dialog, created, now, want_state, want_action in cases:
            with self.subTest(label):
                snapshot = None if intent is None else dict(intent)
                state, action = g.advance(intent, edit_name, dialog, set(created), now)
                self.assertEqual(action, want_action)
                if want_state is None:
                    self.assertIsNone(state)
                elif want_state == same:
                    self.assertEqual(state, intent)
                else:
                    self.assertEqual(state, dict(picking, state=g.EDITING, sketch=edit_name, since=now))
                self.assertEqual(intent, snapshot, "advance() never changes the intent it is given")

    def test_retargeted_command_survives_the_move_to_editing(self):
        g = self.gesture
        intent = {"cmd": "PartDesign_Pocket", "state": g.PICKING, "sketch": None, "since": 5.0,
                  "doc": "Part1", "before": set()}
        state, action = g.advance(intent, "Sketch", True, {"Sketch"}, 5.2)
        self.assertIsNone(action)
        self.assertEqual((state["cmd"], state["state"], state["sketch"]), ("PartDesign_Pocket", g.EDITING, "Sketch"))
        state, action = g.advance(state, None, False, {"Sketch"}, 9.0)
        self.assertEqual((state, action), (None, "start"))


class Test23SketchFirstFlow(DocumentCase):
    """try_run() and the watcher with a fake Part Design document."""

    def setUp(self):
        super().setUp()
        self.gesture = self.module("jellyjams.sketch_gesture", fresh=True)
        self.addCleanup(self.forget)
        STUBS.set_active_workbench(WB)
        STUBS.set_commands(list(SKETCH_FIRST_FEATURES) + ["PartDesign_NewSketch", "Sketcher_LeaveSketch"],
                           info={"PartDesign_Pad": {"menuText": "&Pad"}, "PartDesign_Pocket": {"menuText": "Pocket"},
                                 "PartDesign_Hole": {"menuText": "&Hole"}})
        self.editing = None
        self.doc = FakeDocument("Part1")
        self.open_documents(self.doc)
        self.body = self.new_body("Body")
        self.active_body = self.body
        view = types.SimpleNamespace(getActiveObject=lambda key: self.active_body if key == "pdbody" else None)
        STUBS.gui.ActiveDocument = types.SimpleNamespace(Document=self.doc, ActiveView=view,
                                                         getInEdit=self.view_provider)

    def forget(self):
        self.gesture._intent = None
        self.gesture._pending_since = None

    def fast(self, grace=0.5):
        self.patch(self.gesture, "WATCH_MS", 5)
        self.patch(self.gesture, "PICK_GRACE_S", grace)

    def view_provider(self):
        return None if self.editing is None else types.SimpleNamespace(Object=self.editing)

    def new_body(self, name):
        body = FakeObject(self.doc, name, "PartDesign::Body", Group=[])
        body.hasObject = lambda obj: any(member is obj for member in body.Group)
        return body

    def give_solid(self, body=None):
        """The body now holds a solid feature (a pad has been made in it), which is what FreeCAD's
        Body::isSolid() looks for. Its shape is left null: the rule does not read shapes."""
        owner = body or self.body
        pad = FakeObject(self.doc, owner.Name + "Solid", "PartDesign::Pad",
                         Shape=types.SimpleNamespace(isNull=lambda: True, Solids=[]))
        owner.Group.append(pad)
        return pad

    def hole_refusal(self):
        return "Hole needs a solid to cut into: create a boss or base feature first."

    def feature(self, name, type_id="PartDesign::Pad", body=None):
        """A solid feature appended to the body's Group (no Shape needed by the rules)."""
        obj = FakeObject(self.doc, name, type_id)
        (body or self.body).Group.append(obj)
        return obj

    def sketch(self, name, wires=1, geometry=4, body=None, used=False, null=False, type_id="Sketcher::SketchObject"):
        shape = types.SimpleNamespace(isNull=lambda: null, Wires=[object()] * wires)
        obj = FakeObject(self.doc, name, type_id, Shape=shape, Geometry=[object()] * geometry)
        if body is not False:
            owner = body or self.body
            owner.Group.append(obj)
            obj.InList.append(owner)
        if used:
            obj.InList.append(FakeObject(self.doc, name + "Pad", "PartDesign::Pad"))
        return obj

    def solid(self, name):
        def get_element(sub):
            if sub == "Face1":
                return types.SimpleNamespace(findPlane=lambda: object())
            if sub == "Face2":
                return types.SimpleNamespace(findPlane=lambda: None)
            raise ValueError("no element %s" % sub)

        return FakeObject(self.doc, name, "PartDesign::Pad", Shape=types.SimpleNamespace(getElement=get_element))

    def select(self, *items):
        STUBS.selection_ex[:] = [types.SimpleNamespace(Object=obj, SubElementNames=list(subs)) for obj, subs in items]

    def state(self):
        return (self.gesture._intent or {}).get("state")

    def feature_runs(self):
        return [cmd for cmd, _index in STUBS.run_calls if cmd in SKETCH_FIRST_FEATURES]

    def status(self):
        return STUBS.main_window.statusBar().currentMessage()

    # starting -----------------------------------------------------------------------
    def plane_picker(self):
        self.gesture.try_run("PartDesign_Pad")
        panel = QtWidgets.QWidget()
        self.addCleanup(panel.deleteLater)
        form = QtWidgets.QWidget(panel)
        self.patch(form, "metaObject", lambda: types.SimpleNamespace(className=lambda: "PartDesignGui__TaskFeaturePick"))
        choices = QtWidgets.QListWidget(form)
        choices.setObjectName("listWidget")
        choices.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        plane = FakeObject(self.doc, "XY_Plane", "App::Plane")
        row = QtWidgets.QListWidgetItem("Top Plane", choices)
        row.setData(QtCore.Qt.ItemDataRole.UserRole, plane.Name)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok, panel)
        button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        clicks = []
        button.clicked.connect(lambda: clicks.append("accepted"))
        self.patch(self.module("jellyjams.fcgui"), "task_panel", lambda: panel)
        self.patch(self.module("jellyjams.fcgui"), "task_dock", lambda: panel)
        return panel, form, choices, row, button, clicks

    def test_plane_picker_confirms_one_selected_plane_once(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        row.setSelected(True)
        self.assertTrue(self.gesture._confirm_plane_pick(self.gesture._intent, self.doc))
        self.assertEqual(clicks, ["accepted"])
        self.editing = self.sketch("Sketch")
        self.assertFalse(self.gesture._confirm_plane_pick(self.gesture._intent, self.doc))
        self.assertEqual(clicks, ["accepted"])

    def test_plane_picker_finds_older_hosts_sibling_button_box(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        dock = QtWidgets.QWidget()
        self.addCleanup(dock.deleteLater)
        panel.setParent(dock)
        button.parentWidget().setParent(dock)
        self.patch(self.module("jellyjams.fcgui"), "task_dock", lambda: dock)
        row.setSelected(True)
        self.assertTrue(self.gesture._confirm_plane_pick(self.gesture._intent, self.doc))
        self.assertEqual(clicks, ["accepted"])

    def test_plane_picker_waits_without_a_single_valid_plane(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        intent = self.gesture._intent
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        row.setSelected(True)
        row.setData(QtCore.Qt.ItemDataRole.UserRole, self.body.Name)
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        row.setData(QtCore.Qt.ItemDataRole.UserRole, "XY_Plane")
        row.setHidden(True)
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        row.setHidden(False)
        second = QtWidgets.QListWidgetItem("Other", choices)
        second.setSelected(True)
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        self.assertEqual(clicks, [])

    def test_plane_picker_rejects_stale_intent_inactive_doc_and_other_dialog(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        row.setSelected(True)
        intent = self.gesture._intent
        self.assertFalse(self.gesture._confirm_plane_pick(dict(intent), self.doc))
        self.patch(self.gesture, "_active_doc", lambda: None)
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        self.patch(self.gesture, "_active_doc", lambda: self.doc)
        self.patch(form, "metaObject", lambda: types.SimpleNamespace(className=lambda: "OtherTask"))
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        self.assertEqual(clicks, [])

    def test_plane_picker_does_not_press_disabled_ok_or_disabled_plane(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        row.setSelected(True)
        button.setEnabled(False)
        self.assertFalse(self.gesture._confirm_plane_pick(self.gesture._intent, self.doc))
        button.setEnabled(True)
        row.setFlags(row.flags() & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
        self.assertFalse(self.gesture._confirm_plane_pick(self.gesture._intent, self.doc))
        self.assertEqual(clicks, [])

    def test_attachment_picker_confirms_only_new_sketch_with_one_valid_plane(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        self.patch(form, "metaObject", lambda: types.SimpleNamespace(className=lambda: "PartGui::TaskAttacher"))
        sketch = self.sketch("Sketch")
        sketch.MapMode = "Deactivated"
        sketch.AttachmentSupport = []
        intent = self.gesture._intent
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        plane = self.doc.getObject("XY_Plane")
        sketch.AttachmentSupport = [(plane, [""])]
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))
        sketch.MapMode = "FlatFace"
        self.assertTrue(self.gesture._confirm_plane_pick(intent, self.doc))
        self.assertEqual(clicks, ["accepted"])
        intent["before"].add(sketch.Name)
        self.assertFalse(self.gesture._confirm_plane_pick(intent, self.doc))

    def test_attachment_picker_resolves_origin_paths_and_rejects_multiple_references(self):
        panel, form, choices, row, button, clicks = self.plane_picker()
        sketch = self.sketch("Sketch")
        sketch.MapMode = "FlatFace"
        plane = self.doc.getObject("XY_Plane")
        origin = types.SimpleNamespace(getSubObject=lambda path, ret: plane if path == "XY_Plane." and ret == 1 else None)
        intent = self.gesture._intent
        sketch.AttachmentSupport = [(origin, ["XY_Plane."])]
        self.assertTrue(self.gesture._attachment_has_plane(intent, self.doc))
        sketch.AttachmentSupport = [(origin, ["XY_Plane.", "XZ_Plane."])]
        self.assertFalse(self.gesture._attachment_has_plane(intent, self.doc))
        sketch.AttachmentSupport = [(plane, [""]), (plane, [""])]
        self.assertFalse(self.gesture._attachment_has_plane(intent, self.doc))
        sketch.AttachmentSupport = [(origin, ["Missing."])]
        self.assertFalse(self.gesture._attachment_has_plane(intent, self.doc))

    def test_nothing_selected_and_no_free_sketch_opens_a_new_sketch(self):
        self.fast()
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), True)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])
        intent = self.gesture._intent
        self.assertEqual((intent["cmd"], intent["state"], intent["sketch"], intent["doc"]),
                         ("PartDesign_Pad", self.gesture.PICKING, None, "Part1"))
        self.assertIn("New sketch for Pad", self.status())
        self.assertNoJellyJamsProblems()

    def test_every_sketch_first_feature_starts_a_sketch(self):
        self.give_solid()   # Pocket, Groove and Hole need something to cut
        for cmd in SKETCH_FIRST_FEATURES:
            with self.subTest(cmd=cmd):
                self.forget()
                del STUBS.run_calls[:]
                self.assertIs(self.gesture.try_run(cmd), True)
                self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])
                self.assertEqual(self.gesture._intent["cmd"], cmd)

    def test_additive_features_start_a_sketch_in_an_empty_body(self):
        for cmd in ("PartDesign_Pad", "PartDesign_Revolution"):
            with self.subTest(cmd=cmd):
                self.forget()
                del STUBS.run_calls[:]
                self.assertIs(self.gesture.try_run(cmd), True)
                self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])

    # subtractive features without a solid -----------------------------------------
    def assert_refused(self, cmd, refused, label="", status=""):
        """`refused` is what try_run(cmd) returned for a body with nothing to cut. Pocket and Groove go
        to FreeCAD, which refuses them with its own message (the status bar keeps `status`); JellyJams
        turns Hole down itself, with its own status text and a console warning."""
        if cmd == "PartDesign_Hole":
            self.assertIs(refused, True, "JellyJams takes the press: FreeCAD would build a failing Hole " + label)
            self.assertEqual(self.status(), self.hole_refusal())
            self.assertEqual(self.jj("warning"), [PREFIX + self.hole_refusal() + "\n"], self.lines())
        else:
            self.assertIs(refused, False, "FreeCAD's own message shows at once " + label)
            self.assertEqual(self.status(), status)
            self.assertEqual(self.jj("warning"), [])
        self.assertEqual(self.jj("error"), [])

    def test_subtractive_features_without_a_solid_keep_freecads_refusal(self):
        self.assertEqual(self.gesture.SUBTRACTIVE_FEATURES,
                         ("PartDesign_Pocket", "PartDesign_Groove", "PartDesign_Hole"))
        self.assertEqual(self.gesture.REFUSED_BY_FREECAD, ("PartDesign_Pocket", "PartDesign_Groove"))
        self.assertEqual(self.gesture.NEEDS_SOLID_MS, 6000)
        datum = FakeObject(self.doc, "DatumPlane", "PartDesign::Plane")
        origin_plane = FakeObject(self.doc, "XY_Plane", "App::Plane")
        solid_shape = types.SimpleNamespace(isNull=lambda: False, Solids=[object()])

        def only_datums():
            self.body.Group[:] = [origin_plane, datum]

        def only_a_used_sketch():
            self.body.Group[:] = []
            self.sketch("Sketch", used=True)        # used, so no free sketch to take either

        def solid_shape_without_features():
            self.body.Group[:] = []
            self.body.Shape = solid_shape            # FreeCAD asks for a feature, not for solids

        setups = [("empty body", lambda: None), ("only planes", only_datums), ("only a sketch", only_a_used_sketch),
                  ("a solid shape but no feature", solid_shape_without_features)]
        for label, setup in setups:
            for cmd in self.gesture.SUBTRACTIVE_FEATURES:
                with self.subTest(label, cmd=cmd):
                    self.forget()
                    del STUBS.run_calls[:]
                    STUBS.records.clear()
                    STUBS.main_window.statusBar().clearMessage()
                    setup()
                    self.assertIs(self.gesture._has_solid(self.body), False)
                    refused = self.gesture.try_run(cmd)
                    self.assertEqual(STUBS.run_calls, [], "no sketch is started and nothing runs")
                    self.assertIsNone(self.gesture._intent)
                    self.assert_refused(cmd, refused, label)

    def test_hole_refusal_names_the_command(self):
        STUBS.set_commands(list(SKETCH_FIRST_FEATURES), info={"PartDesign_Hole": {"menuText": "Hole &Wizard"}})
        self.assertIs(self.gesture._refuse_without_solid("PartDesign_Hole"), True)
        self.assertEqual(self.status(), "Hole Wizard needs a solid to cut into: create a boss or base feature first.")
        for cmd in ("PartDesign_Pocket", "PartDesign_Groove"):
            with self.subTest(cmd=cmd):
                STUBS.main_window.statusBar().clearMessage()
                self.assertIs(self.gesture._refuse_without_solid(cmd), False)
                self.assertEqual(self.status(), "", "FreeCAD's own refusal is the message")
        self.assertEqual(len(self.jj("warning")), 1, self.lines())
        self.assertEqual(STUBS.run_calls, [])

    def test_hole_refusal_is_a_temporary_status_message(self):
        fcgui = self.module("jellyjams.fcgui")
        shown = []
        self.patch(fcgui, "status_message", lambda text, ms=0: shown.append((text, ms)))
        self.assertIs(self.gesture.try_run("PartDesign_Hole"), True)
        self.assertEqual(shown, [(self.hole_refusal(), 6000)])

    def test_has_solid_mirrors_freecads_is_solid(self):
        has_solid = self.gesture._has_solid
        self.assertIs(has_solid(self.body), False, "an empty body")
        self.body.Group.append(FakeObject(self.doc, "XY_Plane", "App::Plane"))
        self.body.Group.append(FakeObject(self.doc, "DatumPlane", "PartDesign::Plane"))
        self.sketch("Sketch")
        self.body.Shape = types.SimpleNamespace(isNull=lambda: False, Solids=[object()])
        self.assertIs(has_solid(self.body), False, "planes, a sketch and a shape are no Part Design feature")
        self.body.Shape = types.SimpleNamespace(isNull=lambda: True, Solids=[])
        pad = FakeObject(self.doc, "Pad", "PartDesign::Pad", Shape=types.SimpleNamespace(isNull=lambda: True,
                                                                                         Solids=[]))
        self.body.Group.append(pad)
        self.assertIs(has_solid(self.body), True, "a Pad counts even before its shape is computed")
        self.body.Group[:] = [FakeObject(self.doc, "Pocket", "PartDesign::Pocket")]
        self.assertIs(has_solid(self.body), True, "any Part Design feature")
        broken = FakeObject(self.doc, "Broken", "PartDesign::Body")
        self.assertIs(has_solid(broken), False, "a body without a readable Group")
        self.assertIs(has_solid(None), False)

    def test_subtractive_features_without_a_target_body_are_left_to_freecad(self):
        """Several bodies and none active: FreeCAD asks which body to work in (Hole, with nothing
        selected, says 'No sketch to work on'), so JellyJams neither starts a sketch nor refuses."""
        other = self.new_body("Body001")
        self.active_body = None                    # two bodies, none active: no target body
        for solids in (False, True):
            if solids:
                self.give_solid()
                self.give_solid(other)
            for cmd in self.gesture.SUBTRACTIVE_FEATURES:
                with self.subTest(cmd=cmd, solids=solids):
                    STUBS.records.clear()
                    STUBS.main_window.statusBar().clearMessage()
                    self.assertIs(self.gesture.try_run(cmd), False, "FreeCAD handles the press")
                    self.assertEqual(self.status(), "", "no refusal text")
                    self.assertEqual(self.jj("warning") + self.jj("error"), [])
                    self.assertEqual(STUBS.run_calls, [], "nothing runs: the caller runs the command")
                    self.assertIsNone(self.gesture._intent)
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), True, "additive features still start a sketch")

    def test_nothing_to_cut_needs_a_known_body(self):
        nothing_to_cut = self.gesture._nothing_to_cut
        for cmd in self.gesture.SUBTRACTIVE_FEATURES:
            with self.subTest(cmd=cmd):
                self.body.Group[:] = []
                self.active_body = self.body
                self.assertIs(nothing_to_cut(cmd, self.doc), True, "the active body has no solid")
                self.active_body = None
                self.assertIs(nothing_to_cut(cmd, self.doc), True, "the lone body has no solid")
                other = self.new_body("Body001")
                self.assertIs(nothing_to_cut(cmd, self.doc), False, "no known body: FreeCAD asks")
                self.doc.Objects.remove(other)
                self.active_body = self.body
                self.give_solid()
                self.assertIs(nothing_to_cut(cmd, self.doc), False, "something to cut")
                self.assertIs(nothing_to_cut(cmd, None), False, "no document")
        self.body.Group[:] = []
        for cmd in ("PartDesign_Pad", "PartDesign_Revolution", "PartDesign_Fillet"):
            with self.subTest(cmd=cmd):
                self.assertIs(nothing_to_cut(cmd, self.doc), False, "not a cutting feature")

    def test_retarget_to_a_cutting_feature_without_a_known_body(self):
        self.new_body("Body001")
        self.active_body = None                    # several bodies, none active
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.set_active_dialog("plane picker")
        intent = self.gesture._intent
        for cmd in self.gesture.SUBTRACTIVE_FEATURES:
            with self.subTest(cmd=cmd):
                STUBS.records.clear()
                self.assertIs(self.gesture.try_run(cmd), True)
                self.assertIs(self.gesture._intent, intent, "the same sketch-first, retargeted")
                self.assertEqual(self.gesture._intent["cmd"], cmd)
                self.assertIn("New sketch for", self.status())
                self.assertEqual(self.jj("warning"), [], "no refusal")
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])

    def test_subtractive_feature_with_a_solid_starts_a_sketch(self):
        self.give_solid()
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), True)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])
        self.assertEqual(self.gesture._intent["cmd"], "PartDesign_Pocket")
        self.assertIn("New sketch for Pocket", self.status())

    def test_other_profile_features_keep_freecads_behavior(self):
        for cmd in set(PROFILE_FEATURES) - set(SKETCH_FIRST_FEATURES):
            with self.subTest(cmd=cmd):
                self.assertIs(self.gesture.try_run(cmd), False)
        self.assertIs(self.gesture.try_run("PartDesign_Fillet"), False)
        self.assertEqual(STUBS.run_calls, [])
        self.assertIsNone(self.gesture._intent)

    def test_a_free_sketch_is_used_directly(self):
        self.sketch("Sketch")
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False, "FreeCAD's Pad takes the free sketch")
        self.assertEqual(STUBS.run_calls, [])
        self.assertIsNone(self.gesture._intent)

    def test_free_sketch_rules(self):
        count = self.gesture._free_sketch_count
        other_body = self.new_body("Body001")
        cases = [
            ("free sketch in the active body", dict(), 1),
            ("used by a feature", dict(used=True), 0),
            ("no closed wire", dict(wires=0), 0),
            ("null shape", dict(null=True), 0),
            ("in another body", dict(body=other_body), 0),
            ("outside every body", dict(body=False), 0),
            ("another 2D object type", dict(type_id="Part::Part2DObjectPython"), 1),
        ]
        for label, options, expected in cases:
            with self.subTest(label):
                self.doc.Objects[:] = [self.body, other_body]
                self.body.Group[:] = []
                other_body.Group[:] = []
                self.sketch("Sketch", **options)
                self.assertEqual(count(self.doc, self.body), expected)
        self.doc.Objects[:] = [self.body, other_body]
        self.body.Group[:] = []
        self.sketch("Sketch", body=other_body)
        self.assertEqual(count(self.doc, None), 1, "without an active body every free sketch counts")

    def test_selection_decides(self):
        plane = FakeObject(self.doc, "XY_Plane", "App::Plane")
        datum = FakeObject(self.doc, "DatumPlane", "PartDesign::Plane")
        solid = self.solid("Pad")
        free = self.sketch("Sketch")
        cases = [
            ("origin plane", [(plane, [])], True),
            ("datum plane", [(datum, [""])], True),
            ("flat face", [(solid, ["Face1"])], True),
            ("plane and flat face", [(plane, []), (solid, ["Face1"])], True),
            ("curved face", [(solid, ["Face2"])], False),
            ("edge", [(solid, ["Edge1"])], False),
            ("flat and curved face", [(solid, ["Face1", "Face2"])], False),
            ("whole solid", [(solid, [])], False),
            ("sketch", [(free, [])], False),
            ("plane and sketch", [(plane, []), (free, [])], False),
        ]
        for label, selection, starts in cases:
            with self.subTest(label):
                self.forget()
                del STUBS.run_calls[:]
                self.select(*selection)
                self.assertIs(self.gesture.try_run("PartDesign_Pad"), starts)
                self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)] if starts else [])

    # a selection of containers only counts as no selection ---------------------------------
    def test_container_only_selection_is_cleared_and_treated_as_empty(self):
        origin = FakeObject(self.doc, "Origin", "App::Origin")
        part = FakeObject(self.doc, "Part", "App::Part")
        folder = FakeObject(self.doc, "Group", "App::DocumentObjectGroup")
        cases = [
            ("the body the Body button leaves selected", [(self.body, [])]),
            ("origin", [(origin, [])]),
            ("part", [(part, [""])]),
            ("group", [(folder, [])]),
            ("body and part", [(self.body, []), (part, [])]),
        ]
        for label, selection in cases:
            with self.subTest(label):
                self.forget()
                del STUBS.run_calls[:]
                del STUBS.selection_calls[:]
                self.select(*selection)
                self.assertIs(self.gesture.try_run("PartDesign_Pad"), True, "no profile: a new sketch starts")
                self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])
                self.assertIn(("clearSelection", ()), STUBS.selection_calls)
                self.assertEqual(STUBS.selection_ex, [], "FreeCAD's plane picker opens with nothing selected")
        self.assertNoJellyJamsProblems()

    def test_container_selection_with_a_free_sketch_lets_freecad_use_the_sketch(self):
        self.sketch("Sketch")
        self.select((self.body, []))
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False)
        self.assertEqual(STUBS.run_calls, [])
        self.assertEqual(STUBS.selection_ex, [], "the body is deselected so FreeCAD takes the free sketch")
        self.assertIsNone(self.gesture._intent)

    def test_containers_mixed_with_other_items_are_left_to_freecad(self):
        plane = FakeObject(self.doc, "XY_Plane", "App::Plane")
        solid = self.solid("Pad")
        cases = [
            ("body and a plane", [(self.body, []), (plane, [])]),
            ("a face picked through the body", [(self.body, ["Face1"]), (solid, ["Edge1"])]),
        ]
        for label, selection in cases:
            with self.subTest(label):
                self.forget()
                del STUBS.selection_calls[:]
                self.select(*selection)
                self.assertIs(self.gesture.try_run("PartDesign_Pad"), False)
                self.assertNotIn(("clearSelection", ()), STUBS.selection_calls, "a mixed selection is kept")
                self.assertEqual(len(STUBS.selection_ex), len(selection))
        self.assertEqual(STUBS.run_calls, [])

    # the body that the free-sketch rule looks at --------------------------------------------
    def test_lone_inactive_body_is_the_target(self):
        self.active_body = None                    # FreeCAD activates a lone body by itself
        outside = self.sketch("Sketch", body=False)
        self.assertEqual(self.gesture._target_body(self.doc), self.body)
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), True,
                      "a sketch outside the only body is no profile for it")
        self.forget()
        del STUBS.run_calls[:]
        self.doc.Objects.remove(outside)
        self.sketch("Sketch001")
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False, "the free sketch in the lone body is used")
        self.assertEqual(STUBS.run_calls, [])
        self.body.Group[:] = []                     # no free sketch left
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), False, "nothing to cut yet: FreeCAD refuses")
        self.give_solid()
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), True, "the lone body's solid can be cut")
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])

    def test_no_target_body_with_several_bodies(self):
        other = self.new_body("Body001")
        self.active_body = None
        self.assertIsNone(self.gesture._target_body(self.doc))
        self.sketch("Sketch", body=other)
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False, "without a target body every free sketch counts")

    def test_sketches_after_the_insert_point_are_not_free(self):
        count = self.gesture._free_sketch_count
        pad_sketch = self.sketch("Sketch", used=True)
        pad = self.feature("Pad")
        later = self.sketch("Sketch001")            # free, right after the Pad
        pocket = self.feature("Pocket", "PartDesign::Pocket")
        last = self.sketch("Sketch002")             # free, after the Pocket
        self.assertEqual([o.Name for o in self.body.Group], ["Sketch", "Pad", "Sketch001", "Pocket", "Sketch002"])
        cases = [
            ("tip at the end", pocket, {"Sketch001", "Sketch002"}),
            ("rolled back to the Pad", pad, {"Sketch001"}),
            ("rolled back to the first sketch", pad_sketch, set()),
            ("no tip", None, {"Sketch001", "Sketch002"}),
        ]
        for label, tip, free in cases:
            with self.subTest(label):
                self.body.Tip = tip
                hidden = self.gesture._after_insert_point(self.body)
                self.assertEqual({o.Name for o in (later, last)} - hidden, free)
                self.assertEqual(count(self.doc, self.body), len(free))

    def test_datum_after_the_tip_does_not_move_the_insert_point(self):
        self.sketch("Sketch", used=True)
        pad = self.feature("Pad")
        self.body.Group.append(FakeObject(self.doc, "DatumPlane", "PartDesign::Plane"))
        self.sketch("Sketch001")
        self.body.Tip = pad
        self.assertEqual(self.gesture._after_insert_point(self.body), set(), "only a solid feature hides what follows")
        self.assertEqual(self.gesture._free_sketch_count(self.doc, self.body), 1)

    def test_rolled_back_body_starts_a_sketch_when_only_later_sketches_are_free(self):
        self.sketch("Sketch", used=True)
        pad = self.feature("Pad")
        self.feature("Pocket", "PartDesign::Pocket")
        self.sketch("Sketch001")                    # free, but after the Pocket
        self.body.Tip = pad
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), True)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])
        self.forget()
        del STUBS.run_calls[:]
        self.body.Tip = self.body.Group[-1]
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False, "at the end of the body the sketch is free")

    def test_nothing_happens_without_a_document_or_with_a_dialog_open(self):
        STUBS.set_active_dialog("another task")
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False)
        STUBS.set_active_dialog(None)
        STUBS.gui.ActiveDocument = None
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False)
        self.assertEqual(STUBS.run_calls, [])
        self.assertIsNone(self.gesture._intent)

    def test_failing_new_sketch_command_leaves_no_state(self):
        STUBS.run_errors["PartDesign_NewSketch"] = RuntimeError("command refused by the harness")
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), False)
        self.assertIsNone(self.gesture._intent)
        self.assertEqual(self.status(), "")
        errors = self.jj("error")
        self.assertEqual(len(errors), 1, self.lines())
        self.assertIn("PartDesign_NewSketch", errors[0])

    # following the sketch ----------------------------------------------------------------
    def test_feature_starts_when_the_new_sketch_is_exited(self):
        self.fast()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.set_active_dialog("plane picker")
        STUBS.pump(60)
        self.assertEqual(self.state(), self.gesture.PICKING)
        new = self.sketch("Sketch", geometry=0)   # a plane was picked: FreeCAD opens the new sketch
        STUBS.set_active_dialog("sketch task")
        self.editing = new
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000), self.gesture._intent)
        self.assertEqual(self.gesture._intent["sketch"], "Sketch")
        new.Geometry = [object()] * 4
        self.editing = None                        # Exit Sketch; its task dialog closes a moment later
        STUBS.pump(40)
        self.assertEqual(self.state(), self.gesture.EDITING)
        self.assertEqual(self.feature_runs(), [])
        STUBS.set_active_dialog(None)
        self.assertTrue(STUBS.wait_until(lambda: self.feature_runs(), 1000), STUBS.run_calls)
        self.assertEqual(self.feature_runs(), ["PartDesign_Pad"])
        self.assertIsNone(self.gesture._intent)
        self.assertIn(("addSelection", (new,)), STUBS.selection_calls)
        self.assertEqual(STUBS.selection, [new])
        self.assertEqual(self.status(), "")
        STUBS.pump(60)
        self.assertEqual(self.feature_runs(), ["PartDesign_Pad"], "the feature starts once")
        self.assertNoJellyJamsProblems()

    def test_press_while_picking_retargets(self):
        self.fast()
        self.give_solid()                           # Pocket has something to cut
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.set_active_dialog("plane picker")
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), True)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)], "no second sketch is started")
        self.assertEqual(self.gesture._intent["cmd"], "PartDesign_Pocket")
        self.assertEqual(self.state(), self.gesture.PICKING)
        new = self.sketch("Sketch")
        self.editing = new
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000))
        self.editing = None
        STUBS.set_active_dialog(None)
        self.assertTrue(STUBS.wait_until(lambda: self.feature_runs(), 1000))
        self.assertEqual(self.feature_runs(), ["PartDesign_Pocket"])

    # presses while a sketch-first waits for its plane -------------------------------------
    def test_retarget_rewrites_the_status_hint(self):
        self.give_solid()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        self.assertIn("New sketch for Pad", self.status())
        STUBS.set_active_dialog("plane picker")
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), True)
        self.assertIn("New sketch for Pocket", self.status())
        self.assertNotIn("Pad", self.status())
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])

    def test_retarget_to_a_cutting_feature_needs_a_solid(self):
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))   # an empty body: Pad starts a sketch
        STUBS.set_active_dialog("plane picker")
        intent = self.gesture._intent
        before = dict(intent)
        hint = self.status()
        for cmd in self.gesture.SUBTRACTIVE_FEATURES:
            with self.subTest(cmd=cmd):
                STUBS.records.clear()
                STUBS.main_window.statusBar().showMessage(hint)
                refused = self.gesture.try_run(cmd)
                self.assertIs(self.gesture._intent, intent)
                self.assertEqual(self.gesture._intent, before, "the waiting Pad is kept as it was")
                self.assertEqual(STUBS.active_dialog, "plane picker", "FreeCAD's plane picker stays open")
                self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)], "nothing else runs")
                # Passed on, FreeCAD's Hole would close the open plane picker: JellyJams refuses it.
                # Pocket and Groove go to FreeCAD, which refuses them; the sketch hint stays.
                self.assert_refused(cmd, refused, status=hint)
        self.assertIs(self.gesture.try_run("PartDesign_Revolution"), True, "additive features still retarget")
        self.assertEqual(self.gesture._intent["cmd"], "PartDesign_Revolution")
        self.give_solid()
        for cmd in self.gesture.SUBTRACTIVE_FEATURES:
            with self.subTest(cmd=cmd, solid=True):
                self.assertIs(self.gesture.try_run(cmd), True)
                self.assertIs(self.gesture._intent, intent, "the same sketch-first, retargeted")
                self.assertEqual((self.gesture._intent["cmd"], self.state()), (cmd, self.gesture.PICKING))
                self.assertIn("New sketch for %s" % cmd.split("_", 1)[1], self.status())
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)], "no second sketch is started")
        self.assertEqual(self.jj("error"), [])

    def test_hole_refusal_while_picking_keeps_the_sketch_first_going(self):
        self.fast()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.set_active_dialog("plane picker")
        self.assertIs(self.gesture.try_run("PartDesign_Hole"), True)
        self.assertEqual(self.status(), self.hole_refusal())
        self.assertEqual(self.gesture._intent["cmd"], "PartDesign_Pad", "the waiting Pad is not replaced")
        new = self.sketch("Sketch")                 # the user picks a plane after all
        self.editing = new
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000), self.gesture._intent)
        self.editing = None
        STUBS.set_active_dialog(None)
        self.assertTrue(STUBS.wait_until(lambda: self.feature_runs(), 1000), STUBS.run_calls)
        self.assertEqual(self.feature_runs(), ["PartDesign_Pad"])

    def test_stale_watch_chain_stops_once_its_intent_is_replaced(self):
        fcgui = self.module("jellyjams.fcgui")
        queued = []
        self.patch(fcgui, "defer", lambda fn, ms=0: queued.append(fn))   # run the checks by hand
        polled = []
        real_advance = self.gesture.advance
        self.patch(self.gesture, "advance", lambda intent, *args: polled.append(intent) or real_advance(intent, *args))
        self.patch(self.gesture, "PICK_GRACE_S", 60.0)

        def turn():
            """One event-loop turn: every queued check runs once."""
            pending = queued[:]
            del queued[:]
            del polled[:]
            for fn in pending:
                fn()

        def replace(cmd, checks_before):
            """Press `cmd` once the picker is gone (a fresh sketch-first replaces the waiting one)
            after `checks_before` turns, then follow both chains for a few turns."""
            old = self.gesture._intent
            for _turn in range(checks_before):
                turn()
                self.assertEqual((len(polled), len(queued)), (1, 1), "one chain of checks")
            STUBS.set_active_dialog(None)
            self.assertTrue(self.gesture.try_run(cmd))
            new = self.gesture._intent
            self.assertIsNot(new, old)
            self.assertEqual(len(queued), 2, "the old chain's next check is still queued")
            STUBS.set_active_dialog("plane picker")
            for _turn in range(4):
                turn()
                self.assertEqual(len(polled), 1, "only the new sketch-first is checked")
                self.assertIs(polled[0], new)
                self.assertEqual(len(queued), 1, "the old chain stopped")
            self.assertIs(self.gesture._intent, new)

        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        replace("PartDesign_Revolution", 0)         # before the first check ran
        replace("PartDesign_Pad", 2)                # after a few checks

    def test_only_sketch_first_features_retarget_while_the_picker_is_open(self):
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.set_active_dialog("plane picker")
        before = dict(self.gesture._intent)
        hint = self.status()
        for cmd in sorted(set(PROFILE_FEATURES) - set(SKETCH_FIRST_FEATURES)):
            with self.subTest(cmd=cmd):
                self.assertIs(self.gesture.try_run(cmd), False, "FreeCAD handles it (and refuses, a dialog is open)")
                self.assertEqual(self.gesture._intent, before, "the waiting sketch-first is kept as it was")
                self.assertEqual(self.status(), hint)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)])

    def test_stale_plane_pick_is_dropped_and_the_press_handled_fresh(self):
        self.fast(grace=60.0)                       # the watcher alone would keep waiting
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        first = self.gesture._intent
        STUBS.set_active_dialog(None)               # the picker is gone (cancelled, or never opened)
        self.assertIs(self.gesture.try_run("PartDesign_Revolution"), True)
        self.assertEqual(STUBS.run_calls, [("PartDesign_NewSketch", None)] * 2, "a fresh sketch-first starts")
        self.assertIsNot(self.gesture._intent, first)
        self.assertEqual((self.gesture._intent["cmd"], self.state()), ("PartDesign_Revolution", self.gesture.PICKING))
        self.assertIn("New sketch for Revolution", self.status())
        STUBS.pump(40)
        self.assertEqual((self.gesture._intent["cmd"], self.state()), ("PartDesign_Revolution", self.gesture.PICKING),
                         "still waiting for the plane of the new sketch")

    def test_stale_plane_pick_is_dropped_when_the_fresh_press_needs_no_sketch(self):
        self.fast(grace=60.0)
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        self.assertNotEqual(self.status(), "")
        for cmd in ("PartDesign_AdditivePipe", "PartDesign_Pocket"):   # not sketch first / nothing to cut
            with self.subTest(cmd=cmd):
                self.assertIs(self.gesture.try_run(cmd), False)
                self.assertIsNone(self.gesture._intent, "the stale sketch-first is gone")
                self.assertEqual(self.status(), "", "its status hint is cleared")
                self.assertTrue(self.gesture.try_run("PartDesign_Pad"))   # waiting again for the next case
        self.assertEqual(self.feature_runs(), [])

    def test_status_hint_cleared_when_a_check_fails(self):
        self.fast()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        self.assertNotEqual(self.status(), "")

        def broken(*_args):
            raise RuntimeError("advance broken by the harness")

        self.patch(self.gesture, "advance", broken)
        self.assertTrue(STUBS.wait_until(lambda: self.gesture._intent is None, 1000))
        self.assertEqual(self.status(), "")
        logs = [line for line in self.jj("log") if "stopped" in line]
        self.assertEqual(len(logs), 1, self.lines())
        self.assertIn("advance broken by the harness", logs[0])
        self.assertNoJellyJamsProblems()

    def test_status_hint_cleared_when_a_press_inside_a_sketch_replaces_it(self):
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        self.assertNotEqual(self.status(), "")
        self.editing = self.sketch("Sketch")
        self.assertIs(self.gesture.try_run("PartDesign_Pad"), True)
        self.assertIsNone(self.gesture._intent)
        self.assertEqual(self.status(), "")
        self.editing = None                         # let the queued feature start inside this test
        self.assertTrue(STUBS.wait_until(lambda: self.feature_runs(), 1500))
        self.assertEqual(self.feature_runs(), ["PartDesign_Pad"])

    def test_cancelled_plane_pick_is_dropped_after_the_grace(self):
        self.fast(grace=0.5)
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        STUBS.pump(60)
        self.assertEqual(self.state(), self.gesture.PICKING, "FreeCAD gets time to open its picker")
        STUBS.set_active_dialog("plane picker")
        STUBS.pump(600)
        self.assertEqual(self.state(), self.gesture.PICKING, "an open picker is waited for")
        STUBS.set_active_dialog(None)              # Cancel
        self.assertTrue(STUBS.wait_until(lambda: self.gesture._intent is None, 1500))
        STUBS.pump(30)
        self.assertEqual(self.feature_runs(), [])
        self.assertEqual(self.status(), "")
        self.assertNoJellyJamsProblems()

    def test_editing_another_sketch_drops_it(self):
        self.fast()
        old = self.sketch("Sketch", used=True)
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        new = self.sketch("Sketch001")
        self.editing = new
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000))
        self.editing = old
        self.assertTrue(STUBS.wait_until(lambda: self.gesture._intent is None, 1000))
        self.editing = None
        STUBS.pump(40)
        self.assertEqual(self.feature_runs(), [])

    def test_empty_new_sketch_starts_nothing(self):
        self.fast()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        self.editing = self.sketch("Sketch", geometry=0)
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000))
        self.editing = None
        self.assertTrue(STUBS.wait_until(lambda: self.gesture._intent is None, 1000))
        STUBS.pump(30)
        self.assertEqual(self.feature_runs(), [])
        self.assertNoJellyJamsProblems()

    def test_leaving_jellyjams_or_closing_the_document_cancels(self):
        for what in ("workbench", "document"):
            with self.subTest(what):
                self.fast()
                self.forget()
                STUBS.set_active_workbench(WB)
                self.open_documents(self.doc)
                STUBS.records.clear()
                self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
                if what == "workbench":
                    STUBS.set_active_workbench("PartDesignWorkbench")
                else:
                    self.open_documents()
                self.assertTrue(STUBS.wait_until(lambda: self.gesture._intent is None, 1000))
                logs = [line for line in self.jj("log") if "cancelled" in line]
                self.assertEqual(len(logs), 1, self.lines())
                self.assertIn("PartDesignWorkbench" if what == "workbench" else "document closed", logs[0])
                self.assertEqual(self.feature_runs(), [])

    def test_feature_press_inside_the_new_sketch_wins(self):
        self.fast()
        self.assertTrue(self.gesture.try_run("PartDesign_Pad"))
        new = self.sketch("Sketch")
        self.editing = new
        self.assertTrue(STUBS.wait_until(lambda: self.state() == self.gesture.EDITING, 1000))
        self.assertIs(self.gesture.try_run("PartDesign_Pocket"), True)
        self.assertIsNone(self.gesture._intent)
        self.assertIn(("Sketcher_LeaveSketch", None), STUBS.run_calls)
        self.editing = None
        self.assertTrue(STUBS.wait_until(lambda: self.feature_runs(), 1500))
        STUBS.pump(80)
        self.assertEqual(self.feature_runs(), ["PartDesign_Pocket"])


class Test23EditGuard(HarnessCase):
    """edit_guard: FreeCAD command strings asking for another workbench wait one event-loop
    turn and are dropped when they were part of opening a feature for editing."""

    def setUp(self):
        super().setUp()
        stub_activate = STUBS.gui.activateWorkbench
        self.addCleanup(setattr, STUBS.gui, "activateWorkbench", stub_activate)
        self.switches = []
        self.refused = set()

        def activate(name, *args, **kwargs):
            if name in self.refused:
                raise RuntimeError("workbench %s refused by the harness" % name)
            self.switches.append(name)
            STUBS.active_workbench = name
            return True

        STUBS.gui.activateWorkbench = activate
        self.freecad_activate = activate
        self.guard = self.module("jellyjams.edit_guard", fresh=True)
        STUBS.set_active_workbench(WB)
        self.editing = None
        STUBS.gui.ActiveDocument = types.SimpleNamespace(getInEdit=self.view_provider)
        self.guard.install()
        self.addCleanup(self.guard.uninstall)

    def view_provider(self):
        return None if self.editing is None else types.SimpleNamespace(Object=self.editing)

    def edit(self, name, doc="Part1"):
        self.editing = types.SimpleNamespace(Name=name, Document=types.SimpleNamespace(Name=doc))

    def run_code(self, text, filename="<string>", namespace=None):
        """Run `text` the way FreeCAD runs a command string (Gui::Command::doCommand)."""
        exec(compile(text, filename, "exec"), namespace or {"Gui": STUBS.gui})  # noqa: S102

    def test_install_wraps_once_and_uninstall_restores(self):
        self.assertEqual(self.guard.COMMAND_STRING_FILE, "<string>")
        wrapper = STUBS.gui.activateWorkbench
        self.assertIsNot(wrapper, self.freecad_activate)
        self.assertTrue(self.guard.is_installed())
        self.guard.install()
        self.assertIs(STUBS.gui.activateWorkbench, wrapper, "a second install does not wrap again")
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, self.freecad_activate)
        self.assertFalse(self.guard.is_installed())
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, self.freecad_activate)
        self.guard.install()
        self.assertTrue(self.guard.is_installed())
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, self.freecad_activate)
        self.assertNoJellyJamsProblems()

    def test_python_callers_pass_straight_through(self):
        self.assertIs(STUBS.gui.activateWorkbench("PartDesignWorkbench"), True)
        self.assertEqual(self.switches, ["PartDesignWorkbench"])
        STUBS.set_active_workbench(WB)
        self.edit("Pad")
        for filename in ("<console>", "<stdin>", "C:/path/to/Macros/Switch.FCMacro"):
            with self.subTest(filename=filename):
                del self.switches[:]
                STUBS.set_active_workbench(WB)
                self.run_code("Gui.activateWorkbench('SketcherWorkbench')", filename)
                self.assertEqual(self.switches, ["SketcherWorkbench"], "no waiting for Python code")

    def test_command_string_without_an_edit_switches_one_turn_later(self):
        self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
        self.assertEqual(self.switches, [], "held for one event-loop turn")
        self.assertEqual(STUBS.active_workbench, WB)
        self.assertTrue(STUBS.wait_until(lambda: self.switches, 500))
        self.assertEqual(self.switches, ["PartDesignWorkbench"])
        self.assertEqual(STUBS.active_workbench, "PartDesignWorkbench")
        self.assertNoJellyJamsProblems()

    def test_feature_edit_keeps_jellyjams(self):
        self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
        self.edit("Pad")                            # the view provider's setEdit goes on
        STUBS.pump(80)
        self.assertEqual(self.switches, [])
        self.assertEqual(STUBS.active_workbench, WB)
        logs = [line for line in self.jj("log") if "stayed in JellyJams" in line]
        self.assertEqual(len(logs), 1, self.lines())
        self.assertIn("Pad", logs[0])
        self.assertIn("PartDesignWorkbench", logs[0])
        self.assertNoJellyJamsProblems()

    def test_edit_that_was_already_open_does_not_hold_the_switch(self):
        self.edit("Sketch")
        self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
        self.assertTrue(STUBS.wait_until(lambda: self.switches, 500))
        self.assertEqual(self.switches, ["PartDesignWorkbench"])

    def test_edit_moving_to_another_object_keeps_jellyjams(self):
        for before, after in ((("Pad", "Part1"), ("Pocket", "Part1")), (("Pad", "Part1"), ("Pad", "Part2"))):
            with self.subTest(before=before, after=after):
                del self.switches[:]
                self.edit(*before)
                self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
                self.edit(*after)
                STUBS.pump(80)
                self.assertEqual(self.switches, [])
                self.assertEqual(STUBS.active_workbench, WB)

    def test_requests_that_are_never_held(self):
        self.run_code("Gui.activateWorkbench('%s')" % WB)
        self.assertEqual(self.switches, [WB], "asking for JellyJams itself passes through")
        del self.switches[:]
        STUBS.set_active_workbench("PartDesignWorkbench")
        self.run_code("Gui.activateWorkbench('SketcherWorkbench')")
        self.assertEqual(self.switches, ["SketcherWorkbench"], "JellyJams not active: nothing to guard")

    def test_held_request_is_dropped_when_the_workbench_changed_meanwhile(self):
        self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
        STUBS.gui.activateWorkbench("TechDrawWorkbench")
        STUBS.pump(80)
        self.assertEqual(self.switches, ["TechDrawWorkbench"])
        self.assertEqual(STUBS.active_workbench, "TechDrawWorkbench")

    def test_disarmed_wrapper_passes_through(self):
        wrapper = STUBS.gui.activateWorkbench
        self.guard.uninstall()
        self.run_code("act('PartDesignWorkbench')", namespace={"act": wrapper})
        self.assertEqual(self.switches, ["PartDesignWorkbench"], "a kept reference no longer holds anything")

    def test_failing_switch_after_the_wait_warns(self):
        self.refused.add("BrokenWorkbench")
        self.run_code("Gui.activateWorkbench('BrokenWorkbench')")
        STUBS.pump(80)
        self.assertEqual(self.switches, [])
        warnings = self.jj("warning")
        self.assertEqual(len(warnings), 1, self.lines())
        self.assertIn("BrokenWorkbench", warnings[0])
        self.assertEqual(self.jj("error"), [])

    # another add-on's wrapper on top of the guard -------------------------------------------
    def foreign_wrapper(self):
        """Wrap whatever FreeCADGui.activateWorkbench is now, the way another add-on would."""
        below = STUBS.gui.activateWorkbench
        calls = []

        def foreign(name, *args, **kwargs):
            calls.append(name)
            return below(name, *args, **kwargs)

        STUBS.gui.activateWorkbench = foreign
        return foreign, calls

    def test_reinstall_under_a_foreign_wrapper_only_rearms(self):
        foreign, calls = self.foreign_wrapper()
        self.guard.uninstall()                      # leave JellyJams: the guard is not on top
        self.assertIs(STUBS.gui.activateWorkbench, foreign, "the other add-on's wrapper is left in place")
        self.assertFalse(self.guard.is_installed())
        self.guard.install()                        # enter JellyJams again
        self.assertIs(STUBS.gui.activateWorkbench, foreign, "no second JellyJams wrapper on top")
        self.assertTrue(self.guard.is_installed())
        STUBS.gui.activateWorkbench("PartDesignWorkbench")
        self.assertEqual(calls, ["PartDesignWorkbench"], "the foreign wrapper runs once")
        self.assertEqual(self.switches, ["PartDesignWorkbench"], "FreeCAD's function runs once, no recursion")
        self.assertNoJellyJamsProblems()

    def test_switch_through_a_foreign_wrapper_does_not_recurse(self):
        foreign, calls = self.foreign_wrapper()
        for _cycle in range(3):                     # leave and enter JellyJams a few times
            self.guard.uninstall()
            self.guard.install()
        self.assertIs(STUBS.gui.activateWorkbench, foreign)
        self.run_code("Gui.activateWorkbench('SketcherWorkbench')")
        # The command string sits one frame above the other add-on's wrapper: it is still
        # recognized, so the request waits one event-loop turn (sketching 2.7).
        self.assertEqual(self.switches, [], "held for one event-loop turn")
        self.assertEqual(calls, ["SketcherWorkbench"])
        self.assertTrue(STUBS.wait_until(lambda: self.switches, 500))
        STUBS.pump(80)
        self.assertEqual(self.switches, ["SketcherWorkbench"], "FreeCAD's function runs once, no recursion")
        self.assertEqual(calls, ["SketcherWorkbench"], "the other wrapper is not called again")
        self.assertEqual(STUBS.active_workbench, "SketcherWorkbench")
        STUBS.set_active_workbench(WB)
        STUBS.gui.activateWorkbench(WB)
        self.assertEqual(self.switches[-1], WB)
        self.assertEqual(self.jj("error"), [])

    # command strings recognized above other add-ons' wrappers -----------------------------
    def wrapper_chain(self, count):
        """Stack `count` foreign wrappers on top of the guard; returns their call log."""
        calls = []
        for _index in range(count):
            _foreign, own = self.foreign_wrapper()
            calls.append(own)
        return calls

    def test_command_string_recognized_through_foreign_wrappers(self):
        self.assertEqual(self.guard.FRAME_SEARCH_DEPTH, 6)
        for count in (1, 2):
            with self.subTest(wrappers=count):
                STUBS.gui.activateWorkbench = self.freecad_activate
                guard = self.module("jellyjams.edit_guard", fresh=True)
                guard.install()
                self.addCleanup(guard.uninstall)
                self.wrapper_chain(count)
                del self.switches[:]
                self.editing = None
                STUBS.set_active_workbench(WB)
                self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
                self.edit("Pad")                    # the feature's edit opens meanwhile
                STUBS.pump(80)
                self.assertEqual(self.switches, [], "the feature edit keeps JellyJams")
                self.assertEqual(STUBS.active_workbench, WB)
                self.editing = None
                self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
                self.assertEqual(self.switches, [], "held for one event-loop turn")
                self.assertTrue(STUBS.wait_until(lambda: self.switches, 500))
                self.assertEqual(self.switches, ["PartDesignWorkbench"])
        self.assertNoJellyJamsProblems()

    def test_python_callers_through_foreign_wrappers_pass_straight_through(self):
        self.wrapper_chain(2)
        self.edit("Pad")
        STUBS.gui.activateWorkbench("PartDesignWorkbench")
        self.assertEqual(self.switches, ["PartDesignWorkbench"], "a call from Python code never waits")
        STUBS.set_active_workbench(WB)
        self.run_code("Gui.activateWorkbench('SketcherWorkbench')", "<console>")
        self.assertEqual(self.switches, ["PartDesignWorkbench", "SketcherWorkbench"])

    def test_command_string_beyond_the_search_depth_is_not_recognized(self):
        depth = self.guard.FRAME_SEARCH_DEPTH
        # The wrapper's caller is the first frame searched: with depth - 1 wrappers the command
        # string is the last frame searched, with depth wrappers it is one frame too far.
        for count, held in ((depth - 1, True), (depth, False)):
            with self.subTest(wrappers=count):
                STUBS.gui.activateWorkbench = self.freecad_activate
                guard = self.module("jellyjams.edit_guard", fresh=True)
                guard.install()
                self.addCleanup(guard.uninstall)
                calls = self.wrapper_chain(count)
                del self.switches[:]
                STUBS.set_active_workbench(WB)
                self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
                self.assertEqual(self.switches, [] if held else ["PartDesignWorkbench"])
                self.assertTrue(STUBS.wait_until(lambda: self.switches, 500))
                self.assertEqual(self.switches, ["PartDesignWorkbench"])
                self.assertEqual([len(own) for own in calls], [1] * count, "every wrapper ran once")

    def test_uninstall_leaves_a_foreign_wrapper_and_passes_through(self):
        foreign, calls = self.foreign_wrapper()
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, foreign)
        self.run_code("Gui.activateWorkbench('PartDesignWorkbench')")
        self.assertEqual(self.switches, ["PartDesignWorkbench"], "the disarmed guard holds nothing")
        self.assertEqual(calls, ["PartDesignWorkbench"])

    def test_guard_back_on_top_is_unwrapped_again(self):
        below = STUBS.gui.activateWorkbench
        foreign, _calls = self.foreign_wrapper()
        self.guard.uninstall()
        STUBS.gui.activateWorkbench = below         # the other add-on removes its wrapper
        self.guard.install()
        self.assertIs(STUBS.gui.activateWorkbench, below, "still the one JellyJams wrapper")
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, self.freecad_activate, "FreeCAD's own function is back")
        self.guard.install()
        self.assertIsNot(STUBS.gui.activateWorkbench, self.freecad_activate, "a later install wraps again")
        self.guard.uninstall()
        self.assertIs(STUBS.gui.activateWorkbench, self.freecad_activate)

    def test_install_without_activate_workbench(self):
        self.guard.uninstall()
        self.patch(STUBS.gui, "activateWorkbench", None)
        guard = self.module("jellyjams.edit_guard", fresh=True)
        guard.install()
        self.assertFalse(guard.is_installed())
        self.assertIsNone(STUBS.gui.activateWorkbench)
        guard.uninstall()
        self.assertEqual(self.lines(), [])


# ==========================================================================
# 24. Orientation panel (Space) and Normal To (Ctrl+8)
# ==========================================================================

# (row, column, FreeCAD command, label): the standard views unfolded around Front
EXPECTED_VIEW_GRID = (
    (0, 1, "Std_ViewTop", "Top"),
    (1, 0, "Std_ViewLeft", "Left"),
    (1, 1, "Std_ViewFront", "Front"),
    (1, 2, "Std_ViewRight", "Right"),
    (1, 3, "Std_ViewRear", "Back"),
    (2, 1, "Std_ViewBottom", "Bottom"),
)
EXPECTED_AXONOMETRIC = (("Std_ViewIsometric", "Isometric"), ("Std_ViewTrimetric", "Trimetric"),
                        ("Std_ViewDimetric", "Dimetric"))
EXPECTED_ORIENTATION_TOOLS = (
    ("JellyJams_NormalTo", "Normal To"),
    ("Std_ViewSaveCamera", "Remember this view"),
    ("Std_ViewRestoreCamera", "Go back to the remembered view"),
    ("Std_ViewFitAll", "Zoom to Fit"),
)
ORIENTATION_COMMANDS = ([cmd for cmd, _label in EXPECTED_ORIENTATION_TOOLS]
                        + [cmd for _row, _col, cmd, _label in EXPECTED_VIEW_GRID]
                        + [cmd for cmd, _label in EXPECTED_AXONOMETRIC])
ORIENTATION_BUTTON_PREFIX = "JellyJamsOrientation_"
SKETCH_VIEW_CMD = "Sketcher_ViewSketch"
NORMAL_TO_HINT = "Normal To: select one face, edge, plane or sketch first."
CLASS_VIEW3D = "Gui::View3DInventor"
# The Qt class of every 3D view's drawing area's parent, in a docked, undocked or split view
CLASS_VIEWER = "Gui::View3DInventorViewer"
# The Qt class of a split 3D view: SplitView3DInventor has no Q_OBJECT of its own
CLASS_SPLIT_VIEW3D = "Gui::AbstractSplitView"
MODEL_TREE_CLASS = "Gui::TreeWidget"
# Whole objects Normal To looks at itself, along the sketch plane: sketches and other 2D objects
SKETCH_TYPES = ("Part::Part2DObject",)
# Whole objects FreeCAD's Std_AlignToSelection aligns to by itself: origin planes and axes, datums
DATUM_TYPES = ("App::Plane", "App::Line", "Part::Datum")
# With the pointer over one of these, Space is always for the Orientation panel
SPACE_FOR_PANEL_CLASSES = (CLASS_VIEW3D, CLASS_VIEWER, CLASS_SPLIT_VIEW3D, MODEL_TREE_CLASS)
UNREADABLE = object()


def flat_face():
    return types.SimpleNamespace(ShapeType="Face", findPlane=lambda: object())


def curved_face():
    return types.SimpleNamespace(ShapeType="Face", findPlane=lambda: None)


def straight_edge():
    return types.SimpleNamespace(ShapeType="Edge", Curve=types.SimpleNamespace(TypeId="Part::GeomLine"))


def circular_edge():
    return types.SimpleNamespace(ShapeType="Edge", Curve=types.SimpleNamespace(TypeId="Part::GeomCircle"))


def bspline_edge():
    return types.SimpleNamespace(ShapeType="Edge", Curve=types.SimpleNamespace(TypeId="Part::GeomBSplineCurve"))


def vertex():
    return types.SimpleNamespace(ShapeType="Vertex")


def fake_shape(faces=0, edges=0, solids=0, null=False):
    """A whole object's Shape with that many faces, edges and solids."""
    return types.SimpleNamespace(isNull=lambda: null, Faces=[object()] * faces, Edges=[object()] * edges,
                                 Solids=[object()] * solids)


class FakePick:
    """One entry of Selection.getSelectionEx(): an object and the sub-elements picked on it, with
    their shapes in SubObjects (UNREADABLE: reading SubObjects raises)."""

    def __init__(self, doc, name, subs=(), shapes=(), type_id="Part::Box", obj=None):
        self.DocumentName = doc
        self.ObjectName = name
        self.SubElementNames = list(subs)
        self.Object = obj if obj is not None else FakeObject(None, name, type_id)
        self._shapes = shapes

    def __repr__(self):
        return "<FakePick %s.%s %s>" % (self.DocumentName, self.ObjectName, self.SubElementNames)

    @property
    def SubObjects(self):
        if self._shapes is UNREADABLE:
            raise RuntimeError("sub-shapes cannot be read (harness)")
        return tuple(self._shapes)


def fake_placement(q):
    """A placement whose rotation has the quaternion `q`."""
    return types.SimpleNamespace(Rotation=types.SimpleNamespace(Q=q))


def whole(name, type_id, doc="Part1", subs=(), placement_q=None, global_q=None, **values):
    """A pick of a whole object; with global_q the object reports that global rotation. Other
    keywords become attributes of the object (Shape, for example)."""
    if global_q is not None:
        values["getGlobalPlacement"] = lambda: fake_placement(global_q)
    if placement_q is not None:
        values["Placement"] = fake_placement(placement_q)
    obj = FakeObject(None, name, type_id, label=name + " label", **values)
    return FakePick(doc, name, subs, obj=obj)


FACE = FakePick("Part1", "Box", ["Face6"], [flat_face()])                  # one flat face
OTHER_FACE = FakePick("Part1", "Box001", ["Face2"], [flat_face()])         # a flat face of another object
CURVED_FACE = FakePick("Part1", "Cylinder", ["Face1"], [curved_face()])   # the side of a cylinder


class FakeView3D:
    """FreeCAD's 3D view as Normal To and view3d_active() use it."""

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def getCameraNode(self):
        return object()

    def setCameraOrientation(self, q, *args):
        self.calls.append(("setCameraOrientation", q) + args)
        if self.error is not None:
            raise self.error


def qt_class(name, base):
    """A subclass of `base` whose Qt class name is `name`, like FreeCAD's own C++ widgets."""
    return type(name, (base,), {})


def space_event(key=None, modifiers=None, event_type=None, auto_repeat=False):
    """A key event, by default the ShortcutOverride Qt sends for a plain Space before it runs the
    Space shortcut. It starts ignored, so isAccepted() later tells whether anything accepted it."""
    event = QtGui.QKeyEvent(event_type or QtCore.QEvent.Type.ShortcutOverride,
                            QtCore.Qt.Key.Key_Space if key is None else key,
                            QtCore.Qt.KeyboardModifier.NoModifier if modifiers is None else modifiers,
                            "", auto_repeat)
    event.ignore()
    return event


def focus_on(widget):
    """Show `widget` in its offscreen window and give it the keyboard focus; True when Qt
    reports it as the focus widget."""
    window = widget.window()
    window.show()
    widget.show()
    window.activateWindow()
    widget.setFocus()
    STUBS.pump(10)
    return QtWidgets.QApplication.focusWidget() is widget


def override_accepted(target, event):
    """Deliver a shortcut override to `target` the way Qt does (it travels up to the window);
    True when something accepted it, so that the widget gets the key instead of the shortcut."""
    QtWidgets.QApplication.sendEvent(target, event)
    return event.isAccepted()


def space_filters(window):
    """The orientation module's Space filters that are children of `window`."""
    return [child for child in window.children() if child.metaObject().className() == "SpaceFilter"]


def dark_pixels(widget):
    """Opaque, dark pixels of the widget's rendering (its text on a light background)."""
    image = widget.grab().toImage()
    count = 0
    for x in range(image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if color.alpha() == 255 and color.lightness() < 100:
                count += 1
    return count


class Test24Orientation(HarnessCase):
    """The Orientation panel that Space opens and Normal To (Ctrl+8): commands, layout, clicks,
    keys, the Space filter, colors and lifecycle."""

    def setUp(self):
        super().setUp()
        self.orientation = self.module("jellyjams.orientation", fresh=True)
        # The new main window takes the activation from an earlier test's panel, which queues that
        # panel's click-outside check; let it run now, while this test has no panel yet.
        STUBS.pump(30)
        self.addCleanup(self.orientation.uninstall)
        self.addCleanup(QtWidgets.QToolTip.hideText)   # Normal To's hint shows a real tool tip
        STUBS.set_commands(ORIENTATION_COMMANDS + [ORIENTATION_CMD, ALIGN_CMD, SKETCH_VIEW_CMD],
                           shortcuts={"Std_ViewTop": "Ctrl+5", "Std_ViewFitAll": "F", NORMAL_TO_CMD: "Ctrl+8"})
        self.editing = None
        STUBS.gui.ActiveDocument = types.SimpleNamespace(getInEdit=self.view_provider)

    def view_provider(self):
        return None if self.editing is None else types.SimpleNamespace(Object=self.editing)

    def edit(self, name="Sketch", type_id="Sketcher::SketchObject", doc="Part1"):
        """Put an object of `type_id` into edit (a sketch unless told otherwise)."""
        self.editing = types.SimpleNamespace(Name=name, TypeId=type_id, Document=types.SimpleNamespace(Name=doc))
        return self.editing

    def select(self, *picks):
        """Selection entries as getSelectionEx() gives them: FakePicks, or (document, object, subs)
        for picks whose shapes nobody reads."""
        STUBS.selection_ex[:] = [pick if isinstance(pick, FakePick) else FakePick(*pick) for pick in picks]

    def status(self):
        return STUBS.main_window.statusBar().currentMessage()

    def clock(self, now=100.0):
        """Stand in for time.monotonic() inside the orientation module; set .now to move it."""
        clock = types.SimpleNamespace(now=now)
        self.patch(self.orientation, "time", types.SimpleNamespace(monotonic=lambda: clock.now))
        return clock

    def queue_deferred(self):
        """Collect what fcgui.defer() would run later, so a test runs it by hand."""
        fcgui = self.module("jellyjams.fcgui")
        queued = []
        self.patch(fcgui, "defer", lambda fn, ms=0: queued.append(fn))
        return queued

    def point_at(self, widget):
        """Move the mouse pointer to the middle of `widget`; Qt then reports it under the pointer."""
        self.addCleanup(QtGui.QCursor.setPos, QtGui.QCursor.pos())
        QtGui.QCursor.setPos(widget.mapToGlobal(widget.rect().center()))
        STUBS.pump(10)
        under = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        self.assertTrue(under is not None and (under is widget or widget.isAncestorOf(under)), (under, widget))

    def show_window(self, class_name=None):
        """Make a window of Qt class `class_name` (a plain QWidget for None) the active MDI window."""
        mdi = STUBS.main_window.centralWidget()
        widget = qt_class(class_name, QtWidgets.QWidget)() if class_name else QtWidgets.QWidget()
        sub_window = mdi.addSubWindow(widget)
        sub_window.show()
        mdi.setActiveSubWindow(sub_window)
        STUBS.pump(10)
        return sub_window

    def other_window(self):
        """Another top-level window that takes the keyboard (a click outside FreeCAD's panel)."""
        other = QtWidgets.QWidget()
        other.resize(80, 60)
        self.addCleanup(other.close)
        other.show()
        other.activateWindow()
        STUBS.pump(50)
        self.assertTrue(other.isActiveWindow())
        return other

    def panel(self):
        return self.orientation._panel

    def buttons(self):
        return {button.objectName()[len(ORIENTATION_BUTTON_PREFIX):]: button
                for button in self.panel().findChildren(QtWidgets.QToolButton)
                if button.objectName().startswith(ORIENTATION_BUTTON_PREFIX)}

    def button_order(self, layout):
        """Command ids of the view buttons in the order they were laid out."""
        order = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None and widget.objectName().startswith(ORIENTATION_BUTTON_PREFIX):
                order.append(widget.objectName()[len(ORIENTATION_BUTTON_PREFIX):])
            elif item.layout() is not None:
                order.extend(self.button_order(item.layout()))
        return order

    def key(self, key, auto_repeat=False):
        event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key, QtCore.Qt.KeyboardModifier.NoModifier, "",
                                auto_repeat)
        QtWidgets.QApplication.sendEvent(self.panel(), event)

    def image(self, icon):
        return icon.pixmap(24, 24).toImage()

    def svg_image(self, name):
        return self.image(QtGui.QIcon(os.path.join(ICONS_DIR, name + ".svg")))

    # commands --------------------------------------------------------------------------------------
    def test_commands(self):
        commands = self.orientation.get_commands()
        self.assertEqual(list(commands), [ORIENTATION_CMD, NORMAL_TO_CMD])
        expected = {
            ORIENTATION_CMD: ("View Orientation", "orientation", ("Orientation panel", "Space")),
            NORMAL_TO_CMD: ("Normal To", "normal_to", ("face, edge, plane or sketch", "sketch plane", "Ctrl+8")),
        }
        for cmd_id, (menu_text, icon, words) in expected.items():
            with self.subTest(cmd=cmd_id):
                command = commands[cmd_id]
                self.assertEqual(command.command_id, cmd_id)
                resources = command.GetResources()
                self.assertEqual(resources["MenuText"], menu_text)
                for word in words:
                    self.assertIn(word, resources["ToolTip"])
                for words in ("flat face", "straight edge"):
                    self.assertNotIn(words, resources["ToolTip"], "FreeCAD decides which faces and edges work")
                self.assertNotIn("Accel", resources, "the key comes from the shortcut table, with exact restore")
                self.assertEqual(resources.get("CmdType"), "Alter3DView",
                                 "a camera-only command stays available in a sketch and in task dialogs")
                self.assertEqual(norm_path(resources["Pixmap"]), norm_path(os.path.join(ICONS_DIR, icon + ".svg")))
        self.assertEqual(self.orientation.OBJ_PANEL, "JellyJamsOrientation")
        self.assertEqual(self.orientation.CMD_TYPE_VIEW, "Alter3DView")

    def test_active_while_the_main_windows_active_window_is_a_3d_view(self):
        commands = list(self.orientation.get_commands().values())

        def states():
            return [command.IsActive() for command in commands]

        sheet_view = types.SimpleNamespace(getPage=lambda: None)              # a TechDraw page
        STUBS.set_active_view(FakeView3D())         # what FreeCADGui.activeView() says does not count
        cases = [
            ("no view at all", None, False),
            ("a drawing sheet", sheet_view, False),
            ("a spreadsheet or the start page", types.SimpleNamespace(), False),
            ("a 3D view", FakeView3D(), True),
            ("getActiveWindow() fails", RuntimeError("no active window (harness)"), False),
        ]
        for label, window, expected in cases:
            with self.subTest(label):
                STUBS.set_active_window(window)
                self.assertEqual(states(), [expected, expected])
                self.assertIs(self.orientation.view3d_active(), expected)
        self.assertEqual(self.lines(), [])

    def test_active_view_is_the_main_windows_active_window(self):
        """FreeCAD 1.1's main window has getActiveWindow() (MainWindow::activeWindow), the view in
        front; FreeCADGui.activeView() keeps answering with the document's 3D view while the
        Start page or a drawing is in front."""
        o = self.orientation
        behind = FakeView3D()
        STUBS.set_active_view(behind)
        start_page = types.SimpleNamespace(getWindowTitle=lambda: "Start")   # no camera
        STUBS.set_active_window(start_page)
        self.assertIs(o._active_view(), start_page)
        self.assertIs(o.view3d_active(), False, "the Start page in front: no Space, no Ctrl+8")
        in_front = FakeView3D()
        STUBS.set_active_window(in_front)
        self.assertIs(o._active_view(), in_front, "an undocked or fullscreen 3D view in front")
        self.assertIs(o.view3d_active(), True)
        STUBS.set_active_window(None)
        self.assertIsNone(o._active_view(), "no window in front: activeView() is not asked")
        self.assertIs(o.view3d_active(), False)
        self.assertEqual(self.lines(), [])

    def test_active_view_falls_back_to_freecads_active_view(self):
        plain = QtWidgets.QMainWindow()             # a main window without getActiveWindow()
        self.addCleanup(plain.deleteLater)
        self.assertFalse(hasattr(plain, "getActiveWindow"))
        self.patch(STUBS, "main_window", plain)
        o = self.orientation
        view3d = FakeView3D()
        STUBS.set_active_view(view3d)
        STUBS.set_active_window(types.SimpleNamespace())   # never asked
        self.assertIs(o._active_view(), view3d)
        self.assertIs(o.view3d_active(), True)
        STUBS.set_active_view(types.SimpleNamespace(getPage=lambda: None))
        self.assertIs(o.view3d_active(), False, "a drawing sheet")
        STUBS.set_active_view(RuntimeError("no active view (harness)"))
        self.assertIsNone(o._active_view())
        self.assertIs(o.view3d_active(), False)
        self.assertEqual(self.lines(), [])

    def test_active_view_is_none_on_errors(self):
        o = self.orientation
        STUBS.set_active_view(FakeView3D())
        STUBS.set_active_window(RuntimeError("getActiveWindow broken (harness)"))
        self.assertIsNone(o._active_view(), "a failing getActiveWindow() is no 3D view")
        self.assertIs(o.view3d_active(), False)
        self.patch(STUBS, "main_window", None)
        STUBS.set_active_view(RuntimeError("no active view (harness)"))
        self.assertIsNone(o._active_view(), "no main window and a failing activeView()")
        fcgui = self.module("jellyjams.fcgui")
        self.patch(fcgui, "gui", lambda: None)
        self.assertIsNone(o._active_view(), "without FreeCADGui")
        self.assertIs(o.view3d_active(), False)
        self.assertEqual(self.lines(), [])

    def test_the_mdi_area_does_not_decide_availability(self):
        """The main window's active window follows a 3D view that is undocked, fullscreen or split,
        though it then leaves the MDI area; and a 3D view widget in the MDI area alone is no active
        view."""
        view3d = FakeView3D()
        self.show_window(CLASS_VIEW3D)
        STUBS.set_active_window(None)
        self.assertIs(self.orientation.view3d_active(), False, "a 3D view in the MDI area that FreeCAD does not report")
        self.show_window("TechDrawGui::MDIViewPage")
        STUBS.set_active_window(view3d)
        self.assertIs(self.orientation.view3d_active(), True, "undocked or fullscreen: the MDI area shows a sheet")
        self.patch(STUBS.main_window.centralWidget(), "activeSubWindow", lambda: None)
        self.patch(STUBS.main_window.centralWidget(), "currentSubWindow", lambda: None)
        self.assertIs(self.orientation.view3d_active(), True, "no MDI window at all")
        self.edit()
        STUBS.set_active_dialog("sketch task dialog")
        self.assertIs(self.orientation.view3d_active(), True, "also while a sketch is open")
        self.other_window()                         # the panel itself, or any other window, has the keyboard
        self.assertIs(self.orientation.view3d_active(), True, "the 3D view is still the view the user works in")
        fcgui = self.module("jellyjams.fcgui")
        self.patch(fcgui, "gui", lambda: None)
        self.assertIs(self.orientation.view3d_active(), False, "without FreeCADGui")

    def test_command_toggles_the_panel(self):
        command = self.orientation.get_commands()[ORIENTATION_CMD]
        self.assertFalse(self.orientation.is_open())
        command.Activated()
        self.assertTrue(self.orientation.is_open())
        panel = self.panel()
        self.assertEqual(panel.objectName(), "JellyJamsOrientation")
        self.assertTrue(panel.isWindow())
        self.assertEqual(panel.windowType(), QtCore.Qt.WindowType.Tool, "a small tool window over FreeCAD")
        self.assertTrue(panel.windowFlags() & QtCore.Qt.WindowType.FramelessWindowHint)
        self.assertIs(panel.parent(), STUBS.main_window)
        command.Activated()
        self.assertFalse(self.orientation.is_open(), "Space again closes it")
        self.orientation.toggle()
        self.assertIs(self.panel(), panel, "the panel is built once and reused")
        self.assertTrue(self.orientation.is_open())
        self.assertNoJellyJamsProblems()

    # Normal To --------------------------------------------------------------------------------------
    def test_normal_to_target(self):
        o = self.orientation
        self.assertEqual((o.ALIGN_COMMAND, o.SKETCH_VIEW_COMMAND), (ALIGN_CMD, SKETCH_VIEW_CMD))
        align, sketch_view, sketch_plane = ("command", ALIGN_CMD), ("command", SKETCH_VIEW_CMD), "sketch"
        sketch = ("Sketch", "Sketcher::SketchObject")
        cases = [
            # label, object in edit (name, type) or None, selection, target ("sketch": the first pick's object)
            ("nothing selected", None, [], None),
            # one sub-element, whatever it is: FreeCAD's Align to Selection decides
            ("one flat face", None, [FACE], align),
            ("one curved face", None, [CURVED_FACE], align),
            ("one straight edge", None, [FakePick("Part1", "Box", ["Edge3"], [straight_edge()])], align),
            ("one circular edge", None, [FakePick("Part1", "Cylinder", ["Edge1"], [circular_edge()])], align),
            ("one B-spline edge", None, [FakePick("Part1", "Sweep", ["Edge4"], [bspline_edge()])], align),
            ("one vertex", None, [FakePick("Part1", "Box", ["Vertex2"], [vertex()])], align),
            ("one edge of a sketch that is not open", None,
             [FakePick("Part1", "Sketch001", ["Edge2"], [straight_edge()], type_id="Sketcher::SketchObject")], align),
            ("sub-shapes cannot be read: never read", None, [FakePick("Part1", "Box", ["Face1"], UNREADABLE)], align),
            ("sub-shapes missing", None, [FakePick("Part1", "Box", ["Face1"], [])], align),
            # two picks or more
            ("two flat faces of one object", None,
             [FakePick("Part1", "Box", ["Face1", "Face6"], [flat_face(), flat_face()])], None),
            ("flat faces of two objects", None, [FACE, OTHER_FACE], None),
            ("a flat face and a straight edge", None,
             [FakePick("Part1", "Box", ["Face6", "Edge3"], [flat_face(), straight_edge()])], None),
            ("a flat face and a whole object", None, [FACE, whole("Box001", "Part::Box")], None),
            ("two sketches", None, [whole("Sketch001", "Sketcher::SketchObject"),
                                    whole("Sketch002", "Sketcher::SketchObject")], None),
            ("a sketch and a face", None, [whole("Sketch001", "Sketcher::SketchObject"), FACE], None),
            ("two origin planes", None, [whole("XY_Plane", "App::Plane"), whole("XZ_Plane", "App::Plane")], None),
            # whole objects
            ("a whole sketch", None, [whole("Sketch001", "Sketcher::SketchObject")], sketch_plane),
            ("another 2D object", None, [whole("ShapeString", "Part::Part2DObjectPython")], sketch_plane),
            ("an origin plane", None, [whole("XY_Plane", "App::Plane")], align),
            ("an origin axis", None, [whole("X_Axis", "App::Line")], align),
            ("a datum plane", None, [whole("DatumPlane", "PartDesign::Plane", subs=[""])], align),
            ("a datum line", None, [whole("DatumLine", "PartDesign::Line")], align),
            ("a datum point: FreeCAD decides", None, [whole("DatumPoint", "PartDesign::Point")], align),
            ("an origin point", None, [whole("Origin_Point", "App::Point")], None),
            ("a single-face object", None, [whole("Plane", "Part::Plane", Shape=fake_shape(faces=1, edges=4))],
             align),
            ("a single-edge object", None, [whole("Circle", "Part::Circle", Shape=fake_shape(edges=1))], align),
            ("a two-face shell", None, [whole("Shell", "Part::Feature", Shape=fake_shape(faces=2, edges=7))], None),
            ("a wire of two edges", None, [whole("Wire", "Part::Feature", Shape=fake_shape(edges=2))], None),
            ("a sphere: one face, but a solid", None,
             [whole("Sphere", "Part::Feature", Shape=fake_shape(faces=1, edges=3, solids=1))], None),
            ("a null shape", None, [whole("Empty", "Part::Feature", Shape=fake_shape(null=True))], None),
            ("a whole body", None, [whole("Body", "PartDesign::Body", Shape=fake_shape(faces=6, edges=12,
                                                                                    solids=1))], None),
            ("a whole feature", None, [whole("Pad", "PartDesign::Pad", Shape=fake_shape(faces=6, edges=12,
                                                                                    solids=1))], None),
            ("a whole box", None, [whole("Box", "Part::Box", Shape=fake_shape(faces=6, edges=12, solids=1))], None),
            ("a whole cylinder", None, [whole("Cylinder", "Part::Cylinder", Shape=fake_shape(faces=3, edges=3,
                                                                                         solids=1))], None),
            ("an object without a shape", None, [whole("Group", "App::DocumentObjectGroup")], None),
            # in edit
            ("a feature in edit, nothing selected", ("Pad", "PartDesign::Pad"), [], None),
            ("a feature in edit, a flat face", ("Pad", "PartDesign::Pad"), [FACE], align),
            ("sketch open, nothing selected", sketch, [], sketch_view),
            ("sketch open, its own edges", sketch,
             [FakePick("Part1", "Sketch", ["Edge1", "Edge3"], [circular_edge(), circular_edge()])], sketch_view),
            ("sketch open, the sketch itself", sketch, [whole("Sketch", "Sketcher::SketchObject")], sketch_view),
            ("sketch open, another object's flat face", sketch, [FACE], align),
            ("sketch open, another object's curved face", sketch, [CURVED_FACE], align),
            ("sketch open, its edge and another face", sketch,
             [FakePick("Part1", "Sketch", ["Edge1"], [straight_edge()]), FACE], None),
            ("sketch open, a sketch of that name in another document", sketch,
             [FakePick("Part2", "Sketch", ["Edge1"], [straight_edge()])], align),
            ("sketch open, another whole sketch", sketch, [whole("Sketch001", "Sketcher::SketchObject")],
             sketch_plane),
            ("sketch open, an origin plane", sketch, [whole("XY_Plane", "App::Plane")], align),
        ]
        for label, editing, picks, expected in cases:
            with self.subTest(label):
                self.editing = None
                if editing is not None:
                    self.edit(*editing)
                self.select(*picks)
                target = o.normal_to_target()
                if expected == sketch_plane:
                    self.assertEqual(target, ("sketch", picks[0].Object))
                    self.assertIs(target[1], picks[0].Object)
                else:
                    self.assertEqual(target, expected)
        self.assertEqual(STUBS.run_calls, [], "deciding runs nothing")
        self.assertEqual(self.lines(), [])

    def test_whole_object_types(self):
        o = self.orientation
        self.assertEqual(tuple(o.SKETCH_TYPES), SKETCH_TYPES)
        self.assertEqual(tuple(o.DATUM_TYPES), DATUM_TYPES)
        target = o.normal_to_target
        for type_id in ("Sketcher::SketchObject", "Part::Part2DObjectPython"):
            with self.subTest(type_id):
                pick = whole("Flat", type_id)
                self.select(pick)
                self.assertEqual(target(), ("sketch", pick.Object))
        for type_id in ("App::Plane", "App::Line", "PartDesign::Plane", "PartDesign::Line", "PartDesign::Point"):
            with self.subTest(type_id):
                self.select(whole("Datum", type_id))
                self.assertEqual(target(), ("command", ALIGN_CMD), "FreeCAD aligns to it, through links too")
        for type_id in ("App::Origin", "App::Part", "App::Point", "PartDesign::Body", "PartDesign::Pad",
                        "Part::Feature", "App::DocumentObjectGroup", "App::Link"):
            with self.subTest(type_id):
                self.select(whole("Other", type_id))
                self.assertIsNone(target(), "no shape of one face or one edge")
        broken = whole("Broken", "Part::Box")
        broken.Object.__dict__["isDerivedFrom"] = lambda _type_id: 1 / 0
        self.select(broken)
        self.assertIsNone(target(), "an object that cannot say its type and has no shape is not looked at")
        broken_shape = whole("BrokenShape", "Part::Feature")
        broken_shape.Object.__dict__["Shape"] = types.SimpleNamespace(isNull=lambda: 1 / 0)
        self.select(broken_shape)
        self.assertIsNone(target(), "a shape that cannot be read")
        self.assertEqual(self.lines(), [])

    def test_normal_to_runs_its_target_or_shows_the_hint(self):
        command = self.orientation.get_commands()[NORMAL_TO_CMD]
        STUBS.set_active_view(FakeView3D())
        cases = [
            ("nothing to look at", False, [], None),
            ("a flat face", False, [FACE], ALIGN_CMD),
            ("a curved face", False, [CURVED_FACE], ALIGN_CMD),
            ("a vertex", False, [FakePick("Part1", "Box", ["Vertex2"], [vertex()])], ALIGN_CMD),
            ("an origin plane", False, [whole("XY_Plane", "App::Plane")], ALIGN_CMD),
            ("two flat faces", False, [FACE, OTHER_FACE], None),
            ("a whole body", False, [whole("Body", "PartDesign::Body", Shape=fake_shape(faces=6, solids=1))], None),
            ("sketch open", True, [], SKETCH_VIEW_CMD),
            ("sketch open, another face", True, [FACE], ALIGN_CMD),
            ("sketch open, two faces", True, [FACE, OTHER_FACE], None),
        ]
        for label, sketch, picks, target in cases:
            with self.subTest(label):
                del STUBS.run_calls[:]
                STUBS.main_window.statusBar().clearMessage()
                self.editing = None
                if sketch:
                    self.edit()
                self.select(*picks)
                command.Activated()
                if target is None:
                    self.assertEqual(STUBS.run_calls, [], "Std_AlignToSelection would do nothing at all")
                    self.assertEqual(self.status(), NORMAL_TO_HINT)
                    self.assertIs(self.orientation.normal_to(), False)
                else:
                    self.assertEqual(STUBS.run_calls, [(target, None)])
                    self.assertEqual(self.status(), "")
        self.assertEqual(STUBS.active_view.calls, [], "the camera is only turned for whole sketches")
        self.assertNoJellyJamsProblems()

    def test_normal_to_looks_straight_at_a_whole_sketch(self):
        command = self.orientation.get_commands()[NORMAL_TO_CMD]
        q = (0.0, 0.0, 0.7071067811865476, 0.7071067811865476)
        cases = [
            ("a whole sketch", whole("Sketch001", "Sketcher::SketchObject", global_q=q, placement_q=(0, 0, 0, 1))),
            ("another 2D object", whole("ShapeString", "Part::Part2DObjectPython", global_q=q)),
        ]
        for label, pick in cases:
            with self.subTest(label):
                view = FakeView3D()
                STUBS.set_active_view(view)
                del STUBS.run_calls[:]
                self.select(pick)
                self.assertIs(self.orientation.normal_to(), True)
                self.assertEqual(view.calls, [("setCameraOrientation", q)],
                                 "along the global placement (inside a moved body or part too)")
                command.Activated()
                self.assertEqual(len(view.calls), 2)
                self.assertEqual(STUBS.run_calls, [], "no FreeCAD command is needed")
                self.assertEqual(self.status(), "")
        self.assertNoJellyJamsProblems()

    def test_look_at_sketch_turns_the_main_windows_active_window(self):
        q = (0.5, 0.5, 0.5, 0.5)
        behind, in_front = FakeView3D(), FakeView3D()
        STUBS.set_active_view(behind)               # FreeCADGui.activeView(): the document's last 3D view
        STUBS.set_active_window(in_front)           # an undocked or fullscreen 3D view in front
        sketch = whole("Sketch001", "Sketcher::SketchObject", global_q=q)
        self.select(sketch)
        self.assertIs(self.orientation._look_at_sketch(sketch.Object), True)
        self.assertEqual(in_front.calls, [("setCameraOrientation", q)])
        self.assertEqual(behind.calls, [], "the view the user does not see is left alone")
        self.assertNoJellyJamsProblems()

    def test_sketch_rotation_follows_the_selection_path(self):
        """A sketch reached through a link (or an assembly component) is looked at where it is shown:
        FreeCAD.GeoFeature.getGlobalPlacementOf() along the unresolved selection's path. A sketch's
        own getGlobalPlacement() knows nothing of links."""
        o = self.orientation
        own_q = (0.0, 0.0, 0.25881904510252074, 0.9659258262890683)             # the body's Rz30
        link_q = (0.7071067811865475, 0.0, 0.0, 0.7071067811865476)          # the link's Rx90
        pick = whole("Sketch", "Sketcher::SketchObject", global_q=own_q)
        sketch = pick.Object
        link = FakeObject(None, "Link", "App::Link")
        STUBS.selection_ex[:] = [pick]               # resolved: the sketch itself
        calls = []

        def along_path(target, root, subname):
            calls.append((target, root, subname))
            return fake_placement(link_q)

        self.patch(STUBS.app.GeoFeature, "getGlobalPlacementOf", along_path)
        cases = [
            ("through a link", [FakePick("Part1", "Link", ["Body.Sketch."], obj=link)], (link, "Body.Sketch.")),
            ("at the top of the document", [FakePick("Part1", "Sketch", [], obj=sketch)], (sketch, "")),
            ("an empty sub-element name", [FakePick("Part1", "Sketch", [""], obj=sketch)], (sketch, "")),
        ]
        for label, unresolved, (root, path) in cases:
            with self.subTest(label):
                del calls[:]
                STUBS.unresolved_selection_ex = unresolved
                self.assertEqual(o._sketch_rotation(sketch).Q, link_q)
                self.assertEqual(calls, [(sketch, root, path)])
                self.assertIs(calls[0][0], sketch)
                self.assertIs(calls[0][1], root)
        self.assertIn(("getSelectionEx", ("", 0)), STUBS.selection_calls, "the selection as picked, not resolved")
        view = FakeView3D()
        STUBS.set_active_view(view)
        STUBS.unresolved_selection_ex = cases[0][1]
        self.assertIs(o.normal_to(), True)
        self.assertEqual(view.calls, [("setCameraOrientation", link_q)], "not the body's rotation")
        self.assertEqual(self.lines(), [])

    def test_sketch_rotation_falls_back_to_the_sketchs_own_placement(self):
        o = self.orientation
        own_q = (0.0, 0.0, 0.25881904510252074, 0.9659258262890683)
        pick = whole("Sketch", "Sketcher::SketchObject", global_q=own_q)
        sketch = pick.Object
        body = FakeObject(None, "Body", "PartDesign::Body")
        STUBS.selection_ex[:] = [pick]
        cases = [
            ("nothing unresolved", []),
            ("two unresolved items", [FakePick("Part1", "Body", ["Sketch."], obj=body),
                                      FakePick("Part1", "Body001", ["Sketch001."], obj=body)]),
            ("two paths in one item", [FakePick("Part1", "Body", ["Sketch.", "Pad.Face6"], obj=body)]),
        ]
        for label, unresolved in cases:
            with self.subTest(label):
                del STUBS.placement_calls[:]
                STUBS.unresolved_selection_ex = unresolved
                self.assertEqual(o._sketch_rotation(sketch).Q, own_q)
                self.assertEqual(STUBS.placement_calls, [], "the path is not asked")
        self.assertEqual(self.lines(), [])
        STUBS.unresolved_selection_ex = [FakePick("Part1", "Body", ["Sketch."], obj=body)]
        self.patch(STUBS.app.GeoFeature, "getGlobalPlacementOf", lambda *_args: 1 / 0)
        self.assertEqual(o._sketch_rotation(sketch).Q, own_q, "getGlobalPlacementOf() fails")
        logged = self.jj("log")
        self.assertEqual(len(logged), 1, self.lines())
        self.assertIn("Normal To used the sketch's own placement", logged[0])
        self.assertIn("division by zero", logged[0])
        self.patch(STUBS.app, "GeoFeature", None)   # a FreeCAD without it
        self.assertEqual(o._sketch_rotation(sketch).Q, own_q)
        self.assertNoJellyJamsProblems()

    def test_normal_to_warns_when_the_view_cannot_turn(self):
        q = (0.0, 0.0, 0.0, 1.0)
        no_placement = whole("Sketch002", "Sketcher::SketchObject")
        no_placement.Object.__dict__["getGlobalPlacement"] = lambda: 1 / 0
        cases = [
            ("the view refuses", FakeView3D(error=RuntimeError("camera refused (harness)")),
             whole("Sketch001", "Sketcher::SketchObject", global_q=q), "camera refused"),
            ("no active view", None, whole("Sketch003", "Sketcher::SketchObject", global_q=q), "NoneType"),
            ("no placement", FakeView3D(), no_placement, "division by zero"),
        ]
        for label, view, pick, reason in cases:
            with self.subTest(label):
                STUBS.records.clear()
                STUBS.main_window.statusBar().clearMessage()
                STUBS.set_active_view(view)
                self.select(pick)
                self.assertIs(self.orientation.normal_to(), False)
                warnings = self.jj("warning")
                self.assertEqual(len(warnings), 1, self.lines())
                self.assertIn("Normal To could not turn the view to %s" % pick.Object.Label, warnings[0])
                self.assertIn(reason, warnings[0])
                self.assertEqual(self.status(), "", "there was something to look at: no hint")
        self.assertEqual(STUBS.run_calls, [])
        self.assertEqual(self.jj("error"), [])

    def test_normal_to_hint_is_temporary(self):
        self.assertEqual(self.orientation.HINT_MS, 4000)
        self.patch(self.orientation, "HINT_MS", 40)
        self.orientation.normal_to()
        self.assertEqual(self.status(), NORMAL_TO_HINT)
        self.assertTrue(STUBS.wait_until(lambda: self.status() == "", 1000), "the hint goes away by itself")

    def test_normal_to_hint_shows_at_the_pointer_too(self):
        STUBS.pump(300)                             # tooltips still due from earlier tests
        shown = []
        self.patch(QtWidgets.QToolTip, "showText", lambda *args: shown.append(args))
        self.addCleanup(QtGui.QCursor.setPos, QtGui.QCursor.pos())
        QtGui.QCursor.setPos(QtCore.QPoint(321, 234))
        STUBS.pump(10)
        self.assertEqual(self.orientation.TOOLTIP_DELAY_MS, 150)
        self.assertIs(self.orientation.normal_to(), False)
        self.assertEqual(self.status(), NORMAL_TO_HINT, "in the status bar at once")
        self.assertEqual(shown, [], "the tooltip waits until the panel has handed the keyboard back")
        self.assertTrue(STUBS.wait_until(lambda: shown, 1000), "and then shows next to the pointer")
        self.assertEqual(len(shown), 1)
        position, text = shown[0][:2]
        self.assertEqual(text, NORMAL_TO_HINT)
        self.assertEqual((position.x(), position.y()), (321, 234))
        del shown[:]
        self.select(FACE)
        self.orientation.normal_to()
        STUBS.pump(300)
        self.assertEqual(shown, [], "something to look at: no tooltip")
        self.patch(QtWidgets.QToolTip, "showText", lambda *args: 1 / 0)
        self.select()
        STUBS.main_window.statusBar().clearMessage()
        self.assertIs(self.orientation.normal_to(), False, "a tooltip that cannot show changes nothing else")
        STUBS.pump(300)
        self.assertEqual(self.status(), NORMAL_TO_HINT)
        self.assertNoJellyJamsProblems()

    def test_the_same_sketch_through_two_links_is_two_picks(self):
        """Resolved, the sketch picked under two link instances is one entry; on screen it is two
        places, so Normal To cannot choose and shows the hint."""
        own_q = (0.0, 0.0, 0.25881904510252074, 0.9659258262890683)
        pick = whole("Sketch", "Sketcher::SketchObject", global_q=own_q)
        link1 = FakeObject(None, "L1", "App::Link")
        link2 = FakeObject(None, "L2", "App::Link")
        STUBS.selection_ex[:] = [pick]
        STUBS.unresolved_selection_ex = [FakePick("Part1", "L1", ["Sketch."], obj=link1),
                                         FakePick("Part1", "L2", ["Sketch."], obj=link2)]
        self.assertIsNone(self.orientation.normal_to_target())
        view = FakeView3D()
        STUBS.set_active_view(view)
        self.assertIs(self.orientation.normal_to(), False)
        self.assertEqual(view.calls, [], "the view turns to neither instance")
        self.assertEqual(self.status(), NORMAL_TO_HINT)
        STUBS.unresolved_selection_ex = [FakePick("Part1", "L1", ["Sketch."], obj=link1)]
        self.assertEqual(self.orientation.normal_to_target(), ("sketch", pick.Object), "one instance: one pick")
        self.assertNoJellyJamsProblems()

    def test_normal_to_hint_tooltip_appears(self):
        """Offscreen too, Qt reports the tooltip as shown with the hint as its text."""
        self.addCleanup(QtWidgets.QToolTip.hideText)
        self.orientation.normal_to()
        self.assertTrue(STUBS.wait_until(lambda: QtWidgets.QToolTip.text() == NORMAL_TO_HINT, 1000),
                        QtWidgets.QToolTip.text())

    # layout ----------------------------------------------------------------------------------------
    def test_tables(self):
        self.assertEqual(tuple(map(tuple, self.orientation.VIEW_GRID)), EXPECTED_VIEW_GRID)
        self.assertEqual(tuple(map(tuple, self.orientation.AXONOMETRIC)), EXPECTED_AXONOMETRIC)
        self.assertEqual(tuple(map(tuple, self.orientation.TOOLS)), EXPECTED_ORIENTATION_TOOLS)
        self.assertEqual(dict(self.orientation.FALLBACK_ICONS), ORIENTATION_FALLBACK_ICONS)
        self.assertEqual(self.orientation.NORMAL_TO_HINT, NORMAL_TO_HINT)
        self.assertEqual(self.orientation.HINT_MS, 4000)
        self.assertEqual(self.orientation.MODEL_TREE_CLASS, MODEL_TREE_CLASS)
        self.assertEqual(tuple(self.orientation.SPACE_FOR_PANEL_CLASSES), SPACE_FOR_PANEL_CLASSES)
        self.assertEqual(tuple(self.orientation.SKETCH_TYPES), SKETCH_TYPES)
        self.assertEqual(tuple(self.orientation.DATUM_TYPES), DATUM_TYPES)
        self.assertEqual(self.orientation.OPEN_SETTLE_S, 0.3)

    def test_thirteen_view_buttons_in_their_places(self):
        self.orientation.open_at_cursor()
        buttons = self.buttons()
        self.assertEqual(len(buttons), 13)
        self.assertEqual(sorted(buttons), sorted(ORIENTATION_COMMANDS))
        self.assertEqual(self.button_order(self.panel().layout()), ORIENTATION_COMMANDS,
                         "tools row first, then the unfolded box, then the axonometric column")
        grids = self.panel().findChildren(QtWidgets.QGridLayout)
        self.assertEqual(len(grids), 1)
        grid = grids[0]
        for row, column, cmd, _label in EXPECTED_VIEW_GRID:
            with self.subTest(cmd=cmd):
                item = grid.itemAtPosition(row, column)
                self.assertIsNotNone(item, (row, column))
                self.assertIs(item.widget(), buttons[cmd])
        occupied = {(row, column) for row, column, _cmd, _label in EXPECTED_VIEW_GRID}
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                if (row, column) not in occupied:
                    self.assertIsNone(grid.itemAtPosition(row, column), "empty corner (%d, %d)" % (row, column))
        for cmd in ORIENTATION_COMMANDS:
            with self.subTest(cmd=cmd):
                self.assertTrue(buttons[cmd].isEnabled())
                self.assertFalse(buttons[cmd].isCheckable())

    def test_tooltips_name_the_view_and_its_key(self):
        self.orientation.open_at_cursor()
        buttons = self.buttons()
        labels = dict((cmd, label) for _r, _c, cmd, label in EXPECTED_VIEW_GRID)
        labels.update(EXPECTED_AXONOMETRIC)
        labels.update(EXPECTED_ORIENTATION_TOOLS)
        keys = {"Std_ViewTop": " (Ctrl+5)", "Std_ViewFitAll": " (F)", NORMAL_TO_CMD: " (Ctrl+8)"}
        for cmd in ORIENTATION_COMMANDS:
            with self.subTest(cmd=cmd):
                self.assertEqual(buttons[cmd].toolTip(), labels[cmd] + keys.get(cmd, ""))

    def test_missing_commands_are_disabled(self):
        missing = ("Std_ViewDimetric", "Std_ViewSaveCamera", NORMAL_TO_CMD)
        STUBS.set_commands([cmd for cmd in ORIENTATION_COMMANDS if cmd not in missing])
        self.select(FACE)
        self.orientation.open_at_cursor()
        buttons = self.buttons()
        self.assertEqual(len(buttons), 13, "every place stays filled")
        for cmd in missing:
            with self.subTest(cmd=cmd):
                self.assertFalse(buttons[cmd].isEnabled())
                buttons[cmd].click()
        self.assertEqual(STUBS.run_calls, [])
        self.assertTrue(self.orientation.is_open())

    def test_buttons_follow_the_commands_active_state(self):
        STUBS.set_command_active("Std_ViewRestoreCamera", False)
        STUBS.set_command_active("Std_ViewFitAll", RuntimeError("isActive broken by the harness"))
        STUBS.set_command_active(NORMAL_TO_CMD, False)
        self.orientation.open_at_cursor()
        buttons = self.buttons()
        self.assertFalse(buttons["Std_ViewRestoreCamera"].isEnabled(), "FreeCAD cannot run it now")
        self.assertTrue(buttons["Std_ViewFitAll"].isEnabled(), "a failing check leaves the button usable")
        self.assertTrue(buttons[NORMAL_TO_CMD].isEnabled(), "Normal To says what is missing instead")
        self.assertTrue(buttons["Std_ViewTop"].isEnabled())
        buttons["Std_ViewRestoreCamera"].click()
        self.assertEqual(STUBS.run_calls, [])
        self.orientation.close()
        STUBS.set_command_active("Std_ViewRestoreCamera", True)
        STUBS.set_command_active("Std_ViewTop", False)
        self.orientation.toggle()
        self.assertTrue(buttons["Std_ViewRestoreCamera"].isEnabled(), "refreshed every time the panel opens")
        self.assertFalse(buttons["Std_ViewTop"].isEnabled())
        self.assertNoJellyJamsProblems()

    # clicks and keys --------------------------------------------------------------------------------
    def test_click_applies_the_view_and_closes(self):
        self.select(FACE)                           # Normal To has something to look at
        for cmd in ORIENTATION_COMMANDS:
            with self.subTest(cmd=cmd):
                del STUBS.run_calls[:]
                self.orientation.open_at_cursor()
                self.buttons()[cmd].click()
                self.assertEqual(STUBS.run_calls, [(cmd, None)])
                self.assertFalse(self.orientation.is_open())
        self.assertNoJellyJamsProblems()

    def run_normal_to_like_freecad(self):
        """Make FreeCAD's runCommand run JellyJams' own Normal To, as FreeCAD does; returns the list
        of whether the panel was open each time it ran."""
        fcgui = self.module("jellyjams.fcgui")
        real_run = fcgui.run_command
        command = self.orientation.get_commands()[NORMAL_TO_CMD]
        open_when_run = []

        def run(cmd_id, index=None):
            done = real_run(cmd_id, index)
            if cmd_id == NORMAL_TO_CMD:
                open_when_run.append(self.orientation.is_open())
                command.Activated()
            return done

        self.patch(fcgui, "run_command", run)
        return open_when_run

    def test_normal_to_button_closes_the_panel_unless_pinned(self):
        open_when_run = self.run_normal_to_like_freecad()
        cases = [
            ("nothing selected", [], []),
            ("two flat faces", [FACE, OTHER_FACE], []),
            ("a whole body", [whole("Body", "PartDesign::Body", Shape=fake_shape(faces=6, solids=1))], []),
            ("a flat face", [FACE], [(ALIGN_CMD, None)]),
            ("a curved face", [CURVED_FACE], [(ALIGN_CMD, None)]),
        ]
        for pinned in (False, True):
            for label, picks, runs in cases:
                with self.subTest(label, pinned=pinned):
                    del STUBS.run_calls[:]
                    del open_when_run[:]
                    STUBS.main_window.statusBar().clearMessage()
                    self.select(*picks)
                    self.orientation.open_at_cursor()
                    self.panel().pin_button.setChecked(pinned)
                    button = self.buttons()[NORMAL_TO_CMD]
                    self.assertTrue(button.isEnabled())
                    button.click()
                    self.assertEqual(STUBS.run_calls, [(NORMAL_TO_CMD, None)] + runs)
                    self.assertEqual(open_when_run, [pinned], "an unpinned panel closes before Normal To runs")
                    self.assertEqual(self.orientation.is_open(), pinned)
                    self.assertEqual(self.status(), "" if runs else NORMAL_TO_HINT,
                                     "with nothing to look at the hint shows, the panel gone")
                    self.orientation.close()
        self.assertNoJellyJamsProblems()

    def test_normal_to_button_with_a_plane_selected_closes_the_panel(self):
        self.select(whole("XY_Plane", "App::Plane"))
        self.orientation.open_at_cursor()
        self.buttons()[NORMAL_TO_CMD].click()
        self.assertEqual(STUBS.run_calls, [(NORMAL_TO_CMD, None)], "FreeCAD runs JellyJams' Normal To")
        self.assertFalse(self.orientation.is_open())
        self.assertEqual(self.status(), "")

    def test_pinned_panel_stays_open(self):
        self.orientation.open_at_cursor()
        pin = self.panel().pin_button
        self.assertTrue(pin.isCheckable())
        self.assertFalse(pin.isChecked(), "unpinned by default")
        pin.setChecked(True)
        for cmd in ("Std_ViewTop", "Std_ViewIsometric", "Std_ViewFitAll"):
            self.buttons()[cmd].click()
            self.assertTrue(self.orientation.is_open(), cmd)
        self.assertEqual([call[0] for call in STUBS.run_calls], ["Std_ViewTop", "Std_ViewIsometric", "Std_ViewFitAll"])
        pin.setChecked(False)
        self.buttons()["Std_ViewFront"].click()
        self.assertFalse(self.orientation.is_open())

    def test_escape_and_space_close(self):
        for key in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Space):
            with self.subTest(key=key):
                self.orientation.open_at_cursor()
                self.key(QtCore.Qt.Key.Key_A)
                self.assertTrue(self.orientation.is_open(), "other keys leave it open")
                self.key(key)
                self.assertFalse(self.orientation.is_open())
        self.assertEqual(STUBS.run_calls, [], "closing runs no view command")

    def test_held_keys_do_not_close_the_panel(self):
        self.orientation.open_at_cursor()
        for key in (QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Space):
            with self.subTest(key=key):
                self.key(key, auto_repeat=True)
                self.assertTrue(self.orientation.is_open(), "a repeat of the key that opened it is ignored")
        self.key(QtCore.Qt.Key.Key_Space)
        self.assertFalse(self.orientation.is_open())

    def test_held_space_does_not_repeat_the_command(self):
        window = STUBS.main_window
        action = QtGui.QAction("View Orientation", window)
        self.assertTrue(action.autoRepeat(), "Qt repeats a held shortcut by default")
        STUBS.set_command_actions(ORIENTATION_CMD, [action])
        self.orientation.install()
        self.assertFalse(action.autoRepeat())
        for opened in (True, False):
            with self.subTest(opened=opened):
                action.setAutoRepeat(True)          # FreeCAD made a new action, for example
                self.orientation.toggle()
                self.assertFalse(action.autoRepeat())
                self.assertEqual(self.orientation.is_open(), opened)
        STUBS.set_command_actions(ORIENTATION_CMD, [])
        self.orientation.toggle()                   # no action (the command is in no menu): nothing to change
        self.assertTrue(self.orientation.is_open())
        self.assertNoJellyJamsProblems()

    def test_close_button(self):
        self.orientation.open_at_cursor()
        closer = [b for b in self.panel().findChildren(QtWidgets.QToolButton)
                  if b is not self.panel().pin_button and not b.objectName().startswith(ORIENTATION_BUTTON_PREFIX)]
        self.assertEqual(len(closer), 1)
        self.assertIn("Esc", closer[0].toolTip())
        closer[0].click()
        self.assertFalse(self.orientation.is_open())
        self.assertEqual(STUBS.run_calls, [])

    def test_close_is_safe_when_never_opened(self):
        self.assertIsNone(self.panel())
        self.assertFalse(self.orientation.is_open())
        self.orientation.close()
        self.orientation.close()
        self.assertFalse(self.orientation.is_open())
        self.assertEqual(self.lines(), [])
        self.orientation.open_at_cursor()
        self.orientation.close()
        self.orientation.close()
        self.assertFalse(self.orientation.is_open())
        self.assertEqual(self.lines(), [])

    # clicking elsewhere ------------------------------------------------------------------------------
    def test_click_outside_closes_the_panel_unless_pinned(self):
        clock = self.clock()
        for pinned in (False, True):
            with self.subTest(pinned=pinned):
                clock.now += 10.0
                self.orientation.open_at_cursor()
                STUBS.pump(20)
                self.assertTrue(self.panel().isActiveWindow(), "the panel takes the keyboard when it opens")
                self.panel().pin_button.setChecked(pinned)
                clock.now += 1.0                    # the user clicks elsewhere a second later
                self.other_window()
                STUBS.pump(20)
                self.assertEqual(self.orientation.is_open(), pinned)
                self.orientation.close()
        self.assertEqual(STUBS.run_calls, [])
        self.assertNoJellyJamsProblems()

    def test_deactivation_while_the_opening_settles_does_not_close(self):
        settle = self.orientation.OPEN_SETTLE_S
        clock = self.clock(100.0)
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        self.assertTrue(self.panel().isActiveWindow())
        clock.now = 100.0 + settle / 2              # a menu closing right after Space, for example
        other = QtWidgets.QWidget()
        other.resize(80, 60)
        self.addCleanup(other.close)
        other.show()
        other.activateWindow()
        STUBS.pump(50)
        self.assertTrue(self.orientation.is_open(), "the opening settling is not a click elsewhere")
        self.assertTrue(self.panel().isActiveWindow(), "the panel takes the keyboard back: Esc still closes it")
        self.assertFalse(other.isActiveWindow())
        self.orientation.close()
        clock.now = 200.0
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        self.assertTrue(self.panel().isActiveWindow())
        clock.now = 200.0 + settle + 0.05
        self.other_window()
        STUBS.pump(20)
        self.assertFalse(self.orientation.is_open(), "past the settle time it is a click elsewhere")
        self.assertNoJellyJamsProblems()

    def test_check_within_the_settle_time_takes_the_keyboard_back(self):
        o = self.orientation
        queued = self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        self.assertTrue(o._seen_active)
        calls = []
        self.patch(o._panel, "activateWindow", lambda: calls.append("activateWindow"))
        cases = [
            # label, pinned, time since opening, re-activated, still open
            ("within the settle time", False, o.OPEN_SETTLE_S / 2, True, True),
            ("within the settle time, pinned", True, o.OPEN_SETTLE_S / 2, False, True),
            ("past the settle time, pinned", True, o.OPEN_SETTLE_S + 1.0, False, True),
            ("past the settle time", False, o.OPEN_SETTLE_S + 1.0, False, False),
        ]
        for label, pinned, after, activated, still_open in cases:
            with self.subTest(label):
                QtWidgets.QWidget.activateWindow(o._panel)   # the panel has the keyboard
                STUBS.pump(20)
                self.assertTrue(o._panel.isActiveWindow())
                del calls[:]
                del queued[:]
                self.other_window()                 # the check for this opening waits in `queued`
                self.assertEqual(len(queued), 1)
                o._panel.pin_button.setChecked(pinned)
                clock.now = 100.0 + after
                queued.pop()()
                self.assertEqual(calls, ["activateWindow"] if activated else [])
                self.assertEqual(o.is_open(), still_open)
        self.assertNoJellyJamsProblems()

    def test_settle_check_with_another_program_in_front_closes(self):
        """Within the settle time but with no FreeCAD window active (another program took the
        keyboard), the panel closes instead of asking for the keyboard back."""
        o = self.orientation
        queued = self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        calls = []
        self.patch(o._panel, "activateWindow", lambda: calls.append("panel"))
        self.patch(STUBS.main_window, "activateWindow", lambda: calls.append("main window"))
        self.other_window()
        self.assertEqual(len(queued), 1)
        self.patch(QtWidgets.QApplication, "activeWindow", staticmethod(lambda: None))
        clock.now = 100.0 + o.OPEN_SETTLE_S / 2
        queued.pop()()
        self.assertFalse(o.is_open())
        self.assertEqual(calls, [], "nothing is pulled to the front")
        self.assertNoJellyJamsProblems()

    def test_click_elsewhere_remembers_the_window_for_a_pinned_panel(self):
        """A pinned panel stays open across window switches; when the keyboard leaves it, the
        FreeCAD window that took it becomes the one the panel hands the keyboard back to."""
        o = self.orientation
        queued = self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        first = o._return_to
        o._panel.pin_button.setChecked(True)
        clock.now = 105.0
        other = self.other_window()
        self.assertEqual(len(queued), 1)
        queued.pop()()
        self.assertTrue(o.is_open(), "pinned")
        self.assertIs(o._return_to, other)
        self.assertIsNot(o._return_to, first)
        calls = []
        self.patch(other, "activateWindow", lambda: calls.append("other"))
        QtWidgets.QWidget.activateWindow(o._panel)      # a view button was clicked in the pinned panel
        STUBS.pump(20)
        del queued[:]
        o.close()
        self.assertEqual(calls, ["other"], "the keyboard goes to the window the user was last in")
        o._panel.pin_button.setChecked(False)
        self.assertNoJellyJamsProblems()

    def test_opening_starts_a_new_generation(self):
        o = self.orientation
        clock = self.clock(50.0)
        before = o._generation
        o.open_at_cursor()
        self.assertEqual((o._generation, o._opened_at, o._seen_active), (before + 1, 50.0, False))
        STUBS.pump(20)
        self.assertIs(o._seen_active, True, "the panel got the keyboard")
        o.close()
        clock.now = 60.0
        o.open_at_cursor()
        self.assertEqual((o._generation, o._opened_at, o._seen_active), (before + 2, 60.0, False),
                         "every opening starts over")

    def test_a_late_check_never_closes_a_newer_opening(self):
        o = self.orientation
        queued = self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        self.other_window()                         # click elsewhere: a check for this opening waits
        self.assertEqual(len(queued), 1)
        first_check = queued.pop()
        o.close()
        clock.now = 101.0
        o.open_at_cursor()                          # Space again before that check ran
        STUBS.pump(20)
        self.assertTrue(o._seen_active)
        self.other_window()
        self.assertEqual(len(queued), 1)
        second_check = queued.pop()
        clock.now = 105.0                           # long past the settle time of either opening
        first_check()
        self.assertTrue(o.is_open(), "the check of the earlier opening leaves the new one alone")
        second_check()
        self.assertFalse(o.is_open(), "its own check closes it")
        self.assertNoJellyJamsProblems()

    def test_a_panel_that_never_had_the_keyboard_is_not_closed(self):
        o = self.orientation
        self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        self.other_window()
        clock.now = 105.0
        self.assertFalse(o._panel.isActiveWindow())
        o._seen_active = False                      # as if the panel had never been given the keyboard
        o._close_if_left(o._generation)
        self.assertTrue(o.is_open(), "no keyboard since opening: nothing was clicked away from")
        o._seen_active = True
        o._close_if_left(o._generation)
        self.assertFalse(o.is_open())

    def test_click_outside_check_skips_an_active_closed_or_pinned_panel(self):
        o = self.orientation
        queued = self.queue_deferred()
        clock = self.clock(100.0)
        o.open_at_cursor()
        STUBS.pump(20)
        clock.now = 105.0
        self.assertTrue(o._panel.isActiveWindow())
        o._close_if_left(o._generation)
        self.assertTrue(o.is_open(), "the panel has the keyboard again")
        self.other_window()
        o._panel.pin_button.setChecked(True)
        o._close_if_left(o._generation)
        self.assertTrue(o.is_open(), "pinned")
        o._panel.pin_button.setChecked(False)
        o.close()
        o._close_if_left(o._generation)            # already closed: nothing to do, no error
        self.assertFalse(o.is_open())
        del queued[:]
        o._activation_changed(False)               # a deactivation of a closed panel schedules nothing
        self.assertEqual(queued, [])
        self.assertEqual(self.lines(), [])

    def test_close_gives_the_keyboard_back_only_when_the_panel_had_it(self):
        window = STUBS.main_window
        calls = []
        self.patch(window, "activateWindow", lambda: calls.append("activateWindow"))
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        self.assertTrue(self.panel().isActiveWindow())
        self.orientation.close()
        self.assertEqual(calls, ["activateWindow"], "the next Space reaches FreeCAD again")
        del calls[:]
        self.orientation.open_at_cursor()
        self.panel().pin_button.setChecked(True)
        other = self.other_window()
        self.assertTrue(self.orientation.is_open())
        self.orientation.close()
        self.assertEqual(calls, [], "FreeCAD is not pulled in front of the window the user went to")
        self.assertTrue(other.isActiveWindow())

    def test_close_returns_the_keyboard_to_the_window_that_had_it(self):
        """An undocked or fullscreen 3D view is a window of its own: closing the panel gives the
        keyboard back to it, so it stays in front and the next Space reaches it."""
        import shiboken6

        o = self.orientation
        fcgui = self.module("jellyjams.fcgui")
        calls = []
        self.patch(STUBS.main_window, "activateWindow", lambda: calls.append("main window"))

        def open_over_undocked_view(record=True):
            view = qt_class(CLASS_VIEW3D, QtWidgets.QWidget)()
            view.resize(200, 150)
            self.addCleanup(lambda: fcgui.is_alive(view) and view.close())
            view.show()
            view.activateWindow()
            STUBS.pump(30)
            self.assertIs(QtWidgets.QApplication.activeWindow(), view)
            if record:
                self.patch(view, "activateWindow", lambda: calls.append("undocked view"))
            o.open_at_cursor()
            STUBS.pump(20)
            self.assertIs(o._return_to, view)
            self.assertTrue(o._panel.isActiveWindow())
            return view

        open_over_undocked_view()
        o.close()
        self.assertEqual(calls, ["undocked view"], "the undocked view keeps the keyboard and stays in front")
        del calls[:]
        open_over_undocked_view().hide()
        o.close()
        self.assertEqual(calls, ["main window"], "a window that is gone from the screen: the main window")
        del calls[:]
        shiboken6.delete(open_over_undocked_view(record=False))
        o.close()
        self.assertEqual(calls, ["main window"], "a deleted window: the main window")
        del calls[:]
        open_over_undocked_view()
        o._return_to = None                         # nothing had the keyboard when the panel opened
        o.close()
        self.assertEqual(calls, ["main window"])
        del calls[:]
        open_over_undocked_view()
        o._panel.pin_button.setChecked(True)
        self.other_window()                         # the user went to another program
        o.close()
        self.assertEqual(calls, [], "the panel did not have the keyboard: nothing is pulled to the front")
        o._panel.pin_button.setChecked(False)
        self.assertNoJellyJamsProblems()

    def test_the_panel_is_never_the_window_to_return_to(self):
        o = self.orientation
        o.open_at_cursor()
        STUBS.pump(20)
        self.assertIs(QtWidgets.QApplication.activeWindow(), o._panel)
        o.open_at_cursor()                          # opened again while it has the keyboard
        self.assertIsNone(o._return_to)
        calls = []
        self.patch(STUBS.main_window, "activateWindow", lambda: calls.append("main window"))
        o.close()
        self.assertEqual(calls, ["main window"])

    def test_panel_is_built_again_when_its_widget_was_deleted(self):
        import shiboken6

        self.orientation.open_at_cursor()
        old = self.panel()
        self.orientation.close()
        shiboken6.delete(old)
        self.assertFalse(self.orientation.is_open())
        self.orientation.close()
        self.orientation.open_at_cursor()
        self.assertIsNot(self.panel(), old)
        self.assertTrue(self.orientation.is_open())
        self.assertEqual(len(self.buttons()), 13)
        self.assertEqual(self.jj("warning") + self.jj("error"), [])

    # the Space key ----------------------------------------------------------------------------------
    def test_keeps_space(self):
        keeps = self.orientation.keeps_space
        cases = [
            ("check box", QtWidgets.QCheckBox(), True),
            ("radio button", QtWidgets.QRadioButton(), True),
            ("push button", QtWidgets.QPushButton(), True),
            ("tool button", QtWidgets.QToolButton(), True),
            ("combo box", QtWidgets.QComboBox(), True),
            ("plain list", QtWidgets.QListWidget(), False),
            ("plain tree", QtWidgets.QTreeWidget(), False),
            ("table: typing edits a cell", QtWidgets.QTableWidget(), True),
            ("the model tree", qt_class(MODEL_TREE_CLASS, QtWidgets.QTreeWidget)(), False),
            ("line edit", QtWidgets.QLineEdit(), False),
            ("the 3D view", qt_class(CLASS_VIEW3D, QtWidgets.QWidget)(), False),
            ("nothing", None, False),
        ]
        for label, widget, expected in cases:
            with self.subTest(label):
                self.assertIs(keeps(widget), expected)
                self.assertIs(keeps(widget, None), expected, "no widget under the pointer")

    def checkable_list(self, cls=QtWidgets.QListWidget, checkable=True):
        view = cls()
        item = QtWidgets.QListWidgetItem("Sketch001")
        if checkable:
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        else:
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        view.addItem(item)
        view.setCurrentItem(item)
        self.assertTrue(view.currentIndex().isValid())
        return view

    def test_item_views_keep_space_to_check_or_type(self):
        keeps = self.orientation.keeps_space
        triggers = QtWidgets.QAbstractItemView.EditTrigger
        typing_tree = QtWidgets.QTreeWidget()
        typing_tree.setEditTriggers(typing_tree.editTriggers() | triggers.AnyKeyPressed)
        model_tree = qt_class(MODEL_TREE_CLASS, QtWidgets.QTreeWidget)()
        model_tree.setEditTriggers(model_tree.editTriggers() | triggers.AnyKeyPressed)
        model_item = QtWidgets.QTreeWidgetItem(model_tree, ["Body"])
        model_item.setFlags(model_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        model_tree.setCurrentItem(model_item)
        no_typing_table = QtWidgets.QTableWidget()
        no_typing_table.setEditTriggers(triggers.DoubleClicked)

        class BrokenList(QtWidgets.QListWidget):
            def currentIndex(self):
                raise RuntimeError("currentIndex broken by the harness")

        cases = [
            ("checkable current item", self.checkable_list(), True),
            ("current item not checkable", self.checkable_list(checkable=False), False),
            ("no current item", QtWidgets.QListWidget(), False),
            ("typing edits the current item", typing_tree, True),
            ("a property list with Qt's default triggers", qt_class("Gui::PropertyEditor::PropertyEditor",
                                                                     QtWidgets.QTreeView)(), False),
            ("a table that does not edit on typing", no_typing_table, False),
            ("the model tree, even checkable and typing", model_tree, False),
            ("a list that cannot say its current item", BrokenList(), False),
        ]
        for label, view, expected in cases:
            with self.subTest(label):
                self.assertIs(keeps(view), expected)

    def test_space_over_the_3d_view_or_the_model_tree_always_opens_the_panel(self):
        keeps = self.orientation.keeps_space
        view3d = qt_class(CLASS_VIEW3D, QtWidgets.QWidget)()
        viewport = QtWidgets.QWidget(view3d)         # the drawing area inside FreeCAD's 3D view
        viewer = qt_class(CLASS_VIEWER, QtWidgets.QWidget)()
        gl_widget = QtWidgets.QWidget(viewer)        # the GL widget; its parent is the viewer in every 3D view
        split = qt_class(CLASS_SPLIT_VIEW3D, QtWidgets.QWidget)()
        split_inner = QtWidgets.QWidget(QtWidgets.QSplitter(split))
        split_viewer = QtWidgets.QWidget(qt_class(CLASS_VIEWER, QtWidgets.QWidget)(QtWidgets.QSplitter(split)))
        model_tree = qt_class(MODEL_TREE_CLASS, QtWidgets.QTreeWidget)()
        focused = [("check box", QtWidgets.QCheckBox()), ("combo box", QtWidgets.QComboBox()),
                   ("checkable list", self.checkable_list()), ("push button", QtWidgets.QPushButton())]
        over_model = [("the 3D view", view3d), ("inside the 3D view", viewport),
                      ("a 3D viewer alone", viewer), ("a 3D viewer's drawing area", gl_widget),
                      ("a split 3D view", split), ("deep inside a split 3D view", split_inner),
                      ("one viewer of a split 3D view", split_viewer), ("the model tree", model_tree),
                      ("the model tree's items", model_tree.viewport())]
        for pointer_label, pointer in over_model:
            for widget_label, widget in focused:
                with self.subTest(pointer=pointer_label, focus=widget_label):
                    self.assertIs(keeps(widget, pointer), False,
                                  "a check box clicked a moment ago must not flip unnoticed")
        elsewhere = [("a plain widget", QtWidgets.QWidget()), ("the focused control itself", None),
                     ("a task panel", qt_class("Gui::TaskView::TaskPanel", QtWidgets.QWidget)()),
                     ("a property list", qt_class("Gui::PropertyEditor::PropertyEditor", QtWidgets.QTreeView)()),
                     ("a drawing page", qt_class("TechDrawGui::MDIViewPage", QtWidgets.QWidget)())]
        for pointer_label, pointer in elsewhere:
            for widget_label, widget in focused:
                with self.subTest(pointer=pointer_label, focus=widget_label):
                    self.assertIs(keeps(widget, widget if pointer is None else pointer), True)

    def test_toolbars_status_bar_and_ribbon_never_keep_space(self):
        keeps = self.orientation.keeps_space
        window = STUBS.main_window
        toolbar = window.addToolBar("Workbench")
        selector = qt_class("Gui::WorkbenchComboBox", QtWidgets.QComboBox)()
        toolbar.addWidget(selector)
        toolbar_button = QtWidgets.QToolButton()
        toolbar.addWidget(toolbar_button)
        status_button = QtWidgets.QToolButton()
        window.statusBar().addPermanentWidget(status_button)
        status_combo = QtWidgets.QComboBox()
        window.statusBar().addWidget(status_combo)
        ribbon = QtWidgets.QDockWidget("CommandManager", window)
        ribbon.setObjectName("JellyJamsCommandManager")
        page = QtWidgets.QWidget()
        ribbon.setWidget(page)
        ribbon_button = QtWidgets.QToolButton(page)
        ribbon_check = QtWidgets.QCheckBox(QtWidgets.QFrame(QtWidgets.QFrame(page)))
        tasks = QtWidgets.QDockWidget("Tasks", window)
        tasks.setObjectName("Tasks")
        tasks_page = QtWidgets.QWidget()
        tasks_check = QtWidgets.QCheckBox("Reversed", tasks_page)
        tasks_combo = QtWidgets.QComboBox(tasks_page)
        tasks_combo.move(0, 40)
        tasks.setWidget(tasks_page)
        window.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, tasks)
        tasks.show()
        cases = [
            ("the workbench selector", selector, False),
            ("a toolbar button", toolbar_button, False),
            ("a status bar button", status_button, False),
            ("a status bar combo box", status_combo, False),
            ("a ribbon button", ribbon_button, False),
            ("a check box deep in the ribbon", ribbon_check, False),
            ("a check box in a task panel", tasks_check, True),
            ("a combo box in a task panel", tasks_combo, True),
        ]
        for label, widget, expected in cases:
            with self.subTest(label):
                self.assertIs(keeps(widget), expected)
        self.orientation.install()
        self.assertTrue(focus_on(selector), QtWidgets.QApplication.focusWidget())
        self.assertFalse(override_accepted(selector, space_event()), "the selector keeps the focus after a click")
        self.assertTrue(focus_on(tasks_check))
        self.assertTrue(override_accepted(tasks_check, space_event()))

    def test_space_filter_accepts_plain_space_for_controls_only(self):
        window = STUBS.main_window
        self.orientation.install()
        space_filter = self.orientation._space_filter
        self.assertIsNotNone(space_filter)
        box = QtWidgets.QCheckBox("box", window)
        self.assertTrue(focus_on(box), QtWidgets.QApplication.focusWidget())
        modifier, key = QtCore.Qt.KeyboardModifier, QtCore.Qt.Key
        cases = [
            ("plain Space", space_event(), True),
            ("Shift+Space", space_event(modifiers=modifier.ShiftModifier), False),
            ("Ctrl+Space", space_event(modifiers=modifier.ControlModifier), False),
            ("another key", space_event(key=key.Key_A), False),
            ("Space as a key press", space_event(event_type=QtCore.QEvent.Type.KeyPress), False),
        ]
        for label, event, accepted in cases:
            with self.subTest(label):
                self.assertIs(bool(space_filter.eventFilter(window, event)), accepted)
                self.assertIs(event.isAccepted(), accepted)
        self.assertTrue(override_accepted(box, space_event()), "the override reaches the main window's filter")
        # A line edit takes Space as text by itself (Qt asks the focus widget first); over the model
        # tree and the 3D view nothing takes it, so Space opens the panel there.
        for label, widget, taken in (("line edit", QtWidgets.QLineEdit(window), True),
                                     ("the model tree", qt_class(MODEL_TREE_CLASS, QtWidgets.QTreeWidget)(window), False),
                                     ("the 3D view", qt_class(CLASS_VIEW3D, QtWidgets.QWidget)(window), False)):
            with self.subTest(label):
                widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
                self.assertTrue(focus_on(widget), QtWidgets.QApplication.focusWidget())
                self.assertFalse(space_filter.eventFilter(window, space_event()), "the filter leaves it alone")
                self.assertIs(override_accepted(widget, space_event()), taken)

    def test_space_toggles_a_focused_check_box_instead_of_opening_the_panel(self):
        from PySide6 import QtTest

        window = STUBS.main_window
        fired = []
        action = QtGui.QAction("View Orientation", window)
        action.setShortcut(QtGui.QKeySequence("Space"))
        action.triggered.connect(lambda *_args: fired.append("panel"))
        window.addAction(action)
        box = QtWidgets.QCheckBox("box", window)
        self.assertTrue(focus_on(box))
        QtTest.QTest.keyClick(box, QtCore.Qt.Key.Key_Space)
        self.assertEqual((fired, box.isChecked()), (["panel"], False), "without the filter the shortcut wins")
        self.orientation.install()
        QtTest.QTest.keyClick(box, QtCore.Qt.Key.Key_Space)
        self.assertEqual((fired, box.isChecked()), (["panel"], True), "the check box gets Space")
        view = qt_class(CLASS_VIEW3D, QtWidgets.QWidget)(window)
        view.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.assertTrue(focus_on(view))
        QtTest.QTest.keyClick(view, QtCore.Qt.Key.Key_Space)
        self.assertEqual(fired, ["panel", "panel"], "Space over the 3D view still opens the panel")
        self.orientation.uninstall()
        self.assertTrue(focus_on(box))
        QtTest.QTest.keyClick(box, QtCore.Qt.Key.Key_Space)
        self.assertEqual((fired, box.isChecked()), (["panel"] * 3, True), "after leaving JellyJams, as before")

    def test_space_on_a_focused_panel_button_clicks_it(self):
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        top = self.buttons()["Std_ViewTop"]
        top.setFocus()                              # reached with Tab
        STUBS.pump(10)
        self.assertIs(QtWidgets.QApplication.focusWidget(), top)
        self.assertTrue(override_accepted(top, space_event()), "the panel hands Space to its focused button")
        self.panel().setFocus()
        STUBS.pump(10)
        self.assertFalse(override_accepted(self.panel(), space_event()), "Space on the panel itself closes it")

    def test_space_on_a_focused_panel_button_ignores_the_pointer(self):
        """The panel opens beside the pointer, which usually stays over the 3D view: a view button
        reached with Tab still gets Space."""
        window = STUBS.main_window
        view3d = qt_class(CLASS_VIEW3D, QtWidgets.QWidget)()
        view3d.setMinimumSize(400, 300)
        sub_window = window.centralWidget().addSubWindow(view3d)
        sub_window.show()
        STUBS.pump(20)
        self.point_at(view3d)
        self.orientation.install()                  # the main window's filter follows the pointer rule
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        under = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        self.assertTrue(under is view3d or view3d.isAncestorOf(under), "the pointer is still over the 3D view")
        top = self.buttons()["Std_ViewTop"]
        top.setFocus()
        STUBS.pump(10)
        self.assertIs(QtWidgets.QApplication.focusWidget(), top)
        self.assertTrue(override_accepted(top, space_event()), "the focused view button gets Space")
        self.assertIs(self.orientation._hand_space_to_focus(space_event()), False,
                      "with the pointer rule, Space over the 3D view would be for the panel")
        self.panel().setFocus()
        STUBS.pump(10)
        self.assertFalse(override_accepted(self.panel(), space_event()), "Space on the panel itself closes it")
        self.assertNoJellyJamsProblems()

    def test_install_is_idempotent_and_uninstall_removes_the_filter(self):
        window = STUBS.main_window
        self.orientation.uninstall()                # safe before any install
        self.assertEqual(self.lines(), [])
        self.orientation.install()
        self.orientation.install()
        self.assertEqual(len(space_filters(window)), 1, "one filter, however often JellyJams is activated")
        self.assertEqual(self.orientation._filtered, [window], "a window without docks")
        first = self.orientation._space_filter
        self.orientation.open_at_cursor()
        self.orientation.uninstall()
        self.assertFalse(self.orientation.is_open(), "leaving JellyJams closes the panel")
        self.assertIsNone(self.orientation._space_filter)
        self.assertEqual(self.orientation._filtered, [])
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        self.assertEqual(space_filters(window), [])
        box = QtWidgets.QCheckBox("box", window)
        self.assertTrue(focus_on(box))
        self.assertFalse(override_accepted(box, space_event()))
        self.orientation.uninstall()
        self.orientation.install()
        self.assertEqual(len(space_filters(window)), 1)
        self.assertIsNot(self.orientation._space_filter, first)
        self.assertTrue(override_accepted(box, space_event()))
        self.assertNoJellyJamsProblems()

    def test_install_without_a_main_window_does_nothing(self):
        self.patch(STUBS, "main_window", None)
        self.orientation.install()
        self.assertIsNone(self.orientation._space_filter)
        self.assertEqual(self.orientation._filtered, [])
        self.orientation.uninstall()
        self.assertEqual(self.lines(), [])

    def add_dock(self, title, area=QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, floating=False):
        """A dock of the main window holding one check box; returns (dock, check box)."""
        window = STUBS.main_window
        dock = QtWidgets.QDockWidget(title, window)
        dock.setObjectName(title)
        box = QtWidgets.QCheckBox(title + " option")
        dock.setWidget(box)
        window.addDockWidget(area, dock)
        dock.show()
        if floating:
            dock.setFloating(True)
        STUBS.pump(20)
        return dock, box

    def test_filter_sits_on_the_main_window_and_every_dock(self):
        window = STUBS.main_window
        docked, docked_box = self.add_dock("Tasks")
        floating, floating_box = self.add_dock("Report view", QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
                                               floating=True)
        self.assertTrue(floating.isFloating() and floating.isWindow(), "a floating dock is a window of its own")
        self.assertTrue(focus_on(floating_box), QtWidgets.QApplication.focusWidget())
        self.assertFalse(override_accepted(floating_box, space_event()), "no filter before activation")
        self.orientation.install()
        filtered = list(self.orientation._filtered)
        self.assertIs(filtered[0], window)
        self.assertCountEqual(filtered, [window, docked, floating])
        self.assertTrue(override_accepted(floating_box, space_event()),
                        "the floating dock's own filter hands Space to its check box")
        self.assertTrue(focus_on(docked_box))
        self.assertTrue(override_accepted(docked_box, space_event()))
        first = self.orientation._space_filter
        self.orientation.install()
        self.assertIs(self.orientation._space_filter, first, "installing again changes nothing")
        self.assertEqual(self.orientation._filtered, filtered)
        self.assertEqual(len(space_filters(window)), 1)
        self.assertTrue(focus_on(floating_box))
        self.orientation.uninstall()                # checked before Qt deletes the filter object
        self.assertEqual(self.orientation._filtered, [])
        self.assertFalse(override_accepted(floating_box, space_event()), "removed from the floating dock")
        self.assertTrue(focus_on(docked_box))
        self.assertFalse(override_accepted(docked_box, space_event()), "and from the main window")
        self.assertEqual(self.lines(), [])

    def test_floating_dock_needs_its_own_filter(self):
        """Qt delivers a key event up to the widget's window and no further: a floating dock's
        ShortcutOverride never reaches the main window."""
        window = STUBS.main_window
        floating, floating_box = self.add_dock("Selection view", floating=True)
        self.orientation.install()
        floating.removeEventFilter(self.orientation._space_filter)
        self.assertTrue(focus_on(floating_box))
        self.assertFalse(override_accepted(floating_box, space_event()), "the main window's filter alone misses it")
        floating.setFloating(False)
        STUBS.pump(20)
        self.assertIs(floating_box.window(), window)
        self.assertTrue(focus_on(floating_box))
        self.assertTrue(override_accepted(floating_box, space_event()), "docked again, it reaches the main window")

    def test_uninstall_skips_a_dock_that_was_deleted(self):
        import shiboken6

        dock, _box = self.add_dock("Python console")
        self.orientation.install()
        self.assertIn(dock, self.orientation._filtered)
        shiboken6.delete(dock)
        self.orientation.uninstall()
        self.assertEqual(self.orientation._filtered, [])
        self.assertIsNone(self.orientation._space_filter)
        self.assertEqual(self.lines(), [], "nothing to report")

    def test_a_dock_made_after_activation_gets_the_filter_when_it_takes_focus(self):
        window = STUBS.main_window
        self.orientation.install()
        self.assertEqual(self.orientation._filtered, [window])
        quiet = QtWidgets.QDockWidget("Quiet", window)
        quiet.setWidget(QtWidgets.QLabel("nothing here takes focus"))
        window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, quiet)
        quiet.show()
        STUBS.pump(20)
        self.assertEqual(self.orientation._filtered, [window], "a dock made later is added once it takes focus")
        late, late_box = self.add_dock("Report view", floating=True)   # made later, by a workbench say
        self.assertTrue(late.isFloating() and late.isWindow())
        self.assertTrue(focus_on(late_box), QtWidgets.QApplication.focusWidget())
        self.assertEqual(self.orientation._filtered, [window, late], "its widget took focus")
        self.assertTrue(override_accepted(late_box, space_event()), "its check box gets Space")
        other_box = QtWidgets.QCheckBox("elsewhere", window)
        self.assertTrue(focus_on(other_box))
        self.assertTrue(focus_on(late_box))
        self.assertEqual(self.orientation._filtered, [window, late], "once")
        self.assertEqual(len(space_filters(window)), 1, "still one filter")
        self.orientation.uninstall()
        self.assertEqual(self.orientation._filtered, [])
        self.assertTrue(focus_on(late_box))
        self.assertFalse(override_accepted(late_box, space_event()), "removed from the late dock too")
        self.assertEqual(self.lines(), [])

    def test_focus_outside_a_dock_adds_no_filter(self):
        window = STUBS.main_window
        self.orientation.install()
        box = QtWidgets.QCheckBox("in the main window", window)
        self.assertTrue(focus_on(box))
        dialog = QtWidgets.QDialog(window)
        self.addCleanup(dialog.close)
        dialog_box = QtWidgets.QCheckBox("in a dialog", dialog)
        self.assertTrue(focus_on(dialog_box))
        loose = QtWidgets.QWidget()                 # another top-level window
        self.addCleanup(loose.close)
        loose_box = QtWidgets.QCheckBox("loose", loose)
        self.assertTrue(focus_on(loose_box))
        self.orientation._focus_changed(box, None)  # focus left the application
        self.assertEqual(self.orientation._filtered, [window], "only docks are added")
        self.assertEqual(self.lines(), [])

    def test_focus_changes_after_uninstall_add_nothing(self):
        self.orientation.install()
        self.orientation.uninstall()
        late, late_box = self.add_dock("Selection view", floating=True)
        self.assertTrue(focus_on(late_box))
        self.orientation._focus_changed(None, late_box)
        self.assertEqual(self.orientation._filtered, [])
        self.assertIsNone(self.orientation._space_filter)
        self.assertFalse(override_accepted(late_box, space_event()))
        self.assertEqual(self.lines(), [])

    def test_uninstall_disconnects_the_focus_watch(self):
        """After uninstall Qt no longer calls _focus_changed: with a filter object put back by
        hand, a dock taking focus is still not added."""
        o = self.orientation
        o.install()
        o.uninstall()
        stand_in = QtCore.QObject()
        self.patch(o, "_space_filter", stand_in)
        self.addCleanup(o._filtered.clear)
        late, late_box = self.add_dock("Python console", floating=True)
        self.assertTrue(focus_on(late_box))
        self.assertEqual(o._filtered, [], "nothing calls _focus_changed any more")
        o._focus_changed(None, late_box)            # called by hand, it would add the dock
        self.assertEqual(o._filtered, [late])
        late.removeEventFilter(stand_in)

    def test_space_filter_asks_qt_which_widget_is_under_the_pointer(self):
        window = STUBS.main_window
        mdi = window.centralWidget()
        view3d = qt_class(CLASS_VIEW3D, QtWidgets.QWidget)()
        view3d.setMinimumSize(300, 200)
        sub_window = mdi.addSubWindow(view3d)
        sub_window.show()
        _dock, box = self.add_dock("Tasks")
        self.orientation.install()
        self.assertTrue(focus_on(box))
        self.point_at(box)
        self.assertTrue(override_accepted(box, space_event()), "pointer over the task panel: the check box")
        self.point_at(view3d)
        self.assertIs(QtWidgets.QApplication.focusWidget(), box, "the check box still has the keyboard")
        self.assertFalse(override_accepted(box, space_event()), "pointer over the 3D view: the panel")
        self.assertFalse(box.isChecked())

    # colors -----------------------------------------------------------------------------------------
    def test_stylesheet_gives_every_button_state_its_own_colors(self):
        palette = self.module("jellyjams.palette")
        panel_id = "#" + self.orientation.OBJ_PANEL
        declared = {}
        for selector, declarations in qss_rules(self.orientation._style()):
            values = dict(part.split(":", 1) for part in declarations)
            for single in selector.split(","):
                declared.setdefault(" ".join(single.split()), {}).update(
                    {name.strip(): value.strip() for name, value in values.items()})
        self.assertEqual(declared[panel_id]["background"], palette.PANEL)
        for state, color in (("", palette.TEXT), (":hover", palette.TEXT), (":pressed", palette.TEXT),
                             (":checked", palette.TEXT), (":disabled", palette.TEXT_DISABLED)):
            with self.subTest(state=state or "normal"):
                rule = declared.get("%s QToolButton%s" % (panel_id, state), {})
                self.assertEqual(rule.get("color"), color)
                self.assertIn("background", rule, "a background of its own in this state too")
        self.assertEqual(declared["%s QLabel" % panel_id].get("color"), palette.TEXT)

    def test_panel_text_follows_dark_theme_and_stays_readable(self):
        palette = self.module("jellyjams.palette").widget_colors(dark=True)
        app = STUBS.qapp
        self.addCleanup(app.setStyleSheet, app.styleSheet())
        app.setStyleSheet("* { color: #ffffff; background: #202020; }")   # as FreeCAD's dark themes do
        STUBS.set_commands([cmd for cmd in ORIENTATION_COMMANDS if cmd != "Std_ViewDimetric"])
        self.orientation.open_at_cursor()
        STUBS.pump(20)
        role = QtGui.QPalette.ColorRole
        pin = self.panel().pin_button
        pin.ensurePolished()
        self.assertEqual(pin.palette().color(role.ButtonText).name(), palette.TEXT)
        self.assertEqual(pin.palette().color(QtGui.QPalette.ColorGroup.Disabled, role.ButtonText).name(),
                         palette.TEXT_DISABLED)
        missing = self.buttons()["Std_ViewDimetric"]
        missing.ensurePolished()
        self.assertFalse(missing.isEnabled())
        self.assertEqual(missing.palette().color(QtGui.QPalette.ColorGroup.Disabled, role.ButtonText).name(),
                         palette.TEXT_DISABLED)
        title = [label for label in self.panel().findChildren(QtWidgets.QLabel) if label.objectName() == "title"]
        self.assertEqual(len(title), 1)
        title[0].ensurePolished()
        self.assertEqual(title[0].palette().color(role.WindowText).name(), palette.TEXT)
        pin.setChecked(True)
        rendered = pin.grab().toImage()
        self.assertTrue(any(rendered.pixelColor(x, y).lightness() > 180
                            for x in range(rendered.width()) for y in range(rendered.height())),
                        "the checked Pin shows light text on its dark background")

    def test_leaving_jellyjams_closes_the_panel(self):
        lifecycle = self.module("jellyjams.lifecycle", fresh=True)
        self.addCleanup(lambda: importlib.reload(sys.modules["jellyjams.lifecycle"]))
        calls = []
        modules = _area_fakes(calls, lifecycle)
        modules.pop("jellyjams.orientation")       # the real module takes part
        seen = {}
        modules["jellyjams.naming"].disable = lambda: seen.setdefault("naming", self.orientation.is_open())
        modules["jellyjams.ribbon"].hide = lambda: seen.setdefault("ribbon", self.orientation.is_open())
        with fake_modules(modules):
            lifecycle.activated()
            self.assertEqual(len(space_filters(STUBS.main_window)), 1, "activation installs the Space filter")
            self.orientation.open_at_cursor()
            self.assertTrue(self.orientation.is_open())
            lifecycle.deactivated()
        self.assertFalse(self.orientation.is_open())
        self.assertIsNone(self.orientation._space_filter, "deactivation removes it")
        self.assertEqual(seen, {"naming": True, "ribbon": False}, "closed after naming, before the ribbon hides")
        self.assertEqual(self.jj("error"), [])

    # icons and placement ----------------------------------------------------------------------------
    def test_fallback_icons_when_freecad_has_none(self):
        self.orientation.open_at_cursor()
        buttons = self.buttons()
        for cmd, name in ORIENTATION_FALLBACK_ICONS.items():
            with self.subTest(cmd=cmd):
                self.assertFalse(buttons[cmd].icon().isNull())
                self.assertEqual(self.image(buttons[cmd].icon()), self.svg_image(name))
        self.assertEqual(self.image(buttons[NORMAL_TO_CMD].icon()), self.svg_image("normal_to"))
        self.assertTrue(buttons["Std_ViewTop"].icon().isNull(), "the stub has no FreeCAD icons")

    def test_freecad_icon_wins_over_the_fallback(self):
        icons = self.module("jellyjams.icons")
        own = QtGui.QIcon(os.path.join(ICONS_DIR, "orientation.svg"))
        self.patch(icons, "command_icon", lambda cmd_id, *args, **kwargs: own)
        self.orientation.open_at_cursor()
        for cmd in ORIENTATION_FALLBACK_ICONS:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.image(self.buttons()[cmd].icon()), self.image(own))

    def test_placement_next_to_the_pointer_and_on_screen(self):
        area = QtCore.QRect(0, 0, 1000, 700)
        screen = types.SimpleNamespace(availableGeometry=lambda: area)
        size = QtCore.QSize(200, 150)
        offset = self.orientation.CURSOR_OFFSET_PX
        cases = [
            ("middle", QtCore.QPoint(100, 100), screen, (100 + offset, 100 + offset)),
            ("bottom right corner", QtCore.QPoint(990, 690), screen, (999 - 200, 699 - 150)),
            ("off the left edge", QtCore.QPoint(-50, 300), screen, (0, 300 + offset)),
            ("no screen at the pointer", QtCore.QPoint(100, 100), None, (100 + offset, 100 + offset)),
        ]
        for label, pointer, at, expected in cases:
            with self.subTest(label):
                fake_gui = types.SimpleNamespace(
                    QCursor=types.SimpleNamespace(pos=lambda _p=pointer: QtCore.QPoint(_p)),
                    QGuiApplication=types.SimpleNamespace(screenAt=lambda _pos, _s=at: _s,
                                                          primaryScreen=lambda: screen))
                point = self.orientation._placement(QtCore, fake_gui, size)
                self.assertEqual((point.x(), point.y()), expected)
                self.assertTrue(area.contains(QtCore.QRect(point, size)))


# --------------------------------------------------------------------------
# Appearance library and safe targeting
# --------------------------------------------------------------------------


class Test25Appearances(DocumentCase):
    def setUp(self):
        super().setUp()
        self.appearances = self.module("jellyjams.appearances", fresh=True)
        self.rules = self.module("jellyjams.appearance_rules")
        self.doc = FakeDocument("Colour")
        self.open_documents(self.doc)
        self.patch(STUBS.app, "ActiveDocument", self.doc)
        STUBS.set_active_workbench(WB)
        self.addCleanup(self.appearances.disable)

    def solid(self, name="Box", visible=True):
        return FakeObject(self.doc, name, "Part::Feature",
                          Shape=types.SimpleNamespace(Faces=[None] * 6),
                          ViewObject=types.SimpleNamespace(ShapeAppearance=["original"], Visibility=visible))

    def pick(self, obj, *subs):
        return types.SimpleNamespace(Object=obj, SubElementNames=subs)

    def test_library_and_validation(self):
        for values in self.rules.LIBRARY.values():
            for appearance in values:
                color, specular, shininess, transparency = self.rules.material_values(appearance)
                self.assertEqual(len(color), 3)
                self.assertTrue(all(0 <= value <= 1 for value in (*color, specular, shininess, transparency)))
        self.assertEqual(self.rules.rgb("#FF0080"), (1, 0, 128 / 255))
        for color in ("red", "#fff", "#1234567", "#zz0080", None):
            with self.assertRaises(ValueError):
                self.rules.rgb(color)
        for transparency in (-1, 101, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.rules.material_values(self.rules.Appearance("Bad", "#000000", transparency=transparency))

    def test_faces_deduplicate_and_never_fall_back_to_whole(self):
        obj = self.solid()
        STUBS.selection_ex = [self.pick(obj, "Face1", "Face3", "Face1", "Face7", "Edge2")]
        self.assertEqual(self.appearances.targets(), [(obj, {0, 2})])
        STUBS.selection_ex = [self.pick(obj, "Face7", "Edge2")]
        self.assertEqual(self.appearances.targets(), [])
        self.assertEqual(self.appearances.targets(1), [(obj, None)])

    def test_whole_target_dominates_faces_in_same_selection(self):
        obj = self.solid()
        STUBS.selection_ex = [self.pick(obj, "Face1"), self.pick(obj)]
        self.assertEqual(self.appearances.targets(), [(obj, None)])

    def test_component_override_stops_before_source(self):
        source = self.solid("Source")
        link = FakeObject(self.doc, "Link", "App::Link", LinkedObject=source,
                          Shape=source.Shape, ViewObject=types.SimpleNamespace(
                              ShapeMaterial="local", OverrideMaterial=False, Visibility=True))
        part = FakeObject(self.doc, "Part", "App::Part", Group=[link],
                          ViewObject=types.SimpleNamespace(Visibility=True))
        STUBS.selection_ex = [self.pick(part, "Link.Source.Face1")]
        self.assertEqual(self.appearances.targets(), [])
        self.assertEqual(self.appearances.targets(1), [(link, None)])
        STUBS.selection_ex = [self.pick(link)]
        self.assertEqual(self.appearances.targets(), [(link, None)])
        self.assertEqual(source.ViewObject.ShapeAppearance, ["original"])

    def test_component_apply_changes_only_the_selected_instance(self):
        source = self.solid("Source")
        links = [FakeObject(self.doc, name, "App::Link", LinkedObject=source,
                            Shape=source.Shape, ViewObject=types.SimpleNamespace(
                                ShapeMaterial="original", OverrideMaterial=False, Visibility=True))
                 for name in ("Selected", "Sibling")]
        STUBS.selection_ex = [self.pick(links[0])]
        self.patch(STUBS.app, "Material", types.SimpleNamespace)
        count = self.appearances.apply_appearance(
            self.rules.Appearance("Gold", "#dfbd62", "Polished", 35))
        self.assertEqual(count, 1)
        view = links[0].ViewObject
        self.assertTrue(view.OverrideMaterial)
        self.assertEqual(view.ShapeMaterial.DiffuseColor, (223 / 255, 189 / 255, 98 / 255))
        self.assertAlmostEqual(view.ShapeMaterial.Transparency, .35)
        self.assertAlmostEqual(view.ShapeMaterial.Shininess, .95)
        self.assertEqual(source.ViewObject.ShapeAppearance, ["original"])
        self.assertEqual(links[1].ViewObject.ShapeMaterial, "original")
        self.assertFalse(links[1].ViewObject.OverrideMaterial)
        self.assertEqual(self.doc.call_names(), ["openTransaction", "commitTransaction"])

    def test_component_material_list_on_new_hosts_preserves_source_and_sibling(self):
        source = self.solid("Source")
        links = [FakeObject(self.doc, name, "App::Link", LinkedObject=source,
                            Shape=source.Shape, ViewObject=types.SimpleNamespace(
                                ShapeAppearance=["original"], OverrideMaterial=False, Visibility=True))
                 for name in ("Selected", "Sibling")]
        STUBS.selection_ex = [self.pick(links[0])]
        self.patch(STUBS.app, "Material", types.SimpleNamespace)
        self.assertEqual(self.appearances.apply_appearance(self.rules.Appearance("Red", "#ff0000")), 1)
        self.assertTrue(links[0].ViewObject.OverrideMaterial)
        self.assertEqual(links[0].ViewObject.ShapeAppearance[0].DiffuseColor, (1, 0, 0))
        self.assertEqual(source.ViewObject.ShapeAppearance, ["original"])
        self.assertEqual(links[1].ViewObject.ShapeAppearance, ["original"])
        self.assertFalse(links[1].ViewObject.OverrideMaterial)

    def test_empty_selection_targets_only_visible_models(self):
        visible = self.solid("Visible")
        self.solid("Hidden", False)
        self.assertEqual(self.appearances.targets(), [(visible, None)])
        other = FakeDocument("Other")
        foreign = FakeObject(other, "Visible", "Part::Feature")
        STUBS.selection_ex = [self.pick(foreign)]
        self.assertEqual(self.appearances.targets(), [], "foreign selection must not colour active model")
        STUBS.set_active_dialog(object())
        self.assertEqual(self.appearances.targets(2), [])

    def test_failed_selection_query_never_colours_the_entire_model(self):
        obj = self.solid()

        def unavailable(*_args):
            raise RuntimeError("selection unavailable")

        self.patch(STUBS.gui.Selection, "getSelectionEx", unavailable)
        self.patch(STUBS.app, "Material", types.SimpleNamespace)
        for scope in (0, 1, 2):
            with self.subTest(scope=scope):
                self.assertEqual(self.appearances.targets(scope), [])
                self.assertEqual(self.appearances.apply_appearance(
                    self.rules.Appearance("Red", "#ff0000"), scope), 0)
        self.assertEqual(obj.ViewObject.ShapeAppearance, ["original"])
        self.assertEqual(self.doc.calls, [])

    def test_existing_application_transaction_is_not_joined_or_closed(self):
        obj = self.solid()
        STUBS.selection_ex = [self.pick(obj)]
        transactions = self.use_transactions()
        self.doc.transactions = transactions
        transactions.open("Another tool")
        original = transactions.active
        self.assertFalse(self.doc.HasPendingTransaction)
        with self.assertRaisesRegex(ValueError, "Finish the current edit"):
            self.appearances.apply_appearance(self.rules.Appearance("Red", "#ff0000"))
        self.assertEqual(transactions.active, original)
        self.assertEqual(transactions.closed, [])
        self.assertEqual(self.doc.calls, [])
        self.assertEqual(obj.ViewObject.ShapeAppearance, ["original"])

    def test_face_edit_preserves_other_faces_in_one_transaction(self):
        obj = self.solid()
        STUBS.selection_ex = [self.pick(obj, "Face2", "Face5")]
        self.patch(STUBS.app, "Material", types.SimpleNamespace)
        count = self.appearances.apply_appearance(self.rules.Appearance("Red", "#ff0000"))
        self.assertEqual(count, 1)
        materials = obj.ViewObject.ShapeAppearance
        self.assertEqual([index for index, value in enumerate(materials) if value == "original"], [0, 2, 3, 5])
        self.assertEqual(materials[1].DiffuseColor, (1, 0, 0))
        self.assertEqual(self.doc.call_names(), ["openTransaction", "commitTransaction"])
        self.doc.HasPendingTransaction = True
        with self.assertRaises(ValueError):
            self.appearances.apply_appearance(self.rules.Appearance("Blue", "#0000ff"))

    def test_invalid_edits_never_start_a_transaction(self):
        obj = self.solid()
        STUBS.selection_ex = [self.pick(obj)]
        with self.assertRaises(ValueError):
            self.appearances.apply_appearance(self.rules.Appearance("Bad", "invalid"))
        self.assertEqual(self.doc.calls, [])
        self.assertEqual(obj.ViewObject.ShapeAppearance, ["original"])

    def test_failed_edit_aborts_and_releases_transaction(self):
        first, second = self.solid("First"), self.solid("Second")
        STUBS.selection_ex = [self.pick(first), self.pick(second)]
        transactions = self.use_transactions()
        self.doc.transactions = transactions
        calls = []

        def material_factory():
            calls.append(None)
            if len(calls) == 2:
                raise RuntimeError("material write failed")
            return types.SimpleNamespace()

        self.patch(STUBS.app, "Material", material_factory)
        with self.assertRaisesRegex(RuntimeError, "material write failed"):
            self.appearances.apply_appearance(self.rules.Appearance("Red", "#ff0000"))
        self.assertEqual(len(calls), 2, "fail after the first target was edited")
        self.assertEqual(self.doc.call_names(), ["openTransaction", "abortTransaction"])
        self.assertIsNone(transactions.active, "a failed edit must not leave the application transaction open")
        self.assertEqual(transactions.closed, [(True, 41)])
        # The stubs verify the abort protocol, not native material rollback.
        # gui_appearances.py verifies actual restoration in real FreeCAD.

    def test_deferred_startup_creates_panel_only_while_enabled(self):
        window = STUBS.main_window
        window.hide()
        self.appearances.enable()
        self.assertIsNone(self.appearances.dock())
        self.appearances._timer.setInterval(5)
        window.show()
        self.assertTrue(STUBS.wait_until(lambda: self.appearances.dock() is not None, 1000))
        self.appearances.disable()
        window.hide()
        self.appearances.enable()
        self.appearances.disable()
        window.show()
        STUBS.pump(30)
        self.assertIsNone(self.appearances.dock(), "cancelled startup must not create a late panel")
        self.assertFalse(self.appearances._timer.isActive())
        self.assertNoJellyJamsProblems()

    def test_failed_panel_creation_is_cleaned_up_and_can_retry(self):
        original = self.appearances._AppearancePanel

        def unavailable(_parent):
            raise RuntimeError("panel construction failed")

        self.patch(self.appearances, "_AppearancePanel", unavailable)
        self.appearances.enable()
        self.assertIsNone(self.appearances.dock())
        self.assertEqual(STUBS.main_window.findChildren(
            QtWidgets.QDockWidget, "JellyJamsAppearances"), [])
        self.assertEqual(len(self.jj("error")), 1)
        self.appearances._AppearancePanel = original
        self.appearances._refresh()
        self.assertIsNotNone(self.appearances.dock())
        self.assertIsNotNone(self.appearances.dock().widget())

    def test_quit_cancel_restores_one_panel_and_preserves_closed_choice(self):
        self.appearances.enable()
        timer = self.appearances._timer
        for visible in (True, False):
            with self.subTest(visible=visible):
                self.appearances.dock().setVisible(visible)
                self.appearances.suspend_for_quit()
                self.assertIsNone(self.appearances.dock())
                self.assertFalse(timer.isActive())
                STUBS.pump(20)
                self.assertEqual(STUBS.main_window.findChildren(
                    QtWidgets.QDockWidget, "JellyJamsAppearances"), [])
                self.appearances.resume_after_cancel()
                self.appearances.resume_after_cancel()
                self.assertIs(self.appearances._timer, timer)
                self.assertTrue(timer.isActive())
                self.assertEqual(self.appearances.dock().isHidden(), not visible)
                self.assertEqual(len(STUBS.main_window.findChildren(
                    QtWidgets.QDockWidget, "JellyJamsAppearances")), 1)

    def test_panel_preview_is_read_only_and_disable_cancels_timer(self):
        obj = self.solid()
        self.appearances.enable()
        self.appearances.enable()
        panel = self.appearances.dock().widget()
        panel.gallery.setCurrentRow(5)
        panel.color.setText("#123456")
        panel.transparency.setValue(40)
        self.assertEqual(obj.ViewObject.ShapeAppearance, ["original"])
        self.assertEqual(self.doc.calls, [])
        docks = STUBS.main_window.findChildren(QtWidgets.QDockWidget, "JellyJamsAppearances")
        self.assertEqual(len(docks), 1)
        self.appearances.disable()
        self.appearances.disable()
        self.assertIsNone(self.appearances.dock())
        self.assertFalse(self.appearances._timer.isActive())
        self.assertEqual(STUBS.main_window.findChildren(QtWidgets.QDockWidget, "JellyJamsAppearances"), [])


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------



class Test39SurfaceRules(HarnessCase):
    def test_union_rejects_lost_input_and_non_finite_volume(self):
        rules = self.module("jellyjams.surface_rules")
        self.assertFalse(rules.fusion_retains_input(10717, .00000006))
        self.assertFalse(rules.fusion_retains_input(10717, float("nan")))
        self.assertTrue(rules.fusion_retains_input(10717, 10717.49))
        self.assertTrue(rules.fusion_retains_input(10717, 10716.99999))

    def test_local_edge_matching_is_orientation_independent(self):
        rules = self.module("jellyjams.surface_rules")
        self.assertEqual(rules.edge_match_score((0, 0, 0), (0, 0, 2), 2,
                                               (0, 0, 2), (0, 0, 0), 2), 0)
        self.assertGreater(rules.edge_match_score((1, 0, 0), (1, 0, 2), 2,
                                                  (0, 0, 0), (0, 0, 2), 2), .9)

    def test_control_grid_preserves_u_major_order_and_copies_input(self):
        rules = self.module("jellyjams.surface_rules")
        points = [[i, i + 1, i + 2] for i in range(6)]
        grid = rules.pole_grid(points, 2, 3)
        self.assertEqual(grid, [points[:3], points[3:]])
        grid[0][0][0] = 100
        self.assertEqual(points[0][0], 0)

    def test_control_grid_rejects_invalid_edits(self):
        rules = self.module("jellyjams.surface_rules")
        for points, rows, columns in [([], 0, 1), ([[1, 2, 3]], 2, 1),
                                       ([[1, 2]], 1, 1), ([[0, float("nan"), 2]], 1, 1),
                                       ([[0, float("inf"), 2]], 1, 1)]:
            with self.subTest(points=points, rows=rows, columns=columns):
                with self.assertRaises(ValueError):
                    rules.pole_grid(points, rows, columns)

    def test_surface_numbering_survives_multiple_solids(self):
        rules = self.module("jellyjams.surface_rules")
        data = {"version": 1, "solids": [{"faces": [{"surface": "a"}, {"surface": "b"}]},
                                          {"faces": [{"surface": "c"}]}]}
        self.assertEqual(list(rules.surfaces(data)), [(1, "a"), (2, "b"), (3, "c")])
        with self.assertRaises(ValueError):
            list(rules.surfaces({"version": 2, "solids": []}))

    def test_surface_feature_applies_control_points_without_mutating_schema(self):
        feature = self.module("jellyjams.surface_feature")
        original = {"version": 1, "solids": [{"faces": [{"surface": {
            "kind": "BSplineSurface", "poles": [[[0, 0, 0], [0, 1, 0]]], "weights": [[1, 1]]}}]}]}
        stored = json.dumps(original)
        obj = types.SimpleNamespace(GeometryDefinition=stored, Surface01Poles=[(0, 0, 1), (0, 1, 2)])
        modified = feature.definition_for(obj)
        self.assertEqual(modified["solids"][0]["faces"][0]["surface"]["poles"], [[[0., 0., 1.], [0., 1., 2.]]])
        self.assertEqual(obj.GeometryDefinition, stored)
        self.assertEqual(original["solids"][0]["faces"][0]["surface"]["weights"], [[1, 1]])


class Test40HostCompatibility(HarnessCase):
    def test_task_panel_follows_active_document_through_wrapper_even_with_hidden_dock(self):
        fcgui = self.module("jellyjams.fcgui")
        constants = self.module("jellyjams.constants")
        dock = QtWidgets.QDockWidget(STUBS.main_window)
        stack = QtWidgets.QStackedWidget()
        dock.setWidget(stack)
        panels = []
        for _ in range(2):
            wrapper = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(wrapper)
            panel = QtWidgets.QFrame()
            layout.addWidget(panel)
            stack.addWidget(wrapper)
            panels.append(panel)
        self.patch(fcgui, "task_dock", lambda: dock)
        self.patch(constants, "CLASS_TASK_PANEL", "QFrame")
        stack.setCurrentIndex(1)
        self.assertIs(fcgui.task_panel(), panels[1])
        stack.setCurrentIndex(0)
        self.assertIs(fcgui.task_panel(), panels[0])
        dock.deleteLater()

    def test_optional_native_resources_are_loaded_once_before_command_modules(self):
        fcgui = self.module("jellyjams.fcgui")
        constants = self.module("jellyjams.constants")
        calls = []
        self.patch(fcgui, "_preloaded", None)
        self.patch(fcgui.importlib, "import_module", lambda name: calls.append(name))
        self.assertEqual(fcgui.preload_command_modules(), ([], []))
        self.assertEqual(fcgui.preload_command_modules(), ([], []))
        self.assertEqual(calls, list(constants.OPTIONAL_GUI_COMMAND_MODULES
                                    + constants.GUI_COMMAND_MODULES + constants.ASSEMBLY_COMMAND_MODULES))

    def test_missing_optional_resource_is_normal_but_broken_dependency_is_reported(self):
        fcgui = self.module("jellyjams.fcgui")
        def load(name):
            if name == "AssemblyGui":
                raise ModuleNotFoundError("not installed", name=missing[0])
        self.patch(fcgui.importlib, "import_module", load)
        for dependency, errors in (("AssemblyGui", 0), ("internal_dependency", 1)):
            missing = [dependency]
            self.patch(fcgui, "_preloaded", None)
            self.assertEqual(len(fcgui.preload_command_modules()[0]), errors)


class Test40QuickAccess(HarnessCase):
    def setUp(self):
        super().setUp()
        self.quick = self.module("jellyjams.quick_access")
        self.quick.disable()
        self.addCleanup(self.quick.disable)
        STUBS.set_active_workbench(WB)
        STUBS.set_commands(sorted(ribbon_command_ids()))
        STUBS.app.ActiveDocument = types.SimpleNamespace(Name="A", Uid="first")
        self.fcgui = self.module("jellyjams.fcgui")
        self.rules = self.module("jellyjams.access_rules")

    def test_context_memory_restores_manual_tabs_per_document_and_mode(self):
        memory = self.rules.ContextMemory()
        self.assertEqual(memory.choose("A", "Features", "Drawing"), "Features")
        self.assertIsNone(memory.choose("A", "Features", "Evaluate"))
        self.assertEqual(memory.choose("A", "Sketch", "Evaluate"), "Sketch")
        self.assertEqual(memory.choose("B", "Features", "Sketch"), "Features")
        self.assertEqual(memory.choose("A", "Features", "Features"), "Evaluate")
        self.assertEqual(memory.choose("A", "Sketch", "Evaluate"), "Sketch")

    def test_search_matches_unordered_words_and_native_names(self):
        for query in ("boss extrude", "BASE boss", "pad", ""):
            self.assertTrue(self.rules.matches(query, "Extruded Boss/Base", "PartDesign_Pad"))
        self.assertFalse(self.rules.matches("cut", "Extruded Boss/Base", "PartDesign_Pad"))

    def test_new_sketch_entry_always_selects_sketch_after_manual_feature_tab(self):
        memory = self.rules.ContextMemory()
        memory.choose("A", "Features", "Drawing")
        memory.choose("A", "Sketch", "Evaluate")
        self.assertEqual(memory.choose("A", "Features", "Features"), "Evaluate")
        self.assertEqual(memory.choose("A", "Sketch", "Evaluate"), "Sketch")

    def test_typing_focus_protects_editors_and_list_search(self):
        for kind in (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit,
                     QtWidgets.QSpinBox, QtWidgets.QComboBox, QtWidgets.QListWidget):
            widget = kind()
            self.addCleanup(widget.deleteLater)
            self.assertTrue(self.quick.typing_focus(widget), kind)
        self.assertFalse(self.quick.typing_focus(QtWidgets.QPushButton()))
        self.assertFalse(self.quick.typing_focus(None))

    def test_drawing_sketch_restores_drawing_after_native_view_mode_changes(self):
        memory = self.rules.ContextMemory()
        memory.choose("A", "Drawing", "Features")
        self.assertEqual(memory.choose("A", "Sketch", "Drawing"), "Sketch")
        self.assertEqual(memory.choose("A", "Features", "Features"), "Drawing")
        memory.choose("A", "Sketch", "Evaluate")
        memory.choose("B", "Features", "Features")
        self.assertEqual(memory.choose("A", "Features", "Assembly"), "Evaluate")

    def resolved(self):
        return self.module("jellyjams.ribbon_model").resolve(
            self.module("jellyjams.ribbon_layout").TABS, ribbon_command_ids())

    def test_catalog_contains_variants_unique_ids_and_correct_toggle(self):
        catalog = self.quick.catalog(self.resolved(), "Sketch", True)
        ids = [entry.entry_id for _title, entry in catalog]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(catalog[0][0], "Sketch")
        self.assertIn("Sketcher_LeaveSketch", ids)
        self.assertNotIn("PartDesign_NewSketch", ids)
        self.assertIn("Sketcher_CreateBSpline", ids)

    def popup(self):
        popup = self.quick.SearchPopup(STUBS.main_window, self.resolved())
        self.addCleanup(popup.deleteLater)
        return popup

    def test_search_popup_finds_native_pad_and_dispatches_through_ribbon(self):
        popup = self.popup()
        popup.search.setText("pad")
        entries = [popup.results.item(i).data(QtCore.Qt.ItemDataRole.UserRole).cmd
                   for i in range(popup.results.count())]
        self.assertIn("PartDesign_Pad", entries)
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        popup.choose()
        STUBS.pump(20)
        self.assertEqual(calls, [("PartDesign_Pad", None)])

    def test_search_popup_rejects_changed_document(self):
        popup = self.popup()
        popup.search.setText("pad")
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        STUBS.app.ActiveDocument = types.SimpleNamespace(Name="B", Uid="second")
        popup.choose()
        STUBS.pump(20)
        self.assertEqual(calls, [])

    def test_popup_activation_dispatches_only_once(self):
        popup = self.popup()
        popup.search.setText("pad")
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        popup.choose()
        popup.choose()
        STUBS.pump(20)
        self.assertEqual(calls, [("PartDesign_Pad", None)])

    def test_queued_dispatch_rechecks_mode_and_command_availability(self):
        popup = self.popup()
        popup.search.setText("pad")
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        popup.choose()
        self.patch(self.module("jellyjams.ribbon_widgets"), "command_is_active", lambda _cmd: False)
        STUBS.pump(20)
        self.assertEqual(calls, [])

    def test_search_popup_rechecks_availability(self):
        popup = self.popup()
        popup.search.setText("pad")
        self.patch(self.module("jellyjams.ribbon_widgets"), "command_is_active", lambda _cmd: False)
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        popup.choose()
        STUBS.pump(20)
        self.assertEqual(calls, [])

    def test_queued_dispatch_rechecks_workbench_and_document(self):
        popup = self.popup()
        popup.search.setText("pad")
        calls = []
        self.patch(self.module("jellyjams.ribbon"), "run_entry", lambda *args: calls.append(args))
        popup.choose()
        STUBS.set_active_workbench("PartDesignWorkbench")
        STUBS.pump(20)
        self.assertEqual(calls, [])

    def native_task(self):
        dock = QtWidgets.QDockWidget(STUBS.main_window)
        panel = QtWidgets.QWidget(dock)
        panel.setObjectName("NativeTask")
        dock.setWidget(panel)
        form = QtWidgets.QWidget(panel)
        form.setObjectName("NativeForm")
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel, panel)
        self.addCleanup(dock.deleteLater)
        self.patch(self.fcgui, "task_dialog_open", lambda: True)
        self.patch(self.fcgui, "task_panel", lambda: panel)
        self.patch(self.fcgui, "task_dock", lambda: dock)
        self.patch(self.fcgui, "sketch_in_edit", lambda: None)
        return dock, panel, form, box

    def test_confirmation_calls_native_button_and_checks_disabled_state(self):
        dock, panel, form, box = self.native_task()
        button = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        calls = []
        button.clicked.connect(lambda: calls.append(True))
        token, actions = self.quick.task_state()
        self.assertEqual([name for name, _ in actions], ["OK", "Cancel"])
        self.assertTrue(self.quick.confirm(token, "OK"))
        self.assertEqual(calls, [True])
        button.setEnabled(False)
        self.assertFalse(self.quick.confirm(token, "OK"))
        self.assertEqual(calls, [True])

    def test_confirmation_rejects_replaced_form_document_and_closed_task(self):
        dock, panel, form, box = self.native_task()
        token, _actions = self.quick.task_state()
        other = QtWidgets.QWidget(panel)
        other.setObjectName("ReplacementForm")
        self.assertFalse(self.quick.confirm(token, "OK"))
        other.setParent(None)
        other.deleteLater()
        STUBS.app.ActiveDocument = types.SimpleNamespace(Name="B", Uid="second")
        self.assertFalse(self.quick.confirm(token, "OK"))
        self.patch(self.fcgui, "task_dialog_open", lambda: False)
        self.assertFalse(self.quick.confirm(token, "OK"))

    def test_sketch_confirmation_offers_exit_without_fake_cancel(self):
        self.native_task()
        self.patch(self.fcgui, "sketch_in_edit", lambda: types.SimpleNamespace(Name="Sketch"))
        token, actions = self.quick.task_state()
        self.assertEqual(actions, [("Exit Sketch", None)])
        calls = []
        self.patch(STUBS.gui, "runCommand", lambda cmd: calls.append(cmd))
        self.assertFalse(self.quick.confirm(token, "Cancel"))
        self.assertTrue(self.quick.confirm(token, "Exit Sketch"))
        self.assertEqual(calls, ["Sketcher_LeaveSketch"])

    def test_foreign_document_native_task_never_offers_confirmation(self):
        self.native_task()
        owner = [STUBS.app.ActiveDocument.Name]
        dialog = types.SimpleNamespace(getDocumentName=lambda: owner[0])
        self.patch(STUBS.gui.Control, "activeTaskDialog", lambda: dialog)
        self.assertIsNotNone(self.quick.task_state()[0])
        owner[0] = "AnotherDocument"
        self.assertEqual(self.quick.task_state(), (None, []))
        self.patch(STUBS.gui.Control, "activeTaskDialog", lambda: None)
        self.assertEqual(self.quick.task_state(), (None, []))

    def test_service_idempotency_cleanup_and_no_shortcut_parameter_writes(self):
        before = STUBS.app.ParamGet(P_SHORTCUT).GetContents()
        self.quick.enable()
        service = self.quick._service
        self.quick.enable()
        self.assertIs(service, self.quick._service)
        self.quick.disable()
        self.quick.disable()
        self.assertIsNone(self.quick._service)
        self.assertFalse(service.timer.isActive())
        self.assertEqual(service.targets, [])
        self.assertEqual(STUBS.app.ParamGet(P_SHORTCUT).GetContents(), before)

    def test_key_filter_claims_plain_letters_but_preserves_text_modifiers_and_repeat(self):
        service = self.quick.AccessService(STUBS.main_window)
        service.timer.stop()
        self.addCleanup(service.stop)
        calls = []
        self.patch(service, "show_search", lambda: calls.append("S"))
        self.patch(service, "show_confirmation", lambda: calls.append("D"))
        button = QtWidgets.QPushButton()
        self.addCleanup(button.deleteLater)
        self.patch(QtWidgets.QApplication, "focusWidget", staticmethod(lambda: button))
        for letter in (QtCore.Qt.Key.Key_S, QtCore.Qt.Key.Key_D):
            override = QtGui.QKeyEvent(QtCore.QEvent.Type.ShortcutOverride, letter,
                                      QtCore.Qt.KeyboardModifier.NoModifier)
            self.assertTrue(service.eventFilter(STUBS.main_window, override))
            press = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, letter,
                                   QtCore.Qt.KeyboardModifier.NoModifier)
            self.assertTrue(service.eventFilter(STUBS.main_window, press))
        self.assertEqual(calls, ["S", "D"])
        modified = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_S,
                                  QtCore.Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(service.eventFilter(STUBS.main_window, modified))
        repeated = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_S,
                                  QtCore.Qt.KeyboardModifier.NoModifier, "s", True)
        self.assertTrue(service.eventFilter(STUBS.main_window, repeated))
        self.assertEqual(calls, ["S", "D"])
        edit = QtWidgets.QLineEdit()
        self.addCleanup(edit.deleteLater)
        self.patch(QtWidgets.QApplication, "focusWidget", staticmethod(lambda: edit))
        self.assertFalse(service.eventFilter(STUBS.main_window, press))

    def test_confirmation_leaves_modal_input_and_other_workbenches_alone(self):
        self.native_task()
        token, _actions = self.quick.task_state()
        dialog = QtWidgets.QDialog()
        self.addCleanup(dialog.deleteLater)
        self.patch(QtWidgets.QApplication, "activeModalWidget", staticmethod(lambda: dialog))
        self.assertFalse(self.quick.confirm(token, "OK"))
        self.patch(QtWidgets.QApplication, "activeModalWidget", staticmethod(lambda: None))
        STUBS.set_active_workbench("PartDesignWorkbench")
        self.assertFalse(self.quick.confirm(token, "OK"))


def main():
    faulthandler.enable()
    faulthandler.dump_traceback_later(WATCHDOG_SECONDS, exit=True)
    started = time.monotonic()
    program = unittest.main(module=__name__, argv=[sys.argv[0]] + sys.argv[1:], exit=False,
                            verbosity=2 if "-q" not in sys.argv[1:] else 1)
    result = program.result
    sys.stdout.write("\nJellyJams headless harness: %d tests, %d failures, %d errors, %d skipped in %.1f s (%s)\n" % (
        result.testsRun, len(result.failures), len(result.errors), len(result.skipped),
        time.monotonic() - started, STUBS.pyside_source))
    code = 0 if result.wasSuccessful() else 1
    sys.stdout.flush()
    sys.stderr.flush()
    shutil.rmtree(STUBS.user_dir, ignore_errors=True)
    # Skip interpreter finalization: tearing down Qt objects at exit can crash and
    # would turn a clean run into a non-zero exit code. On Windows os._exit still unloads
    # the Qt and PySide DLLs, whose clean-up can crash the same way; TerminateProcess
    # ends the process without it.
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    os._exit(code)


if __name__ == "__main__":
    main()
