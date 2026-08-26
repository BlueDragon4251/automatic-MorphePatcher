#!/usr/bin/env python3
import argparse
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from curl_cffi import requests

BASE = "https://www.apkmirror.com"
APP_PAGE = f"{BASE}/apk/google-inc/youtube/"
RELEASE_SLUG = "google-inc/youtube/youtube"
USER_AGENT = "automatic-MorphePatcher/1.0"


def version_key(v: str):
    return tuple(int(x) for x in v.split("."))


def clean_text(soup_or_tag) -> str:
    return " ".join(soup_or_tag.stripped_strings)


def release_url(version: str) -> str:
    return f"{BASE}/apk/{RELEASE_SLUG}-{version.replace('.', '-')}-release/"


def get_session():
    return requests.Session(impersonate="chrome", timeout=120)


def get_html(session, url: str, referer: str | None = None) -> str:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {url}")
    return r.text


def target_channel(release_html: str, version: str) -> str:
    soup = BeautifulSoup(release_html, "html.parser")
    text = clean_text(soup)
    pattern = re.compile(rf"YouTube\s+{re.escape(version)}(?:\s+|[^A-Za-z0-9])*(beta|alpha)", re.I)
    m = pattern.search(text)
    if m:
        return m.group(1).lower()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(r"\bbeta\b", title, re.I):
        return "beta"
    if re.search(r"\balpha\b", title, re.I):
        return "alpha"
    return "stable"


def listing_versions(listing_html: str):
    soup = BeautifulSoup(listing_html, "html.parser")
    text = html.unescape(clean_text(soup))
    entries = {}
    pattern = re.compile(
        r"YouTube\s+(\d+\.\d+\.\d+)(?!-SECONDARY)(?:\s+(beta|alpha))?",
        re.I,
    )
    for m in pattern.finditer(text):
        version = m.group(1)
        channel = (m.group(2) or "stable").lower()
        previous = entries.get(version)
        if previous is None or channel in ("beta", "alpha"):
            entries[version] = channel
    return entries


def classify(session, version: str):
    rel_url = release_url(version)
    rel_html = get_html(session, rel_url, BASE + "/")
    channel = target_channel(rel_html, version)

    listing_html = get_html(session, APP_PAGE, BASE + "/")
    versions = listing_versions(listing_html)
    stable = sorted((v for v, c in versions.items() if c == "stable"), key=version_key, reverse=True)
    prerelease = sorted((v for v, c in versions.items() if c in ("beta", "alpha")), key=version_key, reverse=True)

    latest_stable = stable[0] if stable else None
    latest_prerelease = prerelease[0] if prerelease else None

    if channel in ("beta", "alpha"):
        display_label = "latest pre-release (Original)" if version == latest_prerelease else "pre-release (Original)"
    else:
        display_label = "latest release (Original)" if version == latest_stable else "release (Original)"

    return {
        "source": "APKMirror",
        "release_url": rel_url,
        "channel": channel,
        "display_label": display_label,
        "latest_stable_seen": latest_stable,
        "latest_prerelease_seen": latest_prerelease,
        "release_html": rel_html,
    }


def pick_apk_variant(release_html: str):
    soup = BeautifulSoup(release_html, "html.parser")
    candidates = []
    for row in soup.select("div.table-row"):
        link = row.find("a", href=re.compile(r"-android-apk-download/?$"))
        if not link:
            continue
        text = clean_text(row)
        upper = text.upper()
        if "BUNDLE" in upper or not re.search(r"\bAPK\b", upper):
            continue
        low = text.lower()
        score = 0
        if "universal" in low:
            score += 20
        if "nodpi" in low:
            score += 10
        candidates.append((score, link.get("href"), text))
    if not candidates:
        raise RuntimeError("No standalone APK variant found on APKMirror release page")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]


def download_apk(session, release_html: str, rel_url: str, out_path: Path):
    _, variant_path, variant_text = pick_apk_variant(release_html)
    variant_url = urljoin(BASE, variant_path)
    variant_html = get_html(session, variant_url, rel_url)
    variant_soup = BeautifulSoup(variant_html, "html.parser")

    dl_link = variant_soup.find("a", href=re.compile(r"/download/\?key="))
    if not dl_link:
        raise RuntimeError("APKMirror variant page did not expose a keyed download page")
    dl_page = urljoin(BASE, html.unescape(dl_link.get("href")))
    dl_html = get_html(session, dl_page, variant_url)
    dl_soup = BeautifulSoup(dl_html, "html.parser")

    file_link = dl_soup.find("a", href=re.compile(r"download\.php\?"))
    if not file_link:
        raise RuntimeError("APKMirror download page did not expose the file URL")
    file_url = urljoin(BASE, html.unescape(file_link.get("href")))

    r = session.get(file_url, headers={"Referer": dl_page, "User-Agent": USER_AGENT}, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} while downloading APK")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    with out_path.open("wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            digest.update(chunk)
            total += len(chunk)
    if total < 1_000_000:
        raise RuntimeError(f"Downloaded APK is unexpectedly small ({total} bytes)")

    return {
        "variant_url": variant_url,
        "variant": variant_text,
        "download_url": file_url,
        "bytes": total,
        "sha256": digest.hexdigest(),
    }


def write_github_output(metadata: dict):
    out = os.getenv("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"original_channel={metadata['channel']}\n")
        f.write(f"original_label={metadata['display_label']}\n")
        if metadata.get("latest_stable_seen"):
            f.write(f"latest_stable_seen={metadata['latest_stable_seen']}\n")
        if metadata.get("latest_prerelease_seen"):
            f.write(f"latest_prerelease_seen={metadata['latest_prerelease_seen']}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--metadata", default="build/original.json")
    parser.add_argument("--out")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    session = get_session()
    meta = classify(session, args.version)
    release_html = meta.pop("release_html")

    if not args.status_only:
        if not args.out:
            parser.error("--out is required unless --status-only is used")
        meta.update(download_apk(session, release_html, meta["release_url"], Path(args.out)))

    Path(args.metadata).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metadata).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    write_github_output(meta)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"apkmirror.py: {e}", file=sys.stderr)
        sys.exit(1)
