from dataclasses import dataclass, field
from typing import List

# ===================== 1. 数据结构 (Context) =====================
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
    final_video_path: str = ""
    
    srt_stream_index: int = -1  # SRT字幕轨道索引，-1表示未设置
    
    trim_start_time: float = 0.0  # 视频剪辑开始时间（秒）
    trim_end_time: float = 0.0    # 视频剪辑结束时间（秒）
    
    status: bool = True
    error_msg: str = ""

@dataclass
class BatchContext:
    """全局批处理上下文"""
    json_path: str
    task_contexts: List[TaskContext] = field(default_factory=list)
    status: bool = True