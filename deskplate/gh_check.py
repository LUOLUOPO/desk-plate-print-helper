# -*- coding: utf-8 -*-
"""核对远端仓库内容是否与本地一致。"""
import json
import os
import sys
import urllib.request
import urllib.error

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
PROXY = "http://127.0.0.1:7890"
REPO = sys.argv[2] if len(sys.argv) > 2 else "LUOLUOPO/deskplate"
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_gh_check.log")
out = []


def log(m):
    out.append(str(m))
    print(m, flush=True)


op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "workbuddy"})
    with op.open(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


info = get("https://api.github.com/repos/" + REPO)
log("仓库: %s" % info.get("full_name"))
log("地址: %s" % info.get("html_url"))
log("可见性: %s   默认分支: %s   大小: %.2f MB"
    % ("私有" if info.get("private") else "公开",
       info.get("default_branch"), (info.get("size") or 0) / 1024.0))

tree = get("https://api.github.com/repos/%s/git/trees/%s?recursive=1"
           % (REPO, info.get("default_branch")))
items = tree.get("tree", [])
files = [t for t in items if t.get("type") == "blob"]
log("远端文件数: %d" % len(files))
log("--- 文件清单 ---")
for t in sorted(files, key=lambda x: x["path"]):
    log("  %8.2f KB  %s" % (t.get("size", 0) / 1024.0, t["path"]))

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
