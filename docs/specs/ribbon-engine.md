# JellyJams specification: Ribbon engine

> **Implemented in:** [`jellyjams/ribbon.py`](../../jellyjams/ribbon.py), [`ribbon_model.py`](../../jellyjams/ribbon_model.py), [`ribbon_text.py`](../../jellyjams/ribbon_text.py), [`ribbon_widgets.py`](../../jellyjams/ribbon_widgets.py), [`icons.py`](../../jellyjams/icons.py); the feature-from-open-sketch gesture (3.6) and the sketch-first start ([sketching.md](sketching.md) 2.6) in [`sketch_gesture.py`](../../jellyjams/sketch_gesture.py). The ribbon content itself is specified in [ribbon-content.md](ribbon-content.md).
>
> **Status:** see [../status.md](../status.md)

Area: **ribbon-engine** of JellyJams (FreeCAD 1.1+ workbench, key/class
`JellyJamsWorkbench`, MenuText `JellyJams`, English only).

This document states requirements only. Function, class and module names
are not part of the specification; the public facts listed in section 4
(objectNames, parameter paths and keys, FreeCAD command ids and APIs) are.

---

## 1. Purpose

The ribbon engine turns a declarative ribbon layout (owned by the
**ribbon-layout** area: tabs → groups → entries) into a SolidWorks
CommandManager–style ribbon at the top of the FreeCAD main window, and keeps
it alive:

- renders the tabs, groups and the four button kinds (large button, 3-row
  small stack, flyout, toggle);
- runs FreeCAD (and `JellyJams_*`) commands when buttons are pressed;
- greys buttons out when FreeCAD says their command is not applicable now;
- shows FreeCAD's own icons for FreeCAD commands and JellyJams' own icons for
  `JellyJams_*` commands;
- composes tooltips that teach the SolidWorks → FreeCAD mapping;
- switches tabs automatically on context transitions (entering a sketch,
  activating an assembly, activating a drawing sheet), like SolidWorks;
- routes a profile-feature click made while a sketch is open into the
  "feature from open sketch" gesture;
- is visible only while the JellyJams workbench is active, and guards against
  FreeCAD re-showing it elsewhere.

---

## 2. User-visible behavior and UI

### 2.1 Host and frame

- The ribbon is a Qt dock widget (`QDockWidget`) owned by the FreeCAD main
  window (`FreeCADGui.getMainWindow()`), added to the **top dock area**
  (`Qt.DockWidgetArea.TopDockWidgetArea`), spanning the window width above
  the 3D view / MDI area.
- objectName: **`JellyJamsCommandManager`**. Window title: `JellyJams Ribbon`.
- No visible title bar (an empty widget replaces the title bar) and no dock
  features (`NoDockWidgetFeatures`): the user cannot close, float or move it.
- It is a dock, not a toolbar, on purpose: FreeCAD hides/shows the toolbars it
  manages on every workbench switch but leaves foreign docks alone, so
  JellyJams controls the ribbon's visibility itself.
- Inside the dock: one tab widget, objectName **`JellyJamsCommandManagerTabs`**, in
  document mode, with the **tab bar below the buttons** (tab position South),
  as in the SolidWorks CommandManager.
- One tab per layout tab, in layout order. With the JellyJams layout the tabs
  are exactly, in this order: **Features, Sketch, Evaluate, Assembly,
  Drawing**. The tab titles come only from the layout data.
- When the ribbon is first built, the **Features** tab is the current tab,
  regardless of its position in the tab order.
- There is no language selector (English only).

### 2.2 Tab page structure

- A tab page shows its groups side by side, left-aligned, with free space
  pushed to the right end.
- Consecutive non-empty groups are separated by a thin vertical sunken line,
  objectName **`JellyJamsGroupDivider`**. No separator before the first group,
  and a group whose entries all resolved to nothing produces neither content
  nor separator.
- Approximate spacing: page margins about 4 px left/right and 2 px
  top/bottom; about 2 px between widgets; 1 px between cells of a stack.

### 2.3 Button kinds

All ribbon buttons are flat tool buttons (`QToolButton`, auto-raise: flat until
hovered).

