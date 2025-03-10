#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AWS Highspot Sidebar 优化版提取器

这个脚本专门用于从AWS Highspot网页中提取侧边栏(sidebar)的详细信息。
特点:
1. 使用多进程并行处理多个URL，显著提高处理速度
2. 优化浏览器实例管理，减少启动和关闭开销
3. 智能等待策略，减少不必要的等待时间
4. 完全在无头模式下运行，不会打开浏览器窗口
5. 更好的错误处理和进度显示
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import concurrent.futures
from pathlib import Path
import logging
from tqdm import tqdm
import signal

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('highspot_extractor.log')
    ]
)
logger = logging.getLogger(__name__)

# 全局配置
CONFIG = {
    'max_workers': 4,                # 最大并行进程数
    'browser_launch_timeout': 30000, # 浏览器启动超时时间(ms)
    'page_load_timeout': 30000,      # 页面加载超时时间(ms)
    'element_timeout': 10000,        # 元素等待超时时间(ms)
    'retry_attempts': 2,             # 重试次数
    'retry_delay': 2,                # 重试延迟(秒)
    'cookies_path': 'cookies_playwright.json',
    'output_dir': 'output',
}

class HighspotExtractor:
    """Highspot侧边栏提取器类"""
    
    def __init__(self, cookies_path: str = CONFIG['cookies_path']):
        """初始化提取器"""
        self.cookies_path = cookies_path
        self._browser = None
        self._context = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
    
    async def initialize(self):
        """初始化浏览器和上下文"""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._playwright = playwright
            self._browser = await playwright.chromium.launch(
                headless=True,
                timeout=CONFIG['browser_launch_timeout']
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # 加载cookies (如果存在)
            if os.path.exists(self.cookies_path):
                with open(self.cookies_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
    
    async def close(self):
        """关闭浏览器和上下文"""
        if self._context:
            await self._context.close()
            self._context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
            
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
    
    async def save_cookies(self, url: str) -> bool:
        """交互式登录并保存cookies"""
        logger.info("启动浏览器进行登录...")
        
        try:
            await self.initialize()
            page = await self._context.new_page()
            
            # 访问登录页面
            await page.goto(url, timeout=CONFIG['page_load_timeout'])
            logger.info("请在打开的浏览器中完成登录操作...")
            
            # 等待用户手动登录
            input("登录完成后，请按回车键继续...")
            
            # 获取并保存cookies
            cookies = await self._context.cookies()
            with open(self.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cookies已保存至: {self.cookies_path}")
            await page.close()
            return True
            
        except Exception as e:
            logger.error(f"保存cookies失败: {str(e)}")
            return False
    
    async def extract_sidebar_details(self, url: str, retry_count: int = 0) -> Tuple[List[List[str]], bool]:
        """提取侧边栏详细信息，返回每个detail-row的文本列表和成功标志"""
        if not os.path.exists(self.cookies_path):
            logger.error(f"Cookie文件不存在: {self.cookies_path}")
            return [], False
        
        if retry_count > CONFIG['retry_attempts']:
            logger.error(f"超过最大重试次数: {url}")
            return [], False
        
        try:
            await self.initialize()
            page = await self._context.new_page()
            
            # 设置页面超时
            page.set_default_timeout(CONFIG['page_load_timeout'])
            
            # 访问目标页面
            response = await page.goto(url)
            if not response or response.status >= 400:
                logger.error(f"页面加载失败 ({response.status if response else 'unknown'}): {url}")
                await page.close()
                return await self._retry_extract(url, retry_count)
            
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            
            # 等待关键元素出现
            try:
                await page.wait_for_selector('section.pod[data-name="details"]', timeout=CONFIG['element_timeout'])
            except PlaywrightTimeoutError:
                logger.warning(f"未找到关键元素 'section.pod[data-name=\"details\"]': {url}")
                # 尝试截图记录问题
                await page.screenshot(path=f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                await page.close()
                return await self._retry_extract(url, retry_count)
            
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
            
            await page.close()
            
            if not detail_rows:
                logger.warning(f"未提取到侧边栏内容: {url}")
                return await self._retry_extract(url, retry_count)
            
            return detail_rows, True
            
        except Exception as e:
            logger.error(f"提取过程中出错 ({url}): {str(e)}")
            return await self._retry_extract(url, retry_count)
    
    async def _retry_extract(self, url: str, retry_count: int) -> Tuple[List[List[str]], bool]:
        """重试提取逻辑"""
        retry_count += 1
        if retry_count <= CONFIG['retry_attempts']:
            logger.info(f"重试 ({retry_count}/{CONFIG['retry_attempts']}): {url}")
            await asyncio.sleep(CONFIG['retry_delay'])
            return await self.extract_sidebar_details(url, retry_count)
        return [], False

async def process_single_url(url: str, output_path: str, cookies_path: str) -> bool:
    """处理单个URL并保存结果"""
    async with HighspotExtractor(cookies_path) as extractor:
        detail_rows, success = await extractor.extract_sidebar_details(url)
        
        if success and detail_rows:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存为JSON文件
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(detail_rows, f, ensure_ascii=False, indent=2)
            
            return True
        return False

def process_url_wrapper(args):
    """包装异步函数以在进程池中使用"""
    url, output_path, cookies_path = args
    return asyncio.run(process_single_url(url, output_path, cookies_path))

async def ensure_cookies_exist(url: str, cookies_path: str) -> bool:
    """确保cookies文件存在，如果不存在则获取"""
    if not os.path.exists(cookies_path):
        logger.info(f"Cookie文件不存在: {cookies_path}")
        async with HighspotExtractor(cookies_path) as extractor:
            return await extractor.save_cookies(url)
    return True

def load_urls_from_directory(directory_path: str) -> List[Tuple[str, str]]:
    """从目录中加载URL和对应的输出路径"""
    result = []
    directory = Path(directory_path)
    
    if not directory.exists():
        logger.error(f"目录不存在: {directory_path}")
        return result
    
    for file_path in directory.glob('*.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取URL
            if 'metadataAttributes' in data and 'x-amz-bedrock-kb-source-uri' in data['metadataAttributes']:
                url = data['metadataAttributes']['x-amz-bedrock-kb-source-uri']['value']['stringValue']
                output_path = Path(CONFIG['output_dir']) / f"{file_path.name}.json"
                
                # 如果输出文件已存在，跳过
                if not output_path.exists():
                    result.append((url, str(output_path)))
        except Exception as e:
            logger.error(f"处理文件失败 ({file_path}): {str(e)}")
    
    return result

async def main():
    """主函数"""
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='AWS Highspot Sidebar 优化版提取器')
    parser.add_argument('--directory', '-d', type=str, 
                        default='/Users/ianleely/Documents/Codes/aws-genai-try-it-on/files/metadata-files/metadata-chage-pdf-to-txt',
                        help='包含元数据文件的目录路径')
    parser.add_argument('--output', '-o', type=str, 
                        default='/Users/ianleely/Documents/Codes/aws-genai-try-it-on/output',
                        help='输出目录路径')
    parser.add_argument('--workers', '-w', type=int, default=CONFIG['max_workers'],
                        help=f'并行工作进程数 (默认: {CONFIG["max_workers"]})')
    parser.add_argument('--cookies', '-c', type=str, default=CONFIG['cookies_path'],
                        help=f'cookies文件路径 (默认: {CONFIG["cookies_path"]})')
    args = parser.parse_args()
    
    # 更新配置
    CONFIG['output_dir'] = args.output
    CONFIG['max_workers'] = args.workers
    CONFIG['cookies_path'] = args.cookies
    
    # 确保输出目录存在
    os.makedirs(CONFIG['output_dir'], exist_ok=True)
    
    # 加载URL列表
    url_list = load_urls_from_directory(args.directory)
    if not url_list:
        logger.error("未找到需要处理的URL")
        return
    
    logger.info(f"找到 {len(url_list)} 个URL需要处理")
    
    # 确保cookies存在
    sample_url = url_list[0][0] if url_list else "https://aws.highspot.com"
    cookies_exist = await ensure_cookies_exist(sample_url, CONFIG['cookies_path'])
    if not cookies_exist:
        logger.error("无法获取cookies，退出程序")
        return
    
    # 准备进程池参数
    process_args = [(url, output_path, CONFIG['cookies_path']) for url, output_path in url_list]
    
    # 使用进程池并行处理
    start_time = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=CONFIG['max_workers']) as executor:
        results = list(tqdm(
            executor.map(process_url_wrapper, process_args),
            total=len(process_args),
            desc="处理URL"
        ))
    
    # 统计结果
    success_count = sum(1 for r in results if r)
    elapsed_time = time.time() - start_time
    
    logger.info(f"处理完成: 总计 {len(url_list)} 个URL, 成功 {success_count} 个, 失败 {len(url_list) - success_count} 个")
    logger.info(f"总耗时: {elapsed_time:.2f} 秒, 平均每个URL: {elapsed_time/len(url_list):.2f} 秒")

if __name__ == "__main__":
    # 处理Ctrl+C信号
    signal.signal(signal.SIGINT, lambda sig, frame: print("\n程序被用户中断") or os._exit(0))
    
    # 运行主函数
    asyncio.run(main())
