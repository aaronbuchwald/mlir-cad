# geomir — an MLIR-style multi-level IR for CAD exchange (working demo)

The smallest working demonstration of the architecture from
*A Compiler-Theoretic Analysis of AEC Geometry Interoperability*: one
parametric **recipe IR** lowered onto **two open-source kernels with
genuinely different underlying math**, exchanged through an artifact that
carries **recipe + baked oracle**, validated with a **match_cast-style
tolerance contract**, degrading **per element, never per file** — and
lowered to / lifted from **OpenSCAD source** with parameters kept live.

| | OCCT (via CadQuery) | Manifold (via manifold3d) |
|---|---|---|
| Used by | FreeCAD | OpenSCAD (boolean engine) |
| Math | exact analytic B-rep | polyhedral mesh, robust exact booleans |
| A cylinder is | a true analytic surface, V = πr²h | an N-gon prism, V = (N/2π)·sin(2π/N)·πr²h |
| Edge fillet | supported (edges are entities) | impossible (no edges, only triangles) |

That last row is not a bug in the demo — it *is* the demo: kernels
legitimately disagree (faceting) and legitimately differ in capability
(fillet). The IR + contract turn both from silent corruption into checked,
per-element behavior.

## Quickstart

```bash
./setup.sh                 # venv + pip install + tests + kernel smoke test
source .venv/bin/activate
python demo.py
```

Outputs land in `out/`: `model.step` (open in FreeCAD), `model.scad` (open
in OpenSCAD — the parameters are live customizer sliders), `model_manifold.stl`,
`studio_wall.artifact.json` (the exchange artifact), `lifted.ir`.

Requires CPython 3.10–3.12 (cadquery wheel availability). Everything is
pip-installable; no GUI apps needed. FreeCAD/OpenSCAD are optional viewers.

## What the demo proves, act by act

1. **Lower to OCCT, bake an artifact.** The artifact is the cross-level
   carrier: the still-parametric recipe *plus* per-element evaluated oracle
   (volume, bbox, mesh, provenance). Compilers analogy: shipping source
   *with* its reference object code and a source map.
2. **Import on Manifold with match_cast.** The receiving kernel re-evaluates
   the recipe and diffs against the oracle. Wall: exact match → LIVE.
   Colonnade: −0.16% (64-segment faceting) → within the 0.5% contract →
   LIVE. Pedestal: `geom.fillet` unsupported on a mesh kernel → per-element
   FALLBACK to baked geometry. One file, three honest outcomes.
3. **Coarse faceting → DIVERGED.** At 12 segments the colonnade is −4.5%:
   the contract catches the kernels' different math and falls back, checked.
   Faceting policy is a *lowering* flag (the `-ffast-math` of geometry), not
   part of the recipe.
4. **Post-exchange parameter edit.** Widen the window, add columns — LIVE
   elements regenerate on the foreign kernel; the symbolic relation
   `(wall_len − win_w)/2` recomputes (it was never baked to a constant).
   The fallback element is frozen. In an IFC round-trip, *every* element is
   the frozen one — that is the entire point.
5. **Lower to OpenSCAD source, lift back.** `model.scad` carries live
   parameters, real expressions, and a `for`-loop for the column array; the
   filleted pedestal becomes `import("pedestal_baked.stl")` — partial
   lowering visible in source. The lifter parses the emitted subset back to
   IR (hand-edits included); the baked element is flagged unliftable —
   mesh→recipe is decompilation, the research problem, honestly out of scope.

## Layout