**Large button** (default for a top-level entry):
- 32 × 32 px icon with the text **below** the icon.
- The text is the layout label (the SolidWorks name, e.g. "Extruded
  Boss/Base"), keeping the layout's forced line breaks so buttons stay narrow
  (e.g. "Extruded" / "Boss/Base" on two lines).

**Stack** (layout entry declared as a stack with a style):
- A compact block of small buttons (20 × 20 px icons) arranged in a grid
  **3 rows high**, filled **column by column** (first column rows 1–3, then
  the second column, …). Container objectName **`JellyJamsToolStack`**.
- Style "icon": icon only, no text (used for the sketch drawing tools, the view
  orientations and the sheet-sketch shapes).
- Style "text": icon with the label **beside** it on one line; these buttons
  stretch horizontally to align.
- A stack may contain plain entries and flyouts. Entries that resolve to
  nothing are skipped without leaving gaps; an empty stack produces nothing.

**Flyout** (layout entry listing several variants; may appear top-level or
inside a stack):
- A split button (Qt `MenuButtonPopup` popup mode): the main part runs the
  **current variant**; the arrow part opens a menu listing every available
  variant (its icon and its one-line label) in layout order.
- Choosing a variant from the menu makes it the current variant (button
  icon, text, tooltip and objectName update), remembers it persistently
  (section 5), and runs it immediately.
- The button shows the current variant's icon. Its text is the current
  variant's label — or, when the layout gives the flyout a fixed **title**
  (e.g. "Mate" on the Assembly tab), always that title while the icon still
  follows the chosen variant.
- Size and text placement follow where the flyout sits: large with text below
  at top level; small icon-only inside an "icon" stack; small with one-line
  text beside inside a "text" stack.
- Menu entries are not individually greyed out; the whole split button is
  enabled or disabled according to the current variant (section 3.2).
- A flyout with only one available variant is still a flyout (one menu
  entry).

**Toggle** (layout entry with exactly two variants, e.g. "Sketch" / "Exit
Sketch"):
- One large button slot that shows variant 1 normally and variant 2 while a
  sketch is being edited (section 3.3). Text, icon, tooltip and objectName
  follow the shown variant; a click runs the shown variant's command.
- If either variant's command is unavailable, the toggle degrades to a plain
  large button for the first available variant (or to nothing if none is
  available).

### 2.4 Button identity and objectNames

- **Entry id**: the command id, or `<command id>#<index>` when the layout
  entry carries a sub-entry index (section 2.6). When a fallback command
  substitutes a missing one (section 6.1), the id uses the substituted
  command id.
- objectNames (an indexed id's `#` is written as `-`):
  - plain button: `JellyJamsButton-<entry id>` (e.g. `JellyJamsButton-PartDesign_Pad`,
    `JellyJamsButton-Std_DrawStyle-6`);
  - flyout: `JellyJamsFlyout-<entry id of the current variant>` (changes when the
    current variant changes);
  - toggle: `JellyJamsToggle-<entry id of the shown variant>` (e.g.
    `JellyJamsToggle-PartDesign_NewSketch` ↔ `JellyJamsToggle-Sketcher_LeaveSketch`).
- Every plain entry id must be unique within the ribbon. A layout that
  places the same command twice disambiguates the second copy with an index
  (e.g. `JellyJams_MakeDrawing` on the Drawing tab and `JellyJams_MakeDrawing#1` on the
  Assembly tab); both copies are separate, fully functional buttons.

### 2.5 Labels: one-line form

Wherever a label must be shown on one line (text-beside buttons, flyout menu
entries, flyouts with a fixed title in a text stack, tooltip names), the
layout label is flattened as follows:

- a hyphen at a line break followed by a lowercase letter is a hyphenation
  break: hyphen and break are removed and the word is joined
  ("Center-⏎line" → "Centerline");
- any other hyphen at a line break keeps the hyphen and drops the break
  ("Dash-⏎Dot" → "Dash-Dot", "Multi-⏎Transform" → "Multi-Transform");
- any other line break becomes a single space ("Center⏎Rectangle" → "Center
  Rectangle", "Extruded⏎Boss/Base" → "Extruded Boss/Base");
- for tooltip names additionally: soft hyphens (U+00AD) are removed (a soft
  hyphen at a line break joins the parts) and runs of whitespace collapse to
  single spaces.

### 2.6 Group commands (sub-entries)

- A layout entry may carry a sub-entry **index** for a FreeCAD group command,
  e.g. `Std_DrawStyle` index 6 = "Shaded With Edges", 5 = "Shaded",
  3 = "Hidden Lines Removed", 2 = "Wireframe" (FreeCAD 1.1 order: 0 As is, 1 Points,
  2 Wireframe, 3 Hidden line, 4 No shading, 5 Shaded, 6 Flat lines).
- Pressing such a button runs the group command with that index, exactly as
  FreeCAD itself records it (`FreeCADGui.runCommand("Std_DrawStyle", 5)`).
- A `JellyJams_*` command that appears with an index only for disambiguation (e.g.
  `JellyJams_MakeDrawing#1`) must behave identically to its index-less copy; JellyJams
  commands placed this way must accept and ignore the index argument.

### 2.7 Icons

Hard project rule: **no bundled third-party icons**. FreeCAD commands show
FreeCAD's own icons, looked up at runtime; `JellyJams_*` commands show JellyJams'
own, newly drawn icons (drawn by the area that owns each command).

Required precedence for a button's icon (first usable, non-null icon wins):

1. **`JellyJams_*` commands only:** the JellyJams icon named for that entry in the
   layout (an add-on resource; `.svg`, else `.png`). A layout-supplied own
   icon name on a non-`JellyJams_*` command is ignored.
2. The icon of the `QAction` FreeCAD created for the command
   (`FreeCADGui.Command.get(id).getAction()`); for a group command with an
   index, the action of that sub-entry. (Such actions exist only once FreeCAD
   placed the command in a toolbar or menu.)
3. Candidate icon names: an explicit FreeCAD icon name given by the layout
   entry (e.g. `DrawStyleFlatLines`, `DrawStyleShaded`,
   `DrawStyleHiddenLine`, `DrawStyleWireFrame`), then the command's own
   `pixmap` from `getInfo()`. A candidate that is an absolute path to an
   existing file is loaded directly (JellyJams commands may declare file paths).
4. A lookup of each candidate name in FreeCAD's compiled-in Qt resources under
   `:/icons`, searched **recursively** (Sketcher icons live in subfolders
   such as `:/icons/geometry/…`, PartDesign icons directly under `:/icons/`),
   matching the file name without extension, exactly or case-insensitively.
   The index of resource icons is built once, lazily, and capped at 50,000
   entries so a broken environment can never loop endlessly.
5. `FreeCADGui.getIcon(name)` for each candidate name.
6. Otherwise no icon. An icon-only stack button without any icon SHOULD show
   its one-line label as text so it is never blank.

Why step 5 comes after every other source: `getIcon()` has no way to say
"not found". Given a name it cannot resolve, FreeCAD's bitmap factory prints
a `Cannot find icon` warning to the Report view and still hands back a
generic stand-in image that looks to the caller like a successful lookup.
Steps 1–4 can all report a miss cleanly, so they are exhausted first; only
then is `getIcon()` allowed to answer.

The ribbon must not change icons, texts or shortcuts of FreeCAD's own
toolbars, menus or commands: everything above applies to ribbon widgets only.

Preload the optional native `AssemblyGui` resource module before indexing icons
on hosts that provide it (26.3). Its absence on 1.1 is normal; errors inside an
available module are reported with the other command-module loading failures.

The same icon lookup must be available to other JellyJams areas (the Add
Relations panel and the Add Mate panel show buttons for the same FreeCAD
commands and must show the same icons as the ribbon).

### 2.8 Tooltips

Every ribbon button has a tooltip. The **composed tooltip** for a label (SW
name) and a FreeCAD command is:

- Line 1: `<SW name> — (FreeCAD: <FreeCAD menu text>)` — an em dash (U+2014)
  with single spaces around it.
  - `<SW name>` is the label in one-line tooltip form (2.5); if empty, the
    FreeCAD menu text is used.
  - `<FreeCAD menu text>` is the command's `menuText` (from `getInfo()`; for
    an indexed sub-entry, the sub-entry `QAction`'s text and tooltip are used
    when that action exists and has text), converted to plain text: HTML tags
    removed; `&` accelerator markers removed (`&&` becomes a literal `&`;
    HTML entities such as `&amp;` are not mistaken for accelerators); HTML
    entities decoded; whitespace collapsed; a trailing "..." or "…" of a
    dialog command removed.
  - If SW name and FreeCAD name are the **same** (case-insensitive, ignoring
    whitespace differences and one trailing period), line 1 is just the
    name — never "Mate — (FreeCAD: Mate)". This is the normal case for
    `JellyJams_*` commands.
- Line 2 (optional): FreeCAD's own `toolTip`, HTML tags removed, entities
  decoded, trimmed — only when non-empty and different (same-name rule) from
  both the SW name and the FreeCAD name.
- If FreeCAD reports no menu text, there is no composed tooltip.

Examples (label, menuText, toolTip → result):

| Label | menuText | toolTip | Composed tooltip |
|---|---|---|---|
| "Extruded⏎Boss/Base" | "&Pad..." | "" | `Extruded Boss/Base — (FreeCAD: Pad)` |
| "Mate" | "Mate" | "" | `Mate` |
| "Fillet" | "" | "" | *(none)* |
| "Shell" | "Thickness" | "<b>Makes</b> a thick solid" | `Shell — (FreeCAD: Thickness)` ⏎ `Makes a thick solid` |

Which tooltip each kind shows:

- **Plain button**: the composed tooltip. Without one: for an indexed
  sub-entry or an icon-only button, the one-line label; otherwise FreeCAD's
  raw description (its `toolTip` with HTML removed, else its `menuText`, else
  the command id).
- **Toggle**: the shown variant's composed tooltip, else its raw description.
- **Flyout**: built from the current variant:
  - base text: the variant's composed tooltip if it has one, or — when the
    button visibly shows the variant's own label (text shown and no fixed
    title) — the variant's raw description; otherwise the variant's one-line
    label (so the SW name is never lost when it is not printed on the
    button);
  - with a fixed title that differs (same-name rule) from the variant's
    name, the base text is prefixed with `<title>: ` (e.g. a tooltip
    beginning `Mate: Concentric`);
  - always followed by a final line telling the user that the arrow on the
    right offers more variants.
- Tooltips are set when a button is built and when a flyout/toggle changes
  its shown variant. The periodic refresh (3.2) must **not** reset tooltips,
  because some commands change their ribbon button's tooltip dynamically (see
  4.6, `JellyJams_RotateComponent`).

---

## 3. Triggers and timing

### 3.1 Show / hide (workbench lifecycle)

- The workbench's activation shows the ribbon; its deactivation hides it.
  The ribbon is shown after the window-layout area has taken its window-state
  snapshot and applied the layout, and hidden before that area restores the
  window state.
- The ribbon is **built on the first show only**. Later shows reuse it:
  activating the workbench again never duplicates tabs or buttons.
- Show: mark the ribbon as *requested* (it should be visible), make the dock
  visible, start the periodic refresh, and run one refresh immediately
  (enabled states, toggle state and context tab are correct the moment the
  ribbon appears).
- Hide: mark it as *not requested*, hide the dock, stop the periodic refresh.
  All content and state are kept (current tab, flyout choices, remembered
  pre-sketch tab, context state).
- Hiding before the ribbon was ever built is a harmless no-op.
- Show is also called by the window-layout area (a) after a deferred
  autoload entry, because FreeCAD's restoration of the saved window state can
  hide the dock, and (b) after a cancelled quit (the close guard hid it
  before FreeCAD's "Save changes?" prompt). Show must therefore be
  idempotent.
- The window-layout area's close guard hides the ribbon before FreeCAD
  persists `MainWindowState` on quit (FreeCAD never calls `Deactivated()` on
  quit), so a visible ribbon is never saved into the stored window layout.

### 3.2 Periodic refresh (enabled state)

- While the ribbon is shown, a refresh runs every **450 ms**; no polling
  happens while it is hidden.
- Each refresh:
  - evaluates context transitions (3.4);
  - sets each plain button enabled iff
    `FreeCADGui.Command.get(<command id>).isActive()` is true (for indexed
    entries the base command id is asked);
  - sets each flyout enabled according to its **current** variant's command;
  - updates each toggle's shown variant (3.3), then sets it enabled according
    to the shown variant's command.
  - finally synchronizes Measure's checked/highlighted state from the active
    temporary task, keeping the active button enabled so it can toggle off.
- If asking FreeCAD fails (command missing, exception), the button stays
  **enabled** (when in doubt, clickable).
- Effect example: sketch tools become clickable only while a sketch is being
  edited, without JellyJams knowing anything about sketches.

### 3.3 Toggle state

- "Editing a sketch" means: `FreeCADGui.ActiveDocument` exists, its
  `getInEdit()` returns a view provider, and that view provider's
  `Object.TypeId` is `Sketcher::SketchObject`.
- On each refresh, every two-variant toggle shows variant 2 while a sketch is
  being edited, else variant 1. The button is updated only when the shown
  variant actually changes.
- JellyJams layout: variant 1 = `PartDesign_NewSketch` ("Sketch"), variant 2
  = `Sketcher_LeaveSketch` ("Exit Sketch").

### 3.4 Document and edit context

The ribbon switches tabs like SolidWorks, but only on the **transition** into
a context. After the automatic switch the user may click any other tab and
the ribbon will not force it back on later refreshes. Each rule applies only
if its target tab exists. With an active document, choices are remembered per
document identity and mode in a bounded, session-only cache. A new part starts
on Features, a new assembly on Assembly, and a new drawing on Drawing. Returning
to another document restores that document's last tab for its current mode.

- **Sketch** (tab "Sketch"): when sketch editing starts (definition in 3.3),
  remember the current tab, then switch to "Sketch". When sketch editing ends,
  switch back to the remembered tab (even if the user changed tabs inside the
  sketch). Every new sketch-edit entry selects Sketch, regardless of a manual
  tab choice made during an earlier sketch edit. Editing any other object type (e.g. a
  `PartDesign::Pad` feature) causes no switch. Sheet sketches created by the
  Drawing tab's sheet-sketch tools are ordinary sketches: editing one switches
  to "Sketch", exiting returns to "Drawing".
  The prior tab also returns when native sketch edit has replaced the sheet
  window with a 3D window; this return survives switching documents mid-edit.
- **Assembly** (tab "Assembly"): when an assembly becomes active — FreeCAD's
  Assembly helper `UtilsAssembly.activeAssembly()` returns an
  `Assembly::AssemblyObject` (i.e. an assembly in edit mode) — switch to
  "Assembly", unless the ribbon is currently in the sketch context. When it
  becomes inactive, restore that document's remembered part-mode tab, defaulting
  to Features. If the Assembly module is unavailable,
  "no active assembly" is assumed.
- **Drawing** (tab "Drawing"): when a drawing sheet window becomes the active
  MDI window — the main window's `QMdiArea` active sub-window holds a widget
  whose Qt class name is `TechDrawGui::MDIViewPage` — switch to "Drawing".
  Leaving the sheet restores the target document/mode's remembered tab;
  returning to it restores its remembered drawing-mode tab.
- If several transitions are detected in the same refresh, the Sketch rule
  wins (it is applied last).
- Context state is compared with the state last observed while the ribbon was
  shown. Changes that happened while it was hidden are treated as
  transitions at the first refresh after the next show.
- Drawing-context side effects owned by other areas, each failure-isolated
  and silent:
  - on **every** refresh while a sheet window is active: let the sheet drag
    helper (drawing area) attach to the active sheet window (must be
    idempotent);
  - on the **transition** into a sheet window: let the drawing area make the
    existing projected views of `FreeCAD.ActiveDocument` movable, and let the
    naming area refresh SolidWorks-style tree labels of that document's
    drawing objects.

### 3.5 Running a command (button click)

The existing `Sketcher_Dimension` slot runs through `sketch_dimension.run` after
stopping any prior preview correction. It calls the native command once and
aligns new linear previews to the pointer ([sketching.md](sketching.md) 2.9).
Every other ribbon click stops that correction before dispatch. Ribbon hide
also stops it, covering leave and quit without new lifecycle steps or preferences.

Whenever any ribbon button, flyout (main part or menu choice) or toggle runs a
command:

1. If a JellyJams sketch tool mode is running — **Centerline** (`JellyJams_Centerline`)
   or **Midpoint Line** (`JellyJams_MidpointLine`) — and the command being run is not
   that same tool, the running mode is ended first (sketch-tools area must
   offer a safe "stop if running").
2. If the press has no sub-entry index and the command is a **profile
   feature**, `sketch_gesture.try_run` decides first. With a sketch being
   edited, the feature-from-open-sketch gesture (3.6) takes over and the
   command is not run directly. With no sketch being edited and nothing to use
   as the profile, a sketch-first feature opens a new sketch instead
   ([sketching.md](sketching.md) 2.6) and runs once that sketch is exited.
3. The unindexed `Std_Measure` ribbon entry calls `measure.toggle()` instead of
   the native task. It opens/stops the temporary tool with geometry-specific
   sizes, pair distances/angles and totals; see [measure.md](measure.md).
   Ribbon hide stops this task before stock layout restoration, including quit.
4. Otherwise the command runs through `FreeCADGui.runCommand(id)` or, for an
   indexed entry, `FreeCADGui.runCommand(id, index)`.
5. Any failure is reported in the Report view (error naming the command and
   the reason) and never propagates into Qt.

### 3.6 Feature from open sketch (SolidWorks gesture)

- Profile features (FreeCAD 1.1 command ids): `PartDesign_Pad`,
  `PartDesign_Pocket`, `PartDesign_Revolution`, `PartDesign_Groove`,
  `PartDesign_Hole`, `PartDesign_AdditivePipe`, `PartDesign_SubtractivePipe`,
  `PartDesign_AdditiveLoft`, `PartDesign_SubtractiveLoft`,
  `PartDesign_AdditiveHelix`, `PartDesign_SubtractiveHelix`.
- When one of them is pressed in the ribbon while a sketch is being edited:
  1. the sketch is closed exactly as "Exit Sketch" does
     (`FreeCADGui.runCommand("Sketcher_LeaveSketch")`);
  2. about **50 ms** later (so FreeCAD can fully close the sketch task panel):
     the selection is cleared, that sketch object is selected
     (`FreeCADGui.Selection.clearSelection()` / `addSelection(sketch)`), and
     the feature command is run — FreeCAD then uses the preselected sketch as
     the profile.
- If closing the sketch fails, a warning is logged and the feature command
  runs the normal way instead. If selecting fails, a warning is logged and the
  feature still runs. If the feature fails, an error is logged.
- Non-profile features (e.g. `PartDesign_Fillet`) run normally. A press without
  an open sketch runs normally too, except the sketch-first case of
  [sketching.md](sketching.md) 2.6 (Extruded Boss/Base, Extruded Cut, Revolved
  Boss/Base, Revolved Cut and Hole Wizard with nothing to use as the profile).
- The sketch-exit transition (3.4) returns the ribbon to the pre-sketch tab.

### 3.7 Visibility guard

- Whenever the dock reports that it became visible while the ribbon is **not
  requested** (e.g. FreeCAD's delayed window-state restore during a workbench
  switch), it is hidden again on the next event-loop turn (deferred, not
  synchronously inside the visibility notification).
- The same "hide if not requested" check is offered as a service; the
  window-layout area calls it after its delayed second window-state restore
  (~250 ms after leaving), because `restoreState()` can re-show the dock.
- While the ribbon is requested, the guard never hides it. Before the ribbon
  was built, the check does nothing. Errors during the check are swallowed.

### 3.8 Command availability at build time

- Before building, the engine loads FreeCAD GUI modules so their commands
  exist even if the user never opened those workbenches: `PartGui`,
  `SketcherGui`, `PartDesignGui`, `TechDrawGui`. A module that fails to load
  produces a warning naming the module and the reason; the build continues.
- It also imports FreeCAD's Assembly command modules (registered by FreeCAD
  only when the Assembly workbench initializes): `CommandCreateAssembly`,
  `CommandInsertLink`, `CommandInsertNewPart`, `CommandCreateJoint`,
  `CommandSolveAssembly`, `CommandCreateView`, `CommandCreateSimulation`,
  `CommandCreateBom`. Modules that fail to import are listed in one
  log-level message (no warning); only those buttons go missing.
- The set of available commands is then taken from
  `FreeCADGui.listCommands()`. `JellyJams_*` commands are registered by the
  workbench's `Initialize()`, which FreeCAD runs before the first
  `Activated()`, so they are available at build time.

### 3.9 Rebuild on demand

- A rebuild service re-creates the ribbon from the current layout data: the
  old dock is fully disposed of (hidden, removed from the main window,
  detached and scheduled for deletion; each step failure-isolated so a
  failing step never prevents the others), all registries and the skipped
  list are reset, the new dock is built, the previous current tab index is
  restored (clamped to the valid range), and the ribbon is shown (with
  refresh running) if it was requested, otherwise left hidden.
- After a rebuild, commands that customize their ribbon button's tooltip at
  runtime (`JellyJams_RotateComponent`) must re-apply it to the new button (they must not
  assume their old tooltip is still displayed).
- Rebuilding when the ribbon was never built does nothing.

---

## 4. FreeCAD state read or changed

### 4.1 Qt objects created

| Object | Qt type | objectName | Notes |
|---|---|---|---|
| Ribbon dock | `QDockWidget` | `JellyJamsCommandManager` | title "JellyJams Ribbon", empty title-bar widget, `NoDockWidgetFeatures`, `TopDockWidgetArea` |
| Tab widget | `QTabWidget` | `JellyJamsCommandManagerTabs` | document mode, `TabPosition.South` |
| Stack container | `QWidget` | `JellyJamsToolStack` | 3-row grid |
| Group separator | `QFrame` | `JellyJamsGroupDivider` | `VLine`, `Sunken` |
| Plain button | `QToolButton` | `JellyJamsButton-<id>` | auto-raise |
| Flyout | `QToolButton` + `QMenu` | `JellyJamsFlyout-<current id>` | `ToolButtonPopupMode.MenuButtonPopup` |
| Toggle | `QToolButton` | `JellyJamsToggle-<shown id>` | large |
| Refresh timer | `QTimer` | — | 450 ms, owned by the dock, runs only while shown |

The **theme** area styles the ribbon through `QDockWidget#JellyJamsCommandManager`,
`QTabWidget#JellyJamsCommandManagerTabs` (pane, tab bar, tabs, tool buttons, menus),
`QToolButton[popupMode="1"]` (flyouts) and `QFrame#JellyJamsGroupDivider`
inside the `/* @jellyjams-stylesheet-open */` … `/* @jellyjams-stylesheet-close */` block. These
objectNames and the `MenuButtonPopup` mode are therefore a fixed contract.

### 4.2 FreeCAD GUI APIs read

- `FreeCADGui.getMainWindow()`; its `QMdiArea` and `activeSubWindow()`;
  `widget().metaObject().className()` compared with `TechDrawGui::MDIViewPage`.
- `FreeCADGui.listCommands()`.
- `FreeCADGui.Command.get(id)`: `.getInfo()` (keys `menuText`, `toolTip`,
  `pixmap`), `.getAction()` (list of `QAction`: `icon()`, `text()`,
  `toolTip()`), `.isActive()`.
- `FreeCADGui.getIcon(name)`; Qt resources under `:/icons` (recursive).
- `FreeCADGui.ActiveDocument`, `.getInEdit()`, view provider `.Object.TypeId`.
- `UtilsAssembly.activeAssembly()` (FreeCAD `Mod/Assembly`).
- `FreeCAD.ActiveDocument` (passed to drawing/naming hooks).

### 4.3 FreeCAD state changed

- Commands executed: whatever the user presses, via `FreeCADGui.runCommand`;
  plus `Sketcher_LeaveSketch` and selection changes
  (`FreeCADGui.Selection.clearSelection`, `addSelection`) for the gesture.
- Main window: the `JellyJamsCommandManager` dock is added once and shown/hidden.
- FreeCAD GUI/Assembly modules listed in 3.8 are imported (side effect:
  their commands are registered — identical to FreeCAD's own behavior when
  those workbenches load).
- Parameters: only the JellyJams subgroup in 5.1. The ribbon writes **no**
  FreeCAD-owned parameter and never touches `MainWindowState`, toolbars,
  menus, or other workbenches.

### 4.4 Document data

The ribbon stores nothing in users' FreeCAD documents (no custom
properties).

