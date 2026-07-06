"""geomir.scad — lower recipe IR to OpenSCAD source, and lift it back.

Emission is a real *lowering to another CAD system's source language*, not a
mesh export: parameters stay live (OpenSCAD's customizer sees them), symbolic
expressions are emitted as expressions ("(wall_len - win_w) / 2", never a
baked 2250), and geom.repeat_x becomes a for-loop. Open the file in OpenSCAD
and drag the sliders.

Elements whose recipe uses an op OpenSCAD CSG cannot express (geom.fillet)
are lowered to `import("<baked>.stl")` — per-element partial lowering made
visible in the emitted source.

Lifting parses the emitted subset of OpenSCAD back into recipe IR. This is
source-level lifting (the honest, tractable kind); you may hand-edit
parameter values or expressions in the .scad and lift your edit back, as
long as you stay inside the subset. Elements that were baked fallbacks are
reported as unliftable — mesh -> recipe is the research-grade decompilation
problem (InverseCSG, CAD-Recode), deliberately out of scope.

$fn is emitted as a backend faceting policy, not part of the recipe — the
"-O flag" of OpenSCAD — and is ignored on lift.
"""

from __future__ import annotations

import re

from .ir import Module, Op, IRError, verify


class Unrepresentable(Exception):
    def __init__(self, opname: str):
        self.opname = opname
        super().__init__(opname)


# ===========================================================================
# Emitter
# ===========================================================================

def _num(v: float) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else repr(f)


class _Emitter:
    def __init__(self, module: Module, fallback_stl: dict[str, str],
                 fn_segments: int):
        self.m = module
        self.fallback_stl = fallback_stl  # element name -> stl filename
        self.fn = fn_segments

    # scalar expression -> OpenSCAD expression string
    def sexpr(self, o) -> str:
        if isinstance(o, (int, float)):
            return _num(o)
        if isinstance(o, str) and o.startswith("%"):
            op = self.m.op_producing(o)
            if op.name == "recipe.param":
                return op.operands[0]
            sym = {"expr.add": "+", "expr.sub": "-",
                   "expr.mul": "*", "expr.div": "/"}[op.name]
            return f"({self.sexpr(op.operands[0])} {sym} {self.sexpr(op.operands[1])})"
        raise IRError(f"cannot emit scalar {o!r}")

    def _diff_chain(self, op: Op) -> list:
        """Flatten left-nested differences: diff(diff(a,b),c) -> [a,b,c]."""
        a, b = op.operands
        if isinstance(a, str) and a.startswith("%"):
            pa = self.m.op_producing(a)
            if pa.name == "geom.difference":
                return self._diff_chain(pa) + [b]
        return [a, b]

    # solid -> statement lines
    def stmt(self, ref, ind: str) -> list[str]:
        op = self.m.op_producing(ref)
        n = op.name
        if n == "geom.box":
            v = ", ".join(self.sexpr(o) for o in op.operands)
            return [f"{ind}cube([{v}]);"]
        if n == "geom.cylinder":
            r, h = op.operands
            return [f"{ind}cylinder(h = {self.sexpr(h)}, r = {self.sexpr(r)});"]
        if n == "geom.extrude":
            prof = self.m.op_producing(op.operands[0])
            pts = ", ".join(f"[{self.sexpr(p[0])}, {self.sexpr(p[1])}]"
                            for p in prof.operands[0])
            h = self.sexpr(op.operands[1])
            return [f"{ind}linear_extrude(height = {h}) "
                    f"polygon(points = [{pts}]);"]
        if n == "geom.rotate_z":
            head = f"{ind}rotate([0, 0, {self.sexpr(op.operands[1])}])"
            return [head] + self.stmt(op.operands[0], ind + "  ")
        if n == "geom.translate":
            x, y, z = op.operands[1]
            head = (f"{ind}translate([{self.sexpr(x)}, {self.sexpr(y)}, "
                    f"{self.sexpr(z)}])")
            child = self.stmt(op.operands[0], ind + "  ")
            return [head] + child
        if n == "geom.union":
            lines = [f"{ind}union() {{"]
            for o in op.operands:
                lines += self.stmt(o, ind + "  ")
            return lines + [f"{ind}}}"]
        if n == "geom.intersect":
            lines = [f"{ind}intersection() {{"]
            for o in op.operands:
                lines += self.stmt(o, ind + "  ")
            return lines + [f"{ind}}}"]
        if n == "geom.difference":
            lines = [f"{ind}difference() {{"]
            for o in self._diff_chain(op):
                lines += self.stmt(o, ind + "  ")
            return lines + [f"{ind}}}"]
        if n == "geom.repeat_x":
            s, count, spacing = op.operands
            head = (f"{ind}for (i = [0 : {self.sexpr(count)} - 1]) "
                    f"translate([i * {self.sexpr(spacing)}, 0, 0])")
            return [head] + self.stmt(s, ind + "  ")
        if n == "geom.fillet":
            raise Unrepresentable(n)
        raise IRError(f"scad emitter: unhandled op {n}")

    def emit(self) -> str:
        L = [f"// generated by geomir from recipe.module @{self.m.name}",
             "// parameters below are live — use OpenSCAD's customizer",
             "",
             f"$fn = {self.fn};", ""]
        for name, default in self.m.params().items():
            L.append(f"{name} = {_num(default)};")
        L.append("")
        for elem, ref in self.m.exports().items():
            L.append(f"module {elem}() {{")
            try:
                L += self.stmt(ref, "  ")
            except Unrepresentable as e:
                stl = self.fallback_stl.get(elem, f"{elem}_baked.stl")
                L.append(f"  // {e.opname} is not representable in OpenSCAD CSG")
                L.append(f"  // -> per-element fallback to baked geometry")
                L.append(f'  import("{stl}");')
            L.append("}")
            L.append("")
        for elem in self.m.exports():
            L.append(f"{elem}();")
        return "\n".join(L) + "\n"


