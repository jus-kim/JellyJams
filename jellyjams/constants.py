# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Names, ids and keys shared across JellyJams.

Other modules import these literals from here rather than repeating them.
No imports at all.
"""

MEASURE_COMMAND = "Std_Measure"

ADDON_NAME = "JellyJams"
WORKBENCH_KEY = "JellyJamsWorkbench"
MENU_TEXT = "JellyJams"
MENU_NAME = "JellyJams"
WORKBENCH_TOOLTIP = "FreeCAD with a SolidWorks-style interface"
LOG_PREFIX = "JellyJams: "

# --- parameter groups -----------------------------------------------------------------
PARAM_ROOT = "User parameter:BaseApp/Preferences/Mod/JellyJams"
PARAM_RIBBON = PARAM_ROOT + "/FlyoutChoices"
PARAM_VIEW = "User parameter:BaseApp/Preferences/View"
PARAM_SHORTCUT = "User parameter:BaseApp/Preferences/Shortcut"
PARAM_ASSEMBLY = "User parameter:BaseApp/Preferences/Mod/Assembly"
PARAM_PARTDESIGN = "User parameter:BaseApp/Preferences/Mod/PartDesign"
PARAM_TECHDRAW_GENERAL = "User parameter:BaseApp/Preferences/Mod/TechDraw/General"
PARAM_TECHDRAW_REZ = "User parameter:BaseApp/Preferences/Mod/TechDraw/Rez"
PARAM_TECHDRAW_FILES = "User parameter:BaseApp/Preferences/Mod/TechDraw/Files"
PARAM_DOCUMENT = "User parameter:BaseApp/Preferences/Document"
PARAM_GENERAL = "User parameter:BaseApp/Preferences/General"

# --- keys in PARAM_ROOT ---------------------------------------------------------------
KEY_QT_FILTER = "SilenceGlyphWarnings"
KEY_CONTEXT_SKETCH = "ShowSketchButtonOnFace"
# Stored in user.cfg: renaming a backup key would orphan backups that already exist.
KEY_VIEW_BACKUP = "OriginalViewColors"
KEY_NAV_BACKUP = "OriginalNavigationStyle"
KEY_SHORTCUT_BACKUP = "OriginalShortcuts"
KEY_ASSEMBLY_BACKUP = "OriginalSwitchToWB"
KEY_PARTDESIGN_BACKUP = "OriginalPartDesignSwitchToWB"
KEY_TECHDRAW_BACKUP = "OriginalTechDrawSwitchToWB"
KEY_NOTE_HEIGHT = "LastNoteHeight"
KEY_NOTE_UNIT = "LastNoteUnit"
BACKUP_KEYS = (KEY_VIEW_BACKUP, KEY_NAV_BACKUP, KEY_SHORTCUT_BACKUP, KEY_ASSEMBLY_BACKUP,
               KEY_PARTDESIGN_BACKUP, KEY_TECHDRAW_BACKUP)

# --- theme markers --------------------------------------------------------------------
THEME_BEGIN = "/* @jellyjams-stylesheet-open */"
THEME_END = "/* @jellyjams-stylesheet-close */"

# --- JellyJams objectNames ------------------------------------------------------------
# Every objectName JellyJams sets is "JellyJams" followed by a role word; per-command
# widgets add "-" and the ribbon entry id.
OBJ_PREFIX = "JellyJams"
OBJ_RIBBON = "JellyJamsCommandManager"
OBJ_RIBBON_TABS = "JellyJamsCommandManagerTabs"
OBJ_RIBBON_STACK = "JellyJamsToolStack"
OBJ_RIBBON_SEPARATOR = "JellyJamsGroupDivider"
OBJ_BTN_PREFIX = "JellyJamsButton-"
OBJ_FLY_PREFIX = "JellyJamsFlyout-"
OBJ_TOG_PREFIX = "JellyJamsToggle-"
OBJ_PANEL = "JellyJamsPropertyManager"
OBJ_PANEL_TITLE = "JellyJamsPropertyManagerTitle"
OBJ_PANEL_HEADING = "JellyJamsSectionCaption"
OBJ_PANEL_LIST = "JellyJamsItemList"
OBJ_PANEL_DOCK = "JellyJamsPropertyManagerDock"
OBJ_CONTEXT_TOOLBAR = "JellyJamsContextToolbar"
OBJ_LINE_WIDTH_PRESETS = "JellyJamsLineWidthPresets"
OBJ_SHEET_PROPERTIES = "JellyJamsSheetPropertiesForm"
OBJ_PICTURE_FORM = "JellyJamsPictureForm"
OBJ_SURFACE_FINISH = "JellyJamsSurfaceFinishForm"
OBJ_WELD_SYMBOL = "JellyJamsWeldSymbolForm"
OBJ_DIAGNOSTICS_DIALOG = "JellyJamsDiagnosticsDialog"
OBJ_NOTE_DIALOG = "JellyJamsNoteDialog"
OBJ_SCALE_MENU = "JellyJamsViewScaleMenu"
OBJ_APPEARANCES = "JellyJamsAppearances"

# --- FreeCAD Qt names -----------------------------------------------------------------
DOCK_TASKS = "Tasks"
TASK_DOCK_CANDIDATES = ("Tasks", "TaskView", "TaskList", "Task")
DOCK_REPORT = "Report view"
MODEL_DOCK_CANDIDATES = ("Model", "Combo View", "Tree view")
KEPT_TOOLBAR_WORDS = ("File", "Edit", "Workbench")
CLASS_TASK_PANEL = "Gui::TaskView::TaskPanel"
CLASS_SHEET_WINDOW = "TechDrawGui::MDIViewPage"
CLASS_VIEW3D = "Gui::View3DInventor"
CLASS_VIEWER3D = "Gui::View3DInventorViewer"

# --- FreeCAD type ids used in several areas -------------------------------------------
TYPE_SKETCH = "Sketcher::SketchObject"
TYPE_ASSEMBLY = "Assembly::AssemblyObject"
TYPE_ASSEMBLY_LINK = "Assembly::AssemblyLink"
TYPE_JOINT_GROUP = "Assembly::JointGroup"
TYPE_LINK = "App::Link"
TYPE_PART = "App::Part"
TYPE_BODY = "PartDesign::Body"
TYPE_PART_FEATURE = "Part::Feature"
TYPE_GROUP = "App::DocumentObjectGroup"
TYPE_PAGE = "TechDraw::DrawPage"
TYPE_TEMPLATE = "TechDraw::DrawSVGTemplate"
TYPE_PROJ_GROUP = "TechDraw::DrawProjGroup"
TYPE_PROJ_ITEM = "TechDraw::DrawProjGroupItem"
TYPE_VIEW_PART = "TechDraw::DrawViewPart"
TYPE_VIEW_SECTION = "TechDraw::DrawViewSection"
TYPE_COMPLEX_SECTION = "TechDraw::DrawComplexSection"
TYPE_VIEW_DETAIL = "TechDraw::DrawViewDetail"
TYPE_BROKEN_VIEW = "TechDraw::DrawBrokenView"
TYPE_ANNOTATION = "TechDraw::DrawViewAnnotation"
TYPE_SYMBOL = "TechDraw::DrawViewSymbol"
TYPE_IMAGE = "TechDraw::DrawViewImage"
TYPE_DIMENSION = "TechDraw::DrawViewDimension"
TYPE_BALLOON = "TechDraw::DrawViewBalloon"
TYPE_LEADER = "TechDraw::DrawLeaderLine"

# --- JellyJams command ids ------------------------------------------------------------
# "JellyJams_" followed by the tool's ribbon name without spaces; the five sketch
# shapes for the drawing sheet end in "OnSheet".
CMD_PREFIX = "JellyJams_"
CMD_DIAGNOSTICS = "JellyJams_Diagnostics"
CMD_CENTERLINE = "JellyJams_Centerline"
CMD_MIDPOINT_LINE = "JellyJams_MidpointLine"
CMD_NEW_ASSEMBLY = "JellyJams_NewAssembly"
CMD_ROTATE_COMPONENT = "JellyJams_RotateComponent"
CMD_MAKE_DRAWING = "JellyJams_MakeDrawing"
CMD_SHEET_PROPERTIES = "JellyJams_SheetProperties"
CMD_INSERT_PICTURE = "JellyJams_InsertPicture"
CMD_PROJECTED_VIEW = "JellyJams_ProjectedView"
CMD_VIEW_SCALE = "JellyJams_ViewScale"
CMD_SURFACE_FINISH = "JellyJams_SurfaceFinish"
CMD_WELD_SYMBOL = "JellyJams_WeldSymbol"
CMD_LINE_FORMAT = "JellyJams_LineFormat"
CMD_SHEET_LINE = "JellyJams_LineOnSheet"
CMD_SHEET_RECTANGLE = "JellyJams_CornerRectangleOnSheet"
CMD_SHEET_CIRCLE = "JellyJams_CircleOnSheet"
CMD_SHEET_ARC = "JellyJams_CenterpointArcOnSheet"
CMD_SHEET_POLYGON = "JellyJams_PolygonOnSheet"
CMD_NOTE = "JellyJams_Note"
CMD_SAVE_PDF = "JellyJams_SaveAsPDF"
CMD_SAVE_DXF = "JellyJams_SaveAsDXF"
CMD_ORIENTATION = "JellyJams_ViewOrientation"
CMD_NORMAL_TO = "JellyJams_NormalTo"
CMD_APPEARANCES = "JellyJams_Appearances"
ALL_COMMANDS = (
    CMD_DIAGNOSTICS,
    CMD_CENTERLINE,
    CMD_MIDPOINT_LINE,
    CMD_NEW_ASSEMBLY,
    CMD_ROTATE_COMPONENT,
    CMD_MAKE_DRAWING,
    CMD_SHEET_PROPERTIES,
    CMD_INSERT_PICTURE,
    CMD_PROJECTED_VIEW,
    CMD_VIEW_SCALE,
    CMD_SURFACE_FINISH,
    CMD_WELD_SYMBOL,
    CMD_LINE_FORMAT,
    CMD_SHEET_LINE,
    CMD_SHEET_RECTANGLE,
    CMD_SHEET_CIRCLE,
    CMD_SHEET_ARC,
    CMD_SHEET_POLYGON,
    CMD_NOTE,
    CMD_SAVE_PDF,
    CMD_SAVE_DXF,
    CMD_ORIENTATION,
    CMD_NORMAL_TO,
    CMD_APPEARANCES,
)

# --- icon base names in resources/icons (".svg") --------------------------------------
WORKBENCH_ICON = "jellyjams"
COMMAND_ICONS = {
    CMD_DIAGNOSTICS: "diagnostics",
    CMD_CENTERLINE: "centerline",
    CMD_MIDPOINT_LINE: "midpoint_line",
    CMD_NEW_ASSEMBLY: "new_assembly",
    CMD_ROTATE_COMPONENT: "rotate_component",
    CMD_MAKE_DRAWING: "make_drawing",
    CMD_SHEET_PROPERTIES: "sheet_properties",
    CMD_INSERT_PICTURE: "insert_picture",
    CMD_PROJECTED_VIEW: "projected_view",
    CMD_VIEW_SCALE: "view_scale",
    CMD_SURFACE_FINISH: "surface_finish",
    CMD_WELD_SYMBOL: "weld_symbol",
    CMD_LINE_FORMAT: "line_format",
    CMD_SHEET_LINE: "sheet_line",
    CMD_SHEET_RECTANGLE: "sheet_rectangle",
    CMD_SHEET_CIRCLE: "sheet_circle",
    CMD_SHEET_ARC: "sheet_arc",
    CMD_SHEET_POLYGON: "sheet_polygon",
    CMD_ORIENTATION: "orientation",
    CMD_NORMAL_TO: "normal_to",
    CMD_APPEARANCES: "appearances",
    CMD_NOTE: "sheet_text",
    CMD_SAVE_PDF: "export_pdf",
    CMD_SAVE_DXF: "export_dxf",
}
RELATION_ICONS = {
    "Collinear": "relation_collinear",
    "Concentric": "relation_concentric",
    "Midpoint": "relation_midpoint",
}

# --- FreeCAD commands referenced by several areas -------------------------------------
PROFILE_FEATURES = (
    "PartDesign_Pad",
    "PartDesign_Pocket",
    "PartDesign_Revolution",
    "PartDesign_Groove",
    "PartDesign_Hole",
    "PartDesign_AdditivePipe",
    "PartDesign_SubtractivePipe",
    "PartDesign_AdditiveLoft",
    "PartDesign_SubtractiveLoft",
    "PartDesign_AdditiveHelix",
    "PartDesign_SubtractiveHelix",
)
# Features that start with a new sketch when pressed without a usable profile, as the
# matching SolidWorks tools do. Sweeps, lofts and helices need more than one input and
# keep FreeCAD's own behavior.
SKETCH_FIRST_FEATURES = (
    "PartDesign_Pad",
    "PartDesign_Pocket",
    "PartDesign_Revolution",
    "PartDesign_Groove",
    "PartDesign_Hole",
)
NEW_SKETCH_COMMAND = "PartDesign_NewSketch"
ACTIVE_BODY_KEY = "pdbody"   # ActiveView.getActiveObject key of FreeCAD's active PartDesign body
GUI_COMMAND_MODULES = ("PartGui", "SketcherGui", "PartDesignGui", "TechDrawGui")
ASSEMBLY_COMMAND_MODULES = (
    "CommandCreateAssembly",
    "CommandInsertLink",
    "CommandInsertNewPart",
    "CommandCreateJoint",
    "CommandSolveAssembly",
    "CommandCreateView",
    "CommandCreateSimulation",
    "CommandCreateBom",
)

# --- ribbon tabs ----------------------------------------------------------------------
TAB_FEATURES, TAB_SKETCH, TAB_EVALUATE, TAB_ASSEMBLY, TAB_DRAWING = (
    "Features",
    "Sketch",
    "Evaluate",
    "Assembly",
    "Drawing",
)
TAB_TITLES = (TAB_FEATURES, TAB_SKETCH, TAB_EVALUATE, TAB_ASSEMBLY, TAB_DRAWING)
START_TAB = TAB_FEATURES

# --- JellyJams document properties ----------------------------------------------------
# Saved inside .FCStd files: renaming any of these breaks documents that use them.
PROP_GROUP = "JellyJams"
PROP_HOST_SHEET = "HostSheet"
PROP_SHOWN_SKETCH = "ShownSketch"
PROP_BORDER_INDEX = "BorderLineIndex"
PROP_SHEET_NOTE = "SheetNote"
PROP_CAPTION_FOR = "CaptionFor"
PROP_SYMBOL_TYPE = "SymbolType"
PROP_MATERIAL_REMOVAL = "MaterialRemoval"
PROP_ALL_AROUND = "AllAroundOutline"
PROP_WELD_SETTINGS = "WeldSettings"
PROP_ARROWHEAD_X = "ArrowheadX"
PROP_ARROWHEAD_Y = "ArrowheadY"
KIND_SURFACE = "surface"
KIND_WELD = "weld"

# Shared by tree naming and Projected View so both give a direction the same name.
PROJECTION_VIEW_LABELS = {
    "Front": "Front View",
    "Top": "Top View",
    "Bottom": "Bottom View",
    "Left": "Left View",
    "Right": "Right View",
    "Rear": "Back View",
    "FrontTopLeft": "Isometric View",
    "FrontTopRight": "Isometric View",
    "FrontBottomLeft": "Isometric View",
    "FrontBottomRight": "Isometric View",
}

# --- intervals (milliseconds) --------------------------------------------------------
# Starting values only: a module copies the one it uses into a module-level name,
# which the tests can override without touching this file.
RIBBON_REFRESH_MS = 450      # ribbon enabled-state and context-tab poll
QUIT_PROMPT_POLL_MS = 600    # quit watcher: wait between looks for a modal prompt
DIALOG_TERMS_MS = 250        # scan for task-dialog forms to relabel
