# AGENTS.md

Guidance for AI coding agents and human contributors working on JellyJams.
Read this file completely before changing anything.

## 1. What JellyJams is

JellyJams is a FreeCAD 1.1+ workbench (a pure-Python add-on) that gives FreeCAD a
SolidWorks-style UI while it is the active workbench:

- a CommandManager-style ribbon with the tabs Features, Sketch, Evaluate, Assembly and Drawing,
  running FreeCAD's own commands under SolidWorks tool names,
- SolidWorks names in the model and drawing tree, and SolidWorks terms in FreeCAD's task dialogs,
- widget and 3D view colors following FreeCAD's light/dark theme, SolidWorks mouse navigation and SolidWorks keyboard shortcuts,
  including the Orientation panel on `Space` and Normal To on `Ctrl+8`,
- sketch, assembly and drawing helpers (Add Relations / Add Mate panels, Make Drawing, Projected
  View, drawing symbols, PDF/DXF export and more),
- **exact restore** of FreeCAD's stock UI and settings when the user leaves the workbench, quits
  FreeCAD, or starts FreeCAD again after a crash.

| Fact | Value |
|---|---|
| Workbench key / class | `JellyJamsWorkbench` (MenuText `JellyJams`) |
| Version | single source: `__version__` in [jellyjams/\_\_init\_\_.py](jellyjams/__init__.py); mirrored in [package.xml](package.xml) and [CHANGELOG.md](CHANGELOG.md) |
| Minimum FreeCAD | 1.1.0 (developed and tested on FreeCAD 1.1.4, Windows) |
| Runtime | Python 3.11 and PySide6 as bundled with FreeCAD; standard library only, no third-party packages |
| License | MIT, (c) 2026 jus-kim ([LICENSE](LICENSE), [LICENSES/](LICENSES)) |
| Repository | https://github.com/jus-kim/JellyJams (branch `main`) |

"SolidWorks" is used only as descriptive terminology. JellyJams is not affiliated with or
endorsed by Dassault Systèmes.

## 2. Read first

1. [docs/README.md](docs/README.md): index of every document and the reading order.
2. [docs/status.md](docs/status.md): what is implemented, what is verified and how, and what is open.
3. [docs/architecture.md](docs/architecture.md): module map, lifecycle order, persisted state,
   error isolation and step-by-step checklists for extending JellyJams.
4. The spec of the area you are about to touch, in [docs/specs/](docs/specs/) (the module-to-spec
   map is in [docs/specs/README.md](docs/specs/README.md) and in section 4 below).
5. When a change depends on how FreeCAD behaves: [docs/freecad-facts.md](docs/freecad-facts.md),
   and [docs/decisions.md](docs/decisions.md) for why the design is the way it is.

The specs in `docs/specs/` are the normative description of behavior. If the code and a spec
disagree, treat it as a bug: either fix the code or change the spec on purpose, and record the
decision in `docs/status.md`.

## 3. Non-negotiable rules

| # | Rule | Enforced by |
|---|---|---|
| R1 | **License header.** Every Python file (`jellyjams/`, `tests/`, `Init.py`, `InitGui.py`) starts with exactly the three lines below, UTF-8 without BOM. XML and SVG files carry the same two SPDX lines in an XML comment directly after the XML declaration (see [resources/icons/jellyjams.svg](resources/icons/jellyjams.svg), [package.xml](package.xml)). | `Test02Hygiene.test_three_line_header`, `Test21Icons` |
| R2 | **No "SolidWorks" (any case) in identifiers**: not in module, class or function names of the add-on, command ids, Qt objectNames, parameter groups and keys, document property names, file or folder names, or icon file names. It is allowed only in user-visible labels, tooltips, messages, comments and docs (and in test names that check this rule). Command ids are `JellyJams_` plus the tool's ribbon name without spaces (`JellyJams_RotateComponent`); objectNames are `JellyJams` plus a role word (`JellyJamsCommandManager`). | `Test02Hygiene.test_no_solidworks_in_file_names`, `test_no_solidworks_in_identifiers` |
| R3 | **English only.** All user-visible text, code comments and docs are English. There is no translation layer. | review |
| R4 | **Exact restore.** Every change JellyJams makes to FreeCAD parameters or UI must be undone exactly on leave, on quit and after a crash (details below). | headless suites 04, 06, 07, 10, 11, 12, 17; `tests/gui_smoke.py`, `tests/gui_lifecycle.py`, `tests/check_saved_cfg.py` |
| R5 | **Never touch the user's real FreeCAD profile in tests.** The headless suite uses stubs and a temporary data folder. GUI scripts run only with throwaway config files (`-u` / `-s`) under `scratch/`. Never run a GUI test script against the default `user.cfg`, and never write to `%APPDATA%\FreeCAD\v1-1\user.cfg` or `system.cfg`. | review |
| R6 | **No bundled third-party assets.** Ribbon buttons for FreeCAD commands use FreeCAD's own icons, looked up at runtime. New drawings use the ISO TechDraw templates installed with FreeCAD. Icons under `resources/icons/` are original artwork. | `Test21Icons`, review |

