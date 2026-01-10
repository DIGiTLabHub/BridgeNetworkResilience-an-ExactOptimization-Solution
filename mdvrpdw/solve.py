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


def _build_resilience_expr(inputs: Dict[str, Any], y_vars: Dict[Any, Any]) -> gp.LinExpr:
    nodes: List[str] = inputs["nodes"]
    service_nodes: List[str] = inputs["service_nodes"]
    bfi = inputs["bfi"]
    teams = inputs["teams"]
    depots = inputs["depots"]

    base_resilience = sum(bfi[node] for node in nodes) / len(nodes)
    expr = gp.LinExpr(base_resilience)

    for node in service_nodes:
        for depot in depots:
            for team in teams:
                delta = team["delta"]
                coeff = (min(1.0, bfi[node] + delta) - bfi[node]) / len(nodes)
                expr.add(y_vars[(depot, team["name"], node)], coeff)
    return expr


def _build_cost_expr(inputs: Dict[str, Any], y_vars: Dict[Any, Any]) -> gp.LinExpr:
    costs = inputs["costs"]
    depots = inputs["depots"]
    teams = inputs["teams"]
    service_nodes = inputs["service_nodes"]

    expr = gp.LinExpr()
    for node in service_nodes:
        for depot in depots:
            for team in teams:
                expr.add(y_vars[(depot, team["name"], node)], costs[(node, team["name"])])
    return expr


def _extract_solution(inputs: Dict[str, Any], model: gp.Model, y_vars: Dict[Any, Any]) -> Dict[str, Any]:
    solution = {
        "status": model.Status,
        "objective": model.ObjVal if model.SolCount else None,
    }
    if not model.SolCount:
        return solution

    assigned = []
    for (depot, team, node), var in y_vars.items():
        if var.X > 0.5:
            assigned.append({"depot": depot, "team": team, "bridge": node})
    solution["assignments"] = assigned
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
            result = _extract_solution(inputs, model, y_vars)
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
    result = _extract_solution(inputs, model, y_vars)
    if model.SolCount:
        result["resilience"] = resilience_expr.getValue()
        result["cost"] = cost_expr.getValue()
    return result
