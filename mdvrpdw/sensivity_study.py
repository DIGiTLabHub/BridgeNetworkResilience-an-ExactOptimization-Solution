from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass
class SweepResult:
    parameters: Dict[str, Any]
    metrics: Dict[str, Any]


def _set_nested(config: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    target = config
    for key in keys[:-1]:
        if key not in target or not isinstance(target[key], dict):
            target[key] = {}
        target = target[key]
    target[keys[-1]] = value


def build_param_grid(param_grid: Dict[str, Iterable[Any]]) -> List[Dict[str, Any]]:
    keys = list(param_grid.keys())
    value_lists = [list(param_grid[key]) for key in keys]
    combos = []
    for values in product(*value_lists):
        combos.append(dict(zip(keys, values)))
    return combos


def apply_params(base_config: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    config = {**base_config}
    for path, value in parameters.items():
        _set_nested(config, path, value)

    num_bridges = parameters.get("selection.num_bridges")
    if num_bridges is not None:
        file_name = f"bridge_subgraph_{int(num_bridges):03d}.pkl"
        _set_nested(config, "paths.subgraph_file", f"Sample-Subgraphs/{file_name}")

    return config


def _build_one_at_a_time(param_grid: Dict[str, Iterable[Any]]) -> List[Dict[str, Any]]:
    scenarios = []
    for key, values in param_grid.items():
        for value in values:
            scenarios.append({key: value})
    return scenarios


def run_sensitivity(
    base_config: Dict[str, Any],
    param_grid: Dict[str, Iterable[Any]],
    solve_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    metrics_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    mode: str = "one_at_a_time",
) -> List[SweepResult]:
    results = []
    if mode == "full_grid":
        scenarios = build_param_grid(param_grid)
    else:
        scenarios = _build_one_at_a_time(param_grid)

    for parameters in scenarios:
        scenario_config = apply_params(base_config, parameters)
        solution = solve_fn(scenario_config)
        metrics = metrics_fn(solution) if metrics_fn else solution
        results.append(SweepResult(parameters=parameters, metrics=metrics))
    return results
