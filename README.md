Voice Calendar Assistant

基于语音识别 + NLP + Playwright 自动创建 Google Calendar 日程的助手。

本项目为一次“编程实战题”实现，目标是在严格时间限制下构建一个可用 Demo：
通过语音输入 → 转文字 → NLP 提取时间&标题 → Playwright 登录 Google Calendar → 自动创建日程，并包含冲突检测。

📌 功能概述

本项目具备以下完整功能：

✔ 语音输入日程

通过浏览器录音上传到后端

后端使用 Vosk 离线 ASR 进行语音识别

✔ NLP 解析日程信息

解析内容包含：

活动标题

开始时间（支持“下午两点”“明天三点”等自然语言）

结束时间（可自动推断）

日期（今天 / 明天 / 后天）

✔ 自动创建 Google Calendar 事件

使用 Playwright 自动控制浏览器

首次需要人工登录 Google

后续复用 session（storage state）

✔ 自动冲突检测（最新版）

从 Google Calendar DOM 中提取事件文本

直接解析中文时间段，如

“下午 2 点 - 下午 3 点”

“10:00 - 11:00”

判断是否与目标时间段冲突，并阻止创建

✔ 语音反馈（TTS）

使用 edge-tts / 其它声学模型生成语音回答

📁 项目结构（已根据你最终版本整理）
voice-calendar-assistant/
│
├── backend/
│   ├── main.py                  # FastAPI 主入口
│   ├── tmp/                     # TTS & 语音临时文件
│   │
│   ├── gcal/
│   │   ├── browser.py           # Playwright 启动、保存 session
│   │   └── calendar_ops.py      # 创建事件 + 冲突检测核心逻辑
│   │
│   ├── nlp/
│   │   ├── parser_v2.py         # 中文日期/时间 NLP 模块
│   │   └── parser.py            # 旧版（可删除）
│   │
│   ├── speech/
│   │   ├── asr_vosk.py          # Vosk 语音识别
│   │   └── tts.py               # 语音合成
│
├── frontend/
│   └── index.html               # 简单录音网页，用于上传语音
│
└── README.md                    # 本文档


（你已经删除 React / JS 打包的代码，因此这里只保留 index.html）

🧩 环境依赖
1️⃣ Python

推荐使用 Python 3.10
已在 Windows 10/11 环境下测试通过。

pip install -r requirements.txt


你需要的依赖包括（根据你最终项目）：

fastapi
uvicorn
playwright
vosk
edge-tts
pydub


首次使用 Playwright，请运行：

playwright install

🔐 Google 登录说明（非常关键）

第一次运行时：

访问后端地址：

http://localhost:8000/static/index.html


在第一次调用 /api/start 或 /api/speech 时
Playwright 会打开一个真实浏览器（headful 模式）

手动登录 Google 一次

建议关闭二步验证

登录后 Playwright 会自动保存 session 到 storage_state.json

之后所有日程创建均无需再次登录

▶ 如何运行 Demo
启动后端：
py -3.10 -m uvicorn backend.main:app --port 8000 --reload

打开前端：

访问：

http://localhost:8000/static/index.html


点击录音 → 上传 → 自动处理 → 自动创建 Google Calendar 事件。

⚠ 已知问题与限制

❗ Google 会更新 DOM / aria-label，未来可能导致冲突检测或标题解析失效

❗ 语音识别受麦克风环境影响较大

❗ NLP 对部分模糊表达（如“等会儿”“下午中段”）无法完全解析

❗ Demo 未包含移动端 UI

❗ Playwright 属于“伪 API”，容易被 Google 反机器人机制影响