### 4.5 Command ids referenced by the engine itself

`Sketcher_LeaveSketch`, `PartDesign_NewSketch` (toggle content comes from the
layout), the profile-feature list in 3.6, `Std_DrawStyle` (indexed example),
`JellyJams_Centerline`, `JellyJams_MidpointLine`, `JellyJams_RotateComponent`, `JellyJams_MakeDrawing`.

### 4.6 Services offered to other areas

The engine must expose (names free) the following capabilities:

- show the ribbon; hide the ribbon; query whether the ribbon is currently
  requested; "hide if not requested" re-check (3.7); rebuild (3.9);
- icon lookup for a command id with optional sub-entry index and optional
  JellyJams icon name, using the precedence of 2.7 (used by the Add
  Relations and Add Mate panels);
- lookup of the live plain ribbon button for a command id, so a command can
  set a dynamic tooltip on its own button (`JellyJams_RotateComponent` shows the reason
  why it is greyed out; the refresh must not overwrite it);
- the current tab titles and the names of the context tabs;
- for automated tests: all entry ids (plain buttons plus every variant of
  every flyout and toggle), the skipped command ids, the flyouts (id,
  variants, current index), the toggles (variants, shown index), and a way to
  run one refresh synchronously.

---

## 5. Persistence and restore rules

