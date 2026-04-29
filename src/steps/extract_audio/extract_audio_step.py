#!/usr/bin/env python3
# extract_audio.py
import json
import os
import sys
import subprocess
from typing import Optional
from ..base_step import BaseStep
from ..context import TaskContext
from ..util import get_video_duration
from .audio_codec import AudioExtractor, AudioCodecDetector

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
    """音频提取步骤，使用智能编码检测和流复制提取"""
    
    @property
    def step_name(self): return "音频提取"

    def __init__(self):
        super().__init__()
        self.audio_extractor = AudioExtractor()

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        # 使用TaskContext中的修剪时间
        start_time = context.trim_start_time
        end_time = context.trim_end_time
        duration = end_time - start_time if end_time > 0 else 0.0

        # 先尝试根据语言找到对应的音轨
        audio_stream_index = find_audio_stream_by_language(
            task.video_path, 
            task.subtitle.subtitle_lang
        )
        
        if audio_stream_index < 0:
            context.error_msg = "未找到匹配的音轨"
            return False
        
        # 使用智能提取器提取音频
        audio_path = self.audio_extractor.extract_audio(
            task.video_path,
            context.audio_dir,
            audio_stream_index,
            start_time,
            duration
        )
        
        if audio_path:
            context.audio_path = audio_path
            return True
        context.error_msg = "音频提取失败"
        return False

# ===================== 辅助函数 =====================

def find_audio_stream_by_language(video_path: str, language: str) -> int:
    """
    根据给定的语言缩写，智能匹配并找到对应的音轨索引
    
    :param video_path: 视频文件路径
    :param language: 语言代码（如 'en', 'zh', 'ja' 等）
    :return: 音轨索引，如果找不到返回-1
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
        
    # 遍历音轨匹配语言
    for idx, stream in enumerate(streams):
        tags = stream.get('tags', {})
        lang_tag = tags.get('language', '').lower()
        title_tag = tags.get('title', '').lower()
        
        # 匹配逻辑：音轨的language或者title包含目标语言的值
        if any(tl in lang_tag for tl in target_langs) or any(tl in title_tag for tl in target_langs):
            matched_info = f"索引: {idx}, 语言标签: '{lang_tag}', 标题: '{title_tag}'"
            print(f"✅ 匹配到语言音轨 -> {matched_info}")
            return idx
            
    print(f"⚠️ 未找到匹配语言 [{language}] 的音轨，使用默认音轨 0")
    return 0  # 默认返回第一个音轨


def extract_audio_acc_language(
    video_path: str,
    output_dir: str,
    language: str,
    start_time: float = 0.0,
    duration: float = 0.0
) -> Optional[str]:
    """
    根据给定的语言缩写，智能提取对应的音轨（保留向后兼容）
    
    :param video_path: 视频文件路径
    :param output_dir: 输出目录
    :param language: 语言代码
    :param start_time: 提取开始时间（秒）
    :param duration: 提取时长（秒），0表示提取到末尾
    :return: 生成的音频文件路径，失败返回None
    """
    audio_stream_index = find_audio_stream_by_language(video_path, language)
    
    if audio_stream_index < 0:
        return None
    
    extractor = AudioExtractor()
    return extractor.extract_audio(video_path, output_dir, audio_stream_index, start_time, duration)


def extract_audio(
    video_path: str,
    output_dir: str,
    audio_stream_index: int = 0,
    start_time: float = 0.0,
    duration: float = 0.0
) -> Optional[str]:
    """
    智能提取指定音轨的音频，根据编码自动选择格式（保留向后兼容）
    
    :param video_path: 视频文件路径
    :param output_dir: 音频输出目录
    :param audio_stream_index: 音频轨道索引（默认0）
    :param start_time: 提取开始时间（秒）
    :param duration: 提取时长（秒），0表示提取到末尾
    :return: 生成的音频文件路径，失败返回None
    """
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在 {video_path}")
        return None
    
    extractor = AudioExtractor()
    return extractor.extract_audio(video_path, output_dir, audio_stream_index, start_time, duration)
