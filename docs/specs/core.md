# JellyJams specification: Core

> **Implemented in:** [`Init.py`](../../Init.py), [`InitGui.py`](../../InitGui.py), [`package.xml`](../../package.xml), [`jellyjams/__init__.py`](../../jellyjams/__init__.py), [`constants.py`](../../jellyjams/constants.py), [`console.py`](../../jellyjams/console.py), [`params.py`](../../jellyjams/params.py), [`paths.py`](../../jellyjams/paths.py), [`fcgui.py`](../../jellyjams/fcgui.py), [`doc_utils.py`](../../jellyjams/doc_utils.py), [`commands.py`](../../jellyjams/commands.py), [`recovery.py`](../../jellyjams/recovery.py), [`lifecycle.py`](../../jellyjams/lifecycle.py), [`quit_guard.py`](../../jellyjams/quit_guard.py), [`qt_filter.py`](../../jellyjams/qt_filter.py), [`diagnostics.py`](../../jellyjams/diagnostics.py) (all modules under `jellyjams/` unless a path is shown). The navigation and shortcut areas have no separate specification; their contract is stated here (steps A4, A5, D14, D15, section 4.8 and section 7) and implemented in [`navigation.py`](../../jellyjams/navigation.py) and [`shortcuts.py`](../../jellyjams/shortcuts.py). The Orientation panel that `Space` opens and Normal To on `Ctrl+8` have their own spec, [orientation.md](orientation.md).
>
> **Status:** see [../status.md](../status.md)

Area: **core**. This covers the add-on entry points, how the workbench is registered, the workbench lifecycle (what happens on first use, on entering, on leaving, on quit, and at startup after a crash), version and metadata, the Diagnostics command, the Qt message filter, and how commands are registered.

Other areas (layout, theme, viewport colors, navigation, shortcuts, ribbon, tree naming, sketching, assembly, dialog terms, drawing) own their own features. This spec says **when** core calls each of them and **in what order**, and sets the rules every area must follow. Their visual and functional details are in their own specs.

---

## 1. Purpose

JellyJams is a FreeCAD 1.1+ workbench that makes FreeCAD look, feel and work like SolidWorks while it is the active workbench, and leaves stock FreeCAD exactly as it was as soon as the user switches to any other workbench, quits, or restarts after a crash.

Core is the backbone that:

- makes FreeCAD discover the add-on and list the workbench,
- turns the SolidWorks-style experience on when the user enters the workbench and off when they leave, in a fixed order where one failure never stops the other steps,
- makes sure nothing JellyJams changed is ever left behind in the user's saved FreeCAD configuration (on quit, and at the next startup after a crash),
- offers a Diagnostics window with copyable environment details for bug reports,
- hides one known, harmless Qt log flood ("render glyph failed") while the workbench is active.

---

## 2. Global conventions (binding on every area)

1. **Identity strings.** Workbench key and class name `JellyJamsWorkbench`. Menu text `JellyJams`. Every FreeCAD command id that JellyJams registers is `JellyJams_` followed by the tool's ribbon name without spaces (for example `JellyJams_RotateComponent`). Every Qt objectName that JellyJams creates is `JellyJams` followed by a role word; the ribbon dock is `JellyJamsCommandManager`. The theme stylesheet block sits between exactly one `/* @jellyjams-stylesheet-open */` and one `/* @jellyjams-stylesheet-close */` marker.
2. **Parameter group.** All add-on settings and backups live under `User parameter:BaseApp/Preferences/Mod/JellyJams`.
3. **Naming rule.** No identifier, objectName, file name or icon file name may contain "SolidWorks" (in any letter case). SolidWorks words are allowed in user-visible labels, tooltips and messages.
4. **Language.** English only. No translation layer.
5. **Console prefix.** Every Report view / console message from JellyJams starts with `JellyJams: `.
6. **No bundled third-party assets.** Ribbon buttons for FreeCAD commands use FreeCAD's own icons at runtime. JellyJams-only commands (Diagnostics included) and the workbench itself use new, original icons made for this project.
7. **Exact restore.** Any area that writes a persistent FreeCAD parameter must, before its first write, record the previous value or the fact that the key was missing. It must store that record in the JellyJams parameter group so a crash can be recovered, and on restore it must remove keys that were missing before (never write a "default" in their place). Every such area must take part in the startup recovery (section 7) and the quit guard (section 6.6).
8. **Never touch** FreeCAD's `StyleSheet` / `Theme` preferences, and never call a stylesheet setter on the whole application. Theming applies only to the main window (theme area).
9. **No JellyJams toolbars.** The workbench registers no FreeCAD toolbars of its own. Everything visible lives in the ribbon dock, plus one small menu (section 4.2).
10. **Process-wide hooks gate themselves.** Some hooks are document observers or global Qt hooks that must stay registered for the whole session. When such a hook should act only inside JellyJams, it must check that the active workbench is `JellyJamsWorkbench` (from `FreeCADGui.activeWorkbench().name()`) before it does anything.

---

## 3. Add-on entry points and packaging

### 3.1 Files at the add-on root

The add-on uses FreeCAD's classic Mod layout: an add-on folder (installed as `Mod/JellyJams`) containing:

| File / folder | Role |
|---|---|
| `Init.py` | Headless entry point. May be empty. |
| `InitGui.py` | GUI entry point: registers the workbench and runs the startup crash recovery. |
| `package.xml` | Addon Manager metadata (section 3.4). |
| a Python package (`jellyjams/`) | All real code. The package name must not contain "SolidWorks". |
| `resources/icons/` | Original icons: the workbench icon and the JellyJams-only command icons. |
| `README.md`, `CHANGELOG.md`, license file(s) | Release documents (section 3.5). |

### 3.2 Headless entry (`Init.py`)

- FreeCAD runs it also in console mode (`FreeCADCmd`). It must not import `FreeCADGui`, PySide/Qt, or anything that needs a GUI.
- It does nothing visible. Starting `FreeCADCmd` with the add-on installed produces no JellyJams error or warning.

### 3.3 GUI entry (`InitGui.py`): what happens at FreeCAD startup

FreeCAD runs `InitGui.py` with `exec()` at every GUI startup. This happens before any workbench is activated, including an autoloaded one. These FreeCAD facts are binding constraints:

- `__file__` is **not** defined. The add-on folder must be found some other way, for example through the file location of a real module in the add-on's package, falling back to a search of `sys.path` for a folder that holds both `InitGui.py` and the add-on package. It must work when the add-on folder is a symlink or junction.
- Names defined at the top level of `InitGui.py` are **not** visible inside class bodies, and may not be visible in methods called later. Class bodies may contain only literals. Methods import what they need locally. Computed class attributes, such as the icon path, are assigned after the class definition.
- The file must stay light. It only registers the workbench and runs the startup recovery. It builds no widgets, registers no commands, and applies no theme.

At startup, in this order:

1. **Locate the add-on folder** and set the workbench icon to the absolute path of the workbench icon file. If the folder cannot be found, the icon stays empty: the workbench is listed without an icon and registration still goes ahead.
2. **Register the workbench** with `FreeCADGui.addWorkbench(...)`, unless `JellyJamsWorkbench` already appears in `FreeCADGui.listWorkbenches()`.
   - On success: a console message saying the workbench was registered, naming the folder it was loaded from, or saying the path is unknown.
   - Already registered (for example, the add-on is present twice under `Mod/`, as a real folder plus a symlink during development): a **warning** saying this copy is skipped, with its path. No exception, no second entry.
   - Any other failure: an **error** with the traceback. FreeCAD's startup continues.
