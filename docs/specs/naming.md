# JellyJams specification: Naming (SolidWorks names in the FreeCAD model tree)

> **Implemented in:** [`jellyjams/naming.py`](../../jellyjams/naming.py) (document observer, deferral, refresh triggers), [`naming_rules.py`](../../jellyjams/naming_rules.py) (pure naming and numbering rules); the direction-name table `PROJECTION_VIEW_LABELS` shared with Projected View lives in [`constants.py`](../../jellyjams/constants.py).
>
> **Status:** see [../status.md](../status.md)

Product: JellyJams, a FreeCAD 1.1+ workbench (key/class `JellyJamsWorkbench`,
MenuText "JellyJams") that makes FreeCAD look, feel and operate like
SolidWorks. English only. Reference FreeCAD version for every type id,
property name and default label below: **FreeCAD 1.1.4**.

---

## 1. Purpose

While the JellyJams workbench is active, objects that the user creates must
appear in FreeCAD's model tree under the names the English SolidWorks
FeatureManager / drawing tree would give them, instead of FreeCAD's names:

| FreeCAD shows | SolidWorks (and JellyJams) shows |
|---|---|
| `Sketch`, `Sketch001` | `Sketch1`, `Sketch2` |
| `Pad`, `Pocket` | `Boss-Extrude1`, `Cut-Extrude1` |
| `XY_Plane`, `XZ_Plane`, `YZ_Plane` (origin planes) | `Top Plane`, `Front Plane`, `Right Plane` |
| `Assembly`, `Joints` | `Assembly1`, `Mates` |
| a component `Body` linked from file `Shaft.FCStd` | `Shaft<1>`, a fixed one `(f) Shaft<1>` |
| joint `Distance` / `Cylindrical` | mate `Coincident1` / `Concentric1` |
| `Page`, `Template`, `ProjGroup`, `Left` | `Sheet1`, `Sheet Format1`, `Standard 3 View`, `Left View` |

Only the object's **Label** (the tree text) changes. FreeCAD's internal object
**Name** (`Pad`, `Sketch001`, ...) is never changed; FreeCAD refers to objects
by Name, so relabeling is always safe. Because the Label is stored in the
document file, the SolidWorks names stay in the file and are also shown when
the document is later opened in Part Design, Assembly, TechDraw or a FreeCAD
without JellyJams.

---

## 2. Terms used in this spec

- **Label**: FreeCAD's writable `Label` property (tree text).
- **Name**: FreeCAD's immutable internal `Name`.
- **New object**: an object whose creation FreeCAD announces while the
  conditions of section 5.2 hold. Objects that already exist are *not* new.
- **Base name**: the SolidWorks word(s) for a type, e.g. `Boss-Extrude`.
- **Numbered name**: base name immediately followed by a decimal number, no
  space, e.g. `Boss-Extrude3`, `Sheet Format1`, `Bill of Materials1`.
- **Fixed name**: a name that has no number while it is unique in the
  document (`Top Plane`, `Mates`), and gets `2`, `3`, ... appended for further
  ones (`Top Plane2`).
- **Instance name**: component naming `<Base><n>` with angle brackets, e.g.
  `Shaft<2>`.
- **Fixed marker**: the exact 4-character prefix `(f) ` (open parenthesis,
  lowercase f, close parenthesis, one space) in front of a component's label.
- **Default label**: a label that FreeCAD or the JellyJams mate dialog writes
  on its own, as listed in 3.4.5 and 3.5.5: FreeCAD's English text, plus the
  same text in the UI language of the running session as FreeCAD's own
  translation catalog renders it (section 3.7). Only default labels may be
  replaced in objects that are not new (sections 3.4.5 and 3.5.5). Every
  other label is a **user label**.
- **Document scan**: looking at the Labels of *all* objects of the same
  document (every type, every body/assembly/page), excluding the object being
  named itself.

All label comparisons in this spec are exact and case-sensitive.

---

## 3. User-visible behavior

### 3.1 General rules

1. Only the Label is written; never the Name.
2. Renaming applies to new objects (section 5). Existing objects are never
   renamed, with exactly three exceptions that only mirror current state or
   replace default labels:
   a. the fixed marker `(f) ` on assembly components (3.4.4),
   b. mate names that are default labels (3.4.5),
   c. FreeCAD default labels of projection views and sheet formats in an
      existing drawing when its sheet window is activated (3.5.5).
3. A user label is never overwritten. The only change ever made to a user
   label is adding/removing the fixed marker on an assembly component.
4. New objects get their SolidWorks name regardless of the label the creating
   command gave them (FreeCAD default, or a label set by another JellyJams
   tool such as `Weld Symbol` or `Sheet1`); a new object cannot carry a user
   label yet.
5. Types and situations not listed in this section keep FreeCAD's label.
6. Every name JellyJams writes is English. Text in another language is only
   ever read: a label FreeCAD wrote in the session's UI language can be
   recognized as a default label (3.7), but JellyJams never writes one.

### 3.2 Part modeling: numbered names by type

Every new object of these exact `TypeId`s gets a numbered name (numbering:
section 4.1). The first one in a document is `<Base>1`.

| FreeCAD TypeId | Base name | First name |
|---|---|---|
| `Sketcher::SketchObject` | `Sketch` | `Sketch1` |
| `PartDesign::Pad` | `Boss-Extrude` | `Boss-Extrude1` |
| `PartDesign::Pocket` | `Cut-Extrude` | `Cut-Extrude1` |
| `PartDesign::Revolution` | `Revolve` | `Revolve1` |
| `PartDesign::Groove` | `Cut-Revolve` | `Cut-Revolve1` |
| `PartDesign::AdditivePipe` | `Sweep` | `Sweep1` |
| `PartDesign::SubtractivePipe` | `Cut-Sweep` | `Cut-Sweep1` |
| `PartDesign::AdditiveLoft` | `Loft` | `Loft1` |
| `PartDesign::SubtractiveLoft` | `Cut-Loft` | `Cut-Loft1` |
| `PartDesign::Hole` | `Hole` | `Hole1` |
| `PartDesign::Fillet` | `Fillet` | `Fillet1` |
| `PartDesign::Chamfer` | `Chamfer` | `Chamfer1` |
| `PartDesign::Draft` | `Draft` | `Draft1` |
| `PartDesign::Thickness` | `Shell` | `Shell1` |
| `PartDesign::LinearPattern` | `LPattern` | `LPattern1` |
| `PartDesign::PolarPattern` | `CirPattern` | `CirPattern1` |
| `PartDesign::Mirrored` | `Mirror` | `Mirror1` |
| `PartDesign::MultiTransform` | `MultiPattern` | `MultiPattern1` |
| `PartDesign::Plane` (datum plane) | `Plane` | `Plane1` |
| `PartDesign::Line` (datum line) | `Axis` | `Axis1` |
| `PartDesign::Point` (datum point) | `Point` | `Point1` |

