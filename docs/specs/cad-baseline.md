# JellyJams specification: CAD regression baseline

> **Implemented in:** `tests/cad_fixtures.py`, `cad_models.py`, `gui_cad_baseline.py`,
> `run_baseline.py`, `test_cad_fixtures.py`, `fixtures/cad_manifest.json`.
>
> **Status:** see [../status.md](../status.md).

## 1. Purpose and gate

Before new feature work, and again before submitting it, run
`python tests/run_baseline.py`. This combines the existing headless tests,
fixture/runner unit tests, and native CAD and smoke. Add the affected area's
checks with `--extra-suites`; the selection table in [../testing.md](../testing.md)
is part of the contributor workflow. Sketch-first and the broad feature suite
remain required for their areas, rather than for every unrelated change.
Use `--full` to run all registered GUI suites in the same gate for full regression.

Each selected suite MUST run once, preserving first-requested order. The core
cannot be removed with `--extra-suites`. Shared-profile dependencies still require
`discard` before `after`, `crash` before `recover` and `report_view` before
`report_startup`. Invalid selections MUST fail before any tests or downloads.
`--plan` only prints the selection and MUST NOT require FreeCAD, launch tests or
download data. Reports record the selected suites and per-stage/suite elapsed time.
The GUI-only runner defaults to the same core, with `--suites` for focused runs
and `--full` for all suites. A baseline/full run already includes headless checks;
do not repeat them separately for unchanged code on the same interpreter.

The fast fixture unit tests are configured for hosted CI on Windows and Linux
without FreeCAD or network access. A passing stub CI job does not certify native geometry.
The contributor workflow requires the local gate; repository branch protection
and remote native runners are not configured by this change.

Missing FreeCAD, missing or corrupt data, exceptions, timeouts, failed checks and
incomplete native results MUST fail. Offline mode MUST NOT download or silently
skip tests. Results and model artifacts go into unique `scratch/` folders.
The CAD script MUST verify both config paths belong to its runner output folder
before activating the workbench. Rejection MUST leave that FreeCAD session and
its documents open; quitting would save an unowned profile.

## 2. Reference data

The [manifest](../../tests/fixtures/cad_manifest.json) records exact HTTPS URLs,
commit revisions where available, SHA-256, byte lengths, usage terms, ZIP member
names, case identifiers, dimensions and expected geometric properties. The
[catalog](../cad-fixtures.md) explains sources, formulas, operations and limitations.

Third-party STEP files and drawings remain in `scratch/cad_fixtures/`; they are
test data, never add-on resources. Downloads MUST be verified before installation
in the cache. ZIP downloads expose only individually pinned, named members;
archive paths are never extracted as directories. Downloaded code is never run.
Subsequent fetches use a verified cache without network access.

Normal tests MUST NOT regenerate expected values, update hashes, modify the
manifest, or generate their own reference STEP files. An upstream revision or
reference change requires deliberate review of source, dimensions, licenses,
expected values, tests, this spec and the status record in one change.

There are two distinct kinds of references:

- **14 analytic cases:** independently stated dimensions from the CC0
  step-conformance corpus. Expected volume, area, centre and bounds are calculated
  from those dimensions, not from a model rebuilt by JellyJams.
- **6 NIST cases:** published dimensioned AP203 parts and companion drawings,
  with fixed import regression snapshots measured using FreeCAD 1.1.4. These
  snapshots are not independent analytic certifications or GD&T/PMI tests.

The latter use summed solid volumes and volume-weighted solid centres. Querying
a compound's volume can differ from summing its solids on these complex models;
the metric definition MUST remain consistent. Bounds use
`optimalBoundingBox(False, False)` so display triangulation cannot change them.

## 3. Required native coverage

1. Every reference: checksum verification, valid closed solids, solid count,
   volume, surface area, centre of mass and geometric bounds after import.
2. Every analytic reference: export to a new STEP, reimport, repeat all six
   geometric checks. Unit, scale, placement and repeated occurrences are included.
3. Rebuild cylinder, cone, hemisphere, washer, tiny pin, large disc and a rounded
   plate with 100 holes using native, fully constrained Sketcher geometry and
   Part Design Pad/Revolution/Fillet/Pocket features.
4. Compare each rebuild with the independently downloaded STEP using both
   geometric properties and the volume of both directional Boolean differences.
   No alignment or rescaling is applied to conceal a placement/unit error.
5. Edit driving radii for all four circular Pad recipes; verify recomputation,
   Undo and Redo. Save/reopen every rebuilt document, touch its native features,
   recompute and compare with the original reference again.
6. Exercise JellyJams' mathematical geometry codec on the cylinder, washer,
   cone and hemisphere. The cone explicitly uses parametric trims: its apex is
   outside the unbounded cone support's default trimmed face. This does not
   claim that every legacy three-dimensional-only cone trim is supported.
7. Invoke JellyJams New Assembly and use native joints to solve repeated STEP
   components from wrong initial placements. Check shared source identity,
   position/orientation, complete assembly geometry, mated rotation refusal and
   save/reopen/perturb/resolve. A deliberately wrong position MUST fail geometric
   equivalence despite preserving total volume.
8. Solve a three-component spool with a grounded cylinder and two linked washers;
   check the envelope, mass properties, zero interference, axial clearances and
   JellyJams' offered cylindrical mates on actual imported faces.
9. Dispatch Pad and Pocket through JellyJams' ribbon route, accept the native
   length fields, compare the resulting bore with analytic geometry and verify
   that JellyJams stays active with no task left open.

The assemblies use native fixed joints with explicit custom joint coordinate
systems. They test the solver, persistence and JellyJams selection/availability;
they do not claim full interactive mating, mechanism motion or all joint types.
Existing `gui_features.py` additionally clicks an Add Mate button and accepts its
native joint task; select `--extra-suites features` for assembly changes or `--full`.

## 4. Tolerances and exclusions

Lengths/centres use absolute **1e-5 mm**, without a relative allowance for a part
100 m from the origin. Volume and area use the larger of **1e-6** in their native
units and **1e-7 relative**. Rebuild Boolean residuals must be at most the larger
of **1e-7 mm3** and **1e-8 of reference volume**. Non-finite values always fail.
Neither face ordering nor arbitrary edge numbers define expected geometry.

The NURBS cylinder, hemisphere and half torus are research candidates, excluded
from the passing baseline because initial default FreeCAD mass properties
disagree with their analytic definitions. NIST export/reimport and Boolean
equivalence also remain unqualified: initial measurements and Boolean results
were inconsistent. These are recorded findings, not relaxed passing tolerances.
The catalog lists future NIST assembly and reconstruction scenarios separately.

## 5. Acceptance criteria

1. Fixture unit tests fail for corruption, truncation, unsafe paths, missing pins,
   missing data, non-finite reference values and partial native reports.
2. The native script refuses configs outside its runner-owned scratch directory
   before activating JellyJams, and verifies that the installed add-on resolves
   to this checkout.
3. A successful complete native run contains at least **333 checks** with no
   errors. The gate also requires smoke and the area's selected GUI suites.
4. No code under `jellyjams/`, user profile, model library, or add-on resource is
   changed by preparing the fixtures or running these tests.
5. Verification reports distinguish analytic truth, measured regression
   snapshots, existing GUI interaction coverage and unverified scenarios.
