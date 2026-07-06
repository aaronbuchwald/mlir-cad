"""Backend registry + tolerance contracts.

New targets: add one entry to BACKENDS (+ optional TOLERANCES override) and run
`python -m conformance.run --backend <name>`. The runner measures actual op
support and writes the capability manifest — declarations are not trusted
(Relax "analysis feedback": measure, don't annotate).
"""

from __future__ import annotations

import importlib

# name -> (module, class, kwargs, access_route)
BACKENDS: dict[str, tuple[str, str, dict, str]] = {
    "sampler": ("geomir.backends.sampler", "SamplerBackend", {}, "in-process (pure numpy)"),
    "occt": ("geomir.backends.occt", "OCCTBackend", {}, "in-process (cadquery/OCP)"),
    "manifold": ("geomir.backends.manifold_backend", "ManifoldBackend",
                 {"circular_segments": 64}, "in-process (manifold3d)"),
    "manifold12": ("geomir.backends.manifold_backend", "ManifoldBackend",
                   {"circular_segments": 12}, "in-process (manifold3d, coarse faceting)"),
    "sampler_coarse": ("geomir.backends.sampler", "SamplerBackend",
                       {"budget": 300_000}, "in-process (pure numpy, low budget)"),
    # Future targets (see docs/ROADMAP.md and .claude/skills/add-geomir-target):
    # "ifc":     via IfcOpenShell           [Phase 1, no license]
    # "onshape": REST + FeatureScript       [Phase 2, HC-3: account + API keys]
    # "tekla":   Tekla Open API connector   [Phase 3, HC-7: license + Windows runner]
    # "revit":   APS Design Automation      [Phase 3, HC-8: account + ToS review]
}

# relative-volume tolerance per (backend, class). "exact": prismatic/boolean
# content only; "curved": contains faceted-vs-analytic geometry.
TOLERANCES: dict[str, dict[str, float]] = {
    "sampler": {"exact": 0.02, "curved": 0.02},      # sampling estimator noise
    "occt": {"exact": 1e-7, "curved": 1e-7},          # analytic B-rep
    "manifold": {"exact": 1e-9, "curved": 0.005},     # polyhedra exact; 64-seg -0.16%
    "manifold12": {"exact": 1e-9, "curved": 0.05},    # 12-seg -4.5%
    "sampler_coarse": {"exact": 0.05, "curved": 0.05},
}
DEFAULT_TOLERANCE = {"exact": 0.005, "curved": 0.01}
BBOX_TOL = 1.0  # mm, absolute per coordinate


def load_backend(name: str):
    mod, cls, kwargs, route = BACKENDS[name]
    backend = getattr(importlib.import_module(mod), cls)(**kwargs)
    return backend, {"module": mod, "class": cls, "kwargs": kwargs,
                     "access_route": route}


def tolerance(name: str, klass: str) -> float:
    t = TOLERANCES.get(name, DEFAULT_TOLERANCE)
    return t.get(klass, DEFAULT_TOLERANCE.get(klass, 0.01))
