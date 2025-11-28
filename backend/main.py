# backend/main.py

import asyncio
import sys
import os
import tempfile

# 解决 Windows 上的事件循环问题
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ffmpeg import input as ffmpeg_input

# -------------------------
# 项目相关模块
# -------------------------
from gcal.browser import playwright_manager
from gcal.calendar_ops import CalendarOperator

from speech.asr_vosk import transcribe_audio_file
from speech.tts import synthesize_text_async
from nlp.parser_v2 import parse_schedule_from_text_v2 as parse_schedule_from_text


app = FastAPI()


# -------------------------
# 路径配置
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BACKEND_DIR, "tmp")

print(">>> FRONTEND_DIR =", FRONTEND_DIR)
print(">>> TMP_DIR =", TMP_DIR)

os.makedirs(TMP_DIR, exist_ok=True)

# 静态目录
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")


# -------------------------
# Playwright 全局懒加载
# -------------------------
calendar_operator = None
playwright_context = None


async def get_calendar_operator():
    """懒加载 Playwright BrowserContext + 日历操作器"""
    global calendar_operator, playwright_context

    if calendar_operator is None:
        print(">>> 第一次调用：初始化 Playwright ...")
        playwright_context = await playwright_manager.launch(headful=True)
        calendar_operator = CalendarOperator(playwright_context)
        print(">>> Playwright 初始化完成（复用 Google 登录）")

    return calendar_operator


# -------------------------
# API: 开场白
# -------------------------
@app.post("/api/start")
async def start():
    await get_calendar_operator()

    text = "您好，我是您的日程助手，你要记录什么日程？"
    out_file = os.path.join(TMP_DIR, "greeting.mp3")

    synthesize_text_async(text, out_path=out_file)

    return {
        "text": text,
        "audio": "/tmp/greeting.mp3",
    }


# -------------------------
# API: 语音识别 → NLP → 创建日程
# -------------------------
@app.post("/api/speech")
async def handle_speech(file: UploadFile = File(...)):
    op = await get_calendar_operator()

    # ----------- 读取语音数据 -----------
    data = await file.read()

    # ----------- 保存临时输入文件(webm/mp3/ogg等格式) -----------
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
        f.write(data)
        temp_input_path = f.name

    # ----------- 转换为 WAV (16000Hz 单声道) -----------
    wav_path = os.path.join(TMP_DIR, "asr_temp.wav")

    (
        ffmpeg_input(temp_input_path)
        .output(wav_path, ac=1, ar=16000, format="wav")
        .overwrite_output()
        .run(quiet=True)
    )

    # 删除原始 webm 临时文件
    os.remove(temp_input_path)

    # ----------- Vosk 识别 -----------
    user_text = transcribe_audio_file(wav_path)
    print("用户语音识别结果：", user_text)

    # ----------- NLP 解析 -----------
    parsed = parse_schedule_from_text(user_text)

    # ❌ 信息不足
    if parsed.get("missing_fields"):
        msg = parsed.get("message", "我没有听清楚，请再说一次。")
        synthesize_text_async(msg, out_path=os.path.join(TMP_DIR, "error.mp3"))
        return {
            "status": "incomplete",
            "message": msg,
            "audio": "/tmp/error.mp3",
        }

    title = parsed["title"]
    start_dt = parsed["start"]
    end_dt = parsed["end"]

    # ------------------------------
    # 先做冲突检测
    # ------------------------------
    has_conflict = await op.check_conflict(start_dt.date(), start_dt, end_dt)

    if has_conflict:
        msg = f"您在 {start_dt.strftime('%m月%d日 %H:%M')} 到 {end_dt.strftime('%H:%M')} 已有日程，请换个时间。"
        synthesize_text_async(msg, out_path=os.path.join(TMP_DIR, "conflict.mp3"))
        return {
            "status": "conflict",
            "message": msg,
            "audio": "/tmp/conflict.mp3"
        }

    # ------------------------------
    # 没有冲突：继续创建
    # ------------------------------
    ok = await op.create_event(title, start_dt, end_dt)

    if ok is False:
        msg = "创建日程失败，请稍后再试。"
        synthesize_text_async(msg, out_path=os.path.join(TMP_DIR, "fail.mp3"))
        return {
            "status": "error",
            "message": msg,
            "audio": "/tmp/fail.mp3",
        }

    # ----------- 成功反馈 -----------
    msg = "日程已创建成功。"
    synthesize_text_async(msg, out_path=os.path.join(TMP_DIR, "success.mp3"))

    return {
        "status": "ok",
        "message": msg,
        "audio": "/tmp/success.mp3",
        "user_text": user_text,
    }


# -------------------------
# NLP 测试接口
# -------------------------
@app.post("/api/test_parse")
async def test_parse(text: str):
    return parse_schedule_from_text(text)


# -------------------------
# 启动入口
# -------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
