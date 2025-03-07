#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import argparse
import os
import sys
from datetime import datetime

# 确保可以导入爬虫模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from highspot_iframe_crawler import HighspotIframeCrawler
    from advanced_iframe_crawler import AdvancedIframeCrawler
except ImportError as e:
    print(f"导入爬虫模块失败: {e}")
    print("请确保highspot_iframe_crawler.py和advanced_iframe_crawler.py在同一目录下")
    sys.exit(1)

async def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='AWS Highspot网页爬虫，支持iframe表格抓取')
    parser.add_argument('url', help='要爬取的网页URL')
    parser.add_argument('--mode', choices=['basic', 'advanced'], default='advanced',
                      help='爬取模式: basic(基本模式) 或 advanced(高级模式，默认)')
    parser.add_argument('--cookies', default='cookies_playwright.json',
                      help='Cookie文件路径 (默认: cookies_playwright.json)')
    parser.add_argument('--output', default='output',
                      help='输出目录 (默认: output)')
    parser.add_argument('--headless', action='store_true',
                      help='使用无头模式运行浏览器 (默认: 显示浏览器)')
    parser.add_argument('--login', action='store_true',
                      help='强制重新登录获取cookie (默认: 如果cookie文件存在则使用)')
    
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)
    
    # 检查URL是否有效
    if not args.url.startswith(('http://', 'https://')):
        print("错误: URL必须以http://或https://开头")
        sys.exit(1)
    
    # 检查是否需要登录获取cookie
    if args.login or not os.path.exists(args.cookies):
        print("需要登录获取cookie...")
        
        if args.mode == 'basic':
            crawler = HighspotIframeCrawler(cookies_path=args.cookies)
            await crawler.save_cookies(headless=args.headless)
        else:
            crawler = AdvancedIframeCrawler(cookies_path=args.cookies)
            await crawler.save_cookies(args.url, headless=args.headless)
    
    # 根据模式选择爬虫
    if args.mode == 'basic':
        print(f"使用基本爬虫模式爬取: {args.url}")
        crawler = HighspotIframeCrawler(cookies_path=args.cookies)
        crawler.output_dir = args.output
        
        # 爬取内容
        result = await crawler.crawl_page(args.url)
        
        if result:
            print(f"\n爬取完成! Markdown文件保存在: {result['files'].get('markdown')}")
        else:
            print("\n爬取失败!")
    else:
        print(f"使用高级爬虫模式爬取: {args.url}")
        crawler = AdvancedIframeCrawler(cookies_path=args.cookies)
        crawler.output_dir = args.output
        
        # 爬取内容
        markdown_path = await crawler.crawl(args.url)
        
        if markdown_path:
            print(f"\n爬取完成! Markdown文件保存在: {markdown_path}")
        else:
            print("\n爬取失败!")

if __name__ == "__main__":
    # 记录开始时间
    start_time = datetime.now()
    print(f"爬虫开始运行: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行主函数
    asyncio.run(main())
    
    # 记录结束时间
    end_time = datetime.now()
    print(f"爬虫结束运行: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {end_time - start_time}")
