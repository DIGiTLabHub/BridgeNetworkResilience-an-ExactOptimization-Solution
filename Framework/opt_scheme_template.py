```python
"""
Bridge-only repair routing with repairable depot bridges, workload capacity,
time windows, and closed tours (start/end at depot).

Minimal, solver-ready Gurobi template.
- Sets: V bridges, D subset of V are depots (repairable), K team types
- Teams are (d,k) pairs (one team of each type at each depot). Extend as needed.
- Each team must return to its depot if used.
- Each bridge repaired at most once (by any team).
- Workload capacity per team: sum_i q[i] y[d,k,i] <= Q[k] * u[d,k]
- Time precedence: s[j] >= s[i] + tau[i,k]*y[i] + eta[i,j] - M*(1-x[i,j])
- Time windows activated only if repaired.
- MTZ subtour elimination.

Fill the DATA section with your instance.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

import gurobipy as gp
from gurobipy import GRB


def build_and_solve(
    V: List[str],
    D: List[str],
    K: List[str],
    eta: Dict[Tuple[str, str], float],
    a: Dict[str, float],
    b: Dict[str, float],
    q: Dict[str, float],
    Q: Dict[str, float],
    tau: Dict[Tuple[str, str], float],  # (i,k) -> service duration
    delta_xi: Dict[Tuple[str, str], float],  # (i,k) -> resilience gain
    epsilon_cost: float | None = None,
    c: Dict[Tuple[str, str], float] | None = None,  # (i,k) -> cost (optional)
    time_limit_s: int = 300,
    mip_gap: float = 0.01,
):
    assert set(D).issubset(set(V)), "D must be subset of V"
    assert all((i, j) in eta for i in V for j in V if i != j), "eta missing pairs"
    assert all(i in a and i in b for i in V), "time windows missing"
    assert all(i in q for i in V), "workload q missing"
    assert all(k in Q for k in K), "capacity Q missing"

    # Teams = all (depot, type) pairs
    Teams = [(d, k) for d in D for k in K]

    # Feasible arcs: all ordered pairs i!=j (you can prune by distance/time)
    A = [(i, j) for i in V for j in V if i != j]

    # Big-M: tight-ish upper bound for times
    max_eta = max(eta[i, j] for (i, j) in A) if A else 0.0
    max_tau = max(tau[i, k] for i in V for k in K)
    # Rough horizon bound: latest deadline or sum of largest times (conservative)
    H = max(b.values())
    M = H + max_eta + max_tau + 1.0

    m = gp.Model("bridge_repair_routing")

    # -------------------------
    # Variables
    # -------------------------
    x = m.addVars(Teams, A, vtype=GRB.BINARY, name="x")         # travel arcs
    y = m.addVars(Teams, V, vtype=GRB.BINARY, name="y")         # repair decision
    s = m.addVars(Teams, V, vtype=GRB.CONTINUOUS, lb=0.0, name="s")  # start times
    u = m.addVars(Teams, vtype=GRB.BINARY, name="u")            # team used

    # MTZ order vars: defined for i != depot (we'll still create for all, constrain as needed)
    p = m.addVars(Teams, V, vtype=GRB.CONTINUOUS, lb=0.0, name="p")

    # -------------------------
    # Core constraints
    # -------------------------

    # (C0) No self-arcs implicitly (A excludes i==j). If you allow self-arcs, add x==0 constraints.

    # (C1) Each bridge repaired at most once (across all teams)
    for i in V:
        m.addConstr(gp.quicksum(y[d, k, i] for (d, k) in Teams) <= 1, name=f"once[{i}]")

    # (C2) Closed tour start/end at depot, if used
    for (d, k) in Teams:
        m.addConstr(gp.quicksum(x[d, k, d, j] for j in V if j != d) == u[d, k], name=f"start[{d},{k}]")
        m.addConstr(gp.quicksum(x[d, k, i, d] for i in V if i != d) == u[d, k], name=f"end[{d},{k}]")

    # (C3) Flow-repair linking for non-depot nodes (i != d)
    for (d, k) in Teams:
        for i in V:
            if i == d:
                # Depot can be repaired without extra degree beyond start/end; just bind to usage:
                m.addConstr(y[d, k, d] <= u[d, k], name=f"depot_repair_used[{d},{k}]")
                continue
            m.addConstr(
                gp.quicksum(x[d, k, j, i] for j in V if j != i) == y[d, k, i],
                name=f"in_deg[{d},{k},{i}]",
            )
            m.addConstr(
                gp.quicksum(x[d, k, i, j] for j in V if j != i) == y[d, k, i],
                name=f"out_deg[{d},{k},{i}]",
            )

    # (C4) Workload capacity per team (your constraint)
    for (d, k) in Teams:
        m.addConstr(
            gp.quicksum(q[i] * y[d, k, i] for i in V) <= Q[k] * u[d, k],
            name=f"work_cap[{d},{k}]",
        )

    # (C5) Depot time anchor: s[d]=0
    for (d, k) in Teams:
        m.addConstr(s[d, k, d] == 0.0, name=f"anchor_time[{d},{k}]")

    # (C6) Time precedence along arcs: service at i (if repaired) + travel to j
    for (d, k) in Teams:
        for (i, j) in A:
            m.addConstr(
                s[d, k, j] >= s[d, k, i] + tau[i, k] * y[d, k, i] + eta[i, j] - M * (1 - x[d, k, i, j]),
                name=f"time[{d},{k},{i}->{j}]",
            )

    # (C7) Time windows activated only if repaired
    for (d, k) in Teams:
        for i in V:
            m.addConstr(
                s[d, k, i] >= a[i] - M * (1 - y[d, k, i]),
                name=f"tw_start[{d},{k},{i}]",
            )
            m.addConstr(
                s[d, k, i] + tau[i, k] * y[d, k, i] <= b[i] + M * (1 - y[d, k, i]),
                name=f"tw_end[{d},{k},{i}]",
            )

    # (C8) MTZ subtour elimination per team
    nV = len(V)
    for (d, k) in Teams:
        for i in V:
            if i == d:
                # Optional: fix depot order to 0
                m.addConstr(p[d, k, d] == 0.0, name=f"mtz_p_depot[{d},{k}]")
                continue
            # bind p to visit: if not repaired, p can be 0; if repaired, p in [1, nV]
            m.addConstr(p[d, k, i] <= nV * y[d, k, i], name=f"mtz_bind_ub[{d},{k},{i}]")
            m.addConstr(p[d, k, i] >= 1.0 * y[d, k, i], name=f"mtz_bind_lb[{d},{k},{i}]")

        for i in V:
            if i == d:
                continue
            for j in V:
                if j == d or j == i:
                    continue
                # Standard MTZ: p_i - p_j + nV * x_{i,j} <= nV - 1
                m.addConstr(
                    p[d, k, i] - p[d, k, j] + nV * x[d, k, i, j] <= nV - 1,
                    name=f"mtz[{d},{k},{i},{j}]",
                )

    # (Optional) Cost budget (epsilon-constraint)
    if epsilon_cost is not None:
        if c is None:
            raise ValueError("Provide cost dict c[(i,k)] if epsilon_cost is set.")
        m.addConstr(
            gp.quicksum(c[i, k] * y[d, k, i] for (d, k) in Teams for i in V) <= float(epsilon_cost),
            name="cost_budget",
        )

    # -------------------------
    # Objective: maximize resilience gain
    # -------------------------
    m.setObjective(
        gp.quicksum(delta_xi[i, k] * y[d, k, i] for (d, k) in Teams for i in V),
        GRB.MAXIMIZE,
    )

    # -------------------------
    # Solver params
    # -------------------------
    m.Params.TimeLimit = time_limit_s
    m.Params.MIPGap = mip_gap
    m.Params.OutputFlag = 1

    m.optimize()

    # -------------------------
    # Extract solution (if feasible)
    # -------------------------
    if m.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT, GRB.SUBOPTIMAL):
        print(f"Solver status: {m.Status}")
        return None

    sol = {
        "obj": m.ObjVal if m.SolCount > 0 else None,
        "teams_used": [],
        "repairs": [],
        "arcs": [],
        "start_times": [],
    }

    for (d, k) in Teams:
        if u[d, k].X > 0.5:
            sol["teams_used"].append((d, k))
            # repaired nodes by this team
            for i in V:
                if y[d, k, i].X > 0.5:
                    sol["repairs"].append((d, k, i))
                    sol["start_times"].append((d, k, i, s[d, k, i].X))
            # arcs used
            for (i, j) in A:
                if x[d, k, i, j].X > 0.5:
                    sol["arcs"].append((d, k, i, j))

    return sol


def main():
    # =========================================================
    # DATA (replace with your instance)
    # =========================================================
    V = ["B1", "B2", "B3", "B4", "B5"]
    D = ["B1"]  # depot bridges (subset of V) -- repairable
    K = ["RRU", "ERT"]

    # Travel times between all distinct pairs (bridge-only graph)
    eta = {}
    for i in V:
        for j in V:
            if i == j:
                continue
            # Example: symmetric travel time based on index distance
            eta[i, j] = abs(V.index(i) - V.index(j)) + 0.5

    # Time windows
    a = {i: 0.0 for i in V}
    b = {i: 10.0 for i in V}

    # Workload proxy
    q = {i: 1.0 for i in V}
    q["B4"] = 2.0

    # Capacity per team type (workload units over horizon)
    Q = {"RRU": 3.0, "ERT": 4.0}

    # Service durations tau[i,k] (choose consistent with q if desired)
    # Example: tau = q (1 day per workload unit) for both types
    tau = {(i, k): q[i] for i in V for k in K}

    # Resilience gain delta_xi[i,k]
    # Example: RRU gives 0.2, ERT gives 0.35
    delta_xi = {}
    for i in V:
        for k in K:
            delta_xi[i, k] = 0.2 if k == "RRU" else 0.35

    # Optional costs and epsilon budget
    c = {(i, k): (1.0 if k == "RRU" else 2.0) * (1.0 + 0.5 * q[i]) for i in V for k in K}
    epsilon_cost = None  # set e.g. 8.0 to enable cost budget

    # =========================================================
    # Solve
    # =========================================================
    sol = build_and_solve(
        V=V,
        D=D,
        K=K,
        eta=eta,
        a=a,
        b=b,
        q=q,
        Q=Q,
        tau=tau,
        delta_xi=delta_xi,
        epsilon_cost=epsilon_cost,
        c=c,
        time_limit_s=60,
        mip_gap=0.01,
    )

    if sol is None:
        return

    print("\n=== Solution Summary ===")
    print("Objective:", sol["obj"])
    print("Teams used:", sol["teams_used"])
    print("Repairs (d,k,i):", sol["repairs"])
    print("Arcs (d,k,i,j):", sol["arcs"])
    print("Start times (d,k,i,s):", sorted(sol["start_times"], key=lambda t: (t[0], t[1], t[3])))


if __name__ == "__main__":
    main()
```

