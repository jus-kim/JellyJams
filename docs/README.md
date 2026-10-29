# JellyJams documentation

JellyJams is a FreeCAD 1.1+ workbench that gives FreeCAD a SolidWorks-style UI while it is
active: a CommandManager-style ribbon (tabs Features, Sketch, Evaluate, Assembly, Drawing),
SolidWorks tool and tree names, a light theme, SolidWorks navigation and shortcuts, and sketch,
assembly and drawing helpers. When the user leaves the workbench, quits, or restarts after a
crash, FreeCAD's stock UI and settings come back exactly.
Not affiliated with or endorsed by Dassault Systèmes.

License LGPL-3.0-or-later, (c) 2026 jus-kim. Repository: https://github.com/jus-kim/JellyJams.

This page lists every document in the repository and the order to read them in.

## Index

### Project root

| Document | What it is for |
|---|---|
| [../README.md](../README.md) | User-facing overview: features, requirements, install (Addon Manager and developer junction), usage, settings, license. |
| [../AGENTS.md](../AGENTS.md) | Rules and workflow for contributors and AI coding agents: non-negotiable rules, exact-restore discipline, code conventions, repo map, how to run tests. |
| [../CLAUDE.md](../CLAUDE.md) | Entry file for coding agents that look for a `CLAUDE.md`; it only imports `AGENTS.md`. |
| [../CHANGELOG.md](../CHANGELOG.md) | Release notes per version (heading format `## <version> — <date>` is checked by the tests). |
| [../LICENSE](../LICENSE), [../LICENSES/](../LICENSES) | GNU LGPL-3.0-or-later and the GNU GPL-3.0 text it builds on. |

### Project state and testing

| Document | What it is for |
|---|---|
| [status.md](status.md) | What is implemented, what is verified (headless and on real FreeCAD), what is open. The authoritative record of verification results. |
| [testing.md](testing.md) | How to run the headless suite and the GUI acceptance scripts, how to prepare throwaway configs, and how to read the results. |

### Design and internals

| Document | What it is for |
|---|---|
| [architecture.md](architecture.md) | Structure and contracts of the code: invariants, module map, import rules, lifecycle order, persisted state, error isolation, ribbon data model, and checklists for extending JellyJams. |
| [decisions.md](decisions.md) | Short decision records: why the design is the way it is. |
| [freecad-facts.md](freecad-facts.md) | The FreeCAD 1.1 behaviors and APIs the code relies on. |

### Behavior specifications

The specs are the normative description of what JellyJams does. Each ends with numbered
acceptance criteria. Start with the specs index; it explains the shared conventions and maps every
module to its spec.

| Spec | Covers |
|---|---|
| [specs/README.md](specs/README.md) | Specs index: how to read a spec, module-to-spec map, contracts shared across areas (backup keys, preferences, the document properties in the `JellyJams` group, objectNames). |
| [specs/core.md](specs/core.md) | Entry points and `package.xml`, workbench lifecycle (Initialize, Activated, Deactivated), quit guard, autoload, startup crash recovery, command registration, Diagnostics, Qt message filter, navigation and shortcut switching (the key table). |
| [specs/window-layout.md](specs/window-layout.md) | Which toolbars stay and which are hidden, Tasks and Report view docked right, exact restore on leave and quit, autoload deferral. |
| [specs/look.md](specs/look.md) | Palette and WCAG contrast rules, the main-window theme block, 3D background gradient and sketch colors with backup and recovery. |
| [specs/ribbon-engine.md](specs/ribbon-engine.md) | How the ribbon is drawn and kept alive: button kinds, labels, icons, tooltips, enabled states, context tab switching, click dispatch, remembered flyout choices. |
| [specs/ribbon-content.md](specs/ribbon-content.md) | What the five tabs contain: every group, button, flyout, fallback and icon source. |
| [specs/naming.md](specs/naming.md) | SolidWorks names in the model and drawing tree: numbering, origin planes, assembly folders, the `(f)` marker, mates, drawing objects. |
| [specs/dialog-terms.md](specs/dialog-terms.md) | SolidWorks terms inside FreeCAD's own task dialogs and the ISO 128 line-thickness presets row. |
| [specs/sketching.md](specs/sketching.md) | Sketch editing stays in JellyJams, feature from the open sketch, the Sketch context icon, Centerline, Midpoint Line, sketch first for profile features, feature editing stays in JellyJams. |
| [specs/orientation.md](specs/orientation.md) | The Orientation panel on `Space` (standard views, Normal To, remembered view, pin, click outside, who gets Space: the pointer over the model first, then focused controls), Normal To on `Ctrl+8` and the Evaluate tab (the sketch plane in a sketch, otherwise one face, edge, plane or sketch), both available in sketches, task dialogs and undocked 3D views, and the SolidWorks view features that are not available. |
| [specs/relations.md](specs/relations.md) | The Add Relations panel: entity recognition, offered relations, existing relations and deletion. |
| [specs/assembly.md](specs/assembly.md) | Add Mate panel, drag-and-drop `.FCStd` insertion, the `SwitchToWB` overrides of Assembly, Part Design and TechDraw with exact restore, New Assembly, Rotate Component. |
| [specs/drawing-sheet.md](specs/drawing-sheet.md) | Make Drawing, Sheet Properties, template catalog and third-angle variants, shapes and text on the sheet, Insert Picture. |
| [specs/drawing-views.md](specs/drawing-views.md) | Projected View, section and detail view labels, Scale picker, click-anywhere view dragging, zoom line-width compensation. |
| [specs/drawing-symbols-export.md](specs/drawing-symbols-export.md) | Surface Finish, Weld Symbol, Line Format, Save as PDF (multi-sheet), Export DXF. |

