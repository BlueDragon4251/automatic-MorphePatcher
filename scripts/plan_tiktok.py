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
    resolved = read_json("build/tiktok-resolved.json", {})
    original = read_json("build/tiktok-original.json", {})
    state = read_json("state-tiktok.json", {})
    force = os.getenv("FORCE", "false").lower() == "true"

    desired = {
        "tiktok_version": resolved["tiktok_version"],
        "patch_version": resolved["patch_version"],
        "patch_tag": resolved["patch_tag"],
        "original_channel": original["channel"],
    }
    state_matches = all(state.get(k) == v for k, v in desired.items())
    changed = force or not state_matches

    repo = os.getenv("GITHUB_REPOSITORY", "")
    release_exists = False
    asset_exists = False
    if repo:
        tag = urllib.parse.quote(resolved["release_tag"], safe="")
        try:
            release = github_json(f"https://api.github.com/repos/{repo}/releases/tags/{tag}")
            release_exists = True
            asset_exists = any(
                a.get("name") == resolved["asset_name"]
                for a in release.get("assets", [])
            )
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

    needs_build = changed and (force or not asset_exists)
    needs_notify = changed

    output({
        "changed": changed,
        "needs_build": needs_build,
        "needs_notify": needs_notify,
        "release_exists": release_exists,
        "asset_exists": asset_exists,
    })
    print(json.dumps({
        "desired": desired,
        "state": state,
        "force": force,
        "changed": changed,
        "release_exists": release_exists,
        "asset_exists": asset_exists,
        "needs_build": needs_build,
        "needs_notify": needs_notify,
    }, indent=2))


if __name__ == "__main__":
    main()
