#!/usr/bin/env python3
# video_merge_step.py
import os
import subprocess
import tempfile
from .base_step import BaseStep
from .context import TaskContext


def merge_video_audio_subtitle(
    trimmed_video_path: str,
    audio_path: str,
    srt_path: str,
    additional_video_path: str,
    output_dir: str,
    base_name: str
) -> str | None:
    if not os.path.exists(trimmed_video_path):
        print(f"❌ 裁剪后的视频不存在: {trimmed_video_path}")
        return None

    if not os.path.exists(audio_path):
        print(f"❌ 音频文件不存在: {audio_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)
    final_output_path = os.path.join(output_dir, f"{base_name}.mp4").replace('\\', '/')

    has_srt = srt_path and os.path.exists(srt_path)
    has_additional_video = additional_video_path and os.path.exists(additional_video_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        first_merge_path = os.path.join(temp_dir, "first_merge.mp4").replace('\\', '/')

        command = [
            'ffmpeg', '-y',
            '-i', trimmed_video_path,
            '-i', audio_path.replace('\\', '/')
        ]

        if has_srt:
            safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:').replace("'", "\\'")
            command.extend(['-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei,FontSize=16'"])

        command.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-shortest',
            first_merge_path
        ])

        print(f"📽️ 合并画面+音频{'+字幕' if has_srt else ''}...")
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            if not os.path.exists(first_merge_path):
                print("❌ 错误：第一次合并未生成输出文件")
                return None
            print("✅ 第一次合并完成")
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg 第一次合并报错: {e.stderr}")
            return None

        if has_additional_video:
            print(f"🔗 合并额外视频: {os.path.basename(additional_video_path)}")
            concat_command = [
                'ffmpeg', '-y',
                '-i', first_merge_path,
                '-i', additional_video_path.replace('\\', '/'),
                '-filter_complex',
                '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]',
                '-map', '[v]',
                '-map', '[a]',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '192k',
                final_output_path
            ]
            try:
                subprocess.run(concat_command, check=True, capture_output=True, text=True)
                if os.path.exists(final_output_path):
                    print(f"✅ 成功合并额外视频: {final_output_path}")
                    return final_output_path
                else:
                    print("❌ 错误：合并额外视频后未找到输出文件")
                    return None
            except subprocess.CalledProcessError as e:
                print(f"❌ FFmpeg 合并额外视频报错: {e.stderr}")
                return None
        else:
            os.rename(first_merge_path, final_output_path.replace('/', '\\'))
            if os.path.exists(final_output_path):
                print(f"✅ 成功生成最终视频: {final_output_path}")
                return final_output_path
            else:
                print("❌ 错误：重命名输出文件失败")
                return None


class VideoMergeStep(BaseStep):
    @property
    def step_name(self):
        return "音视频合并"

    def execute(self, context: TaskContext) -> bool:
        if context.task.final_video.check_exist:
            base_name = os.path.splitext(os.path.basename(context.task.video_path))[0]
            expected_path = os.path.join(context.final_video_dir, f"{base_name}.mp4")
            if os.path.exists(expected_path):
                print(f"⏭️ 跳过音视频合并（check_exist=true，文件已存在）: {expected_path}")
                context.final_video_path = expected_path.replace('\\', '/')
                return True

        base_name = os.path.splitext(os.path.basename(context.task.video_path))[0]
        additional_video = context.task.final_video.additional_video_path

        merged_path = merge_video_audio_subtitle(
            trimmed_video_path=context.trimmed_video_path,
            audio_path=context.audio_path,
            srt_path=context.srt_path,
            additional_video_path=additional_video,
            output_dir=context.final_video_dir,
            base_name=base_name
        )

        if merged_path:
            context.final_video_path = merged_path
            return True
        context.error_msg = "音视频合并失败"
        return False