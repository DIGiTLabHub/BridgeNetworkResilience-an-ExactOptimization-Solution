from typing import Any, Dict, List

import gurobipy as gp
from gurobipy import GRB

from mdvrpdw.data import load_inputs
from mdvrpdw.depots import select_depots
from mdvrpdw.model import build_model


def _apply_solver_params(model: gp.Model, solver_config: Dict[str, Any]) -> None:
    if solver_config.get("time_limit") is not None:
        model.setParam(GRB.Param.TimeLimit, solver_config["time_limit"])
    if solver_config.get("mip_gap") is not None:
        model.setParam(GRB.Param.MIPGap, solver_config["mip_gap"])
    if solver_config.get("threads") is not None:
        model.setParam(GRB.Param.Threads, solver_config["threads"])
    if solver_config.get("output_flag") is not None:
        model.setParam(GRB.Param.OutputFlag, solver_config["output_flag"])
    if solver_config.get("log_to_console") is not None:
        model.setParam(GRB.Param.LogToConsole, solver_config["log_to_console"])
    if solver_config.get("log_file"):
        model.setParam(GRB.Param.LogFile, solver_config["log_file"])
    if solver_config.get("display_interval") is not None:
        model.setParam(GRB.Param.DisplayInterval, solver_config["display_interval"])


def _build_resilience_expr(inputs: Dict[str, Any], y_vars: gp.tupledict) -> gp.LinExpr:
    nodes: List[str] = inputs["nodes"]
    depots = inputs["depots"]
    teams = inputs["teams"]
    delta_xi = inputs["delta_xi"]

    expr = gp.LinExpr()
    for node in nodes:
        for depot in depots:
            for team in teams:
                expr.add(y_vars[depot, team["name"], node], delta_xi[(node, team["name"])])
    return expr


def _build_cost_expr(inputs: Dict[str, Any], y_vars: gp.tupledict) -> gp.LinExpr:
    costs = inputs["costs"]
    depots = inputs["depots"]
    teams = inputs["teams"]
    nodes = inputs["nodes"]

    expr = gp.LinExpr()
    for node in nodes:
        for depot in depots:
            for team in teams:
                expr.add(y_vars[depot, team["name"], node], costs[(node, team["name"])])
    return expr


def _extract_solution(
    model_bundle: Dict[str, Any],
    model: gp.Model,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    solution = {
        "status": model.Status,
        "objective": model.ObjVal if model.SolCount else None,
    }
    if not model.SolCount:
        return solution

    nodes = inputs["nodes"]
    depots = inputs["depots"]
    teams = inputs["teams"]

    x_vars = model_bundle["x"]
    y_vars = model_bundle["y"]
    s_vars = model_bundle["s"]
    u_vars = model_bundle["u"]
    arcs = model_bundle["arcs"]

    teams_used = []
    repairs = []
    arcs_used = []
    start_times = []

    for depot in depots:
        for team in teams:
            name = team["name"]
            if u_vars[depot, name].X > 0.5:
                teams_used.append({"depot": depot, "team": name})
            for node in nodes:
                if y_vars[depot, name, node].X > 0.5:
                    repairs.append({"depot": depot, "team": name, "bridge": node})
                    start_times.append({"depot": depot, "team": name, "bridge": node, "start": s_vars[depot, name, node].X})
            for (i, j) in arcs:
                if x_vars[depot, name, i, j].X > 0.5:
                    arcs_used.append({"depot": depot, "team": name, "from": i, "to": j})

    solution["teams_used"] = teams_used
    solution["repairs"] = repairs
    solution["arcs"] = arcs_used
    solution["start_times"] = start_times
    solution["resilience"] = None
    solution["cost"] = None
    return solution


def solve_mdvrpdw(config: Dict[str, Any]) -> Dict[str, Any]:
    inputs = load_inputs(config)

    nodes = inputs["nodes"]
    max_depots = 1
    if len(nodes) <= 5:
        max_depots = 1
    elif len(nodes) <= 15:
        max_depots = 2
    elif len(nodes) <= 30:
        max_depots = 3
    else:
        raise ValueError("Bridge count exceeds 30. Reduce selection.")

    depots = select_depots(inputs["graph"], nodes, max_depots)
    inputs["depots"] = depots

    model_bundle = build_model(inputs)
    model = model_bundle["model"]
    y_vars = model_bundle["y"]

    solver_config = config.get("solver", {})
    _apply_solver_params(model, solver_config)

    resilience_expr = _build_resilience_expr(inputs, y_vars)
    cost_expr = _build_cost_expr(inputs, y_vars)

    epsilon_values = solver_config.get("epsilon_values")
    results = []

    if epsilon_values:
        for epsilon in epsilon_values:
            constraint = model.addConstr(cost_expr <= epsilon, name=f"epsilon_{epsilon}")
            model.setObjective(resilience_expr, GRB.MAXIMIZE)
            model.optimize()
            result = _extract_solution(model_bundle, model, inputs)
            result["epsilon"] = epsilon
            if model.SolCount:
                result["resilience"] = resilience_expr.getValue()
                result["cost"] = cost_expr.getValue()
            results.append(result)
            model.remove(constraint)
            model.update()
        return {"solutions": results}

    model.setObjective(resilience_expr, GRB.MAXIMIZE)
    model.optimize()
    result = _extract_solution(model_bundle, model, inputs)
    if model.SolCount:
        result["resilience"] = resilience_expr.getValue()
        result["cost"] = cost_expr.getValue()
    return result