## Suggested reading order

### For users

1. [../README.md](../README.md): what JellyJams does and how to install it.
2. [status.md](status.md): what has been verified on which FreeCAD version and platform.

### For human maintainers

1. [../README.md](../README.md): the product from the user's side.
2. [../AGENTS.md](../AGENTS.md): the rules every change must follow, the repo map and the test commands.
3. [status.md](status.md): current state, known gaps, open work.
4. [architecture.md](architecture.md): how the code is organized; [decisions.md](decisions.md) for the reasons.
5. [testing.md](testing.md): run the headless suite once before changing anything.
6. [specs/README.md](specs/README.md), then the spec of the area you work on.
7. [freecad-facts.md](freecad-facts.md) when a change depends on FreeCAD's own behavior.
8. [../CHANGELOG.md](../CHANGELOG.md) when preparing a release.

### For AI coding agents

1. [../AGENTS.md](../AGENTS.md) (agents that read [../CLAUDE.md](../CLAUDE.md) get it through that file). Follow its rules without exception.
2. [status.md](status.md): what is verified and what is open, so you do not redo or contradict recorded work.
3. [architecture.md](architecture.md): invariants, module map, lifecycle tables and the extension checklists (section 12).
4. [specs/README.md](specs/README.md): find the spec for the module you will touch (module-to-spec map) and the cross-area contracts it must keep.
5. The area spec in [specs/](specs/), including its acceptance criteria.
6. [freecad-facts.md](freecad-facts.md) before relying on any FreeCAD behavior; [decisions.md](decisions.md) before reversing a design choice.
7. The module code under [../jellyjams/](../jellyjams/) and its tests in [../tests/test_headless.py](../tests/test_headless.py).
8. [testing.md](testing.md): run the headless suite; run the GUI scripts when the change affects lifecycle, layout, theme, viewport, navigation, shortcuts, ribbon building or the quit guard.
9. Before committing: update the area spec and [status.md](status.md) in the same change (and [architecture.md](architecture.md) if structure or contracts changed), and report anything not run on real FreeCAD as "not verified".

## Where things are recorded

| Kind of information | Goes in |
|---|---|
| Required behavior, exact strings, acceptance criteria | the area spec in [specs/](specs/) |
| What works, how it was verified, open issues | [status.md](status.md) |
| Module structure, contracts, extension checklists | [architecture.md](architecture.md) |
| Why a design choice was made | [decisions.md](decisions.md) |
| FreeCAD behavior the code depends on | [freecad-facts.md](freecad-facts.md) |
| How to run and prepare tests | [testing.md](testing.md) |
| Rules, conventions, workflow | [../AGENTS.md](../AGENTS.md) |
| User-facing description, install, usage | [../README.md](../README.md) |
| Released changes | [../CHANGELOG.md](../CHANGELOG.md) |
