#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为"仓库只有未签名 ipa、没有官方 AltStore 源"的项目生成 / 持续更新 AltStore + SideStore 源。

每次运行都会：
  1. 读取目标仓库最新的 GitHub Release（默认排除预发布）；
  2. 找到 iOS 未签名 ipa 资产，下载后解析包内 Info.plist；
  3. 生成 alt_store.json（含历史版本列表）并提取应用图标 icon.png。

用法：
    python scripts/update_source.py

环境变量（全部可选，括号内为默认值）：
    REPO_OWNER=mikufoxxx                目标仓库 owner
    REPO_NAME=Wenku8_Flutter            目标仓库名
    IPA_ASSET_SUFFIX=-ios-unsigned.ipa  iOS 资产文件名后缀
    OUTPUT_FILE=alt_store.json          输出源文件名
    ICON_FILE=icon.png                  输出图标文件名
    SOURCE_BRANCH=main                  源文件所在分支（用于拼 iconURL）
    MAX_VERSIONS=8                      源里保留的历史版本数
    INCLUDE_PRERELEASE=0                是否把预发布也当作可用版本
    GITHUB_TOKEN=...                    API token（Actions 里传 secrets.GITHUB_TOKEN）
"""

from __future__ import annotations

import io
import json
import os
import plistlib
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OWNER = os.environ.get("REPO_OWNER", "mikufoxxx")
REPO = os.environ.get("REPO_NAME", "Wenku8_Flutter")
IPA_ASSET_SUFFIX = os.environ.get("IPA_ASSET_SUFFIX", "-ios-unsigned.ipa")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "alt_store.json")
ICON_FILE = os.environ.get("ICON_FILE", "icon.png")
SOURCE_BRANCH = os.environ.get("SOURCE_BRANCH", "main")
MAX_VERSIONS = int(os.environ.get("MAX_VERSIONS", "8"))
INCLUDE_PRERELEASE = os.environ.get("INCLUDE_PRERELEASE", "0") == "1"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

SOURCE_NAME = os.environ.get("SOURCE_NAME", "轻小说文库 Wenku8 源")
SOURCE_IDENTIFIER = os.environ.get(
    "SOURCE_IDENTIFIER", "org.mewx.wenku8Flutter.altstore.source"
)
SOURCE_SUBTITLE = os.environ.get("SOURCE_SUBTITLE", "非官方 AltStore / SideStore 安装源")
SOURCE_DESCRIPTION = os.environ.get(
    "SOURCE_DESCRIPTION",
    "轻小说文库（Wenku8）第三方客户端的安装源。\n\n安装包直接来自上游 GitHub Release，未签名，需要自行签名后侧载。",
)
APP_NAME = os.environ.get("APP_NAME", "轻小说文库 Wenku8")
APP_SUBTITLE = os.environ.get("APP_SUBTITLE", "轻小说文库与本地书籍阅读器")
APP_DESCRIPTION = os.environ.get(
    "APP_DESCRIPTION",
    "轻小说文库（Wenku8）第三方阅读客户端，支持在线书架、本地书籍导入、离线阅读与朗读。"
    "安装包由上游 Release 提供，未签名，需自行签名侧载。",
)
TINT_COLOR = os.environ.get("TINT_COLOR", "#5B8DEF")

API_BASE = "https://api.github.com"
REPO_SLUG = f"{OWNER}/{REPO}"

# 本地仓库路径 -> raw 地址；Actions 里由 GITHUB_REPOSITORY 自动得到
SOURCE_REPO = os.environ.get("GITHUB_REPOSITORY", "")
ICON_BASE_URL = os.environ.get("ICON_BASE_URL", "")


def log(msg: str) -> None:
    print(msg, flush=True)


def api_get(url: str):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "altstore-source-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url: str) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "altstore-source-generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
HTML_TAG = re.compile(r"<[^>]+>")


def md_to_text(md: str, limit: int = 6000) -> str:
    """把 Release 说明里的 Markdown 压成纯文本，供 AltStore 显示。"""
    if not md:
        return ""
    text = HTML_COMMENT.sub("", md)
    text = MD_IMAGE.sub("", text)
    text = MD_LINK.sub(r"\1", text)
    text = HTML_TAG.sub("", text)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[>\-\*\+]\s*", "", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\*+", "", line).replace("~~", "")
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def pick_release(releases):
    """优先稳定版；没有稳定版时退回最新的一版（含预发布）。"""
    for rel in releases:
        if rel.get("draft"):
            continue
        if rel.get("prerelease") and not INCLUDE_PRERELEASE:
            continue
        return rel
    for rel in releases:
        if not rel.get("draft"):
            return rel
    return None


def pick_asset(release):
    for asset in release.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if name.endswith(IPA_ASSET_SUFFIX.lower()):
            return asset
    return None


def parse_ipa(data: bytes) -> dict:
    """从 ipa 里读出主 App 的元信息与图标。"""
    info: dict = {}
    icon_bytes = b""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        main_plist = [
            n
            for n in names
            if n.startswith("Payload/") and n.endswith(".app/Info.plist")
            and ".appex" not in n
        ]
        if not main_plist:
            raise RuntimeError("ipa 里没找到主 App 的 Info.plist")
        main_path = main_plist[0]
        with zf.open(main_path) as f:
            pl = plistlib.load(f)
        info["bundleIdentifier"] = pl.get("CFBundleIdentifier")
        info["displayName"] = pl.get("CFBundleDisplayName") or pl.get("CFBundleName")
        info["version"] = pl.get("CFBundleShortVersionString")
        info["build"] = pl.get("CFBundleVersion")
        info["minOSVersion"] = pl.get("MinimumOSVersion")
        info["privacy"] = {
            k: v
            for k, v in pl.items()
            if k.startswith("NS") and k.endswith("UsageDescription") and isinstance(v, str)
        }
        info["extensions"] = []
        for n in names:
            if ".appex/Info.plist" not in n:
                continue
            try:
                with zf.open(n) as f:
                    epl = plistlib.load(f)
                info["extensions"].append(
                    {
                        "identifier": epl.get("CFBundleIdentifier"),
                        "point": (epl.get("NSExtension") or {}).get(
                            "NSExtensionPointIdentifier"
                        ),
                    }
                )
            except Exception:
                continue

        # 找图标：优先 AppIcon60x60@2x.png，否则取 App 根目录里最大的 AppIcon*.png
        app_dir = main_path[: -len("Info.plist")]
        candidates = [
            n
            for n in names
            if n.startswith(app_dir)
            and n.count("/") == app_dir.count("/")
            and re.search(r"AppIcon.*\.png$", n, re.I)
        ]
        # 在候选图标里挑像素最大的一个，避免源里只放 120×120 的小图
        best_name, best_area = "", -1
        for n in candidates:
            try:
                with zf.open(n) as f:
                    head = f.read(64)
                if head[:8] != b"\x89PNG\r\n\x1a\n":
                    continue
                idx = head.find(b"IHDR")
                if idx == -1:
                    continue
                w = int.from_bytes(head[idx + 4: idx + 8], "big")
                h = int.from_bytes(head[idx + 8: idx + 12], "big")
                if w * h > best_area:
                    best_area, best_name = w * h, n
            except Exception:
                continue
        if best_name:
            with zf.open(best_name) as f:
                icon_bytes = f.read()
    return info, icon_bytes


def load_previous() -> dict:
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def icon_url() -> str:
    if ICON_BASE_URL:
        return ICON_BASE_URL.rstrip("/") + "/" + ICON_FILE
    slug = SOURCE_REPO or f"<your-github-user>/<your-repo>"
    return f"https://raw.githubusercontent.com/{slug}/{SOURCE_BRANCH}/{ICON_FILE}"


def main() -> int:
    log(f"查询 {REPO_SLUG} 的 Release…")
    releases = api_get(f"{API_BASE}/repos/{REPO_SLUG}/releases?per_page=15")
    release = pick_release(releases)
    if not release:
        log("没有可用的 Release，退出")
        return 1
    tag = release.get("tag_name") or ""
    asset = pick_asset(release)
    if not asset:
        log(f"Release {tag} 里没有以 {IPA_ASSET_SUFFIX} 结尾的资产，退出")
        return 1

    log(f"最新版本 {tag} -> {asset['name']} ({asset['size']} bytes)")

    info, icon_bytes = {}, b""
    try:
        log("下载并解析 ipa…")
        info, icon_bytes = parse_ipa(download(asset["browser_download_url"]))
    except Exception as exc:  # 下载失败时退回到已有源里的元信息
        log(f"解析 ipa 失败（{exc}），将沿用已有源中的 Bundle ID 等信息")
        prev = load_previous()
        prev_apps = prev.get("apps") or []
        if prev_apps:
            info["bundleIdentifier"] = prev_apps[0].get("bundleIdentifier")
            info["minOSVersion"] = prev_apps[0].get("minOSVersion")

    if not info.get("bundleIdentifier"):
        log("缺少 Bundle ID，无法生成源，退出")
        return 1

    if icon_bytes:
        with open(ICON_FILE, "wb") as f:
            f.write(icon_bytes)
        log(f"已写入图标 {ICON_FILE}（{len(icon_bytes)} bytes）")
    elif not os.path.exists(ICON_FILE):
        log("警告：没有拿到图标，源文件里的 iconURL 可能显示为占位图")

    published = release.get("published_at") or release.get("created_at") or ""
    try:
        date_str = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    digest = (asset.get("digest") or "").replace("sha256:", "")
    version = info.get("version") or tag.lstrip("v")
    description = md_to_text(release.get("body") or "")
    if not description:
        description = f"更新至 {version}。"

    version_entry = {
        "version": version,
        "date": date_str,
        "localizedDescription": description,
        "downloadURL": asset["browser_download_url"],
        "size": asset["size"],
        "minOSVersion": info.get("minOSVersion") or "13.0",
    }
    if digest:
        version_entry["sha256"] = digest

    prev = load_previous()
    prev_apps = prev.get("apps") or []
    prev_versions = []
    if prev_apps:
        prev_versions = prev_apps[0].get("versions") or []

    versions = [version_entry]
    seen = {version_entry["version"]}
    for old in prev_versions:
        v = old.get("version")
        if not v or v in seen:
            continue
        if old.get("downloadURL"):
            versions.append(old)
            seen.add(v)
    versions = versions[:MAX_VERSIONS]

    app = {
        "name": APP_NAME,
        "bundleIdentifier": info["bundleIdentifier"],
        "developerName": OWNER,
        "subtitle": APP_SUBTITLE,
        "localizedDescription": APP_DESCRIPTION,
        "iconURL": icon_url(),
        "tintColor": TINT_COLOR,
        "category": "other",
        "version": version,
        "versionDate": date_str,
        "versionDescription": description,
        "versionType": "release",
        "downloadURL": asset["browser_download_url"],
        "size": asset["size"],
        "minOSVersion": info.get("minOSVersion") or "13.0",
        "versions": versions,
    }
    if digest:
        app["sha256"] = digest
    if info.get("privacy"):
        app["appPermissions"] = {"entitlements": [], "privacy": info["privacy"]}

    source = {
        "name": SOURCE_NAME,
        "identifier": SOURCE_IDENTIFIER,
        "subtitle": SOURCE_SUBTITLE,
        "description": SOURCE_DESCRIPTION,
        "website": release.get("html_url") or f"https://github.com/{REPO_SLUG}",
        "tintColor": TINT_COLOR,
        "iconURL": icon_url(),
        "apps": [app],
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"已生成 {OUTPUT_FILE}：{version} ({info.get('build', '?')})，共 {len(versions)} 个版本记录")
    if info.get("extensions"):
        log("包内扩展（签名时需一并处理）：" + ", ".join(
            e.get("identifier") or "?" for e in info["extensions"]
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
