# JellyJams specification: Add Relations panel (sketch relations)

> **Implemented in:** [`jellyjams/relations_rules.py`](../../jellyjams/relations_rules.py) (pure entity, offer and existing-relation rules), [`relations_panel.py`](../../jellyjams/relations_panel.py) (the panel and its selection observer), [`panel_host.py`](../../jellyjams/panel_host.py) (task-panel hosting and fallback dock, shared with the Add Mate panel); icons via [`icons.py`](../../jellyjams/icons.py) and [`relation_collinear.svg`](../../resources/icons/relation_collinear.svg), [`relation_concentric.svg`](../../resources/icons/relation_concentric.svg), [`relation_midpoint.svg`](../../resources/icons/relation_midpoint.svg).
>
> **Status:** see [../status.md](../status.md)

This specification describes what the feature does. Target: FreeCAD 1.1+
(verified facts from FreeCAD 1.1.4), PySide6/Qt 6, English only.

---

## 1. Purpose

While the user edits a sketch inside the JellyJams workbench and has one or more
sketch entities selected, JellyJams shows a SolidWorks-style **Add Relations**
PropertyManager section at the top of FreeCAD's Tasks panel. It:

- lists the **Selected Entities** with SolidWorks-like names,
- lists the **Existing Relations** (geometric constraints only, no dimensions)
  that involve those entities and lets the user delete them,
- offers **Add Relations** buttons for ONLY the relations that FreeCAD will
  actually accept for the current selection, each of which runs the matching
  FreeCAD Sketcher constraint command on that selection.

The goal is the SolidWorks workflow "select entities first, then pick a
relation", with no offer that FreeCAD would reject with a "wrong selection"
message.

This feature defines no `JellyJams_*` command ids and no parameters. It is independent of
the Sketch tab's Relations group on the ribbon (owned by the ribbon area), which
has no buttons for individual relations.

---

## 2. User-visible behavior and UI

### 2.1 When the panel is visible

The shared host follows the current document's task panel, including hosts that
wrap and stack several document panels. An inactive document's panel is never
used; lookup remains possible while the Tasks dock is behind another dock tab.

The panel is visible if and only if ALL of the following hold:

1. The JellyJams workbench is the active workbench (the feature is enabled on
   workbench activation and disabled on deactivation, see section 3).
2. The active GUI document has an object in edit mode, and that object is a
   sketch (`TypeId == "Sketcher::SketchObject"`).
3. The current FreeCAD selection contains at least one recognized sketch entity
   (section 4.2) of THAT sketch.

In every other situation the panel (and the fallback dock, if one exists) is
hidden. Examples: nothing selected; only constraints/dimensions selected; the
sketch was closed; a non-sketch object is in edit; the user switched to another
workbench.

### 2.2 Placement

- **Primary placement:** the panel is inserted as the FIRST (topmost) item in
  FreeCAD's task panel content, i.e. the widget whose Qt class name is
  `Gui::TaskView::TaskPanel` and which is the content widget of a QScrollArea
  inside FreeCAD's Tasks dock (dock objectName `Tasks`; tolerate variants by
  accepting the first QDockWidget whose objectName contains `Tasks`, then
  `TaskView`, `TaskList`, `Task`, in that order). FreeCAD's own sketch task
  sections (solver messages, constraints list, elements list, etc.) remain
  below the JellyJams panel.
