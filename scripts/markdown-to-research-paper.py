import markdown
from PIL import Image, ImageDraw, ImageFont
import io
import re
import textwrap
from bs4 import BeautifulSoup

def markdown_to_research_paper_image(markdown_text, output_file="research_paper.png", width=1000, bg_color=(255, 255, 255)):
    # 转换Markdown为HTML
    html = markdown.markdown(markdown_text)
    soup = BeautifulSoup(html, 'html.parser')
    
    # 设置字体（请确保这些字体文件在您的系统上可用，或提供自定义字体路径）
    try:
        title_font = ImageFont.truetype("simhei.ttf", 36)
        subtitle_font = ImageFont.truetype("simsun.ttf", 24)
        author_font = ImageFont.truetype("simsun.ttf", 18)
        header_font = ImageFont.truetype("simhei.ttf", 28)
        content_font = ImageFont.truetype("simsun.ttf", 20)
    except IOError:
        # 如果找不到指定字体，使用默认字体
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        author_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        content_font = ImageFont.load_default()
    
    # 创建空白图像
    height = 1500  # 初始高度，将根据内容动态调整
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # 颜色定义
    header_bg_color = (200, 255, 230)  # 浅绿色背景
    section_bg_color = (30, 100, 200)  # 蓝色区块背景
    text_color = (0, 0, 0)  # 黑色文本
    section_text_color = (255, 255, 255)  # 白色区块文本
    
    y_offset = 0
    
    # 绘制标题区域（绿色背景）
    header_height = 180
    draw.rectangle([(0, y_offset), (width, y_offset + header_height)], fill=header_bg_color)
    
    # 查找标题、副标题和作者
    title = soup.find('h1').text if soup.find('h1') else "研究论文标题"
    draw.text((50, y_offset + 20), title, font=title_font, fill=text_color)
    
    # 查找副标题（假设在第一个和第二个h1之间的文本是副标题）
    paragraphs = soup.find_all('p')
    if paragraphs:
        subtitle = paragraphs[0].text
        draw.text((50, y_offset + 80), subtitle, font=subtitle_font, fill=text_color)
    
    # 查找作者信息（假设在第一个p标签之后的斜体或第二个p标签是作者信息）
    italics = soup.find('em')
    if italics:
        authors = italics.text
        draw.text((50, y_offset + 130), authors, font=author_font, fill=text_color)
    elif len(paragraphs) > 1:
        authors = paragraphs[1].text
        draw.text((50, y_offset + 130), authors, font=author_font, fill=text_color)
    
    y_offset += header_height + 20
    
    # 处理每个部分（h2标题）
    sections = soup.find_all('h2')
    for section in sections:
        section_title = section.text
        
        # 绘制部分标题背景
        draw.rectangle([(20, y_offset), (width - 20, y_offset + 50)], fill=section_bg_color)
        draw.text((40, y_offset + 10), section_title, font=header_font, fill=section_text_color)
        
        y_offset += 70
        
        # 获取此部分内容（在下一个h2之前的所有内容）
        content = []
        next_node = section.next_sibling
        
        while next_node and next_node.name != 'h2':
            if next_node.name in ['p', 'ol', 'ul']:
                if next_node.name == 'ol':
                    for i, li in enumerate(next_node.find_all('li')):
                        content.append(f"{i+1}. {li.text}")
                elif next_node.name == 'ul':
                    for li in next_node.find_all('li'):
                        content.append(f"• {li.text}")
                else:
                    content.append(next_node.text)
            next_node = next_node.next_sibling
        
        # 绘制内容
        for paragraph in content:
            # 文本换行处理
            wrapped_text = textwrap.fill(paragraph, width=80)
            lines = wrapped_text.split('\n')
            
            for line in lines:
                if y_offset >= height - 100:  # 如果接近图像底部，增加图像高度
                    new_height = height + 500
                    new_img = Image.new('RGB', (width, new_height), bg_color)
                    new_img.paste(img, (0, 0))
                    img = new_img
                    draw = ImageDraw.Draw(img)
                    height = new_height
                
                draw.text((40, y_offset), line, font=content_font, fill=text_color)
                y_offset += 30
            
            y_offset += 20  # 段落间距
    
    # 裁剪图像至实际内容高度
    img = img.crop((0, 0, width, y_offset + 50))
    
    # 保存图像
    img.save(output_file)
    print(f"已生成研究论文图像: {output_file}")
    return output_file

# 示例用法
if __name__ == "__main__":
    sample_markdown = """
# Chain-of-Retrieval Augmented Generation

Training x1-like RAG models that retrieve and reason over relevant information step by step before generating the final answer.

*Liang Wang, Microsoft | Haonan Chen | Nan Yang | Xiaolong Huang | Zhicheng Dou | Furu Wei*

## 研究背景
1. 研究问题：如何训练类似RAG（Retrieval-Augmented Generation）模型，使其能够在生成最终答案之前逐步检索和推理相关信息。
2. 研究难点：如何生成高质量的中间检索查询，如何有效地生成中间检索结果以增强现有RAG数据集。
3. 相关工作：FLARE, ITER-RETGEN, IRCoT, Self-RAG, Auto-RAG等方法。

## 研究方法
本文提出了CoRAG（Chain-of-Retrieval Augmented Generation）框架用于解决RAG模型在处理复杂查询时的局限性：

1. 检索链生成：通过拒绝采样自动生成检索链，每个采样链由一系列子查询和对应的子答案组成。
2. 模型训练：多任务学习方法，包括查询预测、子答案预测和最终答案预测。

## 实验设计
1. 数据和评估：使用多个标准数据集进行评估，包括问答数据集和推理数据集。
2. 对比模型：与现有RAG模型进行全面数据测试，训练两个主要模型。

## 结果与分析
1. 主要发现：CoRAG在多个任务中优于基线模型，特别是在复杂推理任务中。
2. 性能分析：检索链长度对性能有显著影响，但需要平衡效率。
3. 消融实验：验证了各组件的必要性。

## 总体结论
CoRAG框架通过逐步检索和推理，显著提升了RAG模型在处理复杂查询时的能力。本研究为未来改进RAG技术提供了新的研究方向。
    """
    
    markdown_to_research_paper_image(sample_markdown, "research_paper_example.png")
