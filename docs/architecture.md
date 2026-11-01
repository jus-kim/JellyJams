# JellyJams architecture

JellyJams is a FreeCAD 1.1+ workbench that gives FreeCAD a SolidWorks-style user interface
while it is the active workbench (a CommandManager-style ribbon, SolidWorks tool and tree
names, light/dark widget colors matching FreeCAD, SolidWorks mouse navigation and keyboard shortcuts) and leaves stock
FreeCAD exactly as it was otherwise. Not affiliated with or endorsed by Dassault Systèmes.

This document describes the **structure and contracts** of the code in
[`jellyjams/`](../jellyjams): the module map, lifecycle order, shared constants, persisted
state, error isolation, the ribbon data model and how to extend the add-on. The **behavior**
of each feature is defined by the specifications in [`specs/`](specs). Related documents:

| Document | Answers |
|---|---|
| [decisions.md](decisions.md) | Why the design is the way it is (short decision records) |
| [freecad-facts.md](freecad-facts.md) | Which FreeCAD 1.1 behaviors the code relies on |
| [`specs/*.md`](specs) | What each feature must do, with acceptance criteria |

**Source of truth.** When this document and the code disagree, the code and the tests in
[`tests/`](../tests) win. Fix this document in the same change.

Version 0.1.0 (2026-10-28), minimum FreeCAD 1.1, license LGPL-3.0-or-later. Checked against
the code on 2026-10-28.

## Contents

