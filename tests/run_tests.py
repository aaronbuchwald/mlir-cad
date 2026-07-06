"""Pure-Python test suite (no compiled kernels needed).

Runs everywhere — including environments without cadquery/manifold3d — by
using the sampler backend (point-membership classification) as the kernel.
Kernel-specific behavior is covered separately by smoke_kernels.py.

Run:  python tests/run_tests.py
"""

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import geomir  # noqa: E402
from geomir import (parse, print_module, evaluate, evaluate_element,  # noqa: E402
                    bake, save, load, import_artifact, regenerate,
                    emit_scad, lift_scad, IRError,
                    LIVE, FALLBACK, DIVERGED)
from geomir.backends.sampler import SamplerBackend  # noqa: E402

RECIPE = os.path.join(os.path.dirname(__file__), "..", "recipes",
                      "studio_wall.ir")

PASS = 0


def check(cond, label):
    global PASS
    if not cond:
        print(f"  FAIL  {label}")
        sys.exit(1)
    PASS += 1
    print(f"  ok    {label}")


def close(a, b, rel, label):
    d = abs(a - b) / abs(b)
    check(d <= rel, f"{label}  ({a:,.0f} vs {b:,.0f}, Δ={d*100:.2f}% <= {rel*100:.1f}%)")


def module_text():
    with open(RECIPE) as f:
        return f.read()


# a fillet-free variant used where all three elements must evaluate on
# non-B-rep backends (scad round-trip fixed point, full-live imports)
def parametric_only(text):
    out = []
    for line in text.splitlines():
        if "fillet" in line and "recipe.param" not in line:
            # %ped1 = geom.fillet %ped0, %fillet_r  ->  pass-through
            if "geom.fillet" in line:
                lhs = line.split("=")[0].strip()
                src = line.split("=")[1].strip().split(" ")[1].rstrip(",")
                out.append(f"  {lhs} = geom.union {src}, {src}")
                continue
        out.append(line)
    return "\n".join(out)


print("== IR core ==")
m = parse(module_text())
check(m.name == "studio_wall", "module parses")
check(set(m.exports()) == {"wall", "colonnade", "pedestal"}, "exports found")
check(len(m.params()) == 14, "params found")

# canonical print -> parse -> print fixed point
p1 = print_module(m)
p2 = print_module(parse(p1))
check(p1 == p2, "print/parse fixed point")

# verifier catches errors
for bad, why in [
    ("recipe.module @x {\n  %a = geom.box 1.0, 2.0\n  recipe.export %a, \"e\"\n}",
     "wrong operand count"),
    ("recipe.module @x {\n  %a = geom.box 1.0, 2.0, %nope\n  recipe.export %a, \"e\"\n}",
     "undefined value"),
    ("recipe.module @x {\n  %a = recipe.param \"p\", 1.0\n  recipe.export %a, \"e\"\n}",
     "scalar exported as solid"),
]:
    try:
        parse(bad)
        check(False, f"verifier rejects: {why}")
    except IRError:
        check(True, f"verifier rejects: {why}")

print("== sampler evaluation vs closed form ==")
S = SamplerBackend(budget=2_000_000)
mp = parse(parametric_only(module_text()))
elems = evaluate(mp, S)

v_wall = S.volume(elems["wall"])
wall_exact = 6000*300*3000 - 1500*300*1200 - 900*300*2100
close(v_wall, wall_exact, 0.02, "wall volume (box minus window minus door)")

v_cols = S.volume(elems["colonnade"])
cols_exact = 3 * math.pi * 150**2 * 2800
close(v_cols, cols_exact, 0.02, "colonnade volume (3x cylinder)")

v_ped = S.volume(elems["pedestal"])
close(v_ped, 800*800*450, 0.02, "pedestal volume (fillet-free variant)")

# symbolic relation actually recomputes: widen wall, window stays centered
h1 = evaluate_element(mp, S, "wall", {"wall_len": 8000.0})
close(S.volume(h1), 8000*300*3000 - 1500*300*1200 - 900*300*2100, 0.02,
      "parameter edit recomputes symbolic relation")

print("== artifact bake / match_cast import ==")
art = bake(mp, S, include_mesh=False)
with tempfile.TemporaryDirectory() as td:
    path = os.path.join(td, "a.json")
    save(art, path)
    art2 = load(path)
res = import_artifact(art2, SamplerBackend(budget=2_000_000))
check(all(r.status == LIVE for r in res.elements.values()),
      "same-kernel import: all elements LIVE")

