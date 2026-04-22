#!/usr/bin/env python3
# extract_audio.py
import json
import os
import sys
import subprocess
from steps.base_step import BaseStep
from steps.context import TaskContext
from util import get_video_duration

# 2. 语言缩写到全称映射字典
LANG_MAP = {
    'en': ['english', 'eng', 'en'],
    'de': ['german', 'ger', 'deu', 'de'],
    'zh': ['chinese', 'chi', 'zho', 'zh'],
    'ja': ['japanese', 'jpn', 'ja'],
    'fr': ['french', 'fre', 'fra', 'fr'],
    'es': ['spanish', 'spa', 'es'],
    'ru': ['russian', 'rus', 'ru']
}

class AudioStep(BaseStep):
    @property
    def step_name(self): return "音频提取"

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        cf, cb = (task.trim.cut_front_seconds, task.trim.cut_back_seconds) if task.trim else (0.0, 0.0)

        if task.subtitle and task.subtitle.subtitle_lang:
            audio_path = extract_audio_acc_language(task.video_path, context.audio_dir, task.subtitle.subtitle_lang, cf, cb)
        else:
            audio_path = extract_audio(task.video_path, context.audio_dir, task.audio.audio_stream_index, cf, cb)
        
        if audio_path:
            context.audio_path = audio_path
            return True
        context.error_msg = "音频提取失败"
        return False

# 3. 添加 extract_audio_acc_language 函数
def extract_audio_acc_language(video_path: str, output_dir: str, language: str, cut_front_seconds: float = 0.0, cut_back_seconds: float = 0.0):
    """
    根据给定的语言缩写，智能匹配并提取对应的音轨
    """
    target_langs = LANG_MAP.get(language.lower(), [language.lower()])
    
    # 获取视频的所有音轨信息
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index:stream_tags=language,title",
        "-of", "json", video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        streams = json.loads(result.stdout).get('streams', [])
    except Exception as e:
        print(f"❌ 获取视频音轨信息失败: {e}")
        return -1
        
    matched_stream_index = -1
    matched_info = ""
    
    # 遍历音轨匹配语言
    for idx, stream in enumerate(streams):
        tags = stream.get('tags', {})
        lang_tag = tags.get('language', '').lower()
        title_tag = tags.get('title', '').lower()
        
        # 匹配逻辑：音轨的language或者title包含目标语言的值
        if any(tl in lang_tag for tl in target_langs) or any(tl in title_tag for tl in target_langs):
            matched_stream_index = idx  # 相对索引，给ffmpeg -map用
            matched_info = f"索引: {idx}, 语言标签: '{lang_tag}', 标题: '{title_tag}'"
            break
            
    if matched_stream_index == -1:
        print(f"⚠️ 未找到匹配语言 [{language}] 的音轨")
        return None  # 没有符合要求的音轨
        
    # 4. print出符合条件的对应音频信息，包括索引和名称
    print(f"✅ 匹配到语言音轨 -> {matched_info}")
    
    # 取第一个执行 extract_audio 并返回生成的路径(等效于True并向后续传递参数)
    return extract_audio(video_path, output_dir, matched_stream_index, cut_front_seconds, cut_back_seconds)

def extract_audio(video_path: str, output_dir: str, audio_stream_index: int = 0, cut_front_seconds: float = 0.0, cut_back_seconds: float = 0.0):
    """
    提取视频指定音轨的音频（AAC编码）
    :param video_path: 视频文件路径
    :param output_dir: 音频输出目录
    :param audio_stream_index: 音频轨道索引（默认0）
    :param cut_front_seconds: 裁剪开头秒数（默认0，不裁剪）
    :param cut_back_seconds: 裁剪结尾秒数（默认0，不裁剪）
    :return: 生成的音频文件路径，失败返回None
    """
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在 {video_path}")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成音频文件名
    video_name = os.path.basename(video_path)
    audio_name = os.path.splitext(video_name)[0] + '.aac'
    audio_path = os.path.join(output_dir, audio_name)
    
    # 构建ffmpeg命令 (按照从左到右顺序拼接)
    command = ["ffmpeg"]
    
    # 处理开头裁剪（-ss 放在 -i 前更高效）
    if cut_front_seconds > 0:
        command.extend(["-ss", str(cut_front_seconds)])
        
    # 处理结尾裁剪
    if cut_back_seconds > 0:
        duration = get_video_duration(video_path)
        if duration > 0:
            end_time = duration - cut_back_seconds
            # 参数校验：防止开头和结尾裁剪加起来超过视频总时长
            if end_time <= cut_front_seconds:
                print(f"错误：视频总时长({duration:.2f}s) 不足以进行开头({cut_front_seconds}s)和结尾({cut_back_seconds}s)的裁剪！")
                return None
            # -to 放在 -i 之前，表示读取文件直到该时间点
            command.extend(["-to", str(end_time)])
        else:
            print("错误：无法获取视频时长，无法完成结尾裁剪。")
            return None
            
    # 追加剩余参数
    command.extend([
        "-i", video_path,
        "-map", f"0:a:{audio_stream_index}",  # 选择指定音轨
        "-vn",  # 不处理视频流
        "-acodec", "aac",  # AAC编码
        "-y",  # 覆盖已有文件
        audio_path
    ])
    
    print(f"开始提取音频：{video_name} (音轨{audio_stream_index})")
    print(f"执行命令: {' '.join(command)}")
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✅ 音频提取完成：{audio_path}")
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"❌ 音频提取失败：{e.stderr}")
        return None

# 单独运行时的命令行逻辑
if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print("使用方法：python extract_audio.py <视频文件路径> <输出目录> [音轨索引] [开头裁剪秒数] [结尾裁剪秒数]")
#         print("示例：")
#         print("  python extract_audio.py ./test.mp4 ./audio 1 5.5 3.0")
#         sys.exit(1)
#     
#     video_path = sys.argv[1]
#     output_dir = sys.argv[2]
#     audio_stream_index = int(sys.argv[3]) if len(sys.argv) >= 4 else 0
#     cut_front_seconds = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
#     cut_back_seconds = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
#     
#     extract_audio(video_path, output_dir, audio_stream_index, cut_front_seconds, cut_back_seconds)
    extract_audio('C:/Users/waner/Desktop/Trim.mp4', 
                  'C:/Users/waner/Desktop/Trim_cut.mp4', 
                  0, 0, 5)