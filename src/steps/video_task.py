# video_task.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Trim:
    """视频裁剪配置"""
    cut_front_seconds: float = 0.0
    cut_back_seconds: float = 0.0
    begin_chapter: str = ""  # 开始章节名称
    end_chapter: str = ""    # 结束章节名称

@dataclass
class Subtitle:
    """字幕相关配置"""
    subtitle_lang: str

@dataclass
class Thumbnail:
    """缩略图配置"""
    pic_path: str = ""
    blur_sigma: float = 0.0

@dataclass
class VideoTask:
    """视频任务数据类，保存单个视频的解析结果（支持扩展新字段）"""
    video_path: str          # 视频文件完整路径
    trim: Optional[Trim] = None  # 裁剪配置，可选
    subtitle: Optional[Subtitle] = None  # 字幕配置，可选
    thumbnail: Thumbnail = field(default_factory=Thumbnail)  # 缩略图配置