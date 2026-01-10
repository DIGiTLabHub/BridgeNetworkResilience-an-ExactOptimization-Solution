from typing import Iterable, List

import numpy as np
import networkx as nx


def _pick_central_bridge(graph: nx.Graph, bridge_nodes: List[str]) -> str:
    latitudes = np.array([graph.nodes[node]["latitude"] for node in bridge_nodes])
    longitudes = np.array([graph.nodes[node]["longitude"] for node in bridge_nodes])
    centroid_lat = float(latitudes.mean())
    centroid_lon = float(longitudes.mean())

    def _distance(node: str) -> float:
        lat = graph.nodes[node]["latitude"]
        lon = graph.nodes[node]["longitude"]
        return (lat - centroid_lat) ** 2 + (lon - centroid_lon) ** 2

    return min(bridge_nodes, key=_distance)


def _pick_farthest_bridge(graph: nx.Graph, bridge_nodes: List[str], selected: List[str]) -> str:
    def _distance(node: str) -> float:
        lat = graph.nodes[node]["latitude"]
        lon = graph.nodes[node]["longitude"]
        return min((lat - graph.nodes[other]["latitude"]) ** 2 + (lon - graph.nodes[other]["longitude"]) ** 2 for other in selected)

    return max(bridge_nodes, key=_distance)


def select_depots(graph: nx.Graph, bridge_nodes: Iterable[str], max_depots: int) -> List[str]:
    nodes = [node for node in bridge_nodes]
    modot_present = "MoDOT" in nodes
    nodes_without_modot = [node for node in nodes if node != "MoDOT"]

    if not nodes_without_modot:
        return ["MoDOT"] if modot_present else []

    if max_depots <= 1:
        return ["MoDOT"] if modot_present else [_pick_central_bridge(graph, nodes_without_modot)]

    depots = []
    if modot_present:
        depots.append("MoDOT")

    depots.append(_pick_central_bridge(graph, nodes_without_modot))

    while len(depots) < max_depots:
        candidate_nodes = [node for node in nodes_without_modot if node not in depots]
        if not candidate_nodes:
            break
        depots.append(_pick_farthest_bridge(graph, candidate_nodes, depots))

    return depots
