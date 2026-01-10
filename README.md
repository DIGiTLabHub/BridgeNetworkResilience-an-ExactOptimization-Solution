# MD-VRPDW (Bridge-Node) Optimization

This project implements a **multi-depot VRPTW** on a bridge-node graph with **bi-objective MILP** (maximize resilience, minimize cost). The solver uses **exact Gurobi MILP optimization** (branch-and-bound/branch-and-cut), not heuristic methods.

## Requirements
- Python 3.10+
- Gurobi Optimizer + `gurobipy`
- Dependencies in `requirements.txt`

## Layout
- `mdvrpdw/` core modules
- `scripts/run_mdvrpdw.py` single-run entry
- `scripts/run_sensitivity.py` parameter sweep runner
- `MD-VRPDW-design.md` formulation and assumptions

## Run (single config)
```
python scripts/run_mdvrpdw.py --config base-config.json --output outputs/solution.json
```

## Run (sensitivity sweep)
```
python scripts/run_sensitivity.py --base-config base-config.json --param-grid param-grid.json --output outputs/sweep.json
```

## Notes
- Depots are bridge nodes; MoDOT can be excluded from service.
- Team types: RRU, ERT, CIRS (one per depot).
- Capacity `Q_k` is a total-horizon workload cap.
