# Research notes: geometry kernels & representations per AEC/CAD tool

Web-verified research pass, 2026-07-04. Per-claim sources inline; unverified
claims flagged at the bottom. Feeds sections 2-3 of the analysis report.

## Per-application findings

### Revit (Autodesk)
- **Kernel:** proprietary in-house, never publicly named. A Revit dev team
  member describes design choices in "Revit's geometry kernel" — it prohibits
  closed/periodic edges and faces (a cylinder is always two half-cylinder
  faces) to avoid parameter-space ambiguity; a choice "made long ago" that
  can't be reversed ([The Building Coder](http://jeremytammik.github.io/tbc/a/1345_kernel_cylinder_faces.htm)).
  Autodesk's developer advocate declined to name the kernel when asked
  ([forum](https://forums.autodesk.com/t5/revit-api-forum/revit-kernel-geometric-modeling-kernel-geometry-presentation/td-p/10473250)).
  Revit *ships* Autodesk ShapeManager (ASM) binaries — Dynamo docs list Revit
  among "ProductsWithASM" ([Dynamo primer](https://primer2.dynamobim.org/1_developer_primer_intro/3_developing_for_dynamo/13-dynamo-integration)).
- **Representation:** exact analytic/parametric B-rep + faceted meshes for imports.
- **Paradigm:** behavioral object families — a "context-driven change engine"
  propagating changes through a relationship network (walls auto-join, hosted
  elements move with hosts); not a user-facing feature tree
  ([Autodesk whitepaper](https://www.academia.edu/5879710/REVIT_BUILDING_INFORMATION_MODELING_Parametric_Building_Modeling_BIMs_Foundation)).

### AutoCAD (Autodesk)
- **Kernel:** ShapeManager (ASM), forked from Spatial's ACIS 7.0 in Nov 2001;
  Autodesk prevailed in court 2003 ([Wikipedia: ShapeManager](https://en.wikipedia.org/wiki/ShapeManager)).
  AutoCAD, Inventor, Fusion all ASM-based ([kernel table](https://en.wikipedia.org/wiki/Geometric_modeling_kernel)).
  Fork froze at ACIS 7.0 → can't read newer SAT ([CADInterop](https://www.cadinterop.com/en/formats/neutral-format/acis.html)).
- **Paradigm:** direct modeling; drafting-first, non-parametric solids.

### ArchiCAD (Graphisoft)
- **Kernel:** proprietary ("Own Kernel" in the Wikipedia table). Historically
  segmented/polygonal curve handling — "the ArchiCAD modeling kernel does not
  process the math formulas for a curve the same way a NURBS modeler does"
  ([Graphisoft Community](https://community.graphisoft.com/t5/Modeling/Real-Curves-in-Archicad/td-p/247201/page/2));
  NURBS primitives added to GDL in v20 ([GDL reference](https://gdl.graphisoft.com/gdl_reference_guide_chapter/nurbs)).
- **Paradigm:** GDL — BASIC-derived interpreted language scripting parametric
  library objects ([About GDL](https://gdl.graphisoft.com/gdl-basics/about-gdl/));
  construction elements use built-in behaviors and priority-based junctions.

### Tekla Structures (Trimble)
- **Kernel:** proprietary in-house (inferred; no licensing footprint found — flagged).
- **Representation:** procedural/CSG-style — part = profile + material +
  boolean modifiers; API exposes `Solid` as "raw solid, fittings and cut
  planes", `BooleanPart` for cuts; faces carry creator-object IDs
  ([Tekla Open API](https://developer.tekla.com/documentation/tekla-structures-191-open-api-release-notes),
  [BooleanPart](https://developer.tekla.com/doc/tekla-structures/2024/boolean-part-class-27061)).
  Part solids instanced and stored part-local for memory/regeneration at
  100k-part scale ([2021 modeling improvements](https://support.tekla.com/doc/tekla-structures/2021/rel_2021_modeling_improvements)).
- **Paradigm:** object-based with parametric custom components; Grasshopper live-link.

### Bentley MicroStation / OpenBuildings
- **Kernel:** Parasolid; earlier ACIS (SmartSolids), replaced "due to
  performance and functional shortcomings" ~MicroStation/J era
  ([Shapr3D history](https://www.shapr3d.com/history-of-cad/bentley-systems-incorporated),
  [kernel table](https://en.wikipedia.org/wiki/Geometric_modeling_kernel)).
  OpenBuildings uses "the Parasolid 3D Modeling kernel"
  ([Bentley docs](https://docs.bentley.com/LiveContent/web/OpenBuildings%20StationDesigner%20Help-v3/en/GUID-E4E9942B-8355-8C0A-7DBA-81B7CB39FE40.html)).
- **Paradigm:** hybrid direct + features + GenerativeComponents dataflow.

### Vectorworks (Nemetschek)
- **Kernel:** Parasolid since Vectorworks 2009 (announced 2008-09-15,
  [Siemens press release](https://www.plm.automation.siemens.com/global/en/our-story/newsroom/siemens-press-release/43290));
  ~4-5x faster 3D ops, up to 12x booleans vs prior kernel
  ([Macworld](https://www.macworld.com/article/196584/vectorworks09.html)).
- **Paradigm:** direct + parametric plug-in objects + Marionette node graph.

### Allplan (Nemetschek)
- **Kernel:** Parasolid, integrated Allplan 2016
  ([AEC Magazine](https://aecmag.com/news/news-nemetschek-opens-up-allplan-to-freeform-modelling/),
  [allplan.com](https://www.allplan.com/us_en/product/allplan-engineering/)).
  Siemens lists Bentley, Midas IT, Allplan, Vectorworks as AEC Parasolid
  adopters ([Siemens](https://plm.sw.siemens.com/en-US/plm-components/parasolid/)).
- **Paradigm:** BIM objects + scripted SmartParts/PythonParts.

### Rhinoceros / Grasshopper (McNeel)
- **Kernel:** own proprietary; openNURBS is the open geometry library/3DM
  format ([What is openNURBS?](https://developer.rhino3d.com/guides/opennurbs/what-is-opennurbs/)).
- **Representation:** NURBS-first; "solids" are joined trimmed-NURBS B-reps
  sealed within document tolerance ([NURBS overview](https://developer.rhino3d.com/guides/opennurbs/nurbs-geometry-overview/)).
- **Paradigm:** direct, no history; Grasshopper dataflow visual programming.

### SketchUp (Trimble)
- **Kernel:** none (face/edge polygon engine); no true curves — circles are
  edge sequences, surfaces are facets softened visually
  ([Ruby API Face](https://ruby.sketchup.com/Sketchup/Face.html),
  [Softening/Smoothing](https://help.sketchup.com/en/sketchup/softening-smoothing-and-hiding-geometry)).
- **Paradigm:** push-pull direct; Dynamic Components with attribute formulas.

### CATIA (Dassault) — and Gehry's Digital Project
- **Kernel:** CGM (Convergence Geometric Modeler), Dassault in-house for
  V5/V6/3DEXPERIENCE, commercialized via Spatial 2011
  ([Spatial](https://blog.spatial.com/news/cgm), [engineering.com](https://www.engineering.com/spatial-acis-cgm-and-the-future-of-geometric-modeling-kernels/)).
  Exact multi-dimensional B-rep with foundation-based tolerant modeling,
  Class-A surfacing ([Spatial CGM](https://www.spatial.com/solutions/3d-modeling/cgm-modeler)).
- **Digital Project:** Gehry Technologies' CAD "based on CATIA V5"
  ([Wikipedia](https://en.wikipedia.org/wiki/Digital_Project),
  [Priceonomics](https://priceonomics.com/the-software-behind-frank-gehrys-geometrically/)).
  Exists because freeform-to-fabrication needed aerospace-grade surfacing.

### SolidWorks (Dassault)
- **Kernel:** Parasolid since SolidWorks 95 — Dassault pays arch-rival
  Siemens for its best-seller's kernel
  ([Wikipedia: Parasolid](https://en.wikipedia.org/wiki/Parasolid),
  [engineering.com](https://www.engineering.com/parasolid-d-cubed-and-siemens-the-heart-of-your-cad-software-belongs-to-another/)).
- **Paradigm:** feature history + D-Cubed DCM sketch constraints.

### Siemens NX
- **Kernel:** Parasolid (Shape Data, Cambridge 1988 → Unigraphics 1996 →
  Siemens). Exact B-rep + Convergent Modeling (facet bodies first-class)
  ([Siemens Parasolid](https://plm.sw.siemens.com/en-US/plm-components/parasolid/)).
- **Paradigm:** history + Synchronous Technology direct editing (D-Cubed 3D DCM).

### FreeCAD
- **Kernel:** Open CASCADE Technology (OCCT), LGPL B-rep kernel
  ([dev.opencascade.org](https://dev.opencascade.org/project/freecad)).
- **Paradigm:** feature-history parametric — canonical demonstration of its
  fragility: the topological naming problem, mitigated in FreeCAD 1.0 via
  realthunder's persistent-naming algorithm
  ([Ondsel](https://www.ondsel.com/blog/toponaming-problem-is-history/),
  [FreeCAD wiki](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Topological_naming_problem.md)).

### Navisworks (Autodesk) — viewer contrast
- No modeling kernel: everything tessellated to triangles on import,
  conditioned for streaming/review (NWC/NWD); clash detection runs on facets
  ([The Candid Startup — by Navisworks' founding architect](https://www.thecandidstartup.org/2023/03/27/navisworks-graphics-pipeline.html)).

### nTopology (nTop) — implicit contrast
- Proprietary implicit kernel (rewritten in nTop 5.0, 2024-06-24
  ([nTop support](https://support.ntop.com/hc/en-us/articles/26062971882131-nTop-5-0-New-Implicit-Modeling-Kernel))).
  Bodies are scalar fields f(x,y,z) ≤ 0; booleans are min/max compositions
  that "never fail" — vs B-rep kernels that "rely on a large number of
  heuristic rules" ([nTop](https://ntopology.com/blog/understanding-the-basics-of-b-reps-and-implicits/)).
  Cost: no exact edges/faces until reconstruction.

## Tolerance models: why the same boolean succeeds in one kernel, fails in another

- Parasolid default precision ~1e-8 (model units) vs ACIS ~1e-6
  ([ProtoTech primer](https://prototechsolutions.com/cad-notes/a-15-minute-primer-to-parasolid-geometry-modeler/),
  [CAD Exchanger](https://cadexchanger.com/acis-to-parasolid/)).
- Tolerant modeling relaxes per-entity: Parasolid docs — "think of edges as
  tubes and vertices as spheres" whose radii grow until geometry intersects
  ([Parasolid overview docs](http://www.q-solid.com/Parasolid_Docs_V35/pdf/ov.pdf)).
  ACIS added tolerant edges/vertices later as a subsystem
  ([ACIS docs](http://www-isl.ece.arizona.edu/ACIS-docs/PDF/KERN/06TMOD.PDF));
  CGM tolerant from the start. Per Roman Lygin (ex-OCCT PM): "Parasolid, like
  Open CASCADE, does use local tolerances attached to the topological
  entities. ACIS introduced local tolerances in some intermediate versions
  only" ([Lygin](https://opencascade.blogspot.com/2010/10/data-model-highlights-parasolid-acis.html)).
- Consequences: a body watertight at 1e-6 has real gaps at 1e-8; kernels
  carry different procedural surface types (rolling-ball blends, lazy
  intersection curves) that must be approximated on export; cross-kernel
  conversion "introduces topological defects invisible on screen"
  ([CADInterop](https://www.cadinterop.com/en/formats/neutral-format/parasolid.html)).

## D-Cubed DCM: the shared constraint solver

D-Cubed 2D DCM is the de facto industry sketch solver — licensed by
SolidWorks, Inventor/Fusion, NX, Solid Edge, Onshape and others; "Siemens
licenses these components to practically every CAD company"
([engineering.com](https://www.engineering.com/parasolid-d-cubed-and-siemens-the-heart-of-your-cad-software-belongs-to-another/),
[Siemens 2D DCM](https://plm.sw.siemens.com/en-US/plm-components/d-cubed/2d-dcm/)).
Proof that shared semantic components are possible when economics align.

## Why domains diverge (no universal representation)

Architecture: prismatic geometry + huge relationship networks + 2D document
extraction. Steel detailing: instanced procedural recipes beat general
B-rep at 100k-part scale. General AEC (Bentley/VW/Allplan): buy Parasolid
robustness. Freeform/fabrication: NURBS surface quality (Rhino) or Class-A
exact B-rep (CGM). Review: tessellation for streaming (Navisworks). Lattice:
implicits (nTop). Tradeoff wall: exact B-rep = precise semantics, heavy,
heuristic-fragile; mesh = robust, dumb, bloated for curves; implicit =
boolean-proof, no persistent topology; procedural = compact, parametric,
must re-evaluate.

## Unverified / flagged

1. Revit: internal split between native kernel and bundled ASM undocumented.
2. Tekla: proprietary kernel inferred (no primary statement).
3. ArchiCAD internals sourced from community forums, not formal docs.
4. MicroStation ACIS→Parasolid transition date soft.
5. SolidWorks-on-Parasolid as of mid-2026 from secondary sources.
6. Numeric tolerance defaults from third-party primers mirroring kernel docs.