### 5.1 Remembered flyout variant (persists across restarts)

- Parameter group:
  **`User parameter:BaseApp/Preferences/Mod/JellyJams/FlyoutChoices`**.
- One **String** entry per flyout that the user has ever chosen from:
  - key = the flyout's id = the entry id of its **first available** variant
    (after missing variants are dropped and fallbacks substituted), e.g.
    `Sketcher_CreateRectangle`, `Sketcher_CreateLine`,
    `PartDesign_LinearPattern`, `Part_DatumPlane` (`PartDesign_Plane` on a
    build that only has the fallback), `TechDraw_Dimension`, `JellyJams_Note`;
  - value = the entry id of the chosen variant, e.g.
    `Sketcher_CreateRectangle_Center`.
- Written only when the user picks a variant from the flyout menu (not on a
  plain click of the main part).
- Read when the flyout is built: the variant whose id equals the stored value
  becomes current; if the key is absent, the value is unknown (e.g. that
  variant does not exist in this FreeCAD version), or reading fails, the
  first variant is current. An unknown stored value is left untouched until
  the user picks again.
- Read/write failures are silent; they never break the ribbon.
- This key format is a compatibility contract: every JellyJams version
  keeps the same group and the same key/value format.
- This is a user preference, intentionally kept when the workbench is left
  or FreeCAD is closed; it is not part of the exact-restore stash and needs no
  crash recovery.

