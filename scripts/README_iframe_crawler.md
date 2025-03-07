# AWS Highspot Iframe 爬虫

这是一个专门用于爬取AWS Highspot网页内容的爬虫工具，特别针对iframe中的表格内容进行处理。

## 功能特点

- 使用Playwright自动获取cookie并登录
- 支持抓取网页文字、表格等内容
- 专门处理iframe中的表格内容
- 保存结果为Markdown格式，尽可能保持原始布局
- 提供基本模式和高级模式两种爬取方式

## 安装依赖

```bash
pip install playwright beautifulsoup4
playwright install chromium
```

## 使用方法

### 1. 运行爬虫

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859
```

### 2. 命令行参数

```
usage: run_iframe_crawler.py [-h] [--mode {basic,advanced}] [--cookies COOKIES] [--output OUTPUT] [--headless] [--login] url

AWS Highspot网页爬虫，支持iframe表格抓取

positional arguments:
  url                   要爬取的网页URL

optional arguments:
  -h, --help            显示帮助信息并退出
  --mode {basic,advanced}
                        爬取模式: basic(基本模式) 或 advanced(高级模式，默认)
  --cookies COOKIES     Cookie文件路径 (默认: cookies_playwright.json)
  --output OUTPUT       输出目录 (默认: output)
  --headless            使用无头模式运行浏览器 (默认: 显示浏览器)
  --login               强制重新登录获取cookie (默认: 如果cookie文件存在则使用)
```

### 3. 爬虫模式说明

- **基本模式 (basic)**: 使用 `HighspotIframeCrawler` 类，提供基本的网页内容抓取和iframe处理功能
- **高级模式 (advanced)**: 使用 `AdvancedIframeCrawler` 类，提供更强大的iframe表格处理功能，能更好地保留原始布局

### 4. 示例

#### 首次运行（需要登录）

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859
```

系统会打开浏览器，等待您手动登录AWS Highspot，登录成功后按回车继续。

#### 使用已保存的cookie运行

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859 --mode advanced
```

#### 强制重新登录

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859 --login
```

#### 使用无头模式（不显示浏览器）

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859 --headless
```

#### 指定输出目录

```bash
python run_iframe_crawler.py https://aws.highspot.com/items/6721f0d483ce12ab121e6859 --output my_output
```

## 爬虫文件说明

- `highspot_iframe_crawler.py`: 基本爬虫实现，提供基础的网页内容抓取和iframe处理功能
- `advanced_iframe_crawler.py`: 高级爬虫实现，专门针对iframe中的表格内容进行处理，能更好地保留原始布局
- `run_iframe_crawler.py`: 主程序，提供命令行接口运行爬虫

## 输出文件

爬虫会在输出目录（默认为`output`）中生成以下文件：

- `{timestamp}_highspot.md`: Markdown格式的爬取结果
- `{timestamp}_highspot.html`: 原始HTML内容
- `{timestamp}_highspot.png`: 页面截图
- `{timestamp}_highspot_iframe_{n}.png`: 各个iframe的截图
- `{timestamp}_highspot_iframe_{n}_full.png`: 各个iframe的完整截图（高级模式）
- `{timestamp}_highspot_iframe_{n}.html`: 各个iframe的HTML内容（高级模式）

## 注意事项

1. 首次运行需要手动登录AWS Highspot，之后会保存cookie供后续使用
2. 如果cookie过期，需要使用`--login`参数重新登录
3. 默认会显示浏览器窗口，如果在服务器上运行，可以使用`--headless`参数
4. 爬虫会尝试处理所有iframe中的表格内容，但可能受到同源策略等限制