def emit_scad(module: Module, fallback_stl: dict[str, str] | None = None,
              fn_segments: int = 64) -> str:
    return _Emitter(module, fallback_stl or {}, fn_segments).emit()


# ===========================================================================
# Lifter (parses exactly the subset the emitter produces)
# ===========================================================================

_TOKEN = re.compile(r"""
    (?P<ws>\s+|//[^\n]*)
  | (?P<num>\d+\.?\d*|\.\d+)
  | (?P<id>[$A-Za-z_][A-Za-z_0-9]*)
  | (?P<str>"[^"]*")
  | (?P<sym>[{}()\[\];:,=*+\-/])
""", re.X)


def _tokenize(src: str) -> list[tuple[str, str]]:
    toks, pos = [], 0
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise IRError(f"scad lift: cannot tokenize at: {src[pos:pos+30]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind != "ws":
            toks.append((kind, m.group()))
    return toks


class _Lifter:
    def __init__(self, src: str):
        self.toks = _tokenize(src)
        self.i = 0
        self.params: dict[str, float] = {}
        self.elements: list[tuple[str, object]] = []  # (name, stmt-ast|None)
        self.warnings: list[str] = []
        self.segments: int | None = None
        self._tmp = 0
        self._ops: list[Op] = []

    # -- token helpers ---------------------------------------------------------
    def peek(self, k=0):
        return self.toks[self.i + k] if self.i + k < len(self.toks) else ("eof", "")

    def eat(self, val=None, kind=None):
        k, v = self.peek()
        if (val is not None and v != val) or (kind is not None and k != kind):
            raise IRError(f"scad lift: expected {val or kind}, got {v!r} (#{self.i})")
        self.i += 1
        return v

    # -- expression parsing (precedence climbing) -------------------------------
    def expr(self):
        node = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.eat()
            node = (op, node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek()[1] in ("*", "/"):
            op = self.eat()
            node = (op, node, self.factor())
        return node

    def factor(self):
        k, v = self.peek()
        if v == "-":
            self.eat()
            inner = self.factor()
            if inner[0] == "num":
                return ("num", -inner[1])
            return ("-", ("num", 0.0), inner)
        if v == "(":
            self.eat()
            node = self.expr()
            self.eat(")")
            return node
        if k == "num":
            self.eat()
            return ("num", float(v))
        if k == "id":
            self.eat()
            return ("ref", v)
        raise IRError(f"scad lift: bad expression token {v!r}")

    # -- statement parsing --------------------------------------------------------
    def vec3(self):
        self.eat("[")
        e1 = self.expr()
        self.eat(",")
        e2 = self.expr()
        self.eat(",")
        e3 = self.expr()
        self.eat("]")
        return [e1, e2, e3]

    def block(self):
        self.eat("{")
        stmts = []
        while self.peek()[1] != "}":
            stmts.append(self.stmt())
        self.eat("}")
        return stmts

    def stmt(self):
        k, v = self.peek()
        if v == "cube":
            self.eat(); self.eat("(")
            vec = self.vec3()
            self.eat(")"); self.eat(";")
            return ("cube", vec)
        if v == "cylinder":
            self.eat(); self.eat("(")
            self.eat("h"); self.eat("=")
            h = self.expr()
            self.eat(","); self.eat("r"); self.eat("=")
            r = self.expr()
            self.eat(")"); self.eat(";")
            return ("cylinder", r, h)
        if v == "translate":
            self.eat(); self.eat("(")
            vec = self.vec3()
            self.eat(")")
            return ("translate", vec, self.stmt())
        if v == "rotate":
            self.eat(); self.eat("(")
            vec = self.vec3()
            self.eat(")")
            if vec[0] != ("num", 0.0) or vec[1] != ("num", 0.0):
                raise IRError("scad lift: only z-axis rotation supported")
            return ("rotate_z", vec[2], self.stmt())
        if v == "linear_extrude":
            self.eat(); self.eat("(")
            self.eat("height"); self.eat("=")
            h = self.expr()
            self.eat(")")
            self.eat("polygon"); self.eat("(")
            self.eat("points"); self.eat("="); self.eat("[")
            pts = []
            while True:
                self.eat("[")
                px = self.expr(); self.eat(","); py = self.expr()
                self.eat("]")
                pts.append((px, py))
                if self.peek()[1] == ",":
                    self.eat()
                else:
                    break
            self.eat("]"); self.eat(")"); self.eat(";")
            return ("extrude", pts, h)
        if v in ("union", "difference", "intersection"):
            self.eat(); self.eat("("); self.eat(")")
            children = self.block()
            if v == "difference" and len(children) < 2:
                raise IRError("scad lift: difference needs >= 2 children")
            return (v, children)
        if v == "for":
            self.eat(); self.eat("(")
            var = self.eat(kind="id")
            self.eat("="); self.eat("[")
            start = self.expr()
            self.eat(":")
            end = self.expr()
            self.eat("]"); self.eat(")")
            return ("for", var, start, end, self.stmt())
        if v == "import":
            self.eat(); self.eat("(")
            fname = self.eat(kind="str")[1:-1]
            self.eat(")"); self.eat(";")
            return ("import", fname)
        raise IRError(f"scad lift: unexpected statement token {v!r}")

    # -- file --------------------------------------------------------------------
    def file(self):
        while self.peek()[0] != "eof":
            k, v = self.peek()
            if v == "$fn":
                self.eat(); self.eat("=")
                self.segments = int(float(self.eat(kind="num")))
                self.eat(";")
            elif v == "module":
                self.eat()
                name = self.eat(kind="id")
                self.eat("("); self.eat(")")
                body = self.block()
                if len(body) != 1:
                    raise IRError(f"scad lift: module {name} must have one root stmt")
                self.elements.append((name, body[0]))
            elif k == "id" and self.peek(1)[1] == "=":
                name = self.eat(kind="id")
                self.eat("=")
                val = self.expr()
                self.eat(";")
                if val[0] != "num":
                    raise IRError(f"scad lift: parameter {name} must be a number")
                self.params[name] = val[1]
            elif k == "id" and self.peek(1)[1] == "(":
                self.eat(); self.eat("("); self.eat(")"); self.eat(";")
            else:
                raise IRError(f"scad lift: unexpected top-level token {v!r}")

    # -- AST -> IR ------------------------------------------------------------------
    def fresh(self) -> str:
        self._tmp += 1
        return f"t{self._tmp}"

    def build_scalar(self, ast):
        """Return an IR operand ('%ref' or float) for a scalar expression."""
        kind = ast[0]
        if kind == "num":
            return ast[1]
        if kind == "ref":
            if ast[1] not in self.params:
                raise IRError(f"scad lift: unknown identifier {ast[1]!r}")
            return f"%{ast[1]}"
        opname = {"+": "expr.add", "-": "expr.sub",
                  "*": "expr.mul", "/": "expr.div"}[kind]
        a = self.build_scalar(ast[1])
        b = self.build_scalar(ast[2])
        r = self.fresh()
        self._ops.append(Op(result=r, name=opname, operands=[a, b]))
        return f"%{r}"

    def build_solid(self, ast) -> str:
        kind = ast[0]
        if kind == "cube":
            r = self.fresh()
            self._ops.append(Op(r, "geom.box",
                                [self.build_scalar(e) for e in ast[1]]))
            return f"%{r}"
        if kind == "cylinder":
            r = self.fresh()
            self._ops.append(Op(r, "geom.cylinder",
                                [self.build_scalar(ast[1]),
                                 self.build_scalar(ast[2])]))
            return f"%{r}"
        if kind == "translate":
            child = self.build_solid(ast[2])
            vec = [self.build_scalar(e) for e in ast[1]]
            r = self.fresh()
            self._ops.append(Op(r, "geom.translate", [child, vec]))
            return f"%{r}"
        if kind == "rotate_z":
            child = self.build_solid(ast[2])
            r = self.fresh()
            self._ops.append(Op(r, "geom.rotate_z",
                                [child, self.build_scalar(ast[1])]))
            return f"%{r}"
        if kind == "extrude":
            pts = [[self.build_scalar(px), self.build_scalar(py)]
                   for px, py in ast[1]]
            pr = self.fresh()
            self._ops.append(Op(pr, "profile.polygon", [pts]))
            r = self.fresh()
            self._ops.append(Op(r, "geom.extrude",
                                [f"%{pr}", self.build_scalar(ast[2])]))
            return f"%{r}"
        if kind in ("union", "intersection"):
            children = [self.build_solid(c) for c in ast[1]]
            if len(children) == 1:
                return children[0]
            r = self.fresh()
            opname = "geom.union" if kind == "union" else "geom.intersect"
            self._ops.append(Op(r, opname, children))
            return f"%{r}"
        if kind == "difference":
            acc = self.build_solid(ast[1][0])
            for c in ast[1][1:]:
                r = self.fresh()
                self._ops.append(Op(r, "geom.difference",
                                    [acc, self.build_solid(c)]))
                acc = f"%{r}"
            return acc
        if kind == "for":
            _, var, start, end, child = ast
            if start != ("num", 0.0):
                raise IRError("scad lift: for-loop must start at 0")
            # end must be <count> - 1
            if not (end[0] == "-" and end[2] == ("num", 1.0)):
                raise IRError("scad lift: for-loop end must be <count> - 1")
            count = self.build_scalar(end[1])
            if child[0] != "translate":
                raise IRError("scad lift: for body must be translate(...)")
            xe, ye, ze = child[1]
            if ye != ("num", 0.0) or ze != ("num", 0.0):
                raise IRError("scad lift: repeat translate must be x-only")
            # x must be i * spacing (either order)
            if xe[0] == "*" and xe[1] == ("ref", var):
                spacing = self.build_scalar(xe[2])
            elif xe[0] == "*" and xe[2] == ("ref", var):
                spacing = self.build_scalar(xe[1])
            else:
                raise IRError("scad lift: repeat x must be i * spacing")
            solid = self.build_solid(child[2])
            r = self.fresh()
            self._ops.append(Op(r, "geom.repeat_x", [solid, count, spacing]))
            return f"%{r}"
        if kind == "import":
            raise Unrepresentable("import")
        raise IRError(f"scad lift: unhandled AST node {kind!r}")

    def to_module(self, name: str) -> Module:
        self._ops = []
        for pname, default in self.params.items():
            self._ops.append(Op(pname, "recipe.param", [pname, default]))
        exported = 0
        for elem, ast in self.elements:
            try:
                ref = self.build_solid(ast)
                self._ops.append(Op(None, "recipe.export", [ref, elem]))
                exported += 1
            except Unrepresentable:
                self.warnings.append(
                    f"element {elem!r}: baked fallback (import of a mesh) — "
                    f"not liftable to a recipe; mesh->recipe is the "
                    f"decompilation research problem, out of scope")
        if exported == 0:
            raise IRError("scad lift: no liftable elements")
        m = Module(name=name, ops=self._ops)
        verify(m)
        return m


def lift_scad(src: str, module_name: str = "lifted"):
    """Parse (our subset of) OpenSCAD source back into a recipe Module.
    Returns (module, warnings, fn_segments)."""
    lf = _Lifter(src)
    lf.file()
    m = lf.to_module(module_name)
    return m, lf.warnings, lf.segments