The sketch rule applies to every sketch (inside a body or not, created from
the ribbon, from Part Design/Sketcher commands or from the Python console)
except a JellyJams sheet sketch (3.5.4).

### 3.3 Origin planes: fixed names by Role

FreeCAD 1.1 gives each origin (of a PartDesign Body, an `App::Part`, an
assembly, and any other container whose origin/coordinate system creates
role-carrying planes) three `App::Plane` objects with a `Role` property.
SolidWorks names follow FreeCAD's view directions (Z up), so the plane name
matches the view button of the same name:

| `App::Plane` with `Role` | Fixed name |
|---|---|
| `XY_Plane` | `Top Plane` |
| `XZ_Plane` | `Front Plane` |
| `YZ_Plane` | `Right Plane` |

- The first origin in a document gets `Top Plane`, `Front Plane`,
  `Right Plane`; a second body/part in the same document gets `Top Plane2`,
  `Front Plane2`, `Right Plane2`; a third `...3`, and so on (rules: 4.2).
- An `App::Plane` with any other or no `Role` is not renamed.
- Not renamed (keep FreeCAD's label): the `App::Origin` container (FreeCAD's
  label `Origin` already matches SolidWorks), the origin axes (`App::Line`,
  roles `X_Axis`/`Y_Axis`/`Z_Axis`), the origin point (`App::Point`), and the
  `PartDesign::Body` itself (stays `Body`).

### 3.4 Assembly tree

#### 3.4.1 Assembly object and bill of materials (numbered)

| FreeCAD TypeId | Base name | First name |
|---|---|---|
| `Assembly::AssemblyObject` | `Assembly` | `Assembly1` |
| `Assembly::BomObject` | `Bill of Materials` | `Bill of Materials1` |

A second assembly object in the same document (e.g. a sub-assembly created
inside it) becomes `Assembly2`. (The *document* name `Assembly1` used by the
JellyJams New Assembly command is owned by that command, not by this area.)

#### 3.4.2 Assembly folders (fixed names)

| FreeCAD TypeId | Fixed name | Second one in the same document |
|---|---|---|
| `Assembly::JointGroup` | `Mates` | `Mates2` |
| `Assembly::ViewGroup` | `Exploded Views` | `Exploded Views2` |
| `Assembly::BomGroup` | `Bills of Materials` | `Bills of Materials2` |
| `Assembly::SimulationGroup` | `Motion Studies` | `Motion Studies2` |

(Rules: 4.2. A type that the running FreeCAD does not create simply never
occurs.)

#### 3.4.3 Components (instance names)

A new object of type `App::Link` or `Assembly::AssemblyLink` is a
**component** when an `Assembly::AssemblyObject` is among the objects that
reference it (its `InList`), i.e. it sits in an assembly. It is named
`<Base><n>`:

- **Base** = when the linked object (`LinkedObject`) lives in another
  document: that document's `Label` (if empty: the document's `Name`). This
  is the part's file name as SolidWorks shows it, e.g. a body in
  `Shaft.FCStd` gives `Shaft`.
- When the linked object lives in the same document: the linked object's
  Label (if empty: its Name) with a leading fixed marker `(f) ` and a trailing
  `<digits>` removed (`(f) Plate<2>` gives `Plate`).
- **n** = instance number (4.4): first instance `Shaft<1>`, then `Shaft<2>`.
- A link that is not inside an assembly, or whose `LinkedObject` is empty, is
  not renamed.
- **Link without a target yet.** A component whose `LinkedObject` is still
  empty when its rename runs is remembered for the session (FreeCAD's New
  Part command creates the link first and sets its target only when its
  dialog is accepted). When its `LinkedObject` is set later, it is queued and
  named by these rules, unless the document is restoring or in undo/redo. A
  component that already has its name keeps it when its target changes. A
  remembered link is forgotten when it is deleted (also while another
  workbench is active) or its document is closed.
- The fixed marker is not part of the name given at creation; it is added by
  3.4.4 if the component is fixed.

#### 3.4.4 Fixed marker `(f) ` (state mirror)

For every component (3.4.3 definition, regardless of how its label came
about, user label included) in every assembly of the document:

- the label starts with `(f) ` **exactly when** the component is grounded,
  i.e. some object of the same document has a property `ObjectToGround` that
  references this component (FreeCAD 1.1 "Toggle Grounded" creates such a
  grounded-joint object; floating deletes it);
- otherwise any leading `(f) ` is removed;
- the rest of the label is left untouched (`Motor` becomes `(f) Motor`).

This mirror is re-established at the refresh triggers of section 5.4,
including after undo/redo, because it reflects state rather than naming a new
object. Links outside assemblies are never touched.

#### 3.4.5 Mates (joint names, state mirror)

A **mate** is an object that is contained in an `Assembly::JointGroup`
(the JointGroup is in its `InList`), has a `JointType` property whose value is
in the table below, and does **not** have an `ObjectToGround` property
(grounded joints are not mates and keep FreeCAD's label, e.g.
`GroundedJoint`).

| FreeCAD `JointType` | SolidWorks mate base name |
|---|---|
| `Fixed` | `Lock` |
| `Revolute` | `Hinge` |
| `Cylindrical` | `Concentric` |
| `Slider` | `Slider` |
| `Ball` | `Ball Joint` |
| `Distance` with `Distance` value 0 (absolute value below 1e-9; also when the value cannot be read as a number) | `Coincident` |
| `Distance` with any other value | `Distance` |
| `Parallel` | `Parallel` |
| `Perpendicular` | `Perpendicular` |
| `Angle` | `Angle` |
| `RackPinion` | `Rack Pinion` |
| `Screw` | `Screw` |
| `Gears` | `Gear` |
| `Belt` | `Belt` |

(`Distance` may be a plain number or a FreeCAD Quantity; its numeric value in
mm is used.) A `JointType` value not in the table: the mate is not renamed.

Naming rule for each mate, applied at every refresh (5.4) to all mates of the
document, in document order, each rename visible to the next:

