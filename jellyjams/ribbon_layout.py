# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
"""Ribbon content for the five JellyJams tabs, kept as plain Python data.

Nothing here imports FreeCAD or Qt. At build time ribbon_model.resolve()
compares every id with the commands FreeCAD has registered (swapping in a
fallback id or dropping the entry), and ribbon_widgets draws what is left.

How the renderer reads the data, shown on a made-up group:

    Group("Example", [
        Toggle(Cmd("PartDesign_NewSketch", "Sketch"),
               Cmd("Sketcher_LeaveSketch", "Exit\\nSketch")),
        Flyout([Cmd("Part_DatumPlane", "Plane", fallbacks=("PartDesign_Plane",)),
                Cmd("Part_DatumLine", "Axis")], title="Reference\\nGeometry"),
        _icons(Cmd("Std_ViewFront", "Front"), Cmd("Std_ViewTop", "Top"),
               Cmd("Std_ViewRight", "Right"), Cmd("Std_ViewRear", "Back")),
        _style(5, "Shaded", "DrawStyleShaded"),
    ])

On the page this turns into, from left to right:

  1. one large slot captioned "Sketch"; whenever a sketch is in edit mode the
     same slot reads "Exit Sketch" on two lines and runs that command instead;
  2. a large split button whose caption stays "Reference Geometry" while its
     icon and click target follow the variant last chosen from the arrow
     menu ("Plane" or "Axis", remembered across sessions); a FreeCAD build
     without Part_DatumPlane gets PartDesign_Plane in that place;
  3. a block of small icon-only buttons, three per column: Front, Top and
     Right fill the first column and Back opens the second (a stack built
     with _text(...) adds a one-line caption beside each icon instead);
  4. a large "Shaded" button that calls Std_DrawStyle with sub-entry 5 and
     uses FreeCAD's DrawStyleShaded icon.

A sunken vertical rule then separates this group from the next one; the
group name itself is never drawn. Each Tab supplies one page and the title
on its tab.

Worth knowing when editing the data:

  - "\\n" in a label only matters on a large button. Menus, stacks and
    tooltips join the parts into one line (ribbon_text.one_line).
  - `index` also gives a second copy of the same command an entry id of its
    own (Make Drawing sits on two tabs).
  - `jj_icon` (filled in by _jj) is used for JellyJams ids only; `fc_icon` names
    an icon among FreeCAD's own resources.

Captions are SolidWorks terms; the id next to each one is the FreeCAD 1.1
command that comes closest.
"""

from jellyjams import constants

STYLE_TEXT = "text"
STYLE_ICON = "icon"
STACK_STYLES = (STYLE_TEXT, STYLE_ICON)


class Cmd:
    """A command id with its caption; also each choice inside a Flyout or Toggle."""

    def __init__(self, cmd, label, index=None, fallbacks=(), fc_icon=None, jj_icon=None):
        if not cmd:
            raise ValueError("a ribbon command needs an id")
        self.cmd = cmd
        self.label = label
        self.index = index
        self.fallbacks = tuple(fallbacks or ())
        self.fc_icon = fc_icon
        self.jj_icon = jj_icon

    def ids(self):
        return (self.cmd,) + self.fallbacks

    def __repr__(self):
        return "Cmd({!r})".format(self.cmd if self.index is None else "{}#{}".format(self.cmd, self.index))


class Flyout:
    """Related commands sharing one split button; the first variant is the initial choice."""

    def __init__(self, variants, title=None):
        self.variants = tuple(variants)
        if not self.variants:
            raise ValueError("a flyout needs at least one variant")
        self.title = title

    def __repr__(self):
        return "Flyout({!r})".format(list(self.variants))


class Toggle:
    """Two commands taking turns in one slot: `editing` during sketch editing, else `normal`."""

    def __init__(self, normal, editing):
        self.normal = normal
        self.editing = editing

    def __repr__(self):
        return "Toggle({!r}, {!r})".format(self.normal, self.editing)


class Stack:
    """Compact grid of small buttons, three rows tall, filled one column at a time."""

    def __init__(self, style, entries):
        if style not in STACK_STYLES:
            raise ValueError("unknown stack style: {!r}".format(style))
        self.style = style
        self.entries = tuple(entries)

    def __repr__(self):
        return "Stack({!r}, {!r})".format(self.style, list(self.entries))


class Group:
    """A run of entries on one page; neighboring groups get a vertical rule between them."""

    def __init__(self, name, entries):
        self.name = name
        self.entries = tuple(entries)

    def __repr__(self):
        return "Group({!r})".format(self.name)


