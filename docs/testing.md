# Testing

JellyJams has two test layers:

1. **Headless suite**: [`tests/test_headless.py`](../tests/test_headless.py) with
   [`tests/headless_stubs.py`](../tests/headless_stubs.py). 528 tests against stubbed
   `FreeCAD` / `FreeCADGui` modules and an offscreen Qt. No FreeCAD window, no profile touched.
   Run it before every commit.
2. **GUI acceptance scripts**: [`tests/gui_smoke.py`](../tests/gui_smoke.py),
   [`tests/gui_lifecycle.py`](../tests/gui_lifecycle.py), [`tests/gui_sketch_first.py`](../tests/gui_sketch_first.py),
   [`tests/gui_orientation.py`](../tests/gui_orientation.py), [`tests/gui_tabs.py`](../tests/gui_tabs.py),
   plus the config inspector [`tests/check_saved_cfg.py`](../tests/check_saved_cfg.py). They drive
   the real FreeCAD GUI and must always run with a throwaway profile.

Current results and what is still unverified: [status.md](status.md). Behavior the tests check
against: [specs/README.md](specs/README.md).

## Automated runner and CI (2026-10-29)

`python tests/run_gui.py --suites report_view report_startup` verifies preservation
of a closed Report view in real FreeCAD. The first process checks activation,
explicit open/close, delayed layout and leave, then saves a disposable profile
configured to autoload JellyJams. The second process uses that saved profile to
check actual startup and leave. Expected checks: 7 and 3; `report_startup` must
follow `report_view`. Actual quit-prompt/Cancel visibility is checked by the
cancel/discard lifecycle modes too. FreeCAD's auto-show-on-message options are
not disabled by this feature.

Run the appearance browser regression with
`python tests/run_gui.py --suites appearances`. Its 38 checks cover read-only
previews/search, real thumbnail double-clicks, native face/body/component
materials, Undo/Redo, atomic rollback, `.FCStd` persistence and dock cleanup.
It writes `appearances.json`, panel/full screenshots and a sample model under
the runner's unique scratch folder. Lifecycle cancel/discard/autoload checks
also include presence/absence of the appearance dock. All use disposable configs.

The GitHub Actions workflow [tests.yml](../.github/workflows/tests.yml) runs the
headless suite and GUI-result validator tests on pushes, pull requests and manual
dispatch, on Windows and Ubuntu with Python 3.11 and PySide6 6.8.3. FreeCAD APIs are
stubbed; this does **not** certify real FreeCAD behavior on either platform.
Linux job installs `libegl1` and `libopengl0` before importing Qt, including with
the offscreen platform. The checkout/Python setup actions use maintained v7 releases.
The three installed-template checks skip when FreeCAD's ISO templates are absent.
Hosted CI execution must be checked after pushing; a local passing test is not a
hosted CI result.

`Test25Appearances` is part of that same CI command, so its 15 tests run on both
matrix operating systems without a FreeCAD installation. They cover validation,
target selection, component-only material writes, transaction abort/cleanup,
read-only browsing and dock lifecycle (deferred startup and quit/Cancel), failed
selection queries, unrelated active transactions and failed panel construction.
Run just those tests locally with `python tests/test_headless.py -q -k Appearances`.
Native rendering, actual material rollback, Undo/Redo and file persistence remain
in `gui_appearances.py`, which runs separately in real FreeCAD with scratch profiles.