1. If the label already **fits**, i.e. is the mate base name immediately
   followed by a positive integer written without leading zeros
   (`Coincident1`, `Lock12`), it is kept.
2. Otherwise, strip all trailing digits from the label (`Distance001` gives
   `Distance`, `RevoluteJoint3` gives `RevoluteJoint`, `Joint` stays `Joint`).
   If the result is in the **default mate label set** below, the mate is
   renamed to the numbered name `<base><N>` (numbering: 4.5).
3. Otherwise the label is a user label and is kept (`Front bearing`,
   `Bearing2`).

Consequently the mate name follows the type while the user changes the type
or the distance in the mate dialog: `Coincident1` becomes `Distance1` when a
non-zero distance is entered, `Parallel1` when the type is switched to
Parallel, and back again.

**Default mate label set** (recognition data, exact and case-sensitive):

- FreeCAD joint type identifiers: `Fixed`, `Revolute`, `Cylindrical`,
  `Slider`, `Ball`, `Distance`, `Parallel`, `Perpendicular`, `Angle`,
  `RackPinion`, `Screw`, `Gears`, `Belt`;
- FreeCAD's generic joint label `Joint`;
- all SolidWorks mate names from the table: `Lock`, `Hinge`, `Concentric`,
  `Slider`, `Ball Joint`, `Coincident`, `Distance`, `Parallel`,
  `Perpendicular`, `Angle`, `Rack Pinion`, `Screw`, `Gear`, `Belt`;
- `Coincident / Distance` (the text the JellyJams-translated joint dialog
  shows for the Distance type; FreeCAD's dialog may copy the displayed type
  text into the label);
- the joint type words of the session's UI language, read at runtime (3.7):
  the Qt translation of every joint type identifier above in context
  `"Assembly"`, plus the entries of `JointObject.TranslatedJointTypes` (the
  list FreeCAD's joint dialog fills its type box from, when the Assembly
  module `JointObject` can be imported). In an English session these are
  the identifiers themselves;
- every FreeCAD joint type identifier and every runtime joint type word
  followed by ` Joint` or `Joint` (`Slider Joint`, `GearsJoint`), because
  FreeCAD swaps the type word inside such a label when the joint type
  changes;
- every entry above also with all spaces removed (`RackPinion`,
  `SliderJoint`, `Coincident/Distance`).

Note: a user who deliberately types one of these words (e.g. `Hinge`) as a
mate name will see it normalized to the SolidWorks form at the next refresh;
this is intended (those words count as automatic names).

### 3.5 Drawing tree (TechDraw)

#### 3.5.1 Numbered drawing names by type

| FreeCAD TypeId | Base name | First name |
|---|---|---|
| `TechDraw::DrawPage` | `Sheet` | `Sheet1` |
| `TechDraw::DrawSVGTemplate` | `Sheet Format` | `Sheet Format1` |
| `TechDraw::DrawViewPart` (plain model view) | `Drawing View` | `Drawing View1` |
| `TechDraw::DrawViewDimension` | `Dimension` | `Dimension1` |
| `TechDraw::DrawViewBalloon` | `Balloon` | `Balloon1` |
| `TechDraw::DrawRichAnno` | `Note` | `Note1` |
| `TechDraw::DrawLeaderLine` | `Leader` | `Leader1` |
| `TechDraw::DrawHatch` | `Area Hatch` | `Area Hatch1` |
| `TechDraw::DrawGeomHatch` | `Area Hatch` | (shares numbering with DrawHatch) |
| `TechDraw::DrawWeldSymbol` | `Weld Symbol` | `Weld Symbol1` |
| `TechDraw::DrawViewClip` | `Crop Frame` | `Crop Frame1` |
| `TechDraw::DrawViewImage` | `Picture` | `Picture1` |
| `TechDraw::DrawViewSymbol` (no JellyJams kind, see 3.5.4) | `Picture` | `Picture1` |

Matching is by exact TypeId: subclasses with their own TypeId (e.g.
`TechDraw::DrawViewSection`, `TechDraw::DrawViewDetail`,
`TechDraw::DrawProjGroupItem`) are not covered by the `DrawViewPart` row.
Objects sharing a base name share one number sequence (e.g. hatches of both
types, JellyJams weld symbols and FreeCAD weld symbols).

#### 3.5.2 Standard 3 View (first one unnumbered)

`TechDraw::DrawProjGroup` gets base name `Standard 3 View`:

- If no other object in the document is labeled `Standard 3 View` and no
  numbered `Standard 3 View<N>` exists, the new group is `Standard 3 View`.
- If the bare name is taken, the new group gets the next number but at
  least 2 (the bare one counts as number 1): `Standard 3 View2`, `...3`.
- If only numbered ones exist (the bare one was deleted or renamed), the new
  group gets the next number: with `Standard 3 View2` present the new one is
  `Standard 3 View3`.

#### 3.5.3 Projection views (direction names, no numbers)

A new `TechDraw::DrawProjGroupItem` is named by its `Type` property:

| `Type` | Name |
|---|---|
| `Front` | `Front View` |
| `Top` | `Top View` |
| `Bottom` | `Bottom View` |
| `Left` | `Left View` |
| `Right` | `Right View` |
| `Rear` | `Back View` |
| `FrontTopLeft` | `Isometric View` |
| `FrontTopRight` | `Isometric View` |
| `FrontBottomLeft` | `Isometric View` |
| `FrontBottomRight` | `Isometric View` |

Any other `Type`: not renamed. These names carry no number; if the same name
already exists in the document (a second Standard 3 View), FreeCAD's own
label de-duplication applies (e.g. `Front View001`) and is accepted. This
table is shared with the JellyJams Projected View tool, which labels the
views it adds with the same names; both must use one single table.

#### 3.5.4 Objects carrying JellyJams marker properties

JellyJams drawing tools (owned by other areas) mark their objects with custom
properties that are stored in users' documents. The marker decides the base
name and takes precedence over 3.5.1 and 3.2. Checked in this order:

| Object has property | Base name | First name | Typical object type |
|---|---|---|---|
| `HostSheet` | `Sheet Sketch` | `Sheet Sketch1` | `Sketcher::SketchObject` |
| `ShownSketch` | `Sheet Sketch View` | `Sheet Sketch View1` | `TechDraw::DrawViewPart` |
| `SheetNote` | `Text` | `Text1` | `TechDraw::DrawViewAnnotation` |

For `TechDraw::DrawViewSymbol` the string property `SymbolType` selects:

