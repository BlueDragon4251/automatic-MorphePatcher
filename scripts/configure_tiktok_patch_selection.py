#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

TIKTOK_BUNDLE = "tiktok-patches.mpp"
MORPHE_BUNDLE = "morphe-extra-patches.mpp"
MORPHE_EXTRAS = {
    "Change installer source",
    "Disable Play Store updates",
}


def write_github_output(total: int, tiktok_total: int, morphe_total: int, forced_on: int) -> None:
    out = os.getenv("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"full_patch_total={total}\n")
        f.write(f"tiktok_patch_total={tiktok_total}\n")
        f.write(f"morphe_extra_total={morphe_total}\n")
        f.write(f"full_patch_forced_on={forced_on}\n")


def bundle_source(bundle: dict) -> str:
    meta = bundle.get("meta") or {}
    return str(meta.get("source") or "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enable all BlueIT TikTok patches and exactly two official Morphe universal patches."
    )
    parser.add_argument("options_file", type=Path)
    args = parser.parse_args()

    path = args.options_file
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Unexpected Morphe options format: top level is not a list")

    tiktok_bundle = None
    morphe_bundle = None
    for bundle in data:
        if not isinstance(bundle, dict):
            continue
        source = bundle_source(bundle)
        if TIKTOK_BUNDLE in source:
            tiktok_bundle = bundle
        elif MORPHE_BUNDLE in source:
            morphe_bundle = bundle

    if tiktok_bundle is None:
        raise SystemExit(f"TikTok patch bundle {TIKTOK_BUNDLE!r} not found in options file")
    if morphe_bundle is None:
        raise SystemExit(f"Official Morphe bundle {MORPHE_BUNDLE!r} not found in options file")

    forced_on = 0
    tiktok_total = 0
    tiktok_names = []
    tiktok_patches = tiktok_bundle.get("patches")
    if not isinstance(tiktok_patches, dict) or not tiktok_patches:
        raise SystemExit("No TikTok patches found in TikTok bundle")

    for name, config in tiktok_patches.items():
        if not isinstance(config, dict):
            raise SystemExit(f"Unexpected TikTok patch config for {name}")
        tiktok_total += 1
        tiktok_names.append(name)
        if config.get("enabled") is not True:
            forced_on += 1
        config["enabled"] = True

    morphe_patches = morphe_bundle.get("patches")
    if not isinstance(morphe_patches, dict):
        raise SystemExit("No patches found in official Morphe bundle")

    found = set()
    for name, config in morphe_patches.items():
        if not isinstance(config, dict):
            raise SystemExit(f"Unexpected official Morphe patch config for {name}")
        should_enable = name in MORPHE_EXTRAS
        if should_enable:
            found.add(name)
            if config.get("enabled") is not True:
                forced_on += 1
            config["enabled"] = True
            if name == "Change installer source":
                options = config.setdefault("options", {})
                options["packageInstallerName"] = "com.android.vending"
        else:
            config["enabled"] = False

    missing = MORPHE_EXTRAS - found
    if missing:
        raise SystemExit(
            "Required official Morphe patches are not compatible/universal for TikTok: "
            + ", ".join(sorted(missing))
        )

    morphe_total = len(found)
    total = tiktok_total + morphe_total
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_github_output(total, tiktok_total, morphe_total, forced_on)

    print(
        f"TikTok selection: {tiktok_total} BlueIT patches + {morphe_total} official Morphe extras = {total} enabled"
    )
    print("Enabled BlueIT TikTok patches:")
    for name in sorted(tiktok_names, key=str.casefold):
        print(f"- {name}")
    print("Enabled official Morphe extras:")
    for name in sorted(found, key=str.casefold):
        suffix = " (com.android.vending)" if name == "Change installer source" else ""
        print(f"- {name}{suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
