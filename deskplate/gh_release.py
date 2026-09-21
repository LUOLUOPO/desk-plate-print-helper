# -*- coding: utf-8 -*-
"""1) 仓库改名  2) 建 Release 并上传 exe  3) 把 exe 从仓库里移除。

用法： python gh_release.py <token> [新仓库名]
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import urllib.error

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
NEW_NAME = sys.argv[2] if len(sys.argv) > 2 else "desk-plate-print-helper"
OLD_REPO = "LUOLUOPO/deskplate"
PROXY = "http://127.0.0.1:7890"
GIT = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
ROOT = r"C:\Users\Administrator\WorkBuddy\2026-09-21-18-06-52"
EXE_REL = "台签打印助手/台签打印助手.exe"
TAG = "v1.0"
LOG = os.path.join(ROOT, "deskplate", "_gh_release.log")

out = []


def log(m=""):
    s = str(m).replace(TOKEN, "***")
    out.append(s)
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")


op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))


def req(url, method="GET", data=None, headers=None, raw=False):
    h = {"Authorization": "Bearer " + TOKEN,
         "Accept": "application/vnd.github+json",
         "User-Agent": "workbuddy"}
    if headers:
        h.update(headers)
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with op.open(r, timeout=300) as resp:
            b = resp.read()
            return resp.status, (b if raw else (json.loads(b.decode("utf-8"))
                                                if b else {}))
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, {"raw": b[:500]}
    except Exception as e:
        return -1, {"err": repr(e)}


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    return req("https://api.github.com" + path, method, data,
               {"Content-Type": "application/json"})


open(LOG, "w", encoding="utf-8").close()
log("=== 1. 仓库改名 ===")
st, info = api("/repos/%s" % OLD_REPO, "PATCH", {"name": NEW_NAME})
if st not in (200, 201):
    log("改名失败 status=%s body=%s" % (st, info))
    sys.exit(1)
full = info["full_name"]
owner = info["owner"]["login"]
rname = info["name"]
log("新仓库: %s" % full)
log("地址: %s" % info["html_url"])

# 本地 remote 跟着改
def run(args, extra_env=None):
    e = dict(os.environ)
    e["http_proxy"] = PROXY
    e["https_proxy"] = PROXY
    e["HTTP_PROXY"] = PROXY
    e["HTTPS_PROXY"] = PROXY
    e["GIT_TERMINAL_PROMPT"] = "0"
    if extra_env:
        e.update(extra_env)
    p = subprocess.run([GIT] + args, cwd=ROOT, env=e, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


new_url = "https://github.com/%s/%s.git" % (owner, urllib.parse.quote(rname))
run(["remote", "set-url", "origin", new_url])
log("origin -> %s" % new_url)

log("")
log("=== 2. 建 Release ===")
rel_path = "/repos/%s/%s/releases" % (owner, urllib.parse.quote(rname))
st, rel = api(rel_path, "POST", {
    "tag_name": TAG,
    "name": "台签打印助手 v1.0",
    "body": ("15×8cm 台签排版打印工具，Windows 独立 exe，无需安装。\n\n"
             "**功能**\n"
             "- 任意字数自动最大字号铺满；默认「拉伸铺满」：每段一行、整行横向撑满，不折行\n"
             "- 自带横向 / 纵向两个字形拉伸滑块（0.40×~2.50×），可手动决定字形胖瘦高矮\n"
             "- 可选系统已装字体，支持加粗 / 反白\n"
             "- A4 纸一次排 3 张，贴边排版只需 4 刀裁完；默认用废料区定位点，成品边缘无墨迹\n\n"
             "**下载**：下面的 `台签打印助手.exe` 即为可执行程序，双击即可运行。\n"
             "源码见仓库 `deskplate/`。"),
    "draft": False,
    "prerelease": False})
if st not in (200, 201):
    log("建 Release 失败 status=%s body=%s" % (st, rel))
    sys.exit(1)
rel_id = rel["id"]
log("Release: %s" % rel.get("html_url"))

exe_abs = os.path.join(ROOT, EXE_REL)
size = os.path.getsize(exe_abs)
log("上传 exe: %.2f MB" % (size / 1048576.0))
with open(exe_abs, "rb") as f:
    blob = f.read()
up = ("https://uploads.github.com/repos/%s/%s/releases/%d/assets?name=%s"
      % (owner, urllib.parse.quote(rname), rel_id,
         urllib.parse.quote("台签打印助手.exe")))
st, a = req(up, "POST", blob, {"Content-Type": "application/octet-stream",
                               "Accept": "application/vnd.github+json"})
if st not in (200, 201):
    log("上传失败 status=%s body=%s" % (st, a))
    sys.exit(1)
log("资源已上传: %s (%.2f MB, %d 次下载位就绪)"
    % (a.get("name"), (a.get("size") or 0) / 1048576.0, a.get("download_count") or 0))

log("")
log("=== 3. 从仓库移除 exe ===")
gi = os.path.join(ROOT, ".gitignore")
txt = open(gi, encoding="utf-8").read()
marker = "# 可执行文件放 GitHub Releases，不入库\n"
if "不入库" not in txt:
    txt = txt.rstrip() + "\n\n" + marker + "*.exe\n"
    open(gi, "w", encoding="utf-8").write(txt)
log(".gitignore 已加 *.exe")

rc, o, e = run(["rm", "--cached", "--quiet", EXE_REL])
log("git rm --cached -> %s" % rc)
rc, o, e = run(["add", "-A"])
rc, o, e = run(["commit", "-m", "exe 移至 Releases 下载，仓库只保留源码与文档"])
log("commit -> %s | %s" % (rc, (o or e)[:200]))

push_url = ("https://%s:%s@github.com/%s/%s.git"
            % (owner, TOKEN, owner, urllib.parse.quote(rname)))
rc, o, e = run(["push", push_url, "HEAD:refs/heads/main"])
log("push -> %s" % rc)
if o:
    log(o[-800:])
if e:
    log(e[-800:])
if rc != 0:
    sys.exit(1)

rc, o, e = run(["push", push_url, TAG])
log("push tag %s -> %s" % (TAG, rc))

st, fin = api("/repos/%s/%s" % (owner, urllib.parse.quote(rname)))
log("")
log("OK 仓库: %s" % fin.get("html_url"))
log("OK 下载: %s/releases/tag/%s" % (fin.get("html_url"), TAG))