### 5.2 In-session state (not persisted)

Current tab, remembered pre-sketch tab, context flags, toggle state and
enabled states live only in memory. Hiding keeps them; quitting discards
them. On the next session the ribbon starts on **Features**.

### 5.3 Window state and crash safety

- The ribbon must never be stored as visible in FreeCAD's saved window
  layout: it is hidden on deactivation and, via the window-layout area's
  close guard, before FreeCAD saves `MainWindowState` on quit.
- After a crash, the next FreeCAD start does not create the dock until
  JellyJams is activated, so a stale saved layout cannot show it in other
  workbenches; the visibility guard covers any delayed re-show.
- No other recovery is needed because the ribbon changes no FreeCAD-owned
  parameter.

---

## 6. Edge cases and failure handling

### 6.1 Missing commands

- An entry whose command is not in `FreeCADGui.listCommands()` tries the
  layout's fallback commands in order; the first available one is used
  (log-level note naming both), e.g. "Convert Entities" uses
  `Sketcher_Projection`, else `Sketcher_External`.
- With no available command the entry is **skipped** and its id recorded.
  After the build, one warning lists how many commands were skipped and their
  ids (only if any).
- Missing flyout variants are dropped; a flyout with no variants left, an
  empty stack and an empty group produce nothing (no separator either).
