# 微信 Hook 配置提取工具

从微信 APK 自动提取小程序登录 Hook 配置项（`j1`, `c`, `a1`, `a7`）。

## 目录结构

```
wxcode_hook_config/
├── .github/workflows/
│   ├── extract-hook-config.yml  # 主 workflow: 提取配置
│   └── upload-apk.yml           # 辅助: 上传 APK 后触发提取
├── scripts/
│   └── extract_hook_config.py   # 核心提取脚本（CI 适配）
├── config/
│   ├── known_configs.json       # 已知版本配置表
│   └── hook_config_*.json       # CI 生成的单版本配置
└── README.md
```

## 使用方式

### 方式一：GitHub Actions（推荐）

**手动触发：**
1. 打开 Actions → `提取微信 Hook 配置` → `Run workflow`
2. 填写版本号（如 `8.0.76`）和 APK 下载链接
3. 运行完成后下载 `hook-config-xxx` artifact

**上传 APK 自动触发：**
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
```

## 输出格式

生成的配置 JSON 会保存在 `config/` 目录下（如 `config/hook_config_8.0.76.json`），与 `known_configs.json` 放在一起。

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

## CI 环境

GitHub Actions 运行时会自动：
1. 安装 Python 3.11 + Java 17
2. 下载 jadx 1.5.5
3. 从 URL 或 artifacts 获取 APK
4. 快速反编译目标包（仅 30 秒）
5. 提取配置并上传为 artifact
