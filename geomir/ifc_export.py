"""Lower a geomir exchange artifact to IFC4 (openBIM target, Phase 1).

STATUS: UNVERIFIED BY FABLE — ifcopenshell cannot run in the build sandbox
(no PyPI). Written defensively against the stable low-level create-entity
API (not ifcopenshell.api, whose surface moves faster). First execution is
a human-checklist item (docs/VERIFICATION.md §4). Expect possible drift.

What it does — and the point of doing it this way:
- Elements whose recipe lowers to profiles + extrusions + booleans become
  REAL parametric-ish IFC: IfcExtrudedAreaSolid (rectangle/circle/polyline
  profiles) composed with IfcBooleanResult — i.e. the *shallow recipe layer
  IFC can actually carry* (report §1), not tessellation.
- Element roles ("IfcWall", "IfcColumn"...) become the entity class.
- Elements with ops IFC-CSG can't express here (fillet) fall back to the
  baked oracle mesh from the artifact as IfcPolygonalFaceSet — per-element
  degradation, visible in the file.
- Transform handling: translate/rotate_z chains are composed top-down and
  pushed into each leaf solid's Axis2Placement3D (z-rotations only, exact).

CLI:  python -m geomir.ifc_export out/studio_wall.artifact.json out/model.ifc
"""

from __future__ import annotations

import math
import sys

from .ir import Module, IRError, parse
from . import artifact as artifact_mod

DEFAULT_CLASS = "IfcBuildingElementProxy"


# --- 2D/z-only rigid transform composition ----------------------------------

class _XF:
    """rotation about +z (radians) then translation; world = R*p + t"""

    def __init__(self, theta=0.0, t=(0.0, 0.0, 0.0)):
        self.theta, self.t = theta, tuple(t)

    def then_local(self, other: "_XF") -> "_XF":
        """self ∘ other (apply other first, then self)."""
        c, s = math.cos(self.theta), math.sin(self.theta)
        ox, oy, oz = other.t
        return _XF(self.theta + other.theta,
                   (self.t[0] + c * ox - s * oy,
                    self.t[1] + s * ox + c * oy,
                    self.t[2] + oz))


def _placement(f, xf: _XF):
    loc = f.createIfcCartesianPoint([float(xf.t[0]), float(xf.t[1]),
                                     float(xf.t[2])])
    if abs(xf.theta) < 1e-12:
        return f.createIfcAxis2Placement3D(loc, None, None)
    axis = f.createIfcDirection([0.0, 0.0, 1.0])
    ref = f.createIfcDirection([math.cos(xf.theta), math.sin(xf.theta), 0.0])
    return f.createIfcAxis2Placement3D(loc, axis, ref)


# --- recipe slice -> IFC solid ----------------------------------------------

class _Lowerer:
    def __init__(self, f, module: Module, env_params: dict):
        self.f, self.m = f, module
        # resolve scalars with the artifact's parameter bindings
        from .eval import evaluate_element  # noqa: F401 (env resolution below)
        self.params = env_params

    def scalar(self, o) -> float:
        if isinstance(o, (int, float)):
            return float(o)
        op = self.m.op_producing(o)
        if op.name == "recipe.param":
            return float(self.params[op.operands[0]])
        a = self.scalar(op.operands[0])
        b = self.scalar(op.operands[1])
        return {"expr.add": a + b, "expr.sub": a - b,
                "expr.mul": a * b, "expr.div": a / b}[op.name]

    def solid(self, ref, xf: _XF):
        f, op = self.f, self.m.op_producing(ref)
        n = op.name
        if n == "geom.translate":
            x, y, z = (self.scalar(c) for c in op.operands[1])
            return self.solid(op.operands[0], xf.then_local(_XF(0.0, (x, y, z))))
        if n == "geom.rotate_z":
            th = math.radians(self.scalar(op.operands[1]))
            return self.solid(op.operands[0], xf.then_local(_XF(th)))
        if n == "geom.box":
            w, d, h = (self.scalar(c) for c in op.operands)
            # rectangle profile is centred; shift to keep corner-at-origin
            corner = xf.then_local(_XF(0.0, (w / 2.0, d / 2.0, 0.0)))
            prof = f.createIfcRectangleProfileDef("AREA", None, None, w, d)
            return f.createIfcExtrudedAreaSolid(
                prof, _placement(f, corner),
                f.createIfcDirection([0.0, 0.0, 1.0]), h)
        if n == "geom.cylinder":
            r, h = (self.scalar(c) for c in op.operands)
            prof = f.createIfcCircleProfileDef("AREA", None, None, r)
            return f.createIfcExtrudedAreaSolid(
                prof, _placement(f, xf),
                f.createIfcDirection([0.0, 0.0, 1.0]), h)
        if n == "geom.extrude":
            prof_op = self.m.op_producing(op.operands[0])
            pts = [[self.scalar(p[0]), self.scalar(p[1])]
                   for p in prof_op.operands[0]]
            pts.append(pts[0])  # close
            poly = f.createIfcPolyline(
                [f.createIfcCartesianPoint([float(x), float(y)])
                 for x, y in pts])
            prof = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
            return f.createIfcExtrudedAreaSolid(
                prof, _placement(f, xf),
                f.createIfcDirection([0.0, 0.0, 1.0]),
                self.scalar(op.operands[1]))
        if n in ("geom.union", "geom.intersect"):
            ifc_op = "UNION" if n == "geom.union" else "INTERSECTION"
            acc = self.solid(op.operands[0], xf)
            for o in op.operands[1:]:
                acc = f.createIfcBooleanResult(ifc_op, acc, self.solid(o, xf))
            return acc
        if n == "geom.difference":
            return f.createIfcBooleanResult(
                "DIFFERENCE", self.solid(op.operands[0], xf),
                self.solid(op.operands[1], xf))
        if n == "geom.repeat_x":
            count = int(round(self.scalar(op.operands[1])))
            spacing = self.scalar(op.operands[2])
            acc = self.solid(op.operands[0], xf)
            for i in range(1, count):
                acc = f.createIfcBooleanResult(
                    "UNION", acc,
                    self.solid(op.operands[0],
                               xf.then_local(_XF(0.0, (i * spacing, 0, 0)))))
            return acc
        raise IRError(f"ifc export: op {n} not expressible as IFC CSG")


