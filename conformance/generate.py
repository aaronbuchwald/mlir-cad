"""Grammar-directed random recipe generator + differential testing mode.

The Csmith-for-geometry-kernels seed (docs/ROADMAP.md Phase 4; the confirmed
research gap in docs/research/compilers-for-cad.md §6): generate random
well-formed recipes from the dialect grammar, evaluate the same recipe on N
independent backends, and treat disagreement beyond the tolerance contract as
a *finding* — data for triage (HC-6), not a test failure.

    python -m conformance.generate --mode gen  --seeds 20 --out /tmp/recipes
    python -m conformance.generate --mode diff --seeds 100 \
        --backend occt --backend manifold --backend sampler

Notes:
- geom.fillet is deliberately excluded (capability-gated; would only add
  noise — capability gaps are the runner's job, not the fuzzer's).
- Differential mode compares volumes only: bbox is skipped because the
  sampler's difference-bbox is intentionally conservative.
- Deterministic per seed: same seed -> same recipe text, forever. Findings
  are reproducible by seed alone.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from geomir.ir import Module, Op, print_module, verify  # noqa: E402
from geomir import parse, evaluate_element  # noqa: E402
from conformance.registry import load_backend, tolerance  # noqa: E402


class _Gen:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seed = seed
        self.ops: list[Op] = []
        self.n = 0
        self.curved = False
        self.params: list[str] = []

    def fresh(self) -> str:
        self.n += 1
        return f"v{self.n}"

    def lit(self, lo: float, hi: float) -> float:
        return round(self.rng.uniform(lo, hi), 1)

    def dim(self, lo: float = 20.0, hi: float = 500.0):
        """A dimension: literal, or a reference to a module parameter."""
        if self.params and self.rng.random() < 0.25:
            return f"%{self.rng.choice(self.params)}"
        return self.lit(lo, hi)

    def emit(self, name: str, operands) -> str:
        r = self.fresh()
        self.ops.append(Op(r, name, operands))
        return f"%{r}"

    def leaf(self) -> str:
        roll = self.rng.random()
        if roll < 0.5:
            return self.emit("geom.box", [self.dim(), self.dim(), self.dim()])
        if roll < 0.75:
            # right-triangle profile extrusion (prismatic -> stays exact-class)
            a, b = self.lit(50, 400), self.lit(50, 400)
            p = self.emit("profile.polygon",
                          [[[0.0, 0.0], [a, 0.0], [0.0, b]]])
            return self.emit("geom.extrude", [p, self.lit(50, 400)])
        self.curved = True
        return self.emit("geom.cylinder",
                         [self.lit(20, 200), self.lit(50, 500)])

    def solid(self, depth: int) -> str:
        if depth <= 0:
            return self.leaf()
        roll = self.rng.random()
        if roll < 0.20:
            return self.emit("geom.translate",
                             [self.solid(depth - 1),
                              [self.lit(-200, 200), self.lit(-200, 200),
                               self.lit(-200, 200)]])
        if roll < 0.32:
            return self.emit("geom.rotate_z",
                             [self.solid(depth - 1), self.lit(-180, 180)])
        if roll < 0.45:
            return self.emit("geom.union",
                             [self.solid(depth - 1), self.solid(depth - 1)])
        if roll < 0.65:  # bias operand b toward overlap with a small offset
            a = self.solid(depth - 1)
            b = self.emit("geom.translate",
                          [self.solid(depth - 1),
                           [self.lit(-100, 100), self.lit(-100, 100),
                            self.lit(-100, 100)]])
            return self.emit("geom.difference", [a, b])
        if roll < 0.82:
            a = self.solid(depth - 1)
            b = self.emit("geom.translate",
                          [self.solid(depth - 1),
                           [self.lit(-80, 80), self.lit(-80, 80),
                            self.lit(-80, 80)]])
            return self.emit("geom.intersect", [a, b])
        return self.emit("geom.repeat_x",
                         [self.solid(depth - 1),
                          float(self.rng.randint(2, 4)),
                          self.lit(300, 800)])

    def module(self) -> tuple[str, str]:
        """Returns (ir_text, class)."""
        for i in range(self.rng.randint(0, 2)):
            p = f"p{i}"
            self.params.append(p)
            self.ops.append(Op(p, "recipe.param", [p, self.lit(100, 400)]))
        root = self.solid(self.rng.randint(2, 4))
        self.ops.append(Op(None, "recipe.export", [root, "e"]))
        m = Module(name=f"gen_{self.seed}", ops=self.ops)
        verify(m)
        return print_module(m), ("curved" if self.curved else "exact")


def gen_recipe(seed: int) -> tuple[str, str]:
    return _Gen(seed).module()


# ---------------------------------------------------------------------------

def mode_gen(args):
    os.makedirs(args.out, exist_ok=True)
    for s in range(args.start, args.start + args.seeds):
        text, klass = gen_recipe(s)
        parse(text)  # round-trip sanity
        with open(os.path.join(args.out, f"gen_{s}.ir"), "w") as f:
            f.write(f"// class: {klass}\n" + text)
    print(f"wrote {args.seeds} recipes to {args.out}")


def mode_diff(args):
    backends = {}
    for name in args.backend:
        try:
            backends[name], _ = load_backend(name)
        except ImportError as e:
            print(f"[{name}] unavailable here: {e} — skipping "
                  f"(see docs/ROADMAP.md HC-0)")
    if len(backends) < 2:
        sys.exit("differential mode needs >= 2 available backends")

    findings, compared = [], 0
    for s in range(args.start, args.start + args.seeds):
        text, klass = gen_recipe(s)
        module = parse(text)
        vols = {}
        for name, b in backends.items():
            try:
                vols[name] = b.volume(evaluate_element(module, b, "e"))
            except Exception as e:
                vols[name] = f"ERROR: {type(e).__name__}: {e}"
        names = list(vols)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b2 = names[i], names[j]
                va, vb = vols[a], vols[b2]
                compared += 1
                if isinstance(va, str) or isinstance(vb, str):
                    findings.append({"seed": s, "class": klass, "pair": [a, b2],
                                     "kind": "evaluation-error",
                                     "volumes": {a: va, b2: vb}})
                    continue
                if abs(va) < 1e-6 and abs(vb) < 1e-6:
                    continue
                rel = abs(va - vb) / max(abs(va), abs(vb), 1e-9)
                contract = max(tolerance(a, klass), tolerance(b2, klass))
                if rel > contract:
                    findings.append({"seed": s, "class": klass, "pair": [a, b2],
                                     "kind": "volume-divergence",
                                     "rel_diff": rel, "contract": contract,
                                     "volumes": {a: va, b2: vb}})

    print(f"differential: {args.seeds} seeds x {len(backends)} backends "
          f"({compared} comparisons) -> {len(findings)} finding(s)")
    for f_ in findings[:10]:
        print(" ", json.dumps(f_, default=str)[:160])
    if args.out:
        with open(args.out, "w") as fh:
            for f_ in findings:
                fh.write(json.dumps(f_) + "\n")
        print(f"findings -> {args.out}")
    if args.fail_on_findings and findings:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="geomir recipe fuzzer / differential tester")
    ap.add_argument("--mode", choices=["gen", "diff"], default="diff")
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--backend", action="append", default=[])
    ap.add_argument("--out", default=None)
    ap.add_argument("--fail-on-findings", action="store_true")
    args = ap.parse_args()
    if args.mode == "gen":
        if not args.out:
            sys.exit("--mode gen requires --out DIR")
        mode_gen(args)
    else:
        mode_diff(args)


if __name__ == "__main__":
    main()
