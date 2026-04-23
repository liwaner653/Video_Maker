
from datetime import timedelta
import json
import os
import re
import subprocess
import sys

from steps.base_step import BaseStep
from steps.context import TaskContext
from steps.util import get_video_duration

sys.stdout.reconfigure(encoding='utf-8')

ERROR_SRT_FILE_SIZE_KB = 20.0  # 字幕文件小于20KB视为生成失败

class SubtitleStep(BaseStep):
    @property
    def step_name(self): return "字幕生成"

    def execute(self, context: TaskContext) -> bool:
        task = context.task
        cf, cb = (task.trim.cut_front_seconds, task.trim.cut_back_seconds) if task.trim else (0.0, 0.0)
        srt_index = context.srt_stream_index

        if srt_index < 0:
            srt_path = generate_subtitles(
                audio_path=context.audio_path,
                output_dir=context.subtitle_dir,
                model='turbo',
                subtitle_lang=task.subtitle.subtitle_lang if task.subtitle else "de"
            )
        else:
            subtitles = extract_mkv_subtitles(task.video_path, context.subtitle_dir, [srt_index], cf, cb)
            srt_path = subtitles[0] if subtitles else None

        # 需求6：如果字幕生成失败或被判断为无效，不中断，赋空值继续
        if srt_path:
            context.srt_path = srt_path
        else:
            print("⚠️ 字幕处理失败或文件无效，将跳过字幕烧录。")
            context.srt_path = "" 
        return True # 始终返回True，允许后续合成执行


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

def adjust_srt_timestamps(srt_path, cut_front_seconds, cut_back_seconds, video_duration):
    """
    读取 SRT 文件并根据开头和结尾裁剪秒数调整时间轴。
    """
    if cut_front_seconds <= 0 and cut_back_seconds <= 0:
        return

    front_td = timedelta(seconds=cut_front_seconds)
    # 计算截止的时间点
    end_threshold_s = video_duration - cut_back_seconds if cut_back_seconds > 0 else video_duration
    
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

            # --- 结尾裁剪逻辑 ---
            # 如果字幕的开始时间已经超过了保留部分的截止点，直接舍弃
            if cut_back_seconds > 0 and start_td.total_seconds() >= end_threshold_s:
                continue
            # 如果字幕横跨了截止点，将其结束时间缩减至截止点
            if cut_back_seconds > 0 and end_td.total_seconds() > end_threshold_s:
                end_td = timedelta(seconds=end_threshold_s)

            # --- 开头裁剪逻辑 ---
            # 减去开头的偏移量
            start_td -= front_td
            end_td -= front_td

            # 如果在开头裁剪后，该句字幕结束时间小于0，跳过
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


def extract_mkv_subtitles(video_path, output_dir, target_track_indices=None, cut_front_seconds=0, cut_back_seconds=0):
    """
    分析 MKV 视频并提取所有文本字幕轨为 SRT 文件。支持双向裁剪时间轴。
    """
    if not os.path.isfile(video_path):
        print(f"❌ 错误: 找不到文件 {video_path}")
        return None

    os.makedirs(output_dir, exist_ok=True)
    
    # 如果需要裁剪结尾，先获取视频时长
    video_duration = 0.0
    if cut_back_seconds > 0:
        video_duration = get_video_duration(video_path)

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
        
        if codec_name in ["hdmv_pgs_subtitle", "dvd_subtitle"]:
            continue
            
        output_filename = f"{video_basename}_track{stream_index}.srt"
        output_file = os.path.join(output_dir, output_filename)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", video_path,
            "-map", f"0:{stream_index}",
            "-c:s", "srt", output_file
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True)
            
            # 处理时间轴裁剪
            if cut_front_seconds > 0 or cut_back_seconds > 0:
                print(f"   ⏱️ 正在根据裁剪参数调整字幕时间轴...")
                # 如果没获取过时长但又需要它（应对逻辑严谨性），则在此获取
                if video_duration == 0: video_duration = get_video_duration(video_path)
                adjust_srt_timestamps(output_file, cut_front_seconds, cut_back_seconds, video_duration)

            print(f"   ✔️ 提取完成: {output_file}")
            extracted_files.append(output_file)
        except subprocess.CalledProcessError:
            print(f"   ❌ 提取失败: 流 {stream_index}")

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