| `SymbolType` | Base name | First name |
|---|---|---|
| `surface` | `Surface Finish` | `Surface Finish1` |
| `weld` | `Weld Symbol` | `Weld Symbol1` |
| absent, empty or any other value | `Picture` | `Picture1` |

Presence of the property is what counts (its value is irrelevant for
`HostSheet`, `ShownSketch`, `SheetNote`). Requirement on the
owning areas: the marker must be added synchronously in the same call that
creates the object, so it exists when the deferred rename (5.3) runs.

#### 3.5.5 Existing drawings (default-label refresh)

When a drawing sheet window becomes the active window (trigger: 5.6), the
**active document** is scanned in document order and:

- every `TechDraw::DrawProjGroupItem` whose label is a **FreeCAD default
  projection label** is renamed to the direction name of 3.5.3 for its
  `Type` (no rename if the Type is not in that table);
- every `TechDraw::DrawSVGTemplate` whose label is a **FreeCAD default
  template label** is renamed to `Sheet Format<N>` (numbering 4.1; each rename
  in the pass is visible to the next, so two templates become
  `Sheet Format1` and `Sheet Format2`);
- a label that already begins with the target name is left as is;
- user labels (anything not recognized) are kept;
- nothing else is renamed in existing drawings (pages stay e.g. `Page`,
  views/dimensions keep their labels).

The pass is idempotent: running it again on the same document changes
nothing.

A label is matched after a trailing **counter** is set aside: a run of
digits at the end, together with any blanks directly in front of it
(`Rear002` and `Rear 2` are both matched as `Rear`). A label without
trailing digits is matched as it is, so trailing blanks alone make it a user
label.

**FreeCAD default projection labels**: after the counter is set aside, one of

- FreeCAD's projection `Type` values, which TechDraw uses as an item's first
  label: `Front`, `Left`, `Right`, `Rear`, `Top`, `Bottom`, `FrontTopLeft`,
  `FrontTopRight`, `FrontBottomLeft`, `FrontBottomRight`;
- `ProjItem`, the object name FreeCAD gives an item (and its label when the
  item is added from a script rather than by its group);
- the Qt translation of each `Type` value in context `"DrawProjGroupItem"`,
  read at runtime (3.7). TechDraw labels a new item with exactly that
  translation plus FreeCAD's de-duplication digits.

Examples: `Bottom`, `Right004`, `Top 3`, `ProjItem012`. Not recognized:
`Front View`, `front`, `Side view`. The new name always comes from the
item's `Type`, never from the word that was recognized.

**FreeCAD default template labels**: after the counter is set aside,
`Template` or its Qt translation in context `"DrawSVGTemplate"`, read at
runtime (3.7). TechDraw's page commands label a new template with that
translation followed by the digits of the object's internal name
(`Template`, `Template001`).

#### 3.5.6 Drawing objects owned by other areas (must NOT be renamed here)

- Section views (`TechDraw::DrawViewSection`, `TechDraw::DrawComplexSection`)
  and detail views (`TechDraw::DrawViewDetail`) are named by the
  section/detail view labeling area (`Section View A-A`,
  `Detail View Z (2:1)`).
- `TechDraw::DrawViewAnnotation` without `SheetNote` (e.g. the view label
  annotation `View Label A-A` created by that area, or a FreeCAD annotation)
  keeps its label.
- The New Drawing command labels its page `Sheet1` and its group
  `Standard 3 View` itself; the rules here produce the same result, so the
  two never disagree.

### 3.6 Never renamed (non-exhaustive examples)

`PartDesign::Body`, `App::Part`, `App::Origin`, origin axes and origin point,
`PartDesign::AdditiveHelix`/`SubtractiveHelix`, PartDesign primitives,
`PartDesign::Boolean`, `PartDesign::ShapeBinder`/`SubShapeBinder`,
`PartDesign::CoordinateSystem` (its own role-carrying planes, if any, follow
3.3), Part workbench objects, links outside assemblies, grounded joints,
`TechDraw::DrawViewSection`/`DrawComplexSection`/`DrawViewDetail`,
`TechDraw::DrawViewAnnotation` without `SheetNote`, `TechDraw::DrawViewMulti`,
`DrawViewSpreadsheet`, `DrawViewDraft`, `DrawViewArch`, `DrawTileWeld`, any
other type not listed in 3.2–3.5. Documents themselves are never relabeled by
this area.

### 3.7 Labels FreeCAD wrote in another UI language

FreeCAD writes some default labels through its Qt translation catalog, so a
non-English session stores them in the UI language. JellyJams does not carry
its own word lists for any language. Instead it asks Qt, through
`QCoreApplication.translate(<context>, <English text>)`, for the very
translation FreeCAD itself uses, in the very context FreeCAD uses:

| Labels | Context | English source texts |
|---|---|---|
| mates (3.4.5) | `"Assembly"` | the 13 joint type identifiers |
| projection items (3.5.5) | `"DrawProjGroupItem"` | the 10 projection `Type` values |
| sheet templates (3.5.5) | `"DrawSVGTemplate"` | `Template` |

Rules:

- The English source texts are always recognized, whatever the UI language.
- The answers are requested the first time a context is needed and kept for
  the rest of the session. If Qt cannot answer, the set falls back to the
  English source texts alone and a log-level console line notes it.
- Only the language that is active in the running session is covered. A
  label written by FreeCAD in a different language (a document created in
  another language than the current one) is a user label and is kept.
- Recognized words are only compared, never written; the names produced are
  the English ones of 3.4.5 and 3.5.3.

---

## 4. Numbering and collision rules

All rules use a document scan (section 2): labels of every object in the same
document except the object being named. FreeCAD silently de-duplicates
duplicate labels by appending digits (`Top Plane` -> `Top Plane001`); the
rules below always produce a label that is unique among existing numbered
labels, so FreeCAD's de-duplication does not kick in for numbered and fixed
names. JellyJams never changes FreeCAD's duplicate-label preference.

### 4.1 Numbered names

`N` = (highest number found among labels consisting of exactly the base name
followed by digits) + 1; `1` if there is none. Digits with leading zeros count
by their numeric value (`Sketch001` counts as 1). Numbers are never compacted
and gaps are not filled: with `Sketch1` and `Sketch4` present, the next sketch
is `Sketch5`. A freed number is reused only if it was the highest (delete
`Sketch5`, next is `Sketch5` again). The bare base name without digits does
not count. Labels of all object types count (a user object labeled `Fillet7`
makes the next fillet `Fillet8`).

