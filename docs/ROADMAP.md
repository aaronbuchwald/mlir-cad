# ROADMAP — geomir: from demo to industry harness

Assumption: the workforce is **Claude (Fable 5)** doing design, code, tests, docs, and
research autonomously; humans appear only where the world requires a body, a license, a
credential, or a judgment call. Wall-clock time is therefore dominated by **human
checkpoints (HC)**, not engineering.

Legend: `[F]` Fable-autonomous · `[HC-n]` human checkpoint (blocking) · `[H~]` human
lightweight (minutes, async).

---

## Phase 0 — Harness core (THIS SESSION)

Goal: make "add a target" a checklist executed by an agent, verified by machinery.

- [F] `geom.intersect` op across dialect/backends/scad/tests (proves the add-an-op
  path; `geom.cone` left as course Lab 4 — rotate_z was implemented in Phase 1).
- [F] **Conformance harness** (`conformance/`): graded corpus (L0 primitives → L4
  pathological tangencies) with closed-form invariants; per-op smoke stage; match_cast
  conformance stage; report card (JSON + text); **auto-generated capability manifests**
  from observed behavior (Relax "analysis feedback": measure support, don't declare it).
- [F] **Random recipe generator + differential mode**: grammar-directed, seeded;
  pairwise backend comparison; findings log. This is the Csmith-for-kernels seed.
- [F] `add-geomir-target` **skill** (`.claude/skills/`): the onboarding playbook with
  hard gates, including the Tekla mapping appendix.
- [F] CI workflow (pure-Python job always; kernel job on ubuntu; commented stanzas for
  license-gated tiers).
- [H~] **HC-0**: run `python tests/run_tests.py && python -m conformance.run --backend occt
  --backend manifold` on the Mac (kernels can't execute in Fable's sandbox) and paste
  the report card back. ~5 minutes.

Exit criteria: three existing backends pass conformance; manifests committed; a new
backend can be onboarded by following the skill with zero tribal knowledge.

## Phase 1 — Dialect v2 + open targets (Fable-days; no licenses)

- [F] Profile sub-dialect: closed 2D profiles (polyline/arc segments, holes), parametric
  dimensions. Constraints deferred (see Phase 4).
- [F] `extrude(profile)`, `revolve`, `sweep(path)`, frames (`rotate_z`, `mirror`),
  `pattern_polar`, `tabulate` (index-parameterized arrays for varying façades).
- [F] Validation v2: surface area, Hausdorff on tessellations (trimesh), sampler as
  neutral **referee** for 2-kernel disagreements; per-op-class ε in manifests.
- [F] **IFC target** via IfcOpenShell (pip-installable): emit recipe →
  `IfcExtrudedAreaSolid` + booleans + element-role classification; **lift** the shallow
  recipe IFC already carries. Makes geomir an IFC round-trip improver — first externally
  legible value.
- [F] FreeCAD script emitter (Python source form; OCCT semantics already covered).
- [F] Element-role annotation layer (classification metadata, never semantic ops —
  the Speckle v2→v3 lesson).
- [H~] **HC-1**: local runs + eyeball IFC output in a viewer (BlenderBIM/FreeCAD).
- [HC-2] **ε contract calibration sign-off**: tolerance classes per op family are an
  engineering judgment with downstream legal/QA weight in AEC deliverables. Fable
  proposes numbers from differential data; a human owns the decision.

## Phase 2 — First proprietary targets, cloud-testable (Fable-days + HC-weeks)

- [HC-3] **Onshape**: human creates account, generates API keys, accepts ToS. (Free tier
  exists; check current API rate limits.)
- [F] Onshape backend: REST evaluation + **FeatureScript emitter** (lowering to a real
  parametric CAD's source language — second source-form target after OpenSCAD) + lift
  from API feature lists. Fully CI-able once keys exist.
- [HC-4] **Secrets into CI** (GitHub Actions): human pastes keys; reviews spend caps.
- [F] Grasshopper emitter (.ghx XML): recipe → GH definition; testable headlessly only
  via Rhino.Compute → [HC-5] Rhino license decision (defer if needed; GH files still
  openable by any Rhino user without our testing them in CI).
- [F] Differential campaign v1 across occt/manifold/sampler/onshape: first findings
  report. [H~] **HC-6**: triage findings — deciding whether a divergence is "interesting,
  file upstream" is a human call (vendor relations, disclosure etiquette).

## Phase 3 — Desktop BIM targets (license-gated; the real HC wall)

- [HC-7] **Tekla Structures**: human acquires license (or Trimble partner/dev program),
  provisions a Windows VM or self-hosted CI runner, installs Tekla + .NET toolchain,
  first-run GUI activation. *Nothing here is automatable; this is THE bottleneck.*
- [F] Tekla connector (C#, Tekla Open API): lowering map — extrusion→Beam/PolyBeam/
  ContourPlate with profile strings, `difference`→BooleanPart, patterns→arrays;
  **lift** — parts expose profile + cuts via API (Tekla's native rep is closest of any
  proprietary tool to geomir's dialect). Fable writes 100% of the code; human executes
  install-time steps and runs the conformance card locally until the runner exists.
- [HC-8] **Autodesk**: account + APS **Design Automation** setup for headless Revit in
  CI; **legal review of APS ToS** (incl. competitor clauses) *before* building anything
  commercial on it; spend approval (DA is metered).
- [F] Revit connector via Design Automation: recipe → native walls/floors/openings with
  element roles; joins applied by Revit's own runtime post-placement, divergence
  measured by contract, flagged not hidden.
- [HC-9] Plugin signing certificates (Revit add-in, Tekla) if distributed to others.
- Exit: the skill's promise holds — "add target" = Fable-days of code + human-days of
  license/provisioning, gated by the same runner.

## Phase 4 — Research spine (parallel, ongoing)

- [F] Differential fuzzing at scale (Tier 0/1 nightly; publishable findings corpus —
  the "empirical kernel semantics spec"). [H~] HC-6 recurs per disclosure.
- [F] E-graph canonicalization pass over the recipe dialect (Szalinski-style): re-idiomize
  constructions per target before emission; capability-aware extraction (cost=∞ for
  unsupported ops) so fallback-to-baked becomes last resort after semantic search.
- [F] Lifting v0: extrusion/pattern recognition from STEP/OCCT B-rep (classical feature
  recognition before ML); then CAD-Recode-style model-assisted lifting behind the same
  match_cast verification gate.
- [F] Sketch-constraint dialect design (the D-Cubed-shaped hole) — research doc first;
  solver choice (write vs license) is [HC-10] a build-vs-buy + budget decision.

## Phase 5 — Meaning it (pilots, positioning)

- [HC-11] **Real project data**: a pilot needs actual models (often confidential).
  Human sources them, owns data governance/NDAs.
- [HC-12] **Beachhead choice** (strategy, human-owned): computational-design→documentation
  handoff (GH/code-CAD → Revit/Tekla native) vs steel detailing vs IFC-improver tooling
  vs AI-verification infrastructure. Fable can build all; someone must choose what to
  sell/publish first.
- [HC-13] Licensing/visibility of this repo (open-source license choice, private→public),
  paper/post authorship decisions.

---

## Standing human checkpoints (summary table)

| HC | What | Why a human |
|---|---|---|
| 0,1 | Run kernel tests locally, paste report | Fable's sandbox has no PyPI/kernels |
| 2 | ε tolerance sign-off | Engineering judgment with QA/legal weight |
| 3,4,5,7,8,9 | Accounts, licenses, installs, secrets, certs, VMs | Bodies, money, ToS acceptance |
| 6 | Differential-finding triage/disclosure | Vendor relations, etiquette |
| 10 | Constraint-solver build-vs-buy | Budget |
| 11 | Pilot data + NDAs | Confidentiality, governance |
| 12,13 | Beachhead, licensing, publication | Strategy and ownership |

Everything not listed above is assumed Fable-autonomous, including all code, tests,
docs, corpus growth, connector logic, research surveys, and this roadmap's maintenance.

## Current status ledger (updated 2026-07-06, second build pass)

- Phase 0: **done** (conformance harness, fuzzer, manifests, skill, CI,
  geom.intersect). HC-0 pending: kernel-backed conformance run on the Mac.
- Phase 1: **partial — license-free slice done**:
  - done [F]: `geom.rotate_z`, `profile.polygon` + `geom.extrude` (new
    'profile' value kind), element roles on `recipe.export` (classification,
    not semantics), validation v2 (mesh area + sampled Hausdorff,
    `import_artifact(deep=True)`), FreeCAD macro emitter (ast-verified),
    IFC4 CSG exporter with per-element baked-mesh fallback (**UNVERIFIED**
    until first ifcopenshell run — VERIFICATION §2), fuzzer/corpus/smoke
    coverage for all new ops, interactive walkthrough
    (`courses/04-two-kernels-live.html`), `docs/VERIFICATION.md`.
  - deferred [F]: revolve/sweep/loft, `tabulate` (index-parameterized
    arrays), polar patterns, profiles with holes/arcs, IFC *lift*
    (import IFC's shallow recipes back to geomir), Grasshopper emitter.
  - human gates unchanged: HC-1 (eyeball IFC in a viewer), HC-2 (ε sign-off).
- Phases 2–5: not started (first wall: HC-3 Onshape keys).
