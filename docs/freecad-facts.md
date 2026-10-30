# FreeCAD facts JellyJams relies on

JellyJams changes FreeCAD's user interface from the outside, so it depends on how FreeCAD
behaves, not only on documented APIs. This page lists the FreeCAD behaviors the code relies
on, where it relies on them, and how sure we are.

**Baseline:** FreeCAD 1.1.4 on Windows (`C:\Program Files\FreeCAD 1.1`), Qt 6.8.3, PySide6
6.8.3, Python 3.11. Minimum supported version: FreeCAD 1.1 (`MIN_FREECAD_VERSION` in
[`jellyjams/__init__.py`](../jellyjams/__init__.py)).

> **Re-verify these facts for every new FreeCAD release** (including patch releases) before
> declaring it supported. Use the [checklist](#re-verification-checklist) at the end and update
> the "Evidence" column and the baseline above.

Evidence column:

| Value | Meaning |
|---|---|
| **Verified 1.1.4** | established on the live FreeCAD 1.1.4 install by instrumented tests or inspection |
| **GUI test** `name` | additionally exercised by a check in the real-FreeCAD GUI scripts in [`tests/`](../tests), which passed on 1.1.4 |
| **Headless test** | checked by [`tests/test_headless.py`](../tests/test_headless.py) against FreeCAD's installed files |
| **Not verified** | the code relies on it (usually with a fallback), but no test or recorded check confirms it |

Related: [architecture.md](architecture.md) (where each behavior is used),
[decisions.md](decisions.md) (why).

---

## Platform and runtime

| Fact | Relied on by | Evidence |
|---|---|---|
| Inside FreeCAD the canonical Qt import is `from PySide import QtCore, QtGui, QtWidgets`, FreeCAD's shim that re-exports PySide6. Widgets live in `QtWidgets`. Qt 6 scoped enums are required (`QtCore.Qt.DockWidgetArea.TopDockWidgetArea`, `QtCore.QEvent.Type.Close`) | every Qt module | Verified 1.1.4 |
| `shiboken6.isValid(obj)` tells whether the C++ object behind a Qt wrapper is still alive | `fcgui.is_alive` | Verified 1.1.4 |
| The user data folder is versioned: `%APPDATA%\FreeCAD\v1-1\`; add-ons live in `...\v1-1\Mod\<Addon>\`. `FREECAD_USER_HOME=<dir>` redirects the whole profile. `FreeCAD.getUserAppDataDir()` returns the user data folder | `paths.user_cache_dir`, developer install in the README | Verified 1.1.4 |
| `FreeCADCmd.exe script.py` runs headless (no `FreeCADGui`). `FreeCAD.exe -u <user.cfg> -s <system.cfg> script.py` runs a script inside the GUI with a throwaway configuration. Script stdout is unreliable; write results to files | GUI test scripts | Verified 1.1.4 |
| FreeCAD's bundled interpreter `bin/python.exe` has PySide6 6.8.3 and shiboken6 available, so the headless harness can use real offscreen Qt | `tests/headless_stubs.py` | Verified 1.1.4 (headless suite runs there) |

## Add-on loading

| Fact | Relied on by | Evidence |
|---|---|---|
| Classic Mod layout: `Init.py` (headless-safe, may be empty) and `InitGui.py` at the add-on root, a Python package beside them | [`Init.py`](../Init.py), [`InitGui.py`](../InitGui.py) | Verified 1.1.4; GUI test `workbench_registered` |
| `InitGui.py` is executed with `exec()`: there is **no `__file__`**, and names defined or imported at its top level are **not visible** inside class bodies or methods called later. Class bodies may hold only literals; methods import what they need | `InitGui.py` | Verified 1.1.4 |
| `inspect.currentframe().f_code.co_filename` inside `InitGui.py` names the real file | `InitGui.py` (`_JELLYJAMS_DIR`) | Not verified; falls back to `paths.addon_dir()` |
| Registering twice must be guarded with `FreeCADGui.listWorkbenches()` (for example a second copy of the add-on on the path) | `InitGui.py` | Verified 1.1.4; headless InitGui tests |
| `package.xml`: `<package format="1" xmlns="https://wiki.freecad.org/Package_Metadata">` with name, description, version, date, maintainer (email), license (file), `url type="repository" branch="main"`, icon, `freecadmin`, `content/workbench` (classname, subdirectory `./`, icon) | [`package.xml`](../package.xml) | Verified 1.1.4 |
| The Addon Manager's custom-repository install defaults the branch to `master` unless a branch is given | README install steps | Verified 1.1.4 |

## Workbench and commands

| Fact | Relied on by | Evidence |
|---|---|---|
| A workbench subclasses `FreeCADGui.Workbench` with `MenuText`, `ToolTip`, `Icon` (a path, assigned after the class definition), `Initialize()` (once), `Activated()`, `Deactivated()`, `GetClassName()` returning `"Gui::PythonWorkbench"`; registered with `FreeCADGui.addWorkbench(instance)` | `InitGui.py`, [`lifecycle.py`](../jellyjams/lifecycle.py) | Verified 1.1.4 |
| A command is an object with `GetResources()` (`MenuText`, `ToolTip`, `Pixmap`, optional `Accel` and `CmdType`), `Activated()` and `IsActive()`; registered with `FreeCADGui.addCommand(id, obj)`. Group commands pass an index to `Activated` | [`commands.py`](../jellyjams/commands.py) | Verified 1.1.4 |
| A Python command that returns no `CmdType` counts as changing the document, the 3D view and the selection (`AlterDoc`, `Alter3DView`, `AlterSelection`). FreeCAD disables a command that changes the document while the open task dialog's `isAllowedAlterDocument()` is False, which is the default of every task dialog; the sketch editor's dialog (`TaskDlgEditSketch`) returns False explicitly. `isAllowedAlterView()` and `isAllowedAlterSelection()` are True by default, so a command with `CmdType` `Alter3DView` stays enabled while a sketch or another default task dialog is open | `BaseCommand.cmd_type`; both orientation commands declare `Alter3DView` | Verified 1.1.4 (instrumented probe with a default task dialog: `isAllowedAlterDocument()` False, `isAllowedAlterView()` True, a Python command without `CmdType` disabled, one with `Alter3DView` enabled; `TaskDlgEditSketch.h` in FreeCAD's source); GUI check `sketch_commands_enabled` (passed, 2026-10-28) |
| `FreeCADGui.runCommand(id[, index])` runs a command (or sub-entry `index` of a group command) | `fcgui.run_command`, `ribbon.run_entry` | Verified 1.1.4 |
| `Gui::Command::assureWorkbench(name)` and `Std_Workbench` (the workbench selector and View > Workbench) both switch workbenches by running the command string `Gui.activateWorkbench('<name>')` through FreeCAD's interpreter; the Python frame that makes that call has the code object file name `<string>`. Python code (macros, scripts, the console) calls `FreeCADGui.activateWorkbench` from its own frames | [`edit_guard.py`](../jellyjams/edit_guard.py) (`COMMAND_STRING_FILE`) | Verified 1.1.4; GUI tests `d_edit_feature_stays_in_jellyjams`, `d_user_switch_to_part_design_works` |
| `FreeCADGui.listCommands()` lists command ids. `FreeCADGui.Command.get(id)` returns an object with `getAction()` (list of QActions), `getShortcut()`, `getInfo()` (dict with `menuText`, `toolTip`, `pixmap`, ...) and `isActive()` (FreeCAD's enabled state of the command now). `FreeCADGui.Command.update()` makes FreeCAD re-evaluate the enabled state of every command at once; there is no `FreeCADGui.updateCommands` | ribbon build and refresh, `shortcuts.py`, `icons.py`, the Orientation panel's enabled buttons (`isActive()`); `Command.update()` in `tests/gui_orientation.py` | Verified 1.1.4 (`Command.update` and the missing `updateCommands` by probe) |
| A command's QActions exist only once FreeCAD has placed the command in a toolbar or menu; before that `getAction()` may be empty | `icons.command_action` (falls back to `fc_icon` / pixmap lookups) | Not verified by a test |
| A command gets a working keyboard shortcut only when it is in a menu or toolbar: FreeCAD binds the key through the command's `QAction`, which it creates only there. Running a command with `FreeCADGui.runCommand` (as the JellyJams ribbon does) creates none, so a ribbon button alone is not enough | `lifecycle._add_menu_once` (`JellyJams_ViewOrientation` and `JellyJams_NormalTo` in the JellyJams menu, so that `Space` and `Ctrl+8` work) | Verified 1.1.4 (recorded in the code); GUI test `space_opens_panel` passes with the menu entry. That Space fails without it is not covered by a test |
| FreeCAD creates command `QAction`s with key repeat on (`autoRepeat()` True), so holding a command's shortcut runs it again and again | `orientation._stop_auto_repeat` (View Orientation would open and close the panel while Space is held) | Verified 1.1.4 (probe); GUI check `orientation_no_auto_repeat` (passed, 2026-10-28) |
| `Std_AlignToSelection` ("Align to Selection") turns the view to look straight at the selection, SolidWorks' Normal To. It needs **exactly one** pick: with nothing selected, or with two or more faces or edges, it does nothing and says nothing. With one pick it decides itself what it can align to, and that is more than flat faces and straight edges: a **curved face** (the side of a cylinder: it looks along the axis), a **straight B-spline edge** (the side edge of a tapered loft), a **planar curve**, a **whole origin plane or axis**, a **whole datum** plane or line, and a **whole object that is a single face or edge**, also when reached through a link. A whole sketch selected in the tree usually does nothing. It has no rule for a sketch in edit. It has no default key, and no FreeCAD 1.1 command owns `Ctrl+8` by default | `orientation.normal_to_target` (any single sub-element, whole `App::Plane` / `App::Line` / `Part::Datum` objects and single-face or single-edge objects are handed to it; whole sketches are turned by JellyJams; two picks and nothing selected get the hint) | Verified 1.1.4: command info and default keys by probe; no camera change with an empty selection, also in sketch edit; a straight B-spline edge of a tapered loft turns the view (probe). GUI checks `normal_to_face_aligns`, `normal_to_nothing_selected_keeps_view`, `normal_to_two_faces_keeps_view`, `align_to_selection_untouched`, and `normal_to_curved_face_turns_view`, `normal_to_datum_line_turns_view`, `normal_to_origin_axis_turns_view` (each compared with FreeCAD's own `Std_AlignToSelection` from the same camera) (passed, 2026-10-28) |
| A document object's `getGlobalPlacement()` is its placement in the document's global coordinates, through every containing body or part, but it does not follow links: a sketch shown through an `App::Link` (or an assembly component) sits where the link puts it (a link's placement replaces the linked body's). `FreeCAD.GeoFeature.getGlobalPlacementOf(target, root, subname)` multiplies the placements along a selection path from `root`, links included; `root` and the path are what the unresolved selection gives (`Selection.getSelectionEx("", 0)`: the top-level object and the sub-name below it, for example `Link` and `Sketch.`). With an empty path it returns the root's own placement, so for a top-level sketch (root = target) its own placement. The `Rotation` of a sketch's placement turns the global Z axis onto the sketch normal. A 3D view's `setCameraOrientation(q)` (q = `Rotation.Q`, a quaternion) turns the camera so that it looks down that rotation's Z axis | `orientation._sketch_rotation`, `orientation._look_at_sketch` (Normal To on a whole sketch) | Verified 1.1.4 by probe: a sketch reached through an `App::Link` turned 90° about X, over a body turned 30° about Z, gives Q (0.707, 0, 0, 0.707) along the path, while `getGlobalPlacement()` gives the body's 30° about Z; `getGlobalPlacementOf(sketch, sketch, "")` and `getGlobalPlacementOf(sketch, body, "Sketch001.")` equal the sketch's own global placement, `getGlobalPlacementOf(sketch, body, "")` the body's (FreeCADCmd probe). GUI checks `normal_to_whole_sketch_aligns`, `normal_to_linked_sketch_follows_link` (passed, 2026-10-28) |
| `Sketcher_ViewSketch` ("Align View to Sketch") turns the camera perpendicular to the plane of the sketch in edit | `orientation.normal_to_target` (Normal To in a sketch with nothing, or only the sketch's own elements, selected) | Command info verified 1.1.4; GUI checks `sketch_normal_to_aligns_to_sketch`, `sketch_ctrl8_aligns_to_sketch` (passed, 2026-10-28) |
| `Std_ViewSaveCamera` and `Std_ViewRestoreCamera` have no icon in FreeCAD 1.1 | `orientation.FALLBACK_ICONS` (original `view_save.svg` / `view_restore.svg`, used only when FreeCAD gives no icon) | Verified 1.1.4 (recorded in the code); not checked by a test |
| `Std_ViewTop` turns the active 3D view to the view direction (0, 0, −1); `Std_ViewFront` to a direction in the XY plane | Orientation panel | Verified 1.1.4; GUI tests `top_view_applied`, `front_view_applied` |
| FreeCAD 1.1 has no command that splits one 3D view into several viewports (SolidWorks' Two View / Four View layouts). `Std_ViewCreate` opens another 3D view window of the document and `Std_TileWindows` tiles the windows | [orientation.md](specs/orientation.md) 4 (not offered) | Verified 1.1.4 (no such id among the `Std_*` command names in `bin/FreeCADGui.dll`) |
| FreeCAD's own icons are available as Qt resources under `:/icons/` and through `FreeCADGui.getIcon(name)`. The code tries `getIcon` last because it may return a placeholder for unknown names | [`icons.py`](../jellyjams/icons.py) | Verified 1.1.4 (availability); icon rendering is checked only visually in the `gui_tabs.py` screenshots |
| Assembly commands are Python modules (`CommandCreateAssembly`, `CommandInsertLink`, `CommandInsertNewPart`, `CommandCreateJoint`, `CommandSolveAssembly`, `CommandCreateView`, `CommandCreateSimulation`, `CommandCreateBom`, listed in `Mod/Assembly/InitGui.py`) that FreeCAD registers only when the Assembly workbench initializes | `fcgui.preload_command_modules`, `constants.ASSEMBLY_COMMAND_MODULES` | Verified 1.1.4 |
| Importing `PartGui`, `SketcherGui`, `PartDesignGui`, `TechDrawGui` and the Assembly command modules registers their commands even if those workbenches were never opened | `fcgui.preload_command_modules`, `constants.GUI_COMMAND_MODULES` | GUI test `gui_tabs.py` (every tab renders its full button count) |
| `Std_DrawStyle` sub-entries in 1.1: 0 As is, 1 Points, 2 Wireframe, 3 Hidden line, 4 No shading, 5 Shaded, 6 Flat lines | [`ribbon_layout.py`](../jellyjams/ribbon_layout.py) (Display style group) | Not verified by a test |
| FreeCAD 1.x provides `Sketcher_Projection`; older builds only know `Sketcher_External` | `ribbon_layout.py` (`fallbacks`) | Not verified; the fallback covers both |

## Main window, docks and toolbars

| Fact | Relied on by | Evidence |
|---|---|---|
| `FreeCADGui.getMainWindow()` returns the QMainWindow. Dock objectNames: tree `Model` (older: `Combo View` / `Tree view`), task panel `Tasks`, report `Report view` | `constants.*_CANDIDATES`, `fcgui.find_dock`, [`layout.py`](../jellyjams/layout.py) | Verified 1.1.4 |
| The task panel content is a `Gui::TaskView::TaskPanel` widget inside a `QScrollArea` of the Tasks dock | `fcgui.task_panel`, `panel_host.py` | Not verified by a GUI test |
| FreeCAD hides and shows the QToolBars it manages on every workbench switch, but leaves foreign QDockWidgets alone | ribbon host (`JellyJamsCommandManager` dock) | Verified 1.1.4; GUI tests `ribbon_visible`, `ribbon_hidden` |
| FreeCAD's asynchronous window-state restore can re-show a dock; guard with `visibilityChanged` | `ribbon._on_visibility_changed` | Verified 1.1.4 |
| **Ordering on a workbench switch:** FreeCAD shows the next workbench's toolbars first, then calls the old workbench's `Deactivated()` about 200 ms later. A blanket `restoreState()` in `Deactivated()` would hide the new workbench's toolbars | `layout.revert` (restores only what JellyJams hid) | Verified 1.1.4; GUI tests `stock_toolbars_back`, `toolbars_back_after_leave` |
| FreeCAD re-docks dock widgets shortly (about 100 ms) after changes, so dock placement needs delayed second passes | `layout.REDOCK_DELAYS_MS`, `layout.SECOND_PASS_MS` | Verified 1.1.4 |
| `QWidget.grab()` cannot capture the 3D (OpenGL) view; use `FreeCADGui.ActiveDocument.ActiveView.saveImage(path, w, h, "Current")` | GUI test screenshots | Verified 1.1.4 |
| The active TechDraw page window's widget class is `TechDrawGui::MDIViewPage`; the 3D view's is `Gui::View3DInventor`. A split 3D view's widget reports `Gui::AbstractSplitView`: `SplitView3DInventor` declares no `Q_OBJECT`, so Qt names its base class. In every 3D view the OpenGL drawing area (`QOpenGLWidget`) is a child of a `Gui::View3DInventorViewer`: inside a `QStackedWidget` of the `Gui::View3DInventor`, or inside a `QSplitter` of the `Gui::AbstractSplitView` | `fcgui.is_sheet_window`, `assembly_commands.py`, `orientation.SPACE_FOR_PANEL_CLASSES` (with the pointer over one of these, Space opens the Orientation panel) | Verified 1.1.4 (page window; the parent chains of the drawing area in a normal and in a split 3D view by probe: `QOpenGLWidget`, `Gui::View3DInventorViewer`, `QStackedWidget`, `Gui::View3DInventor`, `QMdiSubWindow` and `QOpenGLWidget`, `Gui::View3DInventorViewer`, `QSplitter`, `Gui::AbstractSplitView`, `QMdiSubWindow`); the GUI checks `space_opens_panel`, `pad_pointer_over_view_space_opens_panel` and `undocked_space_opens_panel` depend on them (passed, 2026-10-28) |
| `FreeCADGui.getMainWindow()` (a PySide6 `QMainWindow` in FreeCAD 1.1) has `getActiveWindow()`, FreeCAD's `MainWindow::activeWindow`: the MDI view in front, the one FreeCAD's own view commands act on. It is a 3D view (`View3DInventorPy`, it has `getCameraNode`) for a docked, undocked or fullscreen 3D view, the split view's object for a split view, another view object (`MDIViewPy` and others) for the Start page, a TechDraw page or a spreadsheet, and None without any. An undocked or fullscreen 3D view leaves the MDI area (it becomes a top-level window), so the MDI area's active window no longer tells; `getActiveWindow()` still returns the 3D view | `orientation._active_view`, `orientation.view3d_active` (both orientation commands are active only while it is a 3D view; Normal To turns that view) | Verified 1.1.4 offscreen (`getMainWindow()` is a PySide6 `QMainWindow` whose `getActiveWindow()` returned a `View3DInventorPy`); GUI checks `undocked_commands_enabled`, `start_page_commands_disabled` (passed, 2026-10-28) |
| `FreeCADGui.activeView()` is the active document's active view, not the window in front: with the Start page or a TechDraw page in front it keeps returning the document's last 3D view (`View3DInventorPy`), and it returns that 3D view for an undocked, fullscreen or split view too | `orientation._active_view` uses it only when the main window has no `getActiveWindow` | Verified 1.1.4 for a split view by probe (`activeView()` a `View3DInventorPy` while the MDI area's current window is the split view); GUI check `start_page_commands_disabled` records the type with the Start page in front (passed, 2026-10-28) |
| `Std_ViewDockUndockFullscreen` acts on the main window's active MDI window (index 0 docks it, 1 undocks it into a top-level window, 2 makes it fullscreen) and does nothing while another window is active. After undocking, the MDI area's current window is the next one, for example the Start page | `tests/gui_orientation.py` (undock part); `orientation._active_view` follows the undocked view through `getActiveWindow()` | Recorded in `tests/gui_orientation.py` (`view_undocked`, `view_docked_again`; passed, 2026-10-28) |
| FreeCAD's model tree is an item view of Qt class `Gui::TreeWidget`; the property editor is another item view (`Gui::PropertyEditor::PropertyEditor`) whose items are neither checkable nor edited by typing | `orientation.MODEL_TREE_CLASS`, `orientation.SPACE_FOR_PANEL_CLASSES` (Space with the pointer over the tree opens the Orientation panel; a focused property editor does not keep Space) | Verified 1.1.4 (class census of the main window's item views by probe); the property editor's edit triggers are not verified by a recorded check |
| With the focus in another top-level window (a tool window such as the Orientation panel), the main window's `QMdiArea.activeSubWindow()` can be None while `currentSubWindow()` still names the window the user works in | `fcgui.active_mdi_widget` (the active sheet window of the drawing tools and the ribbon's context tabs; the orientation commands use `getActiveWindow` instead) | Not verified by a test (recorded in the code) |
| Controls in toolbars and in the status bar keep the keyboard focus after a click: the workbench selector (`Gui::WorkbenchComboBox`, a combo box in the Workbench toolbar) and the status bar's buttons (navigation style, units). The next plain Space would then go to that control | `orientation.keeps_space` (controls inside a `QToolBar`, the `QStatusBar` or the ribbon dock never keep Space) | GUI checks `workbench_combo_space_opens_panel`, `workbench_combo_space_no_popup` (passed, 2026-10-28) |
| A floating `QDockWidget` is a window of its own: Qt passes a key event, the `ShortcutOverride` included, up the parents only to the widget's window, so the overrides of a floating dock's widgets never reach the main window or its event filters | `orientation.install` (the Space filter sits on the main window and on every dock), `orientation._focus_changed` (docks made later get it when one of their widgets takes the focus, through `QApplication.focusChanged`) | Headless tests `test_floating_dock_needs_its_own_filter`, `test_a_dock_made_after_activation_gets_the_filter_when_it_takes_focus` (Qt 6.8.3); GUI checks `floating_task_dock_space_toggles_check_box`, `floating_task_dock_space_keeps_panel_closed`, `late_dock_gets_space_filter`, `late_dock_space_toggles_check_box` (passed, 2026-10-28) |

## Quit, autoload and modal dialogs

| Fact | Relied on by | Evidence |
|---|---|---|
| On quit FreeCAD **never calls `Deactivated()`**. It persists the window layout (`MainWindowState`) and all parameters on exit | [`quit_guard.py`](../jellyjams/quit_guard.py) | Verified 1.1.4; GUI test `gui_lifecycle.py` mode `discard` + `check_saved_cfg.py` |
| A Close-event filter on the main window runs **before** FreeCAD's own `closeEvent` | `quit_guard.install` | Verified 1.1.4; GUI tests `nav_restored_inside_prompt`, `shortcut_restored_inside_prompt` |
| With unsaved documents, FreeCAD's "Save changes?" QMessageBox runs a nested event loop inside `closeEvent`: QTimers keep firing, `QApplication.activeModalWidget()` is non-null while it is open, and Cancel aborts the close | `quit_guard._check` | Verified 1.1.4; GUI tests `prompt_is_open`, `not_reentered_inside_prompt`, `reapplied_after_cancel` |
| When the workbench is autoloaded at startup, `Activated()` runs **before** the main window is shown and before FreeCAD restores the saved window state | `layout.apply` deferral, `ribbon.show_if_requested` | Verified 1.1.4; GUI tests `layout_active_after_show`, `ribbon_visible_after_show` |

## Parameters

| Fact | Relied on by | Evidence |
|---|---|---|
| `FreeCAD.ParamGet("User parameter:BaseApp/Preferences/...")` returns a group with `Get/Set/Rem` + `Bool/Int/Unsigned/Float/String` | [`params.py`](../jellyjams/params.py), `navigation.py`, `shortcuts.py` | Verified 1.1.4 |
| `GetContents()` returns `(type, name, value)` tuples with type names `"Boolean"`, `"Integer"`, `"Unsigned Long"`, `"Float"`, `"String"`; `GetBools()` / `GetStrings()` / ... return name lists | `params.has_key`, `params.CONTENTS_TYPE_NAMES` | Verified 1.1.4 |
| Parameters are persisted in `user.cfg` on exit, including any value an add-on left behind | exact-restore discipline, crash backups | Verified 1.1.4; `check_saved_cfg.py` |

### Navigation

FreeCAD 1.1.4 normalizes mouse X by viewport width and Y by viewport height before
passing movement to its native sphere projector. On an ultrawide 3571×902 viewport,
a 100-pixel native Rounded Arcball drag measured 5.82° horizontally and 24.06°
vertically. Other orbit modes had the same axis imbalance. `orbit.py` balances
the input deltas; it does not replace the native rotation algorithm or write
orbit, sensitivity or pivot preferences. Verified by `tests/gui_orbit.py`.
Source for the installed revision:
[NavigationStyle::normalizePixelPos](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Gui/Navigation/NavigationStyle.cpp#L1370).

| Fact | Relied on by | Evidence |
|---|---|---|
| `Preferences/View` String `NavigationStyle`; the SolidWorks style is `Gui::SolidWorksNavigationStyle`; FreeCAD's default (key absent) is `Gui::CADNavigationStyle`. A change applies live to open 3D views | [`navigation.py`](../jellyjams/navigation.py) | Verified 1.1.4; GUI tests `nav_is_solidworks`, `nav_restored` |

### Shortcuts

| Fact | Relied on by | Evidence |
|---|---|---|
| `Preferences/Shortcut`: key = command id, value = QKeySequence text. A change applies live; removing the key restores the command's built-in default; an empty value unbinds it | [`shortcuts.py`](../jellyjams/shortcuts.py) | Verified 1.1.4; GUI tests `shortcut_fit`, `shortcut_restored` |
| Qt fires **neither** action when two live actions share a key. In FreeCAD 1.1 `Std_ViewBoxZoom` owns Ctrl+B by default | `shortcuts._clashing_commands` (unbinds conflicts while active) | Verified 1.1.4; GUI tests `rebuild_owns_ctrl_b`, `no_shortcut_conflicts`, `boxzoom_key_restored` |
| In FreeCAD 1.1 `Std_ToggleVisibility` (Hide/Show) owns `Space` by default (built-in key, no `Preferences/Shortcut` entry) | `shortcuts._clashing_commands` unbinds it while `JellyJams_ViewOrientation` has Space | Verified 1.1.4; GUI tests `toggle_visibility_unbound_while_active`, `space_back_to_toggle_visibility` |
| Before Qt runs a window-wide shortcut it sends a `ShortcutOverride` event to the focus widget, which travels up the parents to the window until something accepts it; an accepted override makes Qt deliver the key to the widget instead. Line edits, spin boxes and text editors accept it for typed text, Space included. Buttons, check boxes, combo boxes and item views do not, so a window-wide Space shortcut takes the key from them | the orientation Space filter on the main window and its docks, and the panel's own `event()` | Verified 1.1.4 (live probe: with Space bound and no filter, a focused check box, push button, combo box and list lost Space to the shortcut, a line edit typed a space); Headless tests in `Test24Orientation` (Qt 6.8.3); GUI checks `pad_space_toggles_check_box`, `plain_dock_space_toggles_after_leave` (passed, 2026-10-28) |

### 3D view colors

| Fact | Relied on by | Evidence |
|---|---|---|
| `Preferences/View` holds the background (`Gradient`, `RadialGradient`, `UseBackgroundColorMid` Bools; `BackgroundColor2/3` Unsigned) and sketch colors (`EditedEdgeColor`, `FullyConstraintElementColor`, `FullyConstrainedColor`, `InvalidSketchColor`, `ConstructionColor`, `FullyConstraintConstructionElementColor`, `ConstrainedDimColor`, `NonDrivingConstrDimColor`, `ConstrainedIcoColor`) as packed unsigned RGBA (`0xRRGGBBAA`) | `viewport.MANAGED_KEYS` | Storage format verified 1.1.4; that each key name has the intended visual effect in 1.1.4 is **not verified** by the automated tests |

### Stylesheet

| Fact | Relied on by | Evidence |
|---|---|---|
| `FreeCADGui.getMainWindow().setStyleSheet()` layers on top of the application stylesheet and reverts cleanly. The `StyleSheet` / `Theme` preferences need a restart to take effect, so they are unsuitable for a per-workbench theme (and JellyJams never calls `QApplication.setStyleSheet`) | [`theme.py`](../jellyjams/theme.py) | Verified 1.1.4; GUI tests `theme_marker`, `theme_removed` |
| Dock titles are painted by `Gui::OverlayTitleBar` children; `QDockWidget::title` alone does not style their foreground | `theme.py` | Verified 1.1.4, 2026-10-29: custom title widgets found on all five stock docks; `gui_features: dock_titles_use_readable_color` checks their foreground |

## Assembly

| Fact | Relied on by | Evidence |
|---|---|---|
| `Preferences/Mod/Assembly` Bool `SwitchToWB` controls whether activating an assembly switches to the Assembly workbench; false keeps the current workbench (the code treats an absent key as true). Part Design and TechDraw have similar preferences ([Part Design](#part-design), [TechDraw](#techdraw)) | [`switch_prefs.py`](../jellyjams/switch_prefs.py) | Verified 1.1.4; GUI tests `switch_to_wb_off`, `stayed_in_jellyjams`, `switch_to_wb_restored` |
| Assemblies are `Assembly::AssemblyObject`; joints live in an `Assembly::JointGroup` | naming, mate panel, assembly commands | Verified 1.1.4 |
| `UtilsAssembly.activeAssembly()` (in `Mod/Assembly/UtilsAssembly.py`) returns the assembly only while it is in edit mode (`ViewObject.isInEditMode()`); activating means `Gui.ActiveDocument.setEdit(asm)` | `ribbon._assembly_active` (Assembly context tab), assembly drop and commands | Verified 1.1.4; GUI test `assembly_tab_on_activate` |

## Sketcher

| Fact | Relied on by | Evidence |
|---|---|---|
| When a sketch enters edit mode, FreeCAD asks `Show.mTempoVis.TempoVis.activateWorkbench` to switch to the sketch's `EditingWorkbench` (the Sketcher); if that request is ignored, nothing is switched back when the sketch closes | [`sketch_edit.py`](../jellyjams/sketch_edit.py) | Not verified by a GUI test |
| After `Sketcher_LeaveSketch`, the sketch needs a short moment (first look after about 50 ms) before a feature command sees it as closed | `sketch_gesture.SETTLE_MS` | Verified 1.1.4 (recorded in the code) |
| PartDesign Body origin in 1.1: `body.Origin.OriginFeatures` holds 3 `App::Line` axes, 3 `App::Plane` planes and 1 `App::Point`; each has `.Role` (`X_Axis`, `Y_Axis`, `Z_Axis`, `XY_Plane`, `XZ_Plane`, `YZ_Plane`); default plane labels are lowercase (`XY-plane`). SolidWorks mapping: XY = Top, XZ = Front, YZ = Right | `naming_rules.PLANE_NAMES` | Verified 1.1.4 |

## Part Design

| Fact | Relied on by | Evidence |
|---|---|---|
| Part Design's `ViewProvider::setEdit` calls `Gui::Command::assureWorkbench("PartDesignWorkbench")` for every feature that enters edit (new feature dialogs and editing an existing feature alike); there is no preference for it. `unsetEdit` switches back to the workbench that was active before. The object in edit is registered before control returns to the event loop | [`edit_guard.py`](../jellyjams/edit_guard.py) | Verified 1.1.4; GUI tests `d_edit_feature_stays_in_jellyjams`, `a_still_in_jellyjams_after_ok` |
| `Preferences/Mod/PartDesign` Bool `SwitchToWB`: while true or missing, Part Design switches to its workbench whenever a body becomes active, including when a sketch inside a body is left | [`switch_prefs.py`](../jellyjams/switch_prefs.py) | Verified 1.1.4; GUI test `a_still_in_jellyjams_after_exit` |
| `PartDesign_Pad` run with nothing selected and no usable sketch in the active body shows the warning "No sketch to work on" | [`sketch_gesture.py`](../jellyjams/sketch_gesture.py) (sketch first) | Verified 1.1.4; GUI tests `a_no_warning_dialog`, `b_no_warning_dialog` (no warning under JellyJams) |
| Without a selection, a profile feature takes a sketch when it is a `Part::Part2DObject` in the active body, not used by another Part Design feature, with at least one wire; with exactly one such sketch it is used directly | `sketch_gesture._free_sketch_count` | Verified 1.1.4; GUI tests `c_pad_uses_existing_sketch`, `c_no_new_sketch` |
| The active body is `ActiveView.getActiveObject("pdbody")` | `constants.ACTIVE_BODY_KEY` | Verified 1.1.4 |
| `PartDesign_NewSketch` with a plane or a planar face selected creates a sketch attached to it and opens it at once; with nothing selected it shows a plane picker in the task panel, and cancelling the picker creates no sketch | `sketch_gesture` (sketch first) | Verified 1.1.4; GUI tests `a_sketch_on_selected_plane`, `b_plane_picker_open`, `b_cancel_drops_state` |
| `Body::isSolid()` is true when the body's `Group` holds any non-datum Part Design feature (an object derived from `PartDesign::Feature`; datum planes, lines and points derive from `Part::Datum` and sketches from `Part::Part2DObject`, so neither counts). It does not look at the body's shape, so a Pad that has not been recomputed, or failed, still counts | `sketch_gesture._has_solid` (cutting features: is there anything to cut) | Not verified by a recorded check (FreeCAD's `Body.cpp`); headless `test_has_solid_mirrors_freecads_is_solid` covers JellyJams' copy of the rule |
| `PartDesign_Pocket` and `PartDesign_Groove` refuse at once, with their own message, in a body for which `isSolid()` is false. `PartDesign_Hole` has no check for a solid: with a profile and nothing to cut it builds a Hole that then fails to recompute, with nothing selected in the active body it shows its modal "No sketch to work on", and run while `PartDesign_NewSketch`'s plane picker is open it closes the picker | `sketch_gesture.REFUSED_BY_FREECAD`, `sketch_gesture._refuse_without_solid` (JellyJams refuses Hole itself in a target body without a solid) | GUI checks `hole_without_solid_starts_nothing` (FreeCAD's own "No sketch to work on" is what it rules out), `hole_without_solid_hint` (passed, 2026-10-28) |
| With several bodies and none active, `PartDesign_Hole` first asks which body to work in (modal `PartDesignGui::DlgActiveBody`, "Active Body Required", listing "Create New Body" and the bodies) and creates nothing when that is cancelled | `sketch_gesture._nothing_to_cut` (true only for a known target body), `sketch_gesture._maybe_start_sketch_first` (a cutting feature without a target body is left to FreeCAD) | Verified 1.1.4 by probe with a sketch selected; GUI check `hole_two_bodies_left_to_freecad` with nothing selected (passed, 2026-10-28). That Pocket and Groove ask the same way is not verified |

## Documents and naming

| Fact | Relied on by | Evidence |
|---|---|---|
| `obj.Name` is immutable; `obj.Label` is the tree text and writable. FreeCAD silently de-duplicates labels (`Top Plane` becomes `Top Plane001`) | [`naming.py`](../jellyjams/naming.py), `naming_rules` (numbering avoids collisions) | Verified 1.1.4; GUI tests `pad_sw_name`, `sketch_sw_name` |
| `FreeCAD.addDocumentObserver(o)` delivers `slotCreatedObject(obj)`, `slotChangedObject(obj, prop)`, `slotDeletedObject(obj)`, ... `slotChangedObject(obj, "Label")` fires **before** `slotCreatedObject` during construction; renaming inside an observer re-fires it, so renames are deferred (`QTimer.singleShot(0, ...)`) with a re-entrancy guard | naming, view_labels, weld_symbol, zoom_lines | Verified 1.1.4 |
| Documents expose `doc.Restoring` while loading; the code also reads `doc.Transacting` (and `HasPendingTransaction` in zoom_lines) to skip work during undo / redo. Both are read with a `False` default when missing | naming, view_labels, weld_symbol, projected_view, zoom_lines | Verified 1.1.4 (`Restoring`); not verified (`Transacting`) |
| `FreeCADGui.addDocumentObserver` exists for GUI-document events (such as edit start and end) | `sheet_sketch.install_watcher` | Not verified; falls back to a 250 ms poll |

## TechDraw

| Fact | Relied on by | Evidence |
|---|---|---|
| Pages are `TechDraw::DrawPage`, templates `TechDraw::DrawSVGTemplate` | drawing modules | Verified 1.1.4 |
| `Preferences/Mod/TechDraw/General` Bool `SwitchToWB`: while true or missing, double-clicking a page switches to TechDraw and shows it. When false, the entire native `doubleClicked()` handler does nothing. `page.ViewObject.show()` opens or raises the sheet without switching workbenches | [`switch_prefs.py`](../jellyjams/switch_prefs.py), `drawing_common.open_sheet_window` | Verified 1.1.4, 2026-10-29: Make Drawing's sheet was absent before the fix, active afterwards (`gui_features: drawing_context_tab`). [Matching FreeCAD source](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/TechDraw/Gui/ViewProviderPage.cpp#L265) |
| FreeCAD ships ISO templates under `<FreeCAD.getResourceDir()>/Mod/TechDraw/Templates/` (ISO formats in the `ISO/` subfolder, for example `A4_Portrait_ISO5457_advanced.svg`, `A3_Landscape_ISO5457_advanced.svg`) | [`templates.py`](../jellyjams/templates.py) | Verified 1.1.4; Headless test (catalog, when installed) |
| The ISO `*_ISO5457_advanced/minimal.svg` projection symbol has five elements with ids containing spaces: `first_angle_trapezoid`, `first_angle_inner circle`, `first_angle_outer circle`, `first_angle_horizontal`, `first_angle_vertical` | `templates.transform_symbol` (third-angle derivation) | Headless test `test_third_angle_symbol_on_installed_template` (skips when the template is not installed) |
| Editable title-block fields include `title`, `drawing_number`, `scale`, `creator`, `date_of_issue`, `language_code`, `part_material`, `legal_owner_1..4` | `sheet_properties`, `make_drawing`, `drawing_export` | Recorded from the installed 1.1.4 templates; not verified by a test |
| `Preferences/Mod/TechDraw/Rez` Float `Resolution` scales sheet millimetres to scene units (treated as 10 when 0 or missing); scene y grows downwards | `fcgui.rez`, `fcgui.scene_to_sheet` | Not verified by a GUI test |
| `Preferences/Mod/TechDraw/Files` String `TemplateFile` is the user's default template; `Preferences/Document` String `prefAuthor` is the author name | `templates.new_drawing_template`, `make_drawing` | Not verified by a test |
| A running TechDraw tool changes the sheet view's viewport cursor away from the arrow cursor | `fcgui.techdraw_tool_running` (heuristic; each caller chooses the answer used when detection fails) | Not verified by a test |
| TechDraw's PDF export writes one sheet per file | `drawing_export` (merges with `pdf_merge`) | Not verified by a GUI test |
| Zooming far into a sheet makes Qt log one "render glyph failed" warning per glyph | [`qt_filter.py`](../jellyjams/qt_filter.py) | Not verified by a test |

## Qt messages

| Fact | Relied on by | Evidence |
|---|---|---|
| FreeCAD forwards Qt messages to the Report view with a C++ message handler that cannot be reinstalled from Python once replaced. A Python handler installed with `qInstallMessageHandler` therefore stays for the session and must forward everything it does not drop | `qt_filter.install_and_enable` (self-test probe on install) | Not verified by a test; the install prints `Qt message filter active, self-test ok` or reports that the probe did not arrive |

---

## Re-verification checklist

Run this for every new FreeCAD release, on a throwaway configuration (see
[testing.md](testing.md#rule-never-touch-your-real-freecad-profile)):

1. Headless suite with that release's interpreter:
   `"<FreeCAD>/bin/python.exe" tests/test_headless.py` (all pass; note whether the
   installed-template test ran or skipped).
2. `tests/gui_smoke.py`, `tests/gui_tabs.py` (check the per-tab widget counts in
   [architecture.md](architecture.md#93-resolution-rules-ribbon_modelresolve) and the
   "left out of the ribbon" warning in the Report view), `tests/gui_sketch_first.py`
   (it depends on the [Part Design](#part-design) rows and on command strings running as
   `<string>`), `tests/gui_orientation.py` (Space and `Ctrl+8` through menu `QAction`s, Hide/Show on
   Space, the view directions, Normal To on a face, two faces, a whole sketch, an origin plane, a
   curved face, a datum line, an origin axis and a sketch through a link, the hint and its tool
   tip, the commands while a sketch or a feature dialog is open, in an undocked 3D view and with
   the Start page in front, the keyboard back to the undocked view, Space on a focused check box
   with the pointer over the task panel and over the 3D view, in a floating task dock, in a dock
   made later and after a click on the workbench selector, a Tab-focused panel button, Hole
   Wizard in a body without a solid and with two bodies and none active), and
   `tests/gui_lifecycle.py` in all four modes followed by `tests/check_saved_cfg.py`.
3. Manually confirm the rows marked **Not verified** that matter for the release, in
   particular: sketch editing stays in JellyJams (TempoVis), the `Std_DrawStyle` indices, the
   sketch color keys, TechDraw tool detection and multi-sheet PDF export.
4. Check that the dock objectNames, the Assembly command module names and the TechDraw
   template file names still exist.
5. Update the baseline line at the top and the Evidence column, and note the release in
   [`CHANGELOG.md`](../CHANGELOG.md).
