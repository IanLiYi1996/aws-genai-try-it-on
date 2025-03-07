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
                
                # 提取内容并保存为Markdown
                if extract_text:
                    # 获取页面内容
                    html_content = await page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 获取页面标题
                    title = soup.title.string if soup.title else "无标题页面"
                    
                    # 提取所有内容（不仅限于main article）
                    # 首先尝试获取主要内容区域
                    content_selectors = ["main", "article", ".content", "#content", ".main-content", "body"]
                    main_content = None
                    
                    for selector in content_selectors:
                        elements = soup.select(selector)
                        if elements:
                            main_content = elements
                            break
                    
                    if not main_content:
                        main_content = [soup.body] if soup.body else [soup]
                    
                    # 提取结构化内容
                    markdown_content = f"# {title}\n\n"
                    markdown_content += f"*爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                    markdown_content += f"*来源URL: {url}*\n\n"
                    markdown_content += "---\n\n"
                    
                    # 提取所有标题和段落
                    headers_and_paragraphs = []
                    for element in main_content:
                        # 提取标题
                        for i in range(1, 7):
                            for header in element.find_all(f'h{i}'):
                                header_text = header.get_text(strip=True)
                                if header_text:
                                    headers_and_paragraphs.append({
                                        'type': f'h{i}',
                                        'content': header_text
                                    })
                        
                        # 提取段落
                        for p in element.find_all('p'):
                            p_text = p.get_text(strip=True)
                            if p_text:
                                headers_and_paragraphs.append({
                                    'type': 'p',
                                    'content': p_text
                                })
                    
                    # 将标题和段落添加到Markdown
                    for item in headers_and_paragraphs:
                        if item['type'].startswith('h'):
                            level = int(item['type'][1])
                            markdown_content += f"{'#' * level} {item['content']}\n\n"
                        else:
                            markdown_content += f"{item['content']}\n\n"
                    
                    # 提取所有图片
                    images = []
                    for element in main_content:
                        for img in element.find_all('img'):
                            src = img.get('src')
                            alt = img.get('alt', '图片')
                            if src:
                                # 处理相对URL
                                if not src.startswith(('http://', 'https://', 'data:')):
                                    src = self.base_url + src if src.startswith('/') else self.base_url + '/' + src
                                
                                # 过滤掉base64图片和小图标
                                if not src.startswith('data:'):
                                    images.append({
                                        'src': src,
                                        'alt': alt
                                    })
                    
                    # 将图片添加到Markdown
                    if images:
                        markdown_content += "## 图片内容\n\n"
                        for i, img in enumerate(images, 1):
                            markdown_content += f"### 图片 {i}\n\n"
                            markdown_content += f"![{img['alt']}]({img['src']})\n\n"
                    
                    # 提取所有链接
                    links = []
                    for element in main_content:
                        for a in element.find_all('a'):
                            href = a.get('href')
                            text = a.get_text(strip=True)
                            if href and text:
                                # 处理相对URL
                                if not href.startswith(('http://', 'https://', 'javascript:', '#', 'mailto:')):
                                    href = self.base_url + href if href.startswith('/') else self.base_url + '/' + href
                                
                                links.append({
                                    'text': text,
                                    'href': href
                                })
                    
                    # 将链接添加到Markdown
                    if links:
                        markdown_content += "## 链接内容\n\n"
                        for i, link in enumerate(links, 1):
                            markdown_content += f"{i}. [{link['text']}]({link['href']})\n"
                    
                    # 保存Markdown文件
                    markdown_path = f"{file_prefix}.md"
                    with open(markdown_path, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                    
                    print(f"Markdown内容已保存至: {markdown_path}")
                    result["files"]["markdown"] = markdown_path
                    
                    # 同时保存原始文本文件（保持兼容性）
                    text_path = f"{file_prefix}_content.txt"
                    extracted_text = "\n\n".join([item['content'] for item in headers_and_paragraphs])
                    
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
                        "title": title,
                        "text": extracted_text,
                        "images": images,
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
                                # 使用渐进式滚动来确保所有内容加载
                                prev_height = 0
                                while True:
                                    # 获取当前页面高度
                                    curr_height = await page.evaluate("""() => {
                                        return document.documentElement.scrollHeight;
                                    }""")
                                    
                                    # 如果高度没有变化，说明已经到达真正的底部
                                    if curr_height == prev_height:
                                        break
                                    
                                    # 渐进式滚动
                                    for scroll_pos in range(prev_height, curr_height, 300):  # 每次滚动300像素
                                        await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                                        await asyncio.sleep(0.5)  # 短暂等待让内容加载
                                    
                                    # 滚动到当前检测到的底部
                                    await page.evaluate(f"window.scrollTo(0, {curr_height})")
                                    await asyncio.sleep(2)  # 等待新内容加载
                                    
                                    prev_height = curr_height
                                    
                                # 最后再滚动到顶部，然后慢慢滚动到底部一次，以确保所有内容都被正确加载
                                await page.evaluate("window.scrollTo(0, 0)")
                                await asyncio.sleep(1)
                                
                                final_height = await page.evaluate("document.documentElement.scrollHeight")
                                for scroll_pos in range(0, final_height, 300):
                                    await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                                    await asyncio.sleep(0.5)
                                    
                            elif position == "top":
                                await page.evaluate("window.scrollTo(0, 0)")
                            else:
                                try:
                                    position = int(position)
                                    await page.evaluate(f"window.scrollTo(0, {position})")
                                except:
                                    pass
                            print(f"滚动到: {position}")
                            await asyncio.sleep(1)
        
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
                
                # 提取内容并保存为Markdown
                # 获取页面内容
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 获取页面标题
                title = soup.title.string if soup.title else "无标题页面"
                
                # 提取所有内容（不仅限于main article）
                # 首先尝试获取主要内容区域
                content_selectors = ["main", "article", ".content", "#content", ".main-content", "body"]
                main_content = None
                
                for selector in content_selectors:
                    elements = soup.select(selector)
                    if elements:
                        main_content = elements
                        break
                
                if not main_content:
                    main_content = [soup.body] if soup.body else [soup]
                
                # 提取结构化内容
                markdown_content = f"# {title}\n\n"
                markdown_content += f"*交互式爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                markdown_content += f"*来源URL: {url}*\n\n"
                markdown_content += "---\n\n"
                markdown_content += "## 交互操作\n\n"
                
                # 记录执行的交互操作
                if interactions:
                    for i, interaction in enumerate(interactions, 1):
                        action = interaction.get("action")
                        if action == "click":
                            markdown_content += f"{i}. 点击元素: `{interaction.get('selector')}`\n"
                        elif action == "wait":
                            markdown_content += f"{i}. 等待: {interaction.get('time', 1)} 秒\n"
                        elif action == "scroll":
                            markdown_content += f"{i}. 滚动到: {interaction.get('position', 'bottom')}\n"
                    markdown_content += "\n---\n\n"
                
                # 提取所有标题和段落
                headers_and_paragraphs = []
                for element in main_content:
                    # 提取标题
                    for i in range(1, 7):
                        for header in element.find_all(f'h{i}'):
                            header_text = header.get_text(strip=True)
                            if header_text:
                                headers_and_paragraphs.append({
                                    'type': f'h{i}',
                                    'content': header_text
                                })
                    
                    # 提取段落
                    for p in element.find_all('p'):
                        p_text = p.get_text(strip=True)
                        if p_text:
                            headers_and_paragraphs.append({
                                'type': 'p',
                                'content': p_text
                            })
                
                # 将标题和段落添加到Markdown
                for item in headers_and_paragraphs:
                    if item['type'].startswith('h'):
                        level = int(item['type'][1])
                        markdown_content += f"{'#' * level} {item['content']}\n\n"
                    else:
                        markdown_content += f"{item['content']}\n\n"
                
                # 提取所有图片
                # images = []
                # for element in main_content:
                #     for img in element.find_all('img'):
                #         src = img.get('src')
                #         alt = img.get('alt', '图片')
                #         if src:
                #             # 处理相对URL
                #             if not src.startswith(('http://', 'https://', 'data:')):
                #                 src = self.base_url + src if src.startswith('/') else self.base_url + '/' + src
                            
                #             # 过滤掉base64图片和小图标
                #             if not src.startswith('data:'):
                #                 images.append({
                #                     'src': src,
                #                     'alt': alt
                #                 })
                
                # # 将图片添加到Markdown
                # if images:
                #     markdown_content += "## 图片内容\n\n"
                #     for i, img in enumerate(images, 1):
                #         markdown_content += f"### 图片 {i}\n\n"
                #         markdown_content += f"![{img['alt']}]({img['src']})\n\n"
                
                # 提取所有链接
                links = []
                for element in main_content:
                    for a in element.find_all('a'):
                        href = a.get('href')
                        text = a.get_text(strip=True)
                        if href and text:
                            # 处理相对URL
                            if not href.startswith(('http://', 'https://', 'javascript:', '#', 'mailto:')):
                                href = self.base_url + href if href.startswith('/') else self.base_url + '/' + href
                            
                            links.append({
                                'text': text,
                                'href': href
                            })
                
                # 将链接添加到Markdown
                if links:
                    markdown_content += "## 链接内容\n\n"
                    for i, link in enumerate(links, 1):
                        markdown_content += f"{i}. [{link['text']}]({link['href']})\n"
                
                # 保存Markdown文件
                markdown_path = f"{file_prefix}.md"
                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                
                print(f"Markdown内容已保存至: {markdown_path}")
                result["files"]["markdown"] = markdown_path
                
                # 同时保存原始文本文件（保持兼容性）
                text_path = f"{file_prefix}_content.txt"
                extracted_text = "\n\n".join([item['content'] for item in headers_and_paragraphs])
                
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
                    "title": title,
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
                
                print("交互式爬取完成!")
                return result
                
            except Exception as e:
                print(f"交互式爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()


async def main():
    # 目标URL
    target_url = "https://aws.highspot.com/items/64cc7372c6f98784322eff65"
    
    # 创建爬虫实例
    crawler = HighspotCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(headless=False)  # 显示浏览器进行登录
    
    # 交互式爬取（如果需要）
    print("\n===== 开始交互式爬取 =====")
    interactions = [
        {"action": "wait", "time": 5},  # 等待2秒
        {"action": "scroll", "position": "bottom"},  # 滚动到底部
        {"action": "wait", "time": 5},  # 等待2秒  # 等待2秒
    ]
    interactive_result = await crawler.crawl_with_interaction(target_url, interactions, output_dir="output")
    
    print("\n爬取任务全部完成!")


if __name__ == "__main__":
    asyncio.run(main())
