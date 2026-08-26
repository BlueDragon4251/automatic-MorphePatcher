# automatic-MorphePatcher

Automatically builds and publishes full Morphe-patched APKs for **YouTube** and **TikTok**, stores them as GitHub Release assets, and posts Discord embeds with external download links.

## YouTube

- Checks every hour at minute `17` and can also be run manually.
- Tracks the newest published **Morphe patches dev/pre-release**.
- Selects the numerically newest supported YouTube version from that exact patch release, including experimental targets.
- Detects whether the exact original YouTube build is stable, beta, or alpha through APKMirror.
- Downloads and verifies the exact original `com.google.android.youtube` APK before patching.
- Generates a Morphe options file and enables **every available YouTube patch**, including patches that are disabled by default. This is a true full-patch build rather than only Morphe's default selection.
- Uses the exact `.mpp` asset selected by the resolver so a newer upstream release appearing during a build cannot change the patch set mid-run.
- Publishes a GitHub Release and sends a Discord embed containing version/channel information and the external APK download link.
- Tracks the original release channel as state, so a beta-to-stable transition can trigger a new Discord notification even if the APK version itself is unchanged.

Workflow: `.github/workflows/patch-youtube.yml`

## TikTok

TikTok uses the custom patch repository:

`BlueDragon4251/tiktok-patches-for-morphe`

- Checks every hour at minute `37` and can also be run manually.
- Uses **normal/stable patch releases only**. GitHub drafts/pre-releases are rejected, and tag names containing `dev`, `alpha`, `beta`, `rc`, or `pre` are rejected as an additional guard.
- Resolves the TikTok version supported by the exact stable patch release.
- Downloads the exact original global TikTok APK and requires package `com.zhiliaoapp.musically` plus the exact target version before patching.
- Generates a Morphe options file and enables **every available TikTok patch**, including default-disabled patches, for a true full-patch build.
- Extracts the feature names and descriptions from the stable patch release metadata and includes the feature list in the GitHub Release and Discord embed automatically.
- Signs every published build with the same persistent project key so later project builds can update earlier project builds.
- After patching, verifies APK signatures, ZIP integrity, exact package/version, and parses every generated `classes*.dex` with Android `dexdump`.
- TikTok intentionally does not use Morphe Desktop's optional `--verify-with-sdk` developer check because that check can produce false positives and D8 crashes internally on the supported TikTok APK even after all patches were successfully applied. The explicit post-build checks above are used instead.

Workflow: `.github/workflows/patch-tiktok.yml`

## Full-patch behaviour

For both apps the workflow asks Morphe to create the complete filtered options catalog for the target package and then sets every discovered patch to `enabled: true`. The build log prints the exact `N/N` selection before patching. A real patch failure stops the build; patches are not silently skipped with `--continue-on-error`.

## Required GitHub Actions secrets

Create these repository secrets before scheduled/manual builds:

| Secret | Purpose |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token. The bot must have **View Channel**, **Send Messages**, and **Embed Links** permission in the target channel. |
| `DISCORD_CHANNEL_ID` | Numeric Discord channel ID where release embeds are posted. |
| `MORPHE_KEYSTORE_B64` | Base64-encoded persistent signing keystore. |
| `MORPHE_KEYSTORE_PASSWORD` | Keystore password and key-entry password. |
| `MORPHE_KEY_ALIAS` | Alias of the signing key inside the keystore. |

`GITHUB_TOKEN` is provided automatically by GitHub Actions and receives `contents: write` permission from the workflows.

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

## State and duplicate prevention

YouTube publication state is stored in `state.json`; TikTok publication state is stored separately in `state-tiktok.json`. State is written only after the Discord notification succeeds. Release assets can therefore be reused after a notification failure instead of rebuilding unnecessarily, while the next scheduled run can retry the missing notification.

Long builds also fetch/rebase the current `main` branch before committing state and retry a raced state push, so an unrelated repository update should not cause the final publication step to fail.

## Release storage

APKs are not committed to Git. They are published as GitHub Release assets and Discord receives only the external download URL.

Public distribution of modified proprietary APKs can attract copyright/DMCA complaints. If that becomes a problem, move the release assets to private/object storage while keeping the same Discord-link flow.
