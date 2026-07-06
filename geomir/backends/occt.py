"""OCCT backend via CadQuery — exact analytic B-rep.

This is FreeCAD's math: Open CASCADE Technology. A cylinder here is a true
analytic surface (radius is exact, volume integrates to pi*r^2*h to machine
precision); booleans run surface-surface intersection with OCCT's per-shape
tolerance model. Compare backends/manifold_backend.py, where a cylinder is
N flat facets. Same recipe IR lowers to both; the demo measures the gap.

API notes: written against CadQuery 2.x. Anything version-sensitive is
isolated in the small helpers at the bottom; if smoke_kernels.py fails,
look there first.
"""

from __future__ import annotations

import cadquery as cq


class OCCTBackend:
    name = "occt"

    def __init__(self, mesh_tolerance: float = 0.2):
        # tessellation tolerance (mm) used only when baking oracle meshes;
        # the model itself stays exact B-rep
        self.mesh_tolerance = mesh_tolerance

    # -- constructors --------------------------------------------------------
    def box(self, w, d, h):
        # corner at origin, extending +x/+y/+z (matches geom.box semantics)
        return cq.Workplane("XY").box(w, d, h, centered=(False, False, False))

    def cylinder(self, r, h):
        # base-center at origin, axis +z (CadQuery: height first, then radius)
        return cq.Workplane("XY").cylinder(h, r, centered=(True, True, False))

    # -- combinators ----------------------------------------------------------
    def translate(self, s, x, y, z):
        return s.translate(cq.Vector(x, y, z))

    def union(self, a, b):
        return a.union(b)

    def difference(self, a, b):
        return a.cut(b)

    def intersect(self, a, b):
        return a.intersect(b)

    def fillet(self, s, r):
        # B-rep kernels support edge fillets; mesh/implicit backends do not.
        return s.edges().fillet(r)

    # -- queries ---------------------------------------------------------------
    def volume(self, s) -> float:
        return _volume(_shape(s))

    def bbox(self, s):
        bb = _shape(s).BoundingBox()
        return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)

    def mesh(self, s):
        verts, tris = _shape(s).tessellate(self.mesh_tolerance)
        return ([[float(v.x), float(v.y), float(v.z)] for v in verts],
                [[int(t[0]), int(t[1]), int(t[2])] for t in tris])

    # -- export ----------------------------------------------------------------
    def export_step(self, s, path: str):
        cq.exporters.export(s, path)


# --- version-tolerant helpers -------------------------------------------------

def _shape(s):
    """Accept a Workplane or a Shape; return the underlying Shape."""
    if hasattr(s, "val"):
        v = s.val()
        return v
    return s


def _volume(shape) -> float:
    v = getattr(shape, "Volume")
    return float(v()) if callable(v) else float(v)
