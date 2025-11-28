# backend/nlp/parser_v2.py

from datetime import datetime, timedelta
import re

# -----------------------------
# 中文数字转换表
# -----------------------------
CN_NUM = {
    "零": 0, "〇": 0,
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "十一": 11, "十二": 12
}

WEEKDAY_MAP = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6
}

# -----------------------------
# 中文数字 → 数字
# -----------------------------
def cn2num(s: str):
    if s in CN_NUM:
        return CN_NUM[s]
    # “十七”类情况
    if len(s) == 2 and s[0] == "十":
        return 10 + CN_NUM.get(s[1], 0)
    return None


# -----------------------------
# 日期解析
# -----------------------------
def parse_date(text: str):
    today = datetime.now()

    if "今天" in text:
        return today
    if "明天" in text or "明日" in text:
        return today + timedelta(days=1)
    if "后天" in text:
        return today + timedelta(days=2)

    # 下周 X
    m = re.search(r"下周([一二三四五六日天])", text)
    if m:
        target = WEEKDAY_MAP[m.group(1)]
        delta = (7 - today.weekday() + target) % 7 + 7
        return today + timedelta(days=delta)

    return today


# -----------------------------
# 时间解析（单点 / 时间段）
# -----------------------------
def parse_time(text: str):
    t = text.replace(" ", "")

    # 上午/下午判断
    is_pm = any(k in t for k in ["下午", "晚上", "傍晚"])
    is_am = any(k in t for k in ["上午", "早上", "清晨", "明早"])

    def normalize(h):
        h = int(h)
        if is_pm and h < 12:
            h += 12
        return h

    # ① 数字时间段：9点到10点 / 9:30-10:30
    m = re.search(r"(\d+)(?:点|时|:|：)?(\d*)?\s*(?:到|-|至|~)\s*(\d+)(?:点|时|:|：)?(\d*)?", t)
    if m:
        h1, m1, h2, m2 = m.group(1), m.group(2), m.group(3), m.group(4)
        h1 = normalize(h1)
        h2 = normalize(h2)
        m1 = int(m1) if m1 else 0
        m2 = int(m2) if m2 else 0
        return ("range", (h1, m1), (h2, m2))

    # ② 中文时间段：九点到十点
    m = re.search(r"([一二两三四五六七八九十]+)点(?:到|-|至)([一二两三四五六七八九十]+)点?", t)
    if m:
        h1 = cn2num(m.group(1))
        h2 = cn2num(m.group(2))
        return ("range", (normalize(h1), 0), (normalize(h2), 0))

    # ③ 数字单点：9点 / 9:30
    m = re.search(r"(\d+)(?:点|时|:|：)?(\d*)?", t)
    if m:
        h, m1 = normalize(m.group(1)), int(m.group(2)) if m.group(2) else 0
        return ("single", (h, m1))

    # ④ 中文单点：九点
    m = re.search(r"([一二两三四五六七八九十]+)点", t)
    if m:
        h = cn2num(m.group(1))
        return ("single", (normalize(h), 0))

    return None


# -----------------------------
# 提取标题（此版本非常准！）
# -----------------------------
def extract_title(text: str):
    t = text

    # 去掉日期词
    t = re.sub(r"(今天|明天|后天|上午|下午|早上|晚上|傍晚|清晨|明早)", "", t)

    # 去掉数字时间 & 时间段
    t = re.sub(r"\d+(点|时|:|：)?\d*", "", t)
    t = re.sub(r"(到|至|-|~)", "", t)

    # 去掉中文数字时间
    t = re.sub(r"[一二两三四五六七八九十]+点", "", t)

    return t.strip() if t.strip() else "日程"


# -----------------------------
# 主入口：解析日程
# -----------------------------
def parse_schedule_from_text_v2(text: str):

    date = parse_date(text)
    t = parse_time(text)

    if t is None:
        return {
            "missing_fields": True,
            "message": "我没有听清楚时间，请再说一次，例如：明天早上九点到十点。",
        }

    mode = t[0]

    # 时间段
    if mode == "range":
        (h1, m1), (h2, m2) = t[1], t[2]
        start = date.replace(hour=h1, minute=m1, second=0)
        end = date.replace(hour=h2, minute=m2, second=0)

    # 单点时间 → 默认 1 小时
    else:
        (h, m) = t[1]
        start = date.replace(hour=h, minute=m, second=0)
        end = start + timedelta(hours=1)

    title = extract_title(text)

    return {
        "title": title,
        "start": start,
        "end": end,
    }
