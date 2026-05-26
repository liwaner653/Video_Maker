"""
视频剪辑模块
提供视频剪辑、字幕处理和字幕烧入功能
"""

from .trim_video_task import TrimVideoTask, TrimSegment, TrimAudioConfig, TrimSubtitleConfig
from .video_main import process_trim_task, load_trim_tasks, run_trim_from_json
from .generate_trim_json import generate_trim_json, generate_batch_trim_json, interactive_generate_json

__all__ = [
    'TrimVideoTask',
    'TrimSegment',
    'TrimAudioConfig',
    'TrimSubtitleConfig',
    'process_trim_task',
    'load_trim_tasks',
    'run_trim_from_json',
    'generate_trim_json',
    'generate_batch_trim_json',
    'interactive_generate_json'
]