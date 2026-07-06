"""geomir.ir — the MLIR-style IR core.

This is the "recipe dialect" (D3 in the analysis report): a small SSA-form IR
with an MLIR-flavored textual format, a verifier, and a canonical printer.
It deliberately mimics MLIR's design (ops, operands, attributes, dialects,
progressive lowering) without depending on MLIR/xdsl.

Two dialects:
  recipe.*  module structure: params, exports
  expr.*    scalar symbolic expressions (the Relax "first-class symbolic
            shape" idea: relations like (wall_len - win_w)/2 are carried
            in the IR, never baked to constants)
  geom.*    solid geometry constructors and combinators

Value kinds: scalar (from recipe.param / expr.*) and solid (from geom.*).

Grammar (line-oriented):
  %id = op.name operand (, operand)*        // operands: %ref | number |
                                            //   [v, v, v] | "string"
  comments: // to end of line
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# ---------------------------------------------------------------------------
# Op registry: name -> (operand signature, result kind)
# Signatures are checked by the verifier. 's' scalar, 'g' solid,
# 'v3' vector-of-3-scalars, 'str' string literal, 'int' integer-ish scalar.
# ---------------------------------------------------------------------------

OP_SPECS: dict[str, dict] = {
    # module structure
    "recipe.param":   {"sig": ["str", "s"], "result": "scalar",
                       "doc": "named parameter with default value"},
    "recipe.export":  {"sig": ["g", "str"], "result": None, "variadic": True,
                       "doc": "export a solid as a named element; optional "
                              "third operand = element role (e.g. \"IfcWall\") "
                              "— classification metadata, never semantics"},
    # symbolic scalar expressions
    "expr.add":       {"sig": ["s", "s"], "result": "scalar"},
    "expr.sub":       {"sig": ["s", "s"], "result": "scalar"},
    "expr.mul":       {"sig": ["s", "s"], "result": "scalar"},
    "expr.div":       {"sig": ["s", "s"], "result": "scalar"},
    # 2D profiles (data, resolved at evaluation time — not kernel handles)
    "profile.polygon": {"sig": ["pts"], "result": "profile",
                        "doc": "closed 2D polygon from [[x, y], ...] (CCW, no holes yet)"},
    # solid constructors (all anchored at origin, +x/+y/+z)
    "geom.box":       {"sig": ["s", "s", "s"], "result": "solid",
                       "doc": "box(w, d, h), corner at origin"},
    "geom.cylinder":  {"sig": ["s", "s"], "result": "solid",
                       "doc": "cylinder(radius, height), base center at origin, +z axis"},
    "geom.extrude":   {"sig": ["p", "s"], "result": "solid",
                       "doc": "extrude(profile, height) along +z from z=0"},
    # combinators
    "geom.translate": {"sig": ["g", "v3"], "result": "solid"},
    "geom.rotate_z":  {"sig": ["g", "s"], "result": "solid",
                       "doc": "rotate about the +z axis through the origin, degrees CCW"},
    "geom.union":     {"sig": ["g", "g"], "result": "solid", "variadic": True},
    "geom.difference": {"sig": ["g", "g"], "result": "solid"},
    "geom.intersect": {"sig": ["g", "g"], "result": "solid", "variadic": True},
    "geom.repeat_x":  {"sig": ["g", "s", "s"], "result": "solid",
                       "doc": "repeat_x(solid, count, spacing): union of count copies"},
    # ops with restricted backend support (exercise partial lowering /
    # per-element fallback: OCCT implements fillet; Manifold does not)
    "geom.fillet":    {"sig": ["g", "s"], "result": "solid",
                       "doc": "fillet all edges with radius r (B-rep kernels only)"},
}


# ---------------------------------------------------------------------------
# IR data structures
# ---------------------------------------------------------------------------

Operand = Union[str, float, list, tuple]  # "%ref" | literal | vector | string


@dataclass
class Op:
    result: str | None          # SSA name without '%', or None (recipe.export)
    name: str                   # e.g. "geom.box"
    operands: list[Operand] = field(default_factory=list)

    def is_ref(self, i: int) -> bool:
        o = self.operands[i]
        return isinstance(o, str) and o.startswith("%")


@dataclass
class Module:
    name: str
    ops: list[Op] = field(default_factory=list)

    # -- convenience views ---------------------------------------------------
    def params(self) -> dict[str, float]:
        """name -> default value"""
        out = {}
        for op in self.ops:
            if op.name == "recipe.param":
                out[op.operands[0]] = float(op.operands[1])
        return out

    def exports(self) -> dict[str, str]:
        """element name -> SSA ref that produces it"""
        out = {}
        for op in self.ops:
            if op.name == "recipe.export":
                out[op.operands[1]] = op.operands[0]
        return out

    def roles(self) -> dict[str, str | None]:
        """element name -> role string (classification metadata) or None"""
        out = {}
        for op in self.ops:
            if op.name == "recipe.export":
                out[op.operands[1]] = (op.operands[2]
                                       if len(op.operands) > 2 else None)
        return out

    def op_producing(self, ref: str) -> Op:
        r = ref.lstrip("%")
        for op in self.ops:
            if op.result == r:
                return op
        raise KeyError(f"no op produces %{r}")


class IRError(Exception):
    pass


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _split_top_level(s: str) -> list[str]:
    """Split on commas not inside brackets or quotes."""
    parts, depth, buf, in_str = [], 0, [], False
    for ch in s:
        if ch == '"' and (not buf or buf[-1] != "\\"):
            in_str = not in_str
            buf.append(ch)
        elif in_str:
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _parse_operand(tok: str) -> Operand:
    tok = tok.strip()
    if tok.startswith("%"):
        return tok
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1]
    if tok.startswith("[") and tok.endswith("]"):
        return [_parse_operand(t) for t in _split_top_level(tok[1:-1])]
    try:
        return float(tok)
    except ValueError as e:
        raise IRError(f"cannot parse operand: {tok!r}") from e


def parse(text: str) -> Module:
    module: Module | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("//")[0].strip()
        if not line:
            continue
        if line.startswith("recipe.module"):
            name = line.split("@", 1)[1].split("{", 1)[0].strip()
            module = Module(name=name)
            continue
        if line == "}":
            continue
        if module is None:
            raise IRError(f"line {lineno}: op outside recipe.module")
        # form 1:  %res = op.name operands
        # form 2:  op.name operands            (no result, e.g. recipe.export)
        if line.startswith("%"):
            lhs, rhs = line.split("=", 1)
            result = lhs.strip().lstrip("%")
        else:
            result, rhs = None, line
        rhs = rhs.strip()
        # op name = first whitespace-delimited token
        if " " in rhs:
            opname, rest = rhs.split(" ", 1)
        else:
            opname, rest = rhs, ""
        if opname not in OP_SPECS:
            raise IRError(f"line {lineno}: unknown op {opname!r}")
        operands = [_parse_operand(t) for t in _split_top_level(rest)] if rest.strip() else []
        module.ops.append(Op(result=result, name=opname, operands=operands))
    if module is None:
        raise IRError("no recipe.module found")
    verify(module)
    return module


# ---------------------------------------------------------------------------
# Printer (canonical form; parse(print(m)) == m is tested)
# ---------------------------------------------------------------------------

def _fmt_operand(o: Operand) -> str:
    if isinstance(o, str):
        return o if o.startswith("%") else f'"{o}"'
    if isinstance(o, (list, tuple)):
        return "[" + ", ".join(_fmt_operand(x) for x in o) + "]"
    if isinstance(o, float) and o == int(o):
        return f"{o:.1f}"
    return repr(o)


def print_module(m: Module) -> str:
    lines = [f"recipe.module @{m.name} {{"]
    for op in m.ops:
        ops_s = ", ".join(_fmt_operand(o) for o in op.operands)
        if op.result is not None:
            lines.append(f"  %{op.result} = {op.name} {ops_s}".rstrip())
        else:
            lines.append(f"  {op.name} {ops_s}".rstrip())
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Verifier (MLIR-style: every op checked against its spec; SSA dominance;
# kind-correctness of operands; export integrity)
# ---------------------------------------------------------------------------

def _operand_kind(m: Module, defined: dict[str, str], o: Operand) -> str:
    """Return 's' | 'g' | 'p' | 'v2' | 'v3' | 'pts' | 'str' for an operand."""
    if isinstance(o, str) and o.startswith("%"):
        r = o.lstrip("%")
        if r not in defined:
            raise IRError(f"use of undefined value %{r}")
        return {"scalar": "s", "solid": "g", "profile": "p"}[defined[r]]
    if isinstance(o, str):
        return "str"
    if isinstance(o, (int, float)):
        return "s"
    if isinstance(o, (list, tuple)):
        if o and all(isinstance(c, (list, tuple)) for c in o):
            for c in o:
                if len(c) != 2:
                    raise IRError("point-list entries must be [x, y] pairs")
            return "pts"
        if len(o) == 3:
            return "v3"
        if len(o) == 2:
            return "v2"
        raise IRError(f"vector operand must have 2 or 3 entries, got {len(o)}")
    raise IRError(f"unclassifiable operand {o!r}")


def verify(m: Module) -> None:
    defined: dict[str, str] = {}  # ssa name -> result kind
    export_names: set[str] = set()
    for op in m.ops:
        spec = OP_SPECS[op.name]
        sig, variadic = spec["sig"], spec.get("variadic", False)
        n = len(op.operands)
        if variadic:
            if n < len(sig):
                raise IRError(f"{op.name}: expected >= {len(sig)} operands, got {n}")
            eff_sig = sig + [sig[-1]] * (n - len(sig))
        else:
            if n != len(sig):
                raise IRError(f"{op.name}: expected {len(sig)} operands, got {n}")
            eff_sig = sig
        for want, o in zip(eff_sig, op.operands):
            got = _operand_kind(m, defined, o)
            if want in ("v3", "v2"):
                if got != want:
                    raise IRError(f"{op.name}: expected {want} vector, got {got}")
                for c in o:
                    if _operand_kind(m, defined, c) != "s":
                        raise IRError(f"{op.name}: vector entries must be scalar")
            elif want == "pts":
                if got != "pts":
                    raise IRError(f"{op.name}: expected point list, got {got}")
                for pt in o:
                    for c in pt:
                        if _operand_kind(m, defined, c) != "s":
                            raise IRError(f"{op.name}: point entries must be scalar")
            elif want != got:
                raise IRError(f"{op.name}: expected operand kind {want!r}, got {got!r}")
        if op.name == "recipe.export" and len(op.operands) > 3:
            raise IRError("recipe.export takes at most (solid, name, role)")
        if op.name == "profile.polygon" and len(op.operands[0]) < 3:
            raise IRError("profile.polygon needs at least 3 points")
        if spec["result"] is not None:
            if op.result is None:
                raise IRError(f"{op.name}: must produce a result")
            if op.result in defined:
                raise IRError(f"%{op.result}: redefinition")
            defined[op.result] = spec["result"]
        elif op.result is not None:
            raise IRError(f"{op.name}: produces no result")
        if op.name == "recipe.export":
            nm = op.operands[1]
            if nm in export_names:
                raise IRError(f"duplicate export name {nm!r}")
            export_names.add(nm)
    if not export_names:
        raise IRError("module exports no elements")
