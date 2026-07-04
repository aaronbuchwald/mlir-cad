"""geomir.artifact — the exchange artifact and the match_cast contract.

The artifact is the cross-level exchange unit (report section 6a/8): it
carries the *recipe* (high dialect, still parametric) AND the *baked*
evaluated geometry (low dialect: volume, bbox, optional mesh) per element,
with provenance (which kernel baked it, at what mesh tolerance).

Import = the Relax `match_cast` pattern (report 6c): the receiving kernel
re-evaluates the recipe with the artifact's parameter bindings and diffs
its own result against the shipped baked oracle.

    reproduces within epsilon  -> LIVE      (element stays parametric)
    op unsupported by kernel   -> FALLBACK  (use baked geometry, flagged)
    reproduces but diverges    -> DIVERGED  (use baked geometry, flagged)

The unit of degradation is the element, never the file. A LIVE element can
be re-generated under *new* parameters after import — the exact capability
IFC's DirectShape import loses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .ir import Module, parse, print_module
from .eval import evaluate_element, UnsupportedOp

SCHEMA = "geomir-artifact/0.1"

LIVE = "LIVE"
FALLBACK = "FALLBACK (op unsupported)"
DIVERGED = "DIVERGED (fell back to baked)"
ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Bake (export side)
# ---------------------------------------------------------------------------

def bake(module: Module, backend, params: dict[str, float] | None = None,
         include_mesh: bool = True) -> dict:
    bindings = dict(module.params())
    if params:
        bindings.update(params)
    elements = {}
    for name in module.exports():
        handle = evaluate_element(module, backend, name, bindings)
        mesh = backend.mesh(handle) if include_mesh else None
        elements[name] = {
            "volume": backend.volume(handle),
            "bbox": list(backend.bbox(handle)),
            "mesh": ({"vertices": mesh[0], "faces": mesh[1]}
                     if mesh is not None else None),
        }
    return {
        "schema": SCHEMA,
        "module": module.name,
        "ir": print_module(module),
        "params": bindings,
        "baked_by": backend.name,
        "mesh_tolerance": getattr(backend, "mesh_tolerance", None),
        "elements": elements,
    }


def save(artifact: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(artifact, f)


def load(path: str) -> dict:
    with open(path) as f:
        a = json.load(f)
    if a.get("schema") != SCHEMA:
        raise ValueError(f"not a geomir artifact: {path}")
    return a


# ---------------------------------------------------------------------------
# Import + match_cast (receive side)
# ---------------------------------------------------------------------------

@dataclass
class ElementResult:
    name: str
    status: str
    live: bool
    handle: object | None          # kernel handle if LIVE (or best-effort)
    baked_mesh: dict | None        # mesh dict if fallback path is taken
    volume_new: float | None
    volume_baked: float
    rel_vol_diff: float | None
    detail: str = ""


@dataclass
class ImportResult:
    module: Module
    params: dict[str, float]
    backend_name: str
    epsilon: float
    elements: dict[str, ElementResult] = field(default_factory=dict)

    def table(self) -> str:
        w = max(len(n) for n in self.elements) + 2
        lines = [f"{'element':<{w}} {'status':<34} {'vol(baked)':>14} "
                 f"{'vol(re-eval)':>14} {'Δvol':>9}"]
        for r in self.elements.values():
            vn = f"{r.volume_new:,.0f}" if r.volume_new is not None else "—"
            dv = f"{r.rel_vol_diff * 100:+.3f}%" if r.rel_vol_diff is not None else "—"
            lines.append(f"{r.name:<{w}} {r.status:<34} {r.volume_baked:>14,.0f} "
                         f"{vn:>14} {dv:>9}")
        return "\n".join(lines)


def _bbox_ok(a, b, tol: float) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def import_artifact(artifact: dict, backend,
                    epsilon_rel_vol: float = 0.005,
                    bbox_tol: float = 1.0) -> ImportResult:
    """Re-evaluate the shipped recipe on `backend` and match_cast each
    element against the shipped baked oracle."""
    module = parse(artifact["ir"])
    params = dict(artifact["params"])
    result = ImportResult(module=module, params=params,
                          backend_name=backend.name, epsilon=epsilon_rel_vol)

    for name, baked in artifact["elements"].items():
        v0 = baked["volume"]
        try:
            handle = evaluate_element(module, backend, name, params)
            v1 = backend.volume(handle)
            rel = abs(v1 - v0) / abs(v0) if v0 else abs(v1)
            bb_ok = _bbox_ok(backend.bbox(handle), baked["bbox"], bbox_tol)
            if rel <= epsilon_rel_vol and bb_ok:
                result.elements[name] = ElementResult(
                    name, LIVE, True, handle, None, v1, v0, rel,
                    "recipe reproduced within tolerance contract")
            else:
                why = (f"volume diverged {rel * 100:.3f}% > "
                       f"{epsilon_rel_vol * 100:.2f}%") if rel > epsilon_rel_vol \
                    else f"bbox diverged beyond {bbox_tol}"
                result.elements[name] = ElementResult(
                    name, DIVERGED, False, handle, baked.get("mesh"),
                    v1, v0, rel, why)
        except UnsupportedOp as e:
            result.elements[name] = ElementResult(
                name, FALLBACK, False, None, baked.get("mesh"),
                None, v0, None, str(e))
        except Exception as e:  # kernel failure = also a fallback, flagged
            result.elements[name] = ElementResult(
                name, ERROR, False, None, baked.get("mesh"),
                None, v0, None, f"{type(e).__name__}: {e}")
    return result


def regenerate(result: ImportResult, backend,
               new_params: dict[str, float]) -> dict[str, tuple]:
    """Post-import parameter edit: regenerate LIVE elements under new
    parameter bindings. Fallback elements cannot update — they are frozen
    baked geometry, which is precisely the IFC/DirectShape condition.
    Returns {element: (old_volume, new_volume | None, note)}."""
    params = dict(result.params)
    params.update(new_params)
    out = {}
    for name, r in result.elements.items():
        if r.live:
            handle = evaluate_element(result.module, backend, name, params)
            out[name] = (r.volume_new, backend.volume(handle),
                         "regenerated from recipe")
        else:
            out[name] = (r.volume_baked, None,
                         "FROZEN — baked geometry cannot re-parameterize")
    return out
