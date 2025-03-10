#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AWS Highspot Sidebar 提取器

这个脚本专门用于从AWS Highspot网页中提取侧边栏(sidebar)的详细信息。
它使用Playwright自动获取cookie并登录，然后提取指定xpath下的内容。

使用方法:
1. 首次运行时，会打开浏览器让用户手动登录
2. 登录后，脚本会保存cookie以便后续使用
3. 脚本会提取sidebar中的所有detail-row内容并保存
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright, Page

class HighspotSidebarExtractor:
    """专门用于提取AWS Highspot侧边栏内容的爬虫工具"""
    
    def __init__(self, cookies_path: str = "cookies_playwright.json"):
        """初始化提取器
        
        Args:
            cookies_path: cookie文件路径
        """
        self.cookies_path = cookies_path
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def save_cookies(self, url: str, headless: bool = False) -> None:
        """交互式登录并保存cookies
        
        Args:
            url: 登录页面URL
            headless: 是否使用无头模式
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
            print("请在打开的浏览器中完成登录操作...")
            
            # 等待用户手动登录
            input("登录完成后，请按回车键继续...")
            
            # 获取并保存cookies
            cookies = await context.cookies()
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            print(f"Cookies已保存至: {self.cookies_path}")
            await browser.close()
    
    async def extract_sidebar_details(self, url: str) -> List[List[str]]:
        """提取侧边栏详细信息
        
        Args:
            url: 目标URL
            
        Returns:
            List[List[str]]: 提取的详细信息，每个detail-row作为一个列表
        """
        print(f"开始提取侧边栏内容: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return []
            
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
                
                # 等待页面完全加载
                await page.wait_for_load_state("networkidle")
                
                # 额外等待时间，确保动态内容完全加载
                await asyncio.sleep(5)
                
                # 等待侧边栏元素加载
                try:
                    await page.wait_for_selector("#reader-sidebar", timeout=10000)
                except Exception as e:
                    print(f"侧边栏元素未找到: {e}")
                    return []
                
                # 保存页面截图
                screenshot_path = f"{self.output_dir}/sidebar_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path)
                print(f"页面截图已保存至: {screenshot_path}")
                
                # 提取侧边栏内容
                detail_rows = await self._extract_detail_rows(page)
                
                # 保存为JSON文件
                json_path = f"{self.output_dir}/sidebar_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(detail_rows, f, ensure_ascii=False, indent=2)
                print(f"侧边栏数据已保存至: {json_path}")
                
                print("侧边栏内容提取完成!")
                return detail_rows
                
            except Exception as e:
                print(f"提取过程中出错: {str(e)}")
                return []
            finally:
                await browser.close()
    
    async def _extract_detail_rows(self, page: Page) -> List[List[str]]:
        """提取侧边栏中的detail-row内容
        
        Args:
            page: Playwright页面对象
            
        Returns:
            List[List[str]]: 提取的详细信息，每个detail-row作为一个列表
        """
        # 使用JavaScript提取侧边栏内容
        detail_rows = await page.evaluate("""() => {
            // 使用XPath查找侧边栏元素
            const getElementByXPath = (xpath) => {
                return document.evaluate(
                    xpath, 
                    document, 
                    null, 
                    XPathResult.FIRST_ORDERED_NODE_TYPE, 
                    null
                ).singleNodeValue;
            };
            
            // 查找侧边栏元素
            const sidebar = document.querySelector('#reader-sidebar');
            if (!sidebar) return [];
            
            // 查找details部分
            const detailsSection = Array.from(sidebar.querySelectorAll('section')).find(
                section => section.getAttribute('data-name') === 'details'
            );
            
            if (!detailsSection) return [];
            
            // 提取所有detail-row
            const result = [];
            const rows = detailsSection.querySelectorAll('.detail-row');
            
            Array.from(rows).forEach(row => {
                // 提取该row下的所有文本元素
                const rowTexts = [];
                
                // 提取label
                const label = row.querySelector('.detail-row-label');
                if (label && label.textContent.trim()) {
                    rowTexts.push(label.textContent.trim());
                }
                
                // 提取value
                const value = row.querySelector('.detail-row-value');
                if (value && value.textContent.trim()) {
                    rowTexts.push(value.textContent.trim());
                }
                
                // 如果没有找到label和value，则提取所有文本
                if (rowTexts.length === 0) {
                    const text = row.textContent.trim();
                    if (text) {
                        rowTexts.push(text);
                    }
                }
                
                if (rowTexts.length > 0) {
                    result.push(rowTexts);
                }
            });
            
            return result;
        }""")
        
        return detail_rows


async def main():
    """主函数"""
    # 目标URL
    target_url = "https://aws.highspot.com/items/648c159dc87bf45f04a7fb06"
    
    # 创建提取器实例
    extractor = HighspotSidebarExtractor()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await extractor.save_cookies(target_url, headless=False)
    
    # 提取侧边栏内容
    detail_rows = await extractor.extract_sidebar_details(target_url)
    
    if detail_rows:
        print("\n===== 提取的侧边栏内容 =====")
        for i, row in enumerate(detail_rows, 1):
            print(f"{i}. {' | '.join(row)}")
    else:
        print("提取失败!")


if __name__ == "__main__":
    asyncio.run(main())
