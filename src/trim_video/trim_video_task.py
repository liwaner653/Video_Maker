from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TrimSegment:
    """视频剪辑片段配置"""
    start_time: float  # 开始时间（秒）
    end_time: float    # 结束时间（秒）
    name: str = ""     # 片段名称（可选）


@dataclass
class TrimAudioConfig:
    """音频配置"""
    language: str = ""              # 目标语言（用于自动选择音轨）
    audio_stream_index: int = -1    # 指定音轨索引（-1表示自动检测）
    enabled: bool = True            # 是否保留音频


@dataclass
class TrimSubtitleConfig:
    """字幕配置"""
    language: str = ""              # 目标语言（用于自动选择字幕轨）
    subtitle_stream_index: int = -1 # 指定字幕轨道索引（-1表示自动检测）
    burn_in: bool = True            # 是否烧入视频
    enabled: bool = True            # 是否启用字幕


@dataclass
class TrimVideoTask:
    """视频剪辑任务配置"""
    video_path: str                     # 视频文件完整路径
    output_dir: str = ""                # 输出目录（可选，默认为视频所在目录）
    segments: List[TrimSegment] = field(default_factory=list)  # 剪辑片段列表
    audio: TrimAudioConfig = field(default_factory=TrimAudioConfig)
    subtitle: TrimSubtitleConfig = field(default_factory=TrimSubtitleConfig)
    output_format: str = "mp4"          # 输出格式（mp4/mkv等）
    crf: int = 23                      # 视频质量（CRF值）
    preset: str = "medium"             # 编码预设