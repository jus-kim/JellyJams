# JellyJams specification: Sketching

> **Implemented in:** [`jellyjams/sketch_edit.py`](../../jellyjams/sketch_edit.py) (TempoVis interception, 2.1), [`sketch_gesture.py`](../../jellyjams/sketch_gesture.py) (feature from the open sketch, 2.2; sketch first, 2.6), [`context_sketch.py`](../../jellyjams/context_sketch.py) (context icon, 2.3), [`sketch_tools.py`](../../jellyjams/sketch_tools.py) (`JellyJams_Centerline`, `JellyJams_MidpointLine`, 2.4 and 2.5), [`edit_guard.py`](../../jellyjams/edit_guard.py) (feature editing stays in JellyJams, 2.7); icons [`centerline.svg`](../../resources/icons/centerline.svg), [`midpoint_line.svg`](../../resources/icons/midpoint_line.svg). The Part Design `SwitchToWB` override that 2.6 and 2.7 rely on is owned by [assembly.md](assembly.md) 5 ([`switch_prefs.py`](../../jellyjams/switch_prefs.py)).
>
> **Status:** see [../status.md](../status.md)

Area: **sketching**. Target: FreeCAD 1.1+ (verified facts are for 1.1.4).
Product context: JellyJams is a FreeCAD workbench (key and class `JellyJamsWorkbench`,
MenuText `JellyJams`) that makes FreeCAD look, feel and operate like SolidWorks.
All user-visible text is English. Report-view messages written by JellyJams start
with the prefix `JellyJams: `.

This area covers eight behaviors:

1. **Sketch editing stays in JellyJams.** Opening a sketch does not jump to FreeCAD's
   Sketcher workbench while JellyJams is active. FreeCAD's normal behavior is unchanged
   everywhere else and comes back fully when the user leaves JellyJams.
2. **Feature from the open sketch.** Clicking a profile-feature ribbon button (for example
   "Extruded Boss/Base") while a sketch is open closes the sketch and starts the feature
   on that sketch.
3. **Create-sketch context icon.** Click the flat top of a pad, for example, and a
   one-button "Sketch" popup shows up just above and to the right of the pointer. It
   dims while the pointer travels away and closes beyond a fixed distance.
4. **Centerline** (`JellyJams_Centerline`). Lines drawn with this tool become construction
   geometry automatically.
5. **Midpoint Line** (`JellyJams_MidpointLine`). The user picks the midpoint and one end, and
   the other half is created as a mirror image that stays symmetric.
6. **Sketch first.** Clicking "Extruded Boss/Base" (or Extruded Cut, Revolved Boss/Base,
   Revolved Cut, Hole Wizard) when there is nothing to use as the profile opens a new
   sketch instead of FreeCAD's "No sketch to work on" warning. Exiting that sketch starts
   the feature on it. The cutting features do this only in a body that already holds a
   solid feature; in a body without one, Extruded Cut and Revolved Cut get FreeCAD's own
   refusal, and Hole Wizard gets a JellyJams status-bar message. With several bodies and none
   active, the press goes to FreeCAD, which asks which body to work in.
