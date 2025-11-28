# backend/gcal/browser.py
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# 项目 backend 目录
BACKEND_DIR = Path(__file__).resolve().parents[1]
# 用于持久化登录状态的用户数据目录（Chrome 用户目录）
USER_DATA_DIR = BACKEND_DIR / "playwright_user_data"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

class PlaywrightManager:
    def __init__(self):
        self._pw = None
        self.context = None

    async def launch(self, headful: bool = True):
        """启动带持久化用户目录的浏览器，并确保最终停在真正的 Google Calendar 主界面。"""
        if self.context:
            print(">>> 已有 Playwright context，直接复用")
            return self.context

        print(">>> 启动 Playwright ...")
        self._pw = await async_playwright().start()

        # ⭐ 使用 launch_persistent_context，保证 USER_DATA_DIR 里记录完整登录状态
        self.context = await self._pw.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=not headful,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = await self.context.new_page()

        # 1️⃣ 尝试直接打开日历，看是不是已经登录
        calendar_url = "https://calendar.google.com/calendar/u/0/r"
        print(">>> 尝试直接打开日历:", calendar_url)
        try:
            await page.goto(calendar_url, wait_until="load", timeout=60000)
        except Exception as e:
            print(">>> 打开日历出错:", repr(e))

        await page.wait_for_timeout(2000)
        current_url = page.url
        print(">>> 当前打开 URL:", current_url)

        # ✅ 只有真正在 calendar.google.com/calendar/... 才算“已登录”
        if current_url.startswith("https://calendar.google.com/calendar"):
            print(">>> 检测到已在 Google Calendar 主界面，视为登录成功（复用 USER_DATA_DIR）")
            return self.context

        # ❌ 不在日历主界面（包括 workspace.google.com 宣传页），视为未登录
        print(">>> 当前不是 Calendar 主界面（可能是 workspace 介绍页 / 未登录），进入登录流程 ...")

        # 2️⃣ 跳到 Google 专门的 Calendar 登录入口
        login_url = (
            "https://accounts.google.com/ServiceLogin?"
            "service=cl&continue=https://calendar.google.com/calendar&hl=zh-CN"
        )
        print(">>> 跳转登录页:", login_url)
        await page.goto(login_url, wait_until="load")

        print(">>> 请在弹出的浏览器中完成 Google 登录（包括 MFA）")
        input(">>> 登录完成后，请回到这里按回车继续... ")

        # 3️⃣ 登录完成后，再次打开日历确认
        print(">>> 登录完成，重新进入 Calendar 主界面 ...")
        await page.goto(calendar_url, wait_until="load")
        await page.wait_for_timeout(2000)
        print(">>> 登录流程结束，后续将复用 USER_DATA_DIR 目录中的登录状态")

        return self.context

    async def close(self):
        """关闭浏览器和 Playwright（可选）。"""
        if self.context:
            await self.context.close()
            self.context = None
        if self._pw:
            await self._pw.stop()
            self._pw = None


# 全局单例
playwright_manager = PlaywrightManager()

if __name__ == "__main__":
    # 单独跑这个文件，用于首次登录调试
    asyncio.run(playwright_manager.launch(headful=True))