### 4.2 Fixed names (origin planes, assembly folders)

For a new object whose fixed name is `F`:

1. If its current label is `F`, or `F` followed by a positive integer without
   leading zeros (`Top Plane3`), and no other object has that same label,
   the label is kept (repeat passes change nothing).
2. Else, if no other object is labeled exactly `F`, it becomes `F`.
3. Else it becomes `F<N>` with `N` = max(2, numbered-name `N` of 4.1). The
   bare `F` counts as number 1.

`Top Plane001` (FreeCAD de-duplication, leading zeros) does not fit rule 1
and is replaced (e.g. by `Top Plane2`).

### 4.3 First-unnumbered names

Only `Standard 3 View` (3.5.2).

### 4.4 Instance numbers (components)

`n` = (highest `<n>` among labels of the form `<Base><n>` or `(f) <Base><n>`
anywhere in the document) + 1. The fixed marker does not disturb counting:
with `(f) Shaft<1>` and `Shaft<2>` present, the next is `Shaft<3>`. Different
bases count independently (`Shaft<1>`, `Plate<1>`).

### 4.5 Mate numbers

Mates that are renamed (3.4.5 step 2) get `<base><N>` with `N` per 4.1 over
the whole document. A mate that already fits keeps its number. Because the
mate itself is excluded from the scan, a mate whose type flips back and forth
returns to the lowest consistent number (`Coincident1` -> `Distance1` ->
`Coincident1`).

### 4.6 Direction names

Projection view names (3.5.3) carry no number of their own (see there).

### 4.7 Worked examples

| Document already contains (labels) | New object | Result |
|---|---|---|
| `Sketch1`, `Sketch4`, `Boss-Extrude1` | sketch, pad, body, plane Role `XZ_Plane` | `Sketch5`, `Boss-Extrude2`, `Body` (unchanged), `Front Plane` |
| `Sketch1` | sketch; pad; plane Role `XY_Plane`; DrawProjGroup; DrawProjGroupItem Type `Left`; DrawViewSymbol `SymbolType`=`weld`; JointGroup | `Sketch2`; `Boss-Extrude1`; `Top Plane`; `Standard 3 View`; `Left View`; `Weld Symbol1`; `Mates` |
| `Top Plane`, `Mates` | plane Role `XY_Plane` (FreeCAD labeled it `Top Plane001`); JointGroup | `Top Plane2`; `Mates2` |
| `Standard 3 View` | DrawProjGroup | `Standard 3 View2` |
| — | DrawViewDimension labeled `Dimension001` by FreeCAD | `Dimension1` |
| assembly with links to `Shaft.FCStd` body | 2 links to it, 1 link to same-document `Plate`, 1 link outside the assembly | `Shaft<1>`, `Shaft<2>`, `Plate<1>`, outside link unchanged |
| `(f) Shaft<1>`, `Shaft<2>` | another Shaft link | `Shaft<3>` |
| mates `Lock1` (Fixed), `Joint` (Distance 0), `Joint001` (Distance 2.5 mm), `CylindricalJoint4` (Cylindrical), `Idler axle` (Cylindrical) | refresh | `Lock1`, `Coincident1`, `Distance1`, `Concentric1`, `Idler axle` |

---

## 5. Triggers and timing

### 5.1 Activation scope

- Naming is in effect only while `JellyJamsWorkbench` is the active workbench
  (`FreeCADGui.activeWorkbench().name()`), as of the moment the triggering
  event happens. It starts working at the first activation of the workbench.
- While any other workbench is active, nothing is renamed, no fixed marker is
  updated and no mate is renamed. Whether the document observer stays
  registered while another workbench is active is an implementation choice;
  if it stays, it must be fully inert.
- Activating the workbench any number of times must not register a second
  observer or otherwise cause duplicate processing (a new sketch still
  becomes `Sketch1`, not `Sketch2`).
- Leaving the workbench does not revert any label.

### 5.2 New objects

An object creation announced by FreeCAD (document observer
`slotCreatedObject`) is a new object for this area if, at that moment:

- the JellyJams workbench is active, and
- the object's document does not report `Restoring` (file being opened,
  linked documents being loaded on demand, and any other operation during
  which FreeCAD sets that flag, e.g. pasting/importing objects), and
- the object's document does not report `Transacting` (undo/redo; objects
  re-created by undo/redo come back with the label they had and are not
  renamed and do not consume a new number).

Every creation in any open document qualifies (not only the active document),
whatever created it: ribbon buttons, FreeCAD's own commands, task dialogs,
macros, the Python console.

A creation that is skipped only because of `Transacting` still triggers the
assembly refresh of 5.4 for its document. A creation skipped because of
`Restoring` triggers nothing.

### 5.3 Deferral (mandatory)

The rename of a new object must not happen inside FreeCAD's creation
notification. FreeCAD facts that force this:

- FreeCAD announces a new object before its label and, for origin planes,
  its `Role` are set (Role is assigned after the notification).
- Creating commands set further properties (`LinkedObject`, `Type`,
  JellyJams marker properties, `JointType`) right after creating the object.
- During construction FreeCAD fires `slotChangedObject(obj, "Label")` before
  `slotCreatedObject`, and changing a Label inside an observer callback
  re-fires observer callbacks (re-entrancy).

Therefore new objects are queued and renamed once control returns to the Qt
event loop (next event-loop turn, zero-delay). Requirements:

- Queued objects are renamed in creation order (so numbers ascend in the
  order the user created things, and the three origin planes of a body are
  named together).
- The name is computed at rename time from the object's state at that moment
  (final Role, Type, markers, LinkedObject, membership in an assembly).
- The rename becomes visible essentially immediately (well under one second),
  in particular while the feature's task dialog is still open (e.g. the tree
  shows `Boss-Extrude1` while the Pad dialog is open).
- Objects that were deleted before their turn (e.g. a temporary preview
  object of a cancelled command) are silently dropped; accessing them must
  not raise out of the handler, and the remaining queued objects are still
  renamed.
- No dedicated undo transaction is opened for a rename.

### 5.4 Assembly state refresh (fixed marker + mates)

For a document, the fixed-marker mirror (3.4.4) and then the mate naming
(3.4.5) are re-established, deferred in the same way as 5.3, when any of these
happens while the JellyJams workbench is active:

- an object is created in the document and the document is not `Restoring`
  (this includes creations during undo/redo, e.g. undo brings a grounding
  back -> `(f) ` comes back);
