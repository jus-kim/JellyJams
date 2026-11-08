# JellyJams specification: Appearances

> **Implemented in:** `appearance_rules.py` (pure library and validation),
> `appearances.py` (dock, selection and native view-material edits).
> **Status:** [../status.md](../status.md).

## 1. Official reference and mapping

The user explicitly requested official documentation. Consulted on 2026-10-31:

- [Appearances, Scenes, and Decals Tab, SOLIDWORKS Help 2025](https://help.solidworks.com/2025/english/solidworks/sldworks/r_appearances_scenes_and_decals_tab.htm):
  library browsing and previews in a task-pane tab.
- [Changing an Appearance, SOLIDWORKS Help 2025](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_appearance_assigment_methods.htm?id=68e3af18ff334abb882d28afd43f5421):
  category selection, double-click assignment to selected entities, or to the model
  with an empty selection.
- [Appearances PropertyManager, SOLIDWORKS Help 2024](https://help.solidworks.com/2024/english/SolidWorks/sldworks/HIDD_DVE_MATERIALS_COLOR_IMAGE.htm?id=20.0.8):
  editable colour/transparency and component versus part-document assignment.
- [Appearance Hierarchy, SOLIDWORKS Help 2024](https://help.solidworks.com/2024/english/SolidWorks/sldworks/c_appearance_hierarchy.htm?id=eb8ace515d434ae8b29e0bb7b957c744):
  face, feature, body, part and component assignment levels.

The attempted 2026 topic URLs did not expose usable topic content through the
research tool. The cited official 2024/2025 topics were used, without claiming
verification against the complete 2026 UI.

JellyJams adapts this workflow to native FreeCAD visual materials. Features and
bodies are coloured directly; faces use face-material arrays; part/assembly
containers colour contained objects; components use local link overrides.

## 2. Panel

**Appearances** (`JellyJamsAppearances`) is a right-side dock tab beside Tasks.
Tasks stays in front on activation. **JellyJams > Appearances** raises or reopens
the browser. No new ribbon tab or toolbar is registered.

The top has a target count, scope selector and search. A category tree sits above
the resizable thumbnail gallery. Plastic: High Gloss, Satin, Matte, Clear; Metal:
Polished, Metallic, Matte; Paint: High Gloss, Satin, Matte. There are 102 original
presets. Search filters the current category. Sphere thumbnails are painted with
Qt gradients; no third-party assets are bundled.

Single-click selects a preview and fills **Colour and finish**: hexadecimal RGB,
native colour picker, finish and 0–100% transparency. These controls never write
until **Apply Appearance** or a preset double-click. Each edit is one native
**Apply Appearance** undo step. Validate before opening a transaction; failure
aborts all objects in the edit. Feedback stays in the panel; errors use `console`.

## 3. Scope and protection

1. **Selection (faces or objects)** uses active-document selections. Face paths
   affect those faces only; others retain their materials. Merge duplicate picks;
   a whole-object pick dominates face picks on that object.
2. **Whole selected objects** ignores face/edge suffixes and colours their owner,
   explicitly replacing existing per-face colours, as the tooltip explains.
   Unlike SOLIDWORKS, no lower-priority object appearance is retained beneath
   face assignments.
3. **Entire model**, or an empty selection in the default scope, colours visible
   renderable roots, expanding containers. Hidden historical features are skipped.

Unsupported explicit selections and failed selection queries never fall back to
the model. Ignore foreign documents, invalid faces and unsupported elements.
Open task dialogs or pending document/application-wide transactions prevent an
edit; an unrelated active transaction is neither joined nor
closed. Container traversal prevents cycles.

`App::Link` and `Assembly::AssemblyLink` stop resolution: never follow a link to
edit its source. Set native `ShapeMaterial` (1.1), or the local `ShapeAppearance`
material list (26.3), and `OverrideMaterial` on the selected component only.
Select the property by capability. Per-face linked-instance overrides are unsupported; choose
**Whole selected objects**. Source and sibling instances remain unchanged.

## 4. Rendering, persistence and lifecycle

Presets use diffuse, ambient, specular and emissive colours, normalized shininess
and normalized transparency. Finishes approximate native Phong lighting. Metallic
is not a metalness shader. Textures, bump mapping, scenes, decals, RealView,
display states, saved custom libraries, appearance drag-and-drop and full
feature/body inheritance are not implemented; the UI offers supported controls.
Physical engineering materials and geometry do not change.

Edits are ordinary `.FCStd` view properties and remain on workbench leave.
Serialization quantizes colour channels to 8 bits; save/reopen tests allow one
channel step and check scalar values separately.

The owned dock and 500 ms target-refresh timer run only in JellyJams. Background
or closed tabs do not scan targets. Hidden-window startup defers creation;
repeated enable produces one dock/timer. Leave and quit detach/remove the dock
and stop the timer before stock layout restoration. Native save prompts and cancelled quit retain the browser and editor controls.
The early-Close compatibility fallback re-creates it after Cancel and resets
unsaved controls. No new parameter, backup or custom
document-property contract is introduced. There is no appearance-specific crash
recovery step; saves already contain native document values.

Publish a new dock only after its content is fully constructed. Construction
failure removes the incomplete dock so a subsequent refresh can retry.

## 5. Acceptance criteria

1. The tab, menu reopen, idempotency and light/dark native theme work.
2. Categories, thumbnails and search work without document edits.
3. Selected faces change; others stay unchanged; native Undo/Redo restores both states.
4. Custom RGB, finish and face transparency work; invalid input changes nothing.
5. Empty-selection double-click colours the visible model; body selection works.
6. Component assignment preserves source/siblings; Undo/Redo restores overrides.
7. A failure on the second object rolls back the complete multi-object edit.
8. Face materials and component overrides survive native save/reopen.
9. Leave removes the dock/timer, restores stock tabs and retains document colours.
   Reentry, quit, cancelled quit and autoload work too.

Headless: `Test25Appearances`, included in the existing Windows/Ubuntu CI
headless job. Its 15 tests cover rules/input validation, face targeting,
source-safe component writes, visible-model filtering, document transaction
commit/abort/cleanup, read-only previews, deferred startup, idempotency and
quit/cancel cleanup, failed selection queries, existing application transactions
and construction-failure recovery. Stub tests verify the abort protocol; native rollback,
Undo/Redo and save/reopen remain real-FreeCAD checks.

Real FreeCAD: `tests/gui_appearances.py`.
`gui_lifecycle.py` also checks that the dock stays present during the actual quit prompt and
after Cancel, plus creation on autoload, always using disposable configurations.
