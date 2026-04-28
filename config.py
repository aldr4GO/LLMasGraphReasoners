# config.py
# Central configuration for the TSP Eval-1 pipeline.

import os
from multiprocessing import cpu_count

# ── LKH binary ────────────────────────────────────────────────────────────────
# Set LKH_PATH to the compiled LKH binary on your system.
# Download & build from: http://webhotel4.ruc.dk/~keld/research/LKH-3/
# LKH_PATH = os.environ.get("LKH_PATH", "LKH")   # must be on PATH or absolute
LKH_PATH = "LKH-3.0.9/LKH"   # must be on PATH or absolute

# ── Solver parameters ─────────────────────────────────────────────────────────
# Kept small for speed; warm-start compensates for fewer trials.
LKH_RUNS = 1
LKH_MAX_TRIALS = 100

# ── Perturbation penalty ──────────────────────────────────────────────────────
# Multiplier applied to max(distance_matrix) to penalise a removed edge.
# 5–10× is the recommended range; 7× is a safe default.
# Do NOT use 1e9 or inf — LKH may overflow internally.
PENALTY_MULTIPLIER = 7

# ── Parallelism ───────────────────────────────────────────────────────────────
NUM_WORKERS = max(1, cpu_count() - 1)

# ── Working directory for temp files ─────────────────────────────────────────
TMP_DIR = os.path.join(os.path.dirname(__file__), "tmp")
os.makedirs(TMP_DIR, exist_ok=True)
