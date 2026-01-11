from typing import Any, Dict, Iterable, List, Tuple

import os
import numpy as np
import pandas as pd
import networkx as nx
import pickle


def _read_graph(path: str) -> nx.Graph:
    with open(path, "rb") as handle:
        return pickle.load(handle)


def _sample_nodes(nodes: List[str], keep_nodes: Iterable[str], max_nodes: int, random_state: int) -> List[str]:
    rng = np.random.default_rng(random_state)
    keep_set = list(keep_nodes)
    pool = [node for node in nodes if node not in keep_set]
    if max_nodes >= len(nodes):
        return nodes
    sample_size = max_nodes - len(keep_set)
    if sample_size <= 0:
        return keep_set
    sampled = rng.choice(pool, size=sample_size, replace=False)
    return list(keep_set) + list(sampled)


def _compute_travel_times(
    graph: nx.Graph,
    nodes: List[str],
    speed_mps: float,
    time_scale: float,
    no_path_penalty: float,
) -> Dict[Tuple[str, str], float]:
    travel_times: Dict[Tuple[str, str], float] = {}
    for source in nodes:
        lengths = nx.single_source_dijkstra_path_length(graph, source, weight="highway_distance")
        for target in nodes:
            if source == target:
                continue
            distance = lengths.get(target)
            if distance is None:
                travel_times[(source, target)] = no_path_penalty
                continue
            travel_times[(source, target)] = (distance / speed_mps) / 3600 * time_scale
    return travel_times


def _compute_severity(df: pd.DataFrame, bridge_ids: Iterable[str], config: Dict[str, Any]) -> Dict[str, float]:
    column = config["severity"]["source_column"]
    max_rating = float(config["severity"]["max_rating"])
    scale = float(config["severity"]["q_i_scale"])
    min_value = float(config["severity"]["q_i_min"])

    severity = {}
    for bridge_id in bridge_ids:
        row = df.loc[df["Bridge #"] == bridge_id]
        if row.empty or column not in row:
            severity[bridge_id] = min_value
            continue
        rating = float(row.iloc[0][column])
        value = max_rating - rating
        severity[bridge_id] = max(min_value, value * scale)
    return severity


def _compute_bfi(df: pd.DataFrame, bridge_ids: Iterable[str], config: Dict[str, Any]) -> Dict[str, float]:
    column = config["severity"]["source_column"]
    max_rating = float(config["severity"]["max_rating"])
    scale = float(config["resilience"]["bfi_scale"])
    bfi = {}
    for bridge_id in bridge_ids:
        row = df.loc[df["Bridge #"] == bridge_id]
        if row.empty or column not in row:
            bfi[bridge_id] = min(1.0, scale)
            continue
        rating = float(row.iloc[0][column])
        value = rating / max_rating
        bfi[bridge_id] = min(1.0, max(0.0, value * scale))
    return bfi


def _compute_time_windows(
    node_ids: Iterable[str],
    horizon_hours: float,
    window_length_hours: float,
    window_slack_hours: float,
    window_scale: float,
) -> Dict[str, Tuple[float, float]]:
    windows = {}
    window_length = window_length_hours * window_scale
    latest_finish = min(horizon_hours, window_length + window_slack_hours)
    for node_id in node_ids:
        windows[node_id] = (0.0, latest_finish)
    return windows


def load_inputs(config: Dict[str, Any]) -> Dict[str, Any]:
    paths = config["paths"]
    graph_path = paths.get("subgraph_file")
    if graph_path and os.path.exists(graph_path):
        graph = _read_graph(graph_path)
    else:
        graph = _read_graph(paths["graph_file"])
    df = pd.read_excel(paths["data_file"])

    nodes = list(graph.nodes)
    modot_present = "MoDOT" in nodes

    num_bridges = config["selection"]["num_bridges"]
    random_state = int(config["selection"]["random_state"])

    if num_bridges is not None:
        keep_nodes = ["MoDOT"] if modot_present else []
        nodes = _sample_nodes(nodes, keep_nodes, num_bridges + len(keep_nodes), random_state)

    travel_times = _compute_travel_times(
        graph,
        nodes,
        float(config["travel"]["speed_mps"]),
        float(config["travel"]["time_scale"]),
        float(config["time"]["horizon_hours"]),
    )

    exclude_modot = config["selection"]["exclude_modot_from_service"]
    non_service_nodes = [node for node in nodes if exclude_modot and node == "MoDOT"]
    service_nodes = [node for node in nodes if node not in non_service_nodes]

    severity = _compute_severity(df, service_nodes, config)
    bfi = _compute_bfi(df, nodes, config)

    for node in non_service_nodes:
        severity[node] = 0.0

    time_windows = _compute_time_windows(
        nodes,
        float(config["time"]["horizon_hours"]),
        float(config["time"]["window_length_hours"]),
        float(config["time"]["window_slack_hours"]),
        float(config["time"]["window_scale"]),
    )

    teams = []
    capacity_scale = float(config.get("capacity", {}).get("Q_k_scale", 1.0))
    service_scale = float(config.get("service", {}).get("time_scale", 1.0))
    delta_by_team = config["resilience"]["delta_by_team"]
    for team in config["teams"]["types"]:
        teams.append(
            {
                "name": team["name"],
                "base_cost": float(team["base_cost"]),
                "service_hours": float(team["service_hours"]) * service_scale,
                "capacity_hours": float(team["capacity_hours"]) * capacity_scale,
                "delta": float(delta_by_team.get(team["name"], 0.0)),
            }
        )

    tau = {}
    for node in nodes:
        for team in teams:
            tau[(node, team["name"])] = severity.get(node, 0.0) * team["service_hours"]

    alpha = float(config["cost"]["alpha"])
    cost_scale = float(config["cost"]["scale"])
    costs = {}
    delta_xi = {}
    for node in nodes:
        for team in teams:
            costs[(node, team["name"])] = cost_scale * team["base_cost"] * (1 + alpha * (1 - bfi[node]))
            delta = team["delta"]
            delta_xi[(node, team["name"])] = max(0.0, min(1.0, bfi[node] + delta) - bfi[node])

    max_service = max(tau.values()) if tau else 0.0
    max_travel = max(travel_times.values()) if travel_times else 0.0
    horizon = float(config["time"]["horizon_hours"])
    big_m = config["solver"]["big_m"]
    if big_m is None:
        big_m = horizon + max_service + max_travel

    return {
        "graph": graph,
        "nodes": nodes,
        "service_nodes": service_nodes,
        "non_service_nodes": non_service_nodes,
        "travel_times": travel_times,
        "severity": severity,
        "bfi": bfi,
        "time_windows": time_windows,
        "teams": teams,
        "costs": costs,
        "delta_xi": delta_xi,
        "tau": tau,
        "big_m": big_m,
        "horizon": horizon,
        "modot_present": modot_present,
    }
