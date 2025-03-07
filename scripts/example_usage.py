#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
from highspot_iframe_crawler import HighspotIframeCrawler
from advanced_iframe_crawler import AdvancedIframeCrawler

async def example_basic_crawler():
    """基本爬虫使用示例"""
    print("===== 基本爬虫示例 =====")
    
    # 目标URL
    target_url = "https://aws.highspot.com/items/6721f0d483ce12ab121e6859"
    
    # 创建爬虫实例
    crawler = HighspotIframeCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(headless=False)  # 显示浏览器进行登录
    
    # 爬取内容
    result = await crawler.crawl_page(target_url)
    
    if result:
        print(f"爬取成功! Markdown文件保存在: {result['files'].get('markdown')}")
        
        # 访问爬取结果
        print(f"页面标题: {result['content'].get('title')}")
        print(f"主要内容项数: {len(result['content'].get('main_text', []))}")
        print(f"发现iframe数: {len(result['content'].get('iframes', []))}")
        
        # 访问iframe中的表格
        for i, iframe in enumerate(result['content'].get('iframes', [])):
            print(f"Iframe {i+1} 表格数: {len(iframe.get('tables', []))}")
    else:
        print("爬取失败!")

async def example_advanced_crawler():
    """高级爬虫使用示例"""
    print("\n===== 高级爬虫示例 =====")
    
    # 目标URL
    target_url = "https://aws.highspot.com/items/6721f0d483ce12ab121e6859"
    
    # 创建爬虫实例
    crawler = AdvancedIframeCrawler()
    
    # 如果没有cookie或cookie已过期，先获取cookie
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，开始获取...")
        await crawler.save_cookies(target_url, headless=False)  # 显示浏览器进行登录
    
    # 爬取内容
    markdown_path = await crawler.crawl(target_url)
    
    if markdown_path:
        print(f"爬取成功! Markdown文件保存在: {markdown_path}")
        
        # 读取生成的Markdown文件
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 显示Markdown内容的一部分
        print("\nMarkdown内容预览:")
        print("=" * 50)
        print(content[:500] + "...")  # 显示前500个字符
        print("=" * 50)
    else:
        print("爬取失败!")

async def main():
    """运行示例"""
    # 运行基本爬虫示例
    await example_basic_crawler()
    
    # 运行高级爬虫示例
    await example_advanced_crawler()

if __name__ == "__main__":
    asyncio.run(main())