7. **Feature editing stays in JellyJams.** Opening a Part Design feature for editing (a
   new feature's dialog, or double-clicking a Pad) does not switch to the Part Design
   workbench. Choosing another workbench in the workbench selector still works.

8. **Automatic drawing aids.** Sketch entry enables native object snapping and
   automatic constraints. Previous values return on edit exit or leaving JellyJams.

The words MUST, MUST NOT, SHOULD and MAY are used in their usual normative sense.

---

## 1. Purpose

SolidWorks users expect the following:

- Sketching happens in the same environment as part modeling. The CommandManager
  (JellyJams ribbon) stays on screen and simply shows its Sketch tab.
- Clicking a feature such as Extruded Boss/Base while still in a sketch ends the sketch
  and uses it as the feature's profile.
- Clicking Extruded Boss/Base with no sketch asks for a plane, opens a sketch on it, and
  builds the extrusion from that sketch when the sketch is exited.
- Editing a feature happens in the same environment, with the CommandManager on screen.
- Clicking a planar face offers a context-toolbar "Sketch" button to start a sketch on
  that face.
- The sketch line tools include "Centerline" and "Midpoint Line".

FreeCAD does none of this out of the box. This area adds these behaviors, but only
inside the JellyJams workbench. It MUST NOT change the user's files or FreeCAD's
behavior in other workbenches.

---

## 2. User-visible behavior and UI

### 2.1 Sketch editing stays inside JellyJams

**FreeCAD background (public fact, 1.1.x):** every sketch's view provider has a saved
string property `EditingWorkbench`, which defaults to `SketcherWorkbench`. When a
sketch enters edit mode, FreeCAD asks the `Show` module's TempoVis helper to activate
that workbench (`Show.mTempoVis.TempoVis.activateWorkbench`). When the sketch leaves
edit mode, TempoVis switches back to the workbench that was recorded earlier. In 1.1.x
only the Sketcher uses this workbench switch.

Required behavior:

- While the active workbench is `JellyJamsWorkbench`, a request to switch workbenches
  made through TempoVis MUST be ignored. "Active" means the workbench FreeCAD reports
  as active at the moment of the request (`FreeCADGui.activeWorkbench().name()`). The
  sketch still enters edit mode as usual: edit-mode display, task panel and Sketcher
  commands all work. However, the workbench selector keeps showing "JellyJams", the
  JellyJams ribbon (`JellyJamsCommandManager` dock) stays visible, and the Sketcher workbench
  toolbars do not appear.
- Because no switch was recorded, nothing is switched back when the sketch is closed.
  The user stays in JellyJams.
- This applies to every way of entering sketch edit while JellyJams is active:
  double-clicking a sketch in the tree, Edit sketch, a new sketch from the ribbon or
  context icon, and sketches opened by other JellyJams features such as the drawing
  sheet sketch.
- While any other workbench is active (for example Part Design), FreeCAD MUST behave
  exactly as it normally does: it switches to the Sketcher on edit and switches back on
  close.
- JellyJams MUST NOT read-modify-write or otherwise change any sketch's
  `EditingWorkbench` property. That property is saved in the user's file and also
  controls behavior in Part Design.
- The ribbon switching to its "Sketch" tab on entering a sketch, and back on leaving,
  belongs to the **ribbon** area. This area only guarantees that the workbench does
  not change.

Lifecycle:

- The interception is installed when JellyJams is activated (workbench `Activated()`)
  and removed when JellyJams is deactivated (`Deactivated()`).
- Installing more than once (for example, entering JellyJams repeatedly) MUST NOT stack
  multiple interceptions. At most one JellyJams interception exists at any time.
- On removal, `Show.mTempoVis.TempoVis.activateWorkbench` MUST again be the identical
  original FreeCAD function object that was there before JellyJams first installed.
- If another add-on replaced that method after JellyJams installed, JellyJams MUST NOT
  remove or overwrite the other add-on's replacement. In that case JellyJams' own
  interception may remain underneath. It is harmless because it only acts while
  JellyJams is the active workbench.
- If the active workbench cannot be determined (an exception occurs), the request MUST
  be passed through to FreeCAD unchanged.

### 2.2 "Feature from the open sketch" gesture

**Profile features (exact FreeCAD command ids)** are commands that accept a selected
sketch as their profile:

| Command id | SolidWorks term used on the ribbon |
|---|---|
| `PartDesign_Pad` | Extruded Boss/Base |
| `PartDesign_Pocket` | Extruded Cut |
| `PartDesign_Revolution` | Revolved Boss/Base |
| `PartDesign_Groove` | Revolved Cut |
| `PartDesign_Hole` | Hole Wizard |
| `PartDesign_AdditivePipe` | Swept Boss/Base |
| `PartDesign_SubtractivePipe` | Swept Cut |
| `PartDesign_AdditiveLoft` | Lofted Boss/Base |
| `PartDesign_SubtractiveLoft` | Lofted Cut |
| `PartDesign_AdditiveHelix` | Helical Boss/Base |
| `PartDesign_SubtractiveHelix` | Helical Cut |

Required behavior:

- The gesture applies when the user activates one of the profile features from the
  JellyJams ribbon and, at that moment, the active GUI document has an object of type
  `Sketcher::SketchObject` in edit mode (`FreeCADGui.ActiveDocument.getInEdit()`).
  "From the ribbon" includes every ribbon button form: large button, stacked row,
  flyout button, flyout menu item and toggle slot. The command must be invoked without a
  sub-command index.
- When the gesture applies, the user sees this sequence:
  1. The sketch is closed exactly as "Exit Sketch" closes it. The FreeCAD command used is
     `Sketcher_LeaveSketch`.
  2. The selection is cleared, and the sketch that was being edited becomes the only
     selected object (the whole object, with no sub-element).
  3. The clicked feature command starts. FreeCAD's own behavior with a preselected
     sketch makes that sketch the feature's profile. The user sees the feature's task
     panel with the sketch already used.
- Steps 2 and 3 MUST wait until FreeCAD has finished closing the sketch and its task
  panel. They MUST NOT run inside the click handler. A deferral of about 50 ms after
  issuing the exit has been verified to work on FreeCAD 1.1.4. A more robust "wait
  until no sketch is in edit, with a short cap" is also acceptable.
- The clicked command is run once, not twice. The ordinary run of the command is
  replaced by the gesture.
- When the gesture does not apply, the ribbon runs the command exactly as FreeCAD
  would. No exit or reselection happens. This covers:
  - a non-profile command (for example `PartDesign_Fillet`) with a sketch open;
  - a profile command with no sketch in edit, except the sketch-first case of §2.6;
  - an object other than a sketch in edit (for example a Pad being edited).
- Activations from outside the JellyJams ribbon (FreeCAD menus, other workbenches'
  toolbars, keyboard shortcuts, the Python console) are not required to use the
  gesture. They behave as FreeCAD normally does.
- The gesture applies to any sketch in edit, including JellyJams' drawing-sheet sketch.
  No special case is required. If FreeCAD's feature command cannot use that sketch, it
  reports this itself.

### 2.3 Create-sketch context icon ("Sketch" next to the pointer)

**Appearance**

- A small floating button appears near the mouse pointer. It looks like a frameless
  tooltip-style mini toolbar holding a single flat tool button.
- Qt `objectName` of the floating window: **`JellyJamsContextToolbar`**. It MUST be findable
  from FreeCAD's main window (`getMainWindow().findChild(QWidget, "JellyJamsContextToolbar")`),
  which means it is parented to the main window.
- Size: the button is 30 × 30 px, and its icon is about 22 × 22 px. The frame has a
  3 px inner margin, a white background, a 1 px light grey border (`#c9ced6`) and 4 px
  rounded corners (light JellyJams palette).
- Icon: the icon FreeCAD itself uses for the command `PartDesign_NewSketch`, looked up
  at runtime from that command's pixmap. No bundled copy is used. If the icon cannot be
  found, the button MUST still appear and work. A text fallback "Sketch" is acceptable.
- Tooltip: `Sketch`.
- Position: in global screen coordinates, the window's top-left corner goes 16 px right
  of and 40 px above where the pointer was at the click. The popup's lower edge then
  stays just above the pointer, so the clicked point remains visible, and the pointer
  starts inside the fully opaque zone of the fade (about 40 px from the popup centre).
- It stays on top of the FreeCAD window and MUST NOT take keyboard focus or activate
  itself when shown. Keystrokes keep going to FreeCAD.

**When it appears**

The icon appears when the user selects something and all of the following are true:

1. JellyJams is the active workbench. Its selection listener is installed on
   `Activated()` and removed on `Deactivated()`. The icon MUST NOT appear while another
   workbench is active.
2. The parameter `User parameter:BaseApp/Preferences/Mod/JellyJams`, bool
   **`ShowSketchButtonOnFace`**, is true. An absent key counts as true. The value is read at
   every selection, so changes take effect immediately without a restart.
3. No task dialog is open (`FreeCADGui.Control.activeDialog()` is false). This excludes,
   for example, a feature dialog that is picking faces, a sketch in edit, or a JellyJams
   panel.
4. The selected object exists, and neither it nor any object in its
   `InListRecursive` has type `Assembly::AssemblyObject`. In assemblies, faces are
   picked for mates instead.
5. The selected sub-element is a face. Its element name (the last dot-separated segment
   of the sub-element path, for example `Face6` from `Pad.Face6` or from a
   topological-naming-prefixed path) starts with `Face`, and the object resolves it to
   a shape (`getSubObject(subpath)`). Nested paths, such as a Body selected with
   sub-path `Pad.Face1`, MUST work.
6. The face is planar. Use `isPlanar()` on the face shape. If that is not available,
   use "a plane can be found" or "its surface is a plane" as fallbacks. If none of these
   can be evaluated, treat the face as not planar.
7. Exactly one element is selected in the whole selection. Count every selected
   sub-element, and count an object selected without sub-elements as one.

The icon is meant for 3D model faces only. A selection made on a TechDraw drawing sheet
SHOULD NOT produce the icon.

The icon is shown after FreeCAD has finished processing the click, not synchronously
inside the selection notification. The position uses the pointer position captured when
the selection was reported. Each new qualifying selection repositions the icon and
resets it to full opacity.

**When it disappears**

The icon is hidden when any of the following happens:

- a selection is added that does not qualify (for example Ctrl+click on a second face,
  an edge, a non-planar face, or an object picked in the tree);
- a selection is removed, the selection is replaced, or the selection is cleared (for
  example clicking empty space, or Esc clearing the selection);
- the pointer moves away from the icon (see fade below);
- a task dialog opens while the icon is visible;
- the icon is clicked;
- JellyJams is deactivated. The icon MUST be hidden no later than `Deactivated()`.

**Fade**

While the icon is visible, its window opacity follows the distance from the pointer to
the icon's center. JellyJams checks this about every 50 ms. Monitoring MUST stop while
the icon is hidden.

| Distance d (px) | Opacity |
|---|---|
| d ≤ 50 | 1.0 (fully visible) |
| 50 < d < 180 | linear: 1 − (d − 50) / 130 (for example d = 115 gives 0.5) |
| d ≥ 180 | hidden |

Once the icon has been hidden because of distance, moving the pointer back MUST NOT
bring it back. It returns only with a new qualifying selection.

**Click**

Clicking the button hides the icon and runs the FreeCAD command `PartDesign_NewSketch`.
The face is still selected, so FreeCAD creates a sketch attached to that face and opens
it for editing. Because of §2.1, the user stays in JellyJams. If the command raises an
error, an error is written to the Report view.

### 2.4 Centerline — command `JellyJams_Centerline`

**Command resources**

- MenuText: `Centerline`.
- ToolTip: explains that the tool draws a line that automatically becomes construction
  geometry, and that Esc or right-click ends the tool.
- Pixmap: a new, original JellyJams icon. Suggested design: a diagonal line drawn in
  construction style (dashed or dash-dot) with endpoint markers. It MUST NOT be a copy
  of any third-party or SolidWorks icon, and its file name MUST NOT contain
  "SolidWorks".
- No default keyboard shortcut.
- Enabled (`IsActive`) only while the active GUI document has a `Sketcher::SketchObject`
  in edit mode. At all other times it is greyed out. If activated anyway (for example
  from the console) with no sketch in edit, it does nothing.
- Ribbon placement (owned by the ribbon area): Sketch tab, Line flyout in the icon
  stack, with variants Line (`Sketcher_CreateLine`), Centerline (`JellyJams_Centerline`),
  Midpoint Line (`JellyJams_MidpointLine`) and Polyline (`Sketcher_CreatePolyline`). The ribbon
  label is "Centerline".

**Behavior**

- Activating the command starts FreeCAD's normal line tool (`Sketcher_CreateLine`).
  All the usual helpers stay available: snapping, automatic constraints and on-view
  dimension input. JellyJams MUST NOT draw lines itself.
- While "Centerline mode" runs, every line segment (`Part::GeomLineSegment`) that the
  user creates in that sketch after the mode started is converted to construction
  geometry (`SketchObject.setConstruction(index, True)`). FreeCAD then displays it in
  construction style.
- The conversion MUST happen promptly, within about 0.3 s of FreeCAD adding the line,
  without waiting for further user input. Starting the next tool or pressing a key is
  not required. (Converting the line only when the next tool starts is not
  acceptable.)
- Geometry that existed before the mode started is never touched. Geometry other than
  line segments (circles, arcs, splines, points) is never touched.
- If a line created during the mode reverts to normal geometry while the mode is still
  running (for example, a cancel rolled back the conversion), it MUST be converted again
  at the next check.
- JellyJams MUST NOT rely on toggling the Sketcher's global "create construction
  geometry" mode (`Sketcher_ToggleConstruction` without a selection). Its state cannot
  be read from Python in 1.1, so toggling it blindly could leave it inverted.

**Undo/transactions**

- If FreeCAD has no pending transaction on the document (`Document.HasPendingTransaction`
  is false), the conversion is recorded as its own undo step named `Centerline`. That
  transaction is opened and committed around the conversion, so JellyJams never leaves
  a transaction it opened uncommitted.
- If FreeCAD already has a pending transaction (common while a sketch is being edited),
  the conversion joins it. JellyJams MUST NOT open a nested transaction, and MUST NOT
  postpone the conversion because of it.

**Ending the mode**

Any of the following ends the mode:

- the user presses **Esc** anywhere in the application;
- the user presses the **right mouse button** anywhere in the application. This matches
  how FreeCAD's own tools end;
- the user clicks **any other JellyJams ribbon button**, including Midpoint Line;
- the sketch leaves edit mode, or a different sketch enters edit mode;
- **JellyJams is deactivated** (workbench switch);
- activating Centerline again. This ends the current run and starts a fresh one.

Detection of Esc and right-click MUST NOT consume or alter those events. FreeCAD must
still receive them, so its line tool ends normally. The mode ends just after FreeCAD
has handled the event.

When the mode ends through Esc, right-click, another ribbon button, workbench
deactivation or restart, it makes one final pass first. Lines created up to that moment
are still converted. When the mode ends because the sketch is no longer in edit (or
another sketch is), no geometry is changed.

After the mode has ended, lines drawn with the ordinary line tools stay normal geometry.

Other ways of switching Sketcher tools (keyboard shortcuts, the Sketcher's own
toolbars or menus) are not required to end the mode. This is an accepted limitation:
only line segments are affected.

### 2.5 Midpoint Line — command `JellyJams_MidpointLine`

**Command resources**

- MenuText: `Midpoint Line`.
- ToolTip: explains that the user clicks the midpoint and then one end, the other half
  is mirrored automatically, and Esc or right-click ends the tool.
- Pixmap: a new, original JellyJams icon. Suggested design: a diagonal line with a
  prominent marker at its middle and markers at both ends. One end may be drawn hollow
  to suggest the mirrored side. The same originality and file-name rules as for
  Centerline apply.
- No default keyboard shortcut.
- Enabled only while a `Sketcher::SketchObject` is in edit mode in the active GUI
  document. Ribbon placement: Sketch tab, Line flyout (see §2.4).

**Behavior**

This is the SolidWorks Midpoint Line: the line grows by the same length in both
directions from the first point.

- Activating the command starts FreeCAD's normal line tool (`Sketcher_CreateLine`),
  with all its helpers. The user's first click (the line's start point, PointPos 1) is
  the **midpoint**. The second click (end point, PointPos 2) is **one end**.
