from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class SensitivityConfig:
    base_config: Dict[str, Any]
    param_grid: Dict[str, List[Any]]


def default_config() -> Dict[str, Any]:
    return {
        "paths": {
            "graph_file": "Missouri-Bridges-GeoData-Graphs/missouri_bridge_graph.pkl",
            "data_file": "Missouri-Bridges-GeoData-Graphs/MOpoorbridges.xlsx",
            "subgraph_file": "Missouri-Bridges-GeoData-Graphs/missouri_bridge_subgraph_saved.pkl",
        },
        "selection": {
            "num_bridges": None,
            "random_state": 42,
            "exclude_modot_from_service": True,
        },
        "teams": {
            "types": [
                {"name": "RRU", "base_cost": 1.0, "service_hours": 24.0, "capacity_hours": 72.0},
                {"name": "ERT", "base_cost": 2.0, "service_hours": 24.0, "capacity_hours": 72.0},
                {"name": "CIRS", "base_cost": 5.0, "service_hours": 24.0, "capacity_hours": 72.0},
            ]
        },
        "severity": {
            "source_column": "Minimum",
            "max_rating": 9.0,
            "q_i_scale": 1.0,
            "q_i_min": 1.0,
        },
        "resilience": {
            "bfi_scale": 1.0,
            "delta_by_team": {"RRU": 0.3, "ERT": 0.55, "CIRS": 0.75},
        },
        "time": {
            "horizon_hours": 168.0,
            "window_length_hours": 72.0,
            "window_slack_hours": 0.0,
            "window_scale": 1.0,
        },
        "travel": {
            "speed_mps": 20.0,
            "time_scale": 1.0,
        },
        "service": {
            "time_scale": 1.0,
        },
        "cost": {
            "alpha": 1.0,
            "scale": 1.0,
        },
        "solver": {
            "big_m": None,
            "time_limit": None,
            "mip_gap": None,
            "threads": None,
        },
    }


def default_sensitivity_grid() -> Dict[str, List[Any]]:
    return {
        "selection.num_bridges": [5, 10, 15, 20, 30],
        "capacity.Q_k_scale": [0.8, 1.0, 1.2],
        "severity.q_i_scale": [0.8, 1.0, 1.2],
        "time.window_scale": [0.8, 1.0, 1.2],
        "travel.time_scale": [0.8, 1.0, 1.2],
        "service.time_scale": [0.8, 1.0, 1.2],
        "cost.scale": [0.8, 1.0, 1.2],
    }
