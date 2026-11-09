# Dimensioned CAD fixtures and test catalog

The executable contract is [specs/cad-baseline.md](specs/cad-baseline.md).
The fixed [manifest](../tests/fixtures/cad_manifest.json) is the machine-readable
catalog. All geometry is interpreted in millimetres, even when STEP uses inches.

## Sources investigated

| Source | Existing tests/data | Decision |
|---|---|---|
| [step-conformance, revision 96f30bbe](https://github.com/dan335/step-conformance/tree/96f30bbe09549ef37dbd0a956d70bd8a183fd5d2) | Generated STEP, exact profile definitions, importer checks for units, shape, placement and repeated occurrences | Use 14 compact analytic cases; fetch original STEP and truth JSON with SHA-256 pins. The corpus has its own [CC0 dedication](https://github.com/dan335/step-conformance/blob/96f30bbe09549ef37dbd0a956d70bd8a183fd5d2/corpus/LICENSE). |
| [SolidCraft reference tests](https://github.com/tangency-labs/solidcraft/blob/f7ae792b6929beed856e0a26ea63f95244e4609e/docs/oracle.md) and [STEP conformance tests](https://github.com/tangency-labs/solidcraft/blob/f7ae792b6929beed856e0a26ea63f95244e4609e/tests/step-conformance/README.md) | Parametric recipes, analytic/FreeCAD reference properties, STEP round trips; also uses the CC0 corpus above | Adopt the independent-reference approach and the same public corpus. Write native FreeCAD recipes and harness code here; do not copy Rust implementation code. |
| [FreeCAD 1.1.4 Assembly TestCore](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/src/Mod/Assembly/AssemblyTests/TestCore.py) | Grounded components, native joints, connector placements, solver checks | Use the native APIs and extend coverage with known STEP geometry, bad initial poses, repeated links, clearances and reopen/resolve. Original test implementation; upstream LGPL source is not copied into MIT files. |
| [NIST PMI model collection](https://www.nist.gov/ctl/smart-connected-systems-division/smart-connected-manufacturing-systems-group/mbe-pmi-0) | Published drawings and geometry-only AP203; FTC 07/08/09/10 and CTC 02/04 form assemblies | Fetch six parts, drawings and the FTC assembly illustration. Retain the supplied public-domain/usage acknowledgements. Test import and fixed geometry snapshots initially. |
| [SolidWorks' NIST assembly example](https://blogs.solidworks.com/products/solidworks/3d-pdf-sample-national-institute-standards-technology-nist-test-assembly/) | Explains assembling NIST FTC 07/08/09/10, including exploded configurations | Useful assembly reference; use the original NIST data rather than redistribute unrelated proprietary tutorial models. |

NIST permits unrestricted use and requests acknowledgement. These tests use NIST
data; NIST does not endorse JellyJams. No NIST logo or vendor artwork is bundled.
No copied third-party code or third-party model files ship with the add-on.

## Current analytic part tests

Dimensions below come from the upstream
[generator definition](https://github.com/dan335/step-conformance/blob/96f30bbe09549ef37dbd0a956d70bd8a183fd5d2/generate/src/main.rs),
not from reverse measuring JellyJams output. The upstream Rust generator is a
reference to read, never a dependency to build or execute.

| Case | Dimensions / arrangement | Rebuild and feature tests |
|---|---|---|
| `cylinder` | Diameter 20, height 30 | Origin-constrained circle + radius + Pad; driving radius edit, Undo/Redo, save/recompute; JellyJams codec |
| `cylinder_seam` | Same cylinder, explicit seam topology | Import/export against the same analytic properties |
| `cylinder_inch` | Same physical cylinder, inch units in STEP | Detect a 25.4x scale error |
| `cone_point`, `cone_point_vertex` | Radius 10, height 30, sharp apex | Constrained triangular profile + 360-degree Revolution for the first; verify both apex encodings; codec with parametric trims |
| `dome` | Hemisphere radius 20, flat base at Z=0 | Constrained quarter-circle profile + Revolution; codec |
| `washer` | OD 40, ID 10, thickness 3 | Two concentric dimensioned circles + Pad; radius edit, Undo/Redo, persistence; codec |
| `tiny_pin` | Diameter 0.5, height 2 | Circle + Pad at sub-millimetre scale; editable radius and persistence |
| `sheet_disc` | Diameter 3600, thickness 19 | Circle + Pad at metre scale; editable radius and persistence |
| `far_cylinder` | Cylinder translated to X=100000 | Absolute geometric bounds and centre checks, independent of origin distance |
| `cylinder_placed` | Cylinder origin (40,-25,10), axis (1,1,1)/sqrt(3) | Detect lost assembly transform and rotated extents |
| `cylinder_twice` | Original cylinder plus occurrence at (60,0,10), axis +X | Preserve two solids and their positions; reference for native assembly solve |
| `plate_100_holes` | 100 x 100 x 10, R4 corners; 100 diameter-6 holes, 10 pitch, first centre (5,5) | Constrained rectangle + Pad + four vertical edge Fillets + 100 constrained circles + Pocket |
| `grooved_shaft` | Diameter 20, length 501; 250 V grooves, depth 0.5, pitch 2 | Import/export large topology (753 original faces); no sketch rebuild in the mandatory gate |

All seven rebuild recipes also compare both Boolean differences against the
downloaded reference. Equal volume alone would miss a misplaced hole.
The plate uses a dimensioned circle grid, not a Part Design pattern feature;
linear/circular feature-pattern commands are future extensions.

Independent property formulas include:

- Cylinder: `V = pi*r^2*h`, `A = 2*pi*r*(r+h)`, centre at `h/2`.
- Cone: `V = pi*r^2*h/3`, `A = pi*r*(r+sqrt(r^2+h^2))`, centre at `h/4`.
- Hemisphere: `V = 2*pi*r^3/3`, total area including base `3*pi*r^2`, centre at `3*r/8`.
- Washer: `V = pi*(R^2-r^2)*h`, `A = 2*pi*(R^2-r^2)+2*pi*(R+r)*h`.
- Plate section: `S = 10000-(4-pi)*16-100*pi*9`; volume `10*S`;
  area `2*S+10*(400-32+8*pi+600*pi)`. Symmetry gives centre `(50,50,5)`.
- Shaft: split each V groove into two half-millimetre conical frusta;
  use frustum volume `pi*h*(R^2+R*r+r^2)/3` and lateral area
  `pi*(R+r)*sqrt(h^2+(R-r)^2)`, plus the straight lands and end discs.

## Current assembly and user workflow tests

| Scenario | Known result | Checks |
|---|---|---|
| Repeated cylinder occurrences | Base at origin; second at (60,0,10), cylinder axis +X; envelope (-10,-10,0) to (90,10,30), volume `6000*pi` | JellyJams New Assembly, one shared STEP source, ground + native fixed joint, solve from a displaced/rotated pose, compare complete reference shape, refuse free rotation of mated link, deliberately wrong pose detected, save/reopen/perturb/solve |
| Three-component spool | Cylinder between two washers at Z=-3 and Z=30; envelope 40 x 40 x 36; volume `5250*pi`; centre (0,0,15) | Ground shaft, solve both fixed joints, three solids, zero common volume for each pair, contact with shaft, 30 mm washer gap; JellyJams Hinge/Concentric/Slider offered for selected cylindrical faces |
| Ribbon-built bored cylinder | OD 20, ID 10, length 30; volume `2250*pi` | Ribbon Pad, native length/OK, ribbon Pocket, native length/OK, exact shape, active JellyJams and closed task |

The spool is an original, explicitly specified test arrangement of public corpus
parts, not a standardized manufactured assembly. Its two end washers contact
the cylinder's end faces; their bores are not shaft fits. Custom fixed-joint
coordinate systems deliberately prescribe positions without depending on edge
numbering. They are not a substitute for tests of concentric/distance mating.

## NIST cases and follow-on test list

The fetched files include FTC 07 (box), 08 (cover), 09 (plate), 10 (small part),
CTC 02 and CTC 04, plus each drawing and the FTC assembly illustration. The
drawings include inches as well as metric examples; their notes make the native
model authoritative for dimensions not explicitly called out. The initial
six tests verify valid closed import, solid count and fixed geometric snapshots.
Their numerical values are clearly marked as measured FreeCAD regressions.

The following are **planned tests, not passing coverage**:

| Priority | Scenario | Required independent reference |
|---|---|---|
| Next | Assemble FTC 07/08/09/10 from separated STEP parts | Reviewed datum frames, transformations and mating references derived from the assembly illustration and model geometry; expected clearances/interference |
| Next | Assemble CTC 02 and CTC 04 | Reviewed mounting positions and bolt-hole alignment; neither image similarity nor arbitrary placement is sufficient |
| Next | Rebuild a selected NIST plate and add holes/counterbores | Transcribed drawing dimensions with unit conversions and model-derived unspecified dimensions distinguished |
| Later | Rebuild complete NIST box/cover using shell, pattern, fillet and chamfer features | Exact feature recipe, revision and robust geometric comparison |
| Later | Hinge/slider/concentric/distance solver mechanisms, limits and incompatible mates | Analytic end positions, allowed degrees of freedom and explicit failure expectations |
| Investigate | Rational NURBS cylinder/dome/half torus, NIST STEP round trips | Resolve mass-integration and Boolean discrepancies before adding to the mandatory passing gate |

The first 1.1.4 research pass measured NURBS cylinder volume about 9499.417
against analytic 9424.778 mm3, and NURBS hemisphere 16832.700 against
16755.161 mm3. This alone does not establish whether the issue is geometry,
the source encoding or default mass integration. NIST CTC 02's scalar volume
changed about 302 mm3 after export/reimport, and coincident-shape Boolean
comparisons on complex NIST parts were unreliable. The initial failed results
are retained under `scratch/gui_6bmy54ec`; no tolerance was widened to make these
cases pass. The mandatory round-trip checks cover the 14 analytic cases only.

## Running and reviewing

```powershell
# Download once, or reuse verified cached data. No FreeCAD window is opened here.
python tests/cad_fixtures.py fetch
python tests/cad_fixtures.py catalog
python tests/cad_fixtures.py verify

# Required before feature work and again before submission.
python tests/run_baseline.py
python tests/run_baseline.py --offline

# Add only affected areas; the core and any repeated suite names run once.
python tests/run_baseline.py --offline --extra-suites sketch features
python tests/run_baseline.py --extra-suites assembly_tree features --plan

# Release/full regression: all native suites, including the core, once.
python tests/run_baseline.py --offline --full

# Newer supported host; its bundled Python is selected automatically.
python tests/run_baseline.py --offline --freecad "C:/Program Files/FreeCAD 26.3/bin/FreeCAD.exe"

# Focused development run after fetching, always in throwaway configs.
python tests/run_gui.py --suites cad_baseline --timeout 600
python tests/test_cad_fixtures.py
```

`scratch/baseline_*/summary.json` and stage logs report the complete gate.
The native log points to `scratch/gui_*/cad_baseline.json`, seven rebuilt
`.FCStd` files, two assembly documents, a spool STEP export and preview, and the
ribbon workflow document. The JSON includes the FreeCAD version and manifest
hash. Inspect the actual result; an output model or screenshot alone is not a
passing test.