- For every new line segment (`Part::GeomLineSegment`) created in that sketch while the
  mode runs, JellyJams promptly (within about 0.3 s) adds a **partner** line segment:
  - from the same midpoint M to the mirrored end E' = 2·M − E, where E is the drawn end
    point. Both are in sketch coordinates in the sketch plane (z = 0). Example: drawn
    from (10, 5) to (40, 25), partner from (10, 5) to (−20, −15);
  - with the same construction state as the drawn line. A drawn construction line gets
    a construction partner; a normal line gets a normal partner. Midpoint Line by itself
    never makes lines construction;
  - tied by exactly these two FreeCAD constraints, added in this order:
    1. `Coincident` between the partner's start point and the drawn line's start point
       (partner index, PointPos 1; drawn index, PointPos 1);
    2. `Symmetric` making the drawn line's end point and the partner's end point
       symmetric about the drawn line's start point (drawn index, PointPos 2; partner
       index, PointPos 2; symmetry point: drawn index, PointPos 1).

    Constraint choice. Once the two start points share M, a point-symmetry
    constraint has exactly one solution for the partner's free end, E' = 2·M − E.
    The pair therefore acts as one line pivoting about M: drag either end and the
    opposite end answers by the same amount in the other direction. Encodings that
    pin only direction and length (for example `Parallel` together with `Equal`) MUST
    NOT be used. Those relations also hold for E' = E, a partner lying on top of the
    drawn half, which gives the solver a second admissible state to settle into.
  - After adding partners, the sketch is solved so the display updates immediately.
    Solver errors are ignored here; FreeCAD's normal sketch status reporting applies.
- Partners created by the tool are never mirrored again.
- A zero-length drawn line (start and end within 1e-9) gets no partner.
- Geometry that existed before the mode started, and all non-line geometry, is never
  touched.
- If geometry is removed while the mode runs (undo, delete) so that the sketch has
  fewer geometries than the tool has already examined, the tool continues from the
  current geometry count. It MUST NOT mirror older lines because of shifted indices, and
  it must still mirror lines drawn after the removal.
- Undo/transactions: same rules as Centerline. A separate undo step is named
  `Midpoint Line` when no FreeCAD transaction is pending; otherwise the change joins the
  pending transaction. No nested transaction is opened. One drawn line's partner
  geometry and both constraints go into the same transaction.
- Ending the mode: same triggers and final-pass rules as Centerline (§2.4). Clicking
  Centerline on the ribbon ends Midpoint Line (after its final pass) and starts
  Centerline, and the reverse also holds. A line drawn just before another ribbon button
  is clicked still gets its partner.

### 2.6 Sketch first: a profile feature with nothing to use opens a sketch

**FreeCAD background (verified 1.1.4):** `PartDesign_Pad` run with nothing selected and
no usable sketch in the active body shows the warning "No sketch to work on". The user
then has to cancel, start a sketch, draw it, exit it, select it and press Pad again.
SolidWorks instead asks for a plane, opens a sketch on it and builds the extrusion from
that sketch once the sketch is exited.

**Sketch-first features** (`constants.SKETCH_FIRST_FEATURES`):

| Command id | Ribbon label |
|---|---|
| `PartDesign_Pad` | Extruded Boss/Base |
| `PartDesign_Pocket` | Extruded Cut |
| `PartDesign_Revolution` | Revolved Boss/Base |
| `PartDesign_Groove` | Revolved Cut |
| `PartDesign_Hole` | Hole Wizard |

The swept, lofted and helical features need more than one input (a path, more sections,
an axis) and keep FreeCAD's own behavior.

**Target body.** The body a profile feature works in: the active body
(`ActiveView.getActiveObject("pdbody")`, `constants.ACTIVE_BODY_KEY`); with no active body,
the only `PartDesign::Body` of the document (FreeCAD activates a lone body by itself); with
no body, or several bodies and none active, there is no target body.

**Containers are no selection.** When every selected item is a container selected as a
whole (no sub-element): a `PartDesign::Body`, `App::Origin`, `App::Part` or
`App::DocumentObjectGroup`, JellyJams clears the selection and handles the press as if
nothing were selected. FreeCAD would reject a container as a profile, and the ribbon's Body
button leaves the new body selected. A container selected together with anything else, or
with a sub-element (a face picked through the body), is not cleared and counts as
"other" below.

**When it applies.** A ribbon press of a sketch-first feature (every ribbon button form,
no sub-command index, as in §2.2) while all of these hold:

1. no sketch is in edit (otherwise §2.2 applies);
2. no task dialog is open;
3. there is an active GUI document;
4. for **Extruded Cut, Revolved Cut and Hole Wizard** (`PartDesign_Pocket`,
   `PartDesign_Groove`, `PartDesign_Hole`; `sketch_gesture.SUBTRACTIVE_FEATURES`): there is
   a target body and it holds a solid by FreeCAD's own rule (`Body::isSolid()`): at least one
   object of its `Group` is derived from `PartDesign::Feature` (`sketch_gesture._has_solid`).
   Sketches, origin and datum planes, lines and points are no Part Design features, so a body
   with only those holds no solid; a Pad counts as soon as it is in the body, even before its
   shape has been computed. The body's own shape is not looked at.
   - **No target body** (several bodies, none active): JellyJams does not take the press
     (`try_run` returns False, no status text, no warning). It goes to FreeCAD unchanged,
     which asks which body to work in (FreeCAD 1.1.4: the "Active Body Required" dialog), as
     without JellyJams.
   - **A target body without a solid** (`sketch_gesture._nothing_to_cut`, true only when the
     target body is known): there is nothing to cut, no sketch-first starts, and the press is
     refused at once instead of after the user has drawn a sketch (**refusal without a
     solid**, below);
5. one of:
   - **nothing is selected and there is no free sketch.** A free sketch is one FreeCAD's
     profile feature would take without a selection: an object derived from
     `Part::Part2DObject` that is in the target body (with no target body, any object in
     the document), is not used by a Part Design feature (no `PartDesign::Feature` in its
     `InList`), has a non-null shape with at least one wire, and is not after the body's
     insert point. The insert point follows the body's `Tip`: the first solid Part Design
     feature (a `PartDesign::Feature` that is not a sketch; datum planes do not count) after
     the `Tip` in the body's `Group`, and everything after it, are hidden from FreeCAD's
     profile choice in a rolled-back body, so sketches there do not count;
   - **only planes and planar faces are selected.** Every selected item is a datum or
     origin plane (`App::Plane`, `PartDesign::Plane`) or an object whose selected
     sub-elements are all faces that are planar (`findPlane()` finds a plane).

Anything else runs the feature exactly as FreeCAD would: a selected sketch, an edge, a
curved face, a whole solid, a mix that includes any of these, or nothing selected
with one or more free sketches available.

**Refusal without a solid** (`sketch_gesture._refuse_without_solid`, rule 4). Who refuses
depends on the feature (`REFUSED_BY_FREECAD`):

| Feature | Refused by | What the user sees | `try_run` returns |
|---|---|---|---|
| Extruded Cut (`PartDesign_Pocket`), Revolved Cut (`PartDesign_Groove`) | FreeCAD | The press goes to FreeCAD unchanged, which refuses it at once with its own message. | False |
| Hole Wizard (`PartDesign_Hole`) | JellyJams | Nothing runs. The status bar shows "`<menu text>` needs a solid to cut into: create a boss or base feature first." for 6 s (`NEEDS_SOLID_MS`), and the same text is a Report-view warning. | True |

FreeCAD's Hole has no check for a solid: with a profile and nothing to cut it builds a Hole
that then fails to recompute (with nothing selected in the active body FreeCAD 1.1.4 shows
"No sketch to work on"), and while FreeCAD's plane picker is open it would close the picker
([freecad-facts](../freecad-facts.md)). The same split applies to a fresh press and to a press
while a sketch-first waits for its plane (retarget, below). Without a target body there is no
refusal at all (rule 4).

**Sequence the user sees:**

1. JellyJams runs `PartDesign_NewSketch` instead of the feature. With a plane or planar
   face selected, FreeCAD attaches the new sketch to it and opens it. With nothing
   selected, FreeCAD shows its plane picker in the task panel. The "No sketch to work on"
   warning does not appear.
2. The status bar shows "New sketch for <feature menu text>: pick a plane or a flat face,
   draw the profile, then exit the sketch." It is rewritten when a retarget changes the
   feature, and cleared whenever the sketch-first ends without that hint being replaced: the
   feature starts, the watcher drops it, a stale sketch-first is dropped by the next press,
   a press inside a sketch replaces it (§2.2), a check fails, JellyJams is left or the
   document is closed.
3. One click on a valid origin/datum plane confirms the native picker and opens
   the new sketch in JellyJams (§2.1). Double-clicking is not required. This applies
   to native 3D plane picks and the older picker's plane-list rows. The user draws
   the profile and exits the sketch.
4. After the sketch has left edit mode and its task dialog has closed, and if it holds at
   least one geometry, the selection is cleared, the new sketch becomes the only selected
   object, and the feature command runs once, as in §2.2 steps 2 and 3. The feature's
   task panel opens with the sketch as its profile, and JellyJams stays the active
   workbench (§2.7 and the Part Design `SwitchToWB` override of
   [assembly.md](assembly.md) 5).

