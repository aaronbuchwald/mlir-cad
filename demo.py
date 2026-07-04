#!/usr/bin/env python3
"""One recipe IR, two open-source kernels with different math.

  OCCT (via CadQuery)      = FreeCAD's kernel.  Exact analytic B-rep:
                             a cylinder is a true surface, pi*r^2*h.
  Manifold (via manifold3d) = OpenSCAD's boolean engine.  Polyhedral mesh:
                             a cylinder is N flat facets.

The demo walks the architecture from the analysis report:
  Act 1  lower the recipe to OCCT, bake an exchange artifact
         (recipe + evaluated oracle per element)  -> out/model.step
  Act 2  import on Manifold: re-evaluate + match_cast against the oracle
         (LIVE / FALLBACK per element)            -> out/model_manifold.stl
  Act 3  same import with coarse faceting: the kernels' different math
         exceeds the tolerance contract -> DIVERGED, checked fallback
  Act 4  edit parameters *after* the exchange: LIVE elements regenerate,
         fallback elements are frozen (the IFC DirectShape condition)
  Act 5  lower to OpenSCAD *source* (params/expressions stay live),
         lift the source back to IR                -> out/model.scad
  Act 6  scoreboard

Run inside the venv:  python demo.py       (see setup.sh)
"""

import math
import os
import sys

from geomir import (parse, print_module, bake, save, load, import_artifact,
                    regenerate, emit_scad, lift_scad, evaluate_element)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RECIPE = os.path.join(HERE, "recipes", "studio_wall.ir")
EPS = 0.005  # match_cast contract: 0.5% relative volume


def hdr(s):
    print("\n" + "=" * 78)
    print(s)
    print("=" * 78)


