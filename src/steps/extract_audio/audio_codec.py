#!/usr/bin/env python3
# audio_codec.py
"""
音频编码处理模块
提供OOP的方式来检测、处理和提取不同格式的音频
"""

import json
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class AudioCodecInfo:
    """音频编码信息"""
    codec_name: str  # ffmpeg中的编码名称 (aac, ac3, eac3, mp3, flac等)
    codec_long_name: str  # 完整编码名称
    channels: int  # 声道数
    sample_rate: int  # 采样率
    bit_rate: Optional[str]  # 比特率
    language: str = "und"  # 语言标识
    title: str = ""  # 音轨标题


class AudioCodecHandler(ABC):
    """音频编码处理器的抽象基类"""
    
    @property
    @abstractmethod
    def codec_name(self) -> str:
        """该处理器支持的编码名称"""
        pass
    
    @property
    @abstractmethod
    def output_extension(self) -> str:
        """输出文件扩展名"""
        pass
    
    @abstractmethod
    def get_ffmpeg_codec_args(self) -> list:
        """获取ffmpeg编码参数，使用流复制"""
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(codec={self.codec_name}, ext={self.output_extension})"


class AACCodecHandler(AudioCodecHandler):
    """AAC编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "aac"
    
    @property
    def output_extension(self) -> str:
        return ".aac"
    
    def get_ffmpeg_codec_args(self) -> list:
        """使用流复制，不重新编码"""
        return ["-acodec", "copy"]


class AC3CodecHandler(AudioCodecHandler):
    """AC-3编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "ac3"
    
    @property
    def output_extension(self) -> str:
        return ".ac3"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class EAC3CodecHandler(AudioCodecHandler):
    """E-AC-3编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "eac3"
    
    @property
    def output_extension(self) -> str:
        return ".eac3"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class MP3CodecHandler(AudioCodecHandler):
    """MP3编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "mp3"
    
    @property
    def output_extension(self) -> str:
        return ".mp3"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class FLACCodecHandler(AudioCodecHandler):
    """FLAC编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "flac"
    
    @property
    def output_extension(self) -> str:
        return ".flac"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class DTSCodecHandler(AudioCodecHandler):
    """DTS编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "dts"
    
    @property
    def output_extension(self) -> str:
        return ".dts"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class OpusCodecHandler(AudioCodecHandler):
    """Opus编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "opus"
    
    @property
    def output_extension(self) -> str:
        return ".opus"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class VorbisCodecHandler(AudioCodecHandler):
    """Vorbis编码处理器"""
    
    @property
    def codec_name(self) -> str:
        return "vorbis"
    
    @property
    def output_extension(self) -> str:
        return ".ogg"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "copy"]


class TrueHDCodecHandler(AudioCodecHandler):
    """TrueHD编码处理器（Dolby TrueHD无损音频）"""
    
    @property
    def codec_name(self) -> str:
        return "truehd"
    
    @property
    def output_extension(self) -> str:
        return ".aac"
    
    def get_ffmpeg_codec_args(self) -> list:
        return ["-acodec", "aac"]


class AudioCodecRegistry:
    """音频编码处理器注册表，管理所有支持的编码"""
    
    def __init__(self):
        self._handlers: Dict[str, AudioCodecHandler] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认的编码处理器"""
        handlers = [
            AACCodecHandler(),
            AC3CodecHandler(),
            EAC3CodecHandler(),
            MP3CodecHandler(),
            FLACCodecHandler(),
            DTSCodecHandler(),
            OpusCodecHandler(),
            VorbisCodecHandler(),
            TrueHDCodecHandler(),
        ]
        for handler in handlers:
            self.register(handler)
    
    def register(self, handler: AudioCodecHandler):
        """注册一个编码处理器"""
        self._handlers[handler.codec_name.lower()] = handler
    
    def get_handler(self, codec_name: str) -> Optional[AudioCodecHandler]:
        """根据编码名称获取处理器"""
        return self._handlers.get(codec_name.lower())
    
    def get_output_extension(self, codec_name: str) -> str:
        """根据编码名称获取输出文件扩展名"""
        handler = self.get_handler(codec_name)
        if handler:
            return handler.output_extension
        # 如果没有找到处理器，返回编码名称作为扩展名
        return f".{codec_name.lower()}"
    
    def get_supported_codecs(self) -> list:
        """获取所有支持的编码列表"""
        return list(self._handlers.keys())


