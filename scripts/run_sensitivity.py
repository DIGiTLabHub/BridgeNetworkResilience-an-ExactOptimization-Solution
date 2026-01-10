import argparse
import json
from pathlib import Path
from typing import Any, Dict

from mdvrpdw.sensivity_study import run_sensitivity
from mdvrpdw.solve import solve_mdvrpdw


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--param-grid", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base_config = _load_json(Path(args.base_config))
    param_grid = _load_json(Path(args.param_grid))

    results = run_sensitivity(base_config, param_grid, solve_mdvrpdw)
    output_path = Path(args.output)
    output_path.write_text(json.dumps([result.__dict__ for result in results], indent=2))


if __name__ == "__main__":
    main()
