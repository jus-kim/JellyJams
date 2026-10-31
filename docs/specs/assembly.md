# JellyJams specification: Assembly

> **Implemented in:** [`jellyjams/mate_rules.py`](../../jellyjams/mate_rules.py) (pure entity-kind, offer and hint rules), [`mate_panel.py`](../../jellyjams/mate_panel.py) (Add Mate panel), [`panel_host.py`](../../jellyjams/panel_host.py) (task-panel hosting, shared with Add Relations), [`assembly_drop.py`](../../jellyjams/assembly_drop.py) (drag-and-drop insertion), [`switch_prefs.py`](../../jellyjams/switch_prefs.py) (the `SwitchToWB` overrides of Assembly, Part Design and TechDraw, restore and recovery), [`assembly_commands.py`](../../jellyjams/assembly_commands.py) (`JellyJams_NewAssembly`, `JellyJams_RotateComponent`); icons [`new_assembly.svg`](../../resources/icons/new_assembly.svg), [`rotate_component.svg`](../../resources/icons/rotate_component.svg).
>
> **Status:** see [../status.md](../status.md)

Area: **assembly**. Target: FreeCAD 1.1+, workbench `JellyJamsWorkbench` (MenuText "JellyJams"). English only.

This area covers five features that make FreeCAD's Assembly workbench (the FreeCAD 1.1 built-in "Assembly" module) feel like SolidWorks assemblies while the user stays inside JellyJams:

1. **Add Mate panel**: a context panel that turns the current selection into a short list of fitting SolidWorks-style mates. Each mate starts the matching FreeCAD Assembly joint command.
2. **Drag-and-drop insertion**: dropping `.FCStd` files from the operating-system file browser onto FreeCAD inserts them as components of the active assembly.
3. **Staying in JellyJams on assembly activation**: while JellyJams is active, FreeCAD's "switch to Assembly workbench" preference is turned off, with an exact three-state restore and crash recovery. The same is done for the matching preferences of Part Design (body activation, for example on leaving a sketch) and TechDraw (double-clicking a drawing page).
4. **New Assembly** command (`JellyJams_NewAssembly`): always creates the assembly in a new, separate document, like SolidWorks.
5. **Rotate Component** command (`JellyJams_RotateComponent`): free mouse rotation of one floating, unmated component about its own origin.

The terms MUST, SHOULD and MAY are used in their usual sense.

---

## 1. Purpose

SolidWorks users expect the following:

- Assemblies, parts and drawings are separate files. "New Assembly" never nests an assembly inside an open part.
- Picking two entities (faces, edges, points) on two components brings up a "Mate" property manager that offers only the mates that make sense for that pair.
- Dragging part files from the file explorer into the assembly window inserts them. The first component is fixed at the origin, and later components arrive floating and do not overlap earlier ones.
- Double-clicking or activating an assembly never takes the user out of the current environment. FreeCAD would normally switch to its own Assembly workbench, which would hide the JellyJams ribbon.
- A floating component can be spun freely with the mouse ("Rotate Component").

All of this works only while the JellyJams workbench is active. Outside JellyJams, FreeCAD behaves exactly as stock.

---

## 2. User-visible behavior and UI

### 2.1 Add Mate panel

**What appears.** A framed panel at the very top of FreeCAD's Tasks panel. The content area is the `Gui::TaskView::TaskPanel` widget inside the scroll area of the dock whose objectName is `Tasks`. FreeCAD's own task content stays below the panel. From top to bottom the panel contains:

| Element | Content |
|---|---|
| Title (bold) | `Add Mate` |
| Section heading | `Selected Entities` |
| List | One row per qualifying selected entity, in selection order. The list height fits its content: 1 to 6 rows are visible, then it scrolls. |
| Section heading | `Mates` |
| Mate buttons | A vertical column of full-width, flat (auto-raise) tool buttons, each showing an icon with the text beside it. Only the mates that fit the current selection appear, in the order defined in §2.1.4. |
| Hint label | A word-wrapped line that tells the user what to do next. It is hidden when there is nothing to say. |

**Styling contract.** The panel shares the look of the sketch "Add Relations" panel and uses the same Qt objectNames, so that the JellyJams theme stylesheet applies to both:

- panel frame (QFrame): `JellyJamsPropertyManager`
- title label: `JellyJamsPropertyManagerTitle`
- section headings: `JellyJamsSectionCaption`
- entity list (QListWidget): `JellyJamsItemList`

The theme area owns the styles. This area only has to set these objectNames.

#### 2.1.1 Entity rows

Each row is written as `<Kind> – <Component label>`, with an en dash and a space on each side. If the component cannot be determined, the row shows only `<Kind>`. The component label is the `Label` of the assembly component that holds the entity: the top-level child of the assembly, usually an `App::Link`, `Assembly::AssemblyLink` or `App::Part`.

The kind comes from the geometry of the selected sub-element:

| Selected sub-element | Kind text |
|---|---|
| Face whose surface is a plane (`Part.Plane`) | `Planar face` |
| Face whose surface is a cylinder | `Cylindrical face` |
| Face whose surface is a cone | `Conical face` |
| Face whose surface is a sphere | `Spherical face` |
| Any other face (B-spline, torus, ...) | `Face` |
| Edge whose curve is a line or line segment | `Linear edge` |
| Edge whose curve is a circle, including circular arcs | `Circular edge` |
| Any other edge (ellipse, B-spline, ...) | `Edge` |
| Vertex | `Point` |
| Whole object (selection path ends at an object and names no sub-element), or geometry that cannot be determined | `Component` |

#### 2.1.2 Which selection entries count

- The selection is read across all documents with full paths from the document root, i.e. FreeCAD's `Selection.getSelectionEx("*", 0)`.
- Each selected sub-element path is one candidate entity.
- An entity counts only if FreeCAD's Assembly helper `UtilsAssembly.getComponentReference(assembly, root_object, sub_path)` resolves it to a component of the currently active assembly. Entities outside the active assembly are silently left out. Examples are a selection in another document, or a path that does not pass through the active assembly. Selection entries whose root object belongs to another document than the assembly, has been deleted or cannot be read are skipped before the helper is asked.
- A selection entry that has no sub-element names contributes nothing.
- If the Assembly helper module cannot be imported, entities are still listed, but without a component. The same-component check below then cannot apply.

#### 2.1.3 Mate catalogue (SolidWorks label → FreeCAD command)

The table order is the catalogue order used to break ties in §2.1.4.

