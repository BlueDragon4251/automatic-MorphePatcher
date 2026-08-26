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
RELEASE_SLUG = "tiktok-pte-ltd/tik-tok-including-musical-ly/tiktok"
USER_AGENT = "automatic-MorphePatcher/1.0"


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


def clean_text(tag) -> str:
    return " ".join(tag.stripped_strings)


def target_channel(release_html: str) -> str:
    soup = BeautifulSoup(release_html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1 = soup.find("h1")
    heading = h1.get_text(" ", strip=True) if h1 else ""
    exact_header = f"{title} {heading}"
    if re.search(r"\bbeta\b", exact_header, re.I):
        return "beta"
    if re.search(r"\balpha\b", exact_header, re.I):
        return "alpha"
    return "stable"


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
        raise RuntimeError("No standalone TikTok APK variant found on APKMirror release page")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0]


def download_apk(session, release_html: str, rel_url: str, out_path: Path):
    _, variant_path, variant_text = pick_apk_variant(release_html)
    variant_url = urljoin(BASE, variant_path)
    variant_html = get_html(session, variant_url, rel_url)
    variant_soup = BeautifulSoup(variant_html, "html.parser")

    dl_link = variant_soup.find("a", href=re.compile(r"/download/\?key="))
    if not dl_link:
        raise RuntimeError("APKMirror TikTok variant page did not expose a keyed download page")
    dl_page = urljoin(BASE, html.unescape(dl_link.get("href")))
    dl_html = get_html(session, dl_page, variant_url)
    dl_soup = BeautifulSoup(dl_html, "html.parser")

    file_link = dl_soup.find("a", href=re.compile(r"download\.php\?"))
    if not file_link:
        raise RuntimeError("APKMirror TikTok download page did not expose the file URL")
    file_url = urljoin(BASE, html.unescape(file_link.get("href")))

    r = session.get(
        file_url,
        headers={"Referer": dl_page, "User-Agent": USER_AGENT},
        stream=True,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} while downloading TikTok APK")

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
        raise RuntimeError(f"Downloaded TikTok APK is unexpectedly small ({total} bytes)")

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--metadata", default="build/tiktok-original.json")
    parser.add_argument("--out")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    session = get_session()
    rel_url = release_url(args.version)
    rel_html = get_html(session, rel_url, BASE + "/")
    meta = {
        "source": "APKMirror",
        "release_url": rel_url,
        "channel": target_channel(rel_html),
    }

    if not args.status_only:
        if not args.out:
            parser.error("--out is required unless --status-only is used")
        meta.update(download_apk(session, rel_html, rel_url, Path(args.out)))

    Path(args.metadata).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metadata).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    write_github_output(meta)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"apkmirror_tiktok.py: {e}", file=sys.stderr)
        sys.exit(1)
