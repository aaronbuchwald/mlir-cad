"""geomir.eval — generic lowering/evaluation of a recipe Module on a backend.

This is the "progressive lowering" step: the walker resolves SSA values,
evaluates expr.* symbolically-defined scalars to concrete floats under a
parameter binding, and dispatches geom.* ops to a kernel backend.

A backend is any object with:
    box(w, d, h) -> handle
    cylinder(r, h) -> handle
    translate(handle, x, y, z) -> handle
    union(a, b) -> handle
    difference(a, b) -> handle
    fillet(handle, r) -> handle            (may raise UnsupportedOp)
    volume(handle) -> float
    bbox(handle) -> (xmin, ymin, zmin, xmax, ymax, zmax)
    mesh(handle) -> (vertices: list[[x,y,z]], faces: list[[i,j,k]])
    name: str

`evaluate` returns {element_name: handle}. Elements are evaluated
independently so that one unsupported op fails only its own element —
the unit of fallback is the element, not the file (per-element partial
lowering; see report section 6d/8).
"""

from __future__ import annotations

from .ir import Module, Op, IRError


class UnsupportedOp(Exception):
    """Raised by a backend that cannot lower an op (e.g. fillet on a mesh
    kernel). Caught per-element by the artifact import path, which then
    falls back to the baked geometry shipped alongside the recipe."""

    def __init__(self, backend: str, opname: str):
        self.backend, self.opname = backend, opname
        super().__init__(f"backend {backend!r} cannot lower {opname}")


def _scalar(env: dict, o) -> float:
    if isinstance(o, str) and o.startswith("%"):
        v = env[o.lstrip("%")]
        if not isinstance(v, (int, float)):
            raise IRError(f"{o} is not a scalar")
        return float(v)
    if isinstance(o, (int, float)):
        return float(o)
    raise IRError(f"expected scalar operand, got {o!r}")


def _solid(env: dict, o):
    if isinstance(o, str) and o.startswith("%"):
        return env[o.lstrip("%")]
    raise IRError(f"expected solid ref, got {o!r}")


def evaluate_element(module: Module, backend, export_name: str,
                     params: dict[str, float] | None = None):
    """Evaluate a single exported element. Walks only ops needed by it."""
    bindings = dict(module.params())
    if params:
        for k, v in params.items():
            if k not in bindings:
                raise IRError(f"unknown parameter {k!r}")
            bindings[k] = float(v)

    target_ref = module.exports()[export_name]

    # collect transitive deps of target_ref (backward slice)
    needed: set[str] = set()

    def mark(ref: str):
        r = ref.lstrip("%")
        if r in needed:
            return
        needed.add(r)
        op = module.op_producing(ref)
        for o in op.operands:
            if isinstance(o, str) and o.startswith("%"):
                mark(o)
            elif isinstance(o, (list, tuple)):
                for c in o:
                    if isinstance(c, str) and c.startswith("%"):
                        mark(c)

    mark(target_ref)

    env: dict[str, object] = {}
    for op in module.ops:
        if op.result is None or op.result not in needed:
            continue
        env[op.result] = _eval_op(op, env, bindings, backend)
    return env[target_ref.lstrip("%")]


def _eval_op(op: Op, env: dict, bindings: dict, backend):
    n = op.name
    if n == "recipe.param":
        return bindings[op.operands[0]]
    if n == "expr.add":
        return _scalar(env, op.operands[0]) + _scalar(env, op.operands[1])
    if n == "expr.sub":
        return _scalar(env, op.operands[0]) - _scalar(env, op.operands[1])
    if n == "expr.mul":
        return _scalar(env, op.operands[0]) * _scalar(env, op.operands[1])
    if n == "expr.div":
        return _scalar(env, op.operands[0]) / _scalar(env, op.operands[1])
    if n == "geom.box":
        w, d, h = (_scalar(env, o) for o in op.operands)
        return backend.box(w, d, h)
    if n == "geom.cylinder":
        r, h = (_scalar(env, o) for o in op.operands)
        return backend.cylinder(r, h)
    if n == "geom.translate":
        s = _solid(env, op.operands[0])
        x, y, z = (_scalar(env, c) for c in op.operands[1])
        return backend.translate(s, x, y, z)
    if n == "geom.union":
        acc = _solid(env, op.operands[0])
        for o in op.operands[1:]:
            acc = backend.union(acc, _solid(env, o))
        return acc
    if n == "geom.difference":
        return backend.difference(_solid(env, op.operands[0]),
                                  _solid(env, op.operands[1]))
    if n == "geom.repeat_x":
        s = _solid(env, op.operands[0])
        count = int(round(_scalar(env, op.operands[1])))
        spacing = _scalar(env, op.operands[2])
        if count < 1:
            raise IRError("repeat_x: count must be >= 1")
        acc = s
        for i in range(1, count):
            acc = backend.union(acc, backend.translate(s, i * spacing, 0.0, 0.0))
        return acc
    if n == "geom.fillet":
        s = _solid(env, op.operands[0])
        r = _scalar(env, op.operands[1])
        return backend.fillet(s, r)
    raise IRError(f"evaluator: unhandled op {n}")


def evaluate(module: Module, backend, params: dict[str, float] | None = None):
    """Evaluate every exported element. Returns {name: handle}.
    Raises UnsupportedOp out of this function only if the caller does not
    want per-element handling; artifact.import_artifact catches it per
    element instead."""
    return {name: evaluate_element(module, backend, name, params)
            for name in module.exports()}
