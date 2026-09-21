# 台签（桌签）打印助手

15×8cm 台签排版打印工具。输入姓名，自动最大字号铺满，A4 纸一次排 3 张，4 刀裁完。

## 下载

到 [Releases](https://github.com/LUOLUOPO/desk-plate-print-helper/releases) 下载 exe，双击即可运行，无需安装环境。

## 功能

- 任意字数自动最大字号铺满，不用手动调字号
- 默认「拉伸铺满」：每段一行、整行横向撑满，不会拆成两行
- 横向 / 纵向两个字形拉伸滑块，可手动决定字的胖瘦高矮
- 可选系统已装字体，支持加粗、反白（黑底白字）
- A4 一次排 3 张，贴边排版只需 4 刀；裁切标记默认只印在废料区，成品边缘不留墨

## 用法

1. 左侧输入姓名，一行一个；用 `|` 分隔多行内容（如 姓名|职务）
2. 右侧选字体，需要时拖动字形拉伸滑块
3. 打印后按定位点裁切即可

## 从源码运行

```bash
pip install PySide6-Essentials pyinstaller
python deskplate/app.py        # 运行
python deskplate/pack.py       # 打包成 exe
```

## 目录

| 路径 | 说明 |
|---|---|
| `deskplate/core.py` | 排版与渲染核心（几何量统一用毫米，预览与打印共用同一段代码） |
| `deskplate/app.py` | 界面 |
| `deskplate/verify_*.py` | 自检脚本：排版、拉伸、裁切标记、真裁模拟 |
| `台签打印助手/` | 交付物：exe、示例图 |
