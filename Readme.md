# TSP Eval-1 — Optimized Edge Importance with LKH

Computes **Eval-1 ground-truth edge importance** for TSP instances derived from
the Amazon Last Mile Routing dataset, using the LKH-3 solver throughout.

```
I_e = (C(G \ e) - C(G)) / C(G)
```

---

## Directory Structure

```
tsp_eval1/
├── config.py        # Solver parameters, parallelism, paths
├── tsplib_io.py     # TSPLIB file writer + LKH tour parser
├── lkh_runner.py    # LKH subprocess wrapper + solve_tsp()
├── eval1.py         # Parallel Eval-1 computation
├── pipeline.py      # Top-level orchestration (single + batch)
├── requirements.txt
└── tmp/             # Auto-created; holds intermediate files
```

---

## Prerequisites

1. **Python 3.10+** (uses `str | None` union syntax).
2. **LKH-3 binary** — build from source:
   ```
   wget http://webhotel4.ruc.dk/~keld/research/LKH-3/LKH-3.0.9.tgz
   tar xvfz LKH-3.0.9.tgz && cd LKH-3.0.9 && make
   sudo cp LKH /usr/local/bin/
   ```
3. Set `LKH_PATH` in `config.py` (or export `LKH_PATH=/path/to/LKH` in shell).

---

## Usage

### Single instance
```python
from pipeline import run_instance

result = run_instance(
    station_code="DAX_123",
    nodes=list(range(n)),
    distance_matrix=my_matrix,   # n×n list-of-lists, large finite for missing edges
)

# result["edge_importance"] → { "u,v": importance_float, … }
```

### Batch
```python
from pipeline import run_batch

instances = [
    {"station_code": "S1", "nodes": [...], "distance_matrix": [...]},
    {"station_code": "S2", "nodes": [...], "distance_matrix": [...]},
]
results = run_batch(instances)
```

### CLI smoke-test (10-node synthetic)
```bash
python pipeline.py
```

---

## Design Decisions

| Decision | Rationale |
|---|---|
| `EDGE_WEIGHT_FORMAT = FULL_MATRIX` | Matrix is already sparse-encoded with large finite values; no edge list needed |
| `INITIAL_TOUR_FILE` on every perturbed run | Warm-start cuts convergence from hundreds to ~100 trials |
| `PENALTY = 7 × max(matrix)` | Dominant without causing 32-bit LKH overflow (capped at 2 × 10⁹) |
| `ProcessPoolExecutor` per edge | Embarrassingly parallel; one perturbed solve per worker |
| `NUM_WORKERS = cpu_count() - 1` | Leaves one core free to avoid OS thrashing |
| Row-slice copy for perturbation | Avoids full n² deep-copy; only two rows change per edge |
| Sequential instance processing | Keeps intra-instance parallelism clean; avoids CPU contention |

---

## Output

`run_instance()` returns:
```json
{
  "station_code": "DAX_123",
  "base_cost": 1234.0,
  "base_route": [0, 3, 7, ...],
  "edge_importance": {
    "0,3": 0.042,
    "3,7": 0.015,
    ...
  }
}
```

Results are also written to `tmp/<station_code>/<station_code>_eval1.json`.
