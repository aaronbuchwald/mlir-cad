# Research notes: AEC/CAD interoperability landscape (as of July 2026)

Web-verified research pass, 2026-07-04. Sources inline; flags at bottom.
Feeds sections 1, 5, 7 of the analysis report.

## 1. IFC 4.x: what the schema can carry vs what implementations do

**Schema supports** multiple representation classes — `SweptSolid`,
`AdvancedSweptSolid`, `Brep`, `AdvancedBrep`, `CSG`, `Clipping`,
`Tessellation` etc. ([IfcShapeRepresentation](https://standards.buildingsmart.org/IFC/DEV/IFC4_2/FINAL/HTML/schema/ifcrepresentationresource/lexical/ifcshaperepresentation.htm)):
procedural solids (`IfcExtrudedAreaSolid` = profile + direction + depth,
[IFC4.3 docs](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/IfcExtrudedAreaSolid.htm));
CSG/booleans (`IfcBooleanResult`, openings via `IfcOpeningElement` +
`IfcRelVoidsElement`, filling via `IfcRelFillsElement`); IFC4 exact NURBS
B-rep (`IfcAdvancedBrep`); IFC4 compact meshes (`IfcTriangulatedFaceSet`).
So IFC *can* carry shallow construction history. It cannot carry
dimension-driven sketches, constraint state, regeneration order, or
family/type behavior.

**Exporters:** Revit emits swept solids where it can, falls back to
B-rep/tessellation ([Autodesk IFC manual](https://autodesk.ifc-manual.com/revit/ifc-export-settings-dialog/level-of-detail-advanced));
the only widely certified IFC4 MVD (Reference View) is deliberately
tessellation-oriented one-way coordination
([bSI RV](https://standards.buildingsmart.org/MVD/RELEASE/IFC4/ADD2_TC1/RV1_2/HTML/schema/views/reference-view/index.htm)).

**Importers:** Revit "Open IFC" creates DirectShape — static, non-editable;
cannot modify/cut/join/retype ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-modify-cut-join-geometry-or-apply-material-to-elements-imported-from-IFC-to-Revit.html),
[DirectShape API docs](https://help.autodesk.com/view/RVT/2023/ENU/?guid=Revit_API_Revit_API_Developers_Guide_Revit_Geometric_Elements_DirectShape_html)).
Third-party importers expose "parametric preferred / revert to direct shape
on error" ([Geometry Gym](https://technical.geometrygym.com/revit/revitifc/ifc-import/ifc-import-options)).

**Why round-trips fail:** many-to-many semantic mapping (app ontology ↔ IFC
classes, user-configurable, not idempotent); GUID instability across exports
(documented Revit bugs [#521](https://github.com/Autodesk/revit-ifc/issues/521),
[#313](https://github.com/Autodesk/revit-ifc/issues/313); background
[Tammik](https://jeremytammik.github.io/tbc/a/0819_ifc_guid.htm)); behavior
representable only as *results* (`IfcRelConnectsPathElements`), never rules;
MVD certification tests import/export against a profile, not round-trip
fidelity ([bSI MVD](https://technical.buildingsmart.org/standards/ifc/mvd/)).
The IFC4 **Design Transfer View** (the "import for further editing" MVD)
effectively died — zero certified products
([BIM Corner](https://bimcorner.com/is-the-industry-ready-for-ifc4/),
[bSI forum](https://forums.buildingsmart.org/t/ifc4-design-transfer-view-spec/1737)).
MVD concept being retired in favor of IDS + the
[IFC Validation Service](https://www.buildingsmart.org/users/services/validation-service/).

Current versions: IFC4.0.2.1 (ISO 16739-1:2018), IFC4.3 ADD2
(ISO 16739-1:2024), IFC2x3 TC1 still official; IFC4.4 in planning
([spec database](https://technical.buildingsmart.org/standards/ifc/ifc-schema-specifications/)).

## 2. IFC5: ECS, USD influence, JSON, timeline

[IFC5-development repo](https://github.com/buildingSMART/IFC5-development)
(alpha): files are lists of JSON "components" attached to entities;
multiple files compose as **layers** with opinion overrides — e.g. a
separate `add-firerating` file overrides a property without touching the
original ([Examples FAQ](https://github.com/buildingSMART/IFC5-development/blob/main/Examples_FAQ.md)).
Structurally USD-like; described as ECS
([bSI Spain](https://www.buildingsmart.es/2024/12/03/the-evolution-of-ifc-the-path-to-ifc5/)).
JSON serialization, `.ifcx` extension, TypeSpec schemas, schemas on
[ifcx.dev](https://ifcx.dev/), viewer at
[ifc5.technical.buildingsmart.org](https://ifc5.technical.buildingsmart.org/).
"There will not be STEP syntax in IFC 5."

Status: Core Draft Project Plan consultation closed 2025-08-08 — 67%
weighted support (just above the 65% threshold), joint concern letter from
nine national chapters (finance, governance, technical clarity); Final
Project Plan mandated ([bSI consultation](https://www.buildingsmart.org/ifc-5-core-consultation/)).
No published release date as of mid-2026. Note: community
[ifcJSON](https://github.com/buildingsmart-community/ifcJSON) is a separate
older IFC4 JSON mapping — don't conflate.

## 3. STEP AP242: parametric parts nobody ships

AP242 Ed4 published as ISO 10303-242:2025
([ISO](https://www.iso.org/standard/84300.html),
[ap242.org Ed4](https://www.ap242.org/edition-4.html)). Scope on paper
includes parametric/constrained geometry and construction history via ISO
10303-55/-108/-111
([ap242.org](https://www.ap242.org/geometry-assembly-pmi-interoperability.html),
[ISO 10303-108](https://www.iso.org/standard/34697.html)). Reality:
production translators exchange evaluated B-rep + PMI, not recipes; the only
-55/-108/-111 implementations were research prototypes, chiefly NIST's
([NISTIR 7433](https://www.govinfo.gov/content/pkg/GOVPUB-C13-38c6804180ddd38aa87a68f74ad21bcc/pdf/GOVPUB-C13-38c6804180ddd38aa87a68f74ad21bcc.pdf),
[NIST procedural exchange](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=904157)).
Why: features don't regenerate identically across kernels/solvers, receiving
systems must re-execute and reconcile, mapping/test burden enormous, and
history portability erodes lock-in. Commercial feature migration is
proprietary remastering (Elysium CADfeature, ITI Proficiency).

## 4. OpenUSD + AOUSD

AOUSD ratified **OpenUSD Core Specification 1.0** on 2025-12-17 (grammar,
data model, composition algorithm, USDA/USDC/USDZ, conformance)
([AOUSD](https://aousd.org/news/core-spec-announcement/),
[LF press](https://www.linuxfoundation.org/press/alliance-for-openusd-announces-core-specification-1.0-the-universal-language-for-building-3d-worlds)).
March 2026: roadmap toward Core Spec 1.1; ISO ratification pursued.
**AECO Interest Group** charter renewed 2025-07-28 — assesses USD's role in
AECO and relationship with IFC; interest group, not spec-writing
([AOUSD interest groups](https://aousd.org/community/interest-groups/)).
USD offers layered composition (sublayers, references, variants, opinion
strength) — the mechanism IFC5 is copying. Limits: no manifold B-rep schema,
no solid semantics, no PMI/GD&T, no feature history; `UsdGeomNurbsPatch`
exists but CAD→USD pipelines tessellate
([NVIDIA](https://developer.nvidia.com/blog/building-cad-to-usd-workflows-with-nvidia-omniverse/)).

## 5. Speckle, BHoM, Hypar

**Speckle:** everything derives from `Base` (content-hash id, dynamic
props); large values detached and deduplicated; v3 schema = Collection →
**DataObject** (semantic element with source-app property bag **plus**
`displayValue` mesh fallback) + Proxies; `applicationId` = stable source-app
identity across versions ([data-schema concepts](https://docs.speckle.systems/developers/data-schema/concepts)).
Per-app connectors on Send/Receive. Design honest about lossiness: a Revit
wall received in Rhino is meshes+metadata. **v2→v3 moved away from a
strongly-typed universal BuiltElements ontology to schema-agnostic property
bags — empirical retreat from universal typed schemas.** $12.5M Series A
June 2025 ([blog](https://speckle.systems/blog/speckle-raises-12-5-million-to-build-the-first-aec-data-hub/)).

**BHoM** (Buro Happold, OSS 2018): single common object model + ~50
adapters; same central-schema bet, firm-led ([bhom.xyz](https://bhom.xyz/),
[AEC Magazine](https://aecmag.com/features/bhom-addressing-the-interoperability-challenge/)).

**Hypar Elements** ("smallest useful BIM"): C# library; element types
declared as JSON schemas with code generation; serializes to JSON, IFC, glTF
([GitHub](https://github.com/hypar-io/Elements)).

## 6. Vendor granular-data strategies

**Autodesk:** Data Exchange API (user-curated granular subsets flowing
between Revit/Rhino/Inventor/Civil3D/Power BI,
[APS](https://aps.autodesk.com/apis-and-services/data-exchange-api)) and AEC
Data Model API (GraphQL over granularized Revit models; geometry access
public beta for Revit 2025+,
[APS blog](https://aps.autodesk.com/blog/access-revit-geometry-aec-data-model-public-beta)).
Critical context: RVT granularized *inside Autodesk's cloud*, rate-limited,
APS terms include a "no use by competitors" clause (§5.3) — hence bilateral
interop agreements ([Martyn Day, AEC Magazine](https://aecmag.com/technology/autodesks-granular-data-strategy/)).

**Trimble:** Trimble Connect CDE APIs; Tekla direct links; **Quadri**
(cloud object-model server for civil, bidirectional connectors) is the
closest granular-backbone analog ([Quadri](https://construction.trimble.com/en/products/quadri)).

## 7. Translation/healing middleware

**HOOPS Exchange** (Tech Soft 3D): de facto OEM import library, 30+ formats,
B-rep/PMI/tree/persistent IDs through one API; PRC native
([techsoft3d.com](https://www.techsoft3d.com/developers/products/hoops-exchange/)).
**Elysium**: CADdoctor/3DxSUITE/ASFALIS — PDQ checking + healing, 70+ checks;
frames the problem as "varying mathematical representations, topologies, and
tolerances" ([Elysium](https://www.elysium-global.com/en/solution/pdq-check-and-healing/));
CADfeature does proprietary feature remastering. **CADfix** (ITI):
translation, repair, defeaturing; stitches, rebuilds faces, collapses NURBS
to analytics ([ITI](https://www.iti-global.com/interoperability-products/cadfix/)).
**Datakit**: CrossManager/CrossCad-Ware SDK ([datakit.com](https://www.datakit.com/en/)).

**"Healing" =** re-stitching within adjusted tolerances, re-limiting/
rebuilding surfaces, simplifying to analytics, validating closure — needed
because each kernel has its own tolerance model and surface types
([CAD Interop overview](https://cadinterop.com/en/38-your-needs/311-3d-cad-data-translation-and-repair.html)).
The segment's 30-year persistence is the strongest evidence that even
evaluated-geometry exchange is unsolved.

## Flags / unverified

1. "AP242 Ed4 deployed by all major CAD vendors" — marketing snippet, no
   primary confirmation.
2. AOUSD AECO IG chairs (Angel Velez/Sean Snyders) — secondary sources only.
3. "No commercial implementation of STEP -55/-108/-111" — negative claim;
   NIST prototypes are the only implementations found.
4. Speckle 2026 funding round — Tracxn only.
5. IFC5 publication timeline — none exists publicly.
6. Datakit construction-history extraction depth — vendor marketing.
