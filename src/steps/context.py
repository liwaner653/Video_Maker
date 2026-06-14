from dataclasses import dataclass, field
from typing import List, Optional

# ===================== 1. 数据结构 (Context) =====================
@dataclass
class TrimSegment:
    start_time: float
    end_time: float
    thumbnail: bool
    srt: bool
    audio: bool
    srt_path: str = ""  # 该片段的字幕文件路径
    offset: float = 0.0  # 音频偏移量，剪辑音频时需要减去该值

    def to_json(self) -> dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "thumbnail": self.thumbnail,
            "srt": self.srt,
            "audio": self.audio,
            "srt_path": self.srt_path,
            "offset": self.offset
        }


@dataclass
class TaskContext:
    """单个视频任务的上下文"""
    task: any
    video_name: str
    lang: str = "und"  # 语言标识

    thumb_dir: str = ""
    audio_dir: str = ""
    subtitle_dir: str = ""
    final_video_dir: str = ""

    thumb_path: str = ""
    audio_path: str = ""
    srt_path: str = ""
    trimmed_video_path: str = ""  # 裁剪后的视频路径
    final_video_path: str = ""

    srt_stream_index: int = -1  # SRT字幕轨道索引，-1表示未设置

    trim_segments: List[TrimSegment] = field(default_factory=list)
    
    status: bool = True
    error_msg: str = ""


@dataclass
class BatchContext:
    """全局批处理上下文"""
    json_path: str
    task_contexts: List[TaskContext] = field(default_factory=list)
    status: bool = True