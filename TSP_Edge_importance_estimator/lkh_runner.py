# lkh_runner.py
# Thin wrapper around the LKH binary and a high-level solve_tsp() function.

import os
import subprocess
import tempfile
import time
import uuid
from typing import List, Tuple, Optional

import almrc.LLMasGraphReasoners.TSP_Edge_importance_estimator.config as config
from almrc.LLMasGraphReasoners.TSP_Edge_importance_estimator.tsplib_io import write_tsplib, write_lkh_par, parse_lkh_tour


def run_lkh(par_file: str) -> None:
    """
    Execute LKH with the given parameter file.

    Args:
        par_file: Path to the .par file.

    Raises:
        RuntimeError: If LKH exits with a non-zero return code.
    """
    result = subprocess.run(
        [config.LKH_PATH, par_file],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"LKH failed (exit {result.returncode}).\n"
            f"STDOUT: {result.stdout[-500:]}\n"
            f"STDERR: {result.stderr[-500:]}"
        )


def _tour_cost(matrix: List[List[float]], route: List[int]) -> float:
    """
    Compute the total cost of a closed TSP tour.

    The tour visits nodes in `route` order and returns to the first node.
    """
    n = len(route)
    return sum(matrix[route[i]][route[(i + 1) % n]] for i in range(n))


def solve_tsp(
    matrix: List[List[float]],
    work_dir: str = config.TMP_DIR,
    tag: str = "",
    initial_tour_file: Optional[str] = None,
) -> Tuple[List[int], float]:
    """
    Solve a TSP instance defined by `matrix` using LKH.

    Args:
        matrix:            n×n distance matrix (list-of-lists).
        work_dir:          Directory for temporary files.
        tag:               Short string appended to temp filenames (for tracing).
        initial_tour_file: Optional path to a base.tour for warm-starting.

    Returns:
        (route, cost)
            route: 0-indexed list of nodes in tour order (length n, no repeat).
            cost:  Total tour length computed from the matrix.
    """
    uid = f"{tag}_{uuid.uuid4().hex[:8]}"
    tsp_file  = os.path.join(work_dir, f"{uid}.tsp")
    tour_file = os.path.join(work_dir, f"{uid}.tour")
    par_file  = os.path.join(work_dir, f"{uid}.par")

    try:
        write_tsplib(matrix, tsp_file, name=uid)
        write_lkh_par(
            tsplib_file=tsp_file,
            tour_file=tour_file,
            output_file=par_file,
            initial_tour=initial_tour_file,
            runs=config.LKH_RUNS,
            max_trials=config.LKH_MAX_TRIALS,
        )
        run_lkh(par_file)
        route = parse_lkh_tour(tour_file)
        cost  = _tour_cost(matrix, route)
        return route, cost

    finally:
        # Clean up temp files; leave tour_file if it's the base tour.
        for path in (tsp_file, par_file):
            if os.path.isfile(path):
                os.remove(path)
        # Remove perturbed tour file (not the base); caller manages base.tour.
        if initial_tour_file is not None and os.path.isfile(tour_file):
            os.remove(tour_file)