Pointer-dependent orientation checks use the widget's own screen in
`QCursor.setPos(screen, point)` and record requested/actual cursor coordinates.
The no-screen overload targets the primary screen; the explicit screen avoids
that assumption on mixed-DPI desktops ([Qt 6.8 QCursor documentation](https://doc.qt.io/qt-6.8/qcursor.html)).
Orbit cleanup comparisons recreate the baseline viewport dimensions after stock
dock/toolbars are restored, because native orbit response depends on viewport
size. Neither harness adjustment changes production Space routing or navigation.

To run all real FreeCAD suites locally, with JellyJams already installed:

```powershell
& "C:/Program Files/FreeCAD 1.1/bin/python.exe" tests/run_gui.py
```

The standard-library runner creates a unique `scratch/gui_*` directory, starts
each GUI process sequentially with fresh `-u` / `-s` paths, waits for that exact
process, and reads its JSON. It never copies or writes the real user/system
configuration. FreeCAD still loads installed add-ons and uses its usual caches.
Use `--freecad <exe>` for another installation, `--timeout <seconds>` (default
240 per process), or `--suites smoke sketch orientation features tabs cancel
discard after autoload crash recover` to select suites. `after` must follow
`discard`, and `recover` must follow `crash`; each pair shares only its disposable
config files. Keep other FreeCAD windows closed and avoid input during tests.

The runner exits nonzero for a failed process, timeout, missing result, exception,
failed assertion, insufficient check count or incomplete five-tab capture. It also
runs `check_saved_cfg.py` after Discard and writes `summary.json`. The `crash`
process deliberately exits 86 after saving active preferences; only that suite
accepts that exit code. `test_gui_runner.py` tests result validation without Qt.

`gui_features.py` adds real integration checks for command availability, custom
dock-title colors, Add Relations (Horizontal and Delete button clicks), Centerline
and Midpoint Line processing against real Sketcher geometry, Make Drawing with
scratch file/format pickers, Drawing context, projections, scale, text, sheet
properties, symbol panels, picture insertion, PDF/DXF, New Assembly, Rotate
Component, Add Mate and component insertion. Some checks call the same helpers the
buttons use; they do not simulate every pointer gesture or native file dialog.

`gui_assembly_tree.py` creates a separate new assembly with an empty document
already open, selects it, and sends 100 native pointer clicks to the Assembly and
Origin expand/collapse triangles. Each click must toggle the targeted branch
after returning to the event loop; the assembly and JellyJams must remain active.
Run `python tests/run_gui.py --suites assembly_tree`. The expected result is 104
passing checks in `assembly_tree.json`. It saves partial results before every
click, a final screenshot and Python stack snapshots every 20 seconds. A native
hang may require a native stack capture as well; an empty Python stack does not
establish its cause. FreeCAD may rebuild tree items on selection changes, so the
test resolves the current row afresh on every step.

`gui_crash.py` saves parameters while JellyJams is active and exits without close
events or the quit guard. A second process compares the 14 managed color keys,
navigation, managed shortcuts and conflicting native shortcuts, and all three
SwitchToWB preferences, including absent keys, with their pre-activation state.
It also checks cleared backups and a hidden ribbon. It does not simulate every
possible crash point or assert the complete toolbar geometry.

`--suites theme_dark theme_light` seeds fresh scratch profiles with the installed
FreeCAD Dark/Light themes and runs `gui_theme.py` (22 checks per mode). It checks
actual native theme loading, ribbon/dock/popup colors, unchanged application
stylesheet and theme settings, and exact restoration on leave. A real sketch has
unconstrained, blocked and construction lines plus driving/reference dimensions;
rendered pixels verify their actual colors and the viewport background, and all
14 managed color keys are checked before/after leaving. The native theme
settings are written only into disposable XML configs before starting FreeCAD.
Screenshots are `<mode>_active.png`, `<mode>_orientation.png` and
`<mode>_restored.png`, `<mode>_sketch.png` (the rendered 3D view) and
`<mode>_sketch_window.png`. These two suites are included in the default full run.

`--suites orbit` runs `gui_orbit.py` (49 checks) against real FreeCAD mouse/key
event handling. It compares horizontal/vertical camera angles in all five orbit
modes at normal and ultrawide sizes; checks native Ctrl-pan, Shift-zoom and middle
clicks against a deterministic camera fixture; tests modifier transitions, cursor
warp bypass and removal mid-drag; then checks the original native response after
leaving. It discovers a view created after activation and verifies no orbit/pivot/
sensitivity preferences changed. It sends Qt events directly to the actual 3D
widget, avoiding dependence on desktop pointer placement. It measures software
response, not physical mouse latency or exact parity with SolidWorks. It also
accepts a native Pad edit dialog with its OK button focused and then orbits the
body, repeating 20 times. The immediate-focus-scan implementation crashed on the
first acceptance; deferring discovery until the event loop resumes passes this
regression. Headless tests additionally check deferral, coalescing and cancellation.

The lifecycle suites also require the runtime orbit hook to be absent inside the
quit prompt, restored after Cancel, and correctly installed/removed with autoload.

## Contents

- [Test inventory](#test-inventory)
- [Rule: never touch your real FreeCAD profile](#rule-never-touch-your-real-freecad-profile)
- [Prerequisites](#prerequisites)
- [Headless suite](#headless-suite)
- [GUI acceptance scripts](#gui-acceptance-scripts)
- [Manual checks (not automated)](#manual-checks-not-automated)
- [Adding tests](#adding-tests)

## Test inventory

| File | Kind | Runs in | Covers | Output |
|---|---|---|---|---|
| [`tests/test_headless.py`](../tests/test_headless.py) | Unit and integration tests (unittest) | FreeCAD's bundled `python.exe`, no window | Logic of every module, metadata, hygiene, icons | Console; exit code 0 = all pass |
| [`tests/headless_stubs.py`](../tests/headless_stubs.py) | Stub `FreeCAD` / `FreeCADGui` / `PySide` environment | imported by the suite | n/a | n/a |
| [`tests/gui_smoke.py`](../tests/gui_smoke.py) | GUI acceptance, 31 checks | `FreeCAD.exe` | Activate, ribbon (pages compared with the resolved model, JellyJams plain buttons), theme, navigation, shortcuts, the Assembly, Part Design and TechDraw `SwitchToWB`, crash backups, JellyJams menu, tree naming, Assembly tab, staying in JellyJams, full restore on leave | `gui_smoke_results.json`, `jellyjams_active.png`, `jellyjams_restored.png` |
| [`tests/gui_lifecycle.py`](../tests/gui_lifecycle.py) | GUI acceptance, four modes selected by `JELLYJAMS_LIFECYCLE_MODE` | `FreeCAD.exe` | Quit guard with Cancel and Discard, relaunch after Discard, autoload | `lifecycle_<mode>.json` |
| [`tests/gui_sketch_first.py`](../tests/gui_sketch_first.py) | GUI acceptance, 20 checks | `FreeCAD.exe` | Sketch first for Extruded Boss/Base (plane selected, nothing selected with the plane picker cancelled, a free sketch used directly), staying in JellyJams while a Pad is edited, `Std_Workbench` still switching | `sketch_first.json` |
| [`tests/gui_orientation.py`](../tests/gui_orientation.py) | GUI acceptance, 84 checks | `FreeCAD.exe` | The Orientation panel and Normal To: `Space` and `Ctrl+8` on the JellyJams commands (menu entries, no key repeat, `Std_AlignToSelection` untouched), a real Space key press opens the panel, 13 view buttons, Top, pinned Front, Esc, Space on a Tab-focused view button, click outside after the 0.3 s settle and not before it (the panel takes the keyboard back), Normal To with nothing (status bar and tool tip; the panel's button closes the panel) / a face / a whole sketch / an origin plane / two faces / a curved face / a datum line / an origin axis / a sketch through a rotated link / a sketch in edit, the Evaluate tab's Normal To button, readable under a white-text app stylesheet, Space on the focused workbench selector, an undocked 3D view (and the keyboard given back to it), the Start page in front, Space and Ctrl+8 inside sketch edit and a Pad dialog, Space by pointer position (3D view or task panel), in a floating Tasks dock and in a floating dock made after activation, Hole in an empty body and with two bodies none active, everything closed and given back on leave | `orientation.json`, `orientation_dark_panel.png` |
| [`tests/check_saved_cfg.py`](../tests/check_saved_cfg.py) | Config inspector, 7 checks | any Python 3 (standard library only) | The `user.cfg` FreeCAD saved after a Discard quit | JSON on stdout; exit code 0 = clean |
| [`tests/gui_tabs.py`](../tests/gui_tabs.py) | Visual QA, no assertions | `FreeCAD.exe` | All five ribbon tabs render; button counts, button kinds and separators per tab | `tabs_results.json`, `tab_<n>_<name>.png`, `tabs_full_window.png` |

GUI output goes to the folder named by the environment variable `JELLYJAMS_RESULTS_DIR`, default
`<repo>\scratch` (git-ignored; the scripts create it).

## Rule: never touch your real FreeCAD profile

- The **headless suite** is safe by construction: FreeCAD is stubbed, parameters live in memory,
  and its temporary user folder (`jj_headless_user_*` in the system temp folder) is deleted at exit.
- The **GUI scripts** switch JellyJams on and off, change preferences while it is active
  (navigation style, shortcuts, View colors, the three `SwitchToWB`), create unsaved documents and quit
  FreeCAD, which then saves its configuration. Run them only with one of these:
  1. **`-u` / `-s` with copies** of `user.cfg` and `system.cfg` (all recorded results were made
     this way). These flags replace only the two config files. Add-ons (`Mod`), macros and caches
     still come from `%APPDATA%\FreeCAD\v1-1\`.
  2. **`FREECAD_USER_HOME` set to an empty folder.** This redirects the whole profile. Observed
     with `FreeCADCmd.exe` 1.1.4: `FreeCAD.getUserAppDataDir()` returns that folder itself, and
     `user.cfg` / `system.cfg` are created directly in it, so the add-on must be linked at
     `<folder>\Mod\JellyJams`. GUI runs with this variable are **not verified**.
- Never start a GUI script without one of the two.

## Prerequisites

- Windows with FreeCAD 1.1.x at `C:\Program Files\FreeCAD 1.1` (adjust the paths below if it is
  elsewhere). Recorded results: FreeCAD 1.1.4.
- **Headless suite:** nothing else. The harness puts the repository first on `sys.path`; the add-on
  does not need to be installed.
- **GUI scripts:** JellyJams must be installed in FreeCAD's `Mod` folder, because FreeCAD loads it
  at startup. For a working copy, link the repository (only one copy should be installed; a second
  one is skipped with a warning):

  ```powershell
  New-Item -ItemType Junction -Path "$env:APPDATA\FreeCAD\v1-1\Mod\JellyJams" -Target "C:\path\to\JellyJams"
  ```

- Close other FreeCAD windows before a GUI run (recommended), and do not use the mouse or keyboard
  in the test window while a script runs.

## Headless suite

### Run

From the repository root (the script also works from any folder when given its full path):

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" tests\test_headless.py
```

| Option / variable | Effect |
|---|---|
| (none) | Verbose list of every test, then the summary line |
| `-q` | Quiet output |
| `-k PATTERN` | Run only tests whose name contains `PATTERN` (standard unittest; may be repeated), for example `-k Ribbon`, `-k test_viewport` |
| `Class` or `Class.method` | Run one class or one test, for example `Test10Look` or `Test09Diagnostics.test_format_block` |
| `-f` | Stop at the first failure (standard unittest option) |
| `JELLYJAMS_ECHO_CONSOLE=1` | Also echo the captured FreeCAD console output to stderr (`$env:JELLYJAMS_ECHO_CONSOLE = "1"`) |

A passing run ends with a line like this (about 28 s on the reference machine):

```
JellyJams headless harness: 489 tests, 0 failures, 0 errors, 0 skipped in 28.3 s (FreeCAD PySide shim)
```

- **Exit code** 0 when every test passed, otherwise 1. The process ends without Python's and Qt's
  clean-up, so that tearing down Qt objects cannot turn a clean run into a crash: on Windows with
  `TerminateProcess`, which also skips unloading the Qt and PySide libraries (that alone crashed
  some runs), elsewhere with `os._exit`.
- **Watchdog:** after 300 s the suite dumps every thread's stack (faulthandler) and exits, so a hang
  never blocks a pipeline.
- **Interpreter:** use FreeCAD's bundled `python.exe` (Python 3.11, PySide6 6.8.3). The stubs then
  use FreeCAD's own `PySide` shim from `<FreeCAD>\Ext`; without it they alias `PySide` to `PySide6`.
  Other interpreters are not verified.
- **Skips:** the three template tests in `Test19DrawingHelpers` skip when FreeCAD's ISO templates are
  not found under `<FreeCAD>\data\Mod\TechDraw\Templates\ISO`.

### How it works

- `headless_stubs.install()` runs before anything from `jellyjams` is imported. It selects Qt's
  offscreen platform, creates the `QApplication`, puts the repository first on `sys.path`, provides
  `PySide`, and registers in-memory `FreeCAD` and `FreeCADGui` modules.
- Stub `FreeCAD`: `ParamGet` over an in-memory tree (Get / Set / Rem for Bool, Int, Unsigned, Float,
  String; `GetContents()` with FreeCAD 1.1 type names), captured `Console`, `Version()` = 1.1.4,
  `getUserAppDataDir()` = a temporary folder, `getResourceDir()` = FreeCAD's real data folder when
  present, document observers recorded, and `GeoFeature.getGlobalPlacementOf(target, root, path)`
  (calls recorded in `STUBS.placement_calls`; it returns `target.getGlobalPlacement()`, as FreeCAD
  does for a path without links).
- Stub `FreeCADGui`: `Workbench`, `addWorkbench` / `listWorkbenches`, `addCommand` / `listCommands` /
  `runCommand` (recorded), `Command.get`, `getMainWindow()` returning a real offscreen `QMainWindow`
  with FreeCAD 1.1's `getActiveWindow()`, a settable active workbench, `Selection` (with
  `getSelectionEx("", 0)` giving the unresolved selection when a test sets one),
  `Control.activeDialog()`, `ActiveDocument`, and `activeView()` returning what a test sets with
  `STUBS.set_active_view(...)` (None by default; an exception instance is raised). The main
  window's `getActiveWindow()` returns the same unless a test sets something else with
  `STUBS.set_active_window(...)`.
- Every test starts from fresh stub state (`STUBS.reset()` in `HarnessCase.setUp`).
- Tests import the module under test inside the test (`self.module(...)`), so a missing or broken
  module fails only its own tests and the run continues.

### What it covers

| Class | Tests | Covers | Spec |
|---|---|---|---|
| `Test01ReleaseMetadata` | 10 | `package.xml`, version and date, repository URL and branch, licenses, icons, tags, trademark note in `README.md` and `package.xml`, CHANGELOG heading, `InitGui.py` class (AST) | [core](specs/core.md) 3.4, 3.5 |
| `Test02Hygiene` | 129 | Three-line headers, no "solidworks" in file names and identifiers, constant values, `Init.py` imports nothing from the GUI, pure modules, every `module.name` and `from jellyjams.module import name` between JellyJams modules (in `jellyjams/` and `InitGui.py`, also inside functions) naming something the module defines at its top level, plus a generated `test_import_<module>` and `test_api_<module>` per module | [core](specs/core.md) 2 |
| `Test03InitGui` | 4 | `InitGui.py` executed the way FreeCAD does it (no `__file__`, separate globals and locals): registration, duplicate copy, failing `addWorkbench`, delegation to `lifecycle` | [core](specs/core.md) 3.3 |
| `Test04Recovery` | 10 | Startup crash recovery, documented backup formats, corrupt backups, one failing step; each of the three `SwitchToWB` records, only some records pending, one damaged record among good ones | [core](specs/core.md) 7, [assembly](specs/assembly.md) 5.2 |
| `Test05Commands` | 9 | Registration once per process, providers, resources, icons, `CmdType` only where a command declares it (the two orientation commands, `Alter3DView`) with every other command's resources unchanged, `IsActive` never raises | [core](specs/core.md) 8 |
| `Test06Lifecycle` | 10 | Step tables, fault isolation, Initialize (the JellyJams menu holds View Orientation, Normal To, then Diagnostics), a full activation cycle of the real modules under the stubs (including the three `SwitchToWB` with their backups, `FreeCADGui.activateWorkbench` wrapped while active and identical to FreeCAD's afterwards, `Space` / `Ctrl+8` set on the JellyJams commands with Hide/Show unbound and all restored, the Space filter installed once and removed, and the Orientation panel closed on leave) | [core](specs/core.md) 4 |
| `Test07QuitGuard` | 6 | Close-event filter with a real modal `QDialog`: Cancel, Discard, inactive workbench, double close, failing revert | [core](specs/core.md) 6.6 |
| `Test08QtFilter` | 8 | Dropping, forwarding, chaining, opt-out parameter, a real `qInstallMessageHandler` install | [core](specs/core.md) 10 |
| `Test09Diagnostics` | 4 | Rows, version parsing, text block, command | [core](specs/core.md) 9 |
| `Test10Look` | 15 | Palette, W3C contrast, theme block on an offscreen main window, the 14 View keys and their backup | [look](specs/look.md) |
| `Test11Layout` | 12 | Toolbars and docks on an offscreen main window, restore, autoload deferral | [window-layout](specs/window-layout.md) |
| `Test12NavigationShortcuts` | 19 | The pinned shortcut table (13 keys, `Ctrl+8` on `JellyJams_NormalTo`), navigation style and shortcuts round trips, leftover and unreadable backups, clashing and missing commands (Box Zoom on `Ctrl+B`, Hide/Show on `Space`, also written `space`, a user's `Ctrl+8` on `Std_AlignToSelection`), a user who moved Hide/Show, Space and `Ctrl+8` left alone without the JellyJams commands, crash recovery of Space and `Ctrl+8`, partial restore, backups removed after restore, the shortcut list of `check_saved_cfg.py` run on generated `user.cfg` files | [core](specs/core.md) A5, 4.8, [orientation](specs/orientation.md) 2.4 |
| `Test13RibbonModel` | 12 | Ribbon content resolved against command lists: counts, stacks, labels, fallbacks (one by one and all at once), missing commands, layout validation | [ribbon-content](specs/ribbon-content.md) |
| `Test13RibbonText` | 5 | One-line names and tooltip text | [ribbon-engine](specs/ribbon-engine.md) 2.5, 2.8 |
| `Test13RibbonBuild` | 17 | The real ribbon built offscreen with stub commands: dock, buttons, flyouts (titled ones included), context tabs, dispatch, guard, rebuild, the Evaluate tab's Normal To running `JellyJams_NormalTo` (no `Std_AlignToSelection` button) | [ribbon-engine](specs/ribbon-engine.md), [ribbon-content](specs/ribbon-content.md) |
| `Test14NamingRules` | 10 | Pure naming and numbering rules, worked examples | [naming](specs/naming.md) |
| `Test15RelationsRules` | 8 | Every row of the worked reference table, also in every selection order; catalogue order and capability-table coverage of the 14 relations; offers agree with `accepts`; entity labels, existing relations, deletion order | [relations](specs/relations.md) 4.3, AC 3, 27 |
| `Test16MateRules` | 3 | Entity kinds, mate capability matrix, hints | [assembly](specs/assembly.md) 2.1 |
| `Test17SwitchPrefs` | 13 | `switch_prefs`: the `TARGETS` table; round trips of every absent / true / false combination of the three modules; pending, blank and damaged records; restore and recovery with only some records; quit revert and re-apply; one failing preference group | [assembly](specs/assembly.md) 5 |
| `Test17Assembly` | 1 | Assembly pure helpers (next assembly name, drag rotation, `.FCStd` filter, portal paths) | [assembly](specs/assembly.md) 2 |
| `Test18DialogTerms` | 9 | Relabeling on synthetic forms with FreeCAD's objectNames, projection tool tips, combo safety rule, scale fix, presets row, idle cost | [dialog-terms](specs/dialog-terms.md) |
| `Test19DrawingHelpers` | 13 | Drawing and sketching helper functions, templates and third-angle derivation on FreeCAD's installed template | [drawing-sheet](specs/drawing-sheet.md), [drawing-views](specs/drawing-views.md), [drawing-symbols-export](specs/drawing-symbols-export.md), [sketching](specs/sketching.md) |
| `Test20PdfMerge` | 3 | Merging PDFs written by `QPdfWriter`, rejecting unsupported PDFs | [drawing-symbols-export](specs/drawing-symbols-export.md) 2.9 |
| `Test21Icons` | 2 (one subtest per icon) | Every icon exists, renders, carries both SPDX lines in the comment after the XML declaration, uses no forbidden SVG elements, has the 64 × 64 viewBox; the icon folder holds exactly the command, relation and Orientation fallback icons plus the workbench icon | [core](specs/core.md) 2 |
| `Test22DocumentHelpers` | 8 | `doc_utils.transaction` against a fake transaction API, `primary_model_objects`, the sheet-sketch undo observer | [core](specs/core.md), [drawing-sheet](specs/drawing-sheet.md) 4.1, 7.4 |
| `Test22TreeNaming` | 3 | The naming observer with fake documents: New Part links named when their target arrives, pending links and undo, joint type changes | [naming](specs/naming.md) 3.4 |
| `Test22AssemblySelection` | 2 | Add Mate panel and Rotate Component ignore other documents and dead selection entries | [assembly](specs/assembly.md) 2.1, 2.5 |
| `Test22MakeDrawing` | 2 | Nothing to draw in a sketch-only document; a file of an open document is refused | [drawing-sheet](specs/drawing-sheet.md) 4 |
| `Test22ViewLabels` | 3 | Section/detail labeling in one closed `View Label` undo step, also on failure; waiting for a view drag | [drawing-views](specs/drawing-views.md) 4 |
| `Test22SheetFormat` | 3 | Sheet Properties position snapshot and rescale, format switch as one undo step | [drawing-sheet](specs/drawing-sheet.md) 5.5 |
| `Test22ViewDrag` | 2 | A view drag is one closed `Move View` undo step; no step without movement | [drawing-views](specs/drawing-views.md) 6 |
| `Test22InsertPicture` | 1 | Unusable files are rejected before an undo step opens | [drawing-sheet](specs/drawing-sheet.md) 9.1 |
| `Test23SketchFirstRules` | 4 | `SKETCH_FIRST_FEATURES`; truth tables of `needs_new_sketch` and `advance` (every transition: picking waits, grace, drop on cancel, move to editing, retargeted command kept, drop on another sketch, start on exit) | [sketching](specs/sketching.md) 2.6 |
| `Test23SketchFirstFlow` | 41 | `try_run` and the watcher with a fake Part Design document: new sketch instead of the feature, free-sketch rules, selection kinds, container-only selections cleared, subtractive features only with a solid in the target body (FreeCAD's `isSolid` rule: a Part Design feature in the body's `Group`, also with a null shape; planes, sketches and a solid shape alone do not count), without one Pocket and Groove left to FreeCAD and Hole refused by JellyJams (status text for 6 s, warning, nothing run; on a fresh press and while picking, the waiting sketch-first and its picker kept), `_nothing_to_cut` true only for a known target body, Pocket, Groove and Hole with several bodies and none active left to FreeCAD (False, no text, nothing run, with or without solids) and retargeted while picking, target body (active, lone inactive, none), insert point after the Tip, dialogs and missing documents, failing `PartDesign_NewSketch`, start on exit, retarget while picking (sketch-first features only, cutting features only with a solid, hint rewritten), stale plane picks dropped and the press handled fresh, the replaced sketch-first's checks stopping (checks run by hand, one per turn), status hint cleared on every drop and on a failing check, drop on cancel after the grace, on another sketch, on an empty sketch, on leaving JellyJams or closing the document, a press inside the new sketch | [sketching](specs/sketching.md) 2.6 |
| `Test23EditGuard` | 18 | `edit_guard` with command strings simulated by code compiled as `<string>`: install and identity restore, Python callers pass through, deferral, staying when an edit starts, switching otherwise, requests never held, workbench changed meanwhile, disarmed wrapper, failing switch, missing `activateWorkbench`; chain tracking under another add-on's wrapper (re-install only re-arms, the switch happens once one turn later with no recursion, the other wrapper is left in place, a wrapper back on top is unwrapped); the command string found through one and two other wrappers, Python callers through wrappers passing straight through, and the `FRAME_SEARCH_DEPTH` limit (found at the last frame searched, not one frame beyond) | [sketching](specs/sketching.md) 2.7 |
| `Test24Orientation` | 70 | The Orientation panel and Normal To offscreen: both commands' resources and `CmdType`, active while the stub main window's `getActiveWindow()` is a 3D view (`getCameraNode`; not for None, a sheet or a Start-page-like object even while `activeView()` returns a 3D view, not when it raises, not from the MDI area's window class; also with a sketch and task dialog open and another window active), `activeView()` used only when the main window has no `getActiveWindow`, `_active_view()` None on errors, toggling, Normal To's target with fake selections and shapes (any single sub-element, flat or curved faces, straight, circular or B-spline edges and vertices included, never read; two picks, also the same sketch picked through two links; whole sketches and 2D objects as `("sketch", obj)`; origin planes and axes, datum planes, lines and points; single-face and single-edge objects; solids, shells, wires, null and unreadable shapes, bodies and features; every sketch-edit case), the sketch look through a fake 3D view (the main window's active window, not `activeView()`; `setCameraOrientation` with the rotation from a stub `GeoFeature.getGlobalPlacementOf` along the unresolved selection's one item and path, a link included; the sketch's own global placement with several items or paths or when that call raises, with a log line; a warning and False when turning fails), the hint in the status bar, as a tool tip at the pointer (a failing tool tip changes nothing else) and its timeout, the Normal To button closing the panel unless pinned before Normal To runs (FreeCAD's `runCommand` simulated), a frameless tool window `JellyJamsOrientation`, the pinned tables, 13 buttons in their grid places, tooltips with keys, missing and inactive commands disabled, buttons refreshed on open, the panel built again after its widget was deleted, click runs and closes, pin, Esc / Space / close button, held keys ignored, key repeat switched off on the stub's `QAction`, click outside under a fake clock (unpinned closes, pinned stays, within `OPEN_SETTLE_S` the panel re-activated instead (not when pinned) or closed when no FreeCAD window is active, a late check of an earlier opening never closes a newer one, a panel that never had the keyboard stays, an active or closed panel is left alone), the keyboard given back only when the panel had it, to the window that had it at opening (an undocked view) when alive and visible, else to the main window, never to the panel itself, and for a pinned panel to the FreeCAD window clicked into last, `keeps_space` for every widget kind, the pointer rule (3D view, 3D viewer, split view `Gui::AbstractSplitView`, model tree and widgets inside them), toolbars, the status bar and the ribbon dock, item views (checkable current item, `AnyKeyPressed`, plain lists, the model tree), the Space filter accepting only a plain Space for controls and asking Qt which widget is under the real (moved) pointer, the filter on the main window and every dock (a floating dock's check box gets Space only through its own filter), docks made after activation added once when a widget in them takes the focus (not other widgets, not after `uninstall()`, the focus watch disconnected), removed from all and a deleted dock skipped, real key clicks (`QTest`) on a check box with a Space `QAction`, Space on a focused panel button, also with the pointer over a 3D view beside the panel, one filter however often installed and none after `uninstall()`, the stylesheet's colors for every button state and the text color resolved under a white-on-dark application stylesheet, `close()` before any open, the real activation and deactivation steps, fallback icons and FreeCAD's icon winning, placement on screen | [orientation](specs/orientation.md) |
| **Total** | **489** | | |

## GUI acceptance scripts

### How they work

- FreeCAD runs the script given as a file argument after the GUI has started:
  `FreeCAD.exe -u <user.cfg> -s <system.cfg> <script.py>`.
- Each script schedules a chain of `QTimer` steps (first step after 4 s, 6 s in autoload mode),
  records checks with `note(name, ok, detail)`, prints `JellyJams-smoke` / `JellyJams-lifecycle` / `JellyJams-sketch-first` / `JellyJams-orientation` / `JellyJams-tabs` lines to
  the Report view, writes its JSON to `JELLYJAMS_RESULTS_DIR`, and quits FreeCAD itself.
- Every step is wrapped by `guarded()`: an exception is stored in `errors`, the results are saved,
  and FreeCAD quits.
- After a workbench switch, `gui_smoke.py` and `gui_lifecycle.py` wait `SWITCH_SETTLE_MS` (4 s)
  before they look at the window again. [window-layout](specs/window-layout.md) 7 reads the state
  no sooner than 3.5 s after a switch, by which time every delayed re-dock pass (section 3) has
  run. The Cancel check in `gui_lifecycle.py` keeps its 2.5 s, the limit set by window-layout
  AC 15.
- `FreeCAD.exe` is a Windows GUI program, so PowerShell's `&` returns at once without waiting. Use
  `Start-Process -Wait` (the helper below) whenever the next command depends on the run, for example
  discard, then `check_saved_cfg.py`, then after.
- The scripted steps take about 8 s (`after`) to 26 s (`gui_smoke`), and about 70 s for
  `gui_orientation` (`info.seconds`), plus FreeCAD's startup. A whole `gui_sketch_first` run,
  start to quit, takes about 31 s.

### Common setup (PowerShell)

Paste once per PowerShell session:

```powershell
$Repo = "C:\path\to\JellyJams"                          # this repository
$FC   = "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe"
$Py   = "C:\Program Files\FreeCAD 1.1\bin\python.exe"
$Out  = "$Repo\scratch"                                  # git-ignored
$env:JELLYJAMS_RESULTS_DIR = $Out
New-Item -ItemType Directory -Force $Out | Out-Null

# Throwaway copies of your FreeCAD configuration, one pair per run.
function New-TestProfile([string]$Name) {
    Copy-Item "$env:APPDATA\FreeCAD\v1-1\user.cfg"   "$Out\$($Name)_user.cfg"   -Force
    Copy-Item "$env:APPDATA\FreeCAD\v1-1\system.cfg" "$Out\$($Name)_system.cfg" -Force
}

# Run one GUI script with a throwaway profile and wait until FreeCAD has quit.
function Invoke-FreeCAD([string]$Name, [string]$Script) {
    $argList = '-u "{0}\{1}_user.cfg" -s "{0}\{1}_system.cfg" "{2}"' -f $Out, $Name, "$Repo\tests\$Script"
    Start-Process -FilePath $FC -ArgumentList $argList -Wait
}
```

Delete old results before a full run, because a run that aborts early can leave the previous
file in place: `Remove-Item "$Out\*.json" -ErrorAction SilentlyContinue`.

The recorded results used these profile names: `test` (gui_smoke), `tabs` (gui_tabs), `cancel`,
`discard` (also used by `after`), `autoload`, `sketchfirst` (gui_sketch_first) and `orientation`
(gui_orientation).

### gui_smoke.py

```powershell
New-TestProfile test
Invoke-FreeCAD test gui_smoke.py
```

Sequence: switch to Part Design and record the state, activate JellyJams, check it, create a
Body with a Sketch and a Pad, create and activate an assembly, switch back to Part Design, check
the restore, take two screenshots, quit.

| Check | Asserts | Spec |
|---|---|---|
| `workbench_registered` | `JellyJamsWorkbench` is in `listWorkbenches()` | [core](specs/core.md) AC 2 |
| `ribbon_dock_exists`, `ribbon_tabs`, `ribbon_visible`, `ribbon_has_buttons` | Dock `JellyJamsCommandManager` exists, tabs are exactly Features, Sketch, Evaluate, Assembly, Drawing, the dock is visible, more than 20 tool buttons | [ribbon-engine](specs/ribbon-engine.md) AC 1 to 3 |
| `ribbon_matches_model` | Each tab page holds as many plain buttons, flyouts, toggles and separators as `ribbon_model` resolves for this FreeCAD's command list (counts are not hard-coded; the JSON's `ribbon` entry records the per-tab counts, skipped ids and substitutions) | [ribbon-content](specs/ribbon-content.md) AC 4, 5 |
| `jj_plain_buttons` | `JellyJams_Diagnostics`, the five `JellyJams_*OnSheet`, `JellyJams_RotateComponent`, `JellyJams_MakeDrawing` and `JellyJams_MakeDrawing#1` have plain ribbon buttons | [ribbon-content](specs/ribbon-content.md) AC 16, 17 |
| `theme_marker` | `/* @jellyjams-stylesheet-open */` occurs exactly once in the main-window stylesheet | [look](specs/look.md) AC 1 |
| `nav_is_solidworks` | `NavigationStyle` = `Gui::SolidWorksNavigationStyle` | [core](specs/core.md) AC 16 |
| `switch_to_wb_off` | `SwitchToWB` is false in `Mod/Assembly`, `Mod/PartDesign` and `Mod/TechDraw/General` | [assembly](specs/assembly.md) AC 1 |
| `backups_present` | All six backup keys in `Mod/JellyJams` are non-empty | [core](specs/core.md) AC 16 |
| `jellyjams_menu`, `no_jj_toolbars` | "JellyJams" menu present; no visible toolbar whose objectName starts with `JellyJams` | [core](specs/core.md) AC 10 |
| `shortcut_fit` | `Preferences/Shortcut` `Std_ViewFitAll` = `F` | [core](specs/core.md) AC 16 |
| `rebuild_owns_ctrl_b`, `no_shortcut_conflicts` | `Std_Refresh` is live on `Ctrl+B`; no other command shares a JellyJams key | [core](specs/core.md) A5 |
| `pad_sw_name`, `sketch_sw_name`, `origin_planes_sw` | `Boss-Extrude...`, `Sketch...`, `Top Plane` / `Front Plane` / `Right Plane` | [naming](specs/naming.md) AC 1, 3 |
| `assembly_tab_on_activate`, `stayed_in_jellyjams` | Activating an assembly selects the Assembly tab and keeps JellyJams active | [ribbon-engine](specs/ribbon-engine.md) AC 20, [assembly](specs/assembly.md) AC 7 |
| `theme_removed`, `nav_restored`, `switch_to_wb_restored`, `backups_cleared`, `nav_shortcut_backups_removed`, `jellyjams_menu_gone`, `shortcut_restored`, `boxzoom_key_restored`, `ribbon_hidden`, `stock_toolbars_back` | After leaving: stylesheet identical to before, every setting back, backups empty, the `OriginalNavigationStyle` and `OriginalShortcuts` keys removed, menu gone, `Std_ViewBoxZoom` key back, ribbon hidden, every toolbar visible before is visible again | [core](specs/core.md) AC 17, [window-layout](specs/window-layout.md) AC 6, 9 |

**Pass:** `"ok": true`, 31 checks, `"errors": []`. The `"ok"` key is written only when the script
reaches its last step; a missing `"ok"` means the run aborted (read `errors`).
`shortcut_restored` expects `Std_ViewFitAll` to have no override after leaving, so the profile
must not carry a user override for it.

### gui_lifecycle.py (`JELLYJAMS_LIFECYCLE_MODE`)

| `JELLYJAMS_LIFECYCLE_MODE` | Profile | What happens | Checks |
|---|---|---|---|
| `cancel` (default when unset) | new copy `cancel` | Part Design, then JellyJams; creates an unsaved document (`Dirty`, one `Part::Box`) and closes the main window. 1.5 s into FreeCAD's "Save changes?" prompt it checks that everything is reverted and nothing was re-applied, then presses Cancel. 2.5 s later it checks the re-apply, closes the document and switches to Part Design; 4 s after that switch it checks the restore and quits. | 16 |
| `discard` | new copy `discard` | Same up to the prompt checks, then presses Discard. FreeCAD exits and writes `discard_user.cfg`. Inspect that file with `check_saved_cfg.py` before `after`. | 9 |
| `after` | the **same** `discard` profile (no new copy) | Relaunch after the Discard quit. Reads `lifecycle_discard.json` from `JELLYJAMS_RESULTS_DIR`, switches to Part Design and checks that the stock toolbars recorded before the quit are visible, the ribbon is hidden, the backups are empty and the three `SwitchToWB` are as before (only Assembly's when the discard run recorded a single value). | 5 (4 if `switch_before` was not recorded) |
| `autoload` | new copy `autoload` with `AutoloadModule` = `JellyJamsWorkbench` | FreeCAD starts in JellyJams. 6 s after start it checks the active workbench, the applied layout snapshot, the visible ribbon and that only File, Edit and Workbench toolbars are visible; then switches to Part Design and, 4 s later, checks that more than three toolbars are back and the theme is gone. | 6 |

Check names per mode:

- cancel: `active_before_close`, `switch_to_wb_off_before_close`, `prompt_is_open`,
  `not_reentered_inside_prompt`, `nav_restored_inside_prompt`, `shortcut_restored_inside_prompt`,
  `switch_to_wb_restored_inside_prompt`, `backups_cleared_inside_prompt`, `found_cancel`,
  `reapplied_after_cancel`, `nav_reapplied_after_cancel`, `shortcut_reapplied_after_cancel`,
  `switch_to_wb_reapplied_after_cancel`, `stock_restored_after_leave`,
  `switch_to_wb_restored_after_leave`, `backups_cleared_after_leave`.
- discard: the first eight cancel checks, then `found_discard`.
- after: `expected_known`, `stock_toolbars_visible_after_relaunch`, `ribbon_not_visible`,
  `backups_cleared_after_relaunch`, `switch_to_wb_kept_after_relaunch`.
- autoload: `autoloaded_into_jellyjams`, `layout_active_after_show`, `ribbon_visible_after_show`,
  `stock_toolbars_hidden_after_show`, `toolbars_back_after_leave`, `theme_removed_after_leave`.

Run all four in this order:

```powershell
# cancel
New-TestProfile cancel
$env:JELLYJAMS_LIFECYCLE_MODE = "cancel"
Invoke-FreeCAD cancel gui_lifecycle.py

# discard, then inspect the saved user.cfg, then relaunch with the same profile
New-TestProfile discard
$env:JELLYJAMS_LIFECYCLE_MODE = "discard"
Invoke-FreeCAD discard gui_lifecycle.py
$info = (Get-Content "$Out\lifecycle_discard.json" -Raw | ConvertFrom-Json).info
$nav  = if ($info.nav_before) { $info.nav_before } else { '""' }   # see "Empty arguments" below
$sw   = $info.switch_before                                          # Assembly, PartDesign, TechDraw
& $Py "$Repo\tests\check_saved_cfg.py" "$Out\discard_user.cfg" $nav "$($sw.Assembly)" "$($sw.PartDesign)" "$($sw.TechDraw)" |
    Out-File -Encoding utf8 "$Out\saved_cfg_check.json"
"check_saved_cfg exit code: $LASTEXITCODE"                          # 0 = clean
$env:JELLYJAMS_LIFECYCLE_MODE = "after"
Invoke-FreeCAD discard gui_lifecycle.py

# autoload: set FreeCAD's start-up workbench in the throwaway user.cfg, then run
New-TestProfile autoload
$cfg = "$Out\autoload_user.cfg"
[xml]$x = Get-Content -Raw -Encoding UTF8 $cfg
$g = $x.SelectSingleNode("/FCParameters/FCParamGroup[@Name='Root']/FCParamGroup[@Name='BaseApp']/FCParamGroup[@Name='Preferences']/FCParamGroup[@Name='General']")
$n = $g.SelectSingleNode("FCText[@Name='AutoloadModule']")
if ($null -eq $n) { $n = $x.CreateElement("FCText"); $n.SetAttribute("Name", "AutoloadModule"); [void]$g.AppendChild($n) }
$n.InnerText = "JellyJamsWorkbench"
$x.Save($cfg)
$env:JELLYJAMS_LIFECYCLE_MODE = "autoload"
Invoke-FreeCAD autoload gui_lifecycle.py

Remove-Item Env:JELLYJAMS_LIFECYCLE_MODE
```

The XML edit assumes the copied `user.cfg` already has a `BaseApp/Preferences/General` group; if
`$g` is `$null`, use the alternative: start FreeCAD once with
`-u "$Out\autoload_user.cfg" -s "$Out\autoload_system.cfg"`, choose JellyJams as the start-up
workbench under Edit > Preferences > General, and quit; FreeCAD saves it into the copy.

**Pass:** each `lifecycle_<mode>.json` has `"ok": true`, which the script sets only when there is
at least one check, every check passed and `errors` is empty.

### gui_sketch_first.py

```powershell
New-TestProfile sketchfirst
Invoke-FreeCAD sketchfirst gui_sketch_first.py
```

Presses the ribbon's Extruded Boss/Base exactly as a click does (`ribbon.run_entry("PartDesign_Pad")`)
in four new documents, each with one active Body (`setActiveObject("pdbody", body)`):

| Part | Sequence | Checks |
|---|---|---|
| A, plane selected | Select the body's XY plane, press. Draw a 30 × 20 rectangle in the sketch that opened, run `Sketcher_LeaveSketch`, wait 2.5 s, then press OK in the Pad dialog | `a_no_warning_dialog`, `a_sketch_opened`, `a_sketch_on_selected_plane`, `a_pad_created_after_exit`, `a_pad_uses_new_sketch`, `a_no_pending_state`, `a_still_in_jellyjams_after_exit`, `a_still_in_jellyjams_after_ok` |
| B, nothing selected, no sketch | Press with an empty selection; 1.5 s later the plane picker must be open; cancel it and wait 2.5 s | `b_no_warning_dialog`, `b_plane_picker_open`, `b_waiting_for_plane`, `b_cancel_drops_state`, `b_no_pad_after_cancel` |
| C, a free sketch exists | A closed rectangle sketch on the XY plane, nothing selected, press, then OK | `c_no_warning_dialog`, `c_pad_uses_existing_sketch`, `c_no_new_sketch`, `c_no_pending_state` |
| D, feature edit and a user's switch | `setEdit` on the Pad of C (stays in JellyJams), OK, then `Std_Workbench` with the index of `PartDesignWorkbench` (what the workbench selector and View > Workbench run) | `d_edit_feature_stays_in_jellyjams`, `d_feature_dialog_open`, `d_user_switch_to_part_design_works` |

`info` records the workbench at several moments (`workbench`), the `SwitchToWB` values while
the sketch is open (`a_prefs`), a trace of the sketch-first state machine in part B (`b_trace`)
and how long each step waited for a task dialog to close (`dialog_waits_ms`).

**Pass:** `sketch_first.json` has `"ok": true` (20 checks, every check passed, `errors` empty).
The script ends in Part Design, so FreeCAD's quit happens outside JellyJams. After writing
`sketch_first.json` it closes every open document (its four documents are unsaved, and FreeCAD's
"Save changes?" prompt would otherwise stop the quit) and quits 300 ms later, so the run ends by
itself, about 31 s after FreeCAD starts.

### gui_orientation.py

```powershell
New-TestProfile orientation
Invoke-FreeCAD orientation gui_orientation.py
```

Sequence: record `Std_ToggleVisibility`'s key and `Std_AlignToSelection`'s override, turn off
the camera animations (`View/UseNavigationAnimations`, put back at the end), activate JellyJams,
then run these parts in order:

| Part | What happens |
|---|---|
| keys | A document `Orient` with one `Part::Box`, fitted. The keys, the JellyJams menu and the View Orientation `QAction` are read before the panel is ever opened, so `orientation_no_auto_repeat` sees what activation did. `info.space_filter_on` lists what the Space filter watches (FreeCAD 1.1.4: the main window and its five docks, `Tasks` among them). |
| panel | A real `Space` in the 3D view, the 13 buttons, Top, pinned Front, Esc on the panel. Then, Pin off and the camera skewed, a real `Space` in the 3D view opens the panel again, its Top button gets the focus with `setFocus(Qt.TabFocusReason)` (as Tab gives it), the pointer stays on the 3D view's GL widget beside the panel, and a real `Space` goes to the button. |
| outside | Pin off, open the panel, wait 600 ms (longer than `orientation.OPEN_SETTLE_S`, 0.3 s), `activateWindow()` on FreeCAD's main window (what a click into it does), wait 400 ms; then the same with Pin on. Then Pin off, open the panel and, as soon as it is the active window (polled every 10 ms), activate the main window: a deactivation inside the settle time (0.047 s after opening in the recorded run). 500 ms later the panel is read, and the main window is activated once more, now after the settle time (0.547 s after opening in the recorded run); the panel is read 400 ms after that. |
| normal | From a skewed camera (`App.Rotation((1, 2, 3), 37)`), `Gui.runCommand("JellyJams_NormalTo")` with nothing selected; the status bar is read right after the call, the tool tip (`QToolTip.isVisible()`, `QToolTip.text()`) 600 ms later. Then, still nothing selected and the camera skewed, the pointer goes to the 3D view's GL widget, the unpinned panel is opened beside it and, 600 ms later, its Normal To button is clicked (`QToolButton.click()`); status bar and tool tip are read right after the click and 300 ms later. Then `Box.Face2` (+X) is selected and Normal To runs again. `Orient` is closed afterwards, so the undock part finds no other 3D view in the MDI area. |
| pick | A document `OrientPick`: Body, a 30 × 20 rectangle sketch on its XY plane, `Pad` 10 mm. Each case starts from the skewed camera and runs `Gui.runCommand("JellyJams_NormalTo")`: the whole sketch selected the way a click in the model tree selects it (`addSelection(doc, "Body", "Sketch.")`, the sketch not in edit); the body's `XZ_Plane` selected the same way (`"Origin.XZ_Plane."`, labelled `Front Plane` by JellyJams); two faces of the Pad (`Face1`, `Face2`). Then the ribbon dock `JellyJamsCommandManager` is searched for the button `JellyJamsButton-JellyJams_NormalTo`, the tab holding it is shown, the first Pad face that faces along X is selected and the button is clicked (`QToolButton.click()`, which runs `ribbon.run_entry` as a mouse click does). Then a `Part::Cylinder` `Cylinder` (at x = 60) and a `PartDesign::Line` `DatumLine` in the body (attachment off, placement turned 90° about X) are added. For the cylinder's curved `Face1` (`info.pick_cylinder_face1`: `Part::GeomCylinder`), the whole datum line (`"DatumLine."` below the body) and the body's whole X axis (`"Origin.X_Axis."`), Normal To runs from the skewed camera, and then FreeCAD's own `Std_AlignToSelection` runs with the same selection from the same skewed camera. Last, the body is turned 30° about Z, an `App::Link` `Link` to the body is added with a placement of its own (y = 80, turned 90° about X; a link's placement replaces the linked body's), and the sketch is selected through the link, as a click on it below the link in the tree selects it (`addSelection(doc, "Link", "Sketch.")`), before Normal To runs. |
| combo | The workbench selector (Qt class `Gui::WorkbenchComboBox`, in the `Workbench` toolbar) gets the focus, the pointer goes to the main window's status bar (neither a 3D view nor the model tree, so only the toolbar rule decides) and a real `Space` goes to the combo box. Esc closes the panel. |
| undock | `Gui.runCommand("Std_ViewDockUndockFullscreen", 1)` undocks OrientPick's view (FreeCAD puts a clone of the view into a window of its own); the MDI area's current window is then the Start page (`StartGui::StartView`). The undocked window is activated, `Gui.Command.update()`, then a real `Space` in it, then Esc on the panel; then another real `Space` in the undocked view and a click on the unpinned panel's Top button. It is docked again with index 0 after activating the undocked window (the command acts on the main window's active view and does nothing otherwise); should it still be undocked, an Esc in the view is tried (`info.redock`). |
| start | The Start page's MDI sub-window (`StartGui::StartView`, open since FreeCAD started; the script would run `Start_Start` otherwise, `info.start_page`) is made the MDI area's active window with the main window active, then `Gui.Command.update()`. The Start view itself gets the focus (the script never sends Space to a focused Start page button or combo box), the pointer goes to it and a real `Space` goes to the focused widget. The 3D view's sub-window is made active again afterwards. |
| dark | The application stylesheet is replaced by `* { color: #ffffff; }`, the panel is opened and checked, the panel is saved as `orientation_dark_panel.png`, and the saved stylesheet is set back exactly. |
| sketch | A document `OrientSketch`: a Body with a Sketch on its XY plane, `setEdit` on the sketch (a default task dialog, so `Gui.Control.isAllowedAlterDocument()` is False; `info.sketch_alter_document_allowed`). `Gui.Command.update()`, then real `Space` key presses in the 3D view, Esc and Space on the panel, then Normal To through `Gui.runCommand` and through a real `Ctrl+8`, each from the skewed camera with nothing selected. |
| pad | A document `OrientPad`: Body, rectangle sketch, `Pad` 10 mm, `setEdit` on the Pad. The dialog's `checkBoxReversed` (shown as "Reversed") gets the focus with the pointer over the task panel (`Gui::TaskView::TaskView`) and a real `Space`; then the focus again with the pointer over the 3D view's GL widget and a real `Space` (Esc closes the panel it opens); then `Space` in the 3D view. Then the dock holding the dialog (found by walking up from the check box: `Tasks`) is made floating (`setFloating(True)`) and activated, the check box gets the focus with the pointer over the dock and a real `Space`; the dock is docked again (`info.task_dock`). The dialog is cancelled. |
| hole | A document `OrientHole` with one empty Body, active, nothing selected. `jellyjams.ribbon.run_entry("PartDesign_Hole")` (what a click on Hole Wizard does); the status bar is read right after the call, the document 1.5 s later. A modal dialog still open 2.5 s after the press is closed and recorded (`info.stray_modal`), so a regression cannot hang the run. Then a document `OrientHole2` with two padded bodies (`Body` and `Body001`, each with a rectangle sketch and a 10 mm Pad), none active (`info.hole2`), nothing selected, and the same press. Every message the status bar shows during the press is recorded (its `messageChanged` signal), and every modal dialog that appears within 4 s is recorded and rejected (FreeCAD 1.1.4 asks which body with `PartDesignGui::DlgActiveBody`, "Active Body Required"). |
| late | A `QDockWidget` `OrientationLateDock` holding a `QCheckBox` `OrientationLateCheckBox` is added to the main window after activation, made floating (`setFloating(True)`) and shown over the middle of the main window. 800 ms later its window is activated, the check box gets the focus, the pointer goes to the check box and a real `Space` goes to it; the dock is removed. |
| leave | Pin on, open the panel, switch to Part Design, wait 3.5 s. Then a dock `OrientationTestDock` with a plain `QCheckBox` is added to the main window, the selection is cleared (Hide/Show is then disabled), the check box gets the focus with the pointer over the dock and a real `Space`; the dock is removed. |

Every real key press is a `QTest.keyClick`: in the 3D view the script focuses the view's
`QOpenGLWidget` and sends the key to whatever then holds the focus (FreeCAD 1.1.4:
`Gui::View3DInventorViewer`, in the undocked view `Gui::View3DInventor`; `info.view_key_target`),
on a check box, combo box, panel button or the Start view to that widget itself. QTest sends a `ShortcutOverride` first, so the
key takes the same path as a real one: a widget or filter that accepts the override gets the key,
otherwise Qt's shortcut map gets it.

Who gets Space depends on the widget under the real mouse pointer
(`QApplication.widgetAt(QCursor.pos())`). Before every Space press the script therefore moves the
pointer with `QCursor.setPos(widget.mapToGlobal(widget.rect().center()))` onto the widget the case
is about (the 3D view's GL widget where the panel must open, and beside the panel for its
Tab-focused button; the task panel, a dock or the late dock's check box where a control keeps
Space; the status bar for the workbench selector; the Start view) and processes events; the check
details record what was under it (`under_pointer`, `pointer_over_3d_view`) and whether the
intended widget had the focus. The real pointer moves, so do not touch the mouse while the script
runs. The script keeps the Python wrapper of the view whose GL widget it uses: observed on
FreeCAD 1.1.4 with PySide 6.8.3, an undocked view is a top-level widget nothing else holds, and
once its wrapper was dropped the GL widget's wrapper was reported as "already deleted" right
after the lookup.

If a key press does not open the panel, the check fails and the script opens it another way so
the following checks still run. The scripted steps take about 70 s (`info.seconds`: 71.3 in the
recorded run), the whole run with FreeCAD's start and quit about 80 s.

| Check | Asserts | Spec |
|---|---|---|
| `space_bound_to_orientation`, `ctrl8_normal_to` | `JellyJams_ViewOrientation` has `Space`, `JellyJams_NormalTo` has `Ctrl+8` | [orientation](specs/orientation.md) AC 1 |
| `align_to_selection_untouched` | `Std_AlignToSelection` has no `Ctrl+8`, its `Preferences/Shortcut` entry is as before activation and it is not in the `OriginalShortcuts` backup | [orientation](specs/orientation.md) 2.4 |
| `toggle_visibility_unbound_while_active` | `Std_ToggleVisibility` has no key while JellyJams is active | [orientation](specs/orientation.md) AC 2 |
| `menu_has_normal_to` | The JellyJams menu holds `JellyJams_NormalTo` (detail: the menu's action names in order) | [orientation](specs/orientation.md) AC 19 |
| `normal_to_action_has_ctrl8` | Normal To's `QAction` carries `Ctrl+8`, so the key is live | [orientation](specs/orientation.md) 2.4 |
| `orientation_no_auto_repeat` | View Orientation's `QAction.autoRepeat()` is False right after activation | [orientation](specs/orientation.md) |
| `space_opens_panel` | The Space key press made `JellyJamsOrientation` visible | [orientation](specs/orientation.md) AC 3 |
| `panel_has_13_view_buttons`, `panel_has_normal_to_button` | 13 buttons named `JellyJamsOrientation_<command id>`; `JellyJamsOrientation_JellyJams_NormalTo` is among them and enabled | [orientation](specs/orientation.md) AC 4 |
| `top_view_applied`, `unpinned_panel_closes_after_choice` | Clicking Top gives the view direction (0, 0, −1) and closes the panel | [orientation](specs/orientation.md) AC 6 |
| `front_view_applied`, `pinned_panel_stays_open` | With Pin checked, Front is applied and the panel stays open | [orientation](specs/orientation.md) AC 7 |
| `escape_closes_panel` | Esc on the panel closes it | [orientation](specs/orientation.md) AC 8 |
| `panel_tab_focus_space_applies_view`, `panel_tab_focus_space_closes_unpinned_panel` | With the panel's Top button focused (`focus_is_top_button`) and the pointer over the 3D view beside the panel (`pointer_over_3d_view`), Space clicks the button: the view direction becomes (0, 0, −1) from the skewed start, and the unpinned panel is closed | [orientation](specs/orientation.md) 2.3 |
| `click_outside_closes_unpinned_panel`, `click_outside_keeps_pinned_panel` | The main window was activated more than `OPEN_SETTLE_S` (0.3 s) after opening (`activated_after_s`), and then the unpinned panel is closed; a pinned one is still open | [orientation](specs/orientation.md) 2.3, AC 28 |
| `deactivation_right_after_opening_keeps_panel` | The panel had become the active window (`panel_was_active`), the main window took the activation less than 0.3 s after opening (`deactivated_after_s`), and 500 ms later the panel is still open | [orientation](specs/orientation.md) 2.3 |
| `deactivation_right_after_opening_takes_keyboard_back` | In the same case, 500 ms after that deactivation the panel is the active window again (`panel_active_again`, `active_window_after`: `JellyJamsOrientation`) | [orientation](specs/orientation.md) 2.3 |
| `later_click_elsewhere_closes_panel` | Activating the main window once more, now more than 0.3 s after opening (`activated_after_s`), closes the panel | [orientation](specs/orientation.md) 2.3 |
| `normal_to_nothing_selected_keeps_view`, `normal_to_nothing_selected_hint` | Outside a sketch with nothing selected the view direction does not change and the status bar says `Normal To: select one face, edge, plane or sketch first.` (`orientation.NORMAL_TO_HINT`) | [orientation](specs/orientation.md) 2.6, AC 24 |
| `normal_to_nothing_selected_tooltip` | 600 ms after that call a tool tip with the same text is shown (`QToolTip.text()`) | [orientation](specs/orientation.md) 2.6 |
| `panel_normal_to_nothing_closes_panel` | The panel's Normal To button with nothing selected: the unpinned panel, open and active before the click, is closed afterwards and the view direction is unchanged | [orientation](specs/orientation.md) 2.3 |
| `panel_normal_to_nothing_hint` | The status bar shows the hint right after that click and still 300 ms later | [orientation](specs/orientation.md) 2.3, 2.6 |
| `panel_normal_to_nothing_tooltip` | 300 ms after that click, with the panel closed, the tool tip shows the hint (`tooltip_after_300_ms`; `tooltip_right_after`, the tool tip right after the click, is only recorded) | [orientation](specs/orientation.md) 2.3, 2.6, AC 49 |
| `normal_to_face_aligns` | With `Box.Face2` selected the view direction becomes parallel to the face normal (\|dot\| > 0.999) and differs from the skewed start | [orientation](specs/orientation.md) AC 22 |
| `normal_to_whole_sketch_aligns` | With the whole sketch selected (`getSelectionEx()`: `Sketch` with no sub-element) and no sketch in edit, the view direction becomes parallel to the sketch's normal (the +Z of its global placement) and differs from the skewed start | [orientation](specs/orientation.md) 2.6 |
| `normal_to_origin_plane_aligns` | The same with the body's `XZ_Plane` (label `Front Plane` in the detail): parallel to its normal, (0, ±1, 0) | [orientation](specs/orientation.md) 2.6 |
| `normal_to_two_faces_keeps_view`, `normal_to_two_faces_hint` | With two Pad faces selected the view direction does not change and the status bar shows the hint. FreeCAD's own `Std_AlignToSelection` also leaves the view alone with more than one element selected, so the hint is what tells JellyJams' one-pick rule apart | [orientation](specs/orientation.md) 2.6 |
| `evaluate_ribbon_normal_to_is_jellyjams` | The ribbon dock holds a button `JellyJamsButton-JellyJams_NormalTo` (caption `Normal To`) on the page of the `Evaluate` tab, and no `JellyJamsButton-Std_AlignToSelection` | [ribbon-content](specs/ribbon-content.md) |
| `evaluate_ribbon_normal_to_face_aligns` | With one Pad face that faces along X selected, clicking that ribbon button (enabled) makes the view direction parallel to the face normal and different from the skewed start | [orientation](specs/orientation.md) 2.6 |
| `normal_to_curved_face_turns_view`, `normal_to_datum_line_turns_view`, `normal_to_origin_axis_turns_view` | With the cylinder's curved face, the whole datum line or the whole X axis selected, Normal To (detail `target`: `('command', 'Std_AlignToSelection')`) turns the view away from the skewed start, to the direction FreeCAD's own `Std_AlignToSelection` gives from the same start (each component within 1e-4; recorded (−1, 0, 0), (0, 1, 0) and (−1, 0, 0)) | [orientation](specs/orientation.md) 2.6 |
| `normal_to_linked_sketch_follows_link` | With the sketch selected through the link (`getSelectionEx("", 0)`: `Link` with `Sketch.`), the view direction is parallel to the sketch normal along that path, from `App.GeoFeature.getGlobalPlacementOf(sketch, link, "Sketch.")` ((0, −1, 0)), differs from the skewed start, is not parallel to the sketch's own global normal ((0, 0, 1)), and the camera orientation is that rotation (`Rotation.isSame`, tolerance 1e-4; Q (0.7071, 0, 0, 0.7071)) | [orientation](specs/orientation.md) 2.6 |
| `workbench_combo_space_opens_panel`, `workbench_combo_space_no_popup` | With the workbench selector focused and the pointer on the status bar, Space opens the panel; the combo box's popup stays closed and the workbench is unchanged | [orientation](specs/orientation.md) 2.4 |
| `view_undocked` | After `Std_ViewDockUndockFullscreen` with index 1 a visible `Gui::View3DInventor` is a top-level window | — |
| `undocked_commands_enabled` | With the undocked view active (the MDI area's current window is the Start page) and after `Gui.Command.update()`, both commands' `QAction`s are enabled; the detail also has `orientation.view3d_active()` | [orientation](specs/orientation.md) 2.1, AC 10 |
| `undocked_space_opens_panel` | A real Space in the undocked view, pointer over its GL widget, opens the panel | [orientation](specs/orientation.md) AC 3 |
| `undocked_escape_gives_keyboard_back_to_view`, `undocked_choice_gives_keyboard_back_to_view` | After Esc on that panel, and after a click on the Top button of the panel opened there again, the panel is closed and `QApplication.activeWindow()` is the undocked view (a top-level `Gui::View3DInventor`), not the main window; the detail also has `orientation._return_to` | [orientation](specs/orientation.md) 2.3 |
| `view_docked_again` | Afterwards no 3D view is a top-level window and the MDI area's current window is a 3D view again | — |
| `start_page_commands_disabled` | With the Start page in front and after `Gui.Command.update()`, both commands' `QAction`s are disabled; the detail has `orientation.view3d_active()` (False), the type of the main window's `getActiveWindow()` (`MDIViewPy`) and of `FreeCADGui.activeView()` (still `View3DInventorPy`: the document's last 3D view) | [orientation](specs/orientation.md) 2.1 |
| `start_page_space_keeps_panel_closed` | A real Space with the Start view focused (`StartGui::StartView`) and the pointer on it leaves the panel closed and the list of open documents unchanged | [orientation](specs/orientation.md) 2.1 |
| `dark_rule_in_force` | A plain `QToolButton` outside the panel resolves its ButtonText to `#ffffff`, so the white-text rule really applies | [look](specs/look.md) |
| `dark_panel_text_color` | Under that rule the Pin and Front buttons (ButtonText) and the title (WindowText) resolve to `palette.TEXT` (`#1f2328`) | [orientation](specs/orientation.md) 2.2 |
| `dark_pin_text_readable` | The panel painted with and without the Pin button's text: the pixels the text changes reach at least 4.5:1 against the pixels behind them | [look](specs/look.md) |
| `app_stylesheet_restored` | The application stylesheet is the saved string again | — |
| `sketch_in_edit`, `sketch_commands_enabled` | The sketch is in edit; after `Gui.Command.update()` both commands' `QAction`s are enabled | [orientation](specs/orientation.md) |
| `sketch_space_opens_panel`, `sketch_escape_closes_panel`, `sketch_space_closes_panel` | In sketch edit a real Space in the 3D view opens the panel; Esc closes it; Space opens it again and Space on the panel closes it | [orientation](specs/orientation.md) AC 3, 8 |
| `sketch_normal_to_aligns_to_sketch`, `sketch_ctrl8_aligns_to_sketch` | In sketch edit with nothing selected, Normal To (`Gui.runCommand`, then a real `Ctrl+8`) makes the view direction parallel to the sketch normal and different from the skewed start | [orientation](specs/orientation.md) |
| `pad_dialog_open` | The Pad dialog is open and its `checkBoxReversed` is visible and enabled | — |
| `space_filter_active_in_jellyjams` | With the pointer over the task panel, a plain-Space `ShortcutOverride` sent to the focused check box is accepted on its way up (the Space filter on the `Tasks` dock and the main window) | [orientation](specs/orientation.md) 2.4 |
| `pad_space_toggles_check_box`, `pad_space_on_check_box_keeps_panel_closed` | With the pointer over the task panel, Space on the focused check box toggles it and does not open the panel | [orientation](specs/orientation.md) AC 25 |
| `pad_pointer_over_view_space_opens_panel`, `pad_pointer_over_view_check_box_unchanged` | With the same check box focused and the pointer over the 3D view, Space opens the panel and the check box keeps its state | [orientation](specs/orientation.md) 2.4 |
| `pad_dialog_space_in_view_opens_panel` | With the Pad dialog still open, Space in the 3D view opens the panel | [orientation](specs/orientation.md) AC 10 |
| `floating_task_dock_space_toggles_check_box`, `floating_task_dock_space_keeps_panel_closed` | With the `Tasks` dock floating (a window of its own; detail `filter_on_dock`: the dock is in `orientation._filtered`), the check box focused and the pointer over the dock, Space toggles the check box and the panel stays closed | [orientation](specs/orientation.md) 2.4 |
| `hole_without_solid_starts_nothing` | After pressing Hole in the empty body: the same objects as before, no sketch in edit, no task dialog, no pending sketch-first (`sketch_gesture._intent` is None) and no message box (FreeCAD's own Hole answers with a modal "No sketch to work on") | [sketching](specs/sketching.md) 2.6 |
| `hole_without_solid_hint` | The status bar, read right after the press, says `Hole needs a solid to cut into: create a boss or base feature first.` (the menu text from `getInfo()`, `Hole` in 1.1.4); the detail also says whether it is still shown 1.5 s later | [sketching](specs/sketching.md) 2.6 |
| `hole_two_bodies_no_needs_solid_text` | With two padded bodies and none active, no status-bar message during the press, right after it or 1.5 s later contains `needs a solid to cut into` | [sketching](specs/sketching.md) 2.6 |
| `hole_two_bodies_left_to_freecad` | FreeCAD answered the press itself with a modal dialog (recorded `PartDesignGui::DlgActiveBody`, "Active Body Required", rejected by the script), no sketch-first is pending, the document's objects are unchanged and no sketch is in edit | [sketching](specs/sketching.md) 2.6 |
| `late_dock_gets_space_filter` | Once its check box has the focus, the floating late dock (a window of its own) is in `orientation._filtered` (`filter_on_dock_at_creation`: whether it was already right after it was made; False in the recorded run) | [orientation](specs/orientation.md) 2.4 |
| `late_dock_space_toggles_check_box`, `late_dock_space_keeps_panel_closed` | With the pointer over that check box, Space toggles it and the panel stays closed | [orientation](specs/orientation.md) 2.4 |
| `panel_closed_on_leave` | The pinned panel, open before the switch, is hidden 3.5 s after switching to Part Design | [orientation](specs/orientation.md) AC 15 |
| `space_back_to_toggle_visibility`, `orientation_shortcut_removed`, `normal_to_shortcut_removed` | Hide/Show has its recorded key again; View Orientation and Normal To have none | [orientation](specs/orientation.md) AC 16 |
| `space_filter_dropped_on_leave`, `no_space_filter_after_leave` | `orientation._space_filter` is None and `orientation._filtered` is empty, and the same `ShortcutOverride` sent to the focused dock check box is no longer accepted | [orientation](specs/orientation.md) AC 26 |
| `plain_dock_space_toggles_after_leave`, `panel_stays_closed_after_leave` | In Part Design, Space on the focused dock check box toggles it and the panel stays closed | [orientation](specs/orientation.md) |

**Pass:** `orientation.json` has `"ok": true` (84 checks, every check passed, `errors` empty).
Recorded on FreeCAD 1.1.4 on 2026-10-28: all 84 checks pass, `errors` empty. In
`panel_normal_to_nothing_tooltip` the tool tip is not yet shown right after the click
(`tooltip_right_after`: None) and shows the hint 300 ms later, after the panel has closed (Qt
closes a tool tip on the window activation that closing the unpinned panel causes, so Normal To
shows it a moment later).
`info` records `toggle_visibility_before`, `align_override_before`, `animations_before`, the
animation state of each new view (`animation_enabled`), what the Space filter watches
(`space_filter_on`), the view direction before Top (`before_top`), the active window while the
panel is open, the XZ plane's label right after it was created (`pick_xz_plane_label`: still
FreeCAD's `XZ-plane`, JellyJams renames it a moment later, see the check detail), the surface type
of the cylinder's `Face1` (`pick_cylinder_face1`), whether
`Std_ViewDockUndockFullscreen` exists (`undock_command`), the GL widgets of the undocked view
(`undocked_view_children`), the docking-back attempts (`redock`), whether the Start page was
already open and the MDI window active after the start part (`start_page`), the length of the saved
application stylesheet, `sketch_alter_document_allowed`, the Tasks dock's name and floating state
(`task_dock`), the last key target and pointer in the 3D view (`view_key_target`,
`view_key_pointer`), the focus, pointer and Hide/Show state in the dock part (`dock_space`), a
message box closed during the hole part (`stray_modal`, absent when there was none), the bodies of
`OrientHole2` and its active body (`hole2`: None) and the
duration of the scripted steps (`seconds`). The profile must leave Hide/Show on FreeCAD's default
`Space` and must not bind `Std_AlignToSelection` itself. The script closes `Orient` after the
normal part and its other five documents at the end, and ends in Part Design.

Each check was confirmed to fail when the behavior it guards is broken. The script
opens and closes the panel only when it is not already in that state, so one failure does not
flip the next check.

### check_saved_cfg.py

Inspects a `user.cfg` that FreeCAD wrote after a quit with JellyJams active. Plain Python 3,
standard library only (FreeCAD's `python.exe` works).

```
python check_saved_cfg.py <user.cfg> [expected_nav] [expected_switch_to_wb] [expected_partdesign_switch] [expected_techdraw_switch]
```

| Argument | Meaning |
|---|---|
| `<user.cfg>` | The config file to inspect, for example `scratch\discard_user.cfg` |
| `expected_nav` | `NavigationStyle` the profile had before JellyJams (`info.nav_before` in `lifecycle_discard.json`). An empty string means the key must be absent; `-` skips the check. |
| `expected_switch_to_wb` | `Mod/Assembly` `SwitchToWB` before JellyJams (`info.switch_before.Assembly`): `absent`, `true`, `false` (`1` / `0` also work); `-` or omitted skips the check. |
| `expected_partdesign_switch` | `Mod/PartDesign` `SwitchToWB` before JellyJams (`info.switch_before.PartDesign`), same values; `-` skips the check. Omitted means `absent`, the state of a fresh throwaway profile. |
| `expected_techdraw_switch` | `Mod/TechDraw/General` `SwitchToWB` before JellyJams (`info.switch_before.TechDraw`), same values and default as above. |

| Check | Passes when |
|---|---|
| `nav_not_solidworks` | `NavigationStyle` is not `Gui::SolidWorksNavigationStyle` |
| `nav_matches_expected` | `NavigationStyle` equals `expected_nav` (or the check is skipped) |
| `no_jj_shortcut_overrides` | No `Preferences/Shortcut` entry for `Std_ViewFitAll`, `Std_Refresh`, `Std_ViewIsometric`, `JellyJams_NormalTo`, `Std_AlignToSelection` (FreeCAD's own Normal To, which JellyJams leaves alone), `JellyJams_ViewOrientation`, `Std_ViewBoxZoom`, `Std_ToggleVisibility` (the last two would be empty values left by the unbinding). The list is checked headless by `Test12NavigationShortcuts.test_saved_cfg_check_looks_for_every_jellyjams_key` |
| `no_leftover_backups` | `OriginalNavigationStyle`, `OriginalShortcuts`, `OriginalViewColors`, `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB` are empty or absent |
| `switch_to_wb_matches_expected` | Assembly `SwitchToWB` equals `expected_switch_to_wb` (or the check is skipped) |
| `partdesign_switch_restored` | Part Design `SwitchToWB` equals `expected_partdesign_switch`: absent unless another original was given (or the check is skipped) |
| `techdraw_switch_restored` | TechDraw `SwitchToWB` equals `expected_techdraw_switch`, with the same default (or the check is skipped) |

It prints JSON (`cfg`, `nav`, `overrides`, `backups`, `switch_to_wb` (Assembly), `switches` (all
three), `expected_switches`, `checks`, `ok`) and exits with 0 when clean, 1 otherwise.
`no_jj_shortcut_overrides` assumes the profile had no user override for those eight commands. It
does not inspect the 14 View color keys.

**Empty arguments:** Windows PowerShell 5.1 drops a bare `""` argument when it starts a native
program, which would shift every later argument one position to the left. Pass `'""'`
instead (checked on PowerShell 5.1), or run the command from `cmd.exe`. PowerShell 7 was not
checked. `Out-File -Encoding utf8` in PowerShell 5.1 writes a byte-order mark; read the file with
`ConvertFrom-Json` or Python's `utf-8-sig` codec.

### gui_tabs.py

```powershell
New-TestProfile tabs
Invoke-FreeCAD tabs gui_tabs.py
```

Creates a document with a Body, a Sketch and a Pad, activates JellyJams, selects each ribbon tab,
saves a screenshot of the ribbon dock per tab plus one of the whole window, collects the
Report-view lines that contain "JellyJams" or "Error", switches to Part Design and quits.

It asserts nothing. Review the output:

- `errors` is empty and `report_tail` has no JellyJams warning or error.
- `tabs` lists five tabs with these tool-button counts in a FreeCAD that has every ribbon command:
  Features 21, Sketch 22, Evaluate 22, Assembly 13, Drawing 31 (plain buttons + flyouts + toggle
  per tab, [ribbon-content](specs/ribbon-content.md) 2.6). `kinds` splits them into plain
  buttons, flyouts and toggles, and `separators` should read 3, 3, 3, 3, 4. Fewer buttons mean
  commands were skipped; the skipped ids are in the Report view.
- `enabled` depends on the document state.
- Compare the screenshots with the palette and styled elements in [look](specs/look.md) 2.2 and 2.3.

### Reading the results

Summary of every JSON file in `$Out` (PowerShell 5.1):

```powershell
foreach ($f in Get-ChildItem "$Out\*.json") {
    $r = Get-Content $f.FullName -Raw | ConvertFrom-Json
    $failed = @()
    if ($r.checks) {
        foreach ($c in $r.checks.PSObject.Properties) {
            $ok = if ($c.Value -is [bool]) { $c.Value } else { $c.Value.ok }
            if (-not $ok) { $failed += $c.Name }
        }
    }
    $total = if ($r.checks) { @($r.checks.PSObject.Properties).Count } else { 0 }
    "{0,-26} ok={1,-5} checks={2,-3} failed=[{3}] errors={4}" -f $f.Name, $r.ok, $total, ($failed -join ", "), (@($r.errors | Where-Object { $_ })).Count
}
```

| File | Shape |
|---|---|
| `gui_smoke_results.json` | `steps`, `checks` (`name` to `{ok, detail}`), `errors`, `labels` (object Name to Label), `ribbon` (`tabs` with built kinds and separators per tab, `skipped`, `substitutions`), `ok` |
| `lifecycle_<mode>.json` | `mode`, `checks`, `info` (recorded state, for example `nav_before`, `switch_before`, `stock_toolbars`, `state_during_prompt`), `errors`, `ok` |
| `sketch_first.json` | `checks`, `info` (`workbench` timeline, `a_prefs`, `b_trace`, `dialog_waits_ms`), `errors`, `ok` |
| `orientation.json` | `checks`, `info` (`toggle_visibility_before`, `before_top`), `errors`, `ok` |
| `saved_cfg_check.json` | Output of `check_saved_cfg.py`; `checks` values are plain booleans |
| `tabs_results.json` | `tabs` (`index`, `name`, `buttons`, `enabled`, `kinds` with `plain` / `flyouts` / `toggles`, `separators`, `png`), `errors`, `report_tail`; no `ok` key |

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| `workbench_registered` fails or nothing happens | JellyJams is not in FreeCAD's `Mod` folder. The Report view should show `JellyJams: workbench added, loaded from ...`. |
| The JSON file is from an earlier run | The run aborted before saving. Delete old JSON files before each run and read the new `errors`. |
| `gui_smoke_results.json` has no `ok` key | A step raised; see `errors`. |
| `prompt_is_open` fails | FreeCAD's "Save changes?" prompt was not open 1.5 s after the window was asked to close. |
| Random timing failures | A slow machine; the steps use fixed `QTimer.singleShot` delays. Raise the delays in the script. |
| The next command ran before FreeCAD quit | It was started with `&`; use `Invoke-FreeCAD` (`Start-Process -Wait`). |
| FreeCAD stays open | A modal dialog is waiting that the script did not handle. Close FreeCAD by hand; the results may be incomplete. |

## Manual checks (not automated)

These cover acceptance criteria that no script checks. Results are not recorded;
see [status.md](status.md).

**Crash recovery** ([core](specs/core.md) AC 27, [window-layout](specs/window-layout.md) AC 23,
[look](specs/look.md) AC 27, 28). Uses its own throwaway profile and kills only that FreeCAD
process:

```powershell
New-TestProfile crash
$crashArgs = '-u "{0}\crash_user.cfg" -s "{0}\crash_system.cfg"' -f $Out
$p = Start-Process -FilePath $FC -ArgumentList $crashArgs -PassThru
# In FreeCAD: select JellyJams, then run FreeCAD.saveParameter() in the Python console.
Stop-Process -Id $p.Id -Force
Start-Process -FilePath $FC -ArgumentList $crashArgs
```

Expected after the restart, before touching anything: Report-view recovery messages that mention
"3D background", "navigation style", "shortcuts", and one message each for the Assembly, Part
Design and TechDraw workbench switch; in a workbench other than JellyJams the stock toolbars, no
ribbon, the original navigation style and shortcuts and the original three `SwitchToWB`; the six
backup keys in `Mod/JellyJams` empty or absent.

**Headless entry point** ([core](specs/core.md) AC 4): with the add-on installed, run FreeCAD's
console program with a throwaway profile; the output must contain no JellyJams error or traceback:

```powershell
New-TestProfile cmd
& "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" -u "$Out\cmd_user.cfg" -s "$Out\cmd_system.cfg" -c "import FreeCAD"
```

**Addon Manager install:** in a throwaway profile (`FREECAD_USER_HOME`), add the custom repository
`https://github.com/jus-kim/JellyJams` with branch `main`, install, restart, select JellyJams.

## Adding tests

### Headless tests

- Add a method to the `TestNN...` class of the area in
  [`tests/test_headless.py`](../tests/test_headless.py), or a new class `TestNNName(HarnessCase)`;
  keep the number prefix so the run order follows the areas.
- Import the module under test inside the test with `self.module("jellyjams.<name>")`
  (`fresh=True` reloads it to reset module-level state). Never import `jellyjams` modules at the top
  of the file.
- Keep tests independent; the stubs are reset before each test. Write files only into
  `self.tmpdir()`. Keep the whole suite well below the 300 s watchdog.

Helpers on `HarnessCase`:

| Helper | Use |
|---|---|
| `self.module(name, fresh=False)` | Import (or reload) a module; fails the test with the traceback when the import breaks |
| `self.patch(obj, name, value)` | Monkeypatch, undone automatically after the test |
| `self.fakes({name: module})`, `fake_module(name, **attrs)`, `fake_modules({...})` | Stand-in modules such as `Show`, `UtilsAssembly` or another JellyJams module |
| `self.tmpdir()` | Temporary folder, deleted after the test |
| `self.lines(level)`, `self.jj(level)` | Captured console lines, all or only those prefixed `JellyJams: `; levels `message`, `warning`, `error`, `log` |
| `self.assertNoJellyJamsProblems()`, `self.assertAllPrefixed()` | No JellyJams warnings or errors; every line carries the prefix |
| `param(path)` | The stub `ParamGet(path)` group |

Services on `STUBS`:

| Service | Use |
|---|---|
| `set_commands(ids, info=None, shortcuts=None)` | What `listCommands()`, `Command.get(...).getInfo()` and `getShortcut()` report |
| `set_command_active(cmd_id, state)` | `isActive()` result; pass an exception to make it raise |
| `set_command_actions(cmd_id, actions)` | The `QAction`s that `Command.get(cmd_id).getAction()` returns (none unless set, like a FreeCAD command that is in no menu or toolbar) |
| `set_active_workbench(name)`, `set_active_dialog(value)` | `activeWorkbench().name()`, `Control.activeDialog()` |
| `set_active_view(view)` | What `FreeCADGui.activeView()` returns: None (the default), a view object (a 3D view has `getCameraNode`; `Test24Orientation` uses `FakeView3D`, which also records `setCameraOrientation`), or an exception instance it raises. The main window's `getActiveWindow()` follows it |
| `set_active_window(window)` | What the main window's `getActiveWindow()` returns instead (FreeCAD 1.1's `MainWindow::activeWindow`): None, a view object (a Start page without `getCameraNode`, another `FakeView3D`) or an exception it raises; without an argument it follows `set_active_view` again. A test that needs a main window without `getActiveWindow` patches `STUBS.main_window` with a plain `QMainWindow` |
| `selection_ex` | The list `Selection.getSelectionEx()` returns; `Test24Orientation` fills it with `FakePick` entries (`DocumentName`, `ObjectName`, `SubElementNames`, `SubObjects` shapes, `Object`) |
| `unresolved_selection_ex` | The list `Selection.getSelectionEx("", 0)` returns (the top-level object and the path below it); None (the default) means the same as `selection_ex` |
| `app.GeoFeature.getGlobalPlacementOf`, `placement_calls` | The stub returns `target.getGlobalPlacement()` and records `(target, root, path)`; patch it to return a placement along a link |
| `main_window`, `new_main_window(visible=True)`, `set_main_window(window)` | The offscreen `QMainWindow` that `getMainWindow()` returns |
| `pump(ms)`, `wait_until(predicate, timeout_ms)` | Process Qt events and timers |
| `run_calls`, `run_errors`, `registered`, `duplicate_commands`, `records`, `closed_windows` | Recorded calls and outputs to assert on |
| `gui.ActiveDocument` | Set to a `types.SimpleNamespace` with `getInEdit()` to simulate an object in edit (add `Document` and `ActiveView.getActiveObject` for the sketch-first tests) |
| `gui.activateWorkbench` | Replace it with a recorder to watch workbench switches; restore the stub's function in a cleanup, because `edit_guard` wraps whatever it finds. A FreeCAD command string is simulated with `exec(compile(text, "<string>", "exec"), {"Gui": STUBS.gui})` (`Test23EditGuard.run_code`) |

The suite pins the project's public facts on purpose. Update these tables when the code changes:

| Change | Update in `tests/test_headless.py` (and elsewhere) |
|---|---|
| New module in `jellyjams/` | An import test is generated from disk. Add it to `EXPECTED_MODULES` and its public names to `API_NAMES`; add it to `PURE_MODULES` if it must import nothing from FreeCAD or Qt. Start the file with the three-line header. |
| New `JellyJams_*` command | `EXPECTED_COMMANDS`, `EXPECTED_PROVIDERS`, `EXPECTED_MENU_TEXTS`, `COMMAND_ICONS`, the `CMD_*` and `ALL_COMMANDS` entries of `CONSTANT_VALUES`; add an icon. A command that declares a `cmd_type` goes into `COMMAND_CMD_TYPES`. A command deliberately left off the ribbon goes into `OFF_RIBBON_COMMANDS`; a command in the JellyJams menu into the menu lists of `Test06Lifecycle.test_initialize_order_and_once_per_process` and `test_real_activation_cycle_under_stubs` |
| SolidWorks keyboard shortcut | `EXPECTED_SHORTCUTS` (the whole `shortcuts.SHORTCUTS` table, in order; a JellyJams command also into `JJ_SHORTCUT_COMMANDS`); a FreeCAD command that owns the key by default goes into `DEFAULT_KEY_OWNERS` so the clash and its restore are exercised; the command into `JELLYJAMS_SHORTCUTS` of `check_saved_cfg.py` |
| An icon that is not a command or relation icon (like the Orientation fallbacks) | Its own table (`ORIENTATION_FALLBACK_ICONS`), added to `Test21Icons.icon_names`; `test_icon_folder_holds_exactly_the_used_icons` fails for an icon file nobody uses |
| New icon | `resources/icons/<name>.svg`: XML declaration, then one comment holding both SPDX lines (license and copyright), `viewBox="0 0 64 64"`, no `<text>`, `<style>`, `<image>`, `<script>`, `<filter>`, `<mask>`, `<pattern>`, `<marker>`, `<foreignObject>` or `data:image` URIs (`Test21Icons`) |
| Ribbon content | `RIBBON_PLAIN`, `RIBBON_FLYOUTS`, `RIBBON_FLYOUT_TITLES`, `RIBBON_TOGGLE`, `RIBBON_TAB_COUNTS`, `RIBBON_TOTALS`, `RIBBON_FALLBACKS`, the stack lists in `Test13RibbonModel.test_stacks`; the tables and counts in [ribbon-content](specs/ribbon-content.md) and the gui_tabs counts in [status.md](status.md) and above |
| Lifecycle steps | `INIT_HELPERS`, `ACTIVATION_STEPS`, `DEACTIVATION_STEPS`, `QUIT_REVERT_STEPS`, `QUIT_REAPPLY_STEPS` |
| New constant | `CONSTANT_VALUES` |
| New overridden FreeCAD parameter (needs a crash backup) | `BACKUP_KEYS` in `CONSTANT_VALUES`, a test in `Test04Recovery`, and `BACKUP_KEYS` in `gui_smoke.py`, `gui_lifecycle.py` and `check_saved_cfg.py`. Another module's `SwitchToWB` also goes into `SWITCH_BACKUPS` (headless) and `SWITCH_GROUPS` (the GUI scripts and `check_saved_cfg.py`) |
| Palette | `PALETTE_VALUES`, `MANAGED_KEYS`; the contrast tests must still pass |

Every `.py` file in `tests/` needs the three-line header too (`Test02Hygiene.test_three_line_header`).

### GUI tests

- Put a new script in `tests/` as `gui_<topic>.py`, starting with the three-line header and a
  docstring that shows the exact command line. For a new lifecycle scenario, add a mode to
  `gui_lifecycle.py` (its functions plus an entry in the `START` table at the bottom).
- Follow the existing pattern:
  - output folder from `JELLYJAMS_RESULTS_DIR` (default `<repo>/scratch`);
  - a results dict with `checks` and `errors`, a `note(name, ok, detail)` function, a `save()` that
    writes JSON and sets `"ok"`;
  - steps chained with `QtCore.QTimer.singleShot`, each wrapped by a `guarded` decorator that saves
    and quits on an exception;
  - never `time.sleep()`: it blocks the event loop, so FreeCAD's and JellyJams' own timers stop;
  - record the "before" state first and compare against it instead of assuming profile values;
  - end with `QtWidgets.QApplication.instance().quit()` after saving.
- Use snake_case check names; [status.md](status.md) refers to them by name.
- Run it only with a throwaway profile, add its command to this page, and record the result in
  [status.md](status.md).
