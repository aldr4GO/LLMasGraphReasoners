# data_loader.py
# Loads the Amazon Last Mile Routing JSON distance matrix format and converts
# it into the dense integer matrix expected by the LKH pipeline.
#
# Input JSON structure:
#   {
#     "RouteID_xxxx": {
#       "AD": { "RG": 17.0, "EC": 21.8, ... },   ← sparse k-NN rows
#       "AF": { "KA": 21.8, ... },
#       ...
#     },
#     "RouteID_yyyy": { ... },
#     ...
#   }
#
# Notes:
#   - Only edges explicitly listed are "available"; all others get MISSING_PENALTY.
#   - The matrix is made symmetric: if (u→v) is listed but not (v→u), we mirror it.
#   - Node order is sorted(node_ids) for determinism across runs.

import json
from typing import Dict, List, Tuple, Any

# Large finite value for missing edges.
# Must be consistent with config.PENALTY_MULTIPLIER logic in eval1.py.
# 1_000_000 is safely below the 7× guard in _compute_penalty().
MISSING_PENALTY: int = 1_000_000


def load_json(filepath: str) -> Dict[str, Any]:
    """Load the raw JSON file from disk."""
    with open(filepath, "r") as f:
        return json.load(f)


def parse_route(
    route_data: Dict[str, Dict[str, float]],
    missing_penalty: int = MISSING_PENALTY,
) -> Tuple[List[str], List[List[float]]]:
    """
    Convert one route's sparse distance dict into a dense matrix.

    Args:
        route_data:      { node_id: { neighbor_id: distance, ... }, ... }
        missing_penalty: Value used for edges not present in the sparse data.

    Returns:
        (node_ids, matrix)
            node_ids: sorted list of string node IDs (index i ↔ node_ids[i])
            matrix:   n×n list-of-lists with float distances
    """
    # Collect all node IDs that appear as either a row key or a column key.
    all_nodes = set(route_data.keys())
    for neighbors in route_data.values():
        all_nodes.update(neighbors.keys())

    node_ids: List[str] = sorted(all_nodes)   # deterministic ordering
    n = len(node_ids)
    idx: Dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}

    # Initialise with missing penalty; diagonal stays 0.
    matrix: List[List[float]] = [
        [missing_penalty if i != j else 0 for j in range(n)]
        for i in range(n)
    ]

    # Fill known edges.
    for src, neighbors in route_data.items():
        i = idx[src]
        for dst, dist in neighbors.items():
            j = idx[dst]
            matrix[i][j] = dist

    # Mirror to ensure symmetry: if (i→j) known but (j→i) missing, copy it.
    for i in range(n):
        for j in range(i + 1, n):
            ij = matrix[i][j]
            ji = matrix[j][i]
            if ij == missing_penalty and ji != missing_penalty:
                matrix[i][j] = ji
            elif ji == missing_penalty and ij != missing_penalty:
                matrix[j][i] = ij
            # If both are known, keep them as-is (asymmetric travel times are
            # averaged to satisfy LKH's symmetry requirement).
            elif ij != missing_penalty and ji != missing_penalty and ij != ji:
                avg = (ij + ji) / 2.0
                matrix[i][j] = avg
                matrix[j][i] = avg

    return node_ids, matrix


def load_all_routes(
    filepath: str,
    missing_penalty: int = MISSING_PENALTY,
) -> List[Dict[str, Any]]:
    """
    Load every route from the JSON file and return pipeline-ready instances.

    Args:
        filepath:        Path to the JSON distance matrix file.
        missing_penalty: Penalty for missing edges.

    Returns:
        List of dicts, each with keys:
            station_code   : str  — the RouteID key
            node_ids       : List[str]  — string labels (for reference)
            nodes          : List[int]  — integer indices [0 … n-1]
            distance_matrix: List[List[float]]  — dense n×n matrix
    """
    raw = load_json(filepath)
    instances = []

    for route_id, route_data in raw.items():
        node_ids, matrix = parse_route(route_data, missing_penalty)
        n = len(node_ids)
        instances.append({
            "station_code":    route_id,
            "node_ids":        node_ids,          # string labels
            "nodes":           list(range(n)),    # integer indices
            "distance_matrix": matrix,
        })

    return instances


def load_single_route(
    filepath: str,
    route_id: str,
    missing_penalty: int = MISSING_PENALTY,
) -> Dict[str, Any]:
    """
    Load a single named route from the JSON file.

    Args:
        filepath: Path to the JSON file.
        route_id: The exact key, e.g. "RouteID_00143bdd-...".

    Returns:
        Same dict structure as load_all_routes() entries.

    Raises:
        KeyError: If route_id is not found in the file.
    """
    raw = load_json(filepath)
    if route_id not in raw:
        available = list(raw.keys())[:5]
        raise KeyError(
            f"Route '{route_id}' not found. "
            f"First 5 available: {available}"
        )

    node_ids, matrix = parse_route(raw[route_id], missing_penalty)
    n = len(node_ids)
    return {
        "station_code":    route_id,
        "node_ids":        node_ids,
        "nodes":           list(range(n)),
        "distance_matrix": matrix,
    }