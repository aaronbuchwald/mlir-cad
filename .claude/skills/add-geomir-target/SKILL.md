---
name: add-geomir-target
description: Onboard a new CAD backend/target to geomir (e.g. add Tekla, Revit, Onshape, IFC, Blender). Use when the user asks to add a target, add a backend, port geomir to another CAD system, or run conformance for a new kernel. Covers scaffolding, op-by-op implementation with smoke gates, conformance, emit/lift for source-form targets, capability manifests, CI wiring, and the human checkpoints (licenses, installs, credentials).
---

# Add a geomir target

You are onboarding a new backend to the geomir multi-level IR. The contract:
**never declare capability — measure it.** Every phase ends with a machine
gate; do not proceed past a failing gate.

Read first: `CLAUDE.md` (conventions), `docs/ROADMAP.md` (which phase this
target belongs to and its human checkpoints), `conformance/registry.py`.

## Phase 0 — Access route + human checkpoints (BLOCKING)

Determine the route before writing code:

| Route | Examples | Human needed for |
|---|---|---|
| in-process pip library | OCCT/cadquery, manifold3d, IfcOpenShell, trimesh | nothing (HC-0: run on a machine with PyPI) |
| cloud API | Onshape, Rhino.Compute, APS Design Automation (Revit) | account, API keys, ToS review, spend caps (HC-3/4/8) |
| desktop plugin | Tekla Open API, ArchiCAD, Vectorworks | license, OS/VM, GUI install + activation, CI runner (HC-7) |

STOP and present the human a checklist of exactly what they must provision
(license, account, credentials, machine) before continuing. Do not attempt to
work around a licensing checkpoint.

## Phase 1 — Scaffold

1. Create `geomir/backends/<name>_backend.py` implementing the interface
   (see `geomir/eval.py` docstring): `box, cylinder, translate, union,
   difference, intersect, fillet, volume, bbox, mesh` + `name` attribute.
   - Unsupported ops must `raise UnsupportedOp(self.name, "geom.<op>")` —
     never approximate silently. The per-element fallback machinery depends
     on this.
   - Keep version-sensitive API calls in small helpers at the bottom of the
     file (see `occt.py` `_shape`/`_volume` pattern) so drift is localized.
2. Register in `conformance/registry.py` `BACKENDS` (+ `TOLERANCES` entry:
   start conservative — `{"exact": 1e-6, "curved": 0.01}` — and tighten from
   measured data later).

Gate: `python -c "from conformance.registry import load_backend; load_backend('<name>')"`.

## Phase 2 — Op-by-op with smoke gates

Implement in this order (dependency-light first): `box -> translate -> union ->
difference -> intersect -> cylinder -> repeat_x -> fillet`.
After EACH op: `python -m conformance.run --backend <name>` and confirm that
op flips to supported/PASS in the card before starting the next. Volume comes
from the target's own math where possible (or mesh + divergence theorem, see
`manifold_backend.py`).

Semantics to preserve exactly (from `geomir/ir.py` OP_SPECS docs):
box corner at origin +x/+y/+z; cylinder base-center at origin, axis +z;
units mm; faceting/tessellation is a backend constructor kwarg, never recipe
data.

Gate: report card shows every implementable op PASS; genuinely impossible
ops (e.g. fillet on mesh kernels) show UNSUPPORTED — that is a valid,
recorded outcome, not a failure.

## Phase 3 — Full conformance

`python -m conformance.run --backend <name>` must end `CONFORMANT`:
corpus L0-L2 PASS within the tolerance contract; L3 capability-gated;
L4 informational diffs reviewed (paste any INFO-DIVERGED rows into the PR
description). Then run the fuzzer:
`python -m conformance.generate --mode diff --seeds 200 --backend <name>
--backend occt --backend sampler` — triage findings (HC-6: a human decides
what is reportable upstream).

Gate: CONFORMANT card + committed `conformance/targets/<name>.json` manifest
(auto-generated — do not hand-edit).

## Phase 4 — Source form (only if the target has a language)

If the target has a textual source language (OpenSCAD -> done; FeatureScript,
FreeCAD Python, GH XML), add `emit_<lang>` (+ lifter for the emitted subset
if lifting is feasible) following `geomir/scad.py`'s structure: parameters
stay live, expressions emitted as expressions, unrepresentable elements
lower to a baked import with a comment. Add emit->lift fixed-point + volume
tests mirroring the scad ones in `tests/run_tests.py`.

## Phase 5 — CI + docs

1. Add a job/stanza to `.github/workflows/conformance.yml`: pip targets go in
   the `kernels` job; cloud targets get a job gated on secrets; desktop
   targets get a self-hosted-runner job (HUMAN provisions the runner).
2. Update: `CLAUDE.md` file index, `docs/HANDOFF.md` status ledger,
   `docs/ROADMAP.md` phase checkbox.
3. Commit sequence: scaffold -> per-op batches -> conformance+manifest -> CI+docs.

## Appendix — Tekla Structures cheat sheet (Phase 3 target, HC-7)

Access: Tekla Open API (.NET/C#), requires a running licensed Tekla instance;
no headless cloud mode known (verify current Trimble docs). Connector is a
separate C# project speaking to Python via a thin JSON-RPC bridge or file
drop; the Python backend class wraps that bridge.

Lowering map (Tekla's native rep is procedural — closest proprietary match
to this dialect):

| geomir | Tekla Open API |
|---|---|
| geom.box | ContourPlate or Beam with rectangular profile string (e.g. PL50*100) |
| geom.cylinder | Beam with round profile (D<2r>), vertical |
| extrusion (Phase 1 dialect) | Beam/PolyBeam + profile string |
| geom.difference | BooleanPart (type Cut) — Tekla parts carry cut lists natively |
| geom.union | separate parts or welded assembly (union is often organizational in Tekla) |
| geom.repeat_x | array of parts (instanced — cheap in Tekla) |
| geom.fillet | chamfers on plate corners only — likely UnsupportedOp for general edges |
| element roles | Tekla class / name / profile metadata |

Lifting: parts expose profile + boolean cuts through the API — lift to
recipe is unusually tractable; bake only what the profile catalog can't
express. Volume oracle: Part.GetSolid() mesh + divergence theorem.

Human checkpoints for Tekla specifically: license/partner program, Windows
VM or self-hosted runner, GUI install + first-run activation, model template
selection. Everything else is code.
