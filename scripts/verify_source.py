#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前自检：校验生成的 AltStore 源文件是否符合规范、链接是否可用。"""
import json
import os
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "alt_store.json")
ICON = os.path.join(HERE, "icon.png")
WORKFLOW = os.path.join(HERE, ".github", "workflows", "update-source.yml")

fails = []


def check(cond, msg):
    if cond:
        print(f"PASS  {msg}")
    else:
        print(f"FAIL  {msg}")
        fails.append(msg)


with open(OUT, "r", encoding="utf-8") as f:
    src = json.load(f)

check(isinstance(src.get("name"), str) and src["name"], "顶层 name 存在")
check(isinstance(src.get("identifier"), str) and "." in src["identifier"], "顶层 identifier 存在且像域名")
check(isinstance(src.get("iconURL"), str) and src["iconURL"].startswith("http"), "顶层 iconURL 存在")
check(isinstance(src.get("apps"), list) and src["apps"], "apps 非空")

app = src["apps"][0]
check(app.get("bundleIdentifier") == "org.mewx.wenku8Flutter", "bundleIdentifier 与 ipa 一致")
check(isinstance(app.get("versions"), list) and len(app["versions"]) >= 1, "versions 列表非空")
check(app.get("minOSVersion") == "13.0", "minOSVersion 来自 ipa")

v = app["versions"][0]
for field in ("version", "date", "localizedDescription", "downloadURL", "size", "minOSVersion"):
    check(field in v and v[field], f"version 项字段 {field} 存在")

check(app["version"] == v["version"], "顶层 version 与 versions[0] 一致")
check(app["downloadURL"] == v["downloadURL"], "顶层 downloadURL 与 versions[0] 一致")
check(app["size"] == v["size"] == 39277656, "size 与上游资产一致（39277656）")
check(v.get("sha256") == "dcf7a1b535ed644d1843baebee24acb5c7e13f5393606fe2c0b889ae10058d87", "sha256 与上游一致")
check(v["localizedDescription"].count("*") == 0, "版本说明中不含残留 Markdown 星号")

# 下载链接可达性
try:
    req = urllib.request.Request(v["downloadURL"], method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=60) as resp:
        check(resp.status == 200, f"downloadURL 可访问（HTTP {resp.status}）")
        cl = resp.headers.get("Content-Length")
        check(cl is None or int(cl) >= 0, f"Content-Length={cl}")
except Exception as exc:
    check(False, f"downloadURL 不可访问：{exc}")

# 图标
check(os.path.exists(ICON), "icon.png 存在")
if os.path.exists(ICON):
    with open(ICON, "rb") as f:
        data = f.read()
    head = data[:8]
    check(head == b"\x89PNG\r\n\x1a\n", "icon.png 是合法 PNG")
    if head == b"\x89PNG\r\n\x1a\n":
        idx = data.find(b"IHDR")
        if idx == -1:
            check(False, "icon.png 缺少 IHDR")
        else:
            w = int.from_bytes(data[idx + 4: idx + 8], "big")
            h = int.from_bytes(data[idx + 8: idx + 12], "big")
            check(w >= 120 and h >= 120, f"图标尺寸足够（{w}x{h}）")
            check(1 <= w / h <= 1.5, f"图标为方形比例（{w}x{h}）")

check(os.path.exists(WORKFLOW), "workflow 文件存在")
try:
    import yaml

    with open(WORKFLOW, "r", encoding="utf-8") as f:
        wf = yaml.safe_load(f)
    check(isinstance(wf, dict) and "jobs" in wf, "workflow YAML 可解析且含 jobs")
    check("schedule" in wf.get(True, wf.get("on", {})), "workflow 含 schedule 触发器")
except ImportError:
    print("SKIP  pyyaml 未安装，跳过 YAML 解析校验")
except Exception as exc:
    check(False, f"workflow YAML 解析失败：{exc}")

print()
if fails:
    print(f"共 {len(fails)} 项未通过")
    sys.exit(1)
print("全部检查通过")
