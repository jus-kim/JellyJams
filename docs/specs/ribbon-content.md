# JellyJams specification: Ribbon content

> **Implemented in:** [`jellyjams/ribbon_layout.py`](../../jellyjams/ribbon_layout.py) (the declarative content); module loading before the build in [`fcgui.py`](../../jellyjams/fcgui.py) (`preload_command_modules`, module lists in [`constants.py`](../../jellyjams/constants.py)); the icons of JellyJams' own commands in [`resources/icons/`](../../resources/icons/). Rendering is specified in [ribbon-engine.md](ribbon-engine.md).
>
> **Status:** see [../status.md](../status.md)

Area: **ribbon-content** (called "ribbon-layout" in the [ribbon-engine](ribbon-engine.md) spec).
Product: JellyJams, a FreeCAD 1.1+ workbench (key/class `JellyJamsWorkbench`,
MenuText `JellyJams`, English only) that makes FreeCAD look, feel and operate
like SolidWorks.

This document states requirements only. Data formats and module, class,
function and variable names are not part of the specification.
The exact public facts (tab titles, FreeCAD and `JellyJams_*` command ids, FreeCAD
module names, FreeCAD icon names, parameter group and keys, objectNames) are
fixed and listed in section 4.

How the ribbon is drawn and kept alive (dock, tab widget, button widgets,
enable-state polling, tooltips, context tab switching, flyout mechanics, icon
lookup order) is specified in the **ribbon-engine** spec. This spec defines
**what** the ribbon contains.

---

## 1. Purpose

The JellyJams ribbon plays the role of the SolidWorks **CommandManager**. This
area defines its complete content:

- the five tabs and their order;
- the groups of each tab, left to right;
- every tool: the SolidWorks label shown to the user, the FreeCAD (or
  JellyJams `JellyJams_*`) command it runs, fallback commands, the button kind and
  size, and its grouping into flyouts and stacks;
- which tabs the ribbon engine opens on start and on context changes;
- which FreeCAD GUI and Assembly modules must be loaded before the ribbon is
  built, so that every referenced FreeCAD command exists;
- where each button's icon comes from (FreeCAD's own icons at runtime, or
  JellyJams-original icons for `JellyJams_*` commands).

The arrangement follows the order of the SolidWorks CommandManager tabs, each
tool mapped to the closest FreeCAD 1.1 command. Where no FreeCAD command
matches a SolidWorks tool exactly, the label is an approximation (section 2.8).

Non-functional requirement: the content must be defined **declaratively in one
place**, so that adding, renaming or moving a button means editing only that
definition and never the ribbon engine.

---

## 2. User-visible behavior and UI

### 2.1 Tabs

The ribbon has exactly five tabs, in this order (tab bar below the buttons, as
in the SolidWorks CommandManager; see ribbon-engine):

| # | Tab title | Role |
|---|---|---|
| 1 | `Features` | Part features (PartDesign) and reference geometry. **Start tab**: current when the ribbon is first built, regardless of its position. |
| 2 | `Sketch` | Sketching tools (Sketcher). **Sketch context tab**: the engine switches here when sketch editing starts. |
| 3 | `Evaluate` | Measuring and checking, section views, view orientation, display styles and camera, and JellyJams Diagnostics. There is **no** separate "View" tab: its tools live here. |
| 4 | `Assembly` | Assembly tools (FreeCAD Assembly workbench + JellyJams). **Assembly context tab**: the engine switches here when an assembly becomes active. |
| 5 | `Drawing` | Drawing tools (TechDraw + JellyJams). **Drawing context tab**: the engine switches here when a drawing sheet window becomes active. |

There is no language button and no other tab.

### 2.2 Button kinds (vocabulary used in the tables)

