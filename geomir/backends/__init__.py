"""Kernel backends. Imports are lazy so the pure-Python parts of geomir
(IR, scad emit/lift, artifact logic, sampler) work without cadquery or
manifold3d installed."""

from .sampler import SamplerBackend  # pure numpy, always available


def occt():
    from .occt import OCCTBackend
    return OCCTBackend


def manifold():
    from .manifold_backend import ManifoldBackend
    return ManifoldBackend
