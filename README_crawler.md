# AWS Highspot 网站爬虫

这是一个用于抓取AWS Highspot网站内容的Python爬虫，特别支持动态渲染内容的提取。

## 功能特点

- 使用Playwright自动化浏览器操作，支持完整的JavaScript渲染
- 通过Cookie方式保持登录状态
- 支持交互式操作（点击、滚动等）以获取动态加载的内容
- 提取并保存HTML、截图和文本内容
- 提取JavaScript动态渲染的数据

## 安装依赖

```bash
pip install -r requirements.txt

# 安装Playwright浏览器
python -m playwright install
```

## 使用方法

### 1. 获取Cookie

首次使用时，需要获取Cookie：

```bash
python scripts/aws_highspot_crawler.py
```

脚本会打开浏览器，等待您手动登录AWS Highspot网站。登录成功后，按回车键继续，脚本会自动保存Cookie到`cookies_playwright.json`文件。

### 2. 基本使用

```python
import asyncio
from scripts.aws_highspot_crawler import HighspotCrawler

async def main():
    # 创建爬虫实例
    crawler = HighspotCrawler()
    
    # 爬取目标URL
    url = "https://aws.highspot.com/spots/60bdbd9634d6be4dbd9ce328?list=all&overview=true"
    result = await crawler.crawl_content(url, output_dir="output")
    
    print("爬取完成!")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. 交互式爬取

如果需要在爬取前进行交互操作（如点击、滚动等），可以使用`crawl_with_interaction`方法：

```python
import asyncio
from scripts.aws_highspot_crawler import HighspotCrawler

async def main():
    # 创建爬虫实例
    crawler = HighspotCrawler()
    
    # 定义交互操作
    interactions = [
        {"action": "wait", "time": 2},  # 等待2秒
        {"action": "scroll", "position": "bottom"},  # 滚动到底部
        {"action": "wait", "time": 2},  # 等待2秒
        {"action": "click", "selector": "button.load-more"},  # 点击"加载更多"按钮
    ]
    
    # 爬取目标URL
    url = "https://aws.highspot.com/spots/60bdbd9634d6be4dbd9ce328?list=all&overview=true"
    result = await crawler.crawl_with_interaction(url, interactions, output_dir="output")
    
    print("交互式爬取完成!")

if __name__ == "__main__":
    asyncio.run(main())
```

## 输出文件

爬虫会在指定的输出目录（默认为`output`）生成以下文件：

- `{timestamp}_highspot.html` - 页面HTML内容
- `{timestamp}_highspot.png` - 页面截图
- `{timestamp}_highspot_content.txt` - 提取的文本内容和链接
- `{timestamp}_highspot_js_data.json` - 从JavaScript提取的数据

## 自定义选择器

如果网站结构发生变化，您可能需要调整以下部分：

1. 在`crawl_content`方法中的选择器：
   ```python
   await page.wait_for_selector("main article", timeout=10000)
   ```

2. 在提取文本内容时的选择器：
   ```python
   main_content = soup.select("main article")
   ```

## 注意事项

- Cookie可能会过期，需要定期更新
- 网站结构可能会变化，需要调整选择器
- 爬取频率过高可能会被网站封禁
