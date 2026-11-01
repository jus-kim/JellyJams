# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Catalog of FreeCAD 1.1 task-dialog widgets that get a SolidWorks label.

Pure data, no FreeCAD or Qt imports. Forms are keyed by the objectName of their
root widget, and widgets by their own objectName. A widget is listed only when
the SolidWorks PropertyManager has a standard term for the same control. Every
other widget keeps FreeCAD's text.

Entry layout, per form:
    "texts":          {objectName: text}  labels, buttons, check/radio boxes, group titles
    "combos":         {objectName: entries}  same count and order as FreeCAD's items
    "tooltips":       {objectName: text, or {FreeCAD tooltip: new tooltip}}
    "scale_fix":      (scale-type combo, scale field) or None
    "weight_presets": True when the ISO 128 presets row belongs in the form
"""


def _form(texts=None, combos=None, tooltips=None, scale_fix=None, weight_presets=False):
    return {
        "texts": dict(texts or {}),
        "combos": dict(combos or {}),
        "tooltips": dict(tooltips or {}),
        "scale_fix": tuple(scale_fix) if scale_fix else None,
        "weight_presets": bool(weight_presets),
    }


# --- shared entry lists --------------------------------------------------------------------

# Pad: Dimension, To last, To first, Up to face, Up to shape.
# Pocket: Dimension, Through all, To first, Up to face, Up to shape.
EXTRUDE_END_CONDITIONS = ("Blind", "Through All", "Up To Next", "Up To Surface", "Up To Body")

# One sided, Two sided, Symmetric.
EXTRUDE_SIDES = ("Direction 1", "Direction 1 and 2", "Mid Plane")

# Revolution: Angle, To last, To first, Up to face, Two angles (Groove: Through all at 1).
REVOLVE_TYPES = ("Blind", "Through All", "Up To Next", "Up To Surface", "Two angles")

# FreeCAD 1.1 joint types, in JointObject.JointTypes order.
MATE_TYPES = ("Lock", "Hinge", "Concentric", "Slider", "Ball", "Coincident / Distance", "Parallel",
              "Perpendicular", "Angle", "Rack Pinion", "Screw", "Gear", "Belt")

# Page, Automatic, Custom. "Custom" stays: FreeCAD compares the section dialogs' text to it.
SCALE_TYPES = ("Sheet scale", "Automatic", "Custom")

# First angle, Third angle, Page.
PROJECTION_TYPES = ("First angle", "Third angle", "Sheet")

# FreeCAD rewrites these tooltips whenever the projection type changes, so they are
# translated by their current text instead of being fixed per checkbox.
PROJECTION_TIPS = {
    "FrontTopLeft": "Isometric (front top left)",
    "FrontTopRight": "Isometric (front top right)",
    "FrontBottomLeft": "Isometric (front bottom left)",
    "FrontBottomRight": "Isometric (front bottom right)",
    "LeftFrontTop": "Isometric (front top left)",
    "RightFrontTop": "Isometric (front top right)",
    "LeftFrontBottom": "Isometric (front bottom left)",
    "RightFrontBottom": "Isometric (front bottom right)",
    "Rear": "Back",
}

# Circular, None, Triangle, Inspection, Hexagon, Square, Rectangle, Line.
BALLOON_STYLES = ("Circular", "None", "Triangle", "Inspection", "Hexagon", "Box", "Rectangle", "Underline")

# NoLine, Continuous, Dash, Dot, DashDot, DashDotDot.
BORDER_LINE_STYLES = ("None", "Solid", "Dashed", "Dot", "DashDot", "DashDotDot")

# No line, Continuous, Dash, Dot, DashDot, DashDotDot.
LEADER_LINE_STYLES = ("No line", "Solid", "Dashed", "Dot", "DashDot", "DashDotDot")

LINE_COLOR = "Line color"
LINE_THICKNESS = "Line thickness"
LINE_STYLE = "Line style"


# --- the catalog ------------------------------------------------------------------------------

FORMS = {
    "PartDesignGui::TaskPadPocketParameters": _form(
        texts={
            "side1Label": "Direction 1",
            "textLabel1": "End Condition",
            "labelLength": "Depth",
            "labelOffset": "Offset Distance",
            "labelTaperAngle": "Draft Angle",
            "side2Label": "Direction 2",
            "typeLabel2": "End Condition",
            "labelLength2": "Depth",
            "labelOffset2": "Offset Distance",
            "labelTaperAngle2": "Draft Angle",
            "checkBoxReversed": "Reverse Direction",
            "groupBox": "Direction of Extrusion",
        },
        combos={
            "sidesMode": EXTRUDE_SIDES,
            "changeMode": EXTRUDE_END_CONDITIONS,
            "changeMode2": EXTRUDE_END_CONDITIONS,
        },
    ),
    "PartDesignGui::TaskRevolutionParameters": _form(
        texts={
            "textLabelMode": "Revolve Type",
            "textLabel1": "Axis of Revolution",
            "labelAngle2": "Direction 2 Angle",
            "checkBoxMidplane": "Mid Plane",
            "checkBoxReversed": "Reverse Direction",
        },
        combos={"changeMode": REVOLVE_TYPES},
    ),
    "TaskAssemblyCreateJoint": _form(
        texts={"PushButtonReverse": "Flip Mate Alignment"},
        combos={"jointType": MATE_TYPES},
    ),
    "TaskAssemblyInsertLink": _form(
        texts={"openFileButton": "Browse..."},
    ),
    "TechDrawGui::TaskProjGroup": _form(
        texts={
            "directionGroupbox": "Orientation",
            "secondaryProjGroupbox": "Projected Views",
            "label_7": "Type of projection",
        },
        combos={"cmbScaleType": SCALE_TYPES, "projection": PROJECTION_TYPES},
        tooltips={"chkView%d" % index: PROJECTION_TIPS for index in range(10)},
    ),
    "TechDrawGui::TaskSectionView": _form(
        texts={"label_2": "Label", "pbUpdateNow": "Rebuild"},
        combos={"cmbScaleType": SCALE_TYPES},
        scale_fix=("cmbScaleType", "sbScale"),
    ),
    "TechDrawGui::TaskDetail": _form(
        texts={"label_7": "Label"},
        combos={"cbScaleType": SCALE_TYPES},
    ),
    "TechDrawGui::TaskComplexSection": _form(
        texts={"label_2": "Label", "pbUpdateNow": "Rebuild"},
        combos={"cmbScaleType": SCALE_TYPES},
        scale_fix=("cmbScaleType", "sbScale"),
    ),
    "TechDrawGui::TaskDimension": _form(
        texts={
            "gbTolerancing": "Primary Value",
            "cbArbitrary": "Override value",
            "label_9": "Unit Precision",
            "cbReference": "Add Parentheses",
            "gbFormatting": "Tolerance/Precision",
            "cbEqualTolerance": "Symmetric",
            "cbTheoreticallyExact": "Basic",
            "label_2": "Maximum Variation",
            "label_8": "Minimum Variation",
        },
    ),
    "TechDrawGui::TaskBalloon": _form(
        texts={
            "label": "Balloon text",
            "label_3": "Style",
            "label_4": "Arrow style",
            "label_9": "Leader",
            "label_8": "Leader thickness",
            "label_6": "Bent leader length",
        },
        combos={"comboBubbleShape": BALLOON_STYLES, "comboLineVisible": ("No Leader", "Leader")},
    ),
    "TechDrawGui::TaskRichAnno": _form(
        texts={"label_3": "Border", "label_4": LINE_COLOR, "label_5": LINE_THICKNESS, "label_6": LINE_STYLE},
        combos={"cFrameStyle": BORDER_LINE_STYLES},
    ),
    "TechDrawGui::TaskLeaderLine": _form(
        texts={"label": LINE_COLOR, "label_5": LINE_THICKNESS, "label_6": LINE_STYLE},
        combos={"cboxStyle": LEADER_LINE_STYLES},
    ),
    "TechDrawGui::TaskHatch": _form(
        texts={"label": "Pattern", "label_2": "Scale", "label_4": "Angle"},
    ),
    "TechDrawGui::TaskCenterLine": _form(
        texts={"label": LINE_COLOR, "label_5": LINE_THICKNESS, "label_6": LINE_STYLE},
    ),
    "TaskWeldingSymbol": _form(
        texts={"cbFieldWeld": "Field/Site", "cbAltWeld": "Stagger"},
    ),
    "TechDrawGui::TaskSurfaceFinishSymbols": _form(
        texts={"lbAngle": "Angle"},
    ),
    "TechDrawGui::TaskLineDecor": _form(
        texts={"label_15": LINE_THICKNESS, "label_14": LINE_COLOR, "label_6": LINE_STYLE,
               "label": "Hide/Show Edges"},
        combos={"cb_Visible": ("Hide", "Show")},
        weight_presets=True,
    ),
}

FORM_NAMES = tuple(FORMS)

# Widgets whose text FreeCAD itself rewrites while the dialog is open (state or selection
# feedback). They are never written, even if a catalog entry above named them.
STATE_WIDGETS = {
    "PartDesignGui::TaskPadPocketParameters": ("buttonShapeFace", "buttonShapeFace2"),
    "TaskAssemblyCreateJoint": ("distanceLabel", "offset1Button", "offset2Button"),
    "TechDrawGui::TaskProjGroup": ("lePrimary",),
    "TechDrawGui::TaskSectionView": ("lPendingUpdates",),
    "TechDrawGui::TaskDetail": ("pbDragger",),
    "TechDrawGui::TaskComplexSection": ("lPendingUpdates",),
    "TechDrawGui::TaskLeaderLine": ("pbTracker",),
    "TaskWeldingSymbol": ("pbArrowSymbol", "pbOtherSymbol"),
}


# --- ISO 128 line-thickness presets row (Line Format dialog) -----------------------------------

WEIGHT_FIELD = "dsb_Weight"
WEIGHT_PRESETS_MM = (0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0)
WEIGHT_LABEL = "ISO 128 preset"
PLACEHOLDER = "–"
