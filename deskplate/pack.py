# -*- coding: utf-8 -*-
"""一键打包（等价于 build.bat，但不依赖 cmd.exe，中文参数走 Unicode 传递）。

跑法：  python pack.py
产物：  dist/台签打印助手.exe
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
NAME = "台签打印助手"
EXCLUDES = [
    "tkinter",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtMultimedia",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtWebSockets",
    "PySide6.QtSvgWidgets",
]


def run(cmd):
    print("$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=BASE)
    print(f"  -> exit {r.returncode}", flush=True)
    return r.returncode


def main():
    print("python =", PY, flush=True)

    print("[1/3] 生成图标 ...", flush=True)
    if run([PY, "mkicon.py"]) != 0:
        print("图标生成失败，继续（沿用已有 app.ico）", flush=True)

    print("[2/3] 清理旧产物 ...", flush=True)
    for d in ("build", "dist"):
        p = os.path.join(BASE, d)
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p, ignore_errors=True)

    print("[3/3] PyInstaller 打包中（1-3 分钟）...", flush=True)
    args = [PY, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--windowed",
            "--name", NAME, "--icon", "app.ico"]
    for m in EXCLUDES:
        args += ["--exclude-module", m]
    args.append("app.py")
    rc = run(args)
    if rc != 0:
        return rc

    exe = os.path.join(BASE, "dist", NAME + ".exe")
    size = os.path.getsize(exe) if os.path.isfile(exe) else -1
    print(f"完成：{exe}", flush=True)
    print(f"体积：{size / 1048576:.1f} MB", flush=True)
    return 0 if size > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
