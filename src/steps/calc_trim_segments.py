#!/usr/bin/env python3
# calc_trim_segments.py
"""
计算视频剪辑分段
Mode A (Time-based): 使用 cut_front_seconds/cut_back_seconds 生成多个分段
Mode B (Chapter-based): 使用 start_chapter_name 配合 end_chapter_name/last_seconds 生成单个分段
"""
import json
import subprocess
from .base_step import BaseStep
from .context import TaskContext, TrimSegment
from .util import get_video_duration, get_video_chapters


def calculate_trim_segments(context: TaskContext) -> bool:
    """
    计算所有分段的trim时间
    遍历 task.parts，维护一个TrimSegment上下文，逐个处理VideoPart
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

    current_segment = None

    for i, part in enumerate(task.parts):
        if current_segment is None:
            current_segment = {
                'start_time': 0.0,
                'thumbnail': part.thumbnail,
                'srt': part.srt,
                'audio': part.audio,
                'offset': 0.0
            }

        if part.cut_front_seconds is not None:
            current_segment['start_time'] = part.cut_front_seconds
        elif part.start_chapter_name and part.start_chapter_name in chapters:
            current_segment['start_time'] = chapters[part.start_chapter_name]["start_time"]

        if part.audio_offset_chapter_start_time and part.audio_offset_chapter_start_time in chapters:
            current_segment['offset'] = chapters[part.audio_offset_chapter_start_time]["start_time"]

        has_end_marker = False
        end_time = video_duration

        if part.last_seconds is not None and part.last_seconds > 0:
            end_time = current_segment['start_time'] + part.last_seconds
            has_end_marker = True
        elif part.end_chapter_name and part.end_chapter_name in chapters:
            end_time = chapters[part.end_chapter_name]["end_time"]
            has_end_marker = True

        end_time = min(end_time, video_duration)

        if has_end_marker:
            if current_segment['start_time'] < end_time:
                context.trim_segments.append(TrimSegment(
                    start_time=current_segment['start_time'],
                    end_time=end_time,
                    thumbnail=current_segment['thumbnail'],
                    srt=current_segment['srt'],
                    audio=current_segment['audio'],
                    offset=current_segment['offset']
                ))
            current_segment = None
        else:
            if i + 1 < len(task.parts):
                next_part = task.parts[i + 1]
                if next_part.start_chapter_name and next_part.start_chapter_name in chapters:
                    end_time = chapters[next_part.start_chapter_name]["start_time"]
                elif next_part.cut_front_seconds is not None:
                    end_time = next_part.cut_front_seconds

                end_time = min(end_time, video_duration)

                if current_segment['start_time'] < end_time:
                    context.trim_segments.append(TrimSegment(
                        start_time=current_segment['start_time'],
                        end_time=end_time,
                        thumbnail=current_segment['thumbnail'],
                        srt=current_segment['srt'],
                        audio=current_segment['audio'],
                        offset=current_segment['offset']
                    ))

                current_segment = {
                    'start_time': end_time,
                    'thumbnail': next_part.thumbnail,
                    'srt': next_part.srt,
                    'audio': next_part.audio,
                    'offset': 0.0
                }
            else:
                if current_segment['start_time'] < video_duration:
                    context.trim_segments.append(TrimSegment(
                        start_time=current_segment['start_time'],
                        end_time=video_duration,
                        thumbnail=current_segment['thumbnail'],
                        srt=current_segment['srt'],
                        audio=current_segment['audio'],
                        offset=current_segment['offset']
                    ))
                current_segment = None

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
