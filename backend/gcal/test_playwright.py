import asyncio
from playwright.async_api import async_playwright

async def main():
    print("Starting playwright...")
    async with async_playwright() as p:
        print("Launching chromium...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.google.com")
        print("Browser opened, waiting...")
        await asyncio.sleep(10)
        await browser.close()

asyncio.run(main())
