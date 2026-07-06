# CLAUDE.md — repo index & context for future sessions

## What this is

An analysis of why AEC/CAD tools cannot round-trip models (IFC as one-way
lossy "object code") and a **working demo** of the proposed fix: an
MLIR-style multi-level IR ("geomir") lowered onto two open-source kernels
with genuinely different math — OCCT (FreeCAD's exact B-rep, via CadQuery)
and Manifold (OpenSCAD's polyhedral boolean engine) — exchanged via an
artifact carrying recipe + baked oracle, validated with a Relax-style
match_cast tolerance contract, degrading per element, and lowered to /
lifted from OpenSCAD source.

## Read in this order

1. `docs/HANDOFF.md` — session handoff: thesis, what's proven, verification
   boundaries, next steps, resume prompt. **Start here.**
   (`docs/VERIFICATION.md` = the human checklist; `docs/ROADMAP.md` = the plan.)
2. `docs/aec-geometry-ir-analysis.md` — the full analysis report (the "why").
3. `README.md` — demo quickstart and act-by-act walkthrough (the "what").
4. `docs/research/` — sourced research notes behind the report.

## File index

```
CLAUDE.md                          this index
README.md                          demo quickstart + what each act proves
docs/
  HANDOFF.md                       continuation handoff (state, next steps)
  ROADMAP.md                       full project roadmap, Fable-5 workforce
                                   model, human checkpoints (HC-0..13)
  aec-geometry-ir-analysis.md      main analysis report (kernels, IFC, LLVM/
                                   MLIR/Relax mapping, viable architecture)
  research/
    kernels.md                     per-tool kernels/representations, tolerance
                                   models, D-Cubed; sourced + flagged
    interop-landscape.md           IFC4/IFC5, STEP AP242, USD/AOUSD, Speckle,
                                   healing middleware; sourced + flagged
    compilers-for-cad.md           e-graphs, program-synthesis lifting,
                                   persistent naming, the "no MLIR-for-CAD
                                   exists" gap; sourced + flagged
courses/                           interactive one-day onboarding courses
                                   (self-contained HTML, open in a browser;
                                   progress + quizzes, saved via localStorage)
  01-3d-modeling.html              3D modeling from first principles: the four
                                   representation families, parametric layer,
                                   kernels/tolerances, 60-year history
  02-compilers.html                compilers from first principles: pipeline,
                                   SSA, e-graphs, LLVM, MLIR, Relax, dark arts
  03-geometry-compilers.html       the blend: Rosetta table, three workflows
                                   (export=compilation, import=decompilation,
                                   exchange=binary translation), and hands-on
                                   labs against this repo's demo
  04-two-kernels-live.html         interactive walkthrough: analytic B-rep vs
                                   polyhedral mesh side by side, live sliders,
                                   match_cast verdicts, symbolic centering
geomir/
  ir.py                            recipe dialect: OP_SPECS, parser, canonical
                                   printer, verifier (SSA, kinds, exports)
  eval.py                          progressive lowering onto a backend;
                                   UnsupportedOp; per-element evaluation
  artifact.py                      exchange artifact (recipe + baked oracle),
                                   match_cast import (LIVE/FALLBACK/DIVERGED),
                                   post-import regenerate
  scad.py                          lowering to OpenSCAD source (live params,
                                   expressions, for-loops, import() fallback)
                                   + lifter for the emitted subset
  validate.py                      validation v2: mesh area + sampled
                                   Hausdorff (deep flag on import_artifact)
  freecad_script.py                FreeCAD macro emitter (source-form target;
                                   ast-verified, runtime-verified by human)
  ifc_export.py                    IFC4 CSG exporter w/ per-element mesh
                                   fallback (UNVERIFIED until first
                                   ifcopenshell run — see VERIFICATION §2)
  backends/occt.py                 OCCT/CadQuery — exact B-rep  [FreeCAD math]
  backends/manifold_backend.py     Manifold — polyhedral mesh   [OpenSCAD math]
  backends/sampler.py              pure-numpy point-membership kernel (test
                                   oracle; third math: implicit membership)
recipes/studio_wall.ir             demo model: wall+window+door (symbolic
                                   centering expr), colonnade (repeat_x),
                                   filleted pedestal (B-rep-only op)
conformance/                       the target-onboarding harness
  registry.py                      backend registry + tolerance contracts
  corpus/                          graded recipes L0..L4 + expected.json
                                   (closed-form oracles)
  run.py                           runner: per-op smoke, match_cast corpus,
                                   scad roundtrip, report card, and
                                   AUTO-GENERATED capability manifests
  generate.py                      grammar-directed recipe fuzzer +
                                   differential mode (Csmith-for-kernels)
  targets/                         committed capability manifests (observed,
                                   never hand-edited)
.claude/skills/add-geomir-target/  agent playbook for onboarding a new
                                   backend (phases, gates, HC checklist,
                                   Tekla appendix)
.github/workflows/conformance.yml  CI: pure-python + kernel jobs; commented
                                   stanzas for license-gated tiers
demo.py                            six-act walkthrough (see README)
smoke_kernels.py                   kernel API drift canary — run first on a
                                   new machine; exact expected volumes
tests/run_tests.py                 29 pure-Python checks, no kernels needed
setup.sh / requirements.txt        venv + cadquery, manifold3d, trimesh, numpy
out/                               committed reference outputs from the
                                   verified macOS run (2026-07-04):
                                   model.step (FreeCAD), model.scad
                                   (OpenSCAD, live params), model_manifold
                                   .stl, studio_wall.artifact.json (the
                                   exchange artifact), lifted.ir,
                                   pedestal_baked.stl — regenerable via
                                   `python demo.py`
```

## Running

```bash
./setup.sh                              # venv + installs + tests + smoke
source .venv/bin/activate && python demo.py
python tests/run_tests.py               # pure-Python, runs anywhere
```

Python 3.10–3.12 (cadquery wheel range). FreeCAD/OpenSCAD optional, for
viewing `out/model.step` / `out/model.scad`.

## Verification state (as of 2026-07-06, second build pass)

- **50/50 pure-Python checks pass** (`tests/run_tests.py`): IR, artifact/
  match_cast, dialect v2 (extrude/rotate_z/roles), validation v2, emitter
  structure checks, fuzzer determinism, scad emit→lift fixed point.
  Sampler conformance CONFORMANT (manifest committed).
- Demo verified end-to-end on macOS with real kernels (2026-07-04): OCCT
  volumes exact to closed form; reference outputs in `out/`.
- **Pending human run (HC-0)** — see `docs/VERIFICATION.md`: kernel
  conformance manifests (occt/manifold/manifold12), 300-seed differential
  fuzz, and the FIRST execution of `geomir/ifc_export.py` (ifcopenshell
  never ran in the build sandbox — most drift-prone file) and the FreeCAD
  macro. `smoke_kernels.py` pins exact volumes to localize any API drift.
- Full state, arc, and resume prompt: `docs/HANDOFF.md`. Plan + human
  checkpoints: `docs/ROADMAP.md`.

## Conventions & invariants

- Units: mm. Default match_cast contract: 0.5% relative volume + 1mm bbox.
- The element (recipe.export) is the unit of fallback — never the file.
- Symbolic expressions are never baked: parameters and expr.* relations
  survive lowering (including into emitted .scad).
- Faceting (`circular_segments`, `$fn`) is backend lowering policy, not part
  of the recipe.
- The scad lifter only parses the subset the emitter produces (documented in
  `geomir/scad.py`); baked `import()` elements are honestly unliftable.
- Dialect is deliberately tiny (see `OP_SPECS` in `geomir/ir.py`); add ops
  there + evaluator case + each backend + scad emit/lift + tests together.

## For future assistant sessions

**Start with `docs/HANDOFF.md`** — full arc, verification boundaries, where
to resume, and a paste-ready resume prompt. The plan with human checkpoints
is `docs/ROADMAP.md`; the pending human checklist is `docs/VERIFICATION.md`;
onboarding a new backend goes through the `add-geomir-target` skill
(`.claude/skills/`), with the conformance runner as the arbiter.

Research notes carry per-claim source URLs verified July 2026, with
explicitly flagged uncertainties — re-verify time-sensitive claims (IFC5
status, AOUSD, vendor APIs) before relying on them. Build-sandbox quirks
(no PyPI; `.claude/` write-protected for file tools; git lock deletes) are
listed in HANDOFF §Verification state.
