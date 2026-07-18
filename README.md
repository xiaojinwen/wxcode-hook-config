# 微信 Hook 配置提取工具

从微信 APK 自动提取小程序登录 Hook 配置项（`j1`, `c`, `a1`, `a7`），并支持**定时检查微信更新**，发现新版本后自动触发提取。

## 目录结构

```
wxcode_hook_config/
├── .github/workflows/
│   ├── check-wechat-update.yml   # 定时检查更新 workflow
│   └── extract-hook-config.yml   # 提取 Hook 配置 workflow
├── scripts/
│   └── extract_hook_config.py    # 核心提取脚本（CI 适配）
├── config/
│   ├── known_configs.json        # 已知版本配置表
│   └── hook_config_*.json        # CI 生成的单版本配置
├── .last_apk_url                 # 上次成功提取的 APK 链接记录
├── README.md
└── README.en.md
```

## 使用方式

### 方式一：GitHub Actions（推荐）

**手动触发提取：**
1. 打开 Actions → `提取微信 Hook 配置` → `Run workflow`
2. 填写版本号（如 `8.0.76`）和 APK 下载链接
3. 运行完成后下载 `hook-config-xxx` artifact

**自动检测更新（定时任务）：**
- 每天 UTC 2:00（北京时间 10:00），`check-wechat-update` workflow 自动运行
- 抓取 [微信 Android 更新页面](https://weixin.qq.com/updates?platform=android)
- 定位到「下载最新版本」链接，提取 APK 直链和版本号
- 与上次提取过的链接对比，如有新版本则自动触发 `提取微信 Hook 配置` workflow
- 提取成功后更新 `.last_apk_url` 记录，避免重复提取

**直接上传 APK 触发：**
1. 打开 Actions → `上传微信 APK` → `Run workflow`
2. 填写 APK 下载链接
3. 自动触发配置提取 workflow

### 方式二：本地运行

```bash
# 需要 Java 17+ 和 jadx（自动下载）
export JADX_HOME=tools/jadx

# 快速模式（30 秒）
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --fast --ci

# DEX 兜底（跳过反编译，仅 DEX 级别搜索）
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --dex-fallback

# 保存到指定文件
python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --fast -o output/hook_config_8.0.76.json

# 自动检测 APK 版本号
python scripts/extract_hook_config.py wx-8.0.76.apk --detect-version
```

## 输出格式

生成的配置 JSON 会保存在 `config/` 目录下（如 `config/hook_config_8.0.76.json`），与 `known_configs.json` 放在一起。

```json
{
  "j1": "hm0.j1",
  "c": "cl0.c",
  "a1": "plugin.appbrand.jsapi.auth.i2",
  "a7": "plugin.appbrand.jsapi.auth.m2"
}
```

## 配置项说明

| 字段 | 说明 | 定位方式 |
|------|------|----------|
| `j1` | 任务提交器类 | 搜索 `.d().g(` 链式调用 |
| `c` | 参数构造类 | `new XX.c(str, LinkedList, int, ...)` |
| `a1` | 单参回调（o2 实现） | `new XX(this)` |
| `a7` | 双参回调（h80/j 实现） | `new XX(this, callback)` |

## 已知版本配置

| 版本 | j1 | c | a1 | a7 | 备注 |
|------|-----|-----|-----|-----|------|
| 8.0.49 | `u70.k1` | `o60.c` | `b2` | `f2` | j1_instance=f |
| 8.0.62 | `of0.j1` | `he0.c` | `h2` | `l2` | |
| 8.0.70 | `yj0.j1` | `ti0.c` | `h2` | `l2` | |
| 8.0.71 | `tk0.j1` | `oj0.c` | `h2` | `l2` | |
| 8.0.72 | `dl0.k1` | `yj0.c` | `h2` | `l2` | |
| 8.0.74 | `gm0.j1` | `bl0.c` | `h2` | `l2` | |
| 8.0.76 | `hm0.j1` | `cl0.c` | `i2` | `m2` | 混淆位移！ |

> **8.0.76 注意**: h2/l2 发生了混淆位移，不再是登录回调实现。
> - h2 → 2 参构造，不再是 a1(o2 回调)
> - l2 → Parcelable.Creator，不再是 a7(双参回调)
> - i2 → 新的 a1（单参 o2 回调，`new i2(this)`）
> - m2 → 新的 a7（双参回调，`new m2(this, o2)`）

## 多平台同步

本仓库同时支持 **Gitee** 和 **GitHub** 双平台提交和 CI。

### 远程仓库配置

| 远程名 | 地址 |
|--------|------|
| `origin` | GitHub: `https://github.com/xiaojinwen/wxcode-hook-config.git` |
| `gitee` | Gitee: `https://gitee.com/xiaojinwen/wxcode-hook-config.git` |

`origin` 已配置两个 `pushurl`，直接 `git push` 会自动同时推送到 GitHub 和 Gitee。

### 一键同步脚本

```bash
# 批处理（Windows CMD）
scripts\sync-to-both.bat

# PowerShell（Windows / Linux / macOS）
pwsh scripts/sync-to-both.ps1
```

脚本会依次推送到 GitHub 和 Gitee，任一失败不影响另一平台，适合网络不稳定场景。

### 手动操作

```bash
# 推送当前分支到两个平台
git push origin master
git push gitee master

# 或者直接 git push（利用 pushurl 自动双发：GitHub → Gitee）
git push
```

> ⚠ **首次推送前**，请确保 GitHub 仓库 `xiaojinwen/wxcode-hook-config` 已创建且有推送权限。

## CI 环境

### GitHub Actions

位于 `.github/workflows/`，包含两个 workflow：

**1. `check-wechat-update.yml` — 定时检查微信更新**
- 触发：每天 UTC 2:00（北京时间 10:00）+ 手动触发
- 抓取微信官方更新页面，提取「下载最新版本」链接
- 与 `.last_apk_url` 对比，检测到新版本时自动触发提取 workflow
- 提取成功后更新 `.last_apk_url` 记录并提交到仓库

**2. `extract-hook-config.yml` — 提取 Hook 配置**
- 触发：手动触发 / 被 check-wechat-update 调用
- 运行时自动：
  1. 安装 Python 3.11 + Java 17
  2. 下载 jadx 1.5.5
  3. 从 URL 或 artifacts 获取 APK
  4. 快速反编译目标包（仅 30 秒）
  5. 提取配置并上传为 artifact

### Gitee CI

位于 `.gitee/workflows/`，使用 Gitee 流水线格式，功能与 GitHub Actions 一致。

## 许可证

本项目基于 [MIT](LICENSE) 许可证开源。
