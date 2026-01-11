from typing import Any, Dict, List, Tuple

import gurobipy as gp
from gurobipy import GRB


def build_model(inputs: Dict[str, Any]) -> Dict[str, Any]:
    model = gp.Model("mdvrpdw")

    nodes: List[str] = inputs["nodes"]
    depots: List[str] = inputs["depots"]
    teams: List[Dict[str, Any]] = inputs["teams"]
    travel_times: Dict[Tuple[str, str], float] = inputs["travel_times"]
    time_windows: Dict[str, Tuple[float, float]] = inputs["time_windows"]
    big_m: float = inputs["big_m"]
    severity: Dict[str, float] = inputs["severity"]
    tau: Dict[Tuple[str, str], float] = inputs["tau"]
    non_service_nodes: List[str] = inputs["non_service_nodes"]

    team_names = [team["name"] for team in teams]
    capacity = {team["name"]: team["capacity_hours"] for team in teams}

    arcs = [(i, j) for i in nodes for j in nodes if i != j]

    x = model.addVars(depots, team_names, arcs, vtype=GRB.BINARY, name="x")
    y = model.addVars(depots, team_names, nodes, vtype=GRB.BINARY, name="y")
    s = model.addVars(depots, team_names, nodes, vtype=GRB.CONTINUOUS, lb=0.0, name="s")
    u = model.addVars(depots, team_names, vtype=GRB.BINARY, name="u")
    p = model.addVars(depots, team_names, nodes, vtype=GRB.CONTINUOUS, lb=0.0, name="p")

    model.update()

    for node in nodes:
        model.addConstr(
            gp.quicksum(y[depot, team, node] for depot in depots for team in team_names) <= 1,
            name=f"single_restore_{node}",
        )

    for depot in depots:
        for team in team_names:
            model.addConstr(
                gp.quicksum(x[depot, team, depot, j] for j in nodes if j != depot) == u[depot, team],
                name=f"depart_{depot}_{team}",
            )
            model.addConstr(
                gp.quicksum(x[depot, team, i, depot] for i in nodes if i != depot) == u[depot, team],
                name=f"return_{depot}_{team}",
            )

    for depot in depots:
        for team in team_names:
            for node in nodes:
                if node == depot:
                    model.addConstr(y[depot, team, depot] <= u[depot, team], name=f"depot_repair_{depot}_{team}")
                    continue
                model.addConstr(
                    gp.quicksum(x[depot, team, j, node] for j in nodes if j != node) == y[depot, team, node],
                    name=f"in_link_{depot}_{team}_{node}",
                )
                model.addConstr(
                    gp.quicksum(x[depot, team, node, j] for j in nodes if j != node) == y[depot, team, node],
                    name=f"out_link_{depot}_{team}_{node}",
                )

                model.addConstr(y[depot, team, node] <= u[depot, team], name=f"assign_used_{depot}_{team}_{node}")

    for depot in depots:
        for team in team_names:
            model.addConstr(
                gp.quicksum(severity[node] * y[depot, team, node] for node in nodes)
                <= capacity[team] * u[depot, team],
                name=f"capacity_{depot}_{team}",
            )

    for depot in depots:
        for team in team_names:
            model.addConstr(s[depot, team, depot] == 0.0, name=f"anchor_{depot}_{team}")

    for depot in depots:
        for team in team_names:
            for (i, j) in arcs:
                model.addConstr(
                    s[depot, team, j]
                    >= s[depot, team, i]
                    + tau[(i, team)] * y[depot, team, i]
                    + travel_times[(i, j)]
                    - big_m * (1 - x[depot, team, i, j]),
                    name=f"time_prop_{depot}_{team}_{i}_{j}",
                )

    for depot in depots:
        for team in team_names:
            for node in nodes:
                earliest, latest = time_windows[node]
                model.addConstr(
                    s[depot, team, node] >= earliest - big_m * (1 - y[depot, team, node]),
                    name=f"time_lb_{depot}_{team}_{node}",
                )
                model.addConstr(
                    s[depot, team, node] + tau[(node, team)] * y[depot, team, node]
                    <= latest + big_m * (1 - y[depot, team, node]),
                    name=f"time_ub_{depot}_{team}_{node}",
                )

    n_nodes = len(nodes)
    for depot in depots:
        for team in team_names:
            for node in nodes:
                if node == depot:
                    model.addConstr(p[depot, team, depot] == 0.0, name=f"mtz_anchor_{depot}_{team}")
                    continue
                model.addConstr(p[depot, team, node] <= n_nodes * y[depot, team, node], name=f"mtz_ub_{depot}_{team}_{node}")
                model.addConstr(p[depot, team, node] >= y[depot, team, node], name=f"mtz_lb_{depot}_{team}_{node}")

            for i in nodes:
                if i == depot:
                    continue
                for j in nodes:
                    if j == depot or j == i:
                        continue
                    model.addConstr(
                        p[depot, team, i] - p[depot, team, j] + n_nodes * x[depot, team, i, j] <= n_nodes - 1,
                        name=f"mtz_{depot}_{team}_{i}_{j}",
                    )

    for node in non_service_nodes:
        for depot in depots:
            for team in team_names:
                model.addConstr(y[depot, team, node] == 0, name=f"no_service_{depot}_{team}_{node}")

    return {
        "model": model,
        "x": x,
        "y": y,
        "s": s,
        "u": u,
        "p": p,
        "arcs": arcs,
    }
