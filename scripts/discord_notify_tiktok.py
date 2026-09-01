#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def feature_fields(features):
    lines = []
    for feature in features:
        name = str(feature.get("name", "Unnamed patch")).strip()
        description = str(feature.get("description") or "").strip()
        if len(description) > 125:
            description = description[:122].rstrip() + "..."
        line = f"• **{name}**"
        if description:
            line += f" — {description}"
        lines.append(line)

    chunks = []
    current = ""
    for line in lines:
        candidate = line if not current else current + "\n" + line
        if len(candidate) > 950 and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)

    fields = []
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        title = "Features" if total == 1 else f"Features {i}/{total}"
        fields.append({"name": title, "value": chunk, "inline": False})
    return fields


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", required=True)
    p.add_argument("--channel", required=True)
    p.add_argument("--tiktok-version", required=True)
    p.add_argument("--patch-version", required=True)
    p.add_argument("--patch-count", required=True)
    p.add_argument("--features-json", required=True)
    p.add_argument("--download-url", required=True)
    p.add_argument("--sha256")
    args = p.parse_args()

    features = json.loads(Path(args.features_json).read_text(encoding="utf-8"))
    if not isinstance(features, list) or not features:
        raise SystemExit("TikTok feature list is empty")

    description = (
        f"**TikTok Version:** `{args.tiktok_version}` (supported target)\n\n"
        f"**Patches Version:** `{args.patch_version}` (latest stable)\n\n"
        f"**Full Patch:** `{args.patch_count}/{args.patch_count}` Patches aktiviert\n\n"
        f"[**APK herunterladen**]({args.download_url})"
    )

    fields = feature_fields(features)
    if args.sha256:
        fields.append({"name": "SHA-256", "value": f"`{args.sha256}`", "inline": False})

    payload = {
        "embeds": [{
            "title": "TikTok • Morphe Patches",
            "url": args.download_url,
            "description": description,
            "fields": fields,
            "footer": {"text": "BlueIT-Patcher"},
        }]
    }

    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{args.channel}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bot {args.token}",
            "Content-Type": "application/json",
            "User-Agent": "BlueIT-Patcher/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
            if r.status not in (200, 201):
                raise RuntimeError(f"Discord returned HTTP {r.status}: {body}")
            response = json.loads(body)
            print(f"Discord TikTok message sent: {response.get('id', 'unknown id')}")
    except urllib.error.HTTPError as e:
        print(f"Discord HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
