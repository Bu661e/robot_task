from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = PROJECT_ROOT / "runtime"
ARTIFACTS_DIR = RUNTIME_DIR / "artifacts"

SAM3_PYTHON = Path("/root/autodl-tmp/conda/envs/sam3/bin/python")
SAM3D_OBJECTS_PYTHON = Path("/root/autodl-tmp/conda/envs/sam3d-objects/bin/python")

SAM3_BACKEND_SCRIPT = PROJECT_ROOT / "sam3-ultralytics" / "run_sam3_inference.py"
SAM3D_OBJECTS_BACKEND_SCRIPT = PROJECT_ROOT / "backend_scripts" / "run_sam3d_inference.py"