# fillet recipe on a fillet-less kernel -> per-element FALLBACK, others LIVE
art_f = dict(art)
art_f["ir"] = print_module(m)  # original recipe WITH fillet
res_f = import_artifact(art_f, SamplerBackend(budget=2_000_000))
check(res_f.elements["pedestal"].status == FALLBACK,
      "unsupported op -> FALLBACK on that element only")
check(res_f.elements["wall"].status == LIVE and
      res_f.elements["colonnade"].status == LIVE,
      "other elements stay LIVE")

# synthetic kernel divergence -> DIVERGED (tolerance contract catches it)
art_d = dict(art)
art_d["elements"] = {k: dict(v) for k, v in art["elements"].items()}
art_d["elements"]["colonnade"]["volume"] *= 1.045   # pretend baked kernel ran fat
res_d = import_artifact(art_d, SamplerBackend(budget=2_000_000))
check(res_d.elements["colonnade"].status == DIVERGED,
      "4.5% volume divergence -> DIVERGED")
check(res_d.elements["wall"].status == LIVE, "divergence is per-element")

# post-import parameter edit: LIVE regenerates, fallback stays frozen
regen = regenerate(res_f, SamplerBackend(budget=2_000_000),
                   {"win_w": 2200.0})
old_w, new_w, note_w = regen["wall"]
check(new_w is not None and new_w < old_w, "LIVE element regenerated (smaller wall)")
_, new_p, note_p = regen["pedestal"]
check(new_p is None and "FROZEN" in note_p, "fallback element frozen (the IFC condition)")

print("== geom.intersect (op added via the CLAUDE.md checklist) ==")
IX = """recipe.module @ix {
  %a = geom.box 100.0, 100.0, 100.0
  %b0 = geom.box 100.0, 100.0, 100.0
  %b = geom.translate %b0, [50.0, 0.0, 0.0]
  %i = geom.intersect %a, %b
  recipe.export %i, "e"
}"""
mi = parse(IX)
close(S.volume(evaluate_element(mi, S, "e")), 500_000, 0.02,
      "intersect volume (two offset boxes)")
scad_i = emit_scad(mi)
check("intersection() {" in scad_i, "intersect lowers to OpenSCAD intersection()")
lift_i, warn_i, _ = lift_scad(scad_i)
close(S.volume(evaluate_element(lift_i, S, "e")), 500_000, 0.02,
      "intersect survives scad round trip")

print("== OpenSCAD emit / lift round trip ==")
scad1 = emit_scad(m, fallback_stl={"pedestal": "pedestal_baked.stl"})
check('import("pedestal_baked.stl")' in scad1,
      "unrepresentable element lowers to baked import in .scad")
check("(wall_len - win_w)" in scad1.replace("  ", " "),
      "symbolic expression survives into .scad source")
check("for (i = [0 : col_n - 1])" in scad1, "repeat_x lowers to a live for-loop")

lifted, warnings, segs = lift_scad(scad1)
check(len(warnings) == 1 and "pedestal" in warnings[0],
      "lift flags baked element as unliftable (decompilation boundary)")
check(set(lifted.exports()) == {"wall", "colonnade"}, "parametric elements lifted")
check(lifted.params() == m.params(), "parameters survive round trip")

# lifted recipe evaluates to the same geometry
lw = evaluate_element(lifted, S, "wall")
close(S.volume(lw), wall_exact, 0.02, "lifted wall volume matches")
lc = evaluate_element(lifted, S, "colonnade")
close(S.volume(lc), cols_exact, 0.02, "lifted colonnade volume matches")

# emit(lift(emit)) textual fixed point on the fully-parametric recipe
scad_p1 = emit_scad(mp)
lift_p, warn_p, _ = lift_scad(scad_p1)
check(not warn_p, "fully-parametric recipe lifts with no warnings")
scad_p2 = emit_scad(lift_p)
check(scad_p1.split("\n", 1)[1] == scad_p2.split("\n", 1)[1],
      "emit -> lift -> emit textual fixed point (module name aside)")

# hand-edit simulation: user changes a parameter value in the .scad text
edited = scad_p1.replace("win_w = 1500;", "win_w = 2000;")
lift_e, _, _ = lift_scad(edited)
check(lift_e.params()["win_w"] == 2000.0, "hand-edited .scad param lifts back")

print(f"\nALL {PASS} CHECKS PASSED")
