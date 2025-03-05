#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

class HighspotCrawler:
    """AWS Highspot内容爬取工具，支持动态渲染内容的提取"""
    
    def __init__(self, cookies_path="cookies_playwright.json"):
        """初始化爬虫
        
        Args:
            cookies_path: cookie文件路径
        """
        self.cookies_path = cookies_path
        self.base_url = "https://aws.highspot.com"
    
    async def save_cookies(self, headless=False):
        """交互式登录并保存cookies
        
        Args:
            headless: 是否使用无头模式（默认False，显示浏览器便于登录）
        """
        print("启动浏览器进行登录...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # 访问登录页面
            await page.goto(f"{self.base_url}")
            print(f"请在打开的浏览器中完成登录操作...")
            
            # 等待用户手动登录
            input("登录完成后，请按回车键继续...")
            
            # 获取并保存cookies
            cookies = await context.cookies()
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            print(f"Cookies已保存至: {self.cookies_path}")
            await browser.close()
    
    async def crawl_content(self, url, output_dir="output", save_html=True, save_screenshot=True, extract_text=True):
        """使用已保存的cookies爬取内容
        
        Args:
            url: 目标URL
            output_dir: 输出目录
            save_html: 是否保存HTML
            save_screenshot: 是否保存截图
            extract_text: 是否提取文本内容
            
        Returns:
            dict: 包含爬取结果的字典
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{output_dir}/{timestamp}_highspot"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {}
        }
        
        print(f"开始爬取: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return None
            
            # 启动浏览器
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 加载cookies
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            
            # 创建新页面并访问目标URL
            page = await context.new_page()
            
            # 设置超时时间
            page.set_default_timeout(60000)  # 60秒
            
            try:
                # 访问目标页面
                response = await page.goto(url)
                
                if response.status >= 400:
                    print(f"页面访问失败，状态码: {response.status}")
                    await browser.close()
                    return None
                
                # 等待页面完全加载，包括动态内容
                await page.wait_for_load_state("networkidle")
                
                # 额外等待时间，确保动态内容完全加载
                await asyncio.sleep(5)
                
                # 可选：等待特定元素出现，表明内容已加载
                try:
                    # 这里的选择器需要根据实际页面调整
                    await page.wait_for_selector("main article", timeout=10000)
                except Exception as e:
                    print(f"等待特定元素超时: {e}")
                    # 继续执行，不中断流程
                
                # 保存HTML
                if save_html:
                    html_path = f"{file_prefix}.html"
                    html_content = await page.content()
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print(f"HTML已保存至: {html_path}")
                    result["files"]["html"] = html_path
                
                # 保存截图
                if save_screenshot:
                    screenshot_path = f"{file_prefix}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"截图已保存至: {screenshot_path}")
                    result["files"]["screenshot"] = screenshot_path
                
                # 提取文本内容
                if extract_text:
                    # 获取页面内容
                    html_content = await page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 提取主要内容（根据实际页面结构调整选择器）
                    main_content = soup.select("main article")
                    
                    # 提取文本
                    extracted_text = ""
                    if main_content:
                        for element in main_content:
                            extracted_text += element.get_text(separator="\n", strip=True) + "\n\n"
                    
                    # 提取链接
                    links = []
                    for a in soup.select("main article a"):
                        href = a.get("href")
                        if href:
                            if not href.startswith("http"):
                                href = self.base_url + href if href.startswith("/") else self.base_url + "/" + href
                            links.append({
                                "text": a.get_text(strip=True),
                                "href": href
                            })
                    
                    # 保存提取的内容
                    text_path = f"{file_prefix}_content.txt"
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write("===== 提取的文本内容 =====\n\n")
                        f.write(extracted_text)
                        f.write("\n\n===== 提取的链接 =====\n\n")
                        for i, link in enumerate(links, 1):
                            f.write(f"{i}. {link['text']} - {link['href']}\n")
                    
                    print(f"提取的内容已保存至: {text_path}")
                    result["files"]["text"] = text_path
                    
                    # 将提取的内容也添加到结果中
                    result["extracted_content"] = {
                        "text": extracted_text,
                        "links": links
                    }
                
                # 执行JavaScript获取动态内容
                js_data = await page.evaluate("""() => {
                    // 尝试获取可能存在的全局数据
                    const data = {
                        title: document.title,
                        metaData: {}
                    };
                    
                    // 提取meta标签信息
                    document.querySelectorAll('meta').forEach(meta => {
                        if (meta.name && meta.content) {
                            data.metaData[meta.name] = meta.content;
                        }
                    });
                    
                    // 尝试获取可能存在的JSON数据
                    const scriptTags = Array.from(document.querySelectorAll('script[type="application/json"], script[type="application/ld+json"]'));
                    data.jsonData = scriptTags.map(script => {
                        try {
                            return JSON.parse(script.textContent);
                        } catch (e) {
                            return null;
                        }
                    }).filter(Boolean);
                    
                    return data;
                }""")
                
                # 保存JavaScript提取的数据
                if js_data:
                    js_data_path = f"{file_prefix}_js_data.json"
                    with open(js_data_path, "w", encoding="utf-8") as f:
                        json.dump(js_data, f, ensure_ascii=False, indent=2)
                    print(f"JavaScript数据已保存至: {js_data_path}")
                    result["files"]["js_data"] = js_data_path
                    result["js_data"] = js_data
                
                print("爬取完成!")
                return result
                
            except Exception as e:
                print(f"爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()
    
    async def crawl_with_interaction(self, url, interactions=None, output_dir="output"):
        """带交互的爬取，可以点击、滚动等操作后再获取内容
        
        Args:
            url: 目标URL
            interactions: 交互操作列表，例如：
                [
                    {"action": "click", "selector": "button.load-more"},
                    {"action": "wait", "time": 2},
                    {"action": "scroll", "position": "bottom"}
                ]
            output_dir: 输出目录
            
        Returns:
            dict: 包含爬取结果的字典
        """
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{output_dir}/{timestamp}_highspot_interactive"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {}
        }
        
        print(f"开始交互式爬取: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return None
            
            # 启动浏览器
            browser = await p.chromium.launch(headless=False)  # 使用有头模式便于观察交互
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 加载cookies
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            
            # 创建新页面并访问目标URL
            page = await context.new_page()
            
            try:
                # 访问目标页面
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                
                # 执行交互操作
                if interactions:
                    for interaction in interactions:
                        action = interaction.get("action")
                        
                        if action == "click":
                            selector = interaction.get("selector")
                            if selector:
                                try:
                                    await page.click(selector)
                                    print(f"点击元素: {selector}")
                                    # 等待可能的加载
                                    await page.wait_for_load_state("networkidle")
                                except Exception as e:
                                    print(f"点击元素失败 {selector}: {e}")
                        
                        elif action == "wait":
                            time_to_wait = interaction.get("time", 1)
                            await asyncio.sleep(time_to_wait)
                            print(f"等待 {time_to_wait} 秒")
                        
                        elif action == "scroll":
                            position = interaction.get("position", "bottom")
                            if position == "bottom":
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            elif position == "top":
                                await page.evaluate("window.scrollTo(0, 0)")
                            else:
                                # 滚动到指定位置
                                try:
                                    position = int(position)
                                    await page.evaluate(f"window.scrollTo(0, {position})")
                                except:
                                    pass
                            print(f"滚动到: {position}")
                            await asyncio.sleep(1)  # 等待滚动完成和可能的内容加载
                
                # 保存交互后的HTML
                html_path = f"{file_prefix}.html"
                html_content = await page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"交互后HTML已保存至: {html_path}")
                result["files"]["html"] = html_path
                
                # 保存交互后的截图
                screenshot_path = f"{file_prefix}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"交互后截图已保存至: {screenshot_path}")
                result["files"]["screenshot"] = screenshot_path
                
                print("交互式爬取完成!")
                return result
                
            except Exception as e:
                print(f"交互式爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()


async def main():
    # 目标URL
    target_url = "https://aws.highspot.com/spots/60bdbd9634d6be4dbd9ce328?list=all&overview=true"
    
    # 创建爬虫实例
    crawler = HighspotCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(headless=False)  # 显示浏览器进行登录
    
    # 基本爬取
    print("\n===== 开始基本爬取 =====")
    result = await crawler.crawl_content(target_url, output_dir="output")
    
    # 交互式爬取（如果需要）
    print("\n===== 开始交互式爬取 =====")
    interactions = [
        {"action": "wait", "time": 2},  # 等待2秒
        {"action": "scroll", "position": "bottom"},  # 滚动到底部
        {"action": "wait", "time": 2},  # 等待2秒
        # 可以添加更多交互，如点击"加载更多"按钮等
        # {"action": "click", "selector": "button.load-more"},
    ]
    interactive_result = await crawler.crawl_with_interaction(target_url, interactions, output_dir="output")
    
    print("\n爬取任务全部完成!")


if __name__ == "__main__":
    asyncio.run(main())
