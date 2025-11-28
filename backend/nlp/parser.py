# -*- coding:utf-8 -*-
import re
from datetime import datetime, timedelta

# 中文数字映射
CN_NUM = {
    '零': 0, '〇': 0,
    '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10
}

def chinese_to_int(text: str) -> int:
    """将中文数字（如 十、一、十一、二十三）转换为阿拉伯数字"""
    # 纯数字直接返回
    if text.isdigit():
        return int(text)

    # 特殊情况
    if text == "十":
        return 10
    if text.startswith("十"):
        # 十一 十二 十三...
        return 10 + CN_NUM[text[1]]
    if text.endswith("十"):
        # 二十 三十...
        return CN_NUM[text[0]] * 10
    if "十" in text:
        # 二十三 二十六...
        parts = text.split("十")
        return CN_NUM[parts[0]] * 10 + CN_NUM.get(parts[1], 0)

    # 单数字，如 “三”
    return CN_NUM.get(text, 0)


def _convert_to_24h(hour: int, period: str | None):
    """根据 上午/下午/晚上 转 24 小时制"""
    if period in ["下午", "晚上"]:
        if hour < 12:
            hour += 12
    if period == "上午" and hour == 12:
        hour = 0
    return hour


def parse_schedule_from_text(text: str) -> dict:
    text = text.strip()
    now = datetime.now()

    # ----------- 日期解析：今天/明天/后天 ----------
    date = None
    if "明天" in text:
        date = (now + timedelta(days=1)).date()
    elif "后天" in text:
        date = (now + timedelta(days=2)).date()
    elif "今天" in text:
        date = now.date()
    else:
        date = now.date()

    # ------------ 时间解析：支持 上午/下午/晚上 + 点半 ----------
    pattern = (
    r"(上午|下午|晚上)?\s*"
    r"(\d{1,2}|[一二三四五六七八九十]+)\s*(?:点|时|:)?\s*(半)?"
    r"\s*(?:到|-|至|—|——)\s*"
    r"(上午|下午|晚上)?\s*"
    r"(\d{1,2}|[一二三四五六七八九十]+)\s*(?:点|时|:)?\s*(半)?"
    )


    match = re.search(pattern, text)

    start_dt = None
    end_dt = None

    if match:
        period1, h1, half1, period2, h2, half2 = match.groups()

        h1 = chinese_to_int(h1)
        h2 = chinese_to_int(h2)

        m1 = 30 if half1 else 0
        m2 = 30 if half2 else 0

        h1 = _convert_to_24h(h1, period1)
        h2 = _convert_to_24h(h2, period2 or period1)

        start_dt = datetime.combine(date, datetime.min.time()).replace(
            hour=h1, minute=m1
        )
        end_dt = datetime.combine(date, datetime.min.time()).replace(
            hour=h2, minute=m2
        )

    # ------------------- 生成标题 -------------------------
    title = re.sub(pattern, "", text)
    for w in ["今天", "明天", "后天", "，", "。", " "]:
        title = title.replace(w, "")
    title = title.strip()

    # ------------------- 检查缺字段 ------------------------
    missing = []
    if not start_dt or not end_dt:
        missing.append("time")
    if not title:
        missing.append("title")

    return {
        "start": start_dt,
        "end": end_dt,
        "title": title,
        "missing_fields": missing
    }
