import json
import os
from typing import Any, Dict, List


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def config_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "user-defined-base-config.json")


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
