# -*- coding: utf-8 -*-
"""简化 Release 说明 + 提交并推送本地改动。"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
PROXY = "http://127.0.0.1:7890"
GIT = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
ROOT = r"C:\Users\Administrator\WorkBuddy\2026-09-21-18-06-52"
OWNER = "LUOLUOPO"
REPO = "desk-plate-print-helper"
TAG = "v1.0"
LOG = os.path.join(ROOT, "deskplate", "_gh_update.log")

out = []


def log(m=""):
    s = str(m).replace(TOKEN, "***")
    out.append(s)
    print(s, flush=True)


op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def api(path, method="GET", payload=None):
    h = {"Authorization": "Bearer " + TOKEN,
         "Accept": "application/vnd.github+json",
         "User-Agent": "workbuddy"}
    d = None
    if payload is not None:
        d = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    r = urllib.request.Request("https://api.github.com" + path, data=d,
                               method=method, headers=h)
    try:
        with op.open(r, timeout=120) as resp:
            b = resp.read()
            return resp.status, (json.loads(b.decode("utf-8")) if b else {})
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"raw": b[:300]}
    except Exception as e:
        return -1, {"err": repr(e)}


def run(args):
    e = dict(os.environ)
    e["http_proxy"] = PROXY
    e["https_proxy"] = PROXY
    e["HTTP_PROXY"] = PROXY
    e["HTTPS_PROXY"] = PROXY
    e["GIT_TERMINAL_PROMPT"] = "0"
    p = subprocess.run([GIT] + args, cwd=ROOT, env=e, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


RQ = urllib.parse.quote(REPO, safe="")
log("=== 简化 Release 说明 ===")
st, rel = api("/repos/%s/%s/releases/tags/%s" % (OWNER, RQ, TAG))
if st == 200:
    asset = rel["assets"][0]["name"] if rel.get("assets") else "DeskPlatePrintHelper.exe"
    body = (
        "15×8cm 台签排版打印工具，Windows 独立 exe，双击即用，无需安装。\n\n"
        "**下载**：`{a}`（36 MB）。下载后可改回中文名，不影响运行。\n"
        "_（GitHub 附件不支持中文文件名，所以这里是英文名。）_\n"
    ).format(a=asset)
    st2, _ = api("/repos/%s/%s/releases/%d" % (OWNER, RQ, rel["id"]),
                 "PATCH", {"name": "台签（桌签）打印助手 v1.0", "body": body})
    log("更新 -> %s" % st2)
else:
    log("取 Release 失败 %s" % st)

log("")
log("=== 提交推送 ===")
run(["add", "-A"])
rc, o, e = run(["status", "--porcelain"])
log("待提交 %d 项" % len([x for x in o.splitlines() if x.strip()]))
rc, o, e = run(["commit", "-m", "新增 README；示例改用虚构姓名并重出示例图"])
log("commit -> %s | %s" % (rc, (o or e)[:200]))
push_url = "https://%s:%s@github.com/%s/%s.git" % (OWNER, TOKEN, OWNER, RQ)
rc, o, e = run(["push", push_url, "HEAD:refs/heads/main"])
log("push -> %s | %s" % (rc, (o or e)[-300:]))
rc, o, e = run(["ls-files"])
log("远端跟踪文件数 %d" % len(o.splitlines()))

with open(LOG, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
