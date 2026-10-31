# JellyJams 🪼

**SolidWorks-style UI for FreeCAD.**
Not affiliated with or endorsed by Dassault Systèmes.

Pick **JellyJams** in the workbench selector of FreeCAD 1.1 or later and the window starts to
feel like SolidWorks. A tabbed ribbon modelled on the CommandManager takes over from most stock
toolbars, buttons and tree entries use SolidWorks vocabulary, widget and viewport colors follow FreeCAD's light/dark theme, and the
mouse and keyboard follow SolidWorks habits. JellyJams is a regular FreeCAD workbench, so
moving to a different one reverts all of these changes.

## Features

### Interface

- **Appearances tab** beside Tasks, based on the official SOLIDWORKS appearance
  workflow. Browse Plastic, Metal and Paint presets, choose a custom colour,
  finish or transparency, then double-click a preset or click Apply Appearance.
  Select faces for local colouring, or select a whole body/part/component. Undo
  restores the previous appearance. Open it with **JellyJams > Appearances**.
  These are FreeCAD visual materials; textures, scenes and decals are not included.
- **CommandManager-style ribbon** at the top of the window with five tabs: **Features, Sketch,
  Evaluate, Assembly, Drawing**. Large buttons, three-row button stacks, and flyout buttons that
  remember the tool you picked last (also in later sessions).
- **SolidWorks tool names** on FreeCAD's own commands and icons: *Extruded Boss/Base, Extruded
  Cut, Hole Wizard, Shell, Smart Dimension, Convert Entities, Trim Entities, Zoom to Fit,
  Insert Components, Coincident/Distance, Concentric, Make Drawing, Standard 3 View, ...*. Each
  tooltip also names the FreeCAD command the button runs. Where FreeCAD has no exact counterpart
  of a SolidWorks tool, the label is the closest SolidWorks term or a descriptive name. Commands
  missing from your FreeCAD build are left out of the ribbon.
- **Automatic tab switching:** the ribbon shows the Sketch tab while you edit a sketch (and goes
  back to the previous tab afterwards), the Assembly tab when you activate an assembly, and the
  Drawing tab when a drawing sheet comes to the front.
- **SolidWorks-like window layout:** FreeCAD's toolbars are hidden except File, Edit and the
  workbench selector; Tasks and an already open Report view are docked on the right.
  A closed Report view stays closed. Close it with **View > Panels > Report view**
  or its X button, including inside JellyJams; a normal quit saves that choice
  for the next startup. FreeCAD's own auto-show settings still apply.
- **Light/dark widget and viewport colors matching FreeCAD**, with readable sketch geometry
  and dimensions. Under defined geometry is blue, fully defined geometry is black in light mode
  or green in dark mode, and over defined geometry is red. Your FreeCAD theme setting itself
  is never changed.
- **SolidWorks mouse-button mapping** using FreeCAD's native preset, with balanced horizontal
  and vertical orbit response on wide viewports. Orbit mode, pivot and sensitivity preferences
  are left unchanged.
- **SolidWorks keyboard shortcuts** while JellyJams is active:

  | Key | Action |
  |---|---|
  | `F` | Zoom to fit |
  | `Z` / `Shift+Z` | Zoom out / zoom in |
  | `Ctrl+B` | Rebuild (recompute) |
  | `Ctrl+1` ... `Ctrl+6` | Front, Back, Left, Right, Top, Bottom view |
  | `Ctrl+7` | Isometric view |
  | `Ctrl+8` | Normal To: look straight at the selected face, edge, plane or sketch; in a sketch with nothing selected, at the sketch plane |
  | `Space` | Orientation panel (see below) |

  FreeCAD commands that use one of these keys when you select JellyJams (for example Box Zoom on
  `Ctrl+B`, and Hide/Show on `Space`) are unbound while JellyJams is active and get their keys
  back when you leave. Where `Space` goes depends on the mouse pointer: over the 3D view and the
  model tree it always opens the panel, even if a check box you clicked a moment ago still has
  the keyboard focus. Elsewhere, for example over a task panel or dialog (also a floating one), a
  focused button, check box or drop-down list still gets `Space` (to click, tick or open it), and
  so does a list whose items you tick or type into. Toolbar, status-bar and ribbon controls, such
  as the workbench selector you just used, never take `Space`. Docks that open later, from
  another add-on for example, behave the same once you click into them.
