import os
import sys
import subprocess
import json
from datetime import timedelta
from typing import Optional, List, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steps.extract_subtitles import get_target_subtitle_indices, extract_mkv_subtitles
from steps.extract_audio.extract_audio_step import find_audio_stream_by_language
from steps.subtitle.subtitle_handler import SubtitleHandlerFactory
from trim_video.trim_video_task import TrimVideoTask, TrimSegment, TrimAudioConfig, TrimSubtitleConfig


def get_audio_stream_indices(video_path: str, target_lang: str = "") -> list:
    """获取视频中符合指定语言的音轨索引列表"""
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=index:stream_tags=language',
        '-of', 'json',
        video_path
    ]
    
    matching_indices = []
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, encoding='utf-8')
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        
        for stream in streams:
            index = stream.get('index')
            tags = stream.get('tags', {})
            language = tags.get('language', 'und').lower()
            
            if not target_lang or target_lang.lower() in language:
                matching_indices.append(index)
                print(f"  ✅ 找到音轨 -> 索引: {index} | 语言: {tags.get('language', 'und')}")
                
    except subprocess.CalledProcessError as e:
        print(f"  ❌ ffprobe 处理失败: {os.path.basename(video_path)}\n  错误信息: {e.stderr.strip()}")
    
    return matching_indices


def extract_subtitle_from_video(video_path: str, output_dir: str, target_lang: str = "") -> Optional[str]:
    """从视频中提取指定语言的字幕"""
    target_titles = ['cc', 'sdh']
    matching_indices = get_target_subtitle_indices(video_path, target_lang, target_titles)
    
    if matching_indices:
        extracted_files = extract_mkv_subtitles(video_path, output_dir, [matching_indices[0]])
        if extracted_files:
            return extracted_files[0]
    return None


def trim_video_segment(video_path: str, start_time: float, end_time: float, output_path: str, audio_stream_index: int = -1) -> bool:
    """剪辑指定时间段的视频"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    cmd = [
        'ffmpeg', '-y', '-v', 'error',
        '-i', video_path,
        '-ss', str(start_time),
        '-to', str(end_time),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-pix_fmt', 'yuv420p'
    ]
    
    if audio_stream_index >= 0:
        cmd.extend(['-map', f'0:v', '-map', f'0:a:{audio_stream_index}', '-c:a', 'copy'])
    else:
        cmd.extend(['-c:a', 'copy'])
    
    cmd.append(output_path)
    
    print(f"✂️ 剪辑视频: {start_time:.2f}s -> {end_time:.2f}s")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if os.path.exists(output_path):
            print(f"✅ 视频剪辑完成: {output_path}")
            return True
        else:
            print(f"❌ 视频剪辑失败：输出文件不存在")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 报错: {e.stderr}")
        return False


def adjust_subtitle_timestamps(srt_path: str, start_time: float, end_time: float) -> None:
    """调整字幕时间戳，提取指定时间段内的字幕并重新计时"""
    handler = SubtitleHandlerFactory.get_handler(srt_path)
    if handler:
        handler.adjust_timestamps(start_time, end_time)
        print(f"✅ 字幕时间戳调整完成")
    else:
        print(f"⚠️ 不支持的字幕格式")


def burn_subtitle_to_video(video_path: str, srt_path: str, output_path: str) -> bool:
    """将字幕烧入视频"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    safe_srt_path = srt_path.replace('\\', '/').replace(':', r'\:').replace("'", "\\'")
    
    cmd = [
        'ffmpeg', '-y', '-v', 'error',
        '-i', video_path,
        '-vf', f"subtitles='{safe_srt_path}':force_style='FontName=SimHei,FontSize=24,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Shadow=2,MarginV=20'",
        '-c:a', 'copy',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        output_path
    ]
    
    print(f"🔥 烧入字幕到视频")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if os.path.exists(output_path):
            print(f"✅ 字幕烧入完成: {output_path}")
            return True
        else:
            print(f"❌ 字幕烧入失败：输出文件不存在")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 报错: {e.stderr}")
        return False