class AudioCodecDetector:
    """音频编码检测器，检查视频中指定音轨的编码信息"""
    
    @staticmethod
    def detect_audio_codec(video_path: str, audio_stream_index: int = 0) -> Optional[AudioCodecInfo]:
        """
        检测视频中指定音轨的编码信息
        
        :param video_path: 视频文件路径
        :param audio_stream_index: 音频轨道索引
        :return: 音频编码信息，失败返回None
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", f"a:{audio_stream_index}",
            "-show_entries", "stream=codec_name,codec_long_name,channels,sample_rate,bit_rate:stream_tags=language,title",
            "-of", "json", video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            
            if not streams:
                print(f"⚠️ 未找到音频轨道 {audio_stream_index}")
                return None
            
            stream = streams[0]
            tags = stream.get('tags', {})
            
            codec_info = AudioCodecInfo(
                codec_name=stream.get('codec_name', 'unknown'),
                codec_long_name=stream.get('codec_long_name', 'Unknown Codec'),
                channels=stream.get('channels', 0),
                sample_rate=stream.get('sample_rate', 0),
                bit_rate=stream.get('bit_rate'),
                language=tags.get('language', 'und'),
                title=tags.get('title', '')
            )
            
            return codec_info
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 检测音频编码失败: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ 解析ffprobe输出失败: {e}")
            return None
        except Exception as e:
            print(f"❌ 未知错误: {e}")
            return None


class AudioExtractor:
    """音频提取器，使用OOP方式提取音频"""
    
    def __init__(self):
        self.codec_registry = AudioCodecRegistry()
        self.codec_detector = AudioCodecDetector()
    
    def extract_audio(
        self,
        video_path: str,
        output_dir: str,
        audio_stream_index: int = 0,
        start_time: float = 0.0,
        duration: float = 0.0
    ) -> Optional[str]:
        """
        智能提取音频，根据编码自动选择输出格式和处理方式
        
        :param video_path: 视频文件路径
        :param output_dir: 输出目录
        :param audio_stream_index: 音频轨道索引
        :param start_time: 提取开始时间（秒）
        :param duration: 提取时长（秒），0表示提取到末尾
        :return: 生成的音频文件路径，失败返回None
        """
        import os
        
        if not os.path.exists(video_path):
            print(f"❌ 错误：视频文件不存在 {video_path}")
            return None
        
        # 检测音频编码
        codec_info = self.codec_detector.detect_audio_codec(video_path, audio_stream_index)
        if not codec_info:
            print(f"❌ 无法检测音频编码")
            return None
        
        # 获取对应的处理器
        handler = self.codec_registry.get_handler(codec_info.codec_name)
        if not handler:
            print(f"⚠️ 不支持的编码 {codec_info.codec_name}，将使用流复制导出为 .{codec_info.codec_name}")
            output_ext = f".{codec_info.codec_name.lower()}"
        else:
            output_ext = handler.output_extension
        
        # 打印音频信息
        print(f"✅ 检测到音频编码: {codec_info.codec_name} ({codec_info.codec_long_name})")
        print(f"   声道数: {codec_info.channels}, 采样率: {codec_info.sample_rate} Hz")
        if codec_info.language:
            print(f"   语言: {codec_info.language}, 标题: {codec_info.title}")
        
        # 生成输出文件路径
        os.makedirs(output_dir, exist_ok=True)
        video_name = os.path.basename(video_path)
        audio_name = os.path.splitext(video_name)[0] + output_ext
        audio_path = os.path.join(output_dir, audio_name)
        
        # 构建ffmpeg命令
        command = ["ffmpeg"]
        
        if start_time > 0:
            command.extend(["-ss", str(start_time)])
        
        command.extend(["-i", video_path])
        command.extend(["-map", f"0:a:{audio_stream_index}"])
        command.extend(["-vn"])  # 不处理视频流
        
        # 获取编码参数
        if handler:
            command.extend(handler.get_ffmpeg_codec_args())
        else:
            # 不支持的编码，使用流复制
            command.extend(["-acodec", "copy"])
        
        if duration > 0:
            command.extend(["-t", str(duration)])
        
        command.extend(["-y", audio_path])
        
        print(f"开始提取音频（轨道{audio_stream_index}）: {video_name}")
        print(f"输出格式: {output_ext}")
        
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"✅ 音频提取完成: {audio_path}")
            return audio_path
        except subprocess.CalledProcessError as e:
            print(f"❌ 音频提取失败: {e.stderr}")
            return None