class Tab:
    def __init__(self, title, groups):
        self.title = title
        self.groups = tuple(groups)

    def __repr__(self):
        return "Tab({!r})".format(self.title)


# --- shorthands -----------------------------------------------------------------------------

def _jj(cmd, label, index=None):
    """A JellyJams command, drawn with its own icon from resources/icons."""
    return Cmd(cmd, label, index=index, jj_icon=constants.COMMAND_ICONS[cmd])


def _style(index, label, icon):
    """One entry of FreeCAD's Std_DrawStyle group command."""
    return Cmd("Std_DrawStyle", label, index=index, fc_icon=icon)


def _text(*entries):
    return Stack(STYLE_TEXT, entries)


def _icons(*entries):
    return Stack(STYLE_ICON, entries)


# --- Features -------------------------------------------------------------------------------

_FEATURES = Tab(constants.TAB_FEATURES, [
    Group("Boss/Base", [
        Cmd("PartDesign_Pad", "Extruded\nBoss/Base"),
        Cmd("PartDesign_Revolution", "Revolved\nBoss/Base"),
        _text(
            Cmd("PartDesign_AdditivePipe", "Swept Boss/Base"),
            Cmd("PartDesign_AdditiveLoft", "Lofted Boss/Base"),
            Cmd("PartDesign_AdditiveHelix", "Helical Boss/Base"),
        ),
    ]),
    Group("Cut", [
        Cmd("PartDesign_Pocket", "Extruded\nCut"),
        Cmd("PartDesign_Hole", "Hole\nWizard"),
        Cmd("PartDesign_Groove", "Revolved\nCut"),
        _text(
            Cmd("PartDesign_SubtractivePipe", "Swept Cut"),
            Cmd("PartDesign_SubtractiveLoft", "Lofted Cut"),
            Cmd("PartDesign_SubtractiveHelix", "Helical Cut"),
        ),
    ]),
    Group("Applied features", [
        Flyout([
            Cmd("PartDesign_Fillet", "Fillet"),
            Cmd("PartDesign_Chamfer", "Chamfer"),
        ]),
        Flyout([
            Cmd("PartDesign_LinearPattern", "Linear\nPattern"),
            Cmd("PartDesign_PolarPattern", "Circular\nPattern"),
            Cmd("PartDesign_MultiTransform", "Multi-\nTransform"),
        ]),
        _text(
            Cmd("PartDesign_Draft", "Draft"),
            Cmd("PartDesign_Thickness", "Shell"),
            Cmd("PartDesign_Mirrored", "Mirror"),
        ),
    ]),
    Group("Reference", [
        # FreeCAD 1.1 moved datums to Part_*; older builds only have the PartDesign_* ids.
        Flyout([
            Cmd("Part_DatumPlane", "Plane", fallbacks=("PartDesign_Plane",)),
            Cmd("Part_DatumLine", "Axis", fallbacks=("PartDesign_Line",)),
            Cmd("Part_CoordinateSystem", "Coordinate\nSystem", fallbacks=("PartDesign_CoordinateSystem",)),
            Cmd("Part_DatumPoint", "Point", fallbacks=("PartDesign_Point",)),
        ], title="Reference\nGeometry"),
        Flyout([
            Cmd("Part_ProjectionOnSurface", "Projected Curve"),
            Cmd("Part_Section", "Intersection Curve"),
        ], title="Curves"),
        _text(
            Cmd("PartDesign_Body", "Body"),
            Cmd("PartDesign_Boolean", "Combine"),
            Cmd("PartDesign_SubShapeBinder", "Sub-Shape Binder"),
        ),
    ]),
])


# --- Sketch ---------------------------------------------------------------------------------

