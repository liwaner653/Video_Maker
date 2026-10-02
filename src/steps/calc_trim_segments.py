#!/usr/bin/env python3
# calc_trim_segments.py
"""
计算视频剪辑分段
开始时间: cut_front_seconds 或 start_chapter_name
结束时间: last_seconds、end_chapter_name 或 cut_back_seconds
未指定结束时间时，以下一 part 的开始时间为结束；最后一 part 用视频时长
"""
import json
from .base_step import BaseStep
from .context import TaskContext, TrimSegment
from .util import get_video_duration, get_video_chapters


def _resolve_start_time(part, chapters: dict, default: float) -> float:
    """确定分段开始时间，生效顺序: cut_front_seconds > start_chapter_name > default"""
    if part.cut_front_seconds is not None:
        return part.cut_front_seconds
    if part.start_chapter_name:
        if part.start_chapter_name in chapters:
            return chapters[part.start_chapter_name]["start_time"]
        print(f"⚠️ 开始章节不存在: {part.start_chapter_name}，使用默认开始时间 {default:.2f}s")
    return default


def _resolve_end_time(part, start_time: float, chapters: dict,
                      video_duration: float, default: float) -> float:
    """确定分段结束时间，生效顺序: last_seconds > end_chapter_name > cut_back_seconds > default"""
    if part.last_seconds is not None and part.last_seconds > 0:
        return start_time + part.last_seconds
    if part.end_chapter_name:
        if part.end_chapter_name in chapters:
            return chapters[part.end_chapter_name]["end_time"]
        print(f"⚠️ 结束章节不存在: {part.end_chapter_name}，使用默认结束时间 {default:.2f}s")
    if part.cut_back_seconds is not None:
        return video_duration - part.cut_back_seconds
    return default


def _resolve_audio_offset(part, chapters: dict) -> float:
    """音频偏移量: audio_offset_chapter_start_time 指向章节的 start_time"""
    chapter_name = part.audio_offset_chapter_start_time
    if chapter_name:
        if chapter_name in chapters:
            return chapters[chapter_name]["start_time"]
        print(f"⚠️ 音频偏移章节不存在: {chapter_name}，偏移按 0 处理")
    return 0.0


def calculate_trim_segments(context: TaskContext) -> bool:
    """
    计算所有分段的trim时间
    每个 VideoPart 对应一个分段（时间无效则跳过）
    """
    task = context.task
    video_path = task.video_path
    video_duration = get_video_duration(video_path)

    if video_duration <= 0:
        print(f"❌ 无法获取视频时长")
        return False

    context.trim_segments = []

    if not task.parts:
        context.trim_segments.append(TrimSegment(
            start_time=0.0,
            end_time=video_duration,
            thumbnail=True,
            srt=True,
            audio=True,
            offset=0.0
        ))
        return True

    is_mkv = video_path.lower().endswith('.mkv')
    chapters = get_video_chapters(video_path) if is_mkv else {}

    prev_end = 0.0  # 上一分段的结束时间，作为当前 part 未指定开始时间时的默认值
    for i, part in enumerate(task.parts):
        start_time = _resolve_start_time(part, chapters, default=prev_end)

        # 未指定结束时间时的默认值：下一 part 的开始时间；最后一 part 用视频时长
        if i + 1 < len(task.parts):
            default_end = _resolve_start_time(task.parts[i + 1], chapters, default=video_duration)
        else:
            default_end = video_duration

        end_time = _resolve_end_time(part, start_time, chapters, video_duration, default=default_end)
        end_time = min(end_time, video_duration)

        if start_time < end_time:
            context.trim_segments.append(TrimSegment(
                start_time=start_time,
                end_time=end_time,
                thumbnail=part.thumbnail,
                srt=part.srt,
                audio=part.audio,
                offset=_resolve_audio_offset(part, chapters)
            ))
        else:
            print(f"⚠️ 分段 {i + 1} 无效（start={start_time:.2f}s >= end={end_time:.2f}s），已跳过")

        prev_end = end_time

    total_duration = sum(s.end_time - s.start_time for s in context.trim_segments)
    print(f"✅ 生成了 {len(context.trim_segments)} 个分段，总时长 {total_duration:.2f}s")
    
    for i, seg in enumerate(context.trim_segments, 1):
        duration = seg.end_time - seg.start_time
        print(f"   分段 {i}: [{seg.start_time:.2f}s -> {seg.end_time:.2f}s] 时长={duration:.2f}s thumbnail={seg.thumbnail} srt={seg.srt} audio={seg.audio} offset={seg.offset:.2f}s")

    segments_json = json.dumps([seg.to_json() for seg in context.trim_segments], indent=2, ensure_ascii=False)
    print(f"📋 分段 JSON:\n{segments_json}")

    return True


class TrimSegmentsStep(BaseStep):
    """计算视频剪辑分段时间的步骤"""

    @property
    def step_name(self):
        return "计算剪辑分段"

    def execute(self, context: TaskContext) -> bool:
        """执行剪辑分段计算"""
        try:
            if calculate_trim_segments(context):
                return True
            else:
                context.error_msg = "剪辑分段计算失败"
                return False
        except Exception as e:
            context.error_msg = f"剪辑分段计算异常: {e}"
            print(f"❌ {context.error_msg}")
            return False
