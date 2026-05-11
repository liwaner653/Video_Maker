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
from .video_task import VideoPart
from .util import get_video_duration


def get_mkv_chapters(video_path: str) -> dict:
    """
    从MKV视频中提取所有章节信息
    返回格式: {
        "chapter_name": {
            "start_time": 浮点数（秒）,
            "end_time": 浮点数（秒）
        },
        ...
    }
    """
    chapters = {}

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "chapter=start_time,end_time:chapter_tags=title",
            "-of", "json", video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)

        if "chapters" not in data:
            return chapters

        for chapter in data["chapters"]:
            start_time = float(chapter.get("start_time", 0.0))
            end_time = float(chapter.get("end_time", 0.0))
            tags = chapter.get("tags", {})
            title = tags.get("title", "")

            if title:
                chapters[title] = {
                    "start_time": start_time,
                    "end_time": end_time
                }
    except Exception as e:
        print(f"⚠️ 读取MKV章节信息失败: {e}")

    return chapters


def calculate_time_based_segments(
    part: VideoPart,
    video_duration: float
) -> list:
    """
    根据 cut_front_seconds/cut_back_seconds 生成多个分段
    - Only cut_front_seconds: [0, cut_front) + [cut_front, duration)
    - Only cut_back_seconds: [0, duration-cut_back) + [duration-cut_back, duration)
    - Both: [0, cut_front) + [cut_front, duration-cut_back) + [duration-cut_back, duration)
    """
    segments = []
    cut_front = part.cut_front_seconds if part.cut_front_seconds is not None else 0.0
    cut_back = part.cut_back_seconds if part.cut_back_seconds is not None else 0.0

    has_front = cut_front > 0
    has_back = cut_back > 0

    if has_front and has_back:
        segments.append(TrimSegment(
            start_time=0.0,
            end_time=cut_front,
            thumbnail=False,
            srt=False,
            video=False
        ))
        segments.append(TrimSegment(
            start_time=cut_front,
            end_time=video_duration - cut_back,
            thumbnail=part.thumbnail,
            srt=part.srt,
            video=part.video
        ))
        segments.append(TrimSegment(
            start_time=video_duration - cut_back,
            end_time=video_duration,
            thumbnail=False,
            srt=False,
            video=False
        ))
    elif has_front:
        segments.append(TrimSegment(
            start_time=0.0,
            end_time=cut_front,
            thumbnail=False,
            srt=False,
            video=False
        ))
        segments.append(TrimSegment(
            start_time=cut_front,
            end_time=video_duration,
            thumbnail=part.thumbnail,
            srt=part.srt,
            video=part.video
        ))
    elif has_back:
        segments.append(TrimSegment(
            start_time=0.0,
            end_time=video_duration - cut_back,
            thumbnail=part.thumbnail,
            srt=part.srt,
            video=part.video
        ))
        segments.append(TrimSegment(
            start_time=video_duration - cut_back,
            end_time=video_duration,
            thumbnail=False,
            srt=False,
            video=False
        ))
    else:
        segments.append(TrimSegment(
            start_time=0.0,
            end_time=video_duration,
            thumbnail=part.thumbnail,
            srt=part.srt,
            video=part.video
        ))

    return segments


def calculate_chapter_based_segments(
    part: VideoPart,
    video_duration: float,
    next_part_start: float | None,
    chapters: dict
) -> list:
    """
    根据 start_chapter_name 生成带前导片段的分段
    - 如果 start_chapter_name 章节的 start_time > 0，创建前导片段 [0, start_time)
    - 主片段 [start_time, end_time) 包含 thumbnail/srt/video 标志
    """
    segments = []

    if part.start_chapter_name not in chapters:
        print(f"⚠️ 未找到章节 '{part.start_chapter_name}'")
        return segments

    start_time = chapters[part.start_chapter_name]["start_time"]

    if start_time > 0:
        segments.append(TrimSegment(
            start_time=0.0,
            end_time=start_time,
            thumbnail=False,
            srt=False,
            video=False
        ))

    end_time = video_duration
    if part.last_seconds is not None and part.last_seconds > 0:
        end_time = start_time + part.last_seconds
    elif part.end_chapter_name and part.end_chapter_name in chapters:
        end_time = chapters[part.end_chapter_name]["start_time"]
    elif next_part_start is not None:
        end_time = next_part_start

    end_time = min(end_time, video_duration)

    if end_time > start_time:
        segments.append(TrimSegment(
            start_time=start_time,
            end_time=end_time,
            thumbnail=part.thumbnail,
            srt=part.srt,
            video=part.video
        ))

    return segments


def calculate_trim_segments(context: TaskContext) -> bool:
    """
    计算所有分段的trim时间
    遍历 task.parts，根据每 part 的配置选择 Mode A 或 Mode B
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
            video=True
        ))
        return True

    is_mkv = video_path.lower().endswith('.mkv')
    chapters = get_mkv_chapters(video_path) if is_mkv else {}

    for i, part in enumerate(task.parts):
        next_part_start = None
        if i + 1 < len(task.parts):
            next_part = task.parts[i + 1]
            if next_part.start_chapter_name and next_part.start_chapter_name in chapters:
                next_part_start = chapters[next_part.start_chapter_name]["start_time"]
            elif next_part.cut_front_seconds is not None:
                next_part_start = next_part.cut_front_seconds

        if part.start_chapter_name:
            segments = calculate_chapter_based_segments(part, video_duration, next_part_start, chapters)
        else:
            segments = calculate_time_based_segments(part, video_duration)

        context.trim_segments.extend(segments)

    total_duration = sum(s.end_time - s.start_time for s in context.trim_segments)
    print(f"✅ 生成了 {len(context.trim_segments)} 个分段，总时长 {total_duration:.2f}s")

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