**State machine.** JellyJams follows the plane pick and the sketch edit by looking every
150 ms (`WATCH_MS`). The decision is the pure function `sketch_gesture.advance(intent,
sketch_in_edit, dialog_open, sketches_created_since_the_press, now)`, which returns the
next state and an action (none, `start` or `drop`):

| State | Observation | Result |
|---|---|---|
| picking | a sketch created since the press is in edit | editing that sketch |
| picking | a task dialog is open (the plane picker), or an older sketch is in edit | keep waiting |
| picking | nothing in edit, no dialog, less than `PICK_GRACE_S` (1.5 s) since the press | keep waiting (FreeCAD is still opening its picker) |
| picking | nothing in edit, no dialog, `PICK_GRACE_S` or more since the press | drop quietly (the picker was cancelled) |
| editing | the new sketch is in edit, or nothing is in edit but a dialog is still open | keep waiting |
| editing | another sketch is in edit | drop quietly |
| editing | nothing in edit and no dialog | start the feature (only if the sketch has geometry) |

More rules:

- While this sketch-first is picking in its own active document, the watcher may
  press the current native task's enabled OK button after a valid single plane
  choice. For the older `PartDesignGui::TaskFeaturePick`, require exactly one
  selected, visible, enabled plane row. For the 26.3 `PartGui::TaskAttacher`,
  require exactly one newly created sketch, a non-deactivated attachment mode
  and exactly one plane support. Resolve Origin subpaths as document objects
  (`getSubObject(path, 1)`), not their geometric Python representation.
- Match only those native forms (Qt class or normalized form objectName); do not
  confirm unrelated task dialogs, existing-sketch attachment edits, multiple
  references, disabled choices or an inactive document's task. With no valid
  plane choice, keep waiting. Leave non-plane attachment choices to native OK.
- This confirmation runs in the existing watcher after native selection handling.
  It changes no selection/click preference, attachment property, placement or
  document data itself; FreeCAD's OK handler owns sketch creation/entry. Keep
  watching until edit actually starts, and preserve Cancel and feature retargeting.

- A press of a profile feature while a sketch-first is still picking (no sketch in edit yet):
  - **plane picker open** (a task dialog is open) and the feature is a sketch-first
    feature: no second sketch starts and nothing runs now. It changes which feature runs at
    the end, the last one pressed, and the status hint is rewritten for it (retarget). A
    cutting feature (Extruded Cut, Revolved Cut, Hole Wizard) is retargeted unless the target
    body is known and holds no solid (rule 4 above; with no target body it is retargeted too);
    in that case there is nothing to cut and the press
    is refused as in **refusal without a solid**: Extruded Cut and Revolved Cut go to FreeCAD
    unchanged (which refuses them, as in the next case) and the status hint stays; Hole Wizard
    is refused by JellyJams with its status text and warning, nothing runs and the plane
    picker stays open. In every case the waiting sketch-first keeps its feature;
  - **plane picker open** and any other profile feature (sweep, loft, helix): the press goes
    to FreeCAD unchanged (which refuses it while a dialog is open). The waiting sketch-first
    keeps its feature and its hint;
  - **no task dialog open** (the picker was cancelled or never opened, and the watcher has
    not dropped it yet): the waiting sketch-first is stale. It is dropped, its hint is
    cleared, and the press is handled from the start as if nothing were pending, so it may
    start a new sketch-first or run the feature the ordinary way.
- A press of any profile feature while the new sketch is open is the §2.2 gesture. It
  replaces the sketch-first, and only the pressed feature runs.
- Exiting the new sketch without drawing anything starts no feature.
- The sketch-first ends without a feature when JellyJams stops being the active
  workbench or the document is closed (log-level message).
- If `PartDesign_NewSketch` fails, the command runner reports an error, no sketch-first
  state is kept, and the press runs the feature the ordinary way (FreeCAD then shows its
  own message).
- At most one sketch-first is pending at any time, and it lives in memory only.
- **Checks belong to their sketch-first.** Every check is tied to the sketch-first it was
  scheduled for, and the next check is tied to the state it leads to. A check whose
  sketch-first is no longer the pending one (dropped, started, or replaced by a fresh press)
  does nothing and schedules nothing, so the checks of a replaced sketch-first never look at
  its successor, and only one chain of checks runs at a time. A retarget changes the feature
  of the pending sketch-first itself, so its checks go on.

### 2.7 Feature editing stays in JellyJams

**FreeCAD background (verified 1.1.4):**

- Part Design's view providers call `Gui::Command::assureWorkbench("PartDesignWorkbench")`
  in every `setEdit` of a feature, with no preference to turn it off, and switch back to
  the remembered workbench in `unsetEdit`. `assureWorkbench` runs the command string
  `Gui.activateWorkbench('PartDesignWorkbench')`.
- The workbench selector and View > Workbench (`Std_Workbench`) run the same kind of
  command string, so the caller alone cannot tell a feature edit from a user's choice.
- Separately, Part Design switches to its workbench whenever a body becomes active
  (including on leaving a sketch) while its `SwitchToWB` preference is true or missing.
  That preference is held at false by [assembly.md](assembly.md) 5.

Required behavior:

- While JellyJams is active, `FreeCADGui.activateWorkbench` is wrapped. A request for
  another workbench that comes from a FreeCAD command string is held for one event-loop
  turn. It comes from one when the code object's file name is `<string>` in the frame that
  called the wrapper or in one of the frames above it, `edit_guard.FRAME_SEARCH_DEPTH` (6)
  frames in all, so other add-ons' wrappers in between (up to five) do not hide it. Then:
  - if an object has entered edit mode meanwhile (the object in edit, identified by
    document and object name, is set and differs from the one at the time of the
    request), the request belonged to opening that edit. JellyJams stays active, and a
    log-level message names the object and the workbench that was asked for;
  - otherwise (nothing in edit, or the same object as before), the switch happens as
    requested. The workbench selector and View > Workbench therefore keep working, one
    event-loop turn later;
  - if JellyJams is no longer the active workbench by then, nothing more happens;
  - if the switch raises, a Report-view **warning** names the workbench.
- Calls from Python code (macros, scripts, the Python console, other add-ons) pass
  straight through at once, as do requests for `JellyJamsWorkbench` itself and every
  call while JellyJams is not the active workbench.
- Because the switch on `setEdit` was held, Part Design remembers JellyJams as the
  workbench to return to. Its `unsetEdit` request is for JellyJams and passes through.
- Installed on `Activated()` (after §2.1) and removed on `Deactivated()`. Repeated
  installs never stack. On removal `FreeCADGui.activateWorkbench` is FreeCAD's identical
  original function, unless another add-on replaced it after JellyJams; then the
  JellyJams wrapper stays underneath, disarmed, and passes every call through.
- **Chain tracking.** JellyJams remembers whether its wrapper is still part of the call
  chain. While it is (the JellyJams wrapper on top, or under another add-on's wrapper that
  calls it), entering JellyJams again only re-arms the wrapper where it is. It never wraps
  the other add-on's wrapper: that one already calls the JellyJams wrapper, so the two would
  call each other without end. Removal hands FreeCAD's function back only while the
  JellyJams wrapper is on top; then the wrapper leaves the chain and the next install wraps
  afresh.
- While another add-on's wrapper sits above the JellyJams wrapper, the command string is
  still found a frame or more further up, so feature edits keep JellyJams there too. A
  command string found by mistake (Python code that some other command string called) costs
  only the one-turn wait: the switch still happens unless an edit started meanwhile. A
  command string more than `FRAME_SEARCH_DEPTH` frames up is not looked for, and that request
  passes straight through.

---

### 2.8 Automatic snapping and constraints

Implemented by [`sketch_assist.py`](../../jellyjams/sketch_assist.py).

- On every sketch edit entry while JellyJams is active, enable native `Snap` and
  `SnapToObjects` in `Preferences/Mod/Sketcher/Snap`, and the edited sketch view's
  `Autoconstraints`. This also applies when entering JellyJams with a sketch open.
- Use FreeCAD's native drawing tools and preselection for the sketch origin,
  endpoints, edges and midpoints. Do not implement a second geometry picker.
  Geometry outside the sketch still needs native projection/Convert Entities;
  no automatic external references are added.
- Leave grid snapping, grid visibility, snap angle, selection tolerance and other
  sketches' `Autoconstraints` unchanged. Users may disable aids during the edit;
  they are enabled again on the next edit entry, not forced on every timer tick.
- Back up both snapping Bool values before writing, preserving absence, as JSON
  `{"Snap": [existed, value], "SnapToObjects": [existed, value]}` in
  `Mod/JellyJams/OriginalSketchSnapping`. Absent values are represented by
  `[false, null]`. Never replace a pending valid backup. Damaged backups produce
  one warning and are removed without guessing originals.
- Restore the sketch's original `Autoconstraints` and both preferences on edit
  exit, document close, workbench leave and accepted quit. Remove finished backups.
  Startup recovery restores snapping preferences after an abnormal exit. The quit
  compatibility fallback must resume the aids if quit is cancelled.
- `Autoconstraints` is a saved view property. Keep its original only in memory,
  restore it synchronously at `slotStartSaveDocument`, and resume the current
  edit's setting at `slotFinishSaveDocument`. The file must contain the original
  value, including when saved during editing. No document property is added.
