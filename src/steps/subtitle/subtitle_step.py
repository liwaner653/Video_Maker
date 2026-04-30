
from datetime import timedelta
import json
import os
import re
import subprocess
import sys
from typing import Optional

from steps.base_step import BaseStep
from steps.context import TaskContext
from steps.util import get_video_duration
from steps.subtitle.subtitle_handler import (
    SubtitleHandlerFactory,
    CodecToFormatMapper,
    SubtitleHandler
)

sys.stdout.reconfigure(encoding='utf-8')

ERROR_SRT_FILE_SIZE_KB = 20.0  # 字幕文件小于20KB视为生成失败

class SubtitleStep(BaseStep):
    @property
    def step_name(self): return "字幕生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        # 使用TaskContext中的修剪时间
        start_time = context.trim_start_time
        end_time = context.trim_end_time
        srt_index = context.srt_stream_index

        # 如果check_exist为True，检查输出目录中是否存在同名字幕文件
        if task.subtitle and task.subtitle.check_exist:
            existing_srt = self._find_existing_subtitle(task.video_path, context.subtitle_dir)
            if existing_srt:
                print(f"✅ 检测到已存在的字幕文件：{existing_srt}")
                context.srt_path = existing_srt
                return True

        if srt_index < 0:
            srt_path = generate_subtitles(
                audio_path=context.audio_path,
                output_dir=context.subtitle_dir,
                model='turbo',
                subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
            )
        else:
            subtitles = extract_mkv_subtitles(task.video_path, context.subtitle_dir, [srt_index], start_time, end_time)
            srt_path = subtitles[0] if subtitles else None

        # 需求6：如果字幕生成失败或被判断为无效，不中断，赋空值继续
        if srt_path:
            context.srt_path = srt_path
        else:
            print("⚠️ 字幕处理失败或文件无效，将跳过字幕烧录。")
            context.srt_path = "" 
        return True # 始终返回True，允许后续合成执行
    
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


def extract_pgs_subtitles(video_path, output_dir, target_track_indices=None):
    """
    提取图像类字幕（如 hdmv_pgs_subtitle）为 .sup 格式文件。
    注意：.sup 是图像格式，若要转为 .srt 需要使用第三方 OCR 工具 (如 SubtitleEdit)。
    """
    if not os.path.isfile(video_path):
        return None

    os.makedirs(output_dir, exist_ok=True)
    
    ffprobe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_name",
        "-select_streams", "s", "-of", "json", video_path
    ]
    
    result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    
    extracted_files = []
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    
    for stream in streams:
        idx = stream.get("index")
        codec = stream.get("codec_name")
        
        if codec == "hdmv_pgs_subtitle":
            if target_track_indices and idx not in target_track_indices:
                continue
                
            output_file = os.path.join(output_dir, f"{video_basename}_track{idx}.sup")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-i", video_path,
                "-map", f"0:{idx}",
                "-c:s", "copy",  # 直接拷贝图像流
                output_file
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True)
                print(f"   ✔️ PGS提取完成(请使用OCR转SRT): {output_file}")
                extracted_files.append(output_file)
            except subprocess.CalledProcessError:
                print(f"   ❌ 提取PGS失败: 流 {idx}")
                
    return extracted_files

def adjust_srt_timestamps(srt_path, start_time, end_time):
    """
    读取 SRT 文件并根据时间范围调整时间轴。
    :param srt_path: SRT文件路径
    :param start_time: 范围开始时间（秒）
    :param end_time: 范围结束时间（秒）
    """
    if start_time <= 0 and end_time <= 0:
        return

    front_td = timedelta(seconds=start_time)
    end_threshold_s = end_time if end_time > 0 else float('inf')
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = re.split(r'\n\n+', content.strip())
    new_blocks = []
    new_index = 1

    def parse_time(time_str):
        h, m, s_ms = time_str.split(':')
        s, ms = s_ms.split(',')
        return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))

    def format_time(td):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = int(td.microseconds / 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            times = lines[1].split(' --> ')
            if len(times) != 2:
                continue
            
            try:
                start_td = parse_time(times[0].strip())
                end_td = parse_time(times[1].strip())
            except Exception:
                continue

            # --- 结尾限制逻辑 ---
            # 如果字幕的开始时间已经超过了保留部分的截止点，直接舍弃
            if end_time > 0 and start_td.total_seconds() >= end_threshold_s:
                continue
            # 如果字幕横跨了截止点，将其结束时间缩减至截止点
            if end_time > 0 and end_td.total_seconds() > end_threshold_s:
                end_td = timedelta(seconds=end_threshold_s)

            # --- 开头限制逻辑 ---
            # 减去开头的偏移量
            start_td -= front_td
            end_td -= front_td

            # 如果在开头限制后，该句字幕结束时间小于0，跳过
            if end_td.total_seconds() < 0:
                continue
            # 如果开始时间小于0，置为0
            if start_td.total_seconds() < 0:
                start_td = timedelta(seconds=0)

            # 重组字幕块
            new_lines = [
                str(new_index),
                f"{format_time(start_td)} --> {format_time(end_td)}"
            ]
            new_lines.extend(lines[2:])
            new_blocks.append('\n'.join(new_lines))
            new_index += 1

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(new_blocks) + '\n')