def _mesh_faceset(f, mesh: dict):
    coords = f.createIfcCartesianPointList3D(
        [[float(c) for c in v] for v in mesh["vertices"]])
    return f.createIfcPolygonalFaceSet(
        coords, None,
        [f.createIfcIndexedPolygonalFace([i + 1, j + 1, k + 1])
         for i, j, k in mesh["faces"]], None)


def export_ifc(art: dict, path: str) -> list[str]:
    import ifcopenshell
    import ifcopenshell.guid as guid

    module = parse(art["ir"])
    f = ifcopenshell.file(schema="IFC4")

    # minimal spatial boilerplate ------------------------------------------------
    origin = f.createIfcAxis2Placement3D(
        f.createIfcCartesianPoint([0.0, 0.0, 0.0]), None, None)
    ctx = f.createIfcGeometricRepresentationContext(
        None, "Model", 3, 1e-5, origin, None)
    mm = f.createIfcSIUnit(None, "LENGTHUNIT", "MILLI", "METRE")
    units = f.createIfcUnitAssignment([mm])
    hist = None
    project = f.createIfcProject(guid.new(), hist, art.get("module", "geomir"),
                                 None, None, None, None, [ctx], units)
    site = f.createIfcSite(guid.new(), hist, "Site")
    bldg = f.createIfcBuilding(guid.new(), hist, "Building")
    storey = f.createIfcBuildingStorey(guid.new(), hist, "Storey")
    f.createIfcRelAggregates(guid.new(), hist, None, None, project, [site])
    f.createIfcRelAggregates(guid.new(), hist, None, None, site, [bldg])
    f.createIfcRelAggregates(guid.new(), hist, None, None, bldg, [storey])
    placement = f.createIfcLocalPlacement(None, origin)

    lower = _Lowerer(f, module, art["params"])
    notes, products = [], []
    for name, baked in art["elements"].items():
        role = baked.get("role") or DEFAULT_CLASS
        try:
            solid = lower.solid(module.exports()[name], _XF())
            rep = f.createIfcShapeRepresentation(ctx, "Body", "CSG", [solid])
            notes.append(f"{name}: parametric CSG ({role})")
        except IRError as e:
            if not baked.get("mesh"):
                notes.append(f"{name}: SKIPPED — {e} and no baked mesh")
                continue
            faceset = _mesh_faceset(f, baked["mesh"])
            rep = f.createIfcShapeRepresentation(ctx, "Body", "Tessellation",
                                                 [faceset])
            notes.append(f"{name}: baked-mesh fallback ({e})")
        shape = f.createIfcProductDefinitionShape(None, None, [rep])
        try:
            prod = f.create_entity(role, GlobalId=guid.new(), Name=name,
                                   ObjectPlacement=placement,
                                   Representation=shape)
        except Exception:
            prod = f.create_entity(DEFAULT_CLASS, GlobalId=guid.new(),
                                   Name=name, ObjectPlacement=placement,
                                   Representation=shape)
            notes.append(f"{name}: role {role!r} rejected, used proxy")
        products.append(prod)
    f.createIfcRelContainedInSpatialStructure(
        guid.new(), hist, None, None, products, storey)
    f.write(path)
    return notes


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python -m geomir.ifc_export <artifact.json> <out.ifc>")
    art = artifact_mod.load(sys.argv[1])
    for note in export_ifc(art, sys.argv[2]):
        print(" ", note)
    print(f"wrote {sys.argv[2]} — open in FreeCAD/BlenderBIM/any IFC viewer")


if __name__ == "__main__":
    main()
