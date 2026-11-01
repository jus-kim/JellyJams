# JellyJams specifications

These are the behavior specifications of JellyJams, a FreeCAD 1.1+ workbench that gives FreeCAD a SolidWorks-style UI while it is active. The specifications also require that FreeCAD's stock UI comes back exactly when the user leaves the workbench, quits, or restarts after a crash. Not affiliated with or endorsed by Dassault Systèmes.

The specifications state what JellyJams must do, not how the code is organized. Each file covers one area and ends with numbered acceptance criteria.

- Implementation and test status: [../status.md](../status.md)
- Documentation home: [../README.md](../README.md)

## How to read a spec

Every spec starts with the same block:

| Field | Meaning |
|---|---|
| **Implemented in** | The modules under [`jellyjams/`](../../jellyjams/) (and icons under [`resources/icons/`](../../resources/icons/)) that carry the behavior. Use it as the entry point when you change or debug the area. |
| **Status** | Always points to [../status.md](../status.md). The specs themselves make no claim about whether a requirement works today. |

Conventions used in all specs:

- **MUST / MUST NOT / SHOULD / MAY**: mandatory, forbidden, recommended, optional. Specs that do not use these words state requirements in plain "must" sentences.
- **Exact strings are normative.** Command ids, objectNames, parameter groups and keys, property names, undo-step names and FreeCAD type ids are written in `code` and must match exactly.
- **"Intent" wording** (for example "Tooltip (intent)") means the meaning is fixed but the exact text is free.
- **Reference FreeCAD version** for widget names, type ids and list lengths is 1.1.4 unless a spec says otherwise.
- **Acceptance criteria** are numbered per file. Tests and notes refer to specs by file and section number (for example "ribbon-content 2.5"), so keep section numbers stable and append new criteria at the end of a list where possible.

## Index