- Edit and save observers are registered only while enabled and removed on
  leave/quit. A 150 ms edit poll covers hosts lacking GUI observers and edits
  already open at activation. It must not reapply while a save is in progress.
- Native automatic recovery bypasses normal save callbacks. Install a filter
  only on the application's `Gui::AutoSaver` QObject (never on the application).
  Before its timer event, temporarily restore `Autoconstraints`; resume after
  that event returns, with a callback that cannot affect a retired edit. Recovery
  copies must contain the original setting too. Remove the filter on leave/quit.
- Temporary `Autoconstraints` writes scope the native `NoModify` status so the
  override alone does not mark a model modified. Restore pre-existing status flags.

### 2.9 Smart Dimension preview placement

Implemented by [`sketch_dimension.py`](../../jellyjams/sketch_dimension.py),
started by the ribbon's existing `Sketcher_Dimension` slot.

- Smart Dimension from the JellyJams ribbon runs FreeCAD's command once. Its
  linear dimension preview must follow the pointer without FreeCAD's deliberate
  screen-space gap. The pointer itself is never warped or remapped.
- Native picking, dimension-type inference and M cycling, values, solving,
  confirmation dialogs, cancellation and transactions remain FreeCAD's. Only
  the new preview's native label distance changes. Existing and confirmed
  labels must not move, including during continuous creation and after Cancel.
- On each native viewport mouse move, deliver the original event once, then
  undo the linear preview offset `(view height + view width) * 0.01`, matching
  native camera dimensions for orthographic/perspective and portrait/landscape.
  Apply only to newly created Distance, DistanceX and DistanceY constraints;
  circular arc-length, radial and angular labels keep native placement.
- FreeCAD clears its selection on confirm/cancel. That boundary advances the
  floor of completed constraints before later previews are adjusted. Every
  native mouse move recomputes its own label distance, so the correction must
  not accumulate across events. Do not add undo steps or persistent preferences.
- Watch only the edited viewport, never the application. Remove the filter on
  the next ribbon command, viewport hiding, edit/view changes, a different tool's
  bitmap cursor on a subsequent move, and ribbon hide (leave and quit). A native
  arrow cursor around the value dialog must not end continuous dimensioning. A failed
  correction must not deliver an already handled native move twice.
- This is a ribbon-dispatch behavior. Direct invocation of FreeCAD's native
  command outside that dispatch retains native placement.

## 3. Triggers and timing

