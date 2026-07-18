# WeChat Hook Config Extractor

Automatically extract mini-program login Hook config fields (`j1`, `c`, `a1`, `a7`) from WeChat APK, with **scheduled update detection** that triggers extraction automatically when a new version is found.

## Project Structure

```
wxcode_hook_config/
├── .github/workflows/
│   ├── check-wechat-update.yml   # Scheduled update checker workflow
│   └── extract-hook-config.yml   # Hook config extraction workflow
├── scripts/
│   └── extract_hook_config.py    # Core extraction script (CI-ready)
├── config/
│   ├── known_configs.json        # Known version configuration table
│   └── hook_config_*.json        # CI-generated per-version configs
├── .last_apk_url                 # Last successfully extracted APK URL
├── README.md
└── README.en.md
```

## Usage

### Method 1: GitHub Actions (Recommended)

**Manual trigger:**
1. Go to Actions → `提取微信 Hook 配置` → `Run workflow`
2. Enter the version number (e.g., `8.0.76`) and APK download URL
3. Download the `hook-config-xxx` artifact after completion

**Automatic update detection (scheduled):**
- Runs daily at UTC 2:00 (Beijing 10:00) via `check-wechat-update` workflow
- Fetches the [WeChat Android updates page](https://weixin.qq.com/updates?platform=android)
- Locates the "Download Latest Version" link to extract the APK direct URL and version
- Compares with the last successfully extracted URL; triggers config extraction if a new version is found
- Updates the `.last_apk_url` record after successful extraction to avoid duplicates

**Upload APK to trigger:**
1. Go to Actions → `上传微信 APK` → `Run workflow`
2. Enter the APK download URL
3. Automatically triggers the hook config extraction workflow

### Method 2: Local Execution

```bash
# Requires Java 17+ and jadx (auto-downloaded)
export JADX_HOME=tools/jadx

# Fast mode (~30 seconds)
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --fast --ci

# DEX fallback (skip decompilation, DEX-level search only)
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --dex-fallback

# Save to a specific file
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --fast -o output/hook_config_8.0.76.json

# Auto-detect APK version
python scripts/extract_hook_config.py wx-8.0.76.apk --detect-version
```

## Output Format

Generated config JSON is saved to `config/` (e.g., `config/hook_config_8.0.76.json`), alongside `known_configs.json`.

```json
{
  "j1": "hm0.j1",
  "c": "cl0.c",
  "a1": "plugin.appbrand.jsapi.auth.i2",
  "a7": "plugin.appbrand.jsapi.auth.m2"
}
```

## Config Fields

| Field | Description | Locating Method |
|-------|-------------|-----------------|
| `j1` | Task submitter class | Search for `.d().g(` chained call |
| `c` | Parameter construction class | `new XX.c(str, LinkedList, int, ...)` |
| `a1` | Single-parameter callback (o2 impl) | `new XX(this)` |
| `a7` | Dual-parameter callback (h80/j impl) | `new XX(this, callback)` |

## Known Version Configurations

| Version | j1 | c | a1 | a7 | Notes |
|---------|-----|-----|-----|-----|-------|
| 8.0.49 | `u70.k1` | `o60.c` | `b2` | `f2` | j1_instance=f |
| 8.0.62 | `of0.j1` | `he0.c` | `h2` | `l2` | |
| 8.0.70 | `yj0.j1` | `ti0.c` | `h2` | `l2` | |
| 8.0.71 | `tk0.j1` | `oj0.c` | `h2` | `l2` | |
| 8.0.72 | `dl0.k1` | `yj0.c` | `h2` | `l2` | |
| 8.0.74 | `gm0.j1` | `bl0.c` | `h2` | `l2` | |
| 8.0.76 | `hm0.j1` | `cl0.c` | `i2` | `m2` | Obfuscation shift! |

> **8.0.76 Note**: h2/l2 underwent an obfuscation shift and are no longer login callback implementations.
> - h2 → 2-param constructor, no longer a1 (o2 callback)
> - l2 → Parcelable.Creator, no longer a7 (dual-param callback)
> - i2 → New a1 (single-param o2 callback, `new i2(this)`)
> - m2 → New a7 (dual-param callback, `new m2(this, o2)`)

## Multi-Platform Sync

This repository supports dual-platform push to both **Gitee** and **GitHub**.

### Remote Configuration

| Remote | URL |
|--------|-----|
| `origin` | GitHub: `https://github.com/xiaojinwen/wxcode-hook-config.git` |
| `gitee` | Gitee: `https://gitee.com/xiaojinwen/wxcode-hook-config.git` |

`origin` has two `pushurl` entries configured; a plain `git push` automatically pushes to both GitHub and Gitee simultaneously.

### Sync Scripts

```bash
# Batch (Windows CMD)
scripts\sync-to-both.bat

# PowerShell (Windows / Linux / macOS)
pwsh scripts/sync-to-both.ps1
```

Scripts push to GitHub and Gitee sequentially; failure on one platform does not affect the other. Suitable for unstable network conditions.

### Manual Sync

```bash
# Push current branch to both platforms
git push origin master
git push gitee master

# Or use a single git push (auto-dual-send via pushurl: GitHub → Gitee)
git push
```

> ⚠ **Before first push**, ensure the GitHub repository `xiaojinwen/wxcode-hook-config` has been created and you have push access.

## CI Environment

### GitHub Actions

Located in `.github/workflows/`, includes two workflows:

**1. `check-wechat-update.yml` — Scheduled update checker**
- Trigger: Daily at UTC 2:00 (Beijing 10:00) + manual trigger
- Fetches the WeChat official update page and extracts the "Download Latest Version" link
- Compares with `.last_apk_url`; triggers extraction workflow if a new version is detected
- Updates `.last_apk_url` record and commits it to the repository on success

**2. `extract-hook-config.yml` — Hook config extraction**
- Trigger: Manual trigger / invoked by check-wechat-update
- Automatically:
  1. Installs Python 3.11 + Java 17
  2. Downloads jadx 1.5.5
  3. Fetches APK from URL or artifacts
  4. Fast decompiles the target package (~30 seconds)
  5. Extracts config and uploads as artifact

### Gitee CI

Located in `.gitee/workflows/`, uses Gitee pipeline format with functionality equivalent to GitHub Actions.

## License

This project is open-sourced under the [MIT](LICENSE) license.
