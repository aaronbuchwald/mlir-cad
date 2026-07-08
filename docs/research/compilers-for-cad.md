# Research notes: PL/compiler techniques applied to CAD/BIM

Web-verified research pass, 2026-07-04. Sources inline; gaps flagged at
bottom. Feeds sections 4, 6, 7 of the analysis report — and contains the
documented "no MLIR-for-CAD exists" gap.

## 1. UW PLSE line: Reincarnate, Szalinski, egg

### Reincarnate (ICFP 2018) — primary source read in full 2026-07-07

Nandi, Wilcox, Panchekha, Blau, Grossman, Tatlock, *Functional Programming
for Compiling and Decompiling Computer-Aided Design*, PACMPL 2(ICFP):99
([PDF](https://ttaylorr.com/publications/reincarnate-icfp18.pdf),
[artifact repo](https://github.com/uwplse/reincarnate-aec),
[tool site](http://incarnate.uwplse.org/)). ~20k LOC OCaml.

**What it does.** Treats the 3D-printing pipeline as compilation
(CAD → mesh → slices → G-code ≈ source → IR → asm; meshes are designs with
structure "compiled away", explicitly analogized to stripped binaries).
Four contributions:
1. **λCAD**: purely functional CAD language — primitives (Cube,
   Cylinder(n) = n-gon prism), affine transforms, CSG booleans, plus let/
   functions/recursion. All primitives piecewise-linear; true curves
   explicitly deferred ("compositional notion of equality between
   piecewise-linear approximations to curves ... significant challenge
   left for future work").
2. **Denotational semantics for BOTH languages** to point sets in R³:
   CAD compositionally; meshes via ray-casting parity (`InsideVia`: a point
   is inside iff a "good" halfline crosses an odd number of faces; theorems
   that almost all directions are good and the choice doesn't matter).
3. **Verified compiler** CAD→mesh (split-then-classify booleans on meshes,
   correctness proof against the denotations).
4. **ReIncarnate — the first mesh→CAD synthesis algorithm**: rephrase the
   compiler as small-step with evaluation contexts, "flip the arrows" into
   a synthesis relation driven by three **geometric oracles** with formal
   specs (⟦oracle output⟧ = ⟦input mesh⟧): **Ωprim** recognizes
   affine-transformed primitives via *canonicalization* (dominant-axis
   detection from face-group normal areas → Euler-angle de-rotation →
   unit-scale → center; then re-orient the matched primitive back);
   **Ωadd** splits meshes (connected components / convex rings / face-group
   features); **Ωsub** finds a snug bounding primitive and emits
   bound − residual (i.e., hole recovery). Worklist search with fuel,
   focus/schedule heuristics, restricted target grammar S (booleans above
   affines above primitives; intersections rewritten away), ranked by
   **≤edit** (proxy: program size), with a required *predictability*
   fixed point: synth(compile(synth(m))) = synth(m). Case studies lift
   Thingiverse STLs (candle holder: hundreds of faces → 20-line program)
   and enable edits that break mesh editors.
5. **Numerics** (§8.1): floats break decidable geometric equality; they
   prototype exact arithmetic over a splitting field ℚ-basis of
   cos(πi/2n) — correct but ~600× slower; the codebase is functorized over
   NumSys (float/MPFR/exact) and designed for differential testing against
   OpenSCAD — both 2018 foreshadowings of this repo's tolerance-contract
   and fuzzer choices.

**How it fits geomir** (the mapping is nearly 1:1):
- λCAD ≈ the recipe dialect op-for-op — with one instructive difference:
  their `Cylinder(n)` puts faceting *in the program*; geomir moved it to
  backend lowering policy (the -ffast-math lesson from Relax). Their only
  target was mesh, so the distinction didn't bite them.
- Their mesh denotation (ray-parity point membership) **is** the sampler
  backend: `backends/sampler.py` is a Monte Carlo implementation of their
  ⟦·⟧. Their formalism supplies the theory story for the conformance
  harness: ops specified denotationally, kernels as implementations
  checked against the denotation.
- Their oracle specs assume exact equality ⟦m⟧ = ⟦c⟧ — unenforceable under
  floating point (their own §8.1 admission). geomir's match_cast is the
  missing enforcement: **verified oracles** — speculate structurally,
  check numerically against the shipped baked oracle within ε. Their named
  open problem (equality between piecewise-linear approximations of
  curves) is answered pragmatically by the tolerance contract.
- Ωsub is the money oracle for AEC lifting: "snug bound minus residual" is
  literally wall-minus-openings. Phase 4 lifting v0 should implement
  Ωprim/Ωsub over B-rep/mesh with match_cast-gated acceptance (see
  ROADMAP).
- Their flat output (ICFP letters: 89 LOC of repeated Translate/Scale/Cube)
  is the exact gap Szalinski closed two years later with e-graphs —
  confirming the pipeline stack: oracle/neural decompiler → e-graph
  structuring → per-target emission.
- Their predictability fixed point = geomir's emit→lift→emit fixed-point
  tests, independently reinvented.
- **Szalinski (PLDI 2020)** — mesh decompilers emit *flat* CSG; Szalinski is
  a second decompilation stage shrinking flat CSG into structured programs
  with map/fold operators, via **equality saturation** with CAD rewrites and
  *inverse transformations* (solvers speculatively adding equivalences to an
  e-graph) ([paper page](https://www.mwillsey.com/papers/pldi-szalinski),
  [arXiv:1909.12252](https://arxiv.org/abs/1909.12252),
  [code](https://github.com/uwplse/szalinski)).
- **egg (POPL 2021, distinguished paper)** — "an e-graph compactly represents
  many equivalent programs"; rebuilding + e-class analyses
  ([egraphs-good.github.io](https://egraphs-good.github.io/)). Successor:
  egglog (PLDI 2023). E-graphs are the natural middle-end for a geometry
  compiler: same shape, many constructions, extract per-target idiom.
- **Carpentry Compiler (SIGGRAPH Asia 2019)** — explicit two-level IR:
  HL-HELM lowered to LL-HELM with Pareto optimization over cost/time/precision
  ([project](https://grail.cs.washington.edu/projects/carpentrycompiler/)).
  Follow-up co-optimization via e-graphs ("bag of parts", ICEE search,
  [arXiv:2107.12265](https://arxiv.org/abs/2107.12265)).
- **ShapeCoder (SIGGRAPH 2023)** — library learning for shape programs over
  e-graphs ([project](https://rkjones4.github.io/shapecoder.html)).

## 2. Geometry→program lifting (the import-as-decompilation stack)

- **InverseCSG (TOG 2018, MIT)** — mesh→CSG as program synthesis
  ([project](https://inversecsg.csail.mit.edu/)).
- **CSGNet (CVPR 2018)** — neural shape parser emitting CSG programs
  ([arXiv:1712.08290](https://arxiv.org/abs/1712.08290)).
- **DeepCAD (ICCV 2021)** — generative transformer over CAD command
  sequences; 178,238 models with construction sequences
  ([project](https://www.cs.columbia.edu/cg/deepcad/)).
- **Fusion 360 Gallery (TOG 2021, Autodesk)** — 8,625 human sketch+extrude
  sequences; defines the "CAD reconstruction" task
  ([GitHub](https://github.com/AutodeskAILab/Fusion360GalleryDataset)).
- **Point2CAD (CVPR 2024, ETH)** — point cloud → full B-rep with topology
  ([project](https://www.obukhov.ai/point2cad.html)).
- **CAD-Recode (ICCV 2025)** — LLM (Qwen2-1.5B) lifting point clouds to
  executable **CadQuery Python**; trained on 1M procedural programs
  ([project](https://cad-recode.github.io/),
  [arXiv:2412.14042](https://arxiv.org/abs/2412.14042)).
- LLM-era survey and successors: [LLMs for CAD survey,
  arXiv:2505.08137](https://arxiv.org/pdf/2505.08137); Text-to-CadQuery
  (2505.06507); CAD-Llama (2505.04481); 2026 preprints (titles only, flagged):
  PLLM (2602.12561), CADReasoner (2603.29847), Img2CADSeq (2605.13293).
  Consistent note: CadQuery favored as LLM target because it's Python.

## 3. Persistent naming / topological naming problem

References in later features point at topological entities of earlier ones;
re-evaluation regenerates topology (split/merge) and references dangle.
Literature: Kripac (CAD 1997,
[ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0010448596000401));
**Marcheix & Pierra survey (ACM Solid Modeling 2002,
[ResearchGate](https://www.researchgate.net/publication/221115805_A_survey_of_the_persistent_naming_problem))**;
2018 review ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1110016818300814)).
Blocks *cross-system* parametric exchange: feature mapping + persistent
naming + constraint translation identified as the three killers
([JCDE 2020](https://academic.oup.com/jcde/article/7/5/603/5818508)).

Industrial: FreeCAD's TNP fixed in 1.0 (Nov 2024) via realthunder's
algorithm ([Ondsel](https://www.ondsel.com/blog/toponaming-problem-is-history/),
[wiki](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_naming_problem.md)).
PL-flavored solution: **Onshape FeatureScript** — topological references are
lazily-resolved *queries* (state-based and historical: "the edge generated
by feature X from sketch vertex Y"), i.e. late-bound semantic identifiers
instead of addresses ([FsDoc](https://cad.onshape.com/FsDoc/library.html)).

## 4. MLIR and IRs for CAD/geometry/BIM — THE GAP

**No published MLIR-style or LLVM-style IR proposal for CAD, solid modeling,
or BIM was found** (multiple query formulations, July 2026). Closest:
- Carpentry Compiler's two-level HL/LL-HELM (§1).
- **OpenVCAD** — "open source volumetric multi-material geometry compiler",
  implicit scripting compiled to graded-material volumes
  ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2214860423005250),
  [GitHub](https://github.com/MacCurdyLab/OpenVCAD-Public)).
- eqsat: equality-saturation **dialect for MLIR** (EGRAPHS 2025) — e-graphs
  inside MLIR, but not geometry
  ([PLDI page](https://pldi25.sigplan.org/details/egraphs-2025-papers/3/eqsat-An-Equality-Saturation-Dialect-for-Non-destructive-Rewriting)).
- BIM staged translation: IFC→SimModel→Modelica (IEA Annex 60,
  [LBNL](https://simulationresearch.lbl.gov/iea-annex60/finalReport/activity_1_3.html));
  parallel IFC normalization for version control
  ([arXiv:2312.14931](https://arxiv.org/pdf/2312.14931)).
- Gradual typing / partial-semantics-preservation applied to CAD interop:
  **nothing found** — open theory gap.

## 5. Code-as-CAD and "code as source of truth"

OpenSCAD (script-first CSG, [openscad.org](https://openscad.org/));
CadQuery / build123d (Python over OCCT via shared OCP wrapper,
[build123d docs](https://build123d.readthedocs.io/en/latest/external.html));
PartCAD (package manager for CAD models); Fornjot (Rust code-CAD kernel,
mainline dormant, [GitHub](https://github.com/hannobraun/fornjot));
**Zoo/KittyCAD KCL** — strongest industrial claim: "KCL is the source of
truth behind Zoo models... If you want to know what the software truly knows
about your model, just read the KCL"; text-stored, git-versionable,
LLM-friendly; Text-to-CAD API
([Introducing KCL](https://zoo.dev/research/introducing-kcl)).
AEC equivalents: Hypar Elements text-to-BIM
([AEC Magazine](https://aecmag.com/ai/hypar-text-to-bim-and-beyond/));
GeometryGym (Grasshopper→IFC, ["Parametric IFC"](http://geometrygym.blogspot.com/2014/08/parametric-ifc.html)).
Flag: code-as-source-of-truth as interop strategy is vendor-asserted and
practiced, but no academic paper formalizes it.

## 6. Differential testing / fuzzing of geometry kernels — THE OTHER GAP

**No Csmith-for-geometry-kernels found.** Nearest neighbors:
- MF++ metamorphic fuzzing of C++ libraries (ICST 2022) — methodology maps
  onto kernels, never applied ([PDF](https://www.doc.ic.ac.uk/~afd/papers/2022/ICST.pdf)).
- GraphFuzz differential fuzzing of graph algorithm implementations
  ([arXiv:2502.15160](https://arxiv.org/pdf/2502.15160)).
- Robustness-by-construction instead: "Exact Predicates, Exact Constructions
  and Combinatorics for Mesh CSG" (TOG 2025,
  [ACM](https://dl.acm.org/doi/10.1145/3744642)); a 2026 Boolean-ops survey
  confirms floating-point robustness remains the central unsolved issue.
- Industrial analog: **CAx-IF / MBx-IF** biannual STEP test rounds — human-
  mediated cross-implementation testing producing "Recommended Practices"
  ([MBx-IF](https://www.mbx-if.org/home/cax/testrounds/)).

## 7. Common parametric exchange / semantic lifting of IFC

- **Macro-parametrics** (KAIST, Han group, 2002–2020): translate modeling-
  command macros through a neutral command set (TransCAD); explicitly
  motivated because STEP/IGES "cannot preserve design intent"; foundered on
  feature mapping, naming, constraint translation
  ([IJCC 2002](https://koreascience.kr/article/JAKO200219463923913.page),
  [JCDE 2020](https://academic.oup.com/jcde/article/7/5/603/5818508)).
- STEP's own parametric layer: ISO 10303-55/-108/-112 + NIST prototypes +
  PDES CHAPS business case — standards exist, no commercial uptake.
- **Semantic enrichment** (BIM-side lifting): SeeBIM/Sacks rule-based
  inference over IFC geometry ([Wiley 2016](https://onlinelibrary.wiley.com/doi/abs/10.1111/mice.12128),
  [ITcon 2022 review](https://www.itcon.org/papers/2022_20-ITcon-Bloch.pdf));
  GNN room classification (AutoCon 2021); parametric-IFC reconstruction via
  deep learning (2024); inverse procedural modeling of facades
  ([TOG 2014](https://dl.acm.org/doi/10.1145/2601097.2601162)).
- Flag: **no cross-domain (CAD+BIM) common parametric exchange IR proposal
  found in the MLIR sense** — the pieces exist separately. That absence is
  the opportunity this repo's demo sketches.

## Industry status of this direction (checked 2026-07-07)

- **Mesh→CAD lifting reached production via ML, not synthesis:**
  [Backflip AI](https://www.backflip.ai/) — out of stealth 2025, $30M
  (NEA + a16z), foundation model on 100M synthetic geometries; 3D scan/mesh
  → parametric, **native-format SOLIDWORKS parts** via plugin
  ([3DPI](https://3dprintingindustry.com/news/new-ai-model-from-backflip-accelerates-3d-scan-to-cad-237055/),
  [DEVELOP3D](https://develop3d.com/cad/backflip-introduces-mesh-to-cad/)).
  Reincarnate's exact use case, commercialized. Nobody found ships
  *contract-verified* lifting (output diffed against source geometry) —
  the verified-oracle slot is empty.
- **E-graphs in production — compilers only:** Cranelift's acyclic
  e-graphs (ægraphs) are the mid-end of a shipping production compiler
  ([cfallin, 2026](https://cfallin.org/blog/2026/04/09/aegraph/)); MLIR
  eqsat dialect (2025) at integration stage. No CAD product ships
  Szalinski-style structuring.
- **Robust-geometry substrate shipped:** Manifold's mesh CSG is
  non-experimental in OpenSCAD since 2024.09 (user-selectable backend;
  CGAL still default as of last confirmed info)
  ([openscad list](https://lists.openscad.org/empathy/thread/D6KV3ZLXHLBHSITSQ5GPUZUKHURU4ABE)).
- **Verified/denotational geometry: nowhere in production.** No kernel
  spec, no verified geometry compiler, no differential-testing campaign
  (gap §6 unchanged).
- **AEC lane: empty.** No production parametric lifting of IFC beyond
  heuristic importers; semantic enrichment remains academic.

## Flags / unverified

1. "No MLIR/LLVM-style IR for CAD/BIM" and "no kernel fuzzing campaign" —
   negative claims; searched hard, not provable.
2. 2026 arXiv preprints cited from search titles/snippets only.
3. No gradual-typing-for-CAD paper found — apparent theory gap.
4. Could not confirm whether OCCT is enrolled in OSS-Fuzz.
