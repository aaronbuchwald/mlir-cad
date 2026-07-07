#!/usr/bin/env bash
# One-time environment setup: venv + kernels + verification.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
echo "using $($PY --version) at $(command -v $PY)"
echo "(cadquery ships wheels for CPython 3.10-3.12; if pip fails below,"
echo " point PYTHON at one of those, e.g. PYTHON=python3.12 ./setup.sh)"
echo

$PY -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
# optional: IFC export support (geomir.ifc_export); wheel coverage varies
pip install ifcopenshell || echo "NOTE: ifcopenshell unavailable for this python/platform — IFC export disabled, everything else unaffected"

echo
echo "== pure-python test suite (IR / artifact / match_cast / scad) =="
python tests/run_tests.py | tail -3
echo
echo "== kernel smoke test (catches cadquery/manifold3d API drift) =="
python smoke_kernels.py

echo
echo "Setup complete. Run the demo with:"
echo "  source .venv/bin/activate && python demo.py"
