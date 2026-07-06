"""Conformance runner: point it at any backend in the registry.

    python -m conformance.run --backend sampler --backend occt --backend manifold

Stages per backend:
  1. SMOKE     — one micro-recipe per geometry op, closed-form checks.
                 Observed (not declared) op support -> capability manifest.
  2. CORPUS    — graded recipes (L0..L4) via the match_cast discipline:
                 re-evaluate, diff against closed-form oracles, judge against
                 the backend's tolerance contract per class.
  3. ROUNDTRIP — emit OpenSCAD source, lift it back, re-evaluate: recipe must
                 survive a trip through another system's source language.

Outputs:
  conformance/reports/<name>.report.json   (gitignored; full detail)
  conformance/targets/<name>.json          (capability manifest; committed)

Exit code != 0 iff any hard FAIL (capability gaps and informational diffs are
recorded, not failed — the element/op is the unit of degradation).
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import geomir  # noqa: E402
from geomir import parse, evaluate_element, emit_scad, lift_scad, UnsupportedOp  # noqa: E402
from conformance.registry import (load_backend, tolerance, BBOX_TOL)  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")

# --- smoke micro-recipes: one per geometry op, closed-form ------------------

def _wrap(body: str) -> str:
    return "recipe.module @s {\n" + body + '\n  recipe.export %e, "e"\n}\n'


_SMOKE = {
    "geom.box": (
        _wrap("  %e = geom.box 100.0, 200.0, 50.0"),
        {"volume": 1_000_000.0, "class": "exact"}),
    "geom.cylinder": (
        _wrap("  %e = geom.cylinder 50.0, 100.0"),
        {"volume": math.pi * 2500 * 100, "class": "curved"}),
    "geom.translate": (
        _wrap("  %a = geom.box 10.0, 10.0, 10.0\n"
              "  %e = geom.translate %a, [5.0, 5.0, 5.0]"),
        {"volume": 1000.0, "class": "exact", "bbox": [5, 5, 5, 15, 15, 15]}),
    "geom.union": (
        _wrap("  %a = geom.box 100.0, 100.0, 100.0\n"
              "  %b0 = geom.box 100.0, 100.0, 100.0\n"
              "  %b = geom.translate %b0, [200.0, 0.0, 0.0]\n"
              "  %e = geom.union %a, %b"),
        {"volume": 2_000_000.0, "class": "exact"}),
    "geom.difference": (
        _wrap("  %a = geom.box 100.0, 100.0, 100.0\n"
              "  %b0 = geom.box 50.0, 120.0, 50.0\n"
              "  %b = geom.translate %b0, [25.0, -10.0, 25.0]\n"
              "  %e = geom.difference %a, %b"),
        {"volume": 750_000.0, "class": "exact"}),
    "geom.intersect": (
        _wrap("  %a = geom.box 100.0, 100.0, 100.0\n"
              "  %b0 = geom.box 100.0, 100.0, 100.0\n"
              "  %b = geom.translate %b0, [50.0, 0.0, 0.0]\n"
              "  %e = geom.intersect %a, %b"),
        {"volume": 500_000.0, "class": "exact"}),
    "geom.repeat_x": (
        _wrap("  %a = geom.box 50.0, 50.0, 50.0\n"
              "  %e = geom.repeat_x %a, 3.0, 100.0"),
        {"volume": 375_000.0, "class": "exact"}),
    "geom.fillet": (
        _wrap("  %a = geom.box 200.0, 200.0, 200.0\n"
              "  %e = geom.fillet %a, 20.0"),
        {"volume_range": [7_200_000.0, 8_000_000.0], "class": "exact"}),
    "geom.rotate_z": (
        _wrap("  %a = geom.box 100.0, 50.0, 30.0\n"
              "  %e = geom.rotate_z %a, 45.0"),
        {"volume": 150_000.0, "class": "exact"}),
    "geom.extrude": (
        _wrap("  %p = profile.polygon [[0.0, 0.0], [200.0, 0.0], "
              "[200.0, 100.0], [100.0, 100.0], [100.0, 200.0], [0.0, 200.0]]\n"
              "  %e = geom.extrude %p, 100.0"),
        {"volume": 3_000_000.0, "class": "exact"}),
}


def _bbox_ok(a, b, tol=BBOX_TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _judge(vol, bbox, spec, tol_rel):
    """Return (status, rel_diff)."""
    if "volume_range" in spec:
        lo, hi = spec["volume_range"]
        ok = lo <= vol <= hi
        return ("PASS" if ok else "FAIL"), None
    rel = abs(vol - spec["volume"]) / abs(spec["volume"])
    ok = rel <= tol_rel and (("bbox" not in spec) or _bbox_ok(bbox, spec["bbox"]))
    return ("PASS" if ok else "FAIL"), rel


def run_backend(name: str, out_dir: str, targets_dir: str) -> dict:
    backend, info = load_backend(name)
    report = {"target": name, "backend": info,
              "geomir_version": geomir.__version__,
              "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "smoke": {}, "corpus": {}, "roundtrip": {}}
    hard_fail = False

    # ---- stage 1: smoke -----------------------------------------------------
    for op, (ir_text, spec) in _SMOKE.items():
        module = parse(ir_text)
        try:
            h = evaluate_element(module, backend, "e")
            vol, bbox = backend.volume(h), backend.bbox(h)
            status, rel = _judge(vol, bbox, spec, tolerance(name, spec["class"]))
            report["smoke"][op] = {"supported": True, "status": status,
                                   "rel_diff": rel, "volume": vol}
            hard_fail |= status == "FAIL"
        except UnsupportedOp as e:
            report["smoke"][op] = {"supported": False, "status": "UNSUPPORTED",
                                   "detail": str(e)}
        except Exception as e:
            report["smoke"][op] = {"supported": False, "status": "ERROR",
                                   "detail": f"{type(e).__name__}: {e}"}
            hard_fail = True

    unsupported = {op for op, r in report["smoke"].items() if not r["supported"]}

    # ---- stage 2: corpus ----------------------------------------------------
    with open(os.path.join(CORPUS, "expected.json")) as f:
        expected = json.load(f)["recipes"]
    for rid, meta in expected.items():
        with open(os.path.join(CORPUS, meta["file"])) as f:
            module = parse(f.read())
        klass = meta["class"]
        entry = {"class": klass, "elements": {}}
        for elem, spec in meta["elements"].items():
            try:
                h = evaluate_element(module, backend, elem)
                vol, bbox = backend.volume(h), backend.bbox(h)
                tol = tolerance(name, "curved" if klass == "informational"
                                else ("exact" if klass == "capability" else klass))
                status, rel = _judge(vol, bbox, spec, tol)
                if klass == "informational" and status == "FAIL":
                    status = "INFO-DIVERGED"       # reported, never hard-fails
                entry["elements"][elem] = {"status": status, "volume": vol,
                                           "rel_diff": rel}
                hard_fail |= status == "FAIL"
            except UnsupportedOp as e:
                ok = klass == "capability" or any(op in str(e) for op in unsupported)
                entry["elements"][elem] = {
                    "status": "UNSUPPORTED (ok)" if ok else "FAIL",
                    "detail": str(e)}
                hard_fail |= not ok
            except Exception as e:
                entry["elements"][elem] = {"status": "ERROR",
                                           "detail": f"{type(e).__name__}: {e}"}
                hard_fail = True
        report["corpus"][rid] = entry

    # ---- stage 3: scad round trip -------------------------------------------
    for rid, meta in expected.items():
        if meta["class"] in ("capability",):
            report["roundtrip"][rid] = {"status": "SKIPPED (baked fallback path)"}
            continue
        with open(os.path.join(CORPUS, meta["file"])) as f:
            module = parse(f.read())
        try:
            lifted, warnings, _ = lift_scad(emit_scad(module), module_name=rid)
            ok = True
            for elem in meta["elements"]:
                v0 = backend.volume(evaluate_element(module, backend, elem))
                v1 = backend.volume(evaluate_element(lifted, backend, elem))
                ok &= abs(v1 - v0) <= max(1e-9 * abs(v0), 1e-9)
            report["roundtrip"][rid] = {"status": "PASS" if ok else "FAIL",
                                        "warnings": warnings}
            hard_fail |= not ok
        except UnsupportedOp:
            report["roundtrip"][rid] = {"status": "SKIPPED (op unsupported)"}
        except Exception as e:
            report["roundtrip"][rid] = {"status": "FAIL",
                                        "detail": f"{type(e).__name__}: {e}"}
            hard_fail = True

    # ---- capability manifest (observed, not declared) ------------------------
    manifest = {
        "target": name,
        "generated": report["generated"],
        "geomir_version": geomir.__version__,
        "backend": info,
        "ops": {op: {"supported": r["supported"],
                     "max_rel_diff": r.get("rel_diff")}
                for op, r in report["smoke"].items()},
        "tolerance_contract": {k: tolerance(name, k) for k in ("exact", "curved")},
        "corpus_summary": _summary(report["corpus"]),
        "scad_roundtrip": all(v["status"] != "FAIL"
                              for v in report["roundtrip"].values()),
    }
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(targets_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{name}.report.json"), "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(targets_dir, f"{name}.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    _print_card(name, report, manifest, hard_fail)
    report["hard_fail"] = hard_fail
    return report


def _summary(corpus):
    s = {"PASS": 0, "FAIL": 0, "UNSUPPORTED": 0, "INFO": 0, "ERROR": 0}
    for entry in corpus.values():
        for r in entry["elements"].values():
            st = r["status"]
            key = ("UNSUPPORTED" if st.startswith("UNSUPPORTED")
                   else "INFO" if st.startswith("INFO")
                   else st if st in s else "ERROR")
            s[key] += 1
    return s


def _print_card(name, report, manifest, hard_fail):
    print("=" * 74)
    print(f"CONFORMANCE REPORT CARD — target: {name}  "
          f"(geomir {report['geomir_version']})")
    print("=" * 74)
    sup = [o.split(".")[1] for o, r in report["smoke"].items() if r["supported"]]
    uns = [o.split(".")[1] for o, r in report["smoke"].items() if not r["supported"]]
    print(f"ops supported : {', '.join(sup)}")
    print(f"ops missing   : {', '.join(uns) if uns else '—'}")
    print(f"contract      : exact ≤ {manifest['tolerance_contract']['exact']:g}, "
          f"curved ≤ {manifest['tolerance_contract']['curved']:g} (rel. volume)")
    print(f"{'recipe':<20} {'class':<14} {'status':<20} {'Δvol':>10}")
    for rid, entry in report["corpus"].items():
        for elem, r in entry["elements"].items():
            d = (f"{r['rel_diff']*100:+.3f}%"
                 if r.get("rel_diff") is not None else "—")
            print(f"{rid:<20} {entry['class']:<14} {r['status']:<20} {d:>10}")
    rt = sum(1 for v in report["roundtrip"].values() if v["status"] == "PASS")
    print(f"scad roundtrip: {rt}/{len(report['roundtrip'])} pass "
          f"(rest skipped/gated)")
    print(f"summary       : {manifest['corpus_summary']}  ->  "
          f"{'HARD FAIL' if hard_fail else 'CONFORMANT'}")
    print()


def main():
    ap = argparse.ArgumentParser(description="geomir conformance runner")
    ap.add_argument("--backend", action="append", required=True,
                    help="registry name (repeatable): sampler, occt, manifold, ...")
    ap.add_argument("--reports", default=os.path.join(HERE, "reports"))
    ap.add_argument("--targets", default=os.path.join(HERE, "targets"))
    args = ap.parse_args()
    failed = False
    for name in args.backend:
        try:
            failed |= run_backend(name, args.reports, args.targets)["hard_fail"]
        except ImportError as e:
            print(f"[{name}] backend unavailable in this environment: {e}\n"
                  f"        (run on a machine with its dependencies — see "
                  f"docs/ROADMAP.md HC-0)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
