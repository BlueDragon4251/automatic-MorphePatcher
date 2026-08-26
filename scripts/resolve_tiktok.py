#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PATCH_REPO = os.getenv("TIKTOK_PATCH_REPO", "BlueDragon4251/tiktok-patches-for-morphe")
DESKTOP_REPO = os.getenv("MORPHE_DESKTOP_REPO", "MorpheApp/morphe-desktop")
TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
USER_AGENT = "automatic-MorphePatcher/1.0"
PRE_RELEASE_TAG_RE = re.compile(r"(?:^|[-._])(dev|alpha|beta|rc|pre)(?:[-._]|\d|$)", re.I)


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


def latest_stable_release(repo: str):
    release = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease"):
        raise RuntimeError(f"GitHub latest release for {repo} is not stable: {tag}")
    if PRE_RELEASE_TAG_RE.search(tag):
        raise RuntimeError(f"Refusing pre-release-looking tag for TikTok: {tag}")
    return release


def latest_desktop_release(repo: str):
    return get_json(f"https://api.github.com/repos/{repo}/releases/latest")


def find_asset(release, predicate, description: str) -> str:
    for asset in release.get("assets", []):
        if predicate(asset.get("name", "")):
            return asset["browser_download_url"]
    raise RuntimeError(f"Could not find {description} on release {release.get('tag_name')}")


def version_key(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def load_patch_metadata(repo: str, tag: str):
    encoded_tag = urllib.parse.quote(tag, safe="")
    url = f"https://raw.githubusercontent.com/{repo}/{encoded_tag}/patches-list.json"
    return get_json(url)


def collect_tiktok_features(metadata: dict):
    features = []
    versions = set()

    for patch in metadata.get("patches", []):
        compatible = patch.get("compatiblePackages") or {}
        package_versions = compatible.get(TIKTOK_PACKAGE) or []
        for version in package_versions:
            versions.add(str(version))

        if TIKTOK_PACKAGE not in compatible:
            continue

        features.append({
            "name": str(patch.get("name", "Unnamed patch")),
            "description": str(patch.get("description") or "").strip(),
            "default_enabled": bool(patch.get("use")),
        })

    if not versions:
        for patch in metadata.get("patches", []):
            for compat in patch.get("compatibility") or []:
                if compat.get("packageName") != TIKTOK_PACKAGE:
                    continue
                for target in compat.get("targets") or []:
                    version = target.get("version")
                    if version:
                        versions.add(str(version))

    if not versions:
        raise RuntimeError("No TikTok versions found in stable patch metadata")
    if not features:
        raise RuntimeError("No TikTok patch features found in stable patch metadata")

    return sorted(versions, key=version_key, reverse=True), features


def write_output(values: dict):
    out = os.getenv("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in values.items():
            f.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def main():
    patch_release = latest_stable_release(PATCH_REPO)
    patch_tag = patch_release["tag_name"]
    patch_version = patch_tag.removeprefix("v")
    mpp_url = find_asset(
        patch_release,
        lambda n: n.endswith(".mpp") and "sources" not in n and "javadoc" not in n,
        "MPP asset",
    )

    metadata = load_patch_metadata(PATCH_REPO, patch_tag)
    versions, features = collect_tiktok_features(metadata)
    target_version = versions[0]

    desktop_release = latest_desktop_release(DESKTOP_REPO)
    desktop_version = desktop_release["tag_name"].removeprefix("v")
    desktop_jar_url = find_asset(
        desktop_release,
        lambda n: n.endswith("-all.jar"),
        "Morphe Desktop all-in-one JAR",
    )

    release_tag = f"tiktok-{target_version}-morphe-{patch_version}"
    asset_name = f"TikTok-Morphe-{target_version}-patches-{patch_version}.apk"

    resolved = {
        "patch_repo": PATCH_REPO,
        "patch_tag": patch_tag,
        "patch_version": patch_version,
        "patch_prerelease": False,
        "mpp_url": mpp_url,
        "tiktok_package": TIKTOK_PACKAGE,
        "tiktok_version": target_version,
        "supported_versions": versions,
        "features": features,
        "feature_count": len(features),
        "desktop_repo": DESKTOP_REPO,
        "desktop_version": desktop_version,
        "desktop_jar_url": desktop_jar_url,
        "release_tag": release_tag,
        "asset_name": asset_name,
    }

    Path("build").mkdir(exist_ok=True)
    Path("build/tiktok-resolved.json").write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path("build/tiktok-features.json").write_text(
        json.dumps(features, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    write_output({
        "patch_version": patch_version,
        "patch_tag": patch_tag,
        "mpp_url": mpp_url,
        "tiktok_version": target_version,
        "feature_count": len(features),
        "desktop_version": desktop_version,
        "desktop_jar_url": desktop_jar_url,
        "release_tag": release_tag,
        "asset_name": asset_name,
    })

    print(
        f"TikTok patches={patch_version} (stable only), "
        f"TikTok={target_version}, features={len(features)}, "
        f"Desktop={desktop_version}"
    )


if __name__ == "__main__":
    try:
        main()
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
        print(f"resolve_tiktok.py: {e}", file=sys.stderr)
        sys.exit(1)