def main():
    os.makedirs(OUT, exist_ok=True)

    try:
        from geomir.backends.occt import OCCTBackend
    except ImportError as e:
        sys.exit(f"cadquery not available ({e}) — run ./setup.sh and "
                 f"activate the venv first")
    try:
        from geomir.backends.manifold_backend import ManifoldBackend
    except ImportError as e:
        sys.exit(f"manifold3d not available ({e}) — run ./setup.sh and "
                 f"activate the venv first")
    import trimesh

    # ---- Act 0 ----------------------------------------------------------------
    hdr("ACT 0 — the recipe (one source of truth, still parametric)")
    with open(RECIPE) as f:
        module = parse(f.read())
    print(f"module @{module.name}: {len(module.params())} parameters, "
          f"elements: {', '.join(module.exports())}")
    print("the window position is the *relation* (wall_len - win_w)/2 — "
          "carried symbolically,\nnever baked to a constant "
          "(recipes/studio_wall.ir)")

    # ---- Act 1 ----------------------------------------------------------------
    hdr("ACT 1 — lower to OCCT (exact B-rep), bake the exchange artifact")
    occt = OCCTBackend(mesh_tolerance=0.2)
    artifact = bake(module, occt, include_mesh=True)
    art_path = os.path.join(OUT, "studio_wall.artifact.json")
    save(artifact, art_path)

    scene = None
    for name in module.exports():
        h = evaluate_element(module, occt, name)
        v = occt.volume(h)
        print(f"  {name:<12} volume = {v:>16,.1f} mm^3   (exact B-rep)")
        scene = h if scene is None else occt.union(scene, h)
    step_path = os.path.join(OUT, "model.step")
    occt.export_step(scene, step_path)
    print(f"\n  exchange artifact -> {os.path.relpath(art_path, HERE)}")
    print(f"  (recipe IR + per-element baked oracle: volume, bbox, mesh, "
          f"provenance)")
    print(f"  STEP (open in FreeCAD) -> {os.path.relpath(step_path, HERE)}")

    # pedestal fallback STL for OpenSCAD, from the baked oracle mesh
    ped = artifact["elements"]["pedestal"]["mesh"]
    ped_stl = os.path.join(OUT, "pedestal_baked.stl")
    trimesh.Trimesh(vertices=ped["vertices"], faces=ped["faces"],
                    process=False).export(ped_stl)

    # ---- Act 2 ----------------------------------------------------------------
    hdr("ACT 2 — import on Manifold (polyhedral mesh kernel), match_cast")
    mani = ManifoldBackend(circular_segments=64)
    print(f"receiving kernel re-evaluates the recipe (segments=64) and diffs "
          f"against the\nshipped oracle; contract: |Δvolume| <= "
          f"{EPS*100:.1f}%\n")
    res = import_artifact(load(art_path), mani, epsilon_rel_vol=EPS)
    print(res.table())
    print("\n  fillet needs B-rep edges; a mesh kernel has none -> that one "
          "element fell\n  back to the baked oracle; everything else stayed "
          "parametric. The unit of\n  degradation is the element, not the file.")

    meshes = []
    for name, r in res.elements.items():
        if r.live:
            verts, faces = mani.mesh(r.handle)
        else:
            verts, faces = r.baked_mesh["vertices"], r.baked_mesh["faces"]
        meshes.append(trimesh.Trimesh(vertices=verts, faces=faces,
                                      process=False))
    stl_path = os.path.join(OUT, "model_manifold.stl")
    trimesh.util.concatenate(meshes).export(stl_path)
    print(f"\n  STL (live elements + baked fallback) -> "
          f"{os.path.relpath(stl_path, HERE)}")

    # ---- Act 3 ----------------------------------------------------------------
    hdr("ACT 3 — same recipe, coarser faceting: the kernels' math visibly "
        "disagrees")
    n = 12
    factor = (n / (2 * math.pi)) * math.sin(2 * math.pi / n)
    print(f"a Manifold cylinder with N segments has volume "
          f"(N/2pi)*sin(2pi/N) * pi*r^2*h;\nN={n} -> factor {factor:.5f} "
          f"({(factor-1)*100:+.2f}% vs OCCT's exact pi*r^2*h)\n")
    res12 = import_artifact(load(art_path),
                            ManifoldBackend(circular_segments=n),
                            epsilon_rel_vol=EPS)
    print(res12.table())
    print("\n  the tolerance contract caught the divergence and fell back to "
          "the baked\n  oracle — a checked, per-element degradation instead of "
          "a silent wrong model.\n  (faceting policy is the receiving kernel's "
          "'-ffast-math'; the contract is\n  what makes cross-kernel recipes "
          "trustworthy.)")

    # ---- Act 4 ----------------------------------------------------------------
    hdr("ACT 4 — edit parameters AFTER the exchange (what IFC import cannot do)")
    edits = {"win_w": 2200.0, "col_n": 5.0}
    print(f"edits on the receiving side: {edits}\n")
    regen = regenerate(res, mani, edits)
    w = max(len(k) for k in regen) + 2
    for name, (old, new, note) in regen.items():
        if new is not None:
            print(f"  {name:<{w}} {old:>16,.0f} -> {new:>16,.0f} mm^3   {note}")
        else:
            print(f"  {name:<{w}} {old:>16,.0f} -> {'—':>16}        {note}")
    print("\n  window widened and stayed centered ((wall_len - win_w)/2 "
          "recomputed);\n  colonnade grew to 5 columns (repeat_x). The recipe "
          "survived the kernel\n  boundary; only the fallback element is "
          "frozen — in an IFC round-trip,\n  EVERY element is the frozen one.")

    # ---- Act 5 ----------------------------------------------------------------
    hdr("ACT 5 — lower to OpenSCAD source; lift the source back")
    scad_text = emit_scad(module,
                          fallback_stl={"pedestal": "pedestal_baked.stl"},
                          fn_segments=64)
    scad_path = os.path.join(OUT, "model.scad")
    with open(scad_path, "w") as f:
        f.write(scad_text)
    print(f"  OpenSCAD source -> {os.path.relpath(scad_path, HERE)}   "
          f"(open it: params are live sliders,\n  the window x is emitted as "
          f"the expression (wall_len - win_w) / 2, and the\n  pedestal is an "
          f"import() of baked geometry — partial lowering in plain sight)\n")

    lifted, warnings, _ = lift_scad(scad_text, module_name="studio_wall")
    for wmsg in warnings:
        print(f"  lift warning: {wmsg}")
    ir_path = os.path.join(OUT, "lifted.ir")
    with open(ir_path, "w") as f:
        f.write(print_module(lifted))
    ok = True
    for name in lifted.exports():
        v_orig = res.elements[name].volume_new
        v_lift = mani.volume(evaluate_element(lifted, mani, name))
        ok &= abs(v_lift - v_orig) / v_orig < 1e-9
    print(f"\n  lifted {len(lifted.exports())}/3 elements back to recipe IR "
          f"-> {os.path.relpath(ir_path, HERE)}")
    print(f"  lifted recipe re-evaluates to identical volumes on Manifold: "
          f"{'PASS' if ok else 'FAIL'}")
    print("  (the baked pedestal is honestly unliftable: mesh -> recipe is "
          "decompilation,\n  the research-grade problem — InverseCSG, "
          "CAD-Recode)")

    # ---- Act 6 ----------------------------------------------------------------
    hdr("ACT 6 — scoreboard: what this demonstrated")
    for line in [
        "1. one recipe IR lowered to two kernels with different underlying math",
        "   (OCCT analytic B-rep vs Manifold polyhedral mesh)",
        "2. exchange artifact = cross-level carrier: parametric recipe + baked",
        "   oracle per element, with provenance (the Relax cross-level idea)",
        "3. match_cast on import: re-evaluate, diff vs oracle, LIVE within the",
        "   contract / checked FALLBACK on unsupported ops or divergence",
        "4. symbolic relations never baked: post-exchange parameter edits",
        "   regenerate correctly on the foreign kernel (IFC cannot do this)",
        "5. lowering to another system's SOURCE language (OpenSCAD) with live",
        "   parameters, and source-level lifting back — with the decompilation",
        "   boundary made explicit",
    ]:
        print("  " + line)
    print("\nartifacts in out/: model.step (FreeCAD), model.scad (OpenSCAD), "
          "model_manifold.stl,\nstudio_wall.artifact.json, lifted.ir, "
          "pedestal_baked.stl")


if __name__ == "__main__":
    main()
