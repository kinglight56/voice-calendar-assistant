# backend/gcal/calendar_ops.py
# 2025 年终极版本 —— 带稳定冲突检测 + 稳定事件创建

import asyncio
from datetime import datetime
from typing import Optional
from nlp import parser_v2  # 用它里面的 parse_time 来解析事件时间

class CalendarOperator:
    def __init__(self, context):
        self.context = context

    async def open_calendar(self):
        page = await self.context.new_page()
        await page.goto("https://calendar.google.com/calendar/u/0/r", wait_until="domcontentloaded")
        await page.wait_for_selector("div.XsRa1c", timeout=30000)
        return page

    # ====================================================
    #  创建日程（你之前的逻辑我保留，只修正一些细节）
    # ====================================================
    async def create_event(
        self,
        title: str,
        start_dt: datetime,
        end_dt: datetime,
        location: Optional[str] = None,
        description: Optional[str] = None,
    ):
        page = await self.open_calendar()
        url = f"https://calendar.google.com/calendar/u/0/r/day/{start_dt.year}/{start_dt.month}/{start_dt.day}"

        try:
            # 打开日期
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(1.2)

            # 强制切换为日视图
            await page.keyboard.press("1")
            await asyncio.sleep(1.2)

            # 点击时间行
            hour_index = start_dt.hour
            print(">>> 要点击的时间行 index:", hour_index)

            rows = page.locator("div.XsRa1c")
            count = await rows.count()

            if count < 24:
                raise RuntimeError(f"❌ 小时行数量异常：{count}")

            row = rows.nth(hour_index)

            await row.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            await row.click(force=True)

            print(f"✔ 已点击小时行: {hour_index}")

            # 等待弹窗
            dialog = page.locator("div[role='dialog']").first
            await dialog.wait_for(state="visible", timeout=8000)
            await asyncio.sleep(0.6)

            # ---- 标题 ----
            title_selectors = [
                '[aria-label="添加标题"]',
                '[aria-label="活动名称"]',
                '[aria-label="标题"]',
                '[aria-label="标题（可选）"]',
            ]

            for sel in title_selectors:
                tbox = dialog.locator(sel)
                if await tbox.count():
                    await tbox.fill(title)
                    print("✔ 已填写标题:", sel)
                    break

            # ---- 时间输入 ----
            start_labels = ["开始时间", "开始", "开始日期"]
            end_labels = ["结束时间", "结束", "结束日期"]

            async def find_input(labels):
                for lbl in labels:
                    sel = f'input[aria-label="{lbl}"]'
                    box = dialog.locator(sel)
                    if await box.count():
                        return box
                return None

            start_input = await find_input(start_labels)
            end_input = await find_input(end_labels)

            if start_input and end_input:
                s = start_dt.strftime("%H:%M")
                e = end_dt.strftime("%H:%M")

                print(f"✔ 写入时间 {s} → {e}")

                for box, val in [(start_input, s), (end_input, e)]:
                    await box.evaluate(
                        """
                        (el, value) => {
                            el.value = value;
                            ['input','change','blur','keydown','keyup'].forEach(ev=>{
                                el.dispatchEvent(new Event(ev,{bubbles:true}));
                            });
                            if(el._valueTracker){ el._valueTracker.setValue(value); }
                        }
                        """,
                        val
                    )

            await asyncio.sleep(0.5)

            # ---- 保存 ----
            print(">>> 点击保存")
            await dialog.locator("button:has-text('保存')").click(force=True)
            await asyncio.sleep(1.0)

            try:
                await dialog.wait_for(state="detached", timeout=5000)
            except:
                pass

            print("🎉 创建成功：", title)
            return True

        except Exception as e:
            print("❌ 创建失败：", e)
            await page.screenshot(path=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png", full_page=True)
            return False

        finally:
            await page.close()

    # ====================================================
    #  冲突检测 —— 最终版（parser_v2 + 自定义备份解析）
    # ====================================================
    async def check_conflict(self, date, start_dt: datetime, end_dt: datetime) -> bool:
        """
        根据事件块的 aria-label / innerText 解析出时间段，进行重叠判断。
        """
        from datetime import datetime, timedelta
        import re

        page = await self.open_calendar()
        try:
            print("\n" + "=" * 80)
            print("开始冲突检测（最终版）")
            print(f"目标日期   : {date.strftime('%Y-%m-%d %A')}")
            print(f"目标时间段 : {start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}")
            print("=" * 80)

            # 打开当天日视图
            url = f"https://calendar.google.com/calendar/u/0/r/day/{date.year}/{date.month}/{date.day}"
            await page.goto(url, wait_until="load", timeout=90000)
            await page.keyboard.press("1")  # 日视图
            await asyncio.sleep(1.5)

            # 获取所有事件
            events = await page.evaluate(
                """
                () => {
                    const list = Array.from(document.querySelectorAll('div[data-eventid]'));
                    return list.map(el => {
                        const aria = el.getAttribute('aria-label') || "";
                        const text = (el.innerText || "").replace(/\\s+/g, " ").trim();
                        return {
                            aria,
                            text,
                            combined: (aria + " " + text).trim()
                        };
                    });
                }
                """
            )

            print(f"当天事件数量: {len(events)}")
            print("-" * 80)

            def parse_cn_time_span(label: str):
                """
                备用解析方法（parser_v2 失败时使用）
                支持格式：
                 - 10:00 到 11:00
                 - 上午10点 - 上午11点
                 - 下午2点 - 3点
                """
                # 1) 10:00 - 11:00 格式
                m = re.search(r"(\\d{1,2}):(\\d{2}).*?(\\d{1,2}):(\\d{2})", label)
                if m:
                    sh, sm, eh, em = map(int, m.groups())
                    return sh, sm, eh, em

                # 2) 上午/下午 X点 - 上午/下午 Y点
                m = re.search(
                    r"(上午|下午|中午)?\\s*(\\d{1,2})点.*?(上午|下午|中午)?\\s*(\\d{1,2})点",
                    label
                )
                if m:
                    p1, h1, p2, h2 = m.groups()
                    h1, h2 = int(h1), int(h2)

                    def to24(h, prefix):
                        if prefix in ("下午", "中午"):
                            if h < 12:
                                return h + 12
                        return h

                    sh = to24(h1, p1 or p2)
                    eh = to24(h2, p2 or p1)
                    return sh, 0, eh, 0

                return None

            conflict_found = False

            for idx, evt in enumerate(events):
                combined = evt["combined"]

                print(f"[事件 {idx}] 文本: {combined}")

                if not combined:
                    print("  → 空文本，跳过")
                    print("-" * 80)
                    continue

                # 第一优先：用 parser_v2
                t = parser_v2.parse_time(combined)

                evt_start = evt_end = None

                if t:
                    mode = t[0]

                    if mode == "range":
                        (h1, m1), (h2, m2) = t[1], t[2]
                        evt_start = datetime(date.year, date.month, date.day, h1, m1)
                        evt_end = datetime(date.year, date.month, date.day, h2, m2)
                    else:
                        # 单点事件，默认 1 小时
                        h, m = t[1]
                        evt_start = datetime(date.year, date.month, date.day, h, m)
                        evt_end = evt_start + timedelta(hours=1)

                    print(f"  → parser_v2 成功解析: {evt_start.strftime('%H:%M')} ~ {evt_end.strftime('%H:%M')}")

                else:
                    # 第二优先：自定义正则解析
                    span = parse_cn_time_span(combined)

                    if not span:
                        print("  → 未能解析时间，跳过")
                        print("-" * 80)
                        continue

                    sh, sm, eh, em = span
                    evt_start = datetime(date.year, date.month, date.day, sh, sm)
                    evt_end = datetime(date.year, date.month, date.day, eh, em)

                    print(f"  → 备用解析: {evt_start.strftime('%H:%M')} ~ {evt_end.strftime('%H:%M')}")

                # =========== 重叠判断 ===========
                overlap = not (end_dt <= evt_start or start_dt >= evt_end)
                print(f"  → 是否冲突: {overlap}")

                if overlap:
                    conflict_found = True
                    print("  ❌ 发生时间冲突!")

                print("-" * 80)

            if conflict_found:
                print("最终结论：存在冲突，不允许创建事件")
            else:
                print("最终结论：无冲突，可以创建事件")

            print("=" * 80 + "\\n")
            return conflict_found

        except Exception as e:
            print("冲突检测异常：", e)
            return True  # 出错误时禁止创建，避免误操作

        finally:
            await page.close()
