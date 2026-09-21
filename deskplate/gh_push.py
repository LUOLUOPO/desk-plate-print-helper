# -*- coding: utf-8 -*-
"""把台签打印助手推到用户的 GitHub。

走本机的 Clash 混合代理 127.0.0.1:7890（直连与系统默认代理都到不了 GitHub）。
用法： python gh_push.py <token>
"""
import json
import os
import ssl
import subprocess
import sys
import urllib.request
import urllib.error

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
PROXY = "http://127.0.0.1:7890"
GIT = r"C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
ROOT = r"C:\Users\Administrator\WorkBuddy\2026-09-21-18-06-52"
REPO_NAME = "desk-plate-print-helper"
LOG = os.path.join(ROOT, "deskplate", "_gh_push.log")

CTX = ssl.create_default_context()

out = []


def log(m=""):
    s = str(m).replace(TOKEN, "***")
    out.append(s)
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")


def opener():
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}),
        urllib.request.HTTPSHandler(context=CTX))
    return op


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        "https://api.github.com" + path, data=data, method=method,
        headers={"Authorization": "Bearer " + TOKEN,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "workbuddy",
                 "Content-Type": "application/json"})
    try:
        with opener().open(req, timeout=60) as r:
            body = r.read().decode("utf-8")
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:400]}
    except Exception as e:
        return -1, {"err": repr(e)}


def run(args, cwd=ROOT, extra_env=None):
    e = dict(os.environ)
    e["http_proxy"] = PROXY
    e["https_proxy"] = PROXY
    e["HTTP_PROXY"] = PROXY
    e["HTTPS_PROXY"] = PROXY
    e["GIT_TERMINAL_PROMPT"] = "0"
    if extra_env:
        e.update(extra_env)
    p = subprocess.run([GIT] + args, cwd=cwd, env=e, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


open(LOG, "w", encoding="utf-8").close()
log("=== gh_push via %s ===" % PROXY)

st, me = api("/user")
if st != 200:
    log("FATAL: 拿不到账号 status=%s body=%s" % (st, me))
    sys.exit(1)
owner = me.get("login")
log("账号: %s (%s)" % (owner, me.get("name") or "-"))

st, info = api("/repos/%s/%s" % (owner, REPO_NAME))
if st == 200:
    log("仓库已存在: %s" % info.get("html_url"))
    clone_url = info["clone_url"]
else:
    st2, info2 = api("/user/repos", "POST",
                     {"name": REPO_NAME,
                      "description": "台签打印助手 - 15x8cm 台签排版打印工具（PySide6 + PyInstaller）",
                      "private": False, "auto_init": False})
    if st2 not in (200, 201):
        log("FATAL: 创建仓库失败 status=%s body=%s" % (st2, info2))
        sys.exit(1)
    log("仓库已创建: %s" % info2.get("html_url"))
    clone_url = info2["clone_url"]

if not os.path.isdir(os.path.join(ROOT, ".git")):
    rc, o, e = run(["init", "-b", "main"])
    log("git init -> %s" % rc)
rc, o, e = run(["config", "user.email"])
if not o:
    run(["config", "user.email", "%s@users.noreply.github.com" % owner])
rc, o, e = run(["config", "user.name"])
if not o:
    run(["config", "user.name", owner])
log("identity: %s <%s>" % (run(["config", "user.name"])[1],
                           run(["config", "user.email"])[1]))

rc, o, e = run(["remote", "get-url", "origin"])
if rc != 0:
    run(["remote", "add", "origin", clone_url])
else:
    run(["remote", "set-url", "origin", clone_url])
log("origin = %s" % clone_url)

run(["config", "http.proxy", PROXY])
run(["config", "https.proxy", PROXY])
run(["config", "http.postBuffer", "524288000"])

rc, o, e = run(["add", "-A"])
log("git add -> %s" % rc)
rc, o, e = run(["status", "--porcelain"])
n = len([x for x in o.splitlines() if x.strip()]) if o else 0
log("待提交文件数: %d" % n)
rc, o, e = run(["commit", "-m", "初始提交：台签打印助手（源码 + exe + 示例图 + 使用说明）"])
log("git commit -> %s | %s" % (rc, (o or e)[:300]))

push_url = clone_url.replace("https://github.com/",
                             "https://%s:%s@github.com/" % (owner, TOKEN))
rc, o, e = run(["push", "-u", push_url, "HEAD:refs/heads/main"])
log("git push -> %s" % rc)
if o:
    log(o[-1500:])
if e:
    log(e[-1500:])
if rc != 0:
    sys.exit(1)

st, info3 = api("/repos/%s/%s" % (owner, REPO_NAME))
log("OK: %s" % info3.get("html_url"))
