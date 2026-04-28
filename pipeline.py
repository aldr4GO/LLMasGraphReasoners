# pipeline.py
# Top-level orchestration: solves the base TSP and then runs Eval-1.
# Supports both single-instance and batch processing.

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import config
from lkh_runner import solve_tsp
from tsplib_io import write_tsplib, write_lkh_par, parse_lkh_tour
from eval1 import compute_edge_importance

from data_loader import load_single_route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Base tour helpers ──────────────────────────────────────────────────────────

def _base_tour_path(station_code: str, work_dir: str) -> str:
    return os.path.join(work_dir, f"{station_code}_base.tour")


def _solve_base(
    matrix: List[List[float]],
    station_code: str,
    work_dir: str,
) -> Tuple[List[int], float, str]:
    """
    Solve the base (unperturbed) TSP and persist the tour for warm-starting.

    Returns:
        (base_route, base_cost, base_tour_file_path)
    """
    logger.info(f"[{station_code}] Solving base TSP …")
    t0 = time.perf_counter()

    # Write the base .tsp file (reused by all perturbed runs).
    tsp_file  = os.path.join(work_dir, f"{station_code}_base.tsp")
    tour_file = _base_tour_path(station_code, work_dir)
    par_file  = os.path.join(work_dir, f"{station_code}_base.par")

    write_tsplib(matrix, tsp_file, name=station_code)
    write_lkh_par(
        tsplib_file=tsp_file,
        tour_file=tour_file,
        output_file=par_file,
        initial_tour=None,                  # no warm start for base
        runs=config.LKH_RUNS,
        max_trials=config.LKH_MAX_TRIALS,
    )

    from lkh_runner import run_lkh
    run_lkh(par_file)

    route = parse_lkh_tour(tour_file)

    # Compute cost directly from matrix (ground truth, not LKH's internal cost).
    n = len(route)
    cost = sum(matrix[route[i]][route[(i + 1) % n]] for i in range(n))

    elapsed = time.perf_counter() - t0
    logger.info(
        f"[{station_code}] Base TSP done in {elapsed:.2f}s  "
        f"cost={cost:.2f}  nodes={n}"
    )

    # Clean up par and tsp (tour file is kept for warm-starting).
    for p in (par_file, tsp_file):
        if os.path.isfile(p):
            os.remove(p)

    return route, cost, tour_file


# ── Single-instance entry point ────────────────────────────────────────────────

def run_instance(
    station_code: str,
    nodes: List[int],
    distance_matrix: List[List[float]],
    work_dir: Optional[str] = None,
    save_results: bool = True,
) -> Dict[str, Any]:
    """
    Run the full Eval-1 pipeline for one TSP instance.

    Args:
        station_code:    Unique identifier for the instance.
        nodes:           List of node indices [0 … n-1] (used only for logging).
        distance_matrix: n×n matrix (list-of-lists). Must already encode
                         unavailable edges as large finite values.
        work_dir:        Directory for intermediate files.
                         Defaults to config.TMP_DIR / station_code.
        save_results:    If True, write edge_importance to a JSON file.

    Returns:
        {
          "station_code": str,
          "base_cost":    float,
          "base_route":   List[int],
          "edge_importance": { "u,v": float, … }
        }
    """
    if work_dir is None:
        work_dir = os.path.join(config.TMP_DIR, station_code)
    os.makedirs(work_dir, exist_ok=True)

    # 1. Solve base TSP
    base_route, base_cost, base_tour_file = _solve_base(
        distance_matrix, station_code, work_dir
    )

    # 2. Compute Eval-1 importance (parallel)
    importance = compute_edge_importance(
        matrix=distance_matrix,
        base_route=base_route,
        base_cost=base_cost,
        base_tour_file=base_tour_file,
        work_dir=work_dir,
    )

    # 3. Package results
    result = {
        "station_code": station_code,
        "base_cost":    base_cost,
        "base_route":   base_route,
        # JSON keys must be strings; store as "u,v".
        "edge_importance": {
            f"{u},{v}": imp for (u, v), imp in sorted(importance.items())
        },
    }

    if save_results:
        out_path = os.path.join(work_dir, f"{station_code}_eval1.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"[{station_code}] Results saved → {out_path}")

    return result


# ── Batch processing ───────────────────────────────────────────────────────────

def run_batch(
    instances: List[Dict[str, Any]],
    work_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Process multiple TSP instances sequentially.

    Each element of `instances` must have keys:
        station_code, nodes, distance_matrix

    Note: instances are processed sequentially; parallelism is applied
    *within* each instance's Eval-1 computation (across edges).
    Over-parallelising at the instance level would cause CPU contention.

    Returns:
        List of result dicts (same order as input).
    """
    results = []
    for inst in instances:
        logger.info(f"=== Starting instance: {inst['station_code']} ===")
        r = run_instance(
            station_code=inst["station_code"],
            nodes=inst["nodes"],
            distance_matrix=inst["distance_matrix"],
            work_dir=work_dir,
        )
        results.append(r)
    return results


# ── CLI / demo ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random, math

    # ── Minimal smoke-test with a synthetic 10-node instance ──────────────────
    random.seed(42)
    N = 10
    LARGE = 1_000_000   # represents a missing / unavailable edge

    # Build a random symmetric distance matrix with a few missing edges.
    coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(N)]
    mat = [[0] * N for _ in range(N)]
    for i in range(N):
        for j in range(N):
            if i == j:
                mat[i][j] = 0
            else:
                d = math.dist(coords[i], coords[j])
                # Randomly mark ~10% of edges as unavailable.
                mat[i][j] = LARGE if random.random() < 0.1 else int(d)

    # Ensure symmetry
    for i in range(N):
        for j in range(i + 1, N):
            mat[i][j] = mat[j][i] = min(mat[i][j], mat[j][i])

    single_route = load_single_route("./model_build_inputs/sparse_travel_times.json", "RouteID_00143bdd-0a6b-49ec-bb35-36593d303e77")  # test data loader
    station_code = single_route["station_code"]  # test data loader
    print(enumerate(single_route["node_ids"]))
    nodes = single_route["nodes"]  # test data loader
    mat = single_route["distance_matrix"]  # test data loader
    result = run_instance(
        station_code=station_code,
        nodes=nodes,
        distance_matrix=mat,
    )

    print("\n── Eval-1 Edge Importance ──")
    for edge, imp in sorted(result["edge_importance"].items(), key=lambda x: -x[1]):
        print(f"  edge ({edge}): {imp:.6f}")