- A toggle with a missing variant degrades as described in 2.3.

### 6.2 Messages (Report view, all prefixed `JellyJams: `)

Intent only; exact wording is free:

- info after each build: number of buttons, flyouts and tabs;
- warning: commands skipped because this FreeCAD version lacks them (count +
  ids);
- log: a fallback command substitutes a missing one;
- warning: a required FreeCAD GUI module could not be loaded (module +
  reason);
- log: Assembly command modules that could not be loaded;
- error: running a command failed (command + reason);
- warnings/errors of the feature-from-sketch gesture (3.6);
- log: FreeCAD's resource icons could not be indexed.

### 6.3 Robustness rules

- Nothing raised inside the ribbon (build steps per entry, icon lookup,
  tooltip composition, refresh, context checks, hooks into other areas,
  parameter access) may propagate into Qt or the workbench's
  `Activated()`/`Deactivated()`; failures are logged or silently ignored as
  listed above.
- `getInfo()` failure → treated as no info (tooltip falls back to the command
  id; icon lookup continues with other sources).
- `isActive()` failure → enabled.
- Context detection failure (no document, no MDI area, Assembly module
  missing) → "not in that context".
- A second `Activated()` while the ribbon exists must not rebuild or
  duplicate anything.
- The ribbon must never appear while another workbench is active, including
  right after a workbench switch (FreeCAD shows the next workbench's
  toolbars, then calls the old `Deactivated()` about 200 ms later, and may
  restore window state asynchronously afterwards).
