#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", required=True)
    p.add_argument("--channel", required=True)
    p.add_argument("--youtube-version", required=True)
    p.add_argument("--patch-version", required=True)
    p.add_argument("--original-label", required=True)
    p.add_argument("--download-url", required=True)
    p.add_argument("--sha256")
    args = p.parse_args()

    description = (
        f"**Youtube Version:** `{args.youtube_version}` "
        f"(latest release (Morphe) & {args.original_label})\n\n"
        f"**Patches Version:** `{args.patch_version}` (latest dev)\n\n"
        "⚠️ **ACHTUNG!** : Bitte überprüfe, dass deine originale YouTube app auf dem neuesten Stand ist, "
        "sonst könnte es zu abstürzen bzw Wiedergabe Fehler kommen.\n\n"
        f"[**APK herunterladen**]({args.download_url})"
    )

    fields = []
    if args.sha256:
        fields.append({"name": "SHA-256", "value": f"`{args.sha256}`", "inline": False})

    payload = {
        "embeds": [{
            "title": "YouTube • Morphe Patches",
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
            print(f"Discord message sent: {response.get('id', 'unknown id')}")
    except urllib.error.HTTPError as e:
        print(f"Discord HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