| Code | Kind | Look |
|---|---|---|
| **L** | Large button | 32 px icon, caption **below** the icon (forced line breaks kept). Main functions. |
| **LF** | Large flyout | Large split button with a menu arrow. Main part runs the current variant; the arrow lists all variants. Shows the current variant's icon and caption. ★ marks the default variant (the first one). |
| **LF-T** | Large titled flyout | Like LF, but the caption is a **fixed title** that never changes; only the icon follows the chosen variant. |
| **TOG** | Large toggle slot | One large slot that runs variant A normally and variant B while a sketch is being edited. |
| **STK-T** | Text stack | A block of small buttons (20 px icons), each with its **one-line name beside** the icon, arranged **3 rows high, filled column by column**. |
| **STK-I** | Icon stack | Like STK-T but **icon only** (no text). |
| **s** | Small button inside a stack | |
| **sF** | Small flyout inside a stack | Icon-only in an icon stack; one-line text beside in a text stack (the current variant's name). |
| **sF-T** | Small titled flyout inside a text stack | Like sF, but the text beside the icon is a fixed title. |
| **v** | Flyout variant | One entry of a flyout's menu (icon + one-line name). |

Groups are separated by vertical separator lines. Groups have **no visible
title**; the group names used below are for reference only.

### 2.3 Captions and one-line names

- Captions use the English SolidWorks UI terms (approximations: section 2.8).
- In the tables, `⏎` marks a **forced line break** in a large button's caption
  (it keeps buttons narrow), e.g. `Extruded⏎Boss/Base` is shown as "Extruded"
  over "Boss/Base". A large caption has at most two lines.
- The **one-line name** is used in flyout menus, text stacks, icon-stack
  tooltips and tooltips in general. It follows the flattening rule of the
  ribbon-engine spec (a hyphen at a break before a lowercase letter joins the
  word; a hyphen before an uppercase letter stays; another break becomes a
  space). The tables list the resulting one-line name explicitly; it is
  normative. Example: `Multi-⏎Transform` becomes "Multi-Transform".
- Tooltips combine the SolidWorks name with FreeCAD's own command name
  (format in ribbon-engine), e.g. "Extruded Boss/Base — (FreeCAD: Pad)".

### 2.4 Icon policy

| Code | Icon source |
|---|---|
| **FC** | FreeCAD's own icon for that command, obtained at runtime from the running FreeCAD (the same icon FreeCAD shows in its own toolbars). Nothing is bundled. |
| **FC:`name`** | The FreeCAD icon with that resource name, obtained at runtime (used for sub-entries of a FreeCAD group command, whose own action may not exist yet). |
| **Own** | A **new, original** icon drawn for JellyJams and shipped with the add-on. No icon file name may contain "SolidWorks". The icon may fall back at runtime to a FreeCAD icon if the JellyJams file is missing. |

No third-party or FreeCAD icon file is copied into JellyJams. A FreeCAD
command never shows a JellyJams icon in the ribbon. For each **Own** entry, the
content definition names the JellyJams icon to show (the command's entry in
the shared icon table). The two Make Drawing buttons share one icon because
they run the same command.

### 2.5 Tab contents

Positions run left to right. In stacks, positions are written `row,column`
(rows 1–3, filled column by column). The Fallback column names the command
used when the primary id is not registered (section 6).

#### Tab 1 — `Features` (4 groups)

**Group F1 — Boss/Base**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | L | `Extruded⏎Boss/Base` | Extruded Boss/Base | `PartDesign_Pad` | | FC | profile feature¹ |
| 2 | L | `Revolved⏎Boss/Base` | Revolved Boss/Base | `PartDesign_Revolution` | | FC | profile feature¹ |
| 3 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 3 · 1,1 | s | — | Swept Boss/Base | `PartDesign_AdditivePipe` | | FC | profile feature¹ |
| 3 · 2,1 | s | — | Lofted Boss/Base | `PartDesign_AdditiveLoft` | | FC | profile feature¹ |
| 3 · 3,1 | s | — | Helical Boss/Base | `PartDesign_AdditiveHelix` | | FC | profile feature¹; approximate (2.8) |

**Group F2 — Cut**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | L | `Extruded⏎Cut` | Extruded Cut | `PartDesign_Pocket` | | FC | profile feature¹ |
| 2 | L | `Hole⏎Wizard` | Hole Wizard | `PartDesign_Hole` | | FC | profile feature¹ |
| 3 | L | `Revolved⏎Cut` | Revolved Cut | `PartDesign_Groove` | | FC | profile feature¹ |
| 4 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 4 · 1,1 | s | — | Swept Cut | `PartDesign_SubtractivePipe` | | FC | profile feature¹ |
| 4 · 2,1 | s | — | Lofted Cut | `PartDesign_SubtractiveLoft` | | FC | profile feature¹ |
| 4 · 3,1 | s | — | Helical Cut | `PartDesign_SubtractiveHelix` | | FC | profile feature¹; approximate (2.8) |

**Group F3 — Applied features**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | LF | — | — | — | | — | Fillet flyout |
| 1a ★ | v | `Fillet` | Fillet | `PartDesign_Fillet` | | FC | |
| 1b | v | `Chamfer` | Chamfer | `PartDesign_Chamfer` | | FC | |
| 2 | LF | — | — | — | | — | Pattern flyout |
| 2a ★ | v | `Linear⏎Pattern` | Linear Pattern | `PartDesign_LinearPattern` | | FC | |
| 2b | v | `Circular⏎Pattern` | Circular Pattern | `PartDesign_PolarPattern` | | FC | |
| 2c | v | `Multi-⏎Transform` | Multi-Transform | `PartDesign_MultiTransform` | | FC | approximate (2.8) |
| 3 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 3 · 1,1 | s | — | Draft | `PartDesign_Draft` | | FC | |
| 3 · 2,1 | s | — | Shell | `PartDesign_Thickness` | | FC | |
| 3 · 3,1 | s | — | Mirror | `PartDesign_Mirrored` | | FC | |

**Group F4 — Reference**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | LF-T | **`Reference⏎Geometry`** (fixed title) | Reference Geometry | — | | — | Reference geometry flyout |
| 1a ★ | v | `Plane` | Plane | `Part_DatumPlane` | `PartDesign_Plane` | FC | FreeCAD 1.1 provides the datums as `Part_*` commands; older builds only have the `PartDesign_*` ids. |
| 1b | v | `Axis` | Axis | `Part_DatumLine` | `PartDesign_Line` | FC | |
| 1c | v | `Coordinate⏎System` | Coordinate System | `Part_CoordinateSystem` | `PartDesign_CoordinateSystem` | FC | |
| 1d | v | `Point` | Point | `Part_DatumPoint` | `PartDesign_Point` | FC | |
| 2 | LF-T | **`Curves`** (fixed title) | Curves | — | | — | Curves flyout |
| 2a ★ | v | `Projected Curve` | Projected Curve | `Part_ProjectionOnSurface` | | FC | approximate (2.8) |
| 2b | v | `Intersection Curve` | Intersection Curve | `Part_Section` | | FC | approximate (2.8) |
| 3 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 3 · 1,1 | s | — | Body | `PartDesign_Body` | | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |
| 3 · 2,1 | s | — | Combine | `PartDesign_Boolean` | | FC | approximate (2.8) |
| 3 · 3,1 | s | — | Sub-Shape Binder | `PartDesign_SubShapeBinder` | | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |

¹ *Profile feature*: when pressed while a sketch is being edited, the ribbon
engine first exits the sketch and then starts the feature with that sketch as
its profile (see ribbon-engine, "feature from open sketch"). All eleven
profile features are on this tab.

PartDesign primitives (additive and subtractive box, cylinder, sphere, and so
on) are not on the ribbon.

#### Tab 2 — `Sketch` (4 groups)

**Group S1 — Sketch**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | TOG | — | — | — | | — | One slot, two commands |
| 1-A | (not editing a sketch) | `Sketch` | Sketch | `PartDesign_NewSketch` | `Sketcher_NewSketch` | FC | Creates a sketch. |
| 1-B | (editing a sketch) | `Exit⏎Sketch` | Exit Sketch | `Sketcher_LeaveSketch` | | FC | Closes the sketch being edited. |
| 2 | L | `Smart⏎Dimension` | Smart Dimension | `Sketcher_Dimension` | | FC | |

"Editing a sketch" means that the active document has a `Sketcher::SketchObject`
in edit mode (see ribbon-engine).

**Group S2 — Entities** (one STK-I icon stack, 10 cells → 3 rows × 4 columns;
column 4 holds only row 1)

| Cell (row,col) | Kind | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|
| 1,1 | sF | Line flyout | | | |
| 1,1 a ★ | v | Line | `Sketcher_CreateLine` | FC | |
| 1,1 b | v | Centerline | `JellyJams_Centerline` | Own | JellyJams command (sketching area): lines become construction geometry. |
| 1,1 c | v | Midpoint Line | `JellyJams_MidpointLine` | Own | JellyJams command (sketching area): drawn from the midpoint, the other half is mirrored. |
| 1,1 d | v | Polyline | `Sketcher_CreatePolyline` | FC | approximate (2.8) |
| 2,1 | sF | Rectangle flyout | | | |
| 2,1 a ★ | v | Corner Rectangle | `Sketcher_CreateRectangle` | FC | |
| 2,1 b | v | Center Rectangle | `Sketcher_CreateRectangle_Center` | FC | |
| 2,1 c | v | Rounded Rectangle | `Sketcher_CreateOblong` | FC | approximate (2.8) |
| 3,1 | sF | Slot flyout | | | |
| 3,1 a ★ | v | Straight Slot | `Sketcher_CreateSlot` | FC | |
| 3,1 b | v | Centerpoint Arc Slot | `Sketcher_CreateArcSlot` | FC | |
| 1,2 | sF | Circle flyout | | | |
| 1,2 a ★ | v | Circle | `Sketcher_CreateCircle` | FC | |
| 1,2 b | v | Perimeter Circle | `Sketcher_Create3PointCircle` | FC | |
| 2,2 | sF | Arc flyout | | | |
| 2,2 a ★ | v | Centerpoint Arc | `Sketcher_CreateArc` | FC | |
| 2,2 b | v | 3 Point Arc | `Sketcher_Create3PointArc` | FC | |
| 3,2 | s | Polygon | `Sketcher_CreateRegularPolygon` | FC | |
| 1,3 | sF | Spline flyout | | | |
| 1,3 a ★ | v | Spline | `Sketcher_CreateBSplineByInterpolation` | FC | |
| 1,3 b | v | Style Spline | `Sketcher_CreateBSpline` | FC | |
| 1,3 c | v | Closed Spline | `Sketcher_CreatePeriodicBSplineByInterpolation` | FC | approximate (2.8) |
| 1,3 d | v | Closed Style Spline | `Sketcher_CreatePeriodicBSpline` | FC | approximate (2.8) |
| 2,3 | sF | Ellipse flyout | | | |
| 2,3 a ★ | v | Ellipse | `Sketcher_CreateEllipseByCenter` | FC | |
| 2,3 b | v | Partial Ellipse | `Sketcher_CreateArcOfEllipse` | FC | |
| 2,3 c | v | Parabola | `Sketcher_CreateArcOfParabola` | FC | |
| 2,3 d | v | Hyperbola | `Sketcher_CreateArcOfHyperbola` | FC | approximate (2.8) |
| 3,3 | sF | Sketch fillet flyout | | | |
| 3,3 a ★ | v | Sketch Fillet | `Sketcher_CreateFillet` | FC | |
| 3,3 b | v | Sketch Chamfer | `Sketcher_CreateChamfer` | FC | |
| 1,4 | s | Point | `Sketcher_CreatePoint` | FC | |

Captions of the icon-stack entries are never printed on the button. They
appear in the flyout menus and tooltips as the one-line names above.

**Group S3 — Modify**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | LF | — | — | — | | — | Trim flyout |
| 1a ★ | v | `Trim⏎Entities` | Trim Entities | `Sketcher_Trimming` | | FC | |
| 1b | v | `Extend⏎Entities` | Extend Entities | `Sketcher_Extend` | | FC | |
| 1c | v | `Split⏎Entities` | Split Entities | `Sketcher_Split` | | FC | |
| 2 | LF | — | — | — | | — | Convert flyout |
| 2a ★ | v | `Convert⏎Entities` | Convert Entities | `Sketcher_Projection` | `Sketcher_External` | FC | Projects model edges into the sketch. FreeCAD 1.0 has one external-geometry command; 1.1 splits it in two. |
| 2b | v | `Intersection⏎Curve` | Intersection Curve | `Sketcher_Intersection` | | FC | |
| 2c | v | `Carbon⏎Copy` | Carbon Copy | `Sketcher_CarbonCopy` | | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |
| 3 | L | `Offset⏎Entities` | Offset Entities | `Sketcher_Offset` | | FC | FreeCAD requires the entities to be selected first. |
| 4 | STK-T | — | — | — | | — | 3 cells, 1 column |
| 4 · 1,1 | s | — | Mirror Entities | `Sketcher_Symmetry` | | FC | |
| 4 · 2,1 | sF | — | (current variant's name, beside the icon) | — | | — | Move flyout |
| 4 · 2,1 a ★ | v | — | Move Entities | `Sketcher_Translate` | | FC | |
| 4 · 2,1 b | v | — | Rotate Entities | `Sketcher_Rotate` | | FC | |
| 4 · 2,1 c | v | — | Scale Entities | `Sketcher_Scale` | | FC | |
| 4 · 3,1 | s | — | Construction Geometry | `Sketcher_ToggleConstruction` | | FC | |

**Group S4 — Relations** (one STK-T text stack, 4 cells → 3 rows × 2 columns;
column 2 holds only row 1)

| Cell | Kind | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|
| 1,1 | sF | (current variant's name, beside the icon) | | | Relations flyout |
| 1,1 a ★ | v | Display/Delete Relations | `Sketcher_SelectConstraints` | FC | approximate (2.8) |
| 1,1 b | v | Find Under Defined | `Sketcher_SelectElementsWithDoFs` | FC | approximate (2.8) |
| 1,1 c | v | Delete All Relations | `Sketcher_DeleteAllConstraints` | FC | |
| 2,1 | s | Repair Sketch | `Sketcher_ValidateSketch` | FC | approximate (2.8) |
| 3,1 | s | Normal To | `Sketcher_ViewSketch` | FC | |
| 1,2 | s | Section View | `Sketcher_ViewSection` | FC | |

The ribbon has no buttons for individual sketch relations. Relations that fit
the current selection are offered by the separate Add Relations panel of the
relations area, which is not part of the ribbon.

#### Tab 3 — `Evaluate` (4 groups)

**Group E1 — Analysis**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | L | `Measure` | Measure | `Std_Measure` | FC | Temporary centre/axis distance or clearance; see below |
| 2 | L | `Check` | Check | `Part_CheckGeometry` | FC | |
| 3 | LF | — | — | — | — | Section flyout |
| 3a ★ | v | `Section⏎View` | Section View | `Std_ToggleClipPlane` | FC | approximate (2.8) |
| 3b | v | `Persistent⏎Section` | Persistent Section | `Part_SectionCut` | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |

**Group E2 — View Orientation**

| Pos | Kind | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|
| 1 | STK-I | — | — | — | 9 cells → 3 rows × 3 columns |
| 1 · 1,1 | s | Front | `Std_ViewFront` | FC | |
| 1 · 2,1 | s | Top | `Std_ViewTop` | FC | |
| 1 · 3,1 | s | Right | `Std_ViewRight` | FC | |
| 1 · 1,2 | s | Back | `Std_ViewRear` | FC | |
| 1 · 2,2 | s | Bottom | `Std_ViewBottom` | FC | |
| 1 · 3,2 | s | Left | `Std_ViewLeft` | FC | |
| 1 · 1,3 | s | Isometric | `Std_ViewIsometric` | FC | |
| 1 · 2,3 | s | Dimetric | `Std_ViewDimetric` | FC | |
| 1 · 3,3 | s | Trimetric | `Std_ViewTrimetric` | FC | |
| 2 | STK-T | — | — | — | 3 cells, 1 column |
| 2 · 1,1 | s | Normal To | `JellyJams_NormalTo` | Own (`normal_to.svg`) | JellyJams' Normal To, the same command as `Ctrl+8` and the Orientation panel's first button: the sketch plane in a sketch, otherwise one face, edge, plane or sketch ([orientation.md](orientation.md) 2.6). FreeCAD's `Std_AlignToSelection` has no button. |
| 2 · 2,1 | s | Zoom to Fit | `Std_ViewFitAll` | FC | |
| 2 · 3,1 | s | Zoom to Area | `Std_ViewBoxZoom` | FC | |

**Group E3 — Display Style** (one STK-T text stack, 6 cells → 3 rows × 2 columns)

| Cell | Kind | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|
| 1,1 | s | Shaded With Edges | `Std_DrawStyle`, sub-entry **6** | FC:`DrawStyleFlatLines` | FreeCAD "Flat lines". Button id `Std_DrawStyle#6`. |
| 2,1 | s | Shaded | `Std_DrawStyle`, sub-entry **5** | FC:`DrawStyleShaded` | FreeCAD "Shaded". Button id `Std_DrawStyle#5`. |
| 3,1 | s | Hidden Lines Removed | `Std_DrawStyle`, sub-entry **3** | FC:`DrawStyleHiddenLine` | FreeCAD "Hidden line". Button id `Std_DrawStyle#3`. |
| 1,2 | s | Wireframe | `Std_DrawStyle`, sub-entry **2** | FC:`DrawStyleWireFrame` | FreeCAD "Wireframe". Button id `Std_DrawStyle#2`. |
| 2,2 | s | Perspective | `Std_PerspectiveCamera` | FC | |
| 3,2 | s | Orthographic | `Std_OrthographicCamera` | FC | |

`Std_DrawStyle` is a FreeCAD group command. A display-style button runs it
**with the sub-entry index**, the same way FreeCAD records the action itself
(`FreeCADGui.runCommand("Std_DrawStyle", <index>)`). FreeCAD 1.1 sub-entry
order: 0 As is, 1 Points, 2 Wireframe, 3 Hidden line, 4 No shading, 5 Shaded,
6 Flat lines.

**Group E4 — JellyJams**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | L | `Diagnostics` | Diagnostics | `JellyJams_Diagnostics` | Own | JellyJams command (core area). It is also in the workbench's "JellyJams" menu. |

Groups E2 and E3 replace FreeCAD's View toolbar, which the JellyJams window
layout hides.

#### Tab 4 — `Assembly` (4 groups)

**Group A1 — Assembly**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | L | `New⏎Assembly` | New Assembly | `JellyJams_NewAssembly` | Own | JellyJams command (assembly area): the assembly becomes its **own new document**, as in SolidWorks. FreeCAD's `Assembly_CreateAssembly` must **not** appear in the ribbon, because it adds the assembly to the currently open document. |
| 2 | L | `Make⏎Drawing` | Make Drawing | `JellyJams_MakeDrawing` (second copy, button id `JellyJams_MakeDrawing#1`) | Own | The same command as on the Drawing tab, with an identical effect. Index 1 only gives this copy its own button identity. |
| 3 | STK-T | — | — | — | — | 2 small text buttons, 1 column |
| 3 · 1,1 | s | — | Activate Assembly | `Assembly_ActivateAssembly` | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |
| 3 · 2,1 | s | — | Solve Assembly | `Assembly_SolveAssembly` | FC | approximate (2.8) |

**Group A2 — Components and mates** (SolidWorks mate → FreeCAD joint)

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | LF | — | — | — | — | Insert flyout |
| 1a ★ | v | `Insert⏎Components` | Insert Components | `Assembly_InsertLink` | FC | |
| 1b | v | `New⏎Part` | New Part | `Assembly_InsertNewPart` | FC | |
| 2 | LF-T | **`Mate`** (fixed title) | Mate | — | — | Standard mates |
| 2a ★ | v | `Coincident/Distance` | Coincident/Distance | `Assembly_CreateJointDistance` | FC | A Distance joint at zero distance makes the selected entities coincide; approximate (2.8). |
| 2b | v | `Parallel` | Parallel | `Assembly_CreateJointParallel` | FC | |
| 2c | v | `Perpendicular` | Perpendicular | `Assembly_CreateJointPerpendicular` | FC | |
| 2d | v | `Concentric` | Concentric | `Assembly_CreateJointCylindrical` | FC | Cylindrical joint: same axis, free to rotate and slide. |
| 2e | v | `Lock` | Lock | `Assembly_CreateJointFixed` | FC | |
| 2f | v | `Angle` | Angle | `Assembly_CreateJointAngle` | FC | |
| 3 | LF-T | **`Mechanical⏎Mates`** (fixed title) | Mechanical Mates | — | — | Mechanical mates |
| 3a ★ | v | `Hinge` | Hinge | `Assembly_CreateJointRevolute` | FC | |
| 3b | v | `Slider` | Slider | `Assembly_CreateJointSlider` | FC | |
| 3c | v | `Ball Joint` | Ball Joint | `Assembly_CreateJointBall` | FC | approximate (2.8) |
| 3d | v | `Gear` | Gear | `Assembly_CreateJointGears` | FC | |
| 3e | v | `Rack Pinion` | Rack Pinion | `Assembly_CreateJointRackPinion` | FC | |
| 3f | v | `Screw` | Screw | `Assembly_CreateJointScrew` | FC | |
| 3g | v | `Belt/Chain` | Belt/Chain | `Assembly_CreateJointBelt` | FC | |

**Group A3 — Move** (one STK-T text stack, 3 cells, 1 column)

| Cell | Kind | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|
| 1,1 | s | Move Component | `Std_TransformManip` | FC | approximate (2.8) |
| 2,1 | s | Rotate Component | `JellyJams_RotateComponent` | Own | JellyJams command (assembly area). A plain button on purpose: the command updates its own button's tooltip to explain why it is greyed out. |
| 3,1 | s | Fix/Float | `Assembly_ToggleGrounded` | FC | |

**Group A4 — Studies**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | L | `New Motion⏎Study` | New Motion Study | `Assembly_CreateSimulation` | FC | approximate (2.8) |
| 2 | L | `Bill of⏎Materials` | Bill of Materials | `Assembly_CreateBom` | FC | |
| 3 | L | `Exploded⏎View` | Exploded View | `Assembly_CreateView` | FC | |

#### Tab 5 — `Drawing` (5 groups)

Contains the most important TechDraw tools plus JellyJams drawing commands.
FreeCAD's own TechDraw workbench remains unchanged.

**Group D1 — Sheet**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | L | `Make⏎Drawing` | Make Drawing | `JellyJams_MakeDrawing` | | Own | Like SolidWorks "Make Drawing from Part/Assembly": a separate drawing file. It must **not** appear on the Features tab. |
| 2 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 2 · 1,1 | s | — | Sheet Properties | `JellyJams_SheetProperties` | | Own | Sheet format/template, type of projection, title block. |
| 2 · 2,1 | s | — | Add Sheet | `TechDraw_PageDefault` | | FC | approximate (2.8) |
| 2 · 3,1 | s | — | Insert Picture | `JellyJams_InsertPicture` | | Own | Places an SVG, PNG, JPG or BMP on the sheet. |

**Group D2 — View Layout**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | L | `Standard⏎3 View` | Standard 3 View | `TechDraw_ProjectionGroup` | | FC | |
| 2 | L | `Model⏎View` | Model View | `TechDraw_View` | | FC | |
| 3 | L | `Projected⏎View` | Projected View | `JellyJams_ProjectedView` | | Own | Select a view, then click next to it for an aligned projection. |
| 4 | LF | — | — | — | | — | Section flyout |
| 4a ★ | v | `Section⏎View` | Section View | `TechDraw_SectionView` | | FC | |
| 4b | v | `Aligned⏎Section` | Aligned Section | `TechDraw_ComplexSection` | | FC | approximate (2.8) |
| 5 | L | `Detail⏎View` | Detail View | `TechDraw_DetailView` | | FC | |
| 6 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 6 · 1,1 | s | — | Break | `TechDraw_BrokenView` | | FC | |
| 6 · 2,1 | s | — | Crop View | `TechDraw_ClipGroup` | | FC | approximate (2.8) |
| 6 · 3,1 | s | — | View Scale | `JellyJams_ViewScale` | | Own | Standard scales for the selected view. |

**Group D3 — Annotation**

| Pos | Kind | Caption | One-line name | Command id | Fallback | Icon | Notes |
|---|---|---|---|---|---|---|---|
| 1 | LF | — | — | — | | — | Dimension flyout |
| 1a ★ | v | `Smart⏎Dimension` | Smart Dimension | `TechDraw_Dimension` | `TechDraw_LengthDimension` | FC | `TechDraw_Dimension` is missing from builds older than 1.0. |
| 1b | v | `Horizontal⏎Dimension` | Horizontal Dimension | `TechDraw_HorizontalDimension` | | FC | |
| 1c | v | `Vertical⏎Dimension` | Vertical Dimension | `TechDraw_VerticalDimension` | | FC | |
| 1d | v | `Chain⏎Dimension` | Chain Dimension | `TechDraw_ExtensionCreateHorizChainDimension` | | FC | approximate (2.8) |
| 1e | v | `Baseline⏎Dimension` | Baseline Dimension | `TechDraw_ExtensionCreateHorizCoordDimension` | | FC | approximate (2.8) |
| 1f | v | `Chamfer⏎Dimension` | Chamfer Dimension | `TechDraw_ExtensionCreateHorizChamferDimension` | | FC | |
| 2 | LF | — | — | — | | — | Note flyout |
| 2a ★ | v | `Note` | Note | `JellyJams_Note` | | Own | Plain text placed by clicking on the sheet. |
| 2b | v | `Rich Text⏎Note` | Rich Text Note | `TechDraw_RichTextAnnotation` | | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |
| 3 | STK-T | — | — | — | | — | 3 small text buttons, 1 column |
| 3 · 1,1 | s | — | Balloon | `TechDraw_Balloon` | | FC | |
| 3 · 2,1 | s | — | Surface Finish | `JellyJams_SurfaceFinish` | | Own | Editable surface finish symbol. |
| 3 · 3,1 | s | — | Weld Symbol | `JellyJams_WeldSymbol` | | Own | Weld symbol placed in two clicks. |
| 4 | STK-T | — | — | — | | — | 3 small text flyouts, 1 column |
| 4 · 1,1 | sF | — | (current variant's name) | — | | — | Center mark flyout |
| 4 · 1,1 a ★ | v | — | Center Mark | `TechDraw_ExtensionCircleCenterLines` | | FC | |
| 4 · 1,1 b | v | — | Bolt Circle Mark | `TechDraw_ExtensionHoleCircle` | | FC | approximate (2.8) |
| 4 · 2,1 | sF | — | (current variant's name) | — | | — | Centerline flyout |
| 4 · 2,1 a ★ | v | — | Centerline | `TechDraw_FaceCenterLine` | | FC | |
| 4 · 2,1 b | v | — | 2-Line Centerline | `TechDraw_2LineCenterLine` | | FC | approximate (2.8) |
| 4 · 2,1 c | v | — | 2-Point Centerline | `TechDraw_2PointCenterLine` | | FC | approximate (2.8) |
| 4 · 3,1 | sF | — | (current variant's name) | — | | — | Hatch flyout |
| 4 · 3,1 a ★ | v | — | Area Hatch/Fill | `TechDraw_Hatch` | | FC | |
| 4 · 3,1 b | v | — | Geometric Hatch | `TechDraw_GeometricHatch` | | FC | FreeCAD concept with no SolidWorks counterpart (2.8) |
| 5 | STK-T | — | — | — | | — | 3 cells, 1 column |
| 5 · 1,1 | s | — | Multi-Jog Leader | `TechDraw_LeaderLine` | | FC | approximate (2.8) |
| 5 · 2,1 | s | — | General Table | `TechDraw_SpreadsheetView` | | FC | approximate (2.8) |
| 5 · 3,1 | sF-T | — | **Cosmetic Thread** (fixed title) | — | | — | Cosmetic thread flyout |
| 5 · 3,1 a ★ | v | — | Hole Thread, Side View | `TechDraw_ExtensionThreadHoleSide` | | FC | |
| 5 · 3,1 b | v | — | Hole Thread, End View | `TechDraw_ExtensionThreadHoleBottom` | | FC | |
| 5 · 3,1 c | v | — | Bolt Thread, Side View | `TechDraw_ExtensionThreadBoltSide` | | FC | |
| 5 · 3,1 d | v | — | Bolt Thread, End View | `TechDraw_ExtensionThreadBoltBottom` | | FC | |

**Group D4 — Sheet sketch**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | STK-I | — | — | — | — | 5 cells → 3 rows × 2 columns. The shapes are drawn in the sheet's sheet sketch with full Sketcher relations and dimensions (drawing-sheet area). |
| 1 · 1,1 | s | — | Line | `JellyJams_LineOnSheet` | Own | |
| 1 · 2,1 | s | — | Corner Rectangle | `JellyJams_CornerRectangleOnSheet` | Own | |
| 1 · 3,1 | s | — | Circle | `JellyJams_CircleOnSheet` | Own | |
| 1 · 1,2 | s | — | Centerpoint Arc | `JellyJams_CenterpointArcOnSheet` | Own | |
| 1 · 2,2 | s | — | Polygon | `JellyJams_PolygonOnSheet` | Own | |
| 2 | L | `Line⏎Format` | Line Format | `JellyJams_LineFormat` | Own | Line style, thickness and color of the selected lines. |

**Group D5 — Output**

| Pos | Kind | Caption | One-line name | Command id | Icon | Notes |
|---|---|---|---|---|---|---|
| 1 | L | `Save as⏎PDF` | Save as PDF | `JellyJams_SaveAsPDF` | Own | All sheets into one PDF. |
| 2 | L | `Save as⏎DXF` | Save as DXF | `JellyJams_SaveAsDXF` | Own | One DXF file per sheet. |

### 2.6 Summary counts (all commands available, e.g. FreeCAD 1.1.4)

| Tab | Groups (separators) | Plain buttons (large + in stacks) | Flyouts (variants) | Toggles (states) | Top-level widgets |
|---|---|---|---|---|---|
| Features | 4 (3) | 17 (5 large + 12 small) | 4 (11): 4 large, 2 of them titled | 0 | 21 |
| Sketch | 4 (3) | 9 (2 large + 7 small) | 12 (35): 2 large, 8 in the icon stack, 2 in text stacks | 1 (2) | 22 |
| Evaluate | 4 (3) | 21 (3 large + 18 small) | 1 (2): large | 0 | 22 |
| Assembly | 4 (3) | 10 (5 large + 5 small) | 3 (15): 3 large, 2 of them titled | 0 | 13 |
| Drawing | 5 (4) | 24 (8 large + 16 small) | 7 (21): 3 large, 4 in text stacks (1 titled) | 0 | 31 |
| **Total** | 21 (16) | **81** | **27 (84)** | **1 (2)** | 109 |

"Top-level widgets" counts plain buttons, flyouts and toggles, each one
`QToolButton` on the tab page. That makes **167 distinct button ids** (plain
buttons, every flyout variant and both toggle states). No id occurs twice: the
duplicated Make Drawing is `JellyJams_MakeDrawing` and `JellyJams_MakeDrawing#1`, and the
display styles are `Std_DrawStyle#6/#5/#3/#2`.

Stacks per tab (style, cells): Features four text stacks of 3; Sketch an icon
stack of 10, a text stack of 3 and a text stack of 4; Evaluate an icon stack
of 9, a text stack of 3 and a text stack of 6; Assembly text stacks of 2 and
3; Drawing five text stacks of 3 and an icon stack of 5.

### 2.7 JellyJams commands referenced by the ribbon

These 22 `JellyJams_*` commands each have a new, original icon. Their behavior is
specified by the owning areas. All must be registered before the ribbon is
first built (see section 3).

| Command id | Tab | Owner area | Purpose (for the icon designer) |
|---|---|---|---|
| `JellyJams_Centerline` | Sketch | sketching | line that becomes construction (dashed) geometry |
| `JellyJams_MidpointLine` | Sketch | sketching | line drawn symmetrically from a midpoint |
| `JellyJams_NormalTo` | Evaluate | orientation | look straight at a face, plane or sketch |
| `JellyJams_Diagnostics` | Evaluate | core | environment details for bug reports |
| `JellyJams_NewAssembly` | Assembly | assembly | new assembly as a separate document |
| `JellyJams_MakeDrawing` | Assembly, Drawing | drawing | new drawing document from the open part/assembly |
| `JellyJams_RotateComponent` | Assembly | assembly | free rotation of a component by mouse |
| `JellyJams_SheetProperties` | Drawing | drawing | sheet format / title block |
| `JellyJams_InsertPicture` | Drawing | drawing | picture on the sheet |
| `JellyJams_ProjectedView` | Drawing | drawing | projected view aligned to a parent view |
| `JellyJams_ViewScale` | Drawing | drawing | scale of the selected view |
| `JellyJams_Note` | Drawing | drawing | plain text (note) on the sheet |
| `JellyJams_SurfaceFinish` | Drawing | drawing | surface finish symbol |
| `JellyJams_WeldSymbol` | Drawing | drawing | weld symbol |
| `JellyJams_LineOnSheet` | Drawing | drawing | line on the sheet |
| `JellyJams_CornerRectangleOnSheet` | Drawing | drawing | rectangle on the sheet |
| `JellyJams_CircleOnSheet` | Drawing | drawing | circle on the sheet |
| `JellyJams_CenterpointArcOnSheet` | Drawing | drawing | arc on the sheet |
| `JellyJams_PolygonOnSheet` | Drawing | drawing | polygon on the sheet |
| `JellyJams_LineFormat` | Drawing | drawing | line style / thickness / color |
| `JellyJams_SaveAsPDF` | Drawing | drawing | save all sheets as one PDF |
| `JellyJams_SaveAsDXF` | Drawing | drawing | save the sheets as DXF |

The one other JellyJams command, `JellyJams_ViewOrientation` ([orientation.md](orientation.md)),
has no ribbon button: it runs with `Space` and from the JellyJams menu. `JellyJams_NormalTo` is on
the Evaluate tab and also runs with `Ctrl+8`, from the JellyJams menu and from the Orientation
panel. The Sketch tab's Normal To stays FreeCAD's `Sketcher_ViewSketch` (Tab 2, Relations).

Several ribbon labels differ from the command's own MenuText (owned by the
command's area), for example `JellyJams_Note` is "Note" on the ribbon and "Text" as
MenuText, `JellyJams_ViewScale` is "View Scale" and "Scale", `JellyJams_SaveAsDXF` is
"Save as DXF" and "Export DXF". The tooltip then names both (ribbon-engine
2.8).

### 2.8 Approximate mappings (to be reviewed)

Some FreeCAD commands have no exact SolidWorks counterpart. Their ribbon label
is either the closest SolidWorks term or a descriptive name, and is open for
review by users who know SolidWorks well:

| Label | FreeCAD command | Why it is approximate |
|---|---|---|
| Helical Boss/Base, Helical Cut | `PartDesign_AdditiveHelix`, `PartDesign_SubtractiveHelix` | SolidWorks makes helical features from a helix curve and a sweep |
| Multi-Transform | `PartDesign_MultiTransform` | FreeCAD's combined pattern feature |
| Body, Sub-Shape Binder | `PartDesign_Body`, `PartDesign_SubShapeBinder` | FreeCAD concepts with no SolidWorks counterpart |
| Combine | `PartDesign_Boolean` | FreeCAD's boolean of bodies |
| Projected Curve, Intersection Curve (Features) | `Part_ProjectionOnSurface`, `Part_Section` | Part workbench tools, not reference curves |
| Polyline, Rounded Rectangle, Closed Spline, Closed Style Spline, Hyperbola | `Sketcher_CreatePolyline`, `Sketcher_CreateOblong`, `Sketcher_CreatePeriodicBSplineByInterpolation`, `Sketcher_CreatePeriodicBSpline`, `Sketcher_CreateArcOfHyperbola` | FreeCAD sketch tools without a SolidWorks tool of that name |
| Carbon Copy | `Sketcher_CarbonCopy` | FreeCAD concept |
| Display/Delete Relations, Find Under Defined, Repair Sketch | `Sketcher_SelectConstraints`, `Sketcher_SelectElementsWithDoFs`, `Sketcher_ValidateSketch` | FreeCAD selection and validation tools |
| Section View, Persistent Section (Evaluate) | `Std_ToggleClipPlane`, `Part_SectionCut` | clipping plane and a section-cut object |
| Activate Assembly, Solve Assembly | `Assembly_ActivateAssembly`, `Assembly_SolveAssembly` | FreeCAD assembly states |
| Coincident/Distance, Ball Joint | `Assembly_CreateJointDistance`, `Assembly_CreateJointBall` | FreeCAD joint types |
| Move Component | `Std_TransformManip` | FreeCAD's placement dragger |
| New Motion Study | `Assembly_CreateSimulation` | FreeCAD's assembly simulation |
| Add Sheet, Aligned Section, Crop View | `TechDraw_PageDefault`, `TechDraw_ComplexSection`, `TechDraw_ClipGroup` | TechDraw objects that only partly match |
| Chain Dimension, Baseline Dimension | `TechDraw_ExtensionCreateHorizChainDimension`, `TechDraw_ExtensionCreateHorizCoordDimension` | horizontal-only TechDraw extensions |
| Rich Text Note, Geometric Hatch | `TechDraw_RichTextAnnotation`, `TechDraw_GeometricHatch` | FreeCAD concepts |
| Bolt Circle Mark, 2-Line Centerline, 2-Point Centerline, Multi-Jog Leader, General Table | `TechDraw_ExtensionHoleCircle`, `TechDraw_2LineCenterLine`, `TechDraw_2PointCenterLine`, `TechDraw_LeaderLine`, `TechDraw_SpreadsheetView` | TechDraw tools that only partly match |

---

## 3. Triggers and timing

- **Content is fixed at build time.** The ribbon is built once, on the first
  show (first activation of JellyJams in the session). Command availability is
  decided at that moment from `FreeCADGui.listCommands()`.
- **Before the build**, so that FreeCAD commands exist even if the user has
  never opened the corresponding workbenches:
  1. The following FreeCAD compiled GUI modules are imported (Python import
     names), each on its own: `PartGui`, `SketcherGui`, `PartDesignGui`,
     `TechDrawGui`.
  2. The following FreeCAD Assembly Python command modules (from
     `<FreeCAD>/Mod/Assembly/`) are imported. They register the `Assembly_*`
     commands, which FreeCAD otherwise registers only when the Assembly
     workbench initializes: `CommandCreateAssembly`, `CommandInsertLink`,
     `CommandInsertNewPart`, `CommandCreateJoint`, `CommandSolveAssembly`,
     `CommandCreateView`, `CommandCreateSimulation`, `CommandCreateBom`.
  3. All `JellyJams_*` commands of section 2.7 are already registered (they are
     registered when the workbench initializes, which FreeCAD runs before the
     first activation).
- **Clicks:** a button, flyout (main part or menu choice) or toggle runs its
  command as defined in the tables, through the ribbon engine. Entries with a
  sub-entry index (`Std_DrawStyle` 6/5/3/2) run the group command with that
  index. All others run the plain command (`JellyJams_MakeDrawing#1` runs
  `JellyJams_MakeDrawing` with index 1, which JellyJams commands ignore).
- **Toggle state** (Sketch tab, slot S1-1) follows sketch editing: state A
  when no sketch is in edit, state B while one is (polled by the engine).
- **Context tabs:** the engine opens `Features` at first build and switches to
  `Sketch` / `Assembly` / `Drawing` on the respective context transitions. The
  titles in section 2.1 are the targets.
- **Running any ribbon command** ends a running Centerline or Midpoint Line
  tool first, unless the command is that same tool (the engine does this; the
  sketching area provides the stop).

---

## 4. FreeCAD state read or changed (public contract)

### 4.1 Tab titles (exact, in order)

`Features`, `Sketch`, `Evaluate`, `Assembly`, `Drawing`.
Start tab `Features`; context tabs `Sketch`, `Assembly`, `Drawing`.

### 4.2 FreeCAD command ids used

Primary ids, by module:

- PartDesign (23): `PartDesign_Pad`, `PartDesign_Revolution`,
  `PartDesign_AdditivePipe`, `PartDesign_AdditiveLoft`,
  `PartDesign_AdditiveHelix`, `PartDesign_Pocket`, `PartDesign_Hole`,
  `PartDesign_Groove`, `PartDesign_SubtractivePipe`,
  `PartDesign_SubtractiveLoft`, `PartDesign_SubtractiveHelix`,
  `PartDesign_Fillet`, `PartDesign_Chamfer`, `PartDesign_LinearPattern`,
  `PartDesign_PolarPattern`, `PartDesign_MultiTransform`, `PartDesign_Draft`,
  `PartDesign_Thickness`, `PartDesign_Mirrored`, `PartDesign_Body`,
  `PartDesign_Boolean`, `PartDesign_SubShapeBinder`, `PartDesign_NewSketch`.
- Part (8): `Part_DatumPlane`, `Part_DatumLine`, `Part_CoordinateSystem`,
  `Part_DatumPoint`, `Part_ProjectionOnSurface`, `Part_Section`,
  `Part_CheckGeometry`, `Part_SectionCut`.
- Sketcher (43): `Sketcher_LeaveSketch`, `Sketcher_Dimension`,
  `Sketcher_CreateLine`, `Sketcher_CreatePolyline`, `Sketcher_CreateRectangle`,
  `Sketcher_CreateRectangle_Center`, `Sketcher_CreateOblong`,
  `Sketcher_CreateSlot`, `Sketcher_CreateArcSlot`, `Sketcher_CreateCircle`,
  `Sketcher_Create3PointCircle`, `Sketcher_CreateArc`,
  `Sketcher_Create3PointArc`, `Sketcher_CreateRegularPolygon`,
  `Sketcher_CreateBSplineByInterpolation`, `Sketcher_CreateBSpline`,
  `Sketcher_CreatePeriodicBSplineByInterpolation`,
  `Sketcher_CreatePeriodicBSpline`, `Sketcher_CreateEllipseByCenter`,
  `Sketcher_CreateArcOfEllipse`, `Sketcher_CreateArcOfParabola`,
  `Sketcher_CreateArcOfHyperbola`, `Sketcher_CreateFillet`,
  `Sketcher_CreateChamfer`, `Sketcher_CreatePoint`, `Sketcher_Trimming`,
  `Sketcher_Extend`, `Sketcher_Split`, `Sketcher_Projection`,
  `Sketcher_Intersection`, `Sketcher_CarbonCopy`, `Sketcher_Offset`,
  `Sketcher_Symmetry`, `Sketcher_Translate`, `Sketcher_Rotate`,
  `Sketcher_Scale`, `Sketcher_ToggleConstruction`,
  `Sketcher_SelectConstraints`, `Sketcher_SelectElementsWithDoFs`,
  `Sketcher_DeleteAllConstraints`, `Sketcher_ValidateSketch`,
  `Sketcher_ViewSketch`, `Sketcher_ViewSection`.
- Std (17): `Std_Measure`, `Std_ToggleClipPlane`, `Std_ViewFront`,
  `Std_ViewTop`, `Std_ViewRight`, `Std_ViewRear`, `Std_ViewBottom`,
  `Std_ViewLeft`, `Std_ViewIsometric`, `Std_ViewDimetric`,
  `Std_ViewTrimetric`, `Std_ViewFitAll`,
  `Std_ViewBoxZoom`, `Std_DrawStyle` (indices 6, 5, 3, 2),
  `Std_PerspectiveCamera`, `Std_OrthographicCamera`, `Std_TransformManip`.
  Deliberately **absent**: `Std_AlignToSelection` (the Evaluate tab's Normal To
  is `JellyJams_NormalTo`).
- Assembly (21): `Assembly_ActivateAssembly`, `Assembly_SolveAssembly`,
  `Assembly_InsertLink`, `Assembly_InsertNewPart`,
  `Assembly_CreateJointDistance`, `Assembly_CreateJointParallel`,
  `Assembly_CreateJointPerpendicular`, `Assembly_CreateJointCylindrical`,
  `Assembly_CreateJointFixed`, `Assembly_CreateJointAngle`,
  `Assembly_CreateJointRevolute`, `Assembly_CreateJointSlider`,
  `Assembly_CreateJointBall`, `Assembly_CreateJointGears`,
  `Assembly_CreateJointRackPinion`, `Assembly_CreateJointScrew`,
  `Assembly_CreateJointBelt`, `Assembly_ToggleGrounded`,
  `Assembly_CreateSimulation`, `Assembly_CreateBom`, `Assembly_CreateView`.
  Deliberately **absent**: `Assembly_CreateAssembly` (replaced by
  `JellyJams_NewAssembly`).
- TechDraw (29): `TechDraw_PageDefault`, `TechDraw_ProjectionGroup`,
  `TechDraw_View`, `TechDraw_SectionView`, `TechDraw_ComplexSection`,
  `TechDraw_DetailView`, `TechDraw_BrokenView`, `TechDraw_ClipGroup`,
  `TechDraw_Dimension`, `TechDraw_HorizontalDimension`,
  `TechDraw_VerticalDimension`, `TechDraw_ExtensionCreateHorizChainDimension`,
  `TechDraw_ExtensionCreateHorizCoordDimension`,
  `TechDraw_ExtensionCreateHorizChamferDimension`,
  `TechDraw_RichTextAnnotation`, `TechDraw_Balloon`,
  `TechDraw_ExtensionCircleCenterLines`, `TechDraw_ExtensionHoleCircle`,
  `TechDraw_FaceCenterLine`, `TechDraw_2LineCenterLine`,
  `TechDraw_2PointCenterLine`, `TechDraw_Hatch`, `TechDraw_GeometricHatch`,
  `TechDraw_LeaderLine`, `TechDraw_SpreadsheetView`,
  `TechDraw_ExtensionThreadHoleSide`, `TechDraw_ExtensionThreadHoleBottom`,
  `TechDraw_ExtensionThreadBoltSide`, `TechDraw_ExtensionThreadBoltBottom`.
- JellyJams: the 22 ids of section 2.7.

Fallback ids (used only when the primary id is not registered; never primary
ids themselves): `Part_DatumPlane` → `PartDesign_Plane`, `Part_DatumLine` →
`PartDesign_Line`, `Part_CoordinateSystem` → `PartDesign_CoordinateSystem`,
`Part_DatumPoint` → `PartDesign_Point`, `PartDesign_NewSketch` →
`Sketcher_NewSketch`, `Sketcher_Projection` → `Sketcher_External`,
`TechDraw_Dimension` → `TechDraw_LengthDimension`.

### 4.3 FreeCAD APIs and modules

- `FreeCADGui.listCommands()` decides which entries are built.
- `FreeCADGui.runCommand(id)` and `FreeCADGui.runCommand("Std_DrawStyle", i)`
  are invoked through the ribbon engine.
- Imported modules: `PartGui`, `SketcherGui`, `PartDesignGui`, `TechDrawGui`;
  `CommandCreateAssembly`, `CommandInsertLink`, `CommandInsertNewPart`,
  `CommandCreateJoint`, `CommandSolveAssembly`, `CommandCreateView`,
  `CommandCreateSimulation`, `CommandCreateBom`. Importing them registers
  their commands, which is exactly what FreeCAD itself does when those
  workbenches load. Python's module cache makes a later initialization of the
  Assembly workbench re-use them, so nothing is registered twice.
- FreeCAD icon resource names: `DrawStyleFlatLines`, `DrawStyleShaded`,
  `DrawStyleHiddenLine`, `DrawStyleWireFrame`. All other FreeCAD icons are
  taken from the commands themselves at runtime.

### 4.4 Button identities and objectNames

The ribbon engine derives Qt objectNames from button ids (`JellyJamsButton-<id>`,
`JellyJamsFlyout-<current variant id>`, `JellyJamsToggle-<shown variant id>`, with the `#`
of an indexed id written as `-`). The ids come from this content:

- plain id = command id (for example `JellyJamsButton-PartDesign_Pad`,
  `JellyJamsButton-JellyJams_RotateComponent`);
- indexed id = `<command id>#<index>`: `Std_DrawStyle#6`, `Std_DrawStyle#5`,
  `Std_DrawStyle#3`, `Std_DrawStyle#2`, `JellyJams_MakeDrawing#1` (objectNames
  `JellyJamsButton-Std_DrawStyle-6`, …, `JellyJamsButton-JellyJams_MakeDrawing-1`);
- the toggle is `JellyJamsToggle-PartDesign_NewSketch` / `JellyJamsToggle-Sketcher_LeaveSketch`;
- a flyout is `JellyJamsFlyout-<current variant id>`, for example
  `JellyJamsFlyout-Assembly_CreateJointDistance` until another mate is chosen.

### 4.5 Parameters

Only the remembered flyout choice is persisted, under
**`User parameter:BaseApp/Preferences/Mod/JellyJams/FlyoutChoices`** (String
entries; the semantics are in ribbon-engine). The key of each flyout is the id
of its first available variant. With all commands available, the 27 keys and
their allowed values are:

| Key | Allowed values (variant ids) |
|---|---|
| `PartDesign_Fillet` | `PartDesign_Fillet`, `PartDesign_Chamfer` |
| `PartDesign_LinearPattern` | `PartDesign_LinearPattern`, `PartDesign_PolarPattern`, `PartDesign_MultiTransform` |
| `Part_DatumPlane` | `Part_DatumPlane`, `Part_DatumLine`, `Part_CoordinateSystem`, `Part_DatumPoint` |
| `Part_ProjectionOnSurface` | `Part_ProjectionOnSurface`, `Part_Section` |
| `Sketcher_CreateLine` | `Sketcher_CreateLine`, `JellyJams_Centerline`, `JellyJams_MidpointLine`, `Sketcher_CreatePolyline` |
| `Sketcher_CreateRectangle` | `Sketcher_CreateRectangle`, `Sketcher_CreateRectangle_Center`, `Sketcher_CreateOblong` |
| `Sketcher_CreateSlot` | `Sketcher_CreateSlot`, `Sketcher_CreateArcSlot` |
| `Sketcher_CreateCircle` | `Sketcher_CreateCircle`, `Sketcher_Create3PointCircle` |
| `Sketcher_CreateArc` | `Sketcher_CreateArc`, `Sketcher_Create3PointArc` |
| `Sketcher_CreateBSplineByInterpolation` | `Sketcher_CreateBSplineByInterpolation`, `Sketcher_CreateBSpline`, `Sketcher_CreatePeriodicBSplineByInterpolation`, `Sketcher_CreatePeriodicBSpline` |
| `Sketcher_CreateEllipseByCenter` | `Sketcher_CreateEllipseByCenter`, `Sketcher_CreateArcOfEllipse`, `Sketcher_CreateArcOfParabola`, `Sketcher_CreateArcOfHyperbola` |
| `Sketcher_CreateFillet` | `Sketcher_CreateFillet`, `Sketcher_CreateChamfer` |
| `Sketcher_Trimming` | `Sketcher_Trimming`, `Sketcher_Extend`, `Sketcher_Split` |
| `Sketcher_Projection` | `Sketcher_Projection`, `Sketcher_Intersection`, `Sketcher_CarbonCopy` |
| `Sketcher_Translate` | `Sketcher_Translate`, `Sketcher_Rotate`, `Sketcher_Scale` |
| `Sketcher_SelectConstraints` | `Sketcher_SelectConstraints`, `Sketcher_SelectElementsWithDoFs`, `Sketcher_DeleteAllConstraints` |
| `Std_ToggleClipPlane` | `Std_ToggleClipPlane`, `Part_SectionCut` |
| `Assembly_InsertLink` | `Assembly_InsertLink`, `Assembly_InsertNewPart` |
| `Assembly_CreateJointDistance` | `Assembly_CreateJointDistance`, `Assembly_CreateJointParallel`, `Assembly_CreateJointPerpendicular`, `Assembly_CreateJointCylindrical`, `Assembly_CreateJointFixed`, `Assembly_CreateJointAngle` |
| `Assembly_CreateJointRevolute` | `Assembly_CreateJointRevolute`, `Assembly_CreateJointSlider`, `Assembly_CreateJointBall`, `Assembly_CreateJointGears`, `Assembly_CreateJointRackPinion`, `Assembly_CreateJointScrew`, `Assembly_CreateJointBelt` |
| `TechDraw_SectionView` | `TechDraw_SectionView`, `TechDraw_ComplexSection` |
| `TechDraw_Dimension` | `TechDraw_Dimension`, `TechDraw_HorizontalDimension`, `TechDraw_VerticalDimension`, `TechDraw_ExtensionCreateHorizChainDimension`, `TechDraw_ExtensionCreateHorizCoordDimension`, `TechDraw_ExtensionCreateHorizChamferDimension` |
| `JellyJams_Note` | `JellyJams_Note`, `TechDraw_RichTextAnnotation` |
| `TechDraw_ExtensionCircleCenterLines` | `TechDraw_ExtensionCircleCenterLines`, `TechDraw_ExtensionHoleCircle` |
| `TechDraw_FaceCenterLine` | `TechDraw_FaceCenterLine`, `TechDraw_2LineCenterLine`, `TechDraw_2PointCenterLine` |
| `TechDraw_Hatch` | `TechDraw_Hatch`, `TechDraw_GeometricHatch` |
| `TechDraw_ExtensionThreadHoleSide` | `TechDraw_ExtensionThreadHoleSide`, `TechDraw_ExtensionThreadHoleBottom`, `TechDraw_ExtensionThreadBoltSide`, `TechDraw_ExtensionThreadBoltBottom` |

When a fallback replaces a first variant, the key and the value use the
fallback id (for example `PartDesign_Plane` on a build without
`Part_DatumPlane`). These keys must stay stable across JellyJams versions so
that users keep their choices. Reordering variants is allowed, but changing a
flyout's **first** variant changes its key, and users then lose their
remembered choice for that flyout.

### 4.6 Documents

The ribbon content stores nothing in FreeCAD documents and adds no document
properties.

---

## 5. Persistence and restore rules

- The only persistent state related to this content is the remembered flyout
  variants (section 4.5). It is a JellyJams-owned user preference in the
  JellyJams group. It is kept when the workbench is left or FreeCAD quits. It
  is not part of the exact-restore stash and needs no crash recovery.
- The content changes no FreeCAD-owned parameter. Importing FreeCAD modules
  (section 3) changes no settings.
- Nothing else persists: the tab order, captions and button kinds are
  constant, and the start tab is always `Features` in a new session.

---

## 6. Edge cases and failure handling

1. **Missing command (other FreeCAD version, workbench not installed).** The
   entry is skipped without leaving a gap. The engine reports all skipped ids
   in one Report-view warning. Other entries are unaffected.
2. **Fallback.** Each entry with a fallback (section 4.2) uses the fallback id
   when its primary id is missing, and the engine logs the substitution. With
   neither, the entry is skipped. A FreeCAD build that has only the fallback
   ids still gets every entry (167 ids).
3. **Partially missing flyout.** The missing variants are dropped and the
   others remain, in order. The default variant is the first one remaining,
   and the flyout's persisted key becomes that variant's id. A flyout with
   one variant left remains a flyout.
4. **Fully missing flyout / stack / group.** It disappears entirely. An empty
   group also produces no separator (for example, without `JellyJams_Diagnostics`
   the Evaluate tab has two separators).
5. **Stack reflow.** If a stack entry is missing, the following entries move
   up so that no cell stays empty (filled column by column).
6. **Toggle with a missing state.** The slot becomes a plain large button for
   the remaining command, or disappears if both are missing (ribbon-engine).
7. **Assembly workbench missing or broken.** If the Assembly command modules
   cannot be imported, the engine logs this (log level, not a warning), and
   only the `Assembly_*` buttons are missing. New Assembly
   (`JellyJams_NewAssembly`), Make Drawing (`JellyJams_MakeDrawing#1`), Move Component
   (`Std_TransformManip`) and Rotate Component (`JellyJams_RotateComponent`) remain on the
   Assembly tab.
8. **GUI module import failure** (`PartGui`, `SketcherGui`, `PartDesignGui`,
   `TechDrawGui`). The engine warns with the module name and the reason,
   continues, and skips only the affected commands.
9. **Group-command sub-entries.** If `Std_DrawStyle` has never been placed in
   a FreeCAD toolbar or menu, its sub-entry actions may not exist yet. The
   display-style buttons must still show the named FreeCAD icons of
   section 4.3 and their SolidWorks names.
10. **Duplicate command.** `JellyJams_MakeDrawing` appears twice: as `JellyJams_MakeDrawing`
    on the Drawing tab and as `JellyJams_MakeDrawing#1` on the Assembly tab. Both are
    independent buttons with the same effect and the same enabled state. The
    command must work no matter which copy invokes it.
11. **`JellyJams_*` command not registered** (owning area failed to initialize). The
    button is treated like any missing command (skipped and reported). It
    never raises.
12. **Remembered variant no longer available.** The default variant is shown.
    The stored value is left untouched (ribbon-engine).
13. **Future FreeCAD renames.** Where a FreeCAD release renames a command,
    the new id is added as the primary id and the old one as the fallback (as
    for Convert Entities and the datums), so older and newer releases both
    work.

---

## 7. Acceptance criteria

Unless stated otherwise: FreeCAD 1.1.4 with stock modules, a fresh user
profile (`FREECAD_USER_HOME` pointing to an empty folder), and JellyJams
activated. "The ribbon" is the dock with objectName `JellyJamsCommandManager`.

1. The ribbon's tab titles are exactly `Features`, `Sketch`, `Evaluate`,
   `Assembly`, `Drawing`, in this order. There is no "View" tab and no
   language button.
2. Right after the first activation, `Features` is the current tab.
3. The Report view shows **no** JellyJams warning about skipped commands.
4. The ribbon offers exactly 167 distinct button ids: 81 plain buttons, 27
   flyouts with 84 variants in total, and 1 toggle with 2 states (counted via
   the engine's test services, or by inspecting widgets and menus). The tab
   pages hold 21, 22, 22, 13 and 31 tool buttons (Features to Drawing).
5. Each tab has the groups of section 2.5, separated by vertical lines:
   Features 3, Sketch 3, Evaluate 3, Assembly 3, Drawing 4 separators.
6. Every large button's caption, every text-stack text and every flyout menu
   entry matches the tables (one-line names in menus and text stacks).
   Examples: the menu of the first Sketch icon-stack flyout reads "Line,
   Centerline, Midpoint Line, Polyline". The Pattern flyout menu reads
   "Linear Pattern, Circular Pattern, Multi-Transform". The Mate flyout menu
   reads "Coincident/Distance, Parallel, Perpendicular, Concentric, Lock,
   Angle".
7. Clicking each button, or choosing each flyout variant, runs the command
   listed in the tables. The tooltip names that FreeCAD command next to the
   SolidWorks name. For example: "Shell" starts FreeCAD's Thickness feature,
   "Hole Wizard" starts Hole, "Convert Entities" runs `Sketcher_Projection`,
   "Coincident/Distance" starts a Distance joint, "Concentric" starts a
   Cylindrical joint, and "Crop View" runs `TechDraw_ClipGroup`.
8. On Evaluate, with a part shown in the 3D view: "Shaded With Edges",
   "Shaded", "Hidden Lines Removed" and "Wireframe" set FreeCAD's draw style
   to Flat lines, Shaded, Hidden line and Wireframe, respectively (visible in
   View → Draw style). Their icons are FreeCAD's `DrawStyleFlatLines`,
   `DrawStyleShaded`, `DrawStyleHiddenLine` and `DrawStyleWireFrame`.
9. On Evaluate, "Back" shows the rear view (`Std_ViewRear`). The nine
   orientation buttons, Zoom to Fit, Zoom to Area, Section View
   (clip plane), Perspective and Orthographic behave like the same FreeCAD
   commands run from FreeCAD's own menus. Normal To
   (`JellyJamsButton-JellyJams_NormalTo`, icon `normal_to.svg`) runs
   `JellyJams_NormalTo` and behaves like `Ctrl+8` ([orientation.md](orientation.md) 2.6);
   no button runs `Std_AlignToSelection`.
10. In a profile where Sketcher, Part Design, TechDraw and Assembly were never
    opened, all Sketch, Features, Drawing and Assembly buttons are present on
    first activation.
11. After activating JellyJams, open the Assembly workbench via the workbench
    selector. No error about duplicate command registration appears, and the
    Assembly workbench works normally.
12. The Sketch tab's drawing tools form one icon-only grid of small buttons, 3
    rows by 4 columns, where column 4 holds only row 1. Row 1 reads Line ▾,
    Circle ▾, Spline ▾, Point. Row 2 reads Corner Rectangle ▾, Centerpoint
    Arc ▾, Ellipse ▾. Row 3 reads Straight Slot ▾, Polygon, Sketch Fillet ▾.
    The Evaluate orientation grid is 3 × 3: Front, Back, Isometric over Top,
    Bottom, Dimetric over Right, Left, Trimetric. The Drawing sheet-sketch
    grid reads Line, Centerpoint Arc over Corner Rectangle, Polygon over
    Circle.
13. Text stacks: Features 4 stacks of 3; Sketch 2 stacks (3 entries, the
    middle one a small flyout showing "Move Entities"; 4 entries in two
    columns, the first a small flyout showing "Display/Delete Relations");
    Evaluate 2 stacks (3 entries; 6 entries in two columns); Assembly 2 stacks
    (2, 3 entries); Drawing 5 stacks of 3 (the last entry of the fifth a
    small flyout with the fixed text "Cosmetic Thread").
14. The toggle in Sketch S1 reads "Sketch" outside a sketch and "Exit Sketch"
    while a sketch is being edited.
15. The Assembly tab has no `Assembly_CreateAssembly` button. "New Assembly"
    runs `JellyJams_NewAssembly`, which creates a new document.
16. "New Assembly", "Make Drawing", "New Motion Study", "Bill of Materials"
    and "Exploded View" are standalone large buttons on the Assembly tab
    (objectNames `JellyJamsButton-JellyJams_NewAssembly`, `JellyJamsButton-JellyJams_MakeDrawing-1`,
    `JellyJamsButton-Assembly_CreateSimulation`, `JellyJamsButton-Assembly_CreateBom`,
    `JellyJamsButton-Assembly_CreateView`). "Rotate Component" is a plain small button
    (`JellyJamsButton-JellyJams_RotateComponent`). "Concentric" has no plain button; it is a
    variant of the Mate flyout.
17. "Make Drawing" exists on the Drawing tab (`JellyJamsButton-JellyJams_MakeDrawing`) and on
    the Assembly tab (`JellyJamsButton-JellyJams_MakeDrawing-1`), not on Features. With a part
    open, both produce the same result, and both are enabled or disabled
    together.
18. The Drawing tab contains at least Standard 3 View, Model View, Section
    View, Detail View, Smart Dimension, Balloon, Save as PDF and Save as DXF
    (`TechDraw_ProjectionGroup`, `TechDraw_View`, `TechDraw_SectionView`,
    `TechDraw_DetailView`, `TechDraw_Dimension`, `TechDraw_Balloon`,
    `JellyJams_SaveAsPDF`, `JellyJams_SaveAsDXF`).
19. Titled flyouts keep their caption: after "Concentric" is chosen from the
    "Mate" flyout, it still reads "Mate", its icon is the Concentric icon, its
    main part runs `Assembly_CreateJointCylindrical`, and its tooltip begins
    with `Mate: `. The same holds for "Reference Geometry", "Curves",
    "Mechanical Mates" and "Cosmetic Thread".
20. Choosing "Perimeter Circle" from the circle flyout and restarting FreeCAD
    leaves `user.cfg` with the String `Sketcher_CreateCircle` =
    `Sketcher_Create3PointCircle` under `BaseApp/Preferences/Mod/JellyJams/FlyoutChoices`.
    After the restart, that flyout shows Perimeter Circle.
21. Fallback (test harness with a command list lacking
    `Sketcher_Projection` but providing `Sketcher_External`): the "Convert
    Entities" variant exists and runs `Sketcher_External`. No skipped-command
    warning names it. With every primary id that has a fallback replaced by
    its fallback, all 167 ids are still present.
22. Missing commands (test harness lacking `PartDesign_SubtractiveLoft` and
    `Sketcher_CreateArcSlot`): "Lofted Cut" is absent and the cut stack shows
    "Swept Cut" and "Helical Cut" with no gap. The slot flyout keeps only
    "Straight Slot". One warning lists both ids. Every other button is present.
23. If the Assembly command modules are unavailable (test harness), all
    `Assembly_*` buttons are absent. "New Assembly", "Make Drawing", "Move
    Component" and "Rotate Component" remain on the Assembly tab. No warning
    appears, only a log-level message.
24. Every button for a FreeCAD command shows the same icon as that command in
    FreeCAD's own toolbars or menus. Every `JellyJams_*` button shows a JellyJams
    original icon. No icon in the ribbon is FreeCAD's red "missing icon"
    placeholder or empty.
25. The installed add-on contains no copies of FreeCAD or third-party icon
    files. No file name, objectName, command id or parameter key of the
    ribbon contains "SolidWorks".
26. All captions, menu entries and tooltips are in English and use the
    SolidWorks terms of section 2.5, or the descriptive names of section 2.8.
27. Compare `user.cfg` before activation with `user.cfg` after leaving
    JellyJams and quitting. The ribbon content added nothing outside
    `BaseApp/Preferences/Mod/JellyJams/FlyoutChoices`, and added only keys for flyouts
    the user chose from. Saved `.FCStd` documents contain no ribbon-related
    properties.
28. The only `JellyJams_*` command without a ribbon button is
    `JellyJams_ViewOrientation`; every other registered JellyJams command,
    `JellyJams_NormalTo` included, has one.

## Measure selection behavior

The Evaluate Measure entry retains the native command id and icon for availability,
but ribbon dispatch opens JellyJams' temporary task. It displays geometry-specific
sizes for one pick, distance/angle for two picks, and appropriate totals for multiple
edges/faces. White callouts have black borders/text and a label/value divider.

The complete normative behavior, official SolidWorks measurement catalog, supported
and unsupported modes, and acceptance cases live in [Measure](measure.md). This
supersedes the earlier distance-only specification. Hole centres/axes remain the
default, clearance is explicit, and empty selection removes all owned annotations.
Measure is highlighted while its task remains active; clicking it again stops the
tool and removes all owned measurements. Clearing picks alone keeps it active.
