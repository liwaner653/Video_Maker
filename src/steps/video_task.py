# video_task.py
from dataclasses import dataclass, field
from typing import Optional, List

# Audio class kept for
@dataclass
class Audio:
    """音频相关配置"""
    audio_stream_index: int = 0
    check_exist: bool = False  # 是否检查输出目录中的同名文件是否存在

@dataclass
class Subtitle:
    """字幕相关配置"""
    subtitle_lang: str
    check_exist: bool = False  # 是否检查输出目录中的同名文件是否存在

@dataclass
class Thumbnail:
    """缩略图配置"""
    pic_path: str = ""
    blur_sigma: float = 0.0
    check_exist: bool = False  # 是否检查输出目录中的同名文件是否存在

@dataclass
class VideoPart:
    """视频分段配置（完全自包含）"""
    name: str = ""  # 可选：分段名称
    # 开始时间定义二选一：要么用cut_front_seconds，要么用start_chapter_name
    cut_front_seconds: Optional[float] = None  # 可选：从视频开头裁剪多少秒开始
    cut_back_seconds: Optional[float] = None  # 可选：从视频结尾裁剪多少秒结束
    start_chapter_name: str = ""  # 可选：从指定章节名称开始
    last_seconds: Optional[float] = None  # 可选：持续秒数（支持带帧的小数）
    end_chapter_name: Optional[str] = None  # 可选：结束于指定章节名称
    thumbnail: bool = True  # 默认true：是否生成缩略图
    srt: bool = True  # 默认true：是否生成字幕
    video: bool = True  # 默认true：是否生成分段视频

@dataclass
class FinalVideo:
    """最终视频配置"""
    check_exist: bool = False  # 如果为true，则跳过video_compose_step步骤；为false，则覆盖文件

@dataclass
class VideoTask:
    """视频任务数据类，保存单个视频的解析结果（支持扩展新字段）"""
    video_path: str          # 视频文件完整路径
    audio: Optional[Audio] = None  # 音频配置，可选
    subtitle: Optional[Subtitle] = None  # 字幕配置，可选
    thumbnail: Thumbnail = field(default_factory=Thumbnail)  # 缩略图配置
    final_video: FinalVideo = field(default_factory=FinalVideo)  # 最终视频配置
    parts: List[VideoPart] = field(default_factory=list)  # 可选：视频多段分割配置 - 新的推荐方式
