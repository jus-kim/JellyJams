# Design decisions

A short log of the design decisions behind JellyJams, in the style of architecture decision
records: the **context** that forced a choice, the **decision**, and its **consequences**.
Every decision here is visible in the code; the "Code" line says where. For the overall
structure see [architecture.md](architecture.md); for the FreeCAD behaviors these decisions
react to see [freecad-facts.md](freecad-facts.md).

To change a decision, add a new entry that supersedes the old one and mark the old one
"Superseded by D-xx". Do not edit old entries in place.

| Id | Decision | Status |
|---|---|---|
| [D-01](#d-01-the-ribbon-is-a-dock-widget-not-a-toolbar) | The ribbon is a dock widget, not a toolbar | Accepted |
| [D-02](#d-02-restore-only-what-jellyjams-changed) | Restore only what JellyJams changed | Accepted |
| [D-03](#d-03-exact-restore-with-absent-key-removal-and-json-crash-backups) | Exact restore with absent-key removal and JSON crash backups | Accepted |
| [D-04](#d-04-the-quit-guard-is-modal-aware) | The quit guard is modal-aware | Accepted |
| [D-05](#d-05-defer-the-window-layout-on-autoload) | Defer the window layout on autoload | Accepted |
| [D-06](#d-06-unbind-conflicting-shortcuts-while-active) | Unbind conflicting shortcuts while active | Accepted |
| [D-07](#d-07-freecads-icons-at-runtime-original-icons-for-jellyjams-commands) | FreeCAD's icons at runtime, original icons for JellyJams commands | Accepted |
| [D-08](#d-08-use-freecads-installed-techdraw-templates-at-runtime) | Use FreeCAD's installed TechDraw templates at runtime | Accepted |
| [D-09](#d-09-label-only-renames-with-collision-numbering) | Label-only renames with collision numbering | Accepted |
| [D-10](#d-10-english-only-user-interface) | English-only user interface | Accepted |
| [D-11](#d-11-license-lgpl-30-or-later) | License: LGPL-3.0-or-later | Accepted |
| [D-12](#d-12-lifecycle-order-as-data-with-per-step-isolation) | Lifecycle order as data, with per-step isolation | Accepted |
| [D-13](#d-13-stay-in-jellyjams-while-sketching-and-in-assemblies) | Stay in JellyJams while sketching and in assemblies | Accepted, extended by D-16 |
| [D-14](#d-14-pure-modules-and-a-headless-harness) | Pure modules and a headless harness | Accepted |
| [D-15](#d-15-sketch-first-for-profile-features) | Sketch first for profile features | Accepted |
| [D-16](#d-16-stay-in-jellyjams-while-features-are-edited-with-a-deferred-guard) | Stay in JellyJams while features are edited, with a deferred guard | Accepted |
| [D-17](#d-17-space-opens-an-orientation-panel-ctrl8-is-jellyjams-normal-to-and-both-sit-in-the-jellyjams-menu) | Space opens an Orientation panel, `Ctrl+8` is JellyJams' Normal To, and both sit in the JellyJams menu | Accepted, extended by D-18 |
| [D-18](#d-18-the-orientation-commands-are-3d-view-commands-and-the-pointer-decides-who-gets-space) | The orientation commands are 3D-view commands, and the pointer decides who gets Space | Accepted |
| [D-19](#d-19-match-the-native-lightdark-widget-theme) | Match native light/dark widgets | Extended by D-20 |
| [D-20](#d-20-match-viewport-and-sketch-colors-to-the-native-theme-too) | Match viewport/sketch colors too | Accepted |
| [D-21](#d-21-balance-orbit-input-without-replacing-native-navigation) | Balance orbit input without replacing native navigation | Accepted |
| [D-22](#d-22-defer-orbit-discovery-outside-native-focus-change-callbacks) | Defer orbit discovery outside native focus-change callbacks | Accepted |

---

## D-01. The ribbon is a dock widget, not a toolbar

Status: Accepted. Code: [`ribbon_widgets.py`](../jellyjams/ribbon_widgets.py) (`RibbonUI`),
[`ribbon.py`](../jellyjams/ribbon.py).

**Context.**
* A CommandManager-style ribbon needs tabs, large buttons with two-line captions, three-row
  stacks of small buttons, flyouts and group separators. A `QToolBar` lays out one row of
  actions.
* FreeCAD hides and shows the toolbars it manages on every workbench switch and stores their
  state, but leaves foreign `QDockWidget`s alone.

**Decision.**
* Host the ribbon in a `QDockWidget` named `JellyJamsCommandManager` in the top dock area, with no dock
  features (not movable, floatable or closable) and an empty title-bar widget. It holds a
  `QTabWidget` (`JellyJamsCommandManagerTabs`) with the tabs below the buttons.
* JellyJams registers no `QToolBar` of its own.
* Build on the first show only; `hide()` keeps the widgets for the next activation.
* Every button dispatches through the single function `ribbon.run_entry`.

**Consequences.**
* FreeCAD's toolbar management never touches the ribbon; JellyJams decides its visibility.
* FreeCAD's asynchronous window-state restore can re-show docks, so the ribbon has a
  visibility guard (`hide_if_not_requested` on `visibilityChanged`, and after the layout's
  restore passes).
* The dock is part of the main-window state FreeCAD saves on quit, so the quit guard hides it
  first (D-04).

## D-02. Restore only what JellyJams changed

Status: Accepted. Code: [`layout.py`](../jellyjams/layout.py) (`_restore`, `_second_pass`),
[`theme.py`](../jellyjams/theme.py) (`remove`).

**Context.**
* On a workbench switch FreeCAD shows the next workbench's toolbars first and calls the old
  workbench's `Deactivated()` about 200 ms later. A blanket `restoreState()` there would hide
  the next workbench's toolbars.
* The user, FreeCAD or another add-on may change toolbars or the main-window stylesheet while
  JellyJams is active.

**Decision.**
* `layout.apply()` snapshots the main-window state (in memory only) and records exactly which
  visible toolbars it hid (all except those whose name contains File, Edit or Workbench).
* `layout.revert()` restores the snapshot, then puts every other toolbar back to the
  visibility it has right now and re-shows only the toolbars JellyJams hid. A second pass
  250 ms later repeats this, because FreeCAD may still be rearranging.
* `theme.remove()` restores the exact base sheet when nobody else changed the sheet, and
  otherwise removes only the JellyJams block.
* Parameter overrides restore only the keys JellyJams manages (D-03).

**Consequences.**
* The next workbench's toolbars stay visible after leaving JellyJams (GUI test
  `stock_toolbars_back`); foreign stylesheet rules survive removal (headless test).
* Dock and toolbar positions return to the snapshot taken on activation; position changes
  made while JellyJams was active are not kept.
* The layout snapshot is not persisted and startup recovery has no layout step. On a normal
  quit the quit guard (D-04) keeps JellyJams' layout out of the saved window state.

## D-03. Exact restore with absent-key removal and JSON crash backups

Status: Accepted. Code: [`viewport.py`](../jellyjams/viewport.py),
[`navigation.py`](../jellyjams/navigation.py), [`shortcuts.py`](../jellyjams/shortcuts.py),
[`switch_prefs.py`](../jellyjams/switch_prefs.py), [`recovery.py`](../jellyjams/recovery.py),
[`params.py`](../jellyjams/params.py).

**Context.**
* FreeCAD saves every parameter to `user.cfg` on exit, and FreeCAD can crash while
  JellyJams' overrides are in effect.
* "Restore the default" is wrong in both directions: a user may have a custom value, and a
  key that did not exist must not come back as an explicit value (FreeCAD's built-in default
  applies only while the key is absent).

**Decision.**
* Before the first write, record for every overridden key whether it existed and its value,
  and persist the record in `Mod/JellyJams` (`OriginalViewColors`, `OriginalNavigationStyle`,
  `OriginalShortcuts` as JSON; `OriginalSwitchToWB` as `1` / `0` / `absent`).
* Restore exactly: write recorded values back, **remove** keys that were absent, then clear
  the record. Presence is checked by type and name (`params.has_key`).
* A pending record is never overwritten by a later apply: it holds the real original.
* At every GUI start, `recovery.run_startup_recovery()` restores any record left behind. An
  unreadable record is discarded with one warning so it cannot block later sessions.

**Consequences.**
* Leaving, quitting and crashing all end with the user's own settings (headless round-trip
  tests; GUI tests `nav_restored`, `shortcut_restored`, `backups_cleared`, and
  `check_saved_cfg.py`).
* The record formats are an on-disk contract and must stay stable
  ([architecture.md, section 7.2](architecture.md#72-backup-record-formats-on-disk-contract)).
* Every new persistent override must follow the same pattern
  ([architecture.md, section 12.4](architecture.md#124-override-a-persistent-freecad-setting)).

## D-04. The quit guard is modal-aware

Status: Accepted. Code: [`quit_guard.py`](../jellyjams/quit_guard.py), `QUIT_REVERT_STEPS` /
`QUIT_REAPPLY_STEPS` in [`lifecycle.py`](../jellyjams/lifecycle.py).

**Context.**
* FreeCAD never calls `Deactivated()` on quit, but saves parameters and the window state while
  the main window closes.
* With unsaved documents, FreeCAD's "Save changes?" prompt runs a nested event loop inside the
  close handler; timers keep firing, and Cancel aborts the quit.

**Decision.**
* A Close-event filter on the main window (it runs before FreeCAD's close handling and never
  blocks the event) reverts everything FreeCAD would persist (Assembly preference, ribbon,
  shortcuts, navigation, viewport, layout), plus the theme, whenever JellyJams is active.
* It then checks every 600 ms. While `QApplication.activeModalWidget()` is set, or cannot be
  determined, it keeps waiting. Once no modal dialog is open, and only if the main window is
  still visible and JellyJams is still the active workbench, it re-applies exactly once.

**Consequences.**
* The saved `user.cfg` holds no JellyJams state even when the user waits inside the prompt
  and then discards (GUI lifecycle `discard` + `check_saved_cfg.py`); after Cancel the
  SolidWorks-style UI comes back (GUI lifecycle `cancel`).
* While the prompt is open the user sees stock FreeCAD.
* The guard also covers overrides applied while an autoload layout deferral never completed
  (D-05).

## D-05. Defer the window layout on autoload

Status: Accepted. Code: [`layout.py`](../jellyjams/layout.py) (`_start_deferral`, `_poll`).

**Context.**
* When FreeCAD autoloads JellyJams, `Activated()` runs before the main window is shown and
  before FreeCAD restores its saved window state. A snapshot taken then captures a bootstrap
  layout, and FreeCAD's later restore undoes the changes.

**Decision.**
* `layout.apply()` defers while the main window is hidden: it polls every 200 ms, up to 60
  polls, then gives up with one warning. `revert()` or a switch to another workbench cancels
  the deferral silently.
* All other activation steps apply immediately. When the deferred layout finally applies, it
  re-shows the ribbon (`ribbon.show_if_requested`) in case the state restore hid it.

**Consequences.**
* Autoload ends with the JellyJams layout, and leaving brings back the user's toolbars (GUI
  lifecycle `autoload`).
* If the window stays hidden for about 12 seconds, the layout is not applied (one warning);
  the rest of JellyJams still works.

## D-06. Unbind conflicting shortcuts while active

Status: Accepted. Code: [`shortcuts.py`](../jellyjams/shortcuts.py)
(`_conflicting_commands`).

**Context.**
* Qt fires neither action when two live actions share a key sequence. In FreeCAD 1.1,
  `Std_ViewBoxZoom` owns Ctrl+B, which JellyJams needs for Rebuild (`Std_Refresh`).

**Decision.**
* While JellyJams is active, every other command whose current shortcut equals one of the
  JellyJams keys gets an empty override (unbound). These commands are recorded in the same
  `OriginalShortcuts` and restored with the rest. The unbound commands are listed at log level.
* Commands that do not exist in the running FreeCAD are skipped with one message.

**Consequences.**
* Ctrl+B rebuilds while JellyJams is active and Box Zoom gets Ctrl+B back on leaving (GUI
  tests `rebuild_owns_ctrl_b`, `no_shortcut_conflicts`, `boxzoom_key_restored`).
* Box Zoom has no keyboard shortcut while JellyJams is active; it stays on the ribbon as
  "Zoom to Area".

## D-07. FreeCAD's icons at runtime, original icons for JellyJams commands

Status: Accepted. Code: [`icons.py`](../jellyjams/icons.py),
[`resources/icons/`](../resources/icons), `constants.COMMAND_ICONS`.

**Context.**
* FreeCAD's icons belong to FreeCAD, differ between versions and themes, and are already
  available at runtime. JellyJams' own commands have no FreeCAD icon.

**Decision.**
* Never copy FreeCAD icons. Look them up at runtime in a fixed order: the command's QAction,
  explicit file or `:/` resource paths, a lazily built index of `:/icons` by file stem, and
  `FreeCADGui.getIcon` last.
* JellyJams' own commands use original SVG icons in `resources/icons/` (64 by 64 viewBox, readable at
  16 to 20 px, no text, style, image or script elements, license comment in each file).

**Consequences.**
* Ribbon buttons match the installed FreeCAD's icon set, and the repository ships no
  third-party assets.
* If FreeCAD renames an icon, a button may lose its icon (icon-only buttons then show text);
  nothing fails.
* Icon files are checked by the headless tests (existence, valid SVG, forbidden elements).

## D-08. Use FreeCAD's installed TechDraw templates at runtime

Status: Accepted. Code: [`templates.py`](../jellyjams/templates.py).

**Context.**
* Make Drawing and Sheet Properties need ISO sheet formats with title blocks. FreeCAD ships
  them under `<resource dir>/Mod/TechDraw/Templates/`. Its ISO templates carry the
  first-angle projection symbol only.

**Decision.**
* Build the sheet-format catalog from FreeCAD's installed `ISO/` templates at runtime. A new
  drawing uses the first existing file of: the ISO A4 portrait / A3 landscape template, the
  same file at the templates root, the user's TechDraw `TemplateFile` preference, and
  `Default_Template_A4_Landscape.svg`.
* For third-angle projection, derive a variant at runtime by transforming the five
  `first_angle_*` symbol elements, and cache it as
  `<FreeCAD user data>/JellyJams/templates/<stem>_third_angle.svg`.

**Consequences.**
* No template files are bundled; drawings follow the installed FreeCAD.
* If a FreeCAD release renames the template files or symbol ids, derivation returns nothing
  and the base template is used unchanged; re-verify per release
  ([freecad-facts.md](freecad-facts.md#techdraw)).
* The cache folder can be deleted at any time; variants are re-created on demand.

## D-09. Label-only renames with collision numbering

Status: Accepted. Code: [`naming.py`](../jellyjams/naming.py),
[`naming_rules.py`](../jellyjams/naming_rules.py).

**Context.**
* SolidWorks names (`Boss-Extrude1`, `Sketch1`, `Top Plane`, `Mates`) make the tree familiar,
  but `obj.Name` is FreeCAD's immutable internal id, used by expressions and links.
* FreeCAD silently de-duplicates labels (`Top Plane` becomes `Top Plane001`), which would
  produce non-SolidWorks names.

**Decision.**
* Write only `Label`, never `Name`. Rename new objects on the next event-loop turn, in
  creation order. Change existing labels only when they still match a recognized FreeCAD
  default (for example default joint, projection view and template labels) or to add or
  remove the `(f) ` fixed-component marker.
* Compute unique names before writing: numbered names use the highest existing number of the
  same base among all other labels plus one; fixed names such as `Top Plane` get a number
  from 2 upwards when already taken.
* Name only while JellyJams is active.

**Consequences.**
* Internal names, and therefore expressions and links, are unaffected; only display labels
  differ (GUI tests `pad_sw_name`, `sketch_sw_name`).
* By design, users' own labels are kept. The naming rules are covered by headless tests; this
  is not verified in a GUI test.
* Objects created while another workbench is active keep FreeCAD's names, except default
  drawing labels, which `naming.refresh_drawing` updates when a sheet is shown in JellyJams.

## D-10. English-only user interface

Status: Accepted. Code: all user-visible strings are literals in the modules (for example
[`ribbon_layout.py`](../jellyjams/ribbon_layout.py),
[`dialog_terms_data.py`](../jellyjams/dialog_terms_data.py)).

**Context.**
* The point of JellyJams is SolidWorks terminology, which users know in English. A
  translation layer would add infrastructure for every label, tooltip and dialog text.

**Decision.**
* All JellyJams texts are English. There is no translation layer and no translation files.

**Consequences.**
* On a FreeCAD running in another language, JellyJams' labels are English while FreeCAD's
  own texts follow FreeCAD's language. Ribbon tooltips include FreeCAD's menu text, which is
  in FreeCAD's language.
* `dialog_terms` identifies FreeCAD's dialog widgets by objectName, not by text, and writes
  English texts.
* Adding a language later would need a new decision.

## D-11. License: LGPL-3.0-or-later

Status: Accepted. Code: [`LICENSE`](../LICENSE), [`LICENSES/`](../LICENSES), the header of every
source file, `license` in [`package.xml`](../package.xml).

**Context.**
* JellyJams is an add-on that runs inside FreeCAD, which is itself LGPL-licensed. The project
  wants improvements to JellyJams to stay open while allowing it to be combined freely with
  other software.

**Decision.**
* License all code and the original icons under the GNU Lesser General Public License,
  version 3 or later (`LGPL-3.0-or-later`), (c) 2026 jus-kim. Ship the LGPL text and the GPL
  text it builds on in `LICENSES/`. Every file carries the license header; SVGs carry it in an
  XML comment.
* Bundle no third-party assets (D-07, D-08), so no other license terms apply.

**Consequences.**
* Distributed modifications of JellyJams' files must remain under the LGPL.
* Contributions must be original or under compatible terms; the hygiene tests check the
  header in every Python file.

## D-12. Lifecycle order as data, with per-step isolation

Status: Accepted. Code: [`lifecycle.py`](../jellyjams/lifecycle.py).

**Context.**
* Activation touches many independent features in an order that matters (the layout snapshot
  first, its revert last). One failing feature must not leave FreeCAD half-changed or stop
  the restore of the others.

**Decision.**
* Keep every sequence (`INIT_HELPERS`, `ACTIVATION_STEPS`, `DEACTIVATION_STEPS`,
  `QUIT_REVERT_STEPS`, `QUIT_REAPPLY_STEPS`) as a table of `(key, what, module, function)`.
  `run_steps` resolves each function at call time, reports a failure as
  `JellyJams: could not <what>:` with traceback, and continues.
* Every step function is idempotent.

**Consequences.**
* The order is reviewable in one place and pinned by the headless tests, which also inject
  failures into single steps.
* Adding a feature means adding table rows
  ([architecture.md, section 12.3](architecture.md#123-add-a-feature-module)).

## D-13. Stay in JellyJams while sketching and in assemblies

Status: Accepted, extended by D-16. Code: [`sketch_edit.py`](../jellyjams/sketch_edit.py),
[`switch_prefs.py`](../jellyjams/switch_prefs.py).

**Context.**
* Editing a sketch makes FreeCAD switch to the Sketcher workbench (through
  `TempoVis.activateWorkbench`), and activating an assembly switches to the Assembly
  workbench (`SwitchToWB`). Either switch would leave JellyJams and restore stock FreeCAD
  mid-task.

**Decision.**
* While JellyJams is active, wrap `TempoVis.activateWorkbench` so the switch request is
  ignored; `uninstall()` puts back the identical original function. Sketch objects'
  `EditingWorkbench` properties are never touched.
* Hold the Assembly `SwitchToWB` preference at false while active, with the exact restore of
  D-03.
* The ribbon switches to the Sketch or Assembly tab on these transitions instead.

**Consequences.**
* Assembly activation keeps JellyJams (GUI test `stayed_in_jellyjams`). Staying in JellyJams
  while sketching is **not verified** by a GUI test.
* In every other workbench FreeCAD's behavior is unchanged.

## D-14. Pure modules and a headless harness

Status: Accepted. Code: `PURE_MODULES` and stubs in [`tests/`](../tests).

**Context.**
* Most rules (naming, relations, mates, ribbon resolution, contrast, PDF merging, scale text)
  are logic that does not need a running FreeCAD, while GUI tests are slow and need a real
  installation.

**Decision.**
* Keep such logic in pure modules that import nothing from FreeCAD or Qt.
* Test everything else headlessly against stubbed `FreeCAD` / `FreeCADGui` modules with real
  offscreen Qt, using FreeCAD's bundled Python; keep a small set of GUI scripts for what only
  the real application can show.

**Consequences.**
* Most behavior is covered quickly and repeatably by the headless suite (current count in
  [status.md](status.md)).
* Stubs can drift from real FreeCAD; GUI scripts and [freecad-facts.md](freecad-facts.md) are
  the check against that, and must be re-run per FreeCAD release.

## D-15. Sketch first for profile features

Status: Accepted. Code: [`sketch_gesture.py`](../jellyjams/sketch_gesture.py)
(`try_run`, `needs_new_sketch`, `advance`, `_watch`), `constants.SKETCH_FIRST_FEATURES`.
Spec: [sketching.md](specs/sketching.md) 2.6.

**Context.**
* In SolidWorks, Extruded Boss/Base pressed with no sketch asks for a plane, opens a sketch on
  it and builds the extrusion when the sketch is exited. FreeCAD 1.1.4's `PartDesign_Pad`
  pressed with nothing selected and no usable sketch shows "No sketch to work on" instead of
  going straight into a sketch.
* FreeCAD's feature commands are C++ and cannot be changed from Python. FreeCAD's own
  `PartDesign_NewSketch` already does the first half: it attaches to a selected plane or flat
  face, or shows its plane picker.
* There is no Python signal for "the plane picker was cancelled" or "the sketch was exited";
  both are only visible as task-dialog and in-edit state.

**Decision.**
* In the ribbon's dispatch (`sketch_gesture.try_run`), for Pad, Pocket, Revolution, Groove and
  Hole only: when nothing usable as a profile exists (nothing selected and no free sketch in
  the active body by FreeCAD's own rule, or only planes and planar faces selected), run
  `PartDesign_NewSketch` instead and remember the feature.
* Follow the plane pick and the sketch edit by polling every 150 ms. The decision is the pure
  function `advance()` (picking, editing, start, drop), so every transition is covered by
  headless truth tables. Picking waits 1.5 s before it treats "no dialog, nothing in edit" as a
  cancel, because FreeCAD opens its picker asynchronously.
* When the new sketch is exited with geometry, select it and run the feature, the same way
  the feature-from-open-sketch gesture does. A second press while picking only changes the
  feature; a press inside the new sketch is the ordinary gesture.
* Sweeps, lofts and helices keep FreeCAD's behavior: they need more than one input. Presses
  from FreeCAD's menus, shortcuts or the console keep FreeCAD's behavior too.

**Consequences.**
* No "No sketch to work on" warning from the ribbon: a plane picker or a sketch opens
  instead, and the feature dialog follows on Exit Sketch (GUI test `gui_sketch_first.py`,
  20 / 20 on 1.1.4).
* With a free sketch, or with a sketch selected, nothing changes. A selected body, edge or
  curved face still gets FreeCAD's own behavior and message.
* Extruded Cut, Revolved Cut and Hole Wizard start no sketch-first in a body that holds no solid
  by FreeCAD's own rule (`Body::isSolid()`: a Part Design feature in the body). Pocket and Groove
  then get FreeCAD's immediate refusal; FreeCAD's Hole has none, so JellyJams refuses it with a
  status-bar message, also while a sketch-first waits for its plane.
* The flow needs the Part Design `SwitchToWB` held at false (D-16): leaving the sketch makes the
  body active again, which would otherwise switch to Part Design and end the sketch-first.
* The state lives in memory only; leaving JellyJams or closing the document drops it.

## D-16. Stay in JellyJams while features are edited, with a deferred guard

Status: Accepted. Extends D-13. Code: [`edit_guard.py`](../jellyjams/edit_guard.py),
[`switch_prefs.py`](../jellyjams/switch_prefs.py). Specs: [sketching.md](specs/sketching.md)
2.7, [assembly.md](specs/assembly.md) 5.

**Context.**
* Part Design's view providers call `Gui::Command::assureWorkbench("PartDesignWorkbench")` on
  every `setEdit` of a feature, with no preference. Every feature dialog, including the one the
  sketch-first flow (D-15) opens and a double-click on an existing Pad, would leave JellyJams.
* `assureWorkbench` runs the command string `Gui.activateWorkbench('PartDesignWorkbench')`. The
  workbench selector and View > Workbench (`Std_Workbench`) run the same command string, so
  neither the caller nor the text tells a feature edit from the user's own choice. Blocking
  every command-string request would break the workbench selector.
* `assureWorkbench` and the view providers are C++ and cannot be wrapped from Python;
  `FreeCADGui.activateWorkbench` can.
* Part Design also switches when a body becomes active (including on leaving a sketch), and
  TechDraw when a page is double-clicked, each while its `SwitchToWB` preference is true or
  missing, like Assembly's (D-13).

**Decision.**
* While JellyJams is active, wrap `FreeCADGui.activateWorkbench`. A request for another
  workbench whose calling frame is a FreeCAD command string (code object file name
  `<string>`) waits one event-loop turn. If an object entered edit mode during that turn, the
  request was part of opening that edit and is dropped; otherwise the switch happens. Python
  callers, requests for JellyJams and calls while JellyJams is inactive pass straight through.
  `uninstall()` puts back FreeCAD's identical function.
* Hold the `SwitchToWB` of Part Design and TechDraw at false as well as Assembly's, each with
  its own backup record and the exact restore and crash recovery of D-03
  (`OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB`; Assembly's record is
  `OriginalSwitchToWB`).

**Why the workbench selector still works.** FreeCAD registers the object in edit before
control returns to the event loop, so after a `setEdit` request the deferred check always sees
a new object in edit. A choice in the workbench selector starts no edit, so after the same
one-turn wait the switch goes ahead. Part Design remembers JellyJams as the workbench to return
to, so its request on `unsetEdit` is for JellyJams and passes through.

**Consequences.**
* Opening or editing a Part Design feature keeps the ribbon and JellyJams (GUI tests
  `d_edit_feature_stays_in_jellyjams`, `a_still_in_jellyjams_after_exit`,
  `a_still_in_jellyjams_after_ok`); the workbench selector still switches
  (`d_user_switch_to_part_design_works`), one event-loop turn later.
* A workbench chosen in the very turn in which a new edit starts would be dropped; this is
  accepted as practically impossible.
* The guard depends on FreeCAD running command strings under the file name `<string>`
  ([freecad-facts.md](freecad-facts.md)); re-verify per FreeCAD release. Without the wrapper
  (for example if `activateWorkbench` is missing) feature edits switch as in stock FreeCAD.
* Staying in JellyJams on a TechDraw page double-click is not verified by a GUI test.

## D-17. Space opens an Orientation panel, `Ctrl+8` is JellyJams' Normal To, and both sit in the JellyJams menu

Status: Accepted, extended by D-18. Code: [`orientation.py`](../jellyjams/orientation.py),
[`shortcuts.py`](../jellyjams/shortcuts.py) (`SHORTCUTS`), [`lifecycle.py`](../jellyjams/lifecycle.py)
(`_add_menu_once`, the `orientation` activation and deactivation steps). Spec:
[orientation.md](specs/orientation.md).

**Context.**
* In SolidWorks the Spacebar opens the Orientation dialog at the pointer (standard views,
  Normal To, saved views), and `Ctrl+8` is Normal To; in a sketch with nothing selected, Normal
  To looks straight at the sketch plane. Users press Space all the time.
* FreeCAD 1.1 has every view command needed (`Std_ViewFront` ... `Std_ViewDimetric`,
  `Std_AlignToSelection`, `Sketcher_ViewSketch`, `Std_ViewSaveCamera`, `Std_ViewRestoreCamera`,
  `Std_ViewFitAll`) but no such dialog, and gives Space to `Std_ToggleVisibility` (Hide/Show).
  `Std_AlignToSelection` does nothing at all with an empty selection or with two picks, and has
  no sketch rule. With one pick it handles much more than flat faces and straight edges: curved
  faces, straight B-spline edges, planar curves, whole origin planes and axes, datums and objects
  that are a single face or edge, also through links; for a whole sketch it usually does
  nothing.
* A sketch's own `getGlobalPlacement()` knows nothing of links: a sketch shown through an
  `App::Link` or an assembly component sits where the link puts it.
  `FreeCAD.GeoFeature.getGlobalPlacementOf(target, root, path)` follows the path the user
  picked it through.
* FreeCAD creates a command's `QAction`, and so a working keyboard shortcut, only when the
  command is placed in a menu or toolbar. The JellyJams ribbon calls `FreeCADGui.runCommand` from
  its own buttons and creates no `QAction`. JellyJams registers no toolbar of its own (D-01).
* FreeCAD's actions repeat a held shortcut, so a held Space would open and close a toggling
  panel over and over.
* A tool window stays on top of FreeCAD until it is hidden, and FreeCAD's dark themes and dark
  system palettes give widgets light text.
* FreeCAD 1.1 has no icon for `Std_ViewSaveCamera` and `Std_ViewRestoreCamera`, and no command
  that splits the 3D view into several viewports.

**Decision.**
* Add the command `JellyJams_ViewOrientation`, which toggles a small frameless tool window at
  the pointer (`JellyJamsOrientation`) holding the view commands as buttons: the tools row
  (Normal To first), the six standard views laid out as an unfolded box around Front, and the
  three axonometric views. A click runs the command and closes the panel unless it is pinned
  (Normal To included); Esc and Space close it, and their auto-repeats are ignored. When another
  window becomes active, an unpinned panel closes itself; a deactivation right after opening is
  the opening settling, and the panel takes the keyboard back. Closing hands the keyboard back
  only when the panel had it: to the window that had it before the panel opened (an undocked or
  fullscreen 3D view, for example), else to FreeCAD's main window.
* Add the command `JellyJams_NormalTo`: in a sketch with nothing selected (or only that sketch's
  own elements) it runs `Sketcher_ViewSketch`. Otherwise it needs exactly one pick. Any single
  face, edge or vertex goes to `Std_AlignToSelection`, and so do a whole origin plane or axis, a
  whole datum and a whole object that is one face or one edge: FreeCAD decides what it can align
  to, and it knows more than JellyJams could judge from the shape. A whole sketch or other 2D
  object is looked at directly (`setCameraOrientation` on the view in front), along the
  placement of the path it was picked through (`GeoFeature.getGlobalPlacementOf`, else the
  sketch's own global placement), because `Std_AlignToSelection` cannot do the whole sketch.
  Anything else (two picks, a whole body or feature, nothing) gets a hint in the status bar and
  as a tool tip at the pointer instead of a command that would silently do nothing.
* Bind `Space` to View Orientation and `Ctrl+8` to Normal To through the existing shortcut
  table, so Hide/Show is unbound while JellyJams is active and everything is restored exactly
  (D-03, D-06). Neither command has an `Accel` of its own. FreeCAD's `Std_AlignToSelection` keeps
  its own key.
* List both commands in the JellyJams menu, above Diagnostics. A menu entry is the smallest place
  that gives a command a `QAction` without adding a toolbar; the menu exists only while
  JellyJams is active. Normal To also takes the Normal To place on the ribbon's Evaluate tab
  instead of `Std_AlignToSelection`, so the ribbon button has the sketch and plane rules too;
  the Sketch tab keeps FreeCAD's `Sketcher_ViewSketch`. View Orientation gets no ribbon button:
  the standard views are already on the Evaluate tab.
* Switch off key repeat on View Orientation's `QAction` on activation and whenever the command
  runs.
* Give the panel its own stylesheet with a text color and a background for every button state,
  so no theme can leave light text on the light panel. Enable each button from FreeCAD's
  `isActive()` every time the panel opens.
* Use FreeCAD's icons for the view buttons, `normal_to.svg` for Normal To, and original fallback
  icons only for the two camera commands that have none (D-07).
* Close the panel on leave in its own deactivation step, before the ribbon is hidden.

**Consequences.**
* Space opens the panel and `Ctrl+8` is Normal To while JellyJams is active, also in a sketch
  (D-18); Hide/Show has no key there and gets Space back on leave, on quit and after a crash.
  The GUI test `gui_orientation.py` checks this on FreeCAD itself (all checks passed on
  2026-10-28).
* The JellyJams menu has three entries. Removing View Orientation or Normal To from it would
  silently break its key.
* `Ctrl+8`, the panel and the Evaluate tab's Normal To behave the same. `Std_AlignToSelection`
  has no ribbon button; FreeCAD's own menus and its own key, if the user gave it one, are not
  changed.
* A single pick FreeCAD cannot align to (a vertex, for example) goes to `Std_AlignToSelection`
  anyway: the view stays as it is and no hint shows. The hint is kept for the cases where it is
  certain that nothing can happen.
* A sketch shown through a link or an assembly component is looked at where it is shown, as long
  as the selection names one path; with several items or paths the sketch's own placement is
  used.
* Viewport layouts (single, two, four views), the View Selector cube and named custom views are
  not offered; FreeCAD's navigation cube stays as it is.
* The panel keeps no persistent state, so the quit guard and crash recovery have nothing to do
  for it beyond the shortcut backup.

## D-18. The orientation commands are 3D-view commands, and the pointer decides who gets Space

Status: Accepted. Extends D-17. Code: [`commands.py`](../jellyjams/commands.py)
(`BaseCommand.cmd_type`), [`orientation.py`](../jellyjams/orientation.py) (`CMD_TYPE_VIEW`,
`_active_view`, `view3d_active`, `keeps_space`, `SPACE_FOR_PANEL_CLASSES`, `install`,
`_focus_changed`, `uninstall`),
[`lifecycle.py`](../jellyjams/lifecycle.py) (the `orientation` activation step). Spec:
[orientation.md](specs/orientation.md) 2.1 and 2.4.

**Context.**
* A Python command that declares no `CmdType` counts for FreeCAD as one that changes the
  document, the 3D view and the selection. FreeCAD disables a command that changes the document
  whenever the open task dialog does not allow that (`Gui.Control.isAllowedAlterDocument()` is
  False), and every default task dialog does so, the sketch editor's included
  ([freecad-facts.md](freecad-facts.md)). Without a `CmdType`, Space and `Ctrl+8` would do
  nothing while sketching, which is exactly where looking at the sketch plane matters.
* An undocked, fullscreen or split 3D view leaves the main window's MDI area, so the class of the
  MDI area's active window cannot tell whether the user works in a 3D view. FreeCAD's own view
  commands act on the main window's active window (`MainWindow::activeWindow`, in Python
  `getMainWindow().getActiveWindow()` in FreeCAD 1.1), which follows such a view.
  `FreeCADGui.activeView()` is no substitute: it keeps returning the document's last 3D view
  while the Start page or a drawing is in front, where there is no camera to turn.
* Space is a window-wide shortcut. Before Qt runs a shortcut it sends the focus widget a
  `ShortcutOverride` event; line edits, spin boxes and text editors accept it for typed text,
  but buttons, check boxes, combo boxes and item views do not. With Space bound, a focused
  check box in a task dialog (Pad's "Reversed", for example) could no longer be toggled with
  Space: the Orientation panel opened instead.
* **The focus alone is the wrong signal.** A check box keeps the keyboard focus after it was
  clicked. A user who clicks "Reversed" and then moves to the model and presses Space expects
  the Orientation panel, as in SolidWorks; a focus-only rule would flip the check box instead,
  out of sight, and change the feature. Controls in toolbars and in the status bar keep the
  focus after a click too (the workbench selector, the navigation-style button), so a focus-only
  rule would let Space open the workbench list after every workbench switch. Where the user is
  looking is where the pointer is.
* An event filter on the `QApplication` sees every event of every object in FreeCAD (mouse
  moves, paints, timers), and a Python filter turns each of them into a call into Python. An
  event filter on a window sees that window's own events plus the key events, shortcut
  overrides included, that the widgets inside it pass up unhandled. Qt passes key events up only
  to the widget's window, and a floating dock is a window of its own: a filter on the main window
  never sees the Space pressed in a floating task panel.

**Decision.**
* `BaseCommand` gets a `cmd_type` attribute that `GetResources` returns as `CmdType` only when it
  is set. Both orientation commands set `Alter3DView`: they only move the camera. Every other
  JellyJams command declares nothing and keeps FreeCAD's default, because it changes documents or
  the selection.
* Both orientation commands are active while the main window's active window is a 3D view (it
  has `getCameraNode`), docked, undocked, fullscreen or split; Normal To turns that view.
  `FreeCADGui.activeView()` is used only when the main window has no `getActiveWindow`; the MDI
  area is not asked.
* While JellyJams is active (its own activation step, right after the shortcuts, and the
  deactivation step that closes the panel), one event filter object, installed on FreeCAD's main
  window and on each of its docks but never on the application, decides a plain Space's
  `ShortcutOverride` (`keeps_space(focus widget, widget under the pointer)`):
  - with the pointer over a 3D view (`Gui::View3DInventor`), a 3D viewer
    (`Gui::View3DInventorViewer`, the drawing area's parent in every 3D view), a split 3D view
    (`Gui::AbstractSplitView`) or the model tree (`Gui::TreeWidget`), or anything inside them,
    Space is always for the panel;
  - otherwise a focused button, check box or combo box keeps Space, and so does an item view
    whose current item is checkable or which edits on any key; controls inside a toolbar, the
    status bar or the ribbon dock never keep it, and the model tree never does.
  Accepting the override gives the key to the focused control; everything else passes. The
  panel, a window of its own, applies the same rules to its buttons without the pointer rule: it
  opens beside the pointer, so the pointer is nearly always over the 3D view while the user tabs
  through it.
* Docks created after activation get the filter the first time one of their widgets takes the
  keyboard focus (`QApplication.focusChanged`, connected only while JellyJams is active).
* The model tree is left out of "keeps Space": there Space was Hide/Show before JellyJams, and in
  SolidWorks Space opens the Orientation dialog from the FeatureManager tree as well.

**Consequences.**
* Space opens the panel and `Ctrl+8` works while a sketch or a feature dialog is open and in an
  undocked 3D view (GUI checks `sketch_space_opens_panel`, `sketch_ctrl8_aligns_to_sketch`,
  `pad_dialog_space_in_view_opens_panel`, `undocked_space_opens_panel`). With the pointer over the
  task panel, Space still toggles a focused check box (`pad_space_toggles_check_box`), also in a
  floating task panel (`floating_task_dock_space_toggles_check_box`); with the pointer over the
  3D view it opens the panel and leaves the check box alone
  (`pad_pointer_over_view_check_box_unchanged`). These GUI checks passed on 2026-10-28.
* A user who wants Space for a focused control has to keep the pointer off the 3D view and the
  model tree; reaching a control with Tab and pressing Space over the dialog works as before. In
  the panel itself, Tab and Space work wherever the pointer is.
* The filter costs one Python call per event that reaches the main window or a dock, not one per
  event in FreeCAD. It sees only overrides that no widget inside accepted, which are exactly the
  ones that would run the shortcut. The focus watch costs one Python call per focus change while
  JellyJams is active.
* Docks created after activation (by another add-on, for example) are covered from the moment
  one of their controls takes the focus, which is before any of them can receive Space.
* With the Start page or a drawing in front, Space and `Ctrl+8` do nothing.
* A focused widget of a kind not in the list (a custom control that uses Space) loses Space to
  the panel while JellyJams is active. The property editor and plain lists give Space to the
  panel.
* The filter lives in memory only; leaving JellyJams removes it from every widget it was
  installed on, and a repeated activation never adds a second one.

## D-19. Match the native light/dark widget theme

Status: Accepted, 2026-10-29. Code: `palette`, `theme`, `orientation`, `context_sketch`.

**Context.** The original look spec explicitly accepted light JellyJams surfaces
mixed with dark native menus, editors and Start page. The user reported that
mixture as a bug and chose to follow FreeCAD's selected dark/light theme.

**Decision.** Keep the existing light widget colors and add a dark palette. Read
the effective native menu bar background/text luminances to select between them.
The menu bar is outside JellyJams' overrides, so repeated apply cannot detect its
own background and change modes. Ribbon/tree/dock/panel colors and floating
Orientation/Sketch popup colors follow the selected mode. Popups refresh on open.

**Consequences.** Theme selection is read-only and not persisted by JellyJams.
No new override or backup contract is needed: the main-window block is removed
exactly as before, and only JellyJams-owned popups have their own stylesheet.
Viewport and sketch drawing colors remain independent. Native Dark/Light tests
run in fresh scratch profiles and check colors and exact restoration.

## D-20. Match viewport and sketch colors to the native theme too

Status: Accepted, 2026-10-30. Code: `palette`, `theme`, `viewport`.

**Context.** D-19 left the viewport light. Native dark-theme cursor overlays
remained pale, making sketch creation hard to read. Widget-only theme following
was incomplete.

**Decision.** Use the same `theme.is_dark()` decision for the drawing palette.
Keep existing light colors, add a dark gradient with bright geometry and pale
driving/reference dimensions. Fully Defined geometry becomes bright green on
dark. Leave native cursor/overlay colors under FreeCAD's control.

**Consequences.** Supersedes D-19's independent-viewport policy. The same 14 keys,
types and backup format remain in use, with no additional persistent override.
Dark-mode contrast and exact restore/crash recovery are headless-tested. Native
Dark/Light GUI tests render real sketch geometry and dimensions and assert their
pixel colors as well as the matching background and exact restoration.

## D-21. Balance orbit input without replacing native navigation

Status: Accepted, 2026-10-30. Code: `navigation`, `orbit`, `orbit_rules`.

**Context.** Selecting FreeCAD's SolidWorks preset matched the buttons but left
orbit movement much slower horizontally on the user's ultrawide display. Actual
FreeCAD tests measured about 6° horizontally versus 24° vertically for equal
100-pixel drags. Switching between the five orbit modes did not fix the imbalance.

**Decision.** Normalize unmodified middle-drag deltas by the shorter viewport
dimension before forwarding to the native engine. Preserve its mode, pivot,
sensitivity, pan, zoom and middle-click behavior. Rebase after keyboard/modifier
changes to keep the camera continuous. Native cursor-warp mode bypasses this
correction; wheel zoom ends correction for that held drag.

**Consequences.** The correction is a runtime viewport hook owned by navigation's
existing enter/leave/quit lifecycle. No new saved preference or backup contract is
needed. Equal drag response, native controls, modifier changes and cleanup are
tested against real FreeCAD. This addresses a measured response imbalance; it
does not claim an exact reproduction of SolidWorks' rotation engine or latency.

## D-22. Defer orbit discovery outside native focus-change callbacks

Status: Accepted, 2026-10-30. Code: `orbit`.

**Context.** The orbit hook's new focus watcher scanned all Qt children directly
from `QApplication.focusChanged`. Accepting an extrusion destroys native task
widgets and emits that signal inside their destructors. The user's crash dump
showed PySide QObject type wrapping/child traversal entered from focus change
while FreeCAD reset the Pad edit dialog, ending in native heap corruption
(`0xc0000374`). An isolated test reproduced it on the first OK click.

**Decision.** Focus changes only schedule a coalesced zero-delay timer; the timer
discovers current live views after the callback returns. Initial discovery also
uses this path. Do not queue the old/new focus widget arguments. Cancel the focus
timer as well as periodic discovery on uninstall.

**Consequences.** Orbit scaling is retained without synchronous traversal of
partially destroyed task widgets. A real-GUI regression repeatedly accepts a Pad
edit dialog and orbits the solid, and a headless test checks deferred/coalesced
discovery and timer cancellation. Python exception guards alone cannot contain
this native crash. No new preference or recovery format is introduced.

## D-23. Native appearance edits behind an official-reference browser

Status: Accepted, 2026-10-31. Code: `appearance_rules`, `appearances`, lifecycle
and the dock-scoped part of `theme`. Contract and official SOLIDWORKS Help links:
[appearances.md](specs/appearances.md).

The user requested a colouring task-pane tab, then explicitly requested official
SOLIDWORKS documentation as its basis. Category browsing, sphere previews,
double-click assignment and colour/transparency controls follow those sources.
Native FreeCAD view materials provide the rendering and document persistence.

Use native per-face materials for selected faces, and local link material
overrides for components. Do not edit a link's source as a side effect of an
instance selection. Whole-object assignment explicitly replaces face colours;
we do not add persistent metadata to simulate the full SOLIDWORKS hierarchy.
Presets approximate native Phong finishes, without implying textures, decals,
scenes, metalness shaders or RealView support. Browser-only edits never touch
the document, and application is a single abortable native undo transaction.

The dock is tabbed with Tasks and removed before stock layout restore, including
quit. A cancelled quit re-creates it. No preference override/backup is needed;
user-applied appearance edits remain ordinary native document view properties.
