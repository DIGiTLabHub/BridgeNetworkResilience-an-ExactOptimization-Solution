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
    return config


def run_sensitivity(
    base_config: Dict[str, Any],
    param_grid: Dict[str, Iterable[Any]],
    solve_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    metrics_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> List[SweepResult]:
    results = []
    for parameters in build_param_grid(param_grid):
        scenario_config = apply_params(base_config, parameters)
        solution = solve_fn(scenario_config)
        metrics = metrics_fn(solution) if metrics_fn else solution
        results.append(SweepResult(parameters=parameters, metrics=metrics))
    return results
