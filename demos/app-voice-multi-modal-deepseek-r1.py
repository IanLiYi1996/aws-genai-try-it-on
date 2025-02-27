import gradio as gr
import torch
from transformers import (
    AutoProcessor, 
    LlavaForConditionalGeneration, 
    WhisperProcessor,
    WhisperForConditionalGeneration
)
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan, SpeechT5FeatureExtractor
from PIL import Image
import numpy as np
import io
from pydub import AudioSegment
from dotenv import load_dotenv
from datasets import load_dataset
import os
import torchaudio
from speechbrain.pretrained import EncoderClassifier
import re
import inflect

load_dotenv()

# 初始化语音识别模型
asr_model_id = "openai/whisper-medium"
asr_processor = WhisperProcessor.from_pretrained(asr_model_id)
asr_model = WhisperForConditionalGeneration.from_pretrained(asr_model_id).to("cuda")
asr_model.config.forced_decoder_ids = asr_processor.get_decoder_prompt_ids(language="chinese", task="transcribe")

# 初始化多模态对话模型和处理器
model_id = "/home/ubuntu/Align-DS-V/"
model = LlavaForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True,
).to("cuda")
processor = AutoProcessor.from_pretrained(model_id)

# 初始化多语言语音合成模型
processor_tts = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
model_tts = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts").to("cuda")
vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan").to("cuda")

# 加载声音相似度嵌入向量（可选）
embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
speaker_embeddings = torch.tensor(embeddings_dataset[7306]["xvector"]).unsqueeze(0).to("cuda")

# 初始化说话人识别模型
spk_model_name = "speechbrain/spkrec-xvect-voxceleb"
speaker_model = EncoderClassifier.from_hparams(
    source=spk_model_name, 
    run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"}, 
    savedir=os.path.join("./tmp", spk_model_name)
)

def audio_to_text(audio):
    # 检查音频输入是否为空
    if audio is None:
        return "请先录制音频"
    
    # 将音频转换为正确的采样率
    sample_rate = audio[0]
    audio_data = audio[1]
    
    # 确保音频是单声道的
    if len(audio_data.shape) > 1:
        audio_data = np.mean(audio_data, axis=0)
    
    # 将音频数据转换为float32格式，并归一化到[-1, 1]范围
    if audio_data.dtype == np.int16:
        audio_data = audio_data.astype(np.float32) / 32768.0
    
    # 重采样到16kHz
    if sample_rate != 16000:
        # 计算重采样比例
        resample_ratio = 16000 / sample_rate
        new_length = int(len(audio_data) * resample_ratio)
        audio_data = np.interp(
            np.linspace(0, len(audio_data)-1, new_length),
            np.arange(len(audio_data)),
            audio_data
        )
    
    # 准备模型输入
    inputs = asr_processor(
        audio_data,
        sampling_rate=16000,  # 固定使用16kHz采样率
        return_tensors="pt"
    ).to("cuda")
    
    # 生成转录
    with torch.no_grad():
        predicted_ids = asr_model.generate(**inputs)
    transcription = asr_processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    
    return transcription

def extract_assistant_response(response):
    # 检查输入是否为空或无效
    if not response or not isinstance(response, list) or not response[0]:
        return ""
    
    # 获取对话内容
    conversation = response[0]
    
    # 查找Assistant回复的起始和结束位置
    assistant_start = conversation.find("<｜Assistant｜>")
    
    # 如果找不到Assistant标记，返回空字符串
    if assistant_start == -1:
        return ""
    
    # 提取Assistant的回复（去掉标记）
    assistant_response = conversation[assistant_start + len("<｜Assistant｜>"):]
    
    return assistant_response.strip()

def extract_thinking_process(response):
    # 检查输入是否为空或无效
    if not response or not isinstance(response, str):
        return ""
    
    # 查找思考过程的起始和结束位置
    think_start = response.find("<think>")
    think_end = response.find("</think>")
    
    # 如果找不到think标记，返回空字符串
    if think_start == -1 or think_end == -1:
        return ""
    
    # 提取思考过程（去掉标记）
    thinking_process = response[think_start + len("<think>"):think_end]
    
    return thinking_process.strip()

def extract_speaker_embedding(audio_file):
    """从上传的音频文件中提取说话人特征向量"""
    try:
        # 加载音频文件
        if isinstance(audio_file, tuple):
            sample_rate, waveform = audio_file
            waveform = torch.tensor(waveform)
        else:
            waveform, sample_rate = torchaudio.load(audio_file)
        
        # 确保音频是单声道的
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0)
        
        # 重采样到16kHz（如果需要）
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)
        
        # 确保波形是 [batch, time] 格式
        if len(waveform.shape) == 1:
            waveform = waveform.unsqueeze(0)
        
        # 将波形移到正确的设备上
        waveform = waveform.to(speaker_model.device)
        
        # 使用SpeechBrain提取说话人嵌入
        with torch.no_grad():
            speaker_embeddings = speaker_model.encode_batch(waveform)
            speaker_embeddings = torch.nn.functional.normalize(speaker_embeddings, dim=2)
            speaker_embeddings = speaker_embeddings.squeeze(1).to("cuda")
        
        return speaker_embeddings
    except Exception as e:
        print(f"提取说话人特征时出错: {str(e)}")
        return None