def _adjust_subtitle_timestamps(subtitle_path: str, start_time: float, end_time: float) -> None:
    """
    根据文件格式自动选择处理器并调整字幕时间戳
    :param subtitle_path: 字幕文件路径
    :param start_time: 开始时间（秒）
    :param end_time: 结束时间（秒）
    """
    handler = SubtitleHandlerFactory.get_handler(subtitle_path)
    if handler:
        handler.adjust_timestamps(start_time, end_time)
    else:
        print(f"   ⚠️ 不支持的字幕格式，跳过时间调整")


def extract_mkv_subtitles(video_path, output_dir, target_track_indices=None, start_time=0.0, end_time=0.0):
    """
    分析 MKV 视频并提取所有文本字幕轨。根据字幕编码格式输出不同的文件后缀。
    支持 SRT、ASS、VTT 等多种格式，并支持时间范围限制。
    
    :param video_path: 视频文件路径
    :param output_dir: 输出目录
    :param target_track_indices: 要提取的轨道索引列表
    :param start_time: 提取的开始时间（秒）
    :param end_time: 提取的结束时间（秒），0表示到末尾
    :return: 提取的字幕文件列表
    """
    if not os.path.isfile(video_path):
        print(f"❌ 错误: 找不到文件 {video_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)

    print(f"正在分析视频: {video_path} ...\n")
    
    ffprobe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_name:stream_tags=language,title",
        "-select_streams", "s", "-of", "json", video_path
    ]

    try:
        result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        probe_data = json.loads(result.stdout)
    except Exception as e:
        print(f"❌ 解析视频失败: {e}")
        return None

    streams = probe_data.get("streams", [])
    if not streams:
        print("ℹ️ 在此视频中未找到任何字幕轨。")
        return None

    if target_track_indices is not None:
        streams = [s for s in streams if s.get("index") in target_track_indices]
    
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    extracted_files = []

    for stream in streams:
        stream_index = stream.get("index")
        codec_name = stream.get("codec_name", "unknown")
        tags = stream.get("tags", {})
        language = tags.get("language", "und")
        
        # 跳过图像类字幕格式
        if CodecToFormatMapper.is_image_based_format(codec_name):
            print(f"   ⏭️ 跳过图像类字幕轨（{codec_name}）: 流 {stream_index}")
            continue
        
        # 根据编码获取输出格式和文件后缀
        ffmpeg_format, file_ext = CodecToFormatMapper.get_output_format_and_ext(codec_name)
        
        output_filename = f"{video_basename}_track{stream_index}.{file_ext}"
        output_file = os.path.join(output_dir, output_filename)

        # 构建 FFmpeg 命令
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", video_path,
            "-map", f"0:{stream_index}",
            "-c:s", ffmpeg_format, output_file
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            print(f"   ✔️ 提取完成 ({codec_name}): {output_file}")
            
            # 处理时间范围限制
            if start_time > 0 or end_time > 0:
                print(f"      ⏱️ 正在调整字幕时间轴...")
                _adjust_subtitle_timestamps(output_file, start_time, end_time)
            
            extracted_files.append(output_file)
        except subprocess.CalledProcessError:
            print(f"   ❌ 提取失败: 流 {stream_index} ({codec_name})")

    return extracted_files

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
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        
        # 【新增代码：校验文件大小】
        if os.path.exists(srt_path):
            file_size_kb = os.path.getsize(srt_path) / 1024.0
            if file_size_kb < ERROR_SRT_FILE_SIZE_KB:
                print(f"❌ 字幕生成失败：文件大小仅为 {file_size_kb:.2f}KB (小于{ERROR_SRT_FILE_SIZE_KB}KB)")
                return None  # 按照需求返回失败(None)
                
        print(f"✅ 字幕生成完成：{srt_path}")
        return srt_path
    except FileNotFoundError:
        print("❌ Whisper 未安装或不在 PATH 中。请安装 OpenAI Whisper：pip install openai-whisper")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ 字幕生成失败：{e.stderr}")
        return None