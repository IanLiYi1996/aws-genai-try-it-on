#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AWS Highspot Sidebar 详细信息提取器 (更新版)

这个脚本专门用于从AWS Highspot网页中提取侧边栏(sidebar)的详细信息。
特点:
1. 使用playwright自动获取cookie登录
2. 精确定位section class="pod" data-name="details"元素
3. 获取所有文本元素，并将不同div根据class="detail-row"标签保存成不同的list
4. 支持导出为JSON、CSV和文本格式
"""

import asyncio
import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright, Page

class HighspotSidebarExtractorUpdated:
    """专门用于提取AWS Highspot侧边栏详细信息的工具 (更新版)"""
    
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
    
    async def extract_sidebar_details(self, url: str, save_formats: List[str] = ["json", "txt"]) -> Dict[str, Any]:
        """提取侧边栏详细信息
        
        Args:
            url: 目标URL
            save_formats: 保存格式列表，可选值: "json", "txt", "csv"
            
        Returns:
            Dict[str, Any]: 包含提取结果和保存文件路径的字典
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{self.output_dir}/sidebar_details_{timestamp}"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {},
            "content": {}
        }
        
        print(f"开始提取侧边栏内容: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                print(f"Cookie文件不存在: {self.cookies_path}")
                print("请先运行save_cookies()方法获取cookies")
                return result
            
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
                
                # 保存页面截图
                screenshot_path = f"{file_prefix}.png"
                await page.screenshot(path=screenshot_path)
                print(f"页面截图已保存至: {screenshot_path}")
                result["files"]["screenshot"] = screenshot_path
                
                # 提取侧边栏内容
                sidebar_data = await self._extract_sidebar_data(page)
                result["content"] = sidebar_data
                
                # 保存为不同格式
                if "json" in save_formats:
                    json_path = f"{file_prefix}.json"
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(sidebar_data, f, ensure_ascii=False, indent=2)
                    print(f"侧边栏数据已保存为JSON: {json_path}")
                    result["files"]["json"] = json_path
                
                if "txt" in save_formats:
                    text_path = f"{file_prefix}.txt"
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(f"URL: {url}\n")
                        f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        f.write("===== 侧边栏内容 =====\n\n")
                        
                        for row in sidebar_data["details"]:
                            f.write(f"- {' | '.join(row)}\n")
                        f.write("\n")
                    
                    print(f"侧边栏数据已保存为文本: {text_path}")
                    result["files"]["text"] = text_path
                
                if "csv" in save_formats:
                    csv_path = f"{file_prefix}.csv"
                    with open(csv_path, "w", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Label", "Value"])
                        
                        for row in sidebar_data["details"]:
                            if len(row) >= 2:
                                writer.writerow([row[0], row[1]])
                            elif len(row) == 1:
                                writer.writerow(["", row[0]])
                    
                    print(f"侧边栏数据已保存为CSV: {csv_path}")
                    result["files"]["csv"] = csv_path
                
                print("侧边栏内容提取完成!")
                return result
                
            except Exception as e:
                print(f"提取过程中出错: {str(e)}")
                return result
            finally:
                await browser.close()
    
    async def _extract_sidebar_data(self, page: Page) -> Dict[str, List[List[str]]]:
        """提取侧边栏中的详细数据
        
        Args:
            page: Playwright页面对象
            
        Returns:
            Dict[str, List[List[str]]]: 按部分名称组织的详细信息
        """
        # 使用JavaScript提取侧边栏内容
        sidebar_data = await page.evaluate("""() => {
            // 查找侧边栏元素 - 使用section.pod[data-name="details"]选择器
            const detailsSection = document.querySelector('section.pod[data-name="details"]');
            if (!detailsSection) return { details: [] };
            
            // 提取标题
            const title = detailsSection.querySelector('.pod__heading__title')?.textContent.trim() || 'Details';
            
            // 提取所有detail-row
            const result = { details: [] };
            
            // 查找所有detail-row
            const rows = detailsSection.querySelectorAll('.detail-row');
            
            Array.from(rows).forEach(row => {
                // 提取该row下的所有文本元素
                const rowTexts = [];
                
                // 提取label
                const label = row.querySelector('.detail-label');
                if (label && label.textContent.trim()) {
                    rowTexts.push(label.textContent.trim());
                }
                
                // 提取value - 注意这里使用.detail-text而不是.detail-row-value
                const value = row.querySelector('.detail-text');
                if (value) {
                    // 检查是否有链接
                    const link = value.querySelector('a');
                    if (link) {
                        rowTexts.push(link.textContent.trim());
                    } else {
                        const text = value.textContent.trim();
                        if (text) {
                            rowTexts.push(text);
                        }
                    }
                }
                
                // 如果没有找到label和value，则提取所有文本
                if (rowTexts.length === 0) {
                    const text = row.textContent.trim();
                    if (text) {
                        rowTexts.push(text);
                    }
                }
                
                if (rowTexts.length > 0) {
                    result.details.push(rowTexts);
                }
            });
            
            return result;
        }""")
        
        return sidebar_data


async def main():
    """主函数"""
    # 目标URL
    target_url = "https://aws.highspot.com/items/6721f0d483ce12ab121e6859"
    
    # 创建提取器实例
    extractor = HighspotSidebarExtractorUpdated()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await extractor.save_cookies(target_url, headless=False)
    
    # 提取侧边栏内容
    result = await extractor.extract_sidebar_details(target_url, save_formats=["json", "txt", "csv"])
    
    if result["content"] and "details" in result["content"] and result["content"]["details"]:
        print("\n===== 提取的侧边栏内容 =====")
        for row in result["content"]["details"]:
            print(f"- {' | '.join(row)}")
    else:
        print("提取失败或未找到内容!")


if __name__ == "__main__":
    asyncio.run(main())
