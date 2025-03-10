#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("HighspotSidebarCrawler")

class HighspotSidebarCrawler:
    """AWS Highspot侧边栏内容爬取工具，专门用于抓取reader-sidebar中的详细信息"""
    
    def __init__(self, cookies_path: str = "cookies_playwright.json"):
        """初始化爬虫
        
        Args:
            cookies_path: cookie文件路径
        """
        self.cookies_path = cookies_path
        self.base_url = "https://aws.highspot.com"
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def save_cookies(self, headless: bool = False) -> None:
        """交互式登录并保存cookies
        
        Args:
            headless: 是否使用无头模式（默认False，显示浏览器便于登录）
        """
        logger.info("启动浏览器进行登录...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # 访问登录页面
            await page.goto(f"{self.base_url}")
            logger.info("请在打开的浏览器中完成登录操作...")
            
            # 等待用户手动登录
            input("登录完成后，请按回车键继续...")
            
            # 获取并保存cookies
            cookies = await context.cookies()
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cookies已保存至: {self.cookies_path}")
            await browser.close()
    
    async def crawl_sidebar(self, url: str) -> Dict[str, Any]:
        """爬取侧边栏内容
        
        Args:
            url: 目标URL
            
        Returns:
            dict: 包含爬取结果的字典
        """
        # 生成基于时间戳的文件名前缀
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{self.output_dir}/{timestamp}_sidebar"
        
        result = {
            "url": url,
            "timestamp": timestamp,
            "files": {},
            "content": {}
        }
        
        logger.info(f"开始爬取侧边栏: {url}")
        
        async with async_playwright() as p:
            # 检查cookies文件是否存在
            if not os.path.exists(self.cookies_path):
                logger.error(f"Cookie文件不存在: {self.cookies_path}")
                logger.info("请先运行save_cookies()方法获取cookies")
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
                
                # 等待页面完全加载，包括动态内容
                await page.wait_for_load_state("networkidle")
                
                # 额外等待时间，确保动态内容完全加载
                await asyncio.sleep(5)
                
                # 等待侧边栏元素加载
                try:
                    await page.wait_for_selector("#reader-sidebar", timeout=10000)
                except Exception as e:
                    logger.error(f"侧边栏元素未找到: {e}")
                    return None
                
                # 保存页面截图
                screenshot_path = f"{file_prefix}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"页面截图已保存至: {screenshot_path}")
                result["files"]["screenshot"] = screenshot_path
                
                # 提取侧边栏内容
                sidebar_data = await self._extract_sidebar_content(page)
                result["content"]["sidebar"] = sidebar_data
                
                # 保存为JSON文件
                json_path = f"{file_prefix}.json"
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(sidebar_data, f, ensure_ascii=False, indent=2)
                logger.info(f"侧边栏数据已保存至: {json_path}")
                result["files"]["json"] = json_path
                
                # 保存为文本文件
                text_path = f"{file_prefix}.txt"
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("===== 侧边栏内容 =====\n\n")
                    
                    for section in sidebar_data:
                        f.write(f"## {section['title'] if 'title' in section else '未命名部分'}\n\n")
                        for row in section.get("rows", []):
                            f.write(f"- {' | '.join(row)}\n")
                        f.write("\n")
                
                logger.info(f"侧边栏文本已保存至: {text_path}")
                result["files"]["text"] = text_path
                
                logger.info("侧边栏爬取完成!")
                return result
                
            except Exception as e:
                logger.error(f"爬取过程中出错: {str(e)}")
                return None
            finally:
                await browser.close()
    
    async def _extract_sidebar_content(self, page: Page) -> List[Dict[str, Any]]:
        """提取侧边栏内容
        
        Args:
            page: Playwright页面对象
            
        Returns:
            list: 侧边栏内容列表
        """
        # 使用JavaScript提取侧边栏内容
        sidebar_data = await page.evaluate("""() => {
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
            const sections = detailsSection.querySelectorAll('.detail-section');
            
            Array.from(sections).forEach(section => {
                const sectionData = {
                    title: section.querySelector('.detail-section-title')?.textContent.trim() || '',
                    rows: []
                };
                
                // 提取该section下的所有detail-row
                const rows = section.querySelectorAll('.detail-row');
                Array.from(rows).forEach(row => {
                    // 提取该row下的所有文本元素
                    const textElements = [];
                    
                    // 提取label
                    const label = row.querySelector('.detail-row-label');
                    if (label && label.textContent.trim()) {
                        textElements.push(label.textContent.trim());
                    }
                    
                    // 提取value
                    const value = row.querySelector('.detail-row-value');
                    if (value && value.textContent.trim()) {
                        textElements.push(value.textContent.trim());
                    }
                    
                    // 如果没有找到label和value，则提取所有文本
                    if (textElements.length === 0) {
                        const text = row.textContent.trim();
                        if (text) {
                            textElements.push(text);
                        }
                    }
                    
                    if (textElements.length > 0) {
                        sectionData.rows.push(textElements);
                    }
                });
                
                if (sectionData.rows.length > 0 || sectionData.title) {
                    result.push(sectionData);
                }
            });
            
            return result;
        }""")
        
        return sidebar_data


async def main():
    """主函数"""
    # 目标URL
    target_url = "https://aws.highspot.com/items/648c159dc87bf45f04a7fb06"
    
    # 创建爬虫实例
    crawler = HighspotSidebarCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        logger.info("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(headless=False)
    
    # 爬取侧边栏内容
    result = await crawler.crawl_sidebar(target_url)
    
    if result:
        logger.info(f"爬取成功! 结果保存在: {', '.join(result['files'].values())}")
        
        # 显示提取的内容
        print("\n===== 提取的侧边栏内容 =====")
        for section in result["content"]["sidebar"]:
            print(f"\n## {section.get('title', '未命名部分')}")
            for row in section.get("rows", []):
                print(f"- {' | '.join(row)}")
    else:
        logger.error("爬取失败!")


if __name__ == "__main__":
    asyncio.run(main())
