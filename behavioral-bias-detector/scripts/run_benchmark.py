import argparse
import json

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--agent-ids", default="1,2,3,4")
    parser.add_argument("--scenario-ids", default="1,2,3,4,5,6,7,8")
    args = parser.parse_args()

    payload = {
        "agent_ids": [int(value) for value in args.agent_ids.split(",") if value.strip()],
        "scenario_ids": [int(value) for value in args.scenario_ids.split(",") if value.strip()],
    }

    response = requests.post(f"{args.host}/api/v1/benchmark/run", json=payload, timeout=120)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()

