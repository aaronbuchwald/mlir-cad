# HANDOFF — continue this work in any session

Updated 2026-07-06 (second build pass). Self-contained: everything needed to
resume is in this repo. Companion docs: `docs/ROADMAP.md` (the plan + human
checkpoints), `docs/VERIFICATION.md` (the human checklist currently pending),
`CLAUDE.md` (index + conventions).

## The arc so far

1. **Question** (2026-07-04). AEC tools can't round-trip models; IFC is
   one-way lossy. Why does every tool model differently, and could an
   LLVM/MLIR/Relax-inspired IR fix it?
2. **Research.** Three sourced passes preserved in `docs/research/`
   (kernels per tool; interop landscape IFC/STEP/USD/Speckle as of mid-2026;
   compilers-applied-to-CAD). Full read of the Relax paper (ASPLOS '25).
3. **Analysis.** `docs/aec-geometry-ir-analysis.md` — the thesis (below).
4. **Demo.** geomir: recipe IR → OCCT + Manifold, exchange artifact with
   match_cast, per-element fallback, OpenSCAD emit/lift. Verified end-to-end
   on macOS with real kernels (colonnade = 3·π·r²·h to the decimal).
5. **Courses.** `courses/01–03` (3D modeling, compilers, the blend — with
   labs on this repo), later `04-two-kernels-live.html` (interactive
   analytic-vs-polyhedral walkthrough with live match_cast verdicts).
6. **Sharpened skepticism** (important context for strategy discussions):
   proprietary tools export only object code, BUT deep model access exists
   via in-process APIs (how Speckle/BHoM/Elysium actually work); vendors
   will never ship lossless parametric export; the math across kernels is
   not reversible, only checkable; A↔B between different fundamental
   geometries stays hard — a hub translates only the shareable core and
   makes the rest *explicitly, per-element* lossy. Verdict: dead as a
   standards play; alive as (a) a pattern language for connector builders,
   (b) native substrate for greenfield/AI CAD. Wedges: AI verification
   infra, lifting-as-product, differential kernel testing.
7. **Speckle comparison**: Speckle ships *state* (property bags +
   displayValue meshes + great transport/identity); geomir ships *programs +
   oracle*. Complementary layers; Speckle's v2→v3 retreat from a universal
   typed ontology validates geomir's constructive-vocabulary bet.
8. **Roadmap + Phase 0** (2026-07-06): `docs/ROADMAP.md` with Fable-5
   workforce model and human checkpoints HC-0..13. Built: conformance
   harness (graded corpus L0–L4, per-op smoke, report cards,
   **auto-generated capability manifests**), differential fuzzer
   (Csmith-for-kernels seed), `geom.intersect`, `add-geomir-target` skill
   (`.claude/skills/`, incl. Tekla appendix), CI workflow.
9. **Phase 1 license-free slice** (2026-07-06): dialect v2
   (`profile.polygon`, `geom.extrude`, `geom.rotate_z`, element roles as
   classification metadata), validation v2 (mesh area + sampled Hausdorff,
   `import_artifact(deep=True)`), FreeCAD macro emitter (ast-verified),
   IFC4 CSG exporter (**UNVERIFIED** — first ifcopenshell run pending),
   fuzzer/corpus coverage for new ops, `docs/VERIFICATION.md`.

## Core thesis (compressed)

- IFC's lossiness is threefold: certified paths strip to tessellation;
  importers can't lift (import = decompilation → frozen DirectShape);
  behavioral semantics are vendor code that was never in any file.
- Kernels disagree numerically (tolerance regimes ≈ ISAs with different
  float semantics) — hence the healing-middleware industry.
- A literal LLVM (one IR, one level) is the wrong shape — that's STEP/IFC.
  The right imports: **MLIR** (coexisting dialects, progressive per-element
  lowering) + **Relax** — (a) carry all levels in one artifact with
  provenance; (b) never bake symbolic relations ((wall_len−win_w)/2 travels
  as an expression); (c) **match_cast at the exchange boundary**: ship
  recipe + baked oracle, re-evaluate on the target kernel, diff, per-element
  LIVE/DIVERGED/FALLBACK.
- Confirmed gaps (July 2026, searched hard): no MLIR-style IR for CAD/BIM;
  no kernel differential-testing campaign; no partial-semantics-preservation
  theory for interop.

## Verification state — READ BEFORE TRUSTING ANYTHING

- Pure Python: **50/50 checks pass** (`tests/run_tests.py`) — IR, artifact/
  match_cast (LIVE/FALLBACK/DIVERGED/frozen-regenerate), dialect v2,
  validation v2, emitter structure checks, fuzzer determinism, scad
  fixed point. Sampler conformance: **CONFORMANT** (manifest committed).
- Kernel-verified on macOS (2026-07-04 run): demo end-to-end, exact OCCT
  volumes, reference outputs in `out/`.
- **Pending HC-0** (see VERIFICATION.md §2): kernel conformance run
  (`--backend occt --backend manifold --backend manifold12`) + commit those
  manifests; 300-seed differential fuzz; **first-ever execution of
  `geomir/ifc_export.py` and the FreeCAD macro** — ifc_export is the most
  drift-prone file in the repo (ifcopenshell never ran in the build sandbox).
- Sandbox quirks for future sessions: no PyPI in the build sandbox (kernels
  can't execute there — design for HC-0 handbacks); `.claude/` is protected
  from file tools (write via shell); git needed delete permission once for
  its lock files.

## Where to resume

Next Fable-runnable chunk (no licenses): revolve/sweep/loft, `tabulate`,
polar patterns, profiles with holes/arcs, **IFC lift** (import IFC's shallow
recipes back to geomir), Grasshopper emitter — see ROADMAP Phase 1 deferred
list. First human wall after that: HC-3 (Onshape account/keys), then HC-7
(Tekla license) / HC-8 (Autodesk APS + ToS review). Strategy checkpoints
HC-2 (ε sign-off) and HC-12 (beachhead choice) remain open.

Onboarding a new backend: use the `add-geomir-target` skill — phases with
hard gates; conformance runner is the arbiter; manifests are generated,
never hand-written.

## Resume prompt (paste into a fresh session)

> Read CLAUDE.md, docs/HANDOFF.md, docs/ROADMAP.md (status ledger), and
> docs/VERIFICATION.md in this repo. geomir is an MLIR-style multi-level IR
> for CAD exchange (OCCT + Manifold + sampler backends, conformance harness,
> differential fuzzer, IFC/FreeCAD/OpenSCAD emitters). Phase 0 done; Phase 1
> partial; verification boundaries are in HANDOFF §Verification state.
> I want to: <run VERIFICATION.md §1–2 and hand back results | continue
> ROADMAP Phase 1 deferred items | onboard target X via the
> add-geomir-target skill | discuss strategy (HANDOFF arc §6)>.
