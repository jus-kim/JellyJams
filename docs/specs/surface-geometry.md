# JellyJams specification: Reconstructed surface geometry

> **Implemented in:** `jellyjams/surface_geometry.py`, `surface_feature.py`, `surface_rules.py`, `local_fillet.py`, `surface_boolean.py`.
>
> **Status:** see [../status.md](../status.md).

## 1. Purpose

When a source blend cannot be recreated by FreeCAD's fillet operator, a reconstruction
may use mathematically defined surface tools in native linked Boolean features. This
preserves editable earlier sketches/features and exposes B-spline control points.
It does not reproduce the original fillet dialog or promise a driving radius.

## 2. Document contract

The tool is a `Part::FeaturePython` with its properties in `JellyJams`:

| Property | Meaning |
|---|---|
| `GeometryDefinition` | Read-only JSON, schema `version: 1`; solids contain trimmed faces, analytic or rational B-spline supports, and oriented three-dimensional boundary curves. No BREP, mesh, executable code, or external file reference. |
| `SurfaceNNPoles` | Editable `App::PropertyVectorList` for B-spline face NN, one-based across all solids. U-major order; row/column counts appear in the property description. |
| `GeometryError` | Read-only last execution error; empty after success. |
| `SourceFeatureName` | Read-only provenance label. |
| `SourceNominalRadius` | Optional read-only original radius. It is explicitly reference metadata, not a driving parameter. |

Recompute rebuilds the geometry from the mathematical definition and current control
points. It must reject grids of the wrong size, non-finite coordinates, unsupported
schema versions, null/open/invalid output, and missing mathematical data. Failure
clears the cached shape, records `GeometryError` and reports through JellyJams console.
The feature's native placement must survive both successful and failed recomputes.

The codec retains analytic planes, cylinders, cones, spheres and tori where present;
it stores rational B-spline poles, weights, knots, multiplicities and degrees otherwise.
Original face areas disambiguate the two sides of a periodic trimming loop during
reconstruction. They are reference metadata; an interior-pole edit may change area.
Boundaries retain analytic lines, circles and ellipses or rational B-splines. Not every
periodic seam/pole arrangement can be reconstructed; unsupported topology must fail
the closed-solid preflight rather than be accepted as a converted part.

Schema 1 also permits optional per-solid `edge_id` references and mathematical
`geometry2d` B-spline trimming curves (UV poles, weights, knots, multiplicities,
degree, periodicity and range). Shared edges retain one topological identity across
faces. Parametric trims can be captured explicitly to avoid another 3D projection;
older definitions without these fields remain readable. Unsupported or inconsistent
trim arrangements still fail closed-solid preflight.

Changing interior poles is the normal edit: it leaves the shared boundary in place.
Boundary edits can require coordinated changes to adjacent surfaces. Topological
validity is checked; advanced Boolean interference checks and comparison with the
reference remain part of the conversion's validation, and are reported separately.

## 3. Scope and lifecycle

The API creates document features; it changes no application parameters, UI, or
workbench state. No activation hook or ribbon command is registered. Control points
are edited using FreeCAD's native vector-list property editor. The document can be
reopened/recomputed without the original CAD application or source files, provided
JellyJams is installed. Native linked Booleans remain standard FreeCAD objects.

## 4. Acceptance criteria

1. Mathematical definitions round-trip a box and a cylinder with unchanged geometry.
2. A B-spline interior-pole edit changes the recomputed solid and a dependent feature.
3. Save/reopen preserves the proxy, mathematical definition, and editable points.
4. Invalid point lists clear stale geometry and expose an error without escaping a callback.
5. Original radii are read-only provenance and must not be presented as driving controls.
6. Creation/recompute does not alter application preferences or workbench UI.

## 5. Local fillet change tools

`local_fillet.create` creates a linked `Part::FeaturePython` change tool when the
constant-radius geometry API succeeds on an isolated region. It returns the material
added or removed by the round. Standard native Boolean features apply that change to
the full model; a native mirror can share the tool's radius across symmetric regions.

The following properties are a document compatibility contract, in `JellyJams`:

| Property | Meaning |
|---|---|
| `RoundBase` | `App::PropertyLinkSub`: input object and selected edge names. |
| `RoundScope` | Link to an axis-aligned native `Part::Box` that isolates a material-change tool; empty for a full-result fillet. |
| `Radius` | Editable length that actually drives the constant-radius fillet operation. |
| `RoundOperation` | Enumeration `Add material`, `Remove material` or `Full result`; selects the returned geometry. |
| `GeometryError` | Read-only error, cleared after a successful recompute. |

Recompute copies the input geometry, intersects it with a fresh box at the linked
scope's dimensions and placement, matches unchanged selected edges by curve type,
endpoints and length, and calls `makeFillet`. Clipped or missing selections, rotated
scopes, non-positive/non-finite radii, or null/open/invalid change solids fail with an
empty shape and an error. Placement survives failures and successful recomputes.
The converter must verify that scope boundaries do not change the intended corner
convexity or remove/add the wrong material. Topology-changing upstream edits may
require repairing selections or the scope, as with native edge-based features.

`Full result` requires an empty scope and applies the constant-radius geometry API
to a copy of the complete input solid. Its output is the rounded solid rather than
a material-change tool. This mode supports a native Body's linked BaseFeature and
mixed convex/concave selections when the kernel can construct them. A kernel failure
must clear the shape and report an error; no unverified radius adjustment is applied.

Acceptance requires a radius edit to change volume, invalid radii to clear stale
geometry, valid values to recover, and save/reopen to restore the proxy and links.
There are no application settings, lifecycle hooks or ribbon commands. Native property
editors expose the driving radius and scope; this is distinct from a reconstructed
surface's read-only `SourceNominalRadius` provenance.

## 6. Linked Boolean cell selection

`surface_boolean.create` creates a `Part::FeaturePython` that links its inputs and
recomputes a `Cut` or `Fuse` through the geometry API. It changes no application UI
or preferences. All added properties use the `JellyJams` group:

| Property | Meaning |
|---|---|
| `BooleanBase`, `BooleanTool` | Native document links to the inputs. |
| `BooleanOperation` | `Cut` or `Fuse`. |
| `BooleanTolerance` | Finite, non-negative kernel intersection tolerance. |
| `KeepLargestSolid` | Explicitly retain only the largest solid and discard all other connected cells. Defaults false. |
| `DiscardedSolids` | Read-only number of discarded cells after a successful recompute. |
| `GeometryError` | Read-only error, empty after success. |

An explicit single-cell selection may recover a valid main solid from a kernel
result containing invalid extra cells. The selected output must itself be valid,
closed and solid; failure clears old geometry and reports through the console.
A union must retain at least the largest input solid's volume within numerical
integration tolerance. A kernel output that loses the main input and leaves only
a tiny tool cell is rejected, even if that cell is individually valid.
Advanced checks and comparison with the intended geometry remain separate conversion
requirements. Cell selection must never be enabled implicitly for arbitrary user
Booleans. Save/reopen retains the proxy, properties and input links.

Acceptance requires a split-box cut to retain the largest cell only when requested,
report the discarded count, and retain both cells when the option is switched off.