- Autoload: if JellyJams is FreeCAD's start workbench, `Activated()` runs
  before the main window is shown and before FreeCAD restores the saved
  window state; the ribbon must be visible once the window is shown (the
  window-layout area calls show again; show is idempotent).
- A disabled flyout or toggle cannot be clicked, so its menu is also
  unavailable until its current command becomes active.

---

## 7. Acceptance criteria

Run in FreeCAD 1.1.x with a fresh user profile unless stated otherwise. "Wait
a refresh" means wait at least 0.6 s.

1. Activate JellyJams. The main window contains a `QDockWidget` with
   objectName `JellyJamsCommandManager` in the top dock area; it is visible, shows no title
   bar, and cannot be floated, moved or closed by the user.
2. The dock holds one `QTabWidget` (objectName `JellyJamsCommandManagerTabs`) whose tab bar
   is **below** the buttons; tab titles are exactly `Features`, `Sketch`,
   `Evaluate`, `Assembly`, `Drawing` in this order; `Features` is selected
   after the first activation.
3. The ribbon contains more than 20 `QToolButton`s, and the Report view shows
   one JellyJams info line with the numbers of buttons, flyouts and tabs.
4. On Features, "Extruded Boss/Base" is a large button with a 32 px icon and
   its text on two lines below the icon; "Swept Boss/Base", "Lofted
   Boss/Base", "Helical Boss/Base" form a small text-beside stack.
5. On Sketch, the drawing tools are small icon-only buttons in a grid exactly
   3 rows high, filled column by column (the 4th tool starts the second
   column).
6. Groups on every tab are separated by vertical lines (`JellyJamsGroupDivider`);
   no line appears at the left edge of a tab.
7. Hovering "Extruded Boss/Base" shows a tooltip whose first line is
   `Extruded Boss/Base — (FreeCAD: Pad)` (FreeCAD's menu text with
   accelerator and trailing ellipsis removed). A JellyJams command whose SW name
   equals its menu text shows the name alone, without "(FreeCAD: …)".
8. No ribbon tooltip contains HTML tags or `&` accelerator markers; a second
   tooltip line appears only when FreeCAD's description adds information
   beyond the names.
9. Every ribbon button for a FreeCAD command shows the same icon FreeCAD shows
   for that command in its own toolbars/menus; no add-on file is used as the
   icon of a non-`JellyJams_*` command. `JellyJams_*` buttons (e.g. "Make Drawing") show
   JellyJams icons.
10. On Evaluate, "Shaded With Edges", "Shaded", "Hidden Lines Removed",
    "Wireframe" show FreeCAD's draw-style icons; clicking "Shaded" with a 3D view open has
    the same effect as `FreeCADGui.runCommand("Std_DrawStyle", 5)`.
11. With no document open, Sketch tools (e.g. "Line", "Circle") are greyed
    out. Create a part and edit a sketch: within one refresh they become
    enabled; leave the sketch: within one refresh they are greyed out again.
12. Toggle: outside a sketch, the first Sketch-tab button reads "Sketch" and
    creates a sketch; while a sketch is edited it reads "Exit Sketch"
    (objectName `JellyJamsToggle-Sketcher_LeaveSketch`) and clicking it closes the
    sketch; afterwards it reads "Sketch" again within one refresh.
