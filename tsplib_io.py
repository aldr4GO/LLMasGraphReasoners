# tsplib_io.py
# Handles all TSPLIB format I/O: writing .tsp files and reading LKH tour files.

import os
from typing import List


def write_tsplib(matrix: List[List[float]], filename: str, name: str = "TSP") -> None:
    """
    Write a symmetric distance matrix to a TSPLIB FULL_MATRIX file.

    Args:
        matrix:   n×n distance matrix (Python list-of-lists or numpy 2D array).
        filename: Destination .tsp file path.
        name:     Optional NAME field in the header.

    Notes:
        - Values are rounded to integers; LKH requires integer edge weights.
        - The matrix must already encode unavailable edges as large finite values.
          Do NOT pass inf or NaN.
    """
    n = len(matrix)

    with open(filename, "w") as f:
        # ── Header ────────────────────────────────────────────────────────────
        f.write(f"NAME: {name}\n")
        f.write("TYPE: TSP\n")
        f.write(f"DIMENSION: {n}\n")
        f.write("EDGE_WEIGHT_TYPE: EXPLICIT\n")
        f.write("EDGE_WEIGHT_FORMAT: FULL_MATRIX\n")
        f.write("EDGE_WEIGHT_SECTION\n")

        # ── Matrix body ───────────────────────────────────────────────────────
        # Each row on its own line; values are space-separated integers.
        for row in matrix:
            f.write(" ".join(str(int(round(v))) for v in row) + "\n")

        f.write("EOF\n")


def write_lkh_par(
    tsplib_file: str,
    tour_file: str,
    output_file: str,
    initial_tour: str | None = None,
    runs: int = 1,
    max_trials: int = 100,
) -> None:
    """
    Write an LKH .par parameter file.

    Args:
        tsplib_file:   Path to the .tsp input file.
        tour_file:     Path where LKH writes the best tour.
        output_file:   Path for the LKH output/log file.
        initial_tour:  Optional path to a .tour file used as warm start.
        runs:          Number of LKH restarts (keep at 1 for speed).
        max_trials:    Maximum number of trials per run.
    """
    with open(output_file, "w") as f:
        f.write(f"PROBLEM_FILE = {tsplib_file}\n")
        f.write(f"TOUR_FILE = {tour_file}\n")
        f.write(f"RUNS = {runs}\n")
        f.write(f"MAX_TRIALS = {max_trials}\n")
        # Suppress verbose LKH console output
        f.write("TRACE_LEVEL = 0\n")
        if initial_tour is not None and os.path.isfile(initial_tour):
            f.write(f"INITIAL_TOUR_FILE = {initial_tour}\n")


def parse_lkh_tour(tour_file: str) -> List[int]:
    """
    Parse an LKH TOUR_SECTION output file and return a 0-indexed node list.

    LKH writes 1-indexed nodes; we convert to 0-indexed.
    The returned list does NOT repeat the depot (i.e. length == n).

    Args:
        tour_file: Path to the LKH-generated .tour file.

    Returns:
        List of node indices representing the tour (0-indexed, open path).

    Raises:
        FileNotFoundError: If the tour file does not exist.
        ValueError:        If the expected section is missing.
    """
    if not os.path.isfile(tour_file):
        raise FileNotFoundError(f"LKH tour file not found: {tour_file}")

    route: List[int] = []
    in_section = False

    with open(tour_file, "r") as f:
        for line in f:
            line = line.strip()
            if line == "TOUR_SECTION":
                in_section = True
                continue
            if in_section:
                if line in ("-1", "EOF"):
                    break
                route.append(int(line) - 1)   # convert 1-indexed → 0-indexed

    if not route:
        raise ValueError(f"No tour data found in: {tour_file}")

    return route
