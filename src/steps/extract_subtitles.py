# extract_subtitles.py
import subprocess
import json
import os
from steps.base_step import BaseStep
from steps.config import VIDEO_EXTENSIONS, LANG_MAP
from steps.context import TaskContext
from steps.subtitle.subtitle_handler import (
    SubtitleHandlerFactory,
    CodecToFormatMapper,
    SubtitleHandler
)


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
        
        # 如果check_exist为True，检查最终字幕产物是否已存在，存在则直接复用
        if task.subtitle.check_exist and os.path.isfile(context.final_srt_path):
            context.srt_path = context.final_srt_path
            print(f"⏭️ 跳过字幕提取（check_exist=true，文件已存在）: {context.srt_path}")
            return True
        
        # 使用字幕语言作为过滤条件
        target_langs = LANG_MAP.get(task.subtitle.subtitle_lang.lower(), [task.subtitle.subtitle_lang.lower()])
        subtitle_lang = target_langs[1]
        target_titles = task.subtitle.target_titles
        
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
                # 重命名为最终字幕产物的canonical路径（extract_mkv_subtitles的_track命名保留给trim_video复用）
                os.replace(extracted_files[0], context.final_srt_path)
                context.srt_path = context.final_srt_path
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
