#!/usr/bin/env python3
"""Kernel smoke test — run this FIRST on a new machine.

Isolates version-sensitive kernel API calls with exact numeric expectations,
so any cadquery/manifold3d API drift fails here with a clear message instead
of somewhere inside the demo.
"""

import math
import sys

FAILED = False


def check(cond, label):
    global FAILED
    print(("  ok    " if cond else "  FAIL  ") + label)
    FAILED = FAILED or not cond


def rel(a, b):
    return abs(a - b) / abs(b)


print("== OCCT via CadQuery (exact B-rep) ==")
try:
    from geomir.backends.occt import OCCTBackend
    k = OCCTBackend()
    check(rel(k.volume(k.box(100, 200, 50)), 1_000_000) < 1e-9,
          "box volume exact")
    check(rel(k.volume(k.cylinder(50, 100)), math.pi * 2500 * 100) < 1e-9,
          "cylinder volume = pi*r^2*h to machine precision (analytic surface)")
    # cut spans x[25,75] (fully interior), y[-50,150] (through), z[25,75]
    # -> removes exactly 50*100*50 = 250,000
    cut = k.difference(k.box(100, 100, 100),
                       k.translate(k.box(50, 200, 50), 25, -50, 25))
    check(rel(k.volume(cut), 1_000_000 - 50 * 100 * 50) < 1e-9,
          "boolean difference exact")
    ix = k.intersect(k.box(100, 100, 100),
                     k.translate(k.box(100, 100, 100), 50, 0, 0))
    check(rel(k.volume(ix), 500_000) < 1e-9, "boolean intersect exact")
    f = k.fillet(k.box(100, 100, 100), 10)
    vf = k.volume(f)
    check(0.90 < vf / 1_000_000 < 1.0, f"fillet supported (v={vf:,.0f})")
    verts, faces = k.mesh(k.box(10, 10, 10))
    check(len(verts) >= 8 and len(faces) >= 12, "tessellation works")
    bb = k.bbox(k.translate(k.box(10, 10, 10), 5, 5, 5))
    check(all(rel(x, y) < 1e-6 for x, y in zip(bb, (5, 5, 5, 15, 15, 15))),
          "bbox works")
except Exception as e:
    check(False, f"OCCT backend: {type(e).__name__}: {e}")

print("== Manifold via manifold3d (polyhedral mesh) ==")
try:
    from geomir.backends.manifold_backend import ManifoldBackend
    m = ManifoldBackend(circular_segments=64)
    check(rel(m.volume(m.box(100, 200, 50)), 1_000_000) < 1e-9,
          "box volume exact (boxes are polyhedra)")
    n = 64
    inscribed = (n / (2 * math.pi)) * math.sin(2 * math.pi / n)
    v = m.volume(m.cylinder(50, 100))
    check(rel(v, math.pi * 2500 * 100 * inscribed) < 1e-9,
          f"cylinder volume = inscribed-polygon prism "
          f"({(inscribed-1)*100:+.3f}% vs analytic — the different math)")
    cut = m.difference(m.box(100, 100, 100),
                       m.translate(m.box(50, 200, 50), 25, -50, 25))
    check(rel(m.volume(cut), 1_000_000 - 50 * 100 * 50) < 1e-9,
          "boolean difference exact")
    ix = m.intersect(m.box(100, 100, 100),
                     m.translate(m.box(100, 100, 100), 50, 0, 0))
    check(rel(m.volume(ix), 500_000) < 1e-9, "boolean intersect exact")
    try:
        m.fillet(m.box(10, 10, 10), 1)
        check(False, "fillet should be unsupported on a mesh kernel")
    except Exception:
        check(True, "fillet correctly unsupported (per-element fallback path)")
except Exception as e:
    check(False, f"Manifold backend: {type(e).__name__}: {e}")

print("== trimesh (STL export) ==")
try:
    import tempfile, os
    import trimesh
    t = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                        faces=[[0, 1, 2]], process=False)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.stl")
        t.export(p)
        check(os.path.getsize(p) > 0, "STL export works")
except Exception as e:
    check(False, f"trimesh: {type(e).__name__}: {e}")

print()
sys.exit(1 if FAILED else print("KERNEL SMOKE TEST PASSED") or 0)
