from typing import Any, Dict, List, Tuple

import gurobipy as gp
from gurobipy import GRB


def build_model(inputs: Dict[str, Any]) -> Dict[str, Any]:
    model = gp.Model("mdvrpdw")

    nodes: List[str] = inputs["nodes"]
    service_nodes: List[str] = inputs["service_nodes"]
    depots: List[str] = inputs["depots"]
    teams: List[Dict[str, Any]] = inputs["teams"]
    travel_times: Dict[Tuple[str, str], float] = inputs["travel_times"]
    time_windows: Dict[str, Tuple[float, float]] = inputs["time_windows"]
    big_m: float = inputs["big_m"]
    severity: Dict[str, float] = inputs["severity"]

    team_names = [team["name"] for team in teams]

    x = {}
    for depot in depots:
        for team in team_names:
            for i in nodes:
                for j in nodes:
                    if i == j and not (i == depot and i in service_nodes):
                        continue
                    if i == j and i != depot:
                        continue
                    x[(depot, team, i, j)] = model.addVar(vtype=GRB.BINARY, name=f"x_{depot}_{team}_{i}_{j}")

    y = {
        (depot, team, node): model.addVar(vtype=GRB.BINARY, name=f"y_{depot}_{team}_{node}")
        for depot in depots
        for team in team_names
        for node in service_nodes
    }

    s = {
        (depot, team, node): model.addVar(vtype=GRB.CONTINUOUS, lb=0.0, name=f"s_{depot}_{team}_{node}")
        for depot in depots
        for team in team_names
        for node in service_nodes
    }

    u = {
        (depot, team): model.addVar(vtype=GRB.BINARY, name=f"u_{depot}_{team}")
        for depot in depots
        for team in team_names
    }

    model.update()

    for node in service_nodes:
        model.addConstr(
            gp.quicksum(y[(depot, team, node)] for depot in depots for team in team_names) <= 1,
            name=f"single_restore_{node}",
        )

    for node in service_nodes:
        for depot in depots:
            for team in team_names:
                model.addConstr(
                    gp.quicksum(
                        x[(depot, team, node, j)]
                        for j in nodes
                        if (depot, team, node, j) in x
                    )
                    == y[(depot, team, node)],
                    name=f"out_link_{depot}_{team}_{node}",
                )

    for node in service_nodes:
        for depot in depots:
            for team in team_names:
                if node == depot:
                    continue
                model.addConstr(
                    gp.quicksum(
                        x[(depot, team, j, node)]
                        for j in nodes
                        if (depot, team, j, node) in x
                    )
                    == y[(depot, team, node)],
                    name=f"in_link_{depot}_{team}_{node}",
                )

    for depot in depots:
        for team in team_names:
            model.addConstr(
                gp.quicksum(
                    x[(depot, team, depot, j)]
                    for j in nodes
                    if (depot, team, depot, j) in x
                )
                == u[(depot, team)],
                name=f"depart_{depot}_{team}",
            )
            model.addConstr(
                gp.quicksum(
                    x[(depot, team, i, depot)]
                    for i in nodes
                    if (depot, team, i, depot) in x
                )
                == u[(depot, team)],
                name=f"return_{depot}_{team}",
            )

    service_time = {team["name"]: team["service_hours"] for team in teams}
    capacity = {team["name"]: team["capacity_hours"] for team in teams}

    for depot in depots:
        for team in team_names:
            for node in service_nodes:
                earliest, latest = time_windows[node]
                model.addConstr(s[(depot, team, node)] >= earliest, name=f"time_lb_{depot}_{team}_{node}")
                model.addConstr(
                    s[(depot, team, node)] + service_time[team] <= latest,
                    name=f"time_ub_{depot}_{team}_{node}",
                )

    for depot in depots:
        for team in team_names:
            for i in service_nodes:
                for j in service_nodes:
                    if i == j:
                        continue
                    if (depot, team, i, j) not in x:
                        continue
                    model.addConstr(
                        s[(depot, team, j)]
                        >= s[(depot, team, i)]
                        + service_time[team]
                        + travel_times[(i, j)]
                        - big_m * (1 - x[(depot, team, i, j)]),
                        name=f"time_prop_{depot}_{team}_{i}_{j}",
                    )

            for j in service_nodes:
                if (depot, team, depot, j) not in x:
                    continue
                model.addConstr(
                    s[(depot, team, j)]
                    >= travel_times.get((depot, j), 0.0)
                    - big_m * (1 - x[(depot, team, depot, j)]),
                    name=f"time_start_{depot}_{team}_{j}",
                )

    for depot in depots:
        for team in team_names:
            model.addConstr(
                gp.quicksum(severity[node] * y[(depot, team, node)] for node in service_nodes)
                <= capacity[team],
                name=f"capacity_{depot}_{team}",
            )

    return {
        "model": model,
        "x": x,
        "y": y,
        "s": s,
        "u": u,
    }