3. **Run the startup crash recovery** (section 7). It runs whether or not step 2 succeeded.

### 3.4 `package.xml` (Addon Manager manifest)

It must be valid against `<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">` and contain:

| Element | Required value / rule |
|---|---|
| `name` | `JellyJams` |
| `description` | One or two sentences describing a SolidWorks-style UI for FreeCAD (CommandManager-style ribbon, SolidWorks tool and tree names, light theme, SolidWorks navigation and shortcuts), plus a trademark disclaimer stating that it is not affiliated with or endorsed by Dassault Systèmes. |
| `version` | Exactly the add-on's version string (section 3.5). First release: `0.1.0`. |
| `date` | Release date in `YYYY-MM-DD` form. For `0.1.0`: `2026-10-28`. |
| `icon` | Relative path to the workbench icon file. The file must exist. |
| `maintainer` | `jus-kim`, attribute `email="hi@jus.kim"` |
| `license` | One element per license, with an official SPDX identifier (not abbreviated) as text and a `file` attribute pointing to an existing file in the add-on. Which licenses to use is a project decision. |
| `url` | `type="repository"`, `branch="main"`, text `https://github.com/jus-kim/JellyJams`. The branch must be given, because the Addon Manager otherwise assumes `master`. If a `type="readme"` URL is added, it must point into the same branch (`/blob/main/`). |
| `freecadmin` | `1.1.0`. It must agree with the add-on's minimum FreeCAD version (1.1). |
| `tag` | Search keywords (for example ribbon, ui, theme, solidworks-style). Tags are search metadata, not identifiers. |
| `content/workbench` | `classname` = `JellyJamsWorkbench`; `subdirectory` = `./`; `icon` = same icon path as above; `name` = `JellyJams` (must equal the workbench MenuText); `description` = short SolidWorks-style UI phrase. |

A case-insensitive Addon Manager search for "JellyJams" must find the package through its name, description or tags.

### 3.5 Version: single source of truth

- The add-on keeps its version string (for example `0.1.0`) in exactly one place in its code. The Python package exposes it as `__version__`. The Diagnostics window and the startup environment line read it from that place.
- The minimum supported FreeCAD version is **1.1** (major, minor).
- Release consistency rules, which a release check must verify:
  - `package.xml` `<version>` equals the code's version string.
  - `<date>` is `YYYY-MM-DD`.
  - `<freecadmin>` starts with the code's minimum version (`1.1`).
  - `CHANGELOG.md` has a heading line `## <version> — <date>` (an em dash or a hyphen are both accepted between them).
  - `README.md` contains the "not affiliated with or endorsed by Dassault Systèmes" note.
  - The workbench class name in `InitGui.py` equals `<classname>`.
  - The registration key equals `<classname>`.
  - MenuText equals the `<content><workbench><name>`.
- Bump the version, the date and the changelog together on every release. The Addon Manager uses the version to detect updates.

---

## 4. The workbench

### 4.1 Identity

| Property | Value |
|---|---|
| Registration key / class name | `JellyJamsWorkbench` |
| MenuText (shown in the workbench selector) | `JellyJams` |
| ToolTip | Says it is a SolidWorks-style UI for FreeCAD |
| Icon | Absolute path to the new original JellyJams workbench icon. The file name must not contain "solidworks". |
| `GetClassName()` | `Gui::PythonWorkbench` |

### 4.2 User-visible elements owned by core

