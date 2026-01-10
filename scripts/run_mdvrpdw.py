import argparse
import json
from pathlib import Path

from mdvrpdw.solve import solve_mdvrpdw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    output_path = Path(args.output)

    config = json.loads(config_path.read_text())
    result = solve_mdvrpdw(config)
    output_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