The exact header for R1:

```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 jus-kim <hi@jus.kim>
```

### 3.1 Exact restore (R4) in detail

FreeCAD saves all parameters and the main-window layout when it exits, and it never calls
`Deactivated()` on quit. Anything JellyJams leaves behind would therefore reach the user's next
session and every other workbench. The rules:

- **Back up before the first write.** Record the previous value *or the fact that the key was
  absent*. Restoring removes keys that were absent; it never writes a "default".
- **Persist the backup** as a string in `User parameter:BaseApp/Preferences/Mod/JellyJams` so
  that [jellyjams/recovery.py](jellyjams/recovery.py) can restore it at the next start after a
  crash. Current backup keys (`constants.BACKUP_KEYS`): `OriginalViewColors`,
  `OriginalNavigationStyle`, `OriginalShortcuts`, `OriginalSwitchToWB`,
  `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB`. Their formats are on-disk
  contracts; do not change them without keeping old backups readable.
- **Never overwrite a pending backup.** A leftover backup holds the real originals.
- **Cover all three exit paths:** `DEACTIVATION_STEPS` (leave), `QUIT_REVERT_STEPS` and
  `QUIT_REAPPLY_STEPS` (quit, and quit cancelled at the "Save changes?" prompt) in
  [jellyjams/lifecycle.py](jellyjams/lifecycle.py) driven by
  [jellyjams/quit_guard.py](jellyjams/quit_guard.py), and startup recovery.
- **Theme:** only the main window's own stylesheet is touched, with exactly one block between
  `/* @jellyjams-stylesheet-open */` and `/* @jellyjams-stylesheet-close */`. Never call `QApplication.setStyleSheet`,
  never write `Preferences/MainWindow` (`StyleSheet`, `Theme`), never call `setStyleSheet` on
  FreeCAD-owned widgets.
- **Layout:** restore only what JellyJams changed. FreeCAD shows the next workbench's toolbars
  before it calls the old workbench's `Deactivated()`, so a blanket `restoreState()` would hide them.
- JellyJams registers no `QToolBar` of its own (the ribbon is a `QDockWidget` named `JellyJamsCommandManager`).
- Checklist for a **new** persistent override: backup key in
  [jellyjams/constants.py](jellyjams/constants.py) (`BACKUP_KEYS`), a recovery step in
  `recovery.py`, entries in the activation, deactivation, quit-revert and quit-reapply tables,
  headless tests (apply, restore, absent key, leftover backup, corrupt backup), and the key in
  [tests/check_saved_cfg.py](tests/check_saved_cfg.py) and the GUI scripts' backup lists. Full
  steps: [docs/architecture.md](docs/architecture.md) section 12.4.

### 3.2 Code conventions that tests or FreeCAD depend on

