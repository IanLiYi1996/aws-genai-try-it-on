#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
# 修正导入路径
from aws_highspot_crawler import HighspotCrawler  # 当在同一目录下运行时
# 如果从其他目录运行，可能需要使用以下导入方式
# import sys
# sys.path.append('/path/to/scripts')
# from aws_highspot_crawler import HighspotCrawler

async def run_example():
    """运行爬虫示例"""
    
    # 目标URL
    target_url = "https://aws.highspot.com/spots/60bdbd9634d6be4dbd9ce328?list=all&overview=true"
    
    # 创建输出目录
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建爬虫实例
    crawler = HighspotCrawler()
    
    # 检查cookie是否存在
    if not os.path.exists("cookies_playwright.json"):
        print("Cookie文件不存在，需要先登录获取Cookie")
        await crawler.save_cookies(headless=False)  # 显示浏览器进行登录
    
    # 选择爬取模式
    print("\n请选择爬取模式:")
    print("1. 基本爬取 - 直接获取页面内容")
    print("2. 交互式爬取 - 执行滚动、点击等操作后获取内容")
    print("3. 两种模式都执行")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    if choice == "1" or choice == "3":
        print("\n===== 开始基本爬取 =====")
        result = await crawler.crawl_content(target_url, output_dir=output_dir)
        if result:
            print(f"基本爬取完成，输出文件保存在 {output_dir} 目录")
    
    if choice == "2" or choice == "3":
        print("\n===== 开始交互式爬取 =====")
        
        # 修改默认交互操作
        default_interactions = [
            {"action": "wait", "time": 5},  # 等待5秒确保页面初始加载
            {"action": "scroll", "position": "bottom"},  # 渐进式滚动到底部
            {"action": "wait", "time": 5},  # 等待最终内容加载完成
        ]
        
        # 询问是否需要自定义交互
        custom = input("是否需要自定义交互操作? (y/n): ").strip().lower()
        
        interactions = default_interactions
        
        if custom == "y":
            interactions = []
            print("添加交互操作 (输入'完成'结束):")
            
            while True:
                print("\n可用操作类型:")
                print("1. wait - 等待指定秒数")
                print("2. scroll - 滚动页面 (top/bottom/数字)")
                print("3. click - 点击元素 (需要CSS选择器)")
                print("4. 完成 - 结束添加")
                
                action_type = input("请选择操作类型 (1/2/3/4): ").strip()
                
                if action_type == "4" or action_type.lower() == "完成":
                    break
                
                if action_type == "1":
                    time_value = float(input("等待秒数: ").strip())
                    interactions.append({"action": "wait", "time": time_value})
                
                elif action_type == "2":
                    position = input("滚动位置 (top/bottom/数字): ").strip()
                    interactions.append({"action": "scroll", "position": position})
                
                elif action_type == "3":
                    selector = input("CSS选择器: ").strip()
                    interactions.append({"action": "click", "selector": selector})
        
        # 执行交互式爬取
        interactive_result = await crawler.crawl_with_interaction(
            target_url, interactions, output_dir=output_dir
        )
        
        if interactive_result:
            print(f"交互式爬取完成，输出文件保存在 {output_dir} 目录")
    
    print("\n爬取任务全部完成!")

if __name__ == "__main__":
    asyncio.run(run_example())