```
geomir/ir.py                    recipe dialect: ops, parser, printer, verifier
geomir/eval.py                  progressive lowering onto a backend
geomir/backends/occt.py         OCCT / CadQuery (exact B-rep)      [FreeCAD's math]
geomir/backends/manifold_backend.py  Manifold (polyhedral mesh)    [OpenSCAD's math]
geomir/backends/sampler.py      pure-numpy point-membership kernel (test oracle;
                                also a third math: implicit membership, F-rep-lite)
geomir/artifact.py              exchange artifact + match_cast + per-element fallback
geomir/scad.py                  lowering to / lifting from OpenSCAD source
geomir/validate.py              deep checks: mesh area + sampled Hausdorff
geomir/freecad_script.py        FreeCAD macro emitter (source-form target)
geomir/ifc_export.py            IFC4 CSG exporter (roles -> entity classes)
recipes/studio_wall.ir          the demo model (wall + window + door, colonnade,
                                filleted pedestal)
demo.py                         the six-act walkthrough
smoke_kernels.py                catches kernel API drift with exact expected numbers
tests/run_tests.py              51 checks, pure Python, run anywhere
```

(Full index incl. conformance harness, courses, and skills: `CLAUDE.md`.)

## Courses

`courses/` contains four interactive onboarding courses: 3D modeling from
first principles, compilers from first principles (LLVM / MLIR / Relax),
the blend — with labs that run against this repo's demo — and a live
two-kernel walkthrough. They are self-contained HTML — no server, network,
or build step. Open them straight from disk:

```bash
open courses/01-3d-modeling.html          # macOS (or just double-click)
open courses/02-compilers.html
open courses/03-geometry-compilers.html
open courses/04-two-kernels-live.html
```

(`xdg-open` on Linux, `start` on Windows.)

**Progress is private to you.** Quiz feedback and "mark module complete"
state live in your browser's localStorage — client-side, per browser
profile, per machine. Nothing is ever written back into the HTML files, so
the committed files stay pristine and anyone else cloning this repo starts
at 0/N. The only sharing case is two people using the *same* browser
profile on the *same* computer; for that, each course header has a
**reset** link that clears its progress.

## Conformance harness (adding targets)

```bash
python -m conformance.run --backend occt --backend manifold --backend sampler
python -m conformance.generate --mode diff --seeds 200 \
    --backend occt --backend manifold      # differential kernel testing
```

The runner measures per-op support and tolerance behavior against a graded
corpus with closed-form oracles, prints a report card, and auto-generates
each target's capability manifest (`conformance/targets/`). Onboarding a new
backend (Tekla, Revit, Onshape, IFC…) is a gated playbook — see
`.claude/skills/add-geomir-target/SKILL.md` and `docs/ROADMAP.md` for the
phases and the human checkpoints (licenses, installs, credentials).

More targets and views:

```bash
pip install ifcopenshell   # optional, IFC export only (lazy import)
python -m geomir.ifc_export out/studio_wall.artifact.json out/model.ifc   # openBIM
python -m geomir.freecad_script recipes/studio_wall.ir out/model_freecad.py
open courses/04-two-kernels-live.html    # interactive two-kernel walkthrough
```

Human verification checklist (demo, kernels, fuzzing, edge cases):
`docs/VERIFICATION.md`.

## More in this repo

`CLAUDE.md` is the full index. `docs/HANDOFF.md` carries session state and
next steps; `docs/aec-geometry-ir-analysis.md` is the analysis this demo
implements; `docs/research/` holds the sourced research notes behind it.

## Honest limitations (by design)

Small dialect (primitives, extruded polygon profiles, booleans, translate/
rotate_z, one pattern op, one B-rep-only op) — enough to make every
architectural point; revolve/sweep/loft and richer profiles are roadmapped.
Validation is volume + bbox by default, with an optional sampled-Hausdorff
deep check (`import_artifact(deep=True)`) — sampled, so it has a resolution
floor. Lifting is source-level from our emitted OpenSCAD subset; no
mesh→recipe synthesis. No constraint solving, no persistent-naming stress
test (single producer), no behavioral semantics. The IFC exporter is
unverified until its first ifcopenshell run (`docs/VERIFICATION.md` §2).
Each of these is a known, labeled edge of the map — see the report and
`docs/ROADMAP.md` for where the frontier sits on each.