- **Qt:** `from PySide import QtCore, QtGui, QtWidgets` (FreeCAD's shim over PySide6). Widgets
  come from `QtWidgets`. Use Qt 6 scoped enums (`QtCore.Qt.DockWidgetArea.TopDockWidgetArea`).
  Check `fcgui.is_alive(obj)` before reusing a Qt object FreeCAD may have deleted.
- **Imports:** a module's top level imports only the standard library, `FreeCAD`, `FreeCADGui`,
  `PySide` and the shared core modules (`constants`, `console`, `params`, `paths`, `fcgui`,
  `doc_utils`, `commands`) plus modules of its own area. Other areas and FreeCAD workbench modules
  (`Part`, `Sketcher`, `TechDraw`, `UtilsAssembly`, ...) are imported lazily inside functions, in a
  guarded call.
- **Pure modules** import nothing from FreeCAD or PySide and must run under plain Python:
  `jellyjams/__init__.py`, `constants`, `palette`, `ribbon_layout`, `ribbon_model`,
  `ribbon_text`, `naming_rules`, `relations_rules`, `mate_rules`, `dialog_terms_data`,
  `pdf_merge`, `orbit_rules`, `appearance_rules`. Put new rules logic in a pure module so it can be unit-tested.
- **Boundaries never raise.** Workbench methods, command `GetResources/Activated/IsActive`,
  observers, event filters, timers and slots catch everything (`console.guard`,
  `console.guarded`, `console.safe_call`). Event filters return `False` on internal failure.
  One failing lifecycle step never stops the next one (`lifecycle.run_steps`).
- **Idempotency.** Every `install/enable/start/apply/show` is safe to call twice; every
  `uninstall/disable/stop/restore/hide/revert` is safe to call when nothing is installed.
- **Output** goes through [jellyjams/console.py](jellyjams/console.py) (prefix `JellyJams: `).
  No error pop-ups; errors go to the Report view.
- **Shared literals** (command ids, objectNames, parameter paths and keys, type ids, property
  names) live in [jellyjams/constants.py](jellyjams/constants.py). Do not repeat them.
- **Document properties** that JellyJams adds live in the property group `JellyJams` (for example
  `SymbolType`, `WeldSettings`, `HostSheet`) and are stored in users' `.FCStd` files. Treat their
  names and formats as a file-compatibility contract.
- **[InitGui.py](InitGui.py)** is run by FreeCAD with `exec()`: there is no `__file__`, and
  top-level names are not visible inside the class body or its methods. Class bodies hold only
  literals; methods import what they need.

### 3.3 FreeCAD behavior worth knowing

| Fact | Consequence in JellyJams |
|---|---|
| On quit FreeCAD never calls `Deactivated()`, then saves parameters and window state. | Direct `mainWindowClosed` hook in `quit_guard.py` reverts after accepted save prompts and before layout persistence. Early-Close/poll fallback only if the signal is unavailable. |
| On a workbench switch FreeCAD shows the next workbench's toolbars first and calls `Deactivated()` about 200 ms later. | `layout.revert()` restores only the toolbars JellyJams hid. |
| With autoload, `Activated()` runs before the main window is shown. | `layout.apply()` defers until the window is visible. |
| Qt fires neither action when two live actions share a shortcut (FreeCAD 1.1: Box Zoom owns `Ctrl+B`, Hide/Show owns `Space`). | `shortcuts.py` unbinds conflicting commands while active and restores them. |
| FreeCAD creates a command's `QAction`, and so a working keyboard shortcut, only when the command is in a menu or toolbar; a ribbon button (`runCommand`) does not count. Those actions repeat a held key. | `JellyJams_ViewOrientation` and `JellyJams_NormalTo` are listed in the JellyJams menu so that `Space` and `Ctrl+8` work (decision D-17); View Orientation's key repeat is switched off. |
| A Python command that declares no `CmdType` counts as changing the document, and FreeCAD disables such commands while a task dialog is open, a sketch in edit included (`Gui.Control.isAllowedAlterDocument()` is False). | `BaseCommand.cmd_type`: set it to `Alter3DView` only for a command that just moves the camera (the two orientation commands, decision D-18). Leave it empty for everything else. |
| A window-wide shortcut takes its key from focused buttons, check boxes, combo boxes and lists (line edits keep typed keys). Controls keep the focus after a click (a check box in a dialog, the workbench selector, status-bar buttons). Key events travel only up to their window, and a floating dock is a window of its own; docks can appear at any time. FreeCAD's 3D view is `Gui::View3DInventor`, the parent of its drawing area in every 3D view `Gui::View3DInventorViewer`, a split 3D view `Gui::AbstractSplitView` (`SplitView3DInventor` has no Qt class name of its own), its model tree `Gui::TreeWidget`. | While JellyJams is active, one event filter object on the main window and on every dock (never on the application; a dock made later gets it when one of its widgets takes the focus, through `QApplication.focusChanged`) decides a plain `Space` by the pointer first: over a 3D view, a viewer, a split view or the model tree it is always for the panel; elsewhere a focused button, check box or combo box, or a list with a checkable current item or typing edits, keeps it, and toolbar, status-bar and ribbon controls never do. The panel's own buttons keep Space wherever the pointer is (decision D-18). |
| `Std_AlignToSelection` needs exactly one pick; with one it decides itself what it can align to (curved faces, straight B-spline edges, planar curves, whole datums and single-face or single-edge objects too, through links), but a whole sketch usually does nothing; it says nothing when it does nothing and has no sketch rule. `Sketcher_ViewSketch` looks at the sketch plane. FreeCAD's view commands act on the main window's active window (`getMainWindow().getActiveWindow()`), which follows an undocked or fullscreen view; `FreeCADGui.activeView()` keeps naming the document's 3D view while the Start page or a drawing is in front. A sketch's `getGlobalPlacement()` ignores links; `FreeCAD.GeoFeature.getGlobalPlacementOf` follows the selection path. | `JellyJams_NormalTo` (`Ctrl+8`, the panel, the Evaluate tab) uses `Sketcher_ViewSketch` in a sketch, `Std_AlignToSelection` for any one sub-element, whole datum or one-face or one-edge object, turns the view in front itself (`setCameraOrientation`) for one whole sketch along its unresolved selection path, and otherwise shows the hint in the status bar and as a tool tip. Both orientation commands are active while the main window's active window has `getCameraNode` (`activeView()` only without `getActiveWindow`). |
| FreeCAD's `Body::isSolid()` is true when the body holds any non-datum Part Design feature. Pocket and Groove refuse in a body without one; Hole does not (it builds a failing Hole). With several bodies and none active, FreeCAD asks which body to work in. | `sketch_gesture._has_solid` copies that rule; in a known target body without one, Pocket and Groove go to FreeCAD's refusal and Hole is refused by JellyJams with a status-bar message (`_refuse_without_solid`); without a target body all three are left to FreeCAD (`_nothing_to_cut` is true only for a known body). |
| Assembly commands exist only after the Assembly workbench's command modules are imported. | `fcgui.preload_command_modules()` before building the ribbon and in New Assembly. |
| FreeCAD silently de-duplicates labels. | Naming computes numbers from the labels of all other objects. |
| Part Design switches to its workbench on every feature `setEdit` (no preference) by running the command string `Gui.activateWorkbench(...)`, the same call the workbench selector makes. | `edit_guard.py` wraps `FreeCADGui.activateWorkbench` while active: command-string requests (a `<string>` frame up to `FRAME_SEARCH_DEPTH` frames above the wrapper, so other add-ons' wrappers do not hide it) wait one event-loop turn and are dropped only when an edit started. Python callers pass straight through. |
| Assembly, Part Design (body activation, e.g. leaving a sketch) and TechDraw (page double-click) switch workbenches while their `SwitchToWB` is true or missing. | `switch_prefs.py` holds all three at false with exact restore and crash recovery. |

More verified FreeCAD 1.1 behavior: [docs/freecad-facts.md](docs/freecad-facts.md).

## 4. Repo map

| Path | What it is |
|---|---|
| [Init.py](Init.py) | Headless entry; intentionally empty (JellyJams is GUI-only). |
| [InitGui.py](InitGui.py) | Registers `JellyJamsWorkbench` (warns and skips a second copy) and runs startup crash recovery. |
| [package.xml](package.xml) | Addon Manager manifest (format 1, branch `main`, `freecadmin` 1.1.0). |
| [CHANGELOG.md](CHANGELOG.md) | Release notes; heading format `## <version> — <date>` is tested. |
| [jellyjams/](jellyjams/) | The package (flat, one level). Modules by area below. |
| [resources/icons/](resources/icons/) | Workbench icon and the original icons of the JellyJams commands, three relation buttons and two Orientation panel fallbacks. |
| [tests/](tests/) | Headless suite, GUI acceptance scripts and the saved-config checker. |
| [docs/](docs/) | Documentation; start at [docs/README.md](docs/README.md). |
| `scratch/` | Git-ignored output of GUI test runs and throwaway config copies. Never commit it. |

Modules by area, with the spec that defines each area's behavior:

| Area | Modules (in `jellyjams/`) | Spec |
|---|---|---|
| Core: entry, lifecycle, quit guard, crash recovery, commands, diagnostics, Qt message filter, navigation, shortcuts | `__init__`, `constants`, `console`, `params`, `paths`, `fcgui`, `doc_utils`, `commands`, `recovery`, `lifecycle`, `quit_guard`, `qt_filter`, `diagnostics`, `navigation`, `orbit`, `orbit_rules`, `shortcuts` | [core.md](docs/specs/core.md) |
| Window layout | `layout` | [window-layout.md](docs/specs/window-layout.md) |
| Look: theme, 3D background, sketch colors | `palette`, `theme`, `viewport` | [look.md](docs/specs/look.md) |
| Appearances: colour/finish library, native face/object/component edits and browser dock | `appearance_rules`, `appearances` | [appearances.md](docs/specs/appearances.md) |
| Ribbon engine | `ribbon`, `ribbon_model`, `ribbon_text`, `ribbon_widgets`, `icons` | [ribbon-engine.md](docs/specs/ribbon-engine.md) |
| Ribbon content (what each tab holds) | `ribbon_layout` | [ribbon-content.md](docs/specs/ribbon-content.md) |
| Temporary measurement task and callouts | `measure` | [measure.md](docs/specs/measure.md) |
| Tree naming | `naming`, `naming_rules` | [naming.md](docs/specs/naming.md) |
| SolidWorks terms in task dialogs, ISO 128 presets row | `dialog_terms`, `dialog_terms_data` | [dialog-terms.md](docs/specs/dialog-terms.md) |
| Sketching: stay in JellyJams while sketching and while features are edited, feature from open sketch, sketch first, Sketch context icon, Centerline, Midpoint Line | `sketch_edit`, `edit_guard`, `sketch_gesture`, `sketch_tools`, `context_sketch` | [sketching.md](docs/specs/sketching.md) |
| Add Relations panel | `panel_host` (shared with Add Mate), `relations_rules`, `relations_panel` | [relations.md](docs/specs/relations.md) |
| Assembly: Add Mate panel, file drop, switch-to-workbench overrides (Assembly, Part Design, TechDraw), New Assembly, Rotate Component | `mate_rules`, `mate_panel`, `assembly_drop`, `switch_prefs`, `assembly_commands` | [assembly.md](docs/specs/assembly.md) |
| Drawing sheet: Make Drawing, Sheet Properties, templates, shapes, Text, Insert Picture, on-sheet picking | `drawing_common`, `sheet_pick`, `templates`, `make_drawing`, `sheet_properties`, `sheet_sketch`, `sheet_text`, `insert_picture` | [drawing-sheet.md](docs/specs/drawing-sheet.md) |
| Drawing views: Projected View, section/detail labels, Scale, view dragging, zoom line widths | `projected_view`, `view_labels`, `view_scale`, `sheet_drag`, `zoom_lines` | [drawing-views.md](docs/specs/drawing-views.md) |
| Drawing symbols and export: Surface Finish, Weld Symbol, Line Format, PDF/DXF | `surface_finish`, `weld_symbol`, `line_format`, `drawing_export`, `pdf_merge` | [drawing-symbols-export.md](docs/specs/drawing-symbols-export.md) |
| View orientation: the Orientation panel on `Space` (`JellyJams_ViewOrientation`), Normal To on `Ctrl+8` and the Evaluate tab (`JellyJams_NormalTo`), the Space filter (pointer rule, focused controls, docks, docks made later), the keyboard given back to the window that had it | `orientation` (its keys live in `shortcuts`, its Evaluate entry in `ribbon_layout`) | [orientation.md](docs/specs/orientation.md) |

Common entry points for changes (complete checklists, including which test expectations to
update: [docs/architecture.md](docs/architecture.md) section 12):

| To change | Edit |
|---|---|
| What a ribbon tab contains (buttons, labels, flyouts) | `TABS` in [jellyjams/ribbon_layout.py](jellyjams/ribbon_layout.py) only; the engine does not change. Update the `RIBBON_*` expectations in `tests/test_headless.py` (used by `Test13RibbonModel` / `Test13RibbonBuild`) and the tables in [docs/specs/ribbon-content.md](docs/specs/ribbon-content.md). |
| Order of what happens on enter / leave / quit | Step tables in [jellyjams/lifecycle.py](jellyjams/lifecycle.py) (`Test06Lifecycle` pins the order). |
| SolidWorks keyboard shortcuts | `SHORTCUTS` in [jellyjams/shortcuts.py](jellyjams/shortcuts.py) (pinned by `EXPECTED_SHORTCUTS` in `tests/test_headless.py`; the key table is [core.md](docs/specs/core.md) 4.8). A key for a JellyJams command also needs that command in the JellyJams menu (`lifecycle._add_menu_once`), or the key does nothing. |
| Colors | [jellyjams/palette.py](jellyjams/palette.py) only (contrast pairs are tested against WCAG thresholds). |
| A new `JellyJams_<ToolName>` command | `CMD_*` constant plus `ALL_COMMANDS` and `COMMAND_ICONS` in `constants.py`, a provider module with `get_commands()` listed in `commands.PROVIDERS`, an original SVG icon, a ribbon entry (or, for a command deliberately kept off the ribbon such as `JellyJams_ViewOrientation`, an entry in `OFF_RIBBON_COMMANDS` in the tests), `cmd_type` only if it just moves the camera, tests. |

## 5. Running the tests

Full instructions, including how to prepare each GUI mode: [docs/testing.md](docs/testing.md).
Current results: [docs/status.md](docs/status.md).

**Headless suite** (fast, no FreeCAD window; FreeCAD and FreeCADGui are stubbed, Qt runs offscreen;
run it before every commit):

```powershell
& "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_headless.py        # exit code 0 = all pass
& "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_headless.py -v -k Ribbon
```

Set `JELLYJAMS_ECHO_CONSOLE=1` to echo the captured FreeCAD console output.

**GUI acceptance scripts** run inside the real FreeCAD GUI, always with throwaway config files
(rule R5). FreeCAD loads JellyJams from its `Mod` folder, so the add-on must be installed (for
example with the developer junction from [README.md](README.md)). The `-u` / `-s` flags replace
only the two config files; FreeCAD still uses its normal user data folder for add-ons and caches.

```powershell
$fc = "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe"
& $fc -u scratch\test_user.cfg -s scratch\test_system.cfg tests\gui_smoke.py   # ribbon, theme, navigation, shortcuts, naming, restore
& $fc -u scratch\tabs_user.cfg -s scratch\tabs_system.cfg tests\gui_tabs.py    # all five tabs, screenshots
& $fc -u scratch\orientation_user.cfg -s scratch\orientation_system.cfg tests\gui_orientation.py   # Space, Orientation panel, Normal To (Ctrl+8)
& $fc -u scratch\sketchfirst_user.cfg -s scratch\sketchfirst_system.cfg tests\gui_sketch_first.py # sketch first, feature edits
$env:JELLYJAMS_LIFECYCLE_MODE = "cancel"   # or discard / after / autoload (after follows discard; autoload needs a prepared config)
& $fc -u scratch\cancel_user.cfg -s scratch\cancel_system.cfg tests\gui_lifecycle.py
# after the discard mode: check the user.cfg FreeCAD saved on quit; the two expected values are
# info.nav_before and info.switch_before in scratch\lifecycle_discard.json
python tests\check_saved_cfg.py scratch\discard_user.cfg $navBefore $switchBefore
```

The scripts quit FreeCAD themselves and write JSON results and screenshots to `scratch/` (or to
the folder in `JELLYJAMS_RESULTS_DIR`). Read the JSON; console output is not reliable on Windows.

## 6. Workflow expectations

- **Same change, same commit:** code, tests, the relevant `docs/specs/<area>.md`, and
  [docs/status.md](docs/status.md). A behavior change without a spec update is incomplete.
- **Add tests.** Logic goes into a pure module or a stub-testable function with a headless test.
  UI or lifecycle behavior that the stubs cannot show gets a check in a GUI script.
- **Report honestly.** Record in `docs/status.md` what you ran and the result. Anything not run on
  real FreeCAD is "not verified"; never mark it as working.
- **Run the headless suite** before every commit. Run the GUI scripts when you touched lifecycle,
  layout, theme, viewport, navigation, shortcuts, ribbon building or the quit guard.
- **Keep the tests' pinned facts deliberate.** `tests/test_headless.py` pins constants, ribbon
  counts, step-table order and release metadata. Change the test in the same change only when
  the new value is intended.
- **Releases:** bump `__version__` in `jellyjams/__init__.py`, `version` and `date` in
  `package.xml`, and add a `## <version> — <date>` section to `CHANGELOG.md` (all three are
  cross-checked by `Test01ReleaseMetadata`).
- **Do not commit** `scratch/`, `__pycache__/` or config copies.
- **Icons:** original SVG, `viewBox="0 0 64 64"`, readable at 16-20 px, SPDX comment header,
  no `<text>`, `<style>`, `<image>`, `<script>`, filters, masks, patterns, markers,
  `foreignObject` or embedded rasters (Qt's SVG renderer and `Test21Icons`), file names without
  "solidworks".
