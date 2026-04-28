# eval1.py
# Core Eval-1 implementation: computes edge importance for every edge in the
# base TSP tour using parallel perturbed LKH solves with warm-starting.

import copy
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple

import config
from lkh_runner import solve_tsp

logger = logging.getLogger(__name__)


# ── Penalty helpers ────────────────────────────────────────────────────────────

def _compute_penalty(matrix: List[List[float]]) -> int:
    """
    Return integer penalty = PENALTY_MULTIPLIER × max(finite matrix values).

    Assumption: very large finite values already encode missing edges.
    We scale relative to the matrix max so the penalty is always dominant
    but never triggers LKH integer overflow (which occurs near 2^31).
    """
    flat_max = max(v for row in matrix for v in row)
    penalty = int(config.PENALTY_MULTIPLIER * flat_max)
    # Guard: LKH uses 32-bit integers internally.
    penalty = min(penalty, 2_000_000_000)
    return penalty


def _perturb(matrix: List[List[float]], u: int, v: int, penalty: int) -> List[List[float]]:
    """
    Return a deep-copied matrix with edge (u,v) symmetrically penalised.

    We deep-copy only the two affected rows to avoid copying the entire n×n
    matrix for large instances.
    """
    perturbed = [row[:] for row in matrix]   # shallow row copies (list-of-lists)
    perturbed[u][v] = penalty
    perturbed[v][u] = penalty
    return perturbed


# ── Worker function (must be module-level for multiprocessing pickling) ────────

def _worker(args: Tuple) -> Tuple[Tuple[int, int], float]:
    """
    Worker that solves one perturbed TSP and returns (edge, perturbed_cost).

    Args:
        args: (u, v, matrix, base_tour_file, work_dir, penalty)

    Returns:
        ((min_u, min_v), perturbed_cost)
    """
    u, v, matrix, base_tour_file, work_dir, penalty = args

    perturbed = _perturb(matrix, u, v, penalty)

    _, cost = solve_tsp(
        matrix=perturbed,
        work_dir=work_dir,
        tag=f"e{u}_{v}",
        initial_tour_file=base_tour_file,   # warm start — mandatory
    )
    return (min(u, v), max(u, v)), cost


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_edge_importance(
    matrix: List[List[float]],
    base_route: List[int],
    base_cost: float,
    base_tour_file: str,
    work_dir: str = config.TMP_DIR,
) -> Dict[Tuple[int, int], float]:
    """
    Compute Eval-1 importance for every edge in `base_route`.

    Importance:  I_e = (C(G\\e) - C(G)) / C(G)

    Args:
        matrix:         n×n distance matrix.
        base_route:     0-indexed node order from the base TSP solve.
        base_cost:      Cost of the base tour.
        base_tour_file: Path to the base .tour file used for warm-starting.
        work_dir:       Directory for temporary LKH files.

    Returns:
        Dict mapping (min_u, max_u) → importance_value.
        Larger value ⟹ edge more critical to the optimal tour.
    """
    n = len(base_route)
    penalty = _compute_penalty(matrix)

    # Build canonical list of unique tour edges.
    edges: List[Tuple[int, int]] = []
    for i in range(n):
        u = base_route[i]
        v = base_route[(i + 1) % n]
        edges.append((u, v))

    logger.info(
        f"Computing Eval-1 for {len(edges)} edges | "
        f"base_cost={base_cost:.2f} | penalty={penalty} | "
        f"workers={config.NUM_WORKERS}"
    )

    worker_args = [
        (u, v, matrix, base_tour_file, work_dir, penalty)
        for u, v in edges
    ]

    importance: Dict[Tuple[int, int], float] = {}
    t0 = time.perf_counter()

    with ProcessPoolExecutor(max_workers=config.NUM_WORKERS) as pool:
        futures = {pool.submit(_worker, args): args for args in worker_args}

        for idx, future in enumerate(as_completed(futures), start=1):
            args = futures[future]
            u_raw, v_raw = args[0], args[1]
            try:
                edge_key, perturbed_cost = future.result()
                imp = (perturbed_cost - base_cost) / base_cost
                importance[edge_key] = imp
                elapsed = time.perf_counter() - t0
                logger.info(
                    f"  [{idx}/{len(edges)}] edge=({u_raw},{v_raw}) "
                    f"perturbed_cost={perturbed_cost:.2f} "
                    f"importance={imp:.6f} "
                    f"elapsed={elapsed:.1f}s"
                )
            except Exception as exc:
                logger.error(f"  edge ({u_raw},{v_raw}) failed: {exc}")
                importance[(min(u_raw, v_raw), max(u_raw, v_raw))] = float("nan")

    total = time.perf_counter() - t0
    logger.info(f"Eval-1 complete in {total:.2f}s")
    return importance
