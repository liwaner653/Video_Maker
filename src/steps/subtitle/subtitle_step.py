import subprocess
import os
from typing import Optional

from steps.base_step import BaseStep
from steps.context import TaskContext

ERROR_SRT_FILE_SIZE_KB = 20.0  # 字幕文件小于20KB视为生成失败


class SubtitleStep(BaseStep):
    @property
    def step_name(self):
        return "字幕生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task

        # 如果check_exist为True，检查输出目录中是否存在同名字幕文件
        if task.subtitle and task.subtitle.check_exist:
            existing_srt = self._find_existing_subtitle(task.video_path, context.subtitle_dir)
            if existing_srt:
                print(f"✅ 检测到已存在的字幕文件：{existing_srt}")
                context.srt_path = existing_srt
                return True

        # 如果已有字幕路径（从 ExtractSubtitlesStep），直接使用
        if context.srt_path:
            print(f"✅ 使用已提取的字幕：{context.srt_path}")
            return True

        # 没有现成的字幕，使用 Whisper 生成
        srt_path = generate_subtitles(
            audio_path=context.audio_path,
            output_dir=context.subtitle_dir,
            model='turbo',
            subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
        )

        if srt_path:
            context.srt_path = srt_path
        else:
            print("⚠️ 字幕生成失败或文件无效，将跳过字幕烧录。")
            context.srt_path = ""
        return True

    def _find_existing_subtitle(self, video_path: str, output_dir: str) -> Optional[str]:
        """
        查找输出目录中是否存在与视频文件同名的字幕文件

        :param video_path: 视频文件路径
        :param output_dir: 输出目录
        :return: 存在则返回完整路径，否则返回None
        """
        if not os.path.exists(output_dir):
            return None

        video_name = os.path.basename(video_path)
        name_no_ext = os.path.splitext(video_name)[0]

        # 尝试.srt格式（最常见）
        srt_file = os.path.join(output_dir, name_no_ext + ".srt")
        if os.path.isfile(srt_file):
            return srt_file

        # 尝试其他字幕格式
        subtitle_extensions = ['.ass', '.ssa', '.sub', '.vtt']
        for ext in subtitle_extensions:
            subtitle_file = os.path.join(output_dir, name_no_ext + ext)
            if os.path.isfile(subtitle_file):
                return subtitle_file

        return None


def generate_subtitles(audio_path: str, output_dir: str, model: str = "turbo", subtitle_lang: str = "de"):
    """
    使用Whisper生成指定语言的字幕
    :param audio_path: 音频文件路径
    :param output_dir: 字幕输出目录
    :param model: Whisper模型（默认turbo）
    :param subtitle_lang: 字幕语言（默认de，德语）
    :return: 生成的字幕文件路径，失败返回None
    """
    if not os.path.exists(audio_path):
        print(f"错误：音频文件不存在 {audio_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)

    # 生成字幕文件名
    audio_name = os.path.basename(audio_path)
    srt_name = os.path.splitext(audio_name)[0] + '.srt'
    srt_path = os.path.join(output_dir, srt_name)

    # 构建whisper命令
    command = [
        'whisper', audio_path,
        '--model', model,
        '--language', subtitle_lang,
        '--output_format', 'srt',
        '--output_dir', output_dir
    ]

    print(f"开始生成字幕：{audio_name} (语言：{subtitle_lang})")
    print(f"执行命令: {' '.join(command)}")

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)

        # 校验文件大小
        if os.path.exists(srt_path):
            file_size_kb = os.path.getsize(srt_path) / 1024.0
            if file_size_kb < ERROR_SRT_FILE_SIZE_KB:
                print(f"❌ 字幕生成失败：文件大小仅为 {file_size_kb:.2f}KB (小于{ERROR_SRT_FILE_SIZE_KB}KB)")
                return None

        print(f"✅ 字幕生成完成：{srt_path}")
        return srt_path
    except FileNotFoundError:
        print("❌ Whisper 未安装或不在 PATH 中。请安装 OpenAI Whisper：pip install openai-whisper")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ 字幕生成失败：{e.stderr}")
        return None
