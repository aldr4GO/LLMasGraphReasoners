"""
Convert dense travel time graphs to sparse graphs using k-NN logic.
Inputs and outputs in JSON dict-of-dicts format.
"""

import json
import numpy as np
from pathlib import Path
import tqdm
from typing import Dict, Optional, List, Tuple


def load_json(path: str) -> dict:
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def save_json(data: dict, path: str) -> None:
    """Save dictionary to JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {path}")


def build_sparse_travel_times_from_dense(
    travel_times: Dict[str, Dict[str, float]],
    k: int = 4,
    actual_sequence: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Build a sparse travel time matrix from dense travel time matrix using k-NN.
    
    Args:
        travel_times: Dict mapping source_stop -> {dest_stop: time, ...}
        k: Number of nearest neighbors to keep per node
        actual_sequence: Optional list of stops in actual delivery order
    
    Returns:
        Dict with same structure but only k-NN edges (and actual sequence edges if provided)
    """
    stops = list(travel_times.keys())
    n = len(stops)
    
    if n == 0:
        return {}
    
    # Create stop index for fast lookup
    stop_idx = {s: i for i, s in enumerate(stops)}
    
    # Build numpy matrix for fast k-NN queries
    T = np.full((n, n), np.inf)
    for i, src in enumerate(stops):
        for dst, t in travel_times[src].items():
            if dst in stop_idx:
                T[i][stop_idx[dst]] = float(t)
    
    # Initialize sparse dict
    sparse_times = {stop: {} for stop in stops}
    
    # Add actual sequence edges (if provided)
    if actual_sequence:
        for a, b in zip(actual_sequence, actual_sequence[1:]):
            if a in travel_times and b in travel_times[a]:
                sparse_times[a][b] = travel_times[a][b]
    
    # Add k-NN edges for each node
    for i, src in enumerate(stops):
        # Get all destinations sorted by travel time
        candidates = []
        for j, dst in enumerate(stops):
            if i != j and T[i][j] < np.inf:
                candidates.append((T[i][j], dst))
        
        # Sort by travel time and keep top k
        candidates.sort()
        added = 0
        for travel_time, dst in candidates:
            if added >= k:
                break
            # Only add if not already present (from actual sequence)
            if dst not in sparse_times[src]:
                sparse_times[src][dst] = travel_time
                added += 1
    
    return sparse_times


def convert_dense_to_sparse(
    input_json: str,
    output_json: str,
    k: int = 4,
    sequences_json: Optional[str] = None,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Convert a dense travel times JSON file to sparse travel times JSON file.
    
    Args:
        input_json: Path to JSON file with dense travel times
        output_json: Path to save sparse travel times
        k: Number of nearest neighbors per node
        sequences_json: Optional path to JSON with actual sequences
    
    Returns:
        Dictionary mapping route_id -> sparse_travel_times (dict of dicts)
    """
    # Load travel times
    print(f"Loading dense travel times from {input_json}...")
    travel_times_data = load_json(input_json)
    
    # Load sequences if provided
    sequences = {}
    if sequences_json:
        print(f"Loading sequences from {sequences_json}...")
        sequences = load_json(sequences_json)
    
    # Convert each route to sparse travel times
    sparse_all = {}
    total = len(travel_times_data)
    
    print(f"Converting {total} routes to sparse (k={k})...")
    for idx, (route_id, travel_times) in enumerate(tqdm.tqdm(travel_times_data.items(), desc="Converting routes")):
        # Get actual sequence if available
        actual_seq = None
        if route_id in sequences:
            seq_data = sequences[route_id].get("actual", {})
            if seq_data:
                actual_seq = [stop for stop, order in sorted(seq_data.items(), key=lambda x: x[1])]
        
        # Build sparse travel times
        sparse_times = build_sparse_travel_times_from_dense(
            travel_times,
            k=k,
            actual_sequence=actual_seq,
        )
        
        if sparse_times:
            sparse_all[route_id] = sparse_times
        
        if (idx + 1) % max(1, total // 10) == 0:
            print(f"  {idx + 1}/{total} routes converted")
    
    print(f"Done. Converted {len(sparse_all)} routes.")
    
    # Save to JSON
    save_json(sparse_all, output_json)
    
    return sparse_all


def single_route_dense_to_sparse(
    travel_times: Dict[str, Dict[str, float]],
    k: int = 4,
    actual_sequence: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Convert a single dense travel time matrix to sparse format.
    
    Args:
        travel_times: Dict of dicts with dense travel times
        k: Number of nearest neighbors
        actual_sequence: Optional actual delivery sequence
    
    Returns:
        Dict of dicts with sparse travel times
    """
    return build_sparse_travel_times_from_dense(travel_times, k, actual_sequence)


def get_route_statistics(
    dense_times: Dict[str, Dict[str, float]],
    sparse_times: Dict[str, Dict[str, float]],
) -> dict:
    """
    Get statistics comparing dense and sparse graphs.
    
    Args:
        dense_times: Dense travel time matrix
        sparse_times: Sparse travel time matrix
    
    Returns:
        Dictionary with statistics
    """
    dense_edges = sum(len(v) for v in dense_times.values())
    sparse_edges = sum(len(v) for v in sparse_times.values())
    
    return {
        "nodes": len(dense_times),
        "dense_edges": dense_edges,
        "sparse_edges": sparse_edges,
        "reduction_ratio": round(100 * (1 - sparse_edges / max(dense_edges, 1)), 2),
        "compression": f"{sparse_edges}/{dense_edges}",
    }



if __name__ == "__main__":
    # Example 1: Batch convert from JSON files
    print("=" * 60)
    print("Example 1: Batch convert from JSON files")
    print("=" * 60)
    
    travel_times_file = r"./model_build_inputs/travel_times.json"
    # sequences_file = r"./model_build_inputs/actual_sequences.json"  # Optional
    output_file = r"./model_build_inputs/sparse_travel_times.json"
    
    sparse_all = convert_dense_to_sparse(
        input_json=travel_times_file,
        output_json=output_file,
        k=4,
        # sequences_json=sequences_file,
    )
    
    # Show stats for one route
    if sparse_all:
        route_id = next(iter(sparse_all))
        print(f"\nSample route: {route_id}")
        print(sparse_all[route_id])
    
    # Example 2: Single route conversion
    print("\n" + "=" * 60)
    print("Example 2: Single route conversion")
    print("=" * 60)
    
    # Sample dense travel times
    dense_sample = {
        "AA": {"AA": 0, "AC": 211.5, "AD": 258.7, "AJ": 244.9},
        "AC": {"AA": 219.3, "AC": 0, "AD": 233, "AJ": 235.7},
        "AD": {"AA": 250.1, "AC": 240.5, "AD": 0, "AJ": 100.2},
        "AJ": {"AA": 245.3, "AC": 230.1, "AD": 95.8, "AJ": 0},
    }
    
    sparse_sample = single_route_dense_to_sparse(dense_sample, k=2)
    
    print("Dense travel times:")
    for src, dests in dense_sample.items():
        print(f"  {src}: {dests}")
    
    print("\nSparse travel times (k=2):")
    for src, dests in sparse_sample.items():
        print(f"  {src}: {dests}")
    
    # Get statistics
    stats = get_route_statistics(dense_sample, sparse_sample)
    print("\nStatistics:")
    for key, val in stats.items():
        print(f"  {key}: {val}")