| Spec | Area | What it specifies | Main modules | Acceptance criteria |
|---|---|---|---|---|
| [appearances.md](appearances.md) | Appearances | Official-reference browser, native colour/finish presets, face/object/component edits, undo and cleanup | `appearance_rules`, `appearances` | 9 |
| [core.md](core.md) | Core | Entry points, `package.xml`, workbench identity, Initialize / Activated / Deactivated step order, quit guard, autoload, startup crash recovery and backup formats, command registration, Diagnostics, Qt message filter, navigation and orbit response | `lifecycle`, `quit_guard`, `recovery`, `commands`, `diagnostics`, `qt_filter`, `params`, `constants`, `console`, `fcgui`, `paths`, `doc_utils`, `navigation`, `orbit`, `orbit_rules`, `shortcuts`; `InitGui.py`, `Init.py` | 41 |
| [ribbon-engine.md](ribbon-engine.md) | Ribbon engine | The CommandManager-style dock: button kinds, labels, icons, tooltips, enabled-state refresh, toggle, context tab switching, click dispatch, visibility guard, rebuild, remembered flyout choices | `ribbon`, `ribbon_model`, `ribbon_text`, `ribbon_widgets`, `icons`, `sketch_gesture` | 36 |
| [ribbon-content.md](ribbon-content.md) | Ribbon content | The five tabs (Features, Sketch, Evaluate, Assembly, Drawing), every group, button, flyout, fallback and icon source; summary counts; module preloading; flyout parameter keys; `JellyJams_NormalTo` as the Evaluate tab's Normal To | `ribbon_layout`, `fcgui` (preload), `constants` | 28 |
| [measure.md](measure.md) | Measure | Geometry-specific sizes, centre/axis distance and clearance, angles and totals, temporary white callouts, checked button and cleanup; reference measurement catalog | `measure`, `ribbon`, `palette`, `theme` | 10 |
| [window-layout.md](window-layout.md) | Window layout | Toolbars kept and hidden, Tasks and Report view docked right, exact restore on leave, quit/close guard with Cancel re-apply, autoload deferral | `layout`, `quit_guard`, `lifecycle` | 26 |
| [look.md](look.md) | Look | Light/dark palettes, scoped main-window stylesheet block, WCAG contrast requirements, 3D background gradient and sketch colors with persisted backup and recovery | `palette`, `theme`, `viewport`, `recovery`, `quit_guard` | 42 |
| [naming.md](naming.md) | Naming | SolidWorks labels in the model and drawing tree: numbering, origin planes, assembly folders, components and `(f)` marker, mates, drawing objects, existing-drawing refresh | `naming`, `naming_rules`, `constants` | 25 |
| [sketching.md](sketching.md) | Sketching | Sketch editing stays in JellyJams, feature from the open sketch, "Sketch" context icon, Centerline, Midpoint Line, sketch first for profile features (target body, container selections, subtractive features only with a solid by FreeCAD's `isSolid` rule, also when retargeting, Hole Wizard refused by JellyJams without one, left to FreeCAD without a target body, stale plane picks), feature editing stays in JellyJams (also under other add-ons' wrappers) | `sketch_edit`, `sketch_gesture`, `context_sketch`, `sketch_tools`, `edit_guard` | 61 |
| [orientation.md](orientation.md) | Orientation panel and Normal To | The SolidWorks Spacebar dialog and Normal To: `JellyJams_ViewOrientation` on `Space` and `JellyJams_NormalTo` on `Ctrl+8` and the Evaluate tab (the sketch plane in a sketch with nothing selected; otherwise exactly one pick: any face, edge or vertex, a datum or a one-face or one-edge object through FreeCAD's Align to Selection, a whole sketch looked at along the path it was picked through, links included; a hint in the status bar and at the pointer with nothing to look at), both available in sketches and task dialogs (`CmdType` `Alter3DView`) while the main window's active window is a 3D view (docked, undocked, fullscreen, split; not the Start page), the panel at the pointer (Normal To, remembered view, Zoom to Fit, standard views around Front, Isometric / Trimetric / Dimetric), pin, click outside (generation, keyboard and settle checks, the keyboard taken back while settling), Esc / Space, the keyboard given back to the window that had it, who gets Space (pointer over a 3D view, viewer, split view or the model tree, focused controls, Tab-focused panel buttons, toolbars and status bar, item views, docks, docks made later), buttons that follow FreeCAD's active state, theme-proof colors, close on leave, SolidWorks features not available | `orientation`, `commands`, `shortcuts`, `lifecycle`, `ribbon_layout` | 48 |
| [relations.md](relations.md) | Add Relations panel | Sketch entity recognition, offered relations per selection, existing relations list and delete, panel placement and styling | `relations_rules`, `relations_panel`, `panel_host`, `icons` | 27 |
| [assembly.md](assembly.md) | Assembly | Add Mate panel, drag-and-drop `.FCStd` insertion, `SwitchToWB` overrides of Assembly, Part Design and TechDraw with exact restore, New Assembly, Rotate Component | `mate_rules`, `mate_panel`, `panel_host`, `assembly_drop`, `switch_prefs`, `assembly_commands` | 42 |
| [dialog-terms.md](dialog-terms.md) | Dialog terms | SolidWorks terms inside FreeCAD's own task dialogs (catalog of forms and widgets), combo safety rule, scale-field fix, ISO 128 thickness presets row | `dialog_terms`, `dialog_terms_data` | 27 |
| [drawing-views.md](drawing-views.md) | Drawing views | Projected View, AutoDistribute rule, section/detail lettering and view labels, scale picker, click-anywhere view dragging, zoom line-width compensation | `projected_view`, `view_labels`, `view_scale`, `sheet_drag`, `zoom_lines`, `sheet_pick`, `drawing_common` | 44 |
| [drawing-sheet.md](drawing-sheet.md) | Drawing sheet | Make Drawing, Sheet Properties, template catalog and third-angle variants, sheet sketch shapes, Text, Insert Picture | `make_drawing`, `sheet_properties`, `templates`, `sheet_sketch`, `sheet_text`, `insert_picture`, `drawing_common`, `sheet_pick` | 45 |
| [drawing-symbols-export.md](drawing-symbols-export.md) | Drawing symbols and export | Surface Finish, Weld Symbol (with arrow-follow), Line Format, Save as PDF (multi-sheet merge), Export DXF, file naming | `surface_finish`, `weld_symbol`, `line_format`, `drawing_export`, `pdf_merge`, `dialog_terms`, `sheet_pick`, `sheet_drag` | 47 |

The navigation and shortcut areas ([`navigation.py`](../../jellyjams/navigation.py), [`shortcuts.py`](../../jellyjams/shortcuts.py)) have no separate spec. Their contract (when they are applied and restored, the key table, and their backup formats) is part of [core.md](core.md), steps A4, A5, D14, D15, section 4.8 and section 7. The `Space` and `Ctrl+8` keys of the Orientation panel and Normal To are specified in [orientation.md](orientation.md) 2.4.

## Module to spec map

Use this table to find the spec before you edit a module. All modules are in [`jellyjams/`](../../jellyjams/).

| Module | Spec(s) |
|---|---|
| `__init__.py`, `constants.py`, `console.py`, `params.py`, `paths.py`, `fcgui.py`, `doc_utils.py`, `commands.py` | [core.md](core.md) (shared infrastructure used by every area) |
| `lifecycle.py`, `quit_guard.py` | [core.md](core.md), [window-layout.md](window-layout.md) |
| `recovery.py` | [core.md](core.md) section 7, [look.md](look.md) 5.4, [assembly.md](assembly.md) 5.2 |
| `qt_filter.py`, `diagnostics.py` | [core.md](core.md) sections 10 and 9 |
| `navigation.py`, `shortcuts.py` | [core.md](core.md) (no separate spec); `Space` and `Ctrl+8` also [orientation.md](orientation.md) 2.4 |
| `orientation.py` | [orientation.md](orientation.md) |
| `palette.py`, `theme.py`, `viewport.py` | [look.md](look.md) |
| `layout.py` | [window-layout.md](window-layout.md) |
| `ribbon.py`, `ribbon_model.py`, `ribbon_text.py`, `ribbon_widgets.py` | [ribbon-engine.md](ribbon-engine.md) |
| `ribbon_layout.py` | [ribbon-content.md](ribbon-content.md) |
| `measure.py` | [measure.md](measure.md), including the reference measurement catalog |
| `icons.py` | [ribbon-engine.md](ribbon-engine.md) 2.7, [relations.md](relations.md) 2.4, [assembly.md](assembly.md) 2.1.3 |
| `naming.py`, `naming_rules.py` | [naming.md](naming.md) |
| `dialog_terms.py`, `dialog_terms_data.py` | [dialog-terms.md](dialog-terms.md), [drawing-symbols-export.md](drawing-symbols-export.md) 2.10 |
| `sketch_edit.py`, `sketch_gesture.py`, `context_sketch.py`, `sketch_tools.py`, `edit_guard.py` | [sketching.md](sketching.md), [ribbon-engine.md](ribbon-engine.md) 3.5 and 3.6 |
| `panel_host.py` | [relations.md](relations.md) 2.2, [assembly.md](assembly.md) 2.1 |
| `relations_rules.py`, `relations_panel.py` | [relations.md](relations.md) |
| `mate_rules.py`, `mate_panel.py`, `assembly_drop.py`, `switch_prefs.py`, `assembly_commands.py` | [assembly.md](assembly.md) (`switch_prefs.py`: section 5) |
| `drawing_common.py`, `sheet_pick.py` | [drawing-sheet.md](drawing-sheet.md) 3 and 8.2, [drawing-views.md](drawing-views.md) 2.2 and 3.3, [drawing-symbols-export.md](drawing-symbols-export.md) 2.3 and 2.5.1 |
| `templates.py`, `make_drawing.py`, `sheet_properties.py`, `sheet_sketch.py`, `sheet_text.py`, `insert_picture.py` | [drawing-sheet.md](drawing-sheet.md) |
| `projected_view.py`, `view_labels.py`, `view_scale.py`, `sheet_drag.py`, `zoom_lines.py` | [drawing-views.md](drawing-views.md) |
| `surface_finish.py`, `weld_symbol.py`, `line_format.py`, `drawing_export.py`, `pdf_merge.py` | [drawing-symbols-export.md](drawing-symbols-export.md) |

## Contracts shared across specs

These rules appear in several specs. Changing one affects more than one area, and some of them are stored in users' files or settings.

**Identity and naming** ([core.md](core.md) section 2, rules 1 to 6)

- Workbench key and class `JellyJamsWorkbench`, MenuText `JellyJams`.
- Every JellyJams command id is `JellyJams_` plus the tool's ribbon name without spaces, and every Qt objectName JellyJams creates is `JellyJams` plus a role word.
- "SolidWorks" never appears in identifiers, objectNames, file names, icon file names, parameter keys or command ids. It may appear in user-visible text.
- English only. No bundled third-party icons or templates.

**Exact restore** ([core.md](core.md) section 2 rule 7, sections 7 and 12)

Every FreeCAD-owned setting JellyJams changes is backed up first in `User parameter:BaseApp/Preferences/Mod/JellyJams`, restored exactly on leave and on quit, and recovered at the next startup after a crash.

| Backup key | Restores | Owning spec |
|---|---|---|
| `OriginalViewColors` | 14 keys in `Preferences/View` (gradient and sketch colors) | [look.md](look.md) |
| `OriginalNavigationStyle` | `Preferences/View` `NavigationStyle` | [core.md](core.md) |
| `OriginalShortcuts` | `Preferences/Shortcut` overrides | [core.md](core.md) |
| `OriginalSwitchToWB` | `Preferences/Mod/Assembly` `SwitchToWB` | [assembly.md](assembly.md) |
| `OriginalPartDesignSwitchToWB` | `Preferences/Mod/PartDesign` `SwitchToWB` | [assembly.md](assembly.md) |
| `OriginalTechDrawSwitchToWB` | `Preferences/Mod/TechDraw/General` `SwitchToWB` | [assembly.md](assembly.md) |

**JellyJams' own preferences** (kept across sessions, never restored)

| Group / key | Spec |
|---|---|
| `Mod/JellyJams` `SilenceGlyphWarnings` (Bool, user-owned, never written by JellyJams) | [core.md](core.md) 10 |
| `Mod/JellyJams` `ShowSketchButtonOnFace` (Bool, read only) | [sketching.md](sketching.md) 2.3 |
| `Mod/JellyJams` `LastNoteHeight` (Float), `LastNoteUnit` (String) | [drawing-sheet.md](drawing-sheet.md) 8.5 |
| `Mod/JellyJams/FlyoutChoices` `<flyout id>` (String) | [ribbon-engine.md](ribbon-engine.md) 5.1, [ribbon-content.md](ribbon-content.md) 4.5 |

**Document properties stored in users' files** (all in the property group `JellyJams`; file-compatibility contract: names, types and values must not change)

| Property | On | Spec |
|---|---|---|
| `HostSheet`, `ShownSketch`, `BorderLineIndex` | sheet sketch and its view | [drawing-sheet.md](drawing-sheet.md) 7.3 |
| `SheetNote` | JellyJams text annotations | [drawing-sheet.md](drawing-sheet.md) 8.3 |
| `CaptionFor` | section/detail view labels | [drawing-views.md](drawing-views.md) 4.4 |
| `SymbolType`, `MaterialRemoval`, `AllAroundOutline` | surface finish symbols | [drawing-symbols-export.md](drawing-symbols-export.md) 4.2 |
| `SymbolType`, `WeldSettings`, `ArrowheadX`, `ArrowheadY` | weld symbols | [drawing-symbols-export.md](drawing-symbols-export.md) 4.2 |

The naming spec reads these markers to choose tree names ([naming.md](naming.md) 3.5.4). Drawings made with JellyJams must still open in plain FreeCAD.

**Shared Qt objectNames**

| objectName | Created by | Styled or used by |
|---|---|---|
| `JellyJamsCommandManager`, `JellyJamsCommandManagerTabs`, `JellyJamsToolStack`, `JellyJamsGroupDivider` | [ribbon-engine.md](ribbon-engine.md) 4.1 | [look.md](look.md) 2.3 A, [window-layout.md](window-layout.md) |
| `JellyJamsPropertyManager`, `JellyJamsPropertyManagerTitle`, `JellyJamsSectionCaption`, `JellyJamsItemList` | [relations.md](relations.md) 2.3, [assembly.md](assembly.md) 2.1 | [look.md](look.md) 2.3 B; headings also in [drawing-sheet.md](drawing-sheet.md) 5.1 |

**Gating on the active workbench**

Hooks that stay registered for the whole session (document observers, application-wide event filters, the Qt message handler, timers) must check that `JellyJamsWorkbench` is the active workbench before acting ([core.md](core.md) section 2, rule 10). Exceptions are named in the owning spec, for example the weld arrow-follow watcher ([drawing-symbols-export.md](drawing-symbols-export.md) 2.5.4) and the zoom line-width restore triggers ([drawing-views.md](drawing-views.md) 7.2).

## Cross-area dependencies

| From | To | What |
|---|---|---|
| [core.md](core.md) lifecycle | every area | Step order on enter (A1 to A16) and leave (D1 to D18); each step guarded on its own |
| [core.md](core.md) shortcuts (4.8) | [orientation.md](orientation.md) | `Space` opens the Orientation panel and `Ctrl+8` is Normal To (`JellyJams_NormalTo`); Hide/Show loses `Space` while JellyJams is active. Both commands are in the JellyJams menu so that FreeCAD gives them working shortcuts |
| Quit guard ([core.md](core.md) 6.6, [window-layout.md](window-layout.md) 2.3) | [look.md](look.md), [core.md](core.md), [assembly.md](assembly.md), [ribbon-engine.md](ribbon-engine.md) | Reverts theme, view colors, navigation, shortcuts, the three `SwitchToWB` and hides the ribbon before FreeCAD saves; re-applies on Cancel |
| [ribbon-engine.md](ribbon-engine.md) click dispatch | [sketching.md](sketching.md) | Ends a running Centerline / Midpoint Line; routes profile features to the feature-from-open-sketch gesture and the sketch-first start |
| [ribbon-engine.md](ribbon-engine.md) context refresh | [drawing-views.md](drawing-views.md), [naming.md](naming.md) | Attaches view dragging, applies the AutoDistribute rule and the existing-drawing label refresh when a sheet window becomes active |
| [naming.md](naming.md) | [drawing-views.md](drawing-views.md) | One shared projection-type to label table (`PROJECTION_VIEW_LABELS`); same TechDraw-tool-running detection |
| [drawing-sheet.md](drawing-sheet.md) Make Drawing | [drawing-views.md](drawing-views.md) 3.7, [assembly.md](assembly.md) 3.4 | Start layout and AutoDistribute rule; same model-object priority as drag-and-drop |
| [drawing-symbols-export.md](drawing-symbols-export.md) export | [drawing-views.md](drawing-views.md) 7.2 | Restores standard line widths before writing PDF or DXF |
| [drawing-symbols-export.md](drawing-symbols-export.md) Line Format | [dialog-terms.md](dialog-terms.md) | Labels and ISO 128 presets row inside FreeCAD's line decoration dialog |

## Changing a spec

1. Edit the spec together with the code, in the same change.
2. Keep file-compatibility contracts (backup formats, the document properties in the `JellyJams` group, the `Mod/JellyJams/FlyoutChoices` key format) stable. If one must change, the spec has to say how existing files and settings are still read.
3. Update the **Implemented in** block when modules move or are split.
4. Record what is verified in [../status.md](../status.md), not in the spec.

License: LGPL-3.0-or-later. Copyright (c) 2026 jus-kim.
