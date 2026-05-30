#!/usr/bin/env python3
# audio_trim_step.py
"""
音频修剪步骤：根据trim_segments中audio=true的片段裁剪音频
"""
import os
import subprocess
from ..base_step import BaseStep
from ..context import TaskContext


class AudioTrimStep(BaseStep):
    """音频修剪步骤，根据trim_segments中audio=true的片段裁剪并合并音频"""

    @property
    def step_name(self):
        return "音频修剪"

    def execute(self, context: TaskContext) -> bool:
        audio_path = context.audio_path
        if not audio_path or not os.path.exists(audio_path):
            print("⚠️ 跳过音频修剪：音频文件不存在")
            return True

        audio_segments = [seg for seg in context.trim_segments if seg.audio]
        if not audio_segments:
            print("⚠️ 跳过音频修剪：没有标记为audio=true的片段")
            return True

        if len(audio_segments) == 1:
            segment = audio_segments[0]
            if segment.start_time == 0.0 and segment.end_time >= self._get_audio_duration(audio_path):
                print("⚠️ 跳过音频修剪：整个音频都需要保留")
                return True

        output_path = self._trim_audio_by_segments(audio_path, audio_segments, context.audio_dir)
        if output_path:
            context.audio_path = output_path
            return True
        
        context.error_msg = "音频修剪失败"
        return False

    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频文件时长"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", audio_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)
            return float(data.get('format', {}).get('duration', 0.0))
        except Exception as e:
            print(f"❌ 获取音频时长失败: {e}")
            return 0.0

    def _trim_audio_by_segments(self, audio_path: str, segments: list, output_dir: str) -> str | None:
        """根据多个片段裁剪并合并音频"""
        import tempfile
        
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        ext = os.path.splitext(audio_path)[1]
        output_path = os.path.join(output_dir, f"{base_name}_trimmed{ext}")
        
        if len(segments) == 1:
            segment = segments[0]
            adjusted_start = segment.start_time - segment.offset
            adjusted_end = segment.end_time - segment.offset
            return self._trim_single_segment(audio_path, adjusted_start, adjusted_end, output_path)
        else:
            return self._trim_and_concatenate(audio_path, segments, output_path)

    def _trim_single_segment(self, audio_path: str, start_time: float, end_time: float, output_path: str) -> str | None:
        """修剪单个片段"""
        cmd = [
            'ffmpeg', '-y',
            '-i', audio_path,
            '-ss', str(start_time),
            '-to', str(end_time),
            '-acodec', 'copy',
            output_path
        ]
        
        print(f"✂️ 修剪音频片段: {start_time:.2f}s - {end_time:.2f}s")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if os.path.exists(output_path):
                print(f"✅ 音频修剪完成: {output_path}")
                return output_path
            else:
                print("❌ 错误：命令执行成功但未找到输出文件")
                return None
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 报错: {e.stderr}")
            return None

    def _trim_and_concatenate(self, audio_path: str, segments: list, output_path: str) -> str | None:
        """修剪多个片段并合并"""
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_files = []
            
            for i, segment in enumerate(segments):
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}{os.path.splitext(audio_path)[1]}")
                adjusted_start = segment.start_time - segment.offset
                adjusted_end = segment.end_time - segment.offset
                if not self._trim_single_segment(audio_path, adjusted_start, adjusted_end, segment_path):
                    return None
                segment_files.append(segment_path)
            
            list_file = os.path.join(temp_dir, "segments.txt")
            with open(list_file, 'w', encoding='utf-8') as f:
                for sf in segment_files:
                    # 先处理路径，把反斜杠换成斜杠
                    safe_path = sf.replace('\\', '/')

                    # 再写入，直接使用处理好的变量
                    f.write(f"file '{safe_path}'\n")
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-acodec', 'copy',
                output_path
            ]
            
            print("🔗 合并音频片段...")
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                if os.path.exists(output_path):
                    print(f"✅ 音频合并完成: {output_path}")
                    return output_path
                else:
                    print("❌ 错误：合并命令执行成功但未找到输出文件")
                    return None
            except subprocess.CalledProcessError as e:
                print(f"❌ FFmpeg 合并报错: {e.stderr}")
                return None