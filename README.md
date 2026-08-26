# automatic-MorphePatcher

Automatically tracks the newest **Morphe patches dev pre-release**, resolves the newest YouTube version supported by that patch bundle, determines whether the original YouTube build is stable or a beta/alpha, patches the exact APK, publishes it as a GitHub Release, and posts a Discord bot embed with the external download link.

## Behaviour

- Checks every hour (`17 * * * *`) and can also be run manually.
- Always selects the newest published **Morphe patches pre-release/dev**.
- Selects the numerically newest YouTube version shown in that exact Morphe release's generated supported-version table, including experimental targets.
- Determines the original app channel from APKMirror metadata (`stable`, `beta`, `alpha`).
- Distinguishes `latest release (Original)`, `latest pre-release (Original)`, and older stable/pre-release targets.
- A change in the Original release channel is tracked too. If a version later moves from beta to stable, Discord is updated without rebuilding an already-published identical APK.
- Uses the exact `.mpp` asset from the resolved Morphe release, preventing a race where a newer dev release appears during the build.
- Downloads a standalone universal/nodpi YouTube APK when APKMirror offers one.
- Verifies package name, version name, and APK signatures before patching.
- Runs Morphe without `--force`, `--exclusive`, or `--continue-on-error`: the exact supported version is required, all default-enabled compatible patches are applied, and a real patch failure stops the build.
- Uses a persistent signing key supplied through GitHub Actions secrets so future patched APKs can update older builds signed by this project.
- Publishes the APK to a GitHub Release and sends only the external URL to Discord.

## Required GitHub Actions secrets

Create these repository secrets before the first scheduled/manual build:

| Secret | Purpose |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token. The bot must be in the target server and have **View Channel**, **Send Messages**, and **Embed Links** permission. |
| `DISCORD_CHANNEL_ID` | Numeric channel ID where the embed should be posted. |
| `MORPHE_KEYSTORE_B64` | Base64-encoded signing keystore (`PKCS12`, `JKS`, or another format Morphe can import). |
| `MORPHE_KEYSTORE_PASSWORD` | Keystore password and key-entry password. This workflow intentionally uses the same password for both. |
| `MORPHE_KEY_ALIAS` | Alias of the signing key inside the keystore. |

`GITHUB_TOKEN` is provided automatically by GitHub Actions and is given `contents: write` permission by the workflow.

## Generate a signing key once

Example with Java's `keytool`:

```bash
keytool -genkeypair \
  -alias morphe \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000 \
  -storetype PKCS12 \
  -keystore morphe-signing.p12
```

Use the same password for the keystore and key entry. Then base64-encode the file and store the resulting string in `MORPHE_KEYSTORE_B64`.

Linux:

```bash
base64 -w0 morphe-signing.p12
```

PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("morphe-signing.p12"))
```

Do **not** commit the keystore or bot token.

## Discord message

The bot sends an embed in this form, with all versions/statuses filled dynamically:

> **Youtube Version:** `21.34.243` (latest release (Morphe) & latest pre-release (Original))
>
> **Patches Version:** `1.41.0-dev.1` (latest dev)
>
> ⚠️ **ACHTUNG!** : Bitte überprüfe, dass deine originale YouTube app auf dem neuesten Stand ist, sonst könnte es zu abstürzen bzw Wiedergabe Fehler kommen.
>
> **APK herunterladen**

## State and duplicate prevention

`state.json` is updated only after the Discord message was sent successfully. That means a Discord outage does not permanently suppress the notification: the next scheduled run retries it. If the GitHub Release already exists, the workflow reuses the existing APK instead of patching it again.

## Storage note

The APK is not committed to Git. It is stored as a GitHub Release asset. Public distribution of modified proprietary APKs can attract copyright/DMCA complaints; if that becomes a problem, move the download asset to private storage and keep the same Discord-link flow.