_SKETCH = Tab(constants.TAB_SKETCH, [
    Group("Sketch", [
        Toggle(
            Cmd("PartDesign_NewSketch", "Sketch", fallbacks=("Sketcher_NewSketch",)),
            Cmd("Sketcher_LeaveSketch", "Exit\nSketch"),
        ),
        Cmd("Sketcher_Dimension", "Smart\nDimension"),
    ]),
    Group("Entities", [
        _icons(
            Flyout([
                Cmd("Sketcher_CreateLine", "Line"),
                _jj(constants.CMD_CENTERLINE, "Centerline"),
                _jj(constants.CMD_MIDPOINT_LINE, "Midpoint Line"),
                Cmd("Sketcher_CreatePolyline", "Polyline"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateRectangle", "Corner Rectangle"),
                Cmd("Sketcher_CreateRectangle_Center", "Center Rectangle"),
                Cmd("Sketcher_CreateOblong", "Rounded Rectangle"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateSlot", "Straight Slot"),
                Cmd("Sketcher_CreateArcSlot", "Centerpoint Arc Slot"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateCircle", "Circle"),
                Cmd("Sketcher_Create3PointCircle", "Perimeter Circle"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateArc", "Centerpoint Arc"),
                Cmd("Sketcher_Create3PointArc", "3 Point Arc"),
            ]),
            Cmd("Sketcher_CreateRegularPolygon", "Polygon"),
            Flyout([
                Cmd("Sketcher_CreateBSplineByInterpolation", "Spline"),
                Cmd("Sketcher_CreateBSpline", "Style Spline"),
                Cmd("Sketcher_CreatePeriodicBSplineByInterpolation", "Closed Spline"),
                Cmd("Sketcher_CreatePeriodicBSpline", "Closed Style Spline"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateEllipseByCenter", "Ellipse"),
                Cmd("Sketcher_CreateArcOfEllipse", "Partial Ellipse"),
                Cmd("Sketcher_CreateArcOfParabola", "Parabola"),
                Cmd("Sketcher_CreateArcOfHyperbola", "Hyperbola"),
            ]),
            Flyout([
                Cmd("Sketcher_CreateFillet", "Sketch Fillet"),
                Cmd("Sketcher_CreateChamfer", "Sketch Chamfer"),
            ]),
            Cmd("Sketcher_CreatePoint", "Point"),
        ),
    ]),
    Group("Modify", [
        Flyout([
            Cmd("Sketcher_Trimming", "Trim\nEntities"),
            Cmd("Sketcher_Extend", "Extend\nEntities"),
            Cmd("Sketcher_Split", "Split\nEntities"),
        ]),
        Flyout([
            # FreeCAD 1.0 has one external-geometry command; 1.1 splits it in two.
            Cmd("Sketcher_Projection", "Convert\nEntities", fallbacks=("Sketcher_External",)),
            Cmd("Sketcher_Intersection", "Intersection\nCurve"),
            Cmd("Sketcher_CarbonCopy", "Carbon\nCopy"),
        ]),
        Cmd("Sketcher_Offset", "Offset\nEntities"),
        _text(
            Cmd("Sketcher_Symmetry", "Mirror Entities"),
            Flyout([
                Cmd("Sketcher_Translate", "Move Entities"),
                Cmd("Sketcher_Rotate", "Rotate Entities"),
                Cmd("Sketcher_Scale", "Scale Entities"),
            ]),
            Cmd("Sketcher_ToggleConstruction", "Construction Geometry"),
        ),
    ]),
    Group("Relations", [
        _text(
            Flyout([
                Cmd("Sketcher_SelectConstraints", "Display/Delete Relations"),
                Cmd("Sketcher_SelectElementsWithDoFs", "Find Under Defined"),
                Cmd("Sketcher_DeleteAllConstraints", "Delete All Relations"),
            ]),
            Cmd("Sketcher_ValidateSketch", "Repair Sketch"),
            Cmd("Sketcher_ViewSketch", "Normal To"),
            Cmd("Sketcher_ViewSection", "Section View"),
        ),
    ]),
])


# --- Evaluate -------------------------------------------------------------------------------

_EVALUATE = Tab(constants.TAB_EVALUATE, [
    Group("Analysis", [
        Cmd(constants.MEASURE_COMMAND, "Measure"),
        Cmd("Part_CheckGeometry", "Check"),
        Flyout([
            Cmd("Std_ToggleClipPlane", "Section\nView"),
            Cmd("Part_SectionCut", "Persistent\nSection"),
        ]),
    ]),
    Group("View Orientation", [
        _icons(
            Cmd("Std_ViewFront", "Front"),
            Cmd("Std_ViewTop", "Top"),
            Cmd("Std_ViewRight", "Right"),
            Cmd("Std_ViewRear", "Back"),
            Cmd("Std_ViewBottom", "Bottom"),
            Cmd("Std_ViewLeft", "Left"),
            Cmd("Std_ViewIsometric", "Isometric"),
            Cmd("Std_ViewDimetric", "Dimetric"),
            Cmd("Std_ViewTrimetric", "Trimetric"),
        ),
        _text(
            _jj(constants.CMD_NORMAL_TO, "Normal To"),
            Cmd("Std_ViewFitAll", "Zoom to Fit"),
            Cmd("Std_ViewBoxZoom", "Zoom to Area"),
        ),
    ]),
    Group("Display Style", [
        _text(
            _style(6, "Shaded With Edges", "DrawStyleFlatLines"),
            _style(5, "Shaded", "DrawStyleShaded"),
            _style(3, "Hidden Lines Removed", "DrawStyleHiddenLine"),
            _style(2, "Wireframe", "DrawStyleWireFrame"),
            Cmd("Std_PerspectiveCamera", "Perspective"),
            Cmd("Std_OrthographicCamera", "Orthographic"),
        ),
    ]),
    Group("JellyJams", [
        _jj(constants.CMD_DIAGNOSTICS, "Diagnostics"),
    ]),
])


# --- Assembly -------------------------------------------------------------------------------

_ASSEMBLY = Tab(constants.TAB_ASSEMBLY, [
    Group("Assembly", [
        # JellyJams_NewAssembly stands in for Assembly_CreateAssembly (one assembly per document).
        _jj(constants.CMD_NEW_ASSEMBLY, "New\nAssembly"),
        # Index 1 only keeps this entry's id apart from the Drawing tab's button.
        _jj(constants.CMD_MAKE_DRAWING, "Make\nDrawing", index=1),
        _text(
            Cmd("Assembly_ActivateAssembly", "Activate Assembly"),
            Cmd("Assembly_SolveAssembly", "Solve Assembly"),
        ),
    ]),
    Group("Components and mates", [
        Flyout([
            Cmd("Assembly_InsertLink", "Insert\nComponents"),
            Cmd("Assembly_InsertNewPart", "New\nPart"),
        ]),
        Flyout([
            Cmd("Assembly_CreateJointDistance", "Coincident/Distance"),
            Cmd("Assembly_CreateJointParallel", "Parallel"),
            Cmd("Assembly_CreateJointPerpendicular", "Perpendicular"),
            Cmd("Assembly_CreateJointCylindrical", "Concentric"),
            Cmd("Assembly_CreateJointFixed", "Lock"),
            Cmd("Assembly_CreateJointAngle", "Angle"),
        ], title="Mate"),
        Flyout([
            Cmd("Assembly_CreateJointRevolute", "Hinge"),
            Cmd("Assembly_CreateJointSlider", "Slider"),
            Cmd("Assembly_CreateJointBall", "Ball Joint"),
            Cmd("Assembly_CreateJointGears", "Gear"),
            Cmd("Assembly_CreateJointRackPinion", "Rack Pinion"),
            Cmd("Assembly_CreateJointScrew", "Screw"),
            Cmd("Assembly_CreateJointBelt", "Belt/Chain"),
        ], title="Mechanical\nMates"),
    ]),
    Group("Move", [
        _text(
            Cmd("Std_TransformManip", "Move Component"),
            # Plain button on purpose: assembly_commands updates its tooltip via find_button().
            _jj(constants.CMD_ROTATE_COMPONENT, "Rotate Component"),
            Cmd("Assembly_ToggleGrounded", "Fix/Float"),
        ),
    ]),
    Group("Studies", [
        Cmd("Assembly_CreateSimulation", "New Motion\nStudy"),
        Cmd("Assembly_CreateBom", "Bill of\nMaterials"),
        Cmd("Assembly_CreateView", "Exploded\nView"),
    ]),
])


# --- Drawing --------------------------------------------------------------------------------

_DRAWING = Tab(constants.TAB_DRAWING, [
    Group("Sheet", [
        _jj(constants.CMD_MAKE_DRAWING, "Make\nDrawing"),
        _text(
            _jj(constants.CMD_SHEET_PROPERTIES, "Sheet Properties"),
            Cmd("TechDraw_PageDefault", "Add Sheet"),
            _jj(constants.CMD_INSERT_PICTURE, "Insert Picture"),
        ),
    ]),
    Group("View Layout", [
        Cmd("TechDraw_ProjectionGroup", "Standard\n3 View"),
        Cmd("TechDraw_View", "Model\nView"),
        _jj(constants.CMD_PROJECTED_VIEW, "Projected\nView"),
        Flyout([
            Cmd("TechDraw_SectionView", "Section\nView"),
            Cmd("TechDraw_ComplexSection", "Aligned\nSection"),
        ]),
        Cmd("TechDraw_DetailView", "Detail\nView"),
        _text(
            Cmd("TechDraw_BrokenView", "Break"),
            Cmd("TechDraw_ClipGroup", "Crop View"),
            _jj(constants.CMD_VIEW_SCALE, "View Scale"),
        ),
    ]),
    Group("Annotation", [
        Flyout([
            # TechDraw_Dimension (smart dimension) is missing from builds older than 1.0.
            Cmd("TechDraw_Dimension", "Smart\nDimension", fallbacks=("TechDraw_LengthDimension",)),
            Cmd("TechDraw_HorizontalDimension", "Horizontal\nDimension"),
            Cmd("TechDraw_VerticalDimension", "Vertical\nDimension"),
            Cmd("TechDraw_ExtensionCreateHorizChainDimension", "Chain\nDimension"),
            Cmd("TechDraw_ExtensionCreateHorizCoordDimension", "Baseline\nDimension"),
            Cmd("TechDraw_ExtensionCreateHorizChamferDimension", "Chamfer\nDimension"),
        ]),
        Flyout([
            _jj(constants.CMD_NOTE, "Note"),
            Cmd("TechDraw_RichTextAnnotation", "Rich Text\nNote"),
        ]),
        _text(
            Cmd("TechDraw_Balloon", "Balloon"),
            _jj(constants.CMD_SURFACE_FINISH, "Surface Finish"),
            _jj(constants.CMD_WELD_SYMBOL, "Weld Symbol"),
        ),
        _text(
            Flyout([
                Cmd("TechDraw_ExtensionCircleCenterLines", "Center Mark"),
                Cmd("TechDraw_ExtensionHoleCircle", "Bolt Circle Mark"),
            ]),
            Flyout([
                Cmd("TechDraw_FaceCenterLine", "Centerline"),
                Cmd("TechDraw_2LineCenterLine", "2-Line Centerline"),
                Cmd("TechDraw_2PointCenterLine", "2-Point Centerline"),
            ]),
            Flyout([
                Cmd("TechDraw_Hatch", "Area Hatch/Fill"),
                Cmd("TechDraw_GeometricHatch", "Geometric Hatch"),
            ]),
        ),
        _text(
            Cmd("TechDraw_LeaderLine", "Multi-Jog Leader"),
            Cmd("TechDraw_SpreadsheetView", "General Table"),
            Flyout([
                Cmd("TechDraw_ExtensionThreadHoleSide", "Hole Thread, Side View"),
                Cmd("TechDraw_ExtensionThreadHoleBottom", "Hole Thread, End View"),
                Cmd("TechDraw_ExtensionThreadBoltSide", "Bolt Thread, Side View"),
                Cmd("TechDraw_ExtensionThreadBoltBottom", "Bolt Thread, End View"),
            ], title="Cosmetic Thread"),
        ),
    ]),
    Group("Sheet sketch", [
        _icons(
            _jj(constants.CMD_SHEET_LINE, "Line"),
            _jj(constants.CMD_SHEET_RECTANGLE, "Corner Rectangle"),
            _jj(constants.CMD_SHEET_CIRCLE, "Circle"),
            _jj(constants.CMD_SHEET_ARC, "Centerpoint Arc"),
            _jj(constants.CMD_SHEET_POLYGON, "Polygon"),
        ),
        _jj(constants.CMD_LINE_FORMAT, "Line\nFormat"),
    ]),
    Group("Output", [
        _jj(constants.CMD_SAVE_PDF, "Save as\nPDF"),
        _jj(constants.CMD_SAVE_DXF, "Save as\nDXF"),
    ]),
])


TABS = [_FEATURES, _SKETCH, _EVALUATE, _ASSEMBLY, _DRAWING]


# --- queries --------------------------------------------------------------------------------

def iter_commands(tabs=None):
    """Every Cmd of the layout in ribbon order (stack cells, flyout and toggle variants included)."""
    for tab in TABS if tabs is None else tabs:
        for group in tab.groups:
            yield from _commands_of(group.entries)


def _commands_of(entries):
    for entry in entries:
        if isinstance(entry, Cmd):
            yield entry
        elif isinstance(entry, Flyout):
            yield from entry.variants
        elif isinstance(entry, Toggle):
            yield entry.normal
            yield entry.editing
        elif isinstance(entry, Stack):
            yield from _commands_of(entry.entries)
        else:
            raise TypeError("not a ribbon layout entry: {!r}".format(entry))


def all_command_ids(tabs=None):
    """Each command id the layout mentions (fallbacks included), once, in ribbon order."""
    seen = []
    for command in iter_commands(tabs):
        for cmd_id in command.ids():
            if cmd_id not in seen:
                seen.append(cmd_id)
    return seen
