# A Compiler-Theoretic Analysis of AEC Geometry Interoperability

*Why BIM/CAD tools can't round-trip models, what each actually uses internally, whether an LLVM-style IR could fix it, and what the Relax paper (ASPLOS '25) contributes to the answer.*

---

## 1. Sharpening the premise

Your framing is directionally right but the failure is worse — and more interesting — than "IFC only passes realized geometry."

IFC can actually carry shallow construction recipes, not just baked output. The schema includes `IfcExtrudedAreaSolid` (profile + direction + depth — a one-step program), swept solids, CSG/`IfcBooleanResult`, openings as boolean subtractions (`IfcRelVoidsElement`), and since IFC4, exact NURBS B-reps ([IfcShapeRepresentation](https://standards.buildingsmart.org/IFC/DEV/IFC4_2/FINAL/HTML/schema/ifcrepresentationresource/lexical/ifcshaperepresentation.htm)). Three separate failures make the exchange one-way lossy anyway:

1. **Exporters lower to the floor.** The only widely certified IFC4 exchange profile (the Reference View MVD) is deliberately tessellation-oriented, built for one-way coordination. The MVD that was supposed to support "import for further editing" — the Design Transfer View — died with zero certified products ([BIM Corner](https://bimcorner.com/is-the-industry-ready-for-ifc4/)). Everyone ships `-O0` output because that's the only conformance-tested path.
2. **Importers can't lift.** Revit imports IFC as `DirectShape` — frozen, uneditable geometry containers that can't be joined, cut, or retyped ([Autodesk](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-modify-cut-join-geometry-or-apply-material-to-elements-imported-from-IFC-to-Revit.html)). Even the parametric-ish content IFC *does* preserve (an extrusion recipe) arrives as a dumb solid, because mapping it onto a native Revit family with correct behavior is a decompilation problem, not a parsing problem.
3. **The real semantics were never in any file.** A Revit wall's identity is behavioral: it auto-joins, hosts windows, propagates changes through Revit's proprietary change-propagation engine. IFC has entities recording the *results* of behavior (`IfcRelConnectsPathElements` for a join) but no language for the *rules*. The rules are compiled C++ inside each vendor's binary.

So the situation, precisely: everyone exchanges object code; the format could carry mid-level bytecode but the certified path strips it; and full source exchange wouldn't suffice anyway because each app's "language" has semantics defined only by its proprietary runtime.

## 2. Why they all model it differently

Four forces, none of them accidental:

**Domain economics dictate representation.** Tekla models contain hundreds of thousands of near-identical bolts and plates, so it represents parts as procedural recipes (profile + boolean cuts) with instanced solids stored in part-local coordinates — compact and fast to regenerate, hostile to generic exchange ([Tekla](https://support.tekla.com/doc/tekla-structures/2021/rel_2021_modeling_improvements)). Gehry's office needed aerospace Class-A surfacing for fabrication tolerances, so Digital Project was built on CATIA/CGM. Navisworks tessellates everything into meshes because navigating a hundred federated files at 60fps matters more than exactness. nTop abandoned B-rep entirely for implicits (f(x,y,z) scalar fields) because B-rep booleans at lattice scale are combinatorially explosive and failure-prone ([nTop](https://ntopology.com/blog/understanding-the-basics-of-b-reps-and-implicits/)). No single representation wins on all axes: exact B-rep gives edges/faces with drawing and fabrication semantics but is heavy and heuristic-fragile; meshes are robust but dumb; implicits never fail booleans but have no persistent topology; procedural recipes are compact and parametric but must be re-evaluated to mean anything.

**Kernels disagree at the numerical level.** Parasolid's default precision is ~1e-8, ACIS's ~1e-6; Parasolid and Open CASCADE attach tolerances locally to topological entities ("think of edges as tubes and vertices as spheres"), ACIS bolted local tolerances on later, CGM had tolerant modeling from the start ([Parasolid docs](http://www.q-solid.com/Parasolid_Docs_V35/pdf/ov.pdf); [Lygin](https://opencascade.blogspot.com/2010/10/data-model-highlights-parasolid-acis.html)). A body watertight at 1e-6 has real gaps at 1e-8, so the same boolean classifies cleanly in one kernel and finds open shells in another. Kernels also carry different procedural surface types (rolling-ball blends, lazily evaluated intersection curves) that must be approximated on export. This is why a "healing" middleware industry exists (CADfix, Elysium, HOOPS Exchange): even *evaluated-geometry* exchange isn't solved, never mind semantics.

**Parametric paradigms are genuinely different languages.** Feature-history trees (CATIA, SolidWorks, FreeCAD), behavioral object families with a change-propagation network (Revit), interpreted scripting (ArchiCAD's GDL), dataflow graphs (Grasshopper, Dynamo, GenerativeComponents), direct modeling (SketchUp, AutoCAD). These differ the way Haskell, Prolog, and assembly differ — not in syntax but in evaluation model.

**Irreversible early decisions.** Revit's kernel prohibits closed/periodic faces — a cylinder is permanently two half-cylinders — a choice "made long ago" that can't be reversed ([The Building Coder](http://jeremytammik.github.io/tbc/a/1345_kernel_cylinder_faces.htm)). Every kernel has fossils like this.

## 3. What each tool actually uses

| Tool | Kernel | Native representation | Parametric model |
|---|---|---|---|
| Revit | Proprietary (ships ASM alongside for interop/Dynamo) | Analytic B-rep; no closed faces | Behavioral families + change-propagation engine |
| AutoCAD | ShapeManager (ACIS fork, 2001) | Exact B-rep | Direct; non-parametric solids |
| ArchiCAD | Proprietary | Segmented/polygonal; NURBS in GDL since v20 | GDL scripts + built-in element behaviors |
| Tekla Structures | Proprietary (inferred; no license footprint) | Profile + boolean-cut recipes, instanced | Custom components regenerate on host change |
| MicroStation / OpenBuildings | Parasolid (replaced ACIS) | Exact B-rep | Direct + features + GenerativeComponents |
| Vectorworks | Parasolid (since 2009) | Exact B-rep + NURBS | Direct + plug-in objects + Marionette |
| Allplan | Parasolid (since 2016) | Exact B-rep | SmartParts / PythonParts scripts |
| Rhino / Grasshopper | Proprietary (openNURBS) | Trimmed NURBS joined within document tolerance | No history; Grasshopper dataflow |
| SketchUp | Proprietary polygon engine | Planar facets only (no true curves) | Push-pull direct |
| CATIA / Digital Project | CGM | Exact B-rep, tolerant modeling, Class-A surfacing | Feature-history tree |
| SolidWorks | Parasolid (licensed from rival Siemens) | Exact B-rep | Feature history + D-Cubed DCM |
| Siemens NX | Parasolid | Exact B-rep + convergent (mesh) bodies | History + synchronous direct editing |
| FreeCAD | Open CASCADE | Exact B-rep, per-shape tolerances | Feature history (naming problem fixed in 1.0) |
| Navisworks | None | Tessellated mesh only | None — read-only aggregation |
| nTop | Proprietary implicit kernel | F-rep scalar fields | Function/workflow graphs |

One striking counter-fact: nearly the entire industry — SolidWorks, Inventor, NX, Solid Edge, Onshape — licenses the *same* constraint solver, Siemens' D-Cubed DCM ([engineering.com](https://www.engineering.com/parasolid-d-cubed-and-siemens-the-heart-of-your-cad-software-belongs-to-another/)). Shared semantic components are possible when economics align. They just haven't aligned for geometry.

## 4. The compiler analogy, made precise

The mapping is unusually clean, and taking it seriously clarifies exactly where the problem lives:

| CAD/BIM | Compilers |
|---|---|
| Native parametric model | Source program (language semantics = the app's runtime) |
| Model regeneration | Evaluation / compilation |
| IFC / STEP / mesh export | Object code emission |
| IFC import → DirectShape | Decompilation (hard, heuristic, usually punted) |
| Cross-kernel B-rep exchange | Binary translation between ISAs with different FP semantics |
| Tolerance "healing" (CADfix, Elysium) | Binary patching / fixups |
| Persistent naming problem | Stable symbols across recompilation |
| Onshape FeatureScript queries | Late-bound symbolic references instead of addresses |
| MVDs (Reference View, etc.) | Language profiles/subsets |
| CAx-IF biannual STEP test rounds | Manual differential testing of translators |
| D-Cubed DCM everywhere | A shared libm |

Two entries deserve expansion.

**Import is decompilation.** Lowering is easy and lossy; lifting is hard and heuristic. Recovering "this is a wall of family type X with these constraints" from a B-rep is the same problem shape as recovering structured C from a stripped binary. That's why the interesting academic work (§7) is all on the lifting side.

**The persistent naming problem is the deepest shared structure.** In history-based CAD, later features reference topological entities (face #23) of earlier features; re-evaluating after an edit regenerates topology and the references dangle — entities split, merge, renumber ([Marcheix & Pierra 2002](https://www.researchgate.net/publication/221115805_A_survey_of_the_persistent_naming_problem)). This plagued FreeCAD for a decade until 1.0 (Nov 2024) shipped realthunder's fix ([Ondsel](https://www.ondsel.com/blog/toponaming-problem-is-history/)). It's the reason parametric exchange fails *even between two instances of the same paradigm*: sending a feature history to a different kernel means every topological reference must re-resolve against differently-generated topology. Onshape's FeatureScript points at the PL-shaped answer: references as *semantic queries* ("the edge generated by feature X from sketch vertex Y"), lazily resolved — late binding instead of hard addresses ([FeatureScript](https://cad.onshape.com/FsDoc/library.html)). Any cross-tool IR must adopt this or die.

## 5. Why a literal LLVM fails

LLVM worked because of three preconditions, all absent here:

1. **A shared abstract machine.** C, Rust, and Swift all lower to the same model of computation — linear memory, arithmetic with specified semantics. Lowering to LLVM IR loses high-level structure (templates, ownership) *and that's fine*, because the artifact's purpose is execution, not further editing. In AEC, the artifact's purpose **is** further editing. You don't need a compiler; you need a *transpiler that preserves editability* — semantics-preserving source-to-source translation, which is famously brutal even C++→Rust.
2. **Specified semantics.** LLVM rests on language specs and a defined UB contract. Geometry kernel operations have no spec; the behavior *is* the implementation, down to tolerance heuristics near tangencies. Two kernels can legitimately disagree about whether two surfaces intersect. It's as if every CPU had different floating-point behavior and all code was compiled `-ffast-math`. An IR without an execution-semantics contract is just a file format — which is what IFC already is.
3. **Aligned incentives.** Apple and Google needed LLVM and funded it. In AEC, lossless export is *anti-aligned* with the dominant vendor's business model — Autodesk's granular data APIs run inside Autodesk's cloud, rate-limited, with a "no use by competitors" clause ([AEC Magazine](https://aecmag.com/technology/autodesks-granular-data-strategy/)). The DTV didn't fail for technical reasons alone.

So your suspicion is correct: "they all speak a different underlying language" defeats the single-shared-IR-at-one-level plan. But that's the LLVM-2003 framing. The field moved on, and the direction it moved is exactly the direction AEC needs.

## 6. What MLIR and Relax actually teach

The modern lesson isn't "one IR to rule them all" — it's **MLIR**: multiple dialects at different abstraction levels coexisting in one module, with *progressive, partial* lowering instead of single-shot lowering, and legalization passes between dialects. And **Relax** is the most instructive instance of this philosophy, because every one of its three core ideas maps onto the AEC problem with almost embarrassing directness.

**(a) Cross-level abstraction.** Relax's diagnosis of ML compilers is a perfect description of the AEC pipeline: traditional stacks have separate IRs per level (computational graph → tensor program → hardware) with uni-directional single-shot lowering, so optimization opportunities that span levels are invisible. Relax instead holds computational graphs, loop-level tensor programs, *and opaque external library calls* in one program, so a pass can rewrite the graph using facts learned from inside a kernel. AEC translation: an exchange artifact should carry **design intent/constraints + parametric recipe + evaluated B-rep + tessellation simultaneously, with explicit provenance links between levels** — the way a binary carries DWARF debug info mapping instructions back to source lines. A consumer executes the highest dialect it understands and falls back per-element, not per-file. Today's formats force a single level: IFC-RV is bottom-level only; STEP AP242's parametric parts (ISO 10303-55/-108/-111) exist on paper as a *separate* layer nobody implements ([NIST](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=904157)).

**(b) First-class symbolic shapes.** Relax's sharpest idea: when a tensor dimension is dynamic, don't erase it to `Any`/unknown (as Relay and ONNX did) — keep a symbolic expression (`n`, `4n`) and propagate relations through every pass, because erased relations are exactly what kills optimization. **This is the precise mechanism of IFC's lossiness.** A Revit wall's height isn't 3000mm; it's `level_3.elev − level_2.elev`. Export bakes it to `3000`, erasing the relation — the geometric equivalent of erasing to `Any`. A viable format would keep the symbolic expression attached to the baked value. IFC's own property system can't express "this dimension = that expression over those variables"; this is arguably *the* missing feature, and it's a smaller ask than full parametric exchange.

**(c) `match_cast` and the dynamic fallback.** When Relax can't deduce a shape statically (data-dependent ops like `unique`), it doesn't give up — it lets the program *assert* a symbolic shape via `match_cast`, backed by a cheap runtime check that errors on violation. This suggests the single best concrete design for parametric exchange, and I haven't seen it proposed anywhere: **ship the recipe AND the baked geometry; the importer re-evaluates the recipe on its own kernel and diffs against the baked result. Within tolerance ε → use the live parametric lift; divergence → fall back to the baked level for that element and flag it.** That turns the tolerance problem (§5.2) from a silent correctness bug into a checked, per-element graceful degradation — exactly Relax's "static when possible, dynamic fallback as needed," transposed. The baked geometry plays the role of the runtime check.

**(d) Partial lowering & library dispatch.** Relax lowers *some* subgraphs to cuBLAS/CUTLASS calls (`call_dps_library`), optimizes others itself, and composes both — the lowering decision is per-region, not global. AEC exporters today are all-or-nothing per file. Per-element partial lowering (standard wall → parametric dialect; sculpted façade panel → B-rep dialect; point-cloud furniture → mesh dialect) is the obvious right behavior. And `call_dps_library` has a provocative AEC reading: treat proprietary kernels as *linkable opaque evaluators*. Where a recipe depends on Revit's join-resolution behavior, the IR carries a call to a named evaluator (headless app, vendor cloud API) rather than pretending the semantics are portable — geometry's FFI. You keep semantic fidelity at the cost of a runtime dependency, and it's honest about where portability actually ends.

**(e) Analysis feedback.** Relax runs a lightweight analysis over opaque tensor programs to classify each as `ElementWise` / `Injective` / `Reduction` etc., so graph-level fusion can handle custom kernels without hand annotations. The AEC analog is the lifting toolchain: analyze dumb geometry, classify it back into higher-dialect ops ("this solid is an extrusion of that profile"; "these 40 solids are one array"). That's exactly what's emerging in research — which brings us to what already exists.

## 7. The pieces already exist, scattered

Nobody has built the MLIR-for-buildings, but every component has a working prototype somewhere:

**The lifting direction (decompilers).** InverseCSG (MIT) formulates mesh→CSG as program synthesis ([inversecsg.csail.mit.edu](https://inversecsg.csail.mit.edu/)). Szalinski (PLDI 2020) uses **equality saturation over e-graphs** to shrink flat CSG into editable parametric programs with loops and parameters — an e-graph compactly holds *many equivalent constructions of the same shape* at once, so you can extract the construction idiom the target system prefers ([Szalinski](https://www.mwillsey.com/papers/pldi-szalinski); [egg, POPL 2021](https://egraphs-good.github.io/)). E-graphs are the natural middle-end for a geometry compiler: same shape, multiple constructions, choose per-target. Point2CAD reconstructs full B-rep with topology from point clouds ([ETH](https://www.obukhov.ai/point2cad.html)); CAD-Recode (ICCV 2025) lifts point clouds directly to executable CadQuery Python via an LLM ([cad-recode.github.io](https://cad-recode.github.io/)); Fusion 360 Gallery and DeepCAD provide the training corpora of real construction sequences. On the BIM side this is called "semantic enrichment" (Sacks et al., rule-based and GNN-based inference of semantics from IFC geometry). The lifting side of the compiler is becoming tractable *fast*, largely because of ML — and note the convergence: LLMs prefer code-CAD targets (CadQuery, Zoo's KCL — explicitly "the source of truth... just read the KCL" ([zoo.dev](https://zoo.dev/research/introducing-kcl))), which pushes the industry toward textual, versionable, liftable representations for its own reasons.

**The multi-level/composition direction.** IFC5 itself is quietly conceding the architecture argument: it abandons the monolithic EXPRESS file for an entity-component-system in JSON (`.ifcx`) with **USD-style layered composition** — separate files composing as override layers ([IFC5-development](https://github.com/buildingSMART/IFC5-development); [buildingSMART](https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/)). OpenUSD's composition algebra (ratified as Core Spec 1.0, Dec 2025 ([AOUSD](https://aousd.org/news/core-spec-announcement/))) is a genuine IR for *scene assembly* — but has no B-rep schema, no solid-modeling semantics; CAD→USD means tessellation. USD solves multi-party layering, not geometry semantics.

**The pragmatic-bridge direction.** Speckle is the most honest engineering artifact: per-app connectors convert to a host-agnostic object model where every element carries its source-app property bag, a stable `applicationId`, *and* a `displayValue` mesh fallback ([Speckle docs](https://docs.speckle.systems/developers/data-schema/concepts)) — cross-level carrying with graceful degradation, minus the parametric dialect. Notably, Speckle *retreated* from a strongly-typed universal AEC schema (v2's BuiltElements) to schema-agnostic property bags in v3: empirical evidence that the universal-ontology approach fails and level-carrying wins. KAIST's "macro-parametrics" line (2002–2020) tried translating modeling-command macros through a neutral command set — a real neutral-IR attempt for MCAD that never achieved commercial adoption, foundering on feature mapping, constraint translation, and persistent naming ([JCDE 2020](https://academic.oup.com/jcde/article/7/5/603/5818508)).

**Confirmed gaps** (multiple search strategies, July 2026): no published MLIR/LLVM-style multi-dialect IR proposal for CAD/BIM; no differential-testing/fuzzing campaign against geometry kernels (the CAx-IF's biannual human-mediated STEP test rounds are the closest thing); no formal treatment of interop as gradual/partial semantics preservation. If you're looking for an unclaimed research program, it's sitting right there.

## 8. What a real system would look like

Sketch of the stack the analysis implies:

```
D4  Intent dialect        constraints, symbolic relations, behavioral contracts
D3  Recipe dialect        features, profiles, sweeps, booleans, arrays
                          (references = semantic queries, never topo indices)
D2  Exact-geometry        B-rep with explicit per-entity tolerance semantics
    dialect               (or exact arithmetic à la TOG'25 exact mesh CSG)
D1  Mesh dialect          tessellation, always present, always renderable
────────────────────────────────────────────────────────────────────────
     One artifact carries D4→D1 per element, with provenance links.
     Import = lift as high as validation allows; recipe re-evaluated on
     local kernel, diffed against shipped D2/D1 (match_cast); divergence
     → per-element fallback. Proprietary behavior = FFI to named evaluators.
     Middle-end = e-graph over D3 to re-idiomize constructions per target.
     Conformance = differential test corpus across kernels, CI-style.
```

The honest hard residue: (1) **numerics** — re-evaluating one recipe on two kernels yields different geometry; the match_cast pattern manages this but exact-arithmetic kernels or a specified tolerance contract would be needed to eliminate it; (2) **behavioral semantics are code, not data** — Revit's join resolution can't be exported as data; either vendors adopt a shared behavior language (a GDL/FeatureScript descendant — near-zero incentive) or the FFI/evaluator route institutionalizes partial vendor dependence; (3) **economics** — the binding constraint. LLVM had aligned funders; here the dominant vendor profits from the lossiness. The plausible forcing functions are AI (models want liftable, code-like representations; vendors want AI features), owners/governments demanding data sovereignty in procurement, and buildingSMART's USD-flavored IFC5 lowering the architectural barrier. Watch whether IFC5's component model grows a recipe dialect and symbolic expressions; that's the fork in the road.

## 9. Verdict

Your LLVM instinct is right about the *strategy* (a shared compiler infrastructure with real semantics) and wrong about the *shape* (a single IR at one level). A single shared representation of realized geometry already exists — it's STEP/IFC, and its single-level-ness is precisely the pathology. The applicable state of the art is MLIR's multi-dialect progressive lowering, and Relax is the most relevant single paper you could have picked, more relevant than LLVM itself: its three moves — keep all abstraction levels in one program, never erase symbolic relations even when you must bake values, and pair static structure with checked dynamic fallbacks — are, transposed, a nearly complete design brief for parametric exchange. The blocker is not IR design. It's that geometry kernels have no specified semantics to compile against, cross-system references need late-bound naming, and the incumbent has every incentive to keep compilation one-way. Compiler engineering can solve the first two. The third is why the revolution, if it comes, arrives wearing an AI costume rather than a standards-committee badge.

---

## Sources

**Relax & compiler infrastructure**
- Lai, Shao, Feng, Lyubomirsky et al., [*Relax: Composable Abstractions for End-to-End Dynamic Machine Learning*](https://yuchenjin.github.io/papers/asplos25-relax.pdf), ASPLOS 2025
- [MLIR](https://en.wikipedia.org/wiki/MLIR_(software))

**Kernels & representations**
- [The Building Coder: Revit's geometry kernel](http://jeremytammik.github.io/tbc/a/1345_kernel_cylinder_faces.htm) · [ShapeManager](https://en.wikipedia.org/wiki/ShapeManager) · [Geometric modeling kernel table](https://en.wikipedia.org/wiki/Geometric_modeling_kernel)
- [Siemens: Vectorworks adopts Parasolid](https://www.plm.automation.siemens.com/global/en/our-story/newsroom/siemens-press-release/43290) · [AEC Magazine: Allplan + Parasolid](https://aecmag.com/news/news-nemetschek-opens-up-allplan-to-freeform-modelling/) · [Spatial: CGM](https://blog.spatial.com/news/cgm)
- [Parasolid tolerant modeling docs](http://www.q-solid.com/Parasolid_Docs_V35/pdf/ov.pdf) · [Lygin: Parasolid vs ACIS vs OCCT data models](https://opencascade.blogspot.com/2010/10/data-model-highlights-parasolid-acis.html)
- [engineering.com: Parasolid, D-Cubed and Siemens](https://www.engineering.com/parasolid-d-cubed-and-siemens-the-heart-of-your-cad-software-belongs-to-another/)
- [Tekla modeling internals](https://support.tekla.com/doc/tekla-structures/2021/rel_2021_modeling_improvements) · [Navisworks graphics pipeline (founding architect)](https://www.thecandidstartup.org/2023/03/27/navisworks-graphics-pipeline.html) · [nTop: B-reps vs implicits](https://ntopology.com/blog/understanding-the-basics-of-b-reps-and-implicits/)

**IFC / STEP / USD / interop**
- [IfcShapeRepresentation types](https://standards.buildingsmart.org/IFC/DEV/IFC4_2/FINAL/HTML/schema/ifcrepresentationresource/lexical/ifcshaperepresentation.htm) · [IfcExtrudedAreaSolid](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcExtrudedAreaSolid.htm)
- [Autodesk: IFC-imported elements can't be edited](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-modify-cut-join-geometry-or-apply-material-to-elements-imported-from-IFC-to-Revit.html) · [BIM Corner: IFC4 DTV post-mortem](https://bimcorner.com/is-the-industry-ready-for-ifc4/) · [buildingSMART MVDs](https://technical.buildingsmart.org/standards/ifc/mvd/)
- [IFC5-development (ECS + layered composition)](https://github.com/buildingSMART/IFC5-development) · [IFC5 consultation outcome](https://www.buildingsmart.org/ifc-5-core-consultation/) · [IFC5 examples/viewer](https://ifc5.technical.buildingsmart.org/)
- [NIST: parametric exchange via ISO 10303-108](https://www.govinfo.gov/content/pkg/GOVPUB-C13-38c6804180ddd38aa87a68f74ad21bcc/pdf/GOVPUB-C13-38c6804180ddd38aa87a68f74ad21bcc.pdf) · [AP242 Edition 4](https://www.ap242.org/edition-4.html) · [CAx-IF test rounds](https://www.mbx-if.org/home/cax/testrounds/)
- [AOUSD Core Spec 1.0](https://aousd.org/news/core-spec-announcement/) · [NVIDIA: CAD→USD tessellates](https://developer.nvidia.com/blog/building-cad-to-usd-workflows-with-nvidia-omniverse/)
- [Speckle data schema](https://docs.speckle.systems/developers/data-schema/concepts) · [AEC Magazine: Autodesk's granular data strategy](https://aecmag.com/technology/autodesks-granular-data-strategy/) · [CADfix healing](https://www.iti-global.com/interoperability-products/cadfix/)

**PL/compilers applied to CAD**
- [Szalinski (PLDI 2020)](https://www.mwillsey.com/papers/pldi-szalinski) · [egg (POPL 2021)](https://egraphs-good.github.io/) · [Reincarnate (ICFP 2018)](https://github.com/uwplse/reincarnate-aec) · [Carpentry Compiler](https://grail.cs.washington.edu/projects/carpentrycompiler/)
- [InverseCSG (MIT)](https://inversecsg.csail.mit.edu/) · [DeepCAD](https://www.cs.columbia.edu/cg/deepcad/) · [Fusion 360 Gallery](https://github.com/AutodeskAILab/Fusion360GalleryDataset) · [Point2CAD](https://www.obukhov.ai/point2cad.html) · [CAD-Recode](https://cad-recode.github.io/)
- [Persistent naming survey (Marcheix & Pierra)](https://www.researchgate.net/publication/221115805_A_survey_of_the_persistent_naming_problem) · [FreeCAD toponaming fix](https://www.ondsel.com/blog/toponaming-problem-is-history/) · [Onshape FeatureScript queries](https://cad.onshape.com/FsDoc/library.html)
- [KAIST macro-parametrics / feature mapping & naming issues (JCDE 2020)](https://academic.oup.com/jcde/article/7/5/603/5818508) · [Zoo KCL](https://zoo.dev/research/introducing-kcl) · [Exact predicates mesh CSG (TOG 2025)](https://dl.acm.org/doi/10.1145/3744642)

**Noted uncertainties:** Revit's internal kernel vs. bundled ASM split is undocumented; Tekla's proprietary kernel is inferred (no licensing footprint found); numeric tolerance defaults come from third-party primers mirroring kernel docs; "no MLIR-for-CAD exists" and "no kernel fuzzing campaign exists" are negative claims — repeatedly searched, not provable.
