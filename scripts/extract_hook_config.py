#!/usr/bin/env python3
"""
微信 Hook 配置提取工具 - CI 适配版

支持从 APK 反编译提取登录 Hook 配置（j1, c, a1, a7）。
可独立运行（本地 jadx）或在 GitHub Actions 中运行（自动下载 jadx）。

环境变量:
  JADX_HOME    - jadx 安装目录（默认: tools/jadx）
  JAVA_HOME    - JDK 路径（CI 自动配置）

用法:
  # 本地
  python scripts/extract_hook_config.py wx-8.0.76.apk 8.0.76 --fast

  # CI（工作在 /github/workspace/apk/ 下）
  python scripts/extract_hook_config.py /github/workspace/apk/wx-8.0.76.apk 8.0.76 --fast --ci
"""

import re, sys, json, os, subprocess, zipfile, shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================
# 已知版本配置（辅助消歧）
# ============================================================
KNOWN_CONFIGS: Dict[str, Dict[str, str]] = {
    "8.0.49": {"a1": "b2", "a7": "f2"},
    "8.0.62": {"a1": "h2", "a7": "l2"},
    "8.0.70": {"a1": "h2", "a7": "l2"},
    "8.0.71": {"a1": "h2", "a7": "l2"},
    "8.0.72": {"a1": "h2", "a7": "l2"},
    "8.0.74": {"a1": "h2", "a7": "l2"},
    "8.0.76": {"a1": "i2", "a7": "m2"},
}

# ============================================================
# 路径常量（CI 友好）
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "config"

# jadx 路径: 优先环境变量，其次工具目录
_JADX_HOME = os.environ.get("JADX_HOME")
if _JADX_HOME:
    JADX_PATH = Path(_JADX_HOME)
else:
    JADX_PATH = PROJECT_DIR / "tools" / "jadx"

# ============================================================
# 日志
# ============================================================
class Log:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    def ok(self, msg: str):     print(f"  [OK]   {msg}")
    def info(self, msg: str):   print(f"  [INFO] {msg}")
    def warn(self, msg: str):   print(f"  [WARN] {msg}")
    def err(self, msg: str):    print(f"  [ERR]  {msg}")
    def debug(self, msg: str):
        if self.verbose: print(f"  [DEBUG] {msg}")

# ============================================================
# jadx 管理
# ============================================================
def ensure_jadx(jadx_dir: Path, log: Log) -> Optional[Path]:
    """检查 jadx 是否存在，不存在则自动下载"""
    # Linux
    jadx_bin = jadx_dir / "bin" / "jadx"
    # Windows
    jadx_bat = jadx_dir / "bin" / "jadx.bat"

    if jadx_bin.exists():
        return jadx_bin
    if jadx_bat.exists():
        return jadx_bat

    # CI 环境中自动下载
    if os.environ.get("CI"):
        log.info("CI 环境: 自动下载 jadx ...")
        jadx_dir.mkdir(parents=True, exist_ok=True)
        import urllib.request
        import tarfile
        url = "https://github.com/skylot/jadx/releases/download/v1.5.5/jadx-1.5.5.zip"
        zip_path = jadx_dir / "jadx.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
            import zipfile as zf
            with zf.ZipFile(zip_path, 'r') as z:
                z.extractall(str(jadx_dir))
            zip_path.unlink()
            os.chmod(str(jadx_bin), 0o755)
            log.ok(f"jadx 已下载: {jadx_bin}")
            return jadx_bin
        except Exception as e:
            log.err(f"下载 jadx 失败: {e}")
            return None

    log.err(f"jadx 未找到: {jadx_dir}/bin/jadx")
    return None