| Event | Effect |
|---|---|
| JellyJams `Activated()` | Install the sketch-edit interception, then the feature-edit guard (both idempotent). Install the context-icon selection listener (idempotent). |
| JellyJams `Deactivated()` | Remove the context-icon listener and hide the icon. End any running Centerline / Midpoint Line mode (with final pass). Remove the feature-edit guard, then the sketch-edit interception (restore the original functions). A pending sketch-first ends at its next check. |
| FreeCAD quits | `sketch_assist.disable` restores drawing aids through quit-revert. Other sketch hooks are in memory; FreeCAD does not call `Deactivated()` on quit. |
| Sketch enters edit while JellyJams is active | TempoVis workbench switch ignored. The workbench stays JellyJams. |
| Sketch enters edit in another workbench | FreeCAD default (switch to `SketcherWorkbench`, switch back on close). |
| Ribbon click on a profile feature with a sketch in edit | `Sketcher_LeaveSketch` immediately. After the sketch has closed (about 50 ms): clear the selection, select the sketch, run the feature. |
| Ribbon click on a sketch-first feature with nothing to use as the profile (§2.6) | Run `PartDesign_NewSketch` instead and show the status-bar hint. Check every 150 ms: when the new sketch has been exited with geometry, select it and run the feature. |
| Ribbon click on a sketch-first feature while a sketch-first plane picker is open | No new sketch; the clicked feature replaces the one that runs at the end and the status hint names it. A cutting feature does so unless the target body is known and holds no solid; in that case Extruded Cut and Revolved Cut run through FreeCAD unchanged (refused), Hole Wizard is refused by JellyJams (status text for 6 s and a warning), and the sketch-first keeps its feature and the picker stays open. |
| Ribbon click on another profile feature while a sketch-first plane picker is open | Runs through FreeCAD unchanged; the sketch-first keeps waiting with its feature. |
| Ribbon click on a profile feature while a sketch-first is picking but no task dialog is open | The stale sketch-first is dropped (hint cleared) and the click is handled as a fresh press. |
| Ribbon click on Extruded Cut or Revolved Cut with no solid in the target body | No sketch-first; the feature runs as in FreeCAD, which reports at once that there is nothing to cut. |
| Ribbon click on Hole Wizard with no solid in the target body | No sketch-first and nothing runs; the status bar reads "Hole needs a solid to cut into: create a boss or base feature first." (FreeCAD's menu text) for 6 s, and the Report view shows it as a warning. |
| Ribbon click on Extruded Cut, Revolved Cut or Hole Wizard with several bodies and none active (no target body) | No sketch-first and no JellyJams text; the feature runs as in FreeCAD, which asks which body to work in ("Active Body Required"). |
| Ribbon click on a sketch-first feature with only bodies, origins, parts or groups selected | The selection is cleared, then the click is handled as with nothing selected. |
| Plane picker cancelled (§2.6) | The sketch-first is dropped at the first check at least 1.5 s after the press. |
| FreeCAD command string asks for another workbench while JellyJams is active (§2.7) | Held one event-loop turn; dropped if an object entered edit meanwhile, otherwise the switch happens. |
| Python code calls `FreeCADGui.activateWorkbench` | Passes straight through. |
| Any ribbon click | Ends a running Centerline / Midpoint Line mode unless the click is that same tool (which restarts it). This happens before the clicked command runs. |
| Selection added (JellyJams active) | Evaluate the context-icon conditions. If they hold, show the icon after the click has been processed. Otherwise hide it. |
| Selection removed / set / cleared | Hide the context icon. |
| Every ~50 ms while the icon is visible | Update opacity from the pointer distance. Hide at ≥ 180 px or if a task dialog is open. |
| Context icon clicked | Hide, then run `PartDesign_NewSketch`. |
| `JellyJams_Centerline` / `JellyJams_MidpointLine` activated | End any running run of either tool (with final pass). Remember the sketch in edit and its current geometry count. Start `Sketcher_CreateLine`. |
| New line segment appears while a mode runs | Within about 0.3 s: convert to construction (Centerline) or add a mirrored partner plus constraints (Midpoint Line). |
| Esc key press / right mouse press anywhere | After FreeCAD handles the event: final pass, then the mode ends. |
| Sketch in edit changes or is closed while a mode runs | The mode ends without changing geometry. |

---

## 4. FreeCAD state read or changed (exact names)

**Parameters**

- Read: `User parameter:BaseApp/Preferences/Mod/JellyJams` → bool `ShowSketchButtonOnFace`
  (default true when absent).
- Written during sketch edit: Bool `Snap` and `SnapToObjects` in
  `Preferences/Mod/Sketcher/Snap`, with JSON backup `OriginalSketchSnapping` in
  `Mod/JellyJams`, all restored exactly as defined in 2.8.

**Python/API state changed at runtime (in memory only)**

- `Show.mTempoVis.TempoVis.activateWorkbench` (class attribute of the FreeCAD `Show`
  module's TempoVis class). JellyJams replaces it while installed and restores the
  identical original on removal. It is never persisted.
- `FreeCADGui.activateWorkbench` (module attribute, §2.7). JellyJams replaces it while
  installed and restores the identical original on removal. It is never persisted.
- The sketch-first state of §2.6 (feature, plane-pick or editing state, the new sketch's
  name, the document name and the sketches that existed at the press).
- `FreeCADGui.Selection.addObserver(...)` / `removeObserver(...)` for the context-icon
  listener. The listener receives `addSelection(doc, obj, sub, pnt)`,
  `removeSelection`, `setSelection` and `clearSelection`.
- An application-wide Qt event filter on `QApplication`, present only while a
  Centerline / Midpoint Line mode runs. It is pass-through and watches only Esc key
  presses and right mouse button presses.

**Document objects and properties read**

- `FreeCADGui.ActiveDocument.getInEdit()` → view provider. Its `.Object.TypeId ==
  "Sketcher::SketchObject"` identifies "a sketch is in edit".
- Sketch (`Sketcher::SketchObject`): `Geometry` (list; each item's `TypeId`, line =
  `Part::GeomLineSegment`), `getConstruction(i)`, `getPoint(i, 1|2)`, `Document`.
- Sketch view provider property `EditingWorkbench` (default `SketcherWorkbench`). It is
  **never written**.
- Selected object: `TypeId`, `InListRecursive`, `getSubObject(subpath)`. Face shape:
  `isPlanar()` (fallbacks: `findPlane()`, `Surface` type `Plane`).
- Assembly type id: `Assembly::AssemblyObject`.
- `FreeCAD.getDocument(name).getObject(name)` to resolve selection callbacks.
- `FreeCADGui.Selection.getSelectionEx(...)` to count selected elements.
- `FreeCADGui.Control.activeDialog()` to detect an open task dialog.
- `FreeCADGui.activeWorkbench().name()` compared with `JellyJamsWorkbench`.
- `Document.HasPendingTransaction`.
- Sketch first (§2.6): `FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")`
  (the active body, `constants.ACTIVE_BODY_KEY`), the document's `PartDesign::Body`
  objects (the lone-body fallback), `Body.hasObject(obj)`, `Body.Group`, `Body.Tip`,
  `isDerivedFrom("PartDesign::Feature")` of each object in `Body.Group` (something to cut,
  as FreeCAD's `Body::isSolid()`), the document's
  `Objects`, each 2D object's `InList`, `Shape.isNull()` and `Shape.Wires`, the sketch's
  `Geometry`; for the selection, `isDerivedFrom` with `App::Plane` / `PartDesign::Plane`
  (planes), `PartDesign::Body`, `App::Origin`, `App::Part`, `App::DocumentObjectGroup`
  (containers) and `PartDesign::Feature` (the insert point), and
  `Shape.getElement(sub).findPlane()`. A container-only selection is cleared with
  `FreeCADGui.Selection.clearSelection()`. The menu text of Hole Wizard's command
  (`getInfo()["menuText"]`, `&` removed) names it in the refusal without a solid.
- Feature-edit guard (§2.7): the code object file names of the frame that called the
  wrapper and of the frames above it (`FRAME_SEARCH_DEPTH`, 6, in all), and
  `FreeCADGui.ActiveDocument.getInEdit().Object` (`Document.Name`, `Name`).

**Document data changed (normal FreeCAD data, saved as usual)**

- Centerline: `SketchObject.setConstruction(i, True)` on new line segments.
- Midpoint Line: `SketchObject.addGeometry(Part.LineSegment(...), construction)`,
  `SketchObject.addConstraint(Sketcher.Constraint("Coincident", …))`,
  `SketchObject.addConstraint(Sketcher.Constraint("Symmetric", …))`, `SketchObject.solve()`.
- Transactions: `Document.openTransaction("Centerline")` /
  `openTransaction("Midpoint Line")` and `commitTransaction()`, used only when no
  transaction is pending.
- No custom (JellyJams-specific) properties are added to any document object by this
  area.

**FreeCAD commands run**

`Sketcher_LeaveSketch`, `Sketcher_CreateLine`, `PartDesign_NewSketch` (context icon and
sketch first, `constants.NEW_SKETCH_COMMAND`), and the profile feature ids in §2.2.
Selection is changed through `FreeCADGui.Selection.clearSelection()` and
`FreeCADGui.Selection.addSelection(sketch)`. A workbench switch held by §2.7 is made
later through FreeCAD's original `FreeCADGui.activateWorkbench(name)`.

**JellyJams public identifiers defined by this area**

- Command ids: `JellyJams_Centerline`, `JellyJams_MidpointLine`. They are registered with
  `FreeCADGui.addCommand` when the workbench initializes; registration is owned by the
  commands/workbench area.
- Qt objectName: `JellyJamsContextToolbar`.
- Parameter key: `ShowSketchButtonOnFace` in `Mod/JellyJams`.
- Undo transaction names: `Centerline`, `Midpoint Line`.

---

## 5. Persistence and restore rules

- **Drawing aids:** 2.8 defines the persisted snapping backup and temporary
  `Autoconstraints` override. No document properties are added.
  The sketch-edit interception, the feature-edit guard, the sketch-first
  state, the selection listener, the floating icon and the line-tool modes all live in
  memory only. (The Part Design `SwitchToWB` override is persisted with a backup by the
  assembly area, [assembly.md](assembly.md) 5.)
- **Exact restore on leave:** after `Deactivated()`:
  - `Show.mTempoVis.TempoVis.activateWorkbench` is the identical original object (unless
    another add-on wrapped it later; see §2.1);
  - `FreeCADGui.activateWorkbench` is the identical original object (unless another
    add-on wrapped it later; see §2.7);
  - no sketch-first is pending after its next check;
  - the selection listener is unregistered;
  - the icon is hidden;
  - no Centerline / Midpoint Line mode is running;
  - no JellyJams event filter remains on `QApplication`.
  - original snapping preferences and per-sketch auto constraints are restored;
    the recovery-save filter, edit poll and save observers are removed.
- **Crash recovery:** restore `OriginalSketchSnapping` as defined in 2.8. Other
  hooks lose their in-memory state, and a fresh FreeCAD start begins with FreeCAD's
  original TempoVis behavior. User files are never
  altered in a way that depends on JellyJams. Sketches keep `EditingWorkbench =
  SketcherWorkbench` (or whatever the user had), and centerlines and midpoint lines are
  ordinary construction flags, geometry and constraints.
- **File compatibility:** documents edited with these features open unchanged in plain
  FreeCAD.

---

## 6. Edge cases and failure handling

Each feature is isolated. A failure in one MUST NOT stop the rest of JellyJams from
activating or deactivating; the workbench lifecycle guards each step.

| Situation | Required handling |
|---|---|
| The `Show` module (TempoVis) cannot be imported | Report-view **warning** that the sketch workbench switch cannot be intercepted. JellyJams continues; sketches then switch to the Sketcher as in plain FreeCAD. Uninstall is then a no-op. |
| Interception installed twice | No double wrapping (§2.1). |
| Another add-on wrapped TempoVis after JellyJams | Do not clobber it on uninstall (§2.1). |
| A sketch is in edit while the user switches away from JellyJams | Nothing special. No switch was recorded, so closing the sketch later does not switch workbenches. A sketch opened in another workbench and closed inside JellyJams follows FreeCAD's own TempoVis restore. |
| `Sketcher_LeaveSketch` raises during the gesture | Report-view **warning**. Fall back to running the clicked command normally (no deferred start). |
| Selecting the sketch fails during the gesture | Report-view **warning**. Still run the feature command. |
| The feature command raises | Report-view **error** naming the command. |
| User clicks the profile button again while the deferred start is pending | SHOULD NOT start the feature twice. A second click after the sketch is already closed is an ordinary run. |
| Sketch first: `PartDesign_NewSketch` fails | Report-view **error** from the command runner. No sketch-first state is kept; the feature runs the ordinary way. |
| Sketch first: plane picker cancelled | Dropped quietly; no feature, status hint cleared. |
| Sketch first: the user opens a different sketch instead of drawing | Dropped quietly. |
| Sketch first: the new sketch is exited empty | No feature starts. |
| Sketch first: JellyJams left or the document closed while pending | Dropped with a log-level message. |
| Sketch first: an error inside a check | Log-level message; the sketch-first is dropped and its status hint cleared. |
| Sketch first: the new body is still selected after the ribbon's Body button | Containers only: the selection is cleared and the press continues as with nothing selected. |
| Sketch first: Extruded Cut or Revolved Cut in an empty target body (or one with only sketches and planes) | No sketch-first; FreeCAD's own message appears at once. |
| Sketch first: Hole Wizard in an empty target body (or one with only sketches and planes) | No sketch-first and nothing runs; JellyJams' status text for 6 s and a Report-view **warning** (§2.6, refusal without a solid). |
| Sketch first: Extruded Cut, Revolved Cut or Hole Wizard with several bodies and none active, with or without solids | No sketch-first, no JellyJams text or warning: FreeCAD handles the press and asks which body to work in (§2.6 rule 4). A press while a sketch-first picks its plane is retargeted. |
| Sketch first: a Pad whose shape is not computed yet (or failed) is in the body | The body holds a solid by FreeCAD's rule: cutting features start a sketch-first as usual. |
| Sketch first: a body rolled back before a feature, with unused sketches after it | Those sketches are not free (they are after the insert point); a new sketch starts if no other free sketch exists. |
| Sketch first: one body, not active | It is the target body: only its sketches count as free. |
| Sketch first: plane picker cancelled and a profile feature pressed before the next check | The stale sketch-first is dropped and the press is handled fresh. The dropped one's queued check finds it is no longer pending and stops. |
| Sketch first: plane picker open in a body without a solid, then Extruded Cut or Revolved Cut pressed | Not retargeted: the press goes to FreeCAD unchanged, and the waiting sketch-first keeps its feature and status hint. |
| Sketch first: plane picker open in a body without a solid, then Hole Wizard pressed | Not retargeted and nothing runs: JellyJams' status text replaces the hint for 6 s, with a Report-view **warning**. The plane picker stays open and the waiting sketch-first keeps its feature. |
| Feature-edit guard: `FreeCADGui.activateWorkbench` missing | Nothing is wrapped; Part Design feature edits then switch workbenches as in plain FreeCAD. |
| Feature-edit guard: the held switch raises | Report-view **warning** naming the workbench. JellyJams stays active. |
| Another add-on wrapped `FreeCADGui.activateWorkbench` after JellyJams | Do not clobber it on uninstall; the disarmed JellyJams wrapper passes everything through. Entering JellyJams again re-arms the wrapper in place and never wraps the other add-on's wrapper, so no call recurses (§2.7). FreeCAD's command strings are still recognized through up to five such wrappers. |
| The user picks a workbench while a feature or sketch is already in edit | The object in edit did not change, so the switch happens. |
| Selection listener cannot be registered | Report-view **warning** that the "Sketch" context icon is unavailable. The rest of JellyJams works. |
| Exception while evaluating a selection for the icon | Log-level message only (not shown by default). The icon stays hidden. |
| `PartDesign_NewSketch` fails from the icon | Report-view **error** that the sketch could not be created. |
| Selection callback arrives for a deleted/unknown object | Icon hidden. No message. |
| Planarity cannot be evaluated | Treat as not planar (icon hidden). |
| Icon shown and the user starts a feature dialog | The icon hides on the next check (task dialog open). |
| Multi-monitor / scaled displays | Position and distance use global screen coordinates of the pointer and icon. |
| Centerline/Midpoint activated with no sketch in edit | No-op (the command is greyed out anyway). |
| Exception while converting or mirroring | Report-view **warning**. The mode ends immediately. Already-made changes stay. |
| The user deletes or undoes lines during Midpoint Line | Continue from the current geometry count (§2.5). Never mirror pre-existing lines. |
| The user draws a line by keyboard shortcut with a mode still running | It is processed like any line drawn in that sketch (accepted limitation). |
| A rolled-back centerline conversion | Re-converted while the mode runs (§2.4). |
| Zero-length line in Midpoint Line | No partner. |
| A sketch in a different (non-active) document | Not considered. Only the active GUI document's in-edit sketch counts. |
| Sheet sketch (drawing area) | Centerline and Midpoint Line work in it like in any sketch. |

---

## 7. Acceptance criteria

Setup for all criteria:

- FreeCAD 1.1.x with JellyJams installed, started with Part Design as the startup
  workbench.
- In the Python console, before entering JellyJams for the first time, run
  `import Show.mTempoVis as M; ORIG = M.TempoVis.activateWorkbench; ORIG_WB = Gui.activateWorkbench`.
- Test part: a new document with a PartDesign Body. Sketch1 on the XY plane holds a
  closed rectangle 30 × 20, padded 10 mm (Pad). Sketch2 holds a circle of Ø10, padded
  to a cylinder (giving a cylindrical face).
- Then switch to JellyJams.

**Sketch editing stays in JellyJams**

1. In JellyJams, double-click Sketch1 in the tree. The sketch opens in edit mode. The
   workbench selector still shows "JellyJams", the `JellyJamsCommandManager` dock is still visible,
   and no Sketcher workbench toolbars appear. `Gui.activeWorkbench().name()` returns
   `JellyJamsWorkbench`.
2. Close the sketch with the ribbon's "Exit Sketch". The workbench is still JellyJams
   and no workbench switch occurs.
3. Switch to Part Design and double-click Sketch1. FreeCAD switches to the Sketcher
   workbench. Close the sketch and FreeCAD returns to Part Design.
4. While still in Part Design, `M.TempoVis.activateWorkbench is ORIG` returns `True`.
5. Enter and leave JellyJams three times, then check again: `M.TempoVis.activateWorkbench
   is ORIG` returns `True` after leaving. Inside JellyJams, opening a sketch still does
   not switch workbenches. In Part Design, opening a sketch switches to the Sketcher
   exactly once and returns on close.
6. After the steps above, `Sketch1.ViewObject.EditingWorkbench` is still
   `SketcherWorkbench`. Saving and reopening the file shows the same value.

**Feature from the open sketch**

7. In JellyJams, create a new sketch on a free plane, draw a closed rectangle, and,
   while still in the sketch, click "Extruded Boss/Base" on the Features tab. The
   sketch closes, and the Pad task panel opens with that sketch as profile. After OK,
   the new feature's `Profile` references that sketch. No error appears in the Report
   view.
8. Repeat 7 with "Extruded Cut" (sketch drawn on the pad's top face). The sketch closes
   and the Pocket dialog opens with that sketch as profile.
9. Repeat 7 using the "Swept Boss/Base" or "Helical Boss/Base" entries in the stacked rows, and
   "Lofted Cut" from the stack. Each closes the sketch and starts its feature with the
   sketch preselected. Any feature-specific prompts come from FreeCAD.
10. With a sketch in edit, click "Fillet". JellyJams does not run Exit Sketch. The
    result is identical to running `Gui.runCommand('PartDesign_Fillet')` from the
    console in the same state.
11. With no sketch in edit, select Sketch1 in the tree and click "Extruded Boss/Base".
    FreeCAD's normal Pad behavior with a preselected sketch occurs, and no Exit Sketch
    is issued (`Sketcher_LeaveSketch` is not run).

**Create-sketch context icon**

12. In JellyJams, click the planar top face of the rectangular pad. Right after the
    click, a small framed button appears with its top-left corner 16 px right of and
    40 px above the click point. It shows FreeCAD's New Sketch icon and the tooltip
    "Sketch". `Gui.getMainWindow().findChild(QtWidgets.QWidget, "JellyJamsContextToolbar")`
    returns it, and it is visible.
13. While the icon is visible, `QApplication.activeWindow()` is still FreeCAD's main
    window, so the icon did not take focus.
14. Move the pointer slowly away from the icon. Within 50 px it stays fully opaque.
    Between 50 and 180 px it becomes progressively transparent, at about half opacity
    near 115 px. At 180 px or more it disappears. Moving back toward its former place
    does not bring it back.
15. Click the face again and click the icon. The icon disappears, a new sketch attached
    to that face opens in edit mode, and the workbench is still JellyJams.
16. No icon appears when clicking any of the following:
    - the cylindrical face;
    - an edge;
    - a vertex;
    - the Body or Pad in the tree;
    - a second planar face with Ctrl held (an already visible icon hides);
    - a face while the Pad edit dialog is open;
    - a face while a sketch is in edit.
17. Insert the part into an assembly (Assembly workbench / JellyJams Assembly tab) and
    click a planar face of the part inside the assembly. No icon appears.
18. Run `App.ParamGet("User parameter:BaseApp/Preferences/Mod/JellyJams").SetBool("ShowSketchButtonOnFace", False)`
    and click a planar face: no icon. Run `RemBool("ShowSketchButtonOnFace")` and click again:
    the icon appears, with no restart needed.
19. With the icon visible, click empty space. The icon hides.
20. With the icon visible, switch to Part Design. The icon is hidden. Clicking planar
    faces in Part Design never shows it.

**Centerline**

21. `Gui.Command.get("JellyJams_Centerline")` exists, and its `getInfo()["menuText"]` is
    "Centerline". Outside sketch edit the ribbon button is greyed out
    (`Gui.Command.get("JellyJams_Centerline").isActive()` is False). Inside sketch edit it is
    enabled.
22. Open a sketch that already has one normal line. Choose Centerline from the Sketch
    tab's Line flyout. FreeCAD's line tool starts, with the same cursor and helpers as
    the flyout's "Line". Draw two lines. Within about 0.3 s of each line being completed, and
    without further input, it is shown as construction geometry
    (`sketch.getConstruction(i)` is True for both). The pre-existing line remains
    normal.
23. The conversion can be undone with Edit › Undo, either as an entry named
    "Centerline" or as part of FreeCAD's pending sketch transaction. After all steps,
    no transaction opened by JellyJams is left open, and the Report view has no
    JellyJams warnings.
24. Press Esc. FreeCAD's line tool ends. Then start "Line" and draw a line. It
    stays normal (not construction).
25. Start Centerline again, draw a line, and right-click. The line is construction and
    the mode has ended: a line drawn next with "Line" stays normal.
26. Start Centerline, draw a line, and immediately click "Circle" on the ribbon. The
    line drawn just before is construction. The circle and any lines drawn afterwards
    with Line are normal.
27. Start Centerline, exit the sketch, open another sketch, and draw with "Line".
    The lines are normal, and no geometry in the first sketch changed after it
    was closed.
28. Start Centerline in a sketch, then switch the workbench to Part Design while the
    sketch is open. Drawing lines with the Sketcher's line tool there produces normal
    lines, because the mode ended on deactivation.

**Midpoint Line**

29. `Gui.Command.get("JellyJams_MidpointLine")` exists, its menuText is "Midpoint Line", and it
    is enabled only in sketch edit.
30. In a sketch, choose Midpoint Line. Click at (10, 5), then at (40, 25), using the
    on-view input or snapping to a grid. The sketch now contains the drawn line plus a
    partner from (10, 5) to (−20, −15). Both are normal geometry. Two new constraints
    exist: `Coincident` (partner start ↔ drawn start) and `Symmetric` (drawn end,
    partner end, about drawn start).
31. Drag the end at (40, 25). The opposite end moves symmetrically, and the two halves
    stay collinear and of equal length.
32. Draw a second midpoint line. Exactly one partner is created per drawn line; the
    partners are never mirrored themselves.
33. Turn on construction mode (`Sketcher_ToggleConstruction` with nothing selected),
    then draw a midpoint line. Both halves are construction geometry.
34. Draw a midpoint line and use Undo until it is gone. Then draw another midpoint line.
    A correct partner with correct constraints is created, no pre-existing line gains a
    partner, and there are no errors.
35. Draw a midpoint line and immediately click "Centerline" on the ribbon. The last
    midpoint line still has its partner. Lines drawn now become construction and get no
    partner.
36. Press Esc (or right-click) to end Midpoint Line, then draw with "Line". No
    partner is created. Leaving the sketch while Midpoint Line runs also ends it.

**No persistence / no file changes**

37. After running all of the above, the parameter group
    `User parameter:BaseApp/Preferences/Mod/JellyJams` contains no key created by this
    area (`ShowSketchButtonOnFace` exists only if the tester set it).
38. For each sketch used, `PropertiesList` (object and view provider) is the same set
    as before editing in JellyJams. No JellyJams-specific properties were added.
39. Quit FreeCAD while JellyJams is active with a Centerline mode running, then restart
    with Part Design as the startup workbench. Opening a sketch in Part Design switches
    to the Sketcher normally, and `M.TempoVis.activateWorkbench` is FreeCAD's original
    (a fresh session).

**Sketch first** (each in a new document with one active Body and no sketch, unless
stated otherwise; `tests/gui_sketch_first.py` checks 40 to 42 and 44 in a real FreeCAD
window, all but the status-bar text; `Test23SketchFirstFlow` covers 40 to 47 with a fake
document)

40. Select nothing and click "Extruded Boss/Base". No "No sketch to work on" warning
    appears. FreeCAD's plane picker opens in the task panel, and the status bar starts
    with "New sketch for".
41. Continuing from 40, cancel the plane picker. No sketch and no Pad are created, and
    about 1.5 s later nothing is pending: clicking "Extruded Boss/Base" again behaves as
    in 40.
42. Select the Top Plane in the tree and click "Extruded Boss/Base". A sketch attached
    to that plane opens at once, with no warning. Draw a closed rectangle and click "Exit
    Sketch". The Pad task panel opens with the new sketch as its `Profile`, JellyJams is
    still the active workbench, and after OK it still is.
43. Select the planar top face of a pad and click "Extruded Cut". A sketch opens on that
    face. Draw a circle inside it and exit: the Pocket task panel opens with that sketch
    as its profile.
44. With a finished, unused sketch in the body and nothing selected, click "Extruded
    Boss/Base". No new sketch is created; the Pad uses the existing sketch.
45. With nothing selected, click "Extruded Boss/Base", then, while the plane picker is
    open, click "Extruded Cut". Only one sketch is created. Pick a plane, draw a closed
    profile and exit: a Pocket is created, no Pad.
46. Click "Extruded Boss/Base" with nothing selected, pick a plane, and exit the new
    sketch without drawing. No feature dialog opens.
47. Click "Swept Boss/Base" with nothing selected and no sketch. JellyJams does not open
    a sketch; FreeCAD's own behavior follows.

**Feature editing stays in JellyJams** (`tests/gui_sketch_first.py` checks 48 and 49;
`Test23EditGuard` and `Test06Lifecycle` cover the guard's rules and its restore)

48. Double-click a Pad in the tree. Its task panel opens and `Gui.activeWorkbench().name()`
    is still `JellyJamsWorkbench`. After OK it still is.
49. Choose Part Design in the workbench selector (or View > Workbench). FreeCAD switches
    to Part Design.
50. Back in JellyJams, run `Gui.activateWorkbench("PartWorkbench")` in the Python console:
    the switch happens at once. After leaving JellyJams, `Gui.activateWorkbench is
    ORIG_WB` returns `True`, and double-clicking a Pad from the Part workbench switches to
    Part Design as in plain FreeCAD.

**Sketch first: selection, solids, stale presses and bodies** (`Test23SketchFirstFlow` covers
51 to 57 and 59 with a fake document; none is run in a real FreeCAD window yet)

51. Click **Body** on the Features tab (the new body stays selected), then "Extruded
    Boss/Base". The selection is cleared and FreeCAD's plane picker opens; no "No sketch to
    work on" warning appears. The same holds with only the body's Origin, a Part or a group
    selected.
52. In a new body without any solid (also with a datum plane or a sketch in it), select
    nothing and click "Extruded Cut" or "Revolved Cut". No sketch is created and FreeCAD's own
    message appears at once. Click "Hole Wizard": no sketch is created, no Hole is made, and
    the status bar reads "Hole needs a solid to cut into: create a boss or base feature
    first." for about 6 s, with the same text as a Report-view warning. After a Pad exists in
    the body, "Extruded Cut" and "Hole Wizard" open the plane picker.
53. Click "Extruded Boss/Base" with nothing selected, cancel the plane picker and, within
    1.5 s, click "Revolved Boss/Base": a new plane picker opens and the status bar names
    Revolved Boss/Base. Doing the same with "Swept Boss/Base" instead runs FreeCAD's sweep
    command and leaves the status bar empty.
54. With the plane picker of 40 open, click "Swept Boss/Base": the press goes to FreeCAD,
    the picker stays open, and exiting the new sketch later starts the Pad.
55. With the plane picker of 40 open, click "Extruded Cut" in a body with a solid (a Pad in
    its tree): the status bar now reads "New sketch for Pocket…" (FreeCAD's menu text).
56. Roll a body back (Set Tip) to its Pad, before a Pocket whose own sketch is followed by
    an unused closed sketch; select nothing and click "Extruded Boss/Base": a new sketch
    starts instead of FreeCAD's "No sketch to work on" warning.
57. In a document with a single body that is not active and a closed sketch outside it,
    click "Extruded Boss/Base" with nothing selected: a new sketch starts.

**Feature-edit guard under another add-on** (`Test23EditGuard` covers 58 and 60)

58. Wrap `Gui.activateWorkbench` from the Python console after JellyJams was entered
    (`prev = Gui.activateWorkbench; Gui.activateWorkbench = lambda n, *a: prev(n, *a)`),
    leave and enter JellyJams three times, then choose Part Design in the workbench selector.
    The switch happens with no error and no recursion, and after leaving JellyJams
    `Gui.activateWorkbench` is still the console's wrapper.

**Sketch first: retarget without a solid** (`Test23SketchFirstFlow`)

59. In a new body without any solid, click "Extruded Boss/Base" with nothing selected and,
    while the plane picker is open, click "Extruded Cut": the status bar still names
    Extruded Boss/Base, no second sketch starts, and exiting the new sketch with a profile
    starts the Pad. The same with "Hole Wizard" instead of "Extruded Cut": the status bar
    reads "Hole needs a solid to cut into: create a boss or base feature first." with a
    Report-view warning, no Hole is made, the plane picker stays open, and exiting the new
    sketch with a profile still starts the Pad.

**Feature-edit guard under another add-on, feature edits** (`Test23EditGuard`)

60. With the console wrapper of 58 in place (one or two of them) and JellyJams active,
    double-click a Pad in the tree: its task panel opens and `Gui.activeWorkbench().name()`
    is still `JellyJamsWorkbench`.

**Sketch first: no target body** (`Test23SketchFirstFlow` covers 61 with a fake document;
`gui_orientation.py` has a GUI check for the Hole Wizard part)

61. In a document with two bodies, each with a Pad, and none active, select nothing and click
    "Extruded Cut", "Revolved Cut" or "Hole Wizard": no sketch is created, JellyJams shows no
    status-bar text and writes no warning, and FreeCAD handles the press as without JellyJams
    (FreeCAD 1.1.4 asks which body to work in with its "Active Body Required" dialog). The same
    with two empty bodies.

---

**Automatic snapping and constraints** (`tests/gui_sketch_assist.py`, `Test23SketchAssist`)

62. With snapping off and `Autoconstraints` false, enter a sketch: both snap
    switches and auto constraints are true, the native line tool connects to the
    origin and an existing endpoint with Coincident constraints, and another
    sketch's setting and grid snap remain unchanged.
63. Save during the edit: `GuiDocument.xml` contains the original false value;
    the live sketch resumes auto constraints. Exit and reenter: originals return,
    then aids are enabled again. Originally absent snap keys are removed on exit.
64. Leave JellyJams with a sketch open, or revert for quit: originals return and
    the backup disappears. Enter with the same sketch open, or resume after Cancel:
    aids work again. Abrupt termination during editing followed by startup restores
    preferences with the same absent/false/true distinction.
65. Deliver the native AutoSaver's registered timer during editing: its recovery
    file contains the original false `Autoconstraints`, and the live sketch resumes
    auto constraints after the event returns. The filter is gone on workbench leave.

**Smart Dimension preview placement** (`gui_smart_dimension.py`, `Test23SmartDimension`)

66. Draw horizontal and vertical lines, start Smart Dimension from the ribbon,
    and place their linear dimensions: the preview lines follow the pointer
    within one logical screen pixel. Repeated moves do not accumulate an offset.
67. Confirm a dimension, then create another in the same tool session; the first
    label stays fixed. Escape cancels the second preview without moving the first;
    the next preview still follows the pointer. Native values remain unchanged
    when the dialog is accepted without editing them.
68. Starting another ribbon tool or leaving JellyJams removes the preview filter.
    Existing label positions survive. Normal native Dimension invocation outside
    the ribbon is unaffected; radius, angle and arc-length previews remain native.

**Single-click sketch-first plane choice** (`gui_plane_pick.py`)

69. In a fresh document, press Extruded Boss/Base and click XY, XZ or YZ once:
    exactly one sketch enters edit on that plane, still inside JellyJams.
    With no plane chosen, the picker stays open. Native double-click selection
    preferences remain unchanged, including an explicit false
    `Selection/singleClickFeatureSelect`. Cancel ends the intent without entering
    edit or starting an extrusion. Older native plane-list choices also need only
    one click during this sketch-first flow.

## 8. Boundaries with other areas

- **Workbench lifecycle:** calls this area's install on `Activated()` and uninstall on
  `Deactivated()`, guarding each step separately.
- **Commands/registration:** registers `JellyJams_Centerline` and `JellyJams_MidpointLine` during
  `Initialize()`.
- **Ribbon (`JellyJamsCommandManager`):** does the following:
  - routes every button click through one dispatch point that first ends running
    Centerline / Midpoint Line modes, then offers the click to `sketch_gesture.try_run`
    (the "feature from open sketch" gesture of §2.2 and the sketch-first start of §2.6);
  - hosts the Line flyout and the Sketch / Exit Sketch toggle;
  - switches to the Sketch tab on entering a sketch and back afterwards;
  - greys out buttons whose command `isActive()` is false;
  - preloads `SketcherGui` / `PartDesignGui` so the Sketcher commands exist even though
    the Sketcher workbench is never activated.
- **Icons:** new original SVGs for Centerline and Midpoint Line. FreeCAD's runtime icon
  is used for the context button. Nothing third-party is bundled.
- **Naming (SolidWorks tree names such as Sketch1, Boss-Extrude1):** not part of this
  area.
- **Workbench-switch preferences (assembly area, [assembly.md](assembly.md) 5):** holds
  `Mod/PartDesign` `SwitchToWB` at false while JellyJams is active. Without it, leaving
  the new sketch of §2.6 (which makes the body active again) would switch to Part Design
  before the feature starts.