13. Flyout: the "Corner Rectangle" button has a menu arrow. Clicking its main
    part runs `Sketcher_CreateRectangle`. Choosing "Center Rectangle" from the
    arrow menu runs `Sketcher_CreateRectangle_Center` immediately, and the
    button now shows that variant's icon and tooltip; the next main-part click
    runs `Sketcher_CreateRectangle_Center` again.
14. After criterion 13, quit and restart FreeCAD and activate JellyJams: the
    rectangle flyout still shows "Center Rectangle". `user.cfg` contains under
    `BaseApp/Preferences/Mod/JellyJams/FlyoutChoices` the String
    `Sketcher_CreateRectangle` = `Sketcher_CreateRectangle_Center`.
15. Set that String to a nonexistent id and restart: the flyout shows its
    first variant ("Corner Rectangle"), no error is reported.
16. Every flyout tooltip ends with a line pointing to the arrow for more
    variants. The Assembly tab's "Mate" flyout keeps the caption "Mate"
    whatever mate was chosen, its icon follows the chosen mate, and its
    tooltip begins with `Mate: `.
17. Context, sketch: select the Evaluate tab, then edit a sketch → within one
    refresh the Sketch tab is selected. Click Features while still editing →
    Features stays selected across further refreshes. Leave the sketch → the
    Evaluate tab is selected again.
18. Editing a non-sketch feature (double-click a Pad) does not change the
    tab.
19. Context, drawing: open a TechDraw page window → the Drawing tab is
    selected. Click another tab while the page stays active → that tab stays.
    Switch to the 3D view and back to the page → Drawing is selected again.
    Leaving the page window never changes the tab.
20. Context, assembly: activate an assembly (`Gui.ActiveDocument.setEdit(asm)`
    on an `Assembly::AssemblyObject`) → the Assembly tab is selected within
    one refresh. Deactivating it does not change the tab.
21. Activating an assembly while a sketch is being edited does not leave the
    Sketch tab.
22. Sheet sketch: on a drawing page, use one of the Drawing tab's sheet-sketch
    tools (for example "Circle") → while its sheet sketch is edited the
    Sketch tab is selected; after "Exit Sketch" the Drawing tab is selected
    again.
23. Feature from open sketch: edit a closed-profile sketch inside a Body,
    switch to Features and click "Extruded Boss/Base" → the sketch closes, the
    Pad task panel opens with that sketch as its profile, and the ribbon is
    back on the tab that was selected before the sketch was entered.
24. With a sketch open, clicking "Fillet" does not close the sketch on
    JellyJams' initiative (FreeCAD's normal behavior). Without an open sketch,
    "Extruded Cut" behaves exactly like `PartDesign_Pocket` from Part Design.
25. Start "Centerline" (or "Midpoint Line") in a sketch, then click any other
    ribbon button → the centerline/midpoint mode has ended before the other
    command starts (newly drawn lines are no longer converted).
26. Switch to Part Design → the ribbon disappears and is still hidden 3 s
    later; FreeCAD's stock toolbars are visible.
27. Switch back to JellyJams → the ribbon is visible again with the same
    number of buttons as before (no duplicates), the previously selected tab
    still selected (unless a context transition applies) and flyout choices
    unchanged.
28. Quit FreeCAD while JellyJams is active (also with an unsaved document,
    choosing Discard), restart into Part Design → no ribbon is visible. With
    Cancel in the "Save changes?" prompt, the ribbon is visible again once the
    prompt closes.
29. Make JellyJams the autoload workbench and start FreeCAD → after the window
    appears, the ribbon is visible.
30. In a fresh profile where Sketcher, Part Design, TechDraw and Assembly were
    never opened, activating JellyJams first shows all Sketch, Features,
    Drawing and Assembly tab buttons (commands were loaded by the ribbon).
31. In a FreeCAD build lacking a layout command, that button is absent, other
    buttons are unaffected, and exactly one JellyJams warning lists the
    skipped ids. Where a fallback exists ("Convert Entities": `Sketcher_External`
    when `Sketcher_Projection` is missing) the button is present and runs the
    fallback.
32. A command that raises when run produces one JellyJams error line in the
    Report view; the ribbon keeps working.
33. Compare `user.cfg` before activating JellyJams and after leaving it: the
    ribbon added nothing outside `BaseApp/Preferences/Mod/JellyJams` (only
    `…/Mod/JellyJams/FlyoutChoices` entries for flyouts the user chose from).
34. "Rotate Component" (`JellyJams_RotateComponent`) on the Assembly tab is greyed out
    without an active assembly and its tooltip explains why; that explanation
    is not overwritten by subsequent refreshes.
35. While JellyJams is not the active workbench, programmatically showing the
    `JellyJamsCommandManager` dock (e.g. `dock.show()` from the Python console) results in
    the dock being hidden again immediately; inside JellyJams the guard
    never hides it.
36. The theme block (`/* @jellyjams-stylesheet-open */` … `/* @jellyjams-stylesheet-close */`) styles the
    ribbon: the tab pane, tool buttons, flyout split buttons and separators
    pick up the JellyJams colors (objectNames and popup mode as in 4.1).
37. Select Evaluate in part A, open part B and enter/leave a sketch, then return
    to A: B starts on Features, sketch entry selects Sketch, leaving restores
    Features, and A restores Evaluate. Drawing and assembly entry use their
    respective tabs without making a new part inherit them.