def process_trim_task(task: TrimVideoTask) -> Optional[str]:
    """处理单个视频剪辑任务"""
    video_path = task.video_path
    if not os.path.exists(video_path):
        print(f"❌ 视频文件不存在: {video_path}")
        return None
    
    # 确定输出目录
    output_dir = task.output_dir if task.output_dir else os.path.dirname(video_path)
    os.makedirs(output_dir, exist_ok=True)
    
    video_basename = os.path.splitext(os.path.basename(video_path))[0]
    
    # 确定音轨索引
    audio_stream_index = task.audio.audio_stream_index
    if task.audio.enabled and audio_stream_index < 0 and task.audio.language:
        audio_stream_index = find_audio_stream_by_language(video_path, task.audio.language)
        print(f"🎵 自动检测音轨索引: {audio_stream_index}")
    
    # 处理每个片段
    output_files = []
    for i, segment in enumerate(task.segments):
        segment_name = segment.name if segment.name else f"segment_{i+1:03d}"
        temp_video_path = os.path.join(output_dir, f"{video_basename}_{segment_name}_temp.mp4")
        final_output_path = os.path.join(output_dir, f"{video_basename}_{segment_name}.{task.output_format}")
        
        # 1. 剪辑视频片段
        if not trim_video_segment(video_path, segment.start_time, segment.end_time, temp_video_path, audio_stream_index):
            continue
        
        # 2. 提取并调整字幕
        srt_path = None
        if task.subtitle.enabled:
            subtitle_dir = os.path.join(output_dir, "subtitles")
            os.makedirs(subtitle_dir, exist_ok=True)
            
            # 提取字幕
            if task.subtitle.subtitle_stream_index >= 0:
                extracted_files = extract_mkv_subtitles(video_path, subtitle_dir, [task.subtitle.subtitle_stream_index])
                if extracted_files:
                    srt_path = extracted_files[0]
            else:
                srt_path = extract_subtitle_from_video(video_path, subtitle_dir, task.subtitle.language)
            
            # 调整字幕时间戳
            if srt_path:
                adjust_subtitle_timestamps(srt_path, segment.start_time, segment.end_time)
        
        # 3. 烧入字幕（如果需要）
        if task.subtitle.burn_in and srt_path and os.path.exists(srt_path):
            burn_subtitle_to_video(temp_video_path, srt_path, final_output_path)
            os.remove(temp_video_path)
        else:
            import shutil
            shutil.move(temp_video_path, final_output_path)
        
        output_files.append(final_output_path)
        print(f"🎬 片段 [{segment_name}] 处理完成")
    
    return output_files[0] if output_files else None


def load_trim_tasks(json_path: str) -> List[TrimVideoTask]:
    """从JSON文件加载剪辑任务"""
    tasks = []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for item in data:
                tasks.append(_parse_task(item))
        elif isinstance(data, dict):
            tasks.append(_parse_task(data))
        
        print(f"✅ 加载 {len(tasks)} 个剪辑任务")
    except Exception as e:
        print(f"❌ 加载JSON失败: {e}")
    
    return tasks


def _parse_task(data: dict) -> TrimVideoTask:
    """解析单个任务配置"""
    segments = []
    if 'segments' in data:
        for seg_data in data['segments']:
            segments.append(TrimSegment(
                start_time=float(seg_data['start_time']),
                end_time=float(seg_data['end_time']),
                name=seg_data.get('name', "")
            ))
    
    audio_config = TrimAudioConfig(
        language=data.get('audio', {}).get('language', ""),
        audio_stream_index=int(data.get('audio', {}).get('audio_stream_index', -1)),
        enabled=bool(data.get('audio', {}).get('enabled', True))
    )
    
    subtitle_config = TrimSubtitleConfig(
        language=data.get('subtitle', {}).get('language', ""),
        subtitle_stream_index=int(data.get('subtitle', {}).get('subtitle_stream_index', -1)),
        burn_in=bool(data.get('subtitle', {}).get('burn_in', True)),
        enabled=bool(data.get('subtitle', {}).get('enabled', True))
    )
    
    return TrimVideoTask(
        video_path=data['video_path'],
        output_dir=data.get('output_dir', ""),
        segments=segments,
        audio=audio_config,
        subtitle=subtitle_config,
        output_format=data.get('output_format', 'mp4'),
        crf=int(data.get('crf', 23)),
        preset=data.get('preset', 'medium')
    )


def run_trim_from_json(json_path: str) -> None:
    """从JSON配置文件运行剪辑任务"""
    tasks = load_trim_tasks(json_path)
    
    for task in tasks:
        print(f"\n=====================================")
        print(f"📽️ 处理视频: {os.path.basename(task.video_path)}")
        print(f"=====================================")
        process_trim_task(task)


if __name__ == "__main__":
    json_path = r"D:\sysu\10_myself\8_projects\Video_Maker\src\trim_video\example_trim_config.json"
    
    print(f"📂 使用配置文件: {json_path}")
    run_trim_from_json(json_path)