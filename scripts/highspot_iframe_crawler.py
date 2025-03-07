#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class HighspotIframeCrawler:
    """AWS Highspot内容爬取工具，支持动态渲染内容和iframe表格的提取"""
    
    def __init__(self, cookies_path="cookies_playwright.json"):
        """初始化爬虫
        
        Args:
            cookies_path: cookie文件路径
        """
        self.cookies_path = cookies_path
        self.base_url = "https://aws.highspot.com"
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
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
    
    async def crawl_page(self, url, save_html=True, save_screenshot=True):
        """爬取页面内容，包括处理iframe
        
        Args:
            url: 目标URL
            save_html: 是否保存HTML
            save_screenshot: 是否保存截图
            
        Returns:
            dict: 包含爬取结果的字典
        """
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{self.output_dir}/{timestamp}_highspot"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {},
            "content": {}
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
                
                # 获取页面内容
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 获取页面标题
                title = soup.title.string if soup.title else "无标题页面"
                result["content"]["title"] = title
                
                # 提取主要内容
                main_content = self._extract_main_content(soup)
                result["content"]["main_text"] = main_content
                
                # 查找所有iframe
                iframes = soup.find_all('iframe')
                iframe_contents = []
                
                # 处理每个iframe
                for i, iframe in enumerate(iframes):
                    iframe_src = iframe.get('src')
                    if not iframe_src:
                        continue
                    
                    print(f"发现iframe {i+1}/{len(iframes)}: {iframe_src}")
                    
                    # 处理相对URL
                    if not iframe_src.startswith(('http://', 'https://')):
                        iframe_src = urljoin(url, iframe_src)
                    
                    # 创建新页面访问iframe内容
                    iframe_page = await context.new_page()
                    try:
                        await iframe_page.goto(iframe_src)
                        await iframe_page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2)  # 等待iframe内容加载
                        
                        # 保存iframe截图
                        iframe_screenshot_path = f"{file_prefix}_iframe_{i+1}.png"
                        await iframe_page.screenshot(path=iframe_screenshot_path)
                        print(f"Iframe {i+1} 截图已保存至: {iframe_screenshot_path}")
                        
                        # 获取iframe内容
                        iframe_html = await iframe_page.content()
                        iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                        
                        # 提取iframe中的表格
                        tables = self._extract_tables_from_iframe(iframe_soup)
                        
                        iframe_contents.append({
                            "src": iframe_src,
                            "tables": tables,
                            "screenshot": iframe_screenshot_path
                        })
                        
                    except Exception as e:
                        print(f"处理iframe {i+1} 时出错: {str(e)}")
                    finally:
                        await iframe_page.close()
                
                result["content"]["iframes"] = iframe_contents
                
                # 生成Markdown内容
                markdown_content = self._generate_markdown(result["content"])
                
                # 保存Markdown文件
                markdown_path = f"{file_prefix}.md"
                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                
                print(f"Markdown内容已保存至: {markdown_path}")
                result["files"]["markdown"] = markdown_path
                
                print("爬取完成!")
                return result
                
            except Exception as e:
                print(f"爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()
    
    def _extract_main_content(self, soup):
        """提取页面主要内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            list: 包含内容项的列表
        """
        content_items = []
        
        # 尝试找到主要内容区域
        content_selectors = ["main", "article", ".content", "#content", ".main-content", "body"]
        main_element = None
        
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                main_element = elements[0]
                break
        
        if not main_element:
            main_element = soup.body if soup.body else soup
        
        # 提取所有标题和段落
        for i in range(1, 7):
            for header in main_element.find_all(f'h{i}'):
                header_text = header.get_text(strip=True)
                if header_text:
                    content_items.append({
                        'type': f'h{i}',
                        'content': header_text
                    })
        
        # 提取段落
        for p in main_element.find_all('p'):
            p_text = p.get_text(strip=True)
            if p_text:
                content_items.append({
                    'type': 'p',
                    'content': p_text
                })
        
        # 提取列表
        for ul in main_element.find_all('ul'):
            list_items = []
            for li in ul.find_all('li'):
                li_text = li.get_text(strip=True)
                if li_text:
                    list_items.append(li_text)
            if list_items:
                content_items.append({
                    'type': 'ul',
                    'content': list_items
                })
        
        for ol in main_element.find_all('ol'):
            list_items = []
            for li in ol.find_all('li'):
                li_text = li.get_text(strip=True)
                if li_text:
                    list_items.append(li_text)
            if list_items:
                content_items.append({
                    'type': 'ol',
                    'content': list_items
                })
        
        # 提取表格
        tables = self._extract_tables(main_element)
        for table in tables:
            content_items.append({
                'type': 'table',
                'content': table
            })
        
        return content_items
    
    def _extract_tables(self, element):
        """从HTML元素中提取表格
        
        Args:
            element: HTML元素
            
        Returns:
            list: 表格数据列表
        """
        tables = []
        
        for table_elem in element.find_all('table'):
            table_data = []
            
            # 提取表头
            headers = []
            thead = table_elem.find('thead')
            if thead:
                for th in thead.find_all('th'):
                    headers.append(th.get_text(strip=True))
            
            # 如果没有找到表头，尝试从第一行提取
            if not headers:
                first_row = table_elem.find('tr')
                if first_row:
                    for th in first_row.find_all(['th', 'td']):
                        headers.append(th.get_text(strip=True))
            
            # 提取表格内容
            rows = []
            tbody = table_elem.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr'):
                    row = []
                    for td in tr.find_all('td'):
                        row.append(td.get_text(strip=True))
                    if row:
                        rows.append(row)
            else:
                # 如果没有tbody，直接从table中提取行
                for tr in table_elem.find_all('tr'):
                    # 跳过已处理的表头行
                    if tr == table_elem.find('tr') and not thead and headers:
                        continue
                    
                    row = []
                    for td in tr.find_all('td'):
                        row.append(td.get_text(strip=True))
                    if row:
                        rows.append(row)
            
            table_data = {
                'headers': headers,
                'rows': rows
            }
            
            tables.append(table_data)
        
        return tables
    
    def _extract_tables_from_iframe(self, iframe_soup):
        """从iframe中提取表格
        
        Args:
            iframe_soup: iframe的BeautifulSoup对象
            
        Returns:
            list: 表格数据列表
        """
        # 尝试找到iframe中的主要内容区域
        content_selectors = ["main", "article", ".content", "#content", ".main-content", "body"]
        main_element = None
        
        for selector in content_selectors:
            elements = iframe_soup.select(selector)
            if elements:
                main_element = elements[0]
                break
        
        if not main_element:
            main_element = iframe_soup.body if iframe_soup.body else iframe_soup
        
        # 提取表格
        return self._extract_tables(main_element)
    
    def _generate_markdown(self, content):
        """生成Markdown内容
        
        Args:
            content: 提取的内容
            
        Returns:
            str: Markdown格式的内容
        """
        markdown = f"# {content['title']}\n\n"
        markdown += f"*爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        
        # 添加主要内容
        if content.get('main_text'):
            markdown += "## 页面内容\n\n"
            
            for item in content['main_text']:
                item_type = item['type']
                item_content = item['content']
                
                if item_type.startswith('h'):
                    level = int(item_type[1])
                    markdown += f"{'#' * (level + 1)} {item_content}\n\n"
                
                elif item_type == 'p':
                    markdown += f"{item_content}\n\n"
                
                elif item_type == 'ul':
                    for li in item_content:
                        markdown += f"- {li}\n"
                    markdown += "\n"
                
                elif item_type == 'ol':
                    for i, li in enumerate(item_content, 1):
                        markdown += f"{i}. {li}\n"
                    markdown += "\n"
                
                elif item_type == 'table':
                    table_data = item_content
                    headers = table_data.get('headers', [])
                    rows = table_data.get('rows', [])
                    
                    if headers:
                        markdown += "| " + " | ".join(headers) + " |\n"
                        markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                    
                    for row in rows:
                        # 确保行中的单元格数量与表头一致
                        while len(row) < len(headers):
                            row.append("")
                        markdown += "| " + " | ".join(row) + " |\n"
                    
                    markdown += "\n"
        
        # 添加iframe内容
        if content.get('iframes'):
            markdown += "## Iframe内容\n\n"
            
            for i, iframe in enumerate(content['iframes'], 1):
                markdown += f"### Iframe {i}\n\n"
                markdown += f"源地址: {iframe['src']}\n\n"
                
                # 添加表格
                for j, table in enumerate(iframe['tables'], 1):
                    markdown += f"#### 表格 {j}\n\n"
                    
                    headers = table.get('headers', [])
                    rows = table.get('rows', [])
                    
                    if headers:
                        markdown += "| " + " | ".join(headers) + " |\n"
                        markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                    
                    for row in rows:
                        # 确保行中的单元格数量与表头一致
                        while len(row) < len(headers):
                            row.append("")
                        # 处理表格中的特殊字符
                        processed_row = [cell.replace("|", "\\|") for cell in row]
                        markdown += "| " + " | ".join(processed_row) + " |\n"
                    
                    markdown += "\n"
        
        return markdown
    
    async def crawl_with_iframe_interaction(self, url):
        """爬取页面并处理iframe，包括交互操作
        
        Args:
            url: 目标URL
            
        Returns:
            dict: 包含爬取结果的字典
        """
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{self.output_dir}/{timestamp}_highspot_interactive"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {},
            "content": {}
        }
        
        print(f"开始交互式爬取: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return None
            
            # 启动浏览器
            browser = await p.chromium.launch(headless=False)  # 使用有头模式便于观察
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
                await asyncio.sleep(5)  # 等待页面完全加载
                
                # 保存页面截图
                main_screenshot_path = f"{file_prefix}_main.png"
                await page.screenshot(path=main_screenshot_path)
                result["files"]["main_screenshot"] = main_screenshot_path
                
                # 获取页面内容
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 获取页面标题
                title = soup.title.string if soup.title else "无标题页面"
                result["content"]["title"] = title
                
                # 提取主要内容
                main_content = self._extract_main_content(soup)
                result["content"]["main_text"] = main_content
                
                # 查找所有iframe
                iframes = await page.query_selector_all('iframe')
                iframe_contents = []
                
                # 处理每个iframe
                for i, iframe in enumerate(iframes):
                    try:
                        # 获取iframe属性
                        iframe_src = await iframe.get_attribute('src')
                        if not iframe_src:
                            continue
                        
                        print(f"处理iframe {i+1}/{len(iframes)}: {iframe_src}")
                        
                        # 获取iframe的位置和大小
                        iframe_box = await iframe.bounding_box()
                        if not iframe_box:
                            continue
                        
                        # 截取iframe区域的截图
                        iframe_screenshot_path = f"{file_prefix}_iframe_{i+1}.png"
                        await page.screenshot(
                            path=iframe_screenshot_path,
                            clip={
                                'x': iframe_box['x'],
                                'y': iframe_box['y'],
                                'width': iframe_box['width'],
                                'height': iframe_box['height']
                            }
                        )
                        
                        # 创建新页面访问iframe内容
                        iframe_page = await context.new_page()
                        
                        # 处理相对URL
                        if not iframe_src.startswith(('http://', 'https://')):
                            iframe_src = urljoin(url, iframe_src)
                        
                        await iframe_page.goto(iframe_src)
                        await iframe_page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2)  # 等待iframe内容加载
                        
                        # 保存iframe完整截图
                        iframe_full_screenshot_path = f"{file_prefix}_iframe_{i+1}_full.png"
                        await iframe_page.screenshot(path=iframe_full_screenshot_path, full_page=True)
                        
                        # 获取iframe内容
                        iframe_html = await iframe_page.content()
                        iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                        
                        # 提取iframe中的表格
                        tables = self._extract_tables_from_iframe(iframe_soup)
                        
                        iframe_contents.append({
                            "src": iframe_src,
                            "tables": tables,
                            "screenshot": iframe_screenshot_path,
                            "full_screenshot": iframe_full_screenshot_path
                        })
                        
                        await iframe_page.close()
                        
                    except Exception as e:
                        print(f"处理iframe {i+1} 时出错: {str(e)}")
                
                result["content"]["iframes"] = iframe_contents
                
                # 生成Markdown内容
                markdown_content = self._generate_markdown(result["content"])
                
                # 保存Markdown文件
                markdown_path = f"{file_prefix}.md"
                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                
                print(f"Markdown内容已保存至: {markdown_path}")
                result["files"]["markdown"] = markdown_path
                
                print("交互式爬取完成!")
                return result
                
            except Exception as e:
                print(f"交互式爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()


async def main():
    # 目标URL
    target_url = "https://aws.highspot.com/items/6721f0d483ce12ab121e6859"
    
    # 创建爬虫实例
    crawler = HighspotIframeCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(headless=False)  # 显示浏览器进行登录
    
    # 选择爬取模式
    print("\n请选择爬取模式:")
    print("1. 基本爬取 - 直接获取页面内容")
    print("2. 交互式爬取 - 处理iframe内容")
    
    choice = input("请输入选择 (1/2): ").strip()
    
    if choice == "1":
        print("\n===== 开始基本爬取 =====")
        result = await crawler.crawl_page(target_url)
    else:
        print("\n===== 开始交互式爬取 =====")
        result = await crawler.crawl_with_iframe_interaction(target_url)
    
    if result:
        print(f"\n爬取完成! Markdown文件保存在: {result['files'].get('markdown')}")
    else:
        print("\n爬取失败!")


if __name__ == "__main__":
    asyncio.run(main())