- **Workbench selector entry** "JellyJams" with the JellyJams icon.
- **Menu "JellyJams"** in the main menu bar, present while the workbench is active (FreeCAD shows a workbench's menus only while it is active). It holds four items, in this order:
  1. **View Orientation** (`JellyJams_ViewOrientation`, [orientation.md](orientation.md)).
  2. **Normal To** (`JellyJams_NormalTo`, [orientation.md](orientation.md)). Both orientation commands must be in a menu: FreeCAD creates a command's `QAction`, and so a working keyboard shortcut, only for commands placed in a menu or toolbar, and the ribbon's own buttons do not count. Without these entries `Space` and `Ctrl+8` (section 4.8) would do nothing.
  3. **Appearances** (`JellyJams_Appearances`, [appearances.md](appearances.md)), which raises or reopens the right-side colouring browser.
  4. **Diagnostics** (`JellyJams_Diagnostics`). Diagnostics is also a large button on the ribbon's Evaluate tab ([ribbon-content](ribbon-content.md) 2.5).
- **Diagnostics dialog** (section 9).
- **No toolbars** of its own.

### 4.3 First use: Initialize

FreeCAD calls Initialize once per session, the first time the user activates the workbench (or when FreeCAD autoloads it), before the first Activated. It must:

1. **Report the environment** on one line: a console **message** with the add-on version, the FreeCAD version (major.minor.patch) and the Qt binding in use. If FreeCAD is older than 1.1, print a **warning** instead, saying the FreeCAD version is older than the minimum (1.1) and is not tested. Loading continues in both cases.
2. **Register all JellyJams commands** (section 8).
3. **Start the one-per-session helpers** of other areas that must exist exactly once per process. These are the drawing area's helpers: automatic SolidWorks-style labels for Section View / Detail View, a zoom-dependent line display on drawing sheets, a weld-symbol leader that follows the symbol, and the watcher that re-places a sheet sketch's view after an edit or an undo/redo. Each of them gates itself where its spec says so.
4. **Add the "JellyJams" menu** with `JellyJams_ViewOrientation`, `JellyJams_NormalTo`, `JellyJams_Appearances` and `JellyJams_Diagnostics`, in that order (section 4.2), once per workbench instance.
5. Print a console **message** that the workbench is initialized.

If anything here raises, print a console **error** saying that initialization failed, with the traceback. The exception must not escape to FreeCAD. Activated still runs later, and its steps are still attempted.

### 4.4 Entering the workbench: Activated

FreeCAD calls Activated each time the user switches **to** JellyJams, and also when it autoloads JellyJams at startup. Core must apply the following steps in **exactly this order**. Each step is guarded on its own: if one raises, core prints a console **error** naming the feature in plain words (for example, that the theme could not be applied), with the traceback, and moves on to the next step.

| # | Step (owning area) | What the user gets |
|---|---|---|
| A1 | **Window layout on** (layout) | It must come first: the layout takes its snapshot of the window state before anything else changes the UI. Then it hides FreeCAD's managed toolbars except the quick-access ones (File, Edit, Workbench), and docks the task panel (PropertyManager role) and the Report view on the right. If the main window is not shown yet (autoload), see section 6.5. |
| A2 | **Theme on** (theme) | Light SolidWorks-like stylesheet appended to the main window between the two stylesheet markers, exactly once. |
| A3 | **Viewport colors on** (viewport colors) | Light 3D-view gradient and SolidWorks sketch colors, written to `Preferences/View` with a backup. |
| A4 | **SolidWorks mouse navigation on** (navigation) | `Preferences/View` `NavigationStyle` = `Gui::SolidWorksNavigationStyle`, with a backup. |
| A5 | **SolidWorks keyboard shortcuts on** (shortcuts) | The keys of section 4.8 as overrides in `Preferences/Shortcut`, with a backup; commands that own one of those keys are unbound. |
| A6 | **Who gets Space** (orientation) | A filter on the main window and on each of its docks decides a plain `Space`: with the pointer over a 3D view or the model tree it opens the Orientation panel; elsewhere a focused button, check box or combo box, or a list with a checkable current item or typing edits, takes `Space` itself, while toolbar, status-bar and ribbon controls never do. A dock made later gets the filter once one of its widgets takes the focus (`QApplication.focusChanged` is watched while JellyJams is active). Key repeat is turned off for View Orientation, so a held `Space` opens the panel once ([orientation.md](orientation.md) 2.4). One filter, however often JellyJams is activated. |
| A7 | **Ribbon shown** (ribbon) | The CommandManager-style ribbon dock `JellyJamsCommandManager`. It is built on first show and never rebuilt by later activations. |
| A7a | **Appearances tab shown** (appearances) | The right-side native colour/finish library, tabbed beside Tasks. This suffix preserves existing criterion references; in the code table it follows ribbon and precedes naming. |
| A8 | **FeatureManager tree naming on** (naming) | New features get SolidWorks names (Sketch1, Boss-Extrude1, Top Plane...). The observer is registered once per session and gates itself on the active workbench. |
| A9 | **Edit sketches and features inside JellyJams** (sketching) | Opening a sketch does not switch to the Sketcher workbench (sketch-edit hook, `sketch_edit`). Then the feature-edit guard (`edit_guard`): opening a Part Design feature for editing does not switch to Part Design, while the workbench selector still switches ([sketching.md](sketching.md) 2.7). |
| A10 | **Feature from the open/selected sketch, and sketch first** (sketching) | Only if that area has something to switch on. (Both are started from the ribbon's click dispatch and need no step.) |
| A11 | **"Sketch" context icon next to a selected face** (sketching) | |
| A12 | **Add Relations panel** while sketching (sketching) | |
| A13 | **Mate panel** for assemblies (assembly) | |
| A14 | **Drag files into an assembly**, and **stay in JellyJams when an assembly, a body or a drawing page is activated** (assembly) | The second part (`switch_prefs`) sets `SwitchToWB` = false in `Preferences/Mod/Assembly`, `Preferences/Mod/PartDesign` and `Preferences/Mod/TechDraw/General`, each with its own backup ([assembly.md](assembly.md) 5). |
| A15 | **SolidWorks terms in FreeCAD dialogs** (dialog terms) | |
| A16 | **Qt message filter installed (once) and switched on** (core, section 10) | |

### 4.5 Leaving the workbench: Deactivated

FreeCAD calls Deactivated when the user switches **away** from JellyJams to another workbench. It does **not** call it on quit (section 6.6). The steps run in **reverse order**, each guarded on its own like in Activated, with an error that names the feature:

| # | Step | Result |
|---|---|---|
| D0 | Appearances dock removed and its timer stopped | This happens before all stock-layout restoration. |
| D1 | Qt message filter switched **off** | Messages pass through unchanged again. |
| D2 | Dialog terms off | Stock FreeCAD dialog texts. |
| D3 | Assembly drag-and-drop off, and the three `SwitchToWB` preferences restored exactly | FreeCAD opens dropped files as usual and switches to the Assembly, Part Design and TechDraw workbenches as configured. |
| D4 | Mate panel off | |
| D5 | Add Relations panel off | |
| D6 | "Sketch" context icon off | |
| D7 | **End any running on-sheet pick mode**: placing a Note (text), a Weld Symbol, or a Projected View | The drawing sheet stops catching clicks. |
| D8 | **End a running Rotate Component** (free rotate) | |
| D9 | Feature-from-sketch helper off | Only if that area has something to switch off. |
| D10 | Feature-edit guard off, then sketch-edit hook off | `FreeCADGui.activateWorkbench` and TempoVis are FreeCAD's own functions again: feature edits switch to Part Design and sketches open in the Sketcher, as in stock FreeCAD. |
| D11 | Tree naming | The observer may stay registered for the session, because it gates itself. If the naming area has something to switch off, it is switched off here. |
| D12 | **Orientation panel closed and the Space filter removed** ([orientation.md](orientation.md) 2.5) | The `JellyJamsOrientation` panel is hidden, pinned or not, the focus watch of A6 is disconnected, and the Space filter of A6 is removed from the main window and every dock it was put on (docks made later included). Safe when the panel was never opened, the filter never installed or a dock deleted meanwhile. |
| D13 | Ribbon hidden | Dock `JellyJamsCommandManager` hidden, and it must stay hidden (see the delayed pass in 6.4). |
| D14 | Shortcuts restored exactly | Previous overrides back, added ones removed, unbound commands (Box Zoom on `Ctrl+B`, Hide/Show on `Space`) get their keys back, backup cleared. |
| D15 | Navigation style restored exactly | Previous value, or the key removed if it was missing; backup cleared. |
| D16 | Viewport colors restored exactly | Backup cleared. |
| D17 | Theme removed | The main window stylesheet is byte-for-byte what it was before A2. |
| D18 | Window layout off | Toolbars and docks that JellyJams changed are restored. Toolbars JellyJams did not hide keep the visibility FreeCAD just gave them (FreeCAD shows the next workbench's toolbars before it calls Deactivated). A pending deferred layout apply (6.5) is cancelled. |

### 4.6 Idempotency and fault isolation

- Activated twice in a row, with no Deactivated between them, changes nothing the second time:
  - no duplicate ribbon buttons, and no ribbon rebuild,
  - the theme block appears exactly once,
  - backups are not overwritten,
  - observers and event filters are registered once,
  - the Qt filter is installed once.
- Deactivated without a prior Activated, or twice in a row, does nothing harmful and prints no error.
- Initialize can run again (for example on a reload). Command registration must then be a silent no-op (section 8).
- No step may let an exception escape into FreeCAD's workbench machinery.

### 4.7 Ordering facts that core relies on (FreeCAD 1.1 behavior)

- On a workbench switch, FreeCAD shows the **next** workbench's toolbars first, and calls the old workbench's Deactivated about 200 ms later. So leaving must restore only what JellyJams changed, never a blanket window-state restore that would hide the new workbench's toolbars (layout area).
- FreeCAD's dock overlay manager rearranges docks about 100 ms after changes. Entering and leaving therefore need a delayed second pass. After the delayed pass on leaving (about 250 ms), the ribbon dock must be hidden again if JellyJams is no longer active (layout and ribbon areas).
- FreeCAD's asynchronous window-state restore can re-show a dock. The ribbon guards against this by watching its own visibility.

### 4.7.1 Middle-button orbit response (A4, D15)

The native SolidWorks navigation preset supplies the button mapping: middle drag
orbits, Ctrl+middle drag pans, Shift+middle drag zooms. JellyJams MUST additionally
balance orbit movement against the shorter viewport dimension. FreeCAD divides
horizontal and vertical deltas by width and height separately; without correction
an ultrawide viewport makes horizontal orbiting much slower.

- Only 3D OpenGL widgets under `Gui::View3DInventorViewer` are mouse-filtered.
  Viewer widgets are also watched for key events that require position rebasing.
  New, split and undocked views use the same discovery rule.
- During an unmodified middle drag, scale each physical delta by
  `(axis_size - 1) / (shorter_size - 1)`, with denominators at least one pixel.
  Forward the resulting coordinate stream to FreeCAD's own navigation engine.
  Native orbit mode, sensitivity and pivot settings MUST NOT be overridden.
- Ctrl-pan and Shift-zoom keep physical movement deltas. At modifier/key changes,
  rebase the native mouse position with a middle press before movement, without
  moving the camera. Middle clicks retain native recenter behavior.
- Native cursor-warp navigation (`ResetCursorPosition=True`) bypasses correction.
  A wheel event uses the physical cursor and ends correction for that held drag.
- No application-wide event filter is installed. A focus watcher plus a one-second
  discovery timer finds later view widgets; both stop on leave/quit. Removing a
  transformed drag ends native orbiting before physical coordinates resume.
- The focus callback MUST only schedule/coalesce a zero-delay discovery timer.
  It MUST NOT traverse Qt children synchronously: FreeCAD emits focus changes
  while native task widgets are being destroyed, when PySide child wrapping can
  crash outside Python exception handling. Initial discovery is deferred too.
  No old/new focus widget is captured for queued delivery. Stop MUST cancel both
  the deferred focus timer and periodic discovery timer.
- `navigation.install/uninstall/recover` own the runtime hook. Existing quit-revert
  and quit-reapply steps remove/reinstall it, including a cancelled quit. A crash
  leaves no hook behind. No new persistent setting or backup format is introduced.

### 4.8 SolidWorks keyboard shortcuts (A5, D14)

While JellyJams is active, `Preferences/Shortcut` holds these overrides (`shortcuts.SHORTCUTS`, in this order):

| Key | Command | SolidWorks meaning |
|---|---|---|
| `F` | `Std_ViewFitAll` | Zoom to Fit |
| `Z` | `Std_ViewZoomOut` | Zoom out |
| `Shift+Z` | `Std_ViewZoomIn` | Zoom in |
| `Ctrl+B` | `Std_Refresh` | Rebuild |
| `Ctrl+1` | `Std_ViewFront` | Front |
| `Ctrl+2` | `Std_ViewRear` | Back |
| `Ctrl+3` | `Std_ViewLeft` | Left |
| `Ctrl+4` | `Std_ViewRight` | Right |
| `Ctrl+5` | `Std_ViewTop` | Top |
| `Ctrl+6` | `Std_ViewBottom` | Bottom |
| `Ctrl+7` | `Std_ViewIsometric` | Isometric |
| `Ctrl+8` | `JellyJams_NormalTo` | Normal To; in a sketch with nothing selected, the sketch plane ([orientation.md](orientation.md) 2.6) |
| `Space` | `JellyJams_ViewOrientation` | Orientation dialog ([orientation.md](orientation.md)) |

Rules:

- A command the running FreeCAD does not have is skipped, with one log line naming it. This includes `JellyJams_ViewOrientation` and `JellyJams_NormalTo` when their registration failed; `Space` then stays with its FreeCAD owner and `Ctrl+8` is left as it was.
- FreeCAD's own Normal To, `Std_AlignToSelection`, is not in the table and keeps its key. Only a user who gave it `Ctrl+8` sees it unbound while JellyJams is active (next rule), and gets the key back on leave.
- Every other command that owns one of these keys when JellyJams is activated is unbound (an empty override) while JellyJams is active. In FreeCAD 1.1 these are `Std_ViewBoxZoom` (`Ctrl+B`) and `Std_ToggleVisibility` (Hide/Show, `Space`). Keys are compared in their normalized form (`space` and `Space` are the same key). A command the user has moved to another key keeps it.
- The previous state of every touched command (JellyJams' own and the unbound ones) is saved in `OriginalShortcuts` before the first write (section 7) and restored exactly on leave (D14), on quit (6.6) and at the next start after a crash (section 7).
- `JellyJams_ViewOrientation` and `JellyJams_NormalTo` have no built-in `Accel`; their keys exist only through this table, so they disappear on leave. Both must be listed in the JellyJams menu (4.2), because FreeCAD gives a command a working shortcut only once the command is in a menu or toolbar.

---

## 5. Settings owned by core

Core adds no preferences page. Its only user setting is the boolean parameter `SilenceGlyphWarnings` in `User parameter:BaseApp/Preferences/Mod/JellyJams` (default true; section 10). Core also reads the six crash-backup keys listed in section 7. All parameter use is listed in section 11.

---

## 6. Lifecycle timing in detail

### 6.1 Session start (no autoload)

FreeCAD startup → `InitGui.py` runs → workbench registered → startup crash recovery (section 7) → FreeCAD finishes starting in the user's default workbench. JellyJams changes nothing else until the user selects it.

### 6.2 First selection of JellyJams

Initialize (4.3), then Activated (4.4).

### 6.3 Later selections

Activated only.

### 6.4 Switching away

Deactivated (4.5), then a delayed second pass (about 250 ms) that restores the layout again and re-hides the ribbon if it was re-shown.

### 6.5 Autoload at startup

If JellyJams is FreeCAD's autoload workbench, Activated runs **before** the main window is shown and before FreeCAD restores the saved window state.

- Theme, viewport colors, navigation, shortcuts and the other steps apply right away.
- The **window-layout snapshot and toolbar hiding must wait** until the main window is visible. Core checks about every 200 ms and gives up after about 12 s with a console **warning** that the layout was not applied (the other features stay active).
- If the user has left JellyJams before the window appears, the deferred layout apply is cancelled.
- Once the deferred layout is applied, the ribbon is shown again if JellyJams still wants it, because FreeCAD's window-state restore may have hidden it.
- Result: leaving JellyJams later brings back the user's own saved toolbars, not FreeCAD's bootstrap layout.

### 6.6 Quit guard (FreeCAD never calls Deactivated on quit)

On quit, FreeCAD saves the window layout (`MainWindowState`) and all parameters (`user.cfg`). JellyJams must make sure none of its changes get saved:

- While JellyJams is the active workbench (also when an autoload deferral has not applied the layout yet), a **Close-event filter on the main window** (installed at most once per session; it runs before FreeCAD's own close handling) must, as soon as the main window receives a Close event:
  - restore the window layout,
  - remove the theme,
  - restore the viewport colors,
  - hide the ribbon,
  - restore the shortcuts,
  - restore the navigation style,
  - restore the Assembly, Part Design and TechDraw `SwitchToWB` settings. (They are restored on quit as well; JellyJams does not leave them to the next startup's recovery.)

  All JellyJams backup keys are then cleared. The filter must **not** consume the event: FreeCAD's close goes ahead as usual.
- **If documents have unsaved changes**, FreeCAD shows its "Save changes?" prompt. That prompt runs a nested event loop in which timers keep firing, and `QApplication.activeModalWidget()` is non-null while it is open.
  - **While a modal dialog is open**, JellyJams must **not** re-apply anything. It checks again about every 600 ms.
  - **Cancel** (the window is still visible and JellyJams is still the active workbench once the modal is gone): re-apply the layout, theme, viewport colors, navigation, shortcuts, ribbon and `SwitchToWB` overrides, exactly once each (the theme block exactly once).
  - **Discard / Save** (the application closes): nothing is re-applied, so the saved `user.cfg` and window state are clean.
- If JellyJams is not the active workbench when the window closes, the guard does nothing.

### 6.7 Crash

No Deactivated and no quit guard run. Backups remain in `user.cfg` if FreeCAD had saved them earlier. The next startup recovers them (section 7).

---

## 7. Startup crash recovery

Runs from `InitGui.py` at every GUI startup, after workbench registration. It runs before any workbench activation and whether or not JellyJams will be used in this session.

For each managed setting below, independently (one failure never blocks the others):

| Backup key in `Mod/JellyJams` | FreeCAD settings restored | Owning area |
|---|---|---|
| `OriginalViewColors` | The viewport gradient and sketch color keys in `User parameter:BaseApp/Preferences/View` | viewport colors |
| `OriginalNavigationStyle` | `User parameter:BaseApp/Preferences/View` → `NavigationStyle` | navigation |
| `OriginalShortcuts` | Command-id keys in `User parameter:BaseApp/Preferences/Shortcut` | shortcuts |
| `OriginalSwitchToWB` | `User parameter:BaseApp/Preferences/Mod/Assembly` → `SwitchToWB` (Bool) | assembly (`switch_prefs`) |
| `OriginalPartDesignSwitchToWB` | `User parameter:BaseApp/Preferences/Mod/PartDesign` → `SwitchToWB` (Bool) | assembly (`switch_prefs`) |
| `OriginalTechDrawSwitchToWB` | `User parameter:BaseApp/Preferences/Mod/TechDraw/General` → `SwitchToWB` (Bool) | assembly (`switch_prefs`) |

Rules:

- A **non-empty** backup value means the last session ended while JellyJams was active (crash, or a quit before the guard could restore). Restore every recorded key exactly: re-set the old value, or **remove** the key if it was missing. Then clear the backup (empty string or removed key; both mean "no backup").
- After each successful recovery, print a console **message** that names what was restored and says it was left over from the previous session or an unclean exit. The message must mention "3D background" (viewport colors), "navigation style" and "shortcuts" respectively. Each `SwitchToWB` setting gets a similar message naming its module ("Assembly", "Part Design" or "TechDraw"), one per restored module.
- An **empty or missing** backup means nothing to do: no output at all. A clean startup must not print any message mentioning leftovers, recovery or an unclean exit.
- A recovery failure prints a console **warning** with details. Startup continues.
- An **unreadable or corrupt** backup (for example, invalid JSON) produces one warning and is then discarded (cleared). It must not block later sessions or stop a later apply from taking a fresh backup. A corrupt backup is never kept.
- When an area applies its setting and finds a non-empty backup already there (a leftover that was not recovered), it must **not overwrite** it, because it holds the true original. It just applies its values. The next restore then brings back the true original.

**Backup value formats.** These are persisted in users' `user.cfg` and are a compatibility contract: every JellyJams release must read these formats, so it can recover after a crash of an earlier release, and should keep writing them:

- `OriginalNavigationStyle`: a JSON object with `existed` (boolean) and `value` (the previous string, or null).
- `OriginalShortcuts`: a JSON object mapping each command id to a two-element array: [existed (boolean), previous key-sequence string or null].
- `OriginalViewColors`: a JSON object mapping each `Preferences/View` key name to a three-element array: [parameter type name such as `Bool` / `Unsigned`, existed (boolean), previous value or null].
- `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB`: a plain string each. `1` or `0` is the previous explicit value; `absent` means the key was not set before.

---

## 8. Command registration

- All JellyJams commands are registered with `FreeCADGui.addCommand(id, command)` during **Initialize** (first activation). Before the workbench has been activated once in a session, the `JellyJams_*` ids are therefore not in `FreeCADGui.listCommands()`, and that is acceptable.
- Registration happens **once per process**. A repeated call (Initialize run again) does nothing and prints nothing. It must never raise "command already exists" errors.
- Every id starts with `JellyJams_`. When registration finishes, a log-level console line says the commands are registered.
- Each command provides FreeCAD's standard resources: MenuText, ToolTip, and Pixmap (the absolute path to its original icon; Accel where defined). A command that only changes the camera also declares `CmdType` `Alter3DView`, so that FreeCAD keeps it available while a sketch or another task dialog is open; today these are the two orientation commands ([orientation.md](orientation.md) 2.1). Every other command declares no `CmdType`. The command implements both activation and the active/inactive check.
- **Icon lookup:** a JellyJams icon is looked up by base name in the add-on's icons folder, `.svg` first, then `.png`. If no file is found, the Pixmap is an empty string: the command shows without an icon, and nothing raises.
- Command ids registered by core. Behavior of all except Diagnostics is specified in the owning area:

| Command id | Owning area | MenuText |
|---|---|---|
| `JellyJams_Appearances` | appearances | Appearances |
| `JellyJams_Diagnostics` | core | Diagnostics |
| `JellyJams_Centerline` | sketching | Centerline |
| `JellyJams_MidpointLine` | sketching | Midpoint Line |
| `JellyJams_NewAssembly` | assembly | New Assembly |
| `JellyJams_RotateComponent` | assembly | Rotate Component |
| `JellyJams_MakeDrawing` | drawing | Make Drawing |
| `JellyJams_SheetProperties` | drawing | Sheet Properties |
| `JellyJams_InsertPicture` | drawing | Insert Picture |
| `JellyJams_ProjectedView` | drawing | Projected View |
| `JellyJams_ViewScale` | drawing | Scale |
| `JellyJams_SurfaceFinish` | drawing | Surface Finish |
| `JellyJams_WeldSymbol` | drawing | Weld Symbol |
| `JellyJams_LineFormat` | drawing | Line Format |
| `JellyJams_LineOnSheet`, `JellyJams_CornerRectangleOnSheet`, `JellyJams_CircleOnSheet`, `JellyJams_CenterpointArcOnSheet`, `JellyJams_PolygonOnSheet` | drawing | Line, Rectangle, Circle, Arc, Polygon (sketch shapes on the sheet) |
| `JellyJams_Note` | drawing | Text (shown as "Note" on the ribbon) |
| `JellyJams_SaveAsPDF` | drawing | Save as PDF (all sheets in one file) |
| `JellyJams_SaveAsDXF` | drawing | Export DXF (shown as "Save as DXF" on the ribbon) |
| `JellyJams_ViewOrientation` | orientation ([orientation.md](orientation.md)) | View Orientation (JellyJams menu and `Space`; no ribbon button) |
| `JellyJams_NormalTo` | orientation ([orientation.md](orientation.md)) | Normal To (Evaluate tab, JellyJams menu, Orientation panel and `Ctrl+8`) |

The ribbon may show a different SolidWorks label for a command than its MenuText ([ribbon-content](ribbon-content.md) 2.7).

Other areas may add `JellyJams_*` commands. They must be registered through the same once-per-process registration during Initialize, so that they exist before the ribbon is first built (A7).

---

## 9. Diagnostics command (`JellyJams_Diagnostics`)

**Resources**

- MenuText `Diagnostics`.
- ToolTip: explains that it shows FreeCAD and add-on environment details to copy into a bug report.
- Pixmap: a new original diagnostics icon. The test suite requires that this file exists.
- No keyboard shortcut.

**Availability.** Always active. It needs no open document.

**Where.** The "JellyJams" menu, while the workbench is active. Also runnable with `FreeCADGui.runCommand("JellyJams_Diagnostics")` once registered.

**On activation**

1. Collect the environment rows in this exact order (label → value):

   | Label | Value |
   |---|---|
   | Add-on version | the add-on's version string |
   | FreeCAD version | major.minor.patch from `FreeCAD.Version()`; each part is the leading integer of the element, or 0 if it is not numeric |
   | FreeCAD build | the 4th element of `FreeCAD.Version()` if present, else `-` |
   | Python | Python version (for example `3.11.x`) |
   | Platform | the OS/platform description string |
   | Qt binding | which binding is in use (FreeCAD's PySide shim on 1.1+) |
   | Qt version | Qt runtime version |
   | Add-on path | the absolute add-on folder |
   | Path is a symlink | `True` / `False` |
   | Icons found | `True` / `False` (the icons folder exists) |
   | User AppData | `FreeCAD.getUserAppDataDir()` |
   | Draft available | `yes`, or `NO - <import error text>` |
   | Sketcher available | `yes`, or `NO - <import error text>` |
   | Coin3D (pivy) | the Coin version if pivy reports one, `present` if it imports without a version, or `NO - <error>` |

   Rows may be added at the end, never in between. Any optional module that is missing is reported as a row and never makes the command fail.
2. Format a text block:
   - first line `JellyJams Diagnostics`,
   - second line 40 `=` characters,
   - then one line per row: the label left-aligned and padded to the longest label, then ` : `, then the value.
3. Print the block to the Report view as a console **message** (with a leading blank line), so the information is captured even if the dialog cannot be shown.
4. Show a **modal dialog** titled `JellyJams Diagnostics`, about 640 × 460 px, containing:
   - a read-only, plain-text field with a fixed-width font showing the block,
   - a button row with **Copy to clipboard** on the left, a stretch, and **Close** on the right.

   Clicking **Copy to clipboard** puts the whole block on the system clipboard and changes the button's label to `Copied`. **Close** closes the dialog.

---

## 10. Qt message filter

**Why.** When the user zooms far into a TechDraw sheet, text gets so large that the font rasterizer cannot render it. Qt then logs one warning per glyph, each starting with `render glyph failed`; the error code it carries is the font rasterizer's raster-overflow error. It happens in stock FreeCAD too, is harmless (no effect on display, print or PDF), but floods the Report view and notifications.

**User-visible behavior**

- **While JellyJams is the active workbench:** Qt messages whose text **starts with** `render glyph failed` are dropped. The first time one is dropped in a session, one **log-level** console line explains that these messages are being hidden while zoomed far in and that this is harmless. After that, they are dropped silently.
- **Every other Qt message, and every message while JellyJams is not active, is passed on unchanged**, as follows:
  - If a Python message handler was installed before JellyJams' (for example by another add-on), the message goes to that handler.
  - Otherwise JellyJams forwards it the way FreeCAD's own forwarder does: debug and info messages → console log; warnings → console warning; critical and fatal messages → console error. The text is `(<category>) <message>`, except that the category is left out when it is `default`, followed by a newline.
- **Outside the workbench the filter is fully transparent.** FreeCAD's C++ forwarder cannot be put back from Python once replaced, so the filter stays registered for the rest of the session and imitates it.

**Lifecycle**

- Installed during Activated (step A16) the first time it is allowed, then switched **on**. Deactivated (step D1) switches it **off**. Installing is once per process.
- It may only be switched on if it is installed.
- It uses Qt's `qInstallMessageHandler`, preferring PySide6's QtCore and falling back to FreeCAD's PySide shim. If neither offers the function, or installing raises, print a console **warning** saying the filter is not active and why. Nothing else is affected.
- **Self-test on install:** send one probe Qt warning whose text begins with `render glyph failed` and is marked as a JellyJams self-test. The probe must be suppressed even though the filter is not yet switched on. It must not count as the "first dropped" message, so the explanatory log line still appears on the first real case.
- After install, print a console **message** that the filter is active, followed by either "self-test ok" or a note that the probe did not arrive.
- The handler must never raise, must be cheap, and must not touch widgets: Qt may call it from any thread.

**Opt-out parameter**

- `User parameter:BaseApp/Preferences/Mod/JellyJams` → `SilenceGlyphWarnings` (Bool, default **true** when missing).
- Read whenever the filter would be installed (each activation until it has been installed once in the session).
- If false, the filter is **not registered at all**. FreeCAD's original forwarder stays untouched. A log-level console line says the filter was switched off by parameter. Switching it on is then also a no-op.
- JellyJams never writes this key. The user sets it, for example in Tools → Edit parameters.
- Switching it to false while the filter is already installed takes effect at the next FreeCAD start.

---

## 11. FreeCAD state read or changed by core (consolidated)

**Parameters**

| Group | Key | Type | Core's use |
|---|---|---|---|
| `User parameter:BaseApp/Preferences/Mod/JellyJams` | `SilenceGlyphWarnings` | Bool | read only (default true) |
| same | `OriginalViewColors` | String (JSON) | read at startup, restored and cleared |
| same | `OriginalNavigationStyle` | String (JSON) | read at startup, restored and cleared |
| same | `OriginalShortcuts` | String (JSON) | read at startup, restored and cleared |
| same | `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB` | String | read at startup, restored and cleared |
| `User parameter:BaseApp/Preferences/View` | `NavigationStyle` and the viewport color keys | String / Bool / Unsigned | written only through the owning areas (apply, restore, recover) |
| `User parameter:BaseApp/Preferences/Shortcut` | `<command id>` | String | through the shortcuts area |
| `User parameter:BaseApp/Preferences/Mod/Assembly`, `.../Mod/PartDesign`, `.../Mod/TechDraw/General` | `SwitchToWB` | Bool | through the assembly area (`switch_prefs`) |

**In-memory hooks installed through the step tables:** `Show.mTempoVis.TempoVis.activateWorkbench` (sketch-edit hook) and `FreeCADGui.activateWorkbench` (feature-edit guard), both wrapped only between A9 and D10 and restored to FreeCAD's identical functions ([sketching.md](sketching.md) 2.1 and 2.7). Neither is ever persisted, so the quit guard and crash recovery have nothing to do for them.

**FreeCAD / Qt APIs used by core:**

- `FreeCADGui.addWorkbench`, `FreeCADGui.listWorkbenches`, `FreeCADGui.addCommand`, `FreeCADGui.listCommands`, `FreeCADGui.runCommand`, `FreeCADGui.getMainWindow`, `FreeCADGui.activeWorkbench().name()`
- workbench `appendMenu`
- `FreeCAD.ParamGet` (Get/Set/Rem for String/Bool/Unsigned, plus `GetContents`, `GetBools`)
- `FreeCAD.Version`, `FreeCAD.getUserAppDataDir`
- `FreeCAD.Console.PrintMessage` / `PrintWarning` / `PrintError` / `PrintLog`
- `QtCore.qInstallMessageHandler`, `QtCore.qWarning`
- `QApplication.activeModalWidget`, `QApplication.clipboard`

**Qt objects:** the main-window Close-event filter (one per session); the Space filter of the orientation area on the main window and its docks (only between A6 and D12); ribbon dock `JellyJamsCommandManager` (shown and hidden through the ribbon area); the JellyJams block of the main-window stylesheet (through the theme area).

**No document objects or document properties** are created or read by core.

---

## 12. Persistence and restore rules (summary)

1. Nothing JellyJams applies may survive in `user.cfg` or `MainWindowState` after:
   - leaving the workbench,
   - quitting FreeCAD (with or without the "Save changes?" prompt), or
   - the next startup after a crash.
2. Restores are **exact**: previous values come back, keys that were missing are removed, other keys in the same groups are untouched, and the user's own overrides (for example a different navigation style, or their own shortcuts) come back unchanged.
3. Backups live only in `Mod/JellyJams`. They are present only while JellyJams' change is in effect, and are cleared on every successful restore.
4. A leftover backup is never overwritten by a new apply.
5. The main-window stylesheet after leaving is exactly what it was before entering.
6. `SilenceGlyphWarnings` is user-owned and never written.

---

## 13. Edge cases and failure handling

| Situation | Required behavior |
|---|---|
| Add-on present twice under `Mod/` | Second copy skipped with a warning naming its path; one selector entry; no exception. |
| Add-on folder cannot be determined | Workbench registered without an icon; the registration message says the path is unknown. |
| `InitGui.py` registration raises | Console error with traceback; startup recovery still runs; FreeCAD keeps starting. |
| Initialize raises | Console error with traceback; FreeCAD unaffected; Activated still runs its steps. |
| One Activated or Deactivated step raises | Console error naming that feature, with traceback; all other steps still run. |
| Activated twice / Deactivated twice / Deactivated first | No duplicates, no errors, no changed backups. |
| Initialize runs again | Command registration is a silent no-op. |
| FreeCAD older than 1.1 | Warning at Initialize; everything else still attempted. |
| Icon file missing | Command or workbench shows without an icon; no exception. |
| Draft / Sketcher / pivy missing | Diagnostics shows `NO - <reason>` rows; no failure. |
| Diagnostics dialog cannot be shown | The text is already in the Report view. |
| Crash leftovers present and JellyJams autoloads | Recovery runs first (from `InitGui.py`); Activated then takes fresh backups of the recovered (original) values. |
| Corrupt backup string | One warning; backup discarded; other recoveries still run. |
| Main window never shown within about 12 s of an autoload activation | Warning; layout not applied; other features stay active. |
| User leaves JellyJams before a deferred layout apply | Deferred apply cancelled. |
| Quit with unsaved documents → Cancel | Everything re-applied once the prompt is gone (theme block exactly once). |
| Quit with unsaved documents → Discard/Save | Nothing re-applied; saved configuration clean. |
| Quit while another workbench is active | Guard does nothing. |
| Qt message-handler API unavailable | Warning; Qt messages behave as in stock FreeCAD. |
| `SilenceGlyphWarnings` = false | Filter never registered; glyph messages visible everywhere. |
| Another add-on installed a Python Qt handler first | JellyJams chains to it for all non-dropped messages. |

---

## 14. Acceptance criteria

Unless a criterion says otherwise, start FreeCAD 1.1.x with a fresh profile (for example `FREECAD_USER_HOME` set to an empty folder, or `-u`/`-s` throwaway configs), with JellyJams installed under `Mod/JellyJams`, and the Report view showing messages, warnings, errors and log lines.

**Startup and registration**

1. At GUI startup, the Report view shows a JellyJams message that the workbench was registered, including the add-on folder path. No JellyJams warnings or errors appear.
2. `FreeCADGui.listWorkbenches()` contains the key `JellyJamsWorkbench`. The workbench selector shows **JellyJams** with the JellyJams icon, and the tooltip describes a SolidWorks-style UI for FreeCAD.
3. `FreeCADGui.listWorkbenches()["JellyJamsWorkbench"].GetClassName()` returns `Gui::PythonWorkbench`.
4. Running `FreeCADCmd` (console mode) with the add-on installed prints no JellyJams error or traceback.
5. With a second copy of the add-on under `Mod/` (for example a symlink with another folder name), startup shows exactly one JellyJams entry in the selector, one registration message, and one warning that the other path was skipped. No error appears.
6. On a clean startup (no backups present), no JellyJams message mentions leftovers, recovery, or an unclean exit.

**Initialize and commands**

7. On first activation, the Report view shows a line with the add-on version (`0.1.0`), the FreeCAD version and the Qt binding, then a message that the workbench is initialized. No JellyJams errors appear.
8. After first activation, `FreeCADGui.listCommands()` contains every id in the table in section 8, and every JellyJams-registered id starts with `JellyJams_`.
9. Running Initialize a second time (`FreeCADGui.listWorkbenches()["JellyJamsWorkbench"].Initialize()`) prints no error, and the command list is unchanged.
10. While JellyJams is active, the menu bar has a **JellyJams** menu containing **View Orientation**, **Normal To** and **Diagnostics**, in that order. After switching to Part Design, that menu is gone. JellyJams adds no QToolBar of its own: no visible toolbar objectName starts with `JellyJams`.

**Diagnostics**

11. JellyJams → Diagnostics opens a modal dialog titled **JellyJams Diagnostics** with a read-only, fixed-width text whose first line is `JellyJams Diagnostics`, followed by a line of 40 `=`. It then lists, in this order: Add-on version, FreeCAD version, FreeCAD build, Python, Platform, Qt binding, Qt version, Add-on path, Path is a symlink, Icons found, User AppData, Draft available, Sketcher available, Coin3D (pivy). The colons line up.
12. Add-on version in the dialog equals `<version>` in `package.xml`. FreeCAD version matches Help → About (major.minor.patch). User AppData equals `FreeCAD.getUserAppDataDir()`.
13. **Copy to clipboard** puts exactly the displayed text on the clipboard and the button then reads **Copied**. **Close** closes the dialog.
14. The same text block also appears in the Report view each time the command runs.
15. `FreeCADGui.runCommand("JellyJams_Diagnostics")` works with no document open. The command is never greyed out.

**Enter / leave lifecycle**

16. Before activating, note the visible toolbars in Part Design, `Preferences/View` `NavigationStyle` (or that it is missing), `Preferences/Shortcut` contents, and `SwitchToWB` in `Preferences/Mod/Assembly`, `Preferences/Mod/PartDesign` and `Preferences/Mod/TechDraw/General` (or that it is missing). After activating JellyJams:
    - the main-window stylesheet contains `/* @jellyjams-stylesheet-open */` exactly once,
    - `NavigationStyle` = `Gui::SolidWorksNavigationStyle`,
    - `Preferences/Shortcut` `Std_ViewFitAll` = `F`,
    - the dock `JellyJamsCommandManager` exists and is visible,
    - all three `SwitchToWB` are false,
    - `Mod/JellyJams` contains non-empty `OriginalNavigationStyle`, `OriginalShortcuts`, `OriginalViewColors`, `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB` and `OriginalTechDrawSwitchToWB`.
17. After switching to Part Design and waiting about 1 s:
    - no `@jellyjams-stylesheet-open` remains, and the stylesheet equals the pre-activation value,
    - `NavigationStyle`, the shortcut overrides and the three `SwitchToWB` equal their noted values exactly; a key that was missing before is missing again,
    - `JellyJamsCommandManager` is hidden,
    - every toolbar that was visible before is visible again,
    - all six backup keys are empty or missing.
18. Repeat 16–17 with a user-set `NavigationStyle` of `Gui::TouchpadNavigationStyle` and a user shortcut override (for example `Std_ViewTop` = `T`). After leaving, both values are back unchanged.
19. Calling Activated twice in a row (`Gui.activateWorkbench("JellyJamsWorkbench")` while active, or from the console) leaves exactly one theme marker block, the same number of ribbon buttons, and unchanged backup values.
20. Fault isolation (developer test): make any single activation step raise, for example by temporarily breaking one feature from the Python console. Activating then shows one console error naming that feature, and all other features (theme, navigation, ribbon...) are still applied. The same holds for leaving.
21. Starting to place a Note (`JellyJams_Note`) on a drawing sheet and then switching to Part Design ends the placement mode: clicking the sheet afterwards does not place text.

**Quit guard**

22. With JellyJams active and no unsaved documents, quit FreeCAD. In the saved `user.cfg`:
    - `Preferences/View/NavigationStyle` is not `Gui::SolidWorksNavigationStyle` (it equals the pre-JellyJams value, or is missing),
    - `Preferences/Shortcut` holds none of JellyJams' overrides (no `Std_ViewFitAll`, `Std_Refresh`, `Std_ViewIsometric`, `JellyJams_NormalTo`, `Std_AlignToSelection` or `JellyJams_ViewOrientation` entries unless the user had them, and no `Std_ViewBoxZoom` or `Std_ToggleVisibility` unbinding),
    - `Mod/JellyJams` has no non-empty `OriginalNavigationStyle`, `OriginalShortcuts`, `OriginalViewColors`, `OriginalSwitchToWB`, `OriginalPartDesignSwitchToWB` or `OriginalTechDrawSwitchToWB`,
    - `Mod/Assembly/SwitchToWB`, `Mod/PartDesign/SwitchToWB` and `Mod/TechDraw/General/SwitchToWB` equal their pre-JellyJams states.
23. With JellyJams active and an unsaved document, quit, and while the "Save changes?" prompt is open (wait at least 1.5 s), check that:
    - the theme marker is absent, and `JellyJamsCommandManager` is not visible,
    - `NavigationStyle` and `Std_ViewFitAll` are back to their pre-JellyJams values,
    - nothing has been re-applied during the wait.
24. In 23, pressing **Cancel** brings back within about 1–2 s:
    - the theme (marker exactly once),
    - the visible ribbon,
    - `NavigationStyle` = `Gui::SolidWorksNavigationStyle`,
    - `Std_ViewFitAll` = `F`.

    Then switching to Part Design restores all stock toolbars.
25. In 23, pressing **Discard** quits. The saved `user.cfg` meets criterion 22, and on relaunch Part Design shows the user's stock toolbars and `JellyJamsCommandManager` is not visible.

**Autoload**

26. Set JellyJams as the autoload workbench and restart. Once the window is shown:
    - JellyJams is the active workbench,
    - the ribbon is visible,
    - the only visible FreeCAD toolbars are File, Edit and Workbench.

    Switching to Part Design then brings back the user's full toolbar set (more than three toolbars) and removes the theme.

**Crash recovery**

27. Simulate a crash: activate JellyJams, make FreeCAD save parameters (for example with `FreeCAD.saveParameter()`), then kill the FreeCAD process. Restart.
    - Before the user touches anything, the Report view shows recovery messages mentioning "3D background", "navigation style" and "shortcuts".
    - `NavigationStyle`, the shortcut overrides, the viewport color keys and the three `SwitchToWB` equal their pre-JellyJams states (keys that were missing are missing).
    - All six backup keys are empty or missing.
28. Hand-seeded leftovers in the backup formats of section 7 are recovered exactly at the next startup. Seed:
    - `OriginalNavigationStyle` = `{"existed": false, "value": null}` with `NavigationStyle` set to the SolidWorks style,
    - `OriginalShortcuts` = `{"Std_ViewTop": [false, null], "Std_ViewFront": [true, "1"]}` with `Std_ViewTop` = `Ctrl+5` and `Std_ViewFront` = `Ctrl+1`,
    - `OriginalViewColors` = `{"Gradient": ["Bool", false, null]}` with `Gradient` = true.

    After restart: `NavigationStyle` and `Gradient` are missing, `Std_ViewTop` is missing, `Std_ViewFront` = `1`, and the backups are cleared.
29. Seed `OriginalNavigationStyle` with invalid JSON and restart. Exactly one JellyJams warning appears, the backup is cleared, the other recoveries still happen, and on the next restart there is no warning.
30. Seed a leftover `OriginalNavigationStyle` of `{"existed": true, "value": "Gui::GestureNavigationStyle"}` without restarting, then activate and leave JellyJams. `NavigationStyle` ends as `Gui::GestureNavigationStyle`: the leftover backup was not overwritten on apply.

**Qt message filter**

31. On first activation, the Report view shows a JellyJams message that the Qt message filter is active, ending in "self-test ok". No self-test warning text is visible in the Report view.
32. While JellyJams is active, running `from PySide6 import QtCore; QtCore.qWarning("render glyph failed err=40 manual check")` in the Python console shows **no** warning. One log-level JellyJams line explains the hiding on the first occurrence only. `QtCore.qWarning("an unrelated warning")` **does** appear as a warning.
33. After switching to Part Design, the same `render glyph failed` call **does** appear as a warning in the Report view.
34. A Qt warning with a non-default category is shown as `(<category>) <text>`. One with the default category is shown as plain text.
35. Set `Mod/JellyJams/SilenceGlyphWarnings` to false (Tools → Edit parameters) and restart. On activation there is a log line that the filter is switched off by parameter, no message that the filter is in place, and the `render glyph failed` warning from criterion 32 **is** visible even inside JellyJams. Removing the key or setting it true and restarting turns the filter back on.

**Metadata and release consistency**

36. `package.xml` parses, uses `format="1"` and the Package_Metadata namespace, and has:
    - `name` JellyJams,
    - `version` equal to the Diagnostics "Add-on version",
    - a `date` in `YYYY-MM-DD`,
    - `freecadmin` `1.1.0`,
    - a repository URL `https://github.com/jus-kim/JellyJams` with `branch="main"`,
    - a maintainer email `hi@jus.kim`,
    - `content/workbench/classname` `JellyJamsWorkbench`, `subdirectory` `./`, `name` `JellyJams`,
    - every `icon` and `license file` path existing in the add-on.
37. `CHANGELOG.md` contains `## <version> — <date>` matching `package.xml`. `README.md` and the `package.xml` description both carry the "not affiliated with or endorsed by Dassault Systèmes" note.
38. No file name, icon file name, Qt objectName, command id, parameter key or workbench key of the add-on contains "solidworks" in any case. A search over the add-on's file names, its registered `JellyJams_*` ids and its `JellyJams*` objectNames finds none.
39. Removing one command icon file and restarting still registers that command, which shows without an icon. No exception appears in the Report view.
40. In normal and ultrawide native 3D views, equal 100-pixel horizontal and vertical
    middle drags turn the camera by angles within 8% of each other in all five
    native orbit modes. Ctrl-pan, Shift-zoom and an unmoved middle click produce
    the same camera state as the native preset without correction. Ctrl/orbit
    transitions while held MUST NOT jump the camera. Removal mid-drag MUST NOT
    move the camera and MUST release native orbiting. After leaving, the native
    unbalanced response and original navigation preferences return. Quit/cancel
    and autoload checks MUST verify the runtime hook is removed/reinstalled too.
41. With JellyJams active, open a native Pad edit dialog, focus its OK button,
    accept the feature, then orbit the extruded body. Repeat 20 times without a
    native crash, a stuck edit dialog or invalid geometry. A headless test MUST
    verify focus discovery is deferred/coalesced and cancelled on stop. This
    covers the focus-change signal emitted inside native task-widget destruction.