- a property named `JointType` or `Distance` of an object in the document
  changes and the document is not `Restoring` (this is how mate names follow
  the mate dialog live, and also after undo/redo of such a change);
- an object that has an `ObjectToGround` property is deleted
  (`slotDeletedObject`; float/unground) — evaluated after the deletion has
  completed, so the deleted grounding no longer counts.

The refresh only acts on documents that contain at least one
`Assembly::AssemblyObject`; otherwise it does nothing. Other property
changes (including the user editing a Label) never trigger it. Several
triggers in quick succession may be coalesced; the outcome must be the same
as running the refresh once after the last trigger.

### 5.5 Postponement while a TechDraw tool is running (crash safety)

While a TechDraw interactive tool is in progress in the active drawing sheet
window (dimensioning, balloon placement, panning, ...), relabeling TechDraw
objects causes the views to redraw while TechDraw holds pointers to view
edges, which crashes FreeCAD. Public FreeCAD fact used for detection: while a
TechDraw tool runs, TechDraw sets its own mouse cursor on the sheet's graphics
view viewport and restores the standard arrow cursor when the tool finishes;
the sheet window is the active MDI sub-window whose widget class is
`TechDrawGui::MDIViewPage`.

Requirement: if any queued new object is a TechDraw object (TypeId beginning
with `TechDraw::`) and such a tool is in progress, the pending renames are
postponed and re-checked about every 500 ms until no tool is in progress;
then they are applied in creation order. If no sheet window is active, no
tool is considered in progress. A postponed queue must survive further
creations (new objects join the queue in order).

### 5.6 Existing-drawing refresh trigger

