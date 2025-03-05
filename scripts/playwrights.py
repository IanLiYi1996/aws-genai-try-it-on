import asyncio
import json
from playwright.async_api import async_playwright


async def save_cookies():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # 打开可见浏览器
        page = await browser.new_page()
        await page.goto("https://aws.highspot.com")

        # 手动输入账号密码并登录
        input("请在打开的浏览器中登录，然后按回车继续...")

        # 获取 Cookies 并保存
        cookies = await page.context.cookies()
        with open("cookies_playwright.json", "w") as f:
            json.dump(cookies, f)
        await browser.close()


async def load_cookies_and_save_pdf(url, output_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        # 加载 Cookies
        with open("cookies_playwright.json", "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto(url)

        # 等待页面完全加载（确保所有资源加载完成）
        await page.wait_for_load_state("networkidle")

        await page.pdf(path=output_file)

        # 获取网页内容（HTML）
        html_content = await page.content()

        # 保存 HTML 文件
        with open(output_file + ".html", "w", encoding="utf-8") as f:
            f.write(html_content)

        await page.screenshot(path="screenshot.png", full_page=True)

        await browser.close()


async def main():
    url = "https://aws.highspot.com/items/6723559aa4a2430662bf3ecc"  # 目标网页
    url = "https://aws.highspot.com/items/66714a54d7401d6e7e28a14a"
    url = "https://aws.highspot.com/items/67481bca8203aa9093fef42e"
    output_file = "output.pdf1"

    # 先保存 Cookies（只需执行一次，之后可注释掉）
    await save_cookies()

    # 读取 Cookies 并生成 PDF
    await load_cookies_and_save_pdf(url, output_file)

    print(f"PDF 已保存至 {output_file}")


if __name__ == "__main__":
    asyncio.run(main())