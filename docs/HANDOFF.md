# HANDOFF — continue this work in any session

Written 2026-07-04 at the end of the originating session (Claude, Cowork
mode). Self-contained: everything needed to resume is in this repo.

## The arc of the original conversation

1. **Question.** AEC 3D tools (Revit, ArchiCAD, Tekla, Rhino…) can't
   round-trip models; IFC passes realized geometry and conversion is one-way
   lossy. Why does every tool model differently, what does each use, and
   could something LLVM/IR-inspired fix it? Also: do the ideas in the Relax
   paper (ASPLOS '25, cross-level IR for dynamic ML) transfer?
2. **Research.** Three parallel web-research passes (geometry kernels per
   tool; interop landscape IFC/STEP/USD/Speckle as of mid-2026;
   PL-and-compilers-applied-to-CAD academic work) plus a full read of the
   Relax paper. Findings preserved in `docs/research/`.
3. **Analysis.** `docs/aec-geometry-ir-analysis.md` — the main deliverable.
4. **Brass tacks.** Is there an angle worth exploring with MLIR-for-CAD?
   Answer: yes, but the wedge matters more than the IR (see below).
5. **Demo.** Built the smallest working proof: this repo. One recipe IR, two
   open-source kernels with different math, exchange artifact with
   match_cast validation, per-element fallback, OpenSCAD source emit/lift.

## Core thesis (compressed)

- IFC's lossiness is threefold: certified exchange paths strip to the
  tessellation floor; importers can't lift (Revit → frozen DirectShape;
  import is *decompilation*); and behavioral semantics (wall joins, hosting)
  are proprietary code that was never in any file.
- Kernels also disagree *numerically* (Parasolid ~1e-8 vs ACIS ~1e-6
  tolerance regimes; different procedural surface types) — even evaluated-
  geometry exchange needs a "healing" middleware industry (CADfix, Elysium).
- A literal LLVM (one shared IR at one level) is the wrong shape — that's
  what STEP/IFC already are. The right imports are **MLIR** (multi-dialect,
  progressive partial lowering) and **Relax**: (a) carry all abstraction
  levels in one artifact with provenance links; (b) first-class symbolic
  relations — never bake `(wall_len − win_w)/2` to `2250`; (c) match_cast:
  ship recipe + baked oracle, re-evaluate on the target kernel, diff, fall
  back per-element on divergence — turning the tolerance problem into
  checked graceful degradation.
- Confirmed gaps (as of July 2026, searched hard): no published MLIR-style
  IR for CAD/BIM; no differential-testing/fuzzing campaign for geometry
  kernels; no formal partial-semantics-preservation treatment of interop.
- Viable wedges (incentive-compatible, in order): AI/LLM CAD verification
  infrastructure; lifting-as-a-product (STEP/IFC → native parametric, vs
  Elysium CADfeature/ITI Proficiency incumbents); differential kernel
  testing to produce an empirical semantics spec. The blocker for a
  standards-shaped solution is economics (incumbent lock-in), not IR design.

## What the demo proves (and deliberately doesn't)

Proves: one IR → two kernels (OCCT exact B-rep = FreeCAD's math; Manifold
polyhedral mesh = OpenSCAD's engine); measured divergence caught by a 0.5%
volume contract (64-seg colonnade −0.16% LIVE; 12-seg −4.5% DIVERGED →
checked fallback); per-element fallback for capability gaps (fillet on a
mesh kernel); post-exchange parameter edits regenerate on the foreign kernel
(the exact thing IFC import cannot do); lowering to OpenSCAD *source* with
live params and source-level lifting back, with baked elements flagged
unliftable (the decompilation boundary).

Doesn't (by design, all labeled): mesh→recipe synthesis, constraint solving,
persistent-naming stress (single producer), behavioral semantics, full-shape
validation (volume+bbox only).

## Verification state

- `tests/run_tests.py`: **29/29 pass** (pure Python; IR, evaluator, sampler
  kernel vs closed-form volumes, artifact/match_cast/fallback/divergence,
  scad emit→lift fixed point). Runs anywhere, no kernels needed.
- **Full demo executed successfully end-to-end on macOS on 2026-07-04**
  (real kernels): OCCT baked the artifact with the colonnade volume equal to
  3·π·r²·h to the decimal (593,761,011.5 mm³ — exact analytic B-rep) and the
  wall exactly 4.293e9; Manifold import, fallback, regeneration, and scad
  emit/lift all produced the reference outputs committed in `out/`.
- On any *new* machine, `./setup.sh` re-runs tests + `smoke_kernels.py`;
  the smoke test pins exact expected volumes (incl. the (N/2π)·sin(2π/N)
  faceting factor), so cadquery/manifold3d API drift fails loudly there.
  Drift-sensitive spots are isolated: `occt.py` bottom helpers,
  `manifold_backend._mesh_arrays`, the two cylinder argument orders.

## Natural next steps

Ranked roughly by value-per-effort: (1) run setup on a real machine, fix any
kernel drift; (2) tighten validation — Hausdorff/containment sampling
instead of volume+bbox; (3) third backend with implicit math (sdf/libfive)
to show three paradigms under one IR; (4) STEP→recipe lifting for simple
extrusions (real decompilation, tiny scope); (5) e-graph canonicalization
pass (Szalinski-style) choosing per-target construction idioms; (6) a
persistent-naming stress: two producers editing the same recipe, semantic
queries instead of indices (Onshape FeatureScript model); (7) write up as a
short paper/post — the "no MLIR-for-CAD exists" gap is documented in
`docs/research/compilers-for-cad.md`.

## Key sources (full lists inside the docs)

Relax paper: https://yuchenjin.github.io/papers/asplos25-relax.pdf ·
Szalinski/e-graphs: https://www.mwillsey.com/papers/pldi-szalinski ·
CAD-Recode: https://cad-recode.github.io/ · FreeCAD toponaming:
https://www.ondsel.com/blog/toponaming-problem-is-history/ · IFC5 (ECS/USD
direction): https://github.com/buildingSMART/IFC5-development · Kernel
tolerance models: https://opencascade.blogspot.com/2010/10/data-model-highlights-parasolid-acis.html
· Autodesk granular-data strategy: https://aecmag.com/technology/autodesks-granular-data-strategy/

## Resume prompt (paste into a fresh session)

> Read CLAUDE.md, docs/HANDOFF.md, and docs/aec-geometry-ir-analysis.md in
> this repo. This is a working demo of an MLIR-style multi-level IR for CAD
> exchange between OCCT and Manifold, plus the analysis behind it. Current
> state and verified/unverified boundaries are in HANDOFF §Verification.
> I want to work on: <pick from HANDOFF §Natural next steps or your own>.