While the JellyJams workbench is active, the existing-drawing pass (3.5.5)
runs on the active document whenever the active MDI sub-window changes from a
non-sheet window (or from nothing) to a drawing sheet window (widget class
`TechDrawGui::MDIViewPage`). Detection latency up to about half a second is
acceptable (the ribbon's context polling interval). Because the pass is
idempotent, running it more often (e.g. also when switching directly between
sheet windows of different documents) is allowed. Failures in this pass are
swallowed silently; it never blocks the sheet window or the ribbon.

### 5.7 What never triggers renaming

Opening/loading a file, saving, recompute, selection changes, editing a
Label by hand, switching workbenches, entering/leaving sketch or assembly
edit mode, and any activity while another workbench is active.

---

## 6. FreeCAD state read or changed

This area defines **no** JellyJams command ids (no `JellyJams_*` command), **no** Qt
widgets/docks/objectNames, **no** parameters under
`User parameter:BaseApp/Preferences/Mod/JellyJams`, and writes **no** FreeCAD
parameters at all. It writes no custom properties into documents.

| Item | Read / Write | Purpose |
|---|---|---|
| `FreeCAD.addDocumentObserver(observer)` (and optionally `FreeCAD.removeDocumentObserver`) | call | receive `slotCreatedObject(obj)`, `slotChangedObject(obj, prop)` (`JointType`, `Distance`, and `LinkedObject` of a remembered link, 3.4.3), `slotDeletedObject(obj)`, `slotDeletedDocument(doc)` |
| `FreeCADGui.activeWorkbench().name()` == `"JellyJamsWorkbench"` | read | activation gate (5.1) |
| `Document.Restoring`, `Document.Transacting` | read | skip rules (5.2, 5.4) |
| `Document.Objects` | read | document scan, refreshes |
| `Document.Label`, `Document.Name` | read | component base name (3.4.3) |
| `obj.Label` | **write** (only property ever written) | the SolidWorks name |
| `obj.Name` | read only, never written | identity (grounding comparison) |
| `obj.TypeId` | read | type tables; a deleted object raises on access -> treat as gone |
| `obj.Document` | read | which document to scan |
| `obj.InList` | read | inside an assembly (`Assembly::AssemblyObject` in InList) / inside a Mates folder (`Assembly::JointGroup` in InList) |
| `App::Plane.Role` (`XY_Plane`, `XZ_Plane`, `YZ_Plane`) | read | plane names |
| `TechDraw::DrawProjGroupItem.Type` | read | direction names |
| `App::Link` / `Assembly::AssemblyLink` `.LinkedObject` | read | component base name |
| joint `JointType`, `Distance` | read | mate names |
| any object's `ObjectToGround` | read | grounded components; grounded joints excluded from mates |
| custom properties `HostSheet`, `ShownSketch`, `SheetNote` (presence), `SymbolType` (value `surface` / `weld`) | read | JellyJams-marked drawing objects (3.5.4); written by other areas, stored in users' documents, names must stay exactly these for file compatibility |
| Python module `JointObject` attribute `TranslatedJointTypes` | read, optional | default mate labels in the UI language (3.7) |
| `QtCore.QCoreApplication.translate("Assembly", <joint type>)` | read | default mate labels in the UI language (3.7) |
| `QtCore.QCoreApplication.translate("DrawProjGroupItem", <Type>)` | read | default projection labels in the UI language (3.7) |
| `QtCore.QCoreApplication.translate("DrawSVGTemplate", "Template")` | read | default template labels in the UI language (3.7) |
| main window `QMdiArea` active sub-window, widget class name `TechDrawGui::MDIViewPage`, its `QGraphicsView` viewport cursor shape | read | sheet-window activation (5.6), tool-in-progress detection (5.5) |
| `FreeCAD.Console.PrintLog` | write | diagnostics (prefix `JellyJams: `) |

All TypeIds this area reacts to: `Sketcher::SketchObject`,
`PartDesign::Pad`, `PartDesign::Pocket`, `PartDesign::Revolution`,
`PartDesign::Groove`, `PartDesign::AdditivePipe`,
`PartDesign::SubtractivePipe`, `PartDesign::AdditiveLoft`,
`PartDesign::SubtractiveLoft`, `PartDesign::Hole`, `PartDesign::Fillet`,
`PartDesign::Chamfer`, `PartDesign::Draft`, `PartDesign::Thickness`,
`PartDesign::LinearPattern`, `PartDesign::PolarPattern`,
`PartDesign::Mirrored`, `PartDesign::MultiTransform`, `PartDesign::Plane`,
`PartDesign::Line`, `PartDesign::Point`, `App::Plane`,
`Assembly::AssemblyObject`, `Assembly::BomObject`, `Assembly::JointGroup`,
`Assembly::ViewGroup`, `Assembly::BomGroup`, `Assembly::SimulationGroup`,
`App::Link`, `Assembly::AssemblyLink`, `TechDraw::DrawPage`,
`TechDraw::DrawSVGTemplate`, `TechDraw::DrawProjGroup`,
`TechDraw::DrawProjGroupItem`, `TechDraw::DrawViewPart`,
`TechDraw::DrawViewDimension`, `TechDraw::DrawViewBalloon`,
`TechDraw::DrawRichAnno`, `TechDraw::DrawLeaderLine`, `TechDraw::DrawHatch`,
`TechDraw::DrawGeomHatch`, `TechDraw::DrawWeldSymbol`,
`TechDraw::DrawViewClip`, `TechDraw::DrawViewImage`,
`TechDraw::DrawViewSymbol`, `TechDraw::DrawViewAnnotation` (only with
`SheetNote`); mates are recognized by location and `JointType`, not TypeId
(FreeCAD 1.1 joints are `App::FeaturePython`).

---

## 7. Persistence and restore

- The only persistent effect is the Label of document objects, saved by
  FreeCAD in the `.FCStd` file like any label. Files stay fully compatible
  with plain FreeCAD; nothing JellyJams-specific is added by this area.
- No FreeCAD parameter is changed, so there is no backup, no exact-restore
  record and nothing to recover after a crash. Startup crash recovery has no
  work for this area.
- Leaving the workbench, quitting, or a crash never reverts labels; names are
  ordinary document edits (they are saved when the user saves).
- Re-activating the workbench must not re-process existing objects (only the
  existing-drawing pass and the assembly refresh, both idempotent, may touch
  existing objects, and only per sections 3.4.4, 3.4.5, 3.5.5).
- In-memory queues (pending renames, documents awaiting refresh) are
  transient and need no persistence; losing them on quit is acceptable.

---

## 8. Edge cases and failure handling

1. **Deleted before rename** (cancelled command, preview dimension removed):
   dropped silently, others still processed (5.3).
2. **Rename raises** (object became invalid, read-only, document closed):
   that object is skipped with a log-level console message prefixed
   `JellyJams: `; processing continues; nothing propagates to FreeCAD.
3. **Document closed** before its deferred refresh runs: skipped silently.
4. **Cancelled feature**: Pad created (`Boss-Extrude1`), dialog cancelled
   (object removed) -> the next pad is again `Boss-Extrude1`.
5. **Undo/redo**: objects re-created by undo/redo keep the label the
   undo/redo restores; no new numbers are consumed. Fixed markers and mate
   names are re-mirrored after undo/redo (5.4).
6. **Opening files** (including files with FreeCAD default labels like `Pad`,
   `Sketch001`, and assemblies whose grounded components lack `(f) `): nothing
   is changed on open. The fixed marker / mate names of such an assembly are
   normalized at the next assembly trigger (5.4) in that document while
   JellyJams is active; drawings get the 3.5.5 pass when their sheet window is
   activated.
7. **Objects created outside the workbench** keep FreeCAD's labels forever
   (switching to JellyJams later does not rename them), except the state
   mirrors of 3.4.4/3.4.5/3.5.5 when their triggers occur.
8. **User renames** an auto-named object: kept forever (except `(f) `
   mirror). The name of a manually renamed mate is kept unless it is a default
   mate label (3.4.5).
9. **Manually typed `(f) ` on a non-grounded component**: removed at the next
   refresh; missing `(f) ` on a grounded one: added.
10. **Two assemblies in one document**: folders `Mates`/`Mates2`; component
    instance numbers and mate numbers count across the whole document.
11. **Link outside assembly**: not renamed, no marker. **Component with no
    target yet**: not renamed until its `LinkedObject` is set (3.4.3).
12. **Unknown future types** (`JointType` values, projection `Type`s, roles,
    TypeIds): not renamed.
13. **Duplicate direction names** in a second projection group: FreeCAD's
    de-duplicated form (`Front View001`) is accepted and left alone by later
    passes.
14. **Non-numeric `Distance`** on a Distance joint: treated as 0 ->
    `Coincident`.
15. **Marker property added late** by another tool (after the deferred rename
    ran): the object keeps the type-table name; owning areas must add markers
    synchronously (3.5.4).
16. **TechDraw tool never releases the cursor**: renames of queued TechDraw
    objects stay postponed (re-checked every ~500 ms) and happen as soon as
    the arrow cursor returns or the sheet window is no longer active.
17. **Labels already fitting** (planes/folders 4.2 rule 1, mates 3.4.5 rule
    1): a repeated pass changes nothing (idempotence).
18. **Non-ASCII labels** (e.g. a part file `Spacer Ø12.FCStd`): component
    base names use the document Label verbatim (`Spacer Ø12<1>`).
19. **UI language without a translation catalog, or Qt unavailable**: only
    the English default labels are recognized (3.7); nothing fails.
20. **Startup failure** of the naming service: reported once as a console
    error prefixed `JellyJams: `; the rest of the workbench still activates.

---

## 9. Acceptance criteria

All tests in FreeCAD 1.1.x with the JellyJams workbench active unless stated
otherwise. "Tree" = the Model tree; "label" = the text shown there (also
readable as `obj.Label` in the Python console).

1. New document, create a Body (Part Design Body command or ribbon) ->
   the origin planes are `Top Plane` (Role `XY_Plane`), `Front Plane`
   (`XZ_Plane`), `Right Plane` (`YZ_Plane`); the body stays `Body`; origin,
   axes and origin point keep FreeCAD's labels.
2. In the same document create a second and third Body -> `Top Plane2`,
   `Front Plane2`, `Right Plane2`, then `Top Plane3`, ...; no label ends in
   `001`.
3. Create a sketch on the Top Plane and a Pad from it -> `Sketch1`,
   `Boss-Extrude1`; the tree already shows `Boss-Extrude1` while the Pad task
   dialog is still open. In the Python console `obj.Name` is still `Sketch`
   and `Pad`.
4. Create Pocket, Revolution, Groove, AdditivePipe, SubtractivePipe,
   AdditiveLoft, SubtractiveLoft, Hole, Fillet, Chamfer, Draft, Thickness,
   LinearPattern, PolarPattern, Mirrored, MultiTransform, datum Plane, datum
   Line, datum Point -> `Cut-Extrude1`, `Revolve1`, `Cut-Revolve1`, `Sweep1`,
   `Cut-Sweep1`, `Loft1`, `Cut-Loft1`, `Hole1`, `Fillet1`, `Chamfer1`,
   `Draft1`, `Shell1`, `LPattern1`, `CirPattern1`, `Mirror1`,
   `MultiPattern1`, `Plane1`, `Axis1`, `Point1` respectively.
5. Rename a sketch by hand to `Sketch4` while `Sketch1` exists, then create a
   sketch -> `Sketch5` (no gap filling).
6. Rename `Boss-Extrude1` to `Base plate`, create another pad ->
   `Boss-Extrude2`; `Base plate` is unchanged afterwards and after further
   operations, re-activation of the workbench, save and reopen.
7. Start a Pad, cancel the dialog, start a Pad again -> `Boss-Extrude1`
   (assuming no other Boss-Extrude exists); the Report view shows no error.
8. Create a pad (`Boss-Extrude1`), Undo, Redo -> the pad is back as
   `Boss-Extrude1` (not `Boss-Extrude2`, not `Pad`).
9. Switch to Part Design, create a sketch and a pad -> labels stay FreeCAD's
   (`Sketch`, `Pad` or with FreeCAD suffixes). Switch back to JellyJams ->
   those labels are still unchanged.
10. Open an `.FCStd` saved from plain FreeCAD containing `Pad`, `Sketch001`
    -> after opening (with JellyJams active) no label has changed; creating a
    new sketch then yields `Sketch<highest+1>` where `Sketch001` counts as 1
    (e.g. `Sketch2`).
11. Activate JellyJams, switch away and back five times, create a sketch in a
    new document -> exactly `Sketch1`.
12. Create an assembly (FreeCAD Assembly command while JellyJams is active)
    -> the assembly is `Assembly1`, its joint folder `Mates`; if FreeCAD
    gives the assembly an origin, its planes follow 3.3 (`Top Plane`, or
    `Top Plane2` when the document already has one). A second assembly in
    the same document -> `Assembly2` with folder `Mates2`.
13. Insert the body of a saved part file `Shaft.FCStd` into the assembly
    twice and a part from the same document labeled `Plate` once ->
    `Shaft<1>`, `Shaft<2>`, `Plate<1>`. A plain `App::Link` created outside
    any assembly keeps its label.
14. Ground `Shaft<1>` (Toggle Grounded) -> `(f) Shaft<1>`, `Shaft<2>` stays.
    Unground -> `Shaft<1>`. Undo -> `(f) Shaft<1>` again. Insert another
    Shaft -> `Shaft<3>`. The grounded-joint object keeps FreeCAD's label.
15. Rename a component by hand to `Motor` and ground it -> `(f) Motor`;
    unground -> `Motor`.
16. Create a Distance joint with distance 0 -> `Coincident1`; a Cylindrical
    joint -> `Concentric1`; a Distance joint with 5 mm -> `Distance1`. In the
    joint dialog switch the first one's type to Parallel -> `Parallel1`;
    then set the third one's distance to 0 -> `Coincident1` (the first mate
    no longer holds that name); set it back to 5 mm -> `Distance1`. Each Fixed/Revolute/Slider/Ball/Perpendicular/Angle/
    RackPinion/Screw/Gears/Belt joint gets `Lock1`/`Hinge1`/`Slider1`/
    `Ball Joint1`/`Perpendicular1`/`Angle1`/`Rack Pinion1`/`Screw1`/`Gear1`/
    `Belt1`.
