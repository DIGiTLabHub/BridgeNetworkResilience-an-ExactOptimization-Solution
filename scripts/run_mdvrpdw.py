import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mdvrpdw.obtain_config import config_path, load_config
from mdvrpdw.solve import solve_mdvrpdw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--subgraph-file", default=None)
    parser.add_argument("--print-config", action="store_true")
    parser.add_argument("--solver-log", action="store_true")
    parser.add_argument("--solver-log-file", default=None)
    parser.add_argument("--solver-display-interval", type=int, default=None)
    args = parser.parse_args()

    config_file = args.config or config_path()
    config = load_config(config_file)

    if args.subgraph_file:
        config.setdefault("paths", {})
        config["paths"]["subgraph_file"] = args.subgraph_file

    if args.solver_log:
        config.setdefault("solver", {})
        config["solver"]["output_flag"] = 1
        config["solver"]["log_to_console"] = 1

    if args.solver_log_file:
        config.setdefault("solver", {})
        config["solver"]["output_flag"] = 1
        config["solver"]["log_file"] = args.solver_log_file

    if args.solver_display_interval is not None:
        config.setdefault("solver", {})
        config["solver"]["display_interval"] = args.solver_display_interval

    if args.print_config:
        print(json.dumps(config, indent=2))
        return

    if args.output:
        output_path = Path(args.output)
    else:
        subgraph = Path(config["paths"]["subgraph_file"])
        output_path = Path("opt_results") / f"solution_{subgraph.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = solve_mdvrpdw(config)
    output_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