1. [Invariants](#1-invariants)
2. [Repository layout](#2-repository-layout)
3. [Module map](#3-module-map)
4. [Import and dependency rules](#4-import-and-dependency-rules)
5. [Lifecycle](#5-lifecycle)
6. [Shared constants](#6-shared-constants)
7. [Parameters and persisted state](#7-parameters-and-persisted-state)
8. [Error isolation rules](#8-error-isolation-rules)
9. [Ribbon](#9-ribbon)
10. [Core API quick reference](#10-core-api-quick-reference)
11. [Cross-module calls](#11-cross-module-calls)
12. [How to extend JellyJams](#12-how-to-extend-jellyjams)
13. [Tests and current status](#13-tests-and-current-status)

---

## 1. Invariants

These hold for the whole code base. Most are enforced by the headless tests.

| Rule | Defined in | Enforced by |
|---|---|---|
| Workbench key and class `JellyJamsWorkbench`, MenuText `JellyJams`, `GetClassName()` returns `Gui::PythonWorkbench` | [`InitGui.py`](../InitGui.py), [`constants.py`](../jellyjams/constants.py) | headless InitGui and metadata tests |
| Every command id JellyJams registers is `JellyJams_` plus the tool's ribbon name without spaces (`JellyJams_MakeDrawing`); the five sheet sketch shapes end in `OnSheet` | `constants.CMD_PREFIX`, `constants.CMD_*`, `commands.COMMAND_PREFIX` | `commands.register_all()` refuses other ids; command tests |
| Every Qt objectName JellyJams sets is `JellyJams` plus a role word (ribbon dock `JellyJamsCommandManager`); widgets made per ribbon entry add `-` and the entry id | `constants.OBJ_PREFIX`, `constants.OBJ_*` | ribbon tests |
| JellyJams' own parameters live in `User parameter:BaseApp/Preferences/Mod/JellyJams` | `constants.PARAM_ROOT` | constant-value test |
| The theme is exactly one block between `/* @jellyjams-stylesheet-open */` and `/* @jellyjams-stylesheet-close */` on the main-window stylesheet | `constants.THEME_BEGIN/THEME_END`, [`theme.py`](../jellyjams/theme.py) | theme tests |
| "SolidWorks" (any case) never appears in identifiers, objectNames, file names, icon names, parameter keys, command ids or document property names; it may appear in user-visible labels, tooltips and messages | everywhere | hygiene tests |
| English only; no translation layer | everywhere | review |
| No bundled third-party assets: FreeCAD commands use FreeCAD's icons at runtime, new drawings use FreeCAD's installed templates | [`icons.py`](../jellyjams/icons.py), [`templates.py`](../jellyjams/templates.py) | icon tests, review |
| The version string lives only in [`jellyjams/__init__.py`](../jellyjams/__init__.py) (`__version__`); [`package.xml`](../package.xml) and [`CHANGELOG.md`](../CHANGELOG.md) must match it | `__init__.py` | release-metadata tests |
| Every Python file starts with the same three header lines (encoding, license identifier `LGPL-3.0-or-later`, copyright `2026 jus-kim`); copy them from any existing module. SVG files carry the same information in an XML comment directly after the XML declaration | every file | hygiene and icon tests |
| JellyJams registers no QToolBar of its own, never calls `QApplication.setStyleSheet`, never writes `Preferences/MainWindow`, and styles FreeCAD's widgets only through the one main-window block. Widgets JellyJams creates may carry their own stylesheet | [`theme.py`](../jellyjams/theme.py), [`layout.py`](../jellyjams/layout.py) | GUI smoke test (`no_jj_toolbars`), review |
| No error pop-ups. All Report-view output goes through [`console.py`](../jellyjams/console.py) with the prefix `JellyJams: ` (messages forwarded by the Qt message filter are the one exception) | `console.py` | console-based tests |
| Every persistent FreeCAD parameter JellyJams overrides is backed up before the first write and restored exactly, including removing keys that did not exist | section 7 | headless round-trip tests, GUI smoke and lifecycle tests |
| JellyJams only reads the user-owned opt-out keys `SilenceGlyphWarnings` and `ShowSketchButtonOnFace`; it never writes them | [`qt_filter.py`](../jellyjams/qt_filter.py), [`context_sketch.py`](../jellyjams/context_sketch.py) | review |
| Every `install/enable/start/apply/show` function is safe to call repeatedly; every `uninstall/disable/stop/restore/hide/revert` function is safe when nothing is installed | every area module | lifecycle tests (activate twice, deactivate first) |

---

## 2. Repository layout

```
Init.py                 headless entry: header and docstring only
InitGui.py              registers the workbench, runs startup crash recovery
package.xml             Addon Manager manifest (version, freecadmin 1.1.0, branch main)
README.md, CHANGELOG.md
LICENSE, LICENSES/      LGPL-3.0-or-later (and the GPL-3.0 text it refers to)
resources/icons/        jellyjams.svg (workbench) + 28 original SVGs: JellyJams commands, relations, two Orientation panel buttons
jellyjams/              the package (flat, one level; see section 3)
tests/                  headless harness + GUI scripts (see section 13)
docs/                   this document, decisions, FreeCAD facts, specs/
```

The package is flat on purpose: import paths stay short and the headless harness can import
every module directly.

---

## 3. Module map

Modules are grouped into **areas** (the subsections below). Section 4 uses the areas for the
import rules. **Kind** is either **pure** (in `PURE_MODULES`: runs under a plain Python
interpreter and never imports FreeCAD, FreeCADGui, PySide or shiboken, not even lazily) or
**runtime** (may use FreeCAD, FreeCADGui and Qt, at top level or lazily).

### 3.1 Core (shared infrastructure)

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`__init__.py`](../jellyjams/__init__.py) | `__version__ = "0.1.0"`, `MIN_FREECAD_VERSION = (1, 1)` | pure | [core](specs/core.md) 3.5 |
| [`constants.py`](../jellyjams/constants.py) | every shared literal (section 6) | pure | core |
| [`console.py`](../jellyjams/console.py) | prefixed Report-view output; `guard` / `guarded` / `safe_call` failure containment; never raises | runtime | core |
| [`params.py`](../jellyjams/params.py) | typed parameter access, presence checks, JSON crash-backup strings | runtime | core |
| [`paths.py`](../jellyjams/paths.py) | add-on folder, icon lookup, user cache folder | runtime | core |
| [`fcgui.py`](../jellyjams/fcgui.py) | shared FreeCAD GUI queries (main window, docks, task panel, sheet window, selection, commands); never raises | runtime | core |
| [`doc_utils.py`](../jellyjams/doc_utils.py) | document helpers: liveness, type checks, root and primary model objects (2D profiles excluded), pages, property add, the `transaction` undo-step context manager | runtime | core |
| [`commands.py`](../jellyjams/commands.py) | `BaseCommand` for every JellyJams command (`cmd_type`, when set, becomes FreeCAD's `CmdType` resource); once-per-process registration (`PROVIDERS`) | runtime | core 8 |
| [`recovery.py`](../jellyjams/recovery.py) | startup crash recovery orchestrator | runtime | core 7 |
| [`navigation.py`](../jellyjams/navigation.py) | SolidWorks navigation style while active: `install()`, `uninstall()`, `recover()`, `is_installed()`; persisted backup `OriginalNavigationStyle`, exact restore; owns the runtime orbit hook | runtime | core |
| [`orbit.py`](../jellyjams/orbit.py) | balanced native middle-button orbit input; 3D viewport mouse filters and viewer key filters, deferred/coalesced focus discovery plus periodic discovery, removal on leave/quit; never scan synchronously inside focusChanged/native widget destruction; no persistent preferences | runtime | core 4.7.1 |
| [`orbit_rules.py`](../jellyjams/orbit_rules.py) | physical-to-native drag coordinates, normalized against the shorter viewport dimension | pure | core 4.7.1 |
| [`shortcuts.py`](../jellyjams/shortcuts.py) | SolidWorks shortcuts (`SHORTCUTS`); unbinds the commands that own one of those keys at install time; `install()`, `uninstall()`, `recover()`, `is_installed()`; persisted backup `OriginalShortcuts`, exact restore; uses `console`, `constants` and `params` | runtime | core |

### 3.2 Lifecycle

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`lifecycle.py`](../jellyjams/lifecycle.py) | Initialize / Activated / Deactivated / quit step tables and `run_steps` | runtime | core 4, 6 |
| [`quit_guard.py`](../jellyjams/quit_guard.py) | Direct accepted-close signal before persistence; early-Close/poll fallback on hosts without it | runtime | core 6.6 |
| [`qt_filter.py`](../jellyjams/qt_filter.py) | Qt message handler that drops "render glyph failed" floods while active | runtime | core 10 |
| [`diagnostics.py`](../jellyjams/diagnostics.py) | `JellyJams_Diagnostics` command and dialog; environment line | runtime | core 9 |

### 3.3 Look and layout

Appearance editing is a separate area: `appearance_rules` is pure library/input
logic; `appearances` owns the right-side dock, native document view-material edits
and undo. Its contract and official source references are in
[appearances.md](specs/appearances.md). User-applied document colours persist;
its temporary UI is removed on leave/quit without new preference backups.

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`palette.py`](../jellyjams/palette.py) | the one color palette; W3C relative-luminance and contrast helpers; packed RGBA | pure | [look](specs/look.md) |
| [`theme.py`](../jellyjams/theme.py) | builds, applies and removes the main-window stylesheet block | runtime | look |
| [`viewport.py`](../jellyjams/viewport.py) | 3D background gradient and sketch colors (`MANAGED_KEYS`) with exact restore | runtime | look |
| [`layout.py`](../jellyjams/layout.py) | hides non-kept toolbars, docks Tasks above an already open Report view; closed Report view stays closed; exact restore and autoload deferral | runtime | [window-layout](specs/window-layout.md) |

### 3.4 Ribbon

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`ribbon_layout.py`](../jellyjams/ribbon_layout.py) | declarative content: `Tab` / `Group` / `Cmd` / `Flyout` / `Toggle` / `Stack`; `TABS` | pure | [ribbon-content](specs/ribbon-content.md) |
| [`ribbon_model.py`](../jellyjams/ribbon_model.py) | `resolve(tabs, available)`: fallbacks, skips, entry ids | pure | [ribbon-engine](specs/ribbon-engine.md) |
| [`ribbon_text.py`](../jellyjams/ribbon_text.py) | one-line labels, tooltip composition, mnemonic escaping | pure | ribbon-engine 2.5, 2.8 |
| [`ribbon_widgets.py`](../jellyjams/ribbon_widgets.py) | Qt widgets: `RibbonUI`, `PlainButton`, `FlyoutButton`, `ToggleButton` | runtime | ribbon-engine 2 |
| [`icons.py`](../jellyjams/icons.py) | icon lookup: JellyJams icons from `resources/icons`, FreeCAD icons at runtime | runtime | ribbon-engine 2.7 |
| [`ribbon.py`](../jellyjams/ribbon.py) | public API: show / hide / visibility guard / rebuild / `run_entry` / refresh / test services | runtime | ribbon-engine |

### 3.5 Naming and dialog terms

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`naming_rules.py`](../jellyjams/naming_rules.py) | naming and numbering rules | pure | [naming](specs/naming.md) |
| [`naming.py`](../jellyjams/naming.py) | document observer that writes SolidWorks names into `Label` | runtime | naming |
| [`dialog_terms_data.py`](../jellyjams/dialog_terms_data.py) | catalog of FreeCAD task-dialog forms and their SolidWorks texts | pure | [dialog-terms](specs/dialog-terms.md) |
| [`dialog_terms.py`](../jellyjams/dialog_terms.py) | periodic relabeling of open task dialogs; ISO 128 line-weight presets row | runtime | dialog-terms |

### 3.6 Sketching

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`sketch_edit.py`](../jellyjams/sketch_edit.py) | keeps sketch editing inside JellyJams (wraps `TempoVis.activateWorkbench` while installed) | runtime | [sketching](specs/sketching.md) |
| [`edit_guard.py`](../jellyjams/edit_guard.py) | keeps feature editing inside JellyJams: wraps `FreeCADGui.activateWorkbench` while installed; requests from FreeCAD command strings (a `<string>` code object in the wrapper's caller frame or the frames above it, `FRAME_SEARCH_DEPTH` = 6 frames in all, so other add-ons' wrappers in between do not hide it) wait one event-loop turn and are dropped when an object entered edit meanwhile, Python callers pass straight through; tracks whether its wrapper is still in the call chain (`_in_chain`), so a re-install under another add-on's wrapper only re-arms it | runtime | sketching 2.7 |
| [`sketch_gesture.py`](../jellyjams/sketch_gesture.py) | feature-from-open-sketch (leave the sketch, then start the profile feature) and sketch first (`PartDesign_NewSketch` when there is nothing to use as the profile, then the feature when the new sketch is exited); container-only selections cleared, subtractive features only with a solid in the target body (`_target_body`: active body, else the only body; `_has_solid` mirrors FreeCAD's `Body::isSolid()`: a `PartDesign::Feature` in the body's `Group`), free sketches before the insert point only (`_after_insert_point`), stale plane picks dropped, retarget only for `SKETCH_FIRST_FEATURES` and, for the cutting ones, not when the target body is known and holds no solid (`_nothing_to_cut`, true only for a known target body, also used before a sketch-first starts); a cutting feature without a target body (several bodies, none active) is left to FreeCAD, which asks for the body (`_maybe_start_sketch_first` returns False, no refusal); in a target body without a solid `_refuse_without_solid` leaves Pocket and Groove to FreeCAD's own refusal (`REFUSED_BY_FREECAD`, returns False) and refuses Hole itself (status-bar text for `NEEDS_SOLID_MS` and a warning, returns True), both on a fresh press and while picking; every chain of checks (`_watch(expected)`) belongs to one sketch-first and stops once it is no longer the pending one; pure helpers `needs_new_sketch`, `advance` | runtime | sketching 2.2 and 2.6, ribbon-engine 3.6 |
| [`sketch_tools.py`](../jellyjams/sketch_tools.py) | `JellyJams_Centerline`, `JellyJams_MidpointLine` | runtime | sketching |
| [`context_sketch.py`](../jellyjams/context_sketch.py) | "Sketch" context icon next to a clicked planar face | runtime | sketching |

### 3.7 Panels

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`panel_host.py`](../jellyjams/panel_host.py) | shared host for the two task-panel inserts | runtime | relations, assembly |
| [`relations_rules.py`](../jellyjams/relations_rules.py) | Add Relations rules | pure | [relations](specs/relations.md) |
| [`relations_panel.py`](../jellyjams/relations_panel.py) | Add Relations panel | runtime | relations |
| [`mate_rules.py`](../jellyjams/mate_rules.py) | Add Mate rules | pure | [assembly](specs/assembly.md) |
| [`mate_panel.py`](../jellyjams/mate_panel.py) | Add Mate panel | runtime | assembly |

### 3.8 Assembly

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`switch_prefs.py`](../jellyjams/switch_prefs.py) | holds `SwitchToWB` of Assembly, Part Design and TechDraw (`TARGETS`) at false while active, each with an exact three-state restore and crash recovery | runtime | assembly 5 |
| [`assembly_drop.py`](../jellyjams/assembly_drop.py) | drop `.FCStd` files into the active assembly | runtime | assembly |
| [`assembly_commands.py`](../jellyjams/assembly_commands.py) | `JellyJams_NewAssembly`, `JellyJams_RotateComponent` | runtime | assembly |

### 3.9 Drawing foundation

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`drawing_common.py`](../jellyjams/drawing_common.py) | scale text, target sheet, sheet size and center | runtime | [drawing-sheet](specs/drawing-sheet.md) 3 |
| [`sheet_pick.py`](../jellyjams/sheet_pick.py) | the single on-sheet pick mode (Text, Weld Symbol, Projected View) | runtime | drawing-sheet |
| [`templates.py`](../jellyjams/templates.py) | catalog of FreeCAD's installed ISO templates; third-angle derivation into the user cache | runtime | drawing-sheet 6 |
| [`make_drawing.py`](../jellyjams/make_drawing.py) | `JellyJams_MakeDrawing` | runtime | drawing-sheet 4 |
| [`sheet_properties.py`](../jellyjams/sheet_properties.py) | `JellyJams_SheetProperties` | runtime | drawing-sheet 5 |

### 3.10 Drawing sheet content

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`sheet_sketch.py`](../jellyjams/sheet_sketch.py) | `JellyJams_*OnSheet` (the sheet sketch) + edit watcher | runtime | drawing-sheet 7 |
| [`sheet_text.py`](../jellyjams/sheet_text.py) | `JellyJams_Note` | runtime | drawing-sheet 8 |
| [`insert_picture.py`](../jellyjams/insert_picture.py) | `JellyJams_InsertPicture`; its panel keeps one persistent undo step open (`surface_finish.UndoStep`) | runtime | drawing-sheet 9 |
| [`zoom_lines.py`](../jellyjams/zoom_lines.py) | screen-only line-width compensation when zoomed in | runtime | [drawing-views](specs/drawing-views.md) 7 |

### 3.11 Drawing views

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`projected_view.py`](../jellyjams/projected_view.py) | `JellyJams_ProjectedView`, projection grid, start layout | runtime | drawing-views 3 |
| [`view_labels.py`](../jellyjams/view_labels.py) | section / detail view lettering and labels | runtime | drawing-views 4 |
| [`view_scale.py`](../jellyjams/view_scale.py) | `JellyJams_ViewScale` | runtime | drawing-views 5 |
| [`sheet_drag.py`](../jellyjams/sheet_drag.py) | click-anywhere view dragging; double-click on JellyJams symbols | runtime | drawing-views 6 |

### 3.12 Drawing symbols and export

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`surface_finish.py`](../jellyjams/surface_finish.py) | `JellyJams_SurfaceFinish`; helpers shared by the symbol panels, including `UndoStep` (a persistent undo step that lasts until a panel's OK or Cancel) | runtime | [drawing-symbols-export](specs/drawing-symbols-export.md) |
| [`weld_symbol.py`](../jellyjams/weld_symbol.py) | `JellyJams_WeldSymbol` + arrow-follow watcher | runtime | drawing-symbols-export |
| [`line_format.py`](../jellyjams/line_format.py) | `JellyJams_LineFormat` (runs `TechDraw_DecorateLine`) | runtime | drawing-symbols-export |
| [`drawing_export.py`](../jellyjams/drawing_export.py) | `JellyJams_SaveAsPDF` (all sheets, merged into one file), `JellyJams_SaveAsDXF` (one file per sheet) | runtime | drawing-symbols-export |
| [`pdf_merge.py`](../jellyjams/pdf_merge.py) | standard-library PDF merger; raises `UnsupportedPdf` | pure | drawing-symbols-export |

### 3.13 View orientation

| Module | Role | Kind | Spec |
|---|---|---|---|
| [`orientation.py`](../jellyjams/orientation.py) | `JellyJams_ViewOrientation` (`Space`) and `JellyJams_NormalTo` (`Ctrl+8`, the JellyJams menu, the panel and the Evaluate tab), both `cmd_type` `Alter3DView` and active while the window in front is a 3D view (`view3d_active`: `_active_view()`, the main window's `getActiveWindow()` with `FreeCADGui.activeView()` only as the fallback when that method is missing, has `getCameraNode`; docked, undocked, fullscreen or split; not the Start page or a drawing). Normal To (`normal_to_target`, `normal_to`) runs `Sketcher_ViewSketch` in a sketch with nothing (or only that sketch's elements) selected; otherwise it needs exactly one pick (`_single_pick`): any sub-element runs `Std_AlignToSelection` (FreeCAD decides; shapes are not read), a whole sketch or other 2D object (`SKETCH_TYPES`) gives `("sketch", obj)` and `_look_at_sketch` turns the view in front itself with `_active_view().setCameraOrientation(_sketch_rotation(obj).Q)` (`_sketch_rotation`: `FreeCAD.GeoFeature.getGlobalPlacementOf(obj, item.Object, path)` along the one unresolved selection path from `getSelectionEx("", 0)`, links included, else `getGlobalPlacement()`; a warning when turning fails), a whole origin plane or axis or datum (`DATUM_TYPES`) and a whole object whose shape is one face or one edge (`_single_face_or_edge`) run `Std_AlignToSelection`, and anything else shows the hint in the status bar and as a tool tip at the pointer (`_show_hint`). The Orientation panel: a frameless tool window `JellyJamsOrientation` at the pointer with Normal To, remember / go back to a view, Zoom to Fit, the six standard views around Front (`VIEW_GRID`) and Isometric / Trimetric / Dimetric (`AXONOMETRIC`); its own stylesheet gives every button state a text color and a background; a click closes the panel unless it is pinned and then runs the command (`_choose`, Normal To included); Esc / Space close it and their auto-repeats are ignored; another window becoming active closes it unless pinned (`_activation_changed` from the panel's `changeEvent`, then `_close_if_left(generation)` one turn later: only for the current opening `_generation`, after the panel had the keyboard `_seen_active`; within `OPEN_SETTLE_S` after `_opened_at` it re-activates the panel instead); `close()` gives the keyboard, when the panel had it, back to the window that had it at opening (`_return_to`) if alive and visible, else to the main window; the buttons follow `Command.get(id).isActive()` on every open; it is built again when its widget was deleted; `FALLBACK_ICONS` for the two camera commands that have no FreeCAD icon. `install()` (activation) puts one Space filter on the main window and on each of its docks (`_filtered` via `_watch`; a floating dock is a window of its own), connects `QApplication.focusChanged` to `_focus_changed` (a dock made later gets the filter when one of its widgets takes the focus) and turns off View Orientation's key repeat; the filter asks `keeps_space(focus, widget under the pointer)` (`_hand_space_to_focus`): over a 3D view, a 3D viewer, a split 3D view or the model tree (`SPACE_FOR_PANEL_CLASSES`) Space is always for the panel; otherwise controls in toolbars, the status bar or the ribbon dock never keep it, buttons and combo boxes do, item views only with a checkable current item or `AnyKeyPressed` editing, the model tree never. The panel's own `event()` applies the same rules without the pointer (`use_pointer=False`). `uninstall()` (deactivation) closes the panel, disconnects `focusChanged` and removes the filter from every widget in `_filtered`. Imports `icons` and `palette` lazily | runtime | [orientation](specs/orientation.md) |

---

## 4. Import and dependency rules

1. **Top-level imports** may only be: the standard library, `FreeCAD`, `FreeCADGui`, FreeCAD's
   `PySide` shim (`from PySide import QtCore, QtGui, QtWidgets`), the core modules
   (`constants`, `console`, `params`, `paths`, `fcgui`, `doc_utils`, `commands`), and modules
   of the **same area** (section 3). Examples in the code: `theme` and `viewport` import
   `palette`; `view_scale` imports `projected_view`; `weld_symbol` imports `surface_finish`;
   `quit_guard` imports `lifecycle`.
2. **Other areas are imported lazily** inside functions, inside `try/except` (or
   `console.guard`). This prevents import cycles and keeps one broken area from breaking
   another. Example: [`ribbon.run_entry`](../jellyjams/ribbon.py) imports `sketch_tools` and
   `sketch_gesture` at call time; `context_sketch` reads `palette` lazily.
3. **FreeCAD workbench modules** (`Part`, `Sketcher`, `TechDraw`, `TechDrawGui`, `PartGui`,
   `SketcherGui`, `PartDesignGui`, `Show`, `UtilsAssembly`, `Import`, ...) are imported lazily
   inside functions only.
4. **Pure modules** import nothing from FreeCAD, FreeCADGui, PySide or shiboken, not even
   lazily: `__init__`, `constants`, `palette`, `ribbon_layout`, `ribbon_model`, `ribbon_text`,
   `naming_rules`, `relations_rules`, `mate_rules`, `dialog_terms_data`, `pdf_merge`. The list
   lives in `PURE_MODULES` in [`tests/test_headless.py`](../tests/test_headless.py), which
   checks it by AST and by running the modules in a plain interpreter.
5. Every module must import cleanly under the headless stubs (`EXPECTED_MODULES` in the test
   file).
6. Use absolute imports (`from jellyjams import constants`), Qt widgets from `QtWidgets`, and
   Qt 6 scoped enums (`QtCore.Qt.DockWidgetArea.TopDockWidgetArea`).
7. Before reusing a Qt object that FreeCAD may have destroyed (task panel content, docks,
   sheet views), check `fcgui.is_alive(obj)`.

---

## 5. Lifecycle

All ordering lives in **step tables** in [`lifecycle.py`](../jellyjams/lifecycle.py). A step
is `(key, what, module, function)`. `run_steps(steps)` imports `module` and calls `function`
**at call time** (so tests can monkeypatch), catches every exception, prints
`JellyJams: could not <what>: <exception>` plus traceback, and continues with the next step.
It returns the keys of failed steps.

```
FreeCAD start ──> InitGui.py: register workbench ──> recovery.run_startup_recovery()
                                   │
user selects JellyJams (or autoload)
                                   ▼
             Initialize (first time) ──> Activated ──> ... ──> Deactivated
                                                │
                              main window Close event (quit)
                                                ▼
                           quit_guard: revert_for_quit ──> (Cancel) reapply_after_cancel
```

### 5.1 Startup (every GUI start): `InitGui.py`

FreeCAD runs [`InitGui.py`](../InitGui.py) with `exec()`: there is no `__file__` and top-level
names are not visible inside the class body or methods (see
[freecad-facts.md](freecad-facts.md#add-on-loading)).

1. Determine `_JELLYJAMS_DIR`: the folder of `inspect.currentframe().f_code.co_filename` when it
   names an existing `InitGui.py`; otherwise `jellyjams.paths.addon_dir()`; otherwise `None`.
2. Define `JellyJamsWorkbench(FreeCADGui.Workbench)` with literal class attributes only. Each
   method imports `jellyjams.lifecycle` locally and delegates inside `try/except`
   (`Initialize -> lifecycle.initialize(self)`, `Activated -> lifecycle.activated()`,
   `Deactivated -> lifecycle.deactivated()`, `GetClassName -> "Gui::PythonWorkbench"`).
3. Set `JellyJamsWorkbench.Icon` to `<_JELLYJAMS_DIR>/resources/icons/jellyjams.svg` if it exists.
4. Register: if `JellyJamsWorkbench` is already in `FreeCADGui.listWorkbenches()`, print one
   warning naming the folder of the skipped copy; otherwise `addWorkbench` and print
   `workbench added, loaded from <path>`.
5. Always run `recovery.run_startup_recovery()` (section 5.6), even if registration failed.

Nothing else happens at startup: no widgets, no command registration, no theme.

### 5.2 Initialize (first activation in a session)

`lifecycle.initialize(workbench)`; each step guarded on its own:

| # | Step | Once per |
|---|---|---|
| 1 | Environment line `diagnostics.environment_line()` (`release <version> on FreeCAD <x.y.z>, Qt binding <binding>`) as a message; a warning instead when `diagnostics.freecad_version()[:2] < MIN_FREECAD_VERSION` | call |
| 2 | `commands.register_all()` (silent no-op when repeated) | process |
| 3 | `run_steps(INIT_HELPERS)`: `view_labels.install`, `zoom_lines.start`, `weld_symbol.install_watcher`, `sheet_sketch.install_watcher` | process |
| 4 | `workbench.appendMenu("JellyJams", ["JellyJams_ViewOrientation", "JellyJams_NormalTo", "JellyJams_Appearances", "JellyJams_Diagnostics"])`: both orientation commands must sit in a menu, because FreeCAD gives a command a `QAction`, and so a working shortcut (`Space`, `Ctrl+8`), only when it is in a menu or toolbar | workbench instance |
| 5 | `console.message("workbench set up and ready")` | call |

### 5.3 Activated

The lifecycle tables below retain their earlier A/D labels for existing links.
The new `appearances.enable` step runs immediately after `ribbon.show`, before
`naming.enable`. It creates one dock tab beside Tasks, deferring hidden startup.

`lifecycle.activated()` sets `is_active()` to True **first**, then runs `ACTIVATION_STEPS`.
The older A/D numbers in 5.3 and 5.4 predate the Appearances insertion described above. They differ from the step
numbers in [core.md](specs/core.md) 4.4 and 4.5 (which [status.md](status.md) uses): the spec
has an optional feature-from-sketch step (A10 / D9), folds `edit_guard` into its sketch-edit
step (A9 / D10) and combines `assembly_drop` with `switch_prefs`, while the code adds
`quit_guard`, `sketch_tools` and separate rows for each of these.

| # | Key | Call | Notes |
|---|---|---|---|
| A1 | `layout` | `layout.apply()` | must stay first: snapshots the window before anything changes it; defers on autoload (5.7) |
| A2 | `theme` | `theme.apply()` | |
| A3 | `viewport` | `viewport.apply()` | persisted backup `OriginalViewColors` |
| A4 | `navigation` | `navigation.install()` | persisted backup `OriginalNavigationStyle` |
| A5 | `shortcuts` | `shortcuts.install()` | persisted backup `OriginalShortcuts` |
| A6 | `orientation` | `orientation.install()` | the Space filter on the main window and on each of its docks (one filter object, in memory only) and View Orientation's key repeat off |
| A7 | `ribbon` | `ribbon.show()` | builds on first show only |
| A8 | `naming` | `naming.enable()` | observer registered once per session |
| A9 | `sketch_edit` | `sketch_edit.install()` | |
| A10 | `edit_guard` | `edit_guard.install()` | wraps `FreeCADGui.activateWorkbench` (in memory only) |
| A11 | `context_sketch` | `context_sketch.enable()` | the icon is offered only while `ShowSketchButtonOnFace` is True (read on each click) |
| A12 | `relations_panel` | `relations_panel.enable()` | |
| A13 | `mate_panel` | `mate_panel.enable()` | |
| A14 | `assembly_drop` | `assembly_drop.enable()` | |
| A15 | `switch_prefs` | `switch_prefs.apply()` | persisted backups `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB` |
| A16 | `dialog_terms` | `dialog_terms.start()` | |
| A17 | `qt_filter` | `qt_filter.install_and_enable()` | not installed when `SilenceGlyphWarnings` is False |
| A18 | `quit_guard` | `quit_guard.install()` | once per session |

Feature-from-open-sketch and sketch first have no step: [`ribbon.run_entry`](../jellyjams/ribbon.py)
calls `sketch_gesture.try_run` directly. A pending sketch-first watches the workbench itself
and ends when JellyJams is no longer active.

### 5.4 Deactivated

`appearances.disable` is now the first step, before the older numbered rows below.
It stops target refresh and removes/detaches only the owned dock. Stock layout
restore remains last. The older row labels are retained for existing references.

`lifecycle.deactivated()` sets `is_active()` to False **first**, then runs
`DEACTIVATION_STEPS`. FreeCAD has already shown the next workbench's toolbars at this point
(see [freecad-facts.md](freecad-facts.md#main-window-docks-and-toolbars)), which is why the
layout revert is last and restores only what JellyJams changed.

The numbers below follow `DEACTIVATION_STEPS` one row per step. [core](specs/core.md) 4.5
describes the same sequence for users and groups some steps into one row, so its numbers are
smaller from D4 on (its D12, the Orientation panel, is D14 here).

| # | Key | Call |
|---|---|---|
| D1 | `qt_filter` | `qt_filter.disable()` (handler stays installed, transparent) |
| D2 | `dialog_terms` | `dialog_terms.stop()` |
| D3 | `assembly_drop` | `assembly_drop.disable()` |
| D4 | `switch_prefs` | `switch_prefs.restore()` (all three modules) |
| D5 | `mate_panel` | `mate_panel.disable()` |
| D6 | `relations_panel` | `relations_panel.disable()` |
| D7 | `context_sketch` | `context_sketch.disable()` |
| D8 | `sheet_pick` | `sheet_pick.cancel()` |
| D9 | `rotate_component` | `assembly_commands.stop_rotate_component()` |
| D10 | `sketch_tools` | `sketch_tools.stop_running()` |
| D11 | `edit_guard` | `edit_guard.uninstall()` (FreeCAD's own `activateWorkbench` back, identity restore, only while the JellyJams wrapper is on top; under another add-on's wrapper it is only disarmed) |
| D12 | `sketch_edit` | `sketch_edit.uninstall()` |
| D13 | `naming` | `naming.disable()` (observer stays registered and gates itself) |
| D14 | `orientation` | `orientation.uninstall()` (hides the Orientation panel, pinned or not, and removes the Space filter from the main window and every dock it was put on; safe when neither was ever set up) |
| D15 | `ribbon` | `ribbon.hide()` (widgets kept for the next activation) |
| D16 | `shortcuts` | `shortcuts.uninstall()` (`Space` back to Hide/Show, `Ctrl+B` back to Box Zoom) |
| D17 | `navigation` | `navigation.uninstall()` |
| D18 | `viewport` | `viewport.restore()` |
| D19 | `theme` | `theme.remove()` |
| D20 | `layout` | `layout.revert()`: restores, then schedules a second pass after `SECOND_PASS_MS` (250 ms) that calls `ribbon.hide_if_not_requested()` |

Both layout restore passes retain the list of toolbars JellyJams hid and re-show
those bars. All other toolbars preserve their current visibility. This prevents
a late native workbench update from leaving general bars hidden after cancelled
quit followed by a workbench switch. Report view placement includes only an
already open dock; a closed dock is never shown by startup re-docking.

When the user leaves JellyJams through the workbench selector, the switch itself runs from
`edit_guard`'s deferred decision (5.8): FreeCAD deactivates JellyJams inside that call, and D11
hands FreeCAD's function back.

Activating twice, deactivating twice, or deactivating first are harmless because every area
function is idempotent. Lifecycle schedules no timers itself.

### 5.5 Quit

The appearance dock is removed first through `appearances.suspend_for_quit`.
After Cancel, `appearances.resume_after_cancel` runs after `ribbon.show` and
before `switch_prefs.apply`. The dock and timer remain intact throughout native save prompts; suspension occurs on accepted close.

FreeCAD never calls `Deactivated()` on quit, but it saves the window state and all parameters
while the main window closes. [`quit_guard.py`](../jellyjams/quit_guard.py) installs a
guard on the main window (A18). FreeCAD 1.1.4 emits `mainWindowClosed` after
`tryClose` accepts all document/view closures, immediately before `saveWindowSettings`.

1. Connect once with `Qt.ConnectionType.DirectConnection`; the synchronous slot
   runs `lifecycle.revert_for_quit()` once, before native persistence. Never queue it.
2. During native save prompts, leave JellyJams intact, including its pending backups.
   Cancel never emits the accepted-close signal and requires no reapplication.
3. If the signal connection is unavailable, use the early Close-event revert and
   modal-aware poll/reapply fallback. The event filter always returns False.

| `QUIT_REVERT_STEPS` (accepted close; early Close only on fallback) | `QUIT_REAPPLY_STEPS` (fallback Cancel only) |
|---|---|
| `switch_prefs.restore` | `layout.apply` |
| `ribbon.hide` | `theme.apply` |
| `shortcuts.uninstall` | `viewport.apply` |
| `navigation.uninstall` | `navigation.install` |
| `viewport.restore` | `shortcuts.install` |
| `theme.remove` | `ribbon.show` |
| `layout.revert` | `switch_prefs.apply` |

The quit tables cover everything FreeCAD would persist (parameters and the main-window state,
which includes toolbar and dock visibility) plus the theme. Session-only hooks (naming,
panels, dialog terms, the TempoVis and `activateWorkbench` wrappers) are not touched on quit. The guard acts whenever JellyJams is active,
not only when the layout is applied, so overrides applied while an autoload deferral never
completed are covered too.

### 5.6 Startup crash recovery

[`recovery.run_startup_recovery()`](../jellyjams/recovery.py) runs from `InitGui.py` at every
GUI start. A non-empty backup at startup means the previous session ended while JellyJams'
overrides were in effect. Each step runs under `console.guard(..., level="warning")`:

| # | Step | Corrupt backup handling |
|---|---|---|
| 1 | `viewport.recover()` | viewport deletes an unusable record with one warning; malformed entries are skipped with a warning |
| 2 | navigation: `params.load_backup("OriginalNavigationStyle")`, validate (object with `existed`), then `navigation.recover()` | recovery deletes it with one warning (`deleted the navigation style backup left by the last session because it could not be used (...)`) |
| 3 | shortcuts: validate (object of `[bool, string-or-null]` entries), then `shortcuts.recover()` | same, naming the `keyboard shortcut` backup |
| 4 | `switch_prefs.recover()`: each of the three records on its own, one message per restored module | values other than `1`/`0`/`absent` are removed with one warning naming the module; that setting is left as it is, the other modules still restore |

[`recovery.py`](../jellyjams/recovery.py) checks the navigation and shortcut records before
it calls the modules. The modules also check a record themselves whenever they read it:
`install()` replaces an unreadable leftover with one warning, `uninstall()` discards one with
one warning, and `shortcuts` skips single malformed entries with a warning. A clean start (all
backups empty) prints nothing. Recovery failures are warnings; registration and FreeCAD
startup always continue.

### 5.7 Autoload

If FreeCAD autoloads JellyJams at startup, `Activated()` runs before the main window is shown
and before FreeCAD restores its saved window state.

* A1 `layout.apply()` sees the main window not visible and **defers**: it polls every
  `DEFER_POLL_MS` (200 ms) up to `DEFER_POLL_LIMIT` (60) polls, then gives up with one
  warning. The deferral is cancelled silently by `layout.revert()` or when the active
  workbench is no longer JellyJams. `layout.is_deferred()` reports it.
* A2 to A18 apply immediately (theme, viewport, navigation, shortcuts, ribbon, ...).
* When the deferred layout finally applies, layout calls `ribbon.show_if_requested()`, because
  FreeCAD's restore of the saved window state may have hidden the ribbon dock.
* After every apply, layout re-checks the Tasks / Report view docking and hides any
  non-kept toolbar restored late at `REDOCK_DELAYS_MS` (350, 1200, 3000 ms).
  Newly hidden bars join the restore list once. Each pass runs only for the same
  activation generation, while the layout is applied and JellyJams is still the
  active workbench; it cannot hide the next workbench's bars before deactivation.

### 5.8 Process-wide hooks

Hooks that outlive one activation are registered once and gate themselves.

| Hook | Registered by | When | Lifetime / gating |
|---|---|---|---|
| Direct accepted-close signal and fallback Close-event filter on the main window | `quit_guard.install` | A18 | session; acts only when `lifecycle.is_active()` |
| Qt message handler | `qt_filter.install_and_enable` | A17, first time allowed | session (cannot be uninstalled); drops glyph messages only while enabled |
| Tree-naming document observer | `naming.enable` | A8, first time | session; acts only while enabled and JellyJams is the active workbench. It also remembers assembly components whose `LinkedObject` was still empty at rename time (FreeCAD's New Part sets it only when its dialog is accepted) and names them when the target arrives; deleting the link or closing its document forgets it, even while inactive |
| Section/detail labeling observer + queue timer (250 ms) | `view_labels.install` | Initialize | session; gated on `fcgui.jellyjams_active()`; waits while a task dialog is open, a TechDraw tool runs or a view drag is in progress; each pass is one closed `View Label` undo step per document |
| Zoom line-width timer (180 ms) + document observer | `zoom_lines.start` | Initialize | session; reduces widths only while JellyJams is active; originals come back before saves, while modal dialogs are open, on leaving JellyJams, on zoom-out and for export |
| Weld arrow-follow document observer | `weld_symbol.install_watcher` | Initialize | session; always active |
| Sheet-sketch edit watcher (GUI document observer, or a 250 ms poll if that is unavailable) and undo watcher (document observer) | `sheet_sketch.install_watcher` | Initialize | session; always active (re-places the sheet sketch view after an edit, and after an undo/redo that changed the sketch outside an edit) |
| Ribbon refresh timer (450 ms) | `ribbon.show` | A7 | stopped by `ribbon.hide` |
| Space filter on the main window and its docks (one event filter object installed on that window and on every `QDockWidget` it holds at activation, and on a dock made later when one of its widgets takes the focus, listed in `orientation._filtered`; never application-wide) | `orientation.install`, `orientation._focus_changed` | A6; one filter however often JellyJams is activated; each dock added once | removed from every listed widget that still exists by `orientation.uninstall` (D14); accepts the `ShortcutOverride` of a plain Space when `keeps_space(focus widget, widget under the pointer)` says the focused control keeps Space and lets everything else pass. The docks need it because a floating dock is a window of its own whose key events never reach the main window |
| `QApplication.focusChanged` connected to `orientation._focus_changed` | `orientation.install` | A6 | disconnected by `orientation.uninstall` (D14); installs the Space filter on the nearest `QDockWidget` above the newly focused widget when it is not in `_filtered` yet; other widgets add nothing |
| Orientation panel click-outside check | the panel's `changeEvent` (`_activation_changed`) | each time the open panel loses the keyboard | one `fcgui.defer` turn; `_close_if_left(generation)` does nothing for an earlier opening, a panel that never had the keyboard since opening, a pinned or active panel; within `OPEN_SETTLE_S` (0.3 s) of opening it re-activates the panel; later it closes it |
| The window to give the keyboard back to (`orientation._return_to`) | `orientation.open_at_cursor` (`QApplication.activeWindow()`, never the panel) | each opening | read by `orientation.close()` only when the panel had the keyboard: that window if alive and visible, else the main window |
| Sheet view mouse filter | `sheet_drag.attach` (from the ribbon refresh) | per sheet window | gated on JellyJams active, no dialog, no TechDraw tool, no pick mode |
| Selection observers (Add Relations, Add Mate, context sketch) | their `enable()` | each activation | removed by `disable()` |
| Mate panel re-check timer (500 ms) | `mate_panel.enable` | each activation | stopped by `disable()` |
| Application-wide drop filter | `assembly_drop.enable` | each activation | removed by `disable()` |
| `TempoVis.activateWorkbench` wrapper | `sketch_edit.install` | each activation | original restored by `uninstall()` (identity restore) |
| `FreeCADGui.activateWorkbench` wrapper | `edit_guard.install` | each activation | original restored by `uninstall()` (identity restore). A call that comes from a FreeCAD command string (`co_filename == "<string>"` in the caller frame or one of the frames above it, `FRAME_SEARCH_DEPTH` = 6 frames in all) for another workbench is deferred with `fcgui.defer(..., 0)`; the deferred decision switches unless an object entered edit meanwhile. Python callers, requests for JellyJams and calls while JellyJams is inactive pass straight through. **Chain tracking:** `_in_chain` records that the wrapper is part of the call chain. When another add-on wraps it later, `uninstall()` only disarms it (`_armed = False`) and leaves the other wrapper on top; the next `install()` only re-arms it instead of wrapping the other wrapper (which already calls the JellyJams wrapper, so wrapping it would recurse without end). Only when the wrapper is on top does `uninstall()` hand back FreeCAD's function and clear `_in_chain`. Under other add-ons' wrappers the command string is found a frame or more further up, so feature edits keep JellyJams there too; a false match only delays a real switch by one turn |
| Sketch-first watcher (`WATCH_MS`, 150 ms, re-armed while pending) | `sketch_gesture.try_run` (ribbon press) | while a sketch-first is pending | ends on start, drop, a closed document or when JellyJams is no longer active; each check carries the sketch-first it belongs to and stops when another one has replaced it, so one chain runs at a time |
| Dialog-terms timer (250 ms) | `dialog_terms.start` | each activation | stopped by `stop()` |
| Application-wide end filters | `sketch_tools`, `assembly_commands` | while a Centerline / Midpoint Line / Rotate Component mode runs | removed when the mode ends |
| Sheet view pick filter | `sheet_pick.start` | while a pick mode runs | removed when the mode ends |

---

## 6. Shared constants

All shared literals live in [`constants.py`](../jellyjams/constants.py) (pure). Other modules
use these names instead of repeating literals. `CONSTANT_VALUES` in the headless tests pins
every value, so a change is always deliberate.

| Group | Names | Notes |
|---|---|---|
| Identity | `ADDON_NAME`, `WORKBENCH_KEY`, `MENU_TEXT`, `MENU_NAME`, `WORKBENCH_TOOLTIP`, `LOG_PREFIX` | `LOG_PREFIX = "JellyJams: "` |
| Parameter groups | `PARAM_ROOT`, `PARAM_RIBBON`, `PARAM_VIEW`, `PARAM_SHORTCUT`, `PARAM_ASSEMBLY`, `PARAM_PARTDESIGN`, `PARAM_TECHDRAW_GENERAL`, `PARAM_TECHDRAW_REZ`, `PARAM_TECHDRAW_FILES`, `PARAM_DOCUMENT`, `PARAM_GENERAL` | `PARAM_GENERAL` is defined but not read by any module at present |
| Keys in `PARAM_ROOT` | `KEY_QT_FILTER`, `KEY_CONTEXT_SKETCH`, `KEY_VIEW_BACKUP`, `KEY_NAV_BACKUP`, `KEY_SHORTCUT_BACKUP`, `KEY_ASSEMBLY_BACKUP`, `KEY_PARTDESIGN_BACKUP`, `KEY_TECHDRAW_BACKUP`, `KEY_NOTE_HEIGHT`, `KEY_NOTE_UNIT`, `BACKUP_KEYS` | backup key literals are stored in users' `user.cfg` and must never change; `BACKUP_KEYS` lists all six |
| Theme markers | `THEME_BEGIN`, `THEME_END` | |
| JellyJams objectNames | `OBJ_RIBBON`, `OBJ_RIBBON_TABS`, `OBJ_RIBBON_STACK`, `OBJ_RIBBON_SEPARATOR`, `OBJ_BTN_PREFIX`, `OBJ_FLY_PREFIX`, `OBJ_TOG_PREFIX`, `OBJ_PANEL*`, `OBJ_PANEL_DOCK`, `OBJ_CONTEXT_TOOLBAR`, `OBJ_LINE_WIDTH_PRESETS`, `OBJ_SHEET_PROPERTIES`, `OBJ_PICTURE_FORM`, `OBJ_SURFACE_FINISH`, `OBJ_WELD_SYMBOL`, `OBJ_DIAGNOSTICS_DIALOG`, `OBJ_NOTE_DIALOG`, `OBJ_SCALE_MENU`, `OBJ_PREFIX` | all start with `OBJ_PREFIX` (`JellyJams`) |
| FreeCAD Qt names | `DOCK_TASKS`, `TASK_DOCK_CANDIDATES`, `DOCK_REPORT`, `MODEL_DOCK_CANDIDATES`, `KEPT_TOOLBAR_WORDS`, `CLASS_TASK_PANEL`, `CLASS_SHEET_WINDOW`, `CLASS_VIEW3D` | `KEPT_TOOLBAR_WORDS = ("File", "Edit", "Workbench")` |
| FreeCAD type ids | `TYPE_*` (sketch, assembly, link, part, body, TechDraw page / views / symbols, ...) | |
| JellyJams command ids | `CMD_PREFIX`, `CMD_*`, `ALL_COMMANDS` (23 ids, the last two `CMD_ORIENTATION` = `JellyJams_ViewOrientation` and `CMD_NORMAL_TO` = `JellyJams_NormalTo`) | every id starts with `CMD_PREFIX` (`JellyJams_`) |
| Icons | `WORKBENCH_ICON`, `COMMAND_ICONS` (command id -> SVG base name), `RELATION_ICONS` | files in `resources/icons/` |
| FreeCAD commands used by several areas | `PROFILE_FEATURES`, `SKETCH_FIRST_FEATURES`, `NEW_SKETCH_COMMAND`, `GUI_COMMAND_MODULES`, `ASSEMBLY_COMMAND_MODULES` | `SKETCH_FIRST_FEATURES` (Pad, Pocket, Revolution, Groove, Hole) is a subset of `PROFILE_FEATURES`; the two module lists are preloaded before the ribbon build |
| FreeCAD view keys | `ACTIVE_BODY_KEY` (`"pdbody"`) | `ActiveView.getActiveObject` key of the active Part Design body |
| Ribbon tabs | `TAB_FEATURES`, `TAB_SKETCH`, `TAB_EVALUATE`, `TAB_ASSEMBLY`, `TAB_DRAWING`, `TAB_TITLES`, `START_TAB` | |
| Document properties | `PROP_*`, `KIND_SURFACE`, `KIND_WELD` | stored in users' `.FCStd` files; renaming breaks existing documents (section 7.3) |
| Shared tables | `PROJECTION_VIEW_LABELS` | one table for tree naming and Projected View |
| Timing defaults (ms) | `RIBBON_REFRESH_MS = 450`, `QUIT_PROMPT_POLL_MS = 600`, `DIALOG_TERMS_MS = 250` | modules copy them into patchable module constants |

`navigation.py` and `shortcuts.py` take their group paths and backup keys from `constants` like
every other module; their `BACKUP_KEY` names `KEY_NAV_BACKUP` and `KEY_SHORTCUT_BACKUP`.

---

## 7. Parameters and persisted state

### 7.1 Parameter keys

All group paths start with `User parameter:BaseApp/Preferences/`.

| Group | Key | Type | Owner | Written? | Restore / recovery |
|---|---|---|---|---|---|
| `Mod/JellyJams` | `SilenceGlyphWarnings` | Bool | qt_filter | never (user opt-out, default True) | n/a |
| `Mod/JellyJams` | `ShowSketchButtonOnFace` | Bool | context_sketch | never (user opt-out, default True) | n/a |
| `Mod/JellyJams` | `OriginalViewColors` | String (JSON) | viewport | while active | D18 / quit / recovery step 1 |
| `Mod/JellyJams` | `OriginalNavigationStyle` | String (JSON) | navigation | while active | D17 / quit / recovery step 2 |
| `Mod/JellyJams` | `OriginalShortcuts` | String (JSON) | shortcuts | while active | D16 / quit / recovery step 3 |
| `Mod/JellyJams` | `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB` | String `1` / `0` / `absent` | switch_prefs | while active | D4 / quit / recovery step 4 (each key removed after its restore) |
| `Mod/JellyJams` | `LastNoteHeight`, `LastNoteUnit` | Float (mm) / String (`mm` or `pt`) | sheet_text | yes, as a preference | kept |
| `Mod/JellyJams/FlyoutChoices` | `<flyout id>` | String (variant entry id) | ribbon_widgets | when a variant is picked | kept |
| `View` | the 14 keys of `viewport.MANAGED_KEYS` | Bool / Unsigned | viewport | while active | exact; absent keys removed |
| `View` | `NavigationStyle` | String | navigation | while active | exact; absent key removed |
| `Shortcut` | `<command id>` for each `shortcuts.SHORTCUTS` entry (13: `F`, `Z`, `Shift+Z`, `Ctrl+B`, `Ctrl+1` to `Ctrl+7`, `Ctrl+8` on `JellyJams_NormalTo`, `Space` on `JellyJams_ViewOrientation`) and each conflicting command (in FreeCAD 1.1 `Std_ViewBoxZoom` on `Ctrl+B` and `Std_ToggleVisibility` on `Space`, unbound with an empty value) | String | shortcuts | while active | exact; absent keys removed |
| `Mod/Assembly`, `Mod/PartDesign`, `Mod/TechDraw/General` | `SwitchToWB` | Bool | switch_prefs | while active (held at False) | exact three-state, each on its own |
| read only | `Mod/TechDraw/Rez` `Resolution`, `Mod/TechDraw/Files` `TemplateFile`, `Document` `prefAuthor` | | fcgui, templates, make_drawing | never | n/a |

### 7.2 Backup record formats (on-disk contract)

Backups are written **before** the first override, live in `Mod/JellyJams`, and are emptied
(or removed) after a successful restore. An empty or missing string means "no backup". A
backup that is still pending when an override is applied again is **never overwritten**,
because it holds the real original.

| Key | Format | Example |
|---|---|---|
| `OriginalViewColors` | `{key: [type, existed, previousValue]}` with type `"Bool"` or `"Unsigned"` | `{"Gradient": ["Bool", false, null], "BackgroundColor2": ["Unsigned", true, 4294967295]}` |
| `OriginalNavigationStyle` | `{"existed": bool, "value": string-or-null}` | `{"existed": false, "value": null}` |
| `OriginalShortcuts` | `{commandId: [existed, previousValue]}` | `{"Std_ViewTop": [true, "T"], "Std_ViewBoxZoom": [false, null]}` |
| `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB` | plain string, not JSON | `"1"`, `"0"` or `"absent"` |

Do not change these formats: a backup written by one version must be recoverable by the next.

### 7.3 Document properties (file-compatibility contract)

Markers are added in the same call that creates the object (naming renames on the next
event-loop turn and reads them then). They are stored in `.FCStd` files.

| Property | Type | Group | On | Written by | Read by |
|---|---|---|---|---|---|
| `HostSheet` | `App::PropertyLinkHidden` | JellyJams | sheet sketch | sheet_sketch | naming, sheet_sketch |
| `ShownSketch` | `App::PropertyLinkHidden` | JellyJams | its `DrawViewPart` | sheet_sketch | naming, sheet_sketch |
| `BorderLineIndex` | `App::PropertyInteger` | JellyJams | sheet sketch | sheet_sketch | sheet_sketch |
| `SheetNote` | `App::PropertyBool` | JellyJams | `DrawViewAnnotation` | sheet_text | naming, sheet_text |
| `CaptionFor` | `App::PropertyLink` | JellyJams | view-label annotation | view_labels | view_labels |
| `SymbolType` | `App::PropertyString` (`surface` / `weld`) | JellyJams | `DrawViewSymbol` | surface_finish, weld_symbol | naming, insert_picture, sheet_drag |
| `MaterialRemoval`, `AllAroundOutline` | String / Bool | JellyJams | surface symbol | surface_finish | surface_finish |
| `WeldSettings`, `ArrowheadX`, `ArrowheadY` | String (JSON) / Float / Float | JellyJams | weld symbol | weld_symbol | weld_symbol |

### 7.4 Files outside documents

* Third-angle template variants derived at runtime:
  `<FreeCAD user data>/JellyJams/templates/<stem>_third_angle.svg` (`paths.user_cache_dir("templates")`),
  a re-creatable cache.
* PDF export works in private temporary folders named `jellyjams_pdf_*`, deleted after use.
* Nothing else is written outside FreeCAD's parameters and the user's documents.

---

## 8. Error isolation rules

1. **Boundaries never raise.** Every entry point FreeCAD or Qt calls catches all exceptions:
   workbench methods (`InitGui.py`), `GetResources` / `Activated` / `IsActive`
   (`commands.BaseCommand`), observer slots, event filters, timer callbacks, signal slots,
   task-panel `accept` / `reject`, the Qt message handler. Use `console.guard(what, level)`
   (context manager) or `console.guarded(what, level, default)` (decorator; it also drops
   surplus positional arguments PySide passes to slots).
2. **Area lifecycle functions** (`apply`, `restore`, `install`, `enable`, ...) handle expected
   failures themselves at the level their spec gives. `lifecycle.run_steps` still wraps every
   call; anything that escapes is reported as `JellyJams: could not <what>:` with traceback,
   and the next step runs.
3. **Cross-area calls** are lazy imports inside `try/except`. A failing callee never breaks
   the caller (silent or log level unless the spec asks for a message).
4. **Event filters** return False (let the event through) when they fail internally and
   release any re-entrancy guard in `finally`.
5. **`IsActive` never raises**: `BaseCommand.IsActive` returns `active_on_error` (default
   False) when `is_active()` raises. `BaseCommand.Activated` reports `<menu text> stopped with
   an error` with traceback.
6. **Transactions are always closed** (commit or abort). For an undo step inside one call, use
   `doc_utils.transaction(doc, name, join_pending=False, abort_on_error=False)`:
   * it opens the document step `name`, yields True and commits it when the block ends;
   * if the block raises, it aborts (`abort_on_error=True`) or commits, then re-raises;
   * with `join_pending=True` and a step already pending in `doc`, or with `doc` None, it
     yields False and neither opens nor closes anything;
   * FreeCAD creates a document step only when something changes, so a step without changes
     is not closed by `commitTransaction()`/`abortTransaction()`; when the step opened a new
     application-wide transaction, `transaction` closes that one explicitly
     (`FreeCAD.closeActiveTransaction`), and it never closes an outer transaction that someone
     else opened.

   An undo step that must stay open across a task panel's lifetime (FreeCAD would otherwise
   commit it when the command returns) uses `surface_finish.UndoStep`: a persistent application
   transaction (`FreeCAD.setActiveTransaction(name, True)`) that the panel closes exactly once
   on OK or Cancel (`closeActiveTransaction`). Surface Finish, Weld Symbol and Insert Picture use
   it. Another FreeCAD action can commit such a step early (for example TechDraw's own drag of a
   picture); Insert Picture's Cancel then removes the new picture or writes the old values back
   itself.
7. **Qt liveness**: `fcgui.is_alive(obj)` before reusing widgets FreeCAD can delete.
8. **Levels**: user-actionable failures are errors or warnings; routine or periodic failures
   go to the log (the ribbon refresh logs a repeated failure only once); expected situations
   (user cancel, missing optional value) are silent.
9. **Startup recovery** failures are warnings; registration and FreeCAD startup continue.
10. **Prefix**: everything goes through `console` (`JellyJams: `). Messages forwarded by the
    Qt message filter carry no prefix (they are Qt's, not JellyJams').

---

## 9. Ribbon

### 9.1 Data flow

```
ribbon_layout.TABS            declarative content (pure)
        │  + set(FreeCADGui.listCommands())   after fcgui.preload_command_modules()
        ▼
ribbon_model.resolve()        fallbacks, skipped ids, entry ids (pure)  -> Resolved
        ▼
ribbon_widgets.RibbonUI       QDockWidget "JellyJamsCommandManager" holding QTabWidget "JellyJamsCommandManagerTabs"
        │  every click -> dispatch(cmd_id, index)
        ▼
ribbon.run_entry()            the single click dispatch point
```

The host is a `QDockWidget` (`JellyJamsCommandManager`) in the top dock area, with no dock features and an
empty title-bar widget, so FreeCAD's toolbar management on workbench switches does not touch
it (see [decisions.md](decisions.md#d-01-the-ribbon-is-a-dock-widget-not-a-toolbar)).

### 9.2 Layout data (`ribbon_layout.py`)

`TABS` holds five `Tab(title, groups)` objects. `RibbonUI` gives each tab one page and lays
its `Group(name, entries)` objects out left to right; a group's `name` is for readers of the
data only and is never drawn. What an entry turns into depends on its class and on where it
sits:

| What the renderer draws | Written in `TABS` as | Arguments that change the result |
|---|---|---|
| Large button: 32 px icon, caption under it | `Cmd(...)` directly inside a `Group` | `label` (a `"\n"` splits the caption); `index` (sub-entry of a group command such as `Std_DrawStyle`, also the way to give a duplicate its own entry id); `fallbacks` (ids tried in order when `cmd` is missing); `fc_icon` / `jj_icon` (icon sources, see [ribbon-engine](specs/ribbon-engine.md) 2.7) |
| Split button with an arrow menu | `Flyout(variants, title=None)` | `title` freezes the caption; without it the caption follows the current variant. Variant 0 is current unless the user has picked another one (stored under `Mod/JellyJams/FlyoutChoices`) |
| One slot whose command depends on sketch editing | `Toggle(normal, editing)` | none |
| Grid of 20 px buttons, three rows, filled column-major | `Stack(style, entries)`, written `_icons(...)` or `_text(...)` | `"icon"` draws bare icons; `"text"` adds a one-line caption beside each icon. Cells may be `Cmd` or `Flyout` |

Worked example, the Features tab's *Reference* group:

```python
Group("Reference", [
    Flyout([Cmd("Part_DatumPlane", "Plane", fallbacks=("PartDesign_Plane",)), ...],
           title="Reference\nGeometry"),
    Flyout([Cmd("Part_ProjectionOnSurface", "Projected Curve"), ...], title="Curves"),
    _text(Cmd("PartDesign_Body", "Body"), Cmd("PartDesign_Boolean", "Combine"),
          Cmd("PartDesign_SubShapeBinder", "Sub-Shape Binder")),
])
```

On screen: a `JellyJamsGroupDivider` rule (this is not the page's first group), then two large
split buttons captioned "Reference Geometry" (on two lines) and "Curves", whose icons change
with the chosen variant while the captions stay, then one column of three text-beside buttons.
On a build that lacks `Part_DatumPlane`, the first variant runs `PartDesign_Plane` and that id
also becomes the flyout's id.

Shorthands in the module: `_jj(cmd, label, index=None)` (a JellyJams command with
`jj_icon=COMMAND_ICONS[cmd]`), `_style(index, label, icon)` (one `Std_DrawStyle` sub-entry with
a FreeCAD icon name), `_text` and `_icons` (stacks). `iter_commands()` yields every `Cmd` in
ribbon order, stack cells and variants included; `all_command_ids()` lists each id once,
fallbacks included.

### 9.3 Resolution rules (`ribbon_model.resolve`)

* A command not in the available set is replaced by its first available fallback (recorded in
  `substitutions`; the entry id uses the substitute), else **skipped** (recorded in `skipped`).
* Missing flyout variants are dropped; a flyout with no variants disappears. The **flyout id**
  is the entry id of its first available variant.
* A toggle with both variants stays a toggle; with one it degrades to a plain button; with
  none it disappears.
* Empty stacks and empty groups are dropped (no gaps, no double separators).
* **Entry id** = `cmd` or `cmd#index`. **objectName** = prefix + entry id, the `#` written as
  `-`: `JellyJamsButton-<id>` (plain), `JellyJamsFlyout-<current variant id>` (flyout),
  `JellyJamsToggle-<shown variant id>` (toggle).

With every command available the model has **81 plain buttons, 27 flyouts with 84 variants
and 1 toggle (2 variants) = 167 unique entry ids**:

| Tab | Plain | Flyouts (variants) | Toggles | Separators | Top-level widgets |
|---|---|---|---|---|---|
| Features | 17 | 4 (11) | 0 | 3 | 21 |
| Sketch | 9 | 12 (35) | 1 | 3 | 22 |
| Evaluate | 21 | 1 (2) | 0 | 3 | 22 |
| Assembly | 10 | 3 (15) | 0 | 3 | 13 |
| Drawing | 24 | 7 (21) | 0 | 4 | 31 |

These numbers are pinned by `RIBBON_TAB_COUNTS` and `RIBBON_TOTALS` in the headless tests; the
widget counts match what `tests/gui_tabs.py` rendered on FreeCAD 1.1.4. Five flyouts have a
fixed title (`RIBBON_FLYOUT_TITLES`: Reference Geometry, Curves, Mate, Mechanical Mates,
Cosmetic Thread). Seven entries carry a fallback id (`RIBBON_FALLBACKS`): the four `Part_*`
datums (`PartDesign_*` ids), `PartDesign_NewSketch` (`Sketcher_NewSketch`),
`Sketcher_Projection` (`Sketcher_External`) and `TechDraw_Dimension`
(`TechDraw_LengthDimension`). `JellyJams_Diagnostics` is a large button on the Evaluate tab and is
also in the JellyJams menu. `JellyJams_NormalTo` is the Evaluate tab's Normal To (the first entry
of its View Orientation text stack, in place of FreeCAD's `Std_AlignToSelection`, which has no
button) and is also in the JellyJams menu and on `Ctrl+8`; the Sketch tab keeps
`Sketcher_ViewSketch`. `JellyJams_ViewOrientation` is the only JellyJams command without a ribbon
button (`OFF_RIBBON_COMMANDS` in the headless tests); it is in the JellyJams menu and on `Space`.

### 9.4 Build

`ribbon.show()` builds on the first call only:

1. `fcgui.preload_command_modules()` imports `GUI_COMMAND_MODULES` and
   `ASSEMBLY_COMMAND_MODULES` once per process, so commands of workbenches that were never
   opened are registered. GUI module failures: one warning each. Assembly module failures:
   one log line, and their skipped `Assembly_*` ids go only to that log line.
2. `icons.reset_index()` (newly loaded modules add icons to `:/icons`).
3. `resolve(TABS, set(listCommands()))`; substitutions are logged; other skipped ids produce
   one warning.
4. `RibbonUI(main_window, resolved, run_entry)`; info line
   `ribbon ready with N tabs: N buttons, N flyouts holding N tools, N toggle(s)`.

`ribbon.rebuild()` disposes and rebuilds, keeping the current tab index and visibility.

### 9.5 Dispatch: `ribbon.run_entry(cmd_id, index=None)`

Every button, flyout and toggle calls this one function:

1. `sketch_tools.stop_running(except_cmd=cmd_id)`: end a running Centerline / Midpoint Line
   mode unless the press is that same tool.
2. If `index is None` and `sketch_gesture.try_run(cmd_id)` returns True, stop. (A profile
   feature pressed while a sketch is open: the gesture leaves the sketch and starts the
   feature. A sketch-first feature pressed with nothing to use as the profile: it runs
   `PartDesign_NewSketch` instead and starts the feature once the new sketch is exited. A
   sketch-first feature pressed while a sketch-first plane picker is open: it only changes which
   feature runs at the end. Another profile feature pressed then goes to FreeCAD; a press while
   a sketch-first is picking with no dialog open drops that stale state and is handled fresh.)
3. Otherwise `fcgui.run_command(cmd_id, index)` (`FreeCADGui.runCommand`).

Picking a flyout variant from its menu makes it current, persists it in `Mod/JellyJams/FlyoutChoices`
(key = flyout id, value = variant entry id) and runs it.

### 9.6 Refresh and context tabs

While shown, a timer (`ribbon.REFRESH_MS`, 450 ms) refreshes the ribbon:

* Enabled state of every button from `FreeCADGui.Command.get(id).isActive()` (enabled when
  FreeCAD cannot tell). Toggles show `editing` while a sketch is in edit.
* Context tabs switch only on **transitions**: entering a sheet window selects Drawing and
  runs `projected_view.make_groups_movable(doc)` and `naming.refresh_drawing(doc)`; an
  assembly becoming active (`UtilsAssembly.activeAssembly()`) selects Assembly unless a sketch
  is in edit; entering sketch edit selects Sketch, and leaving it returns to the tab shown
  before. The sketch rule runs last so it wins within one refresh.
* With a sheet window active, every refresh calls `sheet_drag.attach(window)` (idempotent).

Visibility guard: the dock's `visibilityChanged` signal defers `hide_if_not_requested()` when
the dock becomes visible although the ribbon is not requested (FreeCAD's asynchronous window
state restore can re-show docks). `layout` calls `ribbon.show_if_requested()` after a deferred
apply and `ribbon.hide_if_not_requested()` after both restore passes.

### 9.7 Icons (`icons.command_icon`)

Precedence, first usable icon wins:

1. JellyJams commands only: the add-on's own icon (`jj_icon_name`, default
   `COMMAND_ICONS[cmd_id]`) from `resources/icons`.
2. The icon of the command's QAction (of sub-entry `index` for group commands).
3. `fc_icon`, then the command's `pixmap` from `getInfo()`, when it is an existing file path
   (absolute or `:/` resource).
4. The same names looked up by file stem in a lazily built index of `:/icons` (recursive,
   capped at 50,000 entries; exact match, then case-insensitive).
5. `FreeCADGui.getIcon(name)`, last because it may return a placeholder.

An icon-only stack button without an icon shows its text instead. The Add Relations panel
uses `RELATION_ICONS` for Collinear, Concentric and Midpoint and FreeCAD's icons otherwise.

### 9.8 Public API (`ribbon.py`)

| Function | Purpose |
|---|---|
| `show()` / `hide()` | lifecycle; `hide()` keeps the widgets |
| `show_if_requested()` / `hide_if_not_requested()` | visibility guard services for `layout` |
| `rebuild()` / `refresh_now()` | rebuild from the layout / one synchronous refresh |
| `is_requested()`, `is_built()`, `dock()` | state |
| `find_button(entry_id)` | live plain `QToolButton` (used by `JellyJams_RotateComponent` to update its tooltip) |
| `tab_titles()`, `current_tab_title()`, `context_tabs()` | tabs |
| `run_entry(cmd_id, index=None)` | the single click dispatch point |
| `entry_ids()`, `skipped_ids()`, `flyout_states()`, `toggle_states()` | test services |

---

## 10. Core API quick reference

| Module | Public names |
|---|---|
| `console` | `message`, `warning`, `error(text, with_traceback=False)`, `log`, `traceback_text`, `guard(what, level="error")`, `guarded(what, level="error", default=None)`, `safe_call(fn, *args, what="", level="log", default=None, **kwargs)`; levels `error` / `warning` / `log` / `silent` |
| `params` | `TYPE_SUFFIXES`, `CONTENTS_TYPE_NAMES`, `group(path)`, `own()`, `contents(grp)`, `has_key(grp, name, suffix)`, `get_value`, `set_value`, `remove_value`, `get_bool`, `get_float`, `get_string` (these three never raise), `backup_pending(key)`, `load_backup(key)` returning `("none", None)` / `("ok", data)` / `("corrupt", reason)`, `save_backup(key, data)`, `clear_backup(key, remove=False)` |
| `paths` | `addon_dir()` (uses `abspath`, not `realpath`, so a linked add-on keeps its load path), `icons_dir()`, `icon_path(base)` (`.svg`, then `.png`; `""` when missing or empty), `is_link(path)`, `user_cache_dir(*parts)` |
| `fcgui` | `qt`, `gui`, `main_window`, `active_workbench_name`, `jellyjams_active`, `task_dialog_open`, `active_gui_document`, `object_in_edit`, `sketch_in_edit`, `find_dock`, `task_dock`, `task_panel`, `mdi_area`, `active_mdi_widget`, `is_sheet_window`, `active_sheet_window`, `sheet_graphics_view`, `techdraw_tool_running(on_error=True)`, `rez`, `scene_to_sheet`, `status_message`, `clear_status`, `is_alive`, `defer(fn, ms=0)`, `selection`, `selection_ex`, `command_exists`, `command_info`, `run_command(cmd_id, index=None)`, `preload_command_modules()` |
| `doc_utils` | `CONTAINER_TYPES`, `MODEL_PRIORITY`, `PROFILE_2D_TYPE`, `is_alive`, `type_id`, `is_derived`, `is_contained`, `root_objects`, `primary_model_objects` (every root object of the highest-ranked `MODEL_PRIORITY` type; in the `Part::Feature` tier, `Part::Part2DObject` profiles such as sketches are skipped; shared by assembly drop and Make Drawing), `pages`, `parent_page`, `add_property` (adds only if missing), `transaction(doc, name, join_pending=False, abort_on_error=False)` (section 8 rule 6) |
| `commands` | `PROVIDERS`, `COMMAND_PREFIX`, `BaseCommand` (class attributes `command_id`, `menu_text`, `tooltip`, `icon`, `accel`, `cmd_type`, `active_on_error`; `GetResources` adds `Accel` and `CmdType` only when set), `register_all()`, `registered_ids()` |
| `lifecycle` | step tables, `run_steps`, `initialize`, `activated`, `deactivated`, `is_active`, `revert_for_quit`, `reapply_after_cancel` |
| `navigation` | `BACKUP_KEY`, `install()`, `uninstall()`, `recover()`, `is_installed()` (True while the style set by `install()` is in effect and its backup is pending) |
| `shortcuts` | `BACKUP_KEY`, `SHORTCUTS`, `install()`, `uninstall()`, `recover()`, `is_installed()`; the clashing-command scan covers the commands FreeCAD lists at `install()` time |

`API_NAMES` in [`tests/test_headless.py`](../tests/test_headless.py) lists the names the
tests require per module; keep it in sync when you add or rename a public function.

---

## 11. Cross-module calls

Calls between areas (all lazy and guarded unless the callee is a core module).

| Caller | Callee | Purpose |
|---|---|---|
| `InitGui.py` | `lifecycle.initialize/activated/deactivated`, `recovery.run_startup_recovery`, `paths.addon_dir` | workbench and startup |
| `recovery` | `viewport.recover`, `navigation.recover`, `shortcuts.recover`, `switch_prefs.recover` | crash recovery |
| `lifecycle` | every step function; `commands.register_all`; `diagnostics.environment_line/freecad_version` | lifecycle |
| `quit_guard` | `lifecycle.is_active/revert_for_quit/reapply_after_cancel` | quit |
| `layout` | `ribbon.show_if_requested`, `ribbon.hide_if_not_requested` | dock visibility |
| `ribbon` | `sketch_tools.stop_running`, `sketch_gesture.try_run`, `sheet_drag.attach`, `projected_view.make_groups_movable`, `naming.refresh_drawing` | dispatch and context hooks |
| `sketch_gesture` | `fcgui.run_command(constants.NEW_SKETCH_COMMAND)`, `fcgui.defer`, `doc_utils.is_derived` | sketch first: new sketch, watcher, plane check |
| `edit_guard` | `fcgui.object_in_edit`, `fcgui.defer`, `fcgui.jellyjams_active`, `sys._getframe` | command-string check over `FRAME_SEARCH_DEPTH` frames, deferred workbench-switch decision |
| `orientation` | `icons.command_icon`, `icons.jj_icon`, `icons.command_action`, `palette` colors (all imported lazily), `fcgui.run_command`, `fcgui.command_exists`, `fcgui.selection_ex`, `fcgui.sketch_in_edit`, `fcgui.status_message`, `fcgui.defer`, `fcgui.is_alive`, `fcgui.main_window().getActiveWindow()` (`FreeCADGui.activeView()` only without it; `getCameraNode`, `setCameraOrientation`), `fcgui.selection_ex("", 0)` and `FreeCAD.GeoFeature.getGlobalPlacementOf` (imported lazily), `FreeCADGui.Command.get(id).getShortcut()` / `.isActive()`, `QApplication.widgetAt(QCursor.pos())`, `QApplication.activeWindow()`, `QApplication.focusChanged`, `QToolTip.showText` | button icons, tooltips and enabled state, panel style, active state, Normal To, the hint, Space filter, docks made later, key repeat, click-outside close, keyboard return, running the view |
| `lifecycle` | `orientation.install` (A6), `orientation.uninstall` (D14), `appendMenu` with `CMD_ORIENTATION` and `CMD_NORMAL_TO` | Space filter while active; panel closed and filter removed on leave; menu entries that give `Space` and `Ctrl+8` a QAction |
| `relations_panel`, `mate_panel`, `context_sketch` | `icons.command_icon`, `icons.jj_icon`; `palette` colors for the context popup | icons, styling |
| `assembly_commands` | `ribbon.find_button`, `fcgui.preload_command_modules` | tooltip, Assembly commands |
| `make_drawing` | `doc_utils.primary_model_objects`, `templates`, `projected_view.apply_start_layout` | new drawing |
| `assembly_drop` | `doc_utils.primary_model_objects` | same primary-object rule as Make Drawing |
| `sheet_text`, `weld_symbol`, `projected_view` | `sheet_pick.start/cancel/is_active/set_status` | on-sheet clicks |
| `sheet_drag` | `sheet_pick.is_active`, `surface_finish.open_editor`, `weld_symbol.open_editor` | gating, double-click on JellyJams symbols |
| `view_labels` | `sheet_drag.is_dragging` | labeling waits while a view drag holds its `Move View` step open |
| `insert_picture`, `weld_symbol` | `surface_finish.UndoStep` (weld symbol through `surface_finish.open_in_undo_step`) | undo step that lasts until the panel closes |
| `view_labels`, `view_scale`, `make_drawing`, `sheet_properties` | `drawing_common.scale_text/parse_scale` | scale text |
| `drawing_export` | `zoom_lines.restore_all`, `pdf_merge.merge`, `drawing_common.open_sheet_window` | standard line widths in output, one PDF, render unopened sheets |
| `naming` | `fcgui.techdraw_tool_running`, `constants.PROJECTION_VIEW_LABELS` | postpone during TechDraw tools, view names |

---

## 12. How to extend JellyJams

### 12.1 Add a ribbon button for a FreeCAD command

1. Edit **only** [`ribbon_layout.py`](../jellyjams/ribbon_layout.py). Add
   `Cmd("<FreeCAD command id>", "Label")` to the right `Group` of the right tab, or inside a
   `Stack(...)` / `Flyout([...])`. Use `"\n"` in the label for the line break of a large
   button.
2. If the command belongs to a workbench module that FreeCAD loads only when that workbench
   is first opened, add the module to `GUI_COMMAND_MODULES` or `ASSEMBLY_COMMAND_MODULES` in
   [`constants.py`](../jellyjams/constants.py) so the build preloads it.
3. If FreeCAD renamed the command between versions, list the other id in `fallbacks=(...)`.
4. For one sub-entry of a FreeCAD group command, pass `index=` and `fc_icon=` with the
   resource icon stem (a sub-entry may have no action icon until FreeCAD creates its
   actions). Two entries of the same command need different indices so their entry ids
   differ.
5. Changing a flyout's first variant changes its flyout id, so users' remembered choice for
   that flyout falls back to the default.
6. Update the expectations in [`tests/test_headless.py`](../tests/test_headless.py)
   (`RIBBON_PLAIN`, `RIBBON_FLYOUTS`, `RIBBON_FLYOUT_TITLES`, `RIBBON_TAB_COUNTS`,
   `RIBBON_TOTALS`, `RIBBON_TOGGLE`, `RIBBON_FALLBACKS`, and the stack lists in
   `Test13RibbonModel.test_stacks`) and the content tables in
   [`specs/ribbon-content.md`](specs/ribbon-content.md).
7. Run the headless tests, then `tests/gui_tabs.py` on a throwaway config to see the tab.

The engine (`ribbon_model`, `ribbon_widgets`, `ribbon`) does not change for content edits.

### 12.2 Add a JellyJams command

1. In [`constants.py`](../jellyjams/constants.py): add `CMD_X = "JellyJams_<ToolName>"` (the
   ribbon name without spaces), append it to
   `ALL_COMMANDS`, and add `COMMAND_ICONS[CMD_X] = "<icon base name>"`.
2. Add an original SVG `resources/icons/<icon base name>.svg`: `viewBox="0 0 64 64"`,
   readable at 16 to 20 px, palette colors, the license comment after the XML declaration, no
   `<text>`, `<style>`, `<image>` or `<script>` elements, and no "solidworks" in the file name.
   A missing icon is not fatal: `GetResources()` then returns an empty `Pixmap`.
3. In the providing module, subclass `commands.BaseCommand`: set `command_id`, `menu_text`,
   `tooltip`; override `run()` and, if needed, `is_active()`. A command that only moves the
   camera sets `cmd_type = "Alter3DView"` so FreeCAD keeps it available while a sketch or a
   task dialog is open; leave `cmd_type` empty for anything that changes the document or the
   selection. Return it from the module's
   `get_commands()` (no side effects besides building instances).
4. If the module is new, add it with its ids to `commands.PROVIDERS`.
5. Put it on the ribbon with `_jj(C.CMD_X, "Label")` (12.1). A command that is deliberately
   not on the ribbon (like `JellyJams_ViewOrientation`) goes into `OFF_RIBBON_COMMANDS` in the
   headless tests instead.
6. Update `EXPECTED_COMMANDS`, `EXPECTED_PROVIDERS`, `EXPECTED_MENU_TEXTS`, `COMMAND_ICONS` and
   `CONSTANT_VALUES` in the headless tests.
7. If the command needs a keyboard shortcut, add it to `shortcuts.SHORTCUTS` (exact restore,
   clashing commands unbound; `EXPECTED_SHORTCUTS` in the tests) and list the command in the
   JellyJams menu (`lifecycle._add_menu_once`): FreeCAD creates a command's `QAction`, and so
   a working shortcut, only for commands in a menu or toolbar; a ribbon button is not enough.

### 12.3 Add a feature module

1. Create `jellyjams/<name>.py` with the three header lines. Follow the import rules
   (section 4): core modules at top level, other areas lazily and guarded. Put pure logic in a
   separate pure module so it can be tested headlessly (and add it to `PURE_MODULES`).
2. If the feature is switched on while JellyJams is active, expose idempotent
   `enable()` / `disable()` (or `start()` / `stop()`), add a step to `ACTIVATION_STEPS` and the
   matching step to `DEACTIVATION_STEPS` in [`lifecycle.py`](../jellyjams/lifecycle.py).
   Keep `layout` first on activation and last on deactivation. The `what` phrase is what users
   read in `JellyJams: could not <what>:`.
3. If it needs a session-long observer, add it to `INIT_HELPERS` and gate its callbacks on
   `fcgui.jellyjams_active()` where the behavior is JellyJams-only.
4. Wrap every FreeCAD / Qt callback with `console.guarded(...)` and close transactions with
   `doc_utils.transaction(...)` (section 8).
5. Add the module to `EXPECTED_MODULES` (and its public names to `API_NAMES`) and mirror any
   step-table change in the test's `INIT_HELPERS` / `ACTIVATION_STEPS` / `DEACTIVATION_STEPS`.
6. Write or extend the spec under [`specs/`](specs) and add a row to the module map above.

### 12.4 Override a persistent FreeCAD setting

Anything FreeCAD saves (parameters, window state) needs the full restore discipline:

1. Before the first write, record the previous value **or that the key was absent** (use
   `params.has_key`, which checks type and name) in a new `KEY_*_BACKUP` string in
   `Mod/JellyJams`; add it to `BACKUP_KEYS`. Never overwrite a pending backup.
2. Restore exactly: set recorded values back, remove keys that were absent, then clear the
   backup.
3. Provide `recover()` and add a step to `recovery.RECOVERY_STEPS`; discard an unreadable
   backup with one warning.
4. Add the restore to `QUIT_REVERT_STEPS` and the apply to `QUIT_REAPPLY_STEPS`.
5. Extend `BACKUP_KEYS` in [`tests/gui_smoke.py`](../tests/gui_smoke.py),
   [`tests/gui_lifecycle.py`](../tests/gui_lifecycle.py) and
   [`tests/check_saved_cfg.py`](../tests/check_saved_cfg.py), and add headless round-trip
   tests (absent key, user value, pending backup, failing setter).

Another module's "switch to my workbench" Bool of the same three-state kind needs no new
module: add a `(group, backup key, name)` row to `switch_prefs.TARGETS` with new
`PARAM_*` / `KEY_*_BACKUP` constants, then do steps 1 and 5 for it (`SWITCH_BACKUPS` in the
headless tests, `SWITCH_GROUPS` in the GUI scripts and `check_saved_cfg.py`).

---

## 13. Tests and current status

Widgets and the viewport share the read-only `theme.is_dark()` native menu-palette
decision. `palette.viewport_colors(dark)` and `viewport.managed_keys(dark)` choose
matching background/sketch values without changing the 14-key backup contract.

The theme-following update adds `tests/gui_theme.py` and the `theme_dark` /
`theme_light` GUI runner suites. `theme.widget_colors()` reads the native menu
palette; `palette.widget_colors(dark)` returns a pure widget palette. The
main-window block and JellyJams popups share the selected colors (decision D-19).
No application stylesheet/palette or native theme preference is modified.

The 2026-10-29 audit adds GitHub Actions (`.github/workflows/tests.yml`), a
standard-library GUI runner (`tests/run_gui.py`), its result-validation tests
(`tests/test_gui_runner.py`), real feature integration (`tests/gui_features.py`)
and abrupt-exit/restart recovery (`tests/gui_crash.py`). The runner owns disposable
config paths, executes scripts sequentially, validates JSON and enforces timeouts.
See [testing.md](testing.md#automated-runner-and-ci-2026-10-29) for the full command
and [status.md](status.md#2026-10-29-audit) for current results. The older baseline
table below is retained as historical evidence.

| Layer | How to run | What it covers |
|---|---|---|
| Headless | `"C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/test_headless.py` | stubbed FreeCAD / FreeCADGui ([`tests/headless_stubs.py`](../tests/headless_stubs.py)) with real offscreen Qt: metadata, hygiene, InitGui, recovery, commands, lifecycle tables and fault isolation, quit-guard logic, Qt filter, diagnostics, palette contrast, theme, viewport, layout, navigation, shortcuts, ribbon model and widgets, naming / relations / mate rules, the three `SwitchToWB` overrides (`switch_prefs`), dialog terms, drawing helpers, PDF merge, icons, sketch first (`needs_new_sketch` and `advance` truth tables, `try_run` and the watcher with a fake Part Design document, including container selections, subtractive features with FreeCAD's `isSolid` rule, the Hole refusal on a fresh press and while picking, cutting features left to FreeCAD without a target body, stale plane picks, the status hint, the insert point and the lone body), the feature-edit guard (command strings simulated by code compiled as `<string>`, found through one or more other add-ons' wrappers up to `FRAME_SEARCH_DEPTH`), the Orientation panel and Normal To (offscreen: `CmdType`, active while the stub main window's `getActiveWindow()` is a 3D view, the `activeView()` fallback, Normal To's one-pick rule with fake selections and shapes, looking at whole sketches through a fake 3D view along a stub `GeoFeature.getGlobalPlacementOf` path, the hint in the status bar and as a tool tip, layout, clicks, pin, the Normal To button closing the panel, click outside with its generation, keyboard and settle-time checks under a fake clock, the keyboard back to the window that had it, keys and their auto-repeat, the Space filter with real key clicks, the pointer rule with Qt's real `widgetAt`, Tab-focused panel buttons, toolbars / status bar / ribbon, item views, the filter on docks, floating docks and docks made later, theme-proof colors, enabled state, icons, placement, close on leave), the Evaluate tab's Normal To button, and document-level behavior with fake documents (`doc_utils.transaction`, primary model objects, pending-link naming, view labels, sheet format switch, view drag, Insert Picture file checks) |
| GUI smoke | `FreeCAD.exe -u <copy of user.cfg> -s <copy of system.cfg> tests/gui_smoke.py` | real FreeCAD: registration, ribbon (each page holds the buttons, flyouts, toggles and separators the model resolves for that FreeCAD's commands; JellyJams plain buttons present), theme, navigation, shortcuts (including Ctrl+B ownership), the three SwitchToWB, backups, naming of a Pad, a Sketch and the origin planes, staying in JellyJams on assembly activation, restore on leave (stylesheet, navigation, shortcuts, SwitchToWB, backups cleared and removed, menu, ribbon, toolbars) |
| GUI lifecycle | set `JELLYJAMS_LIFECYCLE_MODE` to `cancel`, `discard`, `after` or `autoload`, then run `tests/gui_lifecycle.py` the same way | quit guard with Cancel and Discard inside the "Save changes?" prompt, fresh start after a discard-quit, autoload deferral |
| GUI sketch first | `tests/gui_sketch_first.py` the same way | Extruded Boss/Base with a plane selected, with nothing selected (plane picker, cancel) and with a free sketch; editing a Pad stays in JellyJams; `Std_Workbench` still switches |
| GUI orientation | `tests/gui_orientation.py` the same way | `Space` and `Ctrl+8` on the JellyJams commands with Hide/Show unbound and `Std_AlignToSelection` untouched, both commands in the menu, no key repeat; Space opens the panel with 13 view buttons; Top applied and the panel closed; pinned Front stays open; Esc closes; click outside, and a deactivation right after opening; Normal To with nothing selected (status bar and tool tip), from the panel's button, with a face, with two faces, with a whole sketch, with an origin plane, with a curved face, a datum line and an origin axis (compared with FreeCAD's own Align to Selection) and with a sketch through a link; the Evaluate tab's Normal To; a Tab-focused panel button with the pointer over the 3D view; Space after a choice in the workbench selector; an undocked 3D view and the keyboard back to it; the Start page in front; the panel under a white-text application stylesheet; Space, Esc and `Ctrl+8` while a sketch is in edit; Space on a focused check box of the Pad dialog with the pointer over the task panel and over the 3D view, in a floating Tasks dock and in a dock made after activation; Hole Wizard without a solid and with two bodies and none active; the panel closes on leave, the keys come back and the Space filter is gone |
| Saved config | `python tests/check_saved_cfg.py <user.cfg> <nav> <assembly> <partdesign> <techdraw>` | the `user.cfg` written on quit holds no JellyJams state and the user's three `SwitchToWB` |
| GUI tabs | `tests/gui_tabs.py` | renders all five tabs, records button kinds and separators per tab and saves screenshots |

Always run the GUI scripts with throwaway copies of `user.cfg` and `system.cfg` (see
[testing.md](testing.md#rule-never-touch-your-real-freecad-profile)).

Status as of 2026-10-28 (FreeCAD 1.1.4 on Windows):

| Suite | Result |
|---|---|
| `tests/test_headless.py` (FreeCAD 1.1.4 Python, stubbed FreeCAD) | 489 tests, all pass |
| `tests/gui_orientation.py` | 84 / 84 |
| `tests/gui_sketch_first.py` | 20 / 20 |
| `tests/gui_smoke.py` | 31 / 31 |
| `tests/gui_lifecycle.py`, mode `cancel` | 16 / 16 |
| `tests/gui_lifecycle.py`, mode `discard` (+ `tests/check_saved_cfg.py`) | 9 / 9, saved config clean (`check_saved_cfg.py` 7 / 7) |
| `tests/gui_lifecycle.py`, mode `after` | 5 / 5 |
| `tests/gui_lifecycle.py`, mode `autoload` | 6 / 6 |
| `tests/gui_tabs.py` | all five tabs render (Features 21 buttons, Sketch 22, Evaluate 22, Assembly 13, Drawing 31) |
| Addon Manager install from https://github.com/jus-kim/JellyJams | not run yet (needs the published repository) |

Every GUI row was recorded on 2026-10-28 on FreeCAD 1.1.4; details in [status.md](status.md#test-results).

Feature behavior that no GUI script exercises (for example the drawing tools, the Add
Relations and Add Mate panels, the sketch tools, dialog terms) is covered by headless logic
tests only and is **not verified** end to end on real FreeCAD by the automated suites. See
[status.md](status.md) for the details and the known gaps.

## Temporary Measure task

`measure.py` (runtime; [Measure](specs/measure.md))
flattens unresolved selection paths and resolves world-space shapes lazily through
Part. Circular edges/arcs become centre vertices and cylindrical faces become
finite axis segments by default; a task-local clearance mode uses the original
shapes. Both are measured with `distToShape`. A selection observer coalesces clear/add notifications into a deferred
refresh, restoring earlier picks only for native clear-then-add replacement in
the same event. Single picks report entity size; pairs report distance/angle
with optional XYZ components; homogeneous multi-picks report totals. Chronological
pick order is retained for three-point angles even when plain and additive clicks
are mixed. Lifetime checks use the actual front window, including Start/drawing
windows; retired callbacks cannot stop a later session, and cleanup drops cached
graphics even after the old view is deleted. Formatting
uses FreeCAD's unit schema, including area/volume and angle units.

The task owns a single unpickable Coin `SoAnnotation` (always rendered above
model geometry). A Qt-painted RGBA table becomes a constant-screen-size Coin
`SoImage`: white background, black border, black labels/values and a divider.
Its black leaders have a white underlay. The task also owns a Python task
form and a lifetime timer. Ribbon dispatch starts it; ribbon hide stops it for
leave and quit. Form destruction and document/view changes also clean it up.
There are no persistent settings, document edits, command registrations or new
lifecycle steps. Existing saved native measurements remain user-owned.

Measure's ribbon entry remains a plain command slot in the content model, with
a runtime checkable state. `measure.toggle()` starts/stops the task; `is_active()`
is authoritative. `ribbon.refresh_measure_button()` synchronizes only that button
on start, stop and form destruction, avoiding unrelated context/UI work while a
task is being destroyed. Periodic ribbon refresh repeats that synchronization
after native enabled-state updates and forces the active button enabled so it
can stop. Its checked-state highlight is in the existing scoped theme block.