| Mate (button text) | FreeCAD command run on click |
|---|---|
| `Hinge` | `Assembly_CreateJointRevolute` |
| `Slider` | `Assembly_CreateJointSlider` |
| `Concentric` | `Assembly_CreateJointCylindrical` |
| `Ball Joint` | `Assembly_CreateJointBall` |
| `Coincident` | `Assembly_CreateJointDistance`, left at its default value 0 |
| `Tangent` | `Assembly_CreateJointDistance`, left at its default value 0. For round references FreeCAD adds the radii to the value, so 0 means the surfaces touch. FreeCAD's own tooltip for the command names the plane + cylinder case a tangent joint. |
| `Parallel` | `Assembly_CreateJointParallel` |
| `Perpendicular` | `Assembly_CreateJointPerpendicular` |
| `Angle` | `Assembly_CreateJointAngle` |
| `Distance…` (ends in U+2026, the ellipsis, because FreeCAD's dialog then asks for the value) | `Assembly_CreateJointDistance` |

Button icon and tooltip:

- **Icon**: FreeCAD's own icon for the mapped command, resolved at runtime. Use the command's QAction icon or the icon named by the command's `Pixmap`, via `FreeCADGui.Command.get(id).getInfo()` / `FreeCADGui.getIcon`. JellyJams bundles no mate icons that copy third-party art. If no icon can be resolved, the button shows its text only.
- **Tooltip**: the FreeCAD command's own tooltip. If FreeCAD gives none, the button text is used.

#### 2.1.4 Offered mates (capability matrix)

Mates are offered only when **exactly two** entities count and they sit on different components. Every mate declares the unordered pairs of entity kinds it accepts, and for each pair how many of the six degrees of freedom its FreeCAD joint removes. The panel lists every mate that accepts the selected pair, sorted by that number from highest to lowest, so the most constraining mate comes first. Mates with equal numbers keep the catalogue order of §2.1.3.

**Basis.** FreeCAD 1.1 turns each joint reference into a joint coordinate system (JCS) with `UtilsAssembly.findPlacement`:

- vertex: origin at the point, no usable direction;
- linear edge: Z along the line;
- circular edge: Z on the circle's axis, origin at its centre;
- planar face: Z along the normal;
- cylindrical face: Z on the axis, origin on the axis;
- conical face: Z on the axis, origin at the apex;
- spherical face: origin at the centre, no usable direction;
- any other face or edge: no dependable direction or centre.

The Revolute, Slider, Cylindrical, Ball, Parallel, Perpendicular and Angle joints act on the two JCSs only. The Distance joint first classifies the geometry pair (`getDistanceType`, `AssemblyUtils.cpp`) and has a dedicated solver joint for twenty classes (`makeMbdJointDistance`, `AssemblyObject.cpp`). Every other class falls back to a plain planar joint between the JCSs. JellyJams relies on that fallback in one case only: circular edge + planar face, where it lays the circle's plane onto the face.

Abbreviations: Pt Point, Ln Linear edge, Ci Circular edge, Pl Planar face, Cy Cylindrical face, Co Conical face, Sp Spherical face. "{A, B} × {C, D}" means one kind from each set, in either order. The number in brackets is the count of removed degrees of freedom.

| Mate | Accepted pairs | Basis |
|---|---|---|
| Hinge | {Cy, Ci} × {Cy, Ci} (5) | Revolute joins both axes and both origins. A cone's origin is its apex, so cones are left out. |
| Slider | {Ln, Cy} × {Ln, Cy} (5) | Slider needs a straight line of travel on both sides. |
| Concentric | {Cy, Co, Ci} × {Cy, Co, Ci, Ln} (4) | Cylindrical makes the axes collinear. Two linear edges belong to Coincident. |
| Ball Joint | Sp × Sp, Sp × Pt (3) | Ball joins two centres. FreeCAD already solves two points at distance 0 as a ball joint, so Pt × Pt is left to Coincident. |
| Coincident | Ln × Ln (4); Pt × Pt, Pl × Pl, Ci × Pl (3); Pt × Ln, Ln × Pl (2); Pt × Pl, Pt × Cy, Pt × Sp (1) | Distance classes in which 0 puts one element on the other. |
| Tangent | Cy × Cy (3); Pl × Cy (2); Pl × Sp, Cy × Sp, Sp × Sp (1) | Distance classes that add the radii, so 0 means contact. |
| Parallel | Pl × Pl, or {Ln, Ci, Cy, Co} × {Ln, Ci, Cy, Co} (2) | See "Directions" below. |
| Perpendicular | same pairs as Parallel (1) | |
| Angle | same pairs as Parallel (1) | |
| Distance… | Ln × Ln, Ln × Ci, Ci × Ci, Ci × Pl, Pl × Pl, Cy × Cy (3); Ln × Pl, Pl × Cy (2); Pt × Pt, Pt × Ln, Pt × Pl, Pt × Cy, Pt × Sp, Pl × Sp, Cy × Sp, Sp × Sp (1) | Every pair of these kinds with a dedicated Distance solver joint, counted for a non-zero value. |

**Directions.** Parallel, Perpendicular and Angle compare the Z axes of the two JCSs. A planar face puts its normal there, whereas edges and turned faces put their own direction there. For a plane paired with a line or an axis, FreeCAD's Parallel would leave the line standing normal to the plane, which is the opposite of what a SolidWorks user means by a parallel line and plane. These three mates are therefore offered only when both entities supply the same sort of direction: two planar faces, or two of Ln, Ci, Cy, Co.

**Pairs with no mate.** Any pair that includes `Component`, `Face` or `Edge` gets no mate. So do Pt × Ci, Pt × Co, Ln × Sp, Ci × Sp, Pl × Co and Co × Sp. The hint of §2.1.5 then says that nothing fits.

**Same component.** If both entities belong to the same component, no mates are offered, whatever the kinds. FreeCAD rejects joints within one component.

Resulting button rows for frequent pairs (informative):

| Pair | Buttons, in order |
|---|---|
| Pl + Pl | Coincident, Distance…, Parallel, Perpendicular, Angle |
| Cy + Cy | Hinge, Slider, Concentric, Tangent, Distance…, Parallel, Perpendicular, Angle |
| Ci + Ci | Hinge, Concentric, Distance…, Parallel, Perpendicular, Angle |
| Ci + Cy | Hinge, Concentric, Parallel, Perpendicular, Angle |
| Ln + Cy | Slider, Concentric, Parallel, Perpendicular, Angle |
| Ln + Ln | Slider, Coincident, Distance…, Parallel, Perpendicular, Angle |
| Pl + Cy, Pl + Sp, Cy + Sp | Tangent, Distance… |
| Pt + Sp | Ball Joint, Coincident, Distance… |
| Sp + Sp | Ball Joint, Tangent, Distance… |
| Pt + Pt, Pt + Ln, Pt + Pl, Pt + Cy, Ln + Pl, Ci + Pl | Coincident, Distance… |

#### 2.1.5 Hint line (requirements; the wording is free)

The hint exists to explain why no mate button is on offer. It reports one obstacle at a time; when several conditions hold, the row with the lowest priority number wins.

| Priority | Selection state | What the hint must get across |
|---|---|---|
| 1 | One counted entity | A second entity is still missing, and it has to sit on a different component. |
| 2 | Three or more counted entities | The selection must come down to exactly two entities. |
| 3 | Two entities, one component | The obstacle is that both lie on the same component; the second entity has to come from another one. |
| 4 | Two entities on different components, but §2.1.4 offers nothing | This particular pair has no fitting mate. |

In every other state the panel shows at least one button, nothing needs explaining, and the label is hidden.

#### 2.1.6 When the panel is visible

The panel is visible only when **all** of these hold:

- the JellyJams workbench is active (the feature is installed);
- an assembly is active, meaning FreeCAD's `UtilsAssembly.activeAssembly()` returns an object. That only happens while the assembly is in edit mode;
- no task dialog is open (`FreeCADGui.Control.activeDialog()` is false). While FreeCAD's own joint dialog, or any other task dialog, is open, FreeCAD's dialog has the Tasks panel to itself;
- at least one entity counts (§2.1.2);
- FreeCAD's Tasks content panel exists. If it cannot be found, nothing is shown, and no fallback dock is created.

In every other case the panel is hidden. Hiding keeps the widget for reuse. If FreeCAD has destroyed the hosting widget, a new panel is built and inserted at the top again.

#### 2.1.7 Clicking a mate

A click runs the mapped FreeCAD command with no extra arguments (`FreeCADGui.runCommand(id)`). In FreeCAD 1.1 the joint task picks up the two pre-selected entities itself. The user then confirms with OK in FreeCAD's dialog, or enters a value (Distance, Angle). The joint is created by FreeCAD in the assembly's `Assembly::JointGroup`. While the dialog is open the Add Mate panel is not visible. If the command fails to start, an error line prefixed `JellyJams: ` is written to the Report view and nothing else happens.

### 2.2 Drag-and-drop of `.FCStd` files into the active assembly

**What the user does.** The user drags one or more `.FCStd` files from the OS file explorer onto any part of the FreeCAD main window while JellyJams is active and a target assembly exists (§3.3).

**What the user sees.**

- While dragging over FreeCAD, the cursor shows "drop allowed".
- After dropping:
  - each file's primary object (§3.4) appears as a new component under the assembly in the tree;
  - the first component of an assembly that has no fixed component yet is fixed: FreeCAD shows a grounded joint for it;
  - later components appear 20 mm to the right of everything already in the assembly, so nothing overlaps;
  - the assembly is active (edit mode), so components can be dragged with the mouse at once;
  - the source files are opened hidden, as FreeCAD's "Insert Component" does: no extra document tabs or windows;
  - a Report-view message prefixed `JellyJams: ` states how many components were inserted and their labels.
- The whole drop is **one** undo step named `Insert Component`.
- If the assembly document has never been saved, a Save As dialog appears first. Its title says the assembly must be saved because references need a file location. Its filter is "FreeCAD file (*.FCStd)". The suggested path is the folder of the first dropped file plus the assembly document's Label (or its Name, or `Assembly` as a last resort) plus `.FCStd`. If the user types no extension, `.FCStd` is appended. If the user cancels, or the save does not give the document a file name, nothing is inserted and a Report-view warning says the assembly must be saved first.

**When JellyJams does not intercept.** In each of these cases FreeCAD's normal handling applies, i.e. it opens or imports the file:

- the JellyJams workbench is not active;
- the dragged data contains no local `.FCStd` file (matched case-insensitively, e.g. `.step`, `.png`, text);
- no target assembly can be determined (§3.3). On the actual drop a Report-view message says no unique assembly was found and FreeCAD handles the file as usual.

**Mixed drops.** If a drop contains `.FCStd` files and other files while a target exists, only the `.FCStd` files are inserted. The others are ignored, because the event has been consumed.

### 2.3 Staying in JellyJams when an assembly is activated

FreeCAD's Assembly module has a Boolean preference `SwitchToWB` in the group `User parameter:BaseApp/Preferences/Mod/Assembly`. FreeCAD treats an absent key as true. When the preference is true, double-clicking an assembly switches to FreeCAD's Assembly workbench, which would deactivate JellyJams and hide the ribbon.

While JellyJams is active, this preference MUST be false. As a result, double-clicking an assembly in the tree activates it in place: edit mode, ribbon moves to its "Assembly" tab, and the workbench stays `JellyJamsWorkbench`. Outside JellyJams the user's original setting is in force again, exactly (§5.1).

Two other FreeCAD modules have a Bool `SwitchToWB` with the same meaning (absent counts as true; verified on 1.1.4). JellyJams holds them at false too, with the same exact restore, each with its own backup record:

| Module | Preference group | Switches to its workbench when | Backup record in `Mod/JellyJams` |
|---|---|---|---|
| Assembly | `User parameter:BaseApp/Preferences/Mod/Assembly` | an assembly is activated (double-click) | `OriginalSwitchToWB` |
| Part Design | `User parameter:BaseApp/Preferences/Mod/PartDesign` | a body becomes active, including when a sketch is left (the sketch-first flow of [sketching.md](sketching.md) 2.6 relies on this) | `OriginalPartDesignSwitchToWB` |
| TechDraw | `User parameter:BaseApp/Preferences/Mod/TechDraw/General` | a drawing page is double-clicked | `OriginalTechDrawSwitchToWB` |

The Part Design feature dialogs switch workbench without any preference. That case is handled by the feature-edit guard of [sketching.md](sketching.md) 2.7, not here.

There is no UI for this behavior. It is automatic. The code is [`switch_prefs.py`](../../jellyjams/switch_prefs.py) (`TARGETS` lists the three modules).

### 2.4 New Assembly (`JellyJams_NewAssembly`)

| Resource | Value |
|---|---|
| Command id | `JellyJams_NewAssembly` |
| MenuText | `New Assembly` |
| ToolTip (intent; wording is free) | Conveys that a separate, otherwise empty assembly document is opened and that open parts are not modified, and names the two ways of adding components afterwards: dropping `.FCStd` files (§2.2) and FreeCAD's Insert Component. |
| Icon | A **new original icon** drawn for JellyJams that suggests a new assembly. The file name must not contain "SolidWorks". |
| Availability | Always enabled. It needs no open document. |

**Effect.**

1. A new document is created. Its Name and Label are both `AssemblyN`, where N is the smallest positive integer such that `AssemblyN` is neither the Name nor the Label of any open document. With documents `Part` and `Assembly1` open, the result is `Assembly2`.
2. The new document becomes the active App and Gui document.
3. Once FreeCAD has finished creating the document's 3D view (deferred to the next event-loop turn), FreeCAD's `Assembly_CreateAssembly` runs inside that new document. FreeCAD creates the `Assembly::AssemblyObject`, with its joint group, and activates it in edit mode.

The command MUST NOT run `Assembly_CreateAssembly` in the document that was active before, even when an `App::Part` is active there. Doing so would nest the assembly inside the part.

**Ribbon placement** (owned by the ribbon area, stated here for completeness): the "Assembly" tab uses `JellyJams_NewAssembly` (label "New Assembly", two lines) in place of `Assembly_CreateAssembly`.

### 2.5 Rotate Component (`JellyJams_RotateComponent`)

| Resource | Value |
|---|---|
| Command id | `JellyJams_RotateComponent` |
| MenuText | `Rotate Component` |
| ToolTip (base intent; wording is free) | Identifies the gesture (left-button drag in the 3D view) and states that the tool is limited to a single floating component without mates. |
| Icon | A **new original icon** drawn for JellyJams: a rotation symbol around a part. The file name must not contain "SolidWorks". |

**Availability (the command is enabled when):**

- the tool is currently running. The button stays clickable so that clicking it again ends the tool; or
- all of the following are true:
  - an assembly is active (edit mode);
  - exactly one component of that assembly is selected. Several sub-elements of the same component count as one. A component can be picked in the 3D view (any face, edge or vertex resolves to its component through `UtilsAssembly.getComponentReference`) or in the tree (a direct child of the assembly of type `App::Link` or `Assembly::AssemblyLink`, selected without a sub-element). Selections in other documents do not count;
  - the component is **not fixed**: no document object has an `ObjectToGround` property that points to it;
  - the component has **no mates**: no joint references it. A joint is a document object that has a `JointType` property and no `ObjectToGround` property. A joint references the component when its `Reference1` or `Reference2` names the component as the reference object, or when any of the reference's sub-paths contains the component's `Name` as a dot-separated segment.

**Reason in the ribbon tooltip.** Whenever the ribbon re-evaluates command availability, the tooltip of the ribbon's Rotate Component button is set to the base tooltip. When the command is disabled, a blank line and one reason follow. The reason reports the first availability rule above that fails, and it must leave the user knowing what to change:

| Failed rule | Requirements for the reason |
|---|---|
| An assembly is active | States that the tool needs an active assembly and points to activating one from the tree. |
| Exactly one component selected | Asks for a selection of a single component of the active assembly. |
| Not fixed | Quotes the component's label and identifies its fixed state as the obstacle. |
| No mates | Quotes the component's label and the label of one mate that holds it, and identifies that mate as the obstacle. |

The tooltip is updated only when the text changes. When the ribbon is rebuilt, the new button is given the current text again.

**Running the tool (when the user clicks the enabled command):**

- The availability rules are checked again. If they pass, the tool starts for the selected component. A Report-view message prefixed `JellyJams: ` names the component.
- The main-window status bar carries a persistent hint that names the tool, its drag gesture and the ways to end it (listed below). If the status bar becomes empty while the tool runs, the hint is shown again.
- A semi-transparent **axis cross** appears at the component's placement origin, oriented with the component's current rotation, and is drawn on top of all geometry:
  - X axis red, Y axis green, Z axis blue. Each axis runs symmetrically through the origin with a thick line (about 4 px).
  - A small light-grey sphere marks the pivot. Its radius is about 8% of the axis half-length.
  - The half-length is max(5 mm, 0.4 × the component's bounding-box diagonal). If the size cannot be determined, it is 20 mm.
  - Transparency is about 35%, so the cross stays clearly visible without hiding the part.
  - The cross turns with the component while rotating.
- FreeCAD's own mouse-drag movement of assembly parts is switched off for the duration by setting the active assembly's view property `EnableMovement` to false. Its previous value is remembered. FreeCAD's exploded-view tool does the same.
- **Left-button drag** in the 3D view rotates the component:
  - the left press and release are consumed, so FreeCAD neither selects nor moves anything;
  - mouse moves are consumed only while the left button is held. Without a drag, FreeCAD pre-selection highlighting keeps working;
  - each mouse move of (dx, dy) pixels in screen space (x to the right, y up) rotates the component by |d| × 0.4 degrees (a full turn takes about 900 px of drag). The axis is the screen-plane unit vector perpendicular to the drag direction, (−dy, dx, 0)/|d| in camera coordinates (x right, y up, z towards the viewer), with a positive right-hand rotation. It is converted to world space with the current camera orientation. In other words, dragging horizontally spins about the vertical screen axis and dragging vertically spins about the horizontal screen axis. A diagonal drag does both;
  - the pivot is the component's own placement origin: `Placement.Base` stays unchanged and only `Placement.Rotation` is pre-multiplied by the drag rotation. Rotation over a full 360° is possible, because nothing needs re-solving;
  - each press-drag-release is exactly one undo step named `Rotate Component`, and the document is recomputed when the button is released. A press and release without movement changes nothing.
- **Middle button, wheel and other navigation** are not consumed, so view navigation keeps working during the tool.
- **The tool ends** on any of:
  - Esc key press;
  - right mouse button press, which is consumed and does not open a context menu;
  - running `JellyJams_RotateComponent` again;
  - leaving the JellyJams workbench.

  Ending from inside a 3D-view event is deferred to the next event-loop turn. Ending does all of the following:
  - commits a drag that is still in progress, as its own undo step;
  - removes all 3D-view event hooks and the axis cross;
  - restores `EnableMovement` on the assembly's view object to the remembered value;
  - clears the status-bar message.

**Ribbon placement** (owned by the ribbon area): the "Assembly" tab shows `JellyJams_RotateComponent` as the small text button "Rotate Component" in its Move group, between "Move Component" and "Fix/Float".

---

## 3. Triggers and timing

### 3.1 Workbench lifecycle

Each step below is guarded on its own: one failure is reported in the Report view and never blocks the others.

| Event | Required effect in this area |
|---|---|
| JellyJams `Activated()` | Start the Add Mate panel: register exactly one selection observer, without duplicates on re-activation. Start the drop catcher: install exactly one application-wide event filter. Apply the three SwitchToWB overrides with backup (§5.1). |
| JellyJams `Deactivated()` | End a running Rotate Component tool. Stop the drop catcher by removing the filter. A filter that is not installed MUST never intercept, even if Qt still delivers an event. Restore the three SwitchToWB preferences (§5.1). Stop the Add Mate panel: remove the observer and hide the panel. |
| JellyJams `InitGui.py` load at FreeCAD startup | Crash recovery: restore each SwitchToWB that has a backup record (§5.2). This runs before any later automatic `Activated()`. |
| Main-window close while JellyJams is active (quit guard, owned by the lifecycle/layout area) | Restore the three SwitchToWB preferences before FreeCAD persists parameters. FreeCAD never calls `Deactivated()` on quit. If the close is cancelled (e.g. Cancel in "Save changes?") and JellyJams is still the active workbench, apply the overrides again. |

### 3.2 Add Mate panel refresh

- **Triggers**: every selection change (add, remove, set, clear). Several changes in one burst MUST be combined into a single refresh on the next event-loop turn.
- The panel MUST also stop being visible when its conditions stop holding (§2.1.6) even without a selection change, for example when a task dialog opens or the assembly leaves edit mode. A re-check at the ribbon's periodic availability-refresh cadence is acceptable for this.
- A refresh rebuilds the entity list, the mate buttons and the hint from scratch.

### 3.3 Drop handling

- The application-wide filter reacts to DragEnter, DragMove and Drop events whose data contains URLs. It maps each URL to a local file path and keeps the paths ending in `.fcstd`, matched case-insensitively.
- **Target assembly**, decided per event, first match wins:
  1. the active assembly in edit mode (`UtilsAssembly.activeAssembly()`);
  2. otherwise the active view's active object under the key `"assembly"` (`ActiveView.getActiveObject("assembly")`), if it derives from `Assembly::AssemblyObject`;
  3. otherwise, if the active document holds exactly one top-level `Assembly::AssemblyObject`, that one. Top-level means it is not inside another `Assembly::AssemblyObject` through its `InList`. Several candidates, or none, mean no target.
- With a target: the proposed action is accepted and the event is consumed on DragEnter, DragMove and Drop. On Drop, a Report-view message names the number of files and the assembly label. The insertion is scheduled for the next event-loop turn, after Qt has finished its drag-and-drop handling, and never runs inside the drop event.

### 3.4 Insertion rules (outcome requirements)

**Before inserting.** The save requirement of §2.2 is checked first. Then the target assembly is put into edit mode (activated, the same as `Gui.getDocument(doc).setEdit(assembly)`) **before** the undo transaction is opened, so that undoing removes only the insertion. The assembly is not activated if a task dialog is open, because activating would close it. In that case a Report-view message tells the user to double-click the assembly to move parts.

**One transaction.** All files of one drop go into a single document transaction named `Insert Component`. The transaction is committed even if some files fail.

**Source document per file:**

- If the file is already open in this session (comparing normalized absolute paths, case-insensitively where the OS is), the open document is reused and not opened again.
- Otherwise the file is opened hidden (`FreeCAD.openDocument(path, True)`). The assembly document is then made active again.
- If the file cannot be loaded, an error naming the file is reported and the file is skipped.

**Primary object of a file.** Consider root objects only. A root object is not contained in an `App::Part`, `PartDesign::Body`, `Assembly::AssemblyObject` or `App::DocumentObjectGroup` (checked through `InList`; mere references do not count). Take **all** root objects of the first type present, in this priority order, using derived-type checks:

1. `Assembly::AssemblyObject`
2. `App::Part`
3. `PartDesign::Body`
4. `Part::Feature`, except 2D profiles (`Part::Part2DObject` and its subtypes, such as sketches), which are not models

If none is found, a warning names the file and nothing is inserted from it. The same priority rule is used by the drawing area's "Make Drawing" to choose the model of a file, so both areas MUST stay consistent.

**Component creation (per primary object):**

- **Type**: `Assembly::AssemblyLink` if the object is an assembly (subassembly), otherwise `App::Link`. This is what FreeCAD 1.1's Insert Component creates. The component is created inside the assembly, so it appears in the assembly's `Group`.
- **Label**: the source object's `Label`. It is set explicitly after creation so that non-ASCII characters survive.
- **Link**: `LinkedObject` is set to the source object. If this fails (for example a self-reference when the assembly's own file is dropped), the half-made component is removed again and an error naming the object is reported. The component is then recomputed.
- **Placement**: if the assembly already contains `App::Link` or `Assembly::AssemblyLink` components, including ones added earlier in the same drop, the new component is moved along +X only. Its bounding-box XMin is placed 20 mm to the right of the largest bounding-box XMax among those existing components; Y and Z are unchanged. Bounding boxes come from the shapes as placed. If any needed box is unavailable, the component stays where FreeCAD put it, at the origin.
- **Grounding**: if, at the time of adding, the assembly has no grounded joint (no object reachable through its recursive OutList carries an `ObjectToGround` property), the new component is fixed. This uses FreeCAD's own grounding helper `CommandCreateJoint.createGroundedJoint(component)`, which needs the assembly to be active. Failure to fix produces a warning only.
- **Cleanup**: if nothing at all was linked from a document that was opened just for this drop, that hidden document is closed again and the assembly document is re-activated.

**After the transaction:**

- the assembly document is made active and recomputed;
- if at least one component was added, the assembly is put into edit mode again, because opening documents can end edit mode and parts are draggable only in edit mode;
- the success message of §2.2 is printed.

**Sandboxed-package note.** A dropped path that looks like a sandboxed document-portal path (contains `/run/user/` and `/doc/`) is still inserted. A warning advises that the reference may break after a restart, and that the user should use "Insert Component" instead.

### 3.5 New Assembly timing

Document creation is synchronous. Running `Assembly_CreateAssembly` is deferred to the next event-loop turn so that the new document's 3D view exists.

### 3.6 Rotate Component timing

- The command's availability is polled by the ribbon's periodic refresh, and by FreeCAD when the command is shown in a menu. Each availability check MAY update the ribbon tooltip.
- 3D-view mouse and keyboard handling uses the active view's Coin event callbacks for mouse button, mouse move and keyboard events. Handling an event means marking it handled so that FreeCAD does not process it.

### 3.7 Prerequisite: Assembly commands must exist

FreeCAD registers the `Assembly_*` commands only when its Assembly workbench initializes. Before the ribbon is built, JellyJams MUST import FreeCAD's Assembly command modules:

- `CommandCreateAssembly`
- `CommandInsertLink`
- `CommandInsertNewPart`
- `CommandCreateJoint`
- `CommandSolveAssembly`
- `CommandCreateView`
- `CommandCreateSimulation`
- `CommandCreateBom`

This makes `Assembly_CreateAssembly`, the joint commands and the others available without ever activating the Assembly workbench. The import belongs to the ribbon area, but this area depends on it. If a module is missing, a log-level message is written and the affected commands simply do not exist.

---

## 4. FreeCAD state read or changed

### 4.1 Parameters

| Group | Key | Type | Access |
|---|---|---|---|
| `User parameter:BaseApp/Preferences/Mod/Assembly` | `SwitchToWB` | Bool | Read (presence checked through the group's Bool key list), set to false while JellyJams is active, restored or removed on leave (§5.1) |
| `User parameter:BaseApp/Preferences/Mod/PartDesign` | `SwitchToWB` | Bool | Same as the Assembly key |
| `User parameter:BaseApp/Preferences/Mod/TechDraw/General` | `SwitchToWB` | Bool | Same as the Assembly key |
| `User parameter:BaseApp/Preferences/Mod/JellyJams` | `OriginalSwitchToWB` | String | JellyJams' backup record for Assembly: `"1"` (was explicitly true), `"0"` (was explicitly false), `"absent"` (key did not exist); empty or missing means no record pending |
| `User parameter:BaseApp/Preferences/Mod/JellyJams` | `OriginalPartDesignSwitchToWB` | String | The same record for Part Design |
| `User parameter:BaseApp/Preferences/Mod/JellyJams` | `OriginalTechDrawSwitchToWB` | String | The same record for TechDraw |

No other parameters are touched by this area.

### 4.2 Document objects and properties

| Object / type | Properties used | Read / write |
|---|---|---|
| `Assembly::AssemblyObject` (target or active assembly) | `Group`, `InList`, `OutListRecursive`, `Document`, `Label`, `Name`; method `newObject(type, label)` | read; components are added through `newObject` |
| Assembly view object | `isInEditMode()`, `EnableMovement` | read; `EnableMovement` is written temporarily by Rotate Component and always restored |
| `App::Link` / `Assembly::AssemblyLink` (new components) | `LinkedObject`, `Label`, `Placement` | written on drop |
| Component being rotated | `Placement` (Base and Rotation), `Name`, `Label` | `Placement.Rotation` written while dragging |
| Grounded joint (created by FreeCAD's helper in the `Assembly::JointGroup`) | `ObjectToGround` | read to detect fixed components; created on drop |
| Joints (`JointType` present) | `Reference1`, `Reference2`, `Label` | read to detect mated components |
| Source documents | `Objects`, `FileName`, `Name` | read; opened hidden, possibly closed |
| Assembly document | `FileName`, `Label`, `Name`; `saveAs`, `openTransaction`/`commitTransaction`, `recompute` | written |
| New document (New Assembly) | `Name`, `Label` | created |

**JellyJams stores no custom properties in users' documents in this area.** Everything created is standard FreeCAD content: links, assembly links and grounded joints. Files made with JellyJams therefore open in stock FreeCAD.

### 4.3 FreeCAD commands and APIs

- **Runs**: the joint commands of §2.1.3 and `Assembly_CreateAssembly`.
- **Defines**:
  - `JellyJams_NewAssembly`
  - `JellyJams_RotateComponent`
- **FreeCAD Assembly helpers used**:
  - `UtilsAssembly.activeAssembly()`
  - `UtilsAssembly.getComponentReference(assembly, root_obj, sub)` (returns `(component, relative_sub)` or `(None, "")`)
  - `CommandCreateJoint.createGroundedJoint(obj)`
- **Other FreeCAD APIs used**:
  - `FreeCADGui.Selection.getSelectionEx("*", 0)` and selection observers
  - `FreeCADGui.Control.activeDialog()`
  - `FreeCAD.openDocument(path, True)`
  - `FreeCAD.listDocuments()`
  - `FreeCAD.newDocument(name)`
  - `FreeCAD.setActiveDocument` / `FreeCADGui.setActiveDocument`
  - `FreeCAD.closeDocument`
  - `ActiveView.getActiveObject("assembly")`
  - `ActiveView.getCameraOrientation()`
  - `ActiveView.getSceneGraph()`
  - `ActiveView.addEventCallbackPivy` / `removeEventCallbackPivy`
  - `Part.getShape(obj).BoundBox`

### 4.4 Qt objects

- Add Mate panel objectNames: `JellyJamsPropertyManager`, `JellyJamsPropertyManagerTitle`, `JellyJamsSectionCaption`, `JellyJamsItemList`.
- Host: the `Gui::TaskView::TaskPanel` inside the dock with objectName `Tasks`. FreeCAD 1.1 uses `Tasks`. The layout area's dock lookup MAY accept older names.
- Ribbon dock: `JellyJamsCommandManager`. Its "Assembly" tab and its Rotate Component button are used for the tooltip (ribbon area).
- Main-window status bar: used for the Rotate Component hint.
- An application-wide event filter on the `QApplication` instance, for the drop catcher.

---

## 5. Persistence and restore rules

### 5.1 SwitchToWB exact three-state restore

The rules below apply to each of the three preferences of §2.3 on its own, with its own backup record (Assembly `OriginalSwitchToWB`, Part Design `OriginalPartDesignSwitchToWB`, TechDraw `OriginalTechDrawSwitchToWB`). A failure or a damaged record for one module never stops the other two.

**On entering JellyJams:**

- If **no** backup record is pending (the record empty, blank or missing), record the current state of `SwitchToWB`:
  - `"absent"` if the key is not among the group's Bool keys;
  - otherwise `"1"` or `"0"` for its current value.
- If a record is already pending, for example after re-entering without a clean leave, it MUST NOT be overwritten. The oldest record is the user's true original.
- Then set `SwitchToWB` = false.

**On leaving JellyJams, at startup recovery, and in the quit guard:**

- If a record is pending:
  - `"absent"`: **remove** the `SwitchToWB` key, so FreeCAD's built-in default applies again. Do not write an explicit true.
  - `"1"`: set it to true.
  - `"0"`: set it to false.

  Then remove the record itself.
- If no record is pending, do nothing. A user value is never touched without a record.
- An unrecognized non-empty record value is treated as corrupt: the record is removed with a warning that names the module, and `SwitchToWB` is left as it is. On entering JellyJams a fresh record is then taken.
- If the module's group did not exist before, an empty group may remain afterwards. The key itself must be absent.

The records are parameters, so FreeCAD persists them in `user.cfg`. They survive a crash.

### 5.2 Crash recovery

If FreeCAD crashed or was killed while JellyJams was active, the next start finds `SwitchToWB` = false plus a pending record for each module JellyJams had overridden. Loading `InitGui.py` restores each original state per §5.1 before anything else in JellyJams runs, and prints one Report-view message per restored module that names it ("Assembly", "Part Design" or "TechDraw"). Modules without a record are not touched; for example, a record left only for Part Design restores only Part Design. If JellyJams is then auto-activated, it takes fresh records of the now-correct originals.

### 5.3 Other state

- **Rotate Component**: `EnableMovement` is restored whenever the tool ends. It is never left false. Component placements are ordinary document changes, with undo.
- **Drop**: all changes are ordinary document changes inside one undo transaction. Saving an unsaved assembly is a real save chosen by the user, and it is not undone.
- **Add Mate panel**: no persistent state.

---

## 6. Edge cases and failure handling

All user-relevant messages go to the Report view prefixed `JellyJams: `. Unexpected exceptions are caught, logged with details, and never propagate into Qt or FreeCAD event handling.

### 6.1 Add Mate panel

| Case | Required behavior |
|---|---|
| FreeCAD's Assembly module is unavailable | There is never an active assembly, so the panel never appears. No error is raised. |
| The panel's host widget was destroyed by FreeCAD | The panel is rebuilt and inserted at the top on the next refresh. |
| The selection includes entities outside the active assembly | Those entities are ignored. The others count. |
| More than two entities | List all rows, offer no buttons, show the hint asking for exactly two entities. |
| A joint command is not registered | Clicking reports an error line. The panel stays usable. |

### 6.2 Drag-and-drop

| Case | Required behavior |
|---|---|
| A drag from inside FreeCAD (tree drag, text) | No URLs, so the drop is never intercepted. |
| Several top-level assemblies and none active | No target. FreeCAD handles the drop. |
| An unsaved assembly and the user cancels the Save dialog | Nothing is inserted, and a warning is shown. |
| A dropped file is already open (visible) | It is reused, and is not closed afterwards. |
| A file has no insertable object | A warning is shown. The hidden document is closed again, and the remaining files still insert. |
| One object of a file fails to link | An error is shown. Other objects and files continue. The transaction is still committed. |
| A task dialog is open at drop time | The assembly is not activated. A message advises double-clicking it. Insertion still happens. |
| An exception anywhere during insertion | An error with details is reported. The transaction is committed with whatever was done. |

### 6.3 SwitchToWB

| Case | Required behavior |
|---|---|
| Parameter access fails | A warning naming the module only. The other two modules are still handled, and the workbench still activates or deactivates. |
| The user changed `SwitchToWB` in FreeCAD's Assembly, Part Design or TechDraw preferences while JellyJams was active | The original recorded value wins on leave. This is accepted behavior. |
| A damaged record for one module | That record alone is removed with a warning; the other modules restore normally. |

### 6.4 New Assembly

| Case | Required behavior |
|---|---|
| The document cannot be created | An error is shown. Nothing else happens. |
| `Assembly_CreateAssembly` is unavailable or fails | An error is shown. The new empty document remains open. |

### 6.5 Rotate Component

| Case | Required behavior |
|---|---|
| Coin/pivy is unavailable, or the tool cannot start | An error is shown, and the tool is not marked as running. |
| The axis cross cannot be drawn | A log message only. The rotation still works. |
| The active view, document or component disappears while the tool runs (document closed, component deleted, assembly leaves edit mode) | The tool SHOULD end cleanly per §2.5. Hook-removal and restore errors are swallowed. |
| The assembly view object has no `EnableMovement` property | Skip blocking or restoring silently. |
| The selection changes while the tool is running | The tool keeps rotating the component it started with. |

---

## 7. Acceptance criteria

All checks run in FreeCAD 1.1 with JellyJams installed. "Report view" refers to FreeCAD's Report view. Parameter checks use `FreeCAD.ParamGet(...)` in the Python console.

### SwitchToWB handling

Criteria 1 to 6 hold for each of the three modules of §2.3, each with its own group and backup record: `Mod/Assembly` with `OriginalSwitchToWB`, `Mod/PartDesign` with `OriginalPartDesignSwitchToWB`, `Mod/TechDraw/General` with `OriginalTechDrawSwitchToWB`. They are written for Assembly.

1. Start with no `SwitchToWB` key under `Mod/Assembly`. Activate JellyJams. Now `GetBool("SwitchToWB", True)` is `False`, and `Mod/JellyJams` `GetString("OriginalSwitchToWB")` is `"absent"`.
2. Continuing from 1, switch to Part Design. `"SwitchToWB"` is not in `ParamGet(".../Mod/Assembly").GetBools()`, and `OriginalSwitchToWB` is not in `ParamGet(".../Mod/JellyJams").GetStrings()`.
3. Set `SwitchToWB` explicitly to `True`, then enter and leave JellyJams. The key is present and `True`. Repeat with `False`: present and `False`. In both cases no backup string remains. Mixed states across the three modules (for example Assembly absent, Part Design true, TechDraw false) all come back exactly.
4. While JellyJams is active, set `OriginalSwitchToWB` to `"1"` and trigger the workbench's activation again, without leaving. The record is still `"1"`, not overwritten.
5. Crash recovery: with FreeCAD closed, edit `user.cfg` so that `Mod/Assembly` has `SwitchToWB` = false and `Mod/JellyJams` has `OriginalSwitchToWB` = `"1"`. Start FreeCAD in a workbench other than JellyJams. `SwitchToWB` is `True` and the backup key is gone. With records for only some of the three modules, only those modules change, and the Report view has one message per restored module naming it.
6. With JellyJams active, quit FreeCAD with no unsaved documents. The saved `user.cfg` holds the original `SwitchToWB` state (absent, true or false exactly as before) and no `OriginalSwitchToWB`. If the quit is cancelled at the "Save changes?" prompt, `SwitchToWB` is `False` again while JellyJams stays active.
7. In JellyJams, double-click an `Assembly::AssemblyObject` in the tree. The assembly enters edit mode, `FreeCADGui.activeWorkbench().name()` stays `"JellyJamsWorkbench"`, and the `JellyJamsCommandManager` dock remains visible.

### New Assembly

8. `"JellyJams_NewAssembly"` is in `FreeCADGui.listCommands()`. Its `getInfo()` menu text is `New Assembly`, and it is enabled with no document open.
9. Open documents named `Part` and `Assembly1`, and make an `App::Part` active in `Part`. Run `JellyJams_NewAssembly`. A new document with Name and Label `Assembly2` is active. It contains exactly one `Assembly::AssemblyObject`, which is in edit mode (`UtilsAssembly.activeAssembly()` returns it). The `Part` document gained no new objects.
10. Run `JellyJams_NewAssembly` with no documents open. A document `Assembly1` with an active assembly is created.
11. Run `JellyJams_NewAssembly` before ever activating FreeCAD's Assembly workbench in this session. It still works, because the Assembly command modules are imported by JellyJams.

### Add Mate panel

12. In a saved assembly with two components A and B (neither fixed), activate the assembly and select one planar face of A in the 3D view. The Tasks panel shows, at its top, a frame with objectName `JellyJamsPropertyManager` and the title `Add Mate`. The list has the single row `Planar face – <A label>`. There are no mate buttons, and the hint asks for a second entity on another component.
13. Add a planar face of B. The buttons are exactly, in order: Coincident, Distance…, Parallel, Perpendicular, Angle. The hint is hidden.
14. Two cylindrical faces (A, B): Hinge, Slider, Concentric, Tangent, Distance…, Parallel, Perpendicular, Angle. Two circular edges: Hinge, Concentric, Distance…, Parallel, Perpendicular, Angle.
15. Cylindrical face + planar face: Tangent, Distance…. No Parallel, Perpendicular or Angle button appears for this pair.
16. Linear edge + cylindrical face: Slider, Concentric, Parallel, Perpendicular, Angle. Two linear edges: Slider, Coincident, Distance…, Parallel, Perpendicular, Angle.
17. Vertex + planar face: Coincident, Distance…. Vertex + vertex: Coincident, Distance…. Vertex + spherical face: Ball Joint, Coincident, Distance…. Two spherical faces: Ball Joint, Tangent, Distance…. Circular edge + planar face: Coincident, Distance…. Vertex + circular edge, conical face + planar face, or a B-spline face + planar face: no buttons, and the hint says that no mate fits.
18. Two faces of the same component A: both rows are listed, no buttons appear, and the hint says that both are on the same component.
19. Three entities selected: three rows, no buttons, and a hint asking for exactly two entities.
20. Each mate button shows FreeCAD's own icon of its mapped command, and its tooltip equals that command's FreeCAD tooltip.
21. With planar faces of A and B selected, click Coincident. FreeCAD's Distance joint task opens with both references pre-filled, and the Add Mate panel is not visible while the task is open. After OK, a new joint exists in the assembly's `Assembly::JointGroup`. With two cylindrical faces selected, Concentric opens the Cylindrical joint task and Tangent opens the Distance joint task.
22. Leave assembly edit mode, or have no assembly at all, and select faces. No Add Mate panel appears, and an already visible one disappears.
23. Switch to Part Design, enter an assembly there, and select two faces. No JellyJams panel appears. Switch back to JellyJams and repeat: the panel works, and only one panel or observer is active (no duplicate rows or panels).

### Drag-and-drop

24. With a saved, active assembly that has no components, drag `Shaft.FCStd` (root: one `App::Part`) from the file explorer onto the FreeCAD window. One `App::Link` labelled like the part appears in the assembly. Its `LinkedObject` is that `App::Part`. A grounded joint whose `ObjectToGround` is this link exists. The link sits at the origin. `Shaft` is open as a hidden document with no new tab. The assembly is in edit mode.
25. Then drop `Plate.FCStd`. The new link's bounding-box XMin equals the previous rightmost XMax + 20 mm (within tolerance), its Y and Z are unchanged, and it is not grounded.
26. Drop two files at once. Edit → Undo shows `Insert Component` once, and a single undo removes both new components, plus the grounded joint if one was created by that drop.
27. Drop a file whose root is an `Assembly::AssemblyObject`. An `Assembly::AssemblyLink` is created. A file with only a root `PartDesign::Body`: an `App::Link` to the body. A file with an `App::Part` that contains a body: one link, to the part only.
28. With an assembly in a never-saved document, drop a file. A Save As dialog appears, suggesting `<folder of the dropped file>/<document label>.FCStd`. Cancel: nothing is inserted, and a warning is in the Report view. Repeat and save: the component is inserted. A further drop shows no dialog.
29. Drop a `.FCStd` while the active document has no assembly. FreeCAD opens the file normally, and a JellyJams message about no unique assembly appears.
30. Drop a `.step` or `.png` onto an active assembly. FreeCAD's normal import or open happens, with no JellyJams insertion.
31. Leave JellyJams, for example by switching to Part Design, and drop a `.FCStd` onto an assembly document. FreeCAD opens the file normally.
32. Drop a file that is already open as a visible document. No second copy is opened, and the document stays open afterwards.
33. Drop a `.FCStd` containing only a sketch at root. A warning names the file, and no hidden document for it remains in `FreeCAD.listDocuments()`.

### Rotate Component

34. `"JellyJams_RotateComponent"` is registered with menu text `Rotate Component`. With no active assembly it is disabled, and the ribbon button's tooltip ends with the reason that names the missing active assembly.
35. In an active assembly, select a face of a floating, unmated component. The command is enabled, and the tooltip is just the base text. Select the grounded component: disabled, and the tooltip names it as fixed. Select a component used by a joint labelled e.g. `Concentric1`: disabled, and the tooltip names `Concentric1`. Select faces on two different components: disabled, with the reason asking for a single component of the active assembly.
36. Start the tool on a floating component. The status bar shows the drag/Esc hint, a red/green/blue axis cross appears at the component's placement origin, and the assembly view object's `EnableMovement` is `False`.
37. Drag 30 px to the right with the left button. The component turns 12° about the screen-vertical axis. `Placement.Base` is unchanged, and the selection did not change. Edit → Undo shows `Rotate Component`, and one undo reverts exactly that drag.
38. During the tool, middle-button navigation still orbits or pans the view.
39. Press Esc. The tool ends: the axis cross is gone, the status-bar message is cleared, and `EnableMovement` is back to its previous value (also when it was `False` before). Repeat, ending with a right-click instead: no context menu appears. Repeat, ending with the ribbon button: the same result. Repeat, ending by switching workbench: the same result.
40. A component rotated with the tool and saved, then reopened in stock FreeCAD without JellyJams, shows the same orientation. The document contains no JellyJams-specific properties.

### SwitchToWB of Part Design and TechDraw

41. With no `SwitchToWB` key under `Mod/PartDesign`, in JellyJams open a sketch inside a Body, draw something and exit the sketch. The body becomes active again and `FreeCADGui.activeWorkbench().name()` stays `"JellyJamsWorkbench"`. (`tests/gui_sketch_first.py`, `a_still_in_jellyjams_after_exit`.)
42. With no `SwitchToWB` key under `Mod/TechDraw/General`, in JellyJams double-click a TechDraw page in the tree. The page opens and the workbench stays `"JellyJamsWorkbench"`.

### Assembly tree interaction

43. Create a New Assembly with an empty part document already open. Select the
    assembly and repeatedly click its expand/collapse triangle and the triangle
    of its Origin branch. Each click toggles the targeted branch, the UI remains
    responsive, the assembly stays active and JellyJams remains the workbench.
    `tests/gui_assembly_tree.py` checks 100 native pointer clicks across the two
    branches in a disposable profile. Passing this scenario does not establish
    that every profile or timing of tree interaction is free of hangs.