- **Normal To on `Ctrl+8`**, as in SolidWorks: select **one** face, edge, plane or sketch and the
  view turns to look straight at it. Faces, edges, datum planes and axes go to FreeCAD's own
  *Align to Selection*, which also handles curved faces (it looks along a cylinder's axis); a
  whole sketch is looked at along its plane, also when you picked it through a link or an
  assembly component. While you edit a sketch with nothing selected (or only that sketch's own
  lines), it looks straight at the sketch plane. With nothing it can look at (nothing selected,
  two faces, a whole body), the status bar and a tip next to the pointer say so ("Normal To:
  select one face, edge, plane or sketch first."). It is also in the **JellyJams** menu and on
  the ribbon's Evaluate tab.
- **Orientation panel on `Space`**, like the SolidWorks Orientation dialog: press Space over the
  3D view and a small panel opens at the pointer with Normal To, *Remember this view* / *Go back
  to the remembered view*, Zoom to Fit, the six standard views laid out around Front, and
  Isometric, Trimetric and Dimetric. Click a view to turn the model; the panel closes, unless
  you pin it to try several views. Esc or Space closes it, and so does clicking anywhere else
  (unless it is pinned). You can also move through its buttons with Tab and press Space. `Space`
  and `Ctrl+8` also work while you edit a sketch or have a feature dialog open, and in an
  undocked or fullscreen 3D view, which keeps the keyboard when the panel closes; with the Start
  page or a drawing in front they do nothing. The panel is also in the **JellyJams** menu as
  *View Orientation*. Split viewports
  (two or four views) and the view selector cube are not available, because FreeCAD has no
  counterpart.
- **SolidWorks names in the tree** for new objects: `Sketch1`, `Boss-Extrude1`, `Cut-Extrude1`,
  `Fillet1`; origin planes `Top Plane`, `Front Plane`, `Right Plane`; `Assembly1` with a `Mates`
  folder and mates such as `Coincident1`; `Sheet1`, `Drawing View1` and similar in drawings. Only
  the tree label changes; FreeCAD's internal object names stay as they are.
- **SolidWorks terms in FreeCAD's task dialogs**, for example *Direction 1, End Condition, Blind,
  Through All, Mid Plane* in the Pad dialog. Only the displayed text changes; the dialogs are
  still FreeCAD's own.

### Sketching

- Opening a sketch keeps you in JellyJams (no jump to the Sketcher workbench).
- **Sketch first:** press *Extruded Boss/Base* (or *Extruded Cut*, *Revolved Boss/Base*,
  *Revolved Cut*, *Hole Wizard*) when there is no sketch to use, and a new sketch opens instead
  of FreeCAD's "No sketch to work on" warning: pick a plane (or select a plane or flat face
  first), draw the profile, click *Exit Sketch*, and the feature starts on that sketch. If a
  finished sketch is already there, the feature uses it as before. The cut features (*Extruded
  Cut*, *Revolved Cut*, *Hole Wizard*) do this only once the body has a solid feature (a Pad,
  for example) to cut; before that FreeCAD tells you right away that there is nothing to cut,
  and for *Hole Wizard* the status bar says that it needs a solid to cut into. With several
  bodies and none active, FreeCAD first asks which body to work in, as without JellyJams.
- Pressing a feature button such as *Extruded Boss/Base* while a sketch is open closes the
  sketch and starts the feature on it.
- Creating or editing a feature (for example double-clicking a Pad) keeps you in JellyJams with
  the ribbon on screen; FreeCAD would otherwise switch to Part Design. Choosing another
  workbench in the workbench selector still works as usual.
- **Sketch straight from a face:** a new sketch on a flat face is two clicks away. Click the
  face in the 3D view (outside an assembly) and a small *Sketch* button comes up beside the
  cursor; click that button and the sketch opens, attached to the face. If you move on
  instead, the button dims and goes away.
- **Centerline** (lines become construction geometry) and **Midpoint Line** (you draw from the
  midpoint and the line is mirrored to the other side).
- **Add Relations panel** at the top of the Tasks panel: lists the selected entities and their
  existing relations (which you can delete), and offers only the relations FreeCAD accepts for
  the selection.

### Assembly

- **New Assembly** creates the assembly in a new document.
- **Add Mate panel**: select entities of the active assembly and pick a fitting mate
  (Coincident, Parallel, Perpendicular, Concentric, Distance, Angle, Hinge, Slider, Ball Joint);
  each runs FreeCAD's matching joint command.
- Drag `.FCStd` files from your file browser into FreeCAD to insert them as components of the
  active assembly.
- Activating an assembly keeps you in JellyJams instead of switching to the Assembly workbench.
  The same goes for a Part Design body becoming active (for example after you leave a sketch)
  and for double-clicking a drawing page.
- **Rotate Component**: rotate one floating, unmated component with the mouse.

### Drawing

- **Make Drawing** creates a separate drawing document for the open part or assembly: one sheet
  with an ISO title block from the templates installed with FreeCAD, and a Standard 3 View.
- **Sheet Properties**: sheet format, first or third angle projection, and title-block texts.
- **Projected View**, automatic **section and detail view labels** (`A-A`, `Z (2:1)`, ...),
  a **View Scale** menu of standard scales, and dragging a view by any of its edges or faces.
- **Sketch shapes** (line, rectangle, circle, arc, polygon, with Sketcher relations and
  dimensions) and **Note** text directly on the sheet; **Insert Picture** (SVG, PNG, JPG, BMP).
- **Surface Finish** (ISO 1302) and **Weld Symbol** (ISO 2553) symbols that stay editable;
  **Line Format** opens FreeCAD's line dialog with ISO 128 thickness presets.
- **Save as PDF** (all sheets in one file) and **Save as DXF** (one file per sheet).
- **Thinner lines up close:** small features stay easy to pick for dimensioning, because
  edges and vertex dots on a sheet get thinner in steps the further you zoom in. Only the
  screen changes; saved files, printouts and exports keep the standard widths.

### Clean restore

- **Leaving the workbench** or **quitting FreeCAD** while JellyJams is active puts back exactly
  what JellyJams changed: toolbars and docks, theme, 3D view colors, navigation style, keyboard
  shortcuts and the "switch to workbench" settings of Assembly, Part Design and TechDraw. A
  preference that had no entry in
  your configuration beforehand has none afterwards either, so FreeCAD's built-in default
  keeps applying to it.
- If you **cancel** FreeCAD's "Save changes?" prompt while quitting, the JellyJams interface
  comes back.
- **After a crash**, the next FreeCAD start restores the saved settings JellyJams had changed
  (3D view colors, navigation style, shortcuts, the three "switch to workbench" settings) from
  its backups.

### Diagnostics

**Diagnostics** (on the ribbon's Evaluate tab, and in the **JellyJams** menu) shows FreeCAD and
JellyJams environment details with a **Copy to clipboard** button, for bug reports.

## Requirements

- FreeCAD **1.1.0 or newer**. Developed and tested on FreeCAD 1.1.4 on Windows.
- Nothing else: JellyJams uses only the Python, Qt and modules bundled with FreeCAD.

## Install

### Addon Manager (custom repository)

1. In FreeCAD open **Edit > Preferences > Addon Manager**.
2. Under **Custom repositories** add an entry:
   - Repository URL: `https://github.com/jus-kim/JellyJams`
   - Branch: `main`

   The branch must be set: left empty, it defaults to `master`, but JellyJams is published on
   `main`.
3. Click **OK**, open **Tools > Addon manager**, select **JellyJams**, click **Install** and
   restart FreeCAD.
4. Select **JellyJams** in the workbench selector.

### Developer install (Windows)

Link your clone into FreeCAD's add-on folder with a directory junction, then restart FreeCAD:

```powershell
New-Item -ItemType Junction `
  -Path "$env:APPDATA\FreeCAD\v1-1\Mod\JellyJams" `
  -Target "C:\path\to\your\JellyJams\clone"
```

Install only one copy. If FreeCAD finds JellyJams twice, it uses the first copy and prints a
warning about the second.

## Usage

- **Turn it on:** select **JellyJams** in the workbench selector.
- **Turn it off:** select any other workbench. FreeCAD's own layout, theme, navigation and
  shortcuts come back immediately.
- **Tooltips** show the SolidWorks name and the FreeCAD command each button runs.
- **Flyout buttons** (with a small arrow) hold several tools. Pick one from the arrow menu; it
  runs and stays on the button.
- **Reporting a problem:** copy the text from **JellyJams > Diagnostics** into an issue on the
  [GitHub repository](https://github.com/jus-kim/JellyJams).

### Settings

Two optional switches live in **Tools > Edit parameters** under
`BaseApp/Preferences/Mod/JellyJams` (both Boolean, default `true`):

| Key | Effect when set to `false` |
|---|---|
| `ShowSketchButtonOnFace` | No Sketch icon appears next to a clicked face. Takes effect immediately. |
| `SilenceGlyphWarnings` | Qt's "render glyph failed" warnings (logged when you zoom far into a drawing sheet) are no longer hidden from the Report view. Takes effect at the next FreeCAD start. |

JellyJams also keeps your flyout choices (group `Mod/JellyJams/FlyoutChoices`) and the last text
height and unit of the Text command (`LastNoteHeight`, `LastNoteUnit` in `Mod/JellyJams`).

### Uninstall

Switch to another workbench first, then remove JellyJams in the Addon Manager (or delete the
junction). Your JellyJams preferences stay in the `Mod/JellyJams` parameter group, and
third-angle sheet templates derived from FreeCAD's templates stay cached in the
`JellyJams/templates` folder of your FreeCAD user data folder; both can be deleted.

## Status

Version 0.1.0, first release. On FreeCAD 1.1.4 for Windows, automated GUI tests cover the ribbon
(all five tabs), theme, navigation, shortcuts, tree naming of a sketch, a pad and the origin
planes, the Assembly setting override, sketch first for *Extruded Boss/Base*, staying in
JellyJams while a feature is edited, the Orientation panel on Space, and the restore of the theme, navigation style, shortcuts,
Assembly setting, toolbars and ribbon on leave, on quit (including a cancelled quit) and with
JellyJams autoloaded at startup. They also cover Normal To on `Ctrl+8` and on the Evaluate tab
(on curved faces, datums and a sketch shown through a link), `Space` and `Ctrl+8` in a sketch, in
an undocked 3D view and with the Start page in front, `Space` on a focused check box with the
pointer over the dialog and over the 3D view and in a dock opened later, and *Hole Wizard* in a
body without a solid and with several bodies. All GUI results were recorded on 2026-10-28.
The restored 3D view color values, startup crash recovery and the other sketch, assembly and drawing tools are covered by tests of their logic outside the FreeCAD GUI,
not yet by GUI tests; a real crash has not been tested. Installing from the published repository
through the Addon Manager has not been tested yet. Linux and macOS are not verified.

Details: [docs/status.md](docs/status.md). All documentation: [docs/README.md](docs/README.md).

## Tests

See [docs/testing.md](docs/testing.md). In short, the headless suite runs with FreeCAD's bundled
Python and stubbed FreeCAD modules (no FreeCAD window opens):

```powershell
& "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_headless.py
```

The `tests/gui_*.py` scripts drive the real FreeCAD GUI and must be run with throwaway config
files so your own FreeCAD settings are never touched.

## Contributing

Read [AGENTS.md](AGENTS.md) (rules and workflow for contributors and coding agents) and
[docs/README.md](docs/README.md) first.

## Icons and drawing templates

JellyJams bundles no third-party assets.

- The workbench icon and the icons of JellyJams' own commands in `resources/icons/` are original
  artwork made for this project (LGPL-3.0-or-later, like the code).
- Ribbon buttons for FreeCAD commands show FreeCAD's own icons, looked up at runtime from your
  FreeCAD installation.
- New drawings use the ISO TechDraw templates installed with FreeCAD, found at runtime.
  Third-angle variants are derived from them when needed and cached in your FreeCAD user data
  folder.

## License

JellyJams is licensed under the **GNU Lesser General Public License v3.0 or later**
(LGPL-3.0-or-later). See [LICENSE](LICENSE) and [LICENSES/](LICENSES). Copyright (c) 2026 jus-kim.

SolidWorks is a trademark of Dassault Systèmes. JellyJams uses the name only to describe the
style of interface it provides and ships no Dassault Systèmes assets.
