#!/usr/bin/env python3
# video_trim_step.py
import os
import subprocess
import tempfile
from .base_step import BaseStep
from .context import TaskContext


def trim_video_segments(context: TaskContext) -> str | None:
    video_path = context.task.video_path
    if not os.path.exists(video_path):
        print(f"❌ 原视频文件不存在: {video_path}")
        return None

    audio_segments = [seg for seg in context.trim_segments if seg.audio]
    if not audio_segments:
        print("❌ 没有找到 audio=true 的分段")
        return None

    output_dir = context.final_video_dir
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    trimmed_video_path = os.path.join(output_dir, f"{base_name}_trimmed.mp4").replace('\\', '/')

    if len(audio_segments) == 1:
        seg = audio_segments[0]
        command = [
            'ffmpeg', '-y',
            '-ss', str(seg.start_time),
            '-to', str(seg.end_time),
            '-i', video_path.replace('\\', '/'),
            '-c:v', 'copy',
            '-an',
            trimmed_video_path
        ]
        print(f"📽️ 裁剪单个片段: [{seg.start_time:.2f}s -> {seg.end_time:.2f}s]")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            if os.path.exists(trimmed_video_path):
                print(f"✅ 成功生成裁剪视频: {trimmed_video_path}")
                return trimmed_video_path
            else:
                print("❌ 错误：命令执行成功但未找到输出文件")
                return None
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 裁剪报错: {e.stderr}")
            return None
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_files = []
            concat_list_path = os.path.join(temp_dir, 'segments.txt').replace('\\', '/')

            for i, seg in enumerate(audio_segments):
                segment_path = os.path.join(temp_dir, f"segment_{i}.mp4").replace('\\', '/')
                command = [
                    'ffmpeg', '-y',
                    '-ss', str(seg.start_time),
                    '-to', str(seg.end_time),
                    '-i', video_path.replace('\\', '/'),
                    '-c:v', 'copy',
                    '-an',
                    segment_path
                ]
                try:
                    subprocess.run(command, check=True, capture_output=True, text=True)
                    if os.path.exists(segment_path):
                        segment_files.append(segment_path)
                        print(f"✅ 裁剪片段 {i+1}: [{seg.start_time:.2f}s -> {seg.end_time:.2f}s]")
                    else:
                        print(f"❌ 片段 {i+1} 裁剪失败")
                        return None
                except subprocess.CalledProcessError as e:
                    print(f"❌ FFmpeg 裁剪片段 {i+1} 报错: {e.stderr}")
                    return None

            with open(concat_list_path, 'w', encoding='utf-8') as f:
                for seg_file in segment_files:
                    f.write(f"file '{seg_file}'\n")

            concat_command = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list_path,
                '-c:v', 'copy',
                trimmed_video_path
            ]
            print("🔗 拼接片段...")
            try:
                subprocess.run(concat_command, check=True, capture_output=True, text=True)
                if os.path.exists(trimmed_video_path):
                    print(f"✅ 成功拼接视频: {trimmed_video_path}")
                    return trimmed_video_path
                else:
                    print("❌ 错误：拼接命令执行成功但未找到输出文件")
                    return None
            except subprocess.CalledProcessError as e:
                print(f"❌ FFmpeg 拼接报错: {e.stderr}")
                return None


class VideoTrimStep(BaseStep):
    @property
    def step_name(self):
        return "视频画面裁剪"

    def execute(self, context: TaskContext) -> bool:
        if context.task.final_video.check_exist:
            base_name = os.path.splitext(os.path.basename(context.task.video_path))[0]
            expected_path = os.path.join(context.final_video_dir, f"{base_name}_trimmed.mp4")
            if os.path.exists(expected_path):
                print(f"⏭️ 跳过视频裁剪（check_exist=true，文件已存在）: {expected_path}")
                context.trimmed_video_path = expected_path.replace('\\', '/')
                return True

        trimmed_path = trim_video_segments(context)
        if trimmed_path:
            context.trimmed_video_path = trimmed_path
            return True
        context.error_msg = "视频画面裁剪失败"
        return False