# ============================================================
# 版本检测（从 APK 内部读取）
# ============================================================
def detect_version_from_apk(apk_path: Path, log: Log) -> Optional[str]:
    """
    直接从 APK 的 AndroidManifest 读取 versionName。
    优先级: aapt dump > aapt2 dump > grep 字符串回退
    """
    # 方式1: aapt dump badging（最可靠）
    for cmd_name in ['aapt', 'aapt2']:
        try:
            result = subprocess.run(
                [cmd_name, 'dump', 'badging', str(apk_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'versionName=' in line:
                        # 解析 versionName='8.0.76' 或 versionName="8.0.76"
                        m = re.search(r"versionName='([^']+)'", line)
                        if not m:
                            m = re.search(r'versionName="([^"]+)"', line)
                        if m:
                            ver = m.group(1)
                            log.ok(f"aapt 识别版本: {ver}")
                            return ver
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 方式2: 直接搜 APK 二进制中的版本号特征
    # AndroidManifest.xml 中的 versionName 通常以明文存储
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            # 从 resources.arsc 或 AndroidManifest.xml 中搜索
            for name in ['AndroidManifest.xml', 'resources.arsc']:
                if name in z.namelist():
                    data = z.read(name)
                    # 搜索 x.x.x 模式，过滤常见微信版本
                    for m in re.finditer(rb'(\d+)\.(\d+)\.(\d+)', data):
                        ver = f"{m.group(1).decode()}.{m.group(2).decode()}.{m.group(3).decode()}"
                        # 微信版本号特征: 主版本>=8
                        if int(m.group(1)) >= 8:
                            log.ok(f"从 {name} 识别版本: {ver}")
                            return ver
    except Exception:
        pass

    # 方式3: 搜 DEX 中的 versionName 附近字符串
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            for name in z.namelist():
                if name.endswith('.dex'):
                    data = z.read(name)
                    # 搜索 versionName 后面的版本号
                    idx = data.find(b'versionName')
                    if idx >= 0:
                        chunk = data[idx:idx+200]
                        m = re.search(rb'(\d+\.\d+\.\d+)', chunk)
                        if m and int(m.group(1).decode()) >= 8:
                            ver = m.group(1).decode()
                            log.ok(f"DEX 搜索识别版本: {ver}")
                            return ver
    except Exception:
        pass

    log.warn("无法从 APK 内部识别版本号")
    return None

# ============================================================
# DEX 搜索
# ============================================================
def find_dex_with_package(apk_path: Path, target_pkg: str, log: Log) -> List[str]:
    """在 APK 的 DEX 中搜索目标包路径"""
    needle = target_pkg.replace('.', '/').encode()
    found = []
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            for name in sorted(z.namelist()):
                if name.endswith('.dex'):
                    data = z.read(name)
                    pattern = b'L' + needle + b'/'
                    if pattern in data:
                        found.append(name)
                        classes = set()
                        idx = 0
                        while True:
                            idx = data.find(pattern, idx)
                            if idx < 0:
                                break
                            end = data.find(b';', idx)
                            if end > idx:
                                classes.add(data[idx:end+1].decode('ascii', errors='replace'))
                            idx += 1
                        log.debug(f"  {name}: {len(classes)} 个类")
    except Exception as e:
        log.err(f"DEX 扫描失败: {e}")
    return found

def search_dex_for_class(apk_path: Path, class_descriptor: bytes) -> bool:
    """在 DEX 中搜索类描述符"""
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            for name in z.namelist():
                if name.endswith('.dex') and class_descriptor in z.read(name):
                    return True
    except Exception:
        pass
    return False

def search_dex_for_string(apk_path: Path, s: str) -> Optional[str]:
    """在 DEX 中搜索字符串，返回所在 DEX 文件名"""
    needle = s.encode('utf-8')
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            for name in sorted(z.namelist()):
                if name.endswith('.dex') and needle in z.read(name):
                    return name
    except Exception:
        pass
    return None

# ============================================================
# 反编译
# ============================================================
def decompile_apk_fast(apk_path: Path, version: str, jadx: Path, log: Log,
                       target_pkg: str = "com.tencent.mm.plugin.appbrand.jsapi.auth",
                       work_dir: Optional[Path] = None) -> Optional[Path]:
    """快速反编译：仅反编译目标包所在的 DEX 文件"""
    if work_dir is None:
        work_dir = PROJECT_DIR / ".work" / version
    sources_dir = work_dir / "sources"

    if sources_dir.exists():
        pkg_path = sources_dir / target_pkg.replace('.', '/')
        if pkg_path.exists():
            log.ok(f"已有反编译结果: {sources_dir}")
            return sources_dir
        shutil.rmtree(str(work_dir))

    # 1. 提取 DEX
    dex_dir = work_dir / "dex"
    dex_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"1/3 提取 DEX...")
    dex_files = []
    try:
        with zipfile.ZipFile(str(apk_path), 'r') as z:
            for name in z.namelist():
                if name.endswith('.dex'):
                    z.extract(name, str(dex_dir))
                    dex_files.append(dex_dir / name)
    except Exception as e:
        log.err(f"DEX 提取失败: {e}")
        return None
    log.ok(f"提取 {len(dex_files)} 个 DEX")

    # 2. 定位目标包所在 DEX
    log.info(f"2/3 在 DEX 中搜索包: {target_pkg}")
    target_dexes = find_dex_with_package(apk_path, target_pkg, log)
    if not target_dexes:
        log.warn(f"未找到 {target_pkg}，反编译全部 DEX")
        target_dexes = [f.name for f in dex_files]
    log.ok(f"定位 {len(target_dexes)} 个目标 DEX")

    # 3. 反编译目标 DEX
    log.info(f"3/3 反编译目标 DEX...")
    target_paths = [str(dex_dir / d) for d in target_dexes]
    cmd = [str(jadx), "-d", str(work_dir), "--no-res", "--no-debug-info"] + target_paths
    log.debug(" ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            log.warn(f"jadx 返回: {result.returncode}")
        if result.stderr:
            for line in result.stderr.split('\n')[:5]:
                log.debug(line.strip())
    except subprocess.TimeoutExpired:
        log.err("反编译超时")
        return None

    if sources_dir.exists():
        log.ok(f"反编译完成: {sources_dir}")
        return sources_dir
    log.err("反编译失败")
    return None

# ============================================================
# 搜索策略
# ============================================================
SEARCH_STRATEGIES = {
    "v3": {
        "j1": [
            re.compile(r'(?P<pkg>\w+)\.(?P<cls>\w+)\.(?P<static_m>[a-z])\s*\(\s*\)\s*\.\s*(?P<instance_m>[a-z])\s*\('),
            re.compile(r'(?P<pkg>\w+)\.(?P<cls>\w+)\.(?P<static_m>[a-z])\(\)\s*\n\s*\.\s*(?P<instance_m>[a-z])\s*\('),
        ],
        "c": [
            re.compile(r'new\s+(?P<pkg>\w+)\.(?P<cls>\w+)\s*\([^)]{10,}'),
        ],
        "a1": [
            re.compile(r'(?P<cls>\w+)\s+\w+\s*=\s*new\s+(?P=cls)\s*\(\s*this\s*\)'),
        ],
        "a7": [
            re.compile(r'(?P<cls>\w+)\s+\w+\s*=\s*new\s+(?P=cls)\s*\(\s*this\s*,'),
        ],
    }
}

# ============================================================
# 提取器
# ============================================================
class ConfigExtractor:
    def __init__(self, sources_dir: Path, version: str, log: Log):
        self.sources = sources_dir
        self.version = version
        self.log = log
        self.known = KNOWN_CONFIGS.get(version, {})
        self.result: Dict = {}

    def _find_login_task(self) -> Optional[Path]:
        for p in [
            self.sources / "com/tencent/mm/plugin/appbrand/jsapi/auth/JsApiLogin$LoginTask.java",
            self.sources / "com/tencent/mm/plugin/appbrand/jsapi/auth/JsApiLogin.java",
        ]:
            if p.exists():
                return p
        appbrand = self.sources / "com/tencent/mm/plugin/appbrand"
        if appbrand.exists():
            for f in appbrand.rglob("*.java"):
                try:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    if "post initialized" in content:
                        self.log.ok(f"定位登录文件: {f.relative_to(self.sources)}")
                        return f
                except Exception:
                    pass
        return None

    def _search_j1(self, content: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        for pattern in SEARCH_STRATEGIES["v3"]["j1"]:
            m = pattern.search(content)
            if m:
                full = f"{m.group('pkg')}.{m.group('cls')}"
                return full, m.groupdict().get("static_m"), m.groupdict().get("instance_m")
        fallback = re.search(r'(\w+)\.(\w+)\.\w\(\)\.\w\(', content)
        if fallback:
            return f"{fallback.group(1)}.{fallback.group(2)}", None, None
        return None, None, None

    def _count_params(self, content: str, class_full: str) -> Optional[int]:
        escaped = re.escape(class_full)
        for m in re.finditer(r'new\s+' + escaped + r'\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)', content):
            params_str = m.group(1).strip()
            if not params_str:
                return 0
            parts = []
            depth, current = 0, []
            for ch in params_str:
                if ch in '<(': depth += 1; current.append(ch)
                elif ch in ')>': depth -= 1; current.append(ch)
                elif ch == ',' and depth == 0:
                    parts.append(''.join(current).strip()); current = []
                else: current.append(ch)
            if current: parts.append(''.join(current).strip())
            filtered = [p for p in parts if p]
            return len(filtered) if filtered else None
        return None

    def extract(self) -> Optional[Dict]:
        self.log.info(f"分析微信 {self.version}")
        login_file = self._find_login_task()
        if not login_file:
            self.log.err("未找到登录核心文件")
            return None

        self.log.ok(f"核心文件: {login_file.relative_to(self.sources)}")
        content = login_file.read_text(encoding='utf-8', errors='ignore')

        # j1
        j1_raw, static_m, instance_m = self._search_j1(content)
        static = static_m or "d"
        instance = instance_m or "g"
        if j1_raw:
            self.log.ok(f"j1 = {j1_raw}  (static={static}(), instance=.{instance}())")
        else:
            self.log.warn("j1 未找到")

        # c
        c = None
        c_candidates = []
        for m in SEARCH_STRATEGIES["v3"]["c"][0].finditer(content):
            full = f"{m.group('pkg')}.{m.group('cls')}"
            if full not in c_candidates:
                c_candidates.append(full)
        if c_candidates:
            scored = []
            for full in c_candidates:
                pc = self._count_params(content, full)
                score = 0
                if pc and pc >= 6: score += 10
                if pc and pc == 8: score += 5
                pkg = full.split('.')[0]
                cls = full.split('.')[-1]
                if (self.sources / pkg / f"{cls}.java").exists(): score += 3
                scored.append((score, full, pc))
            scored.sort(key=lambda x: -x[0])
            c = scored[0][1]
            self.log.ok(f"c = {c}  (评分 {scored[0][0]})")
        else:
            self.log.warn("c 未找到")

        # a1 / a7
        a1, a7 = None, None
        for role, pats in [("a1", SEARCH_STRATEGIES["v3"]["a1"]),
                           ("a7", SEARCH_STRATEGIES["v3"]["a7"])]:
            candidates = []
            for pattern in pats:
                for m in pattern.finditer(content):
                    cls = m.group("cls")
                    if cls not in candidates:
                        candidates.append(cls)
            if candidates:
                expected_cls = self.known.get(role)
                scored = []
                for cls in candidates:
                    score = 0
                    if expected_cls and cls == expected_cls: score += 10
                    if (self.sources / "com/tencent/mm/plugin/appbrand/jsapi/auth" / f"{cls}.java").exists():
                        score += 5
                    scored.append((score, cls))
                scored.sort(key=lambda x: -x[0])
                best = scored[0][1]
                result = f"plugin.appbrand.jsapi.auth.{best}"
                self.log.ok(f"{role} = {result}")
                if role == "a1": a1 = result
                else: a7 = result
            else:
                self.log.warn(f"{role} 未找到")

        self.result = {
            "j1": j1_raw,
            "c": c,
            "a1": a1,
            "a7": a7,
            "j1_static_method": static,
            "j1_instance_method": instance,
        }
        return self.result

    def to_json(self) -> dict:
        """返回输出字典"""
        r = self.result
        out = {self.version: {}}
        for k in ("j1", "c", "a1", "a7"):
            if r.get(k): out[self.version][k] = r[k]
        meta = {}
        if r.get("j1_static_method") and r["j1_static_method"] != "d":
            meta["j1_static_method"] = r["j1_static_method"]
        if r.get("j1_instance_method") and r["j1_instance_method"] != "g":
            meta["j1_instance_method"] = r["j1_instance_method"]
        if meta: out[self.version].update(meta)
        return out

# ============================================================
# DEX 兜底搜索
# ============================================================
class DexFallbackSearcher:
    def __init__(self, apk_path: Path, version: str, log: Log):
        self.apk = apk_path
        self.version = version
        self.log = log
        self.known = KNOWN_CONFIGS.get(version, {})

    def search(self) -> Dict:
        result = {"j1": None, "c": None, "a1": None, "a7": None}
        self.log.info("DEX 兜底搜索...")

        marker = search_dex_for_string(self.apk, "Call post initialized callbacks now")
        if marker:
            self.log.ok(f"字符串确认: 'Call post initialized callbacks now' 在 {marker}")

        candidates = {"j1": [], "c": [], "a1": [], "a7": []}

        for dex_suffix in ['j1', 'k1']:
            for prefix in ['hm0', 'gm0', 'dl0', 'tk0', 'yj0', 'of0', 'u70']:
                desc = f'L{prefix}/{dex_suffix};'.encode()
                if search_dex_for_class(self.apk, desc):
                    candidates["j1"].append(f"{prefix}.{dex_suffix}")

        for cname in ['c', 'd']:
            for prefix in ['cl0', 'bl0', 'yj0', 'oj0', 'ti0', 'he0', 'o60']:
                desc = f'L{prefix}/{cname};'.encode()
                if search_dex_for_class(self.apk, desc):
                    candidates["c"].append(f"{prefix}.{cname}")

        if "a1" in self.known:
            result["a1"] = f"plugin.appbrand.jsapi.auth.{self.known['a1']}"
            self.log.ok(f"a1 = {result['a1']} (已知)")
        if "a7" in self.known:
            result["a7"] = f"plugin.appbrand.jsapi.auth.{self.known['a7']}"
            self.log.ok(f"a7 = {result['a7']} (已知)")

        for key in ["j1", "c"]:
            if candidates[key]:
                result[key] = candidates[key][0]
                self.log.ok(f"{key} = {result[key]} (DEX 确认)")

        return result

    def to_json(self, result: Dict) -> dict:
        out = {self.version: {}}
        for k in ("j1", "c", "a1", "a7"):
            if result.get(k): out[self.version][k] = result[k]
        return out


# ============================================================
# 主入口
# ============================================================
def main():
    import argparse

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="微信 Hook 配置提取工具 - CI 适配版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="APK 文件路径")
    parser.add_argument("version", nargs="?", default=None, help="版本号（如 8.0.76）")
    parser.add_argument("--fast", action="store_true", help="快速模式：仅反编译目标 DEX")
    parser.add_argument("--target-pkg", default="com.tencent.mm.plugin.appbrand.jsapi.auth",
                        help="目标包路径")
    parser.add_argument("--dex-fallback", action="store_true",
                        help="仅 DEX 搜索，跳过反编译解析")
    parser.add_argument("--ci", action="store_true", help="CI 模式：自动下载 jadx")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--auto", action="store_true", help="从文件名推断版本")
    parser.add_argument("--detect-version", action="store_true",
                        help="从 APK 内部读取 versionName（需要安装 aapt）")

    args = parser.parse_args()
    log = Log(args.verbose)

    input_path = Path(args.input)
    if not input_path.exists():
        log.err(f"文件不存在: {input_path}")
        sys.exit(1)

    # 版本号优先级: 手动指定 > APK 内部 > 文件名推断 > unknown
    version = args.version
    if not version and args.detect_version:
        detected = detect_version_from_apk(input_path, log)
        if detected:
            version = detected
            log.info(f"APK 内部识别版本: {version}")
    if not version and args.auto:
        m = re.search(r'(\d+\.\d+\.\d+)', input_path.name)
        if m:
            version = m.group(1)
            log.info(f"文件名推断版本: {version}")
    if not version:
        version = "unknown"
        log.warn(f"版本未知: '{version}'")

    is_apk = input_path.suffix.lower() in ('.apk',)
    if not is_apk:
        log.err("输入必须是 .apk 文件")
        sys.exit(1)

    # 确保 jadx
    jadx = ensure_jadx(JADX_PATH, log)
    if not jadx and not args.dex_fallback:
        log.err("jadx 不可用，请设置 JADX_HOME 或使用 --dex-fallback")
        sys.exit(1)

    # ---------- 执行 ----------
    config = None

    if args.dex_fallback:
        searcher = DexFallbackSearcher(input_path, version, log)
        result = searcher.search()
        searcher.print_result(result) if hasattr(searcher, 'print_result') else None
        config = searcher.to_json(result)
    elif args.fast or args.ci:
        log.info(f"快速模式: 反编译 '{args.target_pkg}' ...")
        sources = decompile_apk_fast(input_path, version, jadx, log, args.target_pkg)
        if sources:
            extractor = ConfigExtractor(sources, version, log)
            config_map = extractor.extract()
            if config_map:
                config = extractor.to_json()
        if not config:
            log.warn("反编译解析失败，尝试 DEX 兜底...")
            searcher = DexFallbackSearcher(input_path, version, log)
            result = searcher.search()
            config = searcher.to_json(result)
    else:
        sources = decompile_apk_fast(input_path, version, jadx, log, args.target_pkg)
        if sources:
            extractor = ConfigExtractor(sources, version, log)
            config_map = extractor.extract()
            if config_map:
                config = extractor.to_json()
        if not config:
            log.warn("标准模式失败，尝试 DEX 兜底...")
            searcher = DexFallbackSearcher(input_path, version, log)
            result = searcher.search()
            config = searcher.to_json(result)

    if not config:
        log.err("提取失败")
        sys.exit(1)

    # 输出
    output_path = args.output
    if not output_path:
        # CI 模式默认输出到 output/
        output_dir = OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"hook_config_{version}.json")

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    log.ok(f"配置已保存: {out_p}")
    print()
    print(json.dumps(config, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
