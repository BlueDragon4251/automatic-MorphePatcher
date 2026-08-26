#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enable every patch in a Morphe options JSON file."
    )
    parser.add_argument("options_file", type=Path)
    args = parser.parse_args()

    path = args.options_file
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise SystemExit("Unexpected Morphe options format: top level is not a list")

    total = 0
    forced_on = 0
    names: list[str] = []

    for bundle in data:
        if not isinstance(bundle, dict):
            continue
        patches = bundle.get("patches")
        if not isinstance(patches, dict):
            continue

        for name, config in patches.items():
            if not isinstance(config, dict):
                raise SystemExit(f"Unexpected config for patch: {name}")
            total += 1
            names.append(name)
            if config.get("enabled") is not True:
                forced_on += 1
            config["enabled"] = True

    if total == 0:
        raise SystemExit("No YouTube patches found in Morphe options file")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Full patch selection: {total}/{total} enabled ({forced_on} forced on)")
    print("Enabled patches:")
    for name in sorted(names, key=str.casefold):
        print(f"- {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