- Whenever the panel is shown or refreshed in the primary placement, the Tasks
  dock is raised. When Tasks is tabbed with another dock (for example the Model
  tree, as in FreeCAD's default layout), this brings the Tasks tab
  ("PropertyManager") to the front. In the JellyJams window layout Tasks is
  docked on the right above the Report view ([window-layout](window-layout.md)
  2.1).
- The panel is inserted only once; refreshes reuse the same widget in place.
- **Fallback placement:** if no such task panel can be found (other FreeCAD
  version or layout), the panel is hosted in its own QDockWidget:
  - window title `Relations`,
  - objectName `JellyJamsPropertyManagerDock`,
  - in the main window's LEFT dock area,
  - shown and raised whenever the panel is shown, hidden whenever the panel
    is hidden.
  Only one such dock may ever exist at a time.
- If FreeCAD destroys the underlying Qt widget of the panel (or of the
  fallback dock), the next refresh must transparently create a new one; no
  errors, no duplicates. A destroyed widget must be detected via
  `shiboken6.isValid()` (or an equivalent liveness check) before reuse.
- If the panel currently lives in the fallback dock and the task panel becomes
  available later, the panel moves into the task panel.

### 2.3 Layout of the panel (top to bottom)

All widget class types below matter because the theme's stylesheet selectors
target them (section 2.5).

| # | Element | Qt type | objectName | Content / behavior |
|---|---------|---------|------------|--------------------|
| 0 | Panel frame | `QFrame` | `JellyJamsPropertyManager` | Vertical layout, small margins (about 6 px) and spacing (about 4 px). |
| 1 | Title | `QLabel` | `JellyJamsPropertyManagerTitle` | Text: `Add Relations`. |
| 2 | Heading | `QLabel` | `JellyJamsSectionCaption` | Text: `Selected Entities`. |
| 3 | Selected entities list | `QListWidget` | `JellyJamsItemList` | One row per recognized selected entity, in the order FreeCAD reports the selection. Display only. |
| 4 | Heading | `QLabel` | `JellyJamsSectionCaption` | Text: `Existing Relations`. |
| 5 | Existing relations list | `QListWidget` | `JellyJamsItemList` | One row per existing relation (section 4.4). Extended multi-selection (click, Ctrl+click, Shift+click). |
| 6 | Delete button | `QPushButton` | (none required) | Text `Delete`; tooltip says it deletes the selected existing relations. Disabled when the Existing Relations list is empty. |
| 7 | Heading | `QLabel` | `JellyJamsSectionCaption` | Text: `Add Relations`. |
| 8 | Relation buttons | one `QToolButton` per offered relation, stacked vertically inside a plain container, tight spacing (about 1 px) | (none required) | See 2.4. Rebuilt on every refresh to exactly the offered set, in the specified order (section 4.3). |
| 9 | Hint label | `QLabel`, word-wrapped | (none required) | Text: `No relations can be added to this selection.` Visible only when zero relations are offered. |

The two lists deliberately share the objectName `JellyJamsItemList`.

**List sizing (SolidWorks-like compact lists):** each list's fixed height
equals its row count times the row height, with at least 1 row and at most 6
rows shown (more rows scroll), using a row height of at least 18 px, plus a few
pixels of frame padding. Height is recomputed on every refresh.

**Existing relation row text:** the relation's display name (table in 4.4)
followed by its 1-based constraint number in parentheses, for example
`Horizontal (no. 1)` (exact spacing is free). The number equals FreeCAD's own constraint numbering
(constraint index + 1, as in FreeCAD's "ConstraintN" names).

### 2.4 Relation buttons

Each offered relation is one flat (auto-raise) QToolButton that:

- shows its icon with the label text beside it (text-beside-icon style),
- expands horizontally to the full panel width, fixed height,
- uses the SolidWorks label from the table in 4.3 as its text,
- uses as tooltip the FreeCAD command's own tooltip (`toolTip` entry of
  `FreeCADGui.Command.get(<command id>).getInfo()`), falling back to the label
  if that is unavailable,
- on click runs the mapped FreeCAD command with `FreeCADGui.runCommand(<id>)`.

**Icons (project rule: no bundled third-party assets):**

- Relations whose SolidWorks meaning equals the FreeCAD command (Horizontal,
  Vertical, Perpendicular, Parallel, Tangent, Coincident, Equal, Symmetric,
  Fix, On entity, Block) show FreeCAD's OWN icon for the mapped command, resolved at
  runtime with the same icon-lookup rules the ribbon uses for FreeCAD commands
  (command's QAction icon, then FreeCAD's `:/icons/` resources, then
  `FreeCADGui.getIcon()`).
- Collinear, Concentric and Midpoint reuse another relation's FreeCAD command
  (Tangent, Coincident, Symmetric). To stay distinguishable they show NEW
  original JellyJams icons drawn for this project (one each, depicting
  collinear lines, concentric circles, a point at a line's midpoint). If such
  an icon cannot be loaded, fall back to the mapped command's FreeCAD icon.
  Icon file names must not contain "SolidWorks".
- If no icon can be resolved at all, the button shows text only (no error).

### 2.5 Styling

The JellyJams theme stylesheet (theme area; block between
`/* @jellyjams-stylesheet-open */` and `/* @jellyjams-stylesheet-close */` on the main window) must
contain rules for these selectors; this area only has to set the objectNames
and widget types listed above:

| Selector | Intended look (SolidWorks-like light theme) |
|----------|---------------------------------------------|
| `QFrame#JellyJamsPropertyManager` | Panel (white) background, 1 px accent-blue border, ~3 px corner radius. |
| `QFrame#JellyJamsPropertyManager QLabel` | Normal text color. |
| `QLabel#JellyJamsPropertyManagerTitle` | Bold, small bottom padding. |
| `QLabel#JellyJamsSectionCaption` | Secondary (dim) text color, 1 px bottom border line in the border color, small top padding (section divider). |
| `QListWidget#JellyJamsItemList` | Window-colored background, normal text, 1 px border; selected item uses the theme's selection color with normal text. |
| `QFrame#JellyJamsPropertyManager QToolButton` | Normal text, left-aligned, small padding, transparent 1 px border, ~3 px radius. |
| `QFrame#JellyJamsPropertyManager QToolButton:hover` | Hover background plus 1 px accent border. |

These objectNames are a shared contract: other JellyJams panels (the assembly
Mates panel, the drawing sheet-properties panel) reuse `JellyJamsPropertyManager`,
`JellyJamsPropertyManagerTitle`, `JellyJamsSectionCaption` and `JellyJamsItemList` to get the
same look. They must not be renamed.

Without the theme (e.g. it failed to apply) the panel must still be fully
usable with FreeCAD's default style.

---

## 3. Triggers and timing

| Event | Effect |
|-------|--------|
| JellyJams workbench `Activated()` | Enable the feature: register a selection observer with `FreeCADGui.Selection.addObserver`. Idempotent: repeated activation must never register a second observer (exactly one JellyJams relations observer at any time). Failure is logged as a Report-view warning and must not block the rest of workbench activation. |
| JellyJams workbench `Deactivated()` | Disable the feature: remove the observer with `FreeCADGui.Selection.removeObserver`, hide the panel and the fallback dock. Errors while removing are ignored. After this, no selection change may show the panel. |
| Any selection notification (add, remove, set, clear) | Schedule ONE deferred refresh on the next Qt event-loop turn (zero-delay single-shot). A burst of notifications (box selection, clear followed by add, etc.) must collapse into a single rebuild. |
| Deferred refresh | Re-evaluate section 2.1. If visible: rebuild all three sections from the current selection and sketch state, ensure placement (2.2), show. Otherwise hide. A refresh while the feature is disabled always hides. |
| Relation button click | Run the mapped FreeCAD command (section 4.3) on the current selection. FreeCAD then adds the constraint(s) in its own undo transaction and normally clears the selection, which (via the selection notification) hides the panel, as in SolidWorks. After the command returns, the panel must reflect the then-current selection (a deferred refresh is allowed and recommended so a still-present selection shows the new existing relation). |
| Delete button click | Delete the constraints selected in the Existing Relations list (section 4.5), then schedule a deferred refresh so the lists update. With no rows selected, nothing happens. |
| Leaving sketch edit / closing the document | FreeCAD's selection changes trigger a refresh; since no sketch is in edit, the panel hides. |

Because sketch constraint commands in FreeCAD apply immediately when a
suitable selection exists (rather than entering an interactive tool), and the
panel only appears with a selection, a click applies the relation at once.

The feature has no effect on FreeCAD quitting (FreeCAD does not call
`Deactivated()` on quit; nothing needs to be saved or restored).

---

## 4. FreeCAD state read or changed

### 4.1 Which sketch

- Sketch in edit: `FreeCADGui.ActiveDocument.getInEdit()` returns a view
  provider; its `.Object` must have `TypeId == "Sketcher::SketchObject"`. No
  active GUI document, nothing in edit, or another object type in edit means
  "no sketch".
- Selection: `FreeCADGui.Selection.getSelectionEx()`; only entries whose
  `.Object` is that sketch object are used; their `.SubElementNames` are
  collected in order. Selection entries of other objects are ignored.

### 4.2 Recognizing selected entities

Sketcher selection sub-element names and FreeCAD's GeoId/PosId conventions
(public Sketcher facts):

- GeoId >= 0: the sketch's own geometry, `Geometry[GeoId]`; `EdgeN` is GeoId
  `N-1`.
- GeoId -1: horizontal axis (`H_Axis`); GeoId -2: vertical axis (`V_Axis`).
- External (converted) edges: `ExternalEdgeN` is GeoId `-(N+2)` (first
  external edge = -3). For a negative GeoId g the geometry object is
  `ExternalGeo[-g-1]` (entries 0 and 1 of `ExternalGeo` are the two axes).
- Origin: `RootPoint` is GeoId -1, PosId 1 (FreeCAD treats the origin as the
  start point of the horizontal axis).
- Vertices: `VertexN` maps to (GeoId, PosId) via
  `SketchObject.getGeoVertexIndex(N-1)`. PosId: 1 start, 2 end, 3 center/mid.
  A vertex that maps to (-1, 1) IS the origin.

Entity kind is determined from the geometry's `TypeId`:

| Geometry `TypeId` | Kind | Name stem in Selected Entities |
|-------------------|------|--------------------------------|
| `Part::GeomLineSegment` | line | `Line` |
| `Part::GeomCircle` | circle | `Circle` |
| `Part::GeomArcOfCircle` | arc | `Arc` |
| `Part::GeomEllipse` | ellipse | `Ellipse` |
| `Part::GeomArcOfEllipse` | partial ellipse | `Partial ellipse` |
| `Part::GeomBSplineCurve` | spline | `Spline` |
| `Part::GeomPoint` | point | `Point` |
| anything else (hyperbola, parabola, ...) or unknown | generic edge | `Edge` |

Entities and their display labels:

| Sub-element name | Entity class | Label |
|------------------|--------------|-------|
| `RootPoint` | point (origin) | `Origin` |
| `H_Axis` | edge, kind axis | `Horizontal axis` |
| `V_Axis` | edge, kind axis | `Vertical axis` |
| `ExternalEdgeN` | edge of the external geometry's kind, marked external | `ConvertedN` |
| `EdgeN` whose geometry is a `Part::GeomPoint` | point (PosId 1) | `PointN` |
| `EdgeN` otherwise | edge of its kind | stem + N, e.g. `Line1`, `Circle3`, `Arc4`, `Ellipse5`, `Partial ellipse6`, `Spline7`, `Edge8` |
| `VertexN` mapping to the origin | point (origin) | `Origin` |
| `VertexN` otherwise | point; marked external when its GeoId <= -3 | `PointN` (N = the vertex number) |
| anything else (e.g. `ConstraintN`, malformed names) | ignored | - |

A name that cannot be resolved (bad index, API error) is skipped silently;
the remaining names are still used. Construction geometry is treated exactly
like normal geometry.

Terms used below:

- **point**: any point entity (sketch vertex, sketch Point, external vertex,
  Origin). **edge**: every other entity (including axes and external edges).
- **own geometry**: GeoId >= 0 (not an axis, not the origin, not external).
- **fixed**: everything that is not own geometry, i.e. the axes, the Origin
  and external geometry. This is FreeCAD's notion of fixed geometry
  (`isPointOrSegmentFixed` in `Sketcher/Gui/Utils.cpp`: any GeoId <= -1),
  except that FreeCAD also counts blocked geometry, which the panel does not
  detect (edge case 9 in section 6).
- **line segment**: a line edge, own or external. **line-like edge**: a line
  segment or an axis (FreeCAD stores both axes as line segments, so its
  line-segment test accepts them). **own line**: a line segment that is own
  geometry.
- **conic**: circle, arc, ellipse or partial ellipse (own or external).
- **point of an edge**: a selected point whose GeoId equals the edge's GeoId
  (its start, end or center point). The Origin is a point of the horizontal
  axis.

### 4.3 Offered relations: capability table and command mapping

**Catalogue.** Each button runs one FreeCAD Sketcher command. Buttons always
appear in the order of this table: the familiar SolidWorks relation order,
with On entity and Block (no direct SolidWorks counterpart) last.

| Order | Label (button text) | FreeCAD command id | Note |
|-------|---------------------|--------------------|------|
| 1 | Horizontal | `Sketcher_ConstrainHorizontal` | |
| 2 | Vertical | `Sketcher_ConstrainVertical` | |
| 3 | Collinear | `Sketcher_ConstrainTangent` | For two lines, FreeCAD's tangency places both ends of one line on the other (`Sketch::addTangentConstraint`), so the lines end up collinear. |
| 4 | Perpendicular | `Sketcher_ConstrainPerpendicular` | |
| 5 | Parallel | `Sketcher_ConstrainParallel` | |
| 6 | Tangent | `Sketcher_ConstrainTangent` | |
| 7 | Concentric | `Sketcher_ConstrainCoincident` | Given only conics, the coincident command joins their centers. |
| 8 | Midpoint | `Sketcher_ConstrainSymmetric` | Given one line and one point, the symmetric command makes the line's two ends symmetric about the point, which centers the point on the line. |
| 9 | Coincident | `Sketcher_ConstrainCoincident` | |
| 10 | Equal | `Sketcher_ConstrainEqual` | |
| 11 | Symmetric | `Sketcher_ConstrainSymmetric` | |
| 12 | Fix | `Sketcher_ConstrainLock` | |
| 13 | On entity | `Sketcher_ConstrainPointOnObject` | |
| 14 | Block | `Sketcher_ConstrainBlock` | |

All 14 command ids exist in FreeCAD 1.1.4 and must be verified to exist
(`FreeCADGui.listCommands()`) by the test suite.

**Capability table.** For every relation the rules module lists the selection
shapes the mapped command accepts in FreeCAD 1.1 (selection handling of each
command in `src/Mod/Sketcher/Gui/CommandConstraints.cpp`), narrowed where
FreeCAD would accept the selection but produce something other than the
SolidWorks relation of that name. A shape fixes the number of selected points
**P** and edges **E** (recognized entities only), the kinds every selected
edge may have, and further conditions that must all hold. A relation is
offered when at least one of its shapes fits. The offered set does not depend
on the order in which the entities were selected.

| Relation | P | E | Every edge is | Further conditions | Why (FreeCAD 1.1 behavior) |
|----------|---|---|---------------|--------------------|----------------------------|
| Horizontal, Vertical | 0 | >= 1 | a line segment | none of the edges is fixed (own lines only) | The command refuses any edge that is not a line segment. A fixed line cannot be turned. When an edge is selected the command ignores selected points, so mixed selections get no offer. |
| Horizontal, Vertical | >= 2 | 0 | - | at most one point is fixed | The points are aligned as a chain, each with the next; the command refuses more than one fixed point. |
| Collinear | 0 | 2 | line-like | not both edges are fixed | Tangency between two fixed items is refused. |
| Perpendicular | 0 | 2 | line-like | not both edges are fixed | FreeCAD also accepts a line with a curve (the line becomes normal to the curve), which is not this relation. |
| Parallel | 0 | >= 2 | line-like | at most one edge is fixed | The lines are chained pairwise; a second fixed edge stops the command. |
| Tangent | 0 | 2 | anything but a spline | not both edges are fixed, and at least one edge is not line-like | FreeCAD supports tangency with a B-spline only through a point. Two line-like edges are the Collinear case. |
| Concentric | 0 | >= 2 | a conic | at most one edge is fixed | The command accepts circles, arcs, ellipses and partial ellipses. Each curve is paired with the first one, and a pair of fixed curves stops the command. |
| Midpoint | 1 | 1 | a line segment (not an axis) | the point is not a point of the line, and not both are fixed | The command refuses a line with its own end point and a fixed point with a fixed line. An axis has no real ends to center on. |
| Coincident | >= 2 | 0 | - | at most one point is fixed, and no two points belong to the same geometry | Each point is joined to the first; a pair of fixed points stops the command and a pair on one geometry is skipped. |
| Equal | 0 | >= 2 | a line segment or a conic | at most one edge is fixed, and all edges are lines, or all are circles/arcs, or all are ellipses/partial ellipses | The command refuses axes, B-splines, mixed kinds and a second fixed edge. Arcs may be equal to circles, partial ellipses to ellipses. |
| Symmetric | 3 | 0 | - | not all three points are fixed | The last point picked is the center of symmetry. |
| Symmetric | 2 | 1 | line-like | not all three items are fixed, and not both points are points of the line | The command refuses a line with its own two end points. |
| Fix | 1 | 0 | - | the point is not fixed | With several vertices the lock command fixes them relative to the last one instead of in place, and an external vertex only gets reference dimensions. |
| On entity | 1 | >= 1 | anything | for every point/edge pair: the point is not a point of that edge, and not both are fixed | The command skips a point on its own edge and refuses a fixed point on a fixed edge (this also rules out the Origin with either axis). |
| On entity | >= 1 | 1 | anything | same as above | |
| Block | 0 | >= 1 | anything | none of the edges is fixed | The command refuses vertices and fixed edges. It also refuses a sketch with conflicts or redundancies; FreeCAD reports that case itself. |

If no shape fits, no button is shown and the hint label is visible.

**Worked reference results** (normative; also used in section 7). Reference
sketch: own geometry in this order: Line1, Line2, Circle3, Arc4, Ellipse5, a
sketch Point6, Spline7; one external line (Converted1).

| Selection | Offered (in order) |
|-----------|--------------------|
| Line1 | Horizontal, Vertical, Block |
| Line1 + Line2 | Horizontal, Vertical, Collinear, Perpendicular, Parallel, Equal, Block |
| Line1 + horizontal axis | Collinear, Perpendicular, Parallel |
| Line1 + Line2 + horizontal axis | Parallel |
| Converted1 + horizontal axis | (none; hint shown) |
| Converted1 + Line1 | Collinear, Perpendicular, Parallel, Equal |
| Circle3 + Arc4 | Tangent, Concentric, Equal, Block |
| Line1 + Circle3 | Tangent, Block |
| Circle3 + Ellipse5 | Tangent, Concentric, Block |
| Circle3 + Arc4 + Ellipse5 | Concentric, Block |
| Spline7 | Block |
| Arc4 + Spline7 | Block |
| start point of Line1 | Fix |
| Origin | (none; hint shown) |
| start point of Line1 + start point of Line2 | Horizontal, Vertical, Coincident |
| start and end point of Line1 | Horizontal, Vertical |
| start point of Line1 + Origin | Horizontal, Vertical, Coincident |
| start point of Line1 + start point of Line2 + Point6 | Horizontal, Vertical, Coincident, Symmetric |
| start point of Line2 + Line1 | Midpoint, On entity |
| start point of Line2 + Converted1 | Midpoint, On entity |
| start point of Line2 + horizontal axis | On entity |
| Origin + Line1 | Midpoint, On entity |
| Origin + horizontal axis | (none; hint shown) |
| start point of Line1 + Line1 | (none; hint shown) |
| Point6 + Line1 + Line2 | On entity |
| start point of Line1 + Line1 + Line2 | (none; hint shown) |
| start and end point of Line2 + Line1 | Symmetric, On entity |
| start and end point of Line1 + Line1 | (none; hint shown) |
| start point of Line2 + Circle3 | On entity |
| a constraint/dimension only | (panel hidden) |

### 4.4 Existing relations (read)

Source: `SketchObject.Constraints`, each with `Type`, `First`/`FirstPos`,
`Second`/`SecondPos`, `Third`/`ThirdPos` (unused references carry FreeCAD's
undefined GeoId -2000).

Only these constraint types are listed (dimensions such as Distance,
DistanceX, DistanceY, Radius, Diameter, Angle, SnellsLaw, Weight are NOT
listed, as in SolidWorks; therefore a "Fix" made by `Sketcher_ConstrainLock`,
which FreeCAD stores as dimensional constraints, does not appear):

| Constraint `Type` | Display name |
|-------------------|--------------|
| `Coincident` | Coincident |
| `PointOnObject` | On entity |
| `Horizontal` | Horizontal |
| `Vertical` | Vertical |
| `Parallel` | Parallel |
| `Perpendicular` | Perpendicular |
| `Tangent` | Tangent |
| `Equal` | Equal |
| `Symmetric` | Symmetric |
| `Block` | Blocked |
| `InternalAlignment` | Internal alignment |

A constraint is a relation "of the selection" when it references at least one
selected entity:

- a selected **point** matches a reference with the same GeoId AND the same
  PosId;
- a selected **edge** matches any reference with the same GeoId, whatever the
  PosId (so relations on an edge's end/center points are listed for the edge;
  for the horizontal axis this includes relations on the Origin).

Each constraint appears at most once, in constraint index order. If the
constraint list cannot be read, the list is empty.

### 4.5 Deleting existing relations (write)

- Deletes exactly the constraints shown in the selected rows, via
  `SketchObject.delConstraint(index)`; the result must be correct regardless
  of index shifting caused by earlier deletions in the same operation, and
  duplicate indices must not delete twice.
- All deletions form ONE undo step named `Delete Relations`
  (`Document.openTransaction("Delete Relations")` ...
  `Document.commitTransaction()` on the sketch's App document). If the
  document already has a pending transaction (`Document.HasPendingTransaction`
  is true, e.g. FreeCAD's own sketch-edit transaction), JellyJams must neither
  open nor commit a transaction and the deletions join the pending one. The
  transaction JellyJams opened must be committed even if a deletion fails.
- Afterwards the sketch is re-solved (`SketchObject.solve()`); solver errors
  are ignored (FreeCAD's own solver messages show the state).
- Then the panel refreshes (deferred).

### 4.6 Other state

- Report view messages use the prefix `JellyJams: ` (warnings for failures to
  enable, refresh or delete; an error naming the command id when running a
  relation command raises).
- Qt objects created: the panel frame and children (section 2.3) and, only
  in the fallback case, the dock `JellyJamsPropertyManagerDock`.
- NOT touched: no FreeCAD parameter is read or written; nothing is written
  under `User parameter:BaseApp/Preferences/Mod/JellyJams`; no custom
  properties are added to documents; no FreeCAD toolbar, menu or command is
  modified; FreeCAD's own Sketcher task sections are not altered.

---

## 5. Persistence and restore rules

- The feature is purely runtime UI. It persists nothing and needs no
  exact-restore record and no crash recovery at startup.
- The only document changes are those made by FreeCAD's own constraint
  commands (when the user clicks a relation) and the constraint deletions
  (Delete button); both are normal undoable document edits saved with the
  user's file like any Sketcher edit.
- On workbench deactivation the feature leaves no visible trace: observer
  removed, panel hidden, fallback dock hidden. A hidden panel widget may stay
  parented inside FreeCAD's task panel; it must never become visible again
  while the feature is disabled.
- FreeCAD may record the fallback dock's objectName in its saved window state
  (`MainWindowState`); this must be harmless (the dock only exists once
  JellyJams creates it and is hidden whenever the panel is hidden).

---

## 6. Edge cases and failure handling

1. **Mixed selection with non-entities** (e.g. a dimension plus a line): the
   dimension is ignored; the panel reflects only the line.
2. **Selection on another object** while the sketch is in edit: ignored. If
   nothing of the sketch remains, the panel hides.
3. **Malformed or out-of-range sub-element names** or vertex lookups that
   fail: that name is skipped; others still count.
4. **A selected point that is a point of a selected edge** (its end or
   center point): On entity and Midpoint are not offered for that selection,
   and Symmetric with a mirror line is not offered when both points are
   points of that line (FreeCAD skips or refuses these combinations).
5. **Origin together with an axis** in a mixed selection: On entity is not
   offered (the Origin is a point of the horizontal axis, and the Origin
   with the vertical axis is a pair of fixed items).
6. **Splines:** never offered for Tangent or Equal (FreeCAD only supports
   tangency through a point and no equality for B-splines); Block is still
   offered for own splines.
7. **Fixed geometry (axes, Origin, external geometry):** never gets
   Horizontal/Vertical as an edge, Block or Fix. Relations whose command
   refuses two fixed items are not offered for such a selection: Collinear,
   Perpendicular and Tangent need a movable edge; Parallel, Concentric, Equal,
   Coincident and Horizontal/Vertical for points accept at most one fixed
   item. An external line together with an own line still gets Collinear,
   Perpendicular, Parallel and Equal.
8. **No matching relation:** the panel still appears (with entities and
   existing relations) and shows the hint instead of buttons.
9. **FreeCAD rejects a command anyway** (an untested combination): FreeCAD's
   own message is shown by FreeCAD; JellyJams does not crash and the panel
   stays consistent with the selection.
10. **Command raises a Python exception:** a Report-view error with the
    command id; the panel stays usable.
11. **Delete with nothing selected in the list:** no change, no transaction.
12. **Delete while a transaction is already pending:** deletions join it;
    JellyJams opens/commits nothing.
13. **Widget destroyed by FreeCAD** (task dialog rebuilt, dock closed): next
    refresh recreates it; no exception, no duplicate panels.
14. **Task panel not found:** fallback dock `JellyJamsPropertyManagerDock` in the left
    dock area.
15. **Any unexpected error during refresh:** caught and logged as a
    Report-view warning; never propagates into FreeCAD's selection system.
16. **Repeated workbench activation/deactivation:** at most one observer is
    ever registered; at most one panel widget and one fallback dock exist.
17. **Selection order:** the Selected Entities list follows the order FreeCAD
    reports; the offered set and its order (the catalogue order in 4.3) are
    the same for every selection order.

---

## 7. Acceptance criteria

Setup for criteria 2-24: FreeCAD 1.1+, JellyJams workbench active, a new
document with a sketch in edit mode containing, created in this order: two
line segments Line1 and Line2 (not touching), a circle Circle3, an arc of
circle Arc4, an ellipse Ellipse5, a sketch point Point6, a B-spline Spline7,
and one external (converted) line edge Converted1 taken from other geometry.
Report view open. Label numbers are FreeCAD's geometry/vertex numbers; if
FreeCAD appends internal geometry (ellipse axes, spline control circles) the
numbers in labels shift accordingly, which does not change which relations
are offered.

1. With the JellyJams workbench active and a sketch in edit but nothing
   selected, no "Add Relations" panel is visible anywhere.
2. Selecting Line1 shows the panel as the topmost section of the Tasks panel,
   above FreeCAD's own Sketcher sections; if Model and Tasks are tabbed, the
   Tasks tab comes to the front. The panel shows title "Add Relations",
   headings "Selected Entities", "Existing Relations", "Add Relations", the
   entity row "Line1", and the buttons Horizontal, Vertical, Block (in that
   order).
3. Every selection in the worked reference table of section 4.3 offers
   exactly the listed relations in exactly the listed order, whatever order
   its entities are picked in. In particular, two points never offer Fix,
   three points offer Horizontal and Vertical, and a fixed item paired with
   another fixed item (Converted1 + horizontal axis, Origin + horizontal
   axis) offers nothing.
4. Selecting start point of Line1 + Line1 shows the two entities, no relation
   buttons, and the hint "No relations can be added to this selection."
5. Selecting only a dimension/constraint in the sketch shows no panel.
6. Selecting, in this order, Line1, Circle3, a vertex, the origin, the
   horizontal axis and Converted1 lists, in selection order: "Line1", "Circle3",
   "Point<vertex number>", "Origin", "Horizontal axis", "Converted1".
7. Each button's tooltip equals FreeCAD's tooltip for the mapped command
   (hover Horizontal: same text as Sketcher's Horizontal constraint tooltip).
8. Horizontal, Vertical, Perpendicular, Parallel, Tangent, Coincident, Equal,
   Symmetric, Fix, On entity and Block buttons show FreeCAD's own icon for
   the mapped command; Collinear, Concentric and Midpoint show distinct
   JellyJams icons that differ from Tangent, Coincident and Symmetric.
9. With Line1 + Line2 selected, clicking Parallel adds exactly one Parallel
   constraint (same result as FreeCAD's Sketcher_ConstrainParallel), the
   selection is cleared, and the panel disappears. Ctrl+Z removes the
   constraint.
10. With Line1 + Line2 selected, clicking Collinear makes them collinear
    (FreeCAD stores a Tangent constraint between the two lines).
11. With Circle3 + Arc4 selected, clicking Concentric makes their centers
    coincide (one Coincident constraint on the centers).
12. With start point of Line2 + Line1 selected, clicking Midpoint puts that
    point at Line1's midpoint (FreeCAD Symmetric constraint).
13. With exactly one own point selected, clicking Fix behaves exactly like
    FreeCAD's Sketcher_ConstrainLock on that point (one DistanceX and one
    DistanceY to the origin).
14. Make Line1 Horizontal, make Line1's end point coincident with Line2's
    start point, and add a length dimension to Line1. Selecting Line1 lists
    exactly "Horizontal (no. 1)" and "Coincident (no. 2)" (numbers = FreeCAD's
    constraint numbers); the length dimension is not listed.
15. In the state of 14, selecting Line1's end point lists only the Coincident
    relation; selecting Line1's start point lists nothing and the Delete
    button is disabled.
16. In the state of 14, select Line1, Ctrl+click both rows in Existing
    Relations, click Delete: both constraints are removed, the dimension
    stays, the lists refresh, and a single Ctrl+Z restores both constraints.
    FreeCAD's Undo history shows one entry "Delete Relations" (unless a
    FreeCAD transaction was already pending, in which case no separate
    JellyJams entry appears).
17. Clicking Delete with no row selected changes nothing.
18. Lists grow with their content up to 6 visible rows; with more than 6
    selected entities the Selected Entities list scrolls.
19. Box-selecting many entities rebuilds the panel once (no flicker of
    repeated rebuilds, no Report-view warnings).
20. Leaving sketch edit (Close) hides the panel.
21. While a sketch is in edit with entities selected, switching to another
    workbench hides the panel; selecting entities there never shows it.
    Switching back to JellyJams and selecting entities shows it again.
22. Activating/deactivating the JellyJams workbench several times leaves
    exactly one relations selection observer registered while active and
    none while inactive, and at most one widget named `JellyJamsPropertyManager`
    belonging to this feature exists.
23. With the JellyJams theme active, the panel shows a 1 px accent-blue frame
    on a white background, a bold title, dim headings with a divider line,
    and buttons that highlight with a blue border on hover. Widgets carry the
    objectNames `JellyJamsPropertyManager`, `JellyJamsPropertyManagerTitle`,
    `JellyJamsSectionCaption` (three headings) and `JellyJamsItemList` (two lists).
24. Normal use (criteria 1-23) produces no warnings or errors prefixed
    `JellyJams:` in the Report view.
25. When FreeCAD's task panel widget (`Gui::TaskView::TaskPanel` inside the
    Tasks dock) is not available, selecting sketch entities shows a left-side
    dock titled "Relations" with objectName `JellyJamsPropertyManagerDock` containing the
    same panel; it hides when the selection is cleared and when leaving the
    workbench.
26. After using the panel and restarting FreeCAD, no new keys exist under
    `User parameter:BaseApp/Preferences/Mod/JellyJams` because of this
    feature, and saved documents contain no JellyJams-specific properties
    from it.
27. The test suite verifies that all 14 mapped command ids exist in
    `FreeCADGui.listCommands()` on FreeCAD 1.1.4, and, without a running GUI,
    that the capability table covers exactly the 14 catalogue relations, that
    the catalogue order is the order of 4.3, and that the offer rules
    reproduce every row of the worked reference table for every selection
    order.
