import argparse
import json
from pathlib import Path

from mdvrpdw.obtain_config import config_path, load_config
from mdvrpdw.solve import solve_mdvrpdw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args()

    config_file = args.config or config_path()
    output_path = Path(args.output)

    config = load_config(config_file)
    if args.print_config:
        print(json.dumps(config, indent=2))
        return

    result = solve_mdvrpdw(config)
    output_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
