#!/usr/bin/env python3
# calc_trim_time.py
"""
计算视频剪辑的开始和结束时间
1. 若视频是MKV且begin_chapter和end_chapter非空，则从章节信息中获取时间点
2. 否则，若cut_front_seconds和cut_back_seconds非零，则按原有规则计算
"""
import os
import json
import subprocess
from .base_step import BaseStep
from .context import TaskContext
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


def calculate_trim_times(context: TaskContext) -> bool:
    """
    根据配置计算视频的剪辑开始和结束时间，并更新TaskContext
    
    优先级：
    1. 如果是MKV且指定了begin_chapter/end_chapter，使用章节时间
    2. 否则使用cut_front_seconds/cut_back_seconds的规则
    
    返回True表示计算成功，False表示出错
    """
    task = context.task
    video_path = task.video_path
    trim = task.trim
    
    if not trim:
        context.trim_start_time = 0.0
        context.trim_end_time = get_video_duration(video_path)
        return True
    
    # 检查是否是MKV且指定了章节
    is_mkv = video_path.lower().endswith('.mkv')
    has_chapter = trim.begin_chapter or trim.end_chapter
    
    if is_mkv and has_chapter:
        # 使用章节模式
        print(f"📖 正在从MKV章节中提取时间点...")
        chapters = get_mkv_chapters(video_path)
        
        if not chapters:
            print(f"⚠️ 未找到任何章节信息，将使用cut_seconds规则")
            return calculate_trim_times_by_seconds(context)
        
        # 尝试获取开始章节时间
        start_time = 0.0
        if trim.begin_chapter:
            if trim.begin_chapter in chapters:
                start_time = chapters[trim.begin_chapter]["start_time"]
                print(f"   ✔️ 开始章节 '{trim.begin_chapter}': {start_time:.2f}s")
            else:
                print(f"   ❌ 未找到开始章节 '{trim.begin_chapter}'")
                print(f"   📋 可用章节: {', '.join(chapters.keys())}")
                return False
        
        # 尝试获取结束章节时间
        end_time = get_video_duration(video_path)
        if trim.end_chapter:
            if trim.end_chapter in chapters:
                end_time = chapters[trim.end_chapter]["end_time"]
                print(f"   ✔️ 结束章节 '{trim.end_chapter}': {end_time:.2f}s")
            else:
                print(f"   ❌ 未找到结束章节 '{trim.end_chapter}'")
                print(f"   📋 可用章节: {', '.join(chapters.keys())}")
                return False
        
        if start_time >= end_time:
            print(f"❌ 错误：开始时间({start_time:.2f}s) >= 结束时间({end_time:.2f}s)")
            return False
        
        context.trim_start_time = start_time
        context.trim_end_time = end_time
        print(f"✅ 剪辑时间范围: {start_time:.2f}s - {end_time:.2f}s")
        return True
    else:
        # 使用cut_seconds规则
        return calculate_trim_times_by_seconds(context)


def calculate_trim_times_by_seconds(context: TaskContext) -> bool:
    """
    根据cut_front_seconds和cut_back_seconds计算剪辑时间
    """
    task = context.task
    video_path = task.video_path
    trim = task.trim
    
    video_duration = get_video_duration(video_path)
    
    if video_duration <= 0:
        print(f"❌ 无法获取视频时长")
        return False
    
    cut_front = trim.cut_front_seconds if trim else 0.0
    cut_back = trim.cut_back_seconds if trim else 0.0
    
    start_time = cut_front
    end_time = video_duration - cut_back if cut_back > 0 else video_duration
    
    if start_time >= end_time:
        print(f"❌ 错误：开始裁剪时间({cut_front:.2f}s) + 结束裁剪时间({cut_back:.2f}s) 超过视频总时长({video_duration:.2f}s)")
        return False
    
    context.trim_start_time = start_time
    context.trim_end_time = end_time
    
    if cut_front > 0 or cut_back > 0:
        print(f"✅ 剪辑时间范围: {start_time:.2f}s - {end_time:.2f}s (开头裁{cut_front:.2f}s, 结尾裁{cut_back:.2f}s)")
    else:
        print(f"✅ 剪辑时间范围: {start_time:.2f}s - {end_time:.2f}s (无裁剪)")
    
    return True


class CalcTrimTimeStep(BaseStep):
    """计算视频剪辑时间的步骤"""
    
    @property
    def step_name(self):
        return "计算剪辑时间"
    
    def execute(self, context: TaskContext) -> bool:
        """执行剪辑时间计算"""
        try:
            if calculate_trim_times(context):
                return True
            else:
                context.error_msg = "剪辑时间计算失败"
                return False
        except Exception as e:
            context.error_msg = f"剪辑时间计算异常: {e}"
            print(f"❌ {context.error_msg}")
            return False