def number_to_english_words(text):
    """将文本中的数字转换为英文单词"""
    
    p = inflect.engine()
    
    def replace_match(match):
        return p.number_to_words(int(match.group()))  # 将匹配到的数字转换成英文
    
    return re.sub(r'\d+', replace_match, text)  # 查找并替换所有数字

def process_input(audio, image, text_input, custom_voice=None):
    # 输入验证
    if image is None:
        return "请先上传图片", "请先上传图片后再开始对话", "", None
    
    # 获取输入文本（优先使用语音输入）
    if audio is not None:
        text = audio_to_text(audio)
    elif text_input.strip():
        text = text_input.strip()
    else:
        return "请输入文本或录制语音", "请提供输入后再开始对话", "", None
        
    # 准备模型输入
    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image"},
            ],
        },
    ]
    prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
    
    # 处理图像和文本
    inputs = processor(images=Image.open(image), text=prompt, return_tensors='pt').to("cuda", torch.float16)
    output = model.generate(**inputs, max_new_tokens=4096, do_sample=False)
    response_text = processor.decode(output[0], skip_special_tokens=True)
    
    # 提取思考过程和Assistant的回复
    thinking_process = extract_thinking_process(response_text)
    assistant_response = extract_assistant_response([response_text])
    
    # 文本转语音使用处理后的回复
    final_response = assistant_response.replace(f"<think>{thinking_process}</think>", "").strip()
    
    # 将数字转换为英文单词
    final_response = number_to_english_words(final_response)
    final_response = final_response.replace("-", " ")
    
    inputs = processor_tts(text=final_response, return_tensors="pt", padding=True, truncation=True, max_length=550).to("cuda")
    
    try:
        # 使用自定义音色或默认音色
        current_speaker_embeddings = extract_speaker_embedding(custom_voice) if custom_voice is not None else speaker_embeddings
        
        if current_speaker_embeddings is None:
            current_speaker_embeddings = speaker_embeddings
            
        speech = model_tts.generate_speech(inputs["input_ids"], current_speaker_embeddings, vocoder=vocoder)
        speech = speech.cpu().numpy()
        
        # 确保音频数据是有效的
        if np.isnan(speech).any() or np.isinf(speech).any():
            raise ValueError("生成的音频数据包含无效值")
            
        # 标准化音频数据
        if speech.size > 0:
            speech = speech / np.max(np.abs(speech))
        
    except Exception as e:
        print(f"语音生成出错: {str(e)}")
        sample_rate = 24000
        duration = 1
        speech = np.zeros(sample_rate * duration)
    
    return text, final_response, thinking_process, (16000, speech)

with gr.Blocks(theme=gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="indigo",
    neutral_hue="slate",
    spacing_size="sm",
    radius_size="lg",
    font=["Source Sans Pro", "ui-sans-serif", "system-ui"]
)) as demo:
    gr.Markdown("""
    # 🤖 R1-Jarvis: 智能视觉对话助手

    欢迎使用基于Deepseek-R1的多模态视觉问答系统！

    ## ✨ 功能特点
    - 支持语音输入/文本输入
    - 智能图像问答
    - 支持文本/自定义音色语音回复
    - 支持多语言对话/R1深度思考
    - Supported By DeepSeek-R1-Distill Models

    ## ✨ Todo
    - 流式实时对话
    - 虚拟人物对话
    """)

    with gr.Row():
        with gr.Column(scale=1):
            image_input = gr.Image(
                type="filepath",
                label="📷 上传图片",
                elem_id="image-input",
                height=300
            )

        with gr.Column(scale=1):
            with gr.Tab("🎤 语音输入"):
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="numpy",
                    label="录制语音",
                    elem_id="audio-input"
                )
            
            with gr.Tab("⌨️ 文本输入"):
                text_input = gr.Textbox(
                    label="输入文字",
                    placeholder="在此输入您的问题...",
                    lines=3
                )

            with gr.Tab("🎵 自定义音色"):
                custom_voice_input = gr.Audio(
                    label="上传音频文件（可选）",
                    type="filepath",
                    elem_id="custom-voice-input"
                )
                gr.Markdown("""
                #### 音色设置说明
                - 上传一段清晰的语音来自定义AI回复的音色
                - 建议使用5-10秒的清晰语音
                - 如果不上传则使用默认音色
                """)

            submit_btn = gr.Button("🚀 开始对话", variant="primary", scale=1)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 📝 输入识别结果")
            text_output = gr.Textbox(
                label="识别的文本",
                elem_id="text-output",
                lines=2
            )

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🤔 R1分析过程")
            thinking_output = gr.Textbox(
                label="思考过程",
                elem_id="thinking-output",
                lines=4
            )

        with gr.Column():
            gr.Markdown("### 💡 R1最终回复")
            response_output = gr.Textbox(
                label="回复内容",
                elem_id="response-output",
                lines=4
            )

    with gr.Row():
        gr.Markdown("### 🔊 语音回复")
        audio_output = gr.Audio(
            label="AI语音",
            type="numpy",
            elem_id="audio-output"
        )

    submit_btn.click(
        process_input,
        inputs=[audio_input, image_input, text_input, custom_voice_input],
        outputs=[text_output, response_output, thinking_output, audio_output]
    )

if __name__ == "__main__":
    demo.launch()
