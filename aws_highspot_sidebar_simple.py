#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AWS Highspot Sidebar 简易提取器

这个脚本专门用于从AWS Highspot网页中提取侧边栏(sidebar)的详细信息。
特点:
1. 使用playwright自动获取cookie登录
2. 精确定位section class="pod" data-name="details"元素
3. 获取所有文本元素，并将不同div根据class="detail-row"标签保存成不同的list
4. 简洁易用，专注于提取功能
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright

async def save_cookies(url: str, cookies_path: str = "cookies_playwright.json", headless: bool = False) -> None:
    """交互式登录并保存cookies"""
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
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print(f"Cookies已保存至: {cookies_path}")
        await browser.close()

async def extract_sidebar_details(url: str, cookies_path: str = "cookies_playwright.json") -> List[List[str]]:
    """提取侧边栏详细信息，返回每个detail-row的文本列表"""
    # 检查cookies文件是否存在
    if not os.path.exists(cookies_path):
        print(f"Cookie文件不存在: {cookies_path}")
        print("请先运行save_cookies()函数获取cookies")
        return []
    
    print(f"开始提取侧边栏内容: {url}")
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)  # 使用有头模式便于观察
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # 加载cookies
        with open(cookies_path, "r", encoding="utf-8") as f:
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
            
            # 使用JavaScript提取侧边栏内容
            detail_rows = await page.evaluate("""() => {
                // 查找侧边栏元素 - 使用section.pod[data-name="details"]选择器
                const detailsSection = document.querySelector('section.pod[data-name="details"]');
                if (!detailsSection) return [];
                
                // 提取所有detail-row
                const result = [];
                
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
                        result.push(rowTexts);
                    }
                });
                
                return result;
            }""")
            
            print("侧边栏内容提取完成!")
            return detail_rows
            
        except Exception as e:
            print(f"提取过程中出错: {str(e)}")
            return []
        finally:
            await browser.close()

async def main(target_url, output_dir,file_name):
    """主函数"""
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await save_cookies(target_url)
    
    # 提取侧边栏内容
    detail_rows = await extract_sidebar_details(target_url)
    
    if detail_rows:
        print("\n===== 提取的侧边栏内容 =====")
        for i, row in enumerate(detail_rows, 1):
            print(f"{i}. {' | '.join(row)}")
        
        # 保存为JSON文件
        
        os.makedirs(output_dir, exist_ok=True)
        json_path = file_name
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(detail_rows, f, ensure_ascii=False, indent=2)
        print(f"\n侧边栏数据已保存至: {json_path}")
    else:
        print("提取失败或未找到内容!")

if __name__ == "__main__":
    output_dir = "output"
    target_url = "https://aws.highspot.com/items/668747afb742e193718ee837"
    file_name = f"{output_dir}/{target_url.split('/')[-1]}.json"
    asyncio.run(main(target_url, output_dir, file_name))
