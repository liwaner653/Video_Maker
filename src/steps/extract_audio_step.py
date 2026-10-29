#!/usr/bin/env python3
# extract_audio.py
import json
import os
import subprocess
from typing import Optional
from .base_step import BaseStep
from .context import TaskContext
from .extract_audio.audio_codec import AudioExtractor
from steps.config import LANG_MAP



class AudioStep(BaseStep):
    """音频提取步骤，使用智能编码检测和流复制提取"""
    
    @property
    def step_name(self): return "音频提取"

    def __init__(self, unify_aac: bool = False):
        super().__init__()
        self.audio_extractor = AudioExtractor()
        # video main 流水线要求音频统一为 AAC 48kHz 立体声（保证合并/拼接兼容）；
        # main 流水线只做简单提取，保持默认 False（纯流拷贝）
        self.unify_aac = unify_aac

    def execute(self, context: TaskContext) -> bool:
        task = context.task

        # 如果check_exist为True，检查输出目录中是否存在同名音频文件
        if task.audio and task.audio.check_exist:
            existing_audio = self._find_existing_audio(task.video_path, context.audio_dir)
            if existing_audio:
                print(f"✅ 检测到已存在的音频文件：{existing_audio}")
                context.audio_path = existing_audio
                return True

        # 先尝试根据语言找到对应的音轨
        audio_stream_index = task.audio.audio_stream_index if task.audio else 0
        audio_stream_index = find_audio_stream_by_language(
            task.video_path, 
            task.subtitle.subtitle_lang if task.subtitle else "en"
        )
        
        if audio_stream_index < 0:
            context.error_msg = "未找到匹配的音轨"
            return False
        
        # 提取完整音频，不进行修剪
        audio_path = self.audio_extractor.extract_audio(
            task.video_path,
            context.audio_dir,
            audio_stream_index
        )

        if audio_path and self.unify_aac:
            audio_path = self._ensure_aac(audio_path)

        if audio_path:
            context.audio_path = audio_path
            return True
        context.error_msg = "音频提取失败"
        return False

    def _ensure_aac(self, audio_path: str) -> Optional[str]:
        """确保音频为 AAC 48kHz 立体声 .m4a；不满足则转码，已是AAC则仅流拷贝换封装"""
        probe_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,sample_rate,channels",
            "-of", "json", audio_path
        ]
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            stream = json.loads(result.stdout)['streams'][0]
        except Exception as e:
            print(f"❌ 读取音频参数失败: {e}")
            return None

        root, ext = os.path.splitext(audio_path)
        target_path = root + '.m4a'
        is_aac_48k_stereo = (
            stream.get('codec_name') == 'aac'
            and int(stream.get('sample_rate', 0)) == 48000
            and stream.get('channels') == 2
        )
        if is_aac_48k_stereo and ext.lower() == '.m4a':
            return audio_path

        temp_path = root + '_aac_tmp.m4a'
        command = ['ffmpeg', '-y', '-i', audio_path, '-vn']
        if is_aac_48k_stereo:
            command.extend(['-acodec', 'copy'])  # 已是AAC，仅换封装
        else:
            command.extend(['-acodec', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2'])
        command.append(temp_path)

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            os.replace(temp_path, target_path)
            if os.path.normpath(target_path) != os.path.normpath(audio_path) and os.path.exists(audio_path):
                os.remove(audio_path)
            print(f"✅ 音频已统一为 AAC 48kHz 立体声: {target_path}")
            return target_path
        except subprocess.CalledProcessError as e:
            print(f"❌ 音频转码AAC失败: {e.stderr}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return None
        except OSError as e:
            print(f"❌ 音频文件处理失败: {e}")
            return None
    
    def _find_existing_audio(self, video_path: str, output_dir: str) -> Optional[str]:
        """
        查找输出目录中是否存在与视频文件同名的音频文件
        会尝试多种常见的音频扩展名
        
        :param video_path: 视频文件路径
        :param output_dir: 输出目录
        :return: 存在则返回完整路径，否则返回None
        """
        if not os.path.exists(output_dir):
            return None
        
        video_name = os.path.basename(video_path)
        name_no_ext = os.path.splitext(video_name)[0]
        
        if self.unify_aac:
            # 仅匹配统一转码后的 AAC 文件，旧格式（eac3/ac3等）重新提取
            audio_extensions = ['.m4a']
        else:
            # 尝试多种常见的音频扩展名
            audio_extensions = ['.aac', '.ac3', '.eac3', '.mp3', '.flac', '.wav', '.m4a', '.opus']
        
        for ext in audio_extensions:
            audio_file = os.path.join(output_dir, name_no_ext + ext)
            if os.path.isfile(audio_file):
                return audio_file
        
        return None

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
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", text=True, check=True)
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
        if any(tl in lang_tag for tl in target_langs): # or any(tl in title_tag for tl in target_langs):
            matched_info = f"索引: {idx}, 语言标签: '{lang_tag}', 标题: '{title_tag}'"
            print(f"✅ 匹配到语言音轨 -> {matched_info}")
            return idx
            
    print(f"⚠️ 未找到匹配语言 [{language}] 的音轨，使用默认音轨 0")
    return 0  # 默认返回第一个音轨


def extract_audio(
    video_path: str,
    output_dir: str,
    audio_stream_index: int = 0
) -> Optional[str]:
    """
    智能提取指定音轨的音频，根据编码自动选择格式（保留向后兼容）
    
    :param video_path: 视频文件路径
    :param output_dir: 音频输出目录
    :param audio_stream_index: 音频轨道索引（默认0）
    :return: 生成的音频文件路径，失败返回None
    """
    if not os.path.exists(video_path):
        print(f"错误：视频文件不存在 {video_path}")
        return None
    
    extractor = AudioExtractor()
    return extractor.extract_audio(video_path, output_dir, audio_stream_index)
