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

class AdvancedIframeCrawler:
    """高级网页爬虫，专门处理iframe中的表格内容，支持深度抓取和布局保留"""
    
    def __init__(self, cookies_path="cookies_playwright.json"):
        """初始化爬虫
        
        Args:
            cookies_path: cookie文件路径
        """
        self.cookies_path = cookies_path
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def save_cookies(self, url, headless=False):
        """交互式登录并保存cookies
        
        Args:
            url: 登录页面URL
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
            await page.goto(url)
            print(f"请在打开的浏览器中完成登录操作...")
            
            # 等待用户手动登录
            input("登录完成后，请按回车键继续...")
            
            # 获取并保存cookies
            cookies = await context.cookies()
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            print(f"Cookies已保存至: {self.cookies_path}")
            await browser.close()
    
    async def crawl(self, url):
        """爬取页面内容，包括处理iframe
        
        Args:
            url: 目标URL
            
        Returns:
            str: 生成的Markdown内容路径
        """
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{self.output_dir}/{timestamp}_crawl"
        
        print(f"开始爬取: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return None
            
            # 启动浏览器
            browser = await p.chromium.launch(headless=False)  # 使用有头模式便于调试
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
                await page.screenshot(path=main_screenshot_path, full_page=True)
                print(f"主页面截图已保存至: {main_screenshot_path}")
                
                # 获取页面内容
                html_content = await page.content()
                with open(f"{file_prefix}_main.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                # 解析HTML
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 获取页面标题
                title = soup.title.string if soup.title else "无标题页面"
                
                # 初始化Markdown内容
                markdown_content = f"# {title}\n\n"
                markdown_content += f"*爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
                markdown_content += f"*来源URL: {url}*\n\n"
                markdown_content += "---\n\n"
                
                # 提取主要内容
                main_content_md = await self._extract_main_content_md(page)
                markdown_content += main_content_md
                
                # 查找所有iframe
                iframes = await page.query_selector_all('iframe')
                
                if iframes:
                    markdown_content += "\n## Iframe内容\n\n"
                
                # 处理每个iframe
                for i, iframe in enumerate(iframes):
                    try:
                        # 获取iframe属性
                        iframe_src = await iframe.get_attribute('src')
                        if not iframe_src:
                            continue
                        
                        iframe_title = await iframe.get_attribute('title') or f"Iframe {i+1}"
                        
                        print(f"处理iframe {i+1}/{len(iframes)}: {iframe_title}")
                        markdown_content += f"### {iframe_title}\n\n"
                        
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
                        print(f"Iframe {i+1} 截图已保存至: {iframe_screenshot_path}")
                        
                        # 处理相对URL
                        if not iframe_src.startswith(('http://', 'https://')):
                            iframe_src = urljoin(url, iframe_src)
                        
                        # 创建新页面访问iframe内容
                        iframe_page = await context.new_page()
                        await iframe_page.goto(iframe_src)
                        await iframe_page.wait_for_load_state("networkidle")
                        await asyncio.sleep(2)  # 等待iframe内容加载
                        
                        # 保存iframe完整截图
                        iframe_full_screenshot_path = f"{file_prefix}_iframe_{i+1}_full.png"
                        await iframe_page.screenshot(path=iframe_full_screenshot_path, full_page=True)
                        
                        # 获取iframe内容
                        iframe_html = await iframe_page.content()
                        with open(f"{file_prefix}_iframe_{i+1}.html", "w", encoding="utf-8") as f:
                            f.write(iframe_html)
                        
                        # 提取iframe中的内容
                        iframe_content_md = await self._extract_iframe_content_md(iframe_page)
                        markdown_content += iframe_content_md
                        
                        await iframe_page.close()
                        
                    except Exception as e:
                        print(f"处理iframe {i+1} 时出错: {str(e)}")
                        markdown_content += f"*处理此iframe时出错: {str(e)}*\n\n"
                
                # 保存Markdown文件
                markdown_path = f"{file_prefix}.md"
                with open(markdown_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                
                print(f"Markdown内容已保存至: {markdown_path}")
                return markdown_path
                
            except Exception as e:
                print(f"爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()
    
    async def _extract_main_content_md(self, page):
        """提取页面主要内容并转换为Markdown
        
        Args:
            page: Playwright页面对象
            
        Returns:
            str: Markdown格式的内容
        """
        # 使用JavaScript提取结构化内容
        content_structure = await page.evaluate("""() => {
            function getTextContent(element) {
                return element.textContent.trim();
            }
            
            function extractHeadings() {
                const headings = [];
                for (let i = 1; i <= 6; i++) {
                    document.querySelectorAll(`h${i}`).forEach(h => {
                        headings.push({
                            type: `h${i}`,
                            level: i,
                            content: getTextContent(h)
                        });
                    });
                }
                return headings;
            }
            
            function extractParagraphs() {
                const paragraphs = [];
                document.querySelectorAll('p').forEach(p => {
                    const content = getTextContent(p);
                    if (content) {
                        paragraphs.push({
                            type: 'p',
                            content: content
                        });
                    }
                });
                return paragraphs;
            }
            
            function extractLists() {
                const lists = [];
                
                // 提取无序列表
                document.querySelectorAll('ul').forEach(ul => {
                    const items = [];
                    ul.querySelectorAll('li').forEach(li => {
                        const content = getTextContent(li);
                        if (content) {
                            items.push(content);
                        }
                    });
                    
                    if (items.length > 0) {
                        lists.push({
                            type: 'ul',
                            items: items
                        });
                    }
                });
                
                // 提取有序列表
                document.querySelectorAll('ol').forEach(ol => {
                    const items = [];
                    ol.querySelectorAll('li').forEach(li => {
                        const content = getTextContent(li);
                        if (content) {
                            items.push(content);
                        }
                    });
                    
                    if (items.length > 0) {
                        lists.push({
                            type: 'ol',
                            items: items
                        });
                    }
                });
                
                return lists;
            }
            
            return {
                headings: extractHeadings(),
                paragraphs: extractParagraphs(),
                lists: extractLists()
            };
        }""")
        
        # 提取表格
        tables = await self._extract_tables_from_page(page)
        
        # 生成Markdown
        markdown = "## 页面内容\n\n"
        
        # 添加标题
        for heading in content_structure.get('headings', []):
            level = heading.get('level', 1)
            content = heading.get('content', '')
            if content:
                markdown += f"{'#' * (level + 1)} {content}\n\n"
        
        # 添加段落
        for paragraph in content_structure.get('paragraphs', []):
            content = paragraph.get('content', '')
            if content:
                markdown += f"{content}\n\n"
        
        # 添加列表
        for list_item in content_structure.get('lists', []):
            list_type = list_item.get('type', 'ul')
            items = list_item.get('items', [])
            
            if list_type == 'ul':
                for item in items:
                    markdown += f"- {item}\n"
                markdown += "\n"
            else:  # ol
                for i, item in enumerate(items, 1):
                    markdown += f"{i}. {item}\n"
                markdown += "\n"
        
        # 添加表格
        for i, table in enumerate(tables, 1):
            markdown += f"### 表格 {i}\n\n"
            
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
    
    async def _extract_iframe_content_md(self, iframe_page):
        """提取iframe内容并转换为Markdown
        
        Args:
            iframe_page: Playwright页面对象（iframe）
            
        Returns:
            str: Markdown格式的内容
        """
        # 提取表格（iframe中最重要的内容）
        tables = await self._extract_tables_from_page(iframe_page)
        
        # 生成Markdown
        markdown = ""
        
        # 添加表格
        for i, table in enumerate(tables, 1):
            markdown += f"#### 表格 {i}\n\n"
            
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
        
        # 如果没有表格，尝试提取其他内容
        if not tables:
            # 使用JavaScript提取文本内容
            text_content = await iframe_page.evaluate("""() => {
                return document.body.innerText;
            }""")
            
            if text_content:
                markdown += "#### 文本内容\n\n"
                markdown += f"{text_content}\n\n"
        
        return markdown
    
    async def _extract_tables_from_page(self, page):
        """从页面中提取表格
        
        Args:
            page: Playwright页面对象
            
        Returns:
            list: 表格数据列表
        """
        # 使用JavaScript提取表格
        tables_data = await page.evaluate("""() => {
            const tables = [];
            
            document.querySelectorAll('table').forEach(table => {
                const tableData = {
                    headers: [],
                    rows: []
                };
                
                // 提取表头
                const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
                if (headerRow) {
                    headerRow.querySelectorAll('th, td').forEach(cell => {
                        tableData.headers.push(cell.textContent.trim());
                    });
                }
                
                // 提取表格内容
                const tbody = table.querySelector('tbody') || table;
                const rows = tbody.querySelectorAll('tr');
                
                // 如果第一行是表头，从第二行开始
                const startIndex = (table.querySelector('thead') || tableData.headers.length === 0) ? 0 : 1;
                
                for (let i = startIndex; i < rows.length; i++) {
                    const row = rows[i];
                    const rowData = [];
                    
                    row.querySelectorAll('td').forEach(cell => {
                        rowData.push(cell.textContent.trim());
                    });
                    
                    if (rowData.length > 0) {
                        tableData.rows.push(rowData);
                    }
                }
                
                // 只添加非空表格
                if (tableData.headers.length > 0 || tableData.rows.length > 0) {
                    tables.push(tableData);
                }
            });
            
            return tables;
        }""")
        
        return tables_data


async def main():
    # 目标URL
    target_url = "https://aws.highspot.com/items/6721f0d483ce12ab121e6859"
    
    # 创建爬虫实例
    crawler = AdvancedIframeCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(target_url, headless=False)
    
    # 爬取内容
    markdown_path = await crawler.crawl(target_url)
    
    if markdown_path:
        print(f"\n爬取完成! Markdown文件保存在: {markdown_path}")
    else:
        print("\n爬取失败!")


if __name__ == "__main__":
    asyncio.run(main())
