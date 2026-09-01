#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PATCH_REPO = os.getenv("MORPHE_PATCH_REPO", "MorpheApp/morphe-patches")
DESKTOP_REPO = os.getenv("MORPHE_DESKTOP_REPO", "MorpheApp/morphe-desktop")
YOUTUBE_PACKAGE = "com.google.android.youtube"
USER_AGENT = "automatic-MorphePatcher/1.0"


def headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def get_json(url: str):
    return json.loads(get_bytes(url).decode("utf-8"))


def get_text(url: str) -> str:
    return get_bytes(url).decode("utf-8")


def version_key(v: str):
    return tuple(int(x) for x in v.split("."))


def latest_patch_release(repo: str):
    """Return the newest published patch release, stable or prerelease.

    We still inspect dev releases so a newly-supported YouTube target can be
    picked up immediately. Whether that release deserves a rebuild is decided
    by plan.py; intermediate dev bumps with the same YouTube target are ignored.
    """
    releases = get_json(f"https://api.github.com/repos/{repo}/releases?per_page=100")
    candidates = [
        r for r in releases
        if not r.get("draft") and r.get("published_at")
    ]
    if not candidates:
        raise RuntimeError(f"No published release found for {repo}")
    return max(candidates, key=lambda r: r["published_at"])


def latest_desktop_release(repo: str):
    return get_json(f"https://api.github.com/repos/{repo}/releases/latest")


def find_asset(release, predicate, description: str) -> str:
    for asset in release.get("assets", []):
        if predicate(asset.get("name", "")):
            return asset["browser_download_url"]
    raise RuntimeError(f"Could not find {description} on release {release.get('tag_name')}")


def parse_youtube_supported_versions(readme: str):
    marker = "<summary>📦 YouTube"
    start = readme.find(marker)
    if start < 0:
        raise RuntimeError("YouTube section not found in Morphe README")
    end = readme.find("</details>", start)
    if end < 0:
        end = min(len(readme), start + 20000)
    block = readme[start:end]

    support_marker = "**🎯 Supported versions:**"
    s = block.find(support_marker)
    if s < 0:
        raise RuntimeError("Supported versions table not found in Morphe README")
    support_block = block[s:s + 2500]

    found = []
    for m in re.finditer(r"(🧪\s*)?(\d+\.\d+\.\d+)", support_block):
        version = m.group(2)
        found.append({
            "version": version,
            "channel": "experimental" if m.group(1) else "stable",
        })
    if not found:
        raise RuntimeError("No YouTube versions found in Morphe supported versions table")

    by_version = {}
    for item in found:
        old = by_version.get(item["version"])
        if old is None or item["channel"] == "experimental":
            by_version[item["version"]] = item
    return sorted(by_version.values(), key=lambda x: version_key(x["version"]), reverse=True)


def write_output(values: dict):
    out = os.getenv("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in values.items():
            f.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def main():
    patch_release = latest_patch_release(PATCH_REPO)
    patch_tag = patch_release["tag_name"]
    patch_version = patch_tag.removeprefix("v")
    patch_prerelease = bool(patch_release.get("prerelease"))
    patch_label = "latest dev" if patch_prerelease else "latest release"
    mpp_url = find_asset(
        patch_release,
        lambda n: n.endswith(".mpp") and "sources" not in n and "javadoc" not in n,
        "MPP asset",
    )

    readme_url = f"https://raw.githubusercontent.com/{PATCH_REPO}/{urllib.parse.quote(patch_tag, safe='')}/README.md"
    readme = get_text(readme_url)
    versions = parse_youtube_supported_versions(readme)
    target = versions[0]

    desktop_release = latest_desktop_release(DESKTOP_REPO)
    desktop_version = desktop_release["tag_name"].removeprefix("v")
    desktop_jar_url = find_asset(
        desktop_release,
        lambda n: n.endswith("-all.jar"),
        "Morphe Desktop all-in-one JAR",
    )

    release_tag = f"youtube-{target['version']}-morphe-{patch_version}"
    asset_name = f"YouTube-Morphe-{target['version']}-patches-{patch_version}.apk"

    resolved = {
        "patch_repo": PATCH_REPO,
        "patch_tag": patch_tag,
        "patch_version": patch_version,
        "patch_prerelease": patch_prerelease,
        "patch_label": patch_label,
        "mpp_url": mpp_url,
        "youtube_package": YOUTUBE_PACKAGE,
        "youtube_version": target["version"],
        "morphe_target_channel": target["channel"],
        "morphe_supported_versions": versions,
        "desktop_repo": DESKTOP_REPO,
        "desktop_version": desktop_version,
        "desktop_jar_url": desktop_jar_url,
        "release_tag": release_tag,
        "asset_name": asset_name,
    }

    Path("build").mkdir(exist_ok=True)
    Path("build/resolved.json").write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")

    write_output({
        "patch_version": patch_version,
        "patch_tag": patch_tag,
        "patch_prerelease": patch_prerelease,
        "patch_label": patch_label,
        "mpp_url": mpp_url,
        "youtube_version": target["version"],
        "morphe_target_channel": target["channel"],
        "desktop_version": desktop_version,
        "desktop_jar_url": desktop_jar_url,
        "release_tag": release_tag,
        "asset_name": asset_name,
    })

    print(
        f"Morphe patches={patch_version} ({'prerelease' if patch_prerelease else 'stable'}), "
        f"YouTube={target['version']} ({target['channel']} in Morphe), "
        f"Desktop={desktop_version}"
    )


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
        print(f"resolve.py: {e}", file=sys.stderr)
        sys.exit(1)
