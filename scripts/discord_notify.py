#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://discord.com/api/v10"
USER_AGENT = "BlueIT-Patcher/1.0"


def discord_request(token: str, method: str, url: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
        if r.status < 200 or r.status >= 300:
            raise RuntimeError(f"Discord returned HTTP {r.status}: {body}")
        return json.loads(body) if body else None


def find_existing_message(token: str, channel: str, download_url: str):
    query = urllib.parse.urlencode({"limit": 100})
    messages = discord_request(
        token,
        "GET",
        f"{API_BASE}/channels/{channel}/messages?{query}",
    )
    for message in messages or []:
        for embed in message.get("embeds", []):
            if embed.get("title") != "YouTube • Morphe Patches":
                continue
            if embed.get("url") == download_url:
                return message.get("id")
            description = embed.get("description") or ""
            if download_url in description:
                return message.get("id")
    return None


def patch_label(version: str) -> str:
    lower = version.lower()
    if any(marker in lower for marker in ("-dev", "-alpha", "-beta", "-rc", "-pre")):
        return "latest dev"
    return "latest release"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--token", required=True)
    p.add_argument("--channel", required=True)
    p.add_argument("--youtube-version", required=True)
    p.add_argument("--patch-version", required=True)
    p.add_argument("--original-label", required=True)
    p.add_argument("--download-url", required=True)
    p.add_argument("--sha256")
    p.add_argument(
        "--edit-only",
        action="store_true",
        help="Only edit an existing matching message; never create a new one.",
    )
    args = p.parse_args()

    description = (
        f"**Youtube Version:** `{args.youtube_version}` "
        f"(latest release (Morphe) & {args.original_label})\n\n"
        f"**Patches Version:** `{args.patch_version}` ({patch_label(args.patch_version)})\n\n"
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

    try:
        message_id = find_existing_message(
            args.token,
            args.channel,
            args.download_url,
        )
        if message_id:
            response = discord_request(
                args.token,
                "PATCH",
                f"{API_BASE}/channels/{args.channel}/messages/{message_id}",
                payload,
            )
            print(f"Discord message edited: {response.get('id', message_id)}")
        elif args.edit_only:
            print("No matching Discord message found; edit-only mode will not create a duplicate.")
        else:
            response = discord_request(
                args.token,
                "POST",
                f"{API_BASE}/channels/{args.channel}/messages",
                payload,
            )
            print(f"Discord message sent: {response.get('id', 'unknown id')}")
    except urllib.error.HTTPError as e:
        print(f"Discord HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
