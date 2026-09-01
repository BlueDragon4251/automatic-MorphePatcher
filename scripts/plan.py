#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def github_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "automatic-MorphePatcher/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def read_json(path: str, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def output(values: dict):
    out = os.getenv("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in values.items():
            f.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def main():
    resolved = read_json("build/resolved.json", {})
    original = read_json("build/original.json", {})
    state = read_json("state.json", {})
    force = os.getenv("FORCE", "false").lower() == "true"

    current_patch_prerelease = bool(resolved.get("patch_prerelease"))
    youtube_changed = state.get("youtube_version") != resolved["youtube_version"]

    # Intermediate dev/prerelease bumps do not deserve a rebuild by themselves.
    # A stable Morphe patch release does: this covers dev -> release promotion as
    # well as stable hotfixes. If a dev release introduces a new supported
    # YouTube target, youtube_changed still triggers an immediate build.
    stable_patch_changed = (
        not current_patch_prerelease
        and state.get("patch_version") != resolved["patch_version"]
    )

    build_reason = None
    if force:
        build_reason = "force"
    elif youtube_changed:
        build_reason = "youtube_version_changed"
    elif stable_patch_changed:
        build_reason = "stable_patch_changed"

    changed = build_reason is not None

    repo = os.getenv("GITHUB_REPOSITORY", "")
    release_exists = False
    asset_exists = False
    if repo:
        tag = urllib.parse.quote(resolved["release_tag"], safe="")
        try:
            release = github_json(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
            release_exists = True
            asset_exists = any(a.get("name") == resolved["asset_name"] for a in release.get("assets", []))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

    # Build only for one of the explicit reasons above. Force always rebuilds;
    # otherwise an already-published matching asset is reused.
    needs_build = changed and (force or not asset_exists)
    needs_notify = changed

    output({
        "changed": changed,
        "needs_build": needs_build,
        "needs_notify": needs_notify,
        "release_exists": release_exists,
        "asset_exists": asset_exists,
        "youtube_changed": youtube_changed,
        "stable_patch_changed": stable_patch_changed,
        "build_reason": build_reason or "none",
    })
    print(json.dumps({
        "resolved": {
            "youtube_version": resolved["youtube_version"],
            "patch_version": resolved["patch_version"],
            "patch_prerelease": current_patch_prerelease,
            "original_channel": original.get("channel"),
        },
        "state": state,
        "force": force,
        "youtube_changed": youtube_changed,
        "stable_patch_changed": stable_patch_changed,
        "build_reason": build_reason,
        "changed": changed,
        "release_exists": release_exists,
        "asset_exists": asset_exists,
        "needs_build": needs_build,
        "needs_notify": needs_notify,
    }, indent=2))


if __name__ == "__main__":
    main()
