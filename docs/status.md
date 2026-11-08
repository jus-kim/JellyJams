# Implementation and test status

Status of JellyJams **0.1.0** as of **2026-11-08**, measured on **FreeCAD 1.1.4 and 26.3 RC2 (Windows)**.
This page is the record of what is built, what is verified, and what is open. The behavior
it is measured against is defined in the [specifications](specs/README.md). How to run every
test mentioned here: [testing.md](testing.md).

After any code change, re-run the suites and update this page (see
[Updating this page](#updating-this-page)).

## Consolidated PR Verification (2026-11-08)

The sketch, pointer-tool, host-compatibility, geometry and documentation changes
are collected in [PR #4](https://github.com/jus-kim/JellyJams/pull/4).
Fresh pre-publication checks use only disposable profiles:

| Verification | FreeCAD 1.1.4 | FreeCAD 26.3 RC2 |
|---|---:|---:|
| Full headless suite | 640/640, 42.2 seconds | 640/640, 41.9 seconds |
| Full native GUI coverage | Interrupted; 6 suites passed | 26/26 suites, 741 assertions |
| GUI result-validator unit suite | 10/10 | Shared runner |

GitHub's Linux and Windows headless/runner checks also pass for implementation
commit `ad694dc`. The full 26.3 GUI sweep is under `scratch/gui_d9tlb1wd`.
Its initial Smart Dimension check observed a three-pixel cursor change, and
Orientation's no-selection check encountered a selected face, causing dependent
assertions to fail. Both suites pass unchanged in the separate native rerun
`scratch/gui_x4bpcdwr` (22/22 and 84/84); no tolerances or assertions were relaxed.
Original failed results are retained. The 1.1.4 sweep under
`scratch/gui_0_taciue` passed quick access, plane selection, sketch aids, host
compatibility, surface geometry and Measure (236 assertions across six suites).
Smart Dimension recorded a two-pixel cursor change; the user confirmed active
mouse/keyboard use on this desktop. The runner and its own disposable FreeCAD
process were stopped during Smoke to avoid further interference. This partial
run does not establish a fresh full 1.1.4 pass; earlier dated native passes below
remain historical evidence. PR #4 stays a draft pending an uninterrupted rerun.
Completed native coverage includes geometry
recompute/save/reopen, sketch editing, all ribbon tabs, assembly/drawing helpers,
appearances, measurement, pointer/keyboard controls, light/dark themes and
leave/quit/cancel/crash restoration. Save/Discard include saved-config checks.

## Pointer tools and document context (2026-11-05)

Implemented the first versions of audit items **UX01, UX02 and UX04**:

- **S:** tools for the current part, sketch, assembly or drawing, plus searchable
  ribbon commands and flyout variants. Familiar and native names both match.
  Dispatch uses the ribbon route and rechecks document/context/availability.
- **D and viewport corner:** native OK/Cancel for the active feature, or
  Exit Sketch. Disabled native buttons stay disabled. Native document ownership
  and form identities reject foreign or stale task controls.
- **Context tabs:** new parts start on Features; document/mode choices return
  when switching windows; every sketch-edit entry selects Sketch. Manual tab
  changes are respected until the next context transition.

The service is owned by ribbon visibility and existing quit/reapply paths.
S/D use scoped transient filters, preserve typing and selection, and add no
shortcut settings, backup formats or document properties. Specs:
[quick access](specs/quick-access.md), [ribbon context](specs/ribbon-engine.md#34-document-and-edit-context).

Full headless suites pass **640/640 on both bundled Python runtimes** (1.1.4:
40.6 seconds; 26.3 RC2: 40.2 seconds), including **19 new quick-access tests**.
The drawing sketch's prior tab also returns when FreeCAD leaves the 3D window
active, including document switches during edit. The initial
S popup is a searchable list; customizable icon grids, the shared left manager
and the remaining audit proposals are future work. Undocked/split windows and
every native task type have not been newly certified.

Native Windows regression checks, always with disposable configs:

| Suite | 1.1.4 | 26.3 RC2 |
|---|---:|---:|
| Quick access, native confirmation and document/context return | 44/44 | 44/44 |
| Smoke: ribbon, theme, navigation, shortcuts and restore | 31/31 | 31/31 |
| Sketch-first and feature editing | 20/20 | 20/20 |
| Orientation and keyboard ownership | 84/84 | 84/84 |
| Quit Cancel / Discard / Save / autoload | 16/16; 9/9; 9/9; 6/6 | 16/16; 9/9; 9/9; 6/6 |
| Earlier reported bugs: linear dimension / sketch assist / one plane choice | 22/22; 35/35; 35/35 | 22/22; 35/35; 35/35 |

Results: 1.1.4 `scratch/gui_m3wnrkmx` (broader lifecycle/ribbon checks),
`scratch/gui_1m02mzay` (orientation), `scratch/gui_jv56e0mf` (final quick access),
`scratch/gui_muuavqdm` (reported sketch bugs); 26.3 RC2 `scratch/gui_y5xg5pix`
(broader lifecycle/ribbon/orientation checks), `scratch/gui__dgojtc0` (reported
sketch bugs), `scratch/gui_9wkxp62a` (final quick access). Discard/Save include the runner's saved-config checks. Earlier
popup/quantity-field harness failures were corrected; the passing reruns are
listed here. New popup and corner screenshots were visually inspected: native
icons, readable text/selection in the dark palette and no clipping. Popup suites run one host
at a time because foreground changes dismiss native popups.

## Interface audit and roadmap (2026-11-05)

The [interface audit](audits/2026-11-05-interface-audit.md) compares the running
SolidWorks Design Professional 2026 SP4.0 part/sketch workflow with current
JellyJams on 26.3 RC2. It includes current official 2027 documentation, whose
readable What's New PDF is marked PRERELEASE, a proposed layout schematic,
28 prioritized improvements and a native acceptance plan. Assembly/drawing
findings use code, specs, official references and earlier verification records;
they are not a new full manual comparison of those workflows.

An isolated native probe confirmed a 290-pixel idle Tasks dock in an 1800-pixel
window, retained Drawing-tab selection on a part, native numeric-input support,
and remaining differences in task headers, sketch status and preview appearance.
Live Windows capture displayed geometry correctly; artifacts in Qt OpenGL grabs
are not classified as a rendering bug. The fresh five-tab capture completed
without errors under `scratch/gui_0emxjmr1`. The interactive fixture used only
`scratch/ux_audit_live/user.cfg` and `system.cfg`.

The initial audit delivered documentation and original schematic artwork;
runtime code was unchanged at that point. Its 619-test baseline is historical.
The implementation follow-up above records the subsequently implemented items
and new verification; other proposals remain future work.

## Single-click sketch-first plane selection (2026-11-05)

In a fresh file, Extruded Boss/Base now enters sketch edit after a single plane
choice. The existing sketch-first watcher confirms the native dialog only for
one valid plane in its own pending document. FreeCAD 26.3 creates the sketch
before opening `PartGui::TaskAttacher`; its support must resolve to one plane
and its attachment mode must be active. Older hosts use the selected plane row
in `PartDesignGui::TaskFeaturePick`. Both paths press the native enabled OK
button; the older host's button box sits beside the task panel. No preferences
or document properties are overridden.

Native Windows checks use disposable configs with
`Selection/singleClickFeatureSelect` explicitly false. The new `plane_pick`
suite passes **35/35 on both 1.1.4 and 26.3 RC2**: actual single viewport clicks
on XY/XZ/YZ, the legacy list or 26.3 selection notification, correct support,
exactly one sketch, staying in JellyJams, waiting before choosing, native Cancel
and the preference staying false. Results: `scratch/gui_1v3nwpxx` (1.1.4) and
`scratch/gui_f8dgdwm_` (26.3). Coin face queries include the camera to find an
exposed click position; navigation animation is disabled only in the disposable
test profile. No OS pointer warping or repeated clicks are used.

The existing sketch-first GUI suite passes **20/20 on both hosts**, including
starting the extrusion after leaving a drawn sketch (`scratch/gui_poi5_av8`
and `scratch/gui_k0gxlf7f`). Seven headless regressions cover valid/invalid,
hidden/disabled/multiple rows, stale intents/documents, unrelated tasks,
attachment support paths and the older sibling button box.
The full headless suite passes **619/619 on each host**; the GUI result-validator
suite passes **10/10**, and `git diff --check` is clean.

Unverified: every datum-plane placement, keyboard-only plane selection and
undocked viewport configurations in real FreeCAD. This change intentionally
confirms only planes during the pending sketch-first flow.

## Smart Dimension preview follows the pointer (2026-11-04)

The ribbon's existing native Smart Dimension command now removes FreeCAD's
deliberate linear-preview gap (about 20 logical pixels in the 26.3 RC2 probe at
125% scaling). `sketch_dimension` delivers each native mouse move once, then
corrects only the new linear label distance. It never warps the pointer or
changes dimension values. Confirmed/pre-existing labels stay fixed; native
dialogs, Escape, continuous creation and type inference remain native.
The temporary viewport filter is stopped by subsequent ribbon commands and
ribbon hide/leave/quit. No persistent preferences, commands or lifecycle steps
were added. Radius, angle and arc-length previews retain native placement.

Verification on Windows with disposable configs:

| Check | FreeCAD 1.1.4 | FreeCAD 26.3 RC2 |
|---|---:|---:|
| Full headless suite, including 8 preview regressions | 612/612 | 612/612 |
| Native Smart Dimension: horizontal/vertical preview alignment, repeated moves, native confirmation, continuous creation, Escape, labels staying fixed, other tools and leave | 22/22 | 22/22 |
| Smoke / sketch-first regression | not rerun for this change | 31 / 20 |

Native results: `scratch/gui_8wq3x9as` (1.1.4) and `scratch/gui_m_1fi3p5`
(26.3 RC2). The earlier 26.3 smoke/sketch run is under `scratch/gui_3lu8zwsv`.
The result-validator suite passes 10/10; `git diff --check` is clean.

The native tests use synthetic viewport events without also warping the OS
pointer, avoiding duplicate asynchronous mouse moves. They end the continuous
native tool before destroying the document. Early 1.1.4 test runs hit native
heap corruption (3221226356) when directly closing an edited document with
Dimension still active; a separate control run with only native Dimension and
no preview correction reproduced the same exit in `scratch/dimension_baseline`.
Final runs exit normally after leaving the sketch first. This change does not
repair that older-host native document-close problem.

Unverified: every dimension geometry/type, perspective/undocked views in real
FreeCAD and native shortcuts outside ribbon dispatch. Camera-size math includes
portrait views and rejects invalid inputs in headless tests. 1.1's temporary
arrow cursor around its value dialog is covered by a regression so it does not
disable correction for the next dimension.

## Automatic sketch drawing aids (2026-11-04)

`sketch_assist` now enables native `Snap`, `SnapToObjects` and the edited view's
`Autoconstraints` on sketch entry in JellyJams, including an already open sketch
on workbench entry. It restores originals on exit, leave and quit, supports the
quit/Cancel fallback and recovers snapping preferences at startup after a crash.
Auto constraints are restored before saving the document and resumed afterward;
other sketches and the global AutoConstraints preference are unchanged. Scoped
`NoModify` protects the document's modified state during temporary view-property
writes. No automatic external-geometry projection or grid snapping is added.

Verification on Windows, using only disposable `-u` / `-s` configurations:

| Check | FreeCAD 1.1.4 | FreeCAD 26.3 RC2 |
|---|---:|---:|
| Full headless suite, including 15 sketch-aid regressions | 602/602 | 602/602 |
| Native sketch aids: origin/corner/edge snapping, Coincident/PointOnObject, normal and automatic-recovery serialization, status flags, close/reentry/leave/quit hooks | 35/35 | 35/35 |
| Smoke / sketch first / Cancel / Discard | 31 / 20 / 16 / 9 | 31 / 20 / 16 / 9 |
| Saved configuration after Discard | 7/7 | 7/7 |
| Forced termination during sketch editing / startup recovery | 2 / 3 | 2 / 3 |

The GUI result-validator suite also passes 10/10. Final native aid results are
under `scratch/gui_jskzn1qk` (1.1.4) and `scratch/gui_a708j29s` (26.3); final
forced-termination/recovery results are under `scratch/gui_xrzf9w63` and
`scratch/gui_8rbdxqmi`. Other regression results are under `scratch/gui_n5nxp44x`
and `scratch/gui_k73wzij5`.

Two 26.3 forced-exit attempts saved all assertions and recovered preferences
correctly, but Windows aborted in the C-runtime exit path (3221226505 instead
of 86). The test now calls `TerminateProcess` on itself on Windows, bypassing
native editor-thread cleanup; the final runs require and pass exit code 86.
This is a test-harness change, not a production quit path.

Unverified: every sketch geometry tool and every external-reference scenario;
the native pointer checks use lines and existing sketch geometry. The automatic
recovery check uses the default compressed recovery format. It does not add or
claim automatic projection of solid edges into sketches.

## FreeCAD 26.3 RC2 compatibility sweep (2026-11-03)

The existing workbench works on both tested hosts after targeted compatibility fixes;
it does not need a rewrite. The installed hosts were 1.1.4 R20260928 (`4fd3bf320`,
Python 3.11 / Qt 6.8.3) and 26.3.0 RC2 R20261018 (`9fb16e7f9`, Python 3.13.15 /
Qt 6.11.2). These results apply to these Windows builds, not a later release candidate.

Fixed the following differences, with headless regression tests and native GUI checks:

- Task panels now sit inside wrappers and a stack for individual documents. Add Mate
  and Add Relations find the visible native panel, including when its dock tab is hidden.
- Measure closes the task belonging to its original document. It also cleans up the
  older application's global task when its document is deleted, without closing a
  different document's sketch task on 26.3.
- Component appearances use `ShapeAppearance` on 26.3 and `ShapeMaterial` on 1.1.
  Overrides remain local to the selected link; its source and sibling links are preserved.
- Assembly's native resource module is loaded before its Python commands on 26.3,
  so the ribbon receives the native icons. That module is optional on 1.1.
- Task-dialog discovery accepts Qt's compiled `__` names as well as `::` names.
  Balloon, Rich Text Annotation and Line Format controls receive the intended terms
  and the ISO thickness preset row on both hosts.

The harness also now finds each bundled Qt plugin directory, targets exposed screen
positions for pointer tests, samples sketch backgrounds away from the green axis,
and compares orbit angles using the same complete 3D-view size even when Windows
limits the main-window size. Assertions and tolerances were retained.

Final accepted results, from complete sweeps plus targeted reruns after fixes:

| Verification | 1.1.4 | 26.3 RC2 |
|---|---:|---:|
| Headless suite | 585/585 | 585/585 |
| Native GUI suites | 22/22 | 22/22 |
| Assertions within those suites | 616/616 | 616/616 |
| Saved configuration checks, Save and Discard exits | 14/14 | 14/14 |
| Additional assembly checks using copies of the user's profiles | 104/104 | 104/104 |
| Opening, editing and resaving 1.1.4 fixture documents in 26.3 | source host | 22/22 |

The GUI coverage includes all five ribbon tabs; sketch and feature editing;
orientation and orbit; Measure; native appearance editing and persistence;
assembly creation, mates and tree actions; drawing helpers and exports; reconstructed
surface geometry; Report view behavior; light/dark themes; leave, cancelled quit,
Save/Discard quit, autoload, forced termination and startup recovery. The supplied
`moddoMOUISE_A1 Part 2.stp` was also exercised in Measure on both hosts (83 assertions
instead of the default 72), including its 1.500 mm distance and 0.925 mm clearance.

The migration probe checked face materials, local link overrides, surface/fillet/Boolean
Python proxies, driving pole and radius edits, dependent recompute, drawing projections
and external source links, PDF export, and the assembly container. Saved copies reopened
successfully. The original 1.1.4 fixtures were unchanged. This is representative file
compatibility evidence, not verification of every existing user document.

All GUI runs used disposable `-u` / `-s` configurations. Additional assembly runs used
copies of the two real profiles, and before/after hashes confirmed that their original
configuration files were unchanged. The reported intermittent assembly freeze did not
reproduce; it remains open and is not claimed fixed. Linux/macOS, installation through
the published Addon Manager entry, and the user's complete shell reconstruction remain
outside this verification. Earlier dated sections below retain their historical results;
this sweep supersedes their host/coverage summaries where explicitly covered here.

Evidence (local, git-ignored):

- Consolidated per-suite provenance: `scratch/rc263_verification.json`.
- Headless logs: `scratch/rc263_final_headless.log` and `scratch/rc263_final_headless114.log`.
- Full 26.3 run: `scratch/gui_esspxcko`; final host/Measure reruns: `scratch/gui_siwn5gu1`;
  final orbit rerun: `scratch/gui_4ge2e_1x`.
- Full 1.1.4 run: `scratch/gui_fhk8atj_`; final host/Measure reruns: `scratch/gui_qq_a83h8`.
- Copied-profile assembly results: `scratch/rc263_profile_checks.json` and the two folders it names.
- Cross-version migration: `scratch/rc263_migration/migration.json` and saved copies beside it.

Initial failed runs are retained. The 26.3 full run needed the orbit harness correction;
the 1.1.4 full run exposed the legacy Measure cleanup regression and an incorrect native
dialog test setup. Their final replacements above pass. No result file from a failed
run was edited to claim success.

### Existing FreeCAD MCP integration

The installed **FreeCADMCP 0.1.28** add-on works with 26.3 RC2. Its existing RPC server
is bound to `127.0.0.1:9875`, with remote access disabled. A `freecad` stdio MCP entry
was registered in the local Codex configuration, using the existing `freecad-mcp.exe`
and the 26.3 `FreeCADCmd.exe`; startup/tool timeouts are 30/180 seconds. This uses the
separate installed add-on and bridge, not an assumption that MCP is built into FreeCAD core.

Actual MCP protocol tests discovered 17 tools and verified document/object creation,
parameter editing, valid geometry and volume, viewport image retrieval, save/reopen,
asynchronous execution/status, RPC status, a headless Boolean operation, and reconnection
across GUI restarts. They used disposable profiles and scratch documents. A native modal
dialog blocks GUI dispatch as designed; the headless route was verified separately.
Not every individual tool, such as FEM operations, was exercised.

Evidence: `scratch/rc263_mcp_catalog.json`, `scratch/rc263_mcp/acceptance.json`,
`scratch/rc263_mcp/headless_acceptance.json`, and `scratch/rc263_mcp/reconnect.json`.
The current chat's tool catalog does not dynamically gain the new entry: **restart Codex
once to load the registered FreeCAD tools**. No Codex restart was forced during the sweep.

## Reconstructed surface geometry (2026-11-02)

Added document-level analytic/NURBS geometry tools for source blends that cannot
be reconstructed with the native fillet operator. Mathematical supports and 3D
boundaries are stored in schema-1 JSON; B-spline poles use editable native
vector-list properties. The original radius is explicitly read-only provenance,
not a driving fillet parameter. No application/UI overrides or commands are added.

The codec resolves periodic trim complements using reference face areas, handles
small ellipse radii, and retains feature placement through recompute failures.
Invalid edits clear stale geometry and expose a Report-view error; valid edits
recover. See [surface geometry](specs/surface-geometry.md).

Added a linked local fillet change tool for cases where the constant-radius
geometry API works on an isolated region but the standard feature fails. Its
native `Radius` property drives recomputation; input edges and the box scope are
document links. Standard Boolean/mirror objects apply its material change. A full-result mode
uses the complete input without a scope and returns the rounded solid.

Mathematical definitions now retain shared edge identities and optionally original
UV trimming curves, avoiding another projection for supported surface trims. Added
linked geometry API Boolean features with explicit largest-solid selection and a
read-only discarded-cell count; this can select the valid main solid when the kernel
returns additional cells. The option defaults off for general creation. Unions
that lose the main input solid are rejected instead of accepting an isolated tool cell.

Validation: **575/575 headless**, zero failures/errors/skips
(`scratch/surface_headless.log`); real FreeCAD 1.1.4 **27/27** with disposable
profiles (`scratch/surface_geometry.json`): primitive/ellipse/periodic-trim
round trips, pole edits and dependent updates, save/reopen/proxy restoration,
placement, local driving-radius edits, invalid-edit recovery and staying in JellyJams. The user's complete
shell reconstruction is still in progress and is **not yet verified**.

## MIT licensing (2026-11-01)

At the copyright holder's request, JellyJams code and original icons now use
the MIT License (decision D-25, superseding D-11). Updated `LICENSE`,
`LICENSES/MIT.txt`, all Python/XML/SVG SPDX headers, package metadata,
contributor guidance, documentation and license expectations. Removed the
obsolete bundled license texts. D-11 remains explicitly marked as a historical,
superseded decision; earlier published copies retain their granted permissions.

Validation: **559/559 headless**, no failures/errors/skips, using FreeCAD 1.1.4's
Python and Qt shim (`scratch/mit_headless.log`); GUI-result validator **10/10**;
`git diff --check` passed. Metadata checks require MIT in `package.xml`, matching
complete license texts and the author's copyright notice. Hygiene/icon checks
require MIT SPDX headers. Syntax-tree comparison confirms that all **68**
modified production Python files retain identical executable code. Native GUI
suites were not rerun for this license-only change.

## Keep JellyJams visible during save prompts (2026-10-31)

The user reported the intentional early quit teardown as an unwanted interface
change. FreeCAD 1.1.4 source confirms that `mainWindowClosed` is emitted only
after native close/save acceptance and before `saveWindowSettings`. The quit
watcher now connects synchronously to that signal and runs the existing restore
steps there. Native prompts retain the ribbon, theme, viewport and Appearances;
Cancel leaves JellyJams intact. Hosts without the signal retain the conservative
early-Close/modal-poll fallback. D-24 supersedes the earlier prompt behavior.

Verified on FreeCAD 1.1.4 Windows with disposable profiles:

- **533/533 headless**, no failures/errors/skips, including four accepted-close
  ordering/idempotency tests plus all six fallback tests (`scratch/accepted_quit_headless.log`).
  GUI-result validator **10/10**, Python compilation and `git diff --check` passed.
- Native Cancel **16/16**, Discard **9/9**, relaunch **5/5**, Report view **9/9**,
  saved Report view autoload **3/3** (`scratch/gui_902sdcvt/`, runner exit **0**).
- Native Save **9/9**, saved-config checker **7/7** (`scratch/gui_cizb07_q/`).
  The saved document's Box.Length is **17**, confirming the dirty edit was saved.
  Discard's saved-config checker also passes **7/7**. Both paths persist the
  original navigation/shortcuts/switch preferences with no pending backups.
- Save As cancellation is covered by the signal's native acceptance ordering,
  but was not separately exercised in the GUI. Compatibility fallback remains
  headless-verified; the installed host uses the accepted-close path.

## Report view visibility through quit (2026-10-31)

The user's startup follow-up exposed a missing case: when Report view was open
before activation and closed inside JellyJams, quit restored the snapshot's open
state and FreeCAD saved it. The earlier regression only began with a closed dock.
The new regression failed in both directions before the fix.

Both layout restore passes now preserve Report view's current explicit visibility
while restoring its original position. No profile values or auto-show preferences
are overridden. Closing it once and quitting normally saves the native startup
choice; users can also keep an explicitly reopened Report view open.

Validation: **529/529 headless**, no failures/errors/skips (`scratch/report_choice_headless.log`),
including the two visibility directions and original dock placement; GUI-result
validator **10/10**, compilation and `git diff --check` passed. Native FreeCAD
1.1.4 focused run: Report view **9/9**, saved-state autoload **3/3**, Cancel
**16/16**, Discard **9/9**, post-Discard restart **5/5**, autoload **6/6**;
saved-config validation **7/7**, runner exit **0** (`scratch/gui_ux4asb4v/`).
All GUI validation used disposable profiles.

## Pre-PR audit (2026-10-31)

Audited the pending appearance, Report view/layout and assembly-test changes,
including command registration, lifecycle/quit ordering, native material writes,
transaction ownership, source-document isolation, Qt lifetime/failure handling,
profile isolation, pure imports, icons/licenses, metadata and specification
consistency. Package and test Python files compile; `git diff --check` is clean.

Three appearance findings were fixed with regressions:

- A failed selection query must not be treated as an empty selection and colour
  the model. The appearance query now distinguishes failure and returns no targets.
- A pending application-wide transaction, even with no pending document edits,
  must not be joined or closed by colouring. Native and stub checks now cover it.
- Failed panel construction must not publish an incomplete dock. It is removed
  and a later refresh can retry successfully.

Validation on the audited sources:

- **528/528 headless**, no failures/errors/skips, with both FreeCAD's Qt shim and
  plain PySide6 aliases; **15** appearance tests. Validator **10/10**.
  Logs: `scratch/audit_headless.log`, `scratch/audit_ci_alias_headless.log`.
- Real FreeCAD 1.1.4: smoke **31/31**, sketch **20/20**, features **51/51**,
  assembly tree **104/104**, appearances **38/38**, Report view **7/7**, saved
  Report view autoload **3/3**, five-tab capture complete, quit-cancel **16/16**,
  discard **9/9**, relaunch **5/5**, autoload **6/6**, crash **2/2**, recovery
  **3/3**, native dark/light theme **22/22 each**, saved-config checker **7/7**.
  Evidence: `scratch/gui_fig8tobl/`.
- That initial combined GUI runner exited **1**: Orientation reproduced its
  earlier two pointer-setup failures (**82/84**), and orbit's post-leave response
  comparison failed because restoring stock docks changed viewport dimensions.
  The harness now uses the target widget's screen when positioning the pointer,
  and compares native orbit at the same viewport size as its baseline. Requested
  and actual pointer coordinates and orbit dimensions/angles are recorded.
- After those harness fixes, a bounded rerun passed Orientation **84/84** and
  orbit **49/49**, exit **0**, `scratch/gui_ob8370fs/`. All 18 individual suites
  therefore passed on the audited production sources; the initial combined run
  must not be described as a clean pass. Production Space routing/orbit code was
  not changed. This supersedes the earlier open pointer-test setup issue below.

Hosted Windows/Ubuntu results are available through the PR checks; local runs
alone do not establish hosted status. No new preference/backup contract or
release version is introduced. No remaining actionable finding was identified
in the reviewed changes. The original intermittent assembly freeze remains
unreproduced and unresolved; the passing triangle test does not establish a fix.

## Appearance unit tests in CI (2026-10-31)

The existing Windows/Ubuntu workflow already runs `Test25Appearances` through
the full headless suite. Expanded its coverage from **8 to 12 tests**, adding
component-only material writes (source and sibling unchanged), transaction abort
and application-transaction cleanup after a second-target failure, deferred
startup/cancellation, and idempotent quit/Cancel restoration for open/closed docks.
No workflow or production-code change was needed.

- Full headless suite **525/525**, no failures/errors/skips; GUI result-validator
  tests **10/10**. Log: `scratch/appearance_ci_headless.log`.
- All **12/12** appearance tests also passed with plain PySide6 aliases in an
  isolated scratch venv, exercising the Qt import path used without FreeCAD's
  shim in CI. This was local Windows execution, not a hosted Ubuntu run.
- `git diff --check` is clean. Hosted CI has not been triggered for these
  unpushed working-tree changes. Native rollback/rendering/Undo/persistence remain
  covered by the previously recorded real-FreeCAD GUI tests; the unit tests
  verify the abort protocol rather than simulating native rollback.

## Preserve closed Report view at startup (2026-10-31)

JellyJams no longer forces a closed Report view open when arranging Tasks and
Report view. Hidden Report view docks are excluded from placement, including
delayed startup passes. An already open Report view still docks below Tasks;
explicit open/close remains available. No FreeCAD auto-show-on-message setting
or other preference is changed. To save a closed startup layout, close Report
view in another workbench before entering JellyJams.

The closed-report Cancel regression also exposed late native hiding of general
toolbars after the first restore. The second restore now re-shows the same
toolbars JellyJams originally hid, preserving every other toolbar's current
visibility. Generation guards still protect quick reentry. Initial Cancel runs
failed the stock-toolbar check; after this fix the complete check passes.

- Headless **521/521**, no failures/errors/skips; validator **10/10**. Three new
  regressions cover closed Report view, delayed closure, and late toolbar hiding.
- Real FreeCAD 1.1.4: Report view **7/7**, native relaunch with JellyJams autoload
  **3/3**, smoke **31/31**, actual quit-cancel **16/16**, discard **9/9**, relaunch
  **5/5**, autoload **6/6**, saved-config checker **7/7**. Final runner exit **0**;
  evidence `scratch/gui_bgy37a3i/`. The quit-prompt check explicitly requires
  Report view to remain closed during the prompt and after Cancel.
- All GUI runs used throwaway `-u` / `-s` configs. No real profile was written.
  `git diff --check` is clean. No persistent override or recovery format changed.

## Appearances browser (2026-10-31)

Implemented the requested colouring tab using the official SOLIDWORKS Help
topics linked and mapped in [appearances.md](specs/appearances.md). Open
**JellyJams > Appearances**, or its tab beside Tasks. Category browsing and
102 original sphere previews cover Plastic, Metal and Paint. Double-click
applies a preset to selected faces/objects or the visible model with no
selection; custom RGB, finish and transparency can be applied explicitly.

Assignments use native FreeCAD view materials and one undo transaction. Face
edits retain unselected faces; component colours use local link overrides and
leave their source and siblings unchanged. Invalid edits do nothing; a failed
multi-object operation rolls back. User-applied colours remain ordinary FCStd
view properties. The dock/timer are removed before stock layout restoration on
leave and quit and re-created after Cancel. No new preference override or backup
format was introduced. Browser selections use the existing light/dark palette
inside the main-window stylesheet block, including unfocused item selections.

- Headless **518/518**, no failures/errors/skips. Includes 8 appearance tests
  plus new module/API checks. GUI result-validator tests **10/10**.
- Real FreeCAD 1.1.4, final dark/native-profile appearance regression:
  **37/37**; smoke **31/31**, quit-cancel **16/16**, discard **9/9**, relaunch
  **5/5**, autoload **6/6**, and saved-config checker **7/7**. Runner exit **0**.
  Evidence: `scratch/gui_w8pa5dp_/`.
- Fresh native Light profile: **37/37**, exit **0**;
  `scratch/appearances_light_final_cepzltza/`. Panel screenshots in both folders
  were visually inspected. All GUI runs used disposable `-u` / `-s` profiles.
- The native GUI checks cover real thumbnail double-click, face/body assignment,
  source-safe link overrides, native Undo/Redo, atomic abort, save/reopen,
  reentry and dock cleanup. FCStd colour serialization is checked within its
  8-bit channel precision; an earlier exact-float comparison correctly failed
  and the persistence assertion now accounts for that format.
- `git diff --check` is clean. No release/version bump or commit was requested.

Scope limits: native Phong finish approximations, not textures, scenes, decals,
RealView, saved custom libraries or full SOLIDWORKS appearance inheritance.
Whole-object assignment explicitly replaces existing face colours; per-face
linked-instance overrides are not supported. Drag-and-drop assignment and
physical-mouse interaction were not implemented/verified; the UI offers Apply
and double-click. The unrelated assembly-freeze report below remains unresolved.

## Unresolved freeze after creating an assembly (2026-10-30)

The user reported FreeCAD becoming unresponsive after New Assembly and clicking
the small expand/collapse triangle beside `Assembly1`. The screenshot shows an
empty active assembly with Origin and Mates children, plus an empty `Unnamed`
document. The original process (PID 38228) was observed as unresponsive, but
exited before its stack could be captured. No root cause or runtime fix is
established; this report remains **open**.

- Two exploratory runs in fresh scratch profiles completed without a freeze:
  64 mixed tree operations and 200 triangle clicks across Assembly and Origin.
  These probes did not assert every transition and do not establish a fix.
- Added `gui_assembly_tree.py` and runner suite `assembly_tree`: a fresh assembly
  with `Unnamed` still open, selected assembly, 100 real triangle clicks on the
  Assembly and Origin branches, every transition checked after an event-loop
  turn, and the workbench/active assembly checked at the end. FreeCAD 1.1.4:
  **104/104 passed**, exit 0 (`scratch/gui_itzif2ut/`). Partial JSON is saved
  before each click; periodic Python stack snapshots and a final screenshot
  accompany the result. The test uses model indexes for FreeCAD's native tree
  items; earlier test drafts hit deleted generic Qt item wrappers and are not
  evidence of the user's hang.
- Headless **506/506**, no failures/errors/skips; GUI runner validator **10/10**.
  No production code or real user/system profile was changed. Clean-profile
  passing results do not rule out a profile-dependent or intermittent native
  hang. Further diagnosis requires a stack from a live occurrence.

## GitHub PR and hosted CI (2026-10-30)

[PR #1](https://github.com/jus-kim/JellyJams/pull/1) contains the audit, theme,
orbit and native-crash regression work on `codex/theme-orbit-regression-coverage`.
Commits are authored and committed solely by `jus-kim <hi@jus.kim>`.

The first hosted Windows job passed 506 headless tests (3 installed-template
checks skipped because FreeCAD is absent) and all 10 runner tests. Ubuntu first
failed before test discovery because the hosted image lacked `libEGL.so.1`.
The workflow now explicitly installs `libegl1` and `libopengl0` on Linux and uses
maintained checkout/setup-python v7 actions. The corrected hosted push run
[41057025971](https://github.com/jus-kim/JellyJams/actions/runs/41057025971) passed
on both Windows and Ubuntu: 506 headless tests with the same 3 expected template
skips, plus all 10 runner tests. Current results are also available in the
[PR checks](https://github.com/jus-kim/JellyJams/pull/1/checks). The local GUI
results below remain Windows FreeCAD 1.1.4 results.

## Native crash after extrusion — orbit watcher fix (2026-10-30)

The orbit change below introduced a native crash. The user reported it after
extruding and orbiting a body; Windows recorded it at **07:35:49 America/Toronto**
with exception **0xc0000374**. The original dump was analyzed locally. It shows
FreeCAD resetting a Part Design edit and destroying its task dialog, a focus-change
signal calling Python, and PySide child traversal/QObject type wrapping failing.

- Root cause: the new orbit watcher directly scanned the Qt widget tree from
  `focusChanged`, which FreeCAD emits while native task widgets are being destroyed.
  A Python exception guard cannot contain this native failure.
- Before-fix reproduction crashed on the **first** Pad OK click with the same
  exception and matching relevant native stack offsets (`scratch/feature_crash_6ihakdnp/`).
  After deferring discovery, the same reproduction completed **20/20**, exit 0
  (`scratch/feature_fixed_scooeom0/`).
- Focus callbacks and initial installation now only schedule/coalesce a zero-delay
  discovery timer, capturing no focus widgets. Uninstall cancels both timers.
  The orbit response correction and native mouse controls are retained. No
  preference, backup format or recovery file was changed by the fix.
- Headless **506/506**, no failures/errors/skips; GUI-result validator **10/10**.
  The new unit regression checks deferred/coalesced discovery and cancellation.
- Real FreeCAD orbit regression: **49/49**, including 20 native Pad accept-and-orbit
  cycles (`scratch/gui_zy_27jqn/`, runner exit **0**). Orbit response, native pan/
  zoom, modifier changes and cleanup checks remain passing.
- Sketch **20/20**, feature integration **51/51**, smoke **31/31**, quit-cancel
  **16/16**, discard **9/9**, relaunch **5/5**, autoload **6/6**, crash **2/2**,
  recovery **3/3** and saved-config checker **7/7** also passed
  (`scratch/gui_bbes_4vn/`). That first combined run exited 1: its orbit cleanup
  check injected a synthetic drag before deferred installation had an event-loop
  turn. The harness now waits for installation; the separate 49/49 rerun passes.
  All 20 feature-close/orbit cycles passed in that first run too; no native crash
  occurred with the fix.
- `git diff --check` is clean. Actual user/system config modification times and
  sizes remain unchanged; the original crash dump is preserved. Details and dump
  provenance: `scratch/crash_investigation_2026-10-30.md`.

The older orbit results below did not cover native feature task-panel teardown
and therefore did not establish safety for the workflow that crashed.

## Middle-button orbit follow-up (2026-10-30)

The user reported stiff model rotation, especially unlike SolidWorks. Native
FreeCAD uses viewport width for X normalization and height for Y. Tests confirmed
that changing orbit modes alone did not fix the resulting ultrawide imbalance.

- On a 3571×902 viewport, a 100-pixel native Rounded Arcball drag produced about
  **5.82° horizontally / 24.06° vertically**. With balanced orbit input it produced
  about **23.91° / 24.06°**. The correction passed the equal-response check in all
  five native orbit modes at both normal and ultrawide sizes.
- `orbit_rules.py` provides pure drag-coordinate logic; `orbit.py` forwards balanced
  middle-drag coordinates to FreeCAD's own engine. It preserves native pan, zoom,
  middle clicks and modifier transitions. It leaves orbit/pivot/sensitivity
  preferences unchanged. Cursor-warp navigation bypasses the correction.
- `navigation` owns installation/removal through its existing lifecycle. Filters,
  focus watcher and discovery timer are removed on leave/quit and reinstalled after
  cancelled quit. Removing a transformed drag releases native orbiting without
  moving the camera. No persistent override or backup key was added.
- Headless: **505/505**, no failures/errors/skips. Covers aspect ratios, negative
  motion, resize/degenerate dimensions, modifier deltas, idempotent hook removal
  and runtime cleanup during recovery. GUI-result validator: **10/10**.
- Real FreeCAD 1.1.4: orbit **29/29**, smoke **31/31**, quit-cancel **16/16**,
  discard **9/9**, relaunch **5/5**, autoload **6/6**, crash **2/2**, recovery
  **3/3**, saved config **7/7**. Lifecycle checks additionally require the orbit
  hook to disappear inside the quit prompt and reappear after Cancel/autoload.
  The focused GUI runner exited **0**. Evidence: `scratch/gui_t3tc5rfa/`.
- `git diff --check` is clean. The tests measure real FreeCAD camera response to
  Qt mouse/key events; exact SolidWorks feel and physical mouse latency are not
  verified. The separate orientation pointer-placement issue below remains open;
  this focused run did not rerun that suite.

## Dark sketch visibility follow-up (2026-10-30)

The widget-only theme fix below left JellyJams' viewport light, making FreeCAD
Dark's pale sketch cursor overlays hard to see. That behavior was incomplete and
is superseded by [D-20](decisions.md#d-20-match-viewport-and-sketch-colors-to-the-native-theme-too).

- Widget and viewport palettes now share `theme.is_dark()`. Dark mode uses a dark
  gradient, bright blue unconstrained geometry, green fully constrained geometry,
  pale construction geometry and white/grey driving/reference dimensions.
- The same 14 managed View keys, types and persisted backup format are retained.
  No application theme setting, new backup key or real user profile is changed.
- Headless: **498/498**, no failures/errors/skips. Added dark viewport contrast
  checks and custom-value/absent-key exact restore plus fresh-module crash recovery.
  Result-validator tests: **10/10**.
- Actual FreeCAD 1.1.4, separate native Dark/Light scratch profiles: **22/22 each**.
  Tests now open a real sketch and assert the rendered pixels for unconstrained,
  blocked and construction geometry, driving/reference dimensions and background.
  All 14 color keys restore their original presence/type/value after leaving.
  Rendered sketch images were inspected. Evidence: `scratch/gui_nrn1dimj/`,
  `theme_dark.json`, `theme_light.json` and `<mode>_sketch.png`.
- Other actual GUI checks passed: smoke **31/31**, quit-cancel **16/16**, discard
  **9/9**, relaunch **5/5**, autoload **6/6**, crash **2/2**, recovery **3/3** and
  saved-config checker **7/7** (`scratch/gui_nrn1dimj/`). `git diff --check` is clean.
- **Open GUI-test issue:** orientation was **82/84**, so the combined runner
  exited **1**, not a clean pass. The first run hit pointer/Pad Space assertions;
  a separate repeat (`scratch/gui_n96gzor7/`) failed the two Pad pointer-over-view
  checks. Their pre-key diagnostic was `under_pointer: None`, so the focused
  check box received Space rather than the view. A bounded pointer-settle wait
  did not resolve this (`scratch/gui_f9dacr2a/`) and was removed. The pointer setup
  needs investigation; do not claim all keyboard GUI acceptance checks pass on
  this change. No production Space-routing behavior was changed by this fix.

## Dark/light theme follow-up (2026-10-29)

The user reported a light ribbon/tree/dock area mixed with FreeCAD Dark's native
menus, property editor and Start page, and explicitly chose to have JellyJams
follow FreeCAD's dark/light theme. The previous look spec accepted that mixture;
that policy is superseded by this change.

- `palette.py` now defines a dark widget palette alongside the existing light
  palette. `theme.widget_colors()` compares the native menu bar's effective
  background/text luminance, outside JellyJams' styled scope, to choose the mode.
  Repeated activation cannot read its own override and flip modes.
- Ribbon, tree, dock titles and JellyJams panels use that palette. Orientation
  and Sketch context popups use the same choice and refresh it on opening.
- Only the main-window's existing marked stylesheet block and JellyJams-owned
  popup stylesheets are changed. The application stylesheet/palette and native
  Theme/StyleSheet preferences are untouched. No mode preference or backup key
  was added. Viewport/sketch drawing colors remain the existing independent colors.
- Headless: **496/496**, no failures/errors/skips, including new dark-palette
  contrast checks, dark/light/dark repeated apply/restore and Sketch popup colors.
  Orientation's dark-theme assertion now requires readable light text on dark.
- Actual FreeCAD 1.1.4: `gui_theme.py` with native FreeCAD Dark and FreeCAD Light
  in separate disposable profiles: **16/16 each**. Native theme loading, ribbon
  surface/text, dock titles, Orientation/Sketch popup surfaces, unchanged native
  menu/application stylesheet/theme preferences and exact restore all passed.
  Screenshots were inspected in both modes. Local evidence:
  `scratch/gui_f75vcffs/theme_dark.json`, `theme_light.json` and their screenshots.
- Smoke **31/31**, orientation **84/84**, quit-cancel **16/16**, discard **9/9**,
  relaunch **5/5**, autoload **6/6**, and saved config **7/7** also passed on the
  theme-following code. The theme/lifecycle runner exited 0.
- Feature integration **51/51** and all five tab captures also passed after this
  change (`scratch/gui_uuzahgto/summary.json`). The result-validator suite remains
  **10/10**; `git diff --check` is clean.

The GUI runner includes `theme_dark` and `theme_light` in its default suites;
those tests seed only scratch XML configs before launching FreeCAD. Tests never
change the user's real theme preferences.

## 2026-10-29 audit

The repository already contained 489 headless tests and GUI acceptance scripts;
it had no CI workflow. The tests were strongest around lifecycle, settings and
orientation. Import/API checks and pinned ribbon tables accounted for a substantial
part of the headless count, and did not prove that individual tools worked in FreeCAD.
The earlier per-feature tables below describe the 2026-10-28 baseline; the results
and added coverage in this section supersede their statements about absent GUI tests.

### Confirmed defects fixed

1. **Drawing sheet not opened (high impact).** Make Drawing created a drawing and
   saved its projections, but left the 3D window active. `drawing_common` called
   `page.ViewObject.doubleClicked()`. FreeCAD 1.1.4 gates the entire handler on
   TechDraw's `SwitchToWB`, which JellyJams sets false. This also affected the shared
   opener used by sheet-sketch return and export preparation. The helper and export
   fallback now call `ViewObject.show()`, which opens/raises the sheet directly.
   A new headless regression and a real Make Drawing/Drawing-tab check cover it.
   The matching [FreeCAD source](https://github.com/FreeCAD/FreeCAD/blob/4fd3bf320d9566a27e60069fc8387448aaa3a094/src/Mod/TechDraw/Gui/ViewProviderPage.cpp#L265)
   confirms the preference gate.
2. **Unreadable dock titles (medium impact).** A full-window capture showed white
   Model/Tasks/Report titles against the light background. FreeCAD's custom
   `Gui::OverlayTitleBar` children bypass the existing `QDockWidget::title` rules.
   The main-window stylesheet now scopes the palette foreground/background to those
   children too. The real GUI checks all five stock title-widget foregrounds;
   no FreeCAD-owned widget receives its own stylesheet.
3. **No automatic regression gate (medium impact).** Added GitHub Actions on push,
   pull request and manual dispatch for Windows/Ubuntu, Python 3.11, PySide6 6.8.3.
   Hosted execution has not been run from this local audit. It exercises stubbed
   FreeCAD APIs; installed-template tests skip without FreeCAD resources.
4. **Autoload toolbars restored late (medium impact).** A repeat run failed the
   six-second startup check with stock toolbars visible; a second pre-fix run
   reproduced it. The delayed layout passes previously re-docked panels only.
   They now also hide newly visible non-kept toolbars, record each once for restore,
   and stop when another workbench is active or the activation generation changes.
   Three headless regressions cover late bars, restore, stale timers and the
   interval before the next workbench calls `Deactivated()`.

### Verification and additions

- Baseline headless: **489/489**, no skips. After the fixes and new regression:
  **493/493**, no skips (one drawing-opener and three layout regressions added).
  A separate venv also passed the original 489 with the
  PySide6 alias fallback, rather than FreeCAD's PySide shim.
  The final 493-test suite also passed with the PySide6 alias and FreeCAD resources
  deliberately removed: **3 expected template skips**, no failures or errors.
- New GUI result-validator suite: **10/10**. It rejects empty/incomplete results,
  exceptions, failed/missing check statuses and incomplete tab captures.
- Added `tests/run_gui.py`: unique scratch configs, sequential processes,
  per-process timeout, exit-code and JSON checks, saved-config inspection and a
  machine-readable summary. It uses fresh configs rather than copying the user's
  profile. Installed add-ons and caches remain shared, as with all `-u`/`-s` runs.
- Real GUI baseline rerun: smoke **31/31**, sketch first **20/20**, orientation
  **84/84**, cancel **16/16**, discard **9/9**, after **5/5**, autoload **6/6**;
  saved config **7/7**. All five tabs rendered with counts **21/22/22/13/31**.
- New real feature suite passed **51/51** after the fixes. It checks all
  custom and relation/mate command IDs are registered and no ribbon entries are
  skipped; relation Horizontal/Delete clicks; real Sketcher Centerline/Midpoint
  processing; Make Drawing, linked projections, Drawing context, scale and text;
  Surface Finish Cancel/OK and Weld Symbol OK; SVG Insert Picture command/OK; single/multiple
  PDF and DXF export; New Assembly, Rotate Component start/stop, Add Mate panel and
  Parallel button/OK with a real joint, sheet projection changes and Sheet Properties
  Cancel, file component insertion and grounding.
- New actual abrupt-exit/restart test: **2/2 + 3/3**. Parameters were saved while
  overrides were active, then the process exited without the quit guard. The next
  process restored every checked View value (including a custom background),
  navigation, shortcut presence/values (including a custom `T` for Top), and all
  three SwitchToWB states; all six backups cleared and the ribbon stayed hidden.
- Final-code full GUI runner: **exit 0**, all 11 suites successful, **227 GUI
  assertions plus 7 saved-config checks**, and complete five-tab captures. Local
  evidence is in `scratch/gui_txxaeigc/summary.json` and the per-suite JSON/logs in
  that directory. Autoload also passed a separate targeted post-fix run; the two
  earlier failures are retained in scratch rather than being silently discarded.
- PDF inspection: Poppler recognized the merged export as **two A4 pages** and
  rendered the first page with model geometry, title block, annotations and symbols.
  It emitted `No current point in closepath` warnings on both a direct native
  single-sheet export and the merged export; the cause is not established.

### Custom-button coverage after the audit

Every custom command registers, has resources and an original icon, and is covered
by the headless command contract. The table distinguishes real GUI command invocation
from tests of an internal helper; it does not promote helper checks into button tests.

| Tool | Real FreeCAD coverage | Still unverified |
|---|---|---|
| View Orientation, Normal To | Existing 84-check orientation script, key presses and view changes | Some split-view and unusual selection cases listed below |
| New Assembly | Command creates a separate document and assembly | Every coexistence/nesting/error case |
| Rotate Component | Command enabled for a floating link, starts and stops | Actual pointer drag and placement undo |
| Make Drawing | Command, deterministic format/file pickers, saved drawing, linked views, title block, sheet in front | Native file dialogs and every model/template variant |
| Sheet Properties | Command opens, Cancel closes; helper changes group/page projection | Editing every field through the panel, format change gestures |
| Insert Picture | Command reads an SVG from a patched file picker, panel opens and OK keeps it | Raster inputs, resize/drag, Cancel after an early transaction commit |
| Surface Finish | Command, Cancel removes the object, OK keeps it | Every editable field and on-sheet double-click |
| Weld Symbol | Command, panel and OK, symbol created | Pointer placement, arrow following through save/reload, every weld form |
| Projected View | Helper adds a real Left projection | Command pick mode and every direction |
| Scale | Helper changes a real projection group's scale | Popup choice and custom-input gestures |
| Text | Helper creates a real multiline annotation | Sheet pick and modal editor gestures |
| Centerline, Midpoint Line | Processing modes modify real Sketcher geometry/constraints | Full command + pointer drawing + end gesture |
| Line/Rectangle/Circle/Arc/Polygon on sheet | Headless helpers and resources | Full edit/frame/undo workflow in FreeCAD |
| Line Format | Headless selection helper/resources; native panel terminology and ISO preset activation on both hosts (2026-11-03) | Pointer-driven preset selection and the complete edit/undo workflow |
| Save as PDF, Export DXF | Helpers produce real single/multi-sheet PDF and DXF; PDF independently rendered | Export button + native save dialog, DXF round trip, merge fallback collisions |
| Diagnostics | Headless formatting/resources | Opening and copying from the live dialog |

Add Relations and Add Mate are selection-driven panels rather than custom command
IDs. Horizontal/Delete and Parallel/OK now have real button checks; the complete
relation/mate matrices remain headless-only.

### Remaining limits and open findings

- **Native page double-click remains gated by FreeCAD.** The fixed JellyJams
  helper opens sheets, but holding `SwitchToWB=false` also makes FreeCAD's own
  tree double-click a no-op in 1.1.4. Use the page's native **Show Drawing** context
  action to reopen an existing sheet. A replacement tree gesture is not implemented
  by this audit; the three-preference exact-restore contract is unchanged.
- Registration and ribbon completeness are checked for every entry; **every native
  command has not been functionally exercised**. Individual Part Design features,
  all relation/mate selection combinations, dimension/section/detail workflows,
  motion study, sheet-sketch pointer tools, every flyout variant and file dialogs
  still need more end-to-end coverage. Some new tests drive the shared helper
  directly and do not prove pointer interaction.
- Full-window `QWidget.grab()` images showed 3D framebuffer corruption, so they
  cannot certify viewport appearance. The ribbon captures were readable; independent
  exported PDF rendering was usable. GPU/driver behavior was not diagnosed.
- Only FreeCAD **1.1.4 on Windows** was exercised. Hosted CI, Addon Manager install,
  macOS/Linux GUI, other FreeCAD releases, unusual profiles/add-ons and every crash
  interruption point remain unverified. The suite uses fixed timer delays.
- Existing known limitations below remain, including shortcuts registered after
  activation and early commits of Insert Picture's persistent undo step.

No release bump, commit or push was made. Scratch configs, documents, logs and
screenshots are git-ignored. See [testing.md](testing.md#automated-runner-and-ci-2026-10-29)
for the reproducible commands.

## Contents

- [2026-10-29 audit](#2026-10-29-audit)
- [Test results](#test-results)
- [How to read the tables](#how-to-read-the-tables)
- [Area summary](#area-summary)
- [Feature status by area](#feature-status-by-area)
- [Known gaps and limitations](#known-gaps-and-limitations)
- [Missing SolidWorks features (roadmap)](#missing-solidworks-features-roadmap)
- [Updating this page](#updating-this-page)

## Test results

| Suite | Environment | Result |
|---|---|---|
| [`tests/test_headless.py`](../tests/test_headless.py) | FreeCAD 1.1.4 bundled Python 3.11, stubbed `FreeCAD` / `FreeCADGui` ([`tests/headless_stubs.py`](../tests/headless_stubs.py)), Qt offscreen | **489 tests, all pass**, 0 skipped, exit code 0 (two runs, the same result). |
| [`tests/gui_orientation.py`](../tests/gui_orientation.py) | Real FreeCAD 1.1.4 GUI, Windows, throwaway `-u`/`-s` configs | **84 / 84** checks, `errors` empty ([testing.md](testing.md#gui_orientationpy)): `Space` and `Ctrl+8` on the JellyJams commands with Hide/Show unbound and `Std_AlignToSelection` untouched; the panel (13 view buttons, Top, pinned Front, Esc, a Tab-focused button, click outside after the 0.3 s settle and the keyboard taken back before it); Normal To with nothing selected (status bar and tool tip, also from the panel's button), a face, a whole sketch, an origin plane, two faces, a curved face, a datum line, an origin axis and a sketch through a link, and from the Evaluate tab; readable under a white-text stylesheet; Space by pointer position in a Pad dialog, a floating Tasks dock and a dock made later, on the workbench selector, in sketch edit, in an undocked view (keyboard given back to it) and with the Start page in front; Hole Wizard with no solid and with two bodies none active; everything closed and given back on leave. Scripted steps 71.3 s. |
| [`tests/gui_sketch_first.py`](../tests/gui_sketch_first.py) | Real FreeCAD 1.1.4 GUI, Windows, throwaway `-u`/`-s` configs | **20 / 20** checks: sketch first with a plane selected (Pad from the new sketch, still JellyJams after Exit Sketch and after OK), with nothing selected (plane picker instead of "No sketch to work on", cancel leaves nothing pending), with a free sketch (used directly); editing a Pad stays in JellyJams; `Std_Workbench` still switches to Part Design. The script closes its documents before it quits and the run ends by itself (about 31 s). |
| [`tests/gui_smoke.py`](../tests/gui_smoke.py) | Real FreeCAD 1.1.4 GUI, Windows, throwaway `-u`/`-s` configs | **31 / 31** checks |
| [`tests/gui_lifecycle.py`](../tests/gui_lifecycle.py) `JELLYJAMS_LIFECYCLE_MODE=cancel` | same | **16 / 16** |
| `tests/gui_lifecycle.py` `JELLYJAMS_LIFECYCLE_MODE=discard` | same | **9 / 9**, and [`tests/check_saved_cfg.py`](../tests/check_saved_cfg.py) on the saved `user.cfg`: clean (**7 / 7** checks) |
| `tests/gui_lifecycle.py` `JELLYJAMS_LIFECYCLE_MODE=after` | same (relaunch with the discard profile) | **5 / 5** |
| `tests/gui_lifecycle.py` `JELLYJAMS_LIFECYCLE_MODE=autoload` | same (`AutoloadModule = JellyJamsWorkbench`) | **6 / 6** |
| [`tests/gui_tabs.py`](../tests/gui_tabs.py) | same | All five tabs render. Tool buttons per tab: Features 21, Sketch 22, Evaluate 22, Assembly 13, Drawing 31 (equal to plain buttons + flyouts + toggles per tab in [ribbon-content 2.6](specs/ribbon-content.md)). `errors` empty; the Report view has no JellyJams warning or error. This script records and screenshots; it asserts nothing. |
| Addon Manager install from `https://github.com/jus-kim/JellyJams` (branch `main`) | FreeCAD 1.1.4 | Not run yet (needs the published repository). |

Not run: a crash test (killing FreeCAD while JellyJams is active), any run on
Linux or macOS, any FreeCAD version other than 1.1.4, any non-English FreeCAD UI.

Every GUI script row above (`gui_orientation` to `gui_tabs`) was recorded on 2026-10-28 against
version 0.1.0, on FreeCAD 1.1.4 (Windows, PySide6 6.8.3), each run with its own throwaway `-u`/`-s`
configs; the headless suite was run on the same code.

The `gui_smoke`, `gui_lifecycle` and `check_saved_cfg` runs cover the Part Design and TechDraw
`SwitchToWB` overrides: their `SwitchToWB` checks cover all three modules (Assembly, Part Design
and TechDraw: false while JellyJams was active, absent again afterwards, as in the copied
profile), `backups_present` / `backups_cleared` cover the six backup keys, and
`check_saved_cfg.py` has 7 checks, `partdesign_switch_restored` and `techdraw_switch_restored`
among them.

`check_saved_cfg.py` also requires no override for `JellyJams_NormalTo`,
`Std_AlignToSelection`, `JellyJams_ViewOrientation` and `Std_ToggleVisibility`
(`no_jj_shortcut_overrides`, true in the recorded run).

## How to read the tables

**Status values**

| Status | Meaning |
|---|---|
| **Implemented** | Code is present and the behavior is asserted by automated tests at the level where it can fail: headless for parameter and pure logic, a GUI check on real FreeCAD where the behavior depends on a live window. |
| **Partial** | Code is present, but only part of the spec's acceptance criteria is asserted. The Notes column names what is not. |
| **Not verified** | Code is present, but no test exercises the user-visible behavior in FreeCAD. At most helper functions, command resources, imports or logic against fake documents are tested. The feature may work; nobody has checked it automatically. |
| **Missing** | Not implemented. No spec feature is in this state today: every spec area has its module under [`jellyjams/`](../jellyjams/). |

**"Verified by" notation**

- **H** = headless test in [`tests/test_headless.py`](../tests/test_headless.py), written as `Class.method` or `Class: method, method`.
- **G** = GUI check on real FreeCAD, written as `script: check_name`, where `check_name` is the first argument of `note(...)` in that script. `lifecycle/<mode>` means [`tests/gui_lifecycle.py`](../tests/gui_lifecycle.py) with `JELLYJAMS_LIFECYCLE_MODE=<mode>`. `check_saved_cfg` names are the keys of its `checks` output.
- "AC n" = acceptance criterion n of the spec named in the section heading.

Every module is also covered by the generated `Test02Hygiene.test_import_<module>` (imports under
the stubs) and, where it has a documented public API, `Test02Hygiene.test_api_<module>` (all
public names exist). These are not repeated in the rows below. The `Test22*` classes run module
code against fake documents and a fake transaction API; they check logic, not FreeCAD itself.

## Area summary

| Area | Spec | Overall | Headless coverage | GUI coverage (FreeCAD 1.1.4) |
|---|---|---|---|---|
| Core: packaging, lifecycle, quit guard, autoload, recovery, commands, document helpers | [core.md](specs/core.md) | Implemented; crash recovery, Diagnostics dialog and Qt filter Partial | Test01, Test03 to Test09, Test22DocumentHelpers | gui_smoke, gui_lifecycle (all modes), check_saved_cfg |
| Navigation and shortcuts | [core.md](specs/core.md) (A4, A5, D14, D15, 4.8, 7) | Implemented | Test12 | gui_smoke, gui_lifecycle, check_saved_cfg, gui_orientation (`Space`, `Ctrl+8`, Hide/Show) |
| Window layout | [window-layout.md](specs/window-layout.md) | Toolbars, restore, autoload Implemented; panel docking Partial | Test11 | gui_smoke, gui_lifecycle |
| Look | [look.md](specs/look.md) | Theme block and backups Implemented; rendered colors Not verified | Test10 | gui_smoke, gui_lifecycle |
| Ribbon engine | [ribbon-engine.md](specs/ribbon-engine.md) | Partial | Test13RibbonBuild, Test13RibbonText | gui_smoke, gui_tabs |
| Pointer tools and context memory | [quick-access.md](specs/quick-access.md), [ribbon-engine.md](specs/ribbon-engine.md) 3.4 | Implemented initial scope; undocked/split views and other task types need coverage | Test40QuickAccess | gui_quick_access |
| Ribbon content | [ribbon-content.md](specs/ribbon-content.md) | Structure Implemented; button behavior Partial; labels open for review | Test13RibbonModel | gui_smoke (`ribbon_matches_model`, `jj_plain_buttons`), gui_tabs, gui_orientation (`evaluate_ribbon_normal_to_*`) |
| Tree naming | [naming.md](specs/naming.md) | Partial | Test14 (rules), Test22TreeNaming (observer) | gui_smoke (Body, Sketch, Pad, origin planes) |
| Dialog terms | [dialog-terms.md](specs/dialog-terms.md) | Partial | Test18 (synthetic forms) | none |
| Sketching | [sketching.md](specs/sketching.md) | Sketch first and feature editing in JellyJams Implemented (of the sketch-first and edit-guard rules, only the Hole Wizard cases are also checked in GUI; the rest headless only); the rest Not verified | Test23SketchFirstRules, Test23SketchFirstFlow, Test23EditGuard; helpers for the rest | gui_sketch_first, gui_orientation (`hole_*`) |
| Orientation panel and Normal To | [orientation.md](specs/orientation.md) | Implemented; icons Partial; some criteria headless only (see [section 1](#1-acceptance-criteria-not-verified-in-gui) of the known gaps) | Test24Orientation, Test05 (`CmdType`), Test12 (`Space`, `Ctrl+8`), Test06 (menu, activation and deactivation steps), Test13 (Normal To on the Evaluate tab) | gui_orientation (84 checks), check_saved_cfg (`no_jj_shortcut_overrides`) |
| Add Relations panel | [relations.md](specs/relations.md) | Rules Implemented; panel Not verified | Test15 | none |
| Assembly | [assembly.md](specs/assembly.md) | `SwitchToWB` Implemented; rest Not verified | Test16, Test17SwitchPrefs, Test17Assembly, Test04Recovery, Test22AssemblySelection | gui_smoke, gui_lifecycle, check_saved_cfg (`SwitchToWB` only), gui_sketch_first (Part Design `SwitchToWB`) |
| Drawing sheet | [drawing-sheet.md](specs/drawing-sheet.md) | Templates Implemented; commands Not verified | Test19, Test22MakeDrawing, Test22SheetFormat, Test22InsertPicture | none |
| Drawing views | [drawing-views.md](specs/drawing-views.md) | Not verified | Test19 (helpers), Test22ViewLabels, Test22ViewDrag | none |
| Drawing symbols and export | [drawing-symbols-export.md](specs/drawing-symbols-export.md) | PDF merge Implemented; commands Not verified | Test18, Test19, Test20 | none |
| Icons and source hygiene | [core.md](specs/core.md) 2, [ribbon-content.md](specs/ribbon-content.md) 2.4 | Implemented | Test02, Test21 | none needed |

## Feature status by area

### Core

Spec: [core.md](specs/core.md). Code: [`Init.py`](../Init.py), [`InitGui.py`](../InitGui.py), [`lifecycle.py`](../jellyjams/lifecycle.py), [`quit_guard.py`](../jellyjams/quit_guard.py), [`recovery.py`](../jellyjams/recovery.py), [`commands.py`](../jellyjams/commands.py), [`diagnostics.py`](../jellyjams/diagnostics.py), [`qt_filter.py`](../jellyjams/qt_filter.py), [`doc_utils.py`](../jellyjams/doc_utils.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Headless entry `Init.py` (no GUI imports) | Partial | H `Test02Hygiene.test_init_py_is_headless` | Static import check only. Starting `FreeCADCmd` with the add-on installed (AC 4) is not automated. |
| Registration in `InitGui.py`: icon path, registration message, duplicate copy skipped with one warning, errors isolated, recovery always runs | Implemented | H `Test03InitGui`: `test_first_exec_registers_once_with_path_and_icon`, `test_second_exec_warns_once_and_keeps_one_entry`, `test_raising_add_workbench_reports_error_and_recovery_still_runs`, `test_workbench_methods_delegate_to_lifecycle_and_never_raise`; `Test01ReleaseMetadata.test_initgui_class_menu_text_and_registration`. G `gui_smoke: workbench_registered` | Duplicate copy under `Mod/` (AC 5) asserted headless only. Icon and tooltip in the workbench selector (AC 2) not asserted in GUI. |
| `package.xml`, single version source, CHANGELOG heading, trademark note | Implemented | H `Test01ReleaseMetadata`: all 10 tests | Addon Manager install: see [Test results](#test-results). |
| Initialize: environment line, warning on FreeCAD older than 1.1, command registration, once-per-process helpers, "JellyJams" menu with View Orientation, Normal To and Diagnostics, no toolbars | Implemented | H `Test06Lifecycle`: `test_initialize_order_and_once_per_process` (menu entries and their order), `test_initialize_warns_on_old_freecad`, `test_initialize_survives_failing_steps`, `test_real_activation_cycle_under_stubs` (menu of a real workbench instance). G `gui_smoke: jellyjams_menu`, `jellyjams_menu_gone`, `no_jj_toolbars`; `gui_orientation: space_bound_to_orientation`, `space_opens_panel` (Space works through the menu entry) | The environment line in FreeCAD (AC 7) and Initialize run twice (AC 9) are asserted headless only. The order of the three menu entries is asserted headless only (`gui_orientation: menu_has_normal_to` records it: View Orientation, Normal To, Diagnostics in the recorded run). |
| Activated / Deactivated: fixed step order, one failing step never stops the others, repeated or unpaired calls harmless | Implemented | H `Test06Lifecycle`: `test_step_tables`, `test_activation_fault_isolation`, `test_deactivation_fault_isolation`, `test_run_steps_reports_import_and_attribute_errors`, `test_repeated_and_unpaired_calls_are_harmless`, `test_real_activation_cycle_under_stubs` (also: Orientation panel closed on leave, the Space filter installed once and removed, `Space` / `Ctrl+8` set on the JellyJams commands and removed, `Std_AlignToSelection` untouched, Hide/Show unbound and restored); `Test24Orientation.test_leaving_jellyjams_closes_the_panel` (A6 installs the filter; D12 runs after tree naming and before the ribbon is hidden). G all gui_smoke checks; `gui_orientation: panel_closed_on_leave` | Double activation (AC 19) and fault isolation (AC 20) asserted headless only. AC 21 (leaving ends Note placement) is implemented as a deactivation step (`sheet_pick.cancel`) but has no test. |
| Quit guard: revert on Close before FreeCAD saves, no re-apply while a modal dialog is open, re-apply once after Cancel, nothing after Discard, `SwitchToWB` included | Implemented | H `Test07QuitGuard`: all 6 tests; `Test06Lifecycle.test_quit_tables_run_through_run_steps`. G `lifecycle/cancel` (16 checks), `lifecycle/discard` (9), `check_saved_cfg` (7), `lifecycle/after` (5) | A quit with no unsaved document (AC 22 without prompt) is not run separately; the Discard path checks the same `user.cfg` keys. The guard acts whenever JellyJams is active, also when a deferred layout never got applied. |
| Autoload at startup (layout deferred until the window is shown) | Implemented | H `Test11Layout`: `test_deferral_cancelled_by_revert`, `test_deferral_cancelled_by_workbench_switch`, `test_deferred_apply_runs_once_the_window_is_shown`, `test_deferral_timeout_warns_once_and_changes_nothing`. G `lifecycle/autoload`: all 6 checks | |
| Startup crash recovery of the six backups, documented backup formats, corrupt backup discarded with one warning | Partial | H `Test04Recovery`: all 10 tests; `Test10Look.test_viewport_recover`; `Test17SwitchPrefs`: `test_recover`, `test_recover_with_only_some_records`, `test_corrupt_records`; `Test03InitGui.test_first_exec_registers_once_with_path_and_icon` (recovery runs from `InitGui.py`) | Logic only, with stubbed parameters (AC 28, 29). Killing FreeCAD and restarting (AC 27, [window-layout](specs/window-layout.md) AC 23, [look](specs/look.md) AC 27 to 31) is not automated. |
| A leftover backup is never overwritten by a new apply | Implemented | H `Test12NavigationShortcuts.test_navigation_leftover_backup_not_overwritten`, `Test12NavigationShortcuts.test_shortcuts_leftover_backup_not_overwritten`, `Test10Look.test_viewport_leftover_backup_not_overwritten`, `Test17SwitchPrefs.test_pending_record_not_overwritten` | Parameter logic; AC 30 asserted headless only. |
| Command registration: 24 `JellyJams_*` commands, once per process, resources, `CmdType` only where declared (the two orientation commands, `Alter3DView`), `IsActive` never raises, missing icon gives an empty Pixmap, a sub-command index is ignored | Implemented | H `Test05Commands`: all 9 tests (`test_cmd_type_only_where_declared`, `test_base_command_contract`); `Test13RibbonModel.test_entry_ids_object_names_and_command_ids` (every command but `JellyJams_ViewOrientation` and `JellyJams_Appearances` is on the ribbon). G `gui_smoke: jj_plain_buttons` (plain ribbon buttons exist for `JellyJams_Diagnostics`, the five `JellyJams_*OnSheet`, `JellyJams_RotateComponent`, `JellyJams_MakeDrawing` and `JellyJams_MakeDrawing#1`) | `listCommands()` (AC 8) is not asserted in GUI. |
| Diagnostics (`JellyJams_Diagnostics`) | Partial | H `Test09Diagnostics`: all 4 tests | Row order, values, version parsing and block format asserted. The modal dialog, Copy to clipboard / "Copied", and the Report-view block (AC 11 to 15) are not verified in GUI. |
| Qt message filter ("render glyph failed") | Partial | H `Test08QtFilter`: all 8 tests | `test_real_install_self_test_and_enable_disable` installs a real Qt message handler under the headless Qt. AC 31 to 35 are not verified in GUI. |
| Document helpers: `doc_utils.transaction` (commit, abort or commit on error, join a pending step, close an application transaction the document left open, leave an outer transaction alone), `primary_model_objects` skipping 2D profiles | Implemented | H `Test22DocumentHelpers`: `test_transaction_closes_a_step_the_document_left_open`, `test_transaction_leaves_a_closed_step_alone`, `test_transaction_inside_an_outer_step_does_not_close_it`, `test_transaction_error_aborts_or_commits_and_closes`, `test_transaction_without_the_application_transaction_api`, `test_transaction_joins_a_pending_step`, `test_primary_model_objects_skip_2d_profiles` | Against a fake transaction API modeled on FreeCAD 1.1; FreeCAD's undo history itself is not inspected in GUI. |
| Hygiene: no "solidworks" in file names, ids and keys; three-line headers; constant values; pure modules; references between JellyJams modules resolve | Implemented | H `Test02Hygiene`: `test_three_line_header`, `test_no_solidworks_in_file_names`, `test_no_solidworks_in_identifiers`, `test_constant_values`, `test_pure_modules_import_no_freecad_or_qt`, `test_pure_modules_run_in_plain_python`, `test_cross_module_references_resolve` | AC 38 is checked through file names, `constants` values and command ids. Live objectNames are not scanned in GUI; headless, every ribbon button is checked for the `JellyJamsButton-` / `JellyJamsFlyout-` / `JellyJamsToggle-` prefix. |

### Navigation and shortcuts

Spec: [core.md](specs/core.md) steps A4, A5, D14, D15, section 4.8 and section 7 (no separate spec); `Space` and `Ctrl+8` also [orientation.md](specs/orientation.md) 2.4. Code: [`navigation.py`](../jellyjams/navigation.py), [`shortcuts.py`](../jellyjams/shortcuts.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| `NavigationStyle` = `Gui::SolidWorksNavigationStyle` while active, exact restore (absent key removed, user style restored), backup removed after restore | Implemented | H `Test12NavigationShortcuts`: `test_navigation_absent_key_round_trip`, `test_navigation_user_style_round_trip`, `test_navigation_leftover_backup_not_overwritten`, `test_backups_are_removed_after_restore`, `test_unreadable_backups_found_at_install_are_replaced`, `test_unreadable_backups_found_at_uninstall_change_nothing`. G `gui_smoke: nav_is_solidworks`, `nav_restored`, `nav_shortcut_backups_removed`; `lifecycle/cancel: nav_restored_inside_prompt`, `nav_reapplied_after_cancel`; `check_saved_cfg: nav_not_solidworks`, `nav_matches_expected` | The mouse behavior is FreeCAD's own navigation style; JellyJams only switches the setting. A user-set Blender style (AC 18) asserted headless only. |
| Shortcuts `F`, `Z`, `Shift+Z`, `Ctrl+B`, `Ctrl+1` to `Ctrl+7`, `Ctrl+8` (`JellyJams_NormalTo`), `Space` (`JellyJams_ViewOrientation`) (13 entries, [core](specs/core.md) 4.8); commands that own one of these keys at activation are unbound while active (Box Zoom on `Ctrl+B`, Hide/Show on `Space`); missing commands skipped; exact restore | Implemented | H `Test12NavigationShortcuts`: `test_shortcut_table`, `test_shortcuts_round_trip_with_user_override_and_conflict`, `test_shortcuts_leftover_backup_not_overwritten`, `test_shortcuts_unbind_clashing_commands_and_restore_them`, `test_space_moves_from_show_hide_to_view_orientation`, `test_space_is_left_alone_without_view_orientation`, `test_space_and_ctrl8_recovered_after_a_crash`, `test_user_ctrl8_on_align_to_selection_is_unbound_and_given_back`, `test_saved_cfg_check_looks_for_every_jellyjams_key`, `test_shortcuts_for_missing_commands_are_skipped`, `test_shortcuts_without_a_command_list_set_every_key`, `test_partial_shortcut_restore_keeps_the_backup`, `test_malformed_shortcut_entries_are_skipped`. G `gui_smoke: shortcut_fit`, `rebuild_owns_ctrl_b`, `no_shortcut_conflicts`, `shortcut_restored`, `boxzoom_key_restored`, `nav_shortcut_backups_removed`; `lifecycle/cancel: shortcut_restored_inside_prompt`, `shortcut_reapplied_after_cancel`; `check_saved_cfg: no_jj_shortcut_overrides`; `gui_orientation: space_bound_to_orientation`, `ctrl8_normal_to`, `align_to_selection_untouched`, `normal_to_action_has_ctrl8`, `toggle_visibility_unbound_while_active`, `space_back_to_toggle_visibility`, `orientation_shortcut_removed`, `normal_to_shortcut_removed` | Bindings are asserted; of the keys only Space and `Ctrl+8` are pressed in a 3D view (`gui_orientation: space_opens_panel`, `sketch_ctrl8_aligns_to_sketch`). `check_saved_cfg` inspects 5 of the 13 shortcut commands (`Std_ViewFitAll`, `Std_Refresh`, `Std_ViewIsometric`, `JellyJams_NormalTo`, `JellyJams_ViewOrientation`) plus `Std_AlignToSelection` (no override expected) and the `Std_ViewBoxZoom` and `Std_ToggleVisibility` unbinding; its key list is also checked headless (`test_saved_cfg_check_looks_for_every_jellyjams_key`). A user override such as `Std_ViewTop` = `T` (AC 18), a user who moved Hide/Show to another key and crash recovery of `Space` are asserted headless only. The clashing-command scan covers only the commands registered at activation (see [known gaps](#5-open-items-for-review)). |

### Window layout

Spec: [window-layout.md](specs/window-layout.md). Code: [`layout.py`](../jellyjams/layout.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Keep File, Edit, Workbench (case-insensitive containment); hide every other visible main-window toolbar; never touch toolbars inside docks | Implemented | H `Test11Layout`: `test_kept_toolbar_matching`, `test_apply_hides_visible_non_kept_toolbars_only`. G `lifecycle/autoload: stock_toolbars_hidden_after_show` | The exact visible set inside JellyJams (AC 1) is asserted only in the autoload run. |
| Tasks above Report view, docked right, not tabbed | Partial | H `Test11Layout`: `test_apply_docks_tasks_above_report_on_the_right`, `test_missing_tasks_dock_warns_and_still_hides_toolbars` | Not verified in GUI (AC 2 to 5, 20). The delayed re-dock passes (350, 1200, 3000 ms) have no test. |
| Exact restore on leave: only toolbars JellyJams hid get their old visibility, docks from the in-memory snapshot, 250 ms second pass, quick re-entry safe | Implemented | H `Test11Layout`: `test_revert_restores_only_what_was_hidden`, `test_revert_restores_docks`, `test_quick_reentry_is_not_undone_by_the_second_pass`, `test_revert_when_not_applied_is_silent`. G `gui_smoke: stock_toolbars_back`, `ribbon_hidden`; `lifecycle/cancel: stock_restored_after_leave`; `lifecycle/autoload: toolbars_back_after_leave` | Dock positions after leave (AC 8), the Sketcher/Assembly switch ordering (AC 7), a user-hidden toolbar (AC 10) and repeated cycles in GUI (AC 13) are not verified in GUI. |
| Autoload deferral | Implemented | See the autoload row under [Core](#core) | |
| Close guard for the layout | Implemented | See the quit guard row under [Core](#core) | |
| Crash: stock toolbars after FreeCAD is killed | Not verified | none | By design the layout keeps no on-disk state and relies on FreeCAD saving `MainWindowState` only on an orderly exit (spec 5.5). AC 23 not run. |

### Look

Spec: [look.md](specs/look.md). Code: [`palette.py`](../jellyjams/palette.py), [`theme.py`](../jellyjams/theme.py), [`viewport.py`](../jellyjams/viewport.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Single palette, exact values, WCAG 2.x contrast thresholds | Implemented | H `Test10Look`: `test_palette_values`, `test_luminance_contrast_and_packing`, `test_contrast_requirements` | Ratios are computed with the W3C relative-luminance formula (AC 36, 38). |
| Theme block on the main-window stylesheet: exactly one block, byte-exact removal, stale and truncated blocks, foreign changes survive, application stylesheet untouched | Implemented | H `Test10Look`: `test_theme_block_syntax_and_colors`, `test_theme_apply_remove_exact`, `test_stale_and_truncated_blocks`, `test_foreign_changes_survive_removal`, `test_raising_set_style_sheet_logs_error`. G `gui_smoke: theme_marker`, `theme_removed`; `lifecycle/cancel: not_reentered_inside_prompt`, `reapplied_after_cancel`; `lifecycle/autoload: theme_removed_after_leave` | `Preferences/MainWindow` unchanged (AC 2) is not asserted. |
| Rendered look of ribbon, panels, docks and model tree | Not verified | Screenshots `jellyjams_active.png`, `tab_<n>_<name>.png` (manual review only) | Pixel criteria AC 3 to 9 are not automated. The syntax test only checks that the selectors exist and that colors come from the palette. |
| 3D background gradient and sketch colors: 14 `Preferences/View` keys with persisted backup and exact restore | Partial | H `Test10Look`: `test_viewport_managed_keys`, `test_viewport_apply_restore_absent_keys`, `test_viewport_custom_values_and_type_presence`, `test_viewport_leftover_backup_not_overwritten`, `test_viewport_setter_failing_on_fifth_key`, `test_viewport_restore_failure_keeps_record`, `test_viewport_recover`. G `gui_smoke: backups_present`, `backups_cleared` | In FreeCAD only the presence and clearing of `OriginalViewColors` are asserted, not the 14 values (AC 16), the rendered gradient (AC 17) or the sketch colors (AC 19). `check_saved_cfg` does not compare the 14 View keys (AC 23, 26). |

### Ribbon engine

Spec: [ribbon-engine.md](specs/ribbon-engine.md). Code: [`ribbon.py`](../jellyjams/ribbon.py), [`ribbon_widgets.py`](../jellyjams/ribbon_widgets.py), [`ribbon_model.py`](../jellyjams/ribbon_model.py), [`ribbon_text.py`](../jellyjams/ribbon_text.py), [`icons.py`](../jellyjams/icons.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Dock `JellyJamsCommandManager` in the top area, no title bar, not movable; tab bar below; five tabs; Features first | Implemented | H `Test13RibbonBuild.test_dock_tabs_and_object_names`. G `gui_smoke: ribbon_dock_exists`, `ribbon_tabs`, `ribbon_visible`, `ribbon_has_buttons`; gui_tabs | Dock features, area and the start tab are asserted headless only. |
| Pages hold what the model resolves for the running FreeCAD (plain buttons, flyouts, toggles, separators per tab) | Implemented | H `Test13RibbonBuild.test_dock_tabs_and_object_names`. G `gui_smoke: ribbon_matches_model` | The GUI check compares with the model resolved from that FreeCAD's own command list, so it does not by itself prove that no command was skipped; its JSON records the skipped ids and substitutions without asserting them. |
| Button kinds, icon sizes, one-line names, composed tooltips (no HTML, no `&`) | Partial | H `Test13RibbonBuild`: `test_button_kinds_texts_and_tooltips`, `test_icon_stack_three_rows_column_by_column`; `Test13RibbonText`: all 5 tests | Headless uses stub command info for a few commands. Real FreeCAD tooltips and icons (AC 7 to 10) are only visible in the gui_tabs screenshots. |
| Enabled state follows FreeCAD's `isActive()` (450 ms refresh) | Partial | H `Test13RibbonBuild.test_enabled_state_follows_is_active` | The transition when a sketch opens and closes (AC 11) is not tested in GUI. |
| Flyouts: menu choice runs the variant, is remembered under `Mod/JellyJams/FlyoutChoices`, unknown stored value tolerated, titled flyouts keep their caption | Partial | H `Test13RibbonBuild`: `test_flyout_choice_runs_and_persists`, `test_remembered_choice_and_unknown_value`, `test_titled_flyout_keeps_its_title` | Persistence across a real restart (AC 14, 15) is not verified in GUI. |
| Toggle "Sketch" / "Exit Sketch" | Partial | H `Test13RibbonBuild.test_sketch_context_and_toggle` | AC 12 not verified in GUI. |
| Context tab switching: Sketch, Assembly, Drawing (transition only) | Partial | H `Test13RibbonBuild`: `test_sketch_context_and_toggle`, `test_assembly_context`. G `gui_smoke: assembly_tab_on_activate` | The drawing-sheet context (AC 19, 22) has no test at all; the sketch context and AC 21 are not verified in GUI. |
| Click dispatch: end a running Centerline / Midpoint Line, offer profile features to the open-sketch gesture, indexed entries, errors reported | Partial | H `Test13RibbonBuild`: `test_run_entry_dispatch_order` (with stand-in modules), `test_indexed_entry_runs_with_index` | AC 23 to 25 and 32 are not verified in GUI. |
| Built once; show twice harmless; hide; visibility guard; rebuild | Implemented | H `Test13RibbonBuild`: `test_show_twice_hide_and_visibility_guard`, `test_rebuild`, `test_unbuilt_ribbon_is_inert`. G `gui_smoke: ribbon_hidden`; `lifecycle/after: ribbon_not_visible`; `lifecycle/cancel: reapplied_after_cancel`; `lifecycle/autoload: ribbon_visible_after_show` | Showing the dock from the console outside JellyJams (AC 35) asserted headless only. Same button count after re-entry in GUI (AC 27) not asserted. |
| Command preload (`PartGui`, `SketcherGui`, `PartDesignGui`, `TechDrawGui`, Assembly command modules) and missing-command handling | Partial | H `Test13RibbonBuild`: `test_missing_commands_warning`, `test_assembly_modules_missing_only_logs` | AC 30 needs a fresh profile and is not run. |
| `JellyJams_RotateComponent` dynamic tooltip on its ribbon button | Not verified | none | AC 34. |

### Ribbon content

Spec: [ribbon-content.md](specs/ribbon-content.md). Code: [`ribbon_layout.py`](../jellyjams/ribbon_layout.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Five tabs, groups, separators, stacks; 81 plain buttons, 27 flyouts with 84 variants, 1 toggle, 167 distinct ids | Implemented | H `Test13RibbonModel`: `test_counts_ids_and_tabs`, `test_per_tab_counts_and_separators`, `test_stacks`, `test_entry_ids_object_names_and_command_ids`, `test_layout_primary_ids_are_the_command_set`, `test_layout_constructors_validate_input`; `Test13RibbonBuild.test_dock_tabs_and_object_names`. G `gui_smoke: ribbon_matches_model`; gui_tabs button counts per tab | |
| SolidWorks captions and one-line names | Implemented | H `Test13RibbonModel.test_labels_icons_and_indices`; `Test13RibbonText.test_one_line` | Only examples are asserted, not every caption of the tables (AC 6). Several labels are approximate mappings open for review ([ribbon-content](specs/ribbon-content.md) 2.8). |
| Each button runs the listed FreeCAD command | Partial | H the command ids of every tab are compared in `Test13RibbonModel.test_counts_ids_and_tabs` and `test_per_tab_counts_and_separators` | Clicking in FreeCAD (AC 7 to 9) is not verified. |
| Fallbacks (seven primary ids with an older id), missing commands skipped without gaps, Assembly modules missing, toggle degrading, empty groups vanish | Implemented | H `Test13RibbonModel`: `test_missing_commands_are_skipped_without_gaps`, `test_fallback_substitution`, `test_every_fallback_substitutes`, `test_assembly_commands_missing`, `test_toggle_degrades_and_empty_groups_vanish` | Pure logic. |
| Icons: FreeCAD's own icons at runtime, original icons for the `JellyJams_*` commands | Partial | H `Test21Icons.test_every_icon_exists_renders_and_is_clean`; `Test13RibbonModel.test_labels_icons_and_indices` (icon names) | Runtime icon lookup (AC 24) only visible in screenshots. |
| No duplicate registration when FreeCAD's Assembly workbench is opened after JellyJams | Not verified | none | AC 11. |

### Tree naming

Spec: [naming.md](specs/naming.md). Code: [`naming.py`](../jellyjams/naming.py), [`naming_rules.py`](../jellyjams/naming_rules.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Numbered part names (`Sketch1`, `Boss-Extrude1`, ...) | Partial | H `Test14NamingRules`: `test_numbered_names`, `test_tables`. G `gui_smoke: pad_sw_name`, `sketch_sw_name` | In FreeCAD only a Sketch and a Pad created from a script are checked. The other types (AC 4), numbering after manual renames (AC 5, 6), cancel (7), undo/redo (8), opened files (10), re-activation (11) are not verified in GUI. |
| Origin planes `Top Plane`, `Front Plane`, `Right Plane` | Partial | H `Test14NamingRules.test_fixed_names`. G `gui_smoke: origin_planes_sw` | Second and third body (AC 2) not verified in GUI. |
| Naming only while JellyJams is active | Partial | H `Test22TreeNaming.test_joint_type_change_renames_a_default_mate_label` (no rename while another workbench is active) | Observer logic with fake documents; AC 9, 23 not verified in GUI. |
| Assembly names: `Assembly1`, `Mates`, `Shaft<1>`, `(f) ` marker, mate names | Not verified | H `Test14NamingRules`: `test_components_and_fixed_marker`, `test_mate_bases`, `test_default_mate_labels`, `test_joint_type_word_labels`, `test_mate_label_worked_example` (rules only) | AC 12 to 17. |
| Component inserted with FreeCAD's New Part is named once its link target arrives; pending links survive undo/redo without renaming and are forgotten on delete or document close; a mate follows a joint type change | Partial | H `Test22TreeNaming`: `test_new_part_is_named_when_its_link_target_arrives`, `test_pending_links_wait_out_undo_and_are_dropped`, `test_joint_type_change_renames_a_default_mate_label` | Observer logic with fake documents, not verified in GUI. |
| Drawing names: `Sheet1`, `Sheet Format1`, `Standard 3 View`, direction names, `Dimension1`, existing-drawing refresh | Not verified | H `Test14NamingRules`: `test_standard_3_view`, `test_default_drawing_labels`, `test_tables` (rules only) | AC 18 to 22. |
| Renames postponed while a TechDraw tool runs (crash safety) | Not verified | none | AC 21. Implemented in `naming.py` (500 ms re-check using `fcgui.techdraw_tool_running()`). |
| No parameters written; named files open in plain FreeCAD | Not verified | none | AC 24, 25. |

### Dialog terms

Spec: [dialog-terms.md](specs/dialog-terms.md). Code: [`dialog_terms.py`](../jellyjams/dialog_terms.py), [`dialog_terms_data.py`](../jellyjams/dialog_terms_data.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| SolidWorks terms in 17 FreeCAD task dialogs (labels, group boxes, combo entries); widgets FreeCAD rewrites itself never written | Partial | H `Test18DialogTerms`: `test_catalog`, `test_relabel_and_no_second_write` | Asserted on synthetic forms built from real QWidgets with FreeCAD 1.1.4 objectNames, not on FreeCAD's own dialogs (AC 1 to 5, 11 to 20 not verified in GUI). |
| Projection check-box tool tips translated by FreeCAD's current text, again after a projection-type change | Partial | H `Test18DialogTerms.test_projection_tooltips_follow_freecad_text` | AC 13 not run in FreeCAD. |
| Combo safety rule (relabel only when the entry count matches 1.1.4) | Partial | H `Test18DialogTerms.test_combo_count_safety_rule` | AC 8 not run in FreeCAD. |
| Service: 250 ms check, no widget lookups while no task dialog is open, start/stop idempotent | Partial | H `Test18DialogTerms`: `test_process_once_is_idle_without_dialog`, `test_format_weight_and_service` | Timing and resilience in FreeCAD (AC 6, 7, 9, 10) not verified. |
| Scale-field fix (Section View, Aligned Section) | Partial | H `Test18DialogTerms.test_scale_field_fix` | AC 14, 16 not run in FreeCAD. |
| ISO 128 line-thickness presets row in Line Format | Partial | H `Test18DialogTerms`: `test_weight_presets_row`, `test_weight_presets_edge_cases`; G `gui_host_compatibility.py` on both hosts | Native row and preset activation verified on 2026-11-03; the full pointer-driven AC 21 to 23 workflow remains unverified. |
| Language independence | Not verified | none | AC 24. |

### Sketching

Spec: [sketching.md](specs/sketching.md). Code: [`sketch_edit.py`](../jellyjams/sketch_edit.py), [`sketch_gesture.py`](../jellyjams/sketch_gesture.py), [`edit_guard.py`](../jellyjams/edit_guard.py), [`context_sketch.py`](../jellyjams/context_sketch.py), [`sketch_tools.py`](../jellyjams/sketch_tools.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Sketch editing stays in JellyJams (TempoVis interception, identical function restored on leave) | Partial | H `Test06Lifecycle.test_real_activation_cycle_under_stubs` (identity restore with a stand-in `Show` module) | AC 1 to 6 not verified in GUI. |
| Feature from the open sketch | Not verified | H `Test19DrawingHelpers.test_sketching_helpers` (`is_profile_feature`); `Test13RibbonBuild.test_run_entry_dispatch_order` (dispatch with a stand-in gesture) | AC 7 to 11. |
| "Sketch" context icon on a planar face | Not verified | H `Test19DrawingHelpers.test_sketching_helpers` (`opacity_for_distance`, `popup_position`) | AC 12 to 20. |
| Centerline (`JellyJams_Centerline`) | Not verified | H `Test05Commands` (resources, `IsActive`) | AC 21 to 28. |
| Midpoint Line (`JellyJams_MidpointLine`) | Not verified | H `Test19DrawingHelpers.test_sketching_helpers` (`mirrored_end`) | AC 29 to 36. |
| Sketch first: Extruded Boss/Base, Extruded Cut, Revolved Boss/Base, Revolved Cut and Hole Wizard with nothing to use as the profile open a new sketch (plane picker, or on the selected plane or planar face) and run on Exit Sketch | Implemented | H `Test23SketchFirstRules`: `test_sketch_first_features`, `test_needs_new_sketch_truth_table`, `test_advance_truth_table`, `test_retargeted_command_survives_the_move_to_editing`; `Test23SketchFirstFlow`: all 39 tests. G `gui_sketch_first`: `a_no_warning_dialog`, `a_sketch_opened`, `a_sketch_on_selected_plane`, `a_pad_created_after_exit`, `a_pad_uses_new_sketch`, `a_no_pending_state`, `b_no_warning_dialog`, `b_plane_picker_open`, `b_waiting_for_plane`, `b_cancel_drops_state`, `b_no_pad_after_cancel`, `c_no_warning_dialog`, `c_pad_uses_existing_sketch`, `c_no_new_sketch`, `c_no_pending_state` | AC 40 to 42 and 44 in GUI (the status-bar text of 40 headless only). A planar face (43), a retarget while picking (45), an empty sketch (46) and a sweep with nothing selected (47) are asserted headless only, with a fake document. The press comes from `ribbon.run_entry`, as a click does, not from a real mouse click. The GUI run was recorded on 2026-10-28. |
| Sketch first, selection and solid rules: a selection of only bodies, origins, parts or groups is cleared and treated as empty; Extruded Cut, Revolved Cut and Hole Wizard start a sketch only when the target body holds a solid by FreeCAD's `Body::isSolid()` rule (a Part Design feature in its `Group`, its shape not looked at); without one, Extruded Cut and Revolved Cut go to FreeCAD's own refusal and Hole Wizard is refused by JellyJams (status-bar text for 6 s, warning, nothing runs), on a fresh press and while picking; with several bodies and none active (no target body) all three are left to FreeCAD, which asks for the body (no JellyJams text, nothing runs); a press while picking retargets only sketch-first features with the plane picker open (Extruded Cut, Revolved Cut and Hole Wizard not when the target body is known and has no solid), and a stale pick (no dialog) is dropped and the press handled fresh, its checks stopping once it is replaced; the status hint is cleared whenever the sketch-first is dropped and rewritten on a retarget; free sketches are counted in the target body (active body, else the only body) and only before the insert point | Implemented (the Hole Wizard cases also in GUI; the rest headless only) | H `Test23SketchFirstFlow`: `test_container_only_selection_is_cleared_and_treated_as_empty`, `test_container_selection_with_a_free_sketch_lets_freecad_use_the_sketch`, `test_containers_mixed_with_other_items_are_left_to_freecad`, `test_subtractive_features_without_a_solid_keep_freecads_refusal`, `test_subtractive_features_without_a_target_body_are_left_to_freecad`, `test_nothing_to_cut_needs_a_known_body`, `test_retarget_to_a_cutting_feature_without_a_known_body`, `test_has_solid_mirrors_freecads_is_solid`, `test_hole_refusal_names_the_command`, `test_hole_refusal_is_a_temporary_status_message`, `test_hole_refusal_while_picking_keeps_the_sketch_first_going`, `test_subtractive_feature_with_a_solid_starts_a_sketch`, `test_additive_features_start_a_sketch_in_an_empty_body`, `test_every_sketch_first_feature_starts_a_sketch`, `test_retarget_rewrites_the_status_hint`, `test_press_while_picking_retargets`, `test_retarget_to_a_cutting_feature_needs_a_solid`, `test_only_sketch_first_features_retarget_while_the_picker_is_open`, `test_stale_watch_chain_stops_once_its_intent_is_replaced`, `test_stale_plane_pick_is_dropped_and_the_press_handled_fresh`, `test_stale_plane_pick_is_dropped_when_the_fresh_press_needs_no_sketch`, `test_status_hint_cleared_when_a_check_fails`, `test_status_hint_cleared_when_a_press_inside_a_sketch_replaces_it`, `test_lone_inactive_body_is_the_target`, `test_no_target_body_with_several_bodies`, `test_sketches_after_the_insert_point_are_not_free`, `test_datum_after_the_tip_does_not_move_the_insert_point`, `test_rolled_back_body_starts_a_sketch_when_only_later_sketches_are_free`. G `gui_orientation: hole_without_solid_starts_nothing`, `hole_without_solid_hint`, `hole_two_bodies_no_needs_solid_text`, `hole_two_bodies_left_to_freecad` | AC 51 to 57, 59 and 61. Logic against a fake Part Design document. In FreeCAD 1.1.4 only the Hole Wizard cases are checked: in an empty body nothing is created and the status bar shows the JellyJams text (the Hole refusal of AC 52, not its Report-view warning), and with two padded bodies and none active FreeCAD asks for the body ("Active Body Required") with no JellyJams text (the Hole part of AC 61). Everything else in this row is headless only: whether FreeCAD's own insert-point rule, `isSolid()` and its "nothing to cut" refusal for Pocket and Groove match the fake document is **not verified**. |
| Feature editing stays in JellyJams (`FreeCADGui.activateWorkbench` wrapped; FreeCAD command strings, found up to `FRAME_SEARCH_DEPTH` frames above the wrapper, held one event-loop turn and dropped when an edit started; chain tracking under another add-on's wrapper) | Implemented | H `Test23EditGuard`: all 18 tests (chain tracking: `test_reinstall_under_a_foreign_wrapper_only_rearms`, `test_switch_through_a_foreign_wrapper_does_not_recurse`, `test_uninstall_leaves_a_foreign_wrapper_and_passes_through`, `test_guard_back_on_top_is_unwrapped_again`; frame search: `test_command_string_recognized_through_foreign_wrappers`, `test_python_callers_through_foreign_wrappers_pass_straight_through`, `test_command_string_beyond_the_search_depth_is_not_recognized`; AC 58 and 60 headless only); `Test06Lifecycle.test_real_activation_cycle_under_stubs` (wrapped while active, FreeCAD's function back after leaving). G `gui_sketch_first`: `a_still_in_jellyjams_after_exit`, `a_still_in_jellyjams_after_ok`, `d_edit_feature_stays_in_jellyjams`, `d_feature_dialog_open`, `d_user_switch_to_part_design_works` | AC 48, 49 in GUI. AC 50 (console call at once, identity after leaving, Part Design behavior from another workbench) asserted headless only. The workbench selector itself is exercised through `Std_Workbench` with the Part Design index, the command it runs. |

### Orientation panel and Normal To

Spec: [orientation.md](specs/orientation.md). Code: [`orientation.py`](../jellyjams/orientation.py), `BaseCommand.cmd_type` in [`commands.py`](../jellyjams/commands.py), the `Space` / `Ctrl+8` entries of [`shortcuts.py`](../jellyjams/shortcuts.py), the menu entries and the activation and deactivation steps in [`lifecycle.py`](../jellyjams/lifecycle.py).

Every GUI check named below belongs to `gui_orientation.py`, recorded on 2026-10-28 with all 84 checks passing (see [Test results](#test-results)), except `check_saved_cfg` in the last row.

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| `JellyJams_ViewOrientation` and `JellyJams_NormalTo`: resources with `CmdType` `Alter3DView`, active while the main window's active window is a 3D view (`getMainWindow().getActiveWindow()` has `getCameraNode`, `FreeCADGui.activeView()` only when that method is missing: docked, undocked, fullscreen or split; not with the Start page or a drawing in front; also with a sketch or another task dialog open), View Orientation toggles the panel, both in the JellyJams menu; View Orientation has no ribbon button | Implemented | H `Test24Orientation`: `test_commands`, `test_active_while_the_main_windows_active_window_is_a_3d_view`, `test_active_view_is_the_main_windows_active_window`, `test_active_view_falls_back_to_freecads_active_view`, `test_active_view_is_none_on_errors`, `test_the_mdi_area_does_not_decide_availability`, `test_command_toggles_the_panel`; `Test05Commands`: `test_cmd_type_only_where_declared`, `test_resources_menu_text_and_pixmaps`; `Test06Lifecycle.test_initialize_order_and_once_per_process`. G `gui_orientation: space_opens_panel`, `menu_has_normal_to`, `sketch_in_edit`, `sketch_commands_enabled`, `sketch_space_opens_panel`, `pad_dialog_space_in_view_opens_panel`, `view_undocked`, `undocked_commands_enabled`, `undocked_space_opens_panel`, `view_docked_again`, `start_page_commands_disabled`, `start_page_space_keeps_panel_closed` | AC 9, 10, 31 and 43; AC 9 and the no-document and drawing-sheet parts of AC 10 headless only (a stub main window); fullscreen and split views and `Ctrl+8` in the undocked view (AC 31) are not run in GUI. |
| Normal To: `Sketcher_ViewSketch` in a sketch with nothing (or only that sketch's elements) selected; otherwise exactly one pick: any single sub-element (face, edge, vertex; its shape not read), a whole origin plane or axis or datum (`DATUM_TYPES`) and a whole object that is one face or one edge run `Std_AlignToSelection`; a whole sketch or other 2D object turns the view in front along the placement of the path it was picked through (`GeoFeature.getGlobalPlacementOf` on the unresolved selection, links included; else its own global placement; a warning when turning fails); anything else (two picks, a whole body, feature or other solid, nothing) a hint in the status bar for 4 s and as a tool tip at the pointer, and nothing else | Implemented | H `Test24Orientation`: `test_normal_to_target`, `test_whole_object_types`, `test_normal_to_runs_its_target_or_shows_the_hint`, `test_normal_to_looks_straight_at_a_whole_sketch`, `test_look_at_sketch_turns_the_main_windows_active_window`, `test_sketch_rotation_follows_the_selection_path`, `test_sketch_rotation_falls_back_to_the_sketchs_own_placement`, `test_the_same_sketch_through_two_links_is_two_picks`, `test_normal_to_warns_when_the_view_cannot_turn`, `test_normal_to_hint_is_temporary`, `test_normal_to_hint_shows_at_the_pointer_too`, `test_normal_to_hint_tooltip_appears`. G `gui_orientation: normal_to_nothing_selected_keeps_view`, `normal_to_nothing_selected_hint`, `normal_to_nothing_selected_tooltip`, `normal_to_face_aligns`, `normal_to_whole_sketch_aligns`, `normal_to_origin_plane_aligns`, `normal_to_two_faces_keeps_view`, `normal_to_two_faces_hint`, `normal_to_curved_face_turns_view`, `normal_to_datum_line_turns_view`, `normal_to_origin_axis_turns_view`, `normal_to_linked_sketch_follows_link`, `sketch_normal_to_aligns_to_sketch`, `sketch_ctrl8_aligns_to_sketch` | AC 22 to 24, 32, 33, 39, 42, 44, 45 and 50; a straight edge (22), a sketch's own edges and another object's face in a sketch (23), a face and an edge, whole bodies, datum planes, moved bodies (39), single-face and single-edge objects (45), the warning (42) and the same sketch through two links (50) headless only, with fake selections, shapes, a fake 3D view and a stub `getGlobalPlacementOf`. Which single picks FreeCAD's `Std_AlignToSelection` really aligns to is **not verified** beyond the GUI checks named. |
| Normal To on the Evaluate tab (`JellyJamsButton-JellyJams_NormalTo`, in place of `Std_AlignToSelection`) | Implemented | H `Test13RibbonBuild.test_normal_to_button_on_the_evaluate_tab`; `Test13RibbonModel`: `test_labels_icons_and_indices`, `test_per_tab_counts_and_separators`, `test_entry_ids_object_names_and_command_ids`. G `gui_orientation: evaluate_ribbon_normal_to_is_jellyjams`, `evaluate_ribbon_normal_to_face_aligns` | AC 37; [ribbon-content](specs/ribbon-content.md) AC 9 and 28. |
| Panel `JellyJamsOrientation`: frameless tool window, 13 view buttons (Normal To first), unfolded box around Front, axonometric column, tooltips with the current key, buttons enabled from FreeCAD's `isActive()` on every open, missing commands disabled, built again when its widget was deleted | Implemented | H `Test24Orientation`: `test_tables`, `test_thirteen_view_buttons_in_their_places`, `test_tooltips_name_the_view_and_its_key`, `test_missing_commands_are_disabled`, `test_buttons_follow_the_commands_active_state`, `test_panel_is_built_again_when_its_widget_was_deleted`. G `gui_orientation: panel_has_13_view_buttons`, `panel_has_normal_to_button` | AC 4 in GUI; the grid positions (AC 5), tooltips (AC 12) and the enabled state (AC 13) headless only. |
| Click applies the view and closes unless pinned (the Normal To button too, before Normal To runs); Esc, Space and the close button close; held Esc / Space ignored and no key repeat on View Orientation; Space on a focused panel button clicks it, wherever the pointer is | Implemented | H `Test24Orientation`: `test_click_applies_the_view_and_closes`, `test_normal_to_button_closes_the_panel_unless_pinned`, `test_normal_to_button_with_a_plane_selected_closes_the_panel`, `test_pinned_panel_stays_open`, `test_escape_and_space_close`, `test_held_keys_do_not_close_the_panel`, `test_held_space_does_not_repeat_the_command`, `test_close_button`, `test_space_on_a_focused_panel_button_clicks_it`, `test_space_on_a_focused_panel_button_ignores_the_pointer`. G `gui_orientation: top_view_applied`, `unpinned_panel_closes_after_choice`, `front_view_applied`, `pinned_panel_stays_open`, `escape_closes_panel`, `orientation_no_auto_repeat`, `sketch_escape_closes_panel`, `sketch_space_closes_panel`, `panel_tab_focus_space_applies_view`, `panel_tab_focus_space_closes_unpinned_panel`, `panel_normal_to_nothing_closes_panel`, `panel_normal_to_nothing_hint`, `panel_normal_to_nothing_tooltip` | AC 24, 30, 48 and 49; a held key (AC 27, beyond the `autoRepeat` flag) and Space with the pointer over the panel (AC 30) headless only. |
| Click outside closes an unpinned panel: only the check of the current opening (generation), only after the panel had the keyboard, not while pinned or active again; within 0.3 s of opening (`OPEN_SETTLE_S`) the panel takes the keyboard back instead; closing gives the keyboard back only when the panel had it, to the window that had it at opening (an undocked 3D view) when that is alive and visible, else to the main window; a pinned panel hands it to the FreeCAD window clicked into last; with another program in front within the settle time the panel closes and FreeCAD is not brought to the front | Implemented | H `Test24Orientation`: `test_click_outside_closes_the_panel_unless_pinned`, `test_deactivation_while_the_opening_settles_does_not_close`, `test_check_within_the_settle_time_takes_the_keyboard_back`, `test_settle_check_with_another_program_in_front_closes`, `test_click_elsewhere_remembers_the_window_for_a_pinned_panel`, `test_opening_starts_a_new_generation`, `test_a_late_check_never_closes_a_newer_opening`, `test_a_panel_that_never_had_the_keyboard_is_not_closed`, `test_click_outside_check_skips_an_active_closed_or_pinned_panel`, `test_close_gives_the_keyboard_back_only_when_the_panel_had_it`, `test_close_returns_the_keyboard_to_the_window_that_had_it`, `test_the_panel_is_never_the_window_to_return_to`. G `gui_orientation: click_outside_closes_unpinned_panel`, `click_outside_keeps_pinned_panel`, `deactivation_right_after_opening_keeps_panel`, `deactivation_right_after_opening_takes_keyboard_back`, `later_click_elsewhere_closes_panel`, `undocked_escape_gives_keyboard_back_to_view`, `undocked_choice_gives_keyboard_back_to_view` | AC 28, 38, 41, 47 and 51; another program in front (AC 28, 51), the generation and the keyboard rule (AC 41) and the pinned panel's window clicked into last (AC 51) headless only (fake clock). |
| Theme-proof colors: a text color and a background for every button state | Implemented | H `Test24Orientation`: `test_stylesheet_gives_every_button_state_its_own_colors`, `test_panel_text_stays_dark_under_a_light_on_dark_theme`. G `gui_orientation: dark_rule_in_force`, `dark_panel_text_color`, `dark_pin_text_readable`, `app_stylesheet_restored` | AC 29 under a white-text application stylesheet; FreeCAD's own dark theme and a dark system palette are not run. |
| Space filter: with the pointer over a 3D view, a 3D viewer, a split 3D view (`Gui::AbstractSplitView`) or the model tree Space always opens the panel; elsewhere focused buttons, check boxes and combo boxes keep a plain Space, item views only with a checkable current item or typing edits (never the model tree), and controls in toolbars, the status bar or the ribbon never; one filter installed on the main window and every dock (floating docks included) on activation, and on a dock made later once one of its widgets takes the focus (`QApplication.focusChanged`, disconnected on leave); removed from all on leave | Implemented | H `Test24Orientation`: `test_keeps_space`, `test_item_views_keep_space_to_check_or_type`, `test_space_over_the_3d_view_or_the_model_tree_always_opens_the_panel`, `test_toolbars_status_bar_and_ribbon_never_keep_space`, `test_space_filter_asks_qt_which_widget_is_under_the_pointer`, `test_space_filter_accepts_plain_space_for_controls_only`, `test_space_toggles_a_focused_check_box_instead_of_opening_the_panel`, `test_filter_sits_on_the_main_window_and_every_dock`, `test_floating_dock_needs_its_own_filter`, `test_a_dock_made_after_activation_gets_the_filter_when_it_takes_focus`, `test_focus_outside_a_dock_adds_no_filter`, `test_focus_changes_after_uninstall_add_nothing`, `test_uninstall_disconnects_the_focus_watch`, `test_uninstall_skips_a_dock_that_was_deleted`, `test_install_is_idempotent_and_uninstall_removes_the_filter`, `test_install_without_a_main_window_does_nothing`, `test_leaving_jellyjams_closes_the_panel`; `Test06Lifecycle.test_real_activation_cycle_under_stubs`. G `gui_orientation: pad_dialog_open`, `space_filter_active_in_jellyjams`, `pad_space_toggles_check_box`, `pad_space_on_check_box_keeps_panel_closed`, `pad_pointer_over_view_space_opens_panel`, `pad_pointer_over_view_check_box_unchanged`, `floating_task_dock_space_toggles_check_box`, `floating_task_dock_space_keeps_panel_closed`, `late_dock_gets_space_filter`, `late_dock_space_toggles_check_box`, `late_dock_space_keeps_panel_closed`, `workbench_combo_space_opens_panel`, `workbench_combo_space_no_popup`, `space_filter_dropped_on_leave`, `no_space_filter_after_leave`, `plain_dock_space_toggles_after_leave`, `panel_stays_closed_after_leave` | AC 25, 26, 34 to 36 and 46; push buttons, combo boxes, item views and the model tree (rest of AC 25), status-bar and ribbon buttons and the property editor (AC 40), and the viewer and split-view classes headless only. |
| Icons: `normal_to.svg` for Normal To, FreeCAD's at runtime for the views, `view_save.svg` / `view_restore.svg` only for the two camera commands when FreeCAD has none | Partial | H `Test24Orientation`: `test_fallback_icons_when_freecad_has_none`, `test_freecad_icon_wins_over_the_fallback`; `Test21Icons` | AC 11 headless only; the icons in the real panel are not checked. |
| Placement at the pointer, kept on screen | Implemented | H `Test24Orientation.test_placement_next_to_the_pointer_and_on_screen` | AC 14 headless only (fake screen geometry). |
| Closed and the Space filter removed on leave (deactivation step D12), from the main window and every dock (docks made later included), the focus watch disconnected; `close()` and `uninstall()` safe when nothing was set up or a dock was deleted | Implemented | H `Test24Orientation`: `test_leaving_jellyjams_closes_the_panel`, `test_close_is_safe_when_never_opened`, `test_install_is_idempotent_and_uninstall_removes_the_filter`, `test_filter_sits_on_the_main_window_and_every_dock`, `test_a_dock_made_after_activation_gets_the_filter_when_it_takes_focus`, `test_uninstall_disconnects_the_focus_watch`, `test_uninstall_skips_a_dock_that_was_deleted`; `Test06Lifecycle`: `test_step_tables`, `test_real_activation_cycle_under_stubs`. G `gui_orientation: panel_closed_on_leave`, `space_filter_dropped_on_leave` | |
| `Space` and `Ctrl+8` while active, Hide/Show unbound and restored on leave, quit and after a crash, `Std_AlignToSelection` left alone | Implemented | See the shortcuts row under [Navigation and shortcuts](#navigation-and-shortcuts). G `gui_orientation: space_bound_to_orientation`, `ctrl8_normal_to`, `align_to_selection_untouched`, `normal_to_action_has_ctrl8`, `toggle_visibility_unbound_while_active`, `space_back_to_toggle_visibility`, `orientation_shortcut_removed`, `normal_to_shortcut_removed`; `check_saved_cfg: no_jj_shortcut_overrides` | Quit (AC 17) is checked by `check_saved_cfg` on the `user.cfg` saved by the `lifecycle/discard` run; crash recovery (AC 18), a moved Hide/Show key (AC 20) and AC 21 headless only. |

### Add Relations panel

Spec: [relations.md](specs/relations.md). Code: [`relations_rules.py`](../jellyjams/relations_rules.py), [`relations_panel.py`](../jellyjams/relations_panel.py), [`panel_host.py`](../jellyjams/panel_host.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Offer rules (worked reference table, capability table, catalogue order), entity labels, existing relations, deletion order | Implemented | H `Test15RelationsRules`: `test_worked_reference_table`, `test_offer_is_the_same_for_every_selection_order`, `test_catalogue_order_and_capability_coverage`, `test_offered_relations_agree_with_accepts`, `test_entity_labels_and_identity`, `test_existing_relations`, `test_deletion_order`, `test_tables` | The rule part of AC 27 runs without a GUI: all 29 worked rows in every selection order, a capability table that covers exactly the 14 catalogue relations, and the catalogue order of spec 4.3. The other part of AC 27 (all 14 mapped command ids exist in FreeCAD 1.1.4) is not automated. |
| Panel at the top of the Tasks panel, fallback dock `JellyJamsPropertyManagerDock`, buttons with FreeCAD icons, Delete as one undo step | Not verified | none | AC 1, 2, 7 to 13, 16 to 26. |

### Assembly

Spec: [assembly.md](specs/assembly.md). Code: [`switch_prefs.py`](../jellyjams/switch_prefs.py), [`mate_rules.py`](../jellyjams/mate_rules.py), [`mate_panel.py`](../jellyjams/mate_panel.py), [`assembly_drop.py`](../jellyjams/assembly_drop.py), [`assembly_commands.py`](../jellyjams/assembly_commands.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Stay in JellyJams on assembly activation: `SwitchToWB` held false, three-state exact restore, recovery, quit | Implemented | H `Test17SwitchPrefs`: `test_absent_key_round_trip`, `test_explicit_values_round_trip`, `test_pending_record_not_overwritten`, `test_restore_without_record_touches_nothing`, `test_recover`; `Test04Recovery`: `test_assembly_switch_to_wb_backup`, `test_corrupt_assembly_backup`. G `gui_smoke: switch_to_wb_off`, `switch_to_wb_restored`, `stayed_in_jellyjams`; `lifecycle/cancel: switch_to_wb_off_before_close`, `switch_to_wb_restored_inside_prompt`, `switch_to_wb_reapplied_after_cancel`, `switch_to_wb_restored_after_leave`; `lifecycle/after: switch_to_wb_kept_after_relaunch`; `check_saved_cfg: switch_to_wb_matches_expected` | The GUI runs compare with whatever state the copied profile had; explicit true/false are asserted headless only. The assembly was activated with `setEdit` from a script, not by a tree double-click; ribbon visibility after activation (AC 7) is not asserted. |
| Part Design and TechDraw `SwitchToWB` held false the same way (own backups `OriginalPartDesignSwitchToWB`, `OriginalTechDrawSwitchToWB`; every absent / true / false combination of the three modules; recovery with only some records; one damaged record or failing group never stops the others) | Implemented | H `Test17SwitchPrefs`: `test_targets`, `test_every_combination_round_trips_exactly`, `test_quit_revert_and_reapply_cycle`, `test_restore_with_only_some_records`, `test_recover_with_only_some_records`, `test_corrupt_records`, `test_blank_record_counts_as_none`, `test_one_failing_group_does_not_stop_the_others`; `Test04Recovery`: `test_every_switch_to_wb_backup`, `test_some_switch_to_wb_backups`, `test_corrupt_switch_backup_leaves_the_others_working`; `Test06Lifecycle.test_real_activation_cycle_under_stubs`. G `gui_smoke: switch_to_wb_off`, `switch_to_wb_restored`, `backups_present`, `backups_cleared`; `lifecycle/cancel: switch_to_wb_off_before_close`, `switch_to_wb_restored_inside_prompt`, `switch_to_wb_reapplied_after_cancel`, `switch_to_wb_restored_after_leave`; `lifecycle/after: switch_to_wb_kept_after_relaunch`; `check_saved_cfg: partdesign_switch_restored`, `techdraw_switch_restored`; `gui_sketch_first: a_still_in_jellyjams_after_exit` (leaving a sketch in a body stays in JellyJams) | The GUI runs cover all three modules; the copied profile had none of the three keys, so only the absent case ran in GUI; explicit true/false values, recovery and failing groups are asserted headless only. The TechDraw page double-click (AC 42) has no GUI test. |
| Add Mate panel | Not verified | H `Test16MateRules`: `test_kind_from`, `test_capability_matrix`, `test_commands_and_hints` (rules only); `Test22AssemblySelection.test_mate_panel_ignores_other_documents_and_dead_entries` | Panel UI AC 12 to 23. |
| Drag-and-drop of `.FCStd` files into the active assembly | Not verified | H `Test17Assembly.test_pure_helpers` (`filter_fcstd`, `is_portal_path`); `Test22DocumentHelpers.test_primary_model_objects_skip_2d_profiles` (primary-object rule) | AC 24 to 33. |
| New Assembly (`JellyJams_NewAssembly`) | Not verified | H `Test17Assembly.test_pure_helpers` (`next_assembly_name`); `Test05Commands` | AC 8 to 11. |
| Rotate Component (`JellyJams_RotateComponent`) | Not verified | H `Test17Assembly.test_pure_helpers` (`drag_rotation`); `Test22AssemblySelection.test_rotate_component_ignores_other_documents` | AC 34 to 40. The axis cross needs pivy (Coin). |

### Drawing sheet

Spec: [drawing-sheet.md](specs/drawing-sheet.md). Code: [`make_drawing.py`](../jellyjams/make_drawing.py), [`templates.py`](../jellyjams/templates.py), [`sheet_properties.py`](../jellyjams/sheet_properties.py), [`sheet_sketch.py`](../jellyjams/sheet_sketch.py), [`sheet_text.py`](../jellyjams/sheet_text.py), [`insert_picture.py`](../jellyjams/insert_picture.py), [`sheet_pick.py`](../jellyjams/sheet_pick.py), [`drawing_common.py`](../jellyjams/drawing_common.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Template catalog from FreeCAD's installed ISO templates; third-angle variant derived into `<UserAppData>/JellyJams/templates/` | Implemented | H `Test19DrawingHelpers`: `test_template_names_and_catalog`, `test_third_angle_symbol_on_installed_template`, `test_third_angle_derivation_files` | Run against the real FreeCAD 1.1.4 template files; the three tests skip when FreeCAD's ISO templates are not installed. Display on a sheet not verified. |
| Make Drawing (`JellyJams_MakeDrawing`) | Not verified | H `Test19DrawingHelpers.test_make_drawing_and_sheet_properties_helpers` (`default_format`, `document_name_for`); `Test22MakeDrawing`: `test_sketch_only_document_has_nothing_to_draw`, `test_file_of_an_open_document_is_refused` | AC 1 to 10. |
| Sheet Properties (`JellyJams_SheetProperties`) | Not verified | H `Test19DrawingHelpers.test_make_drawing_and_sheet_properties_helpers` (`field_label`, `ordered_keys`); `Test22SheetFormat`: `test_snapshot_skips_attached_and_cropped_views`, `test_rescale_writes_every_position_once_from_the_snapshot`, `test_switching_the_sheet_format_is_one_undo_step` | AC 11 to 18. |
| Shapes on the sheet (`JellyJams_*OnSheet`, sheet sketch) | Not verified | H `Test19DrawingHelpers.test_sheet_content_helpers` (`frame_points`); `Test22DocumentHelpers.test_sheet_sketch_watcher_adds_one_undo_observer` | AC 19 to 28. |
| Text (`JellyJams_Note`) | Not verified | H `Test19DrawingHelpers.test_sheet_content_helpers` (`split_lines`, `mm_to_pt`, `pt_to_mm`, `ISO_HEIGHTS_MM`) | AC 29 to 35. |
| Insert Picture (`JellyJams_InsertPicture`) | Not verified | H `Test19DrawingHelpers.test_sheet_content_helpers` (`svg_natural_size`, `bitmap_natural_size`, `initial_scale`); `Test22InsertPicture.test_unusable_files_are_rejected_before_an_undo_step` | AC 36 to 42. |

### Drawing views

Spec: [drawing-views.md](specs/drawing-views.md). Code: [`projected_view.py`](../jellyjams/projected_view.py), [`view_labels.py`](../jellyjams/view_labels.py), [`view_scale.py`](../jellyjams/view_scale.py), [`sheet_drag.py`](../jellyjams/sheet_drag.py), [`zoom_lines.py`](../jellyjams/zoom_lines.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Projected View (`JellyJams_ProjectedView`) | Not verified | H `Test19DrawingHelpers.test_zoom_steps_and_projection_rules` (`sheet_slot`, `click_step`, `projection_toward`) | AC 1 to 10. |
| Movable Standard 3 View (`AutoDistribute` off) | Not verified | none | AC 11, 12. |
| Section and detail lettering, view labels, two-way sync; one closed `View Label` undo step; labeling waits for a view drag | Not verified | H `Test19DrawingHelpers.test_view_labels_and_scales` (`next_letter`, `follows_scheme`, `label_text`, `tree_label`); `Test22ViewLabels`: `test_new_views_are_labelled_in_one_closed_undo_step`, `test_failed_labelling_still_closes_the_step`, `test_labelling_waits_for_a_view_drag` | AC 13 to 22. |
| Scale picker (`JellyJams_ViewScale`) | Not verified | H `Test19DrawingHelpers`: `test_view_labels_and_scales` (`STANDARD_SCALES`), `test_scale_text_and_parse` | AC 23 to 28. |
| Click-anywhere view dragging; one closed `Move View` undo step, none without movement | Not verified | H `Test22ViewDrag`: `test_a_drag_without_movement_leaves_no_undo_step`, `test_a_drag_is_one_closed_undo_step` | AC 29 to 35. The mouse handling on a real sheet has no test. |
| Zoom line-width compensation (screen only) | Not verified | H `Test19DrawingHelpers.test_zoom_steps_and_projection_rules` (`reduction_step`) | AC 36 to 41. |

### Drawing symbols and export

Spec: [drawing-symbols-export.md](specs/drawing-symbols-export.md). Code: [`surface_finish.py`](../jellyjams/surface_finish.py), [`weld_symbol.py`](../jellyjams/weld_symbol.py), [`line_format.py`](../jellyjams/line_format.py), [`drawing_export.py`](../jellyjams/drawing_export.py), [`pdf_merge.py`](../jellyjams/pdf_merge.py).

| Feature | Status | Verified by | Notes |
|---|---|---|---|
| Surface Finish (`JellyJams_SurfaceFinish`) | Not verified | H `Test19DrawingHelpers`: `test_surface_finish_svg` (SVG, editable texts, rotation parsing), `test_surface_finish_tables` | AC 4 to 14. |
| Weld Symbol (`JellyJams_WeldSymbol`) with arrow-follow watcher | Not verified | H `Test19DrawingHelpers.test_weld_symbol_data_and_svg` (`DEFAULT_DATA`, `merge_data`, `build_svg`) | AC 15 to 29. |
| Line Format (`JellyJams_LineFormat`) | Partial | H presets row: `Test18DialogTerms.test_weight_presets_row`, `test_weight_presets_edge_cases`; G `gui_host_compatibility.py` | Native panel terminology/preset activation verified on both hosts; complete AC 30 to 35 workflow remains unverified. |
| PDF merge without third-party libraries | Implemented | H `Test20PdfMerge`: `test_merge_two_qt_pdfs`, `test_incremental_update_is_rejected`, `test_xref_stream_and_garbage_are_rejected` | Verified on PDFs written by Qt's `QPdfWriter`. "Opens in two PDF viewers" (AC 45) is a manual check. |
| Save as PDF (`JellyJams_SaveAsPDF`) | Partial | H `Test19DrawingHelpers.test_export_naming` (`sanitize`, `suggested_base`, `per_sheet_paths`); merge as above | Export from real TechDraw pages (AC 36 to 42, 44) not verified. |
| Export DXF (`JellyJams_SaveAsDXF`, "Save as DXF" on the ribbon) | Not verified | H `Test19DrawingHelpers.test_export_naming` (`per_sheet_paths`) | AC 43. |

## Known gaps and limitations

### 1. Acceptance criteria not verified in GUI

Every criterion below is **not verified in GUI**. The middle column lists criteria with no
automated check at all; the right column lists criteria whose logic is asserted only by the
headless suite (stubbed FreeCAD), which can differ from real FreeCAD behavior.

| Spec | No automated check | Logic asserted headless only |
|---|---|---|
| [core](specs/core.md) | 4, 21, 22 (no-prompt quit; the Discard path checks the same keys), 27, and the dialog / clipboard parts of 11, 13, 14, 15 | 1 (message text, no warnings), 2 (icon, tooltip), 3, 5, 6, 7, 8, 9, 11 (rows, format), 12, 18, 19, 20, 28, 29, 30, 31 to 35, 36 to 38, 39 |
| [window-layout](specs/window-layout.md) | 3, 4, 5, 7, 10, 11, 13, 18, 23; 14 with the prompt held 10 s; panel parts of 17 and 19 | 2, 8, 12, 20, 21, 22, 24, 25 |
| [look](specs/look.md) | 3 to 9, 17, 19, 23 and 26 (View keys in the saved `user.cfg`), 27, the View-key parts of 24 and 25, the gradient part of 33 | 2, 11 to 16, 20 to 22, 28 to 32, 34 to 39 |
| [ribbon-engine](specs/ribbon-engine.md) | 9, 10, 11, 19, 21, 22, 30, 33, 34, 36 | 4, 5, 7, 8, 12, 13, 14 and 15 (no restart), 16, 17, 18, 23 to 25 (dispatch order with stand-ins), 27 (show twice keeps the button count), 31, 32, 35 |
| [ribbon-content](specs/ribbon-content.md) | 3 (gui_smoke records the skipped ids without asserting them), 7, 8, 9 (except Normal To, below), 10, 11, 24, 26, 27 | 2, 4 (totals; gui_smoke compares each page with the model), 6, 12 to 16, 17 (both buttons exist in GUI: `gui_smoke: jj_plain_buttons`), 18 to 23, 25, 28; the Normal To part of 9 is checked in GUI (`gui_orientation: evaluate_ribbon_normal_to_is_jellyjams`, `evaluate_ribbon_normal_to_face_aligns`) |
| [naming](specs/naming.md) | 6, 7, 8, 9, 11, 20, 21, 23, 24, 25; 3 while the Pad dialog is open | 2, 4, 5, 10, 12 to 19, 22 (rules and observer logic with fake documents) |
| [dialog-terms](specs/dialog-terms.md) | 3 to 7, 9, 10, 12, 15, 17 to 20, 24 to 26 | 1, 2, 8, 11, 13, 14, 16, 21 to 23, 27 (synthetic forms) |
| [sketching](specs/sketching.md) | 1 to 3, 6, 8 to 11, 13, 15 to 20, 22 to 28, 31 to 39 | 4, 5 (stand-in `Show` module), 7 (dispatch only), 12, 14, 30 (helpers), 21, 29 (command resources only), 43, 45 to 47, 51 to 57, 59 and 61 (fake document; the Hole Wizard refusal of 52 and the Hole Wizard part of 61 are also checked in GUI: `gui_orientation: hole_without_solid_*`, `hole_two_bodies_*`), 50, 58 and 60 (`Test23EditGuard`, `Test06Lifecycle`) |
| [orientation](specs/orientation.md) | none (17 is checked by `check_saved_cfg: no_jj_shortcut_overrides` on a real saved `user.cfg`) | 5, 9, 11 to 14, 18, 20, 21, 40 to 42, 45, 50, 51; the no-document and drawing-sheet parts of 10, the straight-edge part of 22, the own-edges and other-object-face parts of 23, the push button, combo box, list and model tree parts of 25, the held key of 27, another program in 28, FreeCAD's own dark theme in 29, the pointer over the panel in 30, the fullscreen, split and `Ctrl+8` parts of 31, the face-and-edge, whole-body, datum-plane and moved-body parts of 39 |
| [relations](specs/relations.md) | 1, 2, 7 to 13, 16 (one undo step), 17 to 26, 27 (command ids in 1.1.4) | 3, 4, 5, 6, 14, 15, 16 (deletion order), 27 (rules) |
| [assembly](specs/assembly.md) | 11, 12, 20 to 29, 31 to 36, 38 to 40, 42; ribbon visibility in 7 | 3, 4, 5, 8 (menu text only), 9 and 10 (document name only), 13 to 19 (rules), 30 (file filter), 37 (rotation math) |
| [drawing-sheet](specs/drawing-sheet.md) | 1, 2, 5, 7 to 11, 13, 15 to 18, 20 to 29, 31, 34, 35, 38 to 41, 43, 44 | 3, 4, 6, 12, 14, 19, 30, 32, 33, 36, 37, 42 (file rejection), 45 |
| [drawing-views](specs/drawing-views.md) | 1, 2, 9 to 12, 16, 19 to 23, 25 to 27, 29, 30, 32 to 35, 37 to 43 | 3 to 8, 13 to 15, 17, 18, 24, 28, 31 (no undo step without movement), 36, 44 |
| [drawing-symbols-export](specs/drawing-symbols-export.md) | 1 to 4, 7 to 17, 21, 22, 24 to 26, 28 to 32, 35, 39 to 42, 44, 47 | 5, 6, 18 to 20 (SVG content, partly), 23, 27, 33, 34, 36 to 38, 43, 45, 46 |

Criteria not listed for a spec are covered by at least one GUI check (see the tables above).

### 2. Guarded fallbacks (degraded modes by design)

Each situation below is handled without an exception; the code prints a `JellyJams: ` message
and keeps the rest of the workbench working. None of these paths is exercised in GUI; the ones
marked H have a headless test.

| Situation | What happens | Where |
|---|---|---|
| FreeCAD's `Show` module (TempoVis) unavailable | Warning; opening a sketch switches to the Sketcher as in stock FreeCAD | [`sketch_edit.py`](../jellyjams/sketch_edit.py) |
| No usable `qInstallMessageHandler`, or `SilenceGlyphWarnings` = false | Warning (or log line); "render glyph failed" messages stay visible (H `Test08QtFilter.test_parameter_false_registers_nothing`) | [`qt_filter.py`](../jellyjams/qt_filter.py) |
| A FreeCAD GUI module cannot be preloaded / a command is missing | Warning; affected buttons left out. A primary id with a fallback uses the fallback (log line). Missing Assembly command modules only log; `Assembly_*` buttons are absent (H `Test13RibbonBuild.test_missing_commands_warning`, `test_assembly_modules_missing_only_logs`) | [`ribbon.py`](../jellyjams/ribbon.py) |
| `Tasks` dock not found | Warning listing the docks found; panels not moved; toolbars still hidden (H `Test11Layout.test_missing_tasks_dock_warns_and_still_hides_toolbars`) | [`layout.py`](../jellyjams/layout.py) |
| Main window stays hidden about 12 s after an autoload | Warning; layout not applied; other features stay active (H `Test11Layout.test_deferral_timeout_warns_once_and_changes_nothing`) | [`layout.py`](../jellyjams/layout.py) |
| Unreadable crash backup | One warning; backup discarded (H `Test04Recovery`, `Test10Look.test_viewport_recover`, `Test17SwitchPrefs`: `test_recover`, `test_corrupt_records`, `Test12NavigationShortcuts.test_unreadable_backups_found_at_install_are_replaced`, `test_unreadable_backups_found_at_uninstall_change_nothing`) | [`recovery.py`](../jellyjams/recovery.py), [`navigation.py`](../jellyjams/navigation.py), [`shortcuts.py`](../jellyjams/shortcuts.py), [`viewport.py`](../jellyjams/viewport.py), [`switch_prefs.py`](../jellyjams/switch_prefs.py) |
| One `SwitchToWB` preference group cannot be read or written | Warning naming the module; the other two are still applied and restored (H `Test17SwitchPrefs.test_one_failing_group_does_not_stop_the_others`) | [`switch_prefs.py`](../jellyjams/switch_prefs.py) |
| `FreeCADGui.activateWorkbench` missing | Nothing is wrapped; Part Design feature edits switch to Part Design as in stock FreeCAD (H `Test23EditGuard.test_install_without_activate_workbench`) | [`edit_guard.py`](../jellyjams/edit_guard.py) |
| A workbench switch held by the feature-edit guard raises | Warning naming the workbench; JellyJams stays active (H `Test23EditGuard.test_failing_switch_after_the_wait_warns`) | [`edit_guard.py`](../jellyjams/edit_guard.py) |
| `PartDesign_NewSketch` fails during sketch first | Error from the command runner; no pending state; the feature runs the ordinary way (H `Test23SketchFirstFlow.test_failing_new_sketch_command_leaves_no_state`) | [`sketch_gesture.py`](../jellyjams/sketch_gesture.py) |
| A check of a pending sketch first raises | Log line; the sketch-first is dropped and its status hint cleared (H `Test23SketchFirstFlow.test_status_hint_cleared_when_a_check_fails`) | [`sketch_gesture.py`](../jellyjams/sketch_gesture.py) |
| Another add-on wrapped `FreeCADGui.activateWorkbench` after JellyJams | Leaving only disarms the JellyJams wrapper and entering only re-arms it; no recursion, the other wrapper stays. Command strings are still recognized through up to five such wrappers, so feature edits keep JellyJams (H `Test23EditGuard`: the four chain-tracking tests and the three frame-search tests) | [`edit_guard.py`](../jellyjams/edit_guard.py) |
| A view command of the Orientation panel is missing, or FreeCAD has no icon for it | The button is disabled, or shows no icon (the two camera commands use the JellyJams fallback icons) (H `Test24Orientation.test_missing_commands_are_disabled`, `test_fallback_icons_when_freecad_has_none`) | [`orientation.py`](../jellyjams/orientation.py) |
| `JellyJams_ViewOrientation` or `JellyJams_NormalTo` missing when the shortcuts are applied | Its key is skipped with a log line and Hide/Show keeps Space (H `Test12NavigationShortcuts.test_space_is_left_alone_without_view_orientation`) | [`shortcuts.py`](../jellyjams/shortcuts.py) |
| FreeCAD's check whether a view command is active raises | The panel button stays enabled (H `Test24Orientation.test_buttons_follow_the_commands_active_state`) | [`orientation.py`](../jellyjams/orientation.py) |
| The main window's `getActiveWindow()` (or, without it, `FreeCADGui.activeView()`) raises, or FreeCADGui is unavailable | Both orientation commands are inactive; nothing is printed (H `Test24Orientation`: `test_active_while_the_main_windows_active_window_is_a_3d_view`, `test_active_view_falls_back_to_freecads_active_view`, `test_active_view_is_none_on_errors`, `test_the_mdi_area_does_not_decide_availability`) | [`orientation.py`](../jellyjams/orientation.py) |
| Normal To cannot turn the view to a whole sketch (no view in front, no placement, the view refuses) | Warning naming the object; no hint; nothing else changes (H `Test24Orientation.test_normal_to_warns_when_the_view_cannot_turn`) | [`orientation.py`](../jellyjams/orientation.py) |
| The selection path of a whole sketch cannot be followed (`getGlobalPlacementOf` raises or is missing) | Log line; the sketch's own global placement is used (H `Test24Orientation.test_sketch_rotation_falls_back_to_the_sketchs_own_placement`) | [`orientation.py`](../jellyjams/orientation.py) |
| The hint's tool tip cannot be shown | The status-bar hint still shows; nothing is printed (H `Test24Orientation.test_normal_to_hint_shows_at_the_pointer_too`) | [`orientation.py`](../jellyjams/orientation.py) |
| The shape of a whole object cannot be read, or its type cannot be asked | Normal To treats it as nothing to look at (H `Test24Orientation.test_whole_object_types`); a picked sub-element's shape is never read (`test_normal_to_target`) | [`orientation.py`](../jellyjams/orientation.py) |
| The window that had the keyboard before the panel opened was closed or hidden meanwhile | Closing the panel gives the keyboard to the main window instead (H `Test24Orientation.test_close_returns_the_keyboard_to_the_window_that_had_it`) | [`orientation.py`](../jellyjams/orientation.py) |
| A dock with the Space filter was deleted before JellyJams is left | It is skipped; the filter is removed from the rest and nothing is printed (H `Test24Orientation.test_uninstall_skips_a_dock_that_was_deleted`) | [`orientation.py`](../jellyjams/orientation.py) |
| The Orientation panel's widget was deleted, or there is no main window when the Space filter is installed | The panel is built again on the next open; no filter is installed and nothing is printed (H `Test24Orientation`: `test_panel_is_built_again_when_its_widget_was_deleted`, `test_install_without_a_main_window_does_nothing`) | [`shortcuts.py`](../jellyjams/shortcuts.py) |
| A shortcut command does not exist in this FreeCAD build | Log line; that shortcut is skipped (H `Test12NavigationShortcuts.test_shortcuts_for_missing_commands_are_skipped`). Commands already owning a JellyJams key are unbound while active and restored after | [`shortcuts.py`](../jellyjams/shortcuts.py) |
| Third-angle template cannot be read or written | Warning; the template is used unchanged, or the first-angle template is used | [`templates.py`](../jellyjams/templates.py) |
| PDF merge not possible (unsupported PDF structure) | Warning; one PDF per sheet next to the chosen file (merger refusal: H `Test20PdfMerge`) | [`drawing_export.py`](../jellyjams/drawing_export.py) |
| Selection listener for the Sketch context icon cannot be registered | Warning; the icon is unavailable | [`context_sketch.py`](../jellyjams/context_sketch.py) |
| Dialog-terms service cannot start | Warning; dialogs keep FreeCAD's texts | [`dialog_terms.py`](../jellyjams/dialog_terms.py) |
| Dropped file sits in a sandbox document portal path | Warning that the link may break after a restart (H `Test17Assembly.test_pure_helpers` for the path test) | [`assembly_drop.py`](../jellyjams/assembly_drop.py) |
| Dropping into an assembly that was never saved | Save As is offered; on cancel nothing is inserted and a warning is printed | [`assembly_drop.py`](../jellyjams/assembly_drop.py) |
| Insert Picture with an unsupported, unreadable or non-UTF-8 file | Error; nothing inserted and no undo step opened (H `Test22InsertPicture.test_unusable_files_are_rejected_before_an_undo_step`) | [`insert_picture.py`](../jellyjams/insert_picture.py) |

### 3. Behavior limitations by design

- **Exact restore wins.** If the user changes one of the 14 managed View preferences, the
  navigation style or a JellyJams shortcut in Preferences while JellyJams is active, leaving the
  workbench puts back the value from before activation. Dock rearrangements made inside
  JellyJams are discarded on leave. A kept toolbar (File, Edit, Workbench) hidden inside
  JellyJams stays hidden after leaving.
- **Tree names are permanent.** Labels written by tree naming are ordinary document edits; leaving
  the workbench does not revert them.
- **Dialog terms are tied to FreeCAD 1.1.4** objectNames and combo entry counts. Other FreeCAD
  versions may show FreeCAD's own texts for some widgets (combo safety rule).
- **Ribbon content is fixed at first build** in a session. Commands that appear later (for
  example from a workbench loaded afterwards) show up only after a restart. `ribbon.rebuild()`
  exists but has no UI entry point.
- **Kept preferences.** Flyout choices (`Mod/JellyJams/FlyoutChoices`) and the Text tool's `LastNoteHeight` /
  `LastNoteUnit` stay in `user.cfg` after leaving, by design. Derived third-angle templates are cached
  in `<UserAppData>/JellyJams/templates/`.
- **Settings without UI.** `SilenceGlyphWarnings` and `ShowSketchButtonOnFace` (both Bool in
  `Mod/JellyJams`, default true) can only be changed with Tools > Edit parameters.
- **While FreeCAD's "Save changes?" prompt is open**, JellyJams is still the active workbench
  and its layout is reverted, so only FreeCAD's global toolbars are visible. Workbench toolbars
  return after switching workbenches.
- **Centerline / Midpoint Line** also process a line drawn by keyboard shortcut while the mode
  runs (accepted in the spec).
- **Sketch first works from the ribbon only**, for Pad, Pocket, Revolution, Groove and Hole. With
  an edge or a curved face selected and no free sketch, FreeCAD's own behavior and warning still
  apply; a selection of only bodies, origins, parts or groups is cleared first and then counts as
  no selection. Pocket, Groove and Hole start a sketch only when the target body already holds
  a solid by FreeCAD's own rule (a Part Design feature in the body); otherwise FreeCAD's own
  refusal shows for Pocket and Groove, and a JellyJams status-bar message for Hole (FreeCAD's
  Hole has no refusal of its own). With several bodies and none active they are left to FreeCAD,
  which asks which body to work in. Sweeps, lofts and helices keep FreeCAD's behavior.
- **Space belongs to the Orientation panel while JellyJams is active.** FreeCAD's Hide/Show
  (`Std_ToggleVisibility`) has no key there; it is still in FreeCAD's menus and gets Space back
  on leave. With the pointer over the 3D view or the model tree, Space always opens the panel,
  even when a check box clicked a moment ago still has the focus. Elsewhere a focused button,
  check box or combo box keeps Space, and so does a list whose current item is checkable or
  which edits on typing; controls in toolbars, the status bar and the ribbon never do. A custom
  control that uses Space but is none of these loses it to the panel. With the Start page or a
  drawing in front, Space and `Ctrl+8` do nothing. The panel offers no viewport layouts, View
  Selector cube or named views ([orientation](specs/orientation.md) 4).
- **Normal To needs exactly one pick.** `Ctrl+8`, the JellyJams menu, the panel and the Evaluate
  tab's button all run `JellyJams_NormalTo`: the sketch plane in a sketch; otherwise one face,
  edge or vertex, one whole datum or one-face or one-edge object (FreeCAD's Align to Selection
  decides what it can align to; a pick it cannot handle, such as a vertex, changes nothing and
  shows no hint), or one whole sketch. Two picks or a whole body show the hint instead of a view
  change. FreeCAD's `Std_AlignToSelection` has no ribbon button.
- **A workbench chosen in the workbench selector or View > Workbench is applied one event-loop
  turn later** while JellyJams is active (the feature-edit guard waits to see whether an edit
  started). A choice made in the very turn in which a feature enters edit would be dropped.
- Two FreeCAD instances sharing one `user.cfg` are out of scope.

### 4. Test-infrastructure limitations

- **Stubs are not FreeCAD.** The headless suite runs against
  [`tests/headless_stubs.py`](../tests/headless_stubs.py) and, in the `Test22*` classes, against
  fake documents and a fake transaction API. Parameter, console, command and transaction
  behavior is modeled on FreeCAD 1.1.4 but not identical; any feature marked headless-only can
  still fail in FreeCAD.
- **Only Windows and FreeCAD 1.1.4** were tested. Linux and macOS are not verified.
- **GUI scripts use fixed timer delays** (4 s start, 1 to 5 s between steps). A slow machine can
  produce false failures.
- **GUI scripts run on copies of an existing profile**, not on a fresh one. They assume that
  profile has no user overrides for `Std_ViewFitAll`, `Std_Refresh`, `Std_ViewIsometric`,
  `JellyJams_NormalTo`, `Std_AlignToSelection`, `JellyJams_ViewOrientation`, `Std_ViewBoxZoom` and
  `Std_ToggleVisibility` (`gui_smoke: shortcut_restored` and
  `check_saved_cfg: no_jj_shortcut_overrides` would fail otherwise), and that Hide/Show still
  has FreeCAD's default `Space` (`gui_orientation: toggle_visibility_unbound_while_active`). The three `SwitchToWB` and `NavigationStyle` are compared with whatever
  the copied profile held. `check_saved_cfg.py` expects the Part Design and TechDraw
  `SwitchToWB` to be absent unless the originals are passed on its command line.
- **`gui_tabs.py` asserts nothing.** It records button counts, button kinds, separators, enabled
  counts, errors and screenshots for manual review.
- **`gui_smoke.py` writes `"ok"` only when it reaches its last step.** A missing `"ok"` key means the
  run aborted; read `errors`.
- **The headless suite ends with `TerminateProcess` on Windows.** Unloading the Qt and PySide
  libraries after the tests could crash the process now and then and turn a clean run into a
  non-zero exit code, so the harness skips that clean-up; the exit code is the test result.

### 5. Open items for review

- **Approximate ribbon labels.** Several FreeCAD commands on the ribbon have no exact SolidWorks
  counterpart, so their labels are the closest SolidWorks term or a descriptive name and need a
  review by someone who uses SolidWorks daily. The full list is in
  [ribbon-content 2.8](specs/ribbon-content.md); it includes Helical Boss/Base and Helical Cut
  (`PartDesign_*Helix`), Multi-Transform, Body, Combine (`PartDesign_Boolean`), Sub-Shape Binder,
  the Features tab's Projected Curve and Intersection Curve (`Part_ProjectionOnSurface`,
  `Part_Section`), Polyline, Rounded Rectangle (`Sketcher_CreateOblong`), Closed Spline and
  Closed Style Spline, Hyperbola, Carbon Copy, Display/Delete Relations, Find Under Defined,
  Repair Sketch, Section View and Persistent Section on the Evaluate tab
  (`Std_ToggleClipPlane`, `Part_SectionCut`), Activate Assembly, Solve Assembly,
  Coincident/Distance (Distance joint), Ball Joint, Move Component (`Std_TransformManip`), New
  Motion Study (`Assembly_CreateSimulation`), Add Sheet (`TechDraw_PageDefault`), Aligned
  Section (`TechDraw_ComplexSection`), Crop View (`TechDraw_ClipGroup`), Chain and Baseline
  Dimension (horizontal TechDraw extensions), Rich Text Note, Geometric Hatch, Bolt Circle Mark,
  2-Line and 2-Point Centerline, Multi-Jog Leader (`TechDraw_LeaderLine`) and General Table
  (`TechDraw_SpreadsheetView`).
- **Conflicting-shortcut scan covers only the commands registered at activation.**
  `shortcuts.install()` unbinds the commands FreeCAD lists at that moment. A command registered
  later in the session (for example by a workbench loaded afterwards) keeps a key it shares with a
  JellyJams shortcut, and Qt then fires neither action until JellyJams is activated again.
- **Insert Picture's undo step can be committed early.** The panel keeps a persistent undo step
  open until OK or Cancel, but TechDraw's own drag of the picture can commit it first. Cancel
  still removes a new picture or writes the old position, scale and rotation back, but the undo
  history then holds separate steps instead of one.
- **Removing a new section or detail view takes two undo steps.** JellyJams labels the view in its
  own `View Label` step after FreeCAD's creation step, so the first Undo removes the letter, tree
  name and view label, and a second Undo removes the view.
- **PartDesign primitives are not on the ribbon.** The additive and subtractive primitives (box,
  cylinder, sphere and so on) can only be reached through FreeCAD's own Part Design workbench.
- **A split 3D view is not exercised in FreeCAD.** Normal To and the panel's view buttons in a
  split view (`Gui::AbstractSplitView`) rely on FreeCAD's split-view object; in FreeCAD 1.1.4
  its own `Std_View*` commands report themselves inactive there (probe), so the panel's view
  buttons are disabled in a split view. No GUI check covers it.
- **The feature-edit guard under another add-on's wrapper.** If an add-on that wrapped
  `FreeCADGui.activateWorkbench` after JellyJams later replaces the chain with a function that
  no longer calls the JellyJams wrapper, JellyJams still believes its wrapper is in the chain and
  does not wrap again for the rest of the session.

## Missing SolidWorks features (roadmap)

The [2026-11-05 interface audit](audits/2026-11-05-interface-audit.md) is the
current prioritized planning inventory. The older list below remains a broad
capability reference. Proposals need a specification before implementation.
Write the spec first (see the
[specs index](specs/README.md)), then implement. The "Possible basis" column is a first estimate,
not a verified design; check FreeCAD command ids and APIs against the installed version before
relying on them.

| Priority | Feature (SolidWorks term) | What users expect | Possible basis | Notes |
|---|---|---|---|---|
| Implemented initial version | Confirmation corner | Native OK / Cancel and Exit Sketch at the viewport corner and on D | [quick-access specification](specs/quick-access.md) | Docked native feature/sketch checks; other dialog types and undocked/split views need coverage |
| P1 | Heads-up View toolbar | Transparent toolbar at the top of the graphics area: Zoom to Fit, Zoom to Area, Previous View, Section View, View Orientation, Display Style, Hide/Show | Overlay on the 3D view running the `Std_*` commands already on the Evaluate tab | Must respect the light theme and stay out of the navigation cube |
| Implemented initial version | S-key shortcut bar | Context tools and searchable commands at the pointer | [quick-access specification](specs/quick-access.md); scoped transient keys, no shortcut preference writes | Searchable list implemented; customizable icon grid remains future work |
| P3 | Rollback bar | Drag a bar in the FeatureManager tree to roll the model back | Research Body Tip and native history/dependency behavior | Body Tip alone does not establish rollback semantics; separate feasibility project |
| P1 | Options page | One place for JellyJams switches (Sketch context icon, Qt filter, later: theme, shortcuts) like System Options | FreeCAD preference page for `Mod/JellyJams` | Today only Tools > Edit parameters |
| P2 | Mouse gestures | Right-drag radial menu with 4 or 8 commands | Event filter on the 3D viewport, like Rotate Component | Must not break the right button in the SolidWorks navigation style |
| P2 | Context toolbars for more selections | Mini toolbar for edges, features in the tree, sketches (Edit Sketch, Hide, Appearance) | Generalize [`context_sketch.py`](../jellyjams/context_sketch.py) | |
| P2 | Equations / Global Variables | Equations manager with named variables driving dimensions | FreeCAD expressions with a spreadsheet or variable-set object | Verify which objects FreeCAD 1.1 offers |
| P2 | Configurations | Several variants of a part in one file | Spreadsheet-driven configuration tables | Large UX gap; feasibility not assessed |
| P2 | Mass Properties | Mass, volume, center of mass dialog on the Evaluate tab | Part shape properties with a density input | |
| P2 | Advanced appearance / DisplayManager | Scenes, decals, display states and full appearance inheritance | Extend the existing native-material browser | Face/object/component colours and transparency are already implemented; see [appearances](specs/appearances.md) |
| P2 | Selection filter | Filter toolbar (`F5`) for faces, edges, vertices | FreeCAD selection gates | |
| P3 | Sheet Metal, Weldments, Surfaces tabs | CommandManager tabs for these features | Depends on what the installed FreeCAD offers | Ribbon content is data-driven ([`ribbon_layout.py`](../jellyjams/ribbon_layout.py)) |
| P3 | Drawing tables and annotations | BOM table on the sheet, revision table, Auto Balloon, Model Items | Assembly BOM plus a TechDraw spreadsheet view | A General Table (`TechDraw_SpreadsheetView`) is already on the Drawing tab |
| P3 | Assembly tools | Interference Detection, SmartMates (Alt-drag), Move Component with triad | Assembly solver and Part boolean checks | Feasibility not assessed |
| P3 | Customize CommandManager | Users add, remove and reorder ribbon buttons | Persist a user layout next to `ribbon_layout.TABS` | |
| P3 | Instant3D | Drag dimension arrows in the graphics area to change a feature | Not available in stock FreeCAD; would need a custom 3D-view tool | |
| P3 | Localization | Non-English SolidWorks terms | Translation layer (the specs currently require English only) | Spec change needed |

## Updating this page

1. Re-run every suite as described in [testing.md](testing.md); use fresh throwaway configs.
2. Update [Test results](#test-results) with the new counts and the date at the top.
3. When a test is added, add its exact name to the matching row and move the criterion out of
   [section 1](#1-acceptance-criteria-not-verified-in-gui) of the known gaps.
4. Change a status only on test evidence: Implemented needs an assertion at the level where the
   behavior can fail; otherwise use Partial or Not verified.
5. When a roadmap feature gets a spec, move it from the roadmap into a new area table.

## Selection-driven Measure (2026-11-01)

Initial boundary-only implementation; its measurement reference is superseded by
the centre-to-edge correction below. The results in this section are historical.

The Evaluate Measure button now opens a temporary shortest-distance task. Two
ordinary clicks accumulate features; geometry is resolved through placed links
and measured with `Part.getShape` / `distToShape`. Empty selection clears both
result and scene annotation. No measurement objects, preference writes or
selection-style changes are made. The native Tools menu command is unchanged.

The task is owned by `ribbon`: `run_entry` starts it and `hide` stops it on
leave/quit. Form destruction also disposes the observer and annotation; a timer
ends it on active-document/view changes. This intentionally replaces native
Measure's auto-mode/history behavior for the ribbon only. Required behavior and
acceptance cases: [ribbon-content](specs/ribbon-content.md#measure-selection-behavior).

Verification on FreeCAD 1.1.4 Windows:

- **543/543 headless**, no failures/errors/skips (`scratch/measure_headless_final.log`).
- **24/24 native Measure checks**, disposable profile (`scratch/gui_lcg_q8ha/`):
  circular-edge/straight-edge and cylindrical-wall minimums, circle boundary gap,
  linked component placement, ordinary mouse clicks, empty-space clearing,
  external close/reopen, workbench leave, and no measurement document objects.
- Smoke **31/31** and all five ribbon tabs (`scratch/gui_h6f3p3cb/`).
  GUI-result validator **10/10**, compilation and `git diff --check` passed.
- The first native mouse-input tests missed their targets because projected
  viewport coordinates were physical pixels on a 125% DPI screen. Converting
  them to Qt logical pixels fixed the harness; final picks are recorded as
  `Edge1`, `Edge2` and empty space. Earlier runs were not clean passes.
- Native scene export visually inspected; the full-window Qt grab showed GL
  capture artifacts, so it is not evidence of viewport rendering quality.
  Active-document/view-change cleanup is implemented but not separately
  exercised by the native suite. The pictured user PCB file was not available.

## Measure hole centres and supplied PCB regression (2026-11-01)

The user clarified that the intended measurement is from the hole centre to the
PCB edge. The previous boundary-only implementation was geometrically correct
for rim clearance but did not implement that intent. The default task reference
is now **Centers / axes**: circular edges/arcs become centre vertices and
cylindrical faces become finite axis segments after world-space resolution.
**Nearest surfaces (clearance)** explicitly selects the original boundary-gap
behavior. Reference choice is temporary and updates the current annotation.
Empty-selection and task/lifecycle cleanup are retained.

Inspected `moddoMOUISE_A1 Part 2.stp` from the user's Downloads, without modifying
the file. Its PCB solid 202, Edge1066 and Edge1015 establish exactly **1.500 mm**
centre-to-edge, with hole radius **0.575 mm** and rim clearance **0.925 mm**.
The STEP ring is represented by circular arcs, so recognition does not require
a closed edge. The native task's annotation begins at the circle centre.

Verification:

- **545/545 headless**, no failures/errors/skips (`scratch/measure_center_headless.log`).
  Added centre recognition for circular arcs and an explicit-clearance regression.
- Native FreeCAD 1.1.4, disposable profile: **29/29 Measure checks**
  (`scratch/gui_xjao4rni/`), including all 25 default cases and four optional
  supplied-STEP assertions: 1.500 mm, visible task result, annotation at the
  centre, and 0.925 mm in clearance mode. Native scene export visually inspected
  (`supplied_pcb_measure.png`). The default synthetic suite separately passed
  **27/27** in `scratch/gui_vogetrft/`.
- GUI-result validator **10/10**, compilation and `git diff --check` passed.
  No native Measure settings or document measurement objects were introduced.
  The user STEP file remains an optional local fixture and is not committed.

## Hole wall measurement labels and readability (2026-11-01)

The user reported `0 mm` after selecting a hole's inner face and PCB edge and
requested larger, bolder labels. Inspection of the supplied STEP confirms
cylindrical Face1799 with perimeter Edge1015 gives **1.500 mm** with the existing
axis conversion, as does a live task using that exact pair. A numerical zero was
not reproduced for this pair; no live user FreeCAD window was available to read
the original selection. No new geometry correction is claimed here.

Two rendering limitations are fixed: the label previously used Coin's fixed-size
default bitmap font, which ignores the configured size and cannot become bold;
and its scene separator allowed coplanar PCB geometry to depth-test the annotation.
The task now uses a resolved installed font family in **bold at 22 screen pixels**
inside `SoAnnotation`, so the full label and line render above the model. The task
result is also bold and two points larger. This prevents clipped/hidden digits;
it does not establish that clipping caused the user's original zero report.

Verification:

- **547/547 headless**, no failures/errors/skips (`scratch/measure_wall_headless.log`),
  including the supplied cylinder's offset origin, downward axis and negative
  V range, plus the task result's font emphasis.
- **36/36 native Measure checks**, disposable profile (`scratch/gui_l06yk2wr/`):
  all prior cases plus the actual cylindrical wall/edge pair, result and endpoint
  distance 1.500 mm, complete `1.50 mm` scene label, always-visible annotation,
  named 22-pixel bold font and bold task result. The oblique scene export
  `supplied_pcb_wall_measure.png` was visually inspected and the full bold text
  is legible above the PCB. Empty-selection and leave cleanup still pass.
- The first added wall test cleared and re-added the new pair in one event;
  that intentionally invokes additive replacement, keeping an earlier pick.
  Separating the clear and next selection into successive events fixed the
  harness. That initial run was not a clean pass.
- GUI-result validator **10/10**, compilation and `git diff --check` passed.
  All native tests used disposable config files; the user's STEP file was read
  without modification and remains an optional local fixture.

## White measurement cards and geometry-specific readouts (2026-11-01)

The latest user request supersedes the earlier plain bold label and distance-only
scope. Measure now draws an opaque white rectangle with a black one-pixel border,
black regular text, and a divider between label/value columns, following the
supplied examples. Qt font metrics size an 18-pixel screen-space card, and Coin
`SoImage` displays its RGBA pixels inside the existing unpickable `SoAnnotation`.
Black leaders with white underlays remain visible on dark backgrounds. The task
result remains bold; no native preferences or document objects are changed.

Single selections report Length; Radius/Diameter/Center and Circumference or arc
length/chord/angle; point coordinates; face Area/Perimeter; cylindrical and
spherical properties; and whole-body Area/Volume. Pairs report distance or centre
distance, applicable acute line/plane/axis angles, optional XYZ components and
edge/face totals. Three vertices measure an angle at the second vertex; larger
edge/face selections give totals. Periodic seam edges are excluded from perimeter.
The previous selection clearing, linked placement and lifecycle cleanup remain.

The official Measure tool help and `IMeasure` results were consulted. The new
[Measure spec/catalog](specs/measure.md) lists supported quantities and explicit
gaps: maximum/custom arc distances, independent projection/normal modes, projected
area, arbitrary surface-point picks and custom coordinate systems/rotation are
not implemented. Volume is documented as an extension, not an `IMeasure` result.
Pair angles currently use the smaller unoriented angle, not supplementary/reflex
choices. The catalog replaces the earlier distance-only ribbon-content contract.

Verification on FreeCAD 1.1.4 Windows:

- **552/552 headless**, no failures/errors/skips (`scratch/measure_cards_headless.log`).
  Added white/black card pixels/text sizing, single length/coordinates and
  perimeter seam-exclusion checks; existing selection and axis tests still pass.
- **64/64 native Measure checks** with disposable configs and the optional
  supplied STEP (`scratch/gui_8aantpcz/`). The 53 standard cases include labels,
  values, card rendering for eight geometry types, face/body quantities, line
  and three-point angles, XYZ and totals, periodic seams, centre/clearance modes,
  native mouse clicks, clearing, external close and leave. Eleven supplied-file
  checks retain the exact **1.500 mm** rim-centre/inner-wall-axis result and
  **0.925 mm** clearance. Native scene exports and individual card PNGs visually
  inspected; the white/black label is legible over the actual PCB.
- GUI-result validator **10/10**, Python compilation and `git diff --check` pass.
  Earlier exploratory runs exposed unsupported exponentiation of FreeCAD Unit
  objects and a harness assumption that 100 mm² must format as `100 mm²` instead
  of `1 cm²`. Unit construction now parses dimensional unit strings; the test
  compares the underlying area. Those earlier runs were not clean passes.

Reference documentation for specialized unsupported modes is not verification
of those modes. No user model, saved measurements or profile files were modified.

## Measure button active state and toggle-off (2026-11-01)

The Measure ribbon button now stays checked/highlighted for the lifetime of the
measurement task. Checked buttons use Selection fill and an Accent border in
both themes. The active Measure button remains enabled even when FreeCAD disables
its native Measure action during a task, so pressing it again always stops the
session and removes its callouts, leaders, rows, image data and task form.

Checked state follows the real session: clearing picks leaves the tool selected
and ready, while task/external close or leaving unchecks it immediately. Failed
activation is reconciled after dispatch. Start remains idempotent; only ribbon
clicks use toggle behavior. Targeted button synchronization on task destruction
avoids a full ribbon/context refresh inside widget teardown. No persistent
preference, command id, ribbon count or recovery format changes.

Verification:

- **554/554 headless**, no failures/errors/skips (`scratch/measure_toggle_headless.log`),
  including authoritative checked state, keeping the active button stoppable,
  and start/stop toggle dispatch.
- **73/73 native Measure checks** including the optional user PCB
  (`scratch/gui_9u84ea0y/`): actual button on/off/reopen, visible painted highlight,
  all owned measurement state removed on off, continued active state with empty
  selection, unchecked on external close/leave, plus all geometry/style cases.
  `measure_button_on.png` and `measure_button_off.png` visually inspected.
- Broader native run `scratch/gui_erc5hmbq/`: Measure **61/61** before the added
  pixel assertion, smoke **31/31**, all five tabs, native dark/light themes
  **22/22 each**, runner exit **0**. Final targeted synchronization and visual
  assertion were subsequently covered by the 73-check run above.
- GUI-result validator **10/10**, compilation and `git diff --check` pass.
  Native tests used disposable profiles. The user profile and STEP file were
  not modified.

## Pre-PR Measure audit (2026-11-01)

Audited the complete pending Measure change: geometry and units, selection order,
world/link placement, native command dispatch, checked state and scoped styling,
Qt/Coin lifetimes, failure cleanup, profile isolation, restore/recovery behavior,
CI coverage, metadata/licenses and specification consistency. Added user-facing
usage and the missing module/API/spec-index entries. No release bump is made.

Four findings were reproduced with failing headless regressions and corrected:

- A retired task timer could call the global stop function after replacement.
  Lifetime checks now ignore closed or non-current sessions.
- Checking the document's remembered view missed the actual Start/drawing window.
  Start and lifetime checks now follow `getMainWindow().getActiveWindow()` with
  the established active-view fallback; Measure refuses activation without a camera.
- A deleted native view could prevent cached scene/image state from being cleared.
  Cleanup now releases owned data before attempting to detach old scene graphics.
- Restoring an earlier pick appended it after the newest native selection. Mixing
  plain and additive picks could move the middle vertex of a three-point angle.
  Measurement now preserves chronological order across both kinds of click.

Final verification on Windows / FreeCAD 1.1.4:

- **559/559 headless**, no failures/errors/skips, using both FreeCAD's PySide shim
  (`scratch/measure_pr_audit_headless.log`) and PySide6 aliases
  (`scratch/measure_pr_audit_alias_headless.log`). The ordinary system Python
  lacks PySide6, so the alias run used bundled Python 3.11 with shim selection
  redirected in a scratch-only launcher; no system package was installed.
- The complete **20-suite native runner passed**, exit **0**
  (`scratch/gui_3a6hk425/`): Measure 62, smoke 31, sketch 20, orientation 84,
  orbit 49, features/drawing 51, assembly tree 104, appearances 38, Report view 9,
  Report startup 3, five tabs captured, Cancel 16, Discard 9, Save 9, after-quit 5,
  autoload 6, crash 2, recovery 3, dark and light themes 22 each. Saved-config
  validation passed after both Save and Discard.
- That full run began before the audit fixes were finished. The final production
  Measure paths were subsequently verified by **83/83 native checks**, exit **0**
  (`scratch/gui_pdn3160c/`), including the optional supplied STEP, mixed pick-order
  angle, Start-page teardown/refusal, document switch/closure, cached-data cleanup
  and reopening. The supplied hole still measures **1.500 mm** to the PCB edge.
- GUI-result validator **10/10**, Python compilation and staged whitespace checks
  pass. All native tests used disposable configs. No STEP file, config, image,
  scratch output or generated bytecode is included in the commit.

The known advanced measurement gaps remain explicitly listed in
[the Measure catalog](specs/measure.md). The earlier reported numerical zero for
the exact supplied inner-face/edge pair remains unreproduced; verified rendering
and the current regressions show 1.500 mm. No additional actionable finding
remained in this audit. Hosted CI status must be checked on the PR separately.
