# extract_subtitles.py
import subprocess
import json
import os
import re
from datetime import timedelta
from steps.base_step import BaseStep
from steps.context import TaskContext
from steps.subtitle.subtitle_handler import (
    SubtitleHandlerFactory,
    CodecToFormatMapper,
    SubtitleHandler
)

# 定义支持的视频文件后缀，用于在文件夹模式下过滤非视频文件
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.ts'}


def get_target_subtitle_indices(video_path: str, target_lang: str = "", target_title: list = None) -> list:
    """
    获取视频中符合指定语言和标题关键字的字幕轨道索引。
    
    Args:
        video_path: 视频文件的完整路径
        target_lang: 目标语言关键字（不区分大小写，如 'ger', 'chi', 'eng'）
        target_title: 目标标题关键字列表，采用OR逻辑：
                     - None或空列表：不过滤标题
                     - 非空列表：匹配列表中任意一个关键字（不区分大小写）
        
    Returns:
        list: 符合条件的轨道索引列表
    """
    if target_title is None:
        target_title = []
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 's',
        '-show_entries', 'stream=index,codec_name:stream_tags=language,title',
        '-of', 'json',
        video_path
    ]
    
    matching_indices = []
    
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding='utf-8')
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        
        if not streams:
            print(f"  ⚠️ 无字幕: {os.path.basename(video_path)}")
            return matching_indices

        for stream in streams:
            index = stream.get('index')
            tags = stream.get('tags', {})
            
            # 获取语言和标题，转为小写以实现不区分大小写的匹配
            language = tags.get('language', 'und').lower()
            title = tags.get('title', '').lower()
            codec = stream.get('codec_name', '未知')
            
            # 校验逻辑：如果用户输入了条件，则必须包含该关键字；如果为空，则默认该条件通过
            lang_match = (not target_lang) or (target_lang.lower() in language)
            
            # target_title 为列表，采用OR逻辑：至少匹配一个关键字
            title_match = (not target_title) or any(kw.lower() in title for kw in target_title)
            
            if lang_match and title_match:
                matching_indices.append(index)
                print(f"  ✅ 找到匹配轨道 -> 索引: {index} | 语言: {tags.get('language', 'und')} | 名称: {tags.get('title', '无')} | 格式: {codec}")

    except subprocess.CalledProcessError as e:
        print(f"  ❌ ffprobe 处理失败: {os.path.basename(video_path)}\n  错误信息: {e.stderr.strip()}")
    except json.JSONDecodeError:
        print(f"  ❌ JSON 解析失败: {os.path.basename(video_path)}")
        
    return matching_indices


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


def extract_mkv_subtitles(video_path, output_dir, target_track_indices=None):
    """
    分析 MKV 视频并提取所有文本字幕轨。根据字幕编码格式输出不同的文件后缀。
    支持 SRT、ASS、VTT 等多种格式。
    
    :param video_path: 视频文件路径
    :param output_dir: 输出目录
    :param target_track_indices: 要提取的轨道索引列表
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
        # ffmpeg_format, file_ext = CodecToFormatMapper.get_output_format_and_ext(codec_name)
        ffmpeg_format, file_ext = 'srt', 'srt'  # 目前统一输出为SRT格式，后续可根据需要调整

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
            
            # 清除 SRT 字幕中的样式标签
            print(f"      🧹  正在清除字幕样式...")
            handler = SubtitleHandlerFactory.get_handler(output_file)
            if handler:
                handler.clean_styles()
            
            extracted_files.append(output_file)
        except subprocess.CalledProcessError:
            print(f"   ❌ 提取失败: 流 {stream_index} ({codec_name})")

    return extracted_files


def process_path(input_path: str, target_lang: str, target_title: list = None):
    """
    处理用户输入的路径（文件或文件夹）
    """
    if target_title is None:
        target_title = []
    
    if os.path.isfile(input_path):
        # 如果是单一文件，直接判断后缀并处理
        ext = os.path.splitext(input_path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            print(f"\n正在分析文件: {os.path.basename(input_path)}")
            get_target_subtitle_indices(input_path, target_lang, target_title)
        else:
            print(f"❌ 提示：文件 '{input_path}' 不是支持的视频格式。")
            
    elif os.path.isdir(input_path):
        # 如果是文件夹，遍历其中的文件
        print(f"\n📁 正在扫描文件夹: {input_path}")
        video_files = []
        
        for root, _, files in os.walk(input_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in VIDEO_EXTENSIONS:
                    video_files.append(os.path.join(root, file))
                    
        if not video_files:
            print("⚠️ 文件夹中未找到支持的视频文件。")
            return
            
        print(f"共发现 {len(video_files)} 个视频文件，开始批量分析...\n")
        print("-" * 50)
        
        for i, video_file in enumerate(video_files, 1):
            print(f"[{i}/{len(video_files)}] 正在分析: {os.path.basename(video_file)}")
            get_target_subtitle_indices(video_file, target_lang, target_title)
            print("-" * 50)
    else:
        print(f"❌ 错误：找不到文件或路径无效 '{input_path}'")


class ExtractSubtitlesStep(BaseStep):
    """获取字幕轨道索引并提取字幕"""
    
    @property
    def step_name(self) -> str:
        return "提取字幕"
    
    def execute(self, context: TaskContext) -> bool:
        """
        获取视频中符合字幕语言的SRT字幕轨道索引并提取字幕
        将第一个匹配的索引存储到 context.srt_stream_index
        如果提取成功，将文件路径存储到 context.srt_path
        """
        task = context.task
        
        if not task.subtitle:
            # 没有字幕配置，默认索引为-1
            context.srt_stream_index = -1
            return True
        
        # 使用字幕语言作为过滤条件
        subtitle_lang = task.subtitle.subtitle_lang
        target_titles = ['cc', 'sdh', 'Dub']
        
        matching_indices = get_target_subtitle_indices(
            video_path=task.video_path,
            target_lang=subtitle_lang,
            target_title=target_titles
        )
        
        if matching_indices:
            # 取第一个匹配的索引
            context.srt_stream_index = matching_indices[0]
            print(f"✅ 找到字幕轨道：索引 {context.srt_stream_index}")
            
            # 提取字幕
            extracted_files = extract_mkv_subtitles(
                task.video_path,
                context.subtitle_dir,
                [context.srt_stream_index]
            )
            
            if extracted_files:
                context.srt_path = extracted_files[0]
                print(f"✅ 字幕提取成功：{context.srt_path}")
            else:
                context.srt_path = ""
                print(f"⚠️ 字幕提取失败，将使用Whisper生成")
        else:
            # 未找到匹配的字幕，默认索引为-1（将使用Whisper生成）
            context.srt_stream_index = -1
            print(f"ℹ️ 未找到{subtitle_lang}语言的SRT字幕，将使用Whisper生成")
        
        return True


if __name__ == "__main__":
    print("=== 🎬 视频字幕轨道提取工具 (支持批量与过滤) ===")
    
    # 1. 获取路径
    user_input = input("请输入视频文件或文件夹的完整路径: ").strip().strip('"\'')
    
    # 2. 获取过滤条件
    print("\n-- 设置过滤条件 (直接回车表示不限制) --")
    target_lang = input("请输入目标语言关键字 (例如: ger, chi, eng): ").strip()
    target_title_input = input("请输入目标名称关键字 (例如: forced, 简体，多个关键字用逗号分隔): ").strip()
    
    # 将用户输入的字符串转换为列表
    target_titles = [kw.strip() for kw in target_title_input.split(',')] if target_title_input else []
    
    # 3. 开始处理
    process_path(user_input, target_lang, target_titles)
