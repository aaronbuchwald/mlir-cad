"""geomir — a minimal MLIR-style multi-level IR for CAD exchange.

Demo companion to "A Compiler-Theoretic Analysis of AEC Geometry
Interoperability". One recipe IR; two open-source kernels with different
underlying math (OCCT exact B-rep = FreeCAD's kernel; Manifold polyhedral
mesh = OpenSCAD's boolean engine); exchange artifacts that carry recipe +
baked oracle; match_cast-style validation with per-element fallback; and
lowering to / lifting from OpenSCAD source.
"""

__version__ = "0.1.0"

from .ir import parse, print_module, verify, Module, Op, IRError          # noqa
from .eval import evaluate, evaluate_element, UnsupportedOp               # noqa
from .artifact import (bake, save, load, import_artifact, regenerate,     # noqa
                       LIVE, FALLBACK, DIVERGED, ERROR)
from .scad import emit_scad, lift_scad                                    # noqa