17. Rename a mate by hand to `Front bearing` and change its distance/type ->
    it stays `Front bearing`. Rename a Cylindrical mate by hand to
    `Slider5` (or `Joint001`), then trigger a refresh (e.g. create any
    object in that document) -> it becomes `Concentric<N>`.
18. Create a drawing with FreeCAD's TechDraw commands (insert ISO template
    page, projection group with Front/Top/Right/isometric) -> page `Sheet1`,
    template `Sheet Format1`, group `Standard 3 View`, views `Front View`,
    `Top View`, `Right View`, `Isometric View` (a Rear item would be
    `Back View`). A second projection group -> `Standard 3 View2`.
19. On the sheet add a model view, dimension, balloon, rich annotation,
    leader, face hatch, geometric hatch, FreeCAD weld symbol, clip group,
    image, SVG symbol -> `Drawing View1`, `Dimension1`, `Balloon1`, `Note1`,
    `Leader1`, `Area Hatch1`, `Area Hatch2`, `Weld Symbol1`, `Crop Frame1`,
    `Picture1`, `Picture2`.
20. JellyJams drawing tools: sheet sketch -> `Sheet Sketch1` and its view
    `Sheet Sketch View1`; Text tool -> `Text1`; Surface Finish ->
    `Surface Finish1`; JellyJams weld symbol -> `Weld Symbol<N>` (sharing the
    sequence with FreeCAD weld symbols). A section view keeps the section
    labeling area's name (`Section View A-A`) and its view label annotation
    is not renamed by this area.
21. While dimensioning (tool cursor on the sheet, dimension tool active),
    FreeCAD does not crash; after the tool ends (arrow cursor back) the new
    dimension is labeled `Dimension<N>` within about one second. Cancelling a
    dimension tool with Esc produces no error in the Report view.
22. Existing drawing: in a document made with TechDraw outside JellyJams
    (projection group with Front, Top, Left, Right items), relabel the Left
    item to `Left 2`, the Top item to `ProjItem007`, the Front item to
    `Front001`, the Right item to `Side detail`, and the template to
    `Template`; save, reopen, activate JellyJams, open the sheet window ->
    `Left View`, `Top View`, `Front View`, `Side detail` (unchanged),
    `Sheet Format1`; the page keeps `Page`. Switch to the 3D view and back to
    the sheet -> no further label changes.
23. With any non-JellyJams workbench active, opening a sheet window or
    changing joints renames nothing.
24. Leaving the workbench changes no label, and no key under
    `User parameter:BaseApp/Preferences` (in particular nothing under
    `Mod/JellyJams`) is added or changed by the naming feature (compare
    `user.cfg` before/after a session that only exercises naming).
25. A document saved after JellyJams naming opens in plain FreeCAD (JellyJams
    not installed) without errors and shows the same SolidWorks labels.
26. Set FreeCAD's UI language to a language whose catalog translates
    TechDraw and Assembly, and restart. With the TechDraw workbench active,
    make a drawing with its own commands (template page, projection group);
    with the Assembly workbench active, add a Cylindrical joint. Switch to
    JellyJams: opening the sheet window gives the English names of criterion
    22 (`Front View`, `Sheet Format1`, ...), and the next assembly refresh
    (5.4) renames the joint to `Concentric<N>`. In that same session, a
    projection item relabeled to a word of a third language keeps its label.
