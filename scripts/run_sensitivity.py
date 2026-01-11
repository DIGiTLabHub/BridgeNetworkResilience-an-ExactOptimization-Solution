import argparse
import json
from pathlib import Path
from typing import Any, Dict

from mdvrpdw.obtain_config import config_path, load_config
from mdvrpdw.sensivity_study import run_sensitivity
from mdvrpdw.solve import solve_mdvrpdw


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", default=None)
    parser.add_argument("--param-grid", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=["one_at_a_time", "full_grid"], default="one_at_a_time")
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args()

    base_config_path = args.base_config or config_path()
    base_config = load_config(base_config_path)
    if args.print_config:
        print(json.dumps(base_config, indent=2))
        return

    param_grid = _load_json(Path(args.param_grid))

    results = run_sensitivity(base_config, param_grid, solve_mdvrpdw, mode=args.mode)
    output_path = Path(args.output)
    output_path.write_text(json.dumps([result.__dict__ for result in results], indent=2))


if __name__ == "__main__":
